"""Typed metadata payload schemas shared by metadata and provider adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from typing_extensions import TypedDict

from ..utils import (
    canonical_author_key,
    choose_public_landing_page_url,
    dedupe_authors,
    normalize_text,
    safe_text,
)


class FulltextLink(TypedDict, total=False):
    url: str
    content_type: str | None
    content_version: str | None
    intended_application: str | None


class ReferenceMetadata(TypedDict, total=False):
    label: str | None
    raw: str
    doi: str | None
    title: str | None
    year: str | None


class ProviderMetadata(TypedDict, total=False):
    status: str
    provider: str
    official_provider: bool
    source_url: str
    doi: str | None
    pii: str | None
    provider_identifiers: dict[str, str]
    title: str | None
    journal_title: str | None
    publisher: str | None
    article_type: str | None
    authors: list[str]
    keywords: list[str]
    abstract: str | None
    published: str | None
    landing_page_url: str | None
    citation_fulltext_html_url: str | None
    citation_abstract_html_url: str | None
    license_urls: list[str]
    fulltext_links: list[FulltextLink]
    references: list[ReferenceMetadata]


class CrossrefMetadata(ProviderMetadata, total=False):
    pass


class HtmlLookupHints(TypedDict, total=False):
    lookup_title: str | None
    redirect_url: str | None
    identifier_value: str | None


class HtmlMetadata(ProviderMetadata, total=False):
    raw_meta: dict[str, list[str]]
    lookup_title: str | None
    lookup_redirect_url: str | None
    identifier_value: str | None


@dataclass(frozen=True)
class MetadataMergeRule:
    """Field-level merge behavior for ordered provider metadata layers."""

    fill_empty: tuple[str, ...] = ()
    overwrite: tuple[str, ...] = ()
    concat_unique: tuple[str, ...] = ()
    take_first_non_empty: tuple[str, ...] = ()
    scalarize: tuple[str, ...] = ()
    blank_primary_blocks_secondary: tuple[str, ...] = ()


def _metadata_value_is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _metadata_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        values = list(value)
    elif isinstance(value, tuple):
        values = list(value)
    else:
        values = [value]
    return [item for item in values if not _metadata_value_is_empty(item)]


def _metadata_explicit_blank(value: Any) -> bool:
    if isinstance(value, str):
        return not normalize_text(value)
    if isinstance(value, list | tuple):
        return bool(value) and not _metadata_values(value)
    if isinstance(value, Mapping):
        return bool(value) and not _metadata_values(value)
    return value is not None and _metadata_value_is_empty(safe_text(value))


def _metadata_scalarize(value: Any, *, preserve_blank: bool = False) -> str | None:
    if isinstance(value, str):
        normalized = normalize_text(value)
        if normalized:
            return normalized
        return "" if preserve_blank else None
    if isinstance(value, list | tuple):
        for item in value:
            scalar = _metadata_scalarize(item, preserve_blank=preserve_blank)
            if scalar is not None:
                return scalar
        return "" if preserve_blank and value else None
    if isinstance(value, Mapping):
        for key in ("value", "url", "URL"):
            scalar = _metadata_scalarize(value.get(key), preserve_blank=preserve_blank)
            if scalar is not None:
                return scalar
        return "" if preserve_blank and value else None
    if value is None:
        return None
    normalized = safe_text(value)
    if normalized:
        return normalized
    return "" if preserve_blank else None


def _metadata_unique_key(field: str, value: Any) -> Any:
    if field == "authors" and isinstance(value, str):
        return ("author", canonical_author_key(value))
    if field == "fulltext_links" and isinstance(value, Mapping):
        url = normalize_text(value.get("url")).lower()
        if url:
            return ("url", url)
    if field == "references" and isinstance(value, Mapping):
        doi = normalize_text(value.get("doi")).lower()
        if doi:
            return ("doi", doi)
        raw = normalize_text(value.get("raw")).lower()
        if raw:
            return ("raw", raw)
    if isinstance(value, str):
        return ("text", normalize_text(value).lower())
    try:
        hash(value)
    except TypeError:
        return ("repr", repr(value))
    return ("value", value)


def _concat_unique_metadata_values(field: str, *groups: Any) -> list[Any]:
    result: list[Any] = []
    seen: set[Any] = set()
    for group in groups:
        for value in _metadata_values(group):
            candidate = normalize_text(value) if isinstance(value, str) else value
            if _metadata_value_is_empty(candidate):
                continue
            key = _metadata_unique_key(field, candidate)
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
    if field == "authors":
        return dedupe_authors([str(item) for item in result])
    return result


def merge_metadata_layers(
    layers: Sequence[Mapping[str, Any] | None],
    *,
    rule: MetadataMergeRule,
) -> dict[str, Any]:
    """Merge layers in order; undeclared fields default to fill-empty behavior."""

    merged: dict[str, Any] = {}
    fill_empty = set(rule.fill_empty)
    overwrite = set(rule.overwrite)
    concat_unique = set(rule.concat_unique)
    take_first_non_empty = set(rule.take_first_non_empty)
    scalarize = set(rule.scalarize)
    blank_blocks = set(rule.blank_primary_blocks_secondary)
    declared = fill_empty | overwrite | concat_unique | take_first_non_empty
    blocked_empty: set[str] = set()

    for layer in layers:
        if not isinstance(layer, Mapping):
            continue
        for key, raw_value in layer.items():
            value = (
                _metadata_scalarize(raw_value, preserve_blank=key in blank_blocks)
                if key in scalarize
                else raw_value
            )
            if _metadata_value_is_empty(value):
                if (
                    key in blank_blocks
                    and key not in merged
                    and raw_value is not None
                    and _metadata_explicit_blank(raw_value)
                ):
                    merged[key] = ""
                    blocked_empty.add(key)
                continue
            if key in blocked_empty:
                continue
            if key in concat_unique:
                merged[key] = _concat_unique_metadata_values(
                    key, merged.get(key), value
                )
                continue
            if key in overwrite:
                merged[key] = value
                continue
            if key in fill_empty or key in take_first_non_empty or key not in declared:
                if _metadata_value_is_empty(merged.get(key)):
                    merged[key] = value
    return merged


_PRIMARY_SECONDARY_SCALAR_KEYS = (
    "doi",
    "title",
    "journal_title",
    "published",
    "abstract",
    "publisher",
)
_PRIMARY_SECONDARY_LIST_KEYS = (
    "authors",
    "keywords",
    "license_urls",
    "fulltext_links",
    "references",
)
PRIMARY_SECONDARY_METADATA_MERGE_RULE = MetadataMergeRule(
    fill_empty=_PRIMARY_SECONDARY_SCALAR_KEYS,
    concat_unique=_PRIMARY_SECONDARY_LIST_KEYS,
    scalarize=_PRIMARY_SECONDARY_SCALAR_KEYS,
    blank_primary_blocks_secondary=_PRIMARY_SECONDARY_SCALAR_KEYS,
)


def merge_primary_secondary_metadata(
    primary: Mapping[str, Any] | None,
    secondary: Mapping[str, Any] | None,
) -> ProviderMetadata:
    """Merge provider metadata over Crossref metadata using one rule table."""

    merged = dict(secondary or {})
    merged.update(primary or {})
    merged.update(
        merge_metadata_layers(
            [primary, secondary],
            rule=PRIMARY_SECONDARY_METADATA_MERGE_RULE,
        )
    )
    merged["landing_page_url"] = choose_public_landing_page_url(
        (primary or {}).get("landing_page_url"),
        (secondary or {}).get("landing_page_url"),
    )
    for key in _PRIMARY_SECONDARY_SCALAR_KEYS:
        if merged.get(key) == "":
            merged[key] = None
        else:
            merged.setdefault(key, None)
    for key in _PRIMARY_SECONDARY_LIST_KEYS:
        if not isinstance(merged.get(key), list):
            merged[key] = []
    return cast(ProviderMetadata, merged)


__all__ = [
    "PRIMARY_SECONDARY_METADATA_MERGE_RULE",
    "CrossrefMetadata",
    "FulltextLink",
    "HtmlLookupHints",
    "HtmlMetadata",
    "MetadataMergeRule",
    "ProviderMetadata",
    "ReferenceMetadata",
    "merge_metadata_layers",
    "merge_primary_secondary_metadata",
]
