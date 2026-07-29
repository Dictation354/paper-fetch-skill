"""MCP server entrypoint for paper-fetch."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from collections.abc import Callable, Mapping

from mcp import types as mcp_types
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.resources import FileResource, FunctionResource
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, Icon, ToolAnnotations
from mcp.types.version import MODERN_PROTOCOL_VERSIONS
from pydantic import ConfigDict

from ..version import __version__
from ._instructions import fetch_tool_description, server_instructions
from ._deps import MCPDeps, default_mcp_deps
from .batch import batch_check_tool_async, batch_resolve_tool_async
from .batch_fetch import batch_fetch_tool_async
from .browser_preflight import browser_preflight_tool_async
from .cache_index import (
    CACHE_INDEX_RESOURCE_URI,
    CACHED_RESOURCE_TEMPLATE,
    CACHED_RESOURCE_URI_PREFIX,
    cache_scope_id,
    cached_resource_uri,
    is_text_mime_type,
    list_cache_entries,
    scoped_cache_index_resource_uri,
    scoped_cached_resource_uri,
    scoped_cached_resource_uri_prefix,
)
from .cache_payloads import (
    cached_entry_payload,
    get_cached_tool,
    list_cached_payload,
    list_cached_tool,
)
from .fetch_tool import (
    fetch_paper_tool_async,
    has_fulltext_tool,
    provider_status_tool,
    resolve_paper_tool,
)
from .output_schemas import (
    BatchCheckOutput,
    BatchFetchOutput,
    BatchResolveOutput,
    BrowserPreflightOutput,
    FetchPaperOutput,
    GetCachedOutput,
    HasFulltextOutput,
    ListCachedOutput,
    ProviderStatusOutput,
    ResolvePaperOutput,
    compact_tool_output_schema,
)
from .prompts import summarize_paper_prompt, verify_citation_list_prompt
from .provider_catalog import (
    PROVIDER_CATALOG_RESOURCE_URI,
    provider_catalog_resource_payload,
)
from .schemas import (
    ArtifactModeInput,
    BatchCheckModeInput,
    BatchContentMaxCharsInput,
    BatchFetchDetailInput,
    BatchQueriesInput,
    BrowserPreflightDetailInput,
    BrowserPreflightProviderInput,
    BrowserPreflightTimeoutInput,
    CacheDetailInput,
    CacheModeInput,
    ConcurrencyInput,
    FetchStrategyToolInput,
    IncludeRefsInput,
    MCP_TOOL_REQUEST_MODELS,
    MaxTokensInput,
    OutputModesInput,
    ProviderNameInput,
    ProviderStatusDetailInput,
    ProviderStatusGroupInput,
    host_safe_tool_input_schema,
)


class PaperFetchMCPServer(MCPServer):
    """MCPServer with strict native validation and host-safe public schemas."""

    def add_tool(
        self,
        fn: Callable[..., Any],
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
        icons: list[Icon] | None = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
    ) -> None:
        tool = self._tool_manager.add_tool(
            fn,
            name=name,
            title=title,
            description=description,
            annotations=annotations,
            icons=icons,
            meta=meta,
            structured_output=structured_output,
        )
        arg_model = tool.fn_metadata.arg_model
        strict_config = dict(arg_model.model_config)
        strict_config["extra"] = "forbid"
        arg_model.model_config = ConfigDict(**strict_config)
        arg_model.model_rebuild(force=True)
        tool.parameters = arg_model.model_json_schema(by_alias=True)
        tool.fn_metadata.output_schema = compact_tool_output_schema(
            tool.fn_metadata.output_schema
        )
        tool.__dict__.pop("output_schema", None)

    async def list_native_tools(self) -> list[mcp_types.Tool]:
        """Expose the MCPServer-generated schemas for native contract tests."""

        return await super().list_tools()

    async def list_tools(self) -> list[mcp_types.Tool]:
        """Expose reference-free Pydantic schemas to stdio and other MCP hosts."""

        tools = await self.list_native_tools()
        return [
            tool.model_copy(
                update={"input_schema": host_safe_tool_input_schema(tool.name)}
            )
            if tool.name in MCP_TOOL_REQUEST_MODELS
            else tool
            for tool in tools
        ]

    async def run_stdio_async(self) -> None:
        """Run the official v2 stdio transport with legacy resource notifications."""

        async with stdio_server() as (read_stream, write_stream):
            await self._lowlevel_server.run(
                read_stream,
                write_stream,
                self._lowlevel_server.create_initialization_options(
                    NotificationOptions(resources_changed=True)
                ),
            )


def _default_download_dir(*, deps: MCPDeps = default_mcp_deps()) -> Path:
    return deps.resolve_mcp_download_dir(deps.build_runtime_env())


def _parse_download_dir(download_dir: str | None) -> Path | None:
    text = str(download_dir or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def _cache_index_resource_payload(
    download_dir: Path | None = None,
    *,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, object]:
    tool_kwargs: dict[str, Any] = {}
    if download_dir is not None:
        tool_kwargs["download_dir"] = download_dir
    return list_cached_payload(**tool_kwargs, deps=deps)


def _read_only_annotations(*, open_world: bool) -> ToolAnnotations:
    return ToolAnnotations(
        read_only_hint=True,
        open_world_hint=open_world,
    )


def _fetch_annotations() -> ToolAnnotations:
    return ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=True,
    )


def _browser_preflight_annotations() -> ToolAnnotations:
    return ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=True,
    )


def _resource_uri_set(
    resources: Mapping[str, object],
    *,
    index_uri: str,
    entry_prefix: str,
) -> set[str]:
    return {
        uri for uri in resources if uri == index_uri or uri.startswith(entry_prefix)
    }


def _sync_cache_resources(
    server: MCPServer,
    *,
    download_dir: Path,
    scope_id: str | None = None,
) -> bool:
    entries = list_cache_entries(download_dir)
    # mcp has no public remove_resource() API; relies on internal _resources dict (verified mcp>=2).
    # The assertion below will fire immediately if a future mcp version changes this layout.
    resources = server._resource_manager._resources
    assert isinstance(resources, dict), (
        "MCPServer internal layout changed; update _sync_cache_resources for the new mcp version"
    )

    def default_entry_uri(entry_id: object) -> str:
        return cached_resource_uri(str(entry_id))

    def scoped_entry_uri(entry_id: object) -> str:
        assert scope_id is not None
        return scoped_cached_resource_uri(scope_id, str(entry_id))

    if scope_id is None:
        index_uri = CACHE_INDEX_RESOURCE_URI
        entry_uri_for = default_entry_uri
        entry_prefix = CACHED_RESOURCE_URI_PREFIX
        name = "cache_index"
        description = "JSON index of cached MCP downloads in the default shared download directory."
    else:
        index_uri = scoped_cache_index_resource_uri(scope_id)
        entry_uri_for = scoped_entry_uri
        entry_prefix = scoped_cached_resource_uri_prefix(scope_id)
        name = f"cache_index_{scope_id}"
        description = (
            "JSON index of cached MCP downloads in an isolated download directory. "
            f"Scope id: {scope_id}."
        )

    before_uris = _resource_uri_set(
        resources,
        index_uri=index_uri,
        entry_prefix=entry_prefix,
    )

    def index_payload_for_download_dir() -> dict[str, object]:
        return _cache_index_resource_payload(download_dir)

    resources[index_uri] = FunctionResource.from_function(
        index_payload_for_download_dir,
        uri=index_uri,
        name=name,
        description=description,
        mime_type="application/json",
    )

    active_uris = {entry_uri_for(entry["id"]) for entry in entries}
    stale_uris = [
        uri
        for uri in list(resources)
        if uri.startswith(entry_prefix) and uri not in active_uris
    ]
    for uri in stale_uris:
        del resources[uri]

    for entry in entries:
        uri = entry_uri_for(entry["id"])
        resources[uri] = FileResource(
            uri=uri,
            name=f"cached_{entry['id']}",
            description=f"Cached {entry['kind']} for DOI {entry['doi']}.",
            path=Path(str(entry["path"])),
            mime_type=str(entry["mime"]),
            encoding=("utf-8" if is_text_mime_type(str(entry["mime"])) else None),
        )
    after_uris = _resource_uri_set(
        resources,
        index_uri=index_uri,
        entry_prefix=entry_prefix,
    )
    return before_uris != after_uris


def _sync_resources_for_download_dir(
    server: MCPServer,
    download_dir: Path | None,
    *,
    deps: MCPDeps = default_mcp_deps(),
) -> bool:
    if download_dir is None:
        return _sync_cache_resources(
            server, download_dir=_default_download_dir(deps=deps)
        )
    return _sync_cache_resources(
        server, download_dir=download_dir, scope_id=cache_scope_id(download_dir)
    )


def _fetch_resource_sync_dirs(
    *,
    parsed_download_dir: Path | None,
    no_download: bool,
    save_markdown: bool,
    markdown_saved: bool,
    parsed_markdown_output_dir: Path | None,
) -> list[Path | None]:
    sync_dirs: list[Path | None] = []
    if not no_download:
        sync_dirs.append(parsed_download_dir)
    if save_markdown and markdown_saved:
        sync_dirs.append(
            parsed_markdown_output_dir
            if parsed_markdown_output_dir is not None
            else parsed_download_dir
        )

    deduped: list[Path | None] = []
    seen: set[str] = set()
    for item in sync_dirs:
        key = "<default>" if item is None else str(item.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


async def _notify_resource_list_changed(ctx: Context | None) -> None:
    if ctx is None:
        return
    try:
        if ctx.protocol_version in MODERN_PROTOCOL_VERSIONS:
            await ctx.notify_resources_changed()
        else:
            await ctx.session.send_resource_list_changed()
    except Exception:
        return


def build_server() -> PaperFetchMCPServer:
    deps = default_mcp_deps()
    server = PaperFetchMCPServer(
        name="paper-fetch",
        instructions=server_instructions(),
        version=__version__,
    )

    server.add_resource(
        FunctionResource.from_function(
            provider_catalog_resource_payload,
            uri=PROVIDER_CATALOG_RESOURCE_URI,
            name="provider_catalog",
            description=(
                "Runtime-derived provider, source, browser/preflight, and asset-default "
                "catalog."
            ),
            mime_type="application/json",
        )
    )

    def default_cache_index_resource_payload() -> dict[str, object]:
        return _cache_index_resource_payload(deps=deps)

    server.add_resource(
        FunctionResource.from_function(
            default_cache_index_resource_payload,
            uri=CACHE_INDEX_RESOURCE_URI,
            name="cache_index",
            description="JSON index of cached MCP downloads in the default shared download directory.",
            mime_type="application/json",
        )
    )

    @server.resource(
        CACHED_RESOURCE_TEMPLATE,
        name="cached_entry_template",
        description="Read a cached file from the default shared MCP download directory by entry id.",
        mime_type="application/octet-stream",
    )
    def cached_entry_resource(entry_id: str) -> str | bytes:
        entry = cached_entry_payload(entry_id=entry_id, deps=deps)
        if entry is None:
            raise FileNotFoundError(f"Unknown cached entry: {entry_id}")
        path = Path(str(entry["path"]))
        if is_text_mime_type(str(entry["mime"])):
            return path.read_text(encoding="utf-8")
        return path.read_bytes()

    _sync_resources_for_download_dir(server, None, deps=deps)

    @server.prompt(
        name="summarize_paper",
        description="Template for summarizing one known paper with cache-first and provenance-aware fetch discipline.",
    )
    def summarize_paper(query: str, focus: str = "general") -> str:
        return summarize_paper_prompt(query=query, focus=focus)

    @server.prompt(
        name="verify_citation_list",
        description="Template for checking a citation list with batch-first probe discipline.",
    )
    def verify_citation_list(citations: str, mode: str = "metadata") -> str:
        return verify_citation_list_prompt(citations=citations, mode=mode)

    @server.tool(
        name="resolve_paper",
        description="Resolve a DOI, URL, or title query into a normalized paper candidate.",
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    def resolve_paper(
        query: str | None = None,
        title: str | None = None,
        authors: list[str] | str | None = None,
        year: int | None = None,
    ) -> Annotated[CallToolResult, ResolvePaperOutput]:
        return resolve_paper_tool(
            query=query,
            title=title,
            authors=authors,
            year=year,
            deps=deps,
        )

    @server.tool(
        name="has_fulltext",
        description="Probe whether a paper likely has accessible full text using cheap metadata and landing-page signals.",
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    def has_fulltext(query: str) -> Annotated[CallToolResult, HasFulltextOutput]:
        return has_fulltext_tool(query=query, deps=deps)

    @server.tool(
        name="fetch_paper",
        description=fetch_tool_description(),
        annotations=_fetch_annotations(),
        structured_output=True,
    )
    async def fetch_paper(
        query: str,
        modes: OutputModesInput | None = None,
        strategy: FetchStrategyToolInput | None = None,
        include_refs: IncludeRefsInput | None = None,
        max_tokens: MaxTokensInput = "full_text",
        prefer_cache: bool = False,
        no_download: bool = False,
        artifact_mode: ArtifactModeInput = "markdown-assets",
        save_markdown: bool = False,
        markdown_output_dir: str | None = None,
        markdown_filename: str | None = None,
        download_dir: str | None = None,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, FetchPaperOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        parsed_markdown_output_dir = _parse_download_dir(markdown_output_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = await fetch_paper_tool_async(
            query=query,
            modes=[str(mode) for mode in modes] if modes is not None else None,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            prefer_cache=prefer_cache,
            no_download=no_download,
            artifact_mode=artifact_mode,
            save_markdown=save_markdown,
            markdown_output_dir=(
                str(parsed_markdown_output_dir)
                if parsed_markdown_output_dir is not None
                else None
            ),
            markdown_filename=markdown_filename,
            ctx=ctx,
            deps=deps,
            **tool_kwargs,
        )
        if not result.is_error:
            resources_changed = False
            for sync_dir in _fetch_resource_sync_dirs(
                parsed_download_dir=parsed_download_dir,
                no_download=no_download,
                save_markdown=save_markdown,
                markdown_saved=bool(
                    (result.structured_content or {}).get("saved_markdown_path")
                ),
                parsed_markdown_output_dir=parsed_markdown_output_dir,
            ):
                resources_changed = (
                    _sync_resources_for_download_dir(server, sync_dir, deps=deps)
                    or resources_changed
                )
            if resources_changed:
                await _notify_resource_list_changed(ctx)
        return result

    @server.tool(
        name="list_cached",
        description=(
            "List cached downloads without touching the network. cache_mode=index reads "
            "the manifest only, refresh validates and prunes the manifest, and rescan "
            "rebuilds it from DOI-proven fetch-envelope sidecars and Markdown YAML "
            "front matter within the selected download_dir."
        ),
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    async def list_cached(
        download_dir: str | None = None,
        cache_mode: CacheModeInput = "index",
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, ListCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = list_cached_tool(cache_mode=cache_mode, **tool_kwargs, deps=deps)
        if not result.is_error:
            resources_changed = _sync_resources_for_download_dir(
                server, parsed_download_dir, deps=deps
            )
            if resources_changed:
                await _notify_resource_list_changed(ctx)
        return result

    @server.tool(
        name="get_cached",
        description=(
            "Look up DOI-proven cached files within one download_dir without touching "
            "the network. detail=compact returns preferred entries plus request-sensitive "
            "acceptance/asset summaries; preferred_only omits non-preferred entry arrays."
        ),
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    async def get_cached(
        doi: str,
        download_dir: str | None = None,
        detail: CacheDetailInput = "full",
        preferred_only: bool = False,
        modes: OutputModesInput | None = None,
        strategy: FetchStrategyToolInput | None = None,
        include_refs: IncludeRefsInput | None = None,
        max_tokens: MaxTokensInput = "full_text",
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, GetCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = get_cached_tool(
            doi=doi,
            detail=detail,
            preferred_only=preferred_only,
            modes=[str(mode) for mode in modes] if modes is not None else None,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            **tool_kwargs,
            deps=deps,
        )
        if not result.is_error:
            resources_changed = _sync_resources_for_download_dir(
                server, parsed_download_dir, deps=deps
            )
            if resources_changed:
                await _notify_resource_list_changed(ctx)
        return result

    @server.tool(
        name="batch_resolve",
        description="Resolve multiple DOI, URL, or title queries with shared transport reuse and optional cross-host concurrency.",
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    async def batch_resolve(
        queries: BatchQueriesInput,
        concurrency: ConcurrencyInput = 1,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchResolveOutput]:
        return await batch_resolve_tool_async(
            queries=queries, concurrency=concurrency, ctx=ctx, deps=deps
        )

    @server.tool(
        name="batch_fetch",
        description=(
            "Fetch 1..50 papers with bounded concurrency and input-ordered compact "
            "manifest/acceptance results. It may access remote services and write the "
            "same cache, artifacts, or Markdown as fetch_paper. detail=bounded returns "
            "only a batch-wide bounded text sample. Set run_manifest or resume for "
            "auditable persistence; overwrite defaults false."
        ),
        annotations=_fetch_annotations(),
        structured_output=True,
    )
    async def batch_fetch(
        queries: BatchQueriesInput,
        concurrency: ConcurrencyInput = 1,
        modes: OutputModesInput | None = None,
        strategy: FetchStrategyToolInput | None = None,
        include_refs: IncludeRefsInput | None = None,
        max_tokens: MaxTokensInput = "full_text",
        prefer_cache: bool = False,
        no_download: bool = False,
        artifact_mode: ArtifactModeInput = "markdown-assets",
        save_markdown: bool = False,
        markdown_output_dir: str | None = None,
        markdown_filename: str | None = None,
        download_dir: str | None = None,
        detail: BatchFetchDetailInput = "compact",
        content_max_chars: BatchContentMaxCharsInput = 20_000,
        continue_on_error: bool = True,
        run_manifest: str | None = None,
        batch_results: str | None = None,
        resume: str | None = None,
        overwrite: bool = False,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchFetchOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        parsed_markdown_output_dir = _parse_download_dir(markdown_output_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = await batch_fetch_tool_async(
            queries=queries,
            concurrency=concurrency,
            modes=[str(mode) for mode in modes] if modes is not None else None,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            prefer_cache=prefer_cache,
            no_download=no_download,
            artifact_mode=artifact_mode,
            save_markdown=save_markdown,
            markdown_output_dir=(
                str(parsed_markdown_output_dir)
                if parsed_markdown_output_dir is not None
                else None
            ),
            markdown_filename=markdown_filename,
            detail=detail,
            content_max_chars=content_max_chars,
            continue_on_error=continue_on_error,
            run_manifest=run_manifest,
            batch_results=batch_results,
            resume=resume,
            overwrite=overwrite,
            ctx=ctx,
            deps=deps,
            **tool_kwargs,
        )
        if not result.is_error:
            payload = result.structured_content or {}
            resources_changed = False
            for sync_dir in _fetch_resource_sync_dirs(
                parsed_download_dir=parsed_download_dir,
                no_download=no_download,
                save_markdown=save_markdown,
                markdown_saved=bool(
                    (payload.get("summary") or {}).get("saved_markdown")
                ),
                parsed_markdown_output_dir=parsed_markdown_output_dir,
            ):
                resources_changed = (
                    _sync_resources_for_download_dir(server, sync_dir, deps=deps)
                    or resources_changed
                )
            if resources_changed:
                await _notify_resource_list_changed(ctx)
        return result

    @server.tool(
        name="batch_check",
        description=(
            "Check multiple papers without returning full bodies, with optional cross-host concurrency. "
            "Success items keep only lightweight provenance fields."
        ),
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    async def batch_check(
        queries: BatchQueriesInput,
        mode: BatchCheckModeInput = "metadata",
        concurrency: ConcurrencyInput = 1,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchCheckOutput]:
        return await batch_check_tool_async(
            queries=queries, mode=mode, concurrency=concurrency, ctx=ctx, deps=deps
        )

    @server.tool(
        name="browser_preflight",
        description=(
            "Live-check the shared browser HTML path for one provider or all browser "
            "providers. This opens publisher pages and may update filtered storage-state; "
            "it never runs PDF fallback or automatic authentication."
        ),
        annotations=_browser_preflight_annotations(),
        structured_output=True,
    )
    async def browser_preflight(
        provider: BrowserPreflightProviderInput | None = None,
        test_url: str | None = None,
        timeout_ms: BrowserPreflightTimeoutInput | None = None,
        browser_user_agent: str | None = None,
        storage_state_path: str | None = None,
        save_storage_state: bool = True,
        detail: BrowserPreflightDetailInput = "full",
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BrowserPreflightOutput]:
        return await browser_preflight_tool_async(
            provider=provider,
            test_url=test_url,
            timeout_ms=timeout_ms,
            browser_user_agent=browser_user_agent,
            storage_state_path=storage_state_path,
            save_storage_state=save_storage_state,
            detail=detail,
            ctx=ctx,
            deps=deps,
        )

    @server.tool(
        name="provider_status",
        description=(
            "Inspect filtered static provider configuration and local dependency readiness. "
            "This never opens Chrome/CDP or publisher pages; use browser_preflight for live health."
        ),
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    def provider_status(
        provider: ProviderNameInput | None = None,
        group: ProviderStatusGroupInput | None = None,
        detail: ProviderStatusDetailInput = "full",
    ) -> Annotated[CallToolResult, ProviderStatusOutput]:
        return provider_status_tool(
            provider=provider,
            group=group,
            detail=detail,
            deps=deps,
        )

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
