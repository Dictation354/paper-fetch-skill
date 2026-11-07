from __future__ import annotations

import json
from dataclasses import replace

import pytest

from paper_fetch.capability_scope import (
    capability_scope_from_runtime_context,
    UNCACHEABLE_CAPABILITY_SCOPE,
)
from paper_fetch.provider_catalog import (
    ordered_provider_specs,
    provider_has_browser_route,
)
from paper_fetch.providers.browser_runtime.backends.camoufox import (
    DEFAULT_CAMOUFOX_BACKEND,
)

from paper_fetch.providers.browser_runtime.context import (
    browser_context,
    open_browser_context,
)
from paper_fetch.providers.browser_runtime import profile
from paper_fetch.providers.browser_runtime.types import BrowserRuntimeFailure
from paper_fetch.runtime import RuntimeContext
from tests.support.publisher_profiles import NativeProfileDouble


load_runtime_config = DEFAULT_CAMOUFOX_BACKEND.load_runtime_config


@pytest.fixture
def config(tmp_path, monkeypatch):
    NativeProfileDouble.instances = []
    monkeypatch.setattr(profile, "ByparrManager", NativeProfileDouble)
    return load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas", doi="10.1073/pnas.test"
    )


@pytest.mark.parametrize(
    "provider",
    [
        spec.name
        for spec in ordered_provider_specs()
        if provider_has_browser_route(spec.name)
    ],
)
def test_every_browser_provider_opens_persistent_directory(
    tmp_path, monkeypatch, provider
):
    monkeypatch.setattr(profile, "ByparrManager", NativeProfileDouble)
    config = load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider=provider, doi="test"
    )
    with RuntimeContext(env={}) as runtime:
        manager, context = open_browser_context(config, runtime_context=runtime)
        assert manager is None
        assert profile.profile_path(config).name == f"{provider}-camoufox"
        assert profile.profile_path(config).is_dir()
        assert not context.closed
    assert context.closed


def test_borrowed_stages_and_export_disabled_keep_context_alive(config):
    with RuntimeContext(env={}) as runtime:
        with browser_context(config, runtime_context=runtime) as body:
            page = body.context.new_page()
            page.close()
        with browser_context(
            replace(config, persist_storage_state=False), runtime_context=runtime
        ) as assets:
            assert assets.context is body.context
            assert not assets.context.closed
        assert not body.context.closed
    assert body.context.closed
    assert not (profile.profile_path(config) / "storage-state.json").exists()


def test_directory_override_is_canonical_and_cannot_cross_publishers(config, tmp_path):
    config = replace(config, profile_dir=tmp_path / "custom" / ".." / "shared")
    manager, context = open_browser_context(config)
    manager.close()
    assert context.closed
    with pytest.raises(BrowserRuntimeFailure, match="belongs to pnas") as error:
        open_browser_context(replace(config, provider="aip"))
    assert error.value.kind == "browser_profile_provider_conflict"


def test_default_json_only_migrates_into_uninitialized_profile(config):
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    snapshot = path / "storage-state.json"
    payload = {
        "cookies": [
            {"name": "sid", "value": "old", "domain": ".pnas.org", "path": "/"}
        ],
        "origins": [
            {
                "origin": "https://www.pnas.org",
                "localStorage": [{"name": "token", "value": "old"}],
            }
        ],
    }
    snapshot.write_text(json.dumps(payload))
    manager, context = open_browser_context(config)
    assert context.state == payload
    assert manager.diagnostics["json_imported"]
    manager.close()
    snapshot.write_text(json.dumps({**payload, "origins": []}))
    manager, context = open_browser_context(config)
    assert context.state == {"cookies": [], "origins": []}
    assert not manager.diagnostics["json_imported"]
    manager.close()


def test_explicit_json_digest_imports_each_change_once(config, tmp_path):
    snapshot = tmp_path / "legacy.json"
    snapshot.write_text('{"cookies": [], "origins": []}')
    config = replace(config, storage_state_path=snapshot)
    for expected in (True, False, True):
        if expected and profile.profile_path(config).exists():
            snapshot.write_text('{"cookies": [], "origins": []} ')
        manager, _ = open_browser_context(config)
        assert manager.diagnostics["json_imported"] is expected
        manager.close()
    metadata = json.loads(
        (profile.profile_path(config) / profile.METADATA_FILENAME).read_text()
    )
    assert len(metadata["migrations"]) == 1
    assert "cookies" not in metadata


def test_existing_native_profile_never_imports_default_snapshot(config):
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    (path / "prefs.js").touch()
    (path / "storage-state.json").write_text("not JSON")
    manager, _ = open_browser_context(config)
    assert not manager.diagnostics["json_imported"]
    manager.close()


def test_native_locks_are_preserved_and_reported(config, monkeypatch):
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    native_lock = path / "parent.lock"
    native_lock.touch()
    monkeypatch.setattr(profile, "_native_profile_occupied", lambda path: True)
    with pytest.raises(BrowserRuntimeFailure) as error:
        open_browser_context(config)
    assert error.value.kind == "browser_profile_external_occupancy"
    assert native_lock.exists()
    monkeypatch.setattr(profile, "_native_profile_occupied", lambda path: False)
    manager, _ = open_browser_context(config)
    manager.close()


def test_native_summary_changes_cache_scope_and_unavailable_disables_cache(config):
    with RuntimeContext(
        env={"XDG_DATA_HOME": str(profile.profile_path(config).parents[2])}
    ) as runtime:
        _, context = open_browser_context(config, runtime_context=runtime)
        first = capability_scope_from_runtime_context(runtime)
        context.add_cookies(
            [{"name": "sid", "value": "private", "domain": ".pnas.org", "path": "/"}]
        )
        second = capability_scope_from_runtime_context(runtime)
        assert first != second
        context.storage_state = lambda: None
        assert (
            capability_scope_from_runtime_context(runtime)
            == UNCACHEABLE_CAPABILITY_SCOPE
        )
    assert profile.trusted_profile_digest(profile.profile_path(config), "pnas") is None


