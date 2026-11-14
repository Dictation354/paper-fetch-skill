from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_fetch import auth
from paper_fetch.config import XDG_DATA_HOME_ENV_VAR
from paper_fetch.provider_catalog import browser_preflight_provider_names
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
        self.profile_dir: str | None = None
        self.closed = False
        self.route_handler = None
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

    def route(self, pattern: str, handler) -> None:
        assert pattern == "**/*"
        self.route_handler = handler

    def storage_state(self, *, path: str | None = None):
        if path is None:
            return self.state_payload
        self.profile_dir = path
        Path(path).write_text(json.dumps(self.state_payload), encoding="utf-8")

    def close(self) -> None:
        self.closed = True


class _FakeAuthBrowserManager:
    instances: list[_FakeAuthBrowserManager] = []

    def __init__(self) -> None:
        self.context = _FakeAuthContext()
        self.binary_path: str | None = None
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
            config,
            *,
            native_profile: Path,
            runtime_context=None,
        ) -> None:
            super().__init__()
            self.binary_path = config.binary_path
            self.profile_dir = native_profile
            self.user_data_dir = str(native_profile)
            self.headless = config.headless

    from paper_fetch.providers.browser_runtime import profile

    monkeypatch.setattr(profile, "ByparrManager", FakeManager)
    return FakeManager


def _patch_auth_runtime(
    monkeypatch, tmp_path, env: dict[str, str] | None = None
) -> None:
    runtime_env = {XDG_DATA_HOME_ENV_VAR: str(tmp_path / "xdg")}
    if env is not None:
        runtime_env.update(env)
    monkeypatch.setattr(auth, "build_runtime_env", lambda: dict(runtime_env))
    monkeypatch.setattr(auth, "ensure_runtime_ready", lambda _runtime: None)


def test_browser_auth_provider_names_uses_runtime_catalog() -> None:
    names = auth.browser_auth_provider_names()

    assert "wiley" in names
    assert "ams" in names
    assert "arxiv" not in names


def test_browser_entrypoint_providers_have_builtin_targets() -> None:
    declared_providers = set(auth.browser_auth_provider_names()) | set(
        browser_preflight_provider_names()
    )

    assert declared_providers <= auth.AUTH_TARGETS.keys()


def test_provider_label_uses_catalog_display_name() -> None:
    assert auth._provider_label("iop") == "IOP Publishing"
    assert auth._provider_label("aip") == "AIP Publishing"
    assert auth._provider_label("mdpi") == "MDPI"
    assert auth._provider_label("annualreviews") == "Annual Reviews"


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


def test_auth_page_left_on_sso_host_does_not_modify_old_state(
    monkeypatch, tmp_path
) -> None:
    fake_manager = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)
    state_path = (
        tmp_path
        / "xdg"
        / "paper-fetch"
        / "publisher-browser-profiles"
        / "wiley-camoufox"
        / "storage-state.json"
    )
    state_path.parent.mkdir(parents=True)
    old_bytes = b'{"cookies":[{"name":"old"}],"origins":[]}\n'
    state_path.write_bytes(old_bytes)

    def leave_on_sso(_prompt):
        fake_manager.instances[0].context.page.url = "https://login.example.test/sso"

    with pytest.raises(ProviderFailure) as raised:
        auth.authenticate_provider_profile(
            provider="wiley",
            confirm=leave_on_sso,
        )

    assert raised.value.code == "auth_final_url_invalid"
    assert state_path.read_bytes() == old_bytes


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


def test_auth_context_does_not_install_context_wide_network_route(
    monkeypatch, tmp_path
) -> None:
    fake_manager = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)

    auth.authenticate_provider_profile(
        provider="wiley",
        confirm=lambda _prompt: None,
    )

    context = fake_manager.instances[0].context
    assert context.route_handler is None


@pytest.mark.parametrize("value", ["0", " false "])
def test_auth_replay_uses_configured_fetch_window_mode(monkeypatch, tmp_path, value):
    from paper_fetch.config import BROWSER_HEADLESS_ENV_VAR

    fake = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path, {BROWSER_HEADLESS_ENV_VAR: value})
    result = auth.authenticate_provider_profile(
        provider="wiley", confirm=lambda prompt: None
    )
    assert result.verified
    assert [manager.headless for manager in fake.instances] == [False, False]


@pytest.mark.parametrize("provider", ["pnas", "elsevier", "wiley", "ams"])
def test_auth_replays_same_native_profile_without_json(provider, monkeypatch, tmp_path):
    managers = _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)
    result = auth.authenticate_provider_profile(
        provider=provider, confirm=lambda _: None
    )
    assert result.verified
    assert result.profile_dir.name == provider
    assert len(managers.instances) == 2
    assert (
        managers.instances[0].profile_dir
        == managers.instances[1].profile_dir
        == result.profile_dir
    )
    assert all(manager.closed for manager in managers.instances)
    assert not (result.profile_dir / "storage-state.json").exists()


@pytest.mark.parametrize(
    "blocked_attempt,stage,headless",
    [(1, "auth_manual_check", False), (2, "auth_profile_reopen", True)],
)
def test_auth_failures_preserve_raw_challenge_and_actual_window_mode(
    monkeypatch, tmp_path, blocked_attempt, stage, headless
):
    from types import SimpleNamespace

    _install_fake_browser_manager(monkeypatch)
    _patch_auth_runtime(monkeypatch, tmp_path)
    attempts = []

    def detect(*args):
        attempts.append(args)
        return (
            SimpleNamespace(reason="cloudflare_challenge", message="Challenge page")
            if len(attempts) == blocked_attempt
            else None
        )

    monkeypatch.setattr(auth, "detect_html_block", detect)
    with pytest.raises(ProviderFailure) as caught:
        auth.authenticate_provider_profile(
            provider="wiley", confirm=lambda prompt: None
        )
    failure = caught.value
    assert failure.code == "auth_final_url_invalid"
    assert failure.diagnostics.provider == "wiley"
    assert failure.diagnostics.stage == stage
    assert failure.diagnostics.http_status is None
    assert failure.diagnostics.details["headless"] is headless
    assert failure.diagnostics.details["challenge_reason"] == "cloudflare_challenge"
