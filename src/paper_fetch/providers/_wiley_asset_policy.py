"""Wiley preview provenance and acceptance annotations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ..utils import normalize_text
from .browser_workflow.asset_download import _matching_failure, _attempt_from_failure

from .browser_workflow.fetchers.readiness import wait_for_atypon_body_dom_ready


def _wiley_link(page, urls, remaining_ms, set_phase):
    readiness = wait_for_atypon_body_dom_ready(
        page, "wiley", timeout_seconds=remaining_ms() / 1000.0
    )
    if not readiness.ready:
        raise ValueError("article_not_ready")
    set_phase("panel_not_ready")
    supporting = page.locator("section.article-section__supporting").first
    supporting.wait_for(state="attached", timeout=remaining_ms())
    selectors: list[str] = []
    for url in urls:
        parsed = urlsplit(url)
        relative = urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))
        selectors.extend(f"a[href={json.dumps(value)}]" for value in (url, relative))
    link = supporting.locator(", ".join(selectors)).first
    set_phase("link_missing")
    link.wait_for(state="attached", timeout=remaining_ms())
    panel = link.locator(
        "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' accordion ')][1]"
    )
    set_phase("panel_not_ready")
    for attempt in range(3):
        if link.is_visible():
            break
        control = panel.locator("a.accordion__control").first
        if (
            control.get_attribute("aria-expanded", timeout=min(5000, remaining_ms()))
            != "true"
        ):
            control.click(timeout=min(5000, remaining_ms()))
        try:
            link.wait_for(state="visible", timeout=min(5000, remaining_ms()))
            break
        except Exception:
            if attempt == 2:
                raise
    return link


def activate_wiley_supplement(page, link, remaining_ms):
    if link.get_attribute("target", timeout=remaining_ms()) != "_blank":
        link.evaluate("(node) => node.click()", timeout=remaining_ms())
    else:
        link.click(no_wait_after=True, timeout=remaining_ms())


def annotate_wiley_preview(
    result: Mapping[str, Any],
    *,
    direct_failures: list[dict[str, Any]],
    browser_failures: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    assets = [dict(asset) for asset in list(result.get("assets") or [])]
    failures = [dict(failure) for failure in list(result.get("asset_failures") or [])]

    for outcome, recovered in [
        *((asset, True) for asset in assets),
        *((failure, False) for failure in failures),
    ]:
        if outcome.get("kind") != "figure":
            continue
        browser_failure = _matching_failure(outcome, browser_failures)
        browser_backend = normalize_text(
            str(
                outcome.get("browser_backend")
                or (browser_failure or {}).get("browser_backend")
                or ""
            )
        )
        attempts: list[dict[str, Any]] = list(outcome.get("recovery_attempts") or [])
        if browser_failure is not None:
            attempts.append(
                _attempt_from_failure(
                    "full_size",
                    browser_failure,
                    browser_backend=browser_backend,
                )
            )
        if recovered:
            outcome["download_tier"] = "preview"
            outcome["preview_accepted"] = False
            final_fetcher = normalize_text(
                str(
                    outcome.get("final_fetcher")
                    or browser_backend
                    or "selected_browser"
                )
            )
            attempts.append(
                {
                    key: value
                    for key, value in {
                        "stage": "preview_fallback",
                        "provider": "wiley",
                        "browser_backend": browser_backend or None,
                        "content_type": outcome.get("content_type"),
                        "reason": "recovered",
                        "final_fetcher": final_fetcher,
                    }.items()
                    if value not in (None, "")
                }
            )
        else:
            attempts.append(
                _attempt_from_failure(
                    "preview_fallback",
                    outcome,
                    browser_backend=browser_backend,
                )
            )
        if attempts:
            outcome["recovery_attempts"] = attempts

    return {"assets": assets, "asset_failures": failures}
