"""ACS provider-owned browser-workflow rules."""

from __future__ import annotations

import copy
from functools import partial
import re
from typing import Any
from collections.abc import Mapping

from bs4 import BeautifulSoup, NavigableString, Tag

from ..extraction.html.parsing import choose_parser
from ..utils import normalize_text
from ._html_authors import (
    ATYPON_AUTHOR_NOISE_TEXT,
    AuthorExtractionPipeline,
    AuthorStep,
    extract_jsonld_authors,
    extract_meta_authors,
)
from ._html_references import extract_numbered_references_from_html


ACS_JSONLD_ARTICLE_TYPES = frozenset({"article", "scholarlyarticle", "newsarticle"})
# SITE_UI_COPY_REGRESSION_MARKER: ACS Publications article chrome selectors.
# STRUCTURAL_UI_COPY_HOOK: ACS provider cleanup policy removes these only from ACS article HTML.
ACS_DOM_CHROME_SELECTORS = (
    ".article__copy",
    ".article__cc-license",
    ".article__tags",
    ".articleHeaderHistoryDropzone",
    ".articleCitedByDropzone",
    ".TermsAndConditionsDropzone3",
    ".article-metadata-panel",
    ".authorInformationSection",
    ".fig.fig-modal",
    ".graphical-abstract",
    ".refs-header-label",
    ".references-count",
    ".ref-list",
    "#sr-fig-viewer-action",
    ".widget-ArticleDataSupplements",
    "ol#references",
    "script",
)
# SITE_UI_COPY_REGRESSION_MARKER: ACS Publications copy-link chrome labels.
# STRUCTURAL_UI_COPY_HOOK: ACS provider cleanup policy removes these only after ACS markdown rendering.
ACS_MARKDOWN_CHROME_PATTERNS = (
    re.compile(
        r"\s*Click to copy article link\s+Article link copied!$",
        flags=re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"\s*Click to copy section link\s+Section link copied!",
        flags=re.IGNORECASE,
    ),
)
ACS_EMPTY_ABSTRACT_PAIR_PATTERN = re.compile(
    r"(## Abstract\n\n)(## Abstract\n\n)",
    flags=re.IGNORECASE,
)
ACS_FIGURE_ID_ATTRIBUTES = ("data-id", "content-id", "id")


