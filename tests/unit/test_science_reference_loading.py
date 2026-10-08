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
    controls = bibliography.locator.return_value.filter.return_value
    controls.count.return_value = 0
    control = controls.nth.return_value
    control.is_visible.return_value = True
    control.is_enabled.return_value = True
    control.click.side_effect = lambda **kwargs: None
    page.scrolls = 0
    page.snapshot = lambda: {"available": ["R1"], "cited": ["R1", "R2", "R3"]}

    def evaluate(script):
        if "scrollIntoView" in script:
            page.scrolls += 1
            return bool(bibliography.count())
        return page.snapshot()

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
    assert result == {
        "references_before": 1,
        "references_after": 3,
        "missing_reference_targets": [],
        "timed_out": False,
    }
    assert clock.now == pytest.approx(0.4)
    assert page.scrolls == 1
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
