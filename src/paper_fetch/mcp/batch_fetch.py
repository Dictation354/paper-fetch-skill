"""Structured MCP batch-fetch adapter over shared runner and manifest owners."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading
from typing import Any, cast
from uuid import UUID

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult

from ..artifacts import ArtifactMode
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
    ManifestAuditStatus,
    ManifestJsonlWriter,
    ManifestPersistenceError,
    RunManifest,
    RunManifestState,
    RunManifestStore,
    audit_manifest_path,
    build_run_request_fingerprint,
    checkpoint_run_manifest,
    create_run_manifest,
    deterministic_manifest_record_id,
    latest_manifest_records,
    terminal_run_manifest,
)
from ..models import (
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    AssetProfile,
    FetchEnvelope,
)
from ..publisher_identity import (
    extract_doi,
    extract_doi_from_url,
    infer_provider_from_doi,
    infer_provider_from_url,
)
from ..runtime import RuntimeContext
from ..workflow.batch_runner import (
    BatchCompletionEvent,
    BatchFailure,
    BatchItemResult,
    BatchItemStatus,
    BatchProgress,
    BatchRunResult,
    run_batch_async,
)
from ..workflow.types import effective_asset_profile
from ._deps import MCPDeps, default_mcp_deps
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


def _expected_doi(query: str) -> str | None:
    return extract_doi_from_url(query) or extract_doi(query)


def _lane_for_query(query: str) -> str:
    provider = infer_provider_from_url(query)
    if provider:
        return provider
    return infer_provider_from_doi(_expected_doi(query)) or "generic"


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
    if outcome.error is None:
        return None
    return _mcp_batch_failure(outcome.error)


def _compact_messages(values: Sequence[str]) -> list[str]:
    return [str(value)[:400] for value in values[:8]]


def _compact_acceptance(record: ManifestRecord) -> dict[str, Any]:
    acceptance = record.acceptance
    return {
        "overall": acceptance.overall.value,
        "identity": acceptance.identity.status.value,
        "fetch": acceptance.fetch.status.value,
        "content": acceptance.content.status.value,
        "asset": acceptance.asset.status.value,
        "output": acceptance.output.status.value,
        "provenance": acceptance.provenance.status.value,
        "has_fulltext": acceptance.content.has_fulltext,
        "has_abstract": acceptance.content.has_abstract,
        "token_estimate": acceptance.content.token_estimate,
    }


def _artifact_payloads(
    record: ManifestRecord, *, resource_uri: str | None
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for artifact in record.output_artifacts:
        payload = {
            "path": artifact.path,
            "kind": artifact.kind,
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
            "reused": record.index not in attempted_indices,
            "cache_hit": cache_hits.get(key, False),
            "acceptance": _compact_acceptance(record),
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


def _recorded_output_path(raw_path: str, *, manifest_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute() or path.exists():
        return path
    return manifest_path.parent / path


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
    runtime_env = deps.build_runtime_env(env)
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

    with lock_context:
        run_started = False
        records: list[ManifestRecord] = []
        manifest: RunManifest | None = None
        items: list[BatchFetchItem] = []
        append_events = False
        run_result: BatchRunResult[BatchFetchItem, BatchFetchOutcome] | None = None
        record_sequences: dict[tuple[int, int], int] = {}
        envelopes: dict[tuple[int, int], FetchEnvelope] = {}
        saved_results: dict[tuple[int, int], SavedMarkdownResult] = {}
        cache_hits: dict[tuple[int, int], bool] = {}

        def persist_record(record: ManifestRecord) -> None:
            nonlocal manifest
            if store is not None:
                store.append_record(record)
            records.append(record)
            record_sequences[(record.index, record.attempt)] = len(records)
            if store is not None:
                assert manifest is not None
                manifest = store.write(checkpoint_run_manifest(manifest, records))

        def terminalize_missing(*, code: str, reason: str) -> None:
            latest = latest_manifest_records(records)
            for item in items:
                previous = latest.get(item.index)
                if previous is not None and previous.attempt >= item.attempt:
                    continue
                persist_record(
                    _synthetic_aborted_record(
                        request,
                        item,
                        request_parameters=request_parameters,
                        run_id=effective_run_id,
                        tool_version=tool_version,
                        code=code,
                        reason=reason,
                        deps=manifest_deps,
                    )
                )

        try:
            if request.resume is not None:
                if store is None:
                    raise RuntimeError("resume did not resolve a run manifest store")
                manifest = store.read()
                if requested_run_id is not None and requested_run_id != manifest.run_id:
                    raise ValueError("requested run_id differs from the recorded run.")
                if [item.query for item in manifest.inputs] != request.queries:
                    raise ValueError(
                        "queries differ from the recorded run; create a new run instead."
                    )
                if (
                    build_run_request_fingerprint(request.queries, request_parameters)
                    != manifest.request_fingerprint
                ):
                    raise ValueError(
                        "critical fetch/output configuration differs from the recorded run."
                    )
                if manifest.tool_version != tool_version:
                    raise ValueError(
                        "tool version differs from the recorded run; create a new run instead."
                    )
                report = audit_manifest_path(store.manifest_path, mode="audit")
                if report.status is ManifestAuditStatus.INVALID:
                    raise ValueError(
                        "run manifest is structurally invalid and cannot be resumed."
                    )
                records = store.read_records() if store.events_path.is_file() else []
                for sequence, record in enumerate(records, start=1):
                    record_sequences[(record.index, record.attempt)] = sequence
                latest = latest_manifest_records(records)
                reusable_indices = set(report.reusable_indices)
                items = [
                    BatchFetchItem(
                        index=index,
                        query=query,
                        lane_key=_lane_for_query(query),
                        attempt=(latest[index].attempt + 1 if index in latest else 1),
                    )
                    for index, query in enumerate(request.queries, start=1)
                    if index not in reusable_indices
                ]
                if not request.overwrite:
                    existing_outputs = sorted(
                        {
                            str(path)
                            for item in items
                            if (previous := latest.get(item.index)) is not None
                            for artifact in previous.output_artifacts
                            if (
                                path := _recorded_output_path(
                                    artifact.path,
                                    manifest_path=store.manifest_path,
                                )
                            ).exists()
                        }
                    )
                    if existing_outputs:
                        raise FileExistsError(
                            "resume would replace existing stale or below-request output; "
                            "review it and set overwrite=true: "
                            + ", ".join(existing_outputs)
                        )
                effective_run_id = manifest.run_id
                manifest = store.write(checkpoint_run_manifest(manifest, records))
                append_events = True
                run_started = True
            else:
                effective_run_id = requested_run_id or manifest_deps.uuid_factory()
                if store is not None:
                    if store.manifest_path.exists() and not request.overwrite:
                        raise FileExistsError(
                            f"run manifest already exists at {store.manifest_path}; "
                            "set overwrite=true or choose another path."
                        )
                    if store.events_path.exists() and not request.overwrite:
                        raise FileExistsError(
                            f"batch event file already exists at {store.events_path}; "
                            "set overwrite=true or choose another path."
                        )
                    events_reference = store.events_reference()
                else:
                    events_reference = "<memory>"
                manifest = create_run_manifest(
                    run_id=effective_run_id,
                    tool_version=tool_version,
                    queries=request.queries,
                    request_parameters=request_parameters,
                    started_at=manifest_deps.clock(),
                    events_path=events_reference,
                )
                if store is not None:
                    manifest = store.create(manifest, overwrite=request.overwrite)
                run_started = True
                items = [
                    BatchFetchItem(
                        index=index,
                        query=query,
                        lane_key=_lane_for_query(query),
                    )
                    for index, query in enumerate(request.queries, start=1)
                ]

            reused_count = len(request.queries) - len(items)
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
                try:
                    envelope = deps.fetch_paper_envelope(
                        fetch_request,
                        env=runtime_env,
                        download_dir=download_arg,
                        transport=None,
                        include_article_for_assets=True,
                        context=runtime_context,
                        cancel_check=cancelled.is_set,
                        deps=deps,
                    )
                    saved = _save_markdown_result_for_fetch_request(
                        envelope,
                        fetch_request,
                        env=runtime_env,
                        download_dir=download_arg,
                        context=runtime_context,
                        overwrite=request.overwrite,
                        deps=deps,
                    )
                    return BatchFetchOutcome(
                        started_at=started_at,
                        completed_at=manifest_deps.clock(),
                        envelope=envelope,
                        saved_markdown=saved,
                    )
                except Exception as error:  # every submitted item gets one record
                    return BatchFetchOutcome(
                        started_at=started_at,
                        completed_at=manifest_deps.clock(),
                        error=error,
                    )

            def on_completion(
                event: BatchCompletionEvent[BatchFetchItem, BatchFetchOutcome],
            ) -> None:
                nonlocal manifest
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
                if store is not None:
                    assert writer is not None
                    writer.write(record)
                    records.append(record)
                    record_sequences[(record.index, record.attempt)] = len(records)
                    assert manifest is not None
                    manifest = store.write(checkpoint_run_manifest(manifest, records))
                else:
                    records.append(record)
                    record_sequences[(record.index, record.attempt)] = len(records)

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

            latest = latest_manifest_records(records)
            if set(latest) != set(range(1, len(request.queries) + 1)):
                raise RuntimeError(
                    "batch_fetch does not have one latest terminal attempt per input."
                )
            assert manifest is not None
            state = (
                RunManifestState.CANCELLED
                if run_result is not None and run_result.cancelled
                else RunManifestState.COMPLETED
            )
            manifest = terminal_run_manifest(
                manifest,
                records,
                state=state,
                completed_at=manifest_deps.clock(),
            )
            if store is not None:
                manifest = store.write(manifest)
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
                records=records,
                attempted_indices={item.index for item in items},
                record_sequences=record_sequences,
                envelopes=envelopes,
                saved_results=saved_results,
                cache_hits=cache_hits,
                run_result=run_result,
                store=store,
            )
        except asyncio.CancelledError:
            cancelled.set()
            if run_started and manifest is not None:
                try:
                    terminalize_missing(
                        code="request_cancelled",
                        reason="Item was interrupted by MCP cooperative cancellation.",
                    )
                    manifest = terminal_run_manifest(
                        manifest,
                        records,
                        state=RunManifestState.CANCELLED,
                        completed_at=manifest_deps.clock(),
                    )
                    if store is not None:
                        store.write(manifest)
                except Exception:
                    pass
            raise
        except Exception:
            cancelled.set()
            if run_started and manifest is not None:
                try:
                    terminalize_missing(
                        code="batch_interrupted",
                        reason="Item was not completed because batch_fetch was interrupted.",
                    )
                    manifest = terminal_run_manifest(
                        manifest,
                        records,
                        state=RunManifestState.INTERRUPTED,
                        completed_at=manifest_deps.clock(),
                    )
                    if store is not None:
                        store.write(manifest)
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
