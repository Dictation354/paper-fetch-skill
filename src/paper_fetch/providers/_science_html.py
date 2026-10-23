"""Science provider-owned browser-workflow rules."""

from __future__ import annotations

import re
import urllib.parse
import time
from typing import Any
from collections.abc import Callable, Mapping, Sequence

from bs4 import BeautifulSoup, Tag
from ..extraction.html.parsing import choose_parser


from ..quality.html_signals import (
    AAAS_DATALAYER_PATTERN,
    SCIENCE_SIGNAL_SET,
    evaluate_datalayer_blocking_signals,
    evaluate_datalayer_positive_signals,
)
from ..utils import dedupe_authors, normalize_text
from ._html_authors import (
    ATYPON_AUTHOR_COUNT_PATTERN,
    ATYPON_AUTHOR_COLLAPSE_UI_TEXT,
    ATYPON_AUTHOR_NOISE_TEXT,
    AuthorExtractionPipeline,
    AuthorStep,
    extract_property_authors,
    normalized_author_tokens,
)
from ._html_references import (
    NUMBERED_BIBLIOGRAPHY_SELECTORS,
    _candidate_reference_nodes,
    _reference_text,
    _reference_doi,
    extract_numbered_references_from_soup,
)
from ..extraction.html.object_links import resolve_retained_object_links
from ._script_json import extract_assignment_json

SCIENCE_AUTHOR_COUNT_PATTERN = ATYPON_AUTHOR_COUNT_PATTERN
SCIENCE_STRUCTURED_SUBHEADING_PATTERN = re.compile(
    r"(?m)^###\s+([A-Z][A-Z0-9 /-]*)\s*$"
)
SCIENCE_IGNORED_AUTHOR_TEXT = {
    *ATYPON_AUTHOR_NOISE_TEXT,
    *ATYPON_AUTHOR_COLLAPSE_UI_TEXT,
}
SCIENCE_CANONICAL_ABSTRACT_HEADING = "abstract"
SCIENCE_STRUCTURED_ABSTRACT_HEADING = "structured abstract"
SCIENCE_CITATION_TOKEN_PATTERN = r"(?:\d+[A-Za-z]*|[A-Za-z]+\d+[A-Za-z0-9]*)"
SCIENCE_CITATION_ITALIC_PATTERNS = (
    re.compile(
        rf"\*(?P<left>{SCIENCE_CITATION_TOKEN_PATTERN})\*\*(?P<sep>[\u2013,;])\*\s*\*(?P<right>{SCIENCE_CITATION_TOKEN_PATTERN})\*"
    ),
    re.compile(
        rf"\*(?P<left>{SCIENCE_CITATION_TOKEN_PATTERN})\*(?P<sep>\s*[\u2013,;]\s*)\*(?P<right>{SCIENCE_CITATION_TOKEN_PATTERN})\*"
    ),
)


def _usable_reference_targets(nodes: Sequence[Tag]) -> set[str]:
    # Only targets in the candidate list used by extraction count as available.
    available: set[str] = set()
    for node in nodes:
        if not _reference_text(node):
            continue
        targets = [node, *node.select(".citations[id]")]
        available.update(
            str(target["id"])
            for target in targets
            if target.get("id") and re.fullmatch(r"R\d+", str(target["id"]))
        )
    return available


def _reference_coverage(soup: BeautifulSoup) -> tuple[set[str], set[str]]:
    available = _usable_reference_targets(_candidate_reference_nodes(soup))
    cited = {
        str(node.get("data-xml-rid") or str(node.get("href") or "").split("#")[-1])
        for node in soup.select("a[role='doc-biblioref'], a[data-xml-rid]")
    }
    return available, {value for value in cited if re.fullmatch(r"R\d+", value)}