def _extract_jsonld_authors(html_text: str) -> list[str]:
    return extract_jsonld_authors(
        html_text,
        article_types=ACS_JSONLD_ARTICLE_TYPES,
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep(
        "meta",
        partial(extract_meta_authors, keys={"citation_author", "dc.creator"}),
    ),
    AuthorStep("jsonld", _extract_jsonld_authors),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_PIPELINE(html_text)


def _decompose_matching(container: Any, selectors: tuple[str, ...]) -> None:
    if not isinstance(container, Tag):
        return
    for selector in selectors:
        for node in list(container.select(selector)):
            node.decompose()


def acs_before_block_normalization(container: Any) -> None:
    from .atypon_browser_workflow.profile import (
        _drop_promotional_blocks,
        _promo_block_tokens,
    )

    _decompose_matching(container, ACS_DOM_CHROME_SELECTORS)
    _drop_promotional_blocks(container, promo_block_tokens=_promo_block_tokens("acs"))
    # Publisher source wrapping is whitespace inside a heading, not a Markdown
    # block boundary. Preserve inline tags while joining its source text lines.
    for heading in container.select("h1, h2, h3, h4, h5, h6"):
        for text in list(heading.descendants):
            if isinstance(text, NavigableString):
                text.replace_with(re.sub(r"\s+", " ", str(text)))
    # Silverchair can split one labelled table into several visible tables,
    # each accompanied by a hidden accessibility copy. Keep every distinct
    # visible part available to the existing single-table block renderer.
    for wrapper in list(container.select(".table-wrap")):
        from ._html_section_markdown import render_retained_text_from_html

        note_blocks = []
        for note in wrapper.select(".table-wrap-foot"):
            paragraph = BeautifulSoup("", choose_parser()).new_tag("p")
            paragraph.string = render_retained_text_from_html(note)
            note_blocks.append(paragraph)
            note.decompose()
        tables = [
            table
            for table in wrapper.find_all("table")
            if not any(
                parent.get("aria-hidden") == "true"
                for parent in [table, *table.parents]
            )
        ]
        anchor = wrapper
        for table in tables[1:]:
            continuation = BeautifulSoup("", choose_parser()).new_tag("div")
            continuation["class"] = ["table-wrap"]
            continuation.append(table.extract())
            anchor.insert_after(continuation)
            anchor = continuation
        for note in note_blocks:
            anchor.insert_after(note)
            anchor = note


def acs_body_container(container: Any) -> None:
    _decompose_matching(container, ACS_DOM_CHROME_SELECTORS)


def select_content_nodes(container: Any, **_kwargs: Any) -> list[Tag]:
    """Keep a selected Silverchair ``.article-body`` as the extraction root."""

    if not isinstance(container, Tag):
        return []
    classes = {
        normalize_text(str(value))
        for value in (container.get("class") or [])
        if normalize_text(str(value))
    }
    return [container] if "article-body" in classes else []


def _restore_silverchair_figure_download_links(
    body_container: Any,
    raw_body_container: Any,
) -> None:
    if not isinstance(body_container, Tag) or not isinstance(raw_body_container, Tag):
        return

    raw_figures: dict[tuple[str, str], list[Tag]] = {}
    for raw_figure in raw_body_container.select(".fig.fig-section"):
        if not isinstance(raw_figure, Tag):
            continue
        for attribute in ACS_FIGURE_ID_ATTRIBUTES:
            value = normalize_text(str(raw_figure.get(attribute) or ""))
            if value:
                raw_figures.setdefault((attribute, value), []).append(raw_figure)

    for body_figure in body_container.select(".fig.fig-section"):
        if not isinstance(body_figure, Tag):
            continue
        nested_figure = body_figure.select_one(".graphic-wrap, figure")
        download_link_target = (
            nested_figure if isinstance(nested_figure, Tag) else body_figure
        )
        matching_raw_figures: list[Tag] = []
        seen_raw_figures: set[int] = set()
        for attribute in ACS_FIGURE_ID_ATTRIBUTES:
            value = normalize_text(str(body_figure.get(attribute) or ""))
            if not value:
                continue
            for raw_figure in raw_figures.get((attribute, value), []):
                if id(raw_figure) not in seen_raw_figures:
                    seen_raw_figures.add(id(raw_figure))
                    matching_raw_figures.append(raw_figure)

        existing_hrefs = {
            normalize_text(str(anchor.get("href") or ""))
            for anchor in body_figure.find_all("a", href=True)
        }
        for raw_figure in matching_raw_figures:
            for anchor in raw_figure.find_all("a", href=True):
                href = normalize_text(str(anchor.get("href") or ""))
                if (
                    "/downloadfile/downloadimage.aspx" not in href.lower()
                    or href in existing_hrefs
                ):
                    continue
                download_link_target.append(copy.deepcopy(anchor))
                existing_hrefs.add(href)


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
    del source_url
    for node in list(atypon_browser_workflow_supplementary_sections(body_container)):
        node.decompose()

    supplementary_source = (
        raw_body_container
        if isinstance(raw_body_container, Tag)
        else supplementary_container
    )
    supplementary_html = "\n".join(
        str(node)
        for node in atypon_browser_workflow_supplementary_sections(supplementary_source)
        if normalize_text(node.get_text(" ", strip=True))
    )
    _restore_silverchair_figure_download_links(body_container, raw_body_container)
    return (
        content_fragment_html(body_container, publisher=publisher),
        supplementary_html,
    )


def _clean_acs_markdown_chrome(markdown_text: str) -> str:
    text = markdown_text
    for pattern in ACS_MARKDOWN_CHROME_PATTERNS:
        text = pattern.sub("", text)
    text = ACS_EMPTY_ABSTRACT_PAIR_PATTERN.sub(r"\1", text)
    return text


def _clean_reference_text(node: Tag) -> str:
    citation = node.select_one(".NLM_citation") or node
    clone = copy.deepcopy(citation)
    if not isinstance(clone, Tag):
        return ""
    for selector in (
        ".casAbstract",
        ".casContent",
        ".casRecord",
        ".links-group",
        ".NLM_ref-label",
        ".refLabel",
        ".referenceLinks",
        ".references__suffix",
        ".google-scholar",
        ".ext-link",
        "a[href*='scholar.google']",
        "a[href*='getFTRLinkout']",
        "script",
    ):
        for match in list(clone.select(selector)):
            match.decompose()
    text = normalize_text(clone.get_text(" ", strip=True))
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"DOI:\s+", "DOI: ", text, flags=re.IGNORECASE)
    return normalize_text(text)


