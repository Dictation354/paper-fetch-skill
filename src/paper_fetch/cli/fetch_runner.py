"""Single and batch paper fetch runners and interactive AMS auth gate."""

from __future__ import annotations

import json
import os
import select
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import UUID

import paper_fetch.cli as cli_pkg

from ..auth import (
    AuthCancelledError,
    ams_auth_coordination,
    ams_profile_path,
    has_verified_ams_profile,
    require_ams_auth,
)
from ..capability_scope import (
    capability_scope_from_runtime_context,
    capability_scopes_for_query,
)
from ..delivery.fetch_cache import FetchCache
from ..delivery.receipts import target_satisfied
from ..delivery.requests import FetchPaperRequest
from ..http import RequestCancelledError
from ..http.transport import request_cancel_check
from ..manifest import ManifestBuilderDependencies, ManifestRecord
from ..manifest_writer import (
    deterministic_manifest_record_id,
    serialize_manifest_record,
)
from ..models.schema import FetchEnvelope
from ..providers.base import ProviderFailure
from ..reason_codes import ERROR, RATE_LIMITED
from ..runtime import RuntimeContext
from ..service import FetchStrategy, PaperFetchFailure
from ..workflow.batch_routing import (
    expected_doi_from_query,
    fanout_batch_items,
    initial_provider_lane,
    provider_lane_from_resolved,
    provider_lane_limit,
    resolve_batch_item_routing,
)
from ..workflow.batch_runner import (
    BatchCompletionEvent,
    BatchFailure,
    BatchItemResult,
    BatchItemStatus,
    run_batch,
)
from ..workflow.batch_session import BatchExecutionSession
from ..workflow.pipeline import FetchPipeline, FetchPipelineRequest
from ..workflow.rendering import (
    save_markdown_to_disk as save_markdown_to_disk_for_target,
)
from ..workflow.routing import resolve_query_with_session_cache
from .commands import (
    BatchFetchCommand,
    FetchExecutionOptions,
    OutputDirectoryError,
    OutputOverwriteRequired,
    SingleFetchCommand,
    SupportsControlStdin,
    compute_output_modes,
)
from .manifest_io import (
    CliManifestAttempt,
    CliManifestBuildContext,
    SingleFetchResult,
    _aborted_error_payload,
    _build_cli_manifest_record,
    _error_payload,
    _formatted_output_filename,
    _same_output_path,
    _validate_single_manifest_target,
    _write_single_cli_manifest,
    _write_single_failure_manifest,
    exit_code_for_batch_results,
    prepare_output_dir,
    save_formatted_output_copy,
    serialize_envelope,
    write_output,
)
from .progress import _cooperative_batch_cancel


@dataclass(frozen=True, slots=True)
class CliBatchItem:
    """One 1-based CLI input plus its statically inferred scheduling lane."""

    index: int
    query: str
    lane_key: str
    attempt: int = 1
    canonical_doi: str | None = None


@dataclass(frozen=True, slots=True)
class CliFetchOutcome:
    """Wall-clock attempt facts retained when a batch worker fails."""

    started_at: datetime
    completed_at: datetime
    result: SingleFetchResult | None = None
    error: Exception | None = None
    diagnostic_artifacts: tuple[dict[str, Any], ...] = ()


def _confirm_auth_on_stderr(prompt: str, context: RuntimeContext) -> None:
    cli_pkg.sys.stderr.write(prompt)
    cli_pkg.sys.stderr.flush()
    # Keep Ctrl-C cooperative while waiting for a human on the terminal. The
    # control-stdin protocol never reaches this prompt.
    if os.name == "nt":
        msvcrt: Any = import_module("msvcrt")
        while True:
            context.raise_if_cancelled()
            if msvcrt.kbhit() and msvcrt.getwch() in {"\r", "\n"}:
                break
            cli_pkg.time.sleep(0.05)
        return

    while True:
        context.raise_if_cancelled()
        if select.select([cli_pkg.sys.stdin], [], [], 0.05)[0]:
            break
    if not cli_pkg.sys.stdin.readline():
        raise EOFError


