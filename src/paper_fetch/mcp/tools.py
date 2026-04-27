"""Thin MCP tool wrappers over the service layer."""

from __future__ import annotations

import asyncio
import base64
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
import logging
import mimetypes
from pathlib import Path
import queue
import threading
from typing import Any, Callable, Mapping, Sequence

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult, ImageContent, TextContent
from pydantic import ValidationError

from ..config import build_runtime_env, resolve_mcp_download_dir
from ..http import HttpTransport, RequestCancelledError
from ..models import ArticleModel, Asset, FetchEnvelope
from ..provider_catalog import is_official_provider, provider_status_order
from ..providers.base import ProviderFailure, ProviderStatusResult, build_provider_status_check
from ..providers.registry import build_clients
from ..runtime import RuntimeContext
from ..service import PaperFetchFailure, fetch_paper as service_fetch_paper
from ..service import probe_has_fulltext as service_probe_has_fulltext
from ..service import resolve_paper as service_resolve_paper
from ..utils import extend_unique, normalize_text
from ..workflow.types import effective_asset_profile
from .cache_index import (
    find_cached_entry,
    list_cache_entries,
    preferred_cached_entries,
    refresh_cache_index_for_doi,
)
from .fetch_cache import (
    FETCH_ENVELOPE_CACHE_VERSION as _FETCH_ENVELOPE_CACHE_VERSION,
    FETCH_ENVELOPE_EXTRACTION_REVISION as _FETCH_ENVELOPE_EXTRACTION_REVISION,
    FetchCache,
    article_from_payload as _article_from_payload,
    cached_payload_satisfies_request as _cached_payload_satisfies_request,
    cached_request_matches as _cached_request_matches,
    envelope_from_payload as _envelope_from_payload,
    fetch_envelope_cache_path,
    mark_envelope_cached_with_current_revision as _mark_envelope_cached_with_current_revision,
    metadata_from_payload as _metadata_from_payload,
    payload_from_envelope as _payload_from_envelope,
    quality_from_payload as _quality_from_payload,
    request_cache_payload as _request_cache_payload,
    trace_from_payload as _trace_from_payload,
)
from .schemas import (
    BatchCheckRequest,
    BatchResolveRequest,
    FetchPaperRequest,
    FetchStrategyInput,
    HasFulltextRequest,
    InlineImageBudget,
    ResolvePaperRequest,
)

_MCP_DEFAULT_DOWNLOAD_DIR = object()
_BATCH_CHECK_MODES = {
    "article": ["article"],
    "metadata": ["metadata"],
}
_FETCH_PROGRESS_TOTAL = 4
_FETCH_LOGGER_NAMES = ("paper_fetch.service", "paper_fetch.http")
_PROVIDER_STATUS_ORDER = provider_status_order()
_CACHE_COMPAT_SYMBOLS = (
    _FETCH_ENVELOPE_CACHE_VERSION,
    _FETCH_ENVELOPE_EXTRACTION_REVISION,
    _article_from_payload,
    _cached_payload_satisfies_request,
    _cached_request_matches,
    _envelope_from_payload,
    _mark_envelope_cached_with_current_revision,
    _metadata_from_payload,
    _payload_from_envelope,
    _quality_from_payload,
    _request_cache_payload,
    _trace_from_payload,
)
_LOG_LEVEL_BY_RECORD_LEVEL = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


async def _run_blocking_call(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    results: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def invoke() -> Any:
        try:
            results.put((True, func(*args, **kwargs)))
        except BaseException as exc:
            results.put((False, exc))

    threading.Thread(target=invoke, daemon=True).start()
    while True:
        try:
            success, value = results.get_nowait()
            break
        except queue.Empty:
            await asyncio.sleep(0.01)
    if success:
        return value
    raise value


def _dump_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2)


def _tool_result(
    payload: Mapping[str, Any],
    *,
    is_error: bool,
    extra_content: Sequence[TextContent | ImageContent] | None = None,
) -> CallToolResult:
    content: list[TextContent | ImageContent] = [TextContent(type="text", text=_dump_payload(payload))]
    if extra_content:
        content.extend(extra_content)
    return CallToolResult(
        content=content,
        structuredContent=dict(payload),
        isError=is_error,
    )


