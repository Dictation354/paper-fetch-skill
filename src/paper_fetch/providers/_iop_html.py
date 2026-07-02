"""IOP Publishing provider-owned HTML helpers."""

from __future__ import annotations

import re
from typing import Any
from collections.abc import Mapping
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..extraction.html._metadata import parse_html_metadata
from ..extraction.html.assets import (
    extract_figure_assets,
    extract_supplementary_assets,
)
from ..extraction.html.formula_rules import is_tex_formula_script_node
from ..extraction.html.parsing import choose_parser
from ..extraction.html.provider_rules import COMMON_ACCESS_BLOCK_TOKENS
from ..models.markdown import (
    image_reference_candidates,
    image_references_match,
    iter_markdown_images,
)
from ..publisher_identity import normalize_doi
from ..quality.html_signals import TextMarkerRule, TextMarkerSignalSet
from ..utils import normalize_text
from ._html_references import (
    extract_numbered_references_from_soup,
)
from . import browser_workflow


IOP_NOISE_PROFILE = "iop"

# SITE_UI_COPY_REGRESSION_MARKER: IOPScience article chrome selectors and labels.
IOP_SITE_RULE_OVERRIDES: dict[str, object] = {
    "candidate_selectors": [
        "#article",
        "#article-content",
        "#article-full-text",
        "#fulltext",
        "#full-text",
        ".article-content",
        ".article-body",
        ".article-full-text",
        ".article-page",
        ".article-text",
        "[property='articleBody']",
        "[itemprop='articleBody']",
    ],
    "remove_selectors": [
        ".article-tools",
        ".article-metrics",
        ".metrics",
        ".right-rail",
        ".related-content",
        ".recommended-articles",
        ".toc",
        ".download-options",
        ".citation-tools",
        ".share",
        ".cookie-banner",
        ".access-widget",
        ".iopscience-nav",
        ".js-article-toolbar",
    ],
    "drop_keywords": {
        "article-tools",
        "article-metrics",
        "right-rail",
        "download",
        "citation",
    },
    "drop_text": {
        "Download PDF",
        "Export citation",
        "Sign up for alerts",
    },
}

IOP_EXTRACTION_CLEANUP_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "button",
    "input",
    "select",
    "textarea",
    ".article-tools",
    ".article-metrics",
    ".metrics",
    ".right-rail",
    ".related-content",
    ".recommended-articles",
    ".toc",
    ".download-options",
    ".citation-tools",
    ".share",
    ".cookie-banner",
    ".access-widget",
    ".iopscience-nav",
    ".js-article-toolbar",
)
IOP_FORMULA_CONTAINER_TOKENS = ("display-eqn", "inline-eqn", "tex")
IOP_DISPLAY_FORMULA_SELECTORS = (".display-eqn",)
IOP_ACCEPTED_FIGURE_PREVIEW_URL_TOKENS = ("_online.",)
IOP_HIGH_RESOLUTION_FIGURE_URL_PATTERN = re.compile(
    r"(?P<stem>.+)_(?:lr|online)(?P<suffix>\.(?:jpe?g|png|gif|webp))(?:[?#].*)?$",
    re.IGNORECASE,
)
# SITE_UI_COPY_REGRESSION_MARKER: IOPScience article action labels; keep tied to provider cleanup tests.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup policy removes these only from IOP article chrome.
IOP_MARKDOWN_PROMO_TOKENS = (
    "download pdf",
    "export citation",
    "sign up for alerts",
    "article metrics",
    "permissions",
)
# SITE_UI_COPY_REGRESSION_MARKER: IOPScience post-article chrome labels.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup policy uses these as post-body boundaries, not global denylist text.
IOP_POST_CONTENT_BREAK_TOKENS = (
    "about this article",
    "article metrics",
    "permissions",
    "related content",
    "cited by",
)
# SITE_UI_COPY_REGRESSION_MARKER: IOPScience abstract export controls.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup removes these only from IOP abstract payloads.
IOP_ABSTRACT_TRAILING_CHROME_TOKENS = (
    "Export citation and abstract",
    "Export citation",
)
# SITE_UI_COPY_REGRESSION_MARKER: IOPScience figure download action labels.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup removes these only from IOP figure captions.
IOP_FIGURE_DOWNLOAD_PATTERN = re.compile(
    r"\s*Download figure:\s*Standard image\s*High-resolution image",
    re.IGNORECASE,
)
IOP_DUPLICATE_MARKDOWN_FIGURE_LABEL_PATTERN = re.compile(
    r"(\*\*Figure\s+(?:[A-Za-z]\.)?\d+\.?\*\*)\s+\1\s*",
    re.IGNORECASE,
)
IOP_DUPLICATE_TEXT_FIGURE_LABEL_PATTERN = re.compile(
    r"^(Figure\s+(?:[A-Za-z]\.)?\d+\.?)\s+\1\s+",
    re.IGNORECASE,
)
IOP_FRONT_MATTER_EXACT_TEXTS = (
    "iop publishing",
    "iopscience",
    "open access",
    "paper",
)
IOP_FRONT_MATTER_CONTAINS_TOKENS = ()
IOP_FRONT_MATTER_PUBLICATION_KEYWORDS = ("iopscience", "iop publishing")
IOP_SUPPLEMENTARY_TEXT_TOKENS = (
    "supplementary material",
    "supporting information",
    "supplementary data",
)
IOP_ACCESS_BLOCK_TEXT_TOKENS = (
    *COMMON_ACCESS_BLOCK_TOKENS,
    "radware bot manager",
    "perfdrive",
    "we apologize for the inconvenience",
    "confirm you are a human",
    "h-captcha",
)

