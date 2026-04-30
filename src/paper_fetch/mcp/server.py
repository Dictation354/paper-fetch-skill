"""MCP server entrypoint for paper-fetch."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import queue
import sys
import threading
from typing import Annotated

import anyio
from mcp import types as mcp_types
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.resources import FileResource, FunctionResource
from mcp.shared.message import SessionMessage
from mcp.types import CallToolResult, ToolAnnotations

from ..config import build_runtime_env, resolve_mcp_download_dir
from ._instructions import fetch_tool_description, server_instructions
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
from .output_schemas import (
    BatchCheckOutput,
    BatchResolveOutput,
    FetchPaperOutput,
    GetCachedOutput,
    HasFulltextOutput,
    ListCachedOutput,
    ProviderStatusOutput,
    ResolvePaperOutput,
)
from .prompts import summarize_paper_prompt, verify_citation_list_prompt
from .schemas import FetchStrategyInput
from .server_compat import enable_resource_list_changed_capability, resource_registry, run_stdio_server
from .tools import (
    batch_check_tool_async,
    batch_resolve_tool_async,
    cached_entry_payload,
    fetch_paper_tool_async,
    has_fulltext_tool,
    get_cached_tool,
    list_cached_payload,
    list_cached_tool,
    provider_status_tool,
    resolve_paper_tool,
)


_STDIO_SENTINEL = object()


@asynccontextmanager
async def _threaded_stdio_server():
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
    stop = threading.Event()
    incoming: queue.Queue[SessionMessage | Exception | object] = queue.Queue()

    def stdin_reader() -> None:
        try:
            while not stop.is_set():
                line = sys.stdin.readline()
                if line == "":
                    break
                try:
                    message = mcp_types.JSONRPCMessage.model_validate_json(line)
                except Exception as exc:
                    incoming.put(exc)
                    continue
                incoming.put(SessionMessage(message))
        finally:
            incoming.put(_STDIO_SENTINEL)

    async def stdin_pump() -> None:
        async with read_stream_writer:
            while True:
                try:
                    item = incoming.get_nowait()
                except queue.Empty:
                    await anyio.sleep(0.01)
                    continue
                if item is _STDIO_SENTINEL:
                    break
                await read_stream_writer.send(item)

    async def stdout_pump() -> None:
        async with write_stream_reader:
            async for session_message in write_stream_reader:
                line = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                sys.stdout.write(line + "\n")
                sys.stdout.flush()

    reader = threading.Thread(target=stdin_reader, name="paper-fetch-mcp-stdin", daemon=True)
    reader.start()
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(stdin_pump)
        task_group.start_soon(stdout_pump)
        try:
            yield read_stream, write_stream
        finally:
            stop.set()
            task_group.cancel_scope.cancel()


def _default_download_dir() -> Path:
    return resolve_mcp_download_dir(build_runtime_env())


def _parse_download_dir(download_dir: str | None) -> Path | None:
    text = str(download_dir or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def _cache_index_resource_payload(download_dir: Path | None = None) -> dict[str, object]:
    tool_kwargs: dict[str, object] = {}
    if download_dir is not None:
        tool_kwargs["download_dir"] = download_dir
    return list_cached_payload(**tool_kwargs)


def _read_only_annotations(*, open_world: bool) -> ToolAnnotations:
    return ToolAnnotations(
        readOnlyHint=True,
        openWorldHint=open_world,
    )


def _fetch_annotations() -> ToolAnnotations:
    return ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )


def _resource_uri_set(
    resources: dict[str, object],
    *,
    index_uri: str,
    entry_prefix: str,
) -> set[str]:
    return {uri for uri in resources if uri == index_uri or uri.startswith(entry_prefix)}


def _sync_cache_resources(
    server: FastMCP,
    *,
    download_dir: Path,
    scope_id: str | None = None,
) -> bool:
    entries = list_cache_entries(download_dir)
    resources = resource_registry(server)

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
    stale_uris = [uri for uri in list(resources) if uri.startswith(entry_prefix) and uri not in active_uris]
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
            is_binary=not is_text_mime_type(str(entry["mime"])),
        )
    after_uris = _resource_uri_set(
        resources,
        index_uri=index_uri,
        entry_prefix=entry_prefix,
    )
    return before_uris != after_uris


def _sync_resources_for_download_dir(server: FastMCP, download_dir: Path | None) -> bool:
    if download_dir is None:
        return _sync_cache_resources(server, download_dir=_default_download_dir())
    return _sync_cache_resources(server, download_dir=download_dir, scope_id=cache_scope_id(download_dir))


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
            parsed_markdown_output_dir if parsed_markdown_output_dir is not None else parsed_download_dir
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
        await ctx.session.send_resource_list_changed()
    except Exception:
        return


def _enable_resource_list_changed_capability(server: FastMCP) -> None:
    enable_resource_list_changed_capability(server)


def build_server() -> FastMCP:
    server = FastMCP(
        name="paper-fetch",
        instructions=server_instructions(),
        json_response=True,
    )
    _enable_resource_list_changed_capability(server)

    server.add_resource(
        FunctionResource.from_function(
            _cache_index_resource_payload,
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
        entry = cached_entry_payload(entry_id=entry_id)
        if entry is None:
            raise FileNotFoundError(f"Unknown cached entry: {entry_id}")
        path = Path(str(entry["path"]))
        if is_text_mime_type(str(entry["mime"])):
            return path.read_text(encoding="utf-8")
        return path.read_bytes()

    _sync_resources_for_download_dir(server, None)

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
        )

    @server.tool(
        name="has_fulltext",
        description="Probe whether a paper likely has accessible full text using cheap metadata and landing-page signals.",
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    def has_fulltext(query: str) -> Annotated[CallToolResult, HasFulltextOutput]:
        return has_fulltext_tool(query=query)

    @server.tool(
        name="fetch_paper",
        description=fetch_tool_description(),
        annotations=_fetch_annotations(),
        structured_output=True,
    )
    async def fetch_paper(
        query: str,
        modes: list[str] | None = None,
        strategy: FetchStrategyInput | None = None,
        include_refs: str | None = None,
        max_tokens: int | str = "full_text",
        prefer_cache: bool = False,
        no_download: bool = False,
        save_markdown: bool = False,
        markdown_output_dir: str | None = None,
        markdown_filename: str | None = None,
        download_dir: str | None = None,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, FetchPaperOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        parsed_markdown_output_dir = _parse_download_dir(markdown_output_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = await fetch_paper_tool_async(
            query=query,
            modes=modes,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            prefer_cache=prefer_cache,
            no_download=no_download,
            save_markdown=save_markdown,
            markdown_output_dir=(
                str(parsed_markdown_output_dir) if parsed_markdown_output_dir is not None else None
            ),
            markdown_filename=markdown_filename,
            ctx=ctx,
            **tool_kwargs,
        )
        if not result.isError:
            resources_changed = False
            for sync_dir in _fetch_resource_sync_dirs(
                parsed_download_dir=parsed_download_dir,
                no_download=no_download,
                save_markdown=save_markdown,
                markdown_saved=bool(result.structuredContent.get("saved_markdown_path")),
                parsed_markdown_output_dir=parsed_markdown_output_dir,
            ):
                resources_changed = _sync_resources_for_download_dir(server, sync_dir) or resources_changed
            if resources_changed:
                await _notify_resource_list_changed(ctx)
        return result

    @server.tool(
        name="list_cached",
        description="List cached downloads known to the MCP cache index without touching the network.",
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    async def list_cached(
        download_dir: str | None = None,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, ListCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = list_cached_tool(**tool_kwargs)
        if not result.isError:
            resources_changed = _sync_resources_for_download_dir(server, parsed_download_dir)
            if resources_changed:
                await _notify_resource_list_changed(ctx)
        return result

    @server.tool(
        name="get_cached",
        description="Look up cached downloads for a DOI in the cache index and return preferred local files.",
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    async def get_cached(
        doi: str,
        download_dir: str | None = None,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, GetCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = get_cached_tool(doi=doi, **tool_kwargs)
        if not result.isError:
            resources_changed = _sync_resources_for_download_dir(server, parsed_download_dir)
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
        queries: list[str],
        concurrency: int = 1,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchResolveOutput]:
        return await batch_resolve_tool_async(queries=queries, concurrency=concurrency, ctx=ctx)

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
        queries: list[str],
        mode: str = "metadata",
        concurrency: int = 1,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchCheckOutput]:
        return await batch_check_tool_async(queries=queries, mode=mode, concurrency=concurrency, ctx=ctx)

    @server.tool(
        name="provider_status",
        description="Inspect local provider configuration and runtime readiness without calling remote publisher APIs.",
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    def provider_status() -> Annotated[CallToolResult, ProviderStatusOutput]:
        return provider_status_tool()

    return server


def main() -> None:
    server = build_server()

    async def run_stdio() -> None:
        async with _threaded_stdio_server() as (read_stream, write_stream):
            await run_stdio_server(server, read_stream, write_stream)

    anyio.run(run_stdio)


if __name__ == "__main__":
    main()
