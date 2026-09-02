"""CLI entrypoint for paper-fetch."""

from __future__ import annotations

import argparse
import copy
import contextlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
import json
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from .auth import (
    authenticate_provider_profile,
    browser_auth_provider_names,
)
from .artifacts import ArtifactMode, ArtifactStore
from .browser_preflight import (
    BrowserPreflightResult,
    BrowserPreflightRuntimeOptions,
    browser_preflight_next_action,
    run_browser_provider_preflight,
)
from .provider_catalog import browser_preflight_provider_names
from .config import build_runtime_env, resolve_cli_download_dir
from .diagnostics import (
    doctor_payload as build_doctor_payload,
    provider_status_group_names,
    provider_status_provider_names,
)
from .http import RequestCancelledError
from .manifest import (
    DEFAULT_MANIFEST_BUILDER_DEPENDENCIES,
    ManifestBuilderDependencies,
    ManifestOutputArtifactSpec,
    ManifestRecord,
    build_manifest_record,
)
from .manifest_writer import (
    deterministic_manifest_record_id,
    serialize_manifest_record,
    write_manifest_record,
)
from .models import FetchEnvelope, OutputMode, RenderOptions
from .providers.base import ProviderFailure
from .reason_codes import ERROR, NO_ACCESS, RATE_LIMITED
from .runtime import (
    RuntimeContext,
    build_http_transport_for_context,
)
from .service import FetchStrategy, PaperFetchFailure, fetch_paper, resolve_paper
from .tracing import merge_trace, trace_from_markers
from .utils import (
    _extract_year,
    format_paper_stem,
    normalize_text,
    provider_display_name,
)
from .version import package_version
from .workflow.batch_runner import (
    BatchCompletionEvent,
    BatchFailure,
    BatchItemResult,
    BatchItemStatus,
    run_batch,
)
from .workflow.batch_routing import (
    deduplicate_batch_items,
    expected_doi_from_query,
    fanout_batch_items,
    initial_provider_lane,
    provider_lane_limit,
    resolve_batch_item_routing,
)
from .workflow.pipeline import FetchPipeline, FetchPipelineRequest
from .workflow.rendering import rewrite_markdown_asset_links
from .workflow.rendering import (
    save_markdown_to_disk as save_markdown_to_disk_for_target,
)


@dataclass(frozen=True)
class SingleFetchResult:
    envelope: FetchEnvelope
    output_path: Path | None = None
    saved_markdown_path: Path | None = None


@dataclass(frozen=True)
class CliBatchItem:
    """One 1-based CLI input plus its statically inferred scheduling lane."""

    index: int
    query: str
    lane_key: str
    attempt: int = 1
    canonical_doi: str | None = None


@dataclass(frozen=True)
class CliFetchOutcome:
    """Wall-clock attempt facts retained when a batch worker fails."""

    started_at: datetime
    completed_at: datetime
    result: SingleFetchResult | None = None
    error: Exception | None = None
    diagnostic_artifacts: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CliManifestBuildContext:
    """Shared immutable inputs for one CLI manifest record."""

    args: argparse.Namespace
    output_dir: Path
    artifact_mode: ArtifactMode
    run_id: UUID
    tool_version: str
    deps: ManifestBuilderDependencies


@dataclass(frozen=True)
class CliManifestAttempt:
    """Identity and timing facts for one CLI manifest attempt."""

    index: int
    query: str
    started_at: datetime
    completed_at: datetime
    attempt: int = 1
    record_id: UUID | None = None


class OutputDirectoryError(Exception):
    """Raised when the CLI output directory cannot be prepared."""


class ManifestWriteError(OutputDirectoryError):
    """Raised when an explicitly requested CLI manifest cannot be written."""


class ManifestTargetConflict(OutputDirectoryError):
    """Raised when a manifest would overwrite a recorded output artifact."""


class OutputOverwriteRequired(OutputDirectoryError):
    """Raised when replacing an existing final artifact needs permission."""


SubcommandRegistrar = Callable[[argparse._SubParsersAction], None]


@contextlib.contextmanager
def _cooperative_batch_cancel(
    cancel_event: threading.Event,
    close_active_contexts: Callable[[], None],
):
    if threading.current_thread() is not threading.main_thread() or not hasattr(
        signal, "SIGINT"
    ):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGINT)

    def handle_interrupt(_signum, _frame) -> None:
        if cancel_event.is_set():
            close_active_contexts()
            raise KeyboardInterrupt
        cancel_event.set()
        print(
            "Cancellation requested; waiting for active batch workers to stop. "
            "Press Ctrl-C again to force browser shutdown.",
            file=sys.stderr,
        )

    signal.signal(signal.SIGINT, handle_interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous_handler)


def save_markdown_to_disk(
    envelope: FetchEnvelope, *, output_dir: Path, render: RenderOptions
) -> Path | None:
    return save_markdown_to_disk_for_target(
        envelope,
        output_dir=output_dir,
        render=render,
        request_label="--save-markdown",
    )


def serialize_envelope(
    envelope: FetchEnvelope, *, output_format: str, markdown_override: str | None = None
) -> str:
    if output_format == "markdown":
        return (
            markdown_override
            if markdown_override is not None
            else envelope.markdown or ""
        )
    if output_format == "json":
        if envelope.article is None:
            raise ValueError("CLI json output requires the article payload.")
        return envelope.article.to_json()
    if envelope.article is None:
        raise ValueError("CLI both output requires the article payload.")
    markdown = markdown_override if markdown_override is not None else envelope.markdown
    return json.dumps(
        {"article": envelope.article.to_dict(), "markdown": markdown},
        ensure_ascii=False,
        indent=2,
    )


def write_output(
    serialized: str,
    output: str,
    *,
    overwrite: bool = True,
    commit_guard: Callable[[], None] | None = None,
) -> None:
    if commit_guard is not None:
        commit_guard()
    if output == "-":
        sys.stdout.write(serialized)
        if not serialized.endswith("\n"):
            sys.stdout.write("\n")
        return
    target = Path(output)
    if not target.parent.is_dir():
        # Preserve the legacy failure contract for an absent explicit parent.
        target.write_text(serialized, encoding="utf-8")
        return
    ArtifactStore.from_download_dir(
        target.parent,
        commit_guard=commit_guard,
    ).write_text_file(
        target,
        serialized,
        encoding="utf-8",
        overwrite=overwrite,
    )


def prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise OutputDirectoryError(
            f"output directory path exists but is not a directory: {output_dir}"
        )
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputDirectoryError(
            f"could not create output directory {output_dir}: {exc}"
        ) from exc
    if not output_dir.is_dir():
        raise OutputDirectoryError(
            f"output directory path exists but is not a directory: {output_dir}"
        )
    if not os.access(output_dir, os.W_OK | os.X_OK):
        raise OutputDirectoryError(f"output directory is not writable: {output_dir}")


