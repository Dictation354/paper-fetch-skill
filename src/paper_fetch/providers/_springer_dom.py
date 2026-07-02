"""Springer provider-owned HTML extraction and asset helpers."""

from __future__ import annotations

import copy
import re
import urllib.parse
from typing import Any
from collections.abc import Mapping

from ..common_patterns import (
    EXTENDED_DATA_LABEL,
    EXTENDED_DATA_TABLE_PREFIX_PATTERN,
    FIGURE_LABEL_CORE_PATTERN,
    LABEL_NUMBER_PATTERN,
    TABLE_LABEL_PREFIX_PATTERN,
)
from ..extraction.html import decode_html as _decode_html
from ..extraction.html.assets import (
    FULL_SIZE_IMAGE_ATTRS,
    _soup_attr_url,
    looks_like_full_size_asset_url,
)
from ..extraction.html._metadata import (
    parse_html_metadata as parse_generic_html_metadata,
)
from ..extraction.html._runtime import (
    clean_markdown,
    prune_html_tree,
)
from ..extraction.html.language import (
    collect_html_abstract_blocks,
    html_node_language_hint,
)
from ..extraction.html.parsing import choose_parser
from ..extraction.html.semantics import (
    BACK_MATTER_HEADINGS,
    SUPPLEMENTARY_BACK_MATTER_HEADINGS,
    collect_html_section_hints,
    heading_category,
    normalize_section_title,
)
from ..extraction.html.ui_tokens import (
    SPRINGER_FULL_SIZE_IMAGE_LABEL,
    SPRINGER_NATURE_SOURCE_DATA_LABEL,
    SPRINGER_PREVIEW_PHRASE,
)
from ..metadata.types import MetadataMergeRule, merge_metadata_layers
from ..publisher_identity import normalize_doi
from ..utils import dedupe_authors, normalize_text
from ._springer_authors import normalize_display_authors
from .html_springer_nature import (
    clean_springer_nature_text_fragment,
    is_springer_nature_url,
    is_nature_url,
    select_nature_abstract_section,
    select_springer_nature_article_root,
)
from ._html_section_markdown import (
    FIGURE_ACTION_TRAILING_LINK_PATTERN as SPRINGER_FIGURE_TRAILING_LINK_PATTERN,
    render_clean_text_from_html,
)

from bs4 import BeautifulSoup, Tag

