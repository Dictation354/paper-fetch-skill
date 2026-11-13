"""Shared workflow types and public facade contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..failure import FailureDiagnostics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..providers.base import ProviderFailure
from ..metadata.types import ProviderMetadata
from ..models import AssetProfile
from ..provider_catalog import (
    default_asset_profile_for_source,
    effective_route_asset_scope,
    provider_names,
)
from ..tracing import TraceEvent
from ..utils import normalize_text


def allowed_preferred_providers() -> frozenset[str]:
    return frozenset(provider_names())


def source_default_asset_profile(source_name: str | None) -> AssetProfile:
    normalized = normalize_text(source_name).lower()
    return default_asset_profile_for_source(normalized)


def effective_asset_profile(
    asset_profile: AssetProfile | None,
    *,
    provider_name: str | None = None,
    source_name: str | None = None,
    route_name: str | None = None,
) -> AssetProfile:
    if asset_profile is not None:
        return asset_profile
    if provider_name is not None:
        return effective_route_asset_scope(
            None,
            provider_name=provider_name,
            route_name=route_name,
        )
    return source_default_asset_profile(source_name)


class PaperFetchFailure(Exception):
    def __init__(
        self,
        status: str,
        reason: str,
        *,
        candidates: list[dict[str, Any]] | None = None,
        retry_after_seconds: int | None = None,
        warnings: list[str] | None = None,
        trace: list[TraceEvent] | None = None,
        missing_env: list[str] | None = None,
        diagnostics: FailureDiagnostics | None = None,
        doi: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.doi = doi
        self.status = status
        self.reason = reason
        self.candidates = list(candidates or [])
        self.retry_after_seconds = retry_after_seconds
        self.warnings = [str(item) for item in (warnings or [])]
        self.trace = list(trace or [])
        self.missing_env = [str(item) for item in (missing_env or [])]
        self.diagnostics = diagnostics or FailureDiagnostics()

    @classmethod
    def from_provider_failure(
        cls,
        failure: ProviderFailure,
        *,
        candidates: list[dict[str, Any]] | None = None,
    ) -> PaperFetchFailure:
        return cls(
            failure.code,
            failure.message,
            candidates=candidates,
            retry_after_seconds=failure.retry_after_seconds,
            warnings=failure.warnings,
            trace=failure.trace,
            missing_env=failure.missing_env,
            diagnostics=failure.diagnostics,
        )


@dataclass(frozen=True)
class RouteProbeResult:
    provider: str
    state: str
    metadata: ProviderMetadata | None = None


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
    require_local_body_assets: bool = False
    require_full_size_body_assets: bool = False

    def __post_init__(self) -> None:
        if self.require_full_size_body_assets and not self.require_local_body_assets:
            object.__setattr__(self, "require_local_body_assets", True)
        normalized = self.normalized_preferred_providers()
        if normalized is None:
            return
        allowed = allowed_preferred_providers()
        invalid = sorted(normalized - allowed)
        if invalid:
            raise ValueError(
                "unsupported preferred_providers values: "
                + ", ".join(invalid)
                + ". Expected one or more of: "
                + ", ".join(sorted(allowed))
                + "."
            )

    def normalized_preferred_providers(self) -> set[str] | None:
        if self.preferred_providers is None:
            return None
        normalized = {
            normalize_text(item).lower()
            for item in self.preferred_providers
            if normalize_text(item)
        }
        return normalized or set()

    def effective_asset_profile_for_provider(
        self, provider_name: str | None
    ) -> AssetProfile:
        return effective_asset_profile(self.asset_profile, provider_name=provider_name)
