"""Silverchair article, reference, and asset scopes for RSC journals."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from ..extraction.html._metadata import parse_html_metadata, raw_html_meta_values
from ..extraction.html.assets import extract_scoped_html_assets
from ..extraction.html.assets.silverchair import silverchair_download_image_url
from ..extraction.html.figure_links import inject_inline_figure_links
from ..extraction.html.inline import render_html_inline_node
from ..extraction.html.parsing import choose_parser
from ..extraction.html.renderer import (
    clean_rendered_markdown,
    render_provider_html_fragment,
)
from ..extraction.html.signals import HtmlExtractionFailure
from ..extraction.html.tables import render_table_markdown
from ..markdown.images import render_markdown_image
from ..models import AssetProfile
from ..publisher_identity import extract_doi, extract_doi_from_url, normalize_doi
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..reason_codes import ABSTRACT_ONLY, IDENTITY_MISMATCH
from ..rsc_url import is_rsc_main_pdf, is_rsc_silverchair_article, rsc_legacy_doi
from ._html_references import extract_numbered_references_from_soup
from ._html_section_markdown import (
    render_clean_text_from_html,
    render_figure_markdown,
    render_html_fragment_markdown,
)
from .browser_runtime.types import BrowserFetchedHtml

FULLTEXT_SELECTOR = ".article-body .widget-ArticleFulltext"
ABSTRACT_SELECTOR = "section.abstract, .abstractSection, .article-abstract"
SUPPLEMENT_SELECTOR = ".article-body .widget-ArticleDataSupplements"
BODY_PARAGRAPH_SELECTOR = ".article-section-wrapper > p"
_BODY_NOISE = (
    ".fig-modal, .original-slide, .fig-table-toggle, .table-modal, "
    ".table-wrap > .graphic-wrap, .permissionstatement-section-wrapper, "
    ".hidden, .hide, .d-none, [hidden], [aria-hidden='true'], script, style"
)
_TABLE_IMAGES = ".table-wrap .table-overflow img.content-image[src]"
_INLINE_FORMULA_FILENAME = re.compile(r"-t\d+\.", re.I)


def citation_doi(metadata: Mapping[str, Any]) -> str | None:
    dois = {
        doi
        for value in raw_html_meta_values(metadata, "citation_doi")
        if (doi := extract_doi(value))
    }
    if len(dois) == 1:
        doi = next(iter(dois))
        if doi.startswith("10.1039/"):
            return doi
    return None


def article_matches(metadata: Mapping[str, Any], source_url: str, doi: str) -> bool:
    legacy_doi = rsc_legacy_doi(source_url)
    if not legacy_doi and not is_rsc_silverchair_article(source_url):
        return False
    if raw_html_meta_values(metadata, "citation_doi"):
        return citation_doi(metadata) == doi and legacy_doi in {None, doi}
    observed_doi = normalize_doi(metadata.get("doi"))
    return (observed_doi or legacy_doi) == doi and legacy_doi in {None, doi}


def pdf_candidates_from_html(html_text: str, source_url: str, *, doi: str) -> list[str]:
    metadata = parse_html_metadata(html_text, source_url)
    if not article_matches(metadata, source_url, doi):
        return []
    return list(
        dict.fromkeys(
            url
            for value in raw_html_meta_values(metadata, "citation_pdf_url")
            if is_rsc_main_pdf(url := urljoin(source_url, value), doi)
        )
    )


def remaining_html_candidates(
    candidates: list[str], page: BrowserFetchedHtml
) -> list[str]:
    doi = extract_doi_from_url(candidates[-1]) if candidates else None
    if doi and pdf_candidates_from_html(page.html, page.final_url, doi=doi):
        return []
    if page.source_url in candidates:
        return candidates[candidates.index(page.source_url) + 1 :]
    return []


def extract_asset_html_scopes(html_text: str, source_url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html_text, choose_parser())
    body = soup.select_one(FULLTEXT_SELECTOR)
    supplement = soup.select_one(SUPPLEMENT_SELECTOR)
    if body is not None:
        for figure in body.select(".fig-section"):
            image = figure.select_one("img.content-image")
            if image is None:
                continue
            preview = str(image.get("data-src") or image.get("src") or "")
            if original := silverchair_download_image_url(
                figure, source_url, expected_image_basename=preview
            ):
                image["data-hi-res-src"] = original
        for item in body.select(_BODY_NOISE):
            item.decompose()
        for image in body.select("img.content-image"):
            if url := _content_image_url(image, source_url):
                image["src"] = url
                if (
                    image.parent.name == "p"
                    or "block-child-p" in image.parent.get("class", [])
                ) and _INLINE_FORMULA_FILENAME.search(
                    str(image.get("path-from-xml") or "")
                ):
                    image["class"].append("inline-formula")
    return str(body or ""), str(supplement or "")


def _content_image_url(image: Tag, source_url: str) -> str:
    candidate = image.get("data-src") or image.get("src")
    if not candidate:
        return ""
    url = urljoin(source_url, str(candidate))
    parts = urlsplit(url)
    if parts.scheme in {"http", "https"} and not parts.path.endswith("/preloader.gif"):
        return url
    return ""


def extract_scoped_assets(
    body_html: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
    supplementary_html_text: str,
) -> list[dict[str, Any]]:
    assets = extract_scoped_html_assets(
        body_html,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html_text,
    )
    for asset in assets:
        if asset["kind"] == "figure" and asset.get("full_size_url"):
            # Keep the same figure identity when the downloaded rendition is
            # the preview rather than the full-size image.
            asset["original_url"] = asset["full_size_url"]
    soup = BeautifulSoup(body_html, choose_parser())
    for image in soup.select(_TABLE_IMAGES):
        url = _content_image_url(image, source_url)
        if not url:
            continue
        table = image.find_parent(class_="table-wrap")
        label = table.select_one(".table-wrap-title .label") if table else None
        assets.append(
            {
                "kind": "table",
                "heading": label.get_text(strip=True) if label else "Table",
                "url": url,
                "preview_url": url,
                "preview_accepted": "true",
                "section": "body",
                "render_state": "inline",
            }
        )
    return assets


def _abstract_blocks(body: BeautifulSoup) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for node in body.select(f"{ABSTRACT_SELECTOR}, .graphical-abstract"):
        if node.parent is None:
            continue
        if "graphical-abstract" in node.get("class", []):
            figure = node.select_one(".fig-section")
            lines: list[str] = []
            render_figure_markdown(figure, lines)
            title = node.select_one(".graphical-abstract-label")
            heading = title.get_text(strip=True) if title else "Graphical Abstract"
            text = "\n".join(lines).strip()
        else:
            heading, text = "Abstract", render_clean_text_from_html(node)
        node.decompose()
        if text and not any(block["heading"] == heading for block in blocks):
            blocks.append({"heading": heading, "text": text, "kind": "abstract"})
    return blocks


def _table_cell_html(cell: Tag) -> str:
    clone = deepcopy(cell)
    for child in clone.find_all(True):
        if child.name == "img" and str(child.get("src", "")).startswith(
            ("https://", "http://")
        ):
            child.attrs = {"src": child["src"], "alt": "Chemical structure"}
        elif child.name in {"sub", "sup", "em", "strong", "i", "b", "br"}:
            child.attrs = {}
        else:
            child.unwrap()
    return re.sub(r"\s*[\r\n]\s*", " ", clone.decode_contents())


def _replace_with_markdown(body: BeautifulSoup, node: Tag, markdown: str) -> None:
    replacement = body.new_tag("div", attrs={"data-paper-fetch-markdown": "true"})
    replacement.string = markdown
    node.replace_with(replacement)


def _render_tables(body: BeautifulSoup) -> None:
    for wrapper in body.select(".table-wrap"):
        table = wrapper.select_one(".table-overflow > table")
        if table is None:
            continue
        label = wrapper.select_one(".table-wrap-title .label")
        caption = wrapper.select_one(".table-wrap-title .caption")
        markdown = render_table_markdown(
            table,
            label=label.get_text(strip=True) if label else "",
            caption=render_clean_text_from_html(caption),
            render_inline_html=_table_cell_html,
        )
        notes = [
            render_html_inline_node(note, render_text_styles=True)
            for note in wrapper.select(".table-wrap-foot .fn")
        ]
        _replace_with_markdown(body, wrapper, "\n\n".join([markdown, *notes]))


def _render_display_formulas(body: BeautifulSoup, source_url: str) -> None:
    for wrapper in body.select(".formula-wrap"):
        formula = wrapper.select_one(".disp-formula")
        if formula is None:
            continue
        label = wrapper.select_one(":scope > .label")
        number = label.get_text(strip=True) if label else ""
        image = formula.select_one("img.content-image[src]")
        if image is not None and (url := _content_image_url(image, source_url)):
            rendered = render_markdown_image("formula", number, url)
        elif formula.find(["math", "tex-math", "script"]):
            continue
        else:
            rendered = render_html_inline_node(
                formula, render_text_styles=True, break_render="<br>"
            )
        if rendered:
            _replace_with_markdown(
                body, wrapper, " ".join(filter(None, (rendered, number)))
            )


def _extract_references(body: BeautifulSoup) -> list[dict[str, str | None]]:
    for group in body.select(".js-splitview-ref-list > .ref-list"):
        # Migrated articles can give a group of lettered references a shared
        # introduction. Keep it with the first citation in that group.
        first_citation = group.select_one(".ref .ref-body")
        introductions = group.find_all("p", recursive=False)
        if first_citation is not None and introductions:
            lead = " ".join(node.get_text(" ", strip=True) for node in introductions)
            first_citation.insert(0, lead + " ")
    for reference in body.select(".js-splitview-ref-list .ref"):
        label = reference.select_one(".label")
        if label is not None:
            reference["data-counter"] = "".join(label.stripped_strings)
        for note in reference.select(".ref-body > .ref-note"):
            note.insert_before(" ")
            note.insert_after(" ")
    return extract_numbered_references_from_soup(body, content_selector=".ref-body")


def extract_markdown(
    html_text: str, source_url: str, *, metadata: Mapping[str, Any]
) -> tuple[str, dict[str, Any]]:
    html_metadata = parse_html_metadata(html_text, source_url)
    doi = normalize_doi(metadata.get("doi")) or citation_doi(html_metadata)
    if not doi or not article_matches(html_metadata, source_url, doi):
        raise HtmlExtractionFailure(
            IDENTITY_MISMATCH, "The RSC article page does not match the requested DOI."
        )

    body_html, supplement_html = extract_asset_html_scopes(html_text, source_url)
    body = BeautifulSoup(body_html, choose_parser())
    if not body.select_one(BODY_PARAGRAPH_SELECTOR):
        reason = (
            ABSTRACT_ONLY
            if body.select_one(ABSTRACT_SELECTOR)
            else "article_container_not_found"
        )
        raise HtmlExtractionFailure(
            reason, "The RSC page does not expose an article body."
        )

    references = _extract_references(body)
    for node in body.select(".js-splitview-ref-list, .backreferences-title"):
        node.decompose()
    abstracts = _abstract_blocks(body)
    _render_tables(body)
    _render_display_formulas(body, source_url)
    title = str(html_metadata.get("title") or metadata.get("title") or "")
    rendered = render_provider_html_fragment(
        str(body), source_url, title=title, renderer=render_html_fragment_markdown
    )
    assets = extract_scoped_assets(
        body_html,
        source_url,
        asset_profile="all",
        supplementary_html_text=supplement_html,
    )
    markdown = inject_inline_figure_links(
        rendered.markdown_text,
        figure_assets=assets,
        clean_markdown_fn=clean_rendered_markdown,
    )
    abstract_text = next(
        (block["text"] for block in abstracts if block["heading"] == "Abstract"),
        None,
    )
    article_metadata = {
        **metadata,
        "title": title,
        "abstract": abstract_text or metadata.get("abstract"),
    }
    diagnostics = HtmlQualityAssessor("rsc").assess(
        markdown,
        article_metadata,
        html_text=html_text,
        title=title,
        final_url=source_url,
        section_hints=rendered.section_hints,
    )
    if not diagnostics.accepted:
        raise HtmlExtractionFailure(
            diagnostics.reason, availability_failure_message(diagnostics)
        )
    return markdown, {
        "title": title,
        "abstract_text": abstract_text,
        "abstract_sections": abstracts,
        "section_hints": rendered.section_hints,
        "extracted_authors": html_metadata.get("authors") or [],
        "references": references,
        "extracted_assets": assets,
        "availability_diagnostics": diagnostics.to_dict(),
    }