IOP_TEXT_MARKER_SIGNAL_SET = TextMarkerSignalSet(
    blocking_rules=(
        TextMarkerRule("radware bot manager", "iop_radware_challenge"),
        TextMarkerRule("perfdrive", "iop_radware_challenge"),
        TextMarkerRule("confirm you are a human", "iop_captcha_challenge"),
        TextMarkerRule("h-captcha", "iop_captcha_challenge"),
    ),
    strong_rules=(
        TextMarkerRule("iopscience", "iopscience_page"),
        TextMarkerRule("articlebody", "iop_article_body_marker"),
    ),
    soft_rules=(
        TextMarkerRule("citation_pdf_url", "iop_pdf_meta"),
        TextMarkerRule("/article/10.1088/", "iop_article_url"),
    ),
)

IOP_HOSTS = {"iopscience.iop.org"}


def is_iop_url(value: str | None) -> bool:
    parsed = urlparse(normalize_text(value))
    host = normalize_text(parsed.hostname or "").lower()
    return host in IOP_HOSTS or any(host.endswith(f".{known}") for known in IOP_HOSTS)


def direct_article_url(doi: str) -> str:
    normalized_doi = normalize_doi(doi)
    return f"https://iopscience.iop.org/article/{quote(normalized_doi, safe='/')}"


def direct_pdf_url(doi: str) -> str:
    return f"{direct_article_url(doi)}/pdf"


def iop_pdf_url_from_article_url(url: str | None) -> str | None:
    value = normalize_text(url)
    if not is_iop_url(value):
        return None
    parsed = urlparse(value)
    path = normalize_text(parsed.path)
    if not path.startswith("/article/") or path.endswith("/pdf"):
        return None
    return f"{parsed.scheme or 'https'}://{parsed.netloc}{path.rstrip('/')}/pdf"


def _raw_meta_values(metadata: Mapping[str, Any], key: str) -> list[str]:
    raw_meta = metadata.get("raw_meta")
    if not isinstance(raw_meta, Mapping):
        return []
    values = raw_meta.get(key) or raw_meta.get(key.lower()) or []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    return [
        normalize_text(str(item or ""))
        for item in values
        if normalize_text(str(item or ""))
    ]


