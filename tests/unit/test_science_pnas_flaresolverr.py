from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.providers import _flaresolverr


class SciencePnasFlareSolverrTests(unittest.TestCase):
    def setUp(self) -> None:
        _flaresolverr.reset_session_registry_for_tests()

    def tearDown(self) -> None:
        _flaresolverr.reset_session_registry_for_tests()

    def _runtime_config(
        self,
        tmpdir: str,
        provider: str,
        doi: str,
        *,
        keep_session: bool = False,
    ) -> _flaresolverr.FlareSolverrRuntimeConfig:
        return _flaresolverr.FlareSolverrRuntimeConfig(
            provider=provider,
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=Path(tmpdir) / ".env.flaresolverr",
            source_dir=Path(tmpdir),
            artifact_dir=Path(tmpdir) / "artifacts",
            headless=True,
            keep_session=keep_session,
        )

    def _html_response(
        self,
        url: str,
        *,
        title: str = "Example Article",
        body: str = "Readable full text.",
        final_url: str | None = None,
        status: int = 200,
    ) -> dict[str, object]:
        return {
            "status": "ok",
            "solution": {
                "response": f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>",
                "url": final_url or url,
                "status": status,
                "headers": {"content-type": "text/html"},
                "cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".science.org", "path": "/"}],
                "userAgent": "Mozilla/5.0",
            },
        }

    def test_normalize_browser_cookie_for_playwright(self) -> None:
        cookie = _flaresolverr.normalize_browser_cookie_for_playwright(
            {
                "name": "cf_clearance",
                "value": "secret",
                "domain": ".science.org",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "lax",
            }
        )

        self.assertEqual(cookie["name"], "cf_clearance")
        self.assertEqual(cookie["domain"], ".science.org")
        self.assertEqual(cookie["sameSite"], "Lax")
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httpOnly"])

    def test_redact_flaresolverr_response_payload_redacts_cookie_values(self) -> None:
        redacted = _flaresolverr.redact_flaresolverr_response_payload(
            {
                "status": "ok",
                "solution": {
                    "cookies": [
                        {"name": "cf_clearance", "value": "secret"},
                        {"name": "session", "value": "another"},
                    ]
                },
            }
        )

        cookies = redacted["solution"]["cookies"]
        self.assertEqual(cookies[0]["value"], "[redacted]")
        self.assertEqual(cookies[1]["value"], "[redacted]")

    def test_merge_browser_context_seeds_prefers_latest_cookie_and_url(self) -> None:
        merged = _flaresolverr.merge_browser_context_seeds(
            {
                "browser_cookies": [{"name": "cf_clearance", "value": "old", "domain": ".example.org", "path": "/"}],
                "browser_user_agent": "UA/1",
                "browser_final_url": "https://example.org/article",
            },
            {
                "browser_cookies": [
                    {"name": "cf_clearance", "value": "new", "domain": ".example.org", "path": "/"},
                    {"name": "sessionid", "value": "warm", "domain": ".example.org", "path": "/"},
                ],
                "browser_final_url": "https://example.org/pdf",
            },
        )

        self.assertEqual(
            merged["browser_cookies"],
            [
                {"name": "cf_clearance", "value": "new", "domain": ".example.org", "path": "/"},
                {"name": "sessionid", "value": "warm", "domain": ".example.org", "path": "/"},
            ],
        )
        self.assertEqual(merged["browser_user_agent"], "UA/1")
        self.assertEqual(merged["browser_final_url"], "https://example.org/pdf")

    def test_warm_browser_context_with_flaresolverr_merges_existing_and_preflight_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "wiley", "10.1111/test")
            with mock.patch.object(
                _flaresolverr,
                "fetch_html_with_flaresolverr",
                return_value=_flaresolverr.FetchedPublisherHtml(
                    source_url="https://onlinelibrary.wiley.com/doi/epdf/10.1111/test",
                    final_url="https://onlinelibrary.wiley.com/doi/10.1111/test",
                    html="<html><body>pdf wrapper</body></html>",
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="PDF wrapper",
                    summary="PDF wrapper",
                    browser_context_seed={
                        "browser_cookies": [{"name": "sessionid", "value": "warm", "domain": ".wiley.com", "path": "/"}],
                        "browser_user_agent": "Mozilla/5.0",
                        "browser_final_url": "https://onlinelibrary.wiley.com/doi/10.1111/test",
                    },
                ),
            ):
                warmed = _flaresolverr.warm_browser_context_with_flaresolverr(
                    ["https://onlinelibrary.wiley.com/doi/epdf/10.1111/test"],
                    publisher="wiley",
                    config=config,
                    browser_context_seed={
                        "browser_cookies": [{"name": "cf_clearance", "value": "seed", "domain": ".wiley.com", "path": "/"}],
                        "browser_user_agent": "Mozilla/5.0",
                    },
                )

        self.assertEqual(
            warmed["browser_cookies"],
            [
                {"name": "cf_clearance", "value": "seed", "domain": ".wiley.com", "path": "/"},
                {"name": "sessionid", "value": "warm", "domain": ".wiley.com", "path": "/"},
            ],
        )
        self.assertEqual(warmed["browser_final_url"], "https://onlinelibrary.wiley.com/doi/10.1111/test")

    def test_load_runtime_config_does_not_require_rate_limit_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            env_file = tmp / ".env.flaresolverr"
            env_file.write_text('HEADLESS="true"\n', encoding="utf-8")

            config = _flaresolverr.load_runtime_config(
                {
                    "FLARESOLVERR_ENV_FILE": str(env_file),
                    "FLARESOLVERR_SOURCE_DIR": str(tmp / "vendor" / "flaresolverr"),
                    "XDG_DATA_HOME": str(tmp),
                },
                provider="science",
                doi="10.1126/science.ady3136",
            )

        self.assertEqual(config.provider, "science")
        self.assertFalse(hasattr(config, "min_interval_seconds"))

    def test_load_runtime_config_ignores_legacy_rate_limit_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            env_file = tmp / ".env.flaresolverr"
            env_file.write_text('HEADLESS="true"\n', encoding="utf-8")

            config = _flaresolverr.load_runtime_config(
                {
                    "FLARESOLVERR_ENV_FILE": str(env_file),
                    "FLARESOLVERR_SOURCE_DIR": str(tmp / "vendor" / "flaresolverr"),
                    "FLARESOLVERR_MIN_INTERVAL_SECONDS": "1",
                    "FLARESOLVERR_MAX_REQUESTS_PER_HOUR": "300",
                    "FLARESOLVERR_MAX_REQUESTS_PER_DAY": "2000",
                    "XDG_DATA_HOME": str(tmp),
                },
                provider="wiley",
                doi="10.1111/test",
            )

        self.assertEqual(config.provider, "wiley")
        self.assertFalse(hasattr(config, "max_requests_per_hour"))

    def test_health_check_accepts_ok_payload(self) -> None:
        with mock.patch.object(_flaresolverr, "post_to_flaresolverr", return_value={"status": "ok"}):
            _flaresolverr.health_check("http://127.0.0.1:8191/v1")

    def test_fetch_html_with_flaresolverr_can_disable_media_for_fast_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "science", "10.1126/science.ady3136")
            request_payloads: list[dict[str, object]] = []

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                if payload["cmd"] == "sessions.create":
                    return {"status": "ok"}
                if payload["cmd"] == "sessions.destroy":
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    request_payloads.append(dict(payload))
                    return self._html_response(str(payload["url"]))
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post):
                _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config,
                    wait_seconds=0,
                    warm_wait_seconds=0,
                    disable_media=True,
                )

        self.assertEqual(len(request_payloads), 1)
        self.assertEqual(request_payloads[0]["waitInSeconds"], 0)
        self.assertIs(request_payloads[0]["disableMedia"], True)

    def test_fetch_html_with_flaresolverr_does_not_disable_media_for_image_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "science", "10.1126/science.ady3136")
            request_payloads: list[dict[str, object]] = []

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                if payload["cmd"] == "sessions.create":
                    return {"status": "ok"}
                if payload["cmd"] == "sessions.destroy":
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    request_payloads.append(dict(payload))
                    return self._html_response(str(payload["url"]))
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post):
                _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config,
                    return_image_payload=True,
                    disable_media=True,
                )

        self.assertEqual(len(request_payloads), 1)
        self.assertIs(request_payloads[0]["returnImagePayload"], True)
        self.assertNotIn("disableMedia", request_payloads[0])

    def test_fetch_html_with_flaresolverr_destroys_default_session_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "science", "10.1126/science.ady3136")
            created_sessions: list[str] = []
            destroyed_sessions: list[str] = []
            request_payloads: list[dict[str, object]] = []

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                if payload["cmd"] == "sessions.create":
                    created_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "sessions.destroy":
                    destroyed_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    request_payloads.append(dict(payload))
                    return self._html_response(str(payload["url"]))
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post):
                first = _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config,
                )
                second = _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config,
                )

        self.assertEqual(len(created_sessions), 2)
        self.assertEqual(destroyed_sessions, created_sessions)
        self.assertEqual(first.final_url, "https://www.science.org/doi/full/10.1126/science.ady3136")
        self.assertEqual(second.final_url, "https://www.science.org/doi/full/10.1126/science.ady3136")
        self.assertEqual([payload["session"] for payload in request_payloads], created_sessions)

    def test_fetch_html_with_flaresolverr_destroys_default_session_after_cloudflare_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "science", "10.1126/science.ady3136")
            created_sessions: list[str] = []
            destroyed_sessions: list[str] = []

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                if payload["cmd"] == "sessions.create":
                    created_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "sessions.destroy":
                    destroyed_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    return self._html_response(
                        str(payload["url"]),
                        title="Just a moment...",
                        body="Verify you are human",
                    )
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with (
                mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post),
                self.assertRaises(_flaresolverr.FlareSolverrFailure) as ctx,
            ):
                _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config,
                )

        self.assertEqual(ctx.exception.kind, "cloudflare_challenge")
        self.assertTrue(ctx.exception.browser_context_seed["browser_cookies"])
        self.assertEqual(destroyed_sessions, created_sessions)

    def test_fetch_html_with_flaresolverr_reuses_session_across_dois(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_one = self._runtime_config(
                tmpdir, "science", "10.1126/science.ady3136", keep_session=True
            )
            config_two = self._runtime_config(
                tmpdir, "science", "10.1126/science.aeg3511", keep_session=True
            )
            created_sessions: list[str] = []
            request_payloads: list[dict[str, object]] = []

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                if payload["cmd"] == "sessions.create":
                    created_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    request_payloads.append(dict(payload))
                    return self._html_response(str(payload["url"]))
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post):
                first = _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config_one,
                )
                second = _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.aeg3511"],
                    publisher="science",
                    config=config_two,
                )

        self.assertEqual(len(created_sessions), 1)
        self.assertEqual(first.final_url, "https://www.science.org/doi/full/10.1126/science.ady3136")
        self.assertEqual(second.final_url, "https://www.science.org/doi/full/10.1126/science.aeg3511")
        self.assertEqual([payload["session"] for payload in request_payloads], [created_sessions[0], created_sessions[0]])
        self.assertEqual([payload["waitInSeconds"] for payload in request_payloads], [8, 1])
        self.assertEqual([payload["returnScreenshot"] for payload in request_payloads], [False, False])

    def test_fetch_html_with_flaresolverr_retries_warm_challenge_with_cold_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "science", "10.1126/science.ady3136", keep_session=True)
            created_sessions: list[str] = []
            request_payloads: list[dict[str, object]] = []
            request_count = 0

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                nonlocal request_count
                if payload["cmd"] == "sessions.create":
                    created_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    request_payloads.append(dict(payload))
                    request_count += 1
                    if request_count == 1:
                        return self._html_response(str(payload["url"]))
                    if request_count == 2:
                        return self._html_response(
                            str(payload["url"]),
                            title="Just a moment...",
                            body="Verify you are human",
                        )
                    return self._html_response(str(payload["url"]))
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post):
                _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config,
                )
                result = _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config,
                )

        self.assertEqual(len(created_sessions), 1)
        self.assertEqual(result.final_url, "https://www.science.org/doi/full/10.1126/science.ady3136")
        self.assertEqual([payload["waitInSeconds"] for payload in request_payloads], [8, 1, 8])
        self.assertEqual([payload["session"] for payload in request_payloads], [created_sessions[0]] * 3)

    def test_fetch_html_with_flaresolverr_recreates_invalid_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_one = self._runtime_config(
                tmpdir, "science", "10.1126/science.ady3136", keep_session=True
            )
            config_two = self._runtime_config(
                tmpdir, "science", "10.1126/science.aeg3511", keep_session=True
            )
            created_sessions: list[str] = []
            destroyed_sessions: list[str] = []
            request_payloads: list[dict[str, object]] = []
            invalid_returned = False

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                nonlocal invalid_returned
                if payload["cmd"] == "sessions.create":
                    created_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "sessions.destroy":
                    destroyed_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    request_payloads.append(dict(payload))
                    if not invalid_returned and len(request_payloads) == 2:
                        invalid_returned = True
                        return {"status": "error", "message": "Session not found"}
                    return self._html_response(str(payload["url"]))
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post):
                _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.ady3136"],
                    publisher="science",
                    config=config_one,
                )
                result = _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.science.org/doi/full/10.1126/science.aeg3511"],
                    publisher="science",
                    config=config_two,
                )

        self.assertEqual(len(created_sessions), 2)
        self.assertEqual(destroyed_sessions, [created_sessions[0]])
        self.assertEqual(destroyed_sessions.count(created_sessions[0]), 1)
        self.assertEqual(result.final_url, "https://www.science.org/doi/full/10.1126/science.aeg3511")
        self.assertEqual([payload["waitInSeconds"] for payload in request_payloads], [8, 1, 8])
        self.assertEqual([payload["session"] for payload in request_payloads], [created_sessions[0], created_sessions[0], created_sessions[1]])

    def test_fetch_html_with_flaresolverr_destroys_default_session_after_abstract_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "pnas", "10.1073/pnas.81.23.7500")
            created_sessions: list[str] = []
            destroyed_sessions: list[str] = []
            request_payloads: list[dict[str, object]] = []

            def fake_post(_base_url: str, payload: dict[str, object], **_kwargs: object) -> dict[str, object]:
                if payload["cmd"] == "sessions.create":
                    created_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "sessions.destroy":
                    destroyed_sessions.append(str(payload["session"]))
                    return {"status": "ok"}
                if payload["cmd"] == "request.get":
                    request_payloads.append(dict(payload))
                    return {
                        "status": "ok",
                        "solution": {
                            "response": "<html><head><title>Abstract</title></head><body>Abstract only</body></html>",
                            "url": "https://www.pnas.org/doi/abs/10.1073/pnas.81.23.7500",
                            "status": 200,
                            "headers": {"content-type": "text/html"},
                            "cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
                            "userAgent": "Mozilla/5.0",
                        },
                    }
                raise AssertionError(f"Unexpected FlareSolverr payload: {payload}")

            with (
                mock.patch.object(_flaresolverr, "post_to_flaresolverr", side_effect=fake_post),
                self.assertRaises(_flaresolverr.FlareSolverrFailure) as ctx,
            ):
                _flaresolverr.fetch_html_with_flaresolverr(
                    ["https://www.pnas.org/doi/full/10.1073/pnas.81.23.7500"],
                    publisher="pnas",
                    config=config,
                )

        self.assertEqual(ctx.exception.kind, "redirected_to_abstract")
        self.assertTrue(ctx.exception.browser_context_seed["browser_cookies"])
        self.assertEqual(len(created_sessions), 1)
        self.assertEqual(destroyed_sessions, created_sessions)
        self.assertEqual([payload["waitInSeconds"] for payload in request_payloads], [8])


if __name__ == "__main__":
    unittest.main()
