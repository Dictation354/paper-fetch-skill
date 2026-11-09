"""Unified managed navigation and bounded challenge recovery in one context."""

from __future__ import annotations

import contextlib
import re
import time

from .byparr_adapter import supported_challenge


def navigator_for(page):
    return getattr(getattr(page, "context", None), "__dict__", {}).get(
        "_paper_fetch_navigator"
    )


def navigate_page(
    page, url: str, *, timeout_ms: int | None = None, mode="html", **kwargs
):
    timeout_ms = timeout_ms if timeout_ms is not None else kwargs.pop("timeout", 30000)
    navigator = navigator_for(page)
    if navigator is not None:
        return navigator.navigate(page, url, timeout_ms, mode=mode, **kwargs)
    return page.goto(url, timeout=timeout_ms, **kwargs)


def settle_page_navigation(page, *, timeout_ms):
    navigator = navigator_for(page)
    if navigator is not None:
        navigator.settle(page, timeout_ms=timeout_ms)


@contextlib.contextmanager
def managed_action(page, *, timeout_ms, mode="file"):
    navigator = navigator_for(page)
    if navigator is None:
        yield
    else:
        with navigator.action(page, timeout_ms=timeout_ms, mode=mode):
            yield


def _challenge_payload(*, body=b"", headers=None, title=""):
    html = (
        body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    )
    if not title:
        match = re.search(r"<title\b[^>]*>(.*?)</title>", html, re.I | re.S)
        title = match[1] if match else ""
    return supported_challenge(title=title, html=html, headers=headers)


def _recover(context, url, *, deadline, page=None):
    navigator = getattr(context, "__dict__", {}).get("_paper_fetch_navigator")
    if navigator is None:
        return False
    remaining_ms = int((deadline - time.monotonic()) * 1000)
    if remaining_ms <= 0:
        return False
    # Preserve an article/seed page used by the caller. The recovery page shares
    # its context, cookies and original request budget; no context is launched.
    recovery = context.new_page()
    try:
        navigate_page(
            recovery, url, timeout_ms=remaining_ms, wait_until="commit", mode="file"
        )
        return True
    finally:
        recovery.close()


def context_get(context, url, *, timeout=30000, page=None, **kwargs):
    deadline = time.monotonic() + timeout / 1000
    navigator = getattr(context, "__dict__", {}).get("_paper_fetch_navigator")
    get = (
        navigator.context_request_get
        if navigator is not None
        and getattr(navigator, "_invisible_session", None) is not None
        else context.request.get
    )
    response = get(url, timeout=timeout, **kwargs)
    if navigator is None:
        return response
    headers = response.headers
    if "html" not in headers.get(
        "content-type", ""
    ).lower() and not supported_challenge(headers=headers):
        return response
    if _challenge_payload(body=response.body(), headers=headers) and _recover(
        context, url, deadline=deadline, page=page
    ):
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining > 0:
            response = get(url, timeout=remaining, **kwargs)
    return response


def recover_get_result(page, url, result, *, deadline):
    if not isinstance(result, dict) or navigator_for(page) is None:
        return False
    if not _challenge_payload(
        body=result.get("bodySnippet", result.get("text", "")),
        title=result.get("title", ""),
        headers=result.get("headers"),
    ):
        return False
    return _recover(page.context, url, deadline=deadline, page=page)


def evaluate_get(page, expression, args):
    """Keep the successful browser fetch path and retry one challenged GET."""
    deadline = time.monotonic() + args[1] / 1000
    result = page.evaluate(expression, args)
    if recover_get_result(page, args[0], result, deadline=deadline):
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining > 0:
            result = page.evaluate(expression, [args[0], remaining, *args[2:]])
    return result


def evaluate_main_world(page, expression: str):
    """Read page-owned JS state through Camoufox's explicit main-world API."""
    navigator = navigator_for(page)
    return page.evaluate(
        "mw:" + expression
        if navigator is not None and navigator.diagnostics.get("engine") == "camoufox"
        else expression
    )
