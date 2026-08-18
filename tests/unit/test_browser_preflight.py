from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from paper_fetch import browser_preflight
from paper_fetch.providers import _playwright_browser
from paper_fetch.config import (
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    XDG_DATA_HOME_ENV_VAR,
)
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)
from paper_fetch.providers.base import ProviderStatusResult, build_provider_status_check
from paper_fetch.providers.browser_workflow import html_extraction
from paper_fetch.providers.browser_workflow.shared import default_browser_workflow_deps


@pytest.mark.parametrize(
    ("reason_code", "stage", "expected"),
    [
        ("request_cancelled", None, "cancelled"),
        ("browser_runtime_prepare_cancelled", "runtime_prepare", "cancelled"),
        ("aws_waf_challenge", "page", "challenge"),
        ("cloudflare_challenge", "page", "challenge"),
        ("publisher_access_denied", "availability", "auth_required"),
        ("browser_connect_timeout", "browser_connect", "network_timeout"),
        ("article_container_not_found", "html_extraction", "extraction_error"),
        ("empty_article_shell", "html_extraction", "extraction_error"),
        ("managed_chrome_cdp_timeout", "managed_chrome_startup", "runtime_error"),
        ("unknown_html_failure", "html_extraction", "extraction_error"),
        ("unknown_runtime_failure", "browser_context_create", "runtime_error"),
    ],
)
def test_preflight_failure_classification_is_code_and_stage_driven(
    reason_code,
    stage,
    expected,
) -> None:
    assert (
        browser_preflight.classify_browser_preflight_failure(
            reason_code,
            stage=stage,
        )
        == expected
    )


def _runtime_config(tmp_path: Path, *, provider: str, doi: str) -> BrowserRuntimeConfig:
    return BrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=tmp_path / "artifacts" / provider,
        headless=True,
        user_agent=None,
        backend="camoufox",
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


def test_static_browser_capabilities_never_claims_live_health() -> None:
    status = ProviderStatusResult(
        provider="wiley",
        status="ready",
        available=True,
        official_provider=True,
        checks=[
            build_provider_status_check(
                "runtime_env",
                "ok",
                "configured",
                details={
                    "cdp_endpoint_configured": True,
                    "binary_path_configured": False,
                    "auto_cdp_browser_enabled": False,
                },
            ),
            build_provider_status_check(
                "playwright_dependency",
                "ok",
                "dependencies import",
                details={"packages": {"playwright": True, "camoufox": True}},
            ),
        ],
    )

    with mock.patch.object(
        browser_preflight, "probe_runtime_status", return_value=status
    ):
        report = browser_preflight.static_browser_capabilities({}, provider="wiley")

    assert report["live_checked"] is False
    assert report["publisher_page_checked"] is False
    assert report["playwright"]["available"] is True
    assert report["camoufox"]["available"] is True
    assert report["chrome_cdp"]["status"] == "configured"
    assert report["chrome_cdp"]["reason_code"] == ("cdp_endpoint_configured_not_probed")
    assert report["chrome_cdp"]["connection_checked"] is False


def test_browser_preflight_adds_provider_storage_path_for_camoufox(
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
            runtime_options=browser_preflight.BrowserPreflightRuntimeOptions(
                env={
                    XDG_DATA_HOME_ENV_VAR: str(tmp_path),
                }
            ),
        )

    assert len(results) == 1
    result = results[0]
    assert result.ready is True
    assert result.provider == "wiley"
    assert (
        result.final_url == "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322"
    )
    assert result.storage_state_path == (
        tmp_path
        / "paper-fetch"
        / "publisher-browser-profiles"
        / "wiley-camoufox"
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
        == tmp_path / "paper-fetch" / "publisher-browser-profiles" / "wiley-camoufox"
    )
    ensure_runtime_ready.assert_called_once_with(runtime)
    runtime_env = captured["env"]
    assert isinstance(runtime_env, dict)
    assert runtime_env[BROWSER_TIMEOUT_MS_ENV_VAR] == "45000"
    assert BROWSER_USER_AGENT_ENV_VAR not in runtime_env


