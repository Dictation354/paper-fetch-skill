"""The single provider result assembly transaction."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..artifacts import ArtifactStore
from ..asset_budget import use_asset_budget
from ..http import RequestFailure
from ..models import AssetProfile
from ..quality.access_boundary import check_payload_paywall, confirmed_paywall
from ..runtime import RuntimeContext
from ..tracing import download_event
from .base import (
    ProviderClient,
    ProviderFailure,
    ProviderFetchResult,
    restricted_provider_result,
)


@dataclass(frozen=True)
class ResultAssemblyPolicy:
    asset_errors_to_warnings: bool = True
    asset_budget_scope: bool = True
    reassemble_after_asset_attempt: bool = False
    derive_trace_from_article: bool = True
    restricted_result: bool = True
    snapshot_results_before_assets: bool = True


def assemble_provider_result(
    client: ProviderClient,
    doi: str,
    metadata: Mapping[str, Any],
    output_dir: Path | None,
    *,
    asset_profile: AssetProfile = "none",
    artifact_store: ArtifactStore | None = None,
    context: RuntimeContext | None = None,
) -> ProviderFetchResult:
    owns_context = context is None
    context = client._runtime_context(context, output_dir=output_dir)
    active_artifact_store = artifact_store or ArtifactStore.from_download_dir(
        output_dir, commit_guard=context.commit_guard
    )
    assert active_artifact_store is not None
    policy = client.result_assembly_policy()
    asset_output_dir = active_artifact_store.asset_download_dir
    previous_asset_profile = context.asset_profile
    previous_artifact_store = context.artifact_store
    context.asset_profile = asset_profile
    context.artifact_store = active_artifact_store
    try:
        prepared = client.prepare_fetch_result_payload(
            doi, metadata, asset_profile=asset_profile, context=context
        )
        checked_input = check_payload_paywall(
            prepared.raw_payload, {**metadata, "doi": doi}, context=context
        )
        prepared = client.maybe_recover_fetch_result_payload(
            doi,
            metadata,
            prepared,
            asset_profile=asset_profile,
            context=context,
        )
        prepared.raw_payload = client.ensure_html_markdown(
            prepared.raw_payload, metadata, context=context
        )
        prepared.raw_payload = client.validate_raw_payload_identity(
            doi, metadata, prepared.raw_payload
        )
        raw_payload = prepared.raw_payload
        checked_input = check_payload_paywall(
            raw_payload,
            {**metadata, "doi": doi},
            context=context,
            checked_input=checked_input,
        )
        # Assembly can expose an access restriction absent from the initial payload.
        if prepared.provisional_article is None:
            prepared.provisional_article = client.to_article_model(
                metadata, raw_payload, context=context
            )
        checked_input = check_payload_paywall(
            raw_payload,
            {**metadata, "doi": doi},
            context=context,
            checked_input=checked_input,
        )
        assembled_content = raw_payload.content
        artifact_policy = client.describe_artifacts(raw_payload)
        asset_attempted = False
        downloaded_assets: list[Mapping[str, Any]] = []
        asset_failures: list[Mapping[str, Any]] = []
        warnings = list(
            prepared.result_warnings
            if prepared.result_warnings is not None
            else raw_payload.warnings
        )
        trace = list(
            prepared.result_trace
            if prepared.result_trace is not None
            else raw_payload.trace
        )
        if (
            asset_output_dir is not None
            and asset_profile != "none"
            and artifact_policy.allow_related_assets
            and client.should_download_related_assets_for_result(
                raw_payload,
                provisional_article=prepared.provisional_article,
            )
        ):
            asset_attempted = True
            try:
                with (
                    use_asset_budget(context.asset_budget)
                    if policy.asset_budget_scope
                    else nullcontext()
                ):
                    asset_results = client.download_related_assets(
                        doi,
                        metadata,
                        raw_payload,
                        asset_output_dir,
                        asset_profile=asset_profile,
                        context=context,
                    )
                downloaded_assets = list(asset_results.get("assets") or [])
                asset_failures = list(asset_results.get("asset_failures") or [])
            except ProviderFailure as exc:
                if not policy.asset_errors_to_warnings:
                    raise
                warnings.append(client.asset_download_failure_warning(exc))
                trace.extend([download_event(f"{client.name}_assets_failed")])
            except (RequestFailure, OSError) as exc:
                if not policy.asset_errors_to_warnings:
                    raise
                warnings.append(client.asset_download_failure_warning(exc))
                trace.extend([download_event(f"{client.name}_assets_failed")])
        if (
            prepared.provisional_article is not None
            and raw_payload.content is assembled_content
            and not downloaded_assets
            and not asset_failures
            and not (asset_attempted and policy.reassemble_after_asset_attempt)
        ):
            article = prepared.provisional_article
        else:
            article = client.to_article_model(
                metadata,
                raw_payload,
                downloaded_assets=downloaded_assets,
                asset_failures=asset_failures,
                context=context,
            )
        article = client.finalize_fetch_result_article(
            article,
            raw_payload=raw_payload,
            provisional_article=prepared.provisional_article,
            finalize_warnings=prepared.finalize_warnings,
        )
        artifacts = client.describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        if not policy.snapshot_results_before_assets:
            warnings = list(raw_payload.warnings)
            trace = list(raw_payload.trace)
        return ProviderFetchResult(
            provider=client.result_provider_name(raw_payload),
            article=article,
            content=raw_payload.content,
            warnings=warnings,
            trace=list(
                trace or (article.trace if policy.derive_trace_from_article else [])
            ),
            artifacts=artifacts,
        )
    except ProviderFailure as exc:
        if not policy.restricted_result or not confirmed_paywall(exc):
            raise
        return restricted_provider_result(client.name, {**metadata, "doi": doi}, exc)
    finally:
        context.asset_profile = previous_asset_profile
        context.artifact_store = previous_artifact_store
        if owns_context:
            context.close()