def _append_unique(values: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in values:
        values.append(normalized)


def extract_pdf_candidate_urls_from_html(
    html_text: str,
    source_url: str,
) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    return _extract_pdf_candidate_urls_from_soup(soup, source_url)


def _extract_pdf_candidate_urls_from_soup(
    soup: BeautifulSoup,
    source_url: str,
) -> list[str]:
    candidates: list[str] = []
    for selector, attribute in (
        ("meta[name='citation_pdf_url']", "content"),
        ("meta[property='citation_pdf_url']", "content"),
        ("a[href*='/pdf']", "href"),
        ("a[href*='download']", "href"),
    ):
        for node in soup.select(selector):
            attrs = getattr(node, "attrs", None) or {}
            value = normalize_text(str(attrs.get(attribute) or ""))
            if not value:
                continue
            if selector.startswith("a") and "pdf" not in value.lower():
                continue
            _append_unique(candidates, urljoin(source_url, value))
    return candidates


def pdf_candidate_urls(
    metadata: Mapping[str, Any],
    *,
    source_url: str | None = None,
    html_text: str | None = None,
    doi: str | None = None,
) -> list[str]:
    candidates: list[str] = []
    base_url = normalize_text(source_url) or normalize_text(
        str(metadata.get("landing_page_url") or "")
    )
    for value in _raw_meta_values(metadata, "citation_pdf_url"):
        _append_unique(
            candidates, urljoin(base_url or direct_article_url(doi or ""), value)
        )
    for item in metadata.get("fulltext_links") or ():
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        content_type = normalize_text(str(item.get("content_type") or "")).lower()
        if url and ("pdf" in content_type or url.rstrip("/").endswith("/pdf")):
            _append_unique(candidates, urljoin(base_url, url))
    _append_unique(candidates, normalize_text(str(metadata.get("pdf_url") or "")))
    _append_unique(candidates, iop_pdf_url_from_article_url(base_url))
    if html_text:
        for candidate in extract_pdf_candidate_urls_from_html(html_text, base_url):
            _append_unique(candidates, candidate)
    normalized_doi = normalize_doi(str(doi or metadata.get("doi") or ""))
    if normalized_doi:
        _append_unique(candidates, direct_pdf_url(normalized_doi))
    return candidates


def extract_authors(html_text: str) -> list[str]:
    return list(parse_html_metadata(html_text, "").get("authors") or [])


def extract_title(html_text: str, source_url: str | None = None) -> str | None:
    title = normalize_text(
        str(parse_html_metadata(html_text, source_url or "").get("title") or "")
    )
    return title or None


def extract_references(html_text: str) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html_text, choose_parser())
    references = _extract_references_from_soup(soup)
    if not references:
        references = _extract_references_from_metadata(
            parse_html_metadata(html_text, "")
        )
    if references:
        return references
    return _extract_references_from_metadata(parse_html_metadata(html_text, ""))


