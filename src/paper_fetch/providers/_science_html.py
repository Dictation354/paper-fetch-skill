"""Science provider-owned browser-workflow rules."""

from __future__ import annotations

import re
from typing import Any
from collections.abc import Mapping

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
from ._html_references import extract_numbered_references_from_html
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
    frontmatter_sections: list[Mapping[str, Any]],
    existing_hints: list[Mapping[str, Any]],
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
        rebuilt.append(
            {
                **hint,
                "order": int(raw_order) + base_order
                if isinstance(raw_order, int) or str(raw_order or "").isdigit()
                else base_order + index,
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
    from .atypon_browser_workflow.normalization import (
        _drop_front_matter_teaser_figures,
    )

    _drop_front_matter_teaser_figures(container)


def science_before_block_normalization(container: Any) -> None:
    _drop_science_front_matter_teaser_figures(container)


def science_asset_body_container(container: Any) -> None:
    _drop_science_front_matter_teaser_figures(container)


def science_asset_figure_extraction(container: Any) -> None:
    _drop_science_front_matter_teaser_figures(container)


def science_normalize_markdown(markdown_text: str) -> str:
    return merge_science_citation_italics(markdown_text)


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
    for node in list(atypon_browser_workflow_supplementary_sections(body_container)):
        node.decompose()

    supplementary_html = "\n".join(
        str(node)
        for node in atypon_browser_workflow_supplementary_sections(supplementary_container)
        if normalize_text(node.get_text(" ", strip=True))
    )
    return content_fragment_html(
        body_container, publisher=publisher
    ), supplementary_html


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
    del source_url, metadata
    needs_frontmatter_flatten = _has_frontmatter_abstract_split(extraction)
    finalized = _finalize_science_abstracts(extraction)
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    extracted_references = extract_numbered_references_from_html(html_text)
    if extracted_references:
        finalized["references"] = extracted_references
    if needs_frontmatter_flatten:
        markdown_text = _flatten_structured_abstract_markdown(markdown_text)
    return markdown_text, finalized


def scoped_asset_extractor(*args: Any, **kwargs: Any) -> list[dict[str, str]]:
    from .atypon_browser_workflow.asset_scopes import extract_scoped_html_assets

    return extract_scoped_html_assets(*args, **kwargs)
