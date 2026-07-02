from __future__ import annotations

from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any

from paper_fetch import config
from paper_fetch.providers import browser_runtime
from paper_fetch.providers.browser_workflow.shared import default_browser_workflow_deps
from paper_fetch.providers import wiley as wiley_provider
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset


MARKDOWN_REVIEWED_FIXTURES = {
    "structure": "10.1111_gcb.16414",
    "table": "10.1111_cas.16395",
    "formula": "10.1111_gcb.15322",
    "figure": "10.1111_gcb.16414",
    "supplementary": "10.1111_gcb.16414",
    "references": "10.1111_gcb.16998",
    "pdf_fallback": "10.1111_cas.16395",
    "abstract_only": "10.1111_gcb.16998",
}


@cache
def _extract_fixture_markdown(doi: str) -> tuple[str, dict[str, Any]]:
    client = wiley_provider.WileyClient(transport=None, env={})
    html = golden_criteria_asset(doi, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    return client.extract_markdown(
        html,
        f"https://onlinelibrary.wiley.com/doi/full/{doi}",
        metadata={"doi": doi, "title": ""},
    )


def test_markdown_review_loop_structure_figure_and_supplementary_fixture() -> None:
    markdown, extraction = _extract_fixture_markdown("10.1111/gcb.16414")

    assert "## Abstract" in markdown
    assert "## 1 INTRODUCTION" in markdown
    assert "**Figure 1.** Conceptual diagram of velocity" in markdown
    assert "DATA AVAILABILITY STATEMENT" in markdown
    assert len(extraction["references"]) >= 50
    assert "Open in figure viewer" not in markdown
    assert "PowerPoint" not in markdown


def test_markdown_review_loop_table_and_pdf_fallback_fixture() -> None:
    markdown, extraction = _extract_fixture_markdown("10.1111/cas.16395")

    assert "## 1 INTRODUCTION" in markdown
    assert "**Table 1.** AI-SaMD approved as a medical device" in markdown
    assert "| Research area" in markdown
    assert len(extraction["references"]) >= 80
    assert "Open in figure viewer" not in markdown
    assert "PowerPoint" not in markdown


def test_markdown_review_loop_formula_references_and_abstract_only_fixture() -> None:
    formula_markdown, _ = _extract_fixture_markdown("10.1111/gcb.15322")
    references_markdown, references_extraction = _extract_fixture_markdown(
        "10.1111/gcb.16998"
    )

    assert "![Formula]" in formula_markdown
    assert "## Abstract" in references_markdown
    assert len(references_extraction["references"]) >= 70
    assert "Drought thresholds" in references_markdown
    assert "Open in figure viewer" not in references_markdown
    assert "PowerPoint" not in references_markdown


def test_wiley_browser_workflow_does_not_force_default_http_user_agent(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_fetch_html_with_browser(_candidate_urls, *, config, **_kwargs):
        captured["browser_user_agent"] = config.user_agent
        raise browser_runtime.BrowserRuntimeFailure("forced_stop", "stop")

    deps = replace(
        default_browser_workflow_deps(),
        ensure_runtime_ready=lambda _runtime: None,
        fetch_html_with_browser=fake_fetch_html_with_browser,
    )
    env = {
        config.CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR: "ws://127.0.0.1:9222/devtools/browser/test",
        config.XDG_DATA_HOME_ENV_VAR: str(tmp_path),
    }
    client = wiley_provider.WileyClient(transport=None, env=env, deps=deps)

    result = deps.bootstrap_browser_workflow(
        client,
        "10.1029/2023JD040418",
        {
            "doi": "10.1029/2023JD040418",
            "landing_page_url": "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023JD040418",
        },
        allow_runtime_failure=True,
        context=RuntimeContext(env=env),
        deps=deps,
    )

    assert result.html_failure_reason == "forced_stop"
    assert captured["browser_user_agent"] is None


def test_wiley_browser_workflow_uses_explicit_browser_user_agent(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    chrome_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    )

    def fake_fetch_html_with_browser(_candidate_urls, *, config, **_kwargs):
        captured["browser_user_agent"] = config.user_agent
        raise browser_runtime.BrowserRuntimeFailure("forced_stop", "stop")

    deps = replace(
        default_browser_workflow_deps(),
        ensure_runtime_ready=lambda _runtime: None,
        fetch_html_with_browser=fake_fetch_html_with_browser,
    )
    env = {
        config.CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR: "ws://127.0.0.1:9222/devtools/browser/test",
        config.XDG_DATA_HOME_ENV_VAR: str(tmp_path),
        config.BROWSER_USER_AGENT_ENV_VAR: chrome_user_agent,
    }
    client = wiley_provider.WileyClient(transport=None, env=env, deps=deps)

    deps.bootstrap_browser_workflow(
        client,
        "10.1029/2023JD040418",
        {
            "doi": "10.1029/2023JD040418",
            "landing_page_url": "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023JD040418",
        },
        allow_runtime_failure=True,
        context=RuntimeContext(env=env),
        deps=deps,
    )

    assert captured["browser_user_agent"] == chrome_user_agent