def _reference_year(text: str) -> str | None:
    match = re.search(r"\b((?:18|19|20)\d{2})\b", text)
    return match.group(1) if match else None


def _reference_doi(node: Tag) -> str | None:
    citation = node.select_one(".NLM_citation")
    doi = (
        normalize_text(str(citation.get("data-doi") or ""))
        if isinstance(citation, Tag)
        else ""
    )
    return doi or None


def extract_references(html_text: str) -> list[dict[str, str | None]]:
    if not normalize_text(html_text):
        return []
    soup = BeautifulSoup(html_text, choose_parser())
    nodes = [
        node for node in soup.select("ol#references > li") if isinstance(node, Tag)
    ]
    if not nodes:
        return extract_numbered_references_from_html(html_text)

    references: list[dict[str, str | None]] = []
    for index, node in enumerate(nodes, start=1):
        raw = _clean_reference_text(node)
        if not raw:
            continue
        references.append(
            {
                "label": f"{index}.",
                "raw": raw,
                "doi": _reference_doi(node),
                "year": _reference_year(raw),
            }
        )
    return references


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
    markdown_text = _clean_acs_markdown_chrome(markdown_text)
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    extracted_references = extract_references(html_text)
    if extracted_references:
        finalized["references"] = extracted_references
    return markdown_text, finalized


def scoped_asset_extractor(
    body_html_text: str,
    source_url: str,
    **kwargs: Any,
) -> list[dict[str, str]]:
    from ..extraction.html.assets.silverchair import (
        promote_silverchair_srcset_originals,
    )
    from ._html_asset_engine import merge_assets_by_identity
    from .atypon_browser_workflow.asset_scopes import extract_scoped_html_assets

    # Silverchair also embeds chemical graphics in table wrappers, outside
    # .fig-section. Expose those nodes only in the asset-discovery copy; the
    # article's table markup and signed image URLs remain unchanged.
    soup = BeautifulSoup(body_html_text, choose_parser())
    table_graphics: dict[str, tuple[str, str]] = {}
    for graphic in soup.select(".table-wrap .fig-graphic[id]"):
        if graphic.find_parent(class_="table-modal") is None:
            wrapper = graphic.find_parent(class_="table-wrap")
            label = wrapper.select_one(".table-wrap-title .label")
            caption = wrapper.select_one(".table-wrap-title .caption")
            heading = label.get_text(" ", strip=True).rstrip(".") if label else ""
            if not heading or len(wrapper.select(".fig-graphic[id]")) > 1:
                heading = f"{heading or 'Table graphic'} ({graphic['id']})"
            table_graphics[str(graphic["id"])] = (
                heading,
                caption.get_text(" ", strip=True) if caption else heading,
            )
            graphic.name = "figure"

    assets = merge_assets_by_identity(
        extract_scoped_html_assets(
            promote_silverchair_srcset_originals(str(soup)),
            source_url,
            **kwargs,
        )
    )
    # Generic image alt text is shared across chemical graphics. Use their
    # owning table labels so download-result merging cannot collapse them.
    for asset in assets:
        if table_info := table_graphics.get(asset.get("dom_id", "")):
            asset["heading"], asset["caption"] = table_info
    return assets


__all__ = [
    "ATYPON_AUTHOR_NOISE_TEXT",
    "acs_before_block_normalization",
    "acs_body_container",
    "extract_asset_html_scopes",
    "extract_authors",
    "extract_references",
    "finalize_extraction",
    "scoped_asset_extractor",
    "select_content_nodes",
]
