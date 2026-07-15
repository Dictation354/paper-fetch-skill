"""CLI entrypoint for paper-fetch."""

from __future__ import annotations

import argparse
import contextlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import importlib.metadata
import json
import os
import signal
import sys
import threading
import tomllib
from pathlib import Path
from typing import Any
from uuid import UUID

from .auth import (
    authenticate_provider_profile,
    browser_auth_provider_names,
)
from .artifacts import ArtifactMode, ArtifactStore
from .browser_preflight import BrowserPreflightResult, run_browser_provider_preflight
from .config import build_runtime_env, resolve_cli_download_dir
from .diagnostics import (
    doctor_payload as build_doctor_payload,
    provider_status_group_names,
    provider_status_provider_names,
)
from .http import RequestCancelledError
from .manifest import (
    DEFAULT_MANIFEST_BUILDER_DEPENDENCIES,
    LegacyArtifactField,
    ManifestBuilderDependencies,
    ManifestOutputArtifactSpec,
    ManifestRecord,
    ManifestRecordStatus,
    build_manifest_record,
)
from .manifest_writer import (
    ManifestAuditStatus,
    ManifestJsonlWriter,
    ManifestPersistenceError,
    RunManifestState,
    RunManifestStore,
    audit_manifest_path,
    build_run_request_fingerprint,
    checkpoint_run_manifest,
    create_run_manifest,
    deterministic_manifest_record_id,
    latest_manifest_records,
    manifest_audit_exit_code,
    terminal_run_manifest,
    write_manifest_record,
)
from .models import FetchEnvelope, OutputMode, RenderOptions
from .providers.base import ProviderFailure
from .publisher_identity import (
    extract_doi,
    extract_doi_from_url,
    infer_provider_from_doi,
    infer_provider_from_url,
)
from .reason_codes import BROWSER_RUNTIME_FAILURE_CODES, ERROR, NO_ACCESS, RATE_LIMITED
from .runtime import (
    build_http_transport_for_context,
    close_shared_browser_managers,
)
from .service import FetchStrategy, PaperFetchFailure, fetch_paper
from .tracing import merge_trace, trace_from_markers
from .utils import _extract_year, format_paper_stem, provider_display_name
from .workflow.batch_runner import (
    BatchCompletionEvent,
    BatchFailure,
    BatchItemResult,
    BatchItemStatus,
    run_batch,
)
from .workflow.pipeline import FetchPipeline, MarkdownSaveSpec
from .workflow.request_builder import build_fetch_pipeline_request
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


@dataclass(frozen=True)
class CliFetchOutcome:
    """Wall-clock attempt facts retained when a batch worker fails."""

    started_at: datetime
    completed_at: datetime
    result: SingleFetchResult | None = None
    error: Exception | None = None


class OutputDirectoryError(Exception):
    """Raised when the CLI output directory cannot be prepared."""


class ManifestWriteError(OutputDirectoryError):
    """Raised when an explicitly requested CLI manifest cannot be written."""


class ManifestTargetConflict(OutputDirectoryError):
    """Raised when a manifest would overwrite a recorded output artifact."""


class ManifestResumeError(OutputDirectoryError):
    """Raised when a durable run cannot be safely resumed."""


class OutputOverwriteRequired(OutputDirectoryError):
    """Raised when replacing an existing final artifact needs permission."""


SubcommandRegistrar = Callable[[argparse._SubParsersAction], None]


@contextlib.contextmanager
def _cooperative_batch_cancel(cancel_event: threading.Event):
    if threading.current_thread() is not threading.main_thread() or not hasattr(
        signal, "SIGINT"
    ):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGINT)

    def handle_interrupt(_signum, _frame) -> None:
        if cancel_event.is_set():
            close_shared_browser_managers()
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


def package_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        version = payload.get("project", {}).get("version")
        if version:
            return str(version)
    except OSError:
        pass
    try:
        return importlib.metadata.version("paper-fetch-skill")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


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