SPRINGER_MEDIA_SIZE_SEGMENT_PATTERN = re.compile(r"^(?:lw|w|m|h)\d+(?:h\d+)?$")
SPRINGER_INLINE_FIGURE_SELECTORS = (".c-article-section__figure-item",)
SPRINGER_FIGURE_DESCRIPTION_SELECTORS = (".c-article-section__figure-description",)
# Springer figure headings are extracted from captions, alt text, and page URLs;
# keep the caption regex provider-scoped while deriving its core label syntax.
SPRINGER_FIGURE_LABEL_PATTERN = re.compile(
    rf"\b{FIGURE_LABEL_CORE_PATTERN}\b",
    flags=re.IGNORECASE,
)
SPRINGER_FIGURE_PAGE_NUMBER_PATTERN = re.compile(
    r"/figures/(\d+[A-Za-z]?)\b", flags=re.IGNORECASE
)
SPRINGER_INLINE_EQUATION_URL_PATTERN = re.compile(
    r"(?:ieq|math)[-_]?\d+", flags=re.IGNORECASE
)
SPRINGER_TABLE_LABEL_PATTERN = re.compile(
    rf"\b(?:{EXTENDED_DATA_TABLE_PREFIX_PATTERN}|{TABLE_LABEL_PREFIX_PATTERN})"
    rf"\s*\.?\s*(?P<number>{LABEL_NUMBER_PATTERN})\b",
    flags=re.IGNORECASE,
)
SPRINGER_TABLE_PAGE_NUMBER_PATTERN = re.compile(
    r"/tables/(\d+[A-Za-z]?)\b", flags=re.IGNORECASE
)
SPRINGER_TABLE_IMAGE_NUMBER_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:tab|table)[\s_.%-]*0*([a-z]?\d+[a-z]?)"
    r"(?:[^a-z0-9]|$)",
    flags=re.IGNORECASE,
)
SPRINGER_TABLE_IMAGE_EXTENSION_PATTERN = re.compile(
    r"\.(?:avif|gif|jpe?g|png|tiff?|webp)(?:[?#]|$)",
    flags=re.IGNORECASE,
)
SPRINGER_TABLE_IMAGE_HINT_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:tab|table)(?:[\s_.%-]*\d|[^a-z0-9])",
    flags=re.IGNORECASE,
)
SPRINGER_TABLE_IMAGE_ROOT_SELECTORS = (
    ".c-article-table-container",
    "[data-track-component='table']",
    "[data-component='article-container']",
    "[data-container-type='article']",
    ".container-type-article",
    "[role='main']",
    "main",
    "article",
    ".c-article-body",
    ".main-content",
)
# SITE_UI_COPY_REGRESSION_MARKER: site-owned Springer/Nature table-page chrome;
# rerun Springer table image fixture tests when these tokens change.
# STRUCTURAL_UI_COPY_HOOK: used only to constrain table-image discovery context.
SPRINGER_TABLE_IMAGE_CHROME_NODE_NAMES = frozenset({"header", "nav", "footer", "aside"})
SPRINGER_TABLE_IMAGE_CHROME_CONTEXT_TOKENS = (
    "account",
    "advert",
    "breadcrumb",
    "c-ad",
    "citation",
    "cookie",
    "footer",
    "gpt",
    "header",
    "identity",
    "journal-header",
    "login",
    "logo",
    "menu",
    "metrics",
    "newsletter",
    "recommend",
    "related",
    "search",
    "share",
    "social",
)
SPRINGER_TABLE_IMAGE_REJECT_URL_TOKENS = (
    "/favicons/",
    "/logos/",
    "/static/images/",
    "account",
    "advert",
    "crossmark",
    "favicon",
    "gpt-advert",
    "header-",
    "logo",
    "nature-cms/uploads/product",
    "newsletter",
    "orcid",
    "social",
    "verify.nature.com",
)
SPRINGER_SUPPLEMENTARY_HOST_TOKENS = (
    "static-content.springer.com/esm/",
    "/mediaobjects/",
)
SPRINGER_PREVIEW_SENTENCE_PATTERN = re.compile(
    rf"\b{re.escape(SPRINGER_PREVIEW_PHRASE)}\b[,.!;:]*",
    flags=re.IGNORECASE,
)
SPRINGER_PREVIEW_MARKDOWN_LINE_PATTERN = re.compile(
    rf"(?im)^[ \t>*-]*{re.escape(SPRINGER_PREVIEW_PHRASE)}[,.!;:]*\s*$\n?",
)
SPRINGER_AI_ALT_DISCLAIMER_ID_TOKEN = "ai-alt-disclaimer"
SPRINGER_NON_SUPPLEMENTARY_BACK_MATTER_HEADINGS = (
    BACK_MATTER_HEADINGS - SUPPLEMENTARY_BACK_MATTER_HEADINGS
)
# BACK_MATTER_HEADINGS also includes references, acknowledgements, disclosures,
# and similar prose sections; those are not downloadable supplementary scopes.
SPRINGER_SUPPLEMENTARY_SECTION_TITLES = frozenset(
    (
        BACK_MATTER_HEADINGS
        | {EXTENDED_DATA_LABEL, f"{EXTENDED_DATA_LABEL} figures and tables"}
    )
    - SPRINGER_NON_SUPPLEMENTARY_BACK_MATTER_HEADINGS
)
SPRINGER_EXTENDED_DATA_SECTION_TITLES = frozenset(
    {EXTENDED_DATA_LABEL, f"{EXTENDED_DATA_LABEL} figures and tables"}
)
SPRINGER_SOURCE_DATA_SECTION_TITLES = frozenset({SPRINGER_NATURE_SOURCE_DATA_LABEL})
SPRINGER_SOURCE_DATA_TITLE_PREFIX = SPRINGER_NATURE_SOURCE_DATA_LABEL
SPRINGER_PEER_REVIEW_TOKENS = (
    "peer review",
    "peer reviewer report",
    "peer reviewer reports",
    "transparent peer review",
)


