"""Wiley provider-owned browser-workflow rules."""

from __future__ import annotations

import re
import urllib.parse
from functools import partial
from typing import Any
from collections.abc import Mapping

from ..common_patterns import HEADING_TAG_PATTERN
from ..extraction.html.parsing import choose_parser
from ..extraction.html.provider_rules import provider_html_rules
from ..extraction.html.semantics import (
    BACK_MATTER_TOKENS,
    heading_category,
    node_identity_text,
    normalize_heading,
)
from ..extraction.html.shared import (
    append_text_block as _append_text_block,
    short_text as _short_text,
    soup_root as _soup_root,
)
from ..extraction.html.assets import (
    extract_formula_assets as extract_generic_formula_assets,
)
from ..quality.html_signals import WILEY_SIGNAL_SET, evaluate_datalayer_blocking_signals
from ..utils import normalize_text
from ._html_authors import (
    ATYPON_AUTHOR_NOISE_TEXT,
    AuthorExtractionPipeline,
    AuthorStep,
    extract_jsonld_authors,
    extract_meta_authors,
    extract_selector_authors,
)
from ._html_asset_engine import (
    HtmlAssetExtractionPolicy,
    extract_scoped_assets_with_policy,
)
from ._html_references import extract_numbered_references_from_html

from bs4 import BeautifulSoup, Tag

NUMBERED_SECTION_HEADING_PATTERN = re.compile(r"^\d+(?:\.\d+)*\s+\S")
WILEY_AUTHOR_NOISE_TEXT = {
    *ATYPON_AUTHOR_NOISE_TEXT,
    "orcid",
    "search for more papers by this author",
}
WILEY_AUTHOR_NOISE_SELECTORS = (
    "[data-test='orcid-link']",
    "[data-test='author-search-link']",
    "a[href*='orcid.org']",
    "a.moreInfoLink",
)
WILEY_AUTHOR_SELECTOR_CANDIDATES = (
    ".loa-authors-trunc a.author-name",
    ".loa-authors-trunc p.author-name",
    ".accordion-tabbed a.author-name",
    ".accordion-tabbed p.author-name",
)
WILEY_JSONLD_ARTICLE_TYPES = frozenset({"article", "scholarlyarticle", "newsarticle"})
WILEY_SUPPORTING_SECTION_SELECTORS = (
    "section.article-section__supporting",
    "section[data-suppl]",
)
WILEY_SUPPLEMENTARY_DOWNLOAD_PATH_SEGMENT = "downloadsupplement"
WILEY_SUPPLEMENTARY_FILENAME_QUERY_KEYS = ("file", "filename", "attachment", "download")


def blocking_fallback_signals(html_text: str) -> list[str]:
    return evaluate_datalayer_blocking_signals(html_text, WILEY_SIGNAL_SET)


def find_supporting_information_sections(container: Any) -> list[Any]:
    if not isinstance(container, Tag):
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


