"""Structural provider capability protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from ..artifacts import ArtifactStore
from ..http import RequestFailure
from ..models import ArticleModel, AssetProfile
from .base import (
    ProviderFailure,
    ProviderFetchResult,
    ProviderStatusResult,
    RawFulltextPayload,
)


@runtime_checkable
class MetadataProvider(Protocol):
    name: str

    def fetch_metadata(self, query: Mapping[str, str | None]) -> dict[str, Any]:
        ...


@runtime_checkable
class StatusProvider(Protocol):
    name: str
    official_provider: bool

    def probe_status(self) -> ProviderStatusResult:
        ...


@runtime_checkable
class AssetProvider(Protocol):
    name: str

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
    ) -> dict[str, list[dict[str, Any]]]:
        ...

    def asset_download_failure_warning(self, exc: ProviderFailure | RequestFailure | OSError) -> str:
        ...


@runtime_checkable
class RawFulltextProvider(AssetProvider, Protocol):
    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, Any]) -> RawFulltextPayload:
        ...

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ArticleModel:
        ...


@runtime_checkable
class FulltextProvider(Protocol):
    name: str

    def fetch_result(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "none",
        artifact_store: ArtifactStore | None = None,
    ) -> ProviderFetchResult:
        ...
