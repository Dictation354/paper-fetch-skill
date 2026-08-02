# ruff: noqa: F401
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from mcp.types.version import LATEST_HANDSHAKE_VERSION

from paper_fetch.browser_preflight import (
    BrowserPreflightResult,
    classify_browser_preflight_failure,
    run_browser_provider_preflight,
)
from paper_fetch.http import RequestCancelledError, RequestFailure
from paper_fetch.mcp import batch as mcp_batch
from paper_fetch.mcp import browser_preflight as mcp_browser_preflight
from paper_fetch.mcp import cache_payloads as mcp_cache_payloads
from paper_fetch.mcp import fetch_tool as mcp_fetch_tool
from paper_fetch.mcp._deps import MCPDeps, default_mcp_deps
from paper_fetch.mcp.cache_index import (
    IDENTITY_PROOF_MARKDOWN_REGISTRATION,
    LOCK_DIRNAME,
    cache_lock_dir,
    cache_scope_id,
    find_cached_entry,
    list_cache_entries,
    preferred_cached_entries,
    register_markdown_entry,
    refresh_cache_index_for_doi,
    scoped_cache_index_resource_uri,
    scoped_cached_resource_uri_prefix,
)
from paper_fetch.config import build_runtime_env, resolve_mcp_download_dir
from paper_fetch.mcp import server as mcp_server
from paper_fetch.mcp.fetch_cache import (
    FETCH_ENVELOPE_CACHE_VERSION,
    FetchCache,
    article_from_payload,
    envelope_from_payload,
    fetch_envelope_cache_path,
    payload_from_envelope,
)
from paper_fetch.mcp.log_bridge import (
    StructuredLogNotificationHandler,
    parse_structured_log_message,
    structured_log_payload_from_record,
)
from paper_fetch.mcp.results import error_payload_from_exception
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.providers.registry import build_clients
from paper_fetch.models import (
    ArticleModel,
    Asset,
    EXTRACTION_REVISION,
    FetchEnvelope,
    Metadata,
    Quality,
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    RenderOptions,
    Section,
    TokenEstimateBreakdown,
)
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.service import (
    FetchStrategy,
    HasFulltextProbeResult,
    PaperFetchFailure,
    fetch_paper,
    probe_has_fulltext,
    resolve_paper,
)
from paper_fetch.utils import sanitize_filename
from tests.golden_criteria import golden_criteria_scenario_asset


def _mcp_deps_from_namespace(**overrides) -> MCPDeps:
    values = {
        "build_runtime_env": mcp_tools.build_runtime_env,
        "service_fetch_paper": mcp_tools.service_fetch_paper,
        "service_probe_has_fulltext": mcp_tools.service_probe_has_fulltext,
        "service_resolve_paper": mcp_tools.service_resolve_paper,
        "build_clients": mcp_tools.build_clients,
        "refresh_cache_index_for_doi": mcp_tools.refresh_cache_index_for_doi,
        "fetch_paper_envelope": _namespace_fetch_paper_envelope,
        "write_cached_fetch_envelope": _namespace_write_cached_fetch_envelope,
        "resolve_mcp_download_dir": mcp_tools.resolve_mcp_download_dir,
        "find_cached_entry": mcp_tools.find_cached_entry,
        "list_cache_entries": mcp_tools.list_cache_entries,
        "preferred_cached_entries": mcp_tools.preferred_cached_entries,
        "register_markdown_entry": mcp_tools.register_markdown_entry,
        "run_browser_provider_preflight": mcp_tools.run_browser_provider_preflight,
    }
    values.update(overrides)
    return MCPDeps(**values)


def _namespace_fetch_paper_envelope(*args, **kwargs):
    try:
        return mcp_tools._fetch_paper_envelope(*args, **kwargs)
    except TypeError:
        if "deps" not in kwargs:
            raise
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("deps", None)
        return mcp_tools._fetch_paper_envelope(*args, **fallback_kwargs)


def _namespace_write_cached_fetch_envelope(*args, **kwargs):
    try:
        return mcp_tools._write_cached_fetch_envelope(*args, **kwargs)
    except TypeError:
        if "deps" not in kwargs:
            raise
        fallback_kwargs = dict(kwargs)
        fallback_kwargs.pop("deps", None)
        return mcp_tools._write_cached_fetch_envelope(*args, **fallback_kwargs)


def _call_with_namespace_deps(func, kwargs: dict[str, object]):
    kwargs = dict(kwargs)
    deps = kwargs.pop("deps", _mcp_deps_from_namespace())
    return func(**kwargs, deps=deps)


async def _call_async_with_namespace_deps(func, kwargs: dict[str, object]):
    kwargs = dict(kwargs)
    deps = kwargs.pop("deps", _mcp_deps_from_namespace())
    return await func(**kwargs, deps=deps)


