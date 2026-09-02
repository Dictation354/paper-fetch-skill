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
    healthy_client = object()

    def broken_factory(_transport, _env):
        raise RuntimeError("factory exploded")

    def healthy_factory(_transport, _env):
        return healthy_client

    bundles = (
        SimpleNamespace(
            catalog=SimpleNamespace(name="broken", official=True),
            client_factory=broken_factory,
        ),
        SimpleNamespace(
            catalog=SimpleNamespace(name="healthy", official=True),
            client_factory=healthy_factory,
        ),
    )

    monkeypatch.setattr(
        "paper_fetch.providers.registry.PROVIDER_BUNDLES",
        bundles,
    )

    clients = build_clients(transport=mock.Mock(), env={})

    assert isinstance(clients["broken"], FailedProviderClient)
    assert clients["healthy"] is healthy_client


@pytest.mark.parametrize(
    ("conflict_field", "expected_message"),
    [
        ("status_order", "status_order conflict"),
        ("client_factory", "client factory conflict"),
        ("sources", "source conflict"),
        ("domains", "domain conflict"),
    ],
)
def test_fixed_catalog_conflicts_are_rejected(
    conflict_field: str,
    expected_message: str,
) -> None:
    existing = provider_bundle("elsevier")
    catalog = replace(
        existing.catalog,
        name=f"conflict_{conflict_field}",
        display_name=f"Conflict {conflict_field}",
        publisher_aliases=(),
        doi_prefixes=(),
        domain_suffixes=(),
        status_order=10_000,
        domains=(f"{conflict_field}.example.test",),
    )
    sources: tuple[str, ...] = (f"{conflict_field}_source",)

    def client_factory(_transport, _env):
        return object()

    if conflict_field == "status_order":
        catalog = replace(catalog, status_order=existing.catalog.status_order)
    elif conflict_field == "client_factory":
        client_factory = existing.client_factory
    elif conflict_field == "sources":
        sources = existing.sources
    elif conflict_field == "domains":
        catalog = replace(catalog, domains=existing.catalog.domains)
    candidate = ProviderBundle(
        catalog=catalog,
        client_factory=client_factory,
        sources=sources,
    )

    with pytest.raises(ValueError, match=expected_message):
        _registry.validate_provider_bundles((existing, candidate))


def test_fixed_catalog_rejects_duplicate_sources_within_bundle() -> None:
    existing = provider_bundle("elsevier")

    def client_factory(_transport, _env):
        return object()

    candidate = ProviderBundle(
        client_factory=client_factory,
        catalog=replace(
            existing.catalog,
            name="duplicate_sources",
            display_name="Duplicate Sources",
            publisher_aliases=(),
            doi_prefixes=(),
            domains=("duplicate-sources.example.test",),
            status_order=10_000,
        ),
        sources=("duplicate_source", "duplicate_source"),
    )

    with pytest.raises(ValueError, match="source declared more than once"):
        _registry.validate_provider_bundles((candidate,))


def test_provider_bundle_rejects_non_callable_factory() -> None:
    existing = provider_bundle("elsevier")

    with pytest.raises(TypeError, match="client_factory must be callable"):
        ProviderBundle(
            catalog=existing.catalog,
            client_factory="paper_fetch.providers.elsevier:ElsevierClient",  # type: ignore[arg-type]
            sources=existing.sources,
        )