def _ensure_cli_ams_auth(
    options: SupportsControlStdin, context: RuntimeContext
) -> None:
    context.raise_if_cancelled()
    if has_verified_ams_profile(context.env or {}):
        return
    if options.control_stdin or not cli_pkg.sys.stdin.isatty():
        require_ams_auth(context.env or {}, provider="ams")
    with ams_auth_coordination(context.env or {}, cancel=context.raise_if_cancelled):
        # Another CLI may have completed authentication while we waited.
        if has_verified_ams_profile(context.env or {}):
            return
        context.report_progress("stage", stage="authenticating")
        cli_pkg.sys.stderr.write("AMS requires authentication before acquisition.\n")
        try:
            cli_pkg.authenticate_provider_profile(
                provider="ams",
                env=context.env,
                confirm=lambda prompt: _confirm_auth_on_stderr(prompt, context),
            )
        except (KeyboardInterrupt, RequestCancelledError) as exc:
            if isinstance(exc, AuthCancelledError):
                raise
            raise AuthCancelledError(
                str(exc) or "AMS authentication cancelled.",
                provider="ams",
                stage="auth_manual_check",
            ) from exc
        context.raise_if_cancelled()
        require_ams_auth(context.env or {}, provider="ams")


def _ensure_cli_query_auth(
    options: FetchExecutionOptions, *, query: str, context: RuntimeContext
) -> None:
    if context.get_session_cache(("cli", "auth-checked", query)):
        return
    lane = initial_provider_lane(query)
    if lane in {"ams", "generic"}:
        resolved = resolve_query_with_session_cache(
            query, resolver=cli_pkg.resolve_paper, context=context
        )
        if provider_lane_from_resolved(resolved) == "ams":
            _ensure_cli_ams_auth(options, context)
    context.set_session_cache(("cli", "auth-checked", query), True)


def _load_cli_fetch_cache(
    options: FetchExecutionOptions,
    *,
    query: str,
    output_dir: Path,
    context: RuntimeContext,
) -> tuple[FetchPaperRequest, FetchEnvelope | None]:
    modes = compute_output_modes(options.output_plan)
    if options.output_plan.deliver_files:
        modes.update({"article", "markdown"})
    cache_request = FetchPaperRequest(
        query=query,
        target=options.target,
        modes=sorted(modes),
        strategy={
            "asset_profile": options.asset_profile,
            "require_local_body_assets": options.require_local_body_assets,
            "require_full_size_body_assets": options.require_full_size_body_assets,
        },
        include_refs=options.include_refs,
        max_tokens=options.max_tokens,
        prefer_cache=options.prefer_cache,
    )
    cache_key = ("cli", "fetch-cache", cache_request.model_dump_json())
    prepared = context.get_session_cache(cache_key)
    if prepared is not None:
        return prepared
    scopes = capability_scopes_for_query(context.env, query)
    cache = FetchCache(
        output_dir, credential_scope=scopes[0], read_credential_scopes=scopes
    )
    envelope = cache.load_fetch_envelope(
        cache_request, resolve_paper_fn=cli_pkg.resolve_paper, context=context
    )
    prepared = (cache_request, envelope)
    context.set_session_cache(cache_key, prepared)
    return prepared