def test_wiley_preflight_accepts_leading_login_navigation_after_body_readiness(
    tmp_path: Path,
) -> None:
    body = "".join(
        "<p>Paragraph "
        f"{index}. "
        + ("Substantive scientific article content with methods and results. " * 10)
        + "</p>"
        for index in range(12)
    )
    html = (
        "<html><head><title>Open access article</title>"
        "<meta name='citation_title' content='Open access article'>"
        "<meta name='citation_doi' content='10.1111/gcb.15322'>"
        '<script>window.adobeDataLayer = [{"content": {"item": '
        '{"access": "yes", "format-viewed": "full"}}, '
        '"page": {"tertiary-section": "full"}}];</script></head>'
        "<body><nav>Login / Register Individual login Institutional login "
        "Open Access</nav><article><section class='article-section__content en main'>"
        f"<h2>Introduction</h2>{body}</section></article></body></html>"
    )

    class Response:
        status = 200
        headers = {"content-type": "text/html"}

        def all_headers(self):
            return dict(self.headers)

    class Page:
        def __init__(self) -> None:
            self.url = "about:blank"
            self.route_handler = None

        def goto(self, url, **_kwargs):
            self.url = url
            return Response()

        def route(self, _pattern, handler):
            self.route_handler = handler

        def content(self):
            return html

        def title(self):
            return "Open access article"

        def evaluate(self, _script):
            return "Mozilla/5.0 Firefox/152.0"

        def close(self):
            return None

    class Context:
        def __init__(self) -> None:
            self.page = Page()

        def new_page(self):
            return self.page

        def cookies(self, _urls=None):
            return []

        def close(self):
            return None

    runtime = replace(
        _runtime_config(tmp_path, provider="wiley", doi="10.1111/gcb.15322"),
        persist_storage_state=False,
    )
    context = Context()

    def fetch_html_with_playwright(*args, warm_wait_seconds=None, **kwargs):
        del warm_wait_seconds
        return _playwright_browser.fetch_html_with_playwright(*args, **kwargs)

    with (
        mock.patch.object(
            browser_preflight,
            "load_runtime_config",
            return_value=runtime,
        ),
        mock.patch.object(browser_preflight, "ensure_runtime_ready"),
        mock.patch.object(
            browser_preflight,
            "fetch_html_with_browser",
            side_effect=fetch_html_with_playwright,
        ),
        mock.patch.object(
            _playwright_browser,
            "open_browser_context",
            return_value=(None, context),
        ),
        mock.patch.object(
            _playwright_browser,
            "wait_for_atypon_body_dom_ready",
            return_value=SimpleNamespace(
                attempted=True,
                ready=True,
                selector="section.article-section__content",
                text_length=7600,
                paragraph_count=12,
                heading_count=1,
            ),
        ),
    ):
        result = browser_preflight.preflight_browser_provider(
            "wiley",
            env={},
            save_storage_state=False,
        )

    assert result.status == "ready", (result.message, result.diagnostics)
    assert result.reason_code == "browser_preflight_ready"
    trace = result.diagnostics["browser_runtime_trace"]
    assert trace["candidates"][0]["dom_readiness_ready"] is True


def test_browser_preflight_uses_custom_target_and_disables_storage_write(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    state_path = tmp_path / "state with spaces" / "wiley.json"
    target_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/custom.123"

    def load_runtime_config(env, *, provider, doi):
        del env
        captured["doi"] = doi
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del kwargs
        captured["candidate_urls"] = list(candidate_urls)
        captured["publisher"] = publisher
        captured["config"] = config
        return BrowserFetchedHtml(
            source_url=candidate_urls[0],
            final_url=candidate_urls[0],
            html="<html><body>Article body</body></html>",
            response_status=200,
            response_headers={},
            title="Custom sample",
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
            side_effect=_fake_markdown("Custom sample"),
        ),
    ):
        result = browser_preflight.preflight_browser_provider(
            "wiley",
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
            target_url=target_url,
            storage_state_path=state_path,
            save_storage_state=False,
        )

    assert result.ready is True
    assert result.target_url == target_url
    assert result.storage_state_path == state_path
    assert captured["doi"] == "10.1111/custom.123"
    assert captured["publisher"] == "wiley"
    candidate_urls = captured["candidate_urls"]
    assert isinstance(candidate_urls, list)
    assert candidate_urls[0] == target_url
    runtime = captured["config"]
    assert isinstance(runtime, BrowserRuntimeConfig)
    assert runtime.storage_state_path == state_path
    assert runtime.user_data_dir is None
    assert runtime.profile_dir is None
    assert runtime.persist_storage_state is False


