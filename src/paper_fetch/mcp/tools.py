"""Thin MCP tool wrappers over the service layer."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Mapping, Sequence

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult, ImageContent, TextContent
from pydantic import ValidationError

from ..config import build_runtime_env, resolve_mcp_download_dir
from ..http import HttpTransport
from ..models import ArticleModel, Asset, FetchEnvelope
from ..providers.base import ProviderFailure
from ..service import PaperFetchFailure, fetch_paper as service_fetch_paper
from ..service import probe_has_fulltext as service_probe_has_fulltext
from ..service import resolve_paper as service_resolve_paper
from ..utils import extend_unique, normalize_text
from .cache_index import (
    find_cached_entry,
    list_cache_entries,
    preferred_cached_entries,
    refresh_cache_index_for_doi,
)
from .schemas import (
    BatchCheckRequest,
    BatchResolveRequest,
    FetchPaperRequest,
    FetchStrategyInput,
    HasFulltextRequest,
    ResolvePaperRequest,
)

_MCP_DEFAULT_DOWNLOAD_DIR = object()
_BATCH_CHECK_MODES = {
    "article": ["article"],
    "metadata": ["metadata"],
}
_INLINE_IMAGE_MAX_COUNT = 3
_INLINE_IMAGE_MAX_BYTES = 2 * 1024 * 1024
_INLINE_IMAGE_MAX_TOTAL_BYTES = 8 * 1024 * 1024
_FETCH_PROGRESS_TOTAL = 4
_FETCH_LOGGER_NAMES = ("paper_fetch.service", "paper_fetch.http")
_LOG_LEVEL_BY_RECORD_LEVEL = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


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
        return {"status": "error", "reason": _validation_reason(error), "candidates": None}
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
        }
    if isinstance(error, ProviderFailure):
        status = error.code if error.code in {"no_access", "rate_limited"} else "error"
        return {"status": status, "reason": error.message, "candidates": None}
    return {"status": "error", "reason": str(error), "candidates": None}


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
    if include_article_for_assets and request.strategy.asset_profile in {"body", "all"}:
        requested_modes = set(requested_modes)
        requested_modes.add("article")
    return requested_modes


def _fetch_paper_envelope(
    request: FetchPaperRequest,
    *,
    env: Mapping[str, str] | None,
    download_dir: Path | None | object,
    transport: HttpTransport | None,
    include_article_for_assets: bool,
) -> FetchEnvelope:
    runtime_env = build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    envelope = service_fetch_paper(
        request.query,
        modes=_service_modes_for_fetch_request(request, include_article_for_assets=include_article_for_assets),
        strategy=request.strategy.to_service_strategy(),
        render=request.to_render_options(),
        download_dir=effective_download_dir,
        transport=transport,
        env=runtime_env,
    )
    if effective_download_dir is not None and envelope.doi:
        refresh_cache_index_for_doi(effective_download_dir, envelope.doi)
    return envelope


def _payload_from_envelope(envelope: FetchEnvelope, request: FetchPaperRequest) -> dict[str, Any]:
    payload = envelope.to_dict()
    if "article" not in request.requested_modes():
        payload["article"] = None
    return payload


def resolve_paper_payload(
    *,
    query: str | None = None,
    title: str | None = None,
    authors: list[str] | str | None = None,
    year: int | None = None,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    request = ResolvePaperRequest(query=query, title=title, authors=authors, year=year)
    runtime_env = build_runtime_env(env)
    resolved = service_resolve_paper(request.composed_query(), transport=transport, env=runtime_env)
    return resolved.to_dict()


def has_fulltext_payload(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    request = HasFulltextRequest(query=query)
    runtime_env = build_runtime_env(env)
    probe_result = service_probe_has_fulltext(request.query, transport=transport, env=runtime_env)
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
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    request = FetchPaperRequest(
        query=query,
        modes=modes,
        strategy=strategy,
        include_refs=include_refs,
        max_tokens=max_tokens,
    )
    envelope = _fetch_paper_envelope(
        request,
        env=env,
        download_dir=download_dir,
        transport=transport,
        include_article_for_assets=False,
    )
    return _payload_from_envelope(envelope, request)


def list_cached_payload(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    runtime_env = build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    if effective_download_dir is None:
        return {"download_dir": None, "entries": []}
    return {
        "download_dir": str(effective_download_dir),
        "entries": list_cache_entries(effective_download_dir),
    }


def get_cached_payload(
    *,
    doi: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    request = ResolvePaperRequest(query=doi)
    runtime_env = build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    if effective_download_dir is None:
        entries: list[dict[str, Any]] = []
    else:
        entries = refresh_cache_index_for_doi(effective_download_dir, request.composed_query())
    preferred = preferred_cached_entries(entries)
    return {
        "status": "hit" if entries else "miss",
        "doi": request.composed_query(),
        "download_dir": str(effective_download_dir) if effective_download_dir is not None else None,
        "entries": entries,
        "preferred": preferred,
    }


def batch_resolve_payload(
    *,
    queries: list[str],
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = BatchResolveRequest(queries=queries)
    runtime_env = build_runtime_env(env)
    transport = HttpTransport()
    results: list[dict[str, Any]] = []
    abort_reason: dict[str, Any] | None = None

    for query in request.queries:
        try:
            results.append(resolve_paper_payload(query=query, env=runtime_env, transport=transport))
        except Exception as error:
            payload = error_payload_from_exception(error)
            payload["query"] = query
            results.append(payload)
            if payload["status"] == "rate_limited":
                abort_reason = dict(payload)
                break

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
            "probe_state": payload.get("state"),
            "evidence": list(payload.get("evidence") or []),
            "warnings": list(payload.get("warnings") or []),
            "source": None,
            "source_trail": [],
            "token_estimate": None,
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
        "warnings": list(payload.get("warnings") or []),
        "source_trail": list(payload.get("source_trail") or []),
        "token_estimate": payload.get("token_estimate"),
    }


def batch_check_payload(
    *,
    queries: list[str],
    mode: str = "metadata",
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = BatchCheckRequest(queries=queries, mode=mode)
    runtime_env = build_runtime_env(env)
    transport = HttpTransport()
    results: list[dict[str, Any]] = []
    abort_reason: dict[str, Any] | None = None
    requested_modes = _BATCH_CHECK_MODES[request.mode]

    for query in request.queries:
        try:
            if request.mode == "metadata":
                payload = service_probe_has_fulltext(query, transport=transport, env=runtime_env).to_dict()
            else:
                payload = fetch_paper_payload(
                    query=query,
                    modes=requested_modes,
                    env=runtime_env,
                    download_dir=None,
                    transport=transport,
                )
            results.append(_batch_check_success_payload(query, payload, mode=request.mode))
        except Exception as error:
            payload = error_payload_from_exception(error)
            payload["query"] = query
            results.append(payload)
            if payload["status"] == "rate_limited":
                abort_reason = dict(payload)
                break

    return {
        "mode": request.mode,
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }


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


def _inline_image_contents(article: ArticleModel | None) -> tuple[list[TextContent | ImageContent], list[str]]:
    if article is None:
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

        if selected_count >= _INLINE_IMAGE_MAX_COUNT:
            omitted += 1
            continue
        if size > _INLINE_IMAGE_MAX_BYTES or total_bytes + size > _INLINE_IMAGE_MAX_TOTAL_BYTES:
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

    if request.strategy.asset_profile in {"body", "all"}:
        extra_content, image_warnings = _inline_image_contents(envelope.article)
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
            payload = parse_structured_log_message(record.getMessage(), logger_name=record.name)
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


def batch_resolve_tool(
    *,
    queries: list[str],
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(batch_resolve_payload(queries=queries, env=env), is_error=False)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def batch_check_tool(
    *,
    queries: list[str],
    mode: str = "metadata",
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(batch_check_payload(queries=queries, mode=mode, env=env), is_error=False)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


async def fetch_paper_tool_async(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
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
        )
    except Exception as error:
        await _report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed")
        return _tool_result(error_payload_from_exception(error), is_error=True)

    await _report_progress(ctx, 1, _FETCH_PROGRESS_TOTAL, "Fetching paper content")
    try:
        loop = asyncio.get_running_loop()
        bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None
        if bridge is None:
            envelope = await asyncio.to_thread(
                _fetch_paper_envelope,
                request,
                env=env,
                download_dir=download_dir,
                transport=None,
                include_article_for_assets=True,
            )
        else:
            with bridge:
                envelope = await asyncio.to_thread(
                    _fetch_paper_envelope,
                    request,
                    env=env,
                    download_dir=download_dir,
                    transport=None,
                    include_article_for_assets=True,
                )
        await _report_progress(ctx, 3, _FETCH_PROGRESS_TOTAL, "Shaping MCP result")
        result = build_fetch_tool_result(envelope, request)
        await _report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper complete")
        return result
    except Exception as error:
        await _report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed")
        return _tool_result(error_payload_from_exception(error), is_error=True)


async def batch_resolve_tool_async(
    *,
    queries: list[str],
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    try:
        request = BatchResolveRequest(queries=queries)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await _report_progress(ctx, 0, total_queries, "Starting batch_resolve")

    runtime_env = build_runtime_env(env)
    transport = HttpTransport()
    results: list[dict[str, Any]] = []
    abort_reason: dict[str, Any] | None = None
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        if bridge is not None:
            bridge.__enter__()
        for index, query in enumerate(request.queries, start=1):
            try:
                payload = await asyncio.to_thread(
                    resolve_paper_payload,
                    query=query,
                    env=runtime_env,
                    transport=transport,
                )
                results.append(payload)
            except Exception as error:
                payload = error_payload_from_exception(error)
                payload["query"] = query
                results.append(payload)
                if payload["status"] == "rate_limited":
                    abort_reason = dict(payload)
            await _report_progress(ctx, index, total_queries, f"Resolved {index} of {total_queries} queries")
            if abort_reason is not None:
                break
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
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    try:
        request = BatchCheckRequest(queries=queries, mode=mode)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await _report_progress(ctx, 0, total_queries, "Starting batch_check")

    runtime_env = build_runtime_env(env)
    transport = HttpTransport()
    requested_modes = _BATCH_CHECK_MODES[request.mode]
    results: list[dict[str, Any]] = []
    abort_reason: dict[str, Any] | None = None
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        if bridge is not None:
            bridge.__enter__()
        for index, query in enumerate(request.queries, start=1):
            try:
                if request.mode == "metadata":
                    payload = await asyncio.to_thread(
                        lambda: service_probe_has_fulltext(query, transport=transport, env=runtime_env).to_dict()
                    )
                else:
                    payload = await asyncio.to_thread(
                        fetch_paper_payload,
                        query=query,
                        modes=requested_modes,
                        env=runtime_env,
                        download_dir=None,
                        transport=transport,
                    )
                results.append(_batch_check_success_payload(query, payload, mode=request.mode))
            except Exception as error:
                payload = error_payload_from_exception(error)
                payload["query"] = query
                results.append(payload)
                if payload["status"] == "rate_limited":
                    abort_reason = dict(payload)
            await _report_progress(ctx, index, total_queries, f"Checked {index} of {total_queries} queries")
            if abort_reason is not None:
                break
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


def cached_entry_payload(
    *,
    entry_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    runtime_env = build_runtime_env(env)
    default_download_dir = resolve_mcp_download_dir(runtime_env)
    return find_cached_entry(default_download_dir, entry_id)
