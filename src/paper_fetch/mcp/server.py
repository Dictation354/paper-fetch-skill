"""MCP server entrypoint for paper-fetch."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mcp import types as mcp_types
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.resources import FunctionResource
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ToolAnnotations

from ..version import __version__
from ._deps import default_mcp_deps
from ._instructions import fetch_tool_description, server_instructions
from .batch import batch_check_tool_async, batch_resolve_tool_async
from .batch_fetch import batch_fetch_tool_async
from .browser_preflight import browser_preflight_tool_async
from .cache_payloads import (
    get_cached_tool,
    list_cached_tool,
)
from .fetch_tool import (
    fetch_paper_tool_async,
    has_fulltext_tool,
    provider_status_tool,
    resolve_paper_tool,
)
from .provider_catalog import (
    PROVIDER_CATALOG_RESOURCE_URI,
    provider_catalog_resource_payload,
)
from .schemas import (
    MCP_TOOL_REQUEST_MODELS,
    ArtifactModeInput,
    BatchCheckModeInput,
    BatchContentMaxCharsInput,
    BatchFetchDetailInput,
    BatchQueriesInput,
    BrowserPreflightDetailInput,
    BrowserPreflightProviderInput,
    BrowserPreflightTimeoutInput,
    CacheDetailInput,
    ConcurrencyInput,
    FetchStrategyToolInput,
    IncludeRefsInput,
    MaxTokensInput,
    OutputModesInput,
    ProviderNameInput,
    ProviderStatusDetailInput,
    ProviderStatusGroupInput,
    host_safe_tool_input_schema,
)


class PaperFetchMCPServer(MCPServer):
    """MCPServer with strict native validation and host-safe public schemas."""

    async def list_native_tools(self) -> list[mcp_types.Tool]:
        """Expose the MCPServer-generated schemas for native contract tests."""

        tools = await super().list_tools()
        return [
            tool.model_copy(
                update={
                    "input_schema": {
                        **tool.input_schema,
                        "additionalProperties": False,
                    }
                }
            )
            if tool.name in MCP_TOOL_REQUEST_MODELS
            else tool
            for tool in tools
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context | None = None,
    ) -> Any:
        """Validate public request models before delegating through the SDK API."""

        request_model = MCP_TOOL_REQUEST_MODELS.get(name)
        if request_model is not None:
            validated = request_model.model_validate(arguments)
            normalized = validated.model_dump(mode="python", exclude_unset=True)
            arguments = dict(normalized) if isinstance(normalized, Mapping) else {}
        return await super().call_tool(name, arguments, context)

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
        """Run the official v2 stdio transport."""

        async with stdio_server() as (read_stream, write_stream):
            await self._lowlevel_server.run(
                read_stream,
                write_stream,
                self._lowlevel_server.create_initialization_options(
                    NotificationOptions(resources_changed=False)
                ),
            )


def _parse_download_dir(download_dir: str | None) -> Path | None:
    text = str(download_dir or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


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

    @server.tool(
        name="resolve_paper",
        description="Resolve a DOI, URL, or title query into a normalized paper candidate.",
        annotations=_read_only_annotations(open_world=True),
        structured_output=False,
    )
    def resolve_paper(
        query: str | None = None,
        title: str | None = None,
        authors: list[str] | str | None = None,
        year: int | None = None,
    ) -> CallToolResult:
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
        structured_output=False,
    )
    def has_fulltext(query: str) -> CallToolResult:
        return has_fulltext_tool(query=query, deps=deps)

    @server.tool(
        name="fetch_paper",
        description=fetch_tool_description(),
        annotations=_fetch_annotations(),
        structured_output=False,
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
    ) -> CallToolResult:
        parsed_download_dir = _parse_download_dir(download_dir)
        parsed_markdown_output_dir = _parse_download_dir(markdown_output_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        return await fetch_paper_tool_async(
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

    @server.tool(
        name="list_cached",
        description=(
            "List DOI-proven cached downloads from the current cache index without "
            "touching the network or scanning loose files."
        ),
        annotations=_read_only_annotations(open_world=False),
        structured_output=False,
    )
    async def list_cached(
        download_dir: str | None = None,
        ctx: Context | None = None,
    ) -> CallToolResult:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        return list_cached_tool(**tool_kwargs, deps=deps)

    @server.tool(
        name="get_cached",
        description=(
            "Look up DOI-proven cached files within one download_dir without touching "
            "the network. detail=compact returns preferred entries plus request-sensitive "
            "acceptance/asset summaries; preferred_only omits non-preferred entry arrays."
        ),
        annotations=_read_only_annotations(open_world=False),
        structured_output=False,
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
    ) -> CallToolResult:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        return get_cached_tool(
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

    @server.tool(
        name="batch_resolve",
        description="Resolve multiple DOI, URL, or title queries with shared transport reuse and optional cross-host concurrency.",
        annotations=_read_only_annotations(open_world=True),
        structured_output=False,
    )
    async def batch_resolve(
        queries: BatchQueriesInput,
        concurrency: ConcurrencyInput = 1,
        ctx: Context | None = None,
    ) -> CallToolResult:
        return await batch_resolve_tool_async(
            queries=queries, concurrency=concurrency, ctx=ctx, deps=deps
        )

    @server.tool(
        name="batch_fetch",
        description=(
            "Fetch 1..50 papers with bounded concurrency and input-ordered compact "
            "manifest/acceptance results. It may access remote services and write the "
            "same cache, artifacts, or Markdown as fetch_paper. detail=bounded returns "
            "only a batch-wide bounded text sample. batch_results atomically writes "
            "the final input-ordered JSONL result; overwrite defaults false. Browser "
            "routes require an already prepared Camoufox runtime."
        ),
        annotations=_fetch_annotations(),
        structured_output=False,
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
        batch_results: str | None = None,
        overwrite: bool = False,
        ctx: Context | None = None,
    ) -> CallToolResult:
        parsed_download_dir = _parse_download_dir(download_dir)
        parsed_markdown_output_dir = _parse_download_dir(markdown_output_dir)
        tool_kwargs: dict[str, Any] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        return await batch_fetch_tool_async(
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
            batch_results=batch_results,
            overwrite=overwrite,
            ctx=ctx,
            deps=deps,
            **tool_kwargs,
        )

    @server.tool(
        name="batch_check",
        description=(
            "Check multiple papers without returning full bodies, with optional cross-host concurrency. "
            "Success items keep only lightweight provenance fields. Browser routes require "
            "an already prepared Camoufox runtime."
        ),
        annotations=_read_only_annotations(open_world=True),
        structured_output=False,
    )
    async def batch_check(
        queries: BatchQueriesInput,
        mode: BatchCheckModeInput = "metadata",
        concurrency: ConcurrencyInput = 1,
        ctx: Context | None = None,
    ) -> CallToolResult:
        return await batch_check_tool_async(
            queries=queries,
            mode=mode,
            concurrency=concurrency,
            ctx=ctx,
            deps=deps,
        )

    @server.tool(
        name="browser_preflight",
        description=(
            "Live-check the shared browser HTML path for one provider or all browser "
            "providers. This opens publisher pages and may update filtered storage-state; "
            "it never runs PDF fallback, automatic authentication, or runtime installation."
        ),
        annotations=_browser_preflight_annotations(),
        structured_output=False,
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
    ) -> CallToolResult:
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
            "This never opens Camoufox or publisher pages; use browser_preflight for live health."
        ),
        annotations=_read_only_annotations(open_world=False),
        structured_output=False,
    )
    def provider_status(
        provider: ProviderNameInput | None = None,
        group: ProviderStatusGroupInput | None = None,
        detail: ProviderStatusDetailInput = "full",
    ) -> CallToolResult:
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