def run_single_fetch(
    options: FetchExecutionOptions,
    *,
    query: str,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    transport: Any = None,
    cancel_check: Callable[[], bool] | None = None,
    context: RuntimeContext | None = None,
) -> SingleFetchResult:
    """Run one complete fetch/output transaction in one runtime context."""

    owns_context = context is None
    active_context = context or cli_pkg.RuntimeContext(
        env=runtime_env,
        transport=transport,
        download_dir=output_dir,
        artifact_mode=options.artifact_mode,
        asset_profile=options.asset_profile,
        cancel_check=cancel_check,
    )
    token = request_cancel_check.set(active_context.cancel_check)
    try:
        with active_context.fetch_browser_preparation():
            active_context.raise_if_cancelled()
            return cli_pkg._run_single_fetch_with_context(
                options,
                query=query,
                output_dir=output_dir,
                runtime_env=runtime_env,
                transport=transport,
                cancel_check=cancel_check,
                context=active_context,
            )
    finally:
        request_cancel_check.reset(token)
        if owns_context:
            active_context.close()


def _run_single_fetch_with_context(
    options: FetchExecutionOptions,
    *,
    query: str,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    transport: Any = None,
    cancel_check: Callable[[], bool] | None = None,
    context: RuntimeContext,
) -> SingleFetchResult:
    del runtime_env, transport, cancel_check
    plan = options.output_plan
    modes = compute_output_modes(plan)
    if plan.deliver_files:
        modes.update({"article", "markdown"})
    render_options = options.render_options()
    overwrite = plan.overwrite
    try:
        preflight_error = context.get_session_cache(
            ("cli", "auth-error", query), copy_value=False
        )
        if preflight_error is not None:
            raise preflight_error
        cache_request, envelope = _load_cli_fetch_cache(
            options, query=query, output_dir=output_dir, context=context
        )
        if envelope is None:
            _ensure_cli_query_auth(options, query=query, context=context)
        cache_hit = envelope is not None
        envelope = envelope or FetchPipeline(cli_pkg.fetch_paper).run(
            FetchPipelineRequest(
                query=query,
                target=options.target,
                modes=modes,
                strategy=FetchStrategy(
                    allow_metadata_only_fallback=True,
                    asset_profile=options.asset_profile,
                    require_local_body_assets=options.require_local_body_assets,
                    require_full_size_body_assets=options.require_full_size_body_assets,
                ),
                render=render_options,
            ),
            context=context,
        )
        context.raise_if_cancelled()
        if options.prefer_cache and not cache_hit:
            FetchCache(
                output_dir,
                credential_scope=capability_scope_from_runtime_context(context),
            ).write_fetch_envelope(
                envelope, cache_request, commit_guard=context.commit_guard
            )
        context.report_progress("stage", stage="writing")
        saved_markdown_path = None
        if plan.save_markdown_to_disk:
            context.raise_if_cancelled()
            saved_markdown_path = save_markdown_to_disk_for_target(
                envelope,
                output_dir=output_dir,
                render=render_options,
                request_label="--save-markdown",
                overwrite=overwrite,
                commit_guard=context.commit_guard,
            )
    except FileExistsError as exc:
        raise OutputOverwriteRequired(
            f"{exc}; rerun with --overwrite after reviewing the existing output"
        ) from exc

    context.raise_if_cancelled()
    if plan.primary_output_to_output_dir:
        target = output_dir / _formatted_output_filename(
            envelope,
            output_format=plan.output_format,
            fallback_query=query,
        )
        if plan.output_format == "markdown" and _same_output_path(
            saved_markdown_path, target
        ):
            primary_output_path = target
        else:
            try:
                primary_output_path = save_formatted_output_copy(
                    envelope,
                    output_dir=output_dir,
                    output_format=plan.output_format,
                    render=render_options,
                    overwrite=overwrite,
                    fallback_query=query,
                    commit_guard=context.commit_guard,
                )
            except FileExistsError as exc:
                raise OutputOverwriteRequired(
                    f"{exc}; rerun with --overwrite after reviewing the existing output"
                ) from exc
        return SingleFetchResult(
            envelope=envelope,
            output_path=primary_output_path,
            saved_markdown_path=saved_markdown_path,
        )

    markdown_override = (
        cli_pkg.rewrite_markdown_asset_links(
            envelope.markdown or "",
            envelope,
            target_path=Path(plan.output),
            render=render_options,
        )
        if plan.output != "-" and plan.output_format in {"markdown", "both"}
        else None
    )
    serialized = serialize_envelope(
        envelope,
        output_format=plan.output_format,
        markdown_override=markdown_override,
    )
    output_path: Path | None = None
    if plan.save_output_copy:
        target = output_dir / _formatted_output_filename(
            envelope,
            output_format=plan.output_format,
            fallback_query=query,
        )
        if plan.output_format == "markdown" and _same_output_path(
            saved_markdown_path, target
        ):
            output_path = target
        else:
            try:
                output_path = save_formatted_output_copy(
                    envelope,
                    output_dir=output_dir,
                    output_format=plan.output_format,
                    render=render_options,
                    overwrite=overwrite,
                    fallback_query=query,
                    commit_guard=context.commit_guard,
                )
            except FileExistsError as exc:
                raise OutputOverwriteRequired(
                    f"{exc}; rerun with --overwrite after reviewing the existing output"
                ) from exc
    explicit_target = Path(plan.output)
    if not (
        plan.output != "-"
        and plan.output_format == "markdown"
        and _same_output_path(saved_markdown_path, explicit_target)
    ):
        try:
            write_output(
                serialized,
                plan.output,
                overwrite=overwrite,
                commit_guard=context.commit_guard,
            )
        except FileExistsError as exc:
            raise OutputOverwriteRequired(
                f"{exc}; rerun with --overwrite after reviewing the existing output"
            ) from exc
    if plan.output != "-":
        output_path = explicit_target
    return SingleFetchResult(
        envelope=envelope,
        output_path=output_path,
        saved_markdown_path=saved_markdown_path,
    )


