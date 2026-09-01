from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from paper_fetch.capability_scope import (
    BrowserStateCapabilityUse,
    CapabilityScopeBuilder,
    capability_scope_from_runtime_context,
    capability_scopes_for_query,
)
from paper_fetch.mcp.fetch_cache import (
    PUBLIC_CREDENTIAL_SCOPE,
    credential_scope_from_env,
    envelope_capability_scope,
    fetch_envelope_cache_path,
)
from paper_fetch.mcp.fetch_tool import (
    _fetch_paper_envelope,
    _save_markdown_result_for_fetch_request,
)
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.runtime import RuntimeContext
from tests.unit._mcp_support import mcp_test_deps, sample_envelope


def _write_state(path: Path, *, value: str = "session") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "session",
                        "value": value,
                        "domain": ".onlinelibrary.wiley.com",
                        "path": "/",
                    }
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("env_factory", "expected_path_factory"),
    [
        (
            lambda root, state: {"XDG_DATA_HOME": str(root)},
            lambda root, state: (
                root
                / "paper-fetch"
                / "publisher-browser-profiles"
                / "wiley-camoufox"
                / "storage-state.json"
            ),
        ),
        (
            lambda root, state: {"PAPER_FETCH_BROWSER_PROFILE_DIR": str(root)},
            lambda root, state: root / "storage-state.json",
        ),
        (
            lambda root, state: {"PAPER_FETCH_BROWSER_USER_DATA_DIR": str(root)},
            lambda root, state: root / "storage-state.json",
        ),
        (
            lambda root, state: {"PAPER_FETCH_WILEY_STORAGE_STATE_JSON": str(state)},
            lambda root, state: state,
        ),
    ],
    ids=("default", "profile_dir", "user_data_dir", "explicit"),
)
def test_capability_scope_binds_final_browser_state_path_and_digest(
    tmp_path: Path,
    env_factory,
    expected_path_factory,
) -> None:
    state_argument = tmp_path / "explicit.json"
    env = env_factory(tmp_path / "runtime", state_argument)
    expected_path = expected_path_factory(tmp_path / "runtime", state_argument)
    _write_state(expected_path)

    scopes = capability_scopes_for_query(env, "10.1002/unit-test")
    use = BrowserStateCapabilityUse.from_path(
        provider="wiley",
        backend="camoufox",
        storage_state_path=expected_path,
    )
    builder = CapabilityScopeBuilder(env).add_browser_state_use(use)

    assert scopes[0] == builder.build()
    assert scopes[-1] == PUBLIC_CREDENTIAL_SCOPE
    facts = builder.facts()["browser_states"]
    assert facts == [
        {
            "provider": "wiley",
            "backend": "camoufox",
            "storage_state_path": str(expected_path.resolve()),
            "content_sha256": hashlib.sha256(expected_path.read_bytes()).hexdigest(),
            "used": True,
        }
    ]


def test_env_only_scope_uses_current_capability_facts() -> None:
    env = {"ELSEVIER_API_KEY": "unit-secret", "CROSSREF_MAILTO": "x@example.test"}

    assert credential_scope_from_env(env) == CapabilityScopeBuilder(env).build()
    assert credential_scope_from_env(env).startswith("credential:")


def test_runtime_scope_only_records_browser_state_after_actual_use(
    tmp_path: Path,
) -> None:
    state = _write_state(tmp_path / "state.json")
    with RuntimeContext(env={}) as context:
        assert capability_scope_from_runtime_context(context) == PUBLIC_CREDENTIAL_SCOPE
        context.record_browser_state_capability_use(
            provider="wiley",
            backend="camoufox",
            storage_state_path=state,
        )
        scope = capability_scope_from_runtime_context(context)

    assert scope == (
        CapabilityScopeBuilder({})
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="wiley",
                backend="camoufox",
                storage_state_path=state,
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
            backend="camoufox",
            storage_state_path=state,
        )
        state.unlink()
        scope = capability_scope_from_runtime_context(context)

    assert scope.startswith("credential:")
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
        backend="camoufox",
        storage_state_path=tmp_path / "unused.json",
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
        backend="camoufox",
        storage_state_path=state,
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
    _write_state(
        root
        / "paper-fetch"
        / "publisher-browser-profiles"
        / "wiley-camoufox"
        / "storage-state.json"
    )
    _write_state(
        root
        / "paper-fetch"
        / "publisher-browser-profiles"
        / "science-camoufox"
        / "storage-state.json"
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
                backend="camoufox",
                storage_state_path=(
                    root
                    / "paper-fetch"
                    / "publisher-browser-profiles"
                    / "science-camoufox"
                    / "storage-state.json"
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
                provider="wiley", backend="camoufox", storage_state_path=state
            )
        )
        .build()
    )
    state.write_text(state.read_text().replace("first", "second"), encoding="utf-8")
    changed = (
        CapabilityScopeBuilder({})
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="wiley", backend="camoufox", storage_state_path=state
            )
        )
        .build()
    )
    other_provider = (
        CapabilityScopeBuilder({})
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="science", backend="camoufox", storage_state_path=state
            )
        )
        .build()
    )

    assert len({wiley, changed, other_provider}) == 3


