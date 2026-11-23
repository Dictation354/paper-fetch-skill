"""Envelope serialization, output writing, and CLI manifest construction."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

import paper_fetch.cli as cli_pkg

from ..delivery.receipts import (
    receipt_from_record,
    run_receipt_directory,
    save_reading_artifacts,
    target_satisfied,
)
from ..http import RequestCancelledError
from ..manifest import (
    ManifestBuilderDependencies,
    ManifestOutputArtifactSpec,
    ManifestRecord,
    build_manifest_record,
)
from ..models.schema import FetchEnvelope, RenderOptions
from ..providers.base import ProviderFailure
from ..publication_dates import citation_date
from ..reason_codes import ERROR
from ..service import PaperFetchFailure
from ..utils import _extract_year, format_paper_stem, normalize_text
from ..workflow.batch_routing import expected_doi_from_query
from ..workflow.rendering import (
    save_markdown_to_disk as save_markdown_to_disk_for_target,
)
from .commands import (
    FetchExecutionOptions,
    ManifestTargetConflict,
    ManifestWriteError,
    OutputDirectoryError,
    OutputOverwriteRequired,
    SingleFetchCommand,
    compute_output_modes,
)
from .progress import FetchProgress


@dataclass(frozen=True, slots=True)
class SingleFetchResult:
    """Completed single-paper envelope and written artifact paths."""

    envelope: FetchEnvelope
    output_path: Path | None = None
    saved_markdown_path: Path | None = None


@dataclass(frozen=True, slots=True)
class CliManifestBuildContext:
    """Shared immutable inputs for one CLI manifest record."""

    options: FetchExecutionOptions
    output_dir: Path
    run_id: UUID
    tool_version: str
    deps: ManifestBuilderDependencies


@dataclass(frozen=True, slots=True)
class CliManifestAttempt:
    """Identity and timing facts for one CLI manifest attempt."""

    index: int
    query: str
    started_at: datetime
    completed_at: datetime
    attempt: int = 1
    record_id: UUID | None = None


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
    if envelope.target == "supplementary":
        assert envelope.supplementary is not None
        payload = envelope.to_dict()
        payload["status"] = envelope.supplementary.status
        if output_format == "both" and markdown_override is not None:
            payload["markdown"] = markdown_override
        return json.dumps(payload, ensure_ascii=False, indent=2)
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
        cli_pkg.sys.stdout.write(serialized)
        if not serialized.endswith("\n"):
            cli_pkg.sys.stdout.write("\n")
        return
    target = Path(output)
    if not target.parent.is_dir():
        # Preserve the legacy failure contract for an absent explicit parent.
        target.write_text(serialized, encoding="utf-8")
        return
    cli_pkg.ArtifactStore.from_download_dir(
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
    year = _extract_year(citation_date(meta.publication_dates if meta else []))
    title = meta.title if meta else None
    doi = envelope.doi or (
        expected_doi_from_query(fallback_query) if fallback_query else None
    )
    normalized_query = normalize_text(fallback_query)
    if not title and not doi and normalized_query:
        query_digest = sha256(normalized_query.encode("utf-8")).hexdigest()[:16]
        title = f"article_{query_digest}"
    stem = format_paper_stem(authors, year, title, doi=doi)
    if envelope.target == "supplementary":
        stem += "_supplementary"
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
        cli_pkg.rewrite_markdown_asset_links(
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
    return cli_pkg.ArtifactStore.from_download_dir(
        output_dir,
        commit_guard=commit_guard,
    ).write_text_file(
        target,
        serialized,
        encoding="utf-8",
        overwrite=overwrite,
    )


def _error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
            "provider": error.diagnostics.provider,
            "route": error.diagnostics.route,
            "stage": error.diagnostics.stage,
            "http_status": error.diagnostics.http_status,
            "error_category": error.diagnostics.error_category,
            "retryable": error.diagnostics.retryable,
            "retry_after_seconds": error.retry_after_seconds,
            "details": error.diagnostics.details,
            "warnings": error.warnings,
            "events": error.trace,
        }
    if isinstance(error, ProviderFailure):
        return {
            "status": error.code,
            "reason": error.message,
            "provider": error.diagnostics.provider,
            "route": error.diagnostics.route,
            "stage": error.diagnostics.stage,
            "http_status": error.diagnostics.http_status,
            "error_category": error.diagnostics.error_category,
            "retryable": error.diagnostics.retryable,
            "retry_after_seconds": error.retry_after_seconds,
            "details": error.diagnostics.details,
            "warnings": error.warnings,
            "events": error.trace,
        }
    return {"status": ERROR, "reason": str(error)}


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


def _manifest_request_parameters(
    options: FetchExecutionOptions,
    *,
    output_dir: Path,
) -> dict[str, Any]:
    """Return the CLI request semantics covered by the shared fingerprint."""

    plan = options.output_plan
    return {
        **({"target": options.target} if options.target != "paper" else {}),
        "modes": sorted(compute_output_modes(plan)),
        "format": plan.output_format,
        "strategy": {
            "allow_metadata_only_fallback": True,
            "asset_profile": options.asset_profile,
            "require_local_body_assets": (
                options.require_local_body_assets
                or options.require_full_size_body_assets
            ),
            "require_full_size_body_assets": options.require_full_size_body_assets,
        },
        "render": {
            "include_refs": options.include_refs,
            "asset_profile": options.asset_profile,
            "max_tokens": options.max_tokens,
        },
        "artifact_mode": options.artifact_mode,
        "save_markdown": plan.save_markdown_to_disk,
        "output": plan.output,
        "output_dir": str(output_dir),
        "primary_output_to_output_dir": plan.primary_output_to_output_dir,
        "save_output_copy": plan.save_output_copy,
    }


def _manifest_output_artifacts(
    options: FetchExecutionOptions,
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
                }[options.output_plan.output_format],
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
                failure_code=str(diagnostic.get("failure_code") or "") or None,
            )
        )
    return tuple(artifacts)


def _build_cli_manifest_record(
    context: CliManifestBuildContext,
    attempt: CliManifestAttempt,
    *,
    result: SingleFetchResult | None = None,
    error: Exception | None = None,
    error_payload: Mapping[str, Any] | None = None,
    diagnostic_artifacts: Sequence[Mapping[str, Any]] = (),
    aborted: bool = False,
    requested_manifest: str | None = None,
) -> ManifestRecord:
    """Adapt CLI attempt facts to the sole PF-004 record builder."""

    options = context.options
    plan = options.output_plan
    if result is not None:
        envelope = result.envelope
        manifest_error = None
        warnings: Sequence[str] | None = None
        trace = None
        candidate_count = 0
        artifacts = _manifest_output_artifacts(options, result)
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
            manifest_error = {
                **manifest_error,
                **_aborted_error_payload(
                    reason=str(manifest_error["reason"]),
                    code=code,
                ),
            }
        raw_warnings = (
            error.warnings
            if isinstance(error, (PaperFetchFailure, ProviderFailure))
            else ()
        )
        warnings = tuple(str(item) for item in (raw_warnings or ()))
        raw_trace = (
            error.trace
            if isinstance(error, (PaperFetchFailure, ProviderFailure))
            else ()
        )
        trace = list(raw_trace or ()) or None
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

    delivery_dir: Path | None = None
    if plan.deliver_files:
        delivery_dir = run_receipt_directory(context.output_dir, context.run_id) / str(
            attempt.index
        )
        artifacts = (
            *artifacts,
            *save_reading_artifacts(
                delivery_dir, envelope=envelope, error=manifest_error
            ),
        )

    record = build_manifest_record(
        tool_version=context.tool_version,
        run_id=context.run_id,
        record_id=attempt.record_id,
        index=attempt.index,
        attempt=attempt.attempt,
        query=attempt.query,
        request_parameters=_manifest_request_parameters(
            options,
            output_dir=context.output_dir,
        ),
        asset_profile=options.asset_profile,
        envelope=envelope,
        error=manifest_error,
        aborted=aborted,
        requested_outputs=compute_output_modes(plan),
        candidate_count=candidate_count,
        expected_doi=expected_doi_from_query(attempt.query),
        output_artifacts=artifacts,
        trace=trace,
        warnings=warnings,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        deps=context.deps,
    )
    if requested_manifest:
        _write_single_cli_manifest(requested_manifest, record, overwrite=plan.overwrite)
    if delivery_dir is not None:
        path = delivery_dir / "manifest.json"
        cli_pkg.write_manifest_record(path, record, overwrite=True)
        receipt_line = (
            json.dumps(receipt_from_record(record, path), ensure_ascii=False) + "\n"
        )
        cli_pkg.ArtifactStore.from_download_dir(delivery_dir).write_text_file(
            delivery_dir / "receipt.json", receipt_line
        )
        if not (plan.output_is_explicit and plan.output == "-"):
            cli_pkg.sys.stdout.write(receipt_line)
            cli_pkg.sys.stdout.flush()
    return record


def _write_single_cli_manifest(
    path: str,
    record: ManifestRecord,
    *,
    overwrite: bool,
) -> None:
    try:
        cli_pkg.write_manifest_record(Path(path), record, overwrite=overwrite)
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
    command: SingleFetchCommand,
    error: Exception,
    *,
    output_dir: Path,
    run_id: UUID,
    tool_version: str,
    started_at: datetime,
    deps: ManifestBuilderDependencies,
    progress: FetchProgress | None = None,
) -> None:
    if progress is None:
        output_dir = Path(tempfile.mkdtemp(prefix="paper-fetch-failure-"))
        progress = cli_pkg.FetchProgress(
            command.options.progress,
            run_id,
            1,
            receipt_dir=run_receipt_directory(output_dir, run_id)
            if command.options.output_plan.deliver_files
            else None,
        )
    with progress.lock:
        if progress.is_cancelled(1):
            error = RequestCancelledError("Request cancelled.")
        record = _build_cli_manifest_record(
            CliManifestBuildContext(
                options=command.options,
                output_dir=output_dir,
                run_id=run_id,
                tool_version=tool_version,
                deps=deps,
            ),
            CliManifestAttempt(
                index=1,
                query=command.query,
                started_at=started_at,
                completed_at=deps.clock(),
            ),
            error=error,
            aborted=isinstance(error, RequestCancelledError),
        )
        if command.manifest and not isinstance(
            error, (ManifestWriteError, ManifestTargetConflict, OutputOverwriteRequired)
        ):
            _write_single_cli_manifest(
                command.manifest,
                record,
                overwrite=command.options.output_plan.overwrite,
            )
        progress.complete(1, lambda _cancelled: record)


def exit_code_for_batch_results(results: Sequence[ManifestRecord]) -> int:
    return int(any(not target_satisfied(item) for item in results))
