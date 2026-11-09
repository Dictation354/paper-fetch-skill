"""Selection/state contracts and the private solver boundary, without browsers."""

import asyncio
import logging
import sys
from types import SimpleNamespace

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
        ("click", 1, 1, "awaiting_response"),
        ("no_click", 0, 0, None),
    ],
)
def test_diagnostics_distinguish_management_detection_solver_and_click(
    monkeypatch, scenario, expected_calls, expected_clicks, outcome
):
    async def solve_challenge(page, timer):
        logging.getLogger("paper_fetch.byparr.upstream").info(
            "Clicked the challenge checkbox (attempt 1)."
        )
        page.scenario = "normal"

    monkeypatch.setitem(
        sys.modules,
        "byparr_challenge",
        SimpleNamespace(solve_challenge=solve_challenge),
    )
    monkeypatch.setitem(
        sys.modules,
        "byparr_upstream",
        SimpleNamespace(
            TimeoutTimer=lambda **kwargs: kwargs,
            logger=logging.getLogger("paper_fetch.byparr.upstream"),
        ),
    )

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


@pytest.fixture
def sync_operation(monkeypatch, tmp_path):
    from paper_fetch.providers.browser_runtime import byparr_invisible as invisible

    clock = SimpleNamespace(now=0.0, tick=lambda: None)
    monkeypatch.setattr(invisible.time, "monotonic", lambda: clock.now)
    context = Emitter()

    class SyncPage(Emitter):
        url = "https://publisher.test/article"
        _impl_obj = SimpleNamespace(_guid="main")
        widget = False

        def __init__(self):
            super().__init__()
            self.page = self.main_frame = self

        def opener(self):
            return None

        def title(self):
            return "Article"

        def content(self):
            return "body"

        def wait_for_timeout(self, milliseconds):
            clock.now += milliseconds / 1000
            clock.tick()

    page = SyncPage()
    probes, calls = [], []

    def challenge_present(target):
        assert target is page
        probes.append(clock.now)
        return page.widget

    def solve_challenge(target, timer):
        assert target is page
        calls.append((clock.now, timer.remaining()))
        page.widget = False

    solver = SimpleNamespace(
        challenge_present=challenge_present,
        solve_challenge=solve_challenge,
        POLL_INTERVAL=0.25,
        logger=logging.getLogger("paper_fetch.byparr.upstream"),
    )
    monkeypatch.setattr(invisible, "load_solver", lambda runtime, wait: solver)
    owner = SimpleNamespace(
        runtime_context=None,
        context=context,
        _solver_runtime=tmp_path,
        _sync_operations=[],
        diagnostics={},
        work_dir=None,
    )
    operation = invisible.Operation(owner, page, 2000)

    def respond(*, status=200, challenge=False, frame=page):
        class Response:
            pass

        response = Response()
        response.url, response.status, response.frame = page.url, status, frame
        response.request = SimpleNamespace(is_navigation_request=lambda: True)
        response.headers = {"content-type": "text/html"}
        if challenge:
            response.headers["cf-mitigated"] = "challenge"
        operation.response_seen(response)
        return response

    yield SimpleNamespace(
        operation=operation,
        page=page,
        clock=clock,
        calls=calls,
        probes=probes,
        respond=respond,
    )
    operation.close()
    assert not any(context.listeners.values())
    assert not any(page.listeners.values())


def test_invisible_rechecks_delayed_widget_without_new_response(sync_operation):
    state = sync_operation
    state.respond(status=403, challenge=True)

    def tick():
        if not state.calls and state.clock.now >= 0.7:
            state.page.widget = True
        if (
            state.calls
            and state.clock.now >= 1.1
            and len(state.operation.responses) == 1
        ):
            state.respond()

    state.clock.tick = tick
    state.operation.finish()
    assert len(state.calls) == 1
    assert state.probes[0] == pytest.approx(0.5)
    assert state.calls[0][0] == pytest.approx(0.75)
    assert state.calls[0][1] == pytest.approx(1.25)
    assert state.clock.now >= 1.1  # Handler return alone did not finish the operation.
    outcomes = [
        event["outcome"]
        for event in state.operation.events
        if event["kind"] == "challenge_result"
    ]
    assert outcomes == ["awaiting_response", "awaiting_response", "cleared"]


@pytest.mark.parametrize("completion", ["document", "download"])
def test_invisible_automatic_redirect_skips_handler(sync_operation, completion):
    state = sync_operation
    state.respond(status=403, challenge=True)

    def tick():
        if (
            state.clock.now >= 0.2
            and len(state.operation.responses) == 1
            and not state.operation.downloads
        ):
            if completion == "document":
                state.respond()
            else:
                state.operation.download_seen(object())

    state.clock.tick = tick
    state.operation.finish()
    assert not state.calls
    assert not state.probes
    assert state.operation.events[-1]["outcome"] == "auto_verified"


@pytest.mark.parametrize(
    "scenario",
    ["no_widget", "handler_returned", "challenge_200", "old_success", "other_frame"],
)
def test_invisible_needs_new_success_from_challenged_frame(sync_operation, scenario):
    from paper_fetch.providers.browser_runtime.types import BrowserRuntimeFailure

    state = sync_operation
    if scenario == "old_success":
        state.respond()
    state.respond(status=200 if scenario == "challenge_200" else 403, challenge=True)
    if scenario == "other_frame":
        frame = type(state.page)()
        frame._impl_obj = SimpleNamespace(_guid="other")
        state.respond(frame=frame)
    state.page.widget = scenario == "handler_returned"
    with pytest.raises(BrowserRuntimeFailure) as caught:
        state.operation.finish()
    assert caught.value.kind == "byparr_timeout"
    assert state.clock.now == pytest.approx(2.0)
    assert len(state.calls) == int(scenario == "handler_returned")
    assert not any(
        event.get("outcome") in {"cleared", "auto_verified"}
        for event in state.operation.events
    )