def test_idle_native_state_change_invalidates_summary(config):
    manager, _ = open_browser_context(config)
    manager.close()
    path = profile.profile_path(config)
    assert profile.trusted_profile_digest(path, "pnas")
    (path / "cookies.sqlite").write_bytes(b"external update")
    assert profile.trusted_profile_digest(path, "pnas") is None


def test_provider_switch_releases_previous_profile_before_acquiring_next(config):
    with RuntimeContext(env={}) as runtime:
        _, first = open_browser_context(config, runtime_context=runtime)
        _, second = open_browser_context(
            replace(
                config,
                provider="aip",
                user_data_dir=config.user_data_dir.parent / "aip-camoufox",
            ),
            runtime_context=runtime,
        )
        assert first.closed
        assert not second.closed


def test_same_runtime_rejects_other_publisher_on_identical_directory(config):
    with RuntimeContext(env={}) as runtime:
        _, context = open_browser_context(config, runtime_context=runtime)
        with pytest.raises(BrowserRuntimeFailure) as error:
            open_browser_context(
                replace(config, provider="ieee"), runtime_context=runtime
            )
        assert error.value.kind == "browser_profile_provider_conflict"
        assert not context.closed


def test_explicit_json_change_disables_private_read_until_imported(config, tmp_path):
    snapshot = tmp_path / "configured.json"
    snapshot.write_text('{"cookies": [], "origins": []}')
    config = replace(
        config,
        provider="wiley",
        user_data_dir=profile.profile_path(config).parent / "wiley-camoufox",
        storage_state_path=snapshot,
    )
    manager, _ = open_browser_context(config)
    manager.close()
    assert profile.trusted_profile_digest(
        profile.profile_path(config), "wiley", explicit_state_path=snapshot
    )
    snapshot.write_text('{"cookies": [], "origins": []} ')
    assert (
        profile.trusted_profile_digest(
            profile.profile_path(config), "wiley", explicit_state_path=snapshot
        )
        is None
    )
    manager, _ = open_browser_context(config)
    assert manager.diagnostics["json_imported"]
    manager.close()
    assert profile.trusted_profile_digest(
        profile.profile_path(config), "wiley", explicit_state_path=snapshot
    )


def test_failed_initial_migration_can_be_retried_without_overwriting_native_profile(
    config,
):
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    snapshot = path / "storage-state.json"
    snapshot.write_text("invalid JSON")
    with pytest.raises(BrowserRuntimeFailure) as error:
        open_browser_context(config)
    assert error.value.kind == "browser_profile_json_import_failed"
    assert error.value.details["stage"] == "json_import"
    snapshot.write_text('{"cookies": [], "origins": []}')
    manager, _ = open_browser_context(config)
    assert manager.diagnostics["json_imported"]
    manager.close()


def test_switching_publishers_discards_cached_pages_from_previous_context(config):
    from paper_fetch.providers.browser_workflow.fetchers.context import (
        _SharedBrowserPageSession,
    )

    with RuntimeContext(env={}) as runtime:
        _, first = open_browser_context(config, runtime_context=runtime)
        shared = _SharedBrowserPageSession()
        page = first.new_page()
        shared.bind(manager=None, context=first, page=page)
        runtime.set_session_cache("old-figure-page", shared, copy_value=False)
        open_browser_context(
            replace(
                config,
                provider="aip",
                user_data_dir=config.user_data_dir.parent / "aip-camoufox",
            ),
            runtime_context=runtime,
        )
        assert first.closed
        assert page.closed
        assert shared.context is None
        assert runtime.get_session_cache("old-figure-page") is None


def test_reused_context_does_not_claim_a_second_json_import(config):
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    (path / "storage-state.json").write_text('{"cookies": [], "origins": []}')
    with RuntimeContext(env={}) as runtime:
        _, context = open_browser_context(config, runtime_context=runtime)
        assert runtime.browser_profile_diagnostics(context)["json_imported"]
        open_browser_context(config, runtime_context=runtime)
        diagnostics = runtime.browser_profile_diagnostics(context)
        assert diagnostics["context_reused"]
        assert not diagnostics["native_profile_loaded"]
        assert not diagnostics["json_imported"]


def test_cancelled_after_acquiring_directory_never_launches_browser(
    config, monkeypatch
):
    original = profile.PublisherProfileManager._acquire

    def acquire_then_cancel(manager):
        original(manager)
        manager.runtime_context.fence_commits()

    monkeypatch.setattr(
        profile.PublisherProfileManager, "_acquire", acquire_then_cancel
    )
    with RuntimeContext(env={}) as runtime:
        with pytest.raises(Exception, match="cancelled"):
            open_browser_context(config, runtime_context=runtime)
    assert not NativeProfileDouble.instances


def test_native_profile_does_not_require_optional_json_snapshot_to_exist(
    config, tmp_path
):
    snapshot = tmp_path / "missing-snapshot.json"
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    (path / "prefs.js").touch()
    runtime_config = load_runtime_config(
        {
            "PAPER_FETCH_BROWSER_PROFILE_DIR": str(path),
            "PAPER_FETCH_WILEY_STORAGE_STATE_JSON": str(snapshot),
        },
        provider="wiley",
        doi="test",
        require_storage_state=True,
    )
    manager, _ = open_browser_context(runtime_config)
    manager.close()
    assert profile.trusted_profile_digest(path, "wiley", explicit_state_path=snapshot)
