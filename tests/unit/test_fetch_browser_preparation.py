"""Fetch entrypoint contracts with runtime/download/browser boundaries mocked."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from paper_fetch import cli, service
from paper_fetch.http import RequestCancelledError
from paper_fetch.providers.browser_runtime import preparation
from paper_fetch.runtime import RuntimeContext
from tests.support.fetch_fixtures import sample_article

_PREPARE_FETCH_BROWSER = preparation.FetchBrowserPreparation.prepare


@pytest.fixture
def prepare(monkeypatch):
    monkeypatch.setattr(
        preparation.FetchBrowserPreparation, "prepare", _PREPARE_FETCH_BROWSER
    )
    check = Mock(return_value=None)
    monkeypatch.setattr(
        preparation, "package_versions", lambda: preparation.BROWSER_PACKAGE_PINS
    )
    monkeypatch.setattr(preparation, "prepare_chromium", check)
    return check


def _http_article(prepare):
    def fetch(*_args, **_kwargs):
        assert prepare.call_count == 0
        return sample_article()

    return fetch


def test_cli_batch_prepares_before_scheduling_and_children_inherit(
    prepare, monkeypatch, tmp_path
):
    monkeypatch.setattr(service, "fetch_article", lambda *_a, **_kw: sample_article())

    def resolve(item, **_kwargs):
        return item

    def fetch(_args, *, context, query, **_kwargs):
        result = service.fetch_paper(query, context=context)
        context.prepare_fetch_browser()
        return cli.SingleFetchResult(result)

    monkeypatch.setattr(cli, "_resolve_cli_batch_item_lane", resolve)
    monkeypatch.setattr(cli, "_run_single_fetch_with_context", fetch)
    command = cli.BatchFetchCommand(
        queries=("10.1000/one", "10.1000/two"),
        options=cli.FetchExecutionOptions(artifact_mode="none"),
        batch_concurrency=2,
    )
    assert (
        cli.run_batch_fetch(
            command,
            output_dir=tmp_path,
            runtime_env={},
        )
        == 0
    )
    assert prepare.call_count == 2


@pytest.mark.parametrize("skip", ["core", "custom"])
def test_fetch_skips_managed_update_for_core_and_custom_executable(
    prepare, monkeypatch, skip
):
    monkeypatch.setattr(service, "fetch_article", lambda *_a, **_kw: sample_article())
    if skip == "core":
        monkeypatch.setattr(preparation, "package_versions", lambda: {})
    env = (
        {"PAPER_FETCH_BROWSER_BINARY_PATH": "/custom/chromium"}
        if skip == "custom"
        else {}
    )
    with RuntimeContext(env=env) as context:
        service.fetch_paper("10.1000/example", context=context)
    prepare.assert_not_called()


def test_preparation_failure_can_retry_at_next_launch(prepare, monkeypatch):
    prepare.side_effect = RuntimeError("runtime unavailable")
    with RuntimeContext(env={}) as context:
        with context.fetch_browser_preparation():
            with pytest.raises(RuntimeError, match="runtime unavailable"):
                context.prepare_fetch_browser()
            with context.fetch_browser_preparation():
                with pytest.raises(RuntimeError, match="runtime unavailable"):
                    context.prepare_fetch_browser()
    assert prepare.call_count == 2


def test_request_cancellation_during_preparation_propagates(prepare):
    prepare.side_effect = RequestCancelledError("cancelled")
    with RuntimeContext(env={}) as context:
        with context.fetch_browser_preparation():
            with pytest.raises(RequestCancelledError):
                context.prepare_fetch_browser()
    assert preparation.fetch_browser_preparation.get() is None


def test_static_status_resolve_and_help_do_not_prepare(prepare, monkeypatch):
    from paper_fetch.providers.browser_runtime import probe_runtime_status

    monkeypatch.setattr(service, "workflow_resolve_paper", lambda *_a, **_kw: None)
    with RuntimeContext(env={}) as context:
        service.resolve_paper("10.1000/example", context=context)
    probe_runtime_status({}, provider="science")
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])
    assert result.value.code == 0
    prepare.assert_not_called()


def test_concurrent_fetch_calls_check_separately_even_with_shared_context(
    prepare, monkeypatch
):
    import threading
    from concurrent.futures import ThreadPoolExecutor

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
    prepare.assert_not_called()