def _support_build_server():
    with mock.patch.object(
        mcp_server, "default_mcp_deps", side_effect=_mcp_deps_from_namespace
    ):
        return mcp_server.build_server()


mcp_tools = SimpleNamespace(
    FetchPaperRequest=FetchPaperRequest,
    RequestCancelledError=RequestCancelledError,
    StructuredLogNotificationHandler=StructuredLogNotificationHandler,
    _FETCH_ENVELOPE_CACHE_VERSION=FETCH_ENVELOPE_CACHE_VERSION,
    _PROVIDER_STATUS_ORDER=mcp_fetch_tool._PROVIDER_STATUS_ORDER,
    _article_from_payload=article_from_payload,
    _envelope_from_payload=envelope_from_payload,
    _fetch_envelope_cache_path=fetch_envelope_cache_path,
    _fetch_paper_envelope=mcp_fetch_tool._fetch_paper_envelope,
    _inline_image_contents=mcp_fetch_tool._inline_image_contents,
    _payload_from_envelope=payload_from_envelope,
    _write_cached_fetch_envelope=mcp_fetch_tool._write_cached_fetch_envelope,
    batch_check_payload=lambda **kwargs: _call_with_namespace_deps(
        mcp_batch.batch_check_payload, kwargs
    ),
    batch_check_tool_async=lambda **kwargs: _call_async_with_namespace_deps(
        mcp_batch.batch_check_tool_async, kwargs
    ),
    batch_resolve_payload=lambda **kwargs: _call_with_namespace_deps(
        mcp_batch.batch_resolve_payload, kwargs
    ),
    batch_resolve_tool_async=lambda **kwargs: _call_async_with_namespace_deps(
        mcp_batch.batch_resolve_tool_async, kwargs
    ),
    browser_preflight_payload=lambda **kwargs: _call_with_namespace_deps(
        mcp_browser_preflight.browser_preflight_payload, kwargs
    ),
    browser_preflight_tool_async=lambda **kwargs: _call_async_with_namespace_deps(
        mcp_browser_preflight.browser_preflight_tool_async, kwargs
    ),
    build_clients=build_clients,
    build_fetch_tool_result=mcp_fetch_tool.build_fetch_tool_result,
    build_runtime_env=build_runtime_env,
    error_payload_from_exception=error_payload_from_exception,
    fetch_paper_payload=lambda **kwargs: _call_with_namespace_deps(
        mcp_fetch_tool.fetch_paper_payload, kwargs
    ),
    fetch_paper_tool_async=lambda **kwargs: _call_async_with_namespace_deps(
        mcp_fetch_tool.fetch_paper_tool_async, kwargs
    ),
    find_cached_entry=find_cached_entry,
    get_cached_payload=lambda **kwargs: _call_with_namespace_deps(
        mcp_cache_payloads.get_cached_payload, kwargs
    ),
    has_fulltext_tool=lambda **kwargs: _call_with_namespace_deps(
        mcp_fetch_tool.has_fulltext_tool, kwargs
    ),
    list_cache_entries=list_cache_entries,
    list_cached_payload=lambda **kwargs: _call_with_namespace_deps(
        mcp_cache_payloads.list_cached_payload, kwargs
    ),
    parse_structured_log_message=parse_structured_log_message,
    preferred_cached_entries=preferred_cached_entries,
    provider_status_tool=lambda **kwargs: _call_with_namespace_deps(
        mcp_fetch_tool.provider_status_tool, kwargs
    ),
    refresh_cache_index_for_doi=refresh_cache_index_for_doi,
    register_markdown_entry=register_markdown_entry,
    run_browser_provider_preflight=run_browser_provider_preflight,
    resolve_mcp_download_dir=resolve_mcp_download_dir,
    resolve_paper_payload=lambda **kwargs: _call_with_namespace_deps(
        mcp_fetch_tool.resolve_paper_payload, kwargs
    ),
    resolve_paper_tool=lambda **kwargs: _call_with_namespace_deps(
        mcp_fetch_tool.resolve_paper_tool, kwargs
    ),
    service_fetch_paper=fetch_paper,
    service_probe_has_fulltext=probe_has_fulltext,
    service_resolve_paper=resolve_paper,
    structured_log_payload_from_record=structured_log_payload_from_record,
)


def mcp_test_deps(**overrides) -> MCPDeps:
    return replace(default_mcp_deps(), **overrides)


build_server = _support_build_server


def sample_article() -> ArticleModel:
    return ArticleModel(
        doi="10.1000/example",
        source="elsevier_xml",
        metadata=Metadata(
            title="Example Article",
            authors=["Alice Example"],
            abstract="Example abstract",
            journal="Example Journal",
            published="2026-01-01",
        ),
        sections=[
            Section(heading="Introduction", level=2, kind="body", text="Example body.")
        ],
        references=[],
        assets=[],
        quality=Quality(
            has_fulltext=True,
            token_estimate=128,
            warnings=["example warning"],
            source_trail=["source:ok"],
            token_estimate_breakdown=TokenEstimateBreakdown(
                abstract=32, body=96, refs=24
            ),
        ),
    )