def _wiley_author_noise_node(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    data_test = normalize_text(str(node.get("data-test") or "")).lower()
    href = normalize_text(str(node.get("href") or "")).lower()
    raw_classes = node.get("class") or []
    class_values = [raw_classes] if isinstance(raw_classes, str) else list(raw_classes)
    classes = {normalize_text(str(value)).lower() for value in class_values}
    text = normalize_text(node.get_text(" ", strip=True)).lower()
    if data_test in {"orcid-link", "author-search-link"}:
        return True
    if "orcid.org" in href:
        return True
    if "moreinfolink" in classes and text in WILEY_AUTHOR_NOISE_TEXT:
        return True
    return text in WILEY_AUTHOR_NOISE_TEXT


def _wiley_node_visible_author_text(node: Tag) -> str:
    fragments: list[str] = []
    for descendant in node.descendants:
        parent = getattr(descendant, "parent", None)
        if isinstance(parent, Tag):
            current: Tag | None = parent
            blocked = False
            while current is not None and current is not node:
                if _wiley_author_noise_node(current):
                    blocked = True
                    break
                current = current.parent if isinstance(current.parent, Tag) else None
            if blocked:
                continue
        if isinstance(descendant, str):
            text = normalize_text(descendant)
            if text:
                fragments.append(text)
    return normalize_text(" ".join(fragments))


def _strip_wiley_author_noise_text(text: str) -> str:
    candidate = normalize_text(text)
    lowered = candidate.lower()
    for noise_text in WILEY_AUTHOR_NOISE_TEXT:
        if lowered == noise_text:
            return ""
        if lowered.endswith(noise_text):
            candidate = candidate[: -len(noise_text)].strip()
            lowered = candidate.lower()
    return normalize_text(candidate)


def _node_author_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    if _wiley_author_noise_node(node):
        return ""

    span = next(
        (
            item
            for item in node.find_all("span")
            if isinstance(item, Tag) and not _wiley_author_noise_node(item)
        ),
        None,
    )
    candidate_node = span if isinstance(span, Tag) else node
    return _strip_wiley_author_noise_text(
        _wiley_node_visible_author_text(candidate_node)
    )


def _extract_jsonld_authors(html_text: str) -> list[str]:
    return extract_jsonld_authors(html_text, article_types=WILEY_JSONLD_ARTICLE_TYPES)


def _extract_dom_authors(html_text: str) -> list[str]:
    return extract_selector_authors(
        html_text,
        selectors=WILEY_AUTHOR_SELECTOR_CANDIDATES,
        ignored_text=WILEY_AUTHOR_NOISE_TEXT,
        node_text=_node_author_text,
        reject_email=True,
        reject_affiliation=True,
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep("meta", partial(extract_meta_authors, keys={"citation_author"})),
    AuthorStep("jsonld", _extract_jsonld_authors),
    AuthorStep("dom", _extract_dom_authors),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_PIPELINE(html_text)


def _heading_nodes(container: Tag) -> list[Tag]:
    return [
        node
        for node in container.find_all(HEADING_TAG_PATTERN)
        if isinstance(node, Tag)
    ]


def _is_frontmatter_wiley_abbreviations_heading(
    container: Tag,
    heading: Tag,
    *,
    headings: list[Tag] | None = None,
) -> bool:
    active_headings = headings if headings is not None else _heading_nodes(container)
    try:
        heading_index = active_headings.index(heading)
    except ValueError:
        return False

    abstract_index = next(
        (
            index
            for index, node in enumerate(active_headings)
            if normalize_heading(_short_text(node)) == "abstract"
        ),
        None,
    )
    first_numbered_body_index = next(
        (
            index
            for index, node in enumerate(active_headings)
            if NUMBERED_SECTION_HEADING_PATTERN.match(
                normalize_heading(_short_text(node))
            )
        ),
        None,
    )
    return (
        abstract_index is not None
        and first_numbered_body_index is not None
        and abstract_index < heading_index < first_numbered_body_index
    )


def move_wiley_abbreviations_to_end(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return

    headings = _heading_nodes(container)
    heading = next(
        (
            node
            for node in headings
            if normalize_heading(_short_text(node)) == "abbreviations"
            and _is_frontmatter_wiley_abbreviations_heading(
                container, node, headings=headings
            )
        ),
        None,
    )
    if heading is None:
        return

    parent = heading.parent if isinstance(heading.parent, Tag) else None
    if parent is None:
        return
    glossary = heading.find_next_sibling()
    if not isinstance(glossary, Tag) or "list-paired" not in node_identity_text(
        glossary
    ):
        return

    appendix = soup.new_tag("section")
    appendix["class"] = ["article-section__content", "article-section__appendix"]
    appendix_heading = soup.new_tag("h2")
    appendix_heading.string = "Abbreviations"
    appendix.append(appendix_heading)
    glossary_pairs: list[tuple[str, str]] = []
    for row in glossary.select("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [
            cell
            for cell in row.find_all(["th", "td"], recursive=False)
            if isinstance(cell, Tag)
        ]
        if len(cells) < 2:
            cells = [
                cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)
            ]
        if len(cells) < 2:
            continue
        term = _short_text(cells[0])
        expansion = _short_text(cells[1])
        if term and expansion:
            glossary_pairs.append((term, expansion))
    if glossary_pairs:
        for term, expansion in glossary_pairs:
            _append_text_block(appendix, f"{term}: {expansion}", soup=soup)
        glossary.decompose()
    else:
        appendix.append(glossary.extract())

    target_parent = parent if parent.parent is not None else container
    heading.extract()
    if not _short_text(parent):
        parent.decompose()

    insert_before: Tag | None = None
    for child in target_parent.find_all(recursive=False):
        if child is appendix or not isinstance(child, Tag):
            continue
        child_heading = child.find(HEADING_TAG_PATTERN)
        child_heading_text = (
            _short_text(child_heading) if isinstance(child_heading, Tag) else ""
        )
        if (
            any(token in node_identity_text(child) for token in BACK_MATTER_TOKENS)
            or heading_category("h2", child_heading_text) == "references_or_back_matter"
        ):
            insert_before = child
            break

    if insert_before is not None:
        insert_before.insert_before(appendix)
    else:
        target_parent.append(appendix)


def _drop_abstract_sections_from_body_container(container: Any) -> None:
    from .atypon_browser_workflow.profile import (
        _drop_abstract_sections_from_body_container,
    )

    _drop_abstract_sections_from_body_container(container)


def wiley_before_block_normalization(container: Any) -> None:
    del container


def wiley_after_block_normalization(container: Any) -> None:
    move_wiley_abbreviations_to_end(container)


def wiley_body_container(container: Any) -> None:
    _drop_abstract_sections_from_body_container(container)
    move_wiley_abbreviations_to_end(container)


def wiley_asset_body_container(container: Any) -> None:
    _drop_abstract_sections_from_body_container(container)


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
    del source_url, raw_body_container, atypon_browser_workflow_supplementary_sections
    for node in list(find_supporting_information_sections(body_container)):
        node.decompose()

    supplementary_fragments = [
        content_fragment_html(node, publisher=publisher)
        for node in find_supporting_information_sections(supplementary_container)
    ]
    supplementary_html = "\n".join(
        fragment for fragment in supplementary_fragments if normalize_text(fragment)
    )
    return content_fragment_html(
        body_container, publisher=publisher
    ), supplementary_html


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
    return (
        best_candidate if candidate_key(best_candidate) > candidate_key(node) else node
    )


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
    tokens: list[str] = [urllib.parse.unquote(parsed.path)]
    for values in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).values():
        tokens.extend(str(value) for value in values)
    anchor_text = normalize_text(anchor.get_text(" ", strip=True))
    if anchor_text:
        tokens.append(anchor_text)
    return tuple(
        token for token in (normalize_text(value) for value in tokens) if token
    )


def _wiley_supplementary_download_path_is_supported(path: str) -> bool:
    path_segments = [
        normalize_text(segment).lower()
        for segment in urllib.parse.unquote(path).split("/")
        if normalize_text(segment)
    ]
    return WILEY_SUPPLEMENTARY_DOWNLOAD_PATH_SEGMENT in path_segments


def _wiley_supplementary_filename_is_supported(filename: str) -> bool:
    lowered = normalize_text(filename).lower()
    if not lowered or lowered in {"true", "false", "1", "0"}:
        return False
    return bool(re.search(r"\bsup(?:p|pl|porting)?[-_]", lowered)) or "." in lowered


def _wiley_supplementary_anchor_is_supported(anchor: Any) -> bool:
    if not isinstance(anchor, Tag):
        return False

    href = normalize_text(str(anchor.get("href") or ""))
    if not href or href.startswith("#"):
        return False

    data_test = normalize_text(str(anchor.get("data-test") or "")).lower()
    data_track_action = normalize_text(
        str(anchor.get("data-track-action") or "")
    ).lower()
    if data_test == "supp-info-link" or data_track_action == "view supplementary info":
        return True

    parsed = urllib.parse.urlsplit(href)
    if _wiley_supplementary_download_path_is_supported(parsed.path):
        return True
    filename = _wiley_supplementary_filename(anchor)
    if _wiley_supplementary_filename_is_supported(filename):
        return True
    return any(
        "sup-" in token.lower() for token in _wiley_supplementary_link_tokens(anchor)
    )


def _wiley_filename_from_query_value(value: str) -> str:
    candidate = normalize_text(str(value or ""))
    if not _wiley_supplementary_filename_is_supported(candidate):
        return ""
    return candidate.rsplit("/", 1)[-1]


def _wiley_supplementary_filename(anchor: Any) -> str:
    href = normalize_text(str(anchor.get("href") or ""))
    if not href:
        return ""

    parsed = urllib.parse.urlsplit(href)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    for key in WILEY_SUPPLEMENTARY_FILENAME_QUERY_KEYS:
        for value in query.get(key, []):
            candidate = _wiley_filename_from_query_value(str(value or ""))
            if candidate:
                return candidate
    path = normalize_text(parsed.path)
    if not path or _wiley_supplementary_download_path_is_supported(path):
        return ""
    filename = urllib.parse.unquote(path).rsplit("/", 1)[-1]
    return filename if _wiley_supplementary_filename_is_supported(filename) else ""


def extract_supplementary_assets(
    html_text: str, source_url: str
) -> list[dict[str, str]]:

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
        heading = (
            normalize_text(anchor.get_text(" ", strip=True))
            or filename_hint
            or "Supporting Information"
        )
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


def extract_formula_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    return extract_generic_formula_assets(
        html_text,
        source_url,
        noise_profile=provider_html_rules("wiley").noise_profile,
    )


def extract_scoped_html_assets(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile,
    supplementary_html_text: str | None = None,
) -> list[dict[str, str]]:
    return extract_scoped_assets_with_policy(
        body_html_text,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html_text,
        policy=HtmlAssetExtractionPolicy(
            formula_extractor=extract_formula_assets,
            supplementary_extractor=extract_supplementary_assets,
            supplementary_scope_fallback="empty",
        ),
    )


scoped_asset_extractor = extract_scoped_html_assets
