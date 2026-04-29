"""Wiley provider-owned browser-workflow rules."""

from __future__ import annotations

import re
import urllib.parse
from functools import partial
from typing import Any, Mapping

from ..extraction.html import _assets as _html_asset_impl
from ..extraction.html.parsing import choose_parser
from ..quality.html_profiles import (
    WILEY_NOISE_PROFILE,
    WILEY_SITE_RULE_OVERRIDES,
    wiley_blocking_fallback_signals,
    wiley_positive_signals,
)
from ..utils import normalize_text
from ._browser_workflow_authors import AuthorExtractionPipeline, extract_meta_authors, extract_selector_authors
from ._html_references import extract_numbered_references_from_html

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

HOSTS: tuple[str, ...] = ("onlinelibrary.wiley.com", "wiley.com", "www.wiley.com")
BASE_HOSTS: tuple[str, ...] = ("onlinelibrary.wiley.com",)
HTML_PATH_TEMPLATES: tuple[str, ...] = ("/doi/full/{doi}", "/doi/{doi}")
PDF_PATH_TEMPLATES: tuple[str, ...] = (
    "/doi/epdf/{doi}",
    "/doi/pdf/{doi}",
    "/doi/pdfdirect/{doi}",
    "/wol1/doi/{doi}/fullpdf",
)
CROSSREF_PDF_POSITION = 1
NOISE_PROFILE = WILEY_NOISE_PROFILE
SITE_RULE_OVERRIDES: dict[str, Any] = WILEY_SITE_RULE_OVERRIDES
WILEY_IGNORED_AUTHOR_TEXT = {
    "orcid",
    "search for more papers by this author",
}
WILEY_AUTHOR_SELECTOR_CANDIDATES = (
    ".loa-authors-trunc a.author-name",
    ".loa-authors-trunc p.author-name",
    ".accordion-tabbed a.author-name",
    ".accordion-tabbed p.author-name",
)
WILEY_SUPPORTING_SECTION_SELECTORS = (
    "section.article-section__supporting",
    "section[data-suppl]",
)


def blocking_fallback_signals(html_text: str) -> list[str]:
    return wiley_blocking_fallback_signals(html_text)


def find_supporting_information_sections(container: Any) -> list[Any]:
    if Tag is None or not isinstance(container, Tag):
        return []

    sections: list[Any] = []
    seen: set[int] = set()
    for selector in WILEY_SUPPORTING_SECTION_SELECTORS:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag):
                continue
            match_id = id(match)
            if match_id in seen:
                continue
            seen.add(match_id)
            sections.append(match)
    if sections:
        return sections

    heading = container.find(id="support-information-section")
    if isinstance(heading, Tag):
        section = heading.find_parent("section")
        if isinstance(section, Tag):
            return [section]
    return []