def _validation_reason(error: ValidationError) -> str:
    messages: list[str] = []
    for entry in error.errors(include_url=False):
        location = ".".join(str(part) for part in entry.get("loc", ())) or "request"
        messages.append(f"{location}: {entry.get('msg', 'invalid value')}")
    return "Invalid tool arguments. " + "; ".join(messages)


def error_payload_from_exception(error: Exception) -> dict[str, Any]:
    if isinstance(error, ValidationError):
        return {"status": "error", "reason": _validation_reason(error), "candidates": None, "missing_env": None}
    if isinstance(error, RequestCancelledError):
        return {"status": "error", "reason": "Request cancelled.", "candidates": None, "missing_env": None}
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
            "missing_env": None,
        }
    if isinstance(error, ProviderFailure):
        status = error.code if error.code in {"no_access", "rate_limited"} else "error"
        if error.code == "not_configured" and error.missing_env:
            status = "no_access"
        return {
            "status": status,
            "reason": error.message,
            "candidates": None,
            "missing_env": error.missing_env or None,
        }
    return {"status": "error", "reason": str(error), "candidates": None, "missing_env": None}


def _resolve_download_dir(
    runtime_env: Mapping[str, str],
    download_dir: Path | None | object,
) -> Path | None:
    if download_dir is _MCP_DEFAULT_DOWNLOAD_DIR:
        return resolve_mcp_download_dir(runtime_env)
    return download_dir


def _service_modes_for_fetch_request(
    request: FetchPaperRequest,
    *,
    include_article_for_assets: bool,
) -> set[str]:
    requested_modes = request.requested_modes()
    if include_article_for_assets and request.strategy.asset_profile != "none":
        requested_modes = set(requested_modes)
        requested_modes.add("article")
    return requested_modes


def _load_cached_fetch_envelope(
    request: FetchPaperRequest,
    *,
    download_dir: Path | None,
    transport: HttpTransport | None,
    env: Mapping[str, str],
) -> FetchEnvelope | None:
    return FetchCache(
        download_dir,
        refresh_cache_index_for_doi_fn=refresh_cache_index_for_doi,
    ).load_fetch_envelope(
        request,
        resolve_paper_fn=service_resolve_paper,
        transport=transport,
        env=env,
    )


def _write_cached_fetch_envelope(
    download_dir: Path,
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
) -> None:
    FetchCache(
        download_dir,
        refresh_cache_index_for_doi_fn=refresh_cache_index_for_doi,
    ).write_fetch_envelope(envelope, request)


def _call_service_resolve_paper(query: str, *, context: RuntimeContext) -> Any:
    try:
        return service_resolve_paper(query, context=context)
    except TypeError as exc:
        if "context" not in str(exc):
            raise
        return service_resolve_paper(query, transport=context.transport, env=context.env)


def _call_service_probe_has_fulltext(query: str, *, context: RuntimeContext) -> Any:
    try:
        return service_probe_has_fulltext(query, context=context)
    except TypeError as exc:
        if "context" not in str(exc):
            raise
        return service_probe_has_fulltext(query, transport=context.transport, env=context.env)


def _call_service_fetch_paper(
    query: str,
    *,
    modes: set[str],
    strategy,
    render,
    download_dir: Path | None,
    context: RuntimeContext,
) -> FetchEnvelope:
    legacy_kwargs = {
        "modes": modes,
        "strategy": strategy,
        "render": render,
        "download_dir": download_dir,
        "transport": context.transport,
        "env": context.env,
    }
    try:
        return service_fetch_paper(query, context=context, **legacy_kwargs)
    except TypeError as exc:
        if "context" not in str(exc):
            raise
        return service_fetch_paper(query, **legacy_kwargs)


def _fetch_paper_envelope(
    request: FetchPaperRequest,
    *,
    env: Mapping[str, str] | None,
    download_dir: Path | None | object,
    transport: HttpTransport | None,
    include_article_for_assets: bool,
    context: RuntimeContext | None = None,
) -> FetchEnvelope:
    runtime_env = dict(context.env) if context is not None and context.env is not None else build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    runtime_context = RuntimeContext(
        env=runtime_env,
        transport=(context.transport if context is not None else transport),
        clients=(context.clients if context is not None else None),
        download_dir=effective_download_dir,
        cancel_check=(context.cancel_check if context is not None else None),
        fetch_cache=FetchCache(effective_download_dir),
    )
    cached_envelope = _load_cached_fetch_envelope(
        request,
        download_dir=effective_download_dir,
        transport=runtime_context.transport,
        env=runtime_context.env or runtime_env,
    )
    if cached_envelope is not None:
        return cached_envelope
    envelope = _call_service_fetch_paper(
        request.query,
        modes=_service_modes_for_fetch_request(request, include_article_for_assets=include_article_for_assets),
        strategy=request.strategy.to_service_strategy(),
        render=request.to_render_options(),
        download_dir=effective_download_dir,
        context=runtime_context,
    )
    if effective_download_dir is not None and envelope.doi:
        _write_cached_fetch_envelope(effective_download_dir, envelope, request)
    return envelope


