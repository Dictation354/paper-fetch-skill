from __future__ import annotations

from dataclasses import replace
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
from paper_fetch.providers.browser_workflow import html_extraction
from paper_fetch.providers.browser_workflow.shared import default_browser_workflow_deps


def _runtime_config(tmp_path: Path, *, provider: str, doi: str) -> BrowserRuntimeConfig:
    return BrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=tmp_path / "artifacts" / provider,
        headless=True,
        user_agent=None,
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
    )


def _fake_markdown(markdown_title: str = "Sample"):
    def cached_markdown(*args, **kwargs):
        del args, kwargs
        return (
            f"# {markdown_title}\n\n## Results\n\nBody text.",
            {
                "title": markdown_title,
                "availability_diagnostics": {"content_kind": "fulltext"},
            },
        )

    return cached_markdown


def _preflight_deps(markdown_title: str = "Sample"):
    return replace(
        default_browser_workflow_deps(),
        _cached_browser_workflow_markdown=_fake_markdown(markdown_title),
    )


def test_browser_preflight_adds_provider_storage_path_for_external_cdp(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def load_runtime_config(env, *, provider, doi):
        captured["env"] = dict(env)
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del kwargs
        captured["candidate_urls"] = list(candidate_urls)
        captured["publisher"] = publisher
        captured["config"] = config
        return BrowserFetchedHtml(
            source_url=candidate_urls[0],
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
            html="<html><title>Sample</title><body>Article body</body></html>",
            response_status=200,
            response_headers={},
            title="Sample",
            summary="Article body",
            browser_context_seed={},
        )

    with (
        mock.patch.object(
            browser_preflight, "load_runtime_config", side_effect=load_runtime_config
        ),
        mock.patch.object(
            browser_preflight, "ensure_runtime_ready"
        ) as ensure_runtime_ready,
        mock.patch.object(
            browser_preflight,
            "fetch_html_with_browser",
            side_effect=fetch_html_with_browser,
        ),
        mock.patch.object(
            browser_preflight,
            "default_browser_workflow_deps",
            side_effect=_preflight_deps,
        ),
        mock.patch.object(
            html_extraction,
            "_cached_browser_workflow_markdown",
            side_effect=_fake_markdown(),
        ),
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
    assert (
        result.final_url == "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322"
    )
    assert result.storage_state_path == (
        tmp_path
        / "paper-fetch"
        / "publisher-browser-profiles"
        / "wiley"
        / "storage-state.json"
    )
    assert captured["publisher"] == "wiley"
    assert captured["candidate_urls"] == [
        "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
        "https://onlinelibrary.wiley.com/doi/10.1111/gcb.15322",
    ]
    runtime = captured["config"]
    assert isinstance(runtime, BrowserRuntimeConfig)
    assert (
        runtime.user_data_dir
        == tmp_path / "paper-fetch" / "publisher-browser-profiles" / "wiley"
    )
    ensure_runtime_ready.assert_called_once_with(runtime)
    runtime_env = captured["env"]
    assert isinstance(runtime_env, dict)
    assert runtime_env[CLOAKBROWSER_TIMEOUT_MS_ENV_VAR] == "45000"
    assert runtime_env[BROWSER_USER_AGENT_ENV_VAR] == "Mozilla/5.0 preflight-test"


def test_browser_preflight_uses_provider_html_candidates_for_aip(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def load_runtime_config(env, *, provider, doi):
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del publisher, config, kwargs
        captured["candidate_urls"] = list(candidate_urls)
        return BrowserFetchedHtml(
            source_url=candidate_urls[1],
            final_url=(
                "https://pubs.aip.org/aip/adv/article/12/12/125205/2820011/"
                "On-chip-on-demand-delivery-of-K-for-in-vitro"
            ),
            html="<html><body>Article body</body></html>",
            response_status=200,
            response_headers={},
            title="AIP sample",
            summary="Article body",
            browser_context_seed={},
        )

    with (
        mock.patch.object(
            browser_preflight, "load_runtime_config", side_effect=load_runtime_config
        ),
        mock.patch.object(browser_preflight, "ensure_runtime_ready"),
        mock.patch.object(
            browser_preflight,
            "fetch_html_with_browser",
            side_effect=fetch_html_with_browser,
        ),
        mock.patch.object(
            browser_preflight,
            "default_browser_workflow_deps",
            side_effect=_preflight_deps,
        ),
        mock.patch.object(
            html_extraction,
            "_cached_browser_workflow_markdown",
            side_effect=_fake_markdown("AIP sample"),
        ),
    ):
        result = browser_preflight.preflight_browser_provider(
            "aip",
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
        )

    assert result.ok is True
    assert result.provider == "aip"
    assert captured["candidate_urls"] == [
        (
            "https://pubs.aip.org/aip/adv/article/12/12/125205/2820011/"
            "On-chip-on-demand-delivery-of-K-for-in-vitro"
        ),
        "https://pubs.aip.org/doi/full/10.1063/5.0129134",
        "https://pubs.aip.org/doi/10.1063/5.0129134",
    ]


def test_browser_preflight_uses_provider_html_candidates_for_royal_society(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def load_runtime_config(env, *, provider, doi):
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del publisher, config, kwargs
        captured["candidate_urls"] = list(candidate_urls)
        return BrowserFetchedHtml(
            source_url=candidate_urls[1],
            final_url=(
                "https://royalsocietypublishing.org/rsos/article/7/10/201200/95314/"
                "Adaptation-of-the-carbamoyl-phosphate-synthetase"
            ),
            html="<html><body>Royal Society article body</body></html>",
            response_status=200,
            response_headers={},
            title="Royal Society sample",
            summary="Royal Society article body",
            browser_context_seed={},
        )

    with (
        mock.patch.object(
            browser_preflight, "load_runtime_config", side_effect=load_runtime_config
        ),
        mock.patch.object(browser_preflight, "ensure_runtime_ready"),
        mock.patch.object(
            browser_preflight,
            "fetch_html_with_browser",
            side_effect=fetch_html_with_browser,
        ),
        mock.patch.object(
            browser_preflight,
            "default_browser_workflow_deps",
            side_effect=_preflight_deps,
        ),
        mock.patch.object(
            html_extraction,
            "_cached_browser_workflow_markdown",
            side_effect=_fake_markdown("Royal Society sample"),
        ),
    ):
        result = browser_preflight.preflight_browser_provider(
            "royalsocietypublishing",
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
        )

    assert result.ok is True
    assert result.provider == "royalsocietypublishing"
    assert captured["candidate_urls"] == [
        "https://royalsocietypublishing.org/doi/10.1098/rsos.201200",
        "https://doi.org/10.1098/rsos.201200",
    ]


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

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del config, kwargs
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
        mock.patch.object(
            browser_preflight, "load_runtime_config", side_effect=load_runtime_config
        ),
        mock.patch.object(browser_preflight, "ensure_runtime_ready"),
        mock.patch.object(
            browser_preflight,
            "fetch_html_with_browser",
            side_effect=fetch_html_with_browser,
        ),
        mock.patch.object(
            browser_preflight,
            "default_browser_workflow_deps",
            side_effect=_preflight_deps,
        ),
        mock.patch.object(
            html_extraction,
            "_cached_browser_workflow_markdown",
            side_effect=_fake_markdown(),
        ),
    ):
        results = browser_preflight.run_browser_provider_preflight(
            providers=["science", "wiley"],
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
        )

    assert [result.provider for result in results] == ["science", "wiley"]
    assert results[0].ok is False
    assert results[0].reason == "cloudflare_challenge"
    assert (
        results[0].storage_state_path
        == tmp_path / "profiles" / "science" / "storage-state.json"
    )
    assert results[1].ok is True


def test_browser_preflight_does_not_use_pdf_fallback(tmp_path: Path) -> None:
    def load_runtime_config(env, *, provider, doi):
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del candidate_urls, publisher, config, kwargs
        raise BrowserRuntimeFailure(
            "publisher_access_denied",
            "Publisher denied access to the full-text page.",
        )

    def fail_pdf_fallback(*args, **kwargs):
        del args, kwargs
        raise AssertionError("browser-preflight must not run PDF fallback")

    def preflight_deps_without_pdf():
        return replace(
            _preflight_deps(),
            fetch_seeded_browser_pdf_payload=fail_pdf_fallback,
        )

    with (
        mock.patch.object(
            browser_preflight, "load_runtime_config", side_effect=load_runtime_config
        ),
        mock.patch.object(browser_preflight, "ensure_runtime_ready"),
        mock.patch.object(
            browser_preflight,
            "fetch_html_with_browser",
            side_effect=fetch_html_with_browser,
        ),
        mock.patch.object(
            browser_preflight,
            "default_browser_workflow_deps",
            side_effect=preflight_deps_without_pdf,
        ),
        mock.patch.object(
            html_extraction,
            "_cached_browser_workflow_markdown",
            side_effect=_fake_markdown(),
        ),
    ):
        result = browser_preflight.preflight_browser_provider(
            "wiley",
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
        )

    assert result.ok is False
    assert result.reason == "publisher_access_denied"


def test_browser_preflight_reports_missing_builtin_target() -> None:
    with mock.patch.dict(browser_preflight.AUTH_TARGETS, {}, clear=True):
        result = browser_preflight.preflight_browser_provider("wiley", env={})

    assert result.ok is False
    assert result.provider == "wiley"
    assert result.reason == "error"
    assert "No built-in browser preflight URL" in (result.message or "")