def _resolve_cli_batch_item_lane(
    item: CliBatchItem,
    *,
    context: RuntimeContext,
) -> CliBatchItem:
    token = request_cancel_check.set(context.cancel_check)
    try:
        context.raise_if_cancelled()
        context.report_progress("stage", stage="identity")
        resolved = resolve_batch_item_routing(
            item, context=context, resolver=cli_pkg.resolve_paper
        )
        context.raise_if_cancelled()
        return resolved
    finally:
        context.close_browser_for_current_thread()
        request_cancel_check.reset(token)


def _run_batch_item(
    item: CliBatchItem,
    *,
    options: FetchExecutionOptions,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    context: RuntimeContext,
    deps: ManifestBuilderDependencies,
) -> CliFetchOutcome:
    started_at = deps.clock()
    try:
        context.reset_request_deadline()
        result = cli_pkg.run_single_fetch(
            options,
            query=item.query,
            output_dir=output_dir,
            runtime_env=runtime_env,
            context=context,
        )
    except Exception as exc:  # noqa: BLE001 - every batch input gets a terminal record.
        return CliFetchOutcome(
            started_at=started_at,
            completed_at=deps.clock(),
            error=exc,
            diagnostic_artifacts=tuple(
                dict(entry) for entry in context.diagnostic_artifacts
            ),
        )
    else:
        return CliFetchOutcome(
            started_at=started_at,
            completed_at=deps.clock(),
            result=result,
            diagnostic_artifacts=tuple(
                dict(entry) for entry in context.diagnostic_artifacts
            ),
        )
    finally:
        context.close()


