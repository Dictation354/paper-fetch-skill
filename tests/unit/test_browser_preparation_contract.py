"""Component preparation results and request scopes, with no browser/network I/O."""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from paper_fetch.http import RequestCancelledError
from paper_fetch.models.codec import envelope_from_payload, model_to_payload
from paper_fetch.providers.browser_runtime import (
    preparation as prep,
)
from paper_fetch.runtime import RuntimeContext
from tests.support.fetch_fixtures import sample_envelope
from tests.support.transport import configure_stream_transport


@pytest.mark.parametrize(
    "failure", [OSError("offline"), RequestCancelledError("cancelled")]
)
def test_scope_failure_is_retryable(failure):
    scope = prep.FetchBrowserPreparation()
    action = Mock(side_effect=[failure, "ready"])
    with pytest.raises(type(failure)):
        scope.run("component", action)
    assert scope.run("component", action) == "ready"
    assert scope.run("component", action) == "ready"
    assert action.call_count == 2


def test_concurrent_scope_preparation_is_shared():
    scope = prep.FetchBrowserPreparation()
    barrier = threading.Barrier(5)
    release = threading.Event()
    action = Mock(side_effect=lambda: (release.wait(3), "ready")[1])

    def run():
        barrier.wait(3)
        return scope.run("component", action)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(run) for _ in range(5)]
        release.set()
        assert [future.result() for future in futures] == ["ready"] * 5
    action.assert_called_once()


def test_clients_stay_lazy_and_child_transport_is_borrowed(monkeypatch):
    from paper_fetch.providers import registry

    factory = Mock(return_value={"pnas": object()})
    monkeypatch.setattr(registry, "build_clients", factory)
    transport = Mock()
    configure_stream_transport(transport)
    monkeypatch.setattr(
        "paper_fetch.runtime.build_http_transport_for_context",
        lambda *a, **kw: transport,
    )
    with RuntimeContext(env={}) as root:
        mapping = root.get_clients()
        assert "pnas" in tuple(mapping)
        factory.assert_not_called()
        with root.new_request_context() as child:
            assert child.transport is transport
            assert child.get_clients() is not mapping
        transport.close.assert_not_called()
        assert mapping["pnas"] is mapping["pnas"]
        factory.assert_called_once()
    transport.close.assert_called_once()


def test_model_round_trip_preserves_body_assets_and_quality_identity():
    envelope = sample_envelope(modes={"markdown"})
    if envelope.article is not None:
        envelope.article.sections[0].text = "First line\n\n  second line\n"
    payload = model_to_payload(envelope)
    decoded = envelope_from_payload(payload)
    assert model_to_payload(decoded) == payload
    if decoded.article is not None:
        assert decoded.quality is decoded.article.quality


def test_all_prepares_only_supported_backends(monkeypatch):
    from paper_fetch import offline_browsers

    monkeypatch.setattr(offline_browsers.sys, "platform", "darwin")
    setup = Mock()
    offline_browsers.prepare(setup, interactive=False)
    assert [call.args[0] for call in setup.step.call_args_list] == ["Chromium"]
