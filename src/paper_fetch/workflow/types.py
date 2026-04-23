"""Shared workflow types and public facade contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import AssetProfile
from ..utils import normalize_text

HTML_BODY_ASSET_DEFAULT_PROVIDERS = frozenset({"springer", "wiley", "science", "pnas"})
HTML_BODY_ASSET_DEFAULT_SOURCES = frozenset({"springer_html", "wiley_browser", "science", "pnas"})
ALLOWED_PREFERRED_PROVIDERS = frozenset({"elsevier", "springer", "wiley", "science", "pnas", "crossref"})


def provider_default_asset_profile(provider_name: str | None) -> AssetProfile:
    normalized = normalize_text(provider_name).lower()
    if normalized in HTML_BODY_ASSET_DEFAULT_PROVIDERS:
        return "body"
    return "none"


def source_default_asset_profile(source_name: str | None) -> AssetProfile:
    normalized = normalize_text(source_name).lower()
    if normalized in HTML_BODY_ASSET_DEFAULT_SOURCES:
        return "body"
    return "none"


def effective_asset_profile(
    asset_profile: AssetProfile | None,
    *,
    provider_name: str | None = None,
    source_name: str | None = None,
) -> AssetProfile:
    if asset_profile is not None:
        return asset_profile
    if provider_name is not None:
        return provider_default_asset_profile(provider_name)
    return source_default_asset_profile(source_name)


class PaperFetchFailure(Exception):
    def __init__(self, status: str, reason: str, *, candidates: list[dict[str, Any]] | None = None) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.candidates = list(candidates or [])


@dataclass(frozen=True)
class RouteProbeResult:
    provider: str
    state: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class HasFulltextProbeResult:
    query: str
    doi: str | None
    title: str | None
    state: str
    evidence: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "doi": self.doi,
            "title": self.title,
            "state": self.state,
            "evidence": list(self.evidence),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class FetchStrategy:
    allow_metadata_only_fallback: bool = True
    preferred_providers: list[str] | None = None
    asset_profile: AssetProfile | None = None

    def __post_init__(self) -> None:
        normalized = self.normalized_preferred_providers()
        if normalized is None:
            return
        invalid = sorted(normalized - ALLOWED_PREFERRED_PROVIDERS)
        if invalid:
            raise ValueError(
                "unsupported preferred_providers values: "
                + ", ".join(invalid)
                + ". Expected one or more of: "
                + ", ".join(sorted(ALLOWED_PREFERRED_PROVIDERS))
                + "."
            )

    def normalized_preferred_providers(self) -> set[str] | None:
        if self.preferred_providers is None:
            return None
        normalized = {normalize_text(item).lower() for item in self.preferred_providers if normalize_text(item)}
        return normalized or set()

    def effective_asset_profile_for_provider(self, provider_name: str | None) -> AssetProfile:
        return effective_asset_profile(self.asset_profile, provider_name=provider_name)

    def effective_asset_profile_for_source(self, source_name: str | None) -> AssetProfile:
        return effective_asset_profile(self.asset_profile, source_name=source_name)
