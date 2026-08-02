from __future__ import annotations

from paper_fetch.providers.browser_workflow.fetchers import readiness
from paper_fetch.runtime import RuntimeContext


def test_request_deadline_is_initialized_once() -> None:
    context = RuntimeContext(env={}, request_started_at=100.0)
    try:
        assert context.initialize_deadline(120.0) == 220.0
        assert context.initialize_deadline(15.0) == 220.0
    finally:
        context.close()


def test_aip_and_science_publish_current_body_readiness_selectors() -> None:
    assert readiness.atypon_body_ready_selectors("aip") == (
        ".article-body .widget-ArticleFulltext",
        ".widget-ArticleFulltext",
        ".article-body",
    )
    assert readiness.atypon_body_ready_selectors("science")[:3] == (
        "[data-extent='bodymatter']",
        "[property='articleBody']",
        "#bodymatter",
    )


def test_body_readiness_budget_includes_dom_evaluation_time(monkeypatch) -> None:
    clock = [0.0]

    class Page:
        def evaluate(self, _script, _arguments):
            clock[0] += 1.1
            return {
                "ready": False,
                "selector": None,
                "textLength": 0,
                "paragraphCount": 0,
                "headingCount": 0,
                "fingerprint": "",
            }

        def wait_for_timeout(self, milliseconds):
            clock[0] += milliseconds / 1000.0

    monkeypatch.setattr(readiness.time, "monotonic", lambda: clock[0])
    result = readiness.wait_for_atypon_body_dom_ready(
        Page(),
        "aip",
        timeout_seconds=1.0,
        poll_interval_ms=750,
    )

    assert result.attempted is True
    assert result.ready is False
    assert result.elapsed_ms == 1100
    assert clock[0] == 1.1
