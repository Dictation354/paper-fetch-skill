from __future__ import annotations

from pathlib import Path
from unittest import mock

from paper_fetch import browser_preflight
from paper_fetch.config import (
    BROWSER_USER_AGENT_ENV_VAR,
    CLOAKBROWSER_TIMEOUT_MS_ENV_VAR,
    XDG_DATA_HOME_ENV_VAR,
)
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)


def _runtime_config(tmp_path: Path, *, provider: str, doi: str) -> BrowserRuntimeConfig:
    return BrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=tmp_path / "artifacts" / provider,
        headless=True,
        user_agent=None,
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
    )


def test_browser_preflight_adds_provider_storage_path_for_external_cdp(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def load_runtime_config(env, *, provider, doi):
        captured["env"] = dict(env)
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config):
        captured["candidate_urls"] = list(candidate_urls)
        captured["publisher"] = publisher
        captured["config"] = config
        return BrowserFetchedHtml(
            source_url=candidate_urls[0],
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
            html="<html><title>Sample</title><body>Article body</body></html>",
            response_status=200,
            response_headers={},
            title="Sample",
            summary="Article body",
            browser_context_seed={},
        )

    with (
        mock.patch.object(browser_preflight, "load_runtime_config", side_effect=load_runtime_config),
        mock.patch.object(browser_preflight, "ensure_runtime_ready") as ensure_runtime_ready,
        mock.patch.object(browser_preflight, "fetch_html_with_browser", side_effect=fetch_html_with_browser),
    ):
        results = browser_preflight.run_browser_provider_preflight(
            providers=["wiley"],
            timeout_ms=45000,
            browser_user_agent="Mozilla/5.0 preflight-test",
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
        )

    assert len(results) == 1
    result = results[0]
    assert result.ok is True
    assert result.provider == "wiley"
    assert result.final_url == "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414"
    assert result.storage_state_path == (
        tmp_path / "paper-fetch" / "publisher-browser-profiles" / "wiley" / "storage-state.json"
    )
    assert captured["publisher"] == "wiley"
    assert captured["candidate_urls"] == [
        "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414"
    ]
    runtime = captured["config"]
    assert isinstance(runtime, BrowserRuntimeConfig)
    assert runtime.user_data_dir == tmp_path / "paper-fetch" / "publisher-browser-profiles" / "wiley"
    ensure_runtime_ready.assert_called_once_with(runtime)
    runtime_env = captured["env"]
    assert isinstance(runtime_env, dict)
    assert runtime_env[CLOAKBROWSER_TIMEOUT_MS_ENV_VAR] == "45000"
    assert runtime_env[BROWSER_USER_AGENT_ENV_VAR] == "Mozilla/5.0 preflight-test"


def test_browser_preflight_records_failure_and_continues(tmp_path: Path) -> None:
    def load_runtime_config(env, *, provider, doi):
        return BrowserRuntimeConfig(
            provider=provider,
            doi=doi,
            artifact_dir=tmp_path / "artifacts" / provider,
            headless=True,
            user_agent=None,
            user_data_dir=tmp_path / "profiles" / provider,
        )

    def fetch_html_with_browser(candidate_urls, *, publisher, config):
        if publisher == "science":
            raise BrowserRuntimeFailure(
                "cloudflare_challenge",
                "Encountered a challenge or CAPTCHA page while loading publisher HTML.",
            )
        return BrowserFetchedHtml(
            source_url=candidate_urls[0],
            final_url=candidate_urls[0],
            html="<html><body>Article body</body></html>",
            response_status=200,
            response_headers={},
            title="Sample",
            summary="Article body",
            browser_context_seed={},
        )

    with (
        mock.patch.object(browser_preflight, "load_runtime_config", side_effect=load_runtime_config),
        mock.patch.object(browser_preflight, "ensure_runtime_ready"),
        mock.patch.object(browser_preflight, "fetch_html_with_browser", side_effect=fetch_html_with_browser),
    ):
        results = browser_preflight.run_browser_provider_preflight(
            providers=["science", "pnas"],
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
        )

    assert [result.provider for result in results] == ["science", "pnas"]
    assert results[0].ok is False
    assert results[0].reason == "cloudflare_challenge"
    assert results[0].storage_state_path == tmp_path / "profiles" / "science" / "storage-state.json"
    assert results[1].ok is True


def test_browser_preflight_reports_missing_builtin_target() -> None:
    with mock.patch.dict(browser_preflight.AUTH_TARGETS, {}, clear=True):
        result = browser_preflight.preflight_browser_provider("wiley", env={})

    assert result.ok is False
    assert result.provider == "wiley"
    assert result.reason == "error"
    assert "No built-in browser preflight URL" in (result.message or "")

