from __future__ import annotations

from paper_fetch.providers.browser_workflow.fetchers import readiness
from paper_fetch import runtime as runtime_module
from paper_fetch.runtime import RuntimeContext


def test_request_deadline_is_initialized_once() -> None:
    context = RuntimeContext(env={}, request_started_at=100.0)
    try:
        assert context.initialize_deadline(120.0) == 220.0
        assert context.initialize_deadline(15.0) == 220.0
    finally:
        context.close()


def test_reset_request_deadline_preserves_item_state_and_shared_transport(
    monkeypatch,
) -> None:
    shared_transport = object()
    context = RuntimeContext(
        env={},
        transport=shared_transport,
        request_started_at=100.0,
        deadline_monotonic=220.0,
    )
    context.set_session_cache(("resolved_query", "title"), {"doi": "10.1000/test"})
    monkeypatch.setattr(runtime_module.time, "monotonic", lambda: 300.0)

    try:
        context.reset_request_deadline()

        assert context.request_started_at == 300.0
        assert context.deadline_monotonic is None
        assert context.initialize_deadline(120.0) == 420.0
        assert context.remaining_seconds() == 120.0
        assert context.transport is shared_transport
        assert context.get_session_cache(("resolved_query", "title")) == {
            "doi": "10.1000/test"
        }
    finally:
        context.close()


def test_provider_body_readiness_selectors_match_current_parser_containers() -> None:
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
    assert readiness.atypon_body_ready_selectors("mdpi") == (
        ".html-article-content",
        "#article-contents",
        ".prose-article",
    )
    assert readiness.atypon_body_ready_selectors("royalsocietypublishing") == (
        ".widget-ArticleFulltext .article-body",
        ".widget-ArticleFulltext",
        ".article-body",
        ".article-content",
    )
    assert readiness.atypon_body_ready_selectors("pnas") == (
        "#bodymatter [data-extent='bodymatter'][property='articleBody']",
        "#bodymatter [property='articleBody']",
        "#bodymatter [data-extent='bodymatter']",
        "#bodymatter",
    )
    assert ".core-container" not in readiness.atypon_body_ready_selectors("pnas")


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


def test_wiley_body_readiness_requires_two_identical_ready_fingerprints(
    monkeypatch,
) -> None:
    clock = [0.0]
    payloads = [
        {
            "ready": True,
            "selector": "section.article-section__content",
            "textLength": 4200,
            "paragraphCount": 4,
            "headingCount": 1,
            "fingerprint": "stable-body",
        },
        {
            "ready": True,
            "selector": "section.article-section__content",
            "textLength": 4200,
            "paragraphCount": 4,
            "headingCount": 1,
            "fingerprint": "stable-body",
        },
    ]

    class Page:
        def evaluate(self, _script, _arguments):
            return payloads.pop(0)

        def wait_for_timeout(self, milliseconds):
            clock[0] += milliseconds / 1000.0

    monkeypatch.setattr(readiness.time, "monotonic", lambda: clock[0])

    result = readiness.wait_for_atypon_body_dom_ready(
        Page(),
        "wiley",
        timeout_seconds=2.0,
        poll_interval_ms=750,
    )

    assert result.ready is True
    assert result.fingerprint == "stable-body"
    assert payloads == []
    assert clock[0] == 0.75