def decode_html(body: bytes, *, content_type: str | None = None) -> str:
    return _decode_html(body, content_type=content_type)


_SPRINGER_BASE_FIRST_SCALAR_KEYS = frozenset(
    {
        "title",
        "journal_title",
        "published",
        "landing_page_url",
        "doi",
        "article_type",
        "citation_fulltext_html_url",
        "citation_abstract_html_url",
    }
)
_SPRINGER_HTML_METADATA_MERGE_RULE = MetadataMergeRule(
    fill_empty=tuple(_SPRINGER_BASE_FIRST_SCALAR_KEYS),
    overwrite=(
        "abstract",
        "raw_meta",
        "lookup_title",
        "lookup_redirect_url",
        "identifier_value",
    ),
    concat_unique=("authors", "keywords"),
    take_first_non_empty=("references",),
)


def parse_html_metadata(html_text: str, source_url: str):
    metadata = parse_generic_html_metadata(html_text, source_url)
    abstract = normalize_text(str(metadata.get("abstract") or ""))
    if abstract and is_springer_nature_url(source_url):
        metadata["abstract"] = clean_springer_nature_text_fragment(abstract)
    metadata["authors"] = normalize_display_authors(
        [
            normalize_text(str(item))
            for item in (metadata.get("authors") or [])
            if normalize_text(str(item))
        ]
    )
    return metadata


def merge_html_metadata(base_metadata, html_metadata):
    base = dict(base_metadata or {})
    html_metadata = dict(html_metadata or {})
    merged = merge_metadata_layers(
        [base, html_metadata],
        rule=_SPRINGER_HTML_METADATA_MERGE_RULE,
    )
    for key in _SPRINGER_BASE_FIRST_SCALAR_KEYS:
        merged[key] = normalize_text(str(merged.get(key) or "")) or None
    merged["abstract"] = normalize_text(str(merged.get("abstract") or "")) or None
    merged["authors"] = dedupe_authors(
        [str(item) for item in (merged.get("authors") or [])]
    )
    merged["keywords"] = list(merged.get("keywords") or [])
    merged["license_urls"] = list(base.get("license_urls") or [])
    merged["fulltext_links"] = list(base.get("fulltext_links") or [])
    if "references" in base:
        merged["references"] = list(base.get("references") or [])
    else:
        merged.pop("references", None)
    merged["raw_meta"] = html_metadata.get("raw_meta", {})
    for key in ("lookup_title", "lookup_redirect_url", "identifier_value"):
        if html_metadata.get(key):
            merged[key] = html_metadata.get(key)
    if not merged.get("doi"):
        merged["doi"] = normalize_doi(str(html_metadata.get("doi") or ""))
    return merged


def _clean_springer_preview_fragment(text: str) -> str:
    cleaned = SPRINGER_PREVIEW_SENTENCE_PATTERN.sub(" ", text or "")
    return clean_springer_nature_text_fragment(cleaned)


def _clean_springer_asset_caption(text: str) -> str:
    cleaned = SPRINGER_FIGURE_TRAILING_LINK_PATTERN.sub("", normalize_text(text or ""))
    return normalize_text(cleaned)


