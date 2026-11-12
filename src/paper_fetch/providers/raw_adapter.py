"""Explicit compatibility adapter for structural raw-only providers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..models import ArticleModel, AssetProfile
from ..runtime import RuntimeContext
from ..reason_codes import PDF_FALLBACK
from ..utils import safe_text
from .base import ProviderArtifacts, ProviderClient, RawFulltextPayload
from .protocols import AssetProvider, RawFulltextProvider
from ._result import ResultAssemblyPolicy


class RawProviderAdapter(ProviderClient):
    """Preserve the raw protocol's assembly calls and exception propagation."""

    def __init__(self, provider: RawFulltextProvider) -> None:
        self.provider = provider
        self.name = safe_text(getattr(provider, "name", "")) or "provider"

    def result_assembly_policy(self) -> ResultAssemblyPolicy:
        return ResultAssemblyPolicy(
            asset_errors_to_warnings=False,
            asset_budget_scope=False,
            reassemble_after_asset_attempt=True,
            derive_trace_from_article=False,
            restricted_result=False,
            snapshot_results_before_assets=False,
        )

    def result_provider_name(self, raw_payload: RawFulltextPayload) -> str:
        return (
            safe_text(getattr(self.provider, "name", ""))
            or safe_text(raw_payload.provider)
            or "provider"
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        return self.provider.fetch_raw_fulltext(doi, metadata, context=context)

    def ensure_html_markdown(
        self,
        raw_payload: RawFulltextPayload,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext,
    ) -> RawFulltextPayload:
        return raw_payload

    def validate_raw_payload_identity(
        self, doi: str, metadata: Mapping[str, Any], raw_payload: RawFulltextPayload
    ) -> RawFulltextPayload:
        return raw_payload

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ) -> ArticleModel:
        return self.provider.to_article_model(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets or [],
            asset_failures=asset_failures or [],
            context=context,
        )

    def should_download_related_assets_for_result(
        self,
        raw_payload: RawFulltextPayload,
        *,
        provisional_article: ArticleModel | None = None,
    ) -> bool:
        return isinstance(self.provider, AssetProvider)

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        assert isinstance(self.provider, AssetProvider)
        return self.provider.download_related_assets(
            doi,
            metadata,
            raw_payload,
            output_dir,
            asset_profile=asset_profile,
            context=context,
        )

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        content = raw_payload.content
        extracted = (
            list(content.extracted_assets or [])
            if safe_text(content.route_kind).lower() == PDF_FALLBACK
            else []
        )
        return ProviderArtifacts(
            assets=[dict(item) for item in [*extracted, *(downloaded_assets or [])]],
            asset_failures=[dict(item) for item in (asset_failures or [])],
        )