def _fetch_envelope_cache_path(download_dir: Path, doi: str) -> Path:
    return fetch_envelope_cache_path(download_dir, doi)


def resolve_paper_payload(
    *,
    query: str | None = None,
    title: str | None = None,
    authors: list[str] | str | None = None,
    year: int | None = None,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    context: RuntimeContext | None = None,
) -> dict[str, Any]:
    request = ResolvePaperRequest(query=query, title=title, authors=authors, year=year)
    runtime_context = context or RuntimeContext(env=build_runtime_env(env), transport=transport)
    resolved = _call_service_resolve_paper(request.composed_query(), context=runtime_context)
    return resolved.to_dict()


def has_fulltext_payload(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    context: RuntimeContext | None = None,
) -> dict[str, Any]:
    request = HasFulltextRequest(query=query)
    runtime_context = context or RuntimeContext(env=build_runtime_env(env), transport=transport)
    probe_result = _call_service_probe_has_fulltext(request.query, context=runtime_context)
    payload = probe_result.to_dict()
    payload.pop("title", None)
    return payload


def fetch_paper_payload(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    transport: HttpTransport | None = None,
    context: RuntimeContext | None = None,
) -> dict[str, Any]:
    request = FetchPaperRequest(
        query=query,
        modes=modes,
        strategy=strategy,
        include_refs=include_refs,
        max_tokens=max_tokens,
        prefer_cache=prefer_cache,
    )
    envelope = _fetch_paper_envelope(
        request,
        env=env,
        download_dir=download_dir,
        transport=transport,
        include_article_for_assets=False,
        context=context,
    )
    return _payload_from_envelope(envelope, request)