def _classify_batch_outcome(outcome: CliFetchOutcome) -> BatchFailure | None:
    error = outcome.error
    if error is None:
        envelope = outcome.result.envelope if outcome.result is not None else None
        if (
            envelope is not None
            and envelope.target == "supplementary"
            and envelope.supplementary is not None
        ):
            status = envelope.supplementary.status
            if status not in {"complete", "degraded"}:
                return BatchFailure(
                    reason_code=status,
                    message="Supplementary acquisition returned " + status,
                    rate_limited=status == RATE_LIMITED,
                )
        return None
    payload = _error_payload(error)
    status = str(payload.get("status") or ERROR)
    retry_after_value = (
        error.retry_after_seconds
        if isinstance(error, (PaperFetchFailure, ProviderFailure))
        else None
    )
    retry_after_seconds = (
        float(retry_after_value)
        if isinstance(retry_after_value, (int, float))
        and not isinstance(retry_after_value, bool)
        else None
    )
    # Cancelling an auth attempt ends the AMS acquisition, while the batch
    # scheduler's ordinary request cancellation keeps its existing semantics.
    cancelled = isinstance(error, RequestCancelledError) and not isinstance(
        error, AuthCancelledError
    )
    return BatchFailure(
        reason_code="request_cancelled" if cancelled else status,
        message=str(payload.get("reason") or error),
        retry_after_seconds=retry_after_seconds,
        rate_limited=status == RATE_LIMITED,
        cancelled=cancelled,
        details=payload,
    )


def _record_from_batch_result(
    options: FetchExecutionOptions,
    batch_result: BatchItemResult[CliBatchItem, CliFetchOutcome],
    *,
    output_dir: Path,
    run_id: UUID,
    tool_version: str,
    deps: ManifestBuilderDependencies,
) -> ManifestRecord:
    item = batch_result.item
    outcome = batch_result.value
    build_context = CliManifestBuildContext(
        options=options,
        output_dir=output_dir,
        run_id=run_id,
        tool_version=tool_version,
        deps=deps,
    )
    if outcome is not None:
        return _build_cli_manifest_record(
            build_context,
            CliManifestAttempt(
                index=item.index,
                query=item.query,
                started_at=outcome.started_at,
                completed_at=outcome.completed_at,
                attempt=item.attempt,
                record_id=deterministic_manifest_record_id(
                    run_id, index=item.index, attempt=item.attempt
                ),
            ),
            result=outcome.result,
            error=outcome.error,
            diagnostic_artifacts=outcome.diagnostic_artifacts,
            aborted=batch_result.status is BatchItemStatus.CANCELLED
            or isinstance(outcome.error, AuthCancelledError),
        )

    completed_at = deps.clock()
    failure = batch_result.failure
    error_payload = _aborted_error_payload(
        reason=(
            failure.message
            if failure is not None
            else "Item was not scheduled by the batch runner."
        ),
        code=failure.reason_code if failure is not None else ERROR,
        retry_after_seconds=(
            failure.retry_after_seconds if failure is not None else None
        ),
    )
    return _build_cli_manifest_record(
        build_context,
        CliManifestAttempt(
            index=item.index,
            query=item.query,
            started_at=completed_at,
            completed_at=completed_at,
            attempt=item.attempt,
            record_id=deterministic_manifest_record_id(
                run_id, index=item.index, attempt=item.attempt
            ),
        ),
        error_payload=error_payload,
        aborted=True,
    )


