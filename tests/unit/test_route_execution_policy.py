from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest import mock

import pytest

from paper_fetch.http import (
    HttpRequestPolicy,
    HttpTransport,
    HttpTransportOptions,
    RequestCancelledError,
)
from paper_fetch.http.provider_policy import provider_request_policy
import paper_fetch.provider_catalog as provider_catalog_module
from paper_fetch.asset_budget import AssetBudget
from paper_fetch.extraction.html.assets import FIGURE_KIND, download_assets
from paper_fetch.provider_catalog import (
    compile_route_execution_policy,
    effective_route_asset_scope,
)
from paper_fetch.providers import _playwright_browser
from paper_fetch.providers import _pdf_fallback
from paper_fetch.providers import _arxiv_assets
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from paper_fetch.providers.plos import PlosClient, _fetch_plos_redirected_response
from paper_fetch.providers.browser_runtime.types import BrowserRuntimeConfig


REPO_ROOT = Path(__file__).resolve().parents[2]


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.lock = threading.Lock()
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        with self.lock:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self.lock:
            delay = max(0.0, float(seconds))
            self.sleeps.append(delay)
            self.now += delay


class _ControlledClock:
    """A monotonic clock advanced explicitly by the test thread."""

    def __init__(self) -> None:
        self.now = 0.0
        self.condition = threading.Condition()
        self.waiting_targets: list[float] = []

    def monotonic(self) -> float:
        with self.condition:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self.condition:
            target = self.now + max(0.0, float(seconds))
            self.waiting_targets.append(target)
            self.condition.notify_all()
            self.condition.wait_for(lambda: self.now >= target)
            self.waiting_targets.remove(target)
            self.condition.notify_all()

    def wait_until_sleeping_for(self, target: float) -> None:
        with self.condition:
            assert self.condition.wait_for(
                lambda: target in self.waiting_targets,
                timeout=2,
            )

    def advance_to(self, target: float) -> None:
        with self.condition:
            self.now = max(self.now, target)
            self.condition.notify_all()


def test_compiler_unifies_hosts_and_runtime_route_fields() -> None:
    copernicus = compile_route_execution_policy("copernicus", "xml")
    arxiv = compile_route_execution_policy("arxiv", "atom_metadata")

    assert "copernicus.org" in copernicus.hosts
    assert copernicus.acceptance_policy == "structured_xml_body"
    assert copernicus.asset_scope == "body"
    assert copernicus.asset_concurrency_cap == copernicus.concurrency
    assert "dns_error" in copernicus.transient_retry_categories
    assert "temporary_dns" not in copernicus.transient_retry_categories
    assert arxiv.timeout_seconds == 60
    assert arxiv.qps == 1 / 3
    assert arxiv.minimum_interval_seconds == 3.0
    assert arxiv.retry_on_transient is True


