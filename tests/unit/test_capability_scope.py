from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from paper_fetch.capability_scope import (
    UNCACHEABLE_CAPABILITY_SCOPE,
    BrowserStateCapabilityUse,
    CapabilityScopeBuilder,
    capability_scope_from_runtime_context,
    capability_scopes_for_query,
)
from paper_fetch.delivery.fetch_cache import (
    PUBLIC_CREDENTIAL_SCOPE,
)
from paper_fetch.providers.browser_runtime.profile import trusted_profile_digest
from paper_fetch.runtime import RuntimeContext


def _write_state(
    path: Path, *, value: str = "session", provider: str = "wiley"
) -> Path:
    from paper_fetch.providers.browser_runtime.profile import (
        METADATA_FILENAME,
        _native_stamp,
    )

    path.mkdir(parents=True, exist_ok=True)
    (path / "cookies.sqlite").write_text(value)
    (path / METADATA_FILENAME).write_text(
        json.dumps(
            {
                "provider": provider,
                "state_sha256": hashlib.sha256(value.encode()).hexdigest(),
                "native_stamp": _native_stamp(path),
            }
        )
    )
    return path


@pytest.mark.parametrize(
    "profile_env",
    [None, "PAPER_FETCH_BROWSER_PROFILE_DIR", "PAPER_FETCH_BROWSER_USER_DATA_DIR"],
)
def test_capability_scope_binds_final_browser_state_path_and_digest(
    tmp_path, profile_env
):
    from paper_fetch.providers.browser_runtime import load_runtime_config
    from paper_fetch.providers.browser_runtime.profile import profile_path

    env = {"XDG_DATA_HOME": str(tmp_path)}
    if profile_env:
        env[profile_env] = str(tmp_path / "explicit")
    native = profile_path(load_runtime_config(env, provider="wiley", doi="test"))
    _write_state(native)
    scopes = capability_scopes_for_query(env, "10.1002/unit-test")
    use = BrowserStateCapabilityUse.from_path(
        provider="wiley", backend="byparr", profile_dir=native
    )
    builder = CapabilityScopeBuilder(env).add_browser_state_use(use)
    assert scopes[0] == builder.build()
    assert scopes[-1] == PUBLIC_CREDENTIAL_SCOPE
    assert builder.facts()["browser_states"][0]["profile_dir"] == str(native.resolve())


def test_env_only_scope_uses_current_capability_facts() -> None:
    env = {"ELSEVIER_API_KEY": "unit-secret", "CROSSREF_MAILTO": "x@example.test"}

    assert CapabilityScopeBuilder(env).build() == CapabilityScopeBuilder(env).build()
    assert CapabilityScopeBuilder(env).build().startswith("credential:")


def test_runtime_scope_only_records_browser_state_after_actual_use(
    tmp_path: Path,
) -> None:
    state = _write_state(tmp_path / "state.json")
    with RuntimeContext(env={}) as context:
        assert capability_scope_from_runtime_context(context) == PUBLIC_CREDENTIAL_SCOPE
        context.record_browser_state_capability_use(
            provider="wiley",
            backend="byparr",
            profile_dir=state,
            content_sha256=trusted_profile_digest(state, "wiley"),
        )
        scope = capability_scope_from_runtime_context(context)

    assert scope == (
        CapabilityScopeBuilder({})
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="wiley",
                backend="byparr",
                profile_dir=state,
            )
        )
        .build()
    )


def test_actually_used_state_never_degrades_to_public_if_file_disappears(
    tmp_path: Path,
) -> None:
    state = _write_state(tmp_path / "state.json")
    with RuntimeContext(env={}) as context:
        context.record_browser_state_capability_use(
            provider="wiley",
            backend="byparr",
            profile_dir=state,
            content_sha256=trusted_profile_digest(state, "wiley"),
        )
        import shutil

        shutil.rmtree(state)
        scope = capability_scope_from_runtime_context(context)

    assert scope == UNCACHEABLE_CAPABILITY_SCOPE
    assert scope != PUBLIC_CREDENTIAL_SCOPE


def test_missing_configured_state_does_not_pollute_public_scope(tmp_path: Path) -> None:
    env = {"PAPER_FETCH_BROWSER_PROFILE_DIR": str(tmp_path / "empty-profile")}

    assert capability_scopes_for_query(env, "10.1002/unit-test") == (
        PUBLIC_CREDENTIAL_SCOPE,
    )


def test_scope_builder_ignores_incomplete_unused_and_missing_state_facts(
    tmp_path: Path,
) -> None:
    builder = CapabilityScopeBuilder(
        {"PAPER_FETCH_WILEY_STORAGE_STATE_JSON": str(tmp_path / "missing.json")}
    )
    unused = BrowserStateCapabilityUse.from_path(
        provider="wiley",
        backend="byparr",
        profile_dir=tmp_path / "unused.json",
        used=False,
    )

    assert builder.add_browser_state_use({}) is builder
    assert builder.add_browser_state_use(unused) is builder
    assert builder.build() == PUBLIC_CREDENTIAL_SCOPE


def test_scope_builder_deduplicates_used_state_and_handles_static_context(
    tmp_path: Path,
) -> None:
    state = _write_state(tmp_path / "state.json")
    use = BrowserStateCapabilityUse.from_path(
        provider="wiley",
        backend="byparr",
        profile_dir=state,
    )
    builder = CapabilityScopeBuilder({})
    builder.add_browser_state_uses((use, use))

    assert len(builder.facts()["browser_states"]) == 1

    class StaticContext:
        env: dict[str, str] = {}
        browser_state_capability_uses: list[dict[str, object]] = []

    assert capability_scope_from_runtime_context(StaticContext()) == (
        PUBLIC_CREDENTIAL_SCOPE
    )


def test_query_scope_does_not_fall_back_to_another_provider_private_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runtime"
    from paper_fetch.providers.browser_runtime.profile import (
        METADATA_FILENAME,
        _native_stamp,
    )

    for provider in ("wiley", "science"):
        native = root / "paper-fetch" / "publisher-browser-profiles" / provider
        native.mkdir(parents=True)
        (native / METADATA_FILENAME).write_text(
            json.dumps(
                {
                    "provider": provider,
                    "state_sha256": provider * 8,
                    "native_stamp": _native_stamp(native),
                }
            )
        )
    env = {"XDG_DATA_HOME": str(root)}

    wiley_scopes = capability_scopes_for_query(env, "10.1002/unit-test")

    assert len(wiley_scopes) == 2
    assert wiley_scopes[-1] == PUBLIC_CREDENTIAL_SCOPE
    science_scope = (
        CapabilityScopeBuilder(env)
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="science",
                backend="byparr",
                profile_dir=(
                    root / "paper-fetch" / "publisher-browser-profiles" / "science"
                ),
            )
        )
        .build()
    )
    assert science_scope not in wiley_scopes


def test_state_content_and_provider_are_scope_bound(tmp_path: Path) -> None:
    state = _write_state(tmp_path / "state.json", value="first")
    wiley = (
        CapabilityScopeBuilder({})
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="wiley", backend="byparr", profile_dir=state
            )
        )
        .build()
    )
    _write_state(state, value="second")
    changed = (
        CapabilityScopeBuilder({})
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="wiley", backend="byparr", profile_dir=state
            )
        )
        .build()
    )
    other_provider = (
        CapabilityScopeBuilder({})
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="science", backend="byparr", profile_dir=state
            )
        )
        .build()
    )

    assert len({wiley, changed, other_provider}) == 3
