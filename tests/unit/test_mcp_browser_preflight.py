# ruff: noqa: F403,F405
from __future__ import annotations

import pytest
from pydantic import ValidationError

from paper_fetch.config import BROWSER_AUTO_PREPARE_ENV_VAR

from ._mcp_support import *


def _preflight_result(
    provider: str,
    *,
    ok: bool,
    reason: str | None = None,
    message: str | None = None,
    storage_state_path: Path | None = None,
    storage_saved: bool = False,
) -> BrowserPreflightResult:
    return BrowserPreflightResult(
        provider=provider,
        provider_label=provider.upper(),
        status=(
            "ready"
            if ok
            else classify_browser_preflight_failure(
                reason,
                stage="preflight",
            )
        ),
        reason_code=reason
        or ("browser_preflight_ready" if ok else "browser_preflight_failed"),
        stage="complete" if ok else "preflight",
        message=message
        or (
            "Publisher browser HTML preflight completed successfully."
            if ok
            else "Browser preflight failed."
        ),
        target_url=f"https://{provider}.example.test/article",
        final_url=f"https://{provider}.example.test/final" if ok else None,
        title=f"{provider} sample" if ok else None,
        storage_state_path=storage_state_path,
        diagnostics={
            "browser_runtime_trace": {
                "storage_state_save": {
                    "attempted": storage_state_path is not None,
                    "saved": storage_saved,
                }
            }
        },
    )