def write_output(serialized: str, output: str, *, overwrite: bool = True) -> None:
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
    ArtifactStore.from_download_dir(target.parent).write_text_file(
        target,
        serialized,
        encoding="utf-8",
        overwrite=overwrite,
        use_lock=True,
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


def _formatted_output_filename(envelope: FetchEnvelope, *, output_format: str) -> str:
    meta = (
        envelope.article.metadata if envelope.article is not None else envelope.metadata
    )
    authors = list(meta.authors) if meta and meta.authors else None
    year = _extract_year(meta.published if meta else None)
    title = meta.title if meta else None
    stem = format_paper_stem(authors, year, title, doi=envelope.doi)
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
) -> Path:
    target = output_dir / _formatted_output_filename(
        envelope, output_format=output_format
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
    return ArtifactStore.from_download_dir(output_dir).write_text_file(
        target,
        serialized,
        encoding="utf-8",
        overwrite=overwrite,
        use_lock=True,
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
    if args.no_download:
        return "none"
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
        }
    if isinstance(error, ProviderFailure):
        return {"status": error.code, "reason": error.message}
    return {"status": ERROR, "reason": str(error)}


def _render_options_from_args(args: argparse.Namespace) -> RenderOptions:
    return RenderOptions(
        include_refs=args.include_refs,
        asset_profile=args.asset_profile,
        max_tokens=args.max_tokens,
    )


def _markdown_save_spec(
    args: argparse.Namespace,
    *,
    output_dir: Path,
    render_options: RenderOptions,
) -> MarkdownSaveSpec | None:
    if not args.save_markdown_to_disk:
        return None
    return MarkdownSaveSpec(
        output_dir=output_dir,
        render=render_options,
        request_label="--save-markdown",
        overwrite=bool(getattr(args, "overwrite", False)),
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
) -> SingleFetchResult:
    modes = _compute_modes(args)
    render_options = _render_options_from_args(args)
    overwrite = bool(getattr(args, "overwrite", False))
    try:
        result = FetchPipeline(fetch_paper).run(
            build_fetch_pipeline_request(
                query=query,
                modes=modes,
                strategy=FetchStrategy(
                    allow_metadata_only_fallback=True,
                    asset_profile=args.asset_profile,
                ),
                render=render_options,
                env=dict(runtime_env),
                download_dir=output_dir,
                no_download=args.no_download,
                artifact_mode=artifact_mode,
                transport=transport,
                cancel_check=cancel_check,
                markdown_save=_markdown_save_spec(
                    args,
                    output_dir=output_dir,
                    render_options=render_options,
                ),
            )
        )
    except FileExistsError as exc:
        raise OutputOverwriteRequired(
            f"{exc}; rerun with --overwrite after reviewing the existing output"
        ) from exc
    envelope = result.envelope
    if args.primary_output_to_output_dir:
        target = output_dir / _formatted_output_filename(
            envelope, output_format=args.format
        )
        if args.format == "markdown" and _same_output_path(
            result.saved_markdown_path, target
        ):
            primary_output_path = target
        else:
            try:
                primary_output_path = save_formatted_output_copy(
                    envelope,
                    output_dir=output_dir,
                    output_format=args.format,
                    render=render_options,
                    overwrite=overwrite,
                )
            except FileExistsError as exc:
                raise OutputOverwriteRequired(
                    f"{exc}; rerun with --overwrite after reviewing the existing output"
                ) from exc
        return SingleFetchResult(
            envelope=envelope,
            output_path=primary_output_path,
            saved_markdown_path=result.saved_markdown_path,
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
            envelope, output_format=args.format
        )
        if args.format == "markdown" and _same_output_path(
            result.saved_markdown_path, target
        ):
            output_path = target
        else:
            try:
                output_path = save_formatted_output_copy(
                    envelope,
                    output_dir=output_dir,
                    output_format=args.format,
                    render=render_options,
                    overwrite=overwrite,
                )
            except FileExistsError as exc:
                raise OutputOverwriteRequired(
                    f"{exc}; rerun with --overwrite after reviewing the existing output"
                ) from exc
    explicit_target = Path(args.output)
    if not (
        args.output != "-"
        and args.format == "markdown"
        and _same_output_path(result.saved_markdown_path, explicit_target)
    ):
        try:
            write_output(serialized, args.output, overwrite=overwrite)
        except FileExistsError as exc:
            raise OutputOverwriteRequired(
                f"{exc}; rerun with --overwrite after reviewing the existing output"
            ) from exc
    if args.output != "-":
        output_path = Path(args.output)
    return SingleFetchResult(
        envelope=envelope,
        output_path=output_path,
        saved_markdown_path=result.saved_markdown_path,
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
        },
        "render": {
            "include_refs": args.include_refs,
            "asset_profile": args.asset_profile,
            "max_tokens": args.max_tokens,
        },
        "artifact_mode": artifact_mode,
        "no_download": bool(args.no_download),
        "save_markdown": bool(args.save_markdown_to_disk),
        "output": args.output,
        "output_dir": str(output_dir),
        "primary_output_to_output_dir": bool(
            getattr(args, "primary_output_to_output_dir", False)
        ),
        "save_output_copy": bool(getattr(args, "save_output_copy", False)),
        "batch_concurrency": args.batch_concurrency,
    }