def _has_explicit_option(argv: list[str], option: str) -> bool:
    return any(value == option or value.startswith(f"{option}=") for value in argv)


def _should_save_formatted_output_copy(
    args: argparse.Namespace,
    *,
    explicit_format: bool,
    output_is_explicit: bool,
    artifact_mode: ArtifactMode,
) -> bool:
    if not (
        explicit_format
        and output_is_explicit
        and args.output == "-"
        and args.output_dir
    ):
        return False
    if artifact_mode == "all":
        return True
    return artifact_mode == "markdown-assets" and args.format == "markdown"


def _should_write_primary_output_to_output_dir(args: argparse.Namespace) -> bool:
    return bool(args.output_dir and not getattr(args, "output_is_explicit", False))


def _should_save_markdown_via_pipeline(
    args: argparse.Namespace,
    *,
    artifact_mode: ArtifactMode,
) -> bool:
    if args.save_markdown:
        return True
    if artifact_mode != "markdown-assets":
        return False
    primary_output_to_output_dir = getattr(args, "primary_output_to_output_dir", False)
    if args.output != "-" and not primary_output_to_output_dir:
        return False
    return not (
        args.format == "markdown"
        and (getattr(args, "save_output_copy", False) or primary_output_to_output_dir)
    )


def _formatted_output_filename(
    envelope: FetchEnvelope,
    *,
    output_format: str,
    fallback_query: str | None = None,
) -> str:
    meta = (
        envelope.article.metadata if envelope.article is not None else envelope.metadata
    )
    authors = list(meta.authors) if meta and meta.authors else None
    year = _extract_year(meta.published if meta else None)
    title = meta.title if meta else None
    doi = envelope.doi or (
        _expected_doi_for_query(fallback_query) if fallback_query else None
    )
    normalized_query = normalize_text(fallback_query)
    if not title and not doi and normalized_query:
        query_digest = sha256(normalized_query.encode("utf-8")).hexdigest()[:16]
        title = f"article_{query_digest}"
    stem = format_paper_stem(authors, year, title, doi=doi)
    suffix = {
        "markdown": ".md",
        "json": ".json",
        "both": ".both.json",
    }[output_format]
    return f"{stem}{suffix}"


def _same_output_path(left: Path | None, right: Path) -> bool:
    return left is not None and left.resolve(strict=False) == right.resolve(
        strict=False
    )


def save_formatted_output_copy(
    envelope: FetchEnvelope,
    *,
    output_dir: Path,
    output_format: str,
    render: RenderOptions,
    overwrite: bool = True,
    fallback_query: str | None = None,
    commit_guard: Callable[[], None] | None = None,
) -> Path:
    target = output_dir / _formatted_output_filename(
        envelope,
        output_format=output_format,
        fallback_query=fallback_query,
    )
    markdown_override = (
        rewrite_markdown_asset_links(
            envelope.markdown or "",
            envelope,
            target_path=target,
            render=render,
        )
        if output_format in {"markdown", "both"}
        else None
    )
    serialized = serialize_envelope(
        envelope, output_format=output_format, markdown_override=markdown_override
    )
    return ArtifactStore.from_download_dir(
        output_dir,
        commit_guard=commit_guard,
    ).write_text_file(
        target,
        serialized,
        encoding="utf-8",
        overwrite=overwrite,
    )


def parse_max_tokens(value: str) -> int | str:
    normalized = value.strip().lower()
    if normalized == "full_text":
        return "full_text"
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "max_tokens must be a positive integer or 'full_text'."
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("max_tokens must be greater than 0.")
    return parsed


def parse_batch_concurrency(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "batch-concurrency must be an integer from 1 to 8."
        ) from exc
    if not 1 <= parsed <= 8:
        raise argparse.ArgumentTypeError(
            "batch-concurrency must be an integer from 1 to 8."
        )
    return parsed


def parse_positive_int_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer.")
    return parsed


def read_query_file(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read query file {path}: {exc}") from exc

    queries = []
    for line in lines:
        query = line.strip()
        if not query or query.startswith("#"):
            continue
        queries.append(query)
    if not queries:
        raise ValueError(
            "query file did not contain any queries after filtering blank lines and comments."
        )
    return queries


def _compute_modes(args: argparse.Namespace) -> set[OutputMode]:
    modes: set[OutputMode] = {"markdown"} if args.format == "markdown" else {"article"}
    save_markdown_to_disk = getattr(
        args,
        "save_markdown_to_disk",
        getattr(args, "save_markdown", False),
    )

    # Writing Markdown to a file or saving an extra Markdown copy needs the
    # structured article payload so we can rewrite local asset links relative
    # to the target path and decide whether full text was actually usable.
    if args.format == "markdown" and (
        args.output != "-"
        or getattr(args, "save_output_copy", False)
        or getattr(args, "primary_output_to_output_dir", False)
    ):
        modes.add("article")
    if args.format == "both" or save_markdown_to_disk:
        modes.add("markdown")
    if save_markdown_to_disk:
        modes.add("article")
    return modes


def _effective_artifact_mode(args: argparse.Namespace) -> ArtifactMode:
    return args.artifact_mode


def exit_code_for_error(error: Exception) -> int:
    if isinstance(error, PaperFetchFailure):
        status = error.status
    elif isinstance(error, ProviderFailure):
        status = error.code
    else:
        status = ERROR

    if status == "ambiguous":
        return 2
    if status == NO_ACCESS:
        return 3
    if status == RATE_LIMITED:
        return 4
    return 1


def _error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
            "provider": error.provider,
            "route": error.route,
            "stage": error.stage,
            "http_status": error.http_status,
            "error_category": error.error_category,
            "retryable": error.retryable,
            "retry_after_seconds": error.retry_after_seconds,
            "details": error.details,
            "warnings": error.warnings,
            "source_trail": error.source_trail,
        }
    if isinstance(error, ProviderFailure):
        return {
            "status": error.code,
            "reason": error.message,
            "provider": error.provider,
            "route": error.route,
            "stage": error.stage,
            "http_status": error.http_status,
            "error_category": error.error_category,
            "retryable": error.retryable,
            "retry_after_seconds": error.retry_after_seconds,
            "details": error.details,
            "warnings": error.warnings,
            "source_trail": error.source_trail,
        }
    return {"status": ERROR, "reason": str(error)}


def _render_options_from_args(args: argparse.Namespace) -> RenderOptions:
    return RenderOptions(
        include_refs=args.include_refs,
        asset_profile=args.asset_profile,
        max_tokens=args.max_tokens,
    )


