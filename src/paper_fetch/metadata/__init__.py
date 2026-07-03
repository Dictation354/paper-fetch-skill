"""Metadata lookup clients and payload schemas shared by provider adapters."""

from __future__ import annotations

from .types import (
    CrossrefMetadata,
    FulltextLink,
    HtmlLookupHints,
    HtmlMetadata,
    MetadataMergeRule,
    PRIMARY_SECONDARY_METADATA_MERGE_RULE,
    ProviderMetadata,
    ReferenceMetadata,
    merge_primary_secondary_metadata,
    merge_metadata_layers,
)


def __getattr__(name: str):
    if name == "CrossrefLookupClient":
        from .crossref import CrossrefLookupClient

        return CrossrefLookupClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PRIMARY_SECONDARY_METADATA_MERGE_RULE",
    "CrossrefLookupClient",
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
