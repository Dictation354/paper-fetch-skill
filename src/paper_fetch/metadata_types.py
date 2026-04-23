"""Internal metadata type definitions for provider payloads."""

from __future__ import annotations

from typing_extensions import TypedDict


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
