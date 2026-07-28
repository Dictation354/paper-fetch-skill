from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_fetch import auth
from paper_fetch.config import XDG_DATA_HOME_ENV_VAR
from paper_fetch.providers.base import ProviderFailure


class _FakeAuthPage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.goto_calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    def goto(self, url: str, **kwargs) -> None:
        self.url = url
        self.goto_calls.append((url, dict(kwargs)))

    def title(self) -> str:
        return "Publisher Article"

    def close(self) -> None:
        self.closed = True


class _FakeAuthContext:
    def __init__(self) -> None:
        self.page = _FakeAuthPage()
        self.storage_state_path: str | None = None
        self.closed = False
        self.state_payload = {
            "cookies": [
                {
                    "name": "cf_clearance",
                    "value": "wiley",
                    "domain": ".wiley.com",
                    "path": "/",
                },
                {"name": "sid", "value": "ams", "domain": ".ametsoc.org", "path": "/"},
                {
                    "name": "other",
                    "value": "no",
                    "domain": ".example.test",
                    "path": "/",
                },
            ],
            "origins": [
                {
                    "origin": "https://onlinelibrary.wiley.com",
                    "localStorage": [{"name": "ok", "value": "1"}],
                },
                {
                    "origin": "https://journals.ametsoc.org",
                    "localStorage": [{"name": "ams", "value": "1"}],
                },
                {
                    "origin": "https://example.test",
                    "localStorage": [{"name": "no", "value": "1"}],
                },
            ],
        }

    def new_page(self) -> _FakeAuthPage:
        return self.page

    def storage_state(self, *, path: str | None = None):
        if path is None:
            return self.state_payload
        self.storage_state_path = path
        Path(path).write_text(json.dumps(self.state_payload), encoding="utf-8")

    def close(self) -> None:
        self.closed = True


class _FakeAuthBrowserManager:
    instances: list[_FakeAuthBrowserManager] = []

    def __init__(self) -> None:
        self.context = _FakeAuthContext()
        self.binary_path: str | None = None
        self.cdp_endpoint: str | None = None
        self.profile_dir: Path | None = None
        self.user_data_dir: Path | None = None
        self.new_context_kwargs: dict[str, object] = {}
        self.closed = False
        self.instances.append(self)

    def new_context(self, **kwargs):
        self.new_context_kwargs = dict(kwargs)
        return self.context

    def close(self) -> None:
        self.closed = True


def _install_fake_browser_manager(monkeypatch) -> type[_FakeAuthBrowserManager]:
    _FakeAuthBrowserManager.instances = []

    class FakeManager(_FakeAuthBrowserManager):
        def __init__(
            self,
            *,
            binary_path: str | None = None,
            cdp_endpoint: str | None = None,
            profile_dir: Path | None = None,
            user_data_dir: Path | None = None,
            headless: bool = True,
        ) -> None:
            super().__init__()
            self.binary_path = binary_path
            self.cdp_endpoint = cdp_endpoint
            self.profile_dir = profile_dir
            self.user_data_dir = user_data_dir
            self.headless = headless

    monkeypatch.setattr(auth, "CamoufoxPersistentContextManager", FakeManager)
    return FakeManager


def _patch_auth_runtime(
    monkeypatch, tmp_path, env: dict[str, str] | None = None
) -> None:
    runtime_env = {
        "PAPER_FETCH_BROWSER_BACKEND": "camoufox",
        XDG_DATA_HOME_ENV_VAR: str(tmp_path / "xdg"),
    }
    if env is not None:
        runtime_env.update(env)
    monkeypatch.setattr(auth, "build_runtime_env", lambda: dict(runtime_env))
    monkeypatch.setattr(auth, "ensure_runtime_ready", lambda _runtime: None)


def test_upsert_env_file_updates_existing_values(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# existing\n"
        'export PAPER_FETCH_AMS_STORAGE_STATE_JSON="/old/state.json"\n'
        "KEEP=value\n",
        encoding="utf-8",
    )

    auth.upsert_env_file(
        env_file,
        {
            "PAPER_FETCH_AMS_STORAGE_STATE_JSON": "/tmp/with space/state.json",
            "NEW_KEY": 'quoted"value',
        },
    )

    assert env_file.read_text(encoding="utf-8") == (
        "# existing\n"
        'PAPER_FETCH_AMS_STORAGE_STATE_JSON="/tmp/with space/state.json"\n'
        "KEEP=value\n"
        'NEW_KEY="quoted\\"value"\n'
    )


