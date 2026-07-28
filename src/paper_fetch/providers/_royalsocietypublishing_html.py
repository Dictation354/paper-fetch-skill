"""Royal Society Publishing HTML extraction helpers."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from html import escape
import re
from typing import Any
from collections.abc import Mapping
from urllib.parse import quote, unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..extraction.html._metadata import merge_html_metadata, parse_html_metadata
from ..extraction.html.assets import extract_scoped_html_assets
from ..extraction.html.figure_links import inject_inline_figure_links
from ..extraction.html.parsing import choose_parser
from ..extraction.html.renderer import (
    render_html_markdown,
    render_provider_html_fragment,
)
from ..extraction.markdown_render.formulas import (
    normalize_tex_formula_text,
    render_html_mathml_node,
)
from ..models import AssetProfile
from ..publisher_identity import extract_doi, normalize_doi
from ..utils import normalize_text


ARTICLE_BODY_SELECTORS = (
    ".article-body",
    ".widget-ArticleFulltext .article-body",
    ".widget-ArticleFulltext",
)
ROYAL_SOCIETY_EXTRACTION_CLEANUP_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "button",
    "input",
    "select",
    "textarea",
    ".article-metadata-standalone-panel",
    ".article-tools",
    ".article-metrics",
    ".copyright",
    ".license",
    ".figureDownloadLinks",
    ".tableDownloadLinks",
    ".table-modal",
    ".core-widget-popup",
    ".toolbar",
    ".al-article-items",
    ".download-slide",
    ".figure-expand-popup",
    ".fig-view-orig",
    ".ref-list",
    ".js-splitview-ref-list",
    ".ref-links",
    ".cit-extra",
    "a.article-pdfLink",
)
# SITE_UI_COPY_REGRESSION_MARKER: Royal Society/Silverchair article chrome labels; keep tied to provider cleanup tests.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup policy removes these only from Royal Society article chrome.
ROYAL_SOCIETY_MARKDOWN_PROMO_TOKENS = (
    "Open figure viewer",
    "Open table viewer",
    "Download slide",
    "Download citation",
    "Google Scholar",
    "Search ADS",
)
ROYAL_SOCIETY_FRONT_MATTER_EXACT_TEXTS = (
    "Open figure viewer",
    "Open table viewer",
)
ROYAL_SOCIETY_SUPPLEMENTARY_TEXT_TOKENS = (
    "supplementary data",
    "supplementary material",
)
_NOISE_TEXTS = {
    "open figure viewer",
    "open table viewer",
    "download slide",
    "download citation",
}
_GENERIC_FIGURE_HEADINGS = {
    "",
    "figure",
    "supplementary material",
    "view large",
    "download slide",
}
_BACK_MATTER_BODY_HEADINGS = {
    "authors' contributions",
    "competing interests",
    "data accessibility",
    "disclaimer",
    "ethics",
    "funding",
    "acknowledgements",
}
_REFERENCE_FIELD_PATTERN = re.compile(r"\s*([^=;]+)\s*=\s*([^;]*)")
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(
    r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$"
)
_REFERENCE_TABLE_HEADER_RE = re.compile(
    r"^\|\s*reference\s*\|\s*number of patients\s*\|",
    flags=re.IGNORECASE,
)
_BROKEN_REFERENCE_TABLE_ROW_RE = re.compile(r"^\|\s*\[\s*\|")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_INLINE_MATH_SPAN_RE = re.compile(r"\$[^$\n]+\$")
_DISPLAY_EQUATION_RE = re.compile(r"(Equation(?:\s+\d+(?:\.\d+)*)?:\s+\$[^$\n]+\$)")
_ROYAL_FIGURE_BASENAME_RE = re.compile(
    r"^(?:m_)?([a-z0-9._-]+f\d+[a-z]?)(?:\.[a-z0-9]+)?$",
    flags=re.IGNORECASE,
)
_REFERENCE_LEADING_LABEL_RE = re.compile(
    r"^\s*(?:\[\d+[A-Za-z]?\]|\d+[A-Za-z]?[.)])\s+"
)


@dataclass(frozen=True)
class RoyalSocietyHtmlExtraction:
    html_text: str
    markdown_text: str
    metadata: dict[str, Any]
    abstract_sections: list[dict[str, Any]]
    section_hints: list[dict[str, Any]]
    extracted_assets: list[dict[str, Any]]


def direct_article_url(doi: str) -> str:
    normalized_doi = normalize_doi(doi)
    return f"https://royalsocietypublishing.org/doi/{quote(normalized_doi, safe='/')}"


def direct_pdf_url(doi: str) -> str:
    normalized_doi = normalize_doi(doi)
    return (
        f"https://royalsocietypublishing.org/doi/pdf/{quote(normalized_doi, safe='/')}"
    )


def _first_article_body(soup: BeautifulSoup) -> Tag | None:
    for selector in ARTICLE_BODY_SELECTORS:
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            return node
    return None


def _remove_noise_nodes(container: Tag) -> None:
    for selector in ROYAL_SOCIETY_EXTRACTION_CLEANUP_SELECTORS:
        for node in list(container.select(selector)):
            node.decompose()

    for heading in list(container.select(".backreferences-title")):
        heading.decompose()

    for anchor in list(container.find_all("a", href=True)):
        if not isinstance(anchor, Tag):
            continue
        href = normalize_text(str(anchor.get("href") or "")).lower()
        if href in {"javascript:", "javascript:;"}:
            text = normalize_text(anchor.get_text(" ", strip=True))
            if text:
                anchor.replace_with(text)
            else:
                anchor.decompose()

    for node in list(container.find_all(["a", "span", "button"])):
        if not isinstance(node, Tag):
            continue
        text = normalize_text(node.get_text(" ", strip=True)).lower()
        if text in _NOISE_TEXTS:
            node.decompose()


def _normalize_silverchair_dom(container: Tag) -> None:
    for paragraph in list(container.select("div.block-child-p")):
        if isinstance(paragraph, Tag):
            paragraph.name = "p"

    _normalize_table_captions(container)

    for formula_wrap in list(container.select(".formula-wrap")):
        if not isinstance(formula_wrap, Tag):
            continue
        if _replace_display_formula(formula_wrap, formula_wrap.select_one(".label")):
            continue

    for formula in list(container.select(".disp-formula")):
        if isinstance(formula, Tag):
            _replace_display_formula(formula, None)

    for formula in list(container.select(".inline-formula")):
        if not isinstance(formula, Tag):
            continue
        math_node = formula.find("math")
        rendered = (
            normalize_text(render_html_mathml_node(math_node))
            if isinstance(math_node, Tag)
            else ""
        )
        text = rendered or normalize_text(formula.get_text(" ", strip=True))
        if text:
            formula.replace_with(text)

    for inline in list(container.find_all(["em", "i", "strong", "b", "sup", "sub"])):
        if isinstance(inline, Tag):
            inline.replace_with(inline.get_text("", strip=False))

    for cell in list(container.select("table td, table th")):
        if not isinstance(cell, Tag):
            continue
        for inline in list(cell.find_all(["em", "i", "strong", "b", "sup", "sub"])):
            if isinstance(inline, Tag):
                inline.replace_with(inline.get_text(" ", strip=False))
        if not normalize_text(cell.get_text(" ", strip=True)):
            cell.clear()
            cell.append("not specified")

    for math_node in list(container.find_all("math")):
        if not isinstance(math_node, Tag):
            continue
        rendered = normalize_text(render_html_mathml_node(math_node))
        if rendered:
            math_node.replace_with(rendered)


def _normalize_table_captions(container: Tag) -> None:
    for table_wrap in list(container.select(".table-wrap")):
        if not isinstance(table_wrap, Tag):
            continue
        if table_wrap.select_one(".paper-fetch-table-title") is not None:
            continue
        title_node = table_wrap.select_one(".table-wrap-title")
        label = (
            _node_text(title_node.select_one(".label"))
            if isinstance(title_node, Tag)
            else ""
        )
        caption = (
            _node_text(title_node.select_one(".caption"))
            if isinstance(title_node, Tag)
            else ""
        )
        text = normalize_text(": ".join(item for item in (label, caption) if item))
        if not text:
            continue
        caption_soup = BeautifulSoup(
            f'<p class="paper-fetch-table-title">{escape(text)}</p>',
            choose_parser(),
        )
        caption_node = caption_soup.select_one(".paper-fetch-table-title")
        if not isinstance(caption_node, Tag):
            continue
        if isinstance(title_node, Tag):
            title_node.insert_after(caption_node)
        else:
            table_wrap.insert(0, caption_node)


def _replace_display_formula(node: Tag, label_node: Tag | None) -> bool:
    formula_node = node.select_one(".disp-formula")
    formula = formula_node if isinstance(formula_node, Tag) else node
    math_text = render_html_mathml_node(formula).strip()
    math_node = formula.select_one(".math")
    if not math_text and isinstance(math_node, Tag):
        math_text = normalize_tex_formula_text(math_node.get_text("", strip=False))
    if not math_text:
        return False
    label = _node_text(label_node)
    prefix = f"Equation {label}: " if label else "Equation: "
    node.replace_with(f" {prefix}{_inline_formula_markdown(math_text)} ")
    return True


def _inline_formula_markdown(markdown_text: str) -> str:
    lines = [
        line.strip() for line in str(markdown_text or "").splitlines() if line.strip()
    ]
    if len(lines) >= 3 and lines[0] == "$$" and lines[-1] == "$$":
        lines = lines[1:-1]
    text = normalize_text(" ".join(lines))
    text = text.replace(
        r"{\overset{\sim}{X}}_{t - 1}e_{t}",
        r"{\overset{\sim}{X}}_{t - 1}; e_{t}",
    )
    text = text.replace(r"\text{and\textbackslash~}", r"\text{and }")
    if text.startswith("$") and text.endswith("$"):
        return text
    return f"${text}$" if text else ""


def _space_inline_math_spans(line: str) -> str:
    def replace(match: re.Match[str]) -> str:
        start, end = match.span()
        prefix = ""
        suffix = ""
        if (
            start > 0
            and not line[start - 1].isspace()
            and line[start - 1] not in "([{/"
        ):
            prefix = " "
        if end < len(line) and not line[end].isspace() and line[end] not in ".,;:)]}/":
            suffix = " "
        return f"{prefix}{match.group(0)}{suffix}"

    return _INLINE_MATH_SPAN_RE.sub(replace, line)


def _split_display_equation_runs(line: str) -> list[str]:
    matches = list(_DISPLAY_EQUATION_RE.finditer(line))
    if not matches:
        return [line]

    split_lines: list[str] = []
    cursor = 0
    for match in matches:
        prefix = line[cursor : match.start()].strip()
        if prefix:
            split_lines.append(prefix)
        split_lines.append(match.group(1).strip())
        cursor = match.end()
    suffix = line[cursor:].strip()
    if suffix:
        split_lines.append(suffix)
    return split_lines


def _repair_royal_math_text(line: str) -> str:
    line = line.replace(
        r"where Atand $\mathcal{E}_{t}$",
        r"where $A_t$ and $\mathcal{E}_{t}$",
    )
    line = re.sub(
        r"where Atand (\$[^$\n]+\$)",
        r"where $A_t$ and \1",
        line,
    )
    return line.replace("εinot", "εi not")


def _clean_article_body(html_text: str) -> tuple[str, int]:
    soup = BeautifulSoup(html_text, choose_parser())
    return _clean_article_body_from_soup(soup)


def _clean_article_body_from_soup(soup: BeautifulSoup) -> tuple[str, int]:
    body = _first_article_body(soup)
    if body is None:
        return "", 0
    _remove_noise_nodes(body)
    _normalize_silverchair_dom(body)
    body_text_length = len(normalize_text(body.get_text(" ", strip=True)))
    return str(body), body_text_length


def _markdown_render_html(cleaned_html: str) -> str:
    soup = BeautifulSoup(cleaned_html, choose_parser())
    for selector in (".fig-section", ".fig-modal", ".close-reveal-modal"):
        for node in list(soup.select(selector)):
            node.decompose()
    return str(soup)


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


def _parse_citation_reference(value: str) -> dict[str, Any] | None:
    fields: dict[str, list[str]] = {}
    for match in _REFERENCE_FIELD_PATTERN.finditer(value):
        key = normalize_text(match.group(1)).lower()
        field_value = normalize_text(match.group(2))
        if key and field_value:
            fields.setdefault(key, []).append(field_value)
    if not fields:
        raw = normalize_text(value)
        return {"raw": raw} if raw else None

    title = (fields.get("citation_title") or fields.get("title") or [""])[0]
    journal = (fields.get("citation_journal_title") or fields.get("journal") or [""])[0]
    year = (fields.get("citation_year") or fields.get("year") or [""])[0]
    doi = normalize_doi(
        (fields.get("citation_doi") or fields.get("doi") or [""])[0]
    ) or extract_doi(value)
    authors = fields.get("citation_author") or fields.get("author") or []
    parts: list[str] = []
    if authors:
        parts.append(", ".join(authors[:6]))
    if title:
        parts.append(title)
    if journal:
        parts.append(journal)
    if year:
        parts.append(year)
    if doi:
        parts.append(f"doi:{doi}")
    raw = ". ".join(part for part in parts if part)
    if not raw:
        raw = normalize_text(value)
    if not raw:
        return None
    return {
        "raw": raw,
        "title": title or None,
        "year": year or None,
        "doi": doi or None,
    }


def _number_reference(reference: Mapping[str, Any], index: int) -> dict[str, Any]:
    numbered = dict(reference)
    raw = normalize_text(str(numbered.get("raw") or ""))
    raw = _REFERENCE_LEADING_LABEL_RE.sub("", raw).strip()
    numbered["raw"] = f"{index}. {raw}" if raw else ""
    return numbered


def citation_references_from_metadata(
    metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in _raw_meta_values(metadata, "citation_reference"):
        reference = _parse_citation_reference(value)
        if reference is None:
            continue
        key = normalize_text(str(reference.get("raw") or "")).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        references.append(_number_reference(reference, len(references) + 1))
    return references


def _parse_html_reference_node(node: Tag) -> dict[str, Any] | None:
    cloned = copy.deepcopy(node)
    ref = cloned.select_one(".ref") or cloned
    for selector in (".label", ".citation-links", ".ref-links", ".cit-extra"):
        for item in list(ref.select(selector)):
            item.decompose()
    raw = normalize_text(ref.get_text(" ", strip=True))
    raw = re.sub(r"^\d+\s+", "", raw).strip()
    if not raw:
        return None
    title_node = ref.select_one(".article-title, .source")
    year_node = ref.select_one(".year")
    doi = extract_doi(raw)
    return {
        "raw": raw,
        "title": _node_text(title_node) or None,
        "year": _node_text(year_node) or None,
        "doi": doi or None,
    }


def html_references_from_ref_list(html_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, choose_parser())
    return html_references_from_ref_list_soup(soup)


def html_references_from_ref_list_soup(soup: BeautifulSoup) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in soup.select(".ref-list .ref"):
        if not isinstance(node, Tag):
            continue
        reference = _parse_html_reference_node(node)
        if reference is None:
            continue
        key = normalize_text(str(reference.get("raw") or "")).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        references.append(_number_reference(reference, len(references) + 1))
    return references


def merge_metadata_with_html(
    base_metadata: Mapping[str, Any] | None,
    html_text: str,
    source_url: str,
    *,
    doi: str | None = None,
) -> dict[str, Any]:
    html_metadata = parse_html_metadata(html_text, source_url)
    references = html_references_from_ref_list(html_text)
    return _merge_metadata_with_parsed_html(
        base_metadata,
        html_metadata,
        doi=doi,
        references=references,
    )


def _merge_metadata_with_parsed_html(
    base_metadata: Mapping[str, Any] | None,
    html_metadata: Mapping[str, Any],
    *,
    doi: str | None = None,
    references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    merged = merge_html_metadata(base_metadata, html_metadata)
    if doi and not merged.get("doi"):
        merged["doi"] = normalize_doi(doi)
    html_title = normalize_text(str(html_metadata.get("title") or ""))
    current_title = normalize_text(str(merged.get("title") or ""))
    doi_value = normalize_doi(
        str(doi or merged.get("doi") or html_metadata.get("doi") or "")
    )
    if html_title and doi_value and normalize_doi(current_title) == doi_value:
        merged["title"] = html_title
    references = references or citation_references_from_metadata(merged)
    if references and not merged.get("references"):
        merged_payload: dict[str, Any] = dict(merged)
        merged_payload["references"] = references
        return merged_payload
    return dict(merged)


def pdf_candidate_urls(
    metadata: Mapping[str, Any],
    *,
    source_url: str,
    doi: str,
) -> list[str]:
    candidates: list[str] = []
    for value in _raw_meta_values(metadata, "citation_pdf_url"):
        candidates.append(urljoin(source_url, value))
    for item in metadata.get("fulltext_links") or ():
        if not isinstance(item, Mapping):
            continue
        url = normalize_text(str(item.get("url") or ""))
        content_type = normalize_text(str(item.get("content_type") or "")).lower()
        if url and ("pdf" in content_type or "pdf" in url.lower()):
            candidates.append(urljoin(source_url, url))
    candidates.append(direct_pdf_url(doi))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def extract_authors(html_text: str) -> list[str]:
    metadata = parse_html_metadata(html_text, "")
    return list(metadata.get("authors") or [])


def _classes(node: Tag) -> set[str]:
    raw_classes = node.get("class") or []
    return {str(item) for item in raw_classes}


def _node_text(node: Tag | None) -> str:
    if not isinstance(node, Tag):
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def _figure_page_url(node: Tag, source_url: str) -> str:
    for anchor in node.find_all("a", href=True):
        href = normalize_text(str(anchor.get("href") or ""))
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(source_url, href)
        if "/view-large/figure/" in absolute.lower():
            return absolute
    return ""


def _figure_preview_url(node: Tag, source_url: str) -> str:
    image = node.find("img")
    if isinstance(image, Tag):
        for attr in ("data-src", "src", "data-original", "data-lazy-src"):
            candidate = normalize_text(str(image.get(attr) or ""))
            if candidate:
                return urljoin(source_url, candidate)
    return ""


def _royal_figure_basename(value: str) -> str:
    basename = urlparse(value).path.rsplit("/", 1)[-1]
    match = _ROYAL_FIGURE_BASENAME_RE.match(basename)
    return match.group(1).lower() if match is not None else ""


def _silverchair_download_image_url(
    node: Tag,
    source_url: str,
    *,
    expected_figure_basename: str,
) -> str:
    for anchor in node.find_all("a", href=True):
        href = normalize_text(str(anchor.get("href") or ""))
        if not href:
            continue
        wrapper_url = urljoin(source_url, href)
        parsed_wrapper = urlparse(wrapper_url)
        if not parsed_wrapper.path.lower().endswith("/downloadfile/downloadimage.aspx"):
            continue

        query_segments = parsed_wrapper.query.split("&")
        image_value = ""
        outer_signature_segments: dict[str, str] = {}
        for segment in query_segments:
            key, separator, value = segment.partition("=")
            if not separator:
                continue
            normalized_key = unquote(key).strip().lower()
            if normalized_key == "image" and not image_value:
                image_value = value
            elif normalized_key in {"expires", "signature", "key-pair-id"}:
                outer_signature_segments.setdefault(normalized_key, segment)
        if not image_value:
            continue

        image_url = urljoin(source_url, unquote(image_value))
        parsed_image = urlparse(image_url)
        image_host = normalize_text(parsed_image.hostname or "").lower()
        if (
            parsed_image.scheme not in {"http", "https"}
            or not image_host
            or (
                image_host != "silverchair-cdn.com"
                and not image_host.endswith(".silverchair-cdn.com")
            )
        ):
            continue
        image_basename = _royal_figure_basename(image_url)
        if expected_figure_basename and image_basename != expected_figure_basename:
            continue

        nested_keys = {
            unquote(segment.partition("=")[0]).strip().lower()
            for segment in parsed_image.query.split("&")
            if segment
        }
        missing_signature_segments = [
            segment
            for key, segment in outer_signature_segments.items()
            if key not in nested_keys
        ]
        if missing_signature_segments:
            separator = "&" if parsed_image.query else "?"
            image_url = f"{image_url}{separator}{'&'.join(missing_signature_segments)}"
        return image_url
    return ""


def _royal_society_figure_assets(
    html_text: str,
    source_url: str,
    *,
    include_caption: bool = True,
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html_text, choose_parser())
    assets: list[dict[str, str]] = []
    for node in soup.find_all("div"):
        if not isinstance(node, Tag):
            continue
        classes = _classes(node)
        if "fig-section" not in classes or "fig-modal" in classes:
            continue
        label = _node_text(node.select_one(".fig-label")) or "Figure"
        label = label.rstrip(".")
        caption = _node_text(node.select_one(".fig-caption")) if include_caption else ""
        if caption.lower() == label.lower():
            caption = ""
        if include_caption and not caption:
            image = node.find("img")
            if isinstance(image, Tag):
                caption = normalize_text(str(image.get("alt") or ""))
                caption = re.sub(
                    r"\s*Refer to the image caption for details\.?\s*$",
                    "",
                    caption,
                )
        figure_page_url = _figure_page_url(node, source_url)
        preview_url = _figure_preview_url(node, source_url)
        expected_figure_basename = _royal_figure_basename(
            figure_page_url or preview_url
        )
        full_size_url = _silverchair_download_image_url(
            node,
            source_url,
            expected_figure_basename=expected_figure_basename,
        )
        primary_url = full_size_url or preview_url
        if not caption and not (primary_url or figure_page_url):
            continue
        asset: dict[str, str] = {
            "kind": "figure",
            "heading": label or "Figure",
            "caption": caption,
            "section": "body",
            "render_state": "inline",
        }
        if primary_url:
            asset["url"] = primary_url
        if full_size_url:
            asset["full_size_url"] = full_size_url
        if figure_page_url:
            asset["figure_page_url"] = figure_page_url
        if preview_url:
            asset["preview_url"] = preview_url
        dom_id = normalize_text(str(node.get("data-id") or node.get("id") or ""))
        if dom_id:
            asset["dom_id"] = dom_id
        assets.append(asset)
    return assets


def _asset_external_keys(asset: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    dom_id = normalize_text(str(asset.get("dom_id") or "")).lower()
    if dom_id:
        keys.append(f"dom:{dom_id}")
    for field in (
        "url",
        "full_size_url",
        "original_url",
        "preview_url",
        "download_url",
        "figure_page_url",
    ):
        value = normalize_text(str(asset.get(field) or ""))
        if not value:
            continue
        basename = urlparse(value).path.rsplit("/", 1)[-1]
        figure_match = _ROYAL_FIGURE_BASENAME_RE.match(basename)
        if figure_match is not None:
            key = f"figure:{figure_match.group(1).lower()}"
            if key not in keys:
                keys.append(key)
    for field in (
        "url",
        "full_size_url",
        "original_url",
        "preview_url",
        "download_url",
        "figure_page_url",
    ):
        value = normalize_text(str(asset.get(field) or ""))
        if value:
            key = f"url:{value.lower()}"
            if key not in keys:
                keys.append(key)
    return keys


def _merge_asset(existing: dict[str, Any], incoming: Mapping[str, Any]) -> None:
    current_heading = normalize_text(str(existing.get("heading") or ""))
    candidate_heading = normalize_text(str(incoming.get("heading") or ""))
    if candidate_heading and (
        not current_heading or current_heading.lower() in _GENERIC_FIGURE_HEADINGS
    ):
        existing["heading"] = candidate_heading
    current_caption = normalize_text(str(existing.get("caption") or ""))
    candidate_caption = normalize_text(str(incoming.get("caption") or ""))
    if candidate_caption and (
        not current_caption or len(candidate_caption) > len(current_caption)
    ):
        existing["caption"] = candidate_caption
    for field in (
        "url",
        "full_size_url",
        "preview_url",
        "original_url",
        "figure_page_url",
        "dom_id",
        "image_id",
        "asset_order",
        "section",
        "render_state",
    ):
        if incoming.get(field) and not existing.get(field):
            existing[field] = incoming[field]


def _normalize_extracted_assets(assets: list[dict[str, str]]) -> list[dict[str, Any]]:
    normalized_assets: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in assets:
        asset: dict[str, Any] = dict(item)
        for text_field in ("caption", "heading"):
            if asset.get(text_field):
                asset[text_field] = re.sub(
                    r"\s*Refer to the image caption for details\.?\s*$",
                    "",
                    _repair_royal_math_text(
                        normalize_text(str(asset.get(text_field) or ""))
                    ),
                    flags=re.IGNORECASE,
                )
        url = normalize_text(
            str(
                asset.get("url")
                or asset.get("source_url")
                or asset.get("original_url")
                or asset.get("download_url")
                or asset.get("figure_page_url")
                or ""
            )
        ).lower()
        if "/view-large/figure/" in url:
            asset["kind"] = "figure"
            asset["section"] = "body"
            if (
                normalize_text(str(asset.get("heading") or "")).lower()
                in _GENERIC_FIGURE_HEADINGS
            ):
                asset["heading"] = "Figure"
        kind = normalize_text(str(asset.get("kind") or "")).lower()
        keys = [(kind, key) for key in _asset_external_keys(asset)]
        existing = next(
            (by_key[key] for key in keys if key in by_key),
            None,
        )
        if existing is not None:
            _merge_asset(existing, asset)
            for key in keys:
                by_key[key] = existing
            continue
        for key in keys:
            by_key[key] = asset
        normalized_assets.append(asset)
    return normalized_assets


def extract_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any] | None = None,
    asset_profile: AssetProfile = "body",
) -> RoyalSocietyHtmlExtraction:
    soup = BeautifulSoup(html_text, choose_parser())
    raw_article_body = _first_article_body(soup)
    raw_article_body_html = (
        str(raw_article_body) if isinstance(raw_article_body, Tag) else ""
    )
    html_metadata = parse_html_metadata(html_text, source_url)
    html_references = html_references_from_ref_list_soup(soup)
    merged_metadata = _merge_metadata_with_parsed_html(
        metadata,
        html_metadata,
        references=html_references,
    )
    cleaned_html, body_text_length = _clean_article_body_from_soup(soup)
    if not cleaned_html:
        return RoyalSocietyHtmlExtraction(
            html_text="",
            markdown_text="",
            metadata=merged_metadata,
            abstract_sections=[],
            section_hints=[],
            extracted_assets=[],
        )

    render_html = _markdown_render_html(cleaned_html)
    rendered = render_provider_html_fragment(
        render_html,
        source_url,
        title=str(merged_metadata.get("title") or ""),
        postprocessors=(royalsocietypublishing_normalize_markdown,),
    )
    markdown_text = _restore_empty_back_matter_sections(
        rendered.markdown_text,
        _back_matter_section_markdown(render_html, source_url),
    )
    extracted_assets = _normalize_extracted_assets(
        [
            *_royal_society_figure_assets(
                raw_article_body_html,
                source_url,
                include_caption=False,
            ),
            *_royal_society_figure_assets(cleaned_html, source_url),
            *extract_scoped_html_assets(
                cleaned_html,
                source_url,
                asset_profile=asset_profile,
                supplementary_html_text=cleaned_html,
                noise_profile="royalsocietypublishing",
            ),
        ]
    )
    markdown_text = inject_inline_figure_links(
        markdown_text,
        figure_assets=extracted_assets,
        clean_markdown_fn=royalsocietypublishing_normalize_markdown,
    )
    section_hints = _normalize_section_hints(
        [dict(item) for item in rendered.section_hints],
        markdown_text,
    )
    if body_text_length and section_hints:
        section_hints[0].setdefault("container_text_length", body_text_length)
    abstract_sections = [
        dict(item)
        for item in rendered.abstract_sections
        if normalize_text(str(item.get("text") or "")).lower()
        != normalize_text(str(item.get("heading") or "")).lower()
    ]
    return RoyalSocietyHtmlExtraction(
        html_text=cleaned_html,
        markdown_text=markdown_text,
        metadata=merged_metadata,
        abstract_sections=abstract_sections,
        section_hints=section_hints,
        extracted_assets=[dict(item) for item in extracted_assets],
    )


def _normalize_section_hints(
    section_hints: list[dict[str, Any]],
    markdown_text: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    has_authors = False
    for hint in section_hints:
        item = dict(hint)
        heading_key = normalize_text(str(item.get("heading") or "")).lower()
        if heading_key == "authors' contributions":
            has_authors = True
        if heading_key in _BACK_MATTER_BODY_HEADINGS:
            item["kind"] = "body"
        normalized.append(item)

    if has_authors or "## Authors' contributions" not in markdown_text:
        return normalized

    authors_hint = {
        "heading": "Authors' contributions",
        "level": 2,
        "kind": "body",
        "order": 0,
        "language": None,
        "source_selector": "div.widget-items",
    }
    for index, hint in enumerate(normalized):
        heading_key = normalize_text(str(hint.get("heading") or "")).lower()
        if heading_key in {"competing interests", "funding"}:
            authors_hint["order"] = int(hint.get("order") or index)
            return [*normalized[:index], authors_hint, *normalized[index:]]
    authors_hint["order"] = len(normalized)
    return [*normalized, authors_hint]


def _back_matter_section_markdown(cleaned_html: str, source_url: str) -> dict[str, str]:
    soup = BeautifulSoup(cleaned_html, choose_parser())
    sections: dict[str, str] = {}
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if not isinstance(heading, Tag):
            continue
        heading_text = _node_text(heading)
        heading_key = normalize_text(heading_text).lower()
        if heading_key not in _BACK_MATTER_BODY_HEADINGS:
            continue
        fragments: list[str] = []
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in {"h1", "h2", "h3", "h4"}:
                break
            if isinstance(sibling, Tag):
                fragments.append(str(sibling))
        if not fragments:
            continue
        markdown = render_html_markdown(
            "\n".join(fragments),
            source_url,
            cleaned_html=True,
            postprocessors=(royalsocietypublishing_normalize_markdown,),
        )
        markdown = markdown.strip()
        if markdown:
            sections[heading_key] = markdown
    return sections


def _restore_empty_back_matter_sections(
    markdown_text: str,
    back_matter_sections: Mapping[str, str],
) -> str:
    if not back_matter_sections:
        return markdown_text

    lines = str(markdown_text or "").splitlines()
    restored: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        restored.append(line)
        match = _MARKDOWN_HEADING_RE.match(line.strip())
        if match is None:
            index += 1
            continue
        heading_key = normalize_text(match.group(2)).lower()
        replacement = back_matter_sections.get(heading_key)
        if not replacement:
            index += 1
            continue

        next_index = index + 1
        while (
            next_index < len(lines)
            and _MARKDOWN_HEADING_RE.match(lines[next_index].strip()) is None
        ):
            next_index += 1
        existing_body = "\n".join(lines[index + 1 : next_index])
        if normalize_text(existing_body):
            index += 1
            continue

        restored.append("")
        restored.extend(replacement.splitlines())
        if next_index < len(lines):
            restored.append("")
        index = next_index
    return "\n".join(restored).strip()


def royalsocietypublishing_normalize_markdown(text: str) -> str:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        raw_line = re.sub(
            r"\[([^\]]+)\]\(\s*javascript:\s*;?\s*\)",
            r"\1",
            raw_line,
            flags=re.IGNORECASE,
        )
        raw_line = _space_inline_math_spans(raw_line)
        raw_line = _repair_royal_math_text(raw_line)
        for line in _split_display_equation_runs(raw_line):
            normalized = normalize_text(line).lower()
            if normalized in _NOISE_TEXTS:
                continue
            if normalized in {"google scholar", "crossref", "pubmed", "search ads"}:
                continue
            stripped = line.strip()
            if stripped in {"- —", "- –", "- -"}:
                continue
            line = re.sub(r"^(\s*-\s+)[—–-](?=\S)", r"\1", line)
            stripped = line.strip()
            previous = next(
                (item.strip() for item in reversed(lines) if item.strip()), ""
            )
            if (
                previous
                and _MARKDOWN_TABLE_SEPARATOR_RE.fullmatch(previous)
                and not stripped.startswith("|")
                and stripped.count("]") >= 3
            ):
                continue
            if "]|" in stripped and re.search(r"\]\|\s*[A-Za-z][^|]+\|[^|]+", stripped):
                continue
            if stripped.startswith("|") and not stripped.endswith("|"):
                continue
            if _MARKDOWN_TABLE_SEPARATOR_RE.fullmatch(stripped):
                if not (
                    previous.startswith("|")
                    and previous.endswith("|")
                    and not _MARKDOWN_TABLE_SEPARATOR_RE.fullmatch(previous)
                ):
                    continue
            if (
                stripped.startswith("|")
                and stripped.endswith("|")
                and stripped.count("|") < 3
            ):
                continue
            lines.append(line)
    return "\n".join(_drop_broken_reference_table_duplicate(lines)).strip()


def _drop_broken_reference_table_duplicate(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if (
            _REFERENCE_TABLE_HEADER_RE.match(stripped)
            and index + 2 < len(lines)
            and _MARKDOWN_TABLE_SEPARATOR_RE.fullmatch(lines[index + 1].strip())
            and _BROKEN_REFERENCE_TABLE_ROW_RE.match(lines[index + 2].strip())
        ):
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                index += 1
            continue
        if _BROKEN_REFERENCE_TABLE_ROW_RE.match(stripped):
            index += 1
            continue
        cleaned.append(lines[index])
        index += 1
    return cleaned


__all__ = [
    "ARTICLE_BODY_SELECTORS",
    "ROYAL_SOCIETY_EXTRACTION_CLEANUP_SELECTORS",
    "ROYAL_SOCIETY_FRONT_MATTER_EXACT_TEXTS",
    "ROYAL_SOCIETY_MARKDOWN_PROMO_TOKENS",
    "ROYAL_SOCIETY_SUPPLEMENTARY_TEXT_TOKENS",
    "RoyalSocietyHtmlExtraction",
    "citation_references_from_metadata",
    "direct_article_url",
    "direct_pdf_url",
    "extract_authors",
    "extract_markdown",
    "html_references_from_ref_list",
    "merge_metadata_with_html",
    "pdf_candidate_urls",
    "royalsocietypublishing_normalize_markdown",
]