def _expected_doi_for_query(query: str) -> str | None:
    return extract_doi_from_url(query) or extract_doi(query)


def _batch_lane_for_query(query: str) -> str:
    """Infer a provider lane only from existing catalog-backed identity helpers."""

    provider = infer_provider_from_url(query)
    if provider:
        return provider
    doi = _expected_doi_for_query(query)
    return infer_provider_from_doi(doi) or "generic"


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
                legacy_field=LegacyArtifactField.OUTPUT_PATH,
            )
        )
    if result.saved_markdown_path is not None:
        artifacts.append(
            ManifestOutputArtifactSpec(
                path=str(result.saved_markdown_path),
                kind="saved_markdown",
                legacy_field=LegacyArtifactField.SAVED_MARKDOWN_PATH,
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
    args: argparse.Namespace,
    *,
    index: int,
    query: str,
    output_dir: Path,
    artifact_mode: ArtifactMode,
    run_id: UUID,
    tool_version: str,
    started_at: datetime,
    completed_at: datetime,
    attempt: int = 1,
    record_id: UUID | None = None,
    result: SingleFetchResult | None = None,
    error: Exception | None = None,
    error_payload: Mapping[str, Any] | None = None,
    aborted: bool = False,
    deps: ManifestBuilderDependencies,
) -> ManifestRecord:
    """Adapt CLI attempt facts to the sole PF-004 record builder."""

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
        artifacts = ()

    return build_manifest_record(
        tool_version=tool_version,
        run_id=run_id,
        record_id=record_id,
        index=index,
        attempt=attempt,
        query=query,
        request_parameters=_manifest_request_parameters(
            args,
            output_dir=output_dir,
            artifact_mode=artifact_mode,
        ),
        asset_profile=args.asset_profile,
        envelope=envelope,
        error=manifest_error,
        aborted=aborted,
        requested_outputs=_compute_modes(args),
        candidate_count=candidate_count,
        expected_doi=_expected_doi_for_query(query),
        output_artifacts=artifacts,
        trace=trace,
        warnings=warnings,
        started_at=started_at,
        completed_at=completed_at,
        deps=deps,
    )


def _run_batch_item(
    item: CliBatchItem,
    *,
    args: argparse.Namespace,
    output_dir: Path,
    runtime_env: Mapping[str, str],
    artifact_mode: ArtifactMode,
    transport,
    cancel_check: Callable[[], bool] | None,
    deps: ManifestBuilderDependencies,
) -> CliFetchOutcome:
    started_at = deps.clock()
    try:
        result = run_single_fetch(
            args,
            query=item.query,
            output_dir=output_dir,
            runtime_env=runtime_env,
            artifact_mode=artifact_mode,
            transport=transport,
            cancel_check=cancel_check,
        )
    except Exception as exc:  # noqa: BLE001 - every batch input gets a terminal record.
        return CliFetchOutcome(
            started_at=started_at,
            completed_at=deps.clock(),
            error=exc,
        )
    return CliFetchOutcome(
        started_at=started_at,
        completed_at=deps.clock(),
        result=result,
    )


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
    if outcome is not None:
        return _build_cli_manifest_record(
            args,
            index=item.index,
            query=item.query,
            output_dir=output_dir,
            artifact_mode=artifact_mode,
            run_id=run_id,
            tool_version=tool_version,
            started_at=outcome.started_at,
            completed_at=outcome.completed_at,
            attempt=item.attempt,
            record_id=deterministic_manifest_record_id(
                run_id, index=item.index, attempt=item.attempt
            ),
            result=outcome.result,
            error=outcome.error,
            aborted=batch_result.status is BatchItemStatus.CANCELLED,
            deps=deps,
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
        args,
        index=item.index,
        query=item.query,
        output_dir=output_dir,
        artifact_mode=artifact_mode,
        run_id=run_id,
        tool_version=tool_version,
        started_at=completed_at,
        completed_at=completed_at,
        attempt=item.attempt,
        record_id=deterministic_manifest_record_id(
            run_id, index=item.index, attempt=item.attempt
        ),
        error_payload=error_payload,
        aborted=True,
        deps=deps,
    )


def exit_code_for_batch_results(
    results: Sequence[ManifestRecord | Mapping[str, Any]],
) -> int:
    statuses = [
        item.status if isinstance(item, ManifestRecord) else str(item.get("status"))
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


def _default_run_manifest_path(results_path: Path) -> Path:
    return results_path.parent / "run-manifest.json"


def _recorded_output_path(raw_path: str, *, manifest_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute() or path.exists():
        return path
    return manifest_path.parent / path


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
    request_parameters = _manifest_request_parameters(
        args,
        output_dir=output_dir,
        artifact_mode=artifact_mode,
    )
    overwrite = bool(getattr(args, "overwrite", False))
    resume_value = getattr(args, "resume", None)

    if resume_value:
        try:
            store = RunManifestStore.from_manifest(Path(resume_value))
        except ManifestPersistenceError as exc:
            raise ManifestResumeError(str(exc)) from exc
    else:
        results_path = requested_results_path
        manifest_value = getattr(args, "run_manifest", None)
        manifest_path = (
            Path(manifest_value)
            if manifest_value
            else _default_run_manifest_path(results_path)
        )
        if manifest_path.resolve(strict=False) == results_path.resolve(strict=False):
            raise ManifestTargetConflict(
                "--run-manifest and --batch-results must use different paths."
            )
        store = RunManifestStore.for_new_run(
            manifest_path=manifest_path,
            events_path=results_path,
        )

    with store.run_lock():
        run_started = False
        manifest = None
        records: list[ManifestRecord] = []
        try:
            if resume_value:
                try:
                    manifest = store.read()
                except ManifestPersistenceError as exc:
                    raise ManifestResumeError(str(exc)) from exc
                if args.batch_results and (
                    requested_results_path.resolve(strict=False)
                    != store.events_path.resolve(strict=False)
                ):
                    raise ManifestResumeError(
                        "--batch-results differs from the event path recorded by --resume; create a new run instead"
                    )
                if getattr(args, "run_manifest", None):
                    raise ManifestResumeError(
                        "--run-manifest cannot be combined with --resume"
                    )
                if run_id is not None and run_id != manifest.run_id:
                    raise ManifestResumeError(
                        "requested run_id differs from the recorded run"
                    )
                recorded_queries = [item.query for item in manifest.inputs]
                if recorded_queries != queries:
                    raise ManifestResumeError(
                        "query-file inputs differ from the recorded run; create a new run instead"
                    )
                if (
                    build_run_request_fingerprint(queries, request_parameters)
                    != manifest.request_fingerprint
                ):
                    raise ManifestResumeError(
                        "critical fetch/output configuration differs from the recorded run; create a new run instead"
                    )
                if manifest.tool_version != effective_tool_version:
                    raise ManifestResumeError(
                        "tool version differs from the recorded run; create a new run instead"
                    )
                report = audit_manifest_path(store.manifest_path, mode="audit")
                if report.status == ManifestAuditStatus.INVALID:
                    raise ManifestResumeError(
                        "run manifest is structurally invalid and cannot be resumed"
                    )
                try:
                    records = (
                        store.read_records() if store.events_path.is_file() else []
                    )
                except ManifestPersistenceError as exc:
                    raise ManifestResumeError(str(exc)) from exc
                latest = latest_manifest_records(records)
                reusable_indices = set(report.reusable_indices)
                items = [
                    CliBatchItem(
                        index=index,
                        query=query,
                        lane_key=_batch_lane_for_query(query),
                        attempt=(latest[index].attempt + 1 if index in latest else 1),
                    )
                    for index, query in enumerate(queries, start=1)
                    if index not in reusable_indices
                ]
                if not overwrite:
                    existing_retry_outputs = sorted(
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
                    if existing_retry_outputs:
                        raise OutputOverwriteRequired(
                            "resume would replace existing stale or below-request output; "
                            "review it and rerun with --overwrite: "
                            + ", ".join(existing_retry_outputs)
                        )
                effective_run_id = manifest.run_id
                append_events = True
                manifest = store.write(checkpoint_run_manifest(manifest, records))
                run_started = True
            else:
                if store.manifest_path.exists() and not overwrite:
                    raise OutputOverwriteRequired(
                        f"run manifest already exists at {store.manifest_path}; use --overwrite or choose --run-manifest"
                    )
                if store.events_path.exists() and not overwrite:
                    raise OutputOverwriteRequired(
                        f"batch event file already exists at {store.events_path}; use --overwrite or choose --batch-results"
                    )
                effective_run_id = run_id or deps.uuid_factory()
                manifest = create_run_manifest(
                    run_id=effective_run_id,
                    tool_version=effective_tool_version,
                    queries=queries,
                    request_parameters=request_parameters,
                    started_at=deps.clock(),
                    events_path=store.events_reference(),
                )
                manifest = store.create(manifest, overwrite=overwrite)
                run_started = True
                append_events = False
                items = [
                    CliBatchItem(
                        index=index,
                        query=query,
                        lane_key=_batch_lane_for_query(query),
                    )
                    for index, query in enumerate(queries, start=1)
                ]

            run_cancelled = False
            if items:
                cancel_event = threading.Event()
                shared_transport = build_http_transport_for_context(
                    runtime_env,
                    download_dir=output_dir,
                    cancel_check=None,
                    artifact_mode=artifact_mode,
                )
                with ManifestJsonlWriter(
                    store.events_path,
                    append=append_events,
                    overwrite=overwrite,
                ) as writer:

                    def on_completion(
                        event: BatchCompletionEvent[CliBatchItem, CliFetchOutcome],
                    ) -> None:
                        nonlocal manifest
                        record = _record_from_batch_result(
                            args,
                            event.result,
                            output_dir=output_dir,
                            artifact_mode=artifact_mode,
                            run_id=effective_run_id,
                            tool_version=effective_tool_version,
                            deps=deps,
                        )
                        writer.write(record)
                        records.append(record)
                        assert manifest is not None
                        manifest = store.write(
                            checkpoint_run_manifest(manifest, records)
                        )

                    with _cooperative_batch_cancel(cancel_event):
                        run_result = run_batch(
                            items,
                            lambda item: _run_batch_item(
                                item,
                                args=args,
                                output_dir=output_dir,
                                runtime_env=runtime_env,
                                artifact_mode=artifact_mode,
                                transport=shared_transport,
                                cancel_check=cancel_event.is_set,
                                deps=deps,
                            ),
                            max_workers=args.batch_concurrency,
                            lane_key=lambda item: item.lane_key,
                            completion_callback=on_completion,
                            result_classifier=_classify_batch_outcome,
                            cancel_event=cancel_event,
                            cancel_escalation_callback=(close_shared_browser_managers),
                        )
                if run_result.callback_failures:
                    details = "; ".join(
                        f"index {failure.source_index + 1}: {failure.message}"
                        for failure in run_result.callback_failures
                    )
                    raise OutputDirectoryError(
                        f"could not persist complete batch events: {details}"
                    )
                run_cancelled = run_result.cancelled

            latest_records = latest_manifest_records(records)
            if set(latest_records) != set(range(1, len(queries) + 1)):
                raise RuntimeError(
                    "CLI batch run does not have one latest terminal attempt per input."
                )
            run_cancelled = run_cancelled or any(
                record.record_status == ManifestRecordStatus.ABORTED
                and record.error is not None
                and (record.error.model_extra or {}).get("code") == "request_cancelled"
                for record in latest_records.values()
            )
            assert manifest is not None
            store.write(
                terminal_run_manifest(
                    manifest,
                    records,
                    state=(
                        RunManifestState.CANCELLED
                        if run_cancelled
                        else RunManifestState.COMPLETED
                    ),
                    completed_at=deps.clock(),
                )
            )
            return exit_code_for_batch_results(
                [latest_records[index] for index in sorted(latest_records)]
            )
        except BaseException as exc:
            if run_started and manifest is not None:
                try:
                    persisted_records = (
                        store.read_records() if store.events_path.is_file() else records
                    )
                    current_manifest = store.read()
                    store.write(
                        terminal_run_manifest(
                            current_manifest,
                            persisted_records,
                            state=(
                                RunManifestState.INTERRUPTED
                                if isinstance(exc, KeyboardInterrupt)
                                else RunManifestState.CANCELLED
                                if isinstance(exc, RequestCancelledError)
                                else RunManifestState.FAILED
                            ),
                            completed_at=deps.clock(),
                        )
                    )
                except Exception:
                    # Keep the original error; audit exposes any stale checkpoint.
                    pass
            raise


def _default(value: Any, *, suppress_defaults: bool) -> Any:
    return argparse.SUPPRESS if suppress_defaults else value


def _add_fetch_arguments(
    parser: argparse.ArgumentParser,
    *,
    suppress_defaults: bool,
) -> None:
    """Register fetch flags once for the explicit and legacy command surfaces."""
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
        "--run-manifest",
        default=_default(None, suppress_defaults=suppress_defaults),
        help=(
            "Atomic run summary path for --query-file batch mode. Defaults to "
            "run-manifest.json beside --batch-results."
        ),
    )
    parser.add_argument(
        "--resume",
        default=_default(None, suppress_defaults=suppress_defaults),
        help=(
            "Resume a batch from its run-manifest.json after read-only audit. "
            "Requires the original --query-file and matching fetch/output options."
        ),
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
        help=(
            "Allow replacement of existing final outputs or a new run's manifest files. "
            "Resume still audits before replacement."
        ),
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
        "--no-download",
        action="store_true",
        default=_default(False, suppress_defaults=suppress_defaults),
        help=(
            "CLI artifact alias for --artifact-mode none; disables provider artifacts and assets, "
            "but does not block explicit --output, --output-dir primary output, or --save-markdown."
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
        help="CloakBrowser navigation timeout in milliseconds (default: runtime configuration).",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this authentication run (default: runtime configuration).",
    )
    parser.add_argument(
        "--state-json",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--env-file",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-env-write",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--wait-seconds",
        type=parse_positive_int_arg,
        default=None,
        help=argparse.SUPPRESS,
    )


def _build_auth_parent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    _add_auth_arguments(parser)
    return parser


def build_auth_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-fetch auth",
        description="Manage publisher browser authentication state.",
        parents=[_build_auth_parent_parser()],
    )
    return parser


def _add_browser_preflight_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        action="append",
        choices=browser_auth_provider_names(),
        help=(
            "Browser-backed provider to preflight. May be repeated "
            "(default: all browser-backed providers)."
        ),
    )
    parser.add_argument(
        "--timeout-ms",
        type=parse_positive_int_arg,
        default=None,
        help="CloakBrowser navigation timeout in milliseconds (default: runtime configuration).",
    )
    parser.add_argument(
        "--browser-user-agent",
        help="Browser-only User-Agent override for this preflight run (default: runtime configuration).",
    )


def _build_browser_preflight_parent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    _add_browser_preflight_arguments(parser)
    return parser


def build_browser_preflight_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-fetch browser-preflight",
        description=(
            "Serially open browser-backed provider sample pages, save provider "
            "storage-state JSON on success, and report providers that need manual auth."
        ),
        parents=[_build_browser_preflight_parent_parser()],
    )
    return parser


def _run_manifest_namespace(args: argparse.Namespace) -> int:
    report = audit_manifest_path(args.path, mode=args.manifest_action)
    sys.stdout.write(report.to_json() + "\n")
    return manifest_audit_exit_code(report)


def _register_manifest_subcommand(
    subparsers: argparse._SubParsersAction,
) -> None:
    manifest_parser = subparsers.add_parser(
        "manifest",
        help="Read-only audit and reconciliation for run or single manifests.",
        description=(
            "Inspect manifest structure, current output hashes, Markdown front matter, "
            "request fingerprints, and acceptance without writing files or using network."
        ),
    )
    actions = manifest_parser.add_subparsers(
        dest="manifest_action",
        title="manifest commands",
        required=True,
    )
    for action in ("audit", "reconcile"):
        action_parser = actions.add_parser(
            action,
            help=(
                "Inspect manifest state without mutation."
                if action == "audit"
                else "Re-read final artifacts and report stale state without mutation."
            ),
        )
        action_parser.add_argument(
            "path",
            type=Path,
            help="Path to run-manifest.json or a single-paper manifest.",
        )
        action_parser.set_defaults(
            _command_handler=_run_manifest_namespace,
            _command_parser=action_parser,
        )


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
    provenance = report.get("install_provenance")
    if isinstance(provenance, Mapping):
        sys.stdout.write(
            f"Install provenance: {provenance.get('status', 'not_applicable')}"
        )
        expected_version = provenance.get("consistency")
        if isinstance(expected_version, Mapping) and expected_version.get(
            "expected_version"
        ):
            sys.stdout.write(
                f" (expected version {expected_version['expected_version']})"
            )
        sys.stdout.write("\n")
        for issue in provenance.get("issues", []):
            if not isinstance(issue, Mapping):
                continue
            component = issue.get("component", "installation")
            reason_code = issue.get("reason_code", "provenance_issue")
            path = issue.get("path")
            actual = issue.get("actual")
            expected = issue.get("expected")
            sys.stdout.write(f"- {component}: {reason_code}")
            if actual is not None or expected is not None:
                sys.stdout.write(f" (actual={actual}, expected={expected})")
            if path:
                sys.stdout.write(f" — {path}")
            sys.stdout.write("\n")
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
            install_root=args.install_root,
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
        "--install-root",
        type=Path,
        help=(
            "Verify one offline install root, its runtime manifest, and installed "
            "Codex/Claude/Antigravity skill copies."
        ),
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
    manifest_registrar: SubcommandRegistrar | None = None,
    doctor_registrar: SubcommandRegistrar | None = None,
) -> argparse.ArgumentParser:
    """Build the discoverable CLI while retaining root-level fetch flags."""
    parser = argparse.ArgumentParser(
        prog="paper-fetch",
        description=(
            "Fetch AI-friendly paper full text and manage browser-backed provider access."
        ),
        epilog=(
            "Compatibility: root-level fetch flags remain available for one release cycle; "
            "prefer `paper-fetch fetch ...`. Doctor performs static, network-free checks."
        ),
        parents=[_build_fetch_parent_parser(suppress_defaults=False)],
    )
    parser.set_defaults(_command_parser=parser)
    subparsers = parser.add_subparsers(
        dest="_command",
        title="commands",
        description="Run `paper-fetch COMMAND --help` for command-specific options.",
    )

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch one paper or a query-file batch.",
        description=(
            "Fetch AI-friendly full text for a paper by DOI, URL, or title. "
            "Use CLOAKBROWSER_CDP_ENDPOINT for browser-backed providers."
        ),
        parents=[_build_fetch_parent_parser(suppress_defaults=True)],
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

    if manifest_registrar is None:
        _register_manifest_subcommand(subparsers)
    else:
        manifest_registrar(subparsers)
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
    if result.env_written and result.env_file_path is not None:
        sys.stdout.write(f"Environment updated: {result.env_file_path}\n")
    else:
        sys.stdout.write("Environment update skipped.\n")
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
        status = "ok" if result.ok else "failed"
        sys.stdout.write(f"- {status}: {result.provider_label} ({result.provider})\n")
        if result.final_url:
            sys.stdout.write(f"  Final URL: {result.final_url}\n")
        if result.storage_state_path is not None:
            sys.stdout.write(f"  Storage state: {result.storage_state_path}\n")
        trace = (result.diagnostics or {}).get("browser_runtime_trace")
        external = (
            trace.get("external_cdp_context") if isinstance(trace, dict) else None
        )
        if isinstance(external, dict) and external.get("external_cdp"):
            borrowed = external.get("borrowed_existing_context")
            sys.stdout.write(
                "  External CDP: "
                f"{'borrowed existing context' if borrowed else 'new context'}\n"
            )
            ignored = external.get("ignored_context_options") or []
            if ignored:
                sys.stdout.write(f"  Ignored context options: {', '.join(ignored)}\n")
            cookie_count = external.get("storage_state_cookie_count")
            if cookie_count is not None:
                sys.stdout.write(f"  Injected storage cookies: {cookie_count}\n")
        if not result.ok:
            detail = result.message or result.reason or "Browser preflight failed."
            if result.reason:
                sys.stdout.write(f"  Code: {result.reason}\n")
            browser_failure = _browser_preflight_failure_details(result)
            stage = str(browser_failure.get("stage") or "").strip()
            if stage:
                sys.stdout.write(f"  Stage: {stage}\n")
            exit_code = browser_failure.get("exit_code")
            if exit_code is not None:
                sys.stdout.write(f"  Exit code: {exit_code}\n")
            stderr_summary = str(browser_failure.get("stderr_summary") or "").strip()
            if stderr_summary:
                sys.stdout.write(f"  Chrome stderr: {stderr_summary}\n")
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
    failures = [result for result in results if not result.ok]
    if not failures:
        return
    sys.stderr.write(
        "Browser preflight failed for these providers; run manual auth before retrying:\n"
    )
    for result in failures:
        detail = result.message or result.reason or "Browser preflight failed."
        if result.reason in BROWSER_RUNTIME_FAILURE_CODES:
            browser_failure = _browser_preflight_failure_details(result)
            artifact = str(browser_failure.get("diagnostic_path") or "").strip()
            artifact_hint = f" Diagnostic artifact: {artifact}." if artifact else ""
            sys.stderr.write(
                f"- {result.provider_label} ({result.provider}) "
                f"[{result.reason}]: {detail}.{artifact_hint} Retry browser-preflight "
                "after resolving the reported browser runtime state.\n"
            )
        else:
            sys.stderr.write(
                f"- {result.provider_label} ({result.provider}): {detail} "
                f"Run: paper-fetch auth {result.provider}\n"
            )


