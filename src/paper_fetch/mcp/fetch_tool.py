"""MCP fetch, resolve, probe, and provider-status payload shaping."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import mimetypes
from pathlib import Path
import threading
from typing import Any, cast

from mcp.server.mcpserver import Context
from mcp.types import CallToolResult, ImageContent, TextContent

from ..artifacts import ArtifactMode
from ..capability_scope import (
    capability_scope_from_runtime_context,
    capability_scopes_for_query,
)
from ..config import apply_browser_auto_prepare_policy
from ..diagnostics import provider_status_payload as _shared_provider_status_payload
from ..http import HttpTransport
from ..models import ArticleModel, Asset, FetchEnvelope
from ..provider_catalog import provider_status_order
from ..publisher_identity import normalize_doi
from ..providers.browser_runtime.preparation import (
    browser_runtime_preparation_scope,
)
from ..resolve.query import StructuredResolveRequest
from ..runtime import RuntimeContext
from ..utils import extend_unique, normalize_text
from ..workflow.pipeline import FetchPipeline, FetchPipelineCacheHooks
from ..workflow.request_builder import build_fetch_pipeline_request
from ..workflow.singleflight import (
    FETCH_ENVELOPE_SINGLEFLIGHT,
    fetch_request_singleflight_key,
)
from ..workflow.rendering import save_markdown_to_disk
from ..workflow.types import effective_asset_profile
from ..workflow.acceptance import evaluate_fetch_acceptance
from .acceptance_payloads import (
    compact_acceptance_payload,
    expected_doi_from_query,
)
from .batch import report_progress, run_blocking_call
from .cache_payloads import _MCP_DEFAULT_DOWNLOAD_DIR, _resolve_download_dir
from .cache_index import read_scoped_file
from ._deps import MCPDeps, default_mcp_deps
from .fetch_cache import (
    FetchCache,
    FetchCacheDependencies,
    credential_scope_from_env,
    envelope_capability_scope,
    fetch_envelope_cache_path,
    mark_envelope_capability_scope,
    payload_from_envelope as _payload_from_envelope,
)
from .log_bridge import PaperFetchLogBridge
from .results import _tool_result, error_payload_from_exception, with_schema_version
from .schemas import (
    FetchPaperRequest,
    FetchStrategyInput,
    HasFulltextRequest,
    InlineImageBudget,
    ProviderStatusRequest,
    ResolvePaperRequest,
)

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
    deps: MCPDeps = default_mcp_deps(),
) -> Path:
    if request.markdown_output_dir is not None:
        return Path(request.markdown_output_dir).expanduser()
    resolved_download_dir = _resolve_download_dir(runtime_env, download_dir, deps=deps)
    if resolved_download_dir is not None:
        return resolved_download_dir
    return (
        _resolve_download_dir(runtime_env, _MCP_DEFAULT_DOWNLOAD_DIR, deps=deps)
        or Path.cwd()
    )


@dataclass(frozen=True)
class SavedMarkdownResult:
    path: Path
    output_dir: Path
    cache_entry: dict[str, Any] | None


def _save_markdown_result_for_fetch_request(
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    *,
    env: Mapping[str, str] | None,
    download_dir: Path | None | object,
    context: RuntimeContext | None = None,
    overwrite: bool = True,
    deps: MCPDeps = default_mcp_deps(),
) -> SavedMarkdownResult | None:
    if not request.save_markdown:
        return None
    runtime_env = (
        dict(context.env)
        if context is not None and context.env is not None
        else deps.build_runtime_env(env)
    )
    markdown_output_path = _markdown_output_dir_for_fetch_request(
        request,
        runtime_env=runtime_env,
        download_dir=download_dir,
        deps=deps,
    )
    if context is not None:
        context.raise_if_cancelled()
    saved_path = save_markdown_to_disk(
        envelope,
        output_dir=markdown_output_path,
        render=request.to_render_options(),
        markdown_filename=request.markdown_filename,
        overwrite=overwrite,
        commit_guard=(context.commit_guard if context is not None else None),
    )
    if saved_path is None:
        return None
    cache_entry = None
    if envelope.doi:
        if context is not None:
            context.raise_if_cancelled()
        credential_scope = envelope_capability_scope(envelope)
        if credential_scope is None:
            credential_scope = (
                capability_scope_from_runtime_context(context)
                if context is not None
                else credential_scope_from_env(runtime_env)
            )
        cache_entry = FetchCache(
            saved_path.parent,
            dependencies=FetchCacheDependencies(
                refresh_for_doi=deps.refresh_cache_index_for_doi,
                register_markdown=deps.register_markdown_entry,
            ),
            credential_scope=credential_scope,
        ).register_markdown(
            saved_path,
            envelope,
            commit_guard=(context.commit_guard if context is not None else None),
        )
    return SavedMarkdownResult(
        path=saved_path,
        output_dir=markdown_output_path,
        cache_entry=cache_entry,
    )


def _save_markdown_for_fetch_request(
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    *,
    env: Mapping[str, str] | None,
    download_dir: Path | None | object,
    context: RuntimeContext | None = None,
    overwrite: bool = True,
    deps: MCPDeps = default_mcp_deps(),
) -> Path | None:
    result = _save_markdown_result_for_fetch_request(
        envelope,
        request,
        env=env,
        download_dir=download_dir,
        context=context,
        overwrite=overwrite,
        deps=deps,
    )
    return result.path if result is not None else None


def _load_cached_fetch_envelope(
    request: FetchPaperRequest,
    *,
    download_dir: Path | None,
    context: RuntimeContext,
    deps: MCPDeps = default_mcp_deps(),
) -> FetchEnvelope | None:
    read_scopes = capability_scopes_for_query(context.env, request.query)
    return FetchCache(
        download_dir,
        dependencies=FetchCacheDependencies(
            refresh_for_doi=deps.refresh_cache_index_for_doi
        ),
        credential_scope=read_scopes[0],
        read_credential_scopes=read_scopes,
    ).load_fetch_envelope(
        request,
        resolve_paper_fn=deps.service_resolve_paper,
        context=context,
    )


def _write_cached_fetch_envelope(
    download_dir: Path,
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    *,
    commit_guard: Callable[[], None] | None = None,
    credential_scope: str = "public",
    deps: MCPDeps = default_mcp_deps(),
) -> None:
    FetchCache(
        download_dir,
        dependencies=FetchCacheDependencies(
            refresh_for_doi=deps.refresh_cache_index_for_doi
        ),
        credential_scope=credential_scope,
    ).write_fetch_envelope(
        envelope,
        request,
        commit_guard=commit_guard,
    )


def _call_service_resolve_paper(
    query: str | StructuredResolveRequest,
    *,
    context: RuntimeContext,
    deps: MCPDeps = default_mcp_deps(),
) -> Any:
    return deps.service_resolve_paper(query, context=context)


def _call_service_probe_has_fulltext(
    query: str, *, context: RuntimeContext, deps: MCPDeps = default_mcp_deps()
) -> Any:
    return deps.service_probe_has_fulltext(query, context=context)


def _fetch_paper_envelope(
    request: FetchPaperRequest,
    *,
    env: Mapping[str, str] | None,
    download_dir: Path | None | object,
    transport: HttpTransport | None,
    include_article_for_assets: bool,
    context: RuntimeContext | None = None,
    cancel_check: Callable[[], bool] | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> FetchEnvelope:
    runtime_env = (
        dict(context.env)
        if context is not None and context.env is not None
        else deps.build_runtime_env(env)
    )
    cache_download_dir = (
        _resolve_download_dir(runtime_env, download_dir, deps=deps)
        if _needs_download_dir_for_fetch(request)
        else None
    )
    service_download_dir = None if request.no_download else cache_download_dir

    active_runtime_context: RuntimeContext | None = context

    def load_cached(runtime_context: RuntimeContext) -> FetchEnvelope | None:
        nonlocal active_runtime_context
        active_runtime_context = runtime_context
        return _load_cached_fetch_envelope(
            request,
            download_dir=cache_download_dir,
            context=runtime_context,
            deps=deps,
        )

    def write_cached(envelope: FetchEnvelope) -> None:
        runtime_context = active_runtime_context
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
        final_scope = (
            capability_scope_from_runtime_context(runtime_context)
            if runtime_context is not None
            else credential_scope_from_env(runtime_env)
        )
        # The outer MCP adapter may save Markdown after the pipeline-owned runtime
        # context has closed. Preserve the actual producer scope on the in-memory
        # envelope so that later artifact registration cannot become public.
        mark_envelope_capability_scope(envelope, final_scope)
        if (
            not request.no_download
            and service_download_dir is not None
            and envelope.doi
        ):
            deps.write_cached_fetch_envelope(
                service_download_dir,
                envelope,
                request,
                commit_guard=(
                    runtime_context.commit_guard
                    if runtime_context is not None
                    else None
                ),
                credential_scope=final_scope,
                deps=deps,
            )

    preparation_cancel_check = cancel_check or (
        context.cancel_check if context is not None else None
    )
    with browser_runtime_preparation_scope(
        cancel_check=preparation_cancel_check,
    ):
        return (
            FetchPipeline(deps.service_fetch_paper)
            .run(
                build_fetch_pipeline_request(
                    query=request.query,
                    modes=_service_modes_for_fetch_request(
                        request, include_article_for_assets=include_article_for_assets
                    ),  # type: ignore[arg-type]
                    strategy=request.strategy.to_service_strategy(),
                    render=request.to_render_options(),
                    env=runtime_env,
                    transport=transport,
                    context=context,
                    cancel_check=cancel_check,
                    download_dir=cache_download_dir,
                    artifact_mode=request.artifact_mode,
                    no_download=request.no_download,
                    fetch_cache=FetchCache(
                        service_download_dir,
                        credential_scope=credential_scope_from_env(runtime_env),
                    ),
                    cache_hooks=FetchPipelineCacheHooks(
                        load=load_cached, write=write_cached
                    ),
                )
            )
            .envelope
        )


def _fetch_envelope_cache_path(download_dir: Path, doi: str) -> Path:
    return fetch_envelope_cache_path(download_dir, doi)


def _resolve_request_from_inputs(
    *,
    query: str | None,
    title: str | None,
    authors: list[str] | str | None,
    year: int | None,
) -> ResolvePaperRequest:
    return ResolvePaperRequest.model_validate(
        {
            "query": query,
            "title": title,
            "authors": authors,
            "year": year,
        }
    )


def _fetch_request_from_inputs(
    *,
    query: str,
    modes: list[str] | None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None,
    include_refs: str | None,
    max_tokens: int | str,
    prefer_cache: bool,
    no_download: bool,
    artifact_mode: ArtifactMode,
    save_markdown: bool,
    markdown_output_dir: str | None,
    markdown_filename: str | None,
    browser_auto_prepare: bool | None,
) -> FetchPaperRequest:
    return FetchPaperRequest.model_validate(
        {
            "query": query,
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
            "browser_auto_prepare": browser_auto_prepare,
        }
    )


def _response_payload_from_envelope(
    envelope: FetchEnvelope, request: FetchPaperRequest
) -> dict[str, Any]:
    payload = _payload_from_envelope(envelope, request)
    acceptance = evaluate_fetch_acceptance(
        envelope,
        asset_profile=effective_asset_profile(
            request.strategy.asset_profile,
            source_name=envelope.source,
        ),
        requested_outputs=request.requested_modes(),
        expected_doi=expected_doi_from_query(request.query),
    )
    payload["status"] = "ok"
    payload["acceptance"] = compact_acceptance_payload(acceptance)
    if not request.save_markdown:
        return payload

    article_payload = payload.get("article")
    if payload.get("metadata") is None and isinstance(article_payload, Mapping):
        payload["metadata"] = article_payload.get("metadata")
    payload["markdown"] = None
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
    context: RuntimeContext | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    request = _resolve_request_from_inputs(
        query=query, title=title, authors=authors, year=year
    )
    runtime_context = context or RuntimeContext(
        env=deps.build_runtime_env(env), transport=transport
    )
    try:
        service_query: str | StructuredResolveRequest = (
            request.query
            if request.query is not None
            else request.to_resolution_request()
        )
        resolved = _call_service_resolve_paper(
            service_query, context=runtime_context, deps=deps
        )
        return with_schema_version(resolved.to_dict())
    finally:
        if context is None:
            runtime_context.close()


def has_fulltext_payload(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    context: RuntimeContext | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    request = HasFulltextRequest(query=query)
    runtime_context = context or RuntimeContext(
        env=deps.build_runtime_env(env), transport=transport
    )
    try:
        probe_result = _call_service_probe_has_fulltext(
            request.query, context=runtime_context, deps=deps
        )
        payload = probe_result.to_dict()
        payload.pop("title", None)
        return with_schema_version(payload)
    finally:
        if context is None:
            runtime_context.close()


def fetch_paper_payload(
    *,
    query: str,
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
    browser_auto_prepare: bool | None = None,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    transport: HttpTransport | None = None,
    context: RuntimeContext | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    request = _fetch_request_from_inputs(
        query=query,
        modes=modes,
        strategy=strategy,
        include_refs=include_refs,
        max_tokens=max_tokens,
        prefer_cache=prefer_cache,
        no_download=no_download,
        artifact_mode=artifact_mode,
        save_markdown=save_markdown,
        markdown_output_dir=markdown_output_dir,
        markdown_filename=markdown_filename,
        browser_auto_prepare=browser_auto_prepare,
    )
    runtime_env = apply_browser_auto_prepare_policy(
        deps.build_runtime_env(env),
        override=request.browser_auto_prepare,
        default=False,
    )
    cache_download_dir = (
        _resolve_download_dir(runtime_env, download_dir, deps=deps)
        if _needs_download_dir_for_fetch(request)
        else None
    )
    owns_context = context is None
    runtime_context = context or RuntimeContext(
        env=runtime_env,
        transport=transport,
        download_dir=(None if request.no_download else cache_download_dir),
        artifact_mode=("none" if request.no_download else request.artifact_mode),
    )
    try:
        envelope = deps.fetch_paper_envelope(
            request,
            env=runtime_env,
            download_dir=download_dir,
            transport=transport,
            include_article_for_assets=False,
            context=runtime_context,
            deps=deps,
        )
        runtime_context.raise_if_cancelled()
        saved_markdown_path = _save_markdown_for_fetch_request(
            envelope,
            request,
            env=runtime_env,
            download_dir=download_dir,
            context=runtime_context,
            deps=deps,
        )
        payload = _response_payload_from_envelope(envelope, request)
        if saved_markdown_path is not None:
            payload["saved_markdown_path"] = str(saved_markdown_path)
        return with_schema_version(payload)
    finally:
        if owns_context:
            runtime_context.close()


def provider_status_payload(
    *,
    provider: str | None = None,
    group: str | None = None,
    detail: str = "full",
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    request = ProviderStatusRequest.model_validate(
        {"provider": provider, "group": group, "detail": detail}
    )
    return _shared_provider_status_payload(
        provider=request.provider,
        group=request.group,
        detail=request.detail,
        env=env,
        transport=transport,
        build_runtime_env_fn=deps.build_runtime_env,
        build_clients_fn=deps.build_clients,
    )


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
    download_dir: Path | None,
) -> tuple[list[TextContent | ImageContent], list[str]]:
    if article is None:
        return [], []
    if budget.disabled:
        return [], []
    if download_dir is None:
        return [], [
            "Local figure assets were omitted because no explicit MCP download scope was available."
        ]

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

        mime_type = mimetypes.guess_type(path.name)[0] or ""
        if not mime_type.startswith("image/"):
            omitted += 1
            continue

        if selected_count >= budget.max_images:
            omitted += 1
            continue
        expected_size = asset.downloaded_bytes
        expected_hash: str | None = None
        for diagnostic in article.quality.asset_summary.diagnostics:
            if normalize_text(diagnostic.path) != path_text:
                continue
            if diagnostic.byte_count is not None:
                expected_size = diagnostic.byte_count
            expected_hash = normalize_text(diagnostic.sha256) or None
            break
        remaining_budget = budget.max_total_bytes - total_bytes
        opened = read_scoped_file(
            download_dir,
            path_text,
            max_bytes=min(budget.max_bytes_per_image, remaining_budget),
            expected_size=expected_size,
            expected_sha256=expected_hash,
        )
        if opened is None:
            omitted += 1
            continue
        path, image_bytes = opened

        total_bytes += len(image_bytes)
        selected_count += 1
        contents.append(TextContent(type="text", text=_inline_image_note(asset, path)))
        contents.append(
            ImageContent(
                type="image",
                data=base64.b64encode(image_bytes).decode("ascii"),
                mime_type=mime_type,
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
    download_dir: Path | None = None,
) -> CallToolResult:
    payload = _response_payload_from_envelope(envelope, request)
    if saved_markdown_path is not None:
        payload["saved_markdown_path"] = str(saved_markdown_path)
    extra_content: list[TextContent | ImageContent] = []

    resolved_asset_profile = effective_asset_profile(
        request.strategy.asset_profile,
        source_name=envelope.source,
    )
    if not request.save_markdown and resolved_asset_profile in {"body", "all"}:
        extra_content, image_warnings = _inline_image_contents(
            envelope.article,
            budget=request.strategy.resolved_inline_image_budget(),
            download_dir=download_dir,
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
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        return _tool_result(
            resolve_paper_payload(
                query=query,
                title=title,
                authors=authors,
                year=year,
                env=env,
                deps=deps,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def has_fulltext_tool(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        return _tool_result(
            has_fulltext_payload(
                query=query,
                env=env,
                deps=deps,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def provider_status_tool(
    *,
    provider: str | None = None,
    group: str | None = None,
    detail: str = "full",
    env: Mapping[str, str] | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        return _tool_result(
            provider_status_payload(
                provider=provider,
                group=group,
                detail=detail,
                env=env,
                deps=deps,
            ),
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
    no_download: bool = False,
    artifact_mode: ArtifactMode = "markdown-assets",
    save_markdown: bool = False,
    markdown_output_dir: str | None = None,
    markdown_filename: str | None = None,
    browser_auto_prepare: bool | None = None,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    ctx: Context | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    await report_progress(
        ctx, 0, _FETCH_PROGRESS_TOTAL, "Validating fetch_paper request"
    )
    try:
        request = _fetch_request_from_inputs(
            query=query,
            modes=modes,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            prefer_cache=prefer_cache,
            no_download=no_download,
            artifact_mode=artifact_mode,
            save_markdown=save_markdown,
            markdown_output_dir=markdown_output_dir,
            markdown_filename=markdown_filename,
            browser_auto_prepare=browser_auto_prepare,
        )
    except Exception as error:
        await report_progress(
            ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed"
        )
        return _tool_result(error_payload_from_exception(error), is_error=True)

    await report_progress(ctx, 1, _FETCH_PROGRESS_TOTAL, "Fetching paper content")
    cancelled = threading.Event()
    runtime_context: RuntimeContext | None = None
    try:
        runtime_env = apply_browser_auto_prepare_policy(
            deps.build_runtime_env(env),
            override=request.browser_auto_prepare,
            default=False,
        )
        cache_download_dir = (
            _resolve_download_dir(runtime_env, download_dir, deps=deps)
            if _needs_download_dir_for_fetch(request)
            else None
        )
        runtime_context = RuntimeContext(
            env=runtime_env,
            download_dir=(None if request.no_download else cache_download_dir),
            artifact_mode=("none" if request.no_download else request.artifact_mode),
            cancel_check=cancelled.is_set,
        )
        markdown_dir = (
            _markdown_output_dir_for_fetch_request(
                request,
                runtime_env=runtime_env,
                download_dir=download_dir,
                deps=deps,
            )
            if request.save_markdown
            else None
        )

        def fetch_and_save() -> tuple[FetchEnvelope, Path | None]:
            assert runtime_context is not None

            def fetch_owner() -> FetchEnvelope:
                return deps.fetch_paper_envelope(
                    request,
                    env=runtime_env,
                    download_dir=download_dir,
                    transport=None,
                    include_article_for_assets=True,
                    context=runtime_context,
                    cancel_check=cancelled.is_set,
                    deps=deps,
                )

            canonical_doi = normalize_doi(expected_doi_from_query(request.query) or "")
            if canonical_doi:
                scope = capability_scopes_for_query(runtime_context.env, canonical_doi)[
                    0
                ]
                singleflight_key = fetch_request_singleflight_key(
                    canonical_doi,
                    request=request,
                    capability_scope=scope,
                    cache_dir=cache_download_dir,
                    markdown_dir=markdown_dir,
                )
                envelope = cast(
                    FetchEnvelope,
                    FETCH_ENVELOPE_SINGLEFLIGHT.run(
                        singleflight_key,
                        fetch_owner,
                        cancel_check=lambda: runtime_context.cancelled,
                    ),
                )
            else:
                envelope = fetch_owner()
            runtime_context.raise_if_cancelled()
            saved_path = _save_markdown_for_fetch_request(
                envelope,
                request,
                env=runtime_env,
                download_dir=download_dir,
                context=runtime_context,
                deps=deps,
            )
            return envelope, saved_path

        loop = asyncio.get_running_loop()
        bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None
        if bridge is None:
            envelope, saved_markdown_path = await run_blocking_call(
                fetch_and_save,
                cancel_event=cancelled,
                cancel_fence=runtime_context.fence_commits,
            )
        else:
            with bridge:
                envelope, saved_markdown_path = await run_blocking_call(
                    fetch_and_save,
                    cancel_event=cancelled,
                    cancel_fence=runtime_context.fence_commits,
                )
        await report_progress(ctx, 3, _FETCH_PROGRESS_TOTAL, "Shaping MCP result")
        resolved_download_dir = _resolve_download_dir(
            runtime_env, download_dir, deps=deps
        )
        result = build_fetch_tool_result(
            envelope,
            request,
            saved_markdown_path=saved_markdown_path,
            download_dir=resolved_download_dir,
        )
        await report_progress(
            ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper complete"
        )
        return result
    except asyncio.CancelledError:
        cancelled.set()
        if runtime_context is not None:
            runtime_context.fence_commits()
        raise
    except Exception as error:
        await report_progress(
            ctx, _FETCH_PROGRESS_TOTAL, _FETCH_PROGRESS_TOTAL, "fetch_paper failed"
        )
        return _tool_result(error_payload_from_exception(error), is_error=True)
    finally:
        if runtime_context is not None:
            runtime_context.close()