def list_cached_payload(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    runtime_env = build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    return FetchCache(
        effective_download_dir,
        list_cache_entries_fn=list_cache_entries,
    ).list_payload()


def get_cached_payload(
    *,
    doi: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    request = ResolvePaperRequest(query=doi)
    runtime_env = build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    return FetchCache(
        effective_download_dir,
        refresh_cache_index_for_doi_fn=refresh_cache_index_for_doi,
        preferred_cached_entries_fn=preferred_cached_entries,
    ).get_payload(request.composed_query())


def _provider_status_error_payload(
    provider: str,
    *,
    official_provider: bool,
    message: str,
) -> dict[str, Any]:
    return ProviderStatusResult(
        provider=provider,
        status="error",
        available=False,
        official_provider=official_provider,
        notes=[],
        checks=[build_provider_status_check("diagnostics", "error", message)],
    ).to_dict()


def provider_status_payload(
    *,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    runtime_env = build_runtime_env(env)
    active_transport = transport or HttpTransport()
    clients = build_clients(transport=active_transport, env=runtime_env)
    results: list[dict[str, Any]] = []

    for provider_name in _PROVIDER_STATUS_ORDER:
        client = clients.get(provider_name)
        if client is None:
            results.append(
                _provider_status_error_payload(
                    provider_name,
                    official_provider=is_official_provider(provider_name),
                    message=f"{provider_name} is not registered in the provider client registry.",
                )
            )
            continue
        try:
            results.append(client.probe_status().to_dict())
        except Exception as error:
            results.append(
                _provider_status_error_payload(
                    provider_name,
                    official_provider=bool(getattr(client, "official_provider", is_official_provider(provider_name))),
                    message=f"Provider diagnostics failed unexpectedly: {error}",
                )
            )

    return {"providers": results}


def batch_resolve_payload(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = BatchResolveRequest(queries=queries, concurrency=concurrency)
    runtime_env = build_runtime_env(env)
    runtime_context = RuntimeContext(env=runtime_env)
    results, abort_reason = _run_batch_sync(
        queries=request.queries,
        concurrency=request.concurrency,
        process_item=lambda query: resolve_paper_payload(query=query, context=runtime_context),
    )

    return {
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }


def _batch_check_success_payload(query: str, payload: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    title = None
    if mode == "metadata":
        title = payload.get("title")
        return {
            "query": query,
            "doi": payload.get("doi"),
            "title": title,
            "has_fulltext": True if payload.get("state") == "likely_yes" else None,
            "content_kind": None,
            "has_abstract": None,
            "probe_state": payload.get("state"),
            "evidence": list(payload.get("evidence") or []),
            "warnings": list(payload.get("warnings") or []),
            "source": None,
            "source_trail": [],
            "trace": [],
            "token_estimate": None,
            "token_estimate_breakdown": None,
        }
    else:
        article = payload.get("article") or {}
        if isinstance(article, Mapping):
            metadata = article.get("metadata") or {}
            if isinstance(metadata, Mapping):
                title = metadata.get("title")

    return {
        "query": query,
        "doi": payload.get("doi"),
        "title": title,
        "source": payload.get("source"),
        "has_fulltext": payload.get("has_fulltext"),
        "content_kind": payload.get("content_kind"),
        "has_abstract": payload.get("has_abstract"),
        "warnings": list(payload.get("warnings") or []),
        "source_trail": list(payload.get("source_trail") or []),
        "trace": list(payload.get("trace") or []),
        "token_estimate": payload.get("token_estimate"),
        "token_estimate_breakdown": payload.get("token_estimate_breakdown"),
    }


def batch_check_payload(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = BatchCheckRequest(queries=queries, mode=mode, concurrency=concurrency)
    runtime_env = build_runtime_env(env)
    runtime_context = RuntimeContext(env=runtime_env, download_dir=None)
    runtime_context.get_clients()
    requested_modes = _BATCH_CHECK_MODES[request.mode]
    results, abort_reason = _run_batch_sync(
        queries=request.queries,
        concurrency=request.concurrency,
        process_item=lambda query: _run_batch_check_item(
            query,
            mode=request.mode,
            context=runtime_context,
            requested_modes=requested_modes,
        ),
    )

    return {
        "mode": request.mode,
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }


def _run_batch_check_item(
    query: str,
    *,
    mode: str,
    context: RuntimeContext,
    requested_modes: list[str],
) -> dict[str, Any]:
    if mode == "metadata":
        payload = _call_service_probe_has_fulltext(query, context=context).to_dict()
    else:
        payload = fetch_paper_payload(
            query=query,
            modes=requested_modes,
            download_dir=None,
            context=context,
        )
    return _batch_check_success_payload(query, payload, mode=mode)


def _run_batch_sync(
    *,
    queries: list[str],
    concurrency: int,
    process_item: Callable[[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    max_workers = max(1, min(concurrency, len(queries)))
    results: list[dict[str, Any] | None] = [None] * len(queries)
    abort_reason: dict[str, Any] | None = None

    if max_workers == 1:
        for index, query in enumerate(queries):
            try:
                results[index] = process_item(query)
            except Exception as error:
                payload = error_payload_from_exception(error)
                payload["query"] = query
                results[index] = payload
                if payload["status"] == "rate_limited":
                    abort_reason = dict(payload)
                    break
        return [result for result in results if result is not None], abort_reason

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending: dict[Any, tuple[int, str]] = {}
        next_index = 0

        def submit(index: int) -> None:
            future = executor.submit(process_item, queries[index])
            pending[future] = (index, queries[index])

        while next_index < len(queries) and len(pending) < max_workers:
            submit(next_index)
            next_index += 1

        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index, query = pending.pop(future)
                try:
                    results[index] = future.result()
                except Exception as error:
                    payload = error_payload_from_exception(error)
                    payload["query"] = query
                    results[index] = payload
                    if payload["status"] == "rate_limited" and abort_reason is None:
                        abort_reason = dict(payload)
                if abort_reason is None and next_index < len(queries):
                    submit(next_index)
                    next_index += 1

    return [result for result in results if result is not None], abort_reason


def _is_body_figure_asset(asset: Asset) -> bool:
    if normalize_text(asset.kind).lower() != "figure":
        return False
    section = normalize_text(asset.section).lower()
    if not section:
        return True
    return section not in {"supplementary", "appendix", "references", "diagnostics"}


def _inline_image_note(asset: Asset, path: Path) -> str:
    heading = normalize_text(asset.heading) or "Figure"
    caption = normalize_text(asset.caption)
    lines = [f"Inline figure: {heading}"]
    if caption:
        lines.append(f"Caption: {caption}")
    lines.append(f"Local path: {path}")
    return "\n".join(lines)


def _inline_image_contents(
    article: ArticleModel | None,
    *,
    budget: InlineImageBudget,
) -> tuple[list[TextContent | ImageContent], list[str]]:
    if article is None:
        return [], []
    if budget.disabled:
        return [], []

    contents: list[TextContent | ImageContent] = []
    omitted = 0
    total_bytes = 0
    selected_count = 0

    for asset in article.assets:
        if not _is_body_figure_asset(asset):
            continue

        path_text = normalize_text(asset.path)
        if not path_text:
            omitted += 1
            continue
        path = Path(path_text).expanduser()
        if not path.is_file():
            omitted += 1
            continue

        mime_type = mimetypes.guess_type(path.name)[0] or ""
        if not mime_type.startswith("image/"):
            omitted += 1
            continue

        try:
            size = path.stat().st_size
        except OSError:
            omitted += 1
            continue

        if selected_count >= budget.max_images:
            omitted += 1
            continue
        if size > budget.max_bytes_per_image or total_bytes + size > budget.max_total_bytes:
            omitted += 1
            continue

        try:
            image_bytes = path.read_bytes()
        except OSError:
            omitted += 1
            continue

        total_bytes += len(image_bytes)
        selected_count += 1
        contents.append(TextContent(type="text", text=_inline_image_note(asset, path)))
        contents.append(
            ImageContent(
                type="image",
                data=base64.b64encode(image_bytes).decode("ascii"),
                mimeType=mime_type,
            )
        )

    warnings: list[str] = []
    if omitted:
        warnings.append(
            f"{omitted} local figure asset(s) were omitted from inline MCP image output because they exceeded limits or were not readable images."
        )
    return contents, warnings


def build_fetch_tool_result(envelope: FetchEnvelope, request: FetchPaperRequest) -> CallToolResult:
    payload = _payload_from_envelope(envelope, request)
    extra_content: list[TextContent | ImageContent] = []

    resolved_asset_profile = effective_asset_profile(
        request.strategy.asset_profile,
        source_name=envelope.source,
    )
    if resolved_asset_profile in {"body", "all"}:
        extra_content, image_warnings = _inline_image_contents(
            envelope.article,
            budget=request.strategy.resolved_inline_image_budget(),
        )
        warnings = list(payload.get("warnings") or [])
        extend_unique(warnings, image_warnings)
        payload["warnings"] = warnings

    return _tool_result(payload, is_error=False, extra_content=extra_content)


def _parse_log_value(raw_value: str) -> Any:
    if raw_value == "None":
        return None
    lowered = raw_value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if any(marker in raw_value for marker in (".", "e", "E")):
            return float(raw_value)
        return int(raw_value)
    except ValueError:
        return raw_value


def parse_structured_log_message(message: str, *, logger_name: str | None = None) -> dict[str, Any]:
    normalized = normalize_text(message)
    payload: dict[str, Any] = {"event": "log"}
    if logger_name:
        payload["logger"] = logger_name
    if not normalized:
        return payload

    parts = normalized.split()
    payload["event"] = parts[0]
    unparsed_tokens: list[str] = []

    for token in parts[1:]:
        if "=" not in token:
            unparsed_tokens.append(token)
            continue
        key, raw_value = token.split("=", 1)
        if not key:
            unparsed_tokens.append(token)
            continue
        payload[key] = _parse_log_value(raw_value)

    if unparsed_tokens:
        payload["raw_message"] = normalized
    return payload


def structured_log_payload_from_record(record: logging.LogRecord) -> dict[str, Any]:
    raw_payload = getattr(record, "structured_data", None)
    if isinstance(raw_payload, Mapping):
        payload = dict(raw_payload)
        payload["event"] = normalize_text(payload.get("event")) or "log"
        payload.setdefault("logger", record.name)
        return payload
    return parse_structured_log_message(record.getMessage(), logger_name=record.name)


def _mcp_log_level(record: logging.LogRecord) -> str:
    for level, name in sorted(_LOG_LEVEL_BY_RECORD_LEVEL.items()):
        if record.levelno <= level:
            return name
    return "debug"


class StructuredLogNotificationHandler(logging.Handler):
    def __init__(self, *, ctx: Context, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(level=logging.DEBUG)
        self._ctx = ctx
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = structured_log_payload_from_record(record)
            asyncio.run_coroutine_threadsafe(
                self._ctx.session.send_log_message(
                    level=_mcp_log_level(record),
                    data=payload,
                    logger=record.name,
                    related_request_id=self._ctx.request_id,
                ),
                self._loop,
            )
        except Exception:
            return


class PaperFetchLogBridge:
    def __init__(self, *, ctx: Context, loop: asyncio.AbstractEventLoop) -> None:
        self._ctx = ctx
        self._loop = loop
        self._handler = StructuredLogNotificationHandler(ctx=ctx, loop=loop)
        self._logger_states: list[tuple[logging.Logger, int]] = []

    def __enter__(self) -> "PaperFetchLogBridge":
        for logger_name in _FETCH_LOGGER_NAMES:
            logger = logging.getLogger(logger_name)
            self._logger_states.append((logger, logger.level))
            logger.addHandler(self._handler)
            logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        for logger, level in self._logger_states:
            logger.removeHandler(self._handler)
            logger.setLevel(level)
        self._handler.close()


async def _report_progress(
    ctx: Context | None,
    progress: float,
    total: float | None,
    message: str,
) -> None:
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress=progress, total=total, message=message)
    except Exception:
        return


def resolve_paper_tool(
    *,
    query: str | None = None,
    title: str | None = None,
    authors: list[str] | str | None = None,
    year: int | None = None,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(
            resolve_paper_payload(
                query=query,
                title=title,
                authors=authors,
                year=year,
                env=env,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def has_fulltext_tool(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(
            has_fulltext_payload(
                query=query,
                env=env,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def fetch_paper_tool(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    try:
        request = FetchPaperRequest(
            query=query,
            modes=modes,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            prefer_cache=prefer_cache,
        )
        envelope = _fetch_paper_envelope(
            request,
            env=env,
            download_dir=download_dir,
            transport=None,
            include_article_for_assets=True,
        )
        return build_fetch_tool_result(envelope, request)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def list_cached_tool(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    try:
        return _tool_result(
            list_cached_payload(
                env=env,
                download_dir=download_dir,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def get_cached_tool(
    *,
    doi: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    try:
        return _tool_result(
            get_cached_payload(
                doi=doi,
                env=env,
                download_dir=download_dir,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def provider_status_tool(
    *,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(provider_status_payload(env=env), is_error=False)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def batch_resolve_tool(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(batch_resolve_payload(queries=queries, concurrency=concurrency, env=env), is_error=False)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def batch_check_tool(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(
            batch_check_payload(queries=queries, mode=mode, concurrency=concurrency, env=env),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


async def fetch_paper_tool_async(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    ctx: Context | None = None,
) -> CallToolResult:
    await _report_progress(ctx, 0, _FETCH_PROGRESS_TOTAL, "Validating fetch_paper request")
    try:
        request = FetchPaperRequest(
            query=query,
            modes=modes,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            prefer_cache=prefer_cache,
        )
    except Exception as error:
        await _report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed")
        return _tool_result(error_payload_from_exception(error), is_error=True)

    await _report_progress(ctx, 1, _FETCH_PROGRESS_TOTAL, "Fetching paper content")
    cancelled = threading.Event()
    runtime_context = RuntimeContext(env=build_runtime_env(env), cancel_check=cancelled.is_set)
    transport = runtime_context.transport
    try:
        loop = asyncio.get_running_loop()
        bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None
        if bridge is None:
            envelope = await _run_blocking_call(
                _fetch_paper_envelope,
                request,
                env=runtime_context.env,
                download_dir=download_dir,
                transport=transport,
                include_article_for_assets=True,
            )
        else:
            with bridge:
                envelope = await _run_blocking_call(
                    _fetch_paper_envelope,
                    request,
                    env=runtime_context.env,
                    download_dir=download_dir,
                    transport=transport,
                    include_article_for_assets=True,
                )
        await _report_progress(ctx, 3, _FETCH_PROGRESS_TOTAL, "Shaping MCP result")
        result = build_fetch_tool_result(envelope, request)
        await _report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper complete")
        return result
    except asyncio.CancelledError:
        cancelled.set()
        raise
    except Exception as error:
        await _report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed")
        return _tool_result(error_payload_from_exception(error), is_error=True)


async def batch_resolve_tool_async(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    try:
        request = BatchResolveRequest(queries=queries, concurrency=concurrency)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await _report_progress(ctx, 0, total_queries, "Starting batch_resolve")

    runtime_env = build_runtime_env(env)
    cancelled = threading.Event()
    runtime_context = RuntimeContext(env=runtime_env, cancel_check=cancelled.is_set)
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        if bridge is not None:
            bridge.__enter__()
        results, abort_reason = await _run_batch_async(
            queries=request.queries,
            concurrency=request.concurrency,
            process_item=lambda query: resolve_paper_payload(query=query, context=runtime_context),
            ctx=ctx,
            progress_prefix="Resolved",
        )
    except asyncio.CancelledError:
        cancelled.set()
        raise
    finally:
        if bridge is not None:
            bridge.__exit__(None, None, None)

    payload = {
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }
    await _report_progress(
        ctx,
        total_queries,
        total_queries,
        "batch_resolve complete" if abort_reason is None else "batch_resolve stopped after rate limit",
    )
    return _tool_result(payload, is_error=False)


async def batch_check_tool_async(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    try:
        request = BatchCheckRequest(queries=queries, mode=mode, concurrency=concurrency)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await _report_progress(ctx, 0, total_queries, "Starting batch_check")

    runtime_env = build_runtime_env(env)
    cancelled = threading.Event()
    runtime_context = RuntimeContext(env=runtime_env, download_dir=None, cancel_check=cancelled.is_set)
    runtime_context.get_clients()
    requested_modes = _BATCH_CHECK_MODES[request.mode]
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        if bridge is not None:
            bridge.__enter__()
        results, abort_reason = await _run_batch_async(
            queries=request.queries,
            concurrency=request.concurrency,
            process_item=lambda query: _run_batch_check_item(
                query,
                mode=request.mode,
                context=runtime_context,
                requested_modes=requested_modes,
            ),
            ctx=ctx,
            progress_prefix="Checked",
        )
    except asyncio.CancelledError:
        cancelled.set()
        raise
    finally:
        if bridge is not None:
            bridge.__exit__(None, None, None)

    payload = {
        "mode": request.mode,
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }
    await _report_progress(
        ctx,
        total_queries,
        total_queries,
        "batch_check complete" if abort_reason is None else "batch_check stopped after rate limit",
    )
    return _tool_result(payload, is_error=False)


async def _run_batch_async(
    *,
    queries: list[str],
    concurrency: int,
    process_item: Callable[[str], dict[str, Any]],
    ctx: Context | None,
    progress_prefix: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    results: list[dict[str, Any] | None] = [None] * len(queries)
    abort_reason: dict[str, Any] | None = None
    completed = 0
    max_workers = max(1, min(concurrency, len(queries)))
    pending: dict[asyncio.Task[dict[str, Any]], tuple[int, str]] = {}
    next_index = 0

    def launch(index: int) -> None:
        task = asyncio.create_task(_run_blocking_call(process_item, queries[index]))
        pending[task] = (index, queries[index])

    while next_index < len(queries) and len(pending) < max_workers:
        launch(next_index)
        next_index += 1

    while pending:
        done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            index, query = pending.pop(task)
            try:
                results[index] = task.result()
            except Exception as error:
                payload = error_payload_from_exception(error)
                payload["query"] = query
                results[index] = payload
                if payload["status"] == "rate_limited" and abort_reason is None:
                    abort_reason = dict(payload)
            completed += 1
            await _report_progress(ctx, completed, len(queries), f"{progress_prefix} {completed} of {len(queries)} queries")
            if abort_reason is None and next_index < len(queries):
                launch(next_index)
                next_index += 1

    return [result for result in results if result is not None], abort_reason


def cached_entry_payload(
    *,
    entry_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    runtime_env = build_runtime_env(env)
    default_download_dir = resolve_mcp_download_dir(runtime_env)
    return find_cached_entry(default_download_dir, entry_id)
