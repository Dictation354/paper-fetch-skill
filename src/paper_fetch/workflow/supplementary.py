"""Independent supplementary task using the normal resolution and provider routing."""

from __future__ import annotations

from ..models import FetchEnvelope
from ..failure import FailureDiagnostics
from ..models.builders import build_metadata
from ..providers.base import ProviderFailure
from ..reason_codes import NOT_SUPPORTED
from ..tracing import (
    TraceContext,
    resolve_event,
    merge_trace,
    trace_event,
)
from .fulltext import _ranked_fulltext_provider_candidates
from .metadata import fetch_metadata_for_resolved_query
from .routing import resolve_query_with_session_cache
from .types import PaperFetchFailure


def render_supplementary_index(result) -> str:
    lines = []
    for asset in result.assets:
        name = str(
            asset.get("heading")
            or asset.get("filename_hint")
            or "Supplementary Material"
        )
        name = name.replace("\n", " ").replace("[", "\\[").replace("]", "\\]")
        url = (
            asset.get("download_url")
            or asset.get("original_url")
            or asset.get("url")
            or asset.get("link")
            or asset.get("source_url")
        )
        line = f"- [{name}](<{url}>)" if url else f"- {name}"
        if asset.get("path"):
            line += f" — [local](<{asset['path']}>)"
        lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def fetch_supplementary(query, *, strategy, context, modes, resolve_paper_fn):
    context.fetch_trace = []
    context.report_progress("stage", stage="identity")
    resolved = resolve_query_with_session_cache(
        query, resolver=resolve_paper_fn, context=context
    )
    if resolved.candidates and not resolved.doi:
        raise PaperFetchFailure(
            "ambiguous",
            "Query resolution is ambiguous; choose one DOI.",
            candidates=resolved.candidates,
        )
    try:
        clients = context.get_clients()
        metadata, selected, metadata_trail = fetch_metadata_for_resolved_query(
            resolved,
            clients=clients,
            strategy=strategy,
            context=context,
        )
    except (ProviderFailure, PaperFetchFailure) as exc:
        error = (
            PaperFetchFailure.from_provider_failure(exc)
            if isinstance(exc, ProviderFailure)
            else exc
        )
        trace = [
            resolve_event(resolved.query_kind),
            *context.fetch_trace,
            *[event for event in error.trace if event not in context.fetch_trace],
        ]
        context.fetch_trace = trace
        raise PaperFetchFailure(
            error.status,
            error.reason,
            doi=error.doi or resolved.doi,
            candidates=error.candidates,
            warnings=error.warnings,
            trace=trace,
            retry_after_seconds=error.retry_after_seconds,
            missing_env=error.missing_env,
            diagnostics=error.diagnostics.with_updates(
                provider=error.diagnostics.provider or resolved.provider_hint,
                stage=error.diagnostics.stage or "supplementary",
                retryable=False
                if error.status == NOT_SUPPORTED
                else error.diagnostics.retryable,
            ),
        ) from exc
    doi = str(metadata.get("doi") or resolved.doi or metadata.get("arxiv_id") or "")
    trail = [resolve_event(resolved.query_kind), *metadata_trail]
    trace = merge_trace(trail, context.fetch_trace)
    context.fetch_trace = trace
    failures = []

    def failure(exc=None, *, provider=None):
        diagnostics = exc.diagnostics if exc is not None else FailureDiagnostics()
        return PaperFetchFailure(
            exc.code if exc is not None else NOT_SUPPORTED,
            exc.message
            if exc is not None
            else "This source does not support supplementary retrieval.",
            doi=doi or None,
            trace=[
                *trace,
                *[event for event in (exc.trace if exc else []) if event not in trace],
            ],
            warnings=getattr(exc, "warnings", None),
            missing_env=getattr(exc, "missing_env", None),
            retry_after_seconds=getattr(exc, "retry_after_seconds", None),
            diagnostics=diagnostics.with_updates(
                provider=diagnostics.provider or provider,
                stage="supplementary",
                retryable=False
                if exc is None or exc.code == NOT_SUPPORTED
                else diagnostics.retryable,
            ),
        )

    for name, _, _ in _ranked_fulltext_provider_candidates(
        resolved=resolved,
        metadata=metadata,
        selected_provider=selected,
        strategy=strategy,
    ):
        context.raise_if_cancelled()
        context.report_progress("stage", stage="fetching")
        client = clients.get(name)
        if client is None:
            continue
        try:
            result, acquisition = client.fetch_supplementary(
                doi,
                metadata,
                context.artifact_store.asset_download_dir,
                context=context,
            )
        except ProviderFailure as exc:
            failures.append((name, exc))
            trace.append(
                trace_event(
                    "supplementary",
                    name,
                    "fail",
                    code=exc.code,
                    message=exc.message,
                    context=TraceContext(provider=name, route=exc.diagnostics.route),
                )
            )
            if exc.code != NOT_SUPPORTED:
                raise failure(exc, provider=name) from exc
            continue
        trace.append(trace_event("supplementary", name, "success", code=result.status))
        context.fetch_trace = trace
        return FetchEnvelope(
            doi=doi or None,
            source=name,
            target="supplementary",
            supplementary=result,
            metadata=build_metadata(metadata),
            acquisition=acquisition,
            markdown=render_supplementary_index(result)
            if "markdown" in modes
            else None,
            trace=trace,
        )
    if failures:
        name, last_failure = failures[-1]
        raise failure(last_failure, provider=name)
    raise failure(provider=selected or resolved.provider_hint)
