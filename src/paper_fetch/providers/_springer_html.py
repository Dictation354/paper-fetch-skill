"""Springer provider-owned HTML extraction and asset helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Mapping

from ..extraction.html import decode_html as _decode_html
from ..extraction.html._assets import (
    FULL_SIZE_IMAGE_ATTRS,
    PREVIEW_IMAGE_ATTRS,
    FigurePageFetcher,
    download_figure_assets as download_generic_figure_assets,
    extract_figure_assets as extract_generic_figure_assets,
    extract_formula_assets as extract_generic_formula_assets,
    extract_supplementary_assets as extract_generic_supplementary_assets,
    looks_like_full_size_asset_url,
)
from ..extraction.html._metadata import merge_html_metadata as merge_generic_html_metadata
from ..extraction.html._metadata import parse_html_metadata as parse_generic_html_metadata
from ..extraction.html._runtime import (
    clean_markdown,
    extract_article_markdown_from_cleaned_html,
    prune_html_tree,
)
from ..extraction.html.language import collect_html_abstract_blocks, html_node_language_hint
from ..extraction.html.semantics import collect_html_section_hints
from ..utils import dedupe_authors, normalize_text
from ._browser_workflow_authors import (
    extract_jsonld_authors as extract_common_jsonld_authors,
    extract_meta_authors as extract_common_meta_authors,
    extract_selector_authors as extract_common_selector_authors,
    looks_like_author_name,
)
from ._html_references import extract_numbered_references_from_html
from .html_springer_nature import (
    clean_springer_nature_text_fragment,
    extract_springer_nature_markdown,
    is_springer_nature_url,
    is_nature_url,
    select_nature_abstract_section,
    select_springer_nature_article_root,
)
from ._html_section_markdown import render_clean_text_from_html

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

SPRINGER_MEDIA_SIZE_SEGMENT_PATTERN = re.compile(r"^(?:lw|w|m|h)\d+(?:h\d+)?$")
SPRINGER_INLINE_FIGURE_SELECTORS = (".c-article-section__figure-item",)
SPRINGER_FIGURE_DESCRIPTION_SELECTORS = (".c-article-section__figure-description",)
SPRINGER_FIGURE_LABEL_PATTERN = re.compile(r"\bfigure\s+(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
SPRINGER_FIGURE_PAGE_NUMBER_PATTERN = re.compile(r"/figures/(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
SPRINGER_INLINE_EQUATION_URL_PATTERN = re.compile(r"(?:ieq|math)[-_]?\d+", flags=re.IGNORECASE)
SPRINGER_SUPPLEMENTARY_HOST_TOKENS = (
    "static-content.springer.com/esm/",
    "/mediaobjects/",
)
SPRINGER_PREVIEW_SENTENCE_PATTERN = re.compile(
    r"\bthis is a preview of subscription content\b[,.!;:]*",
    flags=re.IGNORECASE,
)
SPRINGER_PREVIEW_MARKDOWN_LINE_PATTERN = re.compile(
    r"(?im)^[ \t>*-]*this is a preview of subscription content[,.!;:]*\s*$\n?",
)
SPRINGER_FIGURE_TRAILING_LINK_PATTERN = re.compile(
    r"\b(?:PowerPoint slide|Full size image)\b.*$",
    flags=re.IGNORECASE,
)
SPRINGER_AI_ALT_DISCLAIMER_ID_TOKEN = "ai-alt-disclaimer"
SPRINGER_AI_ALT_DISCLAIMER_TEXT = "The alternative text for this image may have been generated using AI."
SPRINGER_ARTICLE_JSONLD_TYPES = frozenset(
    {
        "article",
        "newsarticle",
        "medicalscholarlyarticle",
        "scholarlyarticle",
        "webpage",
    }
)
SPRINGER_IGNORED_AUTHOR_TEXT = {
    "authors",
    "author information",
    "authors and affiliations",
    "view author information",
}
SPRINGER_COLLECTIVE_AUTHOR_TOKENS = {
    "collaboration",
    "committee",
    "consortium",
    "group",
    "initiative",
    "network",
    "project",
    "society",
    "team",
}


def decode_html(body: bytes) -> str:
    return _decode_html(body)


def _looks_like_collective_author_text(text: str) -> bool:
    normalized = normalize_text(text).lower()
    if not normalized:
        return False
    if "et al" in normalized:
        return True
    return any(token in normalized.split() for token in SPRINGER_COLLECTIVE_AUTHOR_TOKENS)


def _normalize_display_author_name(name: str) -> str:
    normalized = normalize_text(name)
    if not normalized or normalized.count(",") != 1:
        return normalized
    left, right = [part.strip() for part in normalized.split(",", 1)]
    if not left or not right:
        return normalized
    if not (looks_like_author_name(left) and looks_like_author_name(right)):
        return normalized
    if _looks_like_collective_author_text(left) or _looks_like_collective_author_text(right):
        return normalized
    return normalize_text(f"{right} {left}")


def _normalize_display_authors(authors: list[str]) -> list[str]:
    return dedupe_authors([_normalize_display_author_name(author) for author in authors if normalize_text(author)])


def normalize_display_authors(authors: list[str]) -> list[str]:
    return _normalize_display_authors(authors)


def _extract_meta_authors(html_text: str) -> list[str]:
    return _normalize_display_authors(extract_common_meta_authors(html_text, keys={"citation_author"}))


def _extract_jsonld_authors(html_text: str) -> list[str]:
    return _normalize_display_authors(
        extract_common_jsonld_authors(
            html_text,
            article_types=SPRINGER_ARTICLE_JSONLD_TYPES,
            author_paths=("mainEntity.author",),
        )
    )


def _node_author_text(node: Any) -> str:
    return normalize_text(node.get_text(" ", strip=True)) if Tag is not None and isinstance(node, Tag) else ""


def _extract_dom_authors(html_text: str) -> list[str]:
    return _normalize_display_authors(
        extract_common_selector_authors(
            html_text,
            selectors=(
                "[data-test='author-name']",
                ".c-article-author-list [itemprop='name']",
                ".c-article-author-list li",
                ".authors__name",
            ),
            ignored_text=SPRINGER_IGNORED_AUTHOR_TEXT,
            node_text=_node_author_text,
            reject_email=True,
            reject_affiliation_prefixes=("author information",),
        )
    )


def extract_authors(html_text: str) -> list[str]:
    meta_authors = _extract_meta_authors(html_text)
    if meta_authors:
        return meta_authors
    jsonld_authors = _extract_jsonld_authors(html_text)
    if jsonld_authors:
        return jsonld_authors
    return _extract_dom_authors(html_text)


def parse_html_metadata(html_text: str, source_url: str):
    metadata = parse_generic_html_metadata(html_text, source_url)
    abstract = normalize_text(str(metadata.get("abstract") or ""))
    if abstract and is_springer_nature_url(source_url):
        metadata["abstract"] = clean_springer_nature_text_fragment(abstract)
    metadata["authors"] = _normalize_display_authors(
        [normalize_text(str(item)) for item in (metadata.get("authors") or []) if normalize_text(str(item))]
    )
    return metadata


def merge_html_metadata(base_metadata, html_metadata):
    return merge_generic_html_metadata(base_metadata, html_metadata)


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


def _clean_springer_abstract_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned_sections: list[dict[str, Any]] = []
    for section in sections:
        cleaned_section = dict(section)
        if cleaned_section.get("text") is not None:
            cleaned_section["text"] = _clean_springer_preview_fragment(str(cleaned_section.get("text") or ""))
        cleaned_sections.append(cleaned_section)
    return cleaned_sections


def _springer_node_context_text(node: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
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


def _springer_is_figure_or_illustration_context(node: Any) -> bool:
    current = node
    while Tag is not None and isinstance(current, Tag):
        context_text = _springer_node_context_text(current)
        if current.name == "figure" or "figure" in context_text or "illustration" in context_text:
            return True
        current = current.parent if isinstance(getattr(current, "parent", None), Tag) else None
    return False


def _strip_ai_alt_disclaimer_references(root: Any) -> None:
    if Tag is None or not isinstance(root, Tag):
        return
    for node in root.select(f"[aria-describedby*='{SPRINGER_AI_ALT_DISCLAIMER_ID_TOKEN}']"):
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
    if Tag is None or not isinstance(root, Tag):
        return
    removable_nodes: list[Tag] = []
    seen: set[int] = set()

    for node in root.select(f"[id*='{SPRINGER_AI_ALT_DISCLAIMER_ID_TOKEN}']"):
        if isinstance(node, Tag) and id(node) not in seen:
            removable_nodes.append(node)
            seen.add(id(node))

    target_text = normalize_text(SPRINGER_AI_ALT_DISCLAIMER_TEXT).lower()
    for text_node in list(root.find_all(string=True)):
        if normalize_text(str(text_node)).lower() != target_text:
            continue
        parent = text_node.parent if isinstance(getattr(text_node, "parent", None), Tag) else None
        if parent is None or not _springer_is_figure_or_illustration_context(parent):
            continue
        if id(parent) not in seen:
            removable_nodes.append(parent)
            seen.add(id(parent))

    for node in removable_nodes:
        node.decompose()

    _strip_ai_alt_disclaimer_references(root)


def _normalized_root_html(html_text: str) -> tuple[str, Any]:
    if BeautifulSoup is None:
        return html_text, None
    soup = BeautifulSoup(html_text, "html.parser")
    root = select_springer_nature_article_root(soup) or soup.select_one("article") or soup.select_one("main")
    if root is None:
        root = soup.body or soup
    candidate_soup = BeautifulSoup(str(root), "html.parser")
    active_root = candidate_soup.body or candidate_soup
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
        body_root = article_root.select_one("div.c-article-body") if isinstance(article_root, Tag) else None
        abstract_node = select_nature_abstract_section(body_root or article_root)
        if isinstance(abstract_node, Tag):
            content_root = abstract_node.select_one("div.c-article-section__content") or abstract_node
            abstract_text = render_clean_text_from_html(content_root)
            abstract_sections = (
                [
                    {
                        "heading": "Abstract",
                        "text": abstract_text,
                        "language": html_node_language_hint(abstract_node, allow_soft_hints=True),
                        "kind": "abstract",
                        "order": 0,
                        "source_selector": "section",
                    }
                ]
                if abstract_text
                else []
            )
        else:
            abstract_sections = _clean_springer_abstract_sections(collect_html_abstract_blocks(active_root))
    else:
        abstract_sections = _clean_springer_abstract_sections(collect_html_abstract_blocks(active_root))
    return {
        "cleaned_html": cleaned_html,
        "abstract_sections": abstract_sections,
        "section_hints": collect_html_section_hints(
            active_root,
            title=title,
            language_hint_resolver=lambda node: html_node_language_hint(node, allow_soft_hints=True),
        ),
    }


def extract_article_markdown(cleaned_html: str, source_url: str) -> str:
    custom_markdown = extract_springer_nature_markdown(cleaned_html, source_url)
    if custom_markdown:
        return custom_markdown
    return extract_article_markdown_from_cleaned_html(cleaned_html, source_url)


def extract_html_payload(
    html_text: str,
    source_url: str,
    *,
    title: str | None = None,
) -> dict[str, Any]:
    extraction_sidecars = extract_html_extraction_sidecars(html_text, source_url, title=title)
    markdown_text = _clean_springer_preview_markdown(
        clean_markdown(extract_article_markdown(extraction_sidecars["cleaned_html"], source_url))
    )
    extracted_authors = extract_authors(html_text)
    extracted_references = extract_numbered_references_from_html(html_text)
    return {
        "markdown_text": markdown_text,
        "abstract_sections": list(extraction_sidecars["abstract_sections"]),
        "section_hints": list(extraction_sidecars["section_hints"]),
        "cleaned_html": extraction_sidecars["cleaned_html"],
        "extracted_authors": extracted_authors,
        "references": extracted_references,
    }


def _first_url_from_srcset(value: str | None) -> str:
    srcset = normalize_text(value)
    if not srcset:
        return ""
    first = srcset.split(",", 1)[0].strip()
    if not first:
        return ""
    return first.split()[0].strip()


def _soup_attr_url(tag: Any, *attrs: str) -> str:
    if Tag is None or not isinstance(tag, Tag):
        return ""
    for attr in attrs:
        raw = tag.get(attr)
        if not raw:
            continue
        candidate = _first_url_from_srcset(raw) if attr.endswith("srcset") else normalize_text(str(raw))
        if candidate:
            return candidate
    return ""


def _springer_figure_caption(node: Any, soup: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
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
                caption = _clean_springer_asset_caption(described_node.get_text(" ", strip=True))
                if caption:
                    return caption
    for context in (node, node.parent if isinstance(node.parent, Tag) else None):
        if not isinstance(context, Tag):
            continue
        for selector in SPRINGER_FIGURE_DESCRIPTION_SELECTORS:
            description = context.select_one(selector)
            if isinstance(description, Tag):
                caption = _clean_springer_asset_caption(description.get_text(" ", strip=True))
                if caption:
                    return caption
    return ""


def _springer_figure_page_url(node: Any, source_url: str) -> str:
    if Tag is None or not isinstance(node, Tag):
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
            if "full size image" in hint_blob or "/figures/" in href:
                return urllib.parse.urljoin(source_url, href)
    return ""


def _springer_figure_heading(
    figure_page_url: str,
    *,
    caption: str,
    alt_text: str,
) -> str:
    for candidate in (caption, alt_text):
        match = SPRINGER_FIGURE_LABEL_PATTERN.search(normalize_text(candidate))
        if match:
            return f"Figure {match.group(1)}"
    page_match = SPRINGER_FIGURE_PAGE_NUMBER_PATTERN.search(normalize_text(figure_page_url))
    if page_match:
        return f"Figure {page_match.group(1)}"
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
        return urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc, path, parsed.query, parsed.fragment))
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
                candidate = urllib.parse.urljoin(source_url, normalize_text(str(value or "")))
                if candidate:
                    return candidate
    if BeautifulSoup is None:
        return None
    soup = BeautifulSoup(html_text, "html.parser")
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
            promoted_candidate = promote_springer_media_url_to_full_size(absolute_candidate)
        if fallback_candidate is None:
            fallback_candidate = absolute_candidate
    return promoted_candidate or fallback_candidate


def extract_figure_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return extract_generic_figure_assets(html_text, source_url)
    soup = BeautifulSoup(html_text, "html.parser")
    candidates: list[Any] = []
    seen_nodes: set[int] = set()
    for node in soup.find_all("figure"):
        if id(node) not in seen_nodes:
            seen_nodes.add(id(node))
            candidates.append(node)
    for selector in SPRINGER_INLINE_FIGURE_SELECTORS:
        for node in soup.select(selector):
            if id(node) not in seen_nodes:
                seen_nodes.add(id(node))
                candidates.append(node)

    assets_by_key: dict[str, dict[str, str]] = {}
    fallback_assets: list[dict[str, str]] = []
    for node in candidates:
        if not isinstance(node, Tag):
            continue
        image = node.find("img")
        source = node.find("source")
        preview_url = _soup_attr_url(image, *PREVIEW_IMAGE_ATTRS) if image else ""
        if not preview_url:
            preview_url = _soup_attr_url(source, "srcset", "data-srcset") if source else ""
        full_size_url = _soup_attr_url(image, *FULL_SIZE_IMAGE_ATTRS) if image else ""
        if not full_size_url:
            full_size_url = _soup_attr_url(source, *FULL_SIZE_IMAGE_ATTRS) if source else ""
        absolute_preview = urllib.parse.urljoin(source_url, preview_url) if preview_url else ""
        absolute_full = urllib.parse.urljoin(source_url, full_size_url) if full_size_url else ""
        promoted_preview = promote_springer_media_url_to_full_size(absolute_preview)
        figure_page_url = _springer_figure_page_url(node, source_url)
        caption = _springer_figure_caption(node, soup)
        alt_text = normalize_text(str(image.get("alt") or "")) if isinstance(image, Tag) else ""
        heading = _springer_figure_heading(
            figure_page_url,
            caption=caption,
            alt_text=alt_text,
        )
        if not absolute_preview and not absolute_full and not figure_page_url and not caption:
            continue
        asset = {
            "kind": "figure",
            "heading": heading,
            "caption": caption or alt_text,
            "url": absolute_full or promoted_preview or absolute_preview,
            "section": "body",
        }
        if absolute_preview:
            asset["preview_url"] = absolute_preview
        if absolute_full:
            asset["full_size_url"] = absolute_full
        elif promoted_preview:
            asset["full_size_url"] = promoted_preview
        if figure_page_url:
            asset["figure_page_url"] = figure_page_url
        key = _springer_figure_asset_key(asset)
        if not key:
            fallback_assets.append(asset)
            continue
        existing = assets_by_key.get(key)
        if existing is None:
            assets_by_key[key] = asset
        else:
            if _springer_figure_asset_score(asset) > _springer_figure_asset_score(existing):
                preserved_path = existing.get("path")
                existing.clear()
                existing.update(asset)
                if preserved_path and not existing.get("path"):
                    existing["path"] = preserved_path
            if len(normalize_text(asset.get("caption") or "")) > len(normalize_text(existing.get("caption") or "")):
                existing["caption"] = asset["caption"]
            if len(normalize_text(asset.get("heading") or "")) > len(normalize_text(existing.get("heading") or "")):
                existing["heading"] = asset["heading"]
            if asset.get("full_size_url") and not existing.get("full_size_url"):
                existing["full_size_url"] = asset["full_size_url"]
            if asset.get("preview_url") and not existing.get("preview_url"):
                existing["preview_url"] = asset["preview_url"]
    deduped_assets = list(assets_by_key.values()) + fallback_assets
    return deduped_assets or extract_generic_figure_assets(html_text, source_url)


def extract_supplementary_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return extract_generic_supplementary_assets(html_text, source_url)
    soup = BeautifulSoup(html_text, "html.parser")
    assets: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = normalize_text(str(anchor.get("href") or ""))
        text = normalize_text(anchor.get_text(" ", strip=True)).lower()
        if not href or href.startswith("#"):
            continue
        lowered_href = href.lower()
        if not (
            any(token in text for token in ("supplementary", "extended data", "source data", "peer review"))
            or any(token in lowered_href for token in SPRINGER_SUPPLEMENTARY_HOST_TOKENS)
            or any(token in lowered_href for token in (".pdf", ".csv", ".xlsx", ".zip"))
        ):
            continue
        url = urllib.parse.urljoin(source_url, href)
        if url in seen:
            continue
        seen.add(url)
        assets.append(
            {
                "kind": "supplementary",
                "heading": normalize_text(anchor.get_text(" ", strip=True)) or "Supplementary Material",
                "caption": "",
                "section": "supplementary",
                "url": url,
            }
        )
    return assets or extract_generic_supplementary_assets(html_text, source_url)


def extract_html_assets(
    html_text: str,
    source_url: str,
    *,
    asset_profile,
) -> list[dict[str, str]]:
    assets = extract_figure_assets(html_text, source_url)
    assets.extend(extract_generic_formula_assets(html_text, source_url))
    if asset_profile == "all":
        assets.extend(extract_supplementary_assets(html_text, source_url))
    return assets


def figure_download_candidates(
    transport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: FigurePageFetcher | None = None,
) -> list[str]:
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    preview_url = normalize_text(str(asset.get("preview_url") or "")) or primary_url
    candidates: list[str] = []
    if direct_full_size_url:
        candidates.append(direct_full_size_url)
    promoted_preview = promote_springer_media_url_to_full_size(primary_url)
    if promoted_preview:
        candidates.append(promoted_preview)
    if primary_url and looks_like_full_size_asset_url(primary_url):
        candidates.append(primary_url)

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url:
        try:
            if figure_page_fetcher is not None:
                page_result = figure_page_fetcher(figure_page_url)
                if page_result is None:
                    raise ValueError("missing figure-page HTML")
                page_html, page_url = page_result
            else:
                response = transport.request(
                    "GET",
                    figure_page_url,
                    headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
                    timeout=20,
                    retry_on_rate_limit=True,
                    retry_on_transient=True,
                )
                page_html = decode_html(response["body"])
                page_url = str(response["url"] or figure_page_url)
            full_size_url = extract_full_size_figure_image_url(page_html, page_url)
            if full_size_url:
                candidates.append(full_size_url)
        except Exception:
            pass
    if preview_url:
        candidates.append(preview_url)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def download_figure_assets(
    transport,
    *,
    article_id: str,
    assets: list[dict[str, str]],
    output_dir,
    user_agent: str,
    asset_profile="all",
    figure_page_fetcher: FigurePageFetcher | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    seed_urls: list[str] | None = None,
):
    return download_generic_figure_assets(
        transport,
        article_id=article_id,
        assets=assets,
        output_dir=output_dir,
        user_agent=user_agent,
        asset_profile=asset_profile,
        figure_page_fetcher=figure_page_fetcher,
        browser_context_seed=browser_context_seed,
        seed_urls=seed_urls,
        candidate_builder=figure_download_candidates,
    )
