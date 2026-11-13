from __future__ import annotations
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
        assert profile.profile_path(config).name == provider
        assert profile.profile_path(config).is_dir()
        assert not context.closed
    assert context.closed


def test_borrowed_stages_and_export_disabled_keep_context_alive(config):
    with RuntimeContext(env={}) as runtime:
        with browser_context(config, runtime_context=runtime) as body:
            page = body.context.new_page()
            page.close()
        with browser_context(config, runtime_context=runtime) as assets:
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
    )
    manager, _ = open_browser_context(runtime_config)
    manager.close()
    assert profile.trusted_profile_digest(path, "wiley")


def test_native_profiles_ignore_old_json_files(config):
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    old = path / "storage-state.json"
    old.write_text("invalid old state")
    manager, context = open_browser_context(config)
    assert context.state == {"cookies": [], "origins": []}
    assert "json_imported" not in manager.diagnostics
    manager.close()
    assert old.read_text() == "invalid old state"
