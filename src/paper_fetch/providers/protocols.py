"""Structural provider capability protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from collections.abc import Mapping

from ..artifacts import ArtifactStore
from ..http import RequestFailure
from ..models import ArticleModel, AssetProfile
from ..metadata.types import ProviderMetadata
from ..runtime import RuntimeContext
from .base import (
    ProviderFailure,
    ProviderFetchResult,
    RawFulltextPayload,
)


@runtime_checkable
class MetadataProvider(Protocol):
    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata: ...


@runtime_checkable
class AssetProvider(Protocol):
    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]: ...

    def asset_download_failure_warning(
        self, exc: ProviderFailure | RequestFailure | OSError
    ) -> str: ...


@runtime_checkable
class RawFulltextProvider(Protocol):
    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload: ...

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ) -> ArticleModel: ...


@runtime_checkable
class FulltextProvider(Protocol):
    def fetch_result(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "none",
        artifact_store: ArtifactStore | None = None,
        context: RuntimeContext | None = None,
    ) -> ProviderFetchResult: ...
