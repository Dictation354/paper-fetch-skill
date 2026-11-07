"""Selection/state contracts and the private solver boundary, without browsers."""

import asyncio
import logging
import sys
from types import SimpleNamespace, ModuleType

import pytest

from paper_fetch.provider_catalog import (
    ordered_provider_specs,
    provider_has_browser_route,
)
from paper_fetch.providers.browser_runtime.api import load_runtime_config
from paper_fetch.providers.browser_runtime.byparr_adapter import (
    ManagedOperation,
    supported_challenge,
)

PROVIDERS = [
    spec.name
    for spec in ordered_provider_specs()
    if provider_has_browser_route(spec.name)
]


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("alias", ["auto", "camoufox", "byparr"])
@pytest.mark.parametrize(
    "system,machine",
    [
        ("linux", "x86_64"),
        ("win32", "AMD64"),
        ("darwin", "arm64"),
        ("darwin", "x86_64"),
        ("linux", "aarch64"),
    ],
)
def test_all_providers_share_backend_but_keep_state_binding(
    monkeypatch, tmp_path, provider, alias, system, machine
):
    from paper_fetch.providers.browser_runtime import selection

    monkeypatch.setattr(selection, "sys", SimpleNamespace(platform=system))
    monkeypatch.setattr(selection, "platform", SimpleNamespace(machine=lambda: machine))
    config = load_runtime_config(
        {
            "XDG_DATA_HOME": str(tmp_path),
            f"PAPER_FETCH_{provider.upper()}_BROWSER_BACKEND": alias,
        },
        provider=provider,
        doi="test",
    )
    legacy_json = (
        provider in {"pnas", "elsevier"}
        and system in {"linux", "win32"}
        and machine in {"x86_64", "AMD64"}
        and alias != "camoufox"
    )
    assert config.backend == "byparr"
    assert config.state_mode == ("json" if legacy_json else "native")
    assert (
        config.user_data_dir.name
        == f"{provider}-{'byparr' if legacy_json else 'camoufox'}"
    )


@pytest.mark.parametrize("provider", PROVIDERS)
def test_native_overrides_stay_bound_without_migration(tmp_path, provider):
    config = load_runtime_config(
        {
            f"PAPER_FETCH_{provider.upper()}_BROWSER_BACKEND": "camoufox",
            "PAPER_FETCH_BROWSER_PROFILE_DIR": str(tmp_path / "profile"),
            "PAPER_FETCH_BROWSER_USER_DATA_DIR": str(tmp_path / "data"),
        },
        provider=provider,
        doi="test",
    )
    assert config.state_mode == "native"
    assert config.profile_dir == tmp_path / "profile"
    assert config.user_data_dir == tmp_path / "data"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "title,html,headers,supported",
    [
        ("Article", "normal article", {}, False),
        ("Forbidden", "Access denied", {"server": "cloudflare"}, False),
        ("Sign in", "password required", {}, False),
        ("Verify", '<div class="h-captcha"></div>', {}, False),
        (
            "Article",
            '<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script>',
            {},
            False,
        ),
        ("Just a moment...", "", {}, True),
        ("", "window._cf_chl_opt = {};", {}, True),
        ("", "", {"CF-Mitigated": "challenge"}, True),
    ],
)
def test_only_supported_challenges_enter_solver(title, html, headers, supported):
    assert supported_challenge(title=title, html=html, headers=headers) is supported


class Emitter:
    def __init__(self):
        self.listeners = {}

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

    def remove_listener(self, event, callback):
        self.listeners[event].remove(callback)


class Page(Emitter):
    def __init__(self, context, scenario):
        super().__init__()
        self.context = context
        self.scenario = scenario
        self.url = "https://publisher.test/article"
        self.main_frame = self
        self.checks = 0

    async def opener(self):
        return None

    async def title(self):
        self.checks += 1
        return (
            "Just a moment..."
            if self.scenario == "click"
            or (self.scenario == "auto" and self.checks == 1)
            else "Article"
        )

    async def content(self):
        return "body"

    async def wait_for_load_state(self, *args, **kwargs):
        pass

    @property
    def page(self):
        return self


@pytest.mark.parametrize(
    "scenario,expected_calls,expected_clicks,outcome",
    [
        ("normal", 0, 0, None),
        ("auto", 0, 0, "auto_verified"),
        ("click", 1, 1, "cleared"),
        ("no_click", 0, 0, None),
    ],
)
def test_diagnostics_distinguish_management_detection_solver_and_click(
    monkeypatch, scenario, expected_calls, expected_clicks, outcome
):
    captcha = ModuleType("playwright_captcha")

    class Solver:
        def __init__(self, **kwargs):
            self.page = kwargs["page"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def solve_captcha(self, **kwargs):
            logging.getLogger("playwright_captcha").info(
                "Checkbox clicked successfully"
            )
            self.page.scenario = "normal"

    captcha.ClickSolver = Solver
    captcha.FrameworkType = SimpleNamespace(CAMOUFOX="camoufox")
    captcha.CaptchaType = SimpleNamespace(CLOUDFLARE_INTERSTITIAL="cloudflare")
    monkeypatch.setitem(sys.modules, "playwright_captcha", captcha)
    monkeypatch.setitem(sys.modules, "src.consts", SimpleNamespace(MAX_ATTEMPTS=10))

    async def run():
        context = Emitter()
        page = Page(context, scenario)
        response = SimpleNamespace(
            frame=page,
            request=SimpleNamespace(
                is_navigation_request=lambda: True,
                _impl_obj=SimpleNamespace(_guid="request-1"),
            ),
            status=403 if scenario != "normal" else 200,
            headers={"content-type": "text/html"},
            url=page.url,
        )

        async def finished():
            pass

        response.finished = finished
        saved = []
        operation = ManagedOperation(
            page,
            {"operation": "op-1", "page": "page-1", "timeout_ms": 3000},
            asyncio.Lock(),
            saved.append,
        )
        operation.response_seen(response)
        operation.response_seen(response)
        result = await operation.finish(retain=False)
        assert len(result["documents"]) == 1
        assert result["documents"][0]["status"] == response.status
        kinds = [event["kind"] for event in result["events"]]
        assert kinds.count("navigation_managed") == 1
        assert kinds.count("solver_called") == expected_calls
        assert kinds.count("solver_click") == expected_clicks
        if outcome:
            assert (
                next(
                    event
                    for event in result["events"]
                    if event["kind"] == "challenge_result"
                )["outcome"]
                == outcome
            )
        assert all(event["operation"] == "op-1" for event in result["events"])
        assert not any(context.listeners.values())

    asyncio.run(run())
