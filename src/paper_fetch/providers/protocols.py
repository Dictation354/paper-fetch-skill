"""Structural provider capability protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from collections.abc import Mapping

from ..artifacts import ArtifactStore
from ..http import RequestFailure
from ..models import AssetProfile
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
class SupplementaryProvider(Protocol):
    def fetch_supplementary(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        output_dir: Path | None,
        *,
        context: RuntimeContext,
    ): ...


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