def run_batch_fetch(
    command: BatchFetchCommand,
    *,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    manifest_deps: ManifestBuilderDependencies | None = None,
    run_id: UUID | None = None,
    tool_version: str | None = None,
) -> int:
    options = command.options
    plan = options.output_plan
    queries = list(command.queries)
    deps = manifest_deps or cli_pkg.DEFAULT_MANIFEST_BUILDER_DEPENDENCIES
    requested_results_path = (
        Path(command.batch_results)
        if command.batch_results
        else output_dir / "batch-results.jsonl"
    )
    effective_tool_version = tool_version or cli_pkg.package_version()
    overwrite = plan.overwrite
    if requested_results_path.exists() and not overwrite:
        raise OutputOverwriteRequired(
            f"refusing to overwrite existing batch results: {requested_results_path}; "
            "rerun with --overwrite"
        )

    active_run_id = run_id or deps.uuid_factory()
    progress = cli_pkg.FetchProgress(options.progress, active_run_id, len(queries))
    controlled = options.control_stdin
    if controlled:
        progress.start_control()
    items = [
        CliBatchItem(
            index=index,
            query=query,
            lane_key=initial_provider_lane(query),
            canonical_doi=expected_doi_from_query(query),
        )
        for index, query in enumerate(queries, start=1)
    ]
    records: dict[int, ManifestRecord] = {}
    records_lock = threading.Lock()
    cancel_event = progress.cancel_all
    duplicates_by_owner: dict[int, tuple[CliBatchItem, ...]] = {}
    with (
        cli_pkg.RuntimeContext(
            env=runtime_env,
            download_dir=output_dir,
            artifact_mode=options.artifact_mode,
            cancel_check=cancel_event.is_set,
        ) as batch_context,
        batch_context.fetch_browser_preparation(prepare=False),
    ):
        session = BatchExecutionSession(
            batch_context,
            items,
            asset_profile=options.asset_profile,
            cancelled=progress.is_cancelled,
        )
        item_contexts = session.contexts

        for item in items:
            item_contexts[item.index].progress_callback = (
                lambda event, data, index=item.index: progress.emit(
                    event, index, **data
                )
            )

        def close_active_contexts() -> None:
            session.close()

        def fence_active_contexts() -> None:
            session.fence()

        try:
            with _cooperative_batch_cancel(cancel_event, close_active_contexts):

                def on_identity_completion(
                    event: BatchCompletionEvent[CliBatchItem, CliBatchItem],
                ) -> None:
                    if event.result.status is not BatchItemStatus.CANCELLED:
                        return
                    cancelled_item = event.result.item
                    cancelled_outcome = BatchItemResult[CliBatchItem, CliFetchOutcome](
                        index=event.result.index,
                        item=cancelled_item,
                        lane_key=event.result.lane_key,
                        status=BatchItemStatus.CANCELLED,
                        value=None,
                        failure=event.result.failure,
                        error=event.result.error,
                        submitted_at=event.result.submitted_at,
                        finished_at=event.result.finished_at,
                    )
                    record = progress.complete(
                        cancelled_item.index,
                        lambda _cancelled: _record_from_batch_result(
                            options,
                            cancelled_outcome,
                            output_dir=output_dir,
                            run_id=active_run_id,
                            tool_version=effective_tool_version,
                            deps=deps,
                        ),
                    )
                    records[cancelled_item.index] = record

                prepared_lanes = session.resolve_all(
                    items,
                    lambda item: cli_pkg._resolve_cli_batch_item_lane(
                        item,
                        context=item_contexts[item.index],
                    ),
                    max_workers=command.batch_concurrency,
                    completion_callback=on_identity_completion,
                    cancel_event=cancel_event,
                    item_cancel_check=(
                        (lambda item: progress.is_cancelled(item.index))
                        if controlled
                        else None
                    ),
                    cancel_escalation_callback=fence_active_contexts,
                )
                logical_items = [
                    result.value if result.value is not None else result.item
                    for result in prepared_lanes.results
                    if result.item.index not in records
                ]
                scheduled_items, duplicates_by_owner = session.group(logical_items)

                auth_failures: dict[Path, Exception] = {}
                for owner in scheduled_items:
                    if owner.lane_key != "ams":
                        continue
                    active_context = item_contexts[owner.index]
                    try:
                        _, cached = _load_cli_fetch_cache(
                            options,
                            query=owner.query,
                            output_dir=output_dir,
                            context=active_context,
                        )
                        if cached is None:
                            path = ams_profile_path(active_context.env or {})
                            if path in auth_failures:
                                raise auth_failures[path]
                            try:
                                _ensure_cli_ams_auth(options, active_context)
                            except RequestCancelledError as exc:
                                if isinstance(exc, AuthCancelledError):
                                    auth_failures[path] = exc
                                raise
                            except Exception as exc:
                                auth_failures[path] = exc
                                raise
                        active_context.set_session_cache(
                            ("cli", "auth-checked", owner.query), True
                        )
                    except Exception as exc:
                        active_context.set_session_cache(
                            ("cli", "auth-error", owner.query), exc, copy_value=False
                        )

                for owner in scheduled_items:
                    group = fanout_batch_items(owner, duplicates_by_owner)
                    indexes = tuple(entry.index for entry in group)
                    active_context = item_contexts[owner.index]

                    def report(
                        event: str,
                        data: Mapping[str, Any],
                        indexes: tuple[int, ...] = indexes,
                    ) -> None:
                        for index in indexes:
                            if not progress.is_cancelled(index):
                                progress.emit(event, index, **data)

                    active_context.progress_callback = report
                    for index in indexes:
                        progress.emit("stage", index, stage="queued")

                def on_completion(
                    event: BatchCompletionEvent[CliBatchItem, CliFetchOutcome],
                ) -> None:
                    for fanout_result in session.fanout(event.result):
                        fanout_item = fanout_result.item

                        def build(
                            cancelled: bool,
                            selected: BatchItemResult[
                                CliBatchItem, CliFetchOutcome
                            ] = fanout_result,
                        ) -> ManifestRecord:
                            if cancelled:
                                selected = replace(
                                    selected,
                                    status=BatchItemStatus.CANCELLED,
                                    value=None,
                                    failure=BatchFailure(
                                        reason_code="request_cancelled",
                                        message="Request cancelled.",
                                        cancelled=True,
                                    ),
                                )
                            return _record_from_batch_result(
                                options,
                                selected,
                                output_dir=output_dir,
                                run_id=active_run_id,
                                tool_version=effective_tool_version,
                                deps=deps,
                            )

                        record = progress.complete(fanout_item.index, build)
                        with records_lock:
                            records[fanout_item.index] = record

                run_result = run_batch(
                    scheduled_items,
                    lambda item: cli_pkg._run_batch_item(
                        item,
                        options=options,
                        output_dir=output_dir,
                        runtime_env=runtime_env,
                        context=item_contexts[item.index],
                        deps=deps,
                    ),
                    max_workers=command.batch_concurrency,
                    lane_key=lambda item: item.lane_key,
                    lane_limits=lambda lane: provider_lane_limit(
                        lane,
                        global_limit=command.batch_concurrency,
                    ),
                    completion_callback=on_completion,
                    result_classifier=_classify_batch_outcome,
                    cancel_event=cancel_event,
                    item_cancel_check=(
                        (lambda item: item_contexts[item.index].cancelled)
                        if controlled
                        else None
                    ),
                    cancel_escalation_callback=fence_active_contexts,
                )
        finally:
            close_active_contexts()

    if run_result.callback_failures:
        details = "; ".join(
            f"index {scheduled_items[failure.source_index].index}: {failure.message}"
            for failure in run_result.callback_failures
        )
        raise OutputDirectoryError(f"could not build complete batch results: {details}")
    if len(records) != len(queries):
        raise OutputDirectoryError("batch runner did not produce one result per input")
    ordered_records = [records[index] for index in sorted(records)]
    body = "".join(
        f"{serialize_manifest_record(record)}\n" for record in ordered_records
    )
    try:
        cli_pkg.ArtifactStore.from_download_dir(output_dir).write_text_file(
            requested_results_path,
            body,
            overwrite=overwrite,
        )
    except FileExistsError as exc:
        raise OutputOverwriteRequired(str(exc)) from exc
    return exit_code_for_batch_results(ordered_records)


