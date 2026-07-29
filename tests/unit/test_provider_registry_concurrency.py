from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import threading
import time
from unittest import mock

import pytest

from paper_fetch.providers import _registry
from paper_fetch.providers._registry import ProviderBundle, provider_bundle
from paper_fetch.providers.registry import FailedProviderClient, build_clients
from paper_fetch.runtime import RuntimeContext


def test_runtime_context_builds_clients_once_under_concurrent_first_access(
    monkeypatch,
) -> None:
    calls = 0
    calls_lock = threading.Lock()
    expected = {"provider": object()}

    def fake_build_clients(_transport, _env):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.02)
        return expected

    monkeypatch.setattr(
        "paper_fetch.providers.registry.build_clients",
        fake_build_clients,
    )
    context = RuntimeContext(env={})
    barrier = threading.Barrier(8)
    results: list[object] = []

    def load_clients() -> None:
        barrier.wait()
        results.append(context.get_clients())

    threads = [threading.Thread(target=load_clients) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    context.close()

    assert calls == 1
    assert results == [expected] * 8


def test_build_clients_isolates_one_factory_failure(monkeypatch) -> None:
    specs = (
        SimpleNamespace(
            name="broken",
            client_factory_path="test:broken",
            official=True,
        ),
        SimpleNamespace(
            name="healthy",
            client_factory_path="test:healthy",
            official=True,
        ),
    )
    healthy_client = object()

    def factory_for(path: str):
        if path == "test:broken":
            raise RuntimeError("factory exploded")
        return lambda _transport, _env: healthy_client

    monkeypatch.setattr(
        "paper_fetch.providers.registry.ordered_provider_specs",
        lambda: specs,
    )
    monkeypatch.setattr(
        "paper_fetch.providers.registry._client_factory",
        factory_for,
    )

    clients = build_clients(transport=mock.Mock(), env={})

    assert isinstance(clients["broken"], FailedProviderClient)
    assert clients["healthy"] is healthy_client


@pytest.mark.parametrize(
    ("conflict_field", "expected_message"),
    [
        ("status_order", "status_order conflict"),
        ("client_factory_path", "client factory conflict"),
        ("sources", "source conflict"),
        ("domains", "domain conflict"),
    ],
)
def test_registration_conflicts_are_rejected_before_mutation(
    conflict_field: str,
    expected_message: str,
) -> None:
    existing = provider_bundle("elsevier")
    catalog = replace(
        existing.catalog,
        name=f"conflict_{conflict_field}",
        status_order=10_000,
        client_factory_path=f"test.factory:{conflict_field}",
        domains=(f"{conflict_field}.example.test",),
    )
    sources = (f"{conflict_field}_source",)
    if conflict_field == "status_order":
        catalog = replace(catalog, status_order=existing.catalog.status_order)
    elif conflict_field == "client_factory_path":
        catalog = replace(
            catalog,
            client_factory_path=existing.catalog.client_factory_path,
        )
    elif conflict_field == "sources":
        sources = existing.sources
    elif conflict_field == "domains":
        catalog = replace(catalog, domains=existing.catalog.domains)
    candidate = ProviderBundle(catalog=catalog, sources=sources)

    with pytest.raises(ValueError, match=expected_message):
        _registry._validate_registration_conflicts(
            candidate,
            name=catalog.name,
        )
