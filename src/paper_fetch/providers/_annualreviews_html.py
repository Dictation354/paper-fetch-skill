"""Annual Reviews provider-owned HTML extraction helpers."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, replace
from typing import Any
from collections.abc import Mapping
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup, Comment, Tag

from ..extraction.html._metadata import (
    merge_html_metadata,
    parse_html_metadata,
)
from ..extraction.html.assets import (
    extract_scoped_html_assets as extract_provider_neutral_scoped_assets,
)
from ..extraction.html.assets.silverchair import promote_silverchair_srcset_originals
from ..extraction.html.figure_links import inject_inline_figure_links
from ..extraction.html.parsing import choose_parser
from ..extraction.html.renderer import clean_rendered_markdown, render_html_markdown
from ..extraction.html.semantics import collect_html_section_hints
from ..extraction.html.shared import short_text
from ..extraction.html.signals import HtmlExtractionFailure
from ..extraction.html.tables import render_table_markdown
from ..extraction.markdown_render.figures import (
    INLINE_FIGURE_ALT_ATTR,
    INLINE_FIGURE_SRC_ATTR,
)
from ..extraction.markdown_render.tables import normalize_table_cell_text
from ..models import AssetProfile
from ..publisher_identity import extract_doi, normalize_doi
from ..quality.html_availability import (
    HTML_CONTAINER_SCOPE_ARTICLE,
    HTML_CONTAINER_SCOPE_EXPLICIT_BODY,
    HTML_CONTAINER_SCOPE_PAGE,
    HtmlContainerEvidence,
    HtmlQualityAssessor,
    availability_failure_message,
    html_container_evidence,
)
from ..utils import normalize_text
from ._html_section_markdown import (
    render_clean_text_from_html,
    render_container_markdown,
)


ANNUALREVIEWS_ARTICLE_SELECTORS = (
    "#itemFullTextId",
    "#html_fulltext",
)
ANNUALREVIEWS_EXTRACTION_CLEANUP_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "button",
    "input",
    "select",
    "textarea",
    ".dropDownMenu",
    ".menuButton",
    ".clearer",
    ".downloadAsPptContainer",
    ".download-pdf",
    ".access-options",
    ".article-header-metadata",
    ".article-title-and-authors",
    ".mostreadcontainer",
    ".mostcitedcontainer",
    ".morelikethiscontainer",
    "#js-recommend-load",
    "#metrics_content",
    "dialog",
    ".showPPT",
    ".js-references",
    ".open-table-fullscreen",
    ".toggle-table",
    ".ui-dialog",
    ".ui-autocomplete",
    "[id='figuredialog']",
    "[id='tabledialog']",
    "[id='videodialog']",
    "[id='multimediadialog']",
)
# SITE_UI_COPY_REGRESSION_MARKER: Annual Reviews article toolbar and resolver labels owned by provider cleanup policy; keep tied to provider cleanup tests.
ANNUALREVIEWS_MARKDOWN_PROMO_TOKENS = (
    "Download as PowerPoint",
    "Download PowerPoint",
    "Article Metrics",
    "Google Scholar",
    "Crossref",
    "Web of Science",
    "Medline",
    "Click to view",
    "Go to section",
    "Full text loading",
)
ANNUALREVIEWS_FRONT_MATTER_EXACT_TEXTS = (
    "Download PDF",
    "Toggle display:",
)
ANNUALREVIEWS_FRONT_MATTER_CONTAINS_TOKENS = ("Access provided by:",)
# SITE_UI_COPY_REGRESSION_MARKER: Annual Reviews post-content recommendation labels; keep tied to empty-shell replay tests.
# STRUCTURAL_UI_COPY_HOOK: provider-scoped post-content cutoff, not a generic body denylist.
ANNUALREVIEWS_POST_CONTENT_BREAK_TOKENS = (
    "most read this month",
    "most cited",
    "related articles from annual reviews",
)
ANNUALREVIEWS_SUPPLEMENTARY_TEXT_TOKENS: tuple[str, ...] = ()
ANNUALREVIEWS_SITE_RULE_OVERRIDES: dict[str, object] = {}
ANNUALREVIEWS_NOISE_PROFILE = "annualreviews"

_NOISY_LINES = {
    "top",
    "go to section...",
    "click to view",
    "download as powerpoint",
    "download powerpoint",
    "google scholar",
    "crossref",
    "web of science",
    "medline",
    "article metrics",
    "full text loading",
}
_NOISY_LINE_PREFIXES = (
    "?xml version=",
    "splitrids is ",
    "currentrid is ",
    "current position is ",
    "check position is ",
    "toggle display:",
    "open table ",
)
_REFERENCE_LINK_LABELS = {
    "[crossref]",
    "[google scholar]",
    "[medline]",
    "[pubmed]",
    "[web of science]",
}
_REFERENCE_LEADING_LABEL_RE = re.compile(
    r"^\s*(?:\[\d+[A-Za-z]?\]|\d+[A-Za-z]?[.)])\s+"
)
_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
_PUNCT_SPACE_RE = re.compile(r"\s+([,.;:])")
_TABLE_BLOCK_CLASS = "annualreviews-markdown-table"


@dataclass(frozen=True)
class _AnnualreviewsContainerSelection:
    node: Tag
    evidence: HtmlContainerEvidence


def direct_article_url(doi: str) -> str:
    normalized_doi = normalize_doi(doi)
    return f"https://www.annualreviews.org/content/journals/{quote(normalized_doi, safe='/')}"


def direct_pdf_url(doi: str) -> str:
    normalized_doi = normalize_doi(doi)
    return f"https://www.annualreviews.org/doi/pdf/{quote(normalized_doi, safe='/')}"


def merge_metadata_with_html(
    base_metadata: Mapping[str, Any] | None,
    html_text: str,
    source_url: str,
    *,
    doi: str | None = None,
) -> dict[str, Any]:
    html_metadata = parse_html_metadata(html_text, source_url)
    merged = _merge_metadata_with_parsed_html(
        base_metadata,
        html_metadata,
        doi=doi,
    )
    references = extract_references(html_text)
    if references and not merged.get("references"):
        merged["references"] = references
    return dict(merged)


def _merge_metadata_with_parsed_html(
    base_metadata: Mapping[str, Any] | None,
    html_metadata: Mapping[str, Any],
    *,
    doi: str | None = None,
) -> dict[str, Any]:
    merged = merge_html_metadata(base_metadata, html_metadata)
    doi_value = normalize_doi(str(doi or merged.get("doi") or ""))
    if doi_value and not merged.get("doi"):
        merged["doi"] = doi_value
    html_title = normalize_text(str(html_metadata.get("title") or ""))
    if html_title and (
        not normalize_text(str(merged.get("title") or ""))
        or normalize_doi(str(merged.get("title") or "")) == doi_value
    ):
        merged["title"] = html_title
    return dict(merged)


def extract_authors(html_text: str) -> list[str]:
    return list(parse_html_metadata(html_text, "").get("authors") or [])


def _node_text(node: Tag | None) -> str:
    if not isinstance(node, Tag):
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def _select_article_container(
    soup: BeautifulSoup,
) -> _AnnualreviewsContainerSelection | None:
    for selector in ANNUALREVIEWS_ARTICLE_SELECTORS:
        node = soup.select_one(selector)
        if isinstance(node, Tag) and len(_node_text(node)) >= 1200:
            return _AnnualreviewsContainerSelection(
                node=node,
                evidence=html_container_evidence(
                    node,
                    selector=selector,
                    scope=HTML_CONTAINER_SCOPE_EXPLICIT_BODY,
                ),
            )
    for selector, scope in (
        ("#html-body", HTML_CONTAINER_SCOPE_EXPLICIT_BODY),
        ("article", HTML_CONTAINER_SCOPE_ARTICLE),
        ("main", HTML_CONTAINER_SCOPE_PAGE),
    ):
        node = soup.select_one(selector)
        if isinstance(node, Tag) and len(_node_text(node)) >= 1200:
            return _AnnualreviewsContainerSelection(
                node=node,
                evidence=html_container_evidence(
                    node,
                    selector=selector,
                    scope=scope,
                ),
            )
    return None


def _canonical_heading(text: str) -> str:
    heading = normalize_text(str(text or "").replace("\u2002", " "))
    heading = heading.strip(" \t\r\n:-")
    heading = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", lambda match: match.group(0), heading)
    lowered = heading.casefold()
    aliases = {
        "abstract": "Abstract",
        "literature cited": "References",
        "references": "References",
        "reference": "References",
        "summary points": "Summary Points",
        "future issues": "Future Issues",
        "acknowledgments": "Acknowledgments",
        "acknowledgements": "Acknowledgments",
        "disclosure statement": "Disclosure Statement",
    }
    if lowered in aliases:
        return aliases[lowered]
    if lowered.startswith("literature cited"):
        return "References"
    if heading.isupper() and len(heading) > 3:
        return heading.title()
    return heading


def _new_tag_like(source: Tag, name: str, text: str) -> Tag:
    tag = BeautifulSoup("", choose_parser()).new_tag(name)
    attrs = getattr(source, "attrs", {}) or {}
    for key in ("id", "name"):
        value = attrs.get(key)
        if value:
            tag[key] = value
    tag.string = text
    return tag


def _normalize_section_headings(container: Tag) -> None:
    for divider in list(container.select(".sectionDivider")):
        if not isinstance(divider, Tag):
            continue
        title_node = divider.select_one(".tl-main-part.title")
        title = _canonical_heading(_node_text(title_node))
        if not title:
            divider.decompose()
            continue
        divider.replace_with(_new_tag_like(title_node or divider, "h2", title))

    for lowest in list(container.select(".tl-lowest-section")):
        if not isinstance(lowest, Tag):
            continue
        label_node = lowest.find_previous_sibling(class_="label")
        label = _node_text(label_node if isinstance(label_node, Tag) else None)
        title = _canonical_heading(
            " ".join(item for item in (label, _node_text(lowest)) if item)
        )
        if isinstance(label_node, Tag):
            label_node.decompose()
        if title:
            lowest.replace_with(_new_tag_like(lowest, "h3", title))


def _remove_noise_nodes(container: Tag) -> None:
    for selector in ANNUALREVIEWS_EXTRACTION_CLEANUP_SELECTORS:
        for node in list(container.select(selector)):
            if isinstance(node, Tag):
                node.decompose()

    for anchor in list(container.find_all("a", href=True)):
        if not isinstance(anchor, Tag):
            continue
        href = normalize_text(str(anchor.get("href") or "")).lower()
        text = normalize_text(anchor.get_text(" ", strip=True))
        lowered = text.lower()
        if ".ppt" in href or "powerpoint" in href:
            anchor.decompose()
            continue
        if lowered in _REFERENCE_LINK_LABELS or "google scholar" in lowered:
            anchor.decompose()
            continue
        if href.startswith("#"):
            if text:
                anchor.replace_with(text)
            else:
                anchor.decompose()

    for node in list(container.find_all(["span", "div", "p"])):
        if not isinstance(node, Tag):
            continue
        text = normalize_text(node.get_text(" ", strip=True)).lower()
        if text in _NOISY_LINES:
            node.decompose()

    for text_node in list(container.find_all(string=True)):
        raw_text = str(text_node or "")
        normalized = normalize_text(raw_text).lower()
        if isinstance(text_node, Comment) or any(
            normalized.startswith(prefix) for prefix in _NOISY_LINE_PREFIXES
        ):
            text_node.extract()


def _clean_figure_caption_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = normalized.replace("\u2002", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _figure_caption(figure: Tag) -> str:
    caption = figure.find("figcaption")
    if isinstance(caption, Tag):
        return _clean_figure_caption_text(render_clean_text_from_html(caption))
    caption = figure.find(class_="caption")
    if isinstance(caption, Tag):
        return _clean_figure_caption_text(render_clean_text_from_html(caption))
    return ""


def _normalize_figures(container: Tag, source_url: str) -> None:
    for figure in list(
        container.select(".html-fulltext-responsive-figure, div.figure")
    ):
        if not isinstance(figure, Tag):
            continue
        figure.name = "figure"
        for node in list(
            figure.select(".downloadAsPptContainer, .figure-duplicate-label")
        ):
            if isinstance(node, Tag):
                node.decompose()
        for anchor in list(figure.find_all("a", href=True)):
            if not isinstance(anchor, Tag):
                continue
            href = normalize_text(str(anchor.get("href") or "")).lower()
            if ".ppt" in href or "powerpoint" in href:
                anchor.decompose()
        for paragraph in list(figure.select(".image p")):
            if isinstance(paragraph, Tag):
                paragraph.decompose()

        caption_node = figure.find(class_="caption")
        if isinstance(caption_node, Tag):
            caption_node.name = "figcaption"
        caption = _figure_caption(figure)

        image = figure.find("img")
        if not isinstance(image, Tag):
            continue
        media_link = image.find_parent("a", class_="media-link")
        if not isinstance(media_link, Tag):
            media_link = image.find_parent("a", href=True)
        full_size = (
            urljoin(source_url, normalize_text(str(media_link.get("href") or "")))
            if isinstance(media_link, Tag)
            else ""
        )
        preview = urljoin(source_url, normalize_text(str(image.get("src") or "")))
        figure_url = full_size or preview
        if full_size:
            image["data-full-size"] = full_size
        if figure_url:
            image[INLINE_FIGURE_SRC_ATTR] = figure_url
        image[INLINE_FIGURE_ALT_ATTR] = (
            caption or normalize_text(str(image.get("alt") or "Figure")) or "Figure"
        )


def _table_cell_text(cell: Tag) -> str:
    return normalize_table_cell_text(
        render_clean_text_from_html(cell, collapse_prose_line_breaks=True)
    )


def _table_footnotes(table_container: Tag) -> list[str]:
    footnotes: list[str] = []
    for node in table_container.select(".tabFoot p"):
        if not isinstance(node, Tag):
            continue
        text = render_clean_text_from_html(node, collapse_prose_line_breaks=True)
        if text:
            footnotes.append(text)
    return footnotes


def _markdown_table_block(table: Tag, table_container: Tag) -> str:
    markdown = render_table_markdown(
        table,
        label="",
        caption="",
        render_inline_text=_table_cell_text,
    )
    if not markdown:
        return ""
    lines = [markdown]
    footnotes = _table_footnotes(table_container)
    if footnotes:
        lines.append("")
        lines.extend(footnotes)
    return "\n".join(lines)


def _replace_with_markdown_table(table_container: Tag, table: Tag) -> None:
    markdown = _markdown_table_block(table, table_container)
    if not markdown:
        return
    replacement = BeautifulSoup("", choose_parser()).new_tag("pre")
    replacement["class"] = _TABLE_BLOCK_CLASS
    replacement.string = markdown
    table_container.replace_with(replacement)


def _normalize_tables(container: Tag) -> None:
    for caption in list(container.select(".table-caption-container")):
        if not isinstance(caption, Tag):
            continue
        for selector in (".toggle-table", ".open-table-fullscreen"):
            for node in list(caption.select(selector)):
                if isinstance(node, Tag):
                    node.decompose()

    for table_container in list(container.select(".table-container")):
        if not isinstance(table_container, Tag):
            continue
        table = table_container.select_one("table.html-fulltext-inline-table")
        if isinstance(table, Tag):
            _replace_with_markdown_table(table_container, table)

    for table in list(container.select("table.html-fulltext-inline-table")):
        if not isinstance(table, Tag):
            continue
        _replace_with_markdown_table(table, table)


def _normalize_references(container: Tag) -> None:
    for label in list(container.select(".citation-label")):
        if isinstance(label, Tag):
            label.decompose()
    for node in list(container.select("span.references")):
        if isinstance(node, Tag) and node.find(("ol", "ul")) is not None:
            node.name = "div"


def _cleaned_article_html(
    html_text: str,
    source_url: str,
) -> tuple[
    str,
    str,
    int,
    list[dict[str, Any]],
    list[dict[str, Any]],
    HtmlContainerEvidence,
]:
    soup = BeautifulSoup(html_text, choose_parser())
    html_metadata = parse_html_metadata(html_text, source_url)
    return _cleaned_article_html_from_soup(
        soup,
        html_text,
        source_url,
        html_metadata=html_metadata,
    )


def _cleaned_article_html_from_soup(
    soup: BeautifulSoup,
    html_text: str,
    source_url: str,
    *,
    html_metadata: Mapping[str, Any] | None = None,
) -> tuple[
    str,
    str,
    int,
    list[dict[str, Any]],
    list[dict[str, Any]],
    HtmlContainerEvidence,
]:
    selection = _select_article_container(soup)
    if selection is None:
        raise HtmlExtractionFailure(
            "article_container_not_found",
            "Could not identify the Annual Reviews full-text container.",
        )
    cleaned = copy.deepcopy(selection.node)
    _remove_noise_nodes(cleaned)
    _normalize_section_headings(cleaned)
    _normalize_figures(cleaned, source_url)
    _normalize_tables(cleaned)
    _normalize_references(cleaned)
    _remove_noise_nodes(cleaned)

    title = _extract_page_title_from_soup(soup, metadata=html_metadata)
    container_text_length = len(_node_text(cleaned))
    section_hints = collect_html_section_hints(cleaned, title=title)
    abstract_sections = _abstract_sections(
        cleaned, html_metadata or parse_html_metadata(html_text, source_url)
    )
    article_soup = BeautifulSoup("<article></article>", choose_parser())
    article = article_soup.find("article")
    if not isinstance(article, Tag):
        raise HtmlExtractionFailure(
            "article_container_not_found",
            "Could not create normalized Annual Reviews article container.",
        )
    article.extend(copy.copy(child) for child in cleaned.contents)
    return (
        str(article),
        title,
        container_text_length,
        section_hints,
        abstract_sections,
        replace(selection.evidence, tag="article", synthetic=True),
    )


def _abstract_sections(
    container: Tag, html_metadata: Mapping[str, Any]
) -> list[dict[str, str]]:
    abstract_node = container.select_one(".article-abstract")
    if isinstance(abstract_node, Tag):
        paragraphs = [
            _node_text(paragraph)
            for paragraph in abstract_node.find_all("p")
            if _node_text(paragraph)
        ]
        if paragraphs:
            return [
                {"heading": "Abstract", "text": normalize_text(" ".join(paragraphs))}
            ]
    abstract = normalize_text(str(html_metadata.get("abstract") or ""))
    return [{"heading": "Abstract", "text": abstract}] if abstract else []


def extract_page_title(html_text: str) -> str:
    metadata = parse_html_metadata(html_text, "")
    soup = BeautifulSoup(html_text, choose_parser())
    return _extract_page_title_from_soup(soup, metadata=metadata)


def _extract_page_title_from_soup(
    soup: BeautifulSoup,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    title = normalize_text(str(metadata.get("title") or ""))
    if title:
        return title
    return short_text(soup.find("h1")) or ""


def _render_annualreviews_article_markdown(article_html: str, source_url: str) -> str:
    del source_url
    soup = BeautifulSoup(article_html, choose_parser())
    article = soup.find("article")
    if not isinstance(article, Tag):
        return ""
    lines: list[str] = []
    render_container_markdown(
        article,
        lines,
        level=2,
        section_content_selectors=(),
    )
    return "\n".join(lines)


def annualreviews_normalize_markdown(text: str) -> str:
    blocks = re.split(r"\n\s*\n", str(text or ""))
    kept: list[str] = []
    for block in blocks:
        normalized = normalize_text(block)
        lowered = normalized.lower()
        if not normalized:
            continue
        if lowered in _NOISY_LINES:
            continue
        if any(
            token.lower() in lowered for token in ANNUALREVIEWS_MARKDOWN_PROMO_TOKENS
        ):
            if len(normalized) < 240:
                continue
        cleaned_lines: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                cleaned_lines.append(raw_line)
                continue
            heading_match = _HEADING_RE.match(line)
            if heading_match is not None:
                heading = _canonical_heading(heading_match.group(2))
                cleaned_lines.append(f"{heading_match.group(1)} {heading}")
                continue
            lowered_line = normalize_text(line).lower()
            if lowered_line in _NOISY_LINES:
                continue
            if any(lowered_line.startswith(prefix) for prefix in _NOISY_LINE_PREFIXES):
                continue
            cleaned_lines.append(raw_line)
        cleaned = "\n".join(cleaned_lines).strip()
        if cleaned:
            kept.append(cleaned)
    markdown = "\n\n".join(kept)
    markdown = _PUNCT_SPACE_RE.sub(r"\1", markdown)
    return clean_rendered_markdown(markdown, noise_profile=ANNUALREVIEWS_NOISE_PROFILE)


def extract_references(html_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, choose_parser())
    references: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in soup.select("li.refbody"):
        if not isinstance(node, Tag):
            continue
        ref = copy.deepcopy(node)
        for selector in (".js-references", "a.externallink", "a.js-externallink"):
            for item in list(ref.select(selector)):
                if isinstance(item, Tag):
                    item.decompose()
        for item in list(ref.select(".citation-label")):
            if isinstance(item, Tag):
                item.decompose()
        raw = normalize_text(ref.get_text(" ", strip=True))
        raw = _REFERENCE_LEADING_LABEL_RE.sub("", raw).strip()
        raw = _PUNCT_SPACE_RE.sub(r"\1", raw)
        if not raw:
            continue
        doi = normalize_doi(str(node.get("data-doi") or "")) or extract_doi(raw)
        key = normalize_text(doi or raw).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        title = _node_text(ref.select_one(".reference-article-title")) or None
        year = _node_text(ref.select_one(".reference-year")) or None
        references.append(
            {
                "raw": f"{len(references) + 1}. {raw}",
                "title": title,
                "year": year,
                "doi": doi,
            }
        )
    return references


def extract_keywords(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    metadata = parse_html_metadata(html_text, "")
    return _extract_keywords_from_soup(soup, metadata=metadata)


def _extract_keywords_from_soup(
    soup: BeautifulSoup,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> list[str]:
    keywords: list[str] = []
    for node in soup.select(".keywords li"):
        if not isinstance(node, Tag):
            continue
        value = normalize_text(node.get_text(" ", strip=True)).strip(" ,;")
        if value and value not in keywords:
            keywords.append(value)
    for value in (metadata or {}).get("keywords") or []:
        keyword = normalize_text(str(value))
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    return keywords


def extract_asset_html_scopes(html_text: str, source_url: str) -> tuple[str, str]:
    (
        article_html,
        _title,
        _container_text_length,
        _section_hints,
        _abstract_sections,
        _container_evidence,
    ) = _cleaned_article_html(html_text, source_url)
    return article_html, ""


def extract_scoped_html_assets(
    html_text: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, str]]:
    body_html, supplementary_html = extract_asset_html_scopes(html_text, source_url)
    body_html = promote_silverchair_srcset_originals(body_html)
    assets = extract_provider_neutral_scoped_assets(
        body_html,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html,
        noise_profile=ANNUALREVIEWS_NOISE_PROFILE,
    )
    return _dedupe_assets(assets)


def _dedupe_assets(assets: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for asset in assets:
        key = (
            normalize_text(str(asset.get("kind") or "")).lower(),
            normalize_text(
                str(
                    asset.get("full_size_url")
                    or asset.get("url")
                    or asset.get("preview_url")
                    or asset.get("heading")
                    or ""
                )
            ).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(asset)
    return deduped


def blocking_fallback_signals(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    selection = _select_article_container(soup)
    if (
        selection is not None
        and selection.evidence.scope != HTML_CONTAINER_SCOPE_PAGE
        and len(_node_text(selection.node)) >= 1200
    ):
        return []
    text = normalize_text(soup.get_text(" ", strip=True)).lower()
    signals: list[str] = []
    if selection is not None and selection.evidence.scope == HTML_CONTAINER_SCOPE_PAGE:
        signals.append("untrusted_article_container")
    if "full text loading" in text:
        signals.append("full_text_loading_shell")
    if "the full text of this item is not currently available" in text:
        signals.append("fulltext_unavailable")
    return signals


def extract_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    soup = BeautifulSoup(html_text, choose_parser())
    html_metadata = parse_html_metadata(html_text, source_url)
    merged_metadata = _merge_metadata_with_parsed_html(
        metadata,
        html_metadata,
        doi=str((metadata or {}).get("doi") or html_metadata.get("doi") or "") or None,
    )
    (
        article_html,
        title,
        container_text_length,
        section_hints,
        abstract_sections,
        container_evidence,
    ) = _cleaned_article_html_from_soup(
        soup,
        html_text,
        source_url,
        html_metadata=html_metadata,
    )
    if not title:
        title = normalize_text(str(merged_metadata.get("title") or ""))
    markdown = render_html_markdown(
        article_html,
        source_url,
        trafilatura_backend=None,
        noise_profile=ANNUALREVIEWS_NOISE_PROFILE,
        renderer=_render_annualreviews_article_markdown,
        postprocessors=(annualreviews_normalize_markdown,),
    )
    if title and f"# {title}" not in markdown:
        markdown = f"# {title}\n\n{markdown}".strip()
    references = extract_references(article_html)
    if references and not merged_metadata.get("references"):
        merged_metadata["references"] = references
    extracted_assets = extract_scoped_html_assets(
        article_html,
        source_url,
        asset_profile="body",
    )
    markdown = inject_inline_figure_links(
        markdown,
        figure_assets=extracted_assets,
        clean_markdown_fn=annualreviews_normalize_markdown,
    )

    # Annual Reviews repeats abstract-only metadata and abstract-page hints in
    # citation meta tags even on full-text pages. Keep the availability check
    # focused on DOI/title plus the provider-cleaned DOM.
    quality_metadata = {
        "doi": merged_metadata.get("doi"),
        "title": title or merged_metadata.get("title"),
    }
    diagnostics = HtmlQualityAssessor("annualreviews").assess(
        markdown,
        quality_metadata,
        html_text=article_html,
        title=title,
        final_url=source_url,
        container_tag="article",
        container_text_length=container_text_length,
        container_evidence=container_evidence,
        section_hints=section_hints,
    )
    if not diagnostics.accepted:
        raise HtmlExtractionFailure(
            diagnostics.reason,
            availability_failure_message(diagnostics),
        )

    extraction_payload = {
        "title": title,
        "abstract_text": normalize_text(abstract_sections[0]["text"])
        if abstract_sections
        else None,
        "abstract_sections": abstract_sections,
        "section_hints": section_hints,
        "container_tag": "article",
        "container_selector": container_evidence.selector,
        "container_scope": container_evidence.scope,
        "container_synthetic": container_evidence.synthetic,
        "container_text_length": container_text_length,
        "availability_diagnostics": diagnostics.to_dict(),
        "extracted_authors": extract_authors(html_text),
        "keywords": _extract_keywords_from_soup(soup, metadata=html_metadata),
        "references": references,
        "extracted_assets": extracted_assets,
    }
    return markdown, extraction_payload


__all__ = [
    "ANNUALREVIEWS_ARTICLE_SELECTORS",
    "ANNUALREVIEWS_EXTRACTION_CLEANUP_SELECTORS",
    "ANNUALREVIEWS_FRONT_MATTER_CONTAINS_TOKENS",
    "ANNUALREVIEWS_FRONT_MATTER_EXACT_TEXTS",
    "ANNUALREVIEWS_MARKDOWN_PROMO_TOKENS",
    "ANNUALREVIEWS_NOISE_PROFILE",
    "ANNUALREVIEWS_POST_CONTENT_BREAK_TOKENS",
    "ANNUALREVIEWS_SITE_RULE_OVERRIDES",
    "ANNUALREVIEWS_SUPPLEMENTARY_TEXT_TOKENS",
    "annualreviews_normalize_markdown",
    "blocking_fallback_signals",
    "direct_article_url",
    "direct_pdf_url",
    "extract_asset_html_scopes",
    "extract_authors",
    "extract_keywords",
    "extract_markdown",
    "extract_references",
    "extract_scoped_html_assets",
    "merge_metadata_with_html",
]