def _resolve_fetch_output_dir(
    options: FetchExecutionOptions, runtime_env: Mapping[str, str]
) -> Path:
    configured = options.output_plan.output_dir
    if configured is not None:
        base_dir = configured
    elif options.prefer_cache:
        base_dir = cli_pkg.resolve_cli_download_dir(runtime_env)
    else:
        base_dir = Path(tempfile.mkdtemp(prefix="paper-fetch-read-"))
    return base_dir.expanduser().resolve()


def run_single_fetch_command(command: SingleFetchCommand) -> int:
    """Execute a validated single-paper CLI fetch command."""

    options = command.options
    manifest_deps = cli_pkg.DEFAULT_MANIFEST_BUILDER_DEPENDENCIES
    manifest_run_id = manifest_deps.uuid_factory()
    manifest_tool_version = cli_pkg.package_version()
    manifest_started_at = manifest_deps.clock()
    progress = cli_pkg.FetchProgress(options.progress, manifest_run_id, 1)
    if options.control_stdin:
        progress.start_control()

    output_dir: Path | None = None
    try:
        runtime_env = cli_pkg.build_runtime_env()
        output_dir = _resolve_fetch_output_dir(options, runtime_env)
        prepare_output_dir(output_dir)
        with cli_pkg.RuntimeContext(
            env=runtime_env,
            download_dir=output_dir,
            artifact_mode=options.artifact_mode,
            asset_profile=options.asset_profile,
            cancel_check=lambda: progress.is_cancelled(1),
            progress_callback=lambda event, data: progress.emit(event, 1, **data),
        ) as context:
            with _cooperative_batch_cancel(progress.cancel_all, context.close):
                result = cli_pkg.run_single_fetch(
                    options,
                    query=command.query,
                    output_dir=output_dir,
                    runtime_env=runtime_env,
                    context=context,
                )
        with progress.lock:
            if progress.is_cancelled(1):
                raise RequestCancelledError("Request cancelled.")
            if command.manifest:
                _validate_single_manifest_target(command.manifest, result)
            record = _build_cli_manifest_record(
                CliManifestBuildContext(
                    options=options,
                    output_dir=output_dir,
                    run_id=manifest_run_id,
                    tool_version=manifest_tool_version,
                    deps=manifest_deps,
                ),
                CliManifestAttempt(
                    index=1,
                    query=command.query,
                    started_at=manifest_started_at,
                    completed_at=manifest_deps.clock(),
                ),
                result=result,
            )
            if command.manifest:
                _write_single_cli_manifest(
                    command.manifest,
                    record,
                    overwrite=options.output_plan.overwrite,
                )
            progress.complete(1, lambda _cancelled: record)
        if (
            result.envelope.target == "supplementary"
            and result.envelope.supplementary is not None
            and result.envelope.supplementary.status not in {"complete", "degraded"}
        ):
            return 1
        return int(not target_satisfied(record))
    except Exception as exc:
        if output_dir is not None:
            _write_single_failure_manifest(
                command,
                exc,
                output_dir=output_dir,
                run_id=manifest_run_id,
                tool_version=manifest_tool_version,
                started_at=manifest_started_at,
                deps=manifest_deps,
                progress=progress,
            )
        if isinstance(exc, (OutputDirectoryError, PaperFetchFailure, ProviderFailure)):
            cli_pkg.sys.stderr.write(
                json.dumps(_error_payload(exc), ensure_ascii=False) + "\n"
            )
            return 1
        if isinstance(exc, RequestCancelledError):
            return 1
        raise


def run_batch_fetch_command(command: BatchFetchCommand) -> int:
    """Execute a validated batch CLI fetch command."""

    manifest_deps = cli_pkg.DEFAULT_MANIFEST_BUILDER_DEPENDENCIES
    try:
        runtime_env = cli_pkg.build_runtime_env()
        output_dir = _resolve_fetch_output_dir(command.options, runtime_env)
        prepare_output_dir(output_dir)
        return cli_pkg.run_batch_fetch(
            command,
            output_dir=output_dir,
            runtime_env=runtime_env,
            manifest_deps=manifest_deps,
        )
    except (OutputDirectoryError, PaperFetchFailure, ProviderFailure) as exc:
        cli_pkg.sys.stderr.write(
            json.dumps(_error_payload(exc), ensure_ascii=False) + "\n"
        )
        return 1
    except RequestCancelledError:
        return 1
