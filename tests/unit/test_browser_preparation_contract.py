"""Component preparation results and request scopes, with no browser/network I/O."""

from concurrent.futures import ThreadPoolExecutor
import json
import threading
from unittest.mock import Mock

import pytest

from paper_fetch.http import RequestCancelledError
from paper_fetch.providers.browser_runtime import preparation as prep
from paper_fetch.providers.browser_runtime import byparr_preparation as flare
from paper_fetch.models.codec import envelope_from_payload, model_to_payload
from paper_fetch.runtime import RuntimeContext
from tests.support._mcp_support import sample_envelope


def test_latest_failure_overrides_earlier_success(tmp_path):
    record = tmp_path / "check.json"
    identity = {"component": "test"}
    prep._write_update_check(tmp_path, record, identity)
    assert prep._recent_update_check(record, identity)
    success = json.loads(record.read_text())["checked_at"]
    with pytest.raises(OSError), prep._record_update_check(tmp_path, record, identity):
        raise OSError("offline")
    assert not prep._recent_update_check(record, identity)
    assert json.loads(record.read_text())["checked_at"] == success


def test_legacy_record_is_not_success(tmp_path):
    record = tmp_path / "check.json"
    record.write_text(json.dumps({"checked_at": prep.time.time()}))
    assert not prep._recent_update_check(record, {})


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


def test_offline_component_missing_never_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(flare, "bundled_component_root", lambda: tmp_path / "missing")
    download = Mock(side_effect=AssertionError("offline source must not download"))
    monkeypatch.setattr(flare, "download", download)
    with pytest.raises(flare.BrowserRuntimeFailure) as error:
        flare.prepare_source(tmp_path / "cache", flare.PreparationBudget(1))
    assert error.value.kind == "byparr_installation_error"
    download.assert_not_called()


def test_clients_stay_lazy_and_child_transport_is_borrowed(monkeypatch):
    from paper_fetch.providers import registry

    factory = Mock(return_value={"pnas": object()})
    monkeypatch.setattr(registry, "build_clients", factory)
    transport = Mock()
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
    offline_browsers.prepare(setup, selection="all", interactive=False)
    assert [call.args[0] for call in setup.step.call_args_list] == ["Byparr"]


def test_byparr_scope_reuses_verified_component_and_retries_damage(
    tmp_path, monkeypatch
):
    root = tmp_path / "runtime"
    root.mkdir()
    ready = [True]
    action = Mock(return_value=root)
    monkeypatch.setattr(flare, "prepare_source", action)
    monkeypatch.setattr(flare, "runtime_location", lambda _: (root, {}, "identity"))
    monkeypatch.setattr(flare, "valid_cache", lambda *_: ready[0])
    token = prep.fetch_browser_preparation.set(prep.FetchBrowserPreparation())
    try:
        budget = flare.PreparationBudget(5)
        assert flare.prepare_components(tmp_path, budget) == root
        assert flare.prepare_components(tmp_path, budget) == root
        assert action.call_count == 1
        ready[0] = False
        assert flare.prepare_components(tmp_path, budget) == root
        assert action.call_count == 2
    finally:
        prep.fetch_browser_preparation.reset(token)
