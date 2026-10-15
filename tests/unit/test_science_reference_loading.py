"""Science preparation contracts using only DOM snapshots and boundary mocks."""

from unittest.mock import Mock
from types import SimpleNamespace

import pytest

from paper_fetch.providers import _science_html


@pytest.fixture
def browser_boundary(monkeypatch):
    clock = Mock()
    clock.now = 0.0
    monkeypatch.setattr(
        _science_html, "time", SimpleNamespace(monotonic=lambda: clock.now)
    )
    page = Mock()
    bibliography = page.locator.return_value
    bibliography.count.return_value = 1
    controls = bibliography.locator.return_value
    controls.count.return_value = 0
    control = controls.nth.return_value.filter.return_value
    control.is_visible.return_value = True
    control.is_enabled.return_value = True
    control.click.side_effect = lambda **kwargs: None
    page.scrolls = 0
    page.snapshot = lambda: {"available": ["R1"], "cited": ["R1", "R2", "R3"]}

    def evaluate(script, *args):
        if "scrollIntoView" in script:
            page.scrolls += 1
            return bool(bibliography.count())
        data = page.snapshot()
        return {
            "reference_html": "".join(
                f'<div class="biblioentry"><div class="citations" id="{target}"><div class="citation-content">Study {target}</div></div></div>'
                for target in data["available"]
            ),
            "reference_ids": data["available"],
            "cited": data["cited"],
            "bibliography_present": bool(bibliography.count()),
            "control_index": 0 if controls.count() else -1,
        }

    def wait(milliseconds):
        assert 0 < milliseconds <= 200
        clock.now += milliseconds / 1000

    page.evaluate.side_effect = evaluate
    page.wait_for_timeout.side_effect = wait
    return page, clock, bibliography, controls, control


def test_references_arrive_in_batches(browser_boundary):
    page, clock, _, _, _ = browser_boundary
    page.snapshot = lambda: {
        "available": ["R1", "R2", "R3"][: 1 + int(clock.now / 0.2)],
        "cited": ["R1", "R2", "R3"],
    }
    result = _science_html.prepare_browser_page(page, timeout_ms=1000)
    assert {
        key: result[key]
        for key in (
            "references_before",
            "references_after",
            "missing_reference_targets",
            "timed_out",
        )
    } == {
        "references_before": 1,
        "references_after": 3,
        "missing_reference_targets": [],
        "timed_out": False,
    }
    assert clock.now == pytest.approx(0.4)
    assert page.scrolls == 1
    assert page.evaluate.call_count == 4
    page.content.assert_not_called()


def test_waits_for_delayed_bibliography(browser_boundary):
    page, clock, bibliography, _, _ = browser_boundary
    bibliography.count.side_effect = lambda: int(clock.now >= 0.2)
    page.snapshot = lambda: {
        "available": ["R1", "R2", "R3"] if clock.now >= 0.4 else [],
        "cited": ["R3"],
    }
    result = _science_html.prepare_browser_page(page, timeout_ms=1000)
    assert result["references_before"] == 0
    assert result["references_after"] == 3
    assert result["missing_reference_targets"] == []
    assert not result["timed_out"]
    bibliography.scroll_into_view_if_needed.assert_not_called()


def test_click_timeout_recovers_within_the_same_budget(browser_boundary):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    page, clock, _, controls, control = browser_boundary
    controls.count.side_effect = lambda: int(control.click.call_count < 2)

    def click(*, timeout):
        assert 0 < timeout <= 200
        if control.click.call_count == 1:
            clock.now += timeout / 1000
            raise PlaywrightTimeoutError("control moved during loading")

    control.click.side_effect = click
    page.snapshot = lambda: {
        "available": ["R1", "R2", "R3"] if control.click.call_count >= 2 else ["R1"],
        "cited": ["R3"],
    }
    result = _science_html.prepare_browser_page(page, timeout_ms=1000)
    assert result["references_after"] == 3
    assert result["missing_reference_targets"] == []
    assert not result["timed_out"]
    assert control.click.call_count == 2
    assert clock.now < 1


def test_complete_references_return_without_waiting_or_scrolling(browser_boundary):
    page, _, _, _, control = browser_boundary
    page.snapshot = lambda: {"available": ["R1"], "cited": ["R1"]}
    result = _science_html.prepare_browser_page(page, timeout_ms=1000)
    assert result["references_after"] == 1
    assert not result["timed_out"]
    assert page.scrolls == 0
    page.wait_for_timeout.assert_not_called()
    control.click.assert_not_called()


@pytest.mark.parametrize("budget", [0, 450, 20000])
def test_deadline_reports_actual_remaining_targets(browser_boundary, budget):
    page, clock, _, _, _ = browser_boundary
    page.snapshot = lambda: {
        "available": ["R1", "R2"] if clock.now >= 0.2 else ["R1"],
        "cited": ["R1", "R2", "R3"],
    }
    result = _science_html.prepare_browser_page(page, timeout_ms=budget)
    assert result["timed_out"]
    assert result["missing_reference_targets"] == (
        ["R2", "R3"] if not budget else ["R3"]
    )
    assert result["references_after"] == (2 if budget else 1)
    assert clock.now <= min(budget, 10000) / 1000
    assert clock.now >= max(0, min(budget, 10000) / 1000 - 0.001)