def test_ieee_preflight_requires_matching_article_with_full_readiness_window(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def load_runtime_config(env, *, provider, doi):
        del env
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del config
        captured["candidate_urls"] = list(candidate_urls)
        captured["publisher"] = publisher
        captured.update(kwargs)
        return BrowserFetchedHtml(
            source_url=candidate_urls[0],
            final_url=candidate_urls[0],
            html=("<html><body><article id='article'>10772041</article></body></html>"),
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="IEEE article",
            summary="10772041",
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
    ):
        result = browser_preflight.preflight_browser_provider(
            "ieee",
            env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
            save_storage_state=False,
        )

    assert result.ready is True
    readiness = captured["readiness"]
    assert isinstance(readiness, browser_preflight.BrowserHtmlReadiness)
    assert readiness.selector == "#article"
    assert readiness.selector_text == "10772041"
    assert readiness.require_selector is True
    assert captured["wait_seconds"] == 15


def test_preflight_preserves_captured_page_diagnostic_without_artifact_file(
    tmp_path: Path,
) -> None:
    captured_page = {
        "failure_code": "aws_waf_challenge",
        "raw_html": {"byte_count": 2058, "sha256": "a" * 64},
        "html_shape": {"tag_counts": {"script": 3, "noscript": 1}},
        "diagnostic_path": None,
    }
    runtime = browser_preflight.RuntimeContext(
        env={},
        download_dir=tmp_path,
        artifact_mode="none",
    )
    try:
        with mock.patch.object(
            browser_preflight,
            "capture_page_diagnostic",
            side_effect=AssertionError("must not replace the captured page"),
        ):
            result = browser_preflight._failure_result(
                "ieee",
                target_url="https://ieeexplore.ieee.org/document/10772041/",
                reason_code="aws_waf_challenge",
                stage="selector_readiness",
                diagnostics={
                    "challenge_provider": "aws_waf",
                    "legacy_reason_code": "cloudflare_challenge",
                    "failure_diagnostic": captured_page,
                },
                diagnostic_context=runtime,
            )
    finally:
        runtime.close()

    assert result.status == "challenge"
    assert result.diagnostics is not None
    assert result.diagnostics["failure_diagnostic"] == captured_page
    assert result.diagnostics["challenge_provider"] == "aws_waf"


def test_browser_preflight_uses_provider_html_candidates_for_aip(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def load_runtime_config(env, *, provider, doi):
        return _runtime_config(tmp_path, provider=provider, doi=doi)

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del publisher, kwargs
        captured["candidate_urls"] = list(candidate_urls)
        captured["persist_storage_state"] = config.persist_storage_state
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

    assert result.ready is True
    assert result.provider == "aip"
    assert result.storage_state_path is None
    assert captured["candidate_urls"] == [
        (
            "https://pubs.aip.org/aip/adv/article/12/12/125205/2820011/"
            "On-chip-on-demand-delivery-of-K-for-in-vitro"
        ),
        "https://pubs.aip.org/doi/full/10.1063/5.0129134",
        "https://pubs.aip.org/doi/10.1063/5.0129134",
    ]
    assert captured["persist_storage_state"] is False


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

    assert result.ready is True
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
            backend="camoufox",
            user_data_dir=tmp_path / "profiles" / provider,
        )

    def fetch_html_with_browser(candidate_urls, *, publisher, config, **kwargs):
        del config, kwargs
        if publisher == "science":
            raise BrowserRuntimeFailure(
                "managed_chrome_exited_before_cdp",
                "Managed Chrome exited before CDP was ready.",
                details={
                    "browser_failure": {
                        "stage": "managed_chrome_startup",
                        "exit_code": 12,
                        "stderr_summary": "profile startup failed",
                    }
                },
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
            runtime_options=browser_preflight.BrowserPreflightRuntimeOptions(
                env={XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
                download_dir=tmp_path / "preflight-output",
                artifact_mode="all",
            ),
        )

    assert [result.provider for result in results] == ["science", "wiley"]
    assert results[0].ready is False
    assert results[0].status == "runtime_error"
    assert results[0].reason_code == "managed_chrome_exited_before_cdp"
    assert results[0].diagnostics is not None
    assert results[0].diagnostics["browser_failure"]["exit_code"] == 12
    diagnostic_path = Path(results[0].diagnostics["diagnostic_path"])
    assert diagnostic_path.is_file()
    diagnostic = results[0].diagnostics["failure_diagnostic"]
    assert diagnostic["stage"] == "managed_chrome_startup"
    assert diagnostic["raw_html"] is None
    assert (
        results[0].storage_state_path
        == tmp_path / "profiles" / "science" / "storage-state.json"
    )
    assert results[1].ready is True


def test_browser_preflight_cancellation_keeps_completed_provider_result() -> None:
    cancelled = False
    progress: list[tuple[str, int, int]] = []

    def fake_preflight(provider, **_kwargs):
        return browser_preflight.BrowserPreflightResult(
            provider=provider,
            provider_label=provider.upper(),
            status="ready",
            reason_code="browser_preflight_ready",
        )

    def on_result(result, completed, total):
        nonlocal cancelled
        progress.append((result.provider, completed, total))
        if result.provider == "science":
            cancelled = True

    with mock.patch.object(
        browser_preflight,
        "preflight_browser_provider",
        side_effect=fake_preflight,
    ):
        results = browser_preflight.run_browser_provider_preflight(
            providers=["science", "wiley", "pnas"],
            cancel_check=lambda: cancelled,
            cancel_as_result=True,
            on_result=on_result,
            runtime_options=browser_preflight.BrowserPreflightRuntimeOptions(env={}),
        )

    assert [result.provider for result in results] == ["science", "wiley"]
    assert results[0].ready is True
    assert results[1].ready is False
    assert results[1].status == "cancelled"
    assert results[1].reason_code == "request_cancelled"
    assert progress == [("science", 1, 3), ("wiley", 2, 3)]


def test_browser_preflight_stops_after_runtime_preparation_cancellation() -> None:
    progress: list[tuple[str, int, int]] = []

    def fake_preflight(provider, **_kwargs):
        return browser_preflight.BrowserPreflightResult(
            provider=provider,
            provider_label=provider.title(),
            status="cancelled",
            reason_code="browser_runtime_prepare_cancelled",
        )

    with mock.patch.object(
        browser_preflight,
        "preflight_browser_provider",
        side_effect=fake_preflight,
    ):
        results = browser_preflight.run_browser_provider_preflight(
            providers=["science", "wiley"],
            cancel_as_result=True,
            on_result=lambda result, completed, total: progress.append(
                (result.provider, completed, total)
            ),
            runtime_options=browser_preflight.BrowserPreflightRuntimeOptions(env={}),
        )

    assert [result.provider for result in results] == ["science"]
    assert progress == [("science", 1, 2)]


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

    assert result.ready is False
    assert result.status == "auth_required"
    assert result.reason_code == "publisher_access_denied"


def test_browser_preflight_reports_missing_builtin_target() -> None:
    with mock.patch.dict(browser_preflight.AUTH_TARGETS, {}, clear=True):
        result = browser_preflight.preflight_browser_provider("wiley", env={})

    assert result.ready is False
    assert result.provider == "wiley"
    assert result.reason_code == "error"
    assert "No built-in browser preflight URL" in (result.message or "")
