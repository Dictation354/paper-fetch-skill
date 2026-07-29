from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from paper_fetch.models import ArticleModel, Metadata, Quality, Section
from paper_fetch.providers.base import ProviderFetchResult
from paper_fetch.tracing import (
    TraceContext,
    merge_trace,
    summarize_trace_attempts,
    trace_event,
)
from paper_fetch.workflow import fulltext


def test_official_provider_structured_fallback_trace_reaches_article() -> None:
    browser_failure = trace_event(
        "fulltext",
        "wiley_html",
        "fail",
        code="managed_chrome_cdp_timeout",
        message="CDP startup timed out.",
    )
    article = ArticleModel(
        doi="10.1111/gcb.16414",
        source="wiley_browser",
        metadata=Metadata(title="Wiley fallback"),
        sections=[
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="Fallback body text. " * 100,
            )
        ],
        quality=Quality(has_fulltext=True, content_kind="fulltext"),
    )

    class _Provider:
        def fetch_result(self, *_args, **_kwargs) -> ProviderFetchResult:
            return ProviderFetchResult(
                provider="wiley",
                article=article,
                trace=[browser_failure],
            )

    artifact_store = mock.Mock()
    artifact_store.asset_download_dir = None
    artifact_store.save_provider_payload.return_value = ([], [])
    artifact_store.save_provider_html_payload.return_value = ([], [])
    workflow_trace = []

    result = fulltext._try_official_provider(
        doi="10.1111/gcb.16414",
        metadata={},
        provider_name="wiley",
        strategy=fulltext.FetchStrategy(),
        artifact_store=artifact_store,
        context=SimpleNamespace(asset_profile=None),
        clients={"wiley": _Provider()},
        outputs=fulltext._ProviderAttemptOutputs(trace=workflow_trace),
    )

    assert result is article
    assert browser_failure in article.quality.trace
    assert browser_failure in workflow_trace


def test_trace_attempts_preserve_retries_and_report_provider_percentiles() -> None:
    attempts = [
        trace_event(
            "fulltext",
            "frontiers_xml",
            outcome,
            context=TraceContext(
                provider="frontiers",
                route="xml",
                attempt=index,
                attempt_id=f"xml-{index}",
                duration_ms=duration,
                target=(
                    f"https://www.frontiersin.org/article/xml?token=secret-{index}"
                ),
            ),
        )
        for index, (outcome, duration) in enumerate(
            (("fail", 10.0), ("fail", 20.0), ("ok", 100.0)),
            start=1,
        )
    ]

    merged = merge_trace(attempts[:2], attempts[2:])
    summary = summarize_trace_attempts(merged)

    assert [event.attempt_id for event in merged] == ["xml-1", "xml-2", "xml-3"]
    assert all(
        event.target == "https://www.frontiersin.org/article/xml" for event in merged
    )
    assert len({event.target_sha256 for event in merged}) == 3
    assert summary["frontiers"] == {
        "attempts": 3,
        "failures": 2,
        "failure_rate": 0.666667,
        "p50_duration_ms": 20.0,
        "p95_duration_ms": 100.0,
    }