def test_fetch_writer_uses_final_digest_of_actually_loaded_state(
    tmp_path: Path,
) -> None:
    doi = "10.1002/final-state-scope"
    profile = tmp_path / "profile"
    state = _write_state(profile / "storage-state.json", value="before-fetch")
    env = {"PAPER_FETCH_BROWSER_PROFILE_DIR": str(profile)}
    before_scope = (
        CapabilityScopeBuilder(env)
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="wiley",
                backend="camoufox",
                storage_state_path=state,
            )
        )
        .build()
    )

    def fake_fetch(query, *, modes, strategy, render, context):
        del strategy, render
        context.record_browser_state_capability_use(
            provider="wiley",
            backend="camoufox",
            storage_state_path=state,
        )
        _write_state(state, value="after-fetch")
        return sample_envelope(modes=set(modes), doi=query)

    request = FetchPaperRequest(query=doi, modes=["markdown"])
    with RuntimeContext(env=env, download_dir=tmp_path) as context:
        _fetch_paper_envelope(
            request,
            env=env,
            download_dir=tmp_path,
            transport=None,
            include_article_for_assets=False,
            context=context,
            deps=mcp_test_deps(service_fetch_paper=fake_fetch),
        )

    sidecar = json.loads(
        fetch_envelope_cache_path(tmp_path, doi).read_text(encoding="utf-8")
    )
    final_scope = (
        CapabilityScopeBuilder(env)
        .add_browser_state_use(
            BrowserStateCapabilityUse.from_path(
                provider="wiley",
                backend="camoufox",
                storage_state_path=state,
            )
        )
        .build()
    )
    assert sidecar["credential_scope"] == final_scope
    assert final_scope != before_scope


def test_no_download_markdown_inherits_actual_browser_state_scope(
    tmp_path: Path,
) -> None:
    doi = "10.1002/no-download-private-markdown"
    state = _write_state(tmp_path / "profile" / "storage-state.json")
    env = {"PAPER_FETCH_BROWSER_PROFILE_DIR": str(state.parent)}

    def fake_fetch(query, *, modes, strategy, render, context):
        del strategy, render
        context.record_browser_state_capability_use(
            provider="wiley",
            backend="camoufox",
            storage_state_path=state,
        )
        return sample_envelope(modes=set(modes), doi=query)

    markdown_dir = tmp_path / "markdown"
    request = FetchPaperRequest(
        query=doi,
        modes=["markdown"],
        no_download=True,
        save_markdown=True,
        markdown_output_dir=str(markdown_dir),
    )
    with RuntimeContext(env=env, artifact_mode="none") as context:
        envelope = _fetch_paper_envelope(
            request,
            env=env,
            download_dir=None,
            transport=None,
            include_article_for_assets=False,
            context=context,
            deps=mcp_test_deps(service_fetch_paper=fake_fetch),
        )
        saved = _save_markdown_result_for_fetch_request(
            envelope,
            request,
            env=env,
            download_dir=None,
            context=context,
        )
        expected_scope = capability_scope_from_runtime_context(context)

    assert saved is not None
    assert saved.cache_entry is not None
    assert expected_scope != PUBLIC_CREDENTIAL_SCOPE
    assert envelope_capability_scope(envelope) == expected_scope
    assert saved.cache_entry["credential_scope"] == expected_scope