def test_authenticate_provider_profile_ams_saves_filtered_browser_state(
    monkeypatch, tmp_path
) -> None:
    fake_manager = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)

    result = auth.authenticate_provider_profile(
        provider="ams",
        confirm=lambda _prompt: None,
    )

    profile_dir = (
        tmp_path / "xdg" / "paper-fetch" / "publisher-browser-profiles" / "ams-camoufox"
    )
    storage_state_path = profile_dir / "storage-state.json"
    assert result.provider == "ams"
    assert result.profile_dir == profile_dir
    assert result.storage_state_path == storage_state_path
    assert result.final_url == auth.AUTH_TARGETS["ams"].url
    manager = fake_manager.instances[0]
    assert manager.user_data_dir == str(profile_dir)
    assert manager.context.page.goto_calls == [
        (
            auth.AUTH_TARGETS["ams"].url,
            {"wait_until": "domcontentloaded", "timeout": 120000},
        )
    ]
    assert json.loads(storage_state_path.read_text(encoding="utf-8")) == {
        "cookies": [
            {
                "name": "sid",
                "value": "ams",
                "domain": ".ametsoc.org",
                "path": "/",
            }
        ],
        "origins": [
            {
                "origin": "https://journals.ametsoc.org",
                "localStorage": [{"name": "ams", "value": "1"}],
            }
        ],
    }


def test_browser_auth_provider_names_uses_runtime_catalog() -> None:
    names = auth.browser_auth_provider_names()

    assert "wiley" in names
    assert "ams" in names
    assert "arxiv" not in names


def test_provider_label_uses_catalog_display_name() -> None:
    assert auth._provider_label("iop") == "IOP Publishing"
    assert auth._provider_label("aip") == "AIP Publishing"
    assert auth._provider_label("mdpi") == "MDPI"
    assert auth._provider_label("annualreviews") == "Annual Reviews"


def test_authenticate_provider_profile_uses_sample_headed_profile_and_storage(
    monkeypatch, tmp_path
) -> None:
    fake_manager = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)
    prompts: list[str] = []

    result = auth.authenticate_provider_profile(
        provider="wiley",
        confirm=lambda prompt: prompts.append(prompt),
    )

    profile_dir = (
        tmp_path
        / "xdg"
        / "paper-fetch"
        / "publisher-browser-profiles"
        / "wiley-camoufox"
    )
    storage_state_path = profile_dir / "storage-state.json"
    assert result.provider == "wiley"
    assert result.profile_dir == profile_dir
    assert result.storage_state_path == storage_state_path
    assert result.env_written is False
    assert result.env_file_path is None
    assert result.final_url == auth.AUTH_TARGETS["wiley"].url
    manager = fake_manager.instances[0]
    assert manager.cdp_endpoint is None
    assert manager.user_data_dir == str(profile_dir)
    assert manager.closed is True
    assert "storage_state" not in manager.new_context_kwargs
    assert manager.context.page.goto_calls == [
        (
            auth.AUTH_TARGETS["wiley"].url,
            {"wait_until": "domcontentloaded", "timeout": 120000},
        )
    ]
    assert prompts and str(profile_dir) in prompts[0]
    assert str(storage_state_path) in prompts[0]
    assert json.loads(storage_state_path.read_text(encoding="utf-8")) == {
        "cookies": [
            {
                "name": "cf_clearance",
                "value": "wiley",
                "domain": ".wiley.com",
                "path": "/",
            }
        ],
        "origins": [
            {
                "origin": "https://onlinelibrary.wiley.com",
                "localStorage": [{"name": "ok", "value": "1"}],
            }
        ],
    }


def test_authenticate_provider_profile_url_override(monkeypatch, tmp_path) -> None:
    fake_manager = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)
    target_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/example"

    result = auth.authenticate_provider_profile(
        provider="wiley",
        target_url=target_url,
        timeout_ms=45000,
        confirm=lambda _prompt: None,
    )

    manager = fake_manager.instances[0]
    assert manager.context.page.goto_calls == [
        (target_url, {"wait_until": "domcontentloaded", "timeout": 45000})
    ]
    assert result.final_url == target_url


def test_authenticate_provider_profile_rejects_user_agent_for_camoufox(
    monkeypatch, tmp_path
) -> None:
    _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)

    with pytest.raises(ProviderFailure, match="cannot be used with Camoufox"):
        auth.authenticate_provider_profile(
            provider="wiley",
            browser_user_agent="Mozilla/5.0 auth-test",
            confirm=lambda _prompt: None,
        )


def test_authenticate_provider_profile_rejects_non_browser_provider() -> None:
    try:
        auth.authenticate_provider_profile(provider="arxiv", confirm=None)
    except ProviderFailure as exc:
        assert exc.code == "error"
        assert "Unsupported auth provider" in str(exc)
        assert "wiley" in str(exc)
    else:
        raise AssertionError("expected non-browser provider auth to fail")


def test_authenticate_provider_profile_allows_url_for_catalog_provider_without_sample(
    monkeypatch, tmp_path
) -> None:
    fake_manager = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(auth, "browser_auth_provider_names", lambda: ("newbrowser",))
    target_url = "https://example.test/article"

    result = auth.authenticate_provider_profile(
        provider="newbrowser",
        target_url=target_url,
        confirm=lambda _prompt: None,
    )

    assert result.provider == "newbrowser"
    assert result.final_url == target_url
    assert fake_manager.instances[0].context.page.goto_calls[0][0] == target_url