def _clean_springer_preview_markdown(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    cleaned = SPRINGER_PREVIEW_MARKDOWN_LINE_PATTERN.sub("", markdown_text)
    cleaned = SPRINGER_PREVIEW_SENTENCE_PATTERN.sub(" ", cleaned)
    return clean_markdown(cleaned)


def _clean_springer_abstract_sections(
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cleaned_sections: list[dict[str, Any]] = []
    for section in sections:
        cleaned_section = dict(section)
        if cleaned_section.get("text") is not None:
            cleaned_section["text"] = _clean_springer_preview_fragment(
                str(cleaned_section.get("text") or "")
            )
        cleaned_sections.append(cleaned_section)
    return cleaned_sections


def _springer_node_context_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(getattr(node, "name", "") or "")]
    for key in ("id", "data-test"):
        parts.append(normalize_text(str(attrs.get(key) or "")))
    class_values = attrs.get("class")
    if isinstance(class_values, (list, tuple, set)):
        parts.extend(normalize_text(str(item)) for item in class_values)
    else:
        parts.append(normalize_text(str(class_values or "")))
    return " ".join(part.lower() for part in parts if part)


def _strip_ai_alt_disclaimer_references(root: Any) -> None:
    if not isinstance(root, Tag):
        return
    for node in root.select(
        f"[aria-describedby*='{SPRINGER_AI_ALT_DISCLAIMER_ID_TOKEN}']"
    ):
        if not isinstance(node, Tag):
            continue
        described_by = normalize_text(str(node.get("aria-describedby") or ""))
        if not described_by:
            continue
        tokens = [
            token
            for token in described_by.split()
            if SPRINGER_AI_ALT_DISCLAIMER_ID_TOKEN not in normalize_text(token).lower()
        ]
        if tokens:
            node["aria-describedby"] = " ".join(tokens)
        elif node.has_attr("aria-describedby"):
            del node["aria-describedby"]


def _remove_springer_ai_alt_disclaimers(root: Any) -> None:
    if not isinstance(root, Tag):
        return
    removable_nodes: list[Tag] = []
    seen: set[int] = set()

    for node in root.select(f"[id*='{SPRINGER_AI_ALT_DISCLAIMER_ID_TOKEN}']"):
        if isinstance(node, Tag) and id(node) not in seen:
            removable_nodes.append(node)
            seen.add(id(node))

    for node in removable_nodes:
        node.decompose()

    _strip_ai_alt_disclaimer_references(root)


def _normalized_root_html(html_text: str) -> tuple[str, Any]:
    soup = BeautifulSoup(html_text, choose_parser())
    root = (
        select_springer_nature_article_root(soup)
        or soup.select_one("article")
        or soup.select_one("main")
    )
    if root is None:
        root = soup.body or soup
    active_root = copy.deepcopy(root)
    prune_html_tree(active_root)
    _remove_springer_ai_alt_disclaimers(active_root)
    return str(active_root), active_root


def extract_html_extraction_sidecars(
    html_text: str,
    source_url: str,
    *,
    title: str | None = None,
) -> dict[str, Any]:
    cleaned_html, active_root = _normalized_root_html(html_text)
    if active_root is None:
        return {
            "cleaned_html": cleaned_html,
            "abstract_sections": [],
            "section_hints": [],
        }
    if is_nature_url(source_url):
        article_root = select_springer_nature_article_root(active_root) or active_root
        body_root = (
            article_root.select_one("div.c-article-body")
            if isinstance(article_root, Tag)
            else None
        )
        abstract_node = select_nature_abstract_section(body_root or article_root)
        if isinstance(abstract_node, Tag):
            content_root = (
                abstract_node.select_one("div.c-article-section__content")
                or abstract_node
            )
            abstract_text = render_clean_text_from_html(content_root)
            abstract_sections = (
                [
                    {
                        "heading": "Abstract",
                        "text": abstract_text,
                        "language": html_node_language_hint(
                            abstract_node, allow_soft_hints=True
                        ),
                        "kind": "abstract",
                        "order": 0,
                        "source_selector": "section",
                    }
                ]
                if abstract_text
                else []
            )
        else:
            abstract_sections = _clean_springer_abstract_sections(
                collect_html_abstract_blocks(active_root)
            )
    else:
        abstract_sections = _clean_springer_abstract_sections(
            collect_html_abstract_blocks(active_root)
        )
    return {
        "cleaned_html": cleaned_html,
        "abstract_sections": abstract_sections,
        "section_hints": collect_html_section_hints(
            active_root,
            title=title,
            language_hint_resolver=lambda node: html_node_language_hint(
                node, allow_soft_hints=True
            ),
        ),
    }


def _springer_section_title_key(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    for key in ("data-title", "aria-label"):
        value = normalize_text(str(attrs.get(key) or ""))
        if value:
            return normalize_section_title(value)
    heading = node.find(re.compile(r"^h[1-6]$"))
    if isinstance(heading, Tag):
        return normalize_section_title(heading.get_text(" ", strip=True))
    return ""


def _springer_is_descendant_of(node: Any, ancestor: Any) -> bool:
    current = node.parent if isinstance(getattr(node, "parent", None), Tag) else None
    while isinstance(current, Tag):
        if current is ancestor:
            return True
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
    return False


def _springer_is_supplementary_like_section_title(title_key: str) -> bool:
    normalized_title = normalize_section_title(title_key)
    if not normalized_title:
        return False
    if normalized_title in SPRINGER_EXTENDED_DATA_SECTION_TITLES:
        return True
    return (
        normalized_title in SPRINGER_SUPPLEMENTARY_SECTION_TITLES
        and heading_category("h2", normalized_title) == "references_or_back_matter"
    )


def _springer_collect_asset_sections(article_root: Any) -> tuple[list[Any], list[Any]]:
    if not isinstance(article_root, Tag):
        return [], []
    supplementary_sections: list[Any] = []
    source_data_sections: list[Any] = []

    for node in article_root.find_all(["section", "div"]):
        if not isinstance(node, Tag):
            continue
        title_key = _springer_section_title_key(node)
        if not title_key:
            continue
        if any(
            _springer_is_descendant_of(node, existing)
            for existing in [*supplementary_sections, *source_data_sections]
        ):
            continue
        if normalize_section_title(title_key) in SPRINGER_SOURCE_DATA_SECTION_TITLES:
            source_data_sections.append(node)
            continue
        if _springer_is_supplementary_like_section_title(title_key):
            supplementary_sections.append(node)

    return supplementary_sections, source_data_sections


def _springer_merge_scope_fragments(nodes: list[Any]) -> str:
    fragments = [
        str(node)
        for node in nodes
        if isinstance(node, Tag) and normalize_text(str(node))
    ]
    return "\n".join(fragments)


def _extract_asset_html_scope_fragments(
    cleaned_html: str, active_root: Any
) -> tuple[str, str, str]:
    article_root = select_springer_nature_article_root(active_root) or active_root
    if isinstance(article_root, Tag):
        body_root = (
            article_root.select_one("div.c-article-body div.main-content")
            or article_root.select_one("div.c-article-body")
            or article_root.select_one("div.main-content")
            or article_root
        )
    else:
        body_root = active_root

    supplementary_sections, source_data_sections = _springer_collect_asset_sections(
        article_root if isinstance(article_root, Tag) else active_root
    )
    body_html = str(body_root) if isinstance(body_root, Tag) else cleaned_html
    supplementary_html = _springer_merge_scope_fragments(supplementary_sections)
    source_data_html = _springer_merge_scope_fragments(
        [*supplementary_sections, *source_data_sections]
    )
    return body_html, supplementary_html, source_data_html


def _springer_figure_caption(node: Any, soup: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    figcaption = node.find("figcaption")
    if isinstance(figcaption, Tag):
        caption = _clean_springer_asset_caption(figcaption.get_text(" ", strip=True))
        if caption:
            return caption
    image = node.find("img")
    if isinstance(image, Tag):
        described_by = normalize_text(str(image.get("aria-describedby") or ""))
        if described_by:
            described_node = soup.find(id=described_by)
            if isinstance(described_node, Tag):
                caption = _clean_springer_asset_caption(
                    described_node.get_text(" ", strip=True)
                )
                if caption:
                    return caption
    for context in (node, node.parent if isinstance(node.parent, Tag) else None):
        if not isinstance(context, Tag):
            continue
        for selector in SPRINGER_FIGURE_DESCRIPTION_SELECTORS:
            description = context.select_one(selector)
            if isinstance(description, Tag):
                caption = _clean_springer_asset_caption(
                    description.get_text(" ", strip=True)
                )
                if caption:
                    return caption
    return ""


def _springer_figure_page_url(node: Any, source_url: str) -> str:
    if not isinstance(node, Tag):
        return ""
    contexts = [node]
    if isinstance(node.parent, Tag):
        contexts.append(node.parent)
    for context in contexts:
        for anchor in context.find_all("a", href=True):
            href = normalize_text(str(anchor.get("href") or ""))
            if not href or href.startswith("#"):
                continue
            hint_blob = " ".join(
                [
                    normalize_text(anchor.get_text(" ", strip=True)).lower(),
                    normalize_text(str(anchor.get("aria-label") or "")).lower(),
                    normalize_text(str(anchor.get("title") or "")).lower(),
                ]
            )
            if SPRINGER_FULL_SIZE_IMAGE_LABEL in hint_blob or "/figures/" in href:
                return urllib.parse.urljoin(source_url, href)
    return ""


def _springer_figure_heading(
    figure_page_url: str,
    *,
    caption: str,
    alt_text: str,
) -> str:
    for candidate in (caption, alt_text):
        match = SPRINGER_FIGURE_LABEL_PATTERN.match(normalize_text(candidate))
        if match:
            return f"Figure {match.group(1)}"
    page_match = SPRINGER_FIGURE_PAGE_NUMBER_PATTERN.search(
        normalize_text(figure_page_url)
    )
    if page_match:
        return f"Figure {page_match.group(1)}"
    for candidate in (caption, alt_text):
        match = SPRINGER_FIGURE_LABEL_PATTERN.search(normalize_text(candidate))
        if match:
            return f"Figure {match.group(1)}"
    return caption[:80] or alt_text or "Figure"


def _springer_figure_asset_key(asset: Mapping[str, Any]) -> str:
    for field in ("figure_page_url", "full_size_url", "url", "preview_url"):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return ""


def _springer_figure_asset_score(asset: Mapping[str, Any]) -> int:
    score = 0
    url_blob = " ".join(
        normalize_text(str(asset.get(field) or "")).lower()
        for field in ("full_size_url", "url", "preview_url")
    )
    if normalize_text(str(asset.get("figure_page_url") or "")):
        score += 100
    if "fig" in url_blob:
        score += 40
    if SPRINGER_INLINE_EQUATION_URL_PATTERN.search(url_blob):
        score -= 40
    if normalize_text(str(asset.get("full_size_url") or "")):
        score += 20
    if normalize_text(str(asset.get("preview_url") or "")):
        score += 10
    if normalize_text(str(asset.get("caption") or "")):
        score += 5
    return score


def promote_springer_media_url_to_full_size(url: str | None) -> str | None:
    candidate = normalize_text(url)
    if not candidate:
        return None
    parsed = urllib.parse.urlsplit(candidate)
    hostname = normalize_text(parsed.netloc).lower()
    if "media.springernature.com" not in hostname:
        return None
    path = parsed.path or ""
    if not path.startswith("/"):
        return None
    segments = path.lstrip("/").split("/", 1)
    if len(segments) < 2:
        return None
    size_segment, remainder = segments
    if size_segment == "full":
        return urllib.parse.urlunsplit(
            (
                parsed.scheme or "https",
                parsed.netloc,
                path,
                parsed.query,
                parsed.fragment,
            )
        )
    if not SPRINGER_MEDIA_SIZE_SEGMENT_PATTERN.match(size_segment):
        return None
    if "/springer-static/" not in f"/{remainder}":
        return None
    return urllib.parse.urlunsplit(
        (
            parsed.scheme or "https",
            parsed.netloc,
            f"/full/{remainder}",
            parsed.query,
            parsed.fragment,
        )
    )


def extract_full_size_figure_image_url(html_text: str, source_url: str) -> str | None:
    metadata = parse_html_metadata(html_text, source_url)
    raw_meta = metadata.get("raw_meta") if isinstance(metadata, Mapping) else {}
    if isinstance(raw_meta, Mapping):
        for key in ("twitter:image", "twitter:image:src", "og:image"):
            for value in raw_meta.get(key, []):
                candidate = urllib.parse.urljoin(
                    source_url, normalize_text(str(value or ""))
                )
                if candidate:
                    return candidate
    soup = BeautifulSoup(html_text, choose_parser())
    fallback_candidate = None
    promoted_candidate = None
    seen: set[str] = set()
    for tag in soup.find_all(["img", "source"]):
        candidate = _soup_attr_url(
            tag,
            *FULL_SIZE_IMAGE_ATTRS,
            "data-src",
            "src",
            "data-lazy-src",
            "srcset",
            "data-srcset",
        )
        if not candidate:
            continue
        absolute_candidate = urllib.parse.urljoin(source_url, candidate)
        if not absolute_candidate or absolute_candidate in seen:
            continue
        seen.add(absolute_candidate)
        if looks_like_full_size_asset_url(absolute_candidate.lower()):
            return absolute_candidate
        if promoted_candidate is None:
            promoted_candidate = promote_springer_media_url_to_full_size(
                absolute_candidate
            )
        if fallback_candidate is None:
            fallback_candidate = absolute_candidate
    return promoted_candidate or fallback_candidate


def _springer_table_number_from_label(label: str) -> str:
    match = SPRINGER_TABLE_LABEL_PATTERN.search(normalize_text(label).lower())
    return normalize_text(match.group("number")).lower() if match else ""


def _springer_table_number_from_url(table_url: str) -> str:
    match = SPRINGER_TABLE_PAGE_NUMBER_PATTERN.search(
        urllib.parse.urlparse(table_url).path
    )
    return normalize_text(match.group(1)).lower() if match else ""


def _springer_expected_table_number(label: str, table_url: str) -> str:
    return _springer_table_number_from_label(label) or _springer_table_number_from_url(
        table_url
    )


def _springer_table_image_url_blob(url: str) -> str:
    return urllib.parse.unquote(normalize_text(url)).lower()


def _springer_table_image_number_from_url(url: str) -> str:
    match = SPRINGER_TABLE_IMAGE_NUMBER_PATTERN.search(
        _springer_table_image_url_blob(url)
    )
    return normalize_text(match.group(1)).lower() if match else ""


def _springer_table_image_url_has_expected_number(url: str, table_number: str) -> bool:
    if not table_number:
        return False
    return _springer_table_image_number_from_url(url) == table_number.lower()


def _springer_table_image_url_has_table_semantics(url: str) -> bool:
    blob = _springer_table_image_url_blob(url)
    if SPRINGER_TABLE_IMAGE_HINT_PATTERN.search(blob):
        return True
    return (
        "/springer-static/esm/" in blob and "/mediaobjects/" in blob and "_tab" in blob
    )


def _springer_table_image_url_is_springer_esm_mediaobject(url: str) -> bool:
    blob = _springer_table_image_url_blob(url)
    return "/springer-static/esm/" in blob and "/mediaobjects/" in blob


def _springer_table_image_url_is_chrome(url: str) -> bool:
    blob = _springer_table_image_url_blob(url)
    if not blob or blob.startswith(("data:", "javascript:", "mailto:")):
        return True
    return any(token in blob for token in SPRINGER_TABLE_IMAGE_REJECT_URL_TOKENS)


def _springer_node_is_table_image_chrome(node: Any) -> bool:
    current = node
    while isinstance(current, Tag):
        name = normalize_text(getattr(current, "name", "")).lower()
        if name in SPRINGER_TABLE_IMAGE_CHROME_NODE_NAMES:
            return True
        context_text = _springer_node_context_text(current)
        if any(
            token in context_text
            for token in SPRINGER_TABLE_IMAGE_CHROME_CONTEXT_TOKENS
        ):
            return True
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
    return False


def _springer_node_is_table_content_context(node: Any) -> bool:
    current = node
    while isinstance(current, Tag):
        context_text = _springer_node_context_text(current)
        data_container_section = normalize_text(
            str(current.get("data-container-section") or "")
        ).lower()
        data_track_component = normalize_text(
            str(current.get("data-track-component") or "")
        ).lower()
        if (
            current.name == "table"
            or "c-article-table" in context_text
            or "table-container" in context_text
            or data_container_section == "table"
            or data_track_component == "table"
        ):
            return True
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
    return False


def _springer_table_image_roots(soup: BeautifulSoup) -> list[Tag]:
    roots: list[Tag] = []
    seen: set[int] = set()
    for selector in SPRINGER_TABLE_IMAGE_ROOT_SELECTORS:
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag) and id(match) not in seen:
                seen.add(id(match))
                roots.append(match)
    if roots:
        return roots
    body = soup.body
    return [body] if isinstance(body, Tag) else [soup]


def _springer_table_image_candidate_urls(
    root: Tag,
    source_url: str,
) -> list[tuple[str, Tag]]:
    candidates: list[tuple[str, Tag]] = []
    for tag in root.find_all(["img", "source", "a"]):
        if not isinstance(tag, Tag):
            continue
        if tag.name == "a":
            candidate = normalize_text(str(tag.get("href") or ""))
        else:
            candidate = _soup_attr_url(
                tag,
                *FULL_SIZE_IMAGE_ATTRS,
                "data-src",
                "src",
                "data-lazy-src",
                "srcset",
                "data-srcset",
            )
        if candidate:
            candidates.append((urllib.parse.urljoin(source_url, candidate), tag))
    return candidates


def _springer_table_meta_image_urls(
    soup: BeautifulSoup,
    source_url: str,
) -> list[str]:
    urls: list[str] = []
    for tag in soup.find_all("meta"):
        if not isinstance(tag, Tag):
            continue
        key = normalize_text(str(tag.get("property") or tag.get("name") or "")).lower()
        if key not in {"og:image", "twitter:image", "twitter:image:src"}:
            continue
        candidate = normalize_text(str(tag.get("content") or ""))
        if candidate:
            urls.append(urllib.parse.urljoin(source_url, candidate))
    return urls


def _springer_table_image_candidate_score(
    url: str,
    *,
    node: Tag | None,
    table_number: str,
    from_meta: bool,
) -> int:
    if not SPRINGER_TABLE_IMAGE_EXTENSION_PATTERN.search(url):
        return -1
    if _springer_table_image_url_is_chrome(url):
        return -1
    if node is not None and _springer_node_is_table_image_chrome(node):
        return -1

    candidate_number = _springer_table_image_number_from_url(url)
    if candidate_number and table_number and candidate_number != table_number:
        return -1

    number_matches = _springer_table_image_url_has_expected_number(url, table_number)
    has_table_semantics = _springer_table_image_url_has_table_semantics(url)
    is_esm_mediaobject = _springer_table_image_url_is_springer_esm_mediaobject(url)
    is_table_context = node is not None and _springer_node_is_table_content_context(
        node
    )
    if not (
        number_matches
        or (is_esm_mediaobject and has_table_semantics)
        or (is_table_context and has_table_semantics)
    ):
        return -1
    if from_meta and not (
        number_matches or (is_esm_mediaobject and has_table_semantics)
    ):
        return -1

    blob = _springer_table_image_url_blob(url)
    score = 0
    if number_matches:
        score += 120
    if has_table_semantics:
        score += 60
    if is_esm_mediaobject:
        score += 55
    if "media.springernature.com" in urllib.parse.urlparse(url).netloc.lower():
        score += 25
    if looks_like_full_size_asset_url(blob):
        score += 10
    if is_table_context:
        score += 20
    if node is not None and node.name == "img":
        score += 5
    if "as=webp" in blob or blob.endswith(".webp"):
        score -= 5
    return score