def _node_author_text(node: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""
    span = node.find("span")
    candidate = normalize_text(
        span.get_text(" ", strip=True) if isinstance(span, Tag) else node.get_text(" ", strip=True)
    )
    candidate = re.sub(
        r"\s*Search for more papers by this author\s*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()
    return normalize_text(candidate)


def _extract_dom_authors(html_text: str) -> list[str]:
    return extract_selector_authors(
        html_text,
        selectors=WILEY_AUTHOR_SELECTOR_CANDIDATES,
        ignored_text=WILEY_IGNORED_AUTHOR_TEXT,
        node_text=_node_author_text,
        reject_email=True,
        reject_affiliation_prefixes=("contribution:", "department of ", "institute of "),
    )


_AUTHOR_EXTRACTION_PIPELINE = AuthorExtractionPipeline(
    partial(extract_meta_authors, keys={"citation_author"}),
    _extract_dom_authors,
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_EXTRACTION_PIPELINE(html_text)


def positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return wiley_positive_signals(html_text)


def dom_postprocess(container: Any) -> None:
    from ._science_pnas_postprocess import move_wiley_abbreviations_to_end

    move_wiley_abbreviations_to_end(container)


def refine_selected_container(
    node: Any,
    *,
    direct_child_tags,
    class_tokens,
    container_completeness_score,
    score_container,
) -> Any:
    article_candidates = [
        candidate
        for candidate in [node, *list(node.find_all("article"))]
        if normalize_text(getattr(candidate, "name", "")).lower() == "article"
    ]
    if not article_candidates:
        return node

    def has_direct_abstract_child(candidate: Any) -> bool:
        for child in direct_child_tags(candidate):
            tokens = class_tokens(child)
            if {"abstract-group", "metis-abstract"} <= tokens:
                return True
            if "article-section__abstract" in tokens:
                return True
            if child.select_one(".article-section__abstract") is not None:
                return True
        return False

    def has_direct_body_child(candidate: Any) -> bool:
        for child in direct_child_tags(candidate):
            if "article-section__full" in class_tokens(child):
                return True
        return False

    def candidate_key(candidate: Any) -> tuple[int, int, int, int, int, float]:
        has_direct_abstract = has_direct_abstract_child(candidate)
        has_direct_body = has_direct_body_child(candidate)
        return (
            1 if has_direct_abstract and has_direct_body else 0,
            1 if has_direct_abstract else 0,
            1 if has_direct_body else 0,
            1 if normalize_text(candidate.get("lang") or "") else 0,
            container_completeness_score(candidate),
            score_container(candidate),
        )

    best_candidate = max(article_candidates, key=candidate_key)
    return best_candidate if candidate_key(best_candidate) > candidate_key(node) else node


def finalize_extraction(
    html_text: str,
    source_url: str,
    markdown_text: str,
    extraction: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    del source_url, metadata
    finalized = dict(extraction)
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    extracted_references = extract_numbered_references_from_html(html_text)
    if extracted_references:
        finalized["references"] = extracted_references
    return markdown_text, finalized


def _wiley_supplementary_link_tokens(anchor: Any) -> tuple[str, ...]:
    href = normalize_text(str(anchor.get("href") or ""))
    if not href:
        return ()

    parsed = urllib.parse.urlsplit(href)
    tokens: list[str] = [href, parsed.path]
    for values in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).values():
        tokens.extend(str(value) for value in values)
    anchor_text = normalize_text(anchor.get_text(" ", strip=True))
    if anchor_text:
        tokens.append(anchor_text)
    return tuple(token for token in (normalize_text(value) for value in tokens) if token)


def _wiley_supplementary_anchor_is_supported(anchor: Any) -> bool:
    if Tag is None or not isinstance(anchor, Tag):
        return False

    href = normalize_text(str(anchor.get("href") or ""))
    if not href or href.startswith("#"):
        return False

    if "downloadsupplement" in href.lower():
        return True
    return any("sup-" in token.lower() for token in _wiley_supplementary_link_tokens(anchor))


def _wiley_supplementary_filename(anchor: Any) -> str:
    href = normalize_text(str(anchor.get("href") or ""))
    if not href:
        return ""

    parsed = urllib.parse.urlsplit(href)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    for key in ("file", "filename"):
        for value in query.get(key, []):
            candidate = normalize_text(str(value or ""))
            if candidate:
                return candidate.rsplit("/", 1)[-1]
    path = normalize_text(parsed.path)
    if path:
        return path.rsplit("/", 1)[-1]
    return ""


def extract_supplementary_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, choose_parser())
    assets_by_url: dict[str, dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        if not _wiley_supplementary_anchor_is_supported(anchor):
            continue

        href = normalize_text(str(anchor.get("href") or ""))
        absolute_href = urllib.parse.urljoin(source_url, href)
        if not absolute_href:
            continue

        filename_hint = _wiley_supplementary_filename(anchor)
        heading = normalize_text(anchor.get_text(" ", strip=True)) or filename_hint or "Supporting Information"
        existing = assets_by_url.get(absolute_href)
        if existing is None:
            asset = {
                "kind": "supplementary",
                "heading": heading,
                "caption": "",
                "section": "supplementary",
                "url": absolute_href,
            }
            if filename_hint:
                asset["filename_hint"] = filename_hint
            assets_by_url[absolute_href] = asset
            continue
        if len(heading) > len(normalize_text(existing.get("heading") or "")):
            existing["heading"] = heading
        if filename_hint and not existing.get("filename_hint"):
            existing["filename_hint"] = filename_hint
    return list(assets_by_url.values())


def extract_scoped_html_assets(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile,
    supplementary_html_text: str | None = None,
) -> list[dict[str, str]]:
    assets = _html_asset_impl.extract_figure_assets(body_html_text, source_url)
    assets.extend(_html_asset_impl.extract_formula_assets(body_html_text, source_url))
    if asset_profile == "all":
        assets.extend(extract_supplementary_assets(supplementary_html_text or "", source_url))
    return assets
