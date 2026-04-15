"""Typed MCP tool output schemas used for FastMCP structured output."""

from __future__ import annotations

from typing_extensions import TypedDict


class ResolvedCandidateOutput(TypedDict, total=False):
    doi: str | None
    title: str | None
    journal_title: str | None
    published: str | None
    landing_page_url: str | None
    provider_hint: str | None
    score: float


class ErrorPayloadOutput(TypedDict, total=False):
    status: str
    reason: str
    candidates: list[ResolvedCandidateOutput] | None
    missing_env: list[str] | None


class ResolvePaperOutput(ErrorPayloadOutput, total=False):
    query: str
    query_kind: str
    doi: str | None
    landing_url: str | None
    provider_hint: str | None
    confidence: float
    candidates: list[ResolvedCandidateOutput]
    title: str | None


class HasFulltextOutput(ErrorPayloadOutput, total=False):
    query: str
    doi: str | None
    state: str
    evidence: list[str]
    warnings: list[str]


class MetadataOutput(TypedDict, total=False):
    title: str | None
    authors: list[str]
    abstract: str | None
    journal: str | None
    published: str | None
    keywords: list[str]
    license_urls: list[str]
    landing_page_url: str | None


class SectionOutput(TypedDict, total=False):
    heading: str
    level: int
    kind: str
    text: str


class ReferenceOutput(TypedDict, total=False):
    raw: str
    doi: str | None
    title: str | None
    year: str | None


class AssetOutput(TypedDict, total=False):
    kind: str
    heading: str
    caption: str | None
    url: str | None
    path: str | None
    section: str | None


class TokenEstimateBreakdownOutput(TypedDict, total=False):
    abstract: int
    body: int
    refs: int


class QualityOutput(TypedDict, total=False):
    has_fulltext: bool
    token_estimate: int
    token_estimate_breakdown: TokenEstimateBreakdownOutput
    warnings: list[str]
    source_trail: list[str]


class ArticleOutput(TypedDict, total=False):
    doi: str | None
    source: str
    metadata: MetadataOutput
    sections: list[SectionOutput]
    references: list[ReferenceOutput]
    assets: list[AssetOutput]
    quality: QualityOutput


class FetchPaperOutput(ErrorPayloadOutput, total=False):
    doi: str | None
    source: str
    has_fulltext: bool
    warnings: list[str]
    source_trail: list[str]
    token_estimate: int
    token_estimate_breakdown: TokenEstimateBreakdownOutput
    article: ArticleOutput | None
    markdown: str | None
    metadata: MetadataOutput | None


class CacheEntryOutput(TypedDict, total=False):
    id: str
    doi: str
    kind: str
    path: str
    mime: str
    size: int
    mtime: float


class PreferredCacheEntriesOutput(TypedDict, total=False):
    markdown: CacheEntryOutput | None
    primary_payload: CacheEntryOutput | None
    assets: list[CacheEntryOutput]


class ListCachedOutput(ErrorPayloadOutput, total=False):
    download_dir: str | None
    entries: list[CacheEntryOutput]


class GetCachedOutput(ErrorPayloadOutput, total=False):
    status: str
    doi: str
    download_dir: str | None
    entries: list[CacheEntryOutput]
    preferred: PreferredCacheEntriesOutput


class BatchResolveOutput(ErrorPayloadOutput, total=False):
    results: list[ResolvePaperOutput]
    aborted: bool
    abort_reason: ErrorPayloadOutput | None


class BatchCheckItemOutput(ErrorPayloadOutput, total=False):
    query: str
    doi: str | None
    title: str | None
    source: str | None
    has_fulltext: bool | None
    warnings: list[str]
    source_trail: list[str]
    token_estimate: int | None
    token_estimate_breakdown: TokenEstimateBreakdownOutput | None
    probe_state: str | None
    evidence: list[str]


class BatchCheckOutput(ErrorPayloadOutput, total=False):
    mode: str
    results: list[BatchCheckItemOutput]
    aborted: bool
    abort_reason: ErrorPayloadOutput | None