def _extract_references_from_soup(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    references = extract_numbered_references_from_soup(soup)
    if references:
        return references
    containers = [
        node
        for node in soup.select(
            "section[data-title*='Reference'], "
            "section[id*='reference'], "
            "div[id*='reference'], "
            ".references, "
            ".article-references"
        )
        if isinstance(node, Tag)
    ]
    parsed: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for container in containers:
        nodes = [
            node
            for node in container.select("ol > li, ul > li, .reference, .ref")
            if isinstance(node, Tag)
        ]
        for index, node in enumerate(nodes, start=1):
            raw = normalize_text(node.get_text(" ", strip=True))
            if not raw or raw in seen:
                continue
            seen.add(raw)
            parsed.append({"label": f"{index}.", "raw": raw, "doi": None, "year": None})
    if parsed:
        return parsed

    return []


def _extract_references_from_metadata(
    metadata: Mapping[str, Any],
) -> list[dict[str, str | None]]:
    parsed: list[dict[str, str | None]] = []
    seen: set[str] = set()
    raw_meta = metadata.get("raw_meta")
    values = []
    if isinstance(raw_meta, Mapping):
        raw_values = raw_meta.get("citation_reference") or []
        values = raw_values if isinstance(raw_values, list) else [raw_values]
    for value in values:
        reference = _parse_citation_reference_meta(value)
        raw = normalize_text(reference.get("raw"))
        if not raw or raw in seen:
            continue
        seen.add(raw)
        reference["label"] = f"{len(parsed) + 1}."
        parsed.append(reference)
    return parsed


def _parse_citation_reference_meta(value: Any) -> dict[str, str | None]:
    fields: dict[str, list[str]] = {}
    for chunk in str(value or "").split(";"):
        key, separator, raw_value = chunk.partition("=")
        if not separator:
            continue
        normalized_key = normalize_text(key).lower()
        normalized_value = normalize_text(raw_value)
        if normalized_key and normalized_value:
            fields.setdefault(normalized_key, []).append(normalized_value)

    authors = fields.get("citation_author") or []
    title = normalize_text((fields.get("citation_title") or [""])[0])
    journal = normalize_text((fields.get("citation_journal_title") or [""])[0])
    year = normalize_text((fields.get("citation_publication_date") or [""])[0])
    volume = normalize_text((fields.get("citation_volume") or [""])[0])
    first_page = normalize_text((fields.get("citation_firstpage") or [""])[0])
    last_page = normalize_text((fields.get("citation_lastpage") or [""])[0])
    doi = normalize_text((fields.get("citation_doi") or [""])[0]) or None
    pages = "-".join(part for part in (first_page, last_page) if part)
    parts = [
        ", ".join(authors),
        year,
        title,
        journal,
        volume,
        pages,
        f"doi:{doi}" if doi else "",
    ]
    return {
        "label": None,
        "raw": normalize_text(" ".join(part for part in parts if part)),
        "doi": doi,
        "year": year or None,
    }


def extract_figure_captions(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    return _extract_figure_captions_from_soup(soup)


def _extract_figure_captions_from_soup(soup: BeautifulSoup) -> list[str]:
    captions: list[str] = []
    for node in soup.select(
        "figure figcaption, .figure .caption, .article-figure .caption"
    ):
        if not isinstance(node, Tag):
            continue
        caption = _clean_iop_figure_caption_text(node.get_text(" ", strip=True))
        if caption and caption not in captions:
            captions.append(caption)
    return captions


def _plain_markdown_text(markdown_text: str) -> str:
    return normalize_text(
        re.sub(r"[*_`!\[\]()]|https?://\S+", " ", markdown_text)
    ).lower()


def _clean_iop_figure_caption_text(caption: Any) -> str:
    cleaned = IOP_FIGURE_DOWNLOAD_PATTERN.sub("", normalize_text(caption)).strip()
    cleaned = IOP_DUPLICATE_TEXT_FIGURE_LABEL_PATTERN.sub(r"\1 ", cleaned)
    return cleaned


def _clean_iop_markdown(markdown_text: str) -> str:
    cleaned = IOP_FIGURE_DOWNLOAD_PATTERN.sub("", markdown_text)
    cleaned = IOP_DUPLICATE_MARKDOWN_FIGURE_LABEL_PATTERN.sub(r"\1 ", cleaned)
    return cleaned


def _iop_caption_match_text(value: str | None) -> str:
    text = _plain_markdown_text(_clean_iop_figure_caption_text(value))
    text = re.sub(r"</?(?:sub|sup)>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdownload figure\b.*", " ", text, flags=re.IGNORECASE)
    return re.sub(r"[\W_]+", "", normalize_text(text), flags=re.UNICODE)


def _markdown_contains_caption(markdown_text: str, caption: str) -> bool:
    plain_markdown = _plain_markdown_text(markdown_text)
    normalized_caption = _plain_markdown_text(caption)
    if not normalized_caption:
        return True
    if normalized_caption in plain_markdown:
        return True
    markdown_match_text = _iop_caption_match_text(markdown_text)
    caption_match_text = _iop_caption_match_text(caption)
    if caption_match_text and caption_match_text in markdown_match_text:
        return True
    caption_body = re.sub(
        r"^figure\s+(?:[a-z]+\.?)?\d+[a-z]?\s+",
        "",
        normalized_caption,
    )
    return len(caption_body) >= 40 and caption_body in plain_markdown


def _markdown_contains_asset_image(
    markdown_text: str, asset: Mapping[str, Any]
) -> bool:
    inline_candidates = [
        image_reference_candidates(image.url)
        for image in iter_markdown_images(markdown_text or "")
    ]
    if not inline_candidates:
        return False
    asset_candidates: set[str] = set()
    for field in (
        "path",
        "url",
        "original_url",
        "download_url",
        "source_url",
        "source_path",
        "source_href",
        "preview_url",
        "full_size_url",
        "link",
    ):
        asset_candidates |= image_reference_candidates(str(asset.get(field) or ""))
    return bool(
        asset_candidates
        and any(
            image_references_match(asset_candidates, inline_candidate)
            for inline_candidate in inline_candidates
            if inline_candidate
        )
    )


def _append_missing_figure_captions(
    markdown_text: str,
    captions: list[str],
) -> str:
    missing = [
        caption
        for caption in captions
        if caption and not _markdown_contains_caption(markdown_text, caption)
    ]
    if not missing:
        return markdown_text
    addition = "\n\n".join(f"**{caption}**" for caption in missing)
    marker = "\n## References"
    if marker in markdown_text:
        head, tail = markdown_text.split(marker, 1)
        return f"{head.rstrip()}\n\n{addition}{marker}{tail}"
    return f"{markdown_text.rstrip()}\n\n{addition}\n"


def suppress_iop_asset_captions_already_in_markdown(
    assets: list[dict[str, Any]],
    markdown_text: str | None,
) -> list[dict[str, Any]]:
    """Drop appended figure captions that are already visible in IOP markdown."""
    if not assets or not normalize_text(markdown_text):
        return [dict(asset) for asset in assets]
    suppressed: list[dict[str, Any]] = []
    for asset in assets:
        item = dict(asset)
        caption = normalize_text(str(item.get("caption") or ""))
        if (
            normalize_text(str(item.get("kind") or "")).lower() == "figure"
            and caption
            and _markdown_contains_caption(markdown_text or "", caption)
            and not _markdown_contains_asset_image(markdown_text or "", item)
        ):
            item["caption"] = ""
        suppressed.append(item)
    return suppressed


def _append_references_markdown(
    markdown_text: str,
    references: list[dict[str, str | None]],
) -> str:
    if not references or "## References" in markdown_text:
        return markdown_text
    lines = ["## References"]
    for index, reference in enumerate(references, start=1):
        raw = normalize_text(reference.get("raw"))
        if not raw:
            continue
        label = normalize_text(reference.get("label")) or f"{index}."
        lines.append(f"{label} {raw}")
    if len(lines) == 1:
        return markdown_text
    return f"{markdown_text.rstrip()}\n\n" + "\n\n".join(lines) + "\n"


def _clean_iop_abstract_text(text: Any) -> str:
    cleaned = normalize_text(text)
    for token in IOP_ABSTRACT_TRAILING_CHROME_TOKENS:
        if token in cleaned:
            cleaned = cleaned.split(token, 1)[0].rstrip()
    return cleaned


def _clean_iop_abstract_payloads(extraction: dict[str, Any]) -> None:
    abstract_text = _clean_iop_abstract_text(extraction.get("abstract_text"))
    if abstract_text:
        extraction["abstract_text"] = abstract_text
    sections = extraction.get("abstract_sections")
    if not isinstance(sections, list):
        return
    cleaned_sections: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        cleaned = dict(section)
        cleaned["text"] = _clean_iop_abstract_text(cleaned.get("text"))
        cleaned_sections.append(cleaned)
    extraction["abstract_sections"] = cleaned_sections


def extract_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    soup = BeautifulSoup(html_text, choose_parser())
    html_title = extract_title(html_text, source_url)
    metadata_for_extraction = dict(metadata or {})
    if html_title and _metadata_title_allows_html_title(
        metadata_for_extraction,
        html_title,
    ):
        metadata_for_extraction["title"] = html_title
    markdown_text, extraction = (
        browser_workflow.extract_atypon_browser_workflow_markdown(
            html_text,
            source_url,
            "iop",
            metadata=metadata_for_extraction,
        )
    )
    finalized = dict(extraction)
    if html_title:
        finalized["title"] = html_title
    _clean_iop_abstract_payloads(finalized)
    markdown_text = _clean_iop_markdown(markdown_text)
    authors = extract_authors(html_text)
    if authors:
        finalized["extracted_authors"] = authors
    figure_captions = _extract_figure_captions_from_soup(soup)
    if figure_captions:
        finalized["figure_captions"] = figure_captions
        markdown_text = _append_missing_figure_captions(markdown_text, figure_captions)
    references = _extract_references_from_soup(soup)
    if not references:
        references = _extract_references_from_metadata(
            parse_html_metadata(html_text, "")
        )
    if references:
        finalized["references"] = references
        markdown_text = _append_references_markdown(markdown_text, references)
    pdf_candidates = pdf_candidate_urls(metadata or {}, source_url=source_url)
    for candidate in _extract_pdf_candidate_urls_from_soup(soup, source_url):
        _append_unique(pdf_candidates, candidate)
    if pdf_candidates:
        finalized["pdf_candidates"] = pdf_candidates
    return markdown_text, finalized


def _metadata_title_allows_html_title(
    metadata: Mapping[str, Any],
    html_title: str | None,
) -> bool:
    normalized_html_title = normalize_text(html_title)
    if not normalized_html_title:
        return False
    metadata_title = normalize_text(str(metadata.get("title") or ""))
    if not metadata_title:
        return True
    doi = normalize_doi(str(metadata.get("doi") or ""))
    return bool(doi and normalize_doi(metadata_title) == doi)


def _node_class_tokens(node: Any) -> set[str]:
    if not isinstance(node, Tag):
        return set()
    raw_classes = (getattr(node, "attrs", None) or {}).get("class") or []
    if isinstance(raw_classes, str):
        raw_classes = raw_classes.split()
    return {
        normalize_text(str(value or "")).lower()
        for value in raw_classes
        if normalize_text(str(value or ""))
    }


def _is_iop_latex_formula_container(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    if not (_node_class_tokens(node) & set(IOP_FORMULA_CONTAINER_TOKENS)):
        return False
    return node.find(_is_iop_formula_script) is not None


def _nearest_iop_formula_container_has_tex_script(node: Any) -> bool:
    current = node if isinstance(node, Tag) else None
    depth = 0
    while isinstance(current, Tag) and depth < 8:
        if _is_iop_latex_formula_container(current):
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return False


def _remove_iop_formula_fallback_asset_nodes(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    for node in list(container.select(".inline-eqn, .display-eqn")):
        if (
            isinstance(node, Tag)
            and node.parent is not None
            and _is_iop_latex_formula_container(node)
        ):
            node.decompose()
    for node in list(container.select(".texImage")):
        if (
            isinstance(node, Tag)
            and node.parent is not None
            and _nearest_iop_formula_container_has_tex_script(node)
        ):
            node.decompose()
    for image in list(container.find_all("img")):
        if (
            isinstance(image, Tag)
            and image.parent is not None
            and _nearest_iop_formula_container_has_tex_script(image)
        ):
            image.decompose()


def _iop_asset_extraction_html(html_text: str) -> str:
    soup = BeautifulSoup(html_text, choose_parser())
    _remove_iop_article_chrome(soup)
    _remove_iop_formula_fallback_asset_nodes(soup)
    return str(soup)


def _iop_figure_preview_is_accepted(asset: Mapping[str, Any]) -> bool:
    if normalize_text(str(asset.get("kind") or "")).lower() != "figure":
        return False
    urls = [
        normalize_text(str(asset.get(field) or "")).lower()
        for field in ("url", "preview_url", "full_size_url", "original_url")
    ]
    return any(
        token in url for url in urls for token in IOP_ACCEPTED_FIGURE_PREVIEW_URL_TOKENS
    )


def _iop_high_resolution_figure_url(value: str | None) -> str:
    url = normalize_text(value)
    if not url:
        return ""
    parsed = urlparse(url)
    host = normalize_text(parsed.hostname or "").lower()
    if not (host == "content.cld.iop.org" or host.endswith(".content.cld.iop.org")):
        return ""
    match = IOP_HIGH_RESOLUTION_FIGURE_URL_PATTERN.match(url)
    if match is None:
        return ""
    return f"{match.group('stem')}_hr{match.group('suffix')}"


def _augment_iop_figure_resolution_candidates(
    asset: Mapping[str, Any],
) -> dict[str, Any]:
    item = dict(asset)
    if normalize_text(str(item.get("kind") or "")).lower() != "figure":
        return item
    if normalize_text(str(item.get("full_size_url") or "")):
        return item

    for field in ("preview_url", "url", "original_url", "source_url"):
        high_resolution_url = _iop_high_resolution_figure_url(
            str(item.get(field) or "")
        )
        if high_resolution_url:
            item["full_size_url"] = high_resolution_url
            break
    return item


def _mark_iop_accepted_figure_previews(
    assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    marked: list[dict[str, Any]] = []
    for asset in assets:
        item = _augment_iop_figure_resolution_candidates(asset)
        if _iop_figure_preview_is_accepted(item):
            item["preview_accepted"] = True
        marked.append(item)
    return marked


def extract_scoped_html_assets(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile: str,
    supplementary_html_text: str | None = None,
    noise_profile: str | None = None,
) -> list[dict[str, Any]]:
    del noise_profile
    body_html = _iop_asset_extraction_html(body_html_text)
    assets: list[dict[str, Any]] = [
        dict(asset) for asset in extract_figure_assets(body_html, source_url)
    ]
    if asset_profile == "all":
        supplementary_scope = (
            _iop_asset_extraction_html(supplementary_html_text)
            if supplementary_html_text is not None
            else body_html
        )
        assets.extend(
            dict(asset)
            for asset in extract_supplementary_assets(
                supplementary_scope,
                source_url,
                noise_profile=IOP_NOISE_PROFILE,
            )
        )
    return _mark_iop_accepted_figure_previews(assets)


scoped_asset_extractor = extract_scoped_html_assets


def _is_iop_article_body_node(node: Tag) -> bool:
    attrs = getattr(node, "attrs", None) or {}
    return (
        normalize_text(
            str(attrs.get("property") or attrs.get("itemprop") or "")
        ).lower()
        == "articlebody"
    )


def _contains_iop_abstract(node: Tag) -> bool:
    return (
        node.select_one(
            ".article-abstract, [itemprop='description'], #artAbst, #abstracts, [role='doc-abstract']"
        )
        is not None
    )


def _complete_iop_article_container(body: Tag) -> Tag | None:
    current = body.parent if isinstance(body.parent, Tag) else None
    depth = 0
    while isinstance(current, Tag) and depth < 6:
        name = normalize_text(current.name or "").lower()
        if name in {"html", "body"}:
            break
        if _contains_iop_abstract(current):
            return current
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return None


def refine_selected_container(node: Tag, **_kwargs: Any) -> Tag:
    body = (
        node
        if _is_iop_article_body_node(node)
        else node.select_one("[property='articleBody'], [itemprop='articleBody']")
    )
    if not isinstance(body, Tag):
        return node
    return _complete_iop_article_container(body) or body


def _remove_iop_article_chrome(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    for selector in IOP_EXTRACTION_CLEANUP_SELECTORS:
        try:
            nodes = list(container.select(selector))
        except Exception:
            continue
        for node in nodes:
            if isinstance(node, Tag):
                if _is_iop_formula_script(node):
                    continue
                node.decompose()


def _is_iop_formula_script(node: Any) -> bool:
    return is_tex_formula_script_node(node)


def iop_body_container(container: Any) -> None:
    _remove_iop_article_chrome(container)


def iop_asset_body_container(container: Any) -> None:
    _remove_iop_article_chrome(container)
    _remove_iop_formula_fallback_asset_nodes(container)


def iop_asset_figure_extraction(container: Any) -> None:
    iop_asset_body_container(container)


__all__ = [
    "IOP_ACCESS_BLOCK_TEXT_TOKENS",
    "IOP_DISPLAY_FORMULA_SELECTORS",
    "IOP_EXTRACTION_CLEANUP_SELECTORS",
    "IOP_FORMULA_CONTAINER_TOKENS",
    "IOP_FRONT_MATTER_CONTAINS_TOKENS",
    "IOP_FRONT_MATTER_EXACT_TEXTS",
    "IOP_FRONT_MATTER_PUBLICATION_KEYWORDS",
    "IOP_MARKDOWN_PROMO_TOKENS",
    "IOP_NOISE_PROFILE",
    "IOP_POST_CONTENT_BREAK_TOKENS",
    "IOP_SITE_RULE_OVERRIDES",
    "IOP_SUPPLEMENTARY_TEXT_TOKENS",
    "IOP_TEXT_MARKER_SIGNAL_SET",
    "direct_article_url",
    "direct_pdf_url",
    "extract_authors",
    "extract_figure_captions",
    "extract_markdown",
    "extract_pdf_candidate_urls_from_html",
    "extract_references",
    "extract_scoped_html_assets",
    "extract_title",
    "iop_asset_body_container",
    "iop_asset_figure_extraction",
    "iop_body_container",
    "iop_pdf_url_from_article_url",
    "is_iop_url",
    "pdf_candidate_urls",
    "refine_selected_container",
    "scoped_asset_extractor",
    "suppress_iop_asset_captions_already_in_markdown",
]