def _run_auth_namespace(args: argparse.Namespace) -> int:
    parser = args._command_parser
    uses_direct_storage_args = bool(
        args.state_json
        or args.env_file
        or args.no_env_write
        or args.wait_seconds is not None
    )
    if uses_direct_storage_args:
        parser.error(
            "--state-json, --env-file, --no-env-write, and --wait-seconds are unsupported for provider auth; "
            "auth saves provider-scoped storage-state. Use CLOAKBROWSER_PROFILE_DIR "
            "or CLOAKBROWSER_USER_DATA_DIR to override that location."
        )
    result = authenticate_provider_profile(
        provider=args.provider,
        target_url=args.url,
        timeout_ms=args.timeout_ms,
        browser_user_agent=args.browser_user_agent,
    )
    _write_auth_result(args.provider, provider_display_name(args.provider), result)
    return 0


def _run_browser_preflight_namespace(args: argparse.Namespace) -> int:
    results = run_browser_provider_preflight(
        providers=args.provider,
        timeout_ms=args.timeout_ms,
        browser_user_agent=args.browser_user_agent,
    )
    _write_browser_preflight_results(results)
    _write_browser_preflight_failure_hints(results)
    return 1 if any(not result.ok for result in results) else 0


def run_auth_command(raw_args: list[str]) -> int:
    """Parse and run auth directly for callers that use the historical helper."""
    parser = build_auth_parser()
    args = parser.parse_args(raw_args)
    args._command_parser = parser
    return _run_auth_namespace(args)