def run_single_fetch(
    args: argparse.Namespace,
    *,
    query: str,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
    transport=None,
    cancel_check: Callable[[], bool] | None = None,
    context: RuntimeContext | None = None,
) -> SingleFetchResult:
    """Run one complete fetch/output transaction in one runtime context."""

    owns_context = context is None
    active_context = context or RuntimeContext(
        env=runtime_env,
        transport=transport,
        download_dir=output_dir,
        artifact_mode=artifact_mode,
        asset_profile=args.asset_profile,
        cancel_check=cancel_check,
    )
    try:
        return _run_single_fetch_with_context(
            args,
            query=query,
            output_dir=output_dir,
            runtime_env=runtime_env,
            artifact_mode=artifact_mode,
            transport=transport,
            cancel_check=cancel_check,
            context=active_context,
        )
    finally:
        if owns_context:
            active_context.close()


def _run_single_fetch_with_context(
    args: argparse.Namespace,
    *,
    query: str,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
    transport=None,
    cancel_check: Callable[[], bool] | None = None,
    context: RuntimeContext,
) -> SingleFetchResult:
    modes = _compute_modes(args)
    render_options = _render_options_from_args(args)
    overwrite = bool(getattr(args, "overwrite", False))
    try:
        envelope = FetchPipeline(fetch_paper).run(
            FetchPipelineRequest(
                query=query,
                modes=modes,
                strategy=FetchStrategy(
                    allow_metadata_only_fallback=True,
                    asset_profile=args.asset_profile,
                    require_local_body_assets=bool(
                        getattr(args, "require_local_body_assets", False)
                    ),
                    require_full_size_body_assets=bool(
                        getattr(args, "require_full_size_body_assets", False)
                    ),
                ),
                render=render_options,
            ),
            context=context,
        )
        saved_markdown_path = None
        if args.save_markdown_to_disk:
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
    if args.primary_output_to_output_dir:
        target = output_dir / _formatted_output_filename(
            envelope,
            output_format=args.format,
            fallback_query=query,
        )
        if args.format == "markdown" and _same_output_path(saved_markdown_path, target):
            primary_output_path = target
        else:
            try:
                primary_output_path = save_formatted_output_copy(
                    envelope,
                    output_dir=output_dir,
                    output_format=args.format,
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
        rewrite_markdown_asset_links(
            envelope.markdown or "",
            envelope,
            target_path=Path(args.output),
            render=render_options,
        )
        if args.output != "-" and args.format in {"markdown", "both"}
        else None
    )
    serialized = serialize_envelope(
        envelope, output_format=args.format, markdown_override=markdown_override
    )
    output_path: Path | None = None
    if args.save_output_copy:
        target = output_dir / _formatted_output_filename(
            envelope,
            output_format=args.format,
            fallback_query=query,
        )
        if args.format == "markdown" and _same_output_path(saved_markdown_path, target):
            output_path = target
        else:
            try:
                output_path = save_formatted_output_copy(
                    envelope,
                    output_dir=output_dir,
                    output_format=args.format,
                    render=render_options,
                    overwrite=overwrite,
                    fallback_query=query,
                    commit_guard=context.commit_guard,
                )
            except FileExistsError as exc:
                raise OutputOverwriteRequired(
                    f"{exc}; rerun with --overwrite after reviewing the existing output"
                ) from exc
    explicit_target = Path(args.output)
    if not (
        args.output != "-"
        and args.format == "markdown"
        and _same_output_path(saved_markdown_path, explicit_target)
    ):
        try:
            write_output(
                serialized,
                args.output,
                overwrite=overwrite,
                commit_guard=context.commit_guard,
            )
        except FileExistsError as exc:
            raise OutputOverwriteRequired(
                f"{exc}; rerun with --overwrite after reviewing the existing output"
            ) from exc
    if args.output != "-":
        output_path = Path(args.output)
    return SingleFetchResult(
        envelope=envelope,
        output_path=output_path,
        saved_markdown_path=saved_markdown_path,
    )


def _manifest_request_parameters(
    args: argparse.Namespace,
    *,
    output_dir: Path,
    artifact_mode: ArtifactMode,
) -> dict[str, Any]:
    """Return the CLI request semantics covered by the shared fingerprint."""

    return {
        "modes": sorted(_compute_modes(args)),
        "format": args.format,
        "strategy": {
            "allow_metadata_only_fallback": True,
            "asset_profile": args.asset_profile,
            "require_local_body_assets": bool(
                getattr(args, "require_local_body_assets", False)
                or getattr(args, "require_full_size_body_assets", False)
            ),
            "require_full_size_body_assets": bool(
                getattr(args, "require_full_size_body_assets", False)
            ),
        },
        "render": {
            "include_refs": args.include_refs,
            "asset_profile": args.asset_profile,
            "max_tokens": args.max_tokens,
        },
        "artifact_mode": artifact_mode,
        "no_download": False,
        "save_markdown": bool(args.save_markdown_to_disk),
        "output": args.output,
        "output_dir": str(output_dir),
        "primary_output_to_output_dir": bool(
            getattr(args, "primary_output_to_output_dir", False)
        ),
        "save_output_copy": bool(getattr(args, "save_output_copy", False)),
    }


_expected_doi_for_query = expected_doi_from_query
_batch_lane_for_query = initial_provider_lane


def _resolve_cli_batch_item_lane(
    item: CliBatchItem,
    *,
    context: RuntimeContext,
) -> CliBatchItem:
    return resolve_batch_item_routing(
        item,
        context=context,
        resolver=resolve_paper,
    )


def _manifest_output_artifacts(
    args: argparse.Namespace,
    result: SingleFetchResult,
) -> tuple[ManifestOutputArtifactSpec, ...]:
    artifacts: list[ManifestOutputArtifactSpec] = []
    if result.output_path is not None:
        artifacts.append(
            ManifestOutputArtifactSpec(
                path=str(result.output_path),
                kind={
                    "markdown": "primary_markdown",
                    "json": "primary_json",
                    "both": "primary_both",
                }[args.format],
            )
        )
    if result.saved_markdown_path is not None:
        artifacts.append(
            ManifestOutputArtifactSpec(
                path=str(result.saved_markdown_path),
                kind="saved_markdown",
            )
        )
    for diagnostic in result.envelope.diagnostic_artifacts:
        path = str(diagnostic.get("path") or "").strip()
        if not path:
            continue
        artifacts.append(
            ManifestOutputArtifactSpec(
                path=path,
                kind="diagnostic",
                route=str(diagnostic.get("route") or "") or None,
                failure_code=(str(diagnostic.get("failure_code") or "") or None),
            )
        )
    return tuple(artifacts)


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
    }
    if retry_after_seconds is not None:
        payload["retry_after_seconds"] = retry_after_seconds
    return payload


