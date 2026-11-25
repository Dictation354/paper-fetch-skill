from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from paper_fetch.http import RequestFailure
from paper_fetch.models import ArticleModel, Metadata, Quality, Section
from paper_fetch.providers.base import ProviderFetchResult
from paper_fetch.providers.protocols import FulltextProvider
from paper_fetch.tracing import (
    TraceContext,
    merge_trace,
    nearest_rank_percentile,
    summarize_trace_attempts,
    trace_event,
)
from paper_fetch.workflow import fulltext
from tests.support.trace import trace_facts


def test_official_provider_structured_fallback_trace_reaches_article() -> None:
    browser_failure = trace_event(
        "fulltext",
        "wiley_html",
        "fail",
        code="browser_runtime_prepare_timeout",
        message="Camoufox runtime preparation timed out.",
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

    provider = mock.Mock(spec=FulltextProvider)
    provider.fetch_result.return_value = ProviderFetchResult(
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
        clients={"wiley": provider},
        outputs=fulltext._ProviderAttemptOutputs(trace=workflow_trace),
    )

    assert result is article
    assert browser_failure in workflow_trace
    assert trace_facts(
        trace_event(
            browser_failure.stage, browser_failure.component, browser_failure.outcome
        )
    ) in trace_facts(article.trace)
    assert (
        trace_facts(article.trace).count(
            (browser_failure.stage, browser_failure.component, browser_failure.outcome)
        )
        == 1
    )
    assert not hasattr(article.quality, "trace")
    event = next(event for event in article.trace if event.outcome == "article_ok")
    assert event.duration_ms is not None and event.duration_ms >= 0


def test_official_provider_structures_exhausted_request_failure():
    provider = mock.Mock(spec=FulltextProvider)
    provider.fetch_result.side_effect = RequestFailure(
        None, "Response interrupted", error_category="connection_closed", retryable=True
    )
    outputs = fulltext._ProviderAttemptOutputs()
    assert (
        fulltext._try_official_provider(
            doi="10.1111/gcb.16414",
            metadata={},
            provider_name="wiley",
            strategy=fulltext.FetchStrategy(),
            artifact_store=mock.Mock(),
            context=SimpleNamespace(asset_profile=None),
            clients={"wiley": provider},
            outputs=outputs,
        )
        is None
    )
    (failure,) = outputs.failures
    assert failure.diagnostics.provider == "wiley"
    assert failure.diagnostics.stage == "fulltext"
    assert failure.diagnostics.error_category == "connection_closed"
    assert failure.diagnostics.retryable is True


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
    assert nearest_rank_percentile([100.0, 10.0, 20.0], 0.50) == 20.0


def test_failure_trace_keeps_http_status_and_retryability_without_error_category():
    from paper_fetch.http import RequestFailure
    from paper_fetch.providers.base import map_request_failure
    from paper_fetch.workflow.shared import events_for_failure

    for retryable in (True, False):
        failure = map_request_failure(
            RequestFailure(503, "HTTP 503", retryable=retryable)
        )
        event = events_for_failure("metadata", "crossref", failure)
        assert event.provider == "crossref" and event.stage == "metadata"
        assert event.http_status == 503 and event.retryable is retryable
        assert event.error_category is None
