"""PNAS provider-owned browser-workflow rules."""

from __future__ import annotations

from functools import partial
import re
from typing import Any
from collections.abc import Mapping

from ..extraction.html.semantics import normalize_heading, parse_markdown_heading
from ..quality.html_signals import PNAS_SIGNAL_SET, evaluate_datalayer_blocking_signals
from ._html_authors import (
    ATYPON_AUTHOR_COUNT_PATTERN,
    ATYPON_AUTHOR_COLLAPSE_UI_TEXT,
    ATYPON_AUTHOR_NOISE_TEXT,
    AuthorExtractionPipeline,
    AuthorStep,
    extract_meta_authors,
    extract_property_authors,
)
from ._html_references import extract_numbered_references_from_html

PNAS_AUTHOR_COUNT_PATTERN = ATYPON_AUTHOR_COUNT_PATTERN
PNAS_IGNORED_AUTHOR_TEXT = {
    *ATYPON_AUTHOR_NOISE_TEXT,
    *ATYPON_AUTHOR_COLLAPSE_UI_TEXT,
}


def blocking_fallback_signals(html_text: str) -> list[str]:
    return evaluate_datalayer_blocking_signals(html_text, PNAS_SIGNAL_SET)


def _extract_dom_authors(html_text: str) -> list[str]:
    return extract_property_authors(
        html_text,
        selectors=".contributors [property='author'], #tab-contributors [property='author']",
        ignored_text=PNAS_IGNORED_AUTHOR_TEXT,
        count_pattern=PNAS_AUTHOR_COUNT_PATTERN,
        reject_email=True,
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep("dom", _extract_dom_authors),
    AuthorStep(
        "meta",
        partial(extract_meta_authors, keys={"citation_author", "dc.creator"}),
    ),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_PIPELINE(html_text)


def pnas_before_block_normalization(container: Any) -> None:
    from .atypon_browser_workflow.profile import (
        _drop_promotional_blocks,
        _promo_block_tokens,
    )

    _drop_promotional_blocks(container, promo_block_tokens=_promo_block_tokens("pnas"))
    for listing in container.select('[role="list"]'):
        items = listing.find_all(attrs={"role": "listitem"}, recursive=False)
        labels = [item.find(class_="label", recursive=False) for item in items]
        ordered = bool(items) and all(
            label and re.fullmatch(r"\(?\d+[.)]?", label.get_text(strip=True))
            for label in labels
        )
        listing.name = "ol" if ordered else "ul"
        listing.attrs.pop("role", None)
        for item, label in zip(items, labels, strict=True):
            item.name = "li"
            item.attrs.pop("role", None)
            if ordered:
                label_match = re.search(r"\d+", label.get_text())
                assert label_match is not None
                item["value"] = label_match[0]
                label.decompose()
    from bs4 import BeautifulSoup, Tag

    body = container.select_one("#bodymatter")
    if (
        body is not None
        and container.select_one('#abstract, .abstract, [role="doc-abstract"]')
        is not None
    ):
        root = body.select_one(":scope > .core-container") or body
        first = next((child for child in root.children if isinstance(child, Tag)), None)
        if (
            first is not None
            and first.name == "div"
            and first.get("role") == "paragraph"
        ):
            root.insert(0, BeautifulSoup("<h2>Main Text</h2>", "html.parser").h2)
    from ._html_section_markdown import render_retained_text_from_html

    for quote in container.select("blockquote"):
        text = render_retained_text_from_html(quote)
        quote.name = "p"
        quote.clear()
        quote.append("\n".join("> " + line for line in text.splitlines()))
    for anchor in container.select('a[href^="#eqn"]'):
        # Bold equation numbers are cross-references, not bibliography markers.
        # Prevent the legacy parenthetical citation formatter consuming them.
        for emphasis in list(anchor.select("b, strong, i, em")):
            emphasis.unwrap()


def _pnas_markdown_has_heading(markdown_text: str, heading_text: str) -> bool:
    normalized_target = normalize_heading(heading_text)
    if not normalized_target:
        return False
    for block in re.split(r"\n\s*\n", markdown_text):
        heading_info = parse_markdown_heading(block)
        if heading_info is None:
            continue
        _, current_heading = heading_info
        if normalize_heading(current_heading) == normalized_target:
            return True
    return False


def pnas_suppress_missing_abstract(source_markdown: str) -> bool:
    return _pnas_markdown_has_heading(
        source_markdown,
        "significance",
    ) and _pnas_markdown_has_heading(source_markdown, "abstract")


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


def select_content_nodes(
    container: Any,
    *,
    structural_abstract_nodes,
    nodes_from_selectors,
    content_abstract_selectors,
    content_body_selectors,
    select_availability_nodes,
    dedupe_top_level_nodes,
    is_tag,
) -> list[Any]:
    del content_body_selectors

    body_nodes: list[Any] = []
    for selector in (
        "#bodymatter [data-extent='bodymatter'][property='articleBody']",
        "#bodymatter [property='articleBody']",
        "#bodymatter [data-extent='bodymatter']",
        "#bodymatter",
    ):
        try:
            body_nodes = [node for node in container.select(selector) if is_tag(node)]
        except Exception:
            body_nodes = []
        if body_nodes:
            break
    if not body_nodes:
        return []

    selected: list[Any] = []
    abstract_nodes = structural_abstract_nodes(container) or nodes_from_selectors(
        container, content_abstract_selectors
    )
    availability_nodes = select_availability_nodes(container, body_nodes)
    selected.extend(abstract_nodes)
    selected.extend(body_nodes)
    selected.extend(
        container.select(
            "section[role='doc-acknowledgments'], section#acknowledgments, section#acknowledgements"
        )
    )
    selected.extend(availability_nodes)
    selected = dedupe_top_level_nodes(selected)
    source_order = {id(node): index for index, node in enumerate(container.descendants)}
    return sorted(selected, key=lambda node: source_order.get(id(node), -1))


def finalize_extraction(
    html_text: str,
    source_url: str,
    markdown_text: str,
    extraction: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    del metadata
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    from .atypon_browser_workflow.asset_scopes import (
        _atypon_browser_workflow_supplementary_sections,
    )
    from ._html_section_markdown import render_container_markdown

    soup = BeautifulSoup(html_text, "lxml")
    if not re.search(
        r"(?im)^#{2,6} (?:supporting information|supplementary materials?)\s*$",
        markdown_text,
    ):
        supplementary_lines: list[str] = []
        for section in _atypon_browser_workflow_supplementary_sections(soup):
            for link in section.select("a[href]"):
                link["href"] = urljoin(source_url, str(link["href"]))
            render_container_markdown(
                section,
                supplementary_lines,
                level=3,
                skip_first_heading="Supporting Information",
            )
        if supplementary_lines:
            markdown_text += "\n\n## Supplementary Materials\n\n" + "\n".join(
                supplementary_lines
            )
    finalized = dict(extraction)
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    extracted_references = extract_numbered_references_from_html(html_text)
    if extracted_references:
        finalized["references"] = extracted_references
    return markdown_text, finalized


def scoped_asset_extractor(*args: Any, **kwargs: Any) -> list[dict[str, str]]:
    from .atypon_browser_workflow.asset_scopes import extract_scoped_html_assets

    return extract_scoped_html_assets(*args, **kwargs)
