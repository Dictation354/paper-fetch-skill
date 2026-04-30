"""MCP fetch, resolve, probe, and provider-status payload shaping."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
import threading
from typing import Any, Mapping

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult, ImageContent, TextContent

from ..config import build_runtime_env as _build_runtime_env
from ..http import HttpTransport
from ..models import ArticleModel, Asset, FetchEnvelope
from ..provider_catalog import is_official_provider, provider_status_order
from ..providers.base import ProviderStatusResult, build_provider_status_check
from ..providers.registry import build_clients as _build_clients
from ..runtime import RuntimeContext
from ..service import fetch_paper as _service_fetch_paper
from ..service import probe_has_fulltext as _service_probe_has_fulltext
from ..service import resolve_paper as _service_resolve_paper
from ..utils import extend_unique, normalize_text
from ..workflow.rendering import save_markdown_to_disk
from ..workflow.types import effective_asset_profile
from .batch import report_progress, run_blocking_call
from .cache_index import refresh_cache_index_for_doi as _refresh_cache_index_for_doi
from .cache_payloads import _MCP_DEFAULT_DOWNLOAD_DIR, _resolve_download_dir
from .fetch_cache import (
    FetchCache,
    fetch_envelope_cache_path,
    payload_from_envelope as _payload_from_envelope,
)
from .log_bridge import PaperFetchLogBridge
from .results import _tool_result, error_payload_from_exception
from .schemas import (
    FetchPaperRequest,
    FetchStrategyInput,
    HasFulltextRequest,
    InlineImageBudget,
    ResolvePaperRequest,
)

build_runtime_env = _build_runtime_env
service_fetch_paper = _service_fetch_paper
service_probe_has_fulltext = _service_probe_has_fulltext
service_resolve_paper = _service_resolve_paper
build_clients = _build_clients
refresh_cache_index_for_doi = _refresh_cache_index_for_doi

_FETCH_PROGRESS_TOTAL = 4
_PROVIDER_STATUS_ORDER = provider_status_order()


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


def _needs_download_dir_for_fetch(request: FetchPaperRequest) -> bool:
    return not request.no_download or request.prefer_cache


def _markdown_output_dir_for_fetch_request(
    request: FetchPaperRequest,
    *,
    runtime_env: Mapping[str, str],
    download_dir: Path | None | object,
) -> Path:
    if request.markdown_output_dir is not None:
        return Path(request.markdown_output_dir).expanduser()
    resolved_download_dir = _resolve_download_dir(runtime_env, download_dir)
    if resolved_download_dir is not None:
        return resolved_download_dir
    return _resolve_download_dir(runtime_env, _MCP_DEFAULT_DOWNLOAD_DIR) or Path.cwd()


def _save_markdown_for_fetch_request(
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    *,
    env: Mapping[str, str] | None,
    download_dir: Path | None | object,
    context: RuntimeContext | None = None,
) -> Path | None:
    if not request.save_markdown:
        return None
    runtime_env = dict(context.env) if context is not None and context.env is not None else build_runtime_env(env)
    markdown_output_path = _markdown_output_dir_for_fetch_request(
        request,
        runtime_env=runtime_env,
        download_dir=download_dir,
    )
    saved_path = save_markdown_to_disk(
        envelope,
        output_dir=markdown_output_path,
        render=request.to_render_options(),
        markdown_filename=request.markdown_filename,
    )
    if saved_path is not None and envelope.doi:
        FetchCache(
            saved_path.parent,
            refresh_cache_index_for_doi_fn=refresh_cache_index_for_doi,
        ).refresh_for_doi(envelope.doi)
    return saved_path


def _load_cached_fetch_envelope(
    request: FetchPaperRequest,
    *,
    download_dir: Path | None,
    context: RuntimeContext,
) -> FetchEnvelope | None:
    return FetchCache(
        download_dir,
        refresh_cache_index_for_doi_fn=refresh_cache_index_for_doi,
    ).load_fetch_envelope(
        request,
        resolve_paper_fn=service_resolve_paper,
        context=context,
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
    return service_resolve_paper(query, context=context)


def _call_service_probe_has_fulltext(query: str, *, context: RuntimeContext) -> Any:
    return service_probe_has_fulltext(query, context=context)


def _call_service_fetch_paper(
    query: str,
    *,
    modes: set[str],
    strategy,
    render,
    context: RuntimeContext,
) -> FetchEnvelope:
    return service_fetch_paper(
        query,
        modes=modes,
        strategy=strategy,
        render=render,
        context=context,
    )


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
    cache_download_dir = (
        _resolve_download_dir(runtime_env, download_dir) if _needs_download_dir_for_fetch(request) else None
    )
    service_download_dir = None if request.no_download else cache_download_dir
    runtime_context = RuntimeContext(
        env=runtime_env,
        transport=(context.transport if context is not None else transport),
        clients=(context.clients if context is not None else None),
        download_dir=service_download_dir,
        cancel_check=(context.cancel_check if context is not None else None),
        fetch_cache=FetchCache(service_download_dir),
    )
    try:
        cached_envelope = _load_cached_fetch_envelope(
            request,
            download_dir=cache_download_dir,
            context=runtime_context,
        )
        if cached_envelope is not None:
            return cached_envelope
        envelope = _call_service_fetch_paper(
            request.query,
            modes=_service_modes_for_fetch_request(request, include_article_for_assets=include_article_for_assets),
            strategy=request.strategy.to_service_strategy(),
            render=request.to_render_options(),
            context=runtime_context,
        )
        if not request.no_download and service_download_dir is not None and envelope.doi:
            _write_cached_fetch_envelope(service_download_dir, envelope, request)
        return envelope
    finally:
        runtime_context.close()


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
    no_download: bool = False,
    save_markdown: bool = False,
    markdown_output_dir: str | None = None,
    markdown_filename: str | None = None,
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
        no_download=no_download,
        save_markdown=save_markdown,
        markdown_output_dir=markdown_output_dir,
        markdown_filename=markdown_filename,
    )
    envelope = _fetch_paper_envelope(
        request,
        env=env,
        download_dir=download_dir,
        transport=transport,
        include_article_for_assets=False,
        context=context,
    )
    saved_markdown_path = _save_markdown_for_fetch_request(
        envelope,
        request,
        env=env,
        download_dir=download_dir,
        context=context,
    )
    payload = _payload_from_envelope(envelope, request)
    if saved_markdown_path is not None:
        payload["saved_markdown_path"] = str(saved_markdown_path)
    return payload


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


def build_fetch_tool_result(
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    *,
    saved_markdown_path: Path | None = None,
) -> CallToolResult:
    payload = _payload_from_envelope(envelope, request)
    if saved_markdown_path is not None:
        payload["saved_markdown_path"] = str(saved_markdown_path)
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
    no_download: bool = False,
    save_markdown: bool = False,
    markdown_output_dir: str | None = None,
    markdown_filename: str | None = None,
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
            no_download=no_download,
            save_markdown=save_markdown,
            markdown_output_dir=markdown_output_dir,
            markdown_filename=markdown_filename,
        )
        envelope = _fetch_paper_envelope(
            request,
            env=env,
            download_dir=download_dir,
            transport=None,
            include_article_for_assets=True,
        )
        saved_markdown_path = _save_markdown_for_fetch_request(
            envelope,
            request,
            env=env,
            download_dir=download_dir,
        )
        return build_fetch_tool_result(envelope, request, saved_markdown_path=saved_markdown_path)
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


async def fetch_paper_tool_async(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    no_download: bool = False,
    save_markdown: bool = False,
    markdown_output_dir: str | None = None,
    markdown_filename: str | None = None,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    ctx: Context | None = None,
) -> CallToolResult:
    await report_progress(ctx, 0, _FETCH_PROGRESS_TOTAL, "Validating fetch_paper request")
    try:
        request = FetchPaperRequest(
            query=query,
            modes=modes,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            prefer_cache=prefer_cache,
            no_download=no_download,
            save_markdown=save_markdown,
            markdown_output_dir=markdown_output_dir,
            markdown_filename=markdown_filename,
        )
    except Exception as error:
        await report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed")
        return _tool_result(error_payload_from_exception(error), is_error=True)

    await report_progress(ctx, 1, _FETCH_PROGRESS_TOTAL, "Fetching paper content")
    cancelled = threading.Event()
    runtime_context = RuntimeContext(env=build_runtime_env(env), cancel_check=cancelled.is_set)
    transport = runtime_context.transport
    try:
        loop = asyncio.get_running_loop()
        bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None
        if bridge is None:
            envelope = await run_blocking_call(
                _fetch_paper_envelope,
                request,
                env=runtime_context.env,
                download_dir=download_dir,
                transport=transport,
                include_article_for_assets=True,
                max_workers=1,
                cancel_event=cancelled,
            )
        else:
            with bridge:
                envelope = await run_blocking_call(
                    _fetch_paper_envelope,
                    request,
                    env=runtime_context.env,
                    download_dir=download_dir,
                    transport=transport,
                    include_article_for_assets=True,
                    max_workers=1,
                    cancel_event=cancelled,
                )
        await report_progress(ctx, 3, _FETCH_PROGRESS_TOTAL, "Shaping MCP result")
        saved_markdown_path = _save_markdown_for_fetch_request(
            envelope,
            request,
            env=runtime_context.env,
            download_dir=download_dir,
            context=runtime_context,
        )
        result = build_fetch_tool_result(envelope, request, saved_markdown_path=saved_markdown_path)
        await report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper complete")
        return result
    except asyncio.CancelledError:
        cancelled.set()
        raise
    except Exception as error:
        await report_progress(ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed")
        return _tool_result(error_payload_from_exception(error), is_error=True)