_SCIENCE_REFERENCE_SNAPSHOT = r"""selectors => {
    let candidates = [];
    for (const selector of selectors) {
        candidates = Array.from(document.querySelectorAll(selector));
        if (candidates.length) break;
    }
    const bibliography = document.querySelector('#bibliography');
    const controls = bibliography ? Array.from(bibliography.querySelectorAll('button, a')) : [];
    const pattern = /^(?:show|view|load)\s+(?:all|more|remaining)(?:\s+references)?(?:\s*\(\d+\))?$/i;
    const control = controls.findIndex(node => {
        const style = getComputedStyle(node);
        return pattern.test((node.textContent || '').replace(/\s+/g, ' ').trim())
            && node.getClientRects().length > 0
            && style.visibility !== 'hidden' && style.visibility !== 'collapse'
            && !node.matches(':disabled') && node.getAttribute('aria-disabled') !== 'true';
    });
    return {
        reference_html: candidates.map(node => node.outerHTML).join(''),
        reference_ids: Array.from(document.querySelectorAll('#bibliography .citations[id]'), node => node.id),
        cited: Array.from(document.querySelectorAll('a[role="doc-biblioref"], a[data-xml-rid]'), node =>
            node.getAttribute('data-xml-rid') || (node.getAttribute('href') || '').split('#').pop()
        ).filter(value => /^R\d+$/.test(value)),
        bibliography_present: Boolean(bibliography), control_index: control,
    };
}"""


def prepare_browser_page(
    page: Any,
    *,
    timeout_ms: int,
    cancel_check: Callable[[], None] | None = None,
) -> Mapping[str, Any]:
    """Wait for extractable references and expand only visible publisher controls."""
    from contextlib import suppress
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    started = time.monotonic()
    budget_ms = max(0, min(timeout_ms, 10000))
    deadline = started + budget_ms / 1000
    previous_fragment: str | None = None
    previous_available: set[str] = set()

    def snapshot() -> tuple[Mapping[str, Any], set[str], set[str], set[str]]:
        nonlocal previous_fragment, previous_available
        if cancel_check is not None:
            cancel_check()
        state = page.evaluate(
            _SCIENCE_REFERENCE_SNAPSHOT, list(NUMBERED_BIBLIOGRAPHY_SELECTORS)
        )
        # Reuse the actual extractor's candidate/text rules, including noise-only
        # entries, instead of treating an early ID or linkout as a loaded citation.
        reference_html = state["reference_html"]
        if reference_html != previous_fragment:
            fragment = BeautifulSoup(
                '<div id="reference-snapshot">' + reference_html + "</div>",
                choose_parser(),
            )
            root = fragment.find(id="reference-snapshot")
            # These nodes were already selected in the real document. Do not
            # select them again after losing ancestors such as .ref-list or ol.
            previous_available = _usable_reference_targets(
                [node for node in root.children if isinstance(node, Tag)]
                if root is not None
                else []
            )
            previous_fragment = reference_html
        available = previous_available

        return state, set(state["reference_ids"]), available, set(state["cited"])

    state, before, available, cited = snapshot()
    extractable_before = len(available)
    ids = before
    scrolled = False
    timed_out = False
    while True:
        poll_started = time.monotonic()
        control_index = state["control_index"]
        if control_index < 0 and not cited - available:
            break
        remaining_ms = int(round((deadline - time.monotonic()) * 1000))
        if remaining_ms <= 0:
            timed_out = bool(cited - available or control_index >= 0)
            break
        if cancel_check is not None:
            cancel_check()
        if not scrolled and state["bibliography_present"]:
            scrolled = page.evaluate(
                """() => {
                    const bibliography = document.querySelector('#bibliography');
                    if (!bibliography) return false;
                    bibliography.scrollIntoView();
                    return true;
                }"""
            )
        remaining_ms = int(round((deadline - time.monotonic()) * 1000))
        if control_index >= 0 and remaining_ms > 0:
            with suppress(PlaywrightTimeoutError):
                page.locator("#bibliography").locator("button, a").nth(
                    control_index
                ).filter(
                    has_text=re.compile(
                        r"^(?:show|view|load)\s+(?:all|more|remaining)(?:\s+references)?(?:\s*\(\d+\))?$",
                        re.I,
                    )
                ).click(timeout=min(200, remaining_ms))
        remaining_ms = int(round((deadline - time.monotonic()) * 1000))
        poll_remaining_ms = 200 - int((time.monotonic() - poll_started) * 1000)
        if remaining_ms > 0 and poll_remaining_ms > 0:
            page.wait_for_timeout(min(poll_remaining_ms, remaining_ms))
        state, ids, available, cited = snapshot()
    return {
        "references_before": len(before),
        "references_after": len(ids),
        "extractable_references_before": extractable_before,
        "extractable_references_after": len(available),
        "empty_reference_ids": sorted(ids - available),
        "missing_reference_targets": sorted(cited - available),
        "preparation_budget_ms": budget_ms,
        "preparation_elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        "timed_out": timed_out,
    }


