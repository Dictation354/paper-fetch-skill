"""Structured MCP batch-fetch adapter over shared runner and manifest owners."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import ExitStack, nullcontext
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
import threading
from typing import Any, cast
from uuid import UUID

from mcp.server.mcpserver import Context
from mcp.types import CallToolResult

from ..artifacts import ArtifactMode
from ..config import apply_browser_auto_prepare_policy
from ..manifest import (
    DEFAULT_MANIFEST_BUILDER_DEPENDENCIES,
    LegacyArtifactField,
    ManifestBuilderDependencies,
    ManifestOutputArtifactSpec,
    ManifestRecord,
    ManifestRecordStatus,
    build_manifest_record,
)
from ..manifest_writer import (
    ManifestJsonlWriter,
    ManifestPersistenceError,
    RunManifest,
    RunManifestState,
    RunManifestStore,
    deterministic_manifest_record_id,
    latest_manifest_records,
)
from ..models import (
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    AssetProfile,
    FetchEnvelope,
)
from ..runtime import RuntimeContext
from ..reason_codes import RATE_LIMITED
from ..workflow.batch_runner import (
    BatchCompletionEvent,
    BatchFailure,
    BatchItemResult,
    BatchItemStatus,
    BatchProgress,
    BatchRunResult,
    run_batch_async,
)
from ..workflow.batch_lifecycle import (
    BatchLifecycleOverwriteError,
    BatchManifestJournal,
    prepare_batch_run,
)
from ..workflow.types import effective_asset_profile
from ..workflow.batch_routing import (
    initial_provider_lane,
    provider_lane_limit,
    resolve_provider_lane,
)
from ._deps import MCPDeps, default_mcp_deps
from .acceptance_payloads import (
    compact_acceptance_payload,
    expected_doi_from_query,
)
from .batch import _mcp_batch_failure, report_progress
from .cache_index import (
    cache_scope_id,
    cached_resource_uri,
    scoped_cached_resource_uri,
)
from .cache_payloads import (
    _MCP_DEFAULT_DOWNLOAD_DIR,
    _resolve_download_dir,
)
from .fetch_tool import (
    SavedMarkdownResult,
    _call_service_resolve_paper,
    _markdown_output_dir_for_fetch_request,
    _save_markdown_result_for_fetch_request,
)
from .log_bridge import PaperFetchLogBridge
from .provider_catalog import runtime_tool_version
from .results import _tool_result, error_payload_from_exception, with_schema_version
from .schemas import BatchFetchRequest, FetchStrategyInput


@dataclass(frozen=True, slots=True)
class BatchFetchItem:
    index: int
    query: str
    lane_key: str
    attempt: int = 1


@dataclass(frozen=True, slots=True)
class BatchFetchOutcome:
    started_at: datetime
    completed_at: datetime
    envelope: FetchEnvelope | None = None
    saved_markdown: SavedMarkdownResult | None = None
    error: Exception | None = None
    diagnostic_artifacts: tuple[dict[str, Any], ...] = ()


def _expected_doi(query: str) -> str | None:
    return expected_doi_from_query(query)


def _lane_for_query(query: str) -> str:
    return initial_provider_lane(query)


def _resolve_batch_item_lane(
    item: BatchFetchItem,
    *,
    context: RuntimeContext,
    deps: MCPDeps,
) -> BatchFetchItem:
    try:
        lane_key = resolve_provider_lane(
            item.query,
            initial_lane=item.lane_key,
            context=context,
            resolver=lambda query, *, context: _call_service_resolve_paper(
                query,
                context=context,
                deps=deps,
            ),
        )
    except Exception:
        # The fetch attempt remains the owner of resolution errors and diagnostics.
        return item
    return replace(item, lane_key=lane_key)


async def _resolve_batch_item_lanes(
    items: Sequence[BatchFetchItem],
    *,
    contexts: Mapping[int, RuntimeContext],
    concurrency: int,
    deps: MCPDeps,
) -> list[BatchFetchItem]:
    """Resolve generic inputs before scheduling and retain item-local cache state."""

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def resolve_one(item: BatchFetchItem) -> BatchFetchItem:
        async with semaphore:
            return await asyncio.to_thread(
                _resolve_batch_item_lane,
                item,
                context=contexts[item.index],
                deps=deps,
            )

    return list(await asyncio.gather(*(resolve_one(item) for item in items)))


def _download_argument(request: BatchFetchRequest) -> Path | object:
    if request.download_dir is None:
        return _MCP_DEFAULT_DOWNLOAD_DIR
    return Path(request.download_dir).expanduser()


def _resolved_cache_dir(
    request: BatchFetchRequest,
    *,
    runtime_env: Mapping[str, str],
    download_arg: Path | object,
    deps: MCPDeps,
) -> Path | None:
    if request.no_download and not request.prefer_cache:
        return None
    return _resolve_download_dir(runtime_env, download_arg, deps=deps)


def _resolved_markdown_dir(
    request: BatchFetchRequest,
    *,
    runtime_env: Mapping[str, str],
    download_arg: Path | object,
    deps: MCPDeps,
) -> Path | None:
    if not request.save_markdown:
        return None
    return _markdown_output_dir_for_fetch_request(
        request.to_fetch_request(request.queries[0]),
        runtime_env=runtime_env,
        download_dir=download_arg,
        deps=deps,
    )


def _request_parameters(
    request: BatchFetchRequest,
    *,
    cache_dir: Path | None,
    markdown_dir: Path | None,
) -> dict[str, Any]:
    return {
        "modes": sorted(str(mode) for mode in request.modes),
        "strategy": request.strategy.cache_request_payload(),
        "render": {
            "include_refs": request.include_refs,
            "asset_profile": request.strategy.asset_profile,
            "max_tokens": request.max_tokens,
        },
        "prefer_cache": request.prefer_cache,
        "artifact_mode": request.artifact_mode,
        "no_download": request.no_download,
        "download_dir": str(cache_dir) if cache_dir is not None else None,
        "save_markdown": request.save_markdown,
        "markdown_output_dir": (
            str(markdown_dir) if markdown_dir is not None else None
        ),
        "markdown_filename": request.markdown_filename,
        "primary_output_to_output_dir": request.save_markdown,
        "batch_concurrency": request.concurrency,
        "continue_on_error": request.continue_on_error,
    }


def _resource_uri_for_saved_markdown(
    request: BatchFetchRequest,
    saved: SavedMarkdownResult | None,
) -> str | None:
    if saved is None or saved.cache_entry is None:
        return None
    entry_id = str(saved.cache_entry.get("id") or "")
    if not entry_id:
        return None
    uses_default_scope = (
        request.markdown_output_dir is None and request.download_dir is None
    )
    if uses_default_scope:
        return cached_resource_uri(entry_id)
    return scoped_cached_resource_uri(cache_scope_id(saved.output_dir), entry_id)


def _cache_hit(envelope: FetchEnvelope | None) -> bool:
    if envelope is None:
        return False
    flags = set(envelope.quality.flags)
    if envelope.article is not None:
        flags.update(envelope.article.quality.flags)
    return QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION in flags


def _asset_profile_for_record(
    request: BatchFetchRequest, envelope: FetchEnvelope | None
) -> AssetProfile:
    return effective_asset_profile(
        cast(AssetProfile | None, request.strategy.asset_profile),
        source_name=envelope.source if envelope is not None else None,
    )


def _error_payload_for_outcome(error: Exception) -> dict[str, Any]:
    return error_payload_from_exception(error)


def _aborted_error_payload(
    *,
    reason: str,
    code: str,
    retry_after_seconds: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "aborted",
        "reason": reason,
        "code": code,
        "error_category": ("cancelled" if code == "request_cancelled" else code),
    }
    if retry_after_seconds is not None:
        payload["retry_after_seconds"] = retry_after_seconds
    return payload


def _record_from_batch_result(
    request: BatchFetchRequest,
    result: BatchItemResult[BatchFetchItem, BatchFetchOutcome],
    *,
    request_parameters: Mapping[str, Any],
    run_id: UUID,
    tool_version: str,
    deps: ManifestBuilderDependencies,
) -> ManifestRecord:
    item = result.item
    outcome = result.value
    if outcome is not None:
        artifacts: tuple[ManifestOutputArtifactSpec, ...] = ()
        if outcome.saved_markdown is not None:
            artifacts = (
                ManifestOutputArtifactSpec(
                    path=str(outcome.saved_markdown.path),
                    kind="saved_markdown",
                    legacy_field=LegacyArtifactField.SAVED_MARKDOWN_PATH,
                ),
            )
        diagnostic_artifacts = (
            outcome.envelope.diagnostic_artifacts
            if outcome.envelope is not None
            else outcome.diagnostic_artifacts
        )
        if diagnostic_artifacts:
            artifacts = (
                *artifacts,
                *tuple(
                    ManifestOutputArtifactSpec(
                        path=str(item.get("path")),
                        kind="diagnostic",
                        route=str(item.get("route") or "") or None,
                        failure_code=(str(item.get("failure_code") or "") or None),
                    )
                    for item in diagnostic_artifacts
                    if str(item.get("path") or "").strip()
                ),
            )
        error_payload = (
            _error_payload_for_outcome(outcome.error)
            if outcome.error is not None
            else None
        )
        candidate_count = (
            len(error_payload.get("candidates") or []) if error_payload else 0
        )
        return build_manifest_record(
            tool_version=tool_version,
            run_id=run_id,
            record_id=deterministic_manifest_record_id(
                run_id, index=item.index, attempt=item.attempt
            ),
            index=item.index,
            attempt=item.attempt,
            query=item.query,
            request_parameters=request_parameters,
            asset_profile=_asset_profile_for_record(request, outcome.envelope),
            envelope=outcome.envelope,
            error=error_payload,
            aborted=result.status is BatchItemStatus.CANCELLED,
            requested_outputs=request.to_fetch_request(item.query).requested_modes(),
            candidate_count=candidate_count,
            expected_doi=_expected_doi(item.query),
            output_artifacts=artifacts,
            started_at=outcome.started_at,
            completed_at=outcome.completed_at,
            deps=deps,
        )

    failure = result.failure
    completed_at = deps.clock()
    return build_manifest_record(
        tool_version=tool_version,
        run_id=run_id,
        record_id=deterministic_manifest_record_id(
            run_id, index=item.index, attempt=item.attempt
        ),
        index=item.index,
        attempt=item.attempt,
        query=item.query,
        request_parameters=request_parameters,
        asset_profile=_asset_profile_for_record(request, None),
        error=_aborted_error_payload(
            reason=(
                failure.message
                if failure is not None
                else "Item was not scheduled by the batch runner."
            ),
            code=failure.reason_code if failure is not None else "error",
            retry_after_seconds=(
                failure.retry_after_seconds if failure is not None else None
            ),
        ),
        aborted=True,
        requested_outputs=request.to_fetch_request(item.query).requested_modes(),
        expected_doi=_expected_doi(item.query),
        started_at=completed_at,
        completed_at=completed_at,
        deps=deps,
    )


def _synthetic_aborted_record(
    request: BatchFetchRequest,
    item: BatchFetchItem,
    *,
    request_parameters: Mapping[str, Any],
    run_id: UUID,
    tool_version: str,
    code: str,
    reason: str,
    deps: ManifestBuilderDependencies,
) -> ManifestRecord:
    completed_at = deps.clock()
    return build_manifest_record(
        tool_version=tool_version,
        run_id=run_id,
        record_id=deterministic_manifest_record_id(
            run_id, index=item.index, attempt=item.attempt
        ),
        index=item.index,
        attempt=item.attempt,
        query=item.query,
        request_parameters=request_parameters,
        asset_profile=_asset_profile_for_record(request, None),
        error=_aborted_error_payload(reason=reason, code=code),
        aborted=True,
        requested_outputs=request.to_fetch_request(item.query).requested_modes(),
        expected_doi=_expected_doi(item.query),
        started_at=completed_at,
        completed_at=completed_at,
        deps=deps,
    )


def _classify_outcome(outcome: BatchFetchOutcome) -> BatchFailure | None:
    if outcome.error is not None:
        return _mcp_batch_failure(outcome.error)
    envelope = outcome.envelope
    if envelope is None:
        return None
    rate_limit_events = [
        event
        for event in envelope.trace
        if event.code == RATE_LIMITED
        or event.outcome == RATE_LIMITED
        or event.http_status == 429
    ]
    if not rate_limit_events:
        return None
    retry_after_values = [
        float(event.retry_after_seconds)
        for event in rate_limit_events
        if event.retry_after_seconds is not None
    ]
    providers = [
        event.provider for event in rate_limit_events if event.provider is not None
    ]
    provider_label = providers[-1] if providers else envelope.source
    return BatchFailure(
        reason_code=RATE_LIMITED,
        message=(
            f"{provider_label} was rate limited before the item recovered via "
            f"{envelope.source}."
        ),
        retry_after_seconds=(max(retry_after_values) if retry_after_values else None),
        rate_limited=True,
        details=tuple(rate_limit_events),
    )


def _compact_messages(values: Sequence[str]) -> list[str]:
    return [str(value)[:400] for value in values[:8]]


def _artifact_payloads(
    record: ManifestRecord, *, resource_uri: str | None
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for artifact in record.output_artifacts:
        payload = {
            "path": artifact.path,
            "kind": artifact.kind,
            "route": artifact.route,
            "failure_code": artifact.failure_code,
            "size": artifact.size,
            "sha256": artifact.sha256,
            "completed_at": artifact.completed_at.isoformat(),
            "verification_status": artifact.verification_status.value,
            "resource_uri": (
                resource_uri if artifact.kind == "saved_markdown" else None
            ),
        }
        payloads.append(payload)
    return payloads


def _bounded_content_by_record(
    records: Sequence[ManifestRecord],
    *,
    envelopes: Mapping[tuple[int, int], FetchEnvelope],
    limit: int,
) -> tuple[dict[tuple[int, int], dict[str, Any]], int]:
    eligible = [
        record
        for record in records
        if (envelope := envelopes.get((record.index, record.attempt))) is not None
        and envelope.markdown is not None
    ]
    remaining = limit
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for position, record in enumerate(eligible):
        markdown = envelopes[(record.index, record.attempt)].markdown or ""
        slots = len(eligible) - position
        share = remaining // slots if slots else 0
        returned = markdown[:share]
        remaining -= len(returned)
        result[(record.index, record.attempt)] = {
            "content": returned,
            "content_available_chars": len(markdown),
            "content_returned_chars": len(returned),
            "content_truncated": len(returned) < len(markdown),
        }
    return result, limit - remaining


def _compact_run_payload(
    request: BatchFetchRequest,
    *,
    manifest: RunManifest,
    records: Sequence[ManifestRecord],
    attempted_indices: set[int],
    record_sequences: Mapping[tuple[int, int], int],
    envelopes: Mapping[tuple[int, int], FetchEnvelope],
    saved_results: Mapping[tuple[int, int], SavedMarkdownResult],
    cache_hits: Mapping[tuple[int, int], bool],
    run_result: BatchRunResult[BatchFetchItem, BatchFetchOutcome] | None,
    store: RunManifestStore | None,
) -> dict[str, Any]:
    latest = latest_manifest_records(records)
    ordered_records = [latest[index] for index in range(1, len(request.queries) + 1)]
    content_payloads: dict[tuple[int, int], dict[str, Any]] = {}
    content_returned_chars = 0
    if request.detail == "bounded":
        content_payloads, content_returned_chars = _bounded_content_by_record(
            ordered_records,
            envelopes=envelopes,
            limit=request.content_max_chars,
        )

    results: list[dict[str, Any]] = []
    for record in ordered_records:
        key = (record.index, record.attempt)
        saved = saved_results.get(key)
        resource_uri = _resource_uri_for_saved_markdown(request, saved)
        error_payload = (
            record.error.model_dump(mode="json") if record.error is not None else None
        )
        item = {
            "index": record.index,
            "query": record.query,
            "attempt": record.attempt,
            "completion_sequence": record_sequences.get(key),
            "started_at": record.started_at.isoformat(),
            "completed_at": record.completed_at.isoformat(),
            "record_status": record.record_status.value,
            "status": record.status,
            "run_id": str(record.run_id),
            "record_id": str(record.record_id),
            "request_fingerprint": record.request_fingerprint,
            "doi": record.doi,
            "source": record.source,
            "acquisition": (
                asdict(record.acquisition) if record.acquisition is not None else None
            ),
            "reused": record.index not in attempted_indices,
            "cache_hit": cache_hits.get(key, False),
            "acceptance": compact_acceptance_payload(record.acceptance),
            "fallback_codes": list(record.fallback_codes),
            "warning_codes": list(record.warning_codes),
            "failure_codes": list(record.failure_codes),
            "warnings": _compact_messages(record.warnings),
            "error": error_payload,
            "output_artifacts": _artifact_payloads(record, resource_uri=resource_uri),
            "saved_markdown_path": record.saved_markdown_path,
            "resource_uri": resource_uri,
        }
        if request.detail == "bounded":
            item.update(
                content_payloads.get(
                    key,
                    {
                        "content": None,
                        "content_available_chars": None,
                        "content_returned_chars": 0,
                        "content_truncated": False,
                    },
                )
            )
        results.append(item)

    latest_sequences = sorted(
        (
            (record_sequences.get((record.index, record.attempt)), record)
            for record in ordered_records
        ),
        key=lambda item: item[0] if item[0] is not None else 10**12 + item[1].index,
    )
    completion_order = [
        {
            "sequence": sequence,
            "index": record.index,
            "attempt": record.attempt,
            "status": record.record_status.value,
            "completed_at": record.completed_at.isoformat(),
        }
        for sequence, record in latest_sequences
        if sequence is not None
    ]

    lane_cooldowns: list[dict[str, Any]] = []
    if run_result is not None:
        for lane, cooldown in sorted(
            run_result.lane_cooldowns.items(), key=lambda item: str(item[0])
        ):
            source_item = run_result.results[cooldown.source_index].item
            lane_cooldowns.append(
                {
                    "lane": str(lane),
                    "reason_code": cooldown.reason_code,
                    "source_index": source_item.index,
                    "retry_after_seconds": cooldown.retry_after_seconds,
                    "cooldown_seconds": cooldown.cooldown_seconds,
                }
            )

    record_statuses = Counter(record.record_status.value for record in ordered_records)
    acceptance_counts = Counter(
        record.acceptance.overall.value for record in ordered_records
    )
    aborted = any(
        record.record_status is ManifestRecordStatus.ABORTED
        for record in ordered_records
    )
    cancelled = manifest.state is RunManifestState.CANCELLED
    return with_schema_version(
        {
            "run_id": str(manifest.run_id),
            "request_fingerprint": manifest.request_fingerprint,
            "state": manifest.state.value,
            "persisted": store is not None,
            "run_manifest_path": str(store.manifest_path) if store else None,
            "events_path": str(store.events_path) if store else None,
            "query_count": len(request.queries),
            "attempted_count": len(attempted_indices),
            "reused_count": len(request.queries) - len(attempted_indices),
            "detail": request.detail,
            "content_max_chars": request.content_max_chars,
            "content_returned_chars": content_returned_chars,
            "results": results,
            "completion_order": completion_order,
            "summary": {
                "record_statuses": dict(sorted(record_statuses.items())),
                "acceptance": dict(sorted(acceptance_counts.items())),
                "cache_hits": sum(1 for value in cache_hits.values() if value),
                "saved_markdown": sum(
                    1 for record in ordered_records if record.saved_markdown_path
                ),
            },
            "lane_cooldowns": lane_cooldowns,
            "aborted": aborted,
            "cancelled": cancelled,
        }
    )


def _store_for_request(request: BatchFetchRequest) -> RunManifestStore | None:
    if request.resume is not None:
        return RunManifestStore.from_manifest(Path(request.resume))
    if request.run_manifest is None and request.batch_results is None:
        return None
    results_path = (
        Path(request.batch_results)
        if request.batch_results is not None
        else Path(request.run_manifest or "run-manifest.json").parent
        / "batch-results.jsonl"
    )
    manifest_path = (
        Path(request.run_manifest)
        if request.run_manifest is not None
        else results_path.parent / "run-manifest.json"
    )
    if manifest_path.resolve(strict=False) == results_path.resolve(strict=False):
        raise ValueError("run_manifest and batch_results must use different paths.")
    return RunManifestStore.for_new_run(
        manifest_path=manifest_path,
        events_path=results_path,
    )


async def _execute_batch_fetch(
    request: BatchFetchRequest,
    *,
    env: Mapping[str, str] | None,
    ctx: Context | None,
    deps: MCPDeps,
    manifest_deps: ManifestBuilderDependencies,
    requested_run_id: UUID | None,
    tool_version: str,
) -> dict[str, Any]:
    runtime_env = apply_browser_auto_prepare_policy(
        deps.build_runtime_env(env),
        override=request.browser_auto_prepare,
        default=False,
    )
    download_arg = _download_argument(request)
    cache_dir = _resolved_cache_dir(
        request,
        runtime_env=runtime_env,
        download_arg=download_arg,
        deps=deps,
    )
    markdown_dir = _resolved_markdown_dir(
        request,
        runtime_env=runtime_env,
        download_arg=download_arg,
        deps=deps,
    )
    request_parameters = _request_parameters(
        request, cache_dir=cache_dir, markdown_dir=markdown_dir
    )
    store = _store_for_request(request)
    lock_context = store.run_lock() if store is not None else nullcontext()

    await report_progress(ctx, 0, len(request.queries), "Starting batch_fetch")
    cancelled = threading.Event()
    runtime_context = RuntimeContext(
        env=runtime_env,
        download_dir=cache_dir,
        artifact_mode=("none" if request.no_download else request.artifact_mode),
        cancel_check=cancelled.is_set,
    )
    item_contexts: dict[int, RuntimeContext] = {}

    with lock_context:
        run_started = False
        journal: BatchManifestJournal | None = None
        items: list[BatchFetchItem] = []
        run_result: BatchRunResult[BatchFetchItem, BatchFetchOutcome] | None = None
        envelopes: dict[tuple[int, int], FetchEnvelope] = {}
        saved_results: dict[tuple[int, int], SavedMarkdownResult] = {}
        cache_hits: dict[tuple[int, int], bool] = {}

        try:
            try:
                prepared = prepare_batch_run(
                    store=store,
                    queries=request.queries,
                    request_parameters=request_parameters,
                    tool_version=tool_version,
                    requested_run_id=requested_run_id,
                    resume=request.resume is not None,
                    overwrite=request.overwrite,
                    clock=manifest_deps.clock,
                    uuid_factory=manifest_deps.uuid_factory,
                    item_factory=lambda index, query, attempt: BatchFetchItem(
                        index=index,
                        query=query,
                        lane_key=_lane_for_query(query),
                        attempt=attempt,
                    ),
                )
            except BatchLifecycleOverwriteError as exc:
                raise FileExistsError(
                    str(exc).replace("enable overwrite", "set overwrite=true")
                ) from exc
            journal = BatchManifestJournal(
                manifest=prepared.manifest,
                records=prepared.records,
                store=store,
            )
            items = prepared.items
            effective_run_id = prepared.run_id
            append_events = prepared.append_events
            reused_count = prepared.reused_count
            run_started = True
            item_contexts = {
                item.index: runtime_context.new_request_context(
                    asset_profile=request.strategy.asset_profile,
                )
                for item in items
            }
            items = await _resolve_batch_item_lanes(
                items,
                contexts=item_contexts,
                concurrency=request.concurrency,
                deps=deps,
            )
            if reused_count:
                await report_progress(
                    ctx,
                    reused_count,
                    len(request.queries),
                    f"batch_fetch reused {reused_count} audited result(s)",
                )

            def run_item(item: BatchFetchItem) -> BatchFetchOutcome:
                started_at = manifest_deps.clock()
                fetch_request = request.to_fetch_request(item.query)
                item_context = item_contexts[item.index]
                try:
                    item_context.reset_request_deadline()
                    envelope = deps.fetch_paper_envelope(
                        fetch_request,
                        env=runtime_env,
                        download_dir=download_arg,
                        transport=None,
                        include_article_for_assets=True,
                        context=item_context,
                        cancel_check=cancelled.is_set,
                        deps=deps,
                    )
                    saved = _save_markdown_result_for_fetch_request(
                        envelope,
                        fetch_request,
                        env=runtime_env,
                        download_dir=download_arg,
                        context=item_context,
                        overwrite=request.overwrite,
                        deps=deps,
                    )
                    return BatchFetchOutcome(
                        started_at=started_at,
                        completed_at=manifest_deps.clock(),
                        envelope=envelope,
                        saved_markdown=saved,
                        diagnostic_artifacts=tuple(
                            dict(item) for item in item_context.diagnostic_artifacts
                        ),
                    )
                except Exception as error:  # every submitted item gets one record
                    return BatchFetchOutcome(
                        started_at=started_at,
                        completed_at=manifest_deps.clock(),
                        error=error,
                        diagnostic_artifacts=tuple(
                            dict(item) for item in item_context.diagnostic_artifacts
                        ),
                    )
                finally:
                    item_context.close()

            def on_completion(
                event: BatchCompletionEvent[BatchFetchItem, BatchFetchOutcome],
            ) -> None:
                record = _record_from_batch_result(
                    request,
                    event.result,
                    request_parameters=request_parameters,
                    run_id=effective_run_id,
                    tool_version=tool_version,
                    deps=manifest_deps,
                )
                outcome = event.result.value
                if outcome is not None and outcome.envelope is not None:
                    key = (record.index, record.attempt)
                    envelopes[key] = outcome.envelope
                    cache_hits[key] = _cache_hit(outcome.envelope)
                    if outcome.saved_markdown is not None:
                        saved_results[key] = outcome.saved_markdown
                assert journal is not None
                journal.persist(record, writer=writer)

            async def on_progress(
                progress: BatchProgress[BatchFetchItem, BatchFetchOutcome],
            ) -> None:
                item = progress.event.result.item
                await report_progress(
                    ctx,
                    reused_count + progress.terminal,
                    len(request.queries),
                    (
                        f"batch_fetch index {item.index}: "
                        f"{progress.event.result.status.value} "
                        f"({reused_count + progress.terminal}/{len(request.queries)})"
                    ),
                )

            writer: ManifestJsonlWriter | None = None
            if items:
                writer_context = (
                    ManifestJsonlWriter(
                        store.events_path,
                        append=append_events,
                        overwrite=request.overwrite,
                    )
                    if store is not None
                    else nullcontext(None)
                )
                with writer_context as opened_writer:
                    writer = cast(ManifestJsonlWriter | None, opened_writer)
                    run_result = await run_batch_async(
                        items,
                        run_item,
                        max_workers=request.concurrency,
                        lane_key=lambda item: item.lane_key,
                        lane_limits=lambda lane: provider_lane_limit(
                            lane,
                            global_limit=request.concurrency,
                        ),
                        completion_callback=on_completion,
                        progress_callback=on_progress,
                        stop_predicate=(
                            None
                            if request.continue_on_error
                            else lambda result: (
                                result.status is not BatchItemStatus.SUCCEEDED
                            )
                        ),
                        cancel_event=cancelled,
                        result_classifier=_classify_outcome,
                    )
                if run_result.callback_failures:
                    details = "; ".join(
                        f"index {items[failure.source_index].index}: {failure.message}"
                        for failure in run_result.callback_failures
                    )
                    raise RuntimeError(
                        f"could not persist complete batch_fetch events: {details}"
                    )

            assert journal is not None
            journal.require_complete(len(request.queries))
            state = (
                RunManifestState.CANCELLED
                if run_result is not None and run_result.cancelled
                else RunManifestState.COMPLETED
            )
            manifest = journal.finish(
                state=state,
                completed_at=manifest_deps.clock(),
            )
            await report_progress(
                ctx,
                len(request.queries),
                len(request.queries),
                (
                    "batch_fetch cancelled"
                    if state is RunManifestState.CANCELLED
                    else "batch_fetch complete"
                ),
            )
            return _compact_run_payload(
                request,
                manifest=manifest,
                records=journal.records,
                attempted_indices={item.index for item in items},
                record_sequences=journal.record_sequences,
                envelopes=envelopes,
                saved_results=saved_results,
                cache_hits=cache_hits,
                run_result=run_result,
                store=store,
            )
        except asyncio.CancelledError:
            cancelled.set()
            if run_started and journal is not None:
                try:
                    journal.terminalize_missing(
                        items,
                        lambda item: _synthetic_aborted_record(
                            request,
                            item,
                            request_parameters=request_parameters,
                            run_id=effective_run_id,
                            tool_version=tool_version,
                            code="request_cancelled",
                            reason=(
                                "Item was interrupted by MCP cooperative cancellation."
                            ),
                            deps=manifest_deps,
                        ),
                    )
                    journal.finish(
                        state=RunManifestState.CANCELLED,
                        completed_at=manifest_deps.clock(),
                    )
                except Exception:
                    pass
            raise
        except Exception:
            cancelled.set()
            if run_started and journal is not None:
                try:
                    journal.terminalize_missing(
                        items,
                        lambda item: _synthetic_aborted_record(
                            request,
                            item,
                            request_parameters=request_parameters,
                            run_id=effective_run_id,
                            tool_version=tool_version,
                            code="batch_interrupted",
                            reason=(
                                "Item was not completed because batch_fetch was interrupted."
                            ),
                            deps=manifest_deps,
                        ),
                    )
                    journal.finish(
                        state=RunManifestState.INTERRUPTED,
                        completed_at=manifest_deps.clock(),
                    )
                except Exception:
                    pass
            raise
        finally:
            runtime_context.close()


async def batch_fetch_tool_async(
    *,
    queries: list[str],
    concurrency: int = 1,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    no_download: bool = False,
    artifact_mode: ArtifactMode = "markdown-assets",
    save_markdown: bool = False,
    markdown_output_dir: str | None = None,
    markdown_filename: str | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    detail: str = "compact",
    content_max_chars: int = 20_000,
    continue_on_error: bool = True,
    run_manifest: str | None = None,
    batch_results: str | None = None,
    resume: str | None = None,
    overwrite: bool = False,
    browser_auto_prepare: bool | None = None,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
    deps: MCPDeps = default_mcp_deps(),
    manifest_deps: ManifestBuilderDependencies = DEFAULT_MANIFEST_BUILDER_DEPENDENCIES,
    run_id: UUID | None = None,
    tool_version: str | None = None,
) -> CallToolResult:
    request_payload: dict[str, Any] = {
        "queries": queries,
        "concurrency": concurrency,
        "modes": modes,
        "strategy": strategy,
        "include_refs": include_refs,
        "max_tokens": max_tokens,
        "prefer_cache": prefer_cache,
        "no_download": no_download,
        "artifact_mode": artifact_mode,
        "save_markdown": save_markdown,
        "markdown_output_dir": markdown_output_dir,
        "markdown_filename": markdown_filename,
        "detail": detail,
        "content_max_chars": content_max_chars,
        "continue_on_error": continue_on_error,
        "run_manifest": run_manifest,
        "batch_results": batch_results,
        "resume": resume,
        "overwrite": overwrite,
        "browser_auto_prepare": browser_auto_prepare,
    }
    if download_dir is not _MCP_DEFAULT_DOWNLOAD_DIR:
        request_payload["download_dir"] = (
            str(download_dir) if download_dir is not None else None
        )
    try:
        request = BatchFetchRequest.model_validate(request_payload)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    try:
        loop = asyncio.get_running_loop()
        bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None
        with ExitStack() as stack:
            if bridge is not None:
                stack.enter_context(bridge)
            payload = await _execute_batch_fetch(
                request,
                env=env,
                ctx=ctx,
                deps=deps,
                manifest_deps=manifest_deps,
                requested_run_id=run_id,
                tool_version=tool_version or runtime_tool_version(),
            )
        return _tool_result(payload, is_error=False)
    except asyncio.CancelledError:
        raise
    except (ManifestPersistenceError, OSError, ValueError, RuntimeError) as error:
        await report_progress(
            ctx, len(request.queries), len(request.queries), "batch_fetch failed"
        )
        return _tool_result(error_payload_from_exception(error), is_error=True)


__all__ = [
    "BatchFetchItem",
    "BatchFetchOutcome",
    "batch_fetch_tool_async",
]