def test_provider_owned_network_calls_do_not_inline_raw_request_policy() -> None:
    violations: list[str] = []
    roots = (
        REPO_ROOT / "src/paper_fetch/providers",
        REPO_ROOT / "src/paper_fetch/metadata",
        REPO_ROOT / "src/paper_fetch/extraction",
    )
    for path in (path for root in roots for path in root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function_name = (
                node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if function_name not in {"request", "request_preview", "stream_to_file"}:
                continue
            for keyword in node.keywords:
                if keyword.arg != "request_policy" or not isinstance(
                    keyword.value, ast.Call
                ):
                    continue
                policy_factory = keyword.value.func
                if isinstance(policy_factory, ast.Name) and (
                    policy_factory.id == "HttpRequestPolicy"
                ):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

    assert violations == []


def test_provider_request_policy_projects_compiled_execution_fields() -> None:
    policy = provider_request_policy(
        "arxiv",
        "atom_metadata",
        base=HttpRequestPolicy(allowed_hosts=("mirror.example",)),
    )

    assert "mirror.example" in tuple(policy.allowed_hosts or ())
    assert "arxiv.org" in tuple(policy.allowed_hosts or ())
    assert policy.timeout_seconds == 60
    assert policy.retry_on_transient is True
    assert policy.transient_retries == 2
    assert policy.minimum_interval_seconds == 3.0
    assert policy.cooldown_scope == "provider:arxiv:atom_metadata"
    assert policy.acceptance_policy == "metadata_identity"


def test_shared_rate_slots_space_concurrent_workers_without_real_sleep() -> None:
    transport = HttpTransport(cache_ttl=0, cache_capacity=0)
    clock = _FakeClock()
    barrier = threading.Barrier(3)
    starts: list[float] = []
    starts_lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        transport._wait_for_rate_slot("arxiv", 3.0, None)
        with starts_lock:
            starts.append(clock.monotonic())

    with (
        mock.patch("paper_fetch.http.transport.time.monotonic", clock.monotonic),
        mock.patch.object(transport, "_cancellable_sleep", clock.sleep),
        ThreadPoolExecutor(max_workers=3) as executor,
    ):
        futures = [executor.submit(worker) for _ in range(3)]
        for future in futures:
            future.result()

    assert sorted(starts) == [0.0, 3.0, 6.0]
    assert all(delay <= 3.0 for delay in clock.sleeps)


def test_retry_after_extends_existing_pacing_deadline() -> None:
    transport = HttpTransport(cache_ttl=0, cache_capacity=0)
    clock = _FakeClock()

    with (
        mock.patch("paper_fetch.http.transport.time.monotonic", clock.monotonic),
        mock.patch.object(transport, "_cancellable_sleep", clock.sleep),
    ):
        transport._wait_for_rate_slot("arxiv", 3.0, None)
        transport._set_cooldown("arxiv", 10.0)
        transport._wait_for_rate_slot("arxiv", 3.0, None)

    assert clock.monotonic() == 10.0
    assert clock.sleeps == [10.0]


def test_late_retry_after_keeps_queued_starts_serialized() -> None:
    transport = HttpTransport(cache_ttl=0, cache_capacity=0)
    clock = _ControlledClock()
    semaphore = threading.BoundedSemaphore(1)
    entered = threading.Barrier(3)
    starts: list[float] = []

    with (
        mock.patch("paper_fetch.http.transport.time.monotonic", clock.monotonic),
        mock.patch.object(transport, "_cancellable_sleep", clock.sleep),
    ):
        transport._wait_for_rate_slot("arxiv", 3.0, None)

        def worker() -> None:
            entered.wait()
            with semaphore:
                transport._wait_for_rate_slot("arxiv", 3.0, semaphore)
                starts.append(clock.monotonic())

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            entered.wait()
            clock.wait_until_sleeping_for(3.0)
            transport._set_cooldown("arxiv", 10.0)

            # Both the paced sleeper and the waiter behind its start gate have
            # released their host slots.  A response on this host can therefore
            # complete and publish the Retry-After extension without deadlock.
            assert semaphore.acquire(blocking=False)
            semaphore.release()

            clock.advance_to(3.0)
            clock.wait_until_sleeping_for(10.0)
            clock.advance_to(10.0)
            clock.wait_until_sleeping_for(13.0)
            clock.advance_to(13.0)
            for future in futures:
                future.result()

    assert sorted(starts) == [10.0, 13.0]


def test_rate_start_gate_propagates_cancellation_and_restores_host_slot() -> None:
    cancelled = threading.Event()
    transport = HttpTransport(
        cache_ttl=0,
        cache_capacity=0,
        options=HttpTransportOptions(cancel_check=cancelled.is_set),
    )
    gate = transport._rate_start_gate_for("arxiv")
    semaphore = threading.BoundedSemaphore(1)
    gate.acquire()
    cancelled.set()
    try:
        with semaphore, pytest.raises(RequestCancelledError, match="cancelled"):
            transport._wait_for_rate_slot("arxiv", 3.0, semaphore)
    finally:
        gate.release()

    assert semaphore.acquire(blocking=False)
    semaphore.release()


def test_browser_runtime_caps_deadline_from_compiled_route_policy(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _playwright_browser,
        "compile_route_execution_policy_for_kind",
        lambda *_args, **_kwargs: SimpleNamespace(
            timeout_seconds=7,
            hosts=("annualreviews.com",),
        ),
    )
    config = BrowserRuntimeConfig(
        provider="annualreviews",
        doi="10.1146/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        timeout_ms=120_000,
        backend="camoufox",
    )

    with pytest.raises(_playwright_browser.PlaywrightBrowserFailure) as captured:
        _playwright_browser.fetch_html_with_playwright(
            ["http://127.0.0.1/private"],
            publisher="annualreviews",
            config=config,
        )

    assert captured.value.kind == "unsafe_browser_url"
    assert captured.value.details["trace"]["timeout_budget_ms"] == 7_000


def test_pdf_strategy_uses_compiled_timeout_hosts_and_route_identity() -> None:
    transport = HttpTransport(cache_ttl=0, cache_capacity=0)
    expected = object()
    strategy = _pdf_fallback.PdfFallbackStrategy(
        transport=transport,
        timeout=999,
        provider_name="iop",
    )

    with mock.patch.object(
        _pdf_fallback, "fetch_pdf_over_http", return_value=expected
    ) as fetch:
        result = strategy.fetch(["https://iopscience.iop.org/article.pdf"])

    assert result is expected
    kwargs = fetch.call_args.kwargs
    compiled = compile_route_execution_policy("iop", "browser_pdf")
    assert kwargs["request"].timeout_seconds == compiled.timeout_seconds
    assert kwargs["allowed_hosts"] == compiled.hosts
    assert kwargs["request"].provider_name == "iop"
    assert "provider_name" not in kwargs


def test_pdf_direct_compatibility_provider_compiles_exact_route_policy() -> None:
    candidate = "https://iopscience.iop.org/article.pdf"
    transport = mock.Mock()
    transport.request.return_value = {
        "status_code": 200,
        "headers": {"content-type": "application/pdf"},
        "url": candidate,
        "body": b"%PDF-1.7",
    }
    expected = _pdf_fallback.PdfFetchResult(
        source_url=candidate,
        final_url=candidate,
        pdf_bytes=b"%PDF-1.7",
        markdown_text="# Article\n\nBody",
    )

    with mock.patch.object(
        _pdf_fallback,
        "pdf_fetch_result_from_bytes",
        return_value=expected,
    ):
        result = _pdf_fallback.fetch_pdf_over_http(
            transport,
            [candidate],
            provider_name="iop",
        )

    assert result.pdf_bytes == expected.pdf_bytes
    policy = transport.request.call_args.kwargs["request_policy"]
    compiled = compile_route_execution_policy("iop", "browser_pdf")
    assert policy.timeout_seconds == compiled.timeout_seconds
    assert policy.allowed_hosts == compiled.hosts
    assert policy.transient_retries == compiled.transient_retries


def test_pdf_browser_route_context_binds_compiled_timeout_hosts_and_provider(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = compile_route_execution_policy("iop", "browser_pdf")
    config = BrowserRuntimeConfig(
        provider="iop",
        doi="10.1088/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        timeout_ms=999_000,
        backend="camoufox",
    )
    monkeypatch.setattr(_pdf_fallback.time, "monotonic", lambda: 12.0)

    prepared = _pdf_fallback._prepare_pdf_browser_route_request(
        _pdf_fallback.PdfRequestContext(),
        browser_config=config,
        provider_name=None,
    )

    assert prepared.provider_name == "iop"
    assert prepared.timeout_seconds == compiled.timeout_seconds
    assert prepared.allowed_hosts == compiled.hosts
    assert prepared.request.provider_name == "iop"
    assert prepared.request.deadline_monotonic == 12.0 + compiled.timeout_seconds


def test_oxford_pdf_request_consumes_exact_compiled_policy() -> None:
    transport = mock.Mock()
    candidate = "https://academic.oup.com/doi/pdf/10.1093/example"
    transport.request.return_value = {
        "status_code": 200,
        "headers": {"content-type": "application/pdf"},
        "url": candidate,
        "body": b"%PDF-1.7",
    }

    OxfordAcademicClient(transport, {})._request_pdf_candidate(candidate)

    kwargs = transport.request.call_args.kwargs
    compiled = compile_route_execution_policy("oxfordacademic", "direct_pdf")
    assert "timeout" not in kwargs
    assert "retry_on_transient" not in kwargs
    assert kwargs["request_policy"].timeout_seconds == compiled.timeout_seconds == 120
    assert kwargs["request_policy"].allowed_hosts == compiled.hosts
    assert kwargs["request_policy"].transient_retries == compiled.transient_retries


def test_oxford_html_request_consumes_exact_compiled_policy() -> None:
    transport = mock.Mock()
    client = OxfordAcademicClient(transport, {})
    doi = "10.1093/example"
    candidate = client.html_candidates(doi, {"doi": doi})[0]
    transport.request.return_value = {
        "status_code": 200,
        "headers": {"content-type": "text/html"},
        "url": candidate,
        "body": b"<html><head><title>Example</title></head><body>Text</body></html>",
    }

    client._fetch_article_attempt(doi, {"doi": doi})

    kwargs = transport.request.call_args.kwargs
    compiled = compile_route_execution_policy("oxfordacademic", "direct_html")
    assert "timeout" not in kwargs
    assert "retry_on_transient" not in kwargs
    assert kwargs["request_policy"].timeout_seconds == compiled.timeout_seconds == 90
    assert kwargs["request_policy"].allowed_hosts == compiled.hosts


def test_plos_asset_redirect_request_consumes_exact_compiled_policy() -> None:
    transport = mock.Mock()
    candidate = "https://journals.plos.org/plosone/article/file?id=info:doi/x"
    transport.request.return_value = {
        "status_code": 200,
        "headers": {"content-type": "image/png"},
        "url": candidate,
        "body": b"png",
    }

    response = _fetch_plos_redirected_response(
        transport,
        candidate,
        headers={},
        route_name="assets",
    )

    assert response is not None
    kwargs = transport.request.call_args.kwargs
    compiled = compile_route_execution_policy("plos", "assets")
    assert "timeout" not in kwargs
    assert "retry_on_transient" not in kwargs
    assert kwargs["request_policy"].timeout_seconds == compiled.timeout_seconds
    assert kwargs["request_policy"].allowed_hosts == compiled.hosts
    assert kwargs["request_policy"].asset_scope == "body"


def test_plos_doi_resolver_consumes_xml_route_hosts_and_retries() -> None:
    doi = "10.1371/journal.pnew.0000001"
    transport = mock.Mock()
    transport.request.return_value = {
        "status_code": 200,
        "headers": {"content-type": "text/html"},
        "url": f"https://journals.plos.org/plosnew/article?id={doi}",
        "body": b"",
    }

    path, reason = PlosClient(transport, {})._resolve_journal_path(doi, {})

    assert (path, reason) == ("plosnew", "doi_resolver")
    kwargs = transport.request.call_args.kwargs
    compiled = compile_route_execution_policy("plos", "xml")
    assert "timeout" not in kwargs
    assert "retry_on_transient" not in kwargs
    assert kwargs["request_policy"].allowed_hosts == compiled.hosts
    assert "doi.org" in compiled.hosts
    assert kwargs["request_policy"].transient_retries == compiled.transient_retries


def test_arxiv_source_stream_consumes_compiled_route_policy(tmp_path) -> None:
    transport = mock.Mock()
    transport._pinned_streaming_ready = True
    source_url = "https://arxiv.org/e-print/2401.00001"
    destination = tmp_path / "source.part"
    budget = AssetBudget(
        max_files=4,
        max_bytes_per_asset=64,
        max_bytes_total=128,
        max_pixels=64,
    )
    reservation = budget.reserve()

    def stream(_method, _url, path, **kwargs):
        kwargs["on_content_length"](4)
        kwargs["on_chunk"](4)
        path.write_bytes(b"data")
        return {"status_code": 200, "url": source_url, "headers": {}}

    transport.stream_to_file.side_effect = stream
    _arxiv_assets._stage_arxiv_source_archive(
        transport,
        source_url,
        destination,
        user_agent="paper-fetch-test",
        asset_budget=budget,
        reservation=reservation,
    )

    kwargs = transport.stream_to_file.call_args.kwargs
    compiled = compile_route_execution_policy("arxiv", "source_assets")
    assert "timeout" not in kwargs
    assert "retry_on_transient" not in kwargs
    assert kwargs["request_policy"].minimum_interval_seconds == 3.0
    assert kwargs["request_policy"].allowed_hosts == compiled.hosts
    reservation.rollback()


def test_compiled_asset_scope_selects_unset_profile_and_catalog_mutation_stops_work(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_catalog = dict(provider_catalog_module.PROVIDER_CATALOG)
    plos = original_catalog["plos"]
    mutated_routes = tuple(
        replace(route, asset_scope="none") if route.name == "assets" else route
        for route in plos.routes
    )
    monkeypatch.setattr(
        provider_catalog_module,
        "PROVIDER_CATALOG",
        {**original_catalog, "plos": replace(plos, routes=mutated_routes)},
    )
    transport = mock.Mock()

    assert (
        effective_route_asset_scope(None, provider_name="plos", route_name="assets")
        == "none"
    )
    assert (
        effective_route_asset_scope("all", provider_name="plos", route_name="assets")
        == "all"
    )
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id="10.1371/example",
        assets=[{"kind": "figure", "url": "https://journals.plos.org/f.png"}],
        output_dir=tmp_path,
        user_agent="paper-fetch-test",
        asset_profile=None,
        provider_name="plos",
    )

    assert result == {"assets": [], "asset_failures": []}
    transport.request.assert_not_called()