def _load_aaas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    payload = extract_assignment_json(html_text, AAAS_DATALAYER_PATTERN)
    return payload if isinstance(payload, Mapping) else None


def blocking_fallback_signals(html_text: str) -> list[str]:
    return evaluate_datalayer_blocking_signals(html_text, SCIENCE_SIGNAL_SET)


def _extract_datalayer_authors(html_text: str) -> list[str]:
    payload = _load_aaas_datalayer(html_text)
    if payload is None:
        return []
    page = payload.get("page")
    if not isinstance(page, Mapping):
        return []
    page_info = page.get("pageInfo")
    if not isinstance(page_info, Mapping):
        return []
    return dedupe_authors(normalized_author_tokens(page_info.get("author")))


def _extract_dom_authors(html_text: str) -> list[str]:
    return extract_property_authors(
        html_text,
        selectors=".contributors [property='author']",
        ignored_text=SCIENCE_IGNORED_AUTHOR_TEXT,
        count_pattern=SCIENCE_AUTHOR_COUNT_PATTERN,
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep("datalayer", _extract_datalayer_authors),
    AuthorStep("dom", _extract_dom_authors),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_PIPELINE(html_text)


def _normalize_science_heading(value: Any) -> str:
    return normalize_text(value).lower().strip(" :")


def _science_abstract_role(section: Mapping[str, Any]) -> str:
    heading = _normalize_science_heading(section.get("heading"))
    source_selector = _normalize_science_heading(section.get("source_selector"))
    if "#editor-abstract" in source_selector:
        return "teaser"
    if (
        "#structured-abstract" in source_selector
        or heading == SCIENCE_STRUCTURED_ABSTRACT_HEADING
    ):
        return "structured"
    if "#abstract" in source_selector or heading == SCIENCE_CANONICAL_ABSTRACT_HEADING:
        return "canonical"
    return "abstract"


def _rebuild_science_section_hints(
    frontmatter_sections: Sequence[Mapping[str, Any]],
    existing_hints: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rebuilt: list[dict[str, Any]] = []
    for order, section in enumerate(frontmatter_sections):
        rebuilt.append(
            {
                "heading": normalize_text(section.get("heading")) or "Section",
                "level": 2,
                "kind": "body",
                "order": order,
                "language": normalize_text(section.get("language")) or None,
                "source_selector": normalize_text(section.get("source_selector"))
                or None,
            }
        )
    base_order = len(rebuilt)
    for index, hint in enumerate(existing_hints):
        if not isinstance(hint, Mapping):
            continue
        raw_order = hint.get("order")
        if isinstance(raw_order, int):
            normalized_order = raw_order + base_order
        elif str(raw_order or "").isdigit():
            normalized_order = int(str(raw_order)) + base_order
        else:
            normalized_order = base_order + index
        rebuilt.append(
            {
                **hint,
                "order": normalized_order,
            }
        )
    return rebuilt


def _finalize_science_abstracts(extraction: Mapping[str, Any]) -> dict[str, Any]:
    abstract_sections = [
        dict(item)
        for item in (extraction.get("abstract_sections") or [])
        if isinstance(item, Mapping) and normalize_text(item.get("text"))
    ]
    if not abstract_sections:
        return dict(extraction)

    teaser_sections: list[dict[str, Any]] = []
    structured_sections: list[dict[str, Any]] = []
    canonical_sections: list[dict[str, Any]] = []
    for section in abstract_sections:
        role = _science_abstract_role(section)
        if role == "teaser":
            teaser_sections.append(section)
        elif role == "structured":
            structured_sections.append(section)
        elif role == "canonical":
            canonical_sections.append(section)

    if not canonical_sections or not (teaser_sections or structured_sections):
        return dict(extraction)

    canonical_sections.sort(key=lambda item: int(item.get("order") or 0))
    frontmatter_sections = sorted(
        [*teaser_sections, *structured_sections],
        key=lambda item: int(item.get("order") or 0),
    )
    canonical_abstract = canonical_sections[0]
    finalized = dict(extraction)
    finalized["abstract_text"] = normalize_text(canonical_abstract.get("text")) or None
    finalized["abstract_sections"] = [canonical_abstract]
    finalized["section_hints"] = _rebuild_science_section_hints(
        frontmatter_sections,
        list(extraction.get("section_hints") or []),
    )
    return finalized


def _has_frontmatter_abstract_split(extraction: Mapping[str, Any]) -> bool:
    roles = {
        _science_abstract_role(section)
        for section in (extraction.get("abstract_sections") or [])
        if isinstance(section, Mapping)
    }
    return "canonical" in roles and bool({"teaser", "structured"} & roles)


def _flatten_structured_abstract_markdown(markdown_text: str) -> str:
    match = re.search(r"(?m)^##\s+Structured Abstract\s*$", markdown_text)
    if match is None:
        return markdown_text
    tail = markdown_text[match.end() :]
    next_heading = re.search(r"(?m)^##\s+", tail)
    block_end = (
        match.end() + next_heading.start()
        if next_heading is not None
        else len(markdown_text)
    )
    block = markdown_text[match.end() : block_end]
    flattened = SCIENCE_STRUCTURED_SUBHEADING_PATTERN.sub(
        lambda item: f"**{item.group(1)}.**",
        block,
    )
    return markdown_text[: match.end()] + flattened + markdown_text[block_end:]


def positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return evaluate_datalayer_positive_signals(html_text, SCIENCE_SIGNAL_SET)


def is_front_matter_teaser_figure(
    node: Any, *, abstract_anchor: Any | None = None
) -> bool:
    from .atypon_browser_workflow.normalization import _is_front_matter_teaser_figure

    return _is_front_matter_teaser_figure(node, abstract_anchor=abstract_anchor)


def _drop_science_front_matter_teaser_figures(container: Any) -> None:
    # Graphical abstracts are scientific content; give them their own section
    # so abstract text extraction cannot flatten their image/caption boundary.
    if not isinstance(container, Tag):
        return
    for figure in list(
        container.select(
            ".abstract figure, #structured-abstract figure, section[role=doc-abstract] figure"
        )
    ):
        abstract = (
            figure.find_parent(id="abstracts")
            or figure.find_parent(id="structured-abstract")
            or figure.find_parent(class_="abstract")
            or figure.find_parent("section")
        )
        if abstract is None:
            continue
        section = Tag(name="section", attrs={"class": "paper-fetch-graphical-summary"})
        heading = Tag(name="h2")
        heading.string = "Graphical summary"
        section.append(heading)
        section.append(figure.extract())
        abstract.insert_after(section)


def select_content_nodes(container: Tag, **helpers: Any) -> list[Tag]:
    abstracts = helpers["nodes_from_selectors"](
        container, helpers["content_abstract_selectors"]
    )
    body = helpers["nodes_from_selectors"](container, helpers["content_body_selectors"])
    summaries = container.select("section.paper-fetch-graphical-summary")
    available = helpers["select_availability_nodes"](container, body)
    return helpers["dedupe_top_level_nodes"](
        [*abstracts, *summaries, *body, *available]
    )


def science_before_block_normalization(container: Any) -> None:
    _drop_science_front_matter_teaser_figures(container)
    if not isinstance(container, Tag):
        return
    _promote_science_availability(container)
    body = container.select_one("#bodymatter")
    if body is not None:
        root = body.select_one(":scope > .core-container") or body
        first = next((child for child in root.children if isinstance(child, Tag)), None)
        if (
            first is not None
            and first.name == "div"
            and first.get("role") == "paragraph"
        ):
            heading = BeautifulSoup("<h2>Main Text</h2>", "html.parser").h2
            root.insert(0, heading)
    from ._html_section_markdown import render_heading_text_from_html

    for heading in container.select("h2, h3, h4, h5, h6"):
        if heading.find(["sup", "sub"]) is not None:
            text = render_heading_text_from_html(heading)
            heading.clear()
            heading.append(text)
            heading["data-paper-fetch-markdown"] = "1"
    _normalize_science_table_row_groups(container)


def _normalize_science_table_row_groups(container: Tag) -> None:
    """Single-sample-derived structural rule, limited to Science HTML tables.

    Clamp spans to their source row group and collapse only the existing model
    statistics / single-cell covariate continuation shape, in source order.
    """
    for group in container.select("table > thead, table > tbody, table > tfoot"):
        rows = group.find_all("tr", recursive=False)
        for index, row in enumerate(rows):
            for cell in row.find_all(["th", "td"], recursive=False):
                span_text = str(cell.get("rowspan", "1"))
                if span_text.isdecimal() and int(span_text) > len(rows) - index:
                    cell["rowspan"] = str(len(rows) - index)
        # Model statistics span physical continuation lines of a single
        # covariate list. Collapse only that shape, keeping the source order.
        if group.name != "tbody":
            continue
        for index, row in enumerate(rows):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            spans = [int(str(cell.get("rowspan", "1"))) for cell in cells[:-1]]
            span = spans[0]
            if span <= 1 or any(value != span for value in spans):
                continue
            continuation = rows[index + 1 : index + span]
            tails = [
                part.find_all(["th", "td"], recursive=False) for part in continuation
            ]
            if any(len(part) != 1 or part[0].has_attr("rowspan") for part in tails):
                continue
            for part in tails:
                previous = cells[-1].get_text().rstrip()
                if not previous.endswith(("*", "/", "−", "-", "+")):
                    cells[-1].append(" ")
                for child in list(part[0].contents):
                    cells[-1].append(child.extract())
            for cell in cells[:-1]:
                cell.attrs.pop("rowspan", None)
            cells[-1].smooth()
            for part in continuation:
                part.decompose()


def render_table_with_missing_trailing_cells(
    node: Tag, *, label: str, caption: str
) -> str | None:
    """Preserve browser column positions for unspanned, short source rows."""
    import copy
    from ..extraction.html.tables import render_table_markdown

    table = node if node.name == "table" else node.find("table")
    if not isinstance(table, Tag) or table.find("table") is not None:
        return None
    rows = table.find_all("tr")
    if not rows or table.find("tfoot") is not None:
        return None
    thead = table.find("thead")
    if isinstance(thead, Tag) and len(thead.find_all("tr")) != 1:
        return None
    cells = [row.find_all(["th", "td"], recursive=False) for row in rows]
    if not cells[0] or not all(cell.name == "th" for cell in cells[0]):
        return None
    width = len(cells[0])
    if any(
        str(cell.get(attr, "1")) != "1"
        for row in cells
        for cell in row
        for attr in ("rowspan", "colspan")
    ) or any(not row or len(row) > width for row in cells[1:]):
        return None
    missing = [
        (index, len(row)) for index, row in enumerate(cells[1:], 1) if len(row) < width
    ]
    if not missing:
        return None
    clone = copy.deepcopy(node)
    cloned_table = clone if clone.name == "table" else clone.find("table")
    cloned_rows = cloned_table.find_all("tr")
    for index, count in missing:
        for _ in range(width - count):
            cloned_rows[index].append(Tag(name="td"))
    rendered = render_table_markdown(clone, label=label, caption=caption)
    notes = [
        f"Source table note: data row {index} supplies {count} of {width} cells; missing trailing cells are left blank."
        for index, count in missing
    ]
    return rendered + "\n\n" + "\n".join(notes)


def science_classify_heading(heading: str, title: str | None = None) -> str | None:
    """AAAS labels include materials and combined data/code statements."""
    del title
    label = _normalize_science_heading(heading)
    if label in {
        "data availability",
        "data availability statement",
        "data and materials availability",
        "data and code availability",
        "data, code, and materials availability",
    }:
        return "data_availability"
    if label in {
        "code availability",
        "code availability statement",
        "software availability",
    }:
        return "code_availability"
    return None


def _promote_science_availability(container: Tag) -> None:
    """Retain explicitly labelled data/code/material statements through the next peer label."""
    from copy import deepcopy

    factory = BeautifulSoup("", "html.parser")
    peer_labels = {
        "funding",
        "author contributions",
        "competing interests",
        "acknowledgments",
        "acknowledgements",
    }
    for acknowledgments in container.select(
        "section#acknowledgments, section#acknowledgements"
    ):
        tail = acknowledgments
        for paragraph in list(acknowledgments.select('p, div[role="paragraph"]')):
            children = list(paragraph.contents)
            labels = []
            for index, node in enumerate(children):
                if not isinstance(node, Tag) or node.name not in {"b", "strong"}:
                    continue
                if any(
                    parent.has_attr("hidden")
                    or parent.get("aria-hidden") == "true"
                    or re.search(
                        r"(?:display\s*:\s*none|visibility\s*:\s*hidden)",
                        str(parent.get("style", "")),
                        re.I,
                    )
                    for parent in [node, *node.parents]
                    if isinstance(parent, Tag)
                ):
                    continue
                heading = node.get_text(" ", strip=True).rstrip(":").strip()
                kind = science_classify_heading(heading)
                if kind or heading.casefold() in peer_labels:
                    labels.append((index, heading, kind))
            for position, (index, heading, kind) in enumerate(labels):
                if kind is None:
                    continue
                stop = (
                    labels[position + 1][0]
                    if position + 1 < len(labels)
                    else len(children)
                )
                section = factory.new_tag(
                    "section", attrs={"class": kind.replace("_", "-")}
                )
                heading_node = factory.new_tag("h2")
                heading_node.string = heading
                section.append(heading_node)
                retained = factory.new_tag("p")
                for child in children[index + 1 : stop]:
                    retained.append(deepcopy(child))
                section.append(retained)
                for original in children[index:stop]:
                    original.extract()
                tail.insert_after(section)
                tail = section


def science_body_container(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    from .atypon_browser_workflow.asset_scopes import (
        _atypon_browser_workflow_supplementary_sections,
    )

    for section in _atypon_browser_workflow_supplementary_sections(container):
        section.decompose()
    for node in list(
        container.select("#eletterModal, #elettersSection, #trendmd-suggestions")
    ):
        if node.parent is not None:
            node.decompose()


def science_asset_body_container(container: Any) -> None:
    _drop_science_front_matter_teaser_figures(container)


def science_asset_figure_extraction(container: Any) -> None:
    _drop_science_front_matter_teaser_figures(container)


def science_normalize_markdown(markdown_text: str) -> str:
    return merge_science_citation_italics(markdown_text)


def science_keep_leading_auxiliary_block(
    block: str,
    *,
    publisher: str,
    figure_assets: Sequence[Mapping[str, Any]] | None,
) -> bool:
    from ..extraction.html.figure_links import canonical_figure_label_from_asset

    # Perspectives can start with a manuscript photograph whose body asset
    # survived the teaser filter; retain its caption before the first prose.
    leading_figure = re.match(r"^\*\*(Figure\s+\d+)\.\*\*", block, re.I)
    return bool(
        publisher == "science"
        and leading_figure is not None
        and any(
            canonical_figure_label_from_asset(asset) == leading_figure[1].lower()
            for asset in figure_assets or []
            if asset.get("section", "body") == "body"
        )
    )


def science_keep_unknown_abstract_block(block: str) -> bool:
    return bool(normalize_text(block))


def extract_asset_html_scopes(
    body_container: Any,
    supplementary_container: Any,
    *,
    publisher: str,
    source_url: str | None = None,
    raw_body_container: Any | None = None,
    content_fragment_html,
    atypon_browser_workflow_supplementary_sections,
) -> tuple[str, str]:
    del source_url, raw_body_container
    from .atypon_browser_workflow.asset_scopes import (
        extract_body_and_supplementary_html,
    )

    return extract_body_and_supplementary_html(
        body_container,
        supplementary_container,
        publisher=publisher,
        content_fragment_html=content_fragment_html,
        supplementary_sections=atypon_browser_workflow_supplementary_sections,
    )


def merge_science_citation_italics(markdown_text: str) -> str:
    def render_separator(separator_text: str) -> str:
        separator = normalize_text(separator_text)
        if separator in {",", ";"}:
            return f"{separator} "
        return separator

    merged = markdown_text
    changed = True
    while changed:
        changed = False
        for pattern in SCIENCE_CITATION_ITALIC_PATTERNS:
            merged, replacements = pattern.subn(
                lambda match: (
                    f"*{match.group('left')}{render_separator(match.group('sep'))}{match.group('right')}*"
                ),
                merged,
            )
            changed = changed or replacements > 0
    return merged


def finalize_extraction(
    html_text: str,
    source_url: str,
    markdown_text: str,
    extraction: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    del metadata
    needs_frontmatter_flatten = _has_frontmatter_abstract_split(extraction)
    finalized = _finalize_science_abstracts(extraction)
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    soup = BeautifulSoup(html_text, choose_parser())
    extracted_references = extract_numbered_references_from_soup(soup)
    if not extracted_references:
        # The loaded bibliography template uses biblioentry rather than
        # role=listitem. Its DOI links sit beside the citation text.
        extracted_references = [
            {
                "label": normalize_text(node.select_one(".label").get_text())
                if node.select_one(".label")
                else None,
                "raw": _reference_text(node),
                "doi": _reference_doi(node),
            }
            for node in soup.select("#bibliography .biblioentry")
            if _reference_text(node)
        ]
    if extracted_references:
        finalized["references"] = extracted_references
    if needs_frontmatter_flatten:
        markdown_text = _flatten_structured_abstract_markdown(markdown_text)
    available, cited = _reference_coverage(soup)
    missing = sorted(cited - available)
    if missing:
        finalized["quality_flags"] = [
            *finalized.get("quality_flags", []),
            "reference_targets_missing",
        ]
        finalized["warnings"] = [
            *finalized.get("warnings", []),
            "Science bibliography is incomplete; missing cited targets: "
            + ", ".join(missing),
        ]
        finalized["missing_reference_targets"] = missing
    from .atypon_browser_workflow.asset_scopes import (
        _atypon_browser_workflow_supplementary_sections,
    )
    from ._html_section_markdown import render_container_markdown

    if not re.search(
        r"(?im)^#{2,6} supplementary (?:materials?|information)\s*$", markdown_text
    ):
        supplementary_lines: list[str] = []
        for section in _atypon_browser_workflow_supplementary_sections(soup):
            for link in section.select("a[href]"):
                link["href"] = urllib.parse.urljoin(source_url, str(link["href"]))
            render_container_markdown(
                section,
                supplementary_lines,
                level=3,
                skip_first_heading="Supplementary Materials",
                preserve_heading_levels=True,
            )
        if supplementary_lines:
            markdown_text += "\n\n## Supplementary Materials\n\n" + "\n".join(
                supplementary_lines
            )
    reference_targets = {
        str(node["id"]): str(node["id"]) for node in soup.select(".citations[id]")
    }
    markdown_text = resolve_retained_object_links(
        markdown_text, source_url, reference_targets
    )
    return markdown_text, finalized


def scoped_asset_extractor(*args: Any, **kwargs: Any) -> list[dict[str, str]]:
    from .atypon_browser_workflow.asset_scopes import extract_scoped_html_assets

    return extract_scoped_html_assets(*args, **kwargs)
