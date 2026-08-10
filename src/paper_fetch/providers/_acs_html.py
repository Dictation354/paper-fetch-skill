"""ACS provider-owned browser-workflow rules."""

from __future__ import annotations

import copy
from functools import partial
import re
from typing import Any
from collections.abc import Mapping

from bs4 import BeautifulSoup, Tag

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
    from .atypon_browser_workflow.asset_scopes import extract_scoped_html_assets

    return extract_scoped_html_assets(
        promote_silverchair_srcset_originals(body_html_text),
        source_url,
        **kwargs,
    )


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