def test_browser_preflight_payload_passes_scoped_live_and_storage_options(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    state_path = tmp_path / "wiley-state.json"

    def fake_preflight(**kwargs):
        captured.update(kwargs)
        state_path.write_text('{"cookies": []}\n', encoding="utf-8")
        result = _preflight_result(
            "wiley",
            ok=True,
            storage_state_path=state_path,
            storage_saved=True,
        )
        kwargs["on_result"](result, 1, 1)
        return [result]

    progress: list[tuple[str, int, int]] = []
    payload = mcp_tools.browser_preflight_payload(
        provider=" WILEY ",
        test_url="https://onlinelibrary.wiley.com/doi/full/10.1111/example",
        timeout_ms=45000,
        storage_state_path=str(state_path),
        detail="full",
        on_result=lambda result, completed, total: progress.append(
            (result.provider, completed, total)
        ),
        deps=mcp_test_deps(
            build_runtime_env=lambda env=None: dict(env or {}),
            run_browser_provider_preflight=fake_preflight,
        ),
    )

    assert state_path.is_file()
    assert captured["providers"] == ["wiley"]
    assert captured["target_url"] == (
        "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
    )
    assert captured["storage_state_path"] == state_path
    assert captured["save_storage_state"] is True
    assert captured["cancel_as_result"] is True
    assert captured["runtime_options"].env[BROWSER_AUTO_PREPARE_ENV_VAR] == "false"
    assert progress == [("wiley", 1, 1)]
    assert payload["status"] == "ready"
    assert payload["pdf_fallback_attempted"] is False
    assert payload["auth_attempted"] is False
    assert payload["results"][0]["storage_state"] == {
        "path": str(state_path),
        "save_requested": True,
        "attempted": True,
        "saved": True,
        "reason": None,
    }


def test_browser_preflight_payload_allows_request_auto_prepare_override() -> None:
    captured: dict[str, object] = {}

    def fake_preflight(**kwargs):
        captured.update(kwargs)
        return [_preflight_result("wiley", ok=True)]

    payload = mcp_tools.browser_preflight_payload(
        provider="wiley",
        browser_auto_prepare=True,
        deps=mcp_test_deps(
            build_runtime_env=lambda env=None: dict(env or {}),
            run_browser_provider_preflight=fake_preflight,
        ),
    )

    assert payload["status"] == "ready"
    assert captured["runtime_options"].env[BROWSER_AUTO_PREPARE_ENV_VAR] == "true"


def test_browser_preflight_payload_keeps_per_provider_action_states() -> None:
    results = [
        replace(
            _preflight_result(
                "ieee",
                ok=False,
                reason="aws_waf_challenge",
                message="AWS WAF challenge detected.",
            ),
            diagnostics={
                "challenge_provider": "aws_waf",
                "legacy_reason_code": "cloudflare_challenge",
            },
        ),
        _preflight_result(
            "wiley",
            ok=False,
            reason="publisher_access_denied",
            message="Sign-in is required.",
        ),
        _preflight_result(
            "pnas",
            ok=False,
            reason="cdp_connect_failed",
            message="CDP connection failed after Chrome startup.",
        ),
        _preflight_result("mdpi", ok=True),
    ]

    payload = mcp_tools.browser_preflight_payload(
        detail="full",
        deps=mcp_test_deps(run_browser_provider_preflight=lambda **_kwargs: results),
    )

    assert [item["status"] for item in payload["results"]] == [
        "challenge",
        "auth_required",
        "runtime_error",
        "ready",
    ]
    assert payload["status"] == "partial"
    assert payload["summary"]["challenge"] == 1
    assert payload["summary"]["auth_required"] == 1
    assert payload["summary"]["runtime_error"] == 1
    assert payload["summary"]["ready"] == 1
    assert payload["results"][0]["next_action"] == "paper-fetch auth ieee"
    assert payload["results"][0]["reason_code"] == "aws_waf_challenge"
    assert payload["results"][0]["diagnostics"]["challenge_provider"] == "aws_waf"
    assert (
        payload["results"][0]["diagnostics"]["legacy_reason_code"]
        == "cloudflare_challenge"
    )
    assert payload["results"][3]["next_action"] == "run the requested fetch"


def test_browser_preflight_compact_has_only_routing_fields() -> None:
    payload = mcp_tools.browser_preflight_payload(
        provider="wiley",
        detail="compact",
        save_storage_state=False,
        deps=mcp_test_deps(
            run_browser_provider_preflight=lambda **_kwargs: [
                _preflight_result("wiley", ok=True)
            ]
        ),
    )

    assert payload["results"] == [
        {
            "provider": "wiley",
            "status": "ready",
            "reason_code": "browser_preflight_ready",
            "stage": "complete",
            "message": "Publisher browser HTML preflight completed successfully.",
            "next_action": "run the requested fetch",
        }
    ]
    assert payload["storage_state_write_enabled"] is False


@pytest.mark.parametrize(
    "arguments",
    [
        {"provider": "wiley", "test_url": "file:///tmp/article.html"},
        {
            "provider": "wiley",
            "test_url": "https://user:pass@example.test/article",
        },
        {"test_url": "https://example.test/article"},
        {"storage_state_path": "/tmp/wiley.json"},
    ],
)
def test_browser_preflight_invalid_scoped_input_never_invokes_shared_core(
    arguments,
) -> None:
    def should_not_run(**_kwargs):
        raise AssertionError("invalid browser_preflight input reached the shared core")

    with pytest.raises(ValidationError):
        mcp_tools.browser_preflight_payload(
            **arguments,
            deps=mcp_test_deps(run_browser_provider_preflight=should_not_run),
        )


class McpBrowserPreflightAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_reports_start_per_provider_and_completion_progress(
        self,
    ) -> None:
        ctx = FakeContext()

        def fake_preflight(**kwargs):
            results = [_preflight_result("wiley", ok=True)]
            for index, result in enumerate(results, start=1):
                kwargs["on_result"](result, index, len(results))
            return results

        result = await mcp_tools.browser_preflight_tool_async(
            provider="wiley",
            detail="compact",
            ctx=ctx,
            deps=mcp_test_deps(run_browser_provider_preflight=fake_preflight),
        )

        self.assertFalse(result.is_error)
        self.assertEqual(
            ctx.progress[0],
            (0, 1, "Starting live browser_preflight"),
        )
        self.assertEqual(ctx.progress[1], (1, 1, "Preflight wiley: ready"))
        self.assertEqual(
            ctx.progress[-1],
            (1, 1, "browser_preflight complete"),
        )

    async def test_tool_cancellation_reaches_active_shared_preflight(self) -> None:
        started = threading.Event()
        cancelled_seen = threading.Event()

        def fake_preflight(**kwargs):
            started.set()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if kwargs["cancel_check"]():
                    cancelled_seen.set()
                    return [
                        _preflight_result(
                            "wiley",
                            ok=False,
                            reason="request_cancelled",
                            message="Cancelled.",
                        )
                    ]
                time.sleep(0.01)
            return [_preflight_result("wiley", ok=True)]

        task = asyncio.create_task(
            mcp_tools.browser_preflight_tool_async(
                provider="wiley",
                deps=mcp_test_deps(run_browser_provider_preflight=fake_preflight),
            )
        )
        await wait_for_threading_event(started, 1.0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await wait_for_threading_event(cancelled_seen, 1.0)

        self.assertTrue(cancelled_seen.is_set())
