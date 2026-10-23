"""Fetch entrypoint contracts with runtime/download/browser boundaries mocked."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from paper_fetch import cli, service
from paper_fetch.http import RequestCancelledError
from paper_fetch.mcp import fetch_tool
from paper_fetch.mcp._deps import default_mcp_deps
from paper_fetch.mcp.batch_fetch import batch_fetch_tool_async
from paper_fetch.providers.browser_runtime import preparation
from paper_fetch.providers.browser_runtime.camoufox_manager import (
    _launch_executable_path,
)
from paper_fetch.runtime import RuntimeContext
from tests.support._mcp_support import (
    sample_article,
    sample_envelope,
    sample_resolved_query,
)

_PREPARE_FETCH_BROWSER = preparation.FetchBrowserPreparation.prepare


@pytest.fixture
def prepare(monkeypatch):
    monkeypatch.setattr(
        preparation.FetchBrowserPreparation, "prepare", _PREPARE_FETCH_BROWSER
    )
    check = Mock(return_value=preparation.CamoufoxRuntimeProbe("ready", True, True))
    monkeypatch.setattr(preparation, "find_spec", lambda _name: object())
    monkeypatch.setattr(preparation, "prepare_camoufox_managed_runtime", check)
    # A repeated preparation at launch would bypass the per-request boundary.
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.prepare_camoufox_managed_runtime",
        lambda: pytest.fail("launch must reuse the request preparation"),
    )
    return check


def _http_article(prepare):
    def fetch(*_args, **_kwargs):
        assert prepare.call_count >= 1
        return sample_article()

    return fetch


@pytest.mark.parametrize("entrypoint", ["api", "cli", "mcp", "mcp_async"])
def test_each_fetch_call_prepares_once_even_for_http(
    prepare, monkeypatch, tmp_path, entrypoint
):
    monkeypatch.setattr(service, "fetch_article", _http_article(prepare))

    # The pipeline is the CLI's fetch/output boundary; exercise its nested API call.
    def cli_fetch(_args, *, context, query, **_kwargs):
        result = service.fetch_paper(query, context=context)
        assert _launch_executable_path(None) is None
        return cli.SingleFetchResult(result)

    monkeypatch.setattr(cli, "_run_single_fetch_with_context", cli_fetch)
    deps = replace(default_mcp_deps(), service_fetch_paper=service.fetch_paper)
    with RuntimeContext(env={}, download_dir=None, artifact_mode="none") as context:
        for expected in (1, 2):
            if entrypoint == "api":
                service.fetch_paper("10.1000/example", context=context)
            elif entrypoint == "cli":
                cli.run_single_fetch(
                    SimpleNamespace(asset_profile="none"),
                    query="10.1000/example",
                    output_dir=tmp_path,
                    runtime_env={},
                    artifact_mode="none",
                    context=context,
                )
            elif entrypoint == "mcp":
                fetch_tool.fetch_paper_payload(
                    query="10.1000/example",
                    no_download=True,
                    env={},
                    download_dir=None,
                    context=context,
                    deps=deps,
                )
            else:
                result = asyncio.run(
                    fetch_tool.fetch_paper_tool_async(
                        query="10.1000/example",
                        no_download=True,
                        env={},
                        download_dir=None,
                        deps=deps,
                    )
                )
                assert result.is_error is False
            assert prepare.call_count == expected
    assert preparation.fetch_browser_preparation.get() is None


@pytest.mark.parametrize("failure", [False, True])
def test_mcp_cache_hit_prepares_before_read_and_defers_failure(
    prepare, monkeypatch, failure, capsys
):
    if failure:
        prepare.side_effect = RuntimeError("runtime unavailable")
    cached = sample_envelope(modes={"markdown"})

    def load(*_args, **_kwargs):
        prepare.assert_called_once()
        return cached

    monkeypatch.setattr(fetch_tool, "_load_cached_fetch_envelope", load)
    service_fetch = Mock(side_effect=AssertionError("cache must satisfy fetch"))
    deps = replace(default_mcp_deps(), service_fetch_paper=service_fetch)
    payload = fetch_tool.fetch_paper_payload(
        query="10.1000/example",
        prefer_cache=True,
        no_download=True,
        env={},
        download_dir=None,
        deps=deps,
    )
    assert payload["source"] == cached.source
    prepare.assert_called_once()
    service_fetch.assert_not_called()
    if failure:
        assert "runtime unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("failure", [False, True])
def test_batch_prepares_once_and_children_and_launches_reuse_result(
    prepare, monkeypatch, tmp_path, failure
):
    if failure:
        prepare.side_effect = RuntimeError("runtime unavailable")
    monkeypatch.setattr(service, "fetch_article", _http_article(prepare))

    def resolve(query, **_kwargs):
        prepare.assert_called_once()
        return sample_resolved_query(query)

    def fetch(query, *, context, **_kwargs):
        result = service.fetch_paper(query, context=context)
        if failure:
            with pytest.raises(RuntimeError, match="runtime unavailable"):
                _launch_executable_path(None)
        else:
            assert _launch_executable_path(None) is None
        return result

    deps = replace(
        default_mcp_deps(),
        service_fetch_paper=fetch,
        service_resolve_paper=resolve,
    )
    result = asyncio.run(
        batch_fetch_tool_async(
            queries=["10.1000/one", "10.1000/two"],
            concurrency=2,
            no_download=True,
            artifact_mode="none",
            env={},
            deps=deps,
        )
    )
    assert result.is_error is False
    assert result.structured_content["execution_count"] == 2
    prepare.assert_called_once()


def test_cli_batch_prepares_before_scheduling_and_children_inherit(
    prepare, monkeypatch, tmp_path
):
    monkeypatch.setattr(service, "fetch_article", _http_article(prepare))

    def resolve(item, **_kwargs):
        prepare.assert_called_once()
        return item

    def fetch(_args, *, context, query, **_kwargs):
        result = service.fetch_paper(query, context=context)
        assert _launch_executable_path(None) is None
        return cli.SingleFetchResult(result)

    monkeypatch.setattr(cli, "_resolve_cli_batch_item_lane", resolve)
    monkeypatch.setattr(cli, "_run_single_fetch_with_context", fetch)
    args = SimpleNamespace(
        batch_results=None,
        batch_concurrency=2,
        format="markdown",
        asset_profile="none",
        include_refs="all",
        max_tokens="full_text",
        no_download=True,
        save_markdown_to_disk=False,
        output="-",
    )
    assert (
        cli.run_batch_fetch(
            args,
            queries=["10.1000/one", "10.1000/two"],
            output_dir=tmp_path,
            runtime_env={},
            artifact_mode="none",
        )
        == 0
    )
    prepare.assert_called_once()


@pytest.mark.parametrize("skip", ["core", "custom"])
def test_fetch_skips_managed_update_for_core_and_custom_executable(
    prepare, monkeypatch, skip
):
    monkeypatch.setattr(service, "fetch_article", lambda *_a, **_kw: sample_article())
    if skip == "core":
        monkeypatch.setattr(preparation, "find_spec", lambda _name: None)
    env = (
        {"PAPER_FETCH_BROWSER_BINARY_PATH": "/custom/camoufox"}
        if skip == "custom"
        else {}
    )
    with RuntimeContext(env=env) as context:
        service.fetch_paper("10.1000/example", context=context)
    prepare.assert_not_called()


def test_preparation_failure_keeps_http_and_reports_same_failure_at_launch(
    prepare, monkeypatch
):
    prepare.side_effect = RuntimeError("runtime unavailable")
    with RuntimeContext(env={}) as context:
        with context.fetch_browser_preparation():
            with pytest.raises(RuntimeError, match="runtime unavailable"):
                _launch_executable_path(None)
            with context.fetch_browser_preparation():
                with pytest.raises(RuntimeError, match="runtime unavailable"):
                    _launch_executable_path(None)
    prepare.assert_called_once()


def test_request_cancellation_during_preparation_propagates(prepare):
    prepare.side_effect = RequestCancelledError("cancelled")
    with RuntimeContext(env={}) as context:
        with pytest.raises(RequestCancelledError):
            service.fetch_paper("10.1000/example", context=context)
    assert preparation.fetch_browser_preparation.get() is None


def test_static_status_resolve_and_help_do_not_prepare(prepare, monkeypatch):
    from paper_fetch.providers.browser_runtime.backends.camoufox import CamoufoxBackend

    monkeypatch.setattr(service, "workflow_resolve_paper", lambda *_a, **_kw: None)
    with RuntimeContext(env={}) as context:
        service.resolve_paper("10.1000/example", context=context)
    CamoufoxBackend().probe_runtime_status({}, provider="science")
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])
    assert result.value.code == 0
    prepare.assert_not_called()


def test_concurrent_fetch_calls_check_separately_even_with_shared_context(
    prepare, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    barrier = threading.Barrier(2)

    def article(*_args, **_kwargs):
        barrier.wait(timeout=5)
        return sample_article()

    monkeypatch.setattr(service, "fetch_article", article)
    with RuntimeContext(env={}) as context:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: service.fetch_paper("10.1000/example", context=context),
                    range(2),
                )
            )
    assert len(results) == 2
    assert prepare.call_count == 2