def _build_cli_manifest_record(
    context: CliManifestBuildContext,
    attempt: CliManifestAttempt,
    *,
    result: SingleFetchResult | None = None,
    error: Exception | None = None,
    error_payload: Mapping[str, Any] | None = None,
    diagnostic_artifacts: Sequence[Mapping[str, Any]] = (),
    aborted: bool = False,
) -> ManifestRecord:
    """Adapt CLI attempt facts to the sole PF-004 record builder."""

    args = context.args
    if result is not None:
        envelope = result.envelope
        manifest_error = None
        warnings: Sequence[str] | None = None
        trace = None
        candidate_count = 0
        artifacts = _manifest_output_artifacts(args, result)
    else:
        envelope = None
        if error_payload is not None:
            manifest_error = dict(error_payload)
        elif error is not None:
            manifest_error = _error_payload(error)
        else:
            manifest_error = {"status": ERROR, "reason": "Unknown CLI failure."}
        if aborted and manifest_error.get("status") != "aborted":
            code = (
                "request_cancelled"
                if isinstance(error, RequestCancelledError)
                else str(manifest_error.get("code") or manifest_error["status"])
            )
            manifest_error = _aborted_error_payload(
                reason=str(manifest_error["reason"]),
                code=code,
            )
        warnings = tuple(str(item) for item in (getattr(error, "warnings", ()) or ()))
        source_trail = tuple(
            str(item) for item in (getattr(error, "source_trail", ()) or ())
        )
        structured_error_trace = list(getattr(error, "trace", ()) or ())
        trace = merge_trace(trace_from_markers(source_trail), structured_error_trace)
        if not trace:
            trace = None
        candidate_count = (
            len(error.candidates) if isinstance(error, PaperFetchFailure) else 0
        )
        artifacts = tuple(
            ManifestOutputArtifactSpec(
                path=str(item.get("path")),
                kind="diagnostic",
                route=str(item.get("route") or "") or None,
                failure_code=str(item.get("failure_code") or "") or None,
            )
            for item in diagnostic_artifacts
            if str(item.get("path") or "").strip()
        )

    return build_manifest_record(
        tool_version=context.tool_version,
        run_id=context.run_id,
        record_id=attempt.record_id,
        index=attempt.index,
        attempt=attempt.attempt,
        query=attempt.query,
        request_parameters=_manifest_request_parameters(
            args,
            output_dir=context.output_dir,
            artifact_mode=context.artifact_mode,
        ),
        asset_profile=args.asset_profile,
        envelope=envelope,
        error=manifest_error,
        aborted=aborted,
        requested_outputs=_compute_modes(args),
        candidate_count=candidate_count,
        expected_doi=_expected_doi_for_query(attempt.query),
        output_artifacts=artifacts,
        trace=trace,
        warnings=warnings,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        deps=context.deps,
    )


def _run_batch_item(
    item: CliBatchItem,
    *,
    args: argparse.Namespace,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
    context: RuntimeContext,
    deps: ManifestBuilderDependencies,
) -> CliFetchOutcome:
    started_at = deps.clock()
    try:
        context.reset_request_deadline()
        result = run_single_fetch(
            args,
            query=item.query,
            output_dir=output_dir,
            runtime_env=runtime_env,
            artifact_mode=artifact_mode,
            context=context,
        )
    except Exception as exc:  # noqa: BLE001 - every batch input gets a terminal record.
        return CliFetchOutcome(
            started_at=started_at,
            completed_at=deps.clock(),
            error=exc,
            diagnostic_artifacts=tuple(
                dict(item) for item in context.diagnostic_artifacts
            ),
        )
    else:
        return CliFetchOutcome(
            started_at=started_at,
            completed_at=deps.clock(),
            result=result,
            diagnostic_artifacts=tuple(
                dict(item) for item in context.diagnostic_artifacts
            ),
        )
    finally:
        context.close()


def _classify_batch_outcome(outcome: CliFetchOutcome) -> BatchFailure | None:
    error = outcome.error
    if error is None:
        return None
    payload = _error_payload(error)
    status = str(payload.get("status") or ERROR)
    retry_after_value = getattr(error, "retry_after_seconds", None)
    retry_after_seconds = (
        float(retry_after_value)
        if isinstance(retry_after_value, (int, float))
        and not isinstance(retry_after_value, bool)
        else None
    )
    cancelled = isinstance(error, RequestCancelledError)
    return BatchFailure(
        reason_code="request_cancelled" if cancelled else status,
        message=str(payload.get("reason") or error),
        retry_after_seconds=retry_after_seconds,
        rate_limited=status == RATE_LIMITED,
        cancelled=cancelled,
        details=payload,
    )