def run_browser_preflight_command(raw_args: list[str]) -> int:
    """Parse and run browser preflight directly for historical helper callers."""
    parser = build_browser_preflight_parser()
    args = parser.parse_args(raw_args)
    args._command_parser = parser
    return _run_browser_preflight_namespace(args)


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
        args,
        index=1,
        query=args.query,
        output_dir=output_dir,
        artifact_mode=artifact_mode,
        run_id=run_id,
        tool_version=tool_version,
        started_at=started_at,
        completed_at=deps.clock(),
        error=error,
        deps=deps,
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
    if not batch_mode and args.run_manifest:
        parser.error("--run-manifest requires --query-file.")
    if not batch_mode and args.resume:
        parser.error("--resume requires the original --query-file.")
    if batch_mode and args.run_manifest and args.resume:
        parser.error("--run-manifest cannot be combined with --resume.")
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
                args,
                index=1,
                query=args.query,
                output_dir=output_dir,
                artifact_mode=artifact_mode,
                run_id=manifest_run_id,
                tool_version=manifest_tool_version,
                started_at=manifest_started_at,
                completed_at=manifest_deps.clock(),
                result=result,
                deps=manifest_deps,
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
                    ManifestResumeError,
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
        if getattr(args, "_command", None) is not None:
            parser.error(
                f"command {args._command!r} does not have a registered handler"
            )
        handler = _run_fetch_namespace

    try:
        return handler(args)
    except ProviderFailure as exc:
        sys.stderr.write(json.dumps(_error_payload(exc), ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