def sample_envelope(*, modes: set[str], doi: str = "10.1000/example") -> FetchEnvelope:
    article = sample_article()
    article.doi = doi
    article.metadata.title = (
        "Example Article" if doi == "10.1000/example" else f"Article for {doi}"
    )
    return FetchEnvelope(
        doi=doi,
        source="elsevier_xml",
        has_fulltext=True,
        warnings=["example warning"],
        source_trail=["source:ok"],
        token_estimate=article.quality.token_estimate,
        token_estimate_breakdown=article.quality.token_estimate_breakdown,
        quality=article.quality,
        article=article if "article" in modes else None,
        markdown="# Example Article\n\nExample body.\n"
        if "markdown" in modes
        else None,
        metadata=article.metadata if "metadata" in modes else None,
    )


def sample_resolved_query(query: str) -> ResolvedQuery:
    return ResolvedQuery(
        query=query,
        query_kind="doi",
        doi=query if query.startswith("10.") else "10.1000/example",
        landing_url="https://example.test/article",
        provider_hint="crossref",
        confidence=1.0,
        candidates=[],
        title="Example Article",
    )


def sample_probe_result(
    query: str,
    *,
    doi: str | None = None,
    title: str | None = None,
    state: str = "likely_yes",
    evidence: list[str] | None = None,
    warnings: list[str] | None = None,
) -> HasFulltextProbeResult:
    return HasFulltextProbeResult(
        query=query,
        doi=doi or (query if query.startswith("10.") else "10.1000/example"),
        title=title or f"Article for {query}",
        state=state,
        evidence=list(evidence or ["crossref_fulltext_link"]),
        warnings=list(warnings or []),
    )


def create_cached_downloads(download_dir: Path, doi: str) -> None:
    base = sanitize_filename(doi)
    download_dir.mkdir(parents=True, exist_ok=True)
    (download_dir / f"{base}.xml").write_text("<article />", encoding="utf-8")
    (download_dir / f"{base}.md").write_text(
        "\n".join(
            [
                "---",
                f'doi: "{doi}"',
                'source: "unit_test"',
                "has_fulltext: true",
                'content_kind: "fulltext"',
                "---",
                "",
                "# Cached Markdown",
                "",
            ]
        ),
        encoding="utf-8",
    )
    asset_dir = download_dir / f"{base}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "figure-1.png").write_bytes(b"\x89PNG\r\n")


def create_cached_fetch_envelope(
    download_dir: Path,
    doi: str,
    *,
    modes: list[str] | None = None,
    extraction_revision: int = EXTRACTION_REVISION,
) -> None:
    request = {
        "modes": list(modes or ["article", "markdown"]),
        "strategy": {
            "allow_metadata_only_fallback": True,
            "preferred_providers": None,
            "asset_profile": None,
        },
        "include_refs": None,
        "max_tokens": "full_text",
    }
    payload = sample_envelope(modes=set(request["modes"]), doi=doi).to_dict()
    path = mcp_tools._fetch_envelope_cache_path(download_dir, doi)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": mcp_tools._FETCH_ENVELOPE_CACHE_VERSION,
                "extraction_revision": extraction_revision,
                "request": request,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    mcp_tools.refresh_cache_index_for_doi(download_dir, doi)


def write_binary(path: Path, size: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n" + (b"x" * max(0, size - 6)))


def fake_service_fetch_with_cached_downloads(
    query, *, modes=None, context=None, **kwargs
):
    download_dir = context.download_dir if context is not None else None
    if download_dir is not None:
        create_cached_downloads(download_dir, query)
    return sample_envelope(modes=set(modes or []), doi=query)


async def wait_for_threading_event(event: threading.Event, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if event.is_set():
            return True
        await asyncio.sleep(0.01)
    return event.is_set()


class FakeSession:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.resource_list_changed_calls = 0

    async def send_log_message(
        self, *, level, data, logger=None, related_request_id=None
    ) -> None:
        self.messages.append(
            {
                "level": level,
                "data": data,
                "logger": logger,
                "related_request_id": related_request_id,
            }
        )

    async def send_resource_list_changed(self) -> None:
        self.resource_list_changed_calls += 1


class FakeContext:
    def __init__(self) -> None:
        self.progress: list[tuple[float, float | None, str | None]] = []
        self.session = FakeSession()
        self.request_id = "unit-request"
        self.protocol_version = LATEST_HANDSHAKE_VERSION

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        self.progress.append((progress, total, message))


__all__ = [name for name in globals() if not name.startswith("__")]