def test_rechecks_coverage_when_click_exhausts_budget(browser_boundary):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    page, clock, _, controls, control = browser_boundary
    controls.count.side_effect = lambda: int(clock.now == 0)

    def click(*, timeout):
        assert timeout == 100
        clock.now += timeout / 1000
        raise PlaywrightTimeoutError("action timed out after loading a batch")

    control.click.side_effect = click
    page.snapshot = lambda: {
        "available": ["R1", "R2"] if clock.now else ["R1"],
        "cited": ["R3"],
    }
    result = _science_html.prepare_browser_page(page, timeout_ms=100)
    assert result["references_after"] == 2
    assert result["missing_reference_targets"] == ["R3"]
    assert result["timed_out"]
    page.wait_for_timeout.assert_not_called()


def test_empty_reference_ids_wait_for_extractable_text(browser_boundary):
    page, clock, _, _, _ = browser_boundary
    original = page.evaluate.side_effect

    def evaluate(script, *args):
        state = original(script, *args)
        if args and clock.now < 0.4:
            state["reference_ids"] = ["R1", "R2", "R3"]
            state["reference_html"] = (
                '<div class="biblioentry"><div class="citations" id="R1"><div class="citation-content">Study R1</div></div></div>'
                + "".join(
                    f'<div class="biblioentry"><div class="citations" id="R{i}"><div class="citation-content"></div></div></div>'
                    for i in (2, 3)
                )
            )
        elif args:
            state["reference_ids"] = ["R1", "R2", "R3"]
            state["reference_html"] = "".join(
                f'<div class="biblioentry"><div class="citations" id="R{i}"><div class="citation-content">Study R{i}</div></div></div>'
                for i in (1, 2, 3)
            )
        return state

    page.evaluate.side_effect = evaluate
    result = _science_html.prepare_browser_page(page, timeout_ms=1000)
    assert result["references_before"] == 3
    assert result["extractable_references_before"] == 1
    assert result["extractable_references_after"] == 3
    assert result["empty_reference_ids"] == []
    assert clock.now == pytest.approx(0.4)


def test_cancellation_is_checked_before_browser_read(browser_boundary):
    from paper_fetch.http import RequestCancelledError

    page, _, _, _, _ = browser_boundary
    with pytest.raises(RequestCancelledError):
        _science_html.prepare_browser_page(
            page,
            timeout_ms=1000,
            cancel_check=Mock(side_effect=RequestCancelledError("cancelled")),
        )
    page.evaluate.assert_not_called()


@pytest.mark.parametrize(
    "body, missing",
    [
        ("Study seventy one", []),
        ("", ["R71"]),
        ('<a class="citation-links">Crossref</a>', ["R71"]),
    ],
)
def test_finalize_uses_actual_candidate_text_not_reference_count(body, missing):
    html = (
        '<a role="doc-biblioref" href="#R71">71</a><section id="bibliography"><div class="biblioentry"><div class="citations" id="R71"><div class="citation-content">'
        + body
        + '</div></div></div></section><div id="R99">Not a reference</div>'
    )
    _, result = _science_html.finalize_extraction(
        html, "https://www.science.org/doi/example", "Body", {}
    )
    assert result.get("missing_reference_targets", []) == missing
    assert len(result.get("references", [])) == (0 if missing else 1)


def test_cancellation_during_reference_loading_propagates(browser_boundary):
    from paper_fetch.http import RequestCancelledError

    page, clock, _, _, _ = browser_boundary

    def check():
        if clock.now >= 0.2:
            raise RequestCancelledError("cancelled while loading")

    with pytest.raises(RequestCancelledError):
        _science_html.prepare_browser_page(page, timeout_ms=1000, cancel_check=check)
    assert clock.now == pytest.approx(0.2)


def test_selected_reference_candidates_keep_their_identity_without_ancestors(
    browser_boundary,
):
    page, _, _, _, _ = browser_boundary
    page.evaluate.side_effect = None
    page.evaluate.return_value = {
        "reference_html": '<li class="ref" id="R71"><p>Actual study</p></li>',
        "reference_ids": ["R71"],
        "cited": ["R71"],
        "bibliography_present": True,
        "control_index": -1,
    }
    result = _science_html.prepare_browser_page(page, timeout_ms=0)
    assert result["extractable_references_after"] == 1
    assert not result["timed_out"]


def test_unchanged_reference_fragment_is_not_reparsed_each_poll(
    browser_boundary, monkeypatch
):
    page, _, _, _, _ = browser_boundary
    parser = Mock(wraps=_science_html.BeautifulSoup)
    monkeypatch.setattr(_science_html, "BeautifulSoup", parser)
    result = _science_html.prepare_browser_page(page, timeout_ms=600)
    assert result["timed_out"]
    assert page.evaluate.call_count == 5  # four snapshots and one scroll
    assert parser.call_count == 1
