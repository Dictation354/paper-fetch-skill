"""arXiv metadata derivation and official HTML frontmatter helpers."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any
from collections.abc import Mapping, Sequence
import re

from ..arxiv_id import (
    arxiv_id_from_doi,
    arxiv_id_from_query,
    canonical_arxiv_abs_url,
    canonical_arxiv_doi,
    canonical_arxiv_html_url,
    canonical_arxiv_pdf_url,
    normalize_arxiv_id,
)
from ..extraction.html.semantics import SECTION_HEADING_PATTERN
from ..http import PDF_MIME_TYPE
from ..metadata.types import MetadataMergeRule, ProviderMetadata, merge_metadata_layers
from ..provider_catalog import register_metadata_probe_short_circuit
from ..reason_codes import NO_RESULT, NOT_SUPPORTED
from ..utils import dedupe_authors, normalize_text
from ._arxiv_authors import _AUTHOR_PIPELINE
from ._arxiv_html import (
    Tag,
    _arxiv_ar5iv_selectors,
    _arxiv_select_one,
    _clean_arxiv_frontmatter_text,
)
from ._html_section_markdown import render_heading_text_from_html
from .base import ProviderFailure

_ARXIV_WATERMARK_PATTERN = re.compile(
    r"arxiv:\s*(?P<arxiv_id>[^\s\[]+)(?:\s+\[(?P<category>[^\]]+)\])?(?:\s+(?P<date>\d{1,2}\s+[A-Za-z]{3}\s+\d{4}))?",
    flags=re.IGNORECASE,
)
_ARXIV_LIST_KEYS = frozenset(
    {
        "authors",
        "keywords",
        "license_urls",
        "fulltext_links",
        "categories",
    }
)
_ARXIV_SKIP_KEYS = frozenset({"source_url", "references"})
_ARXIV_SCALAR_KEYS = (
    "provider",
    "official_provider",
    "doi",
    "external_doi",
    "title",
    "abstract",
    "published",
    "updated",
    "journal_title",
    "publisher",
    "landing_page_url",
    "arxiv_id",
    "primary_category",
    "pdf_url",
    "html_url",
)
_ARXIV_APPEND_MERGE_RULE = MetadataMergeRule(
    overwrite=_ARXIV_SCALAR_KEYS,
    concat_unique=tuple(_ARXIV_LIST_KEYS),
)
_ARXIV_API_MERGE_RULE = MetadataMergeRule(
    overwrite=(*_ARXIV_SCALAR_KEYS, *_ARXIV_LIST_KEYS),
)
_ARXIV_TEXT_LIST_RULE = MetadataMergeRule(concat_unique=("values",))


def _mergeable_arxiv_layer(layer: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(layer, Mapping):
        return {}
    return {
        key: value
        for key, value in layer.items()
        if key not in _ARXIV_SKIP_KEYS and value not in (None, "", [])
    }


def _first_header_value(
    headers: Mapping[str, Any] | None, key: str, default: str = ""
) -> str:
    lowered = key.lower()
    for raw_key, value in (headers or {}).items():
        if str(raw_key).lower() == lowered:
            return str(value or default)
    return default


def _dedupe_metadata_text_values(values: Sequence[Any]) -> list[str]:
    merged = merge_metadata_layers(
        [{"values": list(values)}],
        rule=_ARXIV_TEXT_LIST_RULE,
    )
    return list(merged.get("values") or [])


def _dedupe_strings(values: Sequence[Any]) -> list[str]:
    return _dedupe_metadata_text_values(values)


def _datetime_to_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    normalized = normalize_text(value)
    return normalized or None


def _result_short_id(result: Any) -> str:
    get_short_id = getattr(result, "get_short_id", None)
    if callable(get_short_id):
        return normalize_arxiv_id(str(get_short_id()))
    entry_id = normalize_text(getattr(result, "entry_id", ""))
    return arxiv_id_from_query(entry_id)


def _result_authors(result: Any) -> list[str]:
    authors: list[str] = []
    for author in list(getattr(result, "authors", []) or []):
        name = normalize_text(getattr(author, "name", author))
        if name and name not in authors:
            authors.append(name)
    return authors


def metadata_from_arxiv_result(
    result: Any, *, requested_arxiv_id: str | None = None
) -> ProviderMetadata:
    arxiv_id = _result_short_id(result) or normalize_arxiv_id(requested_arxiv_id)
    if not arxiv_id:
        raise ProviderFailure(
            NO_RESULT, "arXiv API result did not include a usable arXiv ID."
        )
    pdf_url = normalize_text(getattr(result, "pdf_url", "")) or canonical_arxiv_pdf_url(
        arxiv_id
    )
    categories = [
        normalize_text(item)
        for item in list(getattr(result, "categories", []) or [])
        if normalize_text(item)
    ]
    external_doi = normalize_text(getattr(result, "doi", ""))
    metadata: dict[str, Any] = {
        "provider": "arxiv",
        "official_provider": True,
        "doi": canonical_arxiv_doi(arxiv_id),
        "external_doi": external_doi or None,
        "title": normalize_text(getattr(result, "title", "")) or None,
        "authors": _result_authors(result),
        "abstract": normalize_text(getattr(result, "summary", "")) or None,
        "published": _datetime_to_date(getattr(result, "published", None)),
        "updated": _datetime_to_date(getattr(result, "updated", None)),
        "journal_title": "arXiv",
        "publisher": "arXiv",
        "landing_page_url": canonical_arxiv_abs_url(arxiv_id),
        "arxiv_id": arxiv_id,
        "primary_category": normalize_text(getattr(result, "primary_category", ""))
        or None,
        "categories": categories,
        "keywords": categories,
        "license_urls": [],
        "references": [],
        "pdf_url": pdf_url,
        "html_url": canonical_arxiv_html_url(arxiv_id),
        "fulltext_links": [
            {
                "url": canonical_arxiv_html_url(arxiv_id),
                "content_type": "text/html",
                "content_version": arxiv_id,
                "intended_application": "full_text",
            },
            {
                "url": pdf_url,
                "content_type": PDF_MIME_TYPE,
                "content_version": arxiv_id,
                "intended_application": "full_text",
            },
        ],
    }
    return metadata


def _arxiv_id_from_metadata_or_doi(doi: str | None, metadata: Mapping[str, Any]) -> str:
    return (
        normalize_arxiv_id(str(metadata.get("arxiv_id") or ""))
        or arxiv_id_from_doi(str(metadata.get("doi") or ""))
        or arxiv_id_from_doi(doi)
        or arxiv_id_from_query(str(metadata.get("landing_page_url") or ""))
        or arxiv_id_from_query(str(metadata.get("html_url") or ""))
        or arxiv_id_from_query(str(metadata.get("pdf_url") or ""))
        or arxiv_id_from_query(str(metadata.get("url") or ""))
        or arxiv_id_from_query(str(metadata.get("entry_id") or ""))
    )


def _default_arxiv_fulltext_links(arxiv_id: str, pdf_url: str) -> list[dict[str, Any]]:
    return [
        {
            "url": canonical_arxiv_html_url(arxiv_id),
            "content_type": "text/html",
            "content_version": arxiv_id,
            "intended_application": "full_text",
        },
        {
            "url": pdf_url,
            "content_type": PDF_MIME_TYPE,
            "content_version": arxiv_id,
            "intended_application": "full_text",
        },
    ]


def _minimal_arxiv_metadata(
    arxiv_id: str,
    *,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> ProviderMetadata:
    pdf_url = canonical_arxiv_pdf_url(arxiv_id)
    merged: dict[str, Any] = dict(metadata or {})
    merged.pop("source_url", None)
    merged.update(
        {
            "provider": "arxiv",
            "official_provider": True,
            "doi": canonical_arxiv_doi(arxiv_id)
            or normalize_text(doi)
            or normalize_text(metadata.get("doi"))
            or None,
            "journal_title": normalize_text(metadata.get("journal_title")) or "arXiv",
            "publisher": normalize_text(metadata.get("publisher")) or "arXiv",
            "landing_page_url": canonical_arxiv_abs_url(arxiv_id),
            "arxiv_id": arxiv_id,
            "pdf_url": pdf_url,
            "html_url": canonical_arxiv_html_url(arxiv_id),
        }
    )
    merged.setdefault("title", normalize_text(metadata.get("title")) or None)
    merged.setdefault("abstract", normalize_text(metadata.get("abstract")) or None)
    merged.setdefault("authors", list(metadata.get("authors") or []))
    merged.setdefault("keywords", list(metadata.get("keywords") or []))
    merged.setdefault("license_urls", list(metadata.get("license_urls") or []))
    merged.setdefault("references", list(metadata.get("references") or []))
    merged["fulltext_links"] = _default_arxiv_fulltext_links(arxiv_id, pdf_url)
    return merged


def minimal_arxiv_metadata(
    arxiv_id: str,
    *,
    doi: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ProviderMetadata:
    """Build route metadata that is sufficient to fetch arXiv HTML/PDF."""

    normalized = normalize_arxiv_id(arxiv_id)
    if not normalized:
        raise ProviderFailure(NOT_SUPPORTED, "A valid arXiv ID is required.")
    return _minimal_arxiv_metadata(normalized, doi=doi, metadata=metadata or {})


def arxiv_metadata_probe_short_circuit(doi: str) -> ProviderMetadata | None:
    arxiv_id = arxiv_id_from_doi(doi)
    if not arxiv_id:
        return None
    return minimal_arxiv_metadata(arxiv_id, doi=doi, metadata={})


register_metadata_probe_short_circuit("arxiv", arxiv_metadata_probe_short_circuit)


def _arxiv_date_to_iso(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if not normalized:
        return None
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue
    return normalized


def _extract_arxiv_watermark_metadata(root: Any) -> dict[str, Any]:
    if not isinstance(root, Tag):
        return {}
    candidates = []
    for selector in _arxiv_ar5iv_selectors("watermark"):
        candidates.extend(root.select(selector))
    candidates.append(root)
    for node in candidates:
        text = normalize_text(
            node.get_text(" ", strip=True) if isinstance(node, Tag) else ""
        )
        match = _ARXIV_WATERMARK_PATTERN.search(text)
        if match is None:
            continue
        arxiv_id = normalize_arxiv_id(match.group("arxiv_id"))
        if not arxiv_id:
            continue
        primary_category = normalize_text(match.group("category"))
        return {
            "arxiv_id": arxiv_id,
            "primary_category": primary_category or None,
            "published": _arxiv_date_to_iso(match.group("date")),
        }
    return {}


def _arxiv_node_identity_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(getattr(node, "name", "") or "")]
    for key in ("id", "aria-label", "aria-labelledby", "data-title"):
        parts.append(normalize_text(str(attrs.get(key) or "")))
    class_values = attrs.get("class")
    if isinstance(class_values, (list, tuple, set)):
        parts.extend(normalize_text(str(item)) for item in class_values)
    else:
        parts.append(normalize_text(str(class_values or "")))
    return " ".join(part.lower() for part in parts if part)


def _select_arxiv_title_node(article: Any) -> Any:
    title_node = _arxiv_select_one(article, "document_title")
    if isinstance(title_node, Tag):
        return title_node
    return article.find("h1") if isinstance(article, Tag) else None


def _select_arxiv_abstract_node(article: Any) -> Any:
    abstract_node = _arxiv_select_one(article, "abstract")
    if isinstance(abstract_node, Tag):
        return abstract_node
    if not isinstance(article, Tag):
        return None
    for candidate in article.find_all(["section", "div"]):
        if not isinstance(candidate, Tag):
            continue
        identity = _arxiv_node_identity_text(candidate)
        heading_node = candidate.find(SECTION_HEADING_PATTERN)
        title = normalize_text(
            render_heading_text_from_html(heading_node)
            if isinstance(heading_node, Tag)
            else ""
        ).lower()
        if "abstract" in identity or title.strip(" .:") == "abstract":
            return candidate
    return None


def _extract_arxiv_html_frontmatter(
    soup: Any,
    article: Any,
    source_url: str,
    *,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(article, Tag):
        return {}
    arxiv_id = _arxiv_id_from_metadata_or_doi(
        str(metadata.get("doi") or ""), metadata
    ) or arxiv_id_from_query(source_url)
    watermark_metadata = _extract_arxiv_watermark_metadata(soup)
    arxiv_id = normalize_arxiv_id(watermark_metadata.get("arxiv_id")) or arxiv_id

    title_node = _select_arxiv_title_node(article)
    title = (
        _clean_arxiv_frontmatter_text(title_node) if isinstance(title_node, Tag) else ""
    )
    abstract_node = _select_arxiv_abstract_node(article)
    abstract = ""
    if isinstance(abstract_node, Tag):
        abstract_clone = copy.deepcopy(abstract_node)
        if isinstance(abstract_clone, Tag):
            for heading_selector in _arxiv_ar5iv_selectors("abstract_heading"):
                for heading in abstract_clone.select(heading_selector):
                    heading.decompose()
            for heading in abstract_clone.find_all(SECTION_HEADING_PATTERN):
                heading.decompose()
            abstract = _clean_arxiv_frontmatter_text(abstract_clone)

    html_metadata: dict[str, Any] = {
        "provider": "arxiv",
        "official_provider": True,
        "journal_title": "arXiv",
        "publisher": "arXiv",
    }
    if arxiv_id:
        html_metadata.update(
            {
                "doi": canonical_arxiv_doi(arxiv_id),
                "arxiv_id": arxiv_id,
                "landing_page_url": canonical_arxiv_abs_url(arxiv_id),
                "html_url": canonical_arxiv_html_url(arxiv_id),
                "pdf_url": canonical_arxiv_pdf_url(arxiv_id),
                "fulltext_links": _default_arxiv_fulltext_links(
                    arxiv_id, canonical_arxiv_pdf_url(arxiv_id)
                ),
            }
        )
    if title:
        html_metadata["title"] = title
    authors = _AUTHOR_PIPELINE(str(article))
    if authors:
        html_metadata["authors"] = authors
    if abstract:
        html_metadata["abstract"] = abstract
    if watermark_metadata.get("published"):
        html_metadata["published"] = watermark_metadata["published"]
    if watermark_metadata.get("primary_category"):
        html_metadata["primary_category"] = watermark_metadata["primary_category"]
        html_metadata["categories"] = [watermark_metadata["primary_category"]]
        html_metadata["keywords"] = [watermark_metadata["primary_category"]]
    html_metadata.pop("source_url", None)
    return html_metadata


def _merge_arxiv_metadata_layers(
    derived_metadata: Mapping[str, Any],
    *,
    html_metadata: Mapping[str, Any] | None = None,
    api_metadata: Mapping[str, Any] | None = None,
    references: Sequence[Mapping[str, Any]] | None = None,
) -> ProviderMetadata:
    merged = merge_metadata_layers(
        [
            _mergeable_arxiv_layer(derived_metadata),
            _mergeable_arxiv_layer(html_metadata),
        ],
        rule=_ARXIV_APPEND_MERGE_RULE,
    )
    merged = merge_metadata_layers(
        [merged, _mergeable_arxiv_layer(api_metadata)],
        rule=_ARXIV_API_MERGE_RULE,
    )

    arxiv_id = normalize_arxiv_id(str(merged.get("arxiv_id") or ""))
    if arxiv_id:
        merged["doi"] = canonical_arxiv_doi(arxiv_id)
        merged["landing_page_url"] = canonical_arxiv_abs_url(arxiv_id)
        merged["html_url"] = canonical_arxiv_html_url(arxiv_id)
        merged["pdf_url"] = normalize_text(
            merged.get("pdf_url")
        ) or canonical_arxiv_pdf_url(arxiv_id)
        merged["fulltext_links"] = _default_arxiv_fulltext_links(
            arxiv_id, normalize_text(merged.get("pdf_url"))
        )
    merged["provider"] = "arxiv"
    merged["official_provider"] = True
    merged["journal_title"] = normalize_text(merged.get("journal_title")) or "arXiv"
    merged["publisher"] = normalize_text(merged.get("publisher")) or "arXiv"
    merged["authors"] = dedupe_authors(
        [str(item) for item in (merged.get("authors") or [])]
    )
    merged["keywords"] = _dedupe_metadata_text_values(
        list(merged.get("keywords") or [])
    )
    merged["license_urls"] = _dedupe_metadata_text_values(
        list(merged.get("license_urls") or [])
    )
    if references:
        merged["references"] = [dict(item) for item in references]
    else:
        merged["references"] = list(merged.get("references") or [])
    merged.pop("source_url", None)
    return merged
