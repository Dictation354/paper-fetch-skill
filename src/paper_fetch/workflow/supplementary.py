"""Independent supplementary task using the normal resolution and provider routing."""

from __future__ import annotations

from ..models import FetchEnvelope
from ..models.builders import build_metadata
from ..providers.base import ProviderFailure
from ..reason_codes import NOT_SUPPORTED
from ..tracing import resolve_marker, project_source_trail_trace, trace_event
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
    clients = dict(context.get_clients())
    metadata, selected, metadata_trail = fetch_metadata_for_resolved_query(
        resolved,
        clients=clients,
        strategy=strategy,
        context=context,
    )
    doi = str(metadata.get("doi") or resolved.doi or metadata.get("arxiv_id") or "")
    trail = [resolve_marker(resolved.query_kind), *metadata_trail]
    trace = project_source_trail_trace(trail, [])
    failures = []
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
            failures.append(exc)
            trace.append(
                trace_event(
                    "supplementary", name, "fail", code=exc.code, message=exc.message
                )
            )
            if exc.code != NOT_SUPPORTED:
                raise PaperFetchFailure.from_provider_failure(exc) from exc
            continue
        trace.append(trace_event("supplementary", name, "success", code=result.status))
        context.fetch_trace = trace
        return FetchEnvelope(
            doi=doi or None,
            source=name,
            target="supplementary",
            supplementary=result,
            has_fulltext=False,
            metadata=build_metadata(metadata),
            acquisition=acquisition,
            markdown=render_supplementary_index(result)
            if "markdown" in modes
            else None,
            trace=trace,
            source_trail=trail,
        )
    if failures:
        raise PaperFetchFailure.from_provider_failure(failures[-1])
    raise PaperFetchFailure(
        NOT_SUPPORTED, "This source does not support supplementary retrieval."
    )
