"""Science provider-owned browser-workflow rules."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from ..quality.html_profiles import (
    SCIENCE_NOISE_PROFILE,
    SCIENCE_SITE_RULE_OVERRIDES,
    science_blocking_fallback_signals,
    science_positive_signals,
)
from ..utils import dedupe_authors, normalize_text
from ._html_references import extract_numbered_references_from_html

from ._browser_workflow_shared import (
    build_base_urls,
    preferred_html_candidate_from_landing_page,
)

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

HOSTS: tuple[str, ...] = ("www.science.org", "science.org")
BASE_HOSTS: tuple[str, ...] = HOSTS
NOISE_PROFILE = SCIENCE_NOISE_PROFILE
SITE_RULE_OVERRIDES: dict[str, Any] = SCIENCE_SITE_RULE_OVERRIDES
AAAS_DATALAYER_PATTERN = re.compile(r"AAASdataLayer=(\{.*?\});(?:if\(|</script>)", flags=re.DOTALL)
SCIENCE_AUTHOR_COUNT_PATTERN = re.compile(r"^\+\s*\d+\s+authors?$", flags=re.IGNORECASE)
SCIENCE_STRUCTURED_SUBHEADING_PATTERN = re.compile(r"(?m)^###\s+([A-Z][A-Z0-9 /-]*)\s*$")
SCIENCE_IGNORED_AUTHOR_TEXT = {
    "authors info & affiliations",
    "fewer",
    "view all articles by this author",
}
SCIENCE_CANONICAL_ABSTRACT_HEADING = "abstract"
SCIENCE_STRUCTURED_ABSTRACT_HEADING = "structured abstract"


def _load_aaas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    match = AAAS_DATALAYER_PATTERN.search(html_text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def blocking_fallback_signals(html_text: str) -> list[str]:
    return science_blocking_fallback_signals(html_text)


def _normalized_author_tokens(value: str | None) -> list[str]:
    return [
        normalize_text(token)
        for token in str(value or "").split("|")
        if normalize_text(token)
    ]


def _is_ignored_author_text(text: str) -> bool:
    normalized = normalize_text(text).lower()
    if not normalized:
        return True
    if normalized in SCIENCE_IGNORED_AUTHOR_TEXT:
        return True
    if normalized == "orcid":
        return True
    if SCIENCE_AUTHOR_COUNT_PATTERN.fullmatch(normalized):
        return True
    return normalized.startswith("http://") or normalized.startswith("https://") or "orcid.org" in normalized


def _looks_like_author_name(text: str) -> bool:
    normalized = normalize_text(text)
    return bool(normalized) and any(character.isalpha() for character in normalized)


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
    return dedupe_authors(_normalized_author_tokens(page_info.get("author")))


def _extract_dom_authors(html_text: str) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    for node in soup.select(".contributors [property='author']"):
        if Tag is not None and not isinstance(node, Tag):
            continue
        given_node = node.select_one("[property='givenName']")
        family_node = node.select_one("[property='familyName']")
        name = normalize_text(
            " ".join(
                item
                for item in (
                    given_node.get_text(" ", strip=True) if given_node else "",
                    family_node.get_text(" ", strip=True) if family_node else "",
                )
                if normalize_text(item)
            )
        )
        if not name:
            name_node = node.select_one("[property='name']")
            if name_node is not None:
                name = normalize_text(name_node.get_text(" ", strip=True))
        if not name:
            fragments = [
                fragment
                for fragment in (normalize_text(item) for item in node.stripped_strings)
                if fragment and not _is_ignored_author_text(fragment)
            ]
            name = normalize_text(" ".join(fragments))
        if _looks_like_author_name(name):
            authors.append(name)
    return dedupe_authors(authors)


def extract_authors(html_text: str) -> list[str]:
    datalayer_authors = _extract_datalayer_authors(html_text)
    if datalayer_authors:
        return datalayer_authors
    return _extract_dom_authors(html_text)


def _normalize_science_heading(value: Any) -> str:
    return normalize_text(value).lower().strip(" :")


def _science_abstract_role(section: Mapping[str, Any]) -> str:
    heading = _normalize_science_heading(section.get("heading"))
    source_selector = _normalize_science_heading(section.get("source_selector"))
    if "#editor-abstract" in source_selector:
        return "teaser"
    if "#structured-abstract" in source_selector or heading == SCIENCE_STRUCTURED_ABSTRACT_HEADING:
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
                "source_selector": normalize_text(section.get("source_selector")) or None,
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
    tail = markdown_text[match.end():]
    next_heading = re.search(r"(?m)^##\s+", tail)
    block_end = match.end() + next_heading.start() if next_heading is not None else len(markdown_text)
    block = markdown_text[match.end():block_end]
    flattened = SCIENCE_STRUCTURED_SUBHEADING_PATTERN.sub(
        lambda item: f"**{item.group(1)}.**",
        block,
    )
    return markdown_text[:match.end()] + flattened + markdown_text[block_end:]


def build_html_candidates(doi: str, landing_page_url: str | None = None) -> list[str]:
    path_templates = ("/doi/full/{doi}", "/doi/{doi}")
    candidates: list[str] = []
    preferred_candidate = preferred_html_candidate_from_landing_page(
        doi,
        landing_page_url,
        hosts=HOSTS,
    )
    if preferred_candidate:
        candidates.append(preferred_candidate)
    for base in build_base_urls(hosts=HOSTS, base_hosts=BASE_HOSTS, landing_page_url=landing_page_url):
        for template in path_templates:
            candidate = f"{base}{template.format(doi=doi)}"
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def build_pdf_candidates(doi: str, crossref_pdf_url: str | None) -> list[str]:
    candidates: list[str] = []

    def append(candidate: str | None) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    append(crossref_pdf_url)
    for base in build_base_urls(hosts=HOSTS, base_hosts=BASE_HOSTS, landing_page_url=crossref_pdf_url):
        for template in ("/doi/epdf/{doi}", "/doi/pdf/{doi}", "/doi/pdf/{doi}?download=true"):
            append(f"{base}{template.format(doi=doi)}")
    return candidates


def positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return science_positive_signals(html_text)


def markdown_postprocess(markdown_text: str) -> str:
    from ._science_pnas_postprocess import merge_science_citation_italics

    return merge_science_citation_italics(markdown_text)


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


def extract_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    from . import _science_pnas

    return _science_pnas.extract_science_pnas_markdown(
        html_text,
        source_url,
        "science",
        metadata=metadata,
    )
