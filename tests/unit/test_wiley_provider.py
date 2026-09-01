from __future__ import annotations

from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any
from unittest import mock

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


def test_wiley_camoufox_workflow_ignores_explicit_browser_user_agent(
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

    assert captured["browser_user_agent"] is None


def test_wiley_confirmed_403_html_passes_markdown_and_availability(
    tmp_path: Path,
) -> None:
    doi = "10.1111/gcb.16414"
    landing_url = f"https://onlinelibrary.wiley.com/doi/{doi}"
    html = golden_criteria_asset(doi, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    runtime = browser_runtime.BrowserRuntimeConfig(
        provider="wiley",
        doi=doi,
        artifact_dir=tmp_path / "artifacts",
        headless=True,
        user_agent=None,
        profile_dir=None,
        user_data_dir=None,
        storage_state_path=None,
        persist_storage_state=False,
    )
    browser_html = browser_runtime.BrowserFetchedHtml(
        source_url=landing_url,
        final_url=landing_url,
        html=html,
        response_status=403,
        response_headers={"content-type": "text/html"},
        title="Global Change Biology",
        summary="Wiley article body",
        browser_context_seed={},
        diagnostics={
            "browser_runtime_trace": {
                "candidates": [
                    {
                        "status": 403,
                        "result": "success",
                        "http_access_status_review": {
                            "status": 403,
                            "body_ready": True,
                            "doi_evidence_present": True,
                            "doi_evidence_sources": ["citation_meta"],
                            "doi_match": True,
                            "doi_match_sources": ["citation_meta"],
                            "blocking_signals": [],
                            "candidate_confirmed": True,
                            "status_override_applied": True,
                            "fulltext_acceptance": "pending",
                            "accepted": False,
                            "reason": "pending_fulltext_acceptance",
                        },
                    }
                ]
            }
        },
    )
    html_fetch = mock.Mock(return_value=browser_html)
    pdf_fetch = mock.Mock()
    deps = replace(
        default_browser_workflow_deps(),
        load_runtime_config=mock.Mock(return_value=runtime),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=html_fetch,
        fetch_seeded_browser_pdf_payload=pdf_fetch,
    )
    client = wiley_provider.WileyClient(transport=None, env={}, deps=deps)
    context = RuntimeContext(env={})
    try:
        raw_payload = client.fetch_raw_fulltext(
            doi,
            {"doi": doi, "landing_page_url": landing_url},
            context=context,
        )
    finally:
        context.close()

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "html"
    diagnostics = raw_payload.content.diagnostics
    assert diagnostics["availability_diagnostics"]["accepted"] is True
    assert diagnostics["html_attempts"][0]["response_status"] == 403
    review = diagnostics["browser_runtime_trace"]["candidates"][0][
        "http_access_status_review"
    ]
    assert review["status"] == 403
    assert review["accepted"] is True
    assert review["fulltext_acceptance"] == "accepted"
    assert review["reason"] == "fulltext_accepted"
    html_fetch.assert_called_once()
    pdf_fetch.assert_not_called()
    assert not list(tmp_path.rglob("storage-state.json"))


def test_wiley_confirmed_403_extraction_failure_continues_next_candidate(
    tmp_path: Path,
) -> None:
    doi = "10.1111/gcb.16414"
    landing_url = f"https://onlinelibrary.wiley.com/doi/{doi}"
    full_url = f"https://onlinelibrary.wiley.com/doi/full/{doi}"
    accepted_html = golden_criteria_asset(doi, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    runtime = browser_runtime.BrowserRuntimeConfig(
        provider="wiley",
        doi=doi,
        artifact_dir=tmp_path / "artifacts",
        headless=True,
        user_agent=None,
        profile_dir=None,
        user_data_dir=None,
        storage_state_path=None,
        persist_storage_state=False,
    )
    provisional_review = {
        "status": 403,
        "body_ready": True,
        "doi_evidence_present": True,
        "doi_evidence_sources": ["citation_meta"],
        "doi_match": True,
        "doi_match_sources": ["citation_meta"],
        "blocking_signals": [],
        "candidate_confirmed": True,
        "status_override_applied": True,
        "fulltext_acceptance": "pending",
        "accepted": False,
        "reason": "pending_fulltext_acceptance",
    }
    first_result = browser_runtime.BrowserFetchedHtml(
        source_url=landing_url,
        final_url=landing_url,
        html=(
            "<html><head><meta name='citation_doi' "
            f"content='{doi}'><title>Article</title></head>"
            "<body><main>Short shell</main></body></html>"
        ),
        response_status=403,
        response_headers={"content-type": "text/html"},
        title="Article",
        summary="Short shell",
        browser_context_seed={},
        diagnostics={
            "browser_runtime_trace": {
                "candidate_count": 3,
                "navigation_count": 1,
                "candidates": [
                    {
                        "url": landing_url,
                        "status": 403,
                        "result": "success",
                        "http_access_status_review": provisional_review,
                    }
                ],
            }
        },
    )
    second_result = browser_runtime.BrowserFetchedHtml(
        source_url=full_url,
        final_url=full_url,
        html=accepted_html,
        response_status=200,
        response_headers={"content-type": "text/html"},
        title="Global Change Biology",
        summary="Wiley article body",
        browser_context_seed={},
        diagnostics={
            "browser_runtime_trace": {
                "candidate_count": 2,
                "navigation_count": 1,
                "candidates": [
                    {
                        "url": full_url,
                        "status": 200,
                        "result": "success",
                    }
                ],
            }
        },
    )
    html_fetch = mock.Mock(side_effect=[first_result, second_result])
    pdf_fetch = mock.Mock()
    deps = replace(
        default_browser_workflow_deps(),
        load_runtime_config=mock.Mock(return_value=runtime),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=html_fetch,
        fetch_seeded_browser_pdf_payload=pdf_fetch,
    )
    client = wiley_provider.WileyClient(transport=None, env={}, deps=deps)
    context = RuntimeContext(env={})
    try:
        raw_payload = client.fetch_raw_fulltext(
            doi,
            {"doi": doi, "landing_page_url": landing_url},
            context=context,
        )
    finally:
        context.close()

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "html"
    assert raw_payload.content.source_url == full_url
    assert html_fetch.call_count == 2
    first_candidates = html_fetch.call_args_list[0].args[0]
    second_candidates = html_fetch.call_args_list[1].args[0]
    assert first_candidates[0] == landing_url
    assert second_candidates == first_candidates[1:]
    diagnostics = raw_payload.content.diagnostics
    candidates = diagnostics["browser_runtime_trace"]["candidates"]
    assert [candidate["status"] for candidate in candidates] == [403, 200]
    assert candidates[0]["result"] == "extraction_failure"
    rejected_review = candidates[0]["http_access_status_review"]
    assert rejected_review["fulltext_acceptance"] == "rejected"
    assert rejected_review["accepted"] is False
    assert candidates[1]["result"] == "success"
    attempts = diagnostics["html_attempts"]
    assert [attempt["result"] for attempt in attempts] == [
        "extraction_failure",
        "success",
    ]
    assert attempts[0]["candidate_continuation"] is True
    pdf_fetch.assert_not_called()