def _record_from_batch_result(
    args: argparse.Namespace,
    batch_result: BatchItemResult[CliBatchItem, CliFetchOutcome],
    *,
    output_dir: Path,
    artifact_mode: ArtifactMode,
    run_id: UUID,
    tool_version: str,
    deps: ManifestBuilderDependencies,
) -> ManifestRecord:
    item = batch_result.item
    outcome = batch_result.value
    build_context = CliManifestBuildContext(
        args=args,
        output_dir=output_dir,
        artifact_mode=artifact_mode,
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
            aborted=batch_result.status is BatchItemStatus.CANCELLED,
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


def exit_code_for_batch_results(
    results: Sequence[ManifestRecord | Mapping[str, Any]],
) -> int:
    statuses = [
        (
            ("ok" if item.error is None else item.error.status)
            if isinstance(item, ManifestRecord)
            else str(item.get("status"))
        )
        for item in results
    ]
    failure_statuses = {status for status in statuses if status != "ok"}
    if not failure_statuses:
        return 0
    for status, exit_code in (
        (NO_ACCESS, 3),
        (RATE_LIMITED, 4),
        ("ambiguous", 2),
    ):
        if status in failure_statuses:
            return exit_code
    return 1


def run_batch_fetch(
    args: argparse.Namespace,
    *,
    queries: list[str],
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
    manifest_deps: ManifestBuilderDependencies | None = None,
    run_id: UUID | None = None,
    tool_version: str | None = None,
) -> int:
    deps = manifest_deps or DEFAULT_MANIFEST_BUILDER_DEPENDENCIES
    requested_results_path = (
        Path(args.batch_results)
        if args.batch_results
        else output_dir / "batch-results.jsonl"
    )
    effective_tool_version = tool_version or package_version()
    overwrite = bool(getattr(args, "overwrite", False))
    if requested_results_path.exists() and not overwrite:
        raise OutputOverwriteRequired(
            f"refusing to overwrite existing batch results: {requested_results_path}; "
            "rerun with --overwrite"
        )

    active_run_id = run_id or deps.uuid_factory()
    items = [
        CliBatchItem(
            index=index,
            query=query,
            lane_key=_batch_lane_for_query(query),
            canonical_doi=_expected_doi_for_query(query),
        )
        for index, query in enumerate(queries, start=1)
    ]
    records: dict[int, ManifestRecord] = {}
    records_lock = threading.Lock()
    cancel_event = threading.Event()
    shared_transport = build_http_transport_for_context(
        runtime_env,
        download_dir=output_dir,
        cancel_check=cancel_event.is_set,
        artifact_mode=artifact_mode,
    )
    with RuntimeContext(
        env=runtime_env,
        transport=shared_transport,
        download_dir=output_dir,
        artifact_mode=artifact_mode,
        cancel_check=cancel_event.is_set,
    ) as batch_context:
        item_contexts = {
            item.index: batch_context.new_request_context(
                asset_profile=args.asset_profile,
            )
            for item in items
        }

        def close_active_contexts() -> None:
            for active_context in item_contexts.values():
                active_context.close()

        try:
            with _cooperative_batch_cancel(cancel_event, close_active_contexts):
                prepared_lanes = run_batch(
                    items,
                    lambda item: _resolve_cli_batch_item_lane(
                        item,
                        context=item_contexts[item.index],
                    ),
                    max_workers=args.batch_concurrency,
                    lane_key=lambda item: f"resolve:{item.index}",
                    cancel_event=cancel_event,
                )
                logical_items = [
                    result.value if result.value is not None else result.item
                    for result in prepared_lanes.results
                ]
                scheduled_items, duplicates_by_owner = deduplicate_batch_items(
                    logical_items
                )

                def on_completion(
                    event: BatchCompletionEvent[CliBatchItem, CliFetchOutcome],
                ) -> None:
                    fanout_items = fanout_batch_items(
                        event.result.item,
                        duplicates_by_owner,
                    )
                    for position, fanout_item in enumerate(fanout_items):
                        outcome = event.result.value
                        if position and outcome is not None:
                            with contextlib.suppress(Exception):
                                outcome = copy.deepcopy(outcome)
                        fanout_result = replace(
                            event.result,
                            item=fanout_item,
                            lane_key=fanout_item.lane_key,
                            value=outcome,
                        )
                        record = _record_from_batch_result(
                            args,
                            fanout_result,
                            output_dir=output_dir,
                            artifact_mode=artifact_mode,
                            run_id=active_run_id,
                            tool_version=effective_tool_version,
                            deps=deps,
                        )
                        with records_lock:
                            records[fanout_item.index] = record

                run_result = run_batch(
                    scheduled_items,
                    lambda item: _run_batch_item(
                        item,
                        args=args,
                        output_dir=output_dir,
                        runtime_env=runtime_env,
                        artifact_mode=artifact_mode,
                        context=item_contexts[item.index],
                        deps=deps,
                    ),
                    max_workers=args.batch_concurrency,
                    lane_key=lambda item: item.lane_key,
                    lane_limits=lambda lane: provider_lane_limit(
                        lane,
                        global_limit=args.batch_concurrency,
                    ),
                    completion_callback=on_completion,
                    result_classifier=_classify_batch_outcome,
                    cancel_event=cancel_event,
                    cancel_escalation_callback=close_active_contexts,
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
        ArtifactStore.from_download_dir(output_dir).write_text_file(
            requested_results_path,
            body,
            overwrite=overwrite,
        )
    except FileExistsError as exc:
        raise OutputOverwriteRequired(str(exc)) from exc
    return exit_code_for_batch_results(ordered_records)


def _default(value: Any, *, suppress_defaults: bool) -> Any:
    return argparse.SUPPRESS if suppress_defaults else value


def _add_fetch_arguments(
    parser: argparse.ArgumentParser,
    *,
    suppress_defaults: bool,
) -> None:
    """Register the current fetch flags on a parser."""
    query_group = parser.add_mutually_exclusive_group()
    query_group.add_argument(
        "--query",
        default=_default(None, suppress_defaults=suppress_defaults),
        help="DOI, paper landing URL, or title query",
    )
    query_group.add_argument(
        "--query-file",
        default=_default(None, suppress_defaults=suppress_defaults),
        help="Batch mode: read one DOI, paper landing URL, or title query per line.",
    )
    parser.add_argument(
        "--batch-concurrency",
        type=parse_batch_concurrency,
        default=_default(1, suppress_defaults=suppress_defaults),
        help="Maximum concurrent fetches for --query-file batch mode (1-8; default: 1).",
    )
    parser.add_argument(
        "--batch-results",
        default=_default(None, suppress_defaults=suppress_defaults),
        help="JSONL summary path for --query-file batch mode. Defaults to <output-dir>/batch-results.jsonl.",
    )
    parser.add_argument(
        "--manifest",
        default=_default(None, suppress_defaults=suppress_defaults),
        help=(
            "Single-paper schema-v2 manifest path. No manifest is written by "
            "default; batch mode uses --batch-results."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=_default(False, suppress_defaults=suppress_defaults),
        help=("Allow replacement of existing final outputs and batch results."),
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "both"),
        default=_default("markdown", suppress_defaults=suppress_defaults),
        help=(
            "Serialization format for stdout, --output, or the default file under --output-dir "
            "when --output is omitted (default: markdown)."
        ),
    )
    parser.add_argument(
        "--output",
        default=_default("-", suppress_defaults=suppress_defaults),
        help=(
            "Output destination (default: - for stdout). Omit with --output-dir "
            "to write a default file there."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=_default(None, suppress_defaults=suppress_defaults),
        help=(
            "Directory for the default formatted output when --output is omitted, plus Markdown, "
            "PDF fallback sources, and assets. Defaults to PAPER_FETCH_DOWNLOAD_DIR or the user "
            "data downloads directory."
        ),
    )
    parser.add_argument(
        "--artifact-mode",
        choices=("markdown-assets", "all", "none"),
        default=_default("markdown-assets", suppress_defaults=suppress_defaults),
        help=(
            "Controls local artifact retention. markdown-assets saves Markdown plus assets from "
            "--asset-profile and keeps PDF fallback sources; all preserves raw provider/cache "
            "artifacts; none disables provider artifacts and assets (default: markdown-assets)."
        ),
    )
    parser.add_argument(
        "--save-markdown",
        action="store_true",
        default=_default(False, suppress_defaults=suppress_defaults),
        help=(
            "Also write the rendered AI Markdown full text to disk (defaults to PAPER_FETCH_DOWNLOAD_DIR "
            "or the user data downloads directory, "
            "overridable via --output-dir). Only writes when full text was actually retrieved. "
            "For Wiley the preferred Markdown route is provider-managed HTML; TDM or browser PDF/ePDF "
            "fallbacks may be lower fidelity than Elsevier XML or publisher-managed HTML."
        ),
    )
    parser.add_argument(
        "--include-refs",
        choices=("none", "top10", "all"),
        default=_default(None, suppress_defaults=suppress_defaults),
        help=(
            "Reference rendering mode for Markdown output. Defaults to all for full_text "
            "and top10 for numeric --max-tokens."
        ),
    )
    parser.add_argument(
        "--asset-profile",
        choices=("none", "body", "all"),
        default=_default("body", suppress_defaults=suppress_defaults),
        help=(
            "Local content asset scope: none skips asset downloads, body saves body "
            "figures/tables/formula images, all also saves supplementary assets "
            "(default: body)."
        ),
    )
    parser.add_argument(
        "--require-local-body-assets",
        action="store_true",
        default=_default(False, suppress_defaults=suppress_defaults),
        help=(
            "Degrade acceptance unless every discovered body asset is archived "
            "locally. Applies only to --asset-profile body or all."
        ),
    )
    parser.add_argument(
        "--require-full-size-body-assets",
        action="store_true",
        default=_default(False, suppress_defaults=suppress_defaults),
        help=(
            "Degrade acceptance unless every discovered body asset is a local "
            "full-size file; this also implies --require-local-body-assets."
        ),
    )
    parser.add_argument(
        "--max-tokens",
        type=parse_max_tokens,
        default=_default("full_text", suppress_defaults=suppress_defaults),
        help=(
            "Markdown rendering budget: a positive integer token budget or full_text "
            "for the complete article (default: full_text)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"paper-fetch {package_version()}",
        help="Show the installed paper-fetch version and exit.",
    )


def _build_fetch_parent_parser(*, suppress_defaults: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    _add_fetch_arguments(parser, suppress_defaults=suppress_defaults)
    return parser


def _add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "provider",
        choices=browser_auth_provider_names(),
        help="Browser-backed provider to open for manual authentication.",
    )
    parser.add_argument(
        "--url",
        help="Publisher URL to open (default: the provider's built-in sample article).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=parse_positive_int_arg,
        default=None,
        help="Browser navigation timeout in milliseconds (default: runtime configuration).",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this authentication run (default: runtime configuration).",
    )


def _build_auth_parent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    _add_auth_arguments(parser)
    return parser


def _add_browser_preflight_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        action="append",
        choices=browser_preflight_provider_names(),
        help=(
            "Browser-backed provider to preflight. May be repeated "
            "(default: all browser-backed providers)."
        ),
    )
    parser.add_argument(
        "--timeout-ms",
        type=parse_positive_int_arg,
        default=None,
        help="Browser navigation timeout in milliseconds (default: runtime configuration).",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this preflight run (default: runtime configuration).",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=None,
        help="Directory for privacy-sanitized failure diagnostics.",
    )
    parser.add_argument(
        "--artifact-mode",
        choices=("none", "all"),
        default="none",
        help="Use 'all' to persist sanitized page diagnostics (default: none).",
    )


def _build_browser_preflight_parent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    _add_browser_preflight_arguments(parser)
    return parser


def _write_doctor_human(report: Mapping[str, Any]) -> None:
    provider_report = report.get("provider_status")
    providers = (
        provider_report.get("providers", [])
        if isinstance(provider_report, Mapping)
        else []
    )
    sys.stdout.write(
        "Paper Fetch doctor: static configuration and local dependencies\n"
    )
    sys.stdout.write(f"Status: {report.get('status', ERROR)}\n")
    sys.stdout.write("Live publisher or browser-page checks: not run\n")
    for item in providers:
        if not isinstance(item, Mapping):
            continue
        provider_name = item.get("provider", "unknown")
        status = item.get("status", ERROR)
        reason = item.get("reason")
        action = item.get("suggested_action")
        sys.stdout.write(f"- {provider_name}: {status}")
        if reason:
            sys.stdout.write(f" — {reason}")
        sys.stdout.write("\n")
        if action:
            sys.stdout.write(f"  Next: {action}\n")
    sys.stdout.write(
        "For real browser-path health, run browser-preflight; if authentication is "
        "required, run auth explicitly.\n"
    )


def _run_doctor_namespace(args: argparse.Namespace) -> int:
    try:
        report = build_doctor_payload(
            provider=args.provider,
            group=args.group,
            detail=args.detail,
            env_file=args.env_file,
        )
    except ValueError as error:
        args._command_parser.error(str(error))
    if args.output_json:
        sys.stdout.write(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    else:
        _write_doctor_human(report)
    status = report.get("status")
    if status == "ready":
        return 0
    if status == ERROR:
        return 2
    return 1


def _register_doctor_subcommand(
    subparsers: argparse._SubParsersAction,
) -> None:
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Inspect static provider configuration and local dependencies.",
        description=(
            "Inspect provider configuration sources and local browser/image dependencies "
            "without network access. Use browser-preflight for real page health."
        ),
    )
    doctor_parser.add_argument(
        "--provider",
        choices=provider_status_provider_names(),
        help="Inspect one provider instead of the full catalog.",
    )
    doctor_parser.add_argument(
        "--group",
        choices=provider_status_group_names(),
        help="Inspect a catalog-derived provider group.",
    )
    doctor_parser.add_argument(
        "--detail",
        choices=("full", "compact"),
        default="full",
        help="Diagnostic detail level (default: full).",
    )
    doctor_parser.add_argument(
        "--env-file",
        type=Path,
        help="Explicit dotenv file used only for source-aware static diagnostics.",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Write the machine-readable diagnostic report.",
    )
    doctor_parser.set_defaults(
        _command_handler=_run_doctor_namespace,
        _command_parser=doctor_parser,
    )


def build_parser(
    *,
    doctor_registrar: SubcommandRegistrar | None = None,
) -> argparse.ArgumentParser:
    """Build the discoverable command-oriented CLI."""
    parser = argparse.ArgumentParser(
        prog="paper-fetch",
        description=(
            "Fetch AI-friendly paper full text and manage browser-backed provider access."
        ),
        epilog="Doctor performs static, network-free checks.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"paper-fetch {package_version()}",
        help="Show the installed paper-fetch version and exit.",
    )
    subparsers = parser.add_subparsers(
        dest="_command",
        title="commands",
        description="Run `paper-fetch COMMAND --help` for command-specific options.",
    )
    subparsers.required = True

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch one paper or a query-file batch.",
        description=(
            "Fetch AI-friendly full text for a paper by DOI, URL, or title. "
            "Browser-backed providers use Camoufox when the browser extra is installed."
        ),
        parents=[_build_fetch_parent_parser(suppress_defaults=False)],
    )
    fetch_parser.set_defaults(
        _command_handler=_run_fetch_namespace,
        _command_parser=fetch_parser,
    )

    auth_parser = subparsers.add_parser(
        "auth",
        help="Open a headed browser and save provider authentication state.",
        description="Manage publisher browser authentication state.",
        parents=[_build_auth_parent_parser()],
    )
    auth_parser.set_defaults(
        _command_handler=_run_auth_namespace,
        _command_parser=auth_parser,
    )

    preflight_parser = subparsers.add_parser(
        "browser-preflight",
        help="Live-check browser-backed providers and save usable storage state.",
        description=(
            "Serially open browser-backed provider sample pages, save provider "
            "storage-state JSON on success, and report providers that need manual auth."
        ),
        parents=[_build_browser_preflight_parent_parser()],
    )
    preflight_parser.set_defaults(
        _command_handler=_run_browser_preflight_namespace,
        _command_parser=preflight_parser,
    )

    if doctor_registrar is None:
        _register_doctor_subcommand(subparsers)
    else:
        doctor_registrar(subparsers)
    return parser


def _write_auth_result(provider_key: str, provider_label: str, result) -> None:
    sys.stdout.write(f"{provider_label} storage state: {result.storage_state_path}\n")
    profile_dir = getattr(result, "profile_dir", None)
    if profile_dir is not None:
        sys.stdout.write(f"{provider_label} profile dir: {profile_dir}\n")
    if result.verified:
        sys.stdout.write(f"{provider_label} verification detected: yes\n")
    else:
        sys.stdout.write(f"{provider_label} verification detected: no\n")
        sys.stderr.write(
            f"Warning: {provider_label} article body was not detected before timeout; rerun `paper-fetch auth {provider_key}` if fetches still hit verification.\n"
        )
    if result.final_url:
        sys.stdout.write(f"Final URL: {result.final_url}\n")
    sys.stdout.write(
        "Persistent browser state is optional; fetches still run without it.\n"
    )


def _write_browser_preflight_results(results: list[BrowserPreflightResult]) -> None:
    sys.stdout.write("Browser preflight results:\n")
    for result in results:
        status = "ok" if result.ready else result.status
        sys.stdout.write(f"- {status}: {result.provider_label} ({result.provider})\n")
        if result.final_url:
            sys.stdout.write(f"  Final URL: {result.final_url}\n")
        if result.storage_state_path is not None:
            sys.stdout.write(f"  Storage state: {result.storage_state_path}\n")
        if not result.ready:
            detail = result.message or "Browser preflight failed."
            sys.stdout.write(f"  Code: {result.reason_code}\n")
            browser_failure = _browser_preflight_failure_details(result)
            stage = result.stage or str(browser_failure.get("stage") or "").strip()
            if stage:
                sys.stdout.write(f"  Stage: {stage}\n")
            exit_code = browser_failure.get("exit_code")
            if exit_code is not None:
                sys.stdout.write(f"  Exit code: {exit_code}\n")
            stderr_summary = str(browser_failure.get("stderr_summary") or "").strip()
            if stderr_summary:
                sys.stdout.write(f"  Browser runtime stderr: {stderr_summary}\n")
            diagnostic_path = str(browser_failure.get("diagnostic_path") or "").strip()
            if diagnostic_path:
                sys.stdout.write(f"  Diagnostic artifact: {diagnostic_path}\n")
            sys.stdout.write(f"  Reason: {detail}\n")


def _browser_preflight_failure_details(
    result: BrowserPreflightResult,
) -> Mapping[str, Any]:
    diagnostics = result.diagnostics or {}
    browser_failure = diagnostics.get("browser_failure")
    if isinstance(browser_failure, Mapping):
        return browser_failure
    trace = diagnostics.get("trace")
    if isinstance(trace, Mapping):
        browser_failure = trace.get("browser_failure")
        if isinstance(browser_failure, Mapping):
            return browser_failure
    return {}


def _write_browser_preflight_failure_hints(
    results: list[BrowserPreflightResult],
) -> None:
    failures = [result for result in results if not result.ready]
    if not failures:
        return
    sys.stderr.write("Browser preflight needs attention for these providers:\n")
    for result in failures:
        detail = result.message or "Browser preflight failed."
        browser_failure = _browser_preflight_failure_details(result)
        artifact = str(browser_failure.get("diagnostic_path") or "").strip()
        if not artifact:
            artifact = str(
                (result.diagnostics or {}).get("diagnostic_path") or ""
            ).strip()
        artifact_hint = f" Diagnostic artifact: {artifact}." if artifact else ""
        action = browser_preflight_next_action(result.provider, result.status)
        sys.stderr.write(
            f"- {result.provider_label} ({result.provider}) "
            f"[{result.status}/{result.reason_code}]: {detail}.{artifact_hint} "
            f"Next action: {action}.\n"
        )


def _run_auth_namespace(args: argparse.Namespace) -> int:
    runtime_env = build_runtime_env()
    result = authenticate_provider_profile(
        provider=args.provider,
        target_url=args.url,
        timeout_ms=args.timeout_ms,
        browser_user_agent=args.browser_user_agent,
        env=runtime_env,
    )
    _write_auth_result(args.provider, provider_display_name(args.provider), result)
    return 0


def _run_browser_preflight_namespace(args: argparse.Namespace) -> int:
    runtime_env = build_runtime_env()
    results = run_browser_provider_preflight(
        providers=args.provider,
        timeout_ms=args.timeout_ms,
        browser_user_agent=args.browser_user_agent,
        runtime_options=BrowserPreflightRuntimeOptions(
            env=runtime_env,
            download_dir=args.download_dir,
            artifact_mode=args.artifact_mode,
        ),
    )
    _write_browser_preflight_results(results)
    _write_browser_preflight_failure_hints(results)
    return 1 if any(not result.ready for result in results) else 0


def _write_single_cli_manifest(
    path: str,
    record: ManifestRecord,
    *,
    overwrite: bool,
) -> None:
    try:
        write_manifest_record(Path(path), record, overwrite=overwrite)
    except FileExistsError as exc:
        raise OutputOverwriteRequired(
            f"single-paper manifest already exists at {path}; use --overwrite after reviewing it"
        ) from exc
    except OSError as exc:
        raise ManifestWriteError(
            f"could not write single-paper manifest {path}: {exc}"
        ) from exc


def _validate_single_manifest_target(path: str, result: SingleFetchResult) -> None:
    manifest_target = Path(path).resolve(strict=False)
    output_targets = {
        candidate.resolve(strict=False)
        for candidate in (result.output_path, result.saved_markdown_path)
        if candidate is not None
    }
    if manifest_target in output_targets:
        raise ManifestTargetConflict(
            "--manifest must not overwrite the primary output or saved Markdown."
        )


def _write_single_failure_manifest(
    args: argparse.Namespace,
    error: Exception,
    *,
    output_dir: Path,
    artifact_mode: ArtifactMode,
    run_id: UUID,
    tool_version: str,
    started_at: datetime,
    deps: ManifestBuilderDependencies,
) -> None:
    record = _build_cli_manifest_record(
        CliManifestBuildContext(
            args=args,
            output_dir=output_dir,
            artifact_mode=artifact_mode,
            run_id=run_id,
            tool_version=tool_version,
            deps=deps,
        ),
        CliManifestAttempt(
            index=1,
            query=args.query,
            started_at=started_at,
            completed_at=deps.clock(),
        ),
        error=error,
    )
    _write_single_cli_manifest(
        args.manifest,
        record,
        overwrite=bool(getattr(args, "overwrite", False)),
    )


def _run_fetch_namespace(args: argparse.Namespace) -> int:
    parser = args._command_parser
    raw_args = args._raw_args
    if args.query is None and args.query_file is None:
        parser.error("one of the arguments --query --query-file is required")
    if args.query is not None and args.query_file is not None:
        parser.error("argument --query-file: not allowed with argument --query")

    artifact_mode = _effective_artifact_mode(args)
    args.output_is_explicit = _has_explicit_option(raw_args, "--output")
    batch_mode = bool(args.query_file)
    if batch_mode and args.output_is_explicit:
        parser.error(
            "--output cannot be used with --query-file; batch mode writes one primary output per query under --output-dir."
        )
    if batch_mode and args.manifest:
        parser.error(
            "--manifest is single-paper only; batch mode uses --batch-results."
        )
    if not batch_mode and args.batch_results:
        parser.error("--batch-results requires --query-file.")
    args.primary_output_to_output_dir = (
        batch_mode or _should_write_primary_output_to_output_dir(args)
    )
    args.save_output_copy = _should_save_formatted_output_copy(
        args,
        explicit_format=_has_explicit_option(raw_args, "--format"),
        output_is_explicit=args.output_is_explicit,
        artifact_mode=artifact_mode,
    )
    args.save_markdown_to_disk = _should_save_markdown_via_pipeline(
        args,
        artifact_mode=artifact_mode,
    )
    queries = None
    if batch_mode:
        try:
            queries = read_query_file(Path(args.query_file))
        except ValueError as exc:
            parser.error(str(exc))

    manifest_deps = getattr(
        args, "_manifest_deps", DEFAULT_MANIFEST_BUILDER_DEPENDENCIES
    )
    manifest_run_id = (
        manifest_deps.uuid_factory() if args.manifest and not batch_mode else None
    )
    manifest_tool_version = (
        package_version() if args.manifest and not batch_mode else None
    )
    manifest_started_at = (
        manifest_deps.clock() if args.manifest and not batch_mode else None
    )
    output_dir: Path | None = None

    try:
        runtime_env = build_runtime_env()
        output_dir = (
            Path(args.output_dir)
            if args.output_dir
            else resolve_cli_download_dir(runtime_env)
        )
        prepare_output_dir(output_dir)
        if batch_mode:
            assert queries is not None
            return run_batch_fetch(
                args,
                queries=queries,
                output_dir=output_dir,
                runtime_env=runtime_env,
                artifact_mode=artifact_mode,
                manifest_deps=manifest_deps,
            )

        result = run_single_fetch(
            args,
            query=args.query,
            output_dir=output_dir,
            runtime_env=runtime_env,
            artifact_mode=artifact_mode,
        )
        if args.manifest:
            assert manifest_run_id is not None
            assert manifest_tool_version is not None
            assert manifest_started_at is not None
            _validate_single_manifest_target(args.manifest, result)
            record = _build_cli_manifest_record(
                CliManifestBuildContext(
                    args=args,
                    output_dir=output_dir,
                    artifact_mode=artifact_mode,
                    run_id=manifest_run_id,
                    tool_version=manifest_tool_version,
                    deps=manifest_deps,
                ),
                CliManifestAttempt(
                    index=1,
                    query=args.query,
                    started_at=manifest_started_at,
                    completed_at=manifest_deps.clock(),
                ),
                result=result,
            )
            _write_single_cli_manifest(
                args.manifest,
                record,
                overwrite=bool(getattr(args, "overwrite", False)),
            )
        return 0
    except OutputDirectoryError as exc:
        if (
            args.manifest
            and not batch_mode
            and output_dir is not None
            and not isinstance(
                exc,
                (
                    ManifestWriteError,
                    ManifestTargetConflict,
                    OutputOverwriteRequired,
                ),
            )
        ):
            assert manifest_run_id is not None
            assert manifest_tool_version is not None
            assert manifest_started_at is not None
            _write_single_failure_manifest(
                args,
                exc,
                output_dir=output_dir,
                artifact_mode=artifact_mode,
                run_id=manifest_run_id,
                tool_version=manifest_tool_version,
                started_at=manifest_started_at,
                deps=manifest_deps,
            )
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)
    except PaperFetchFailure as exc:
        if args.manifest and output_dir is not None:
            assert manifest_run_id is not None
            assert manifest_tool_version is not None
            assert manifest_started_at is not None
            _write_single_failure_manifest(
                args,
                exc,
                output_dir=output_dir,
                artifact_mode=artifact_mode,
                run_id=manifest_run_id,
                tool_version=manifest_tool_version,
                started_at=manifest_started_at,
                deps=manifest_deps,
            )
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)
    except ProviderFailure as exc:
        if args.manifest and output_dir is not None:
            assert manifest_run_id is not None
            assert manifest_tool_version is not None
            assert manifest_started_at is not None
            _write_single_failure_manifest(
                args,
                exc,
                output_dir=output_dir,
                artifact_mode=artifact_mode,
                run_id=manifest_run_id,
                tool_version=manifest_tool_version,
                started_at=manifest_started_at,
                deps=manifest_deps,
            )
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)
    except Exception as exc:
        if args.manifest and not batch_mode and output_dir is not None:
            assert manifest_run_id is not None
            assert manifest_tool_version is not None
            assert manifest_started_at is not None
            _write_single_failure_manifest(
                args,
                exc,
                output_dir=output_dir,
                artifact_mode=artifact_mode,
                run_id=manifest_run_id,
                tool_version=manifest_tool_version,
                started_at=manifest_started_at,
                deps=manifest_deps,
            )
        raise


def main(argv: list[str] | None = None) -> int:
    raw_args = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    args = parser.parse_args(raw_args)
    args._raw_args = raw_args
    handler = getattr(args, "_command_handler", None)
    if handler is None:
        parser.error(f"command {args._command!r} does not have a registered handler")

    try:
        return handler(args)
    except ProviderFailure as exc:
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
