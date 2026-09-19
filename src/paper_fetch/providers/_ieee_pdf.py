"""IEEE stamp wrappers expose their PDF through a same-article iframe."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from ..extraction.html.parsing import choose_parser
from ..quality.access_boundary import raise_for_paywall


def _article_number(url: str, path: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "ieeexplore.ieee.org"
        or parsed.path != path
    ):
        return ""
    values = parse_qs(parsed.query).get("arnumber", [])
    return values[0] if len(values) == 1 and values[0].isdigit() else ""


def stamp_article_number(url: str) -> str:
    return _article_number(url, "/stamp/stamp.jsp")


def iframe_pdf_candidates(html: str, stamp_url: str) -> list[str]:
    article_number = stamp_article_number(stamp_url)
    if not article_number:
        return []
    soup = BeautifulSoup(html, choose_parser())
    return list(
        dict.fromkeys(
            target
            for iframe in soup.select("iframe[src]")
            if (target := urljoin(stamp_url, str(iframe["src"])))
            and _article_number(target, "/stampPDF/getPDF.jsp") == article_number
        )
    )


def navigate_stamp_pdf(
    page: Any,
    url: str,
    *,
    goto_kwargs: dict[str, Any],
    timeout_ms: int,
    expected_identity: Any,
    check_cancelled: Callable[[], None] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> tuple[Any, Any, Any]:
    """Observe before navigation, retaining direct PDF and download responses."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    article_number = stamp_article_number(url)
    initial_response = None
    child_responses: list[Any] = []
    downloads: list[Any] = []
    deadline = time.monotonic() + timeout_ms / 1000

    def on_response(response: Any) -> None:
        if _article_number(response.url, "/stampPDF/getPDF.jsp") == article_number:
            child_responses.append(response)

    def on_download(download: Any) -> None:
        downloads.append(download)

    page.on("response", on_response)
    page.on("download", on_download)
    try:
        try:
            initial_response = page.goto(url, **goto_kwargs)
        except PlaywrightTimeoutError:
            pass
        except PlaywrightError as exc:
            if "Download is starting" not in str(exc):
                raise
        while not downloads and not child_responses:
            if check_cancelled is not None:
                check_cancelled()
            if initial_response is not None and _is_pdf_response(initial_response):
                return initial_response, initial_response, None
            if initial_response is not None and initial_response.status >= 400:
                break
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                break
            page.wait_for_timeout(min(50, remaining_ms))
        if downloads:
            return initial_response, None, downloads[0]
        html = page.content()
        raise_for_paywall(
            html, metadata=expected_identity, source_url=page.url, provider="ieee"
        )
        candidates = iframe_pdf_candidates(html, page.url)
        if stamp_article_number(page.url) == article_number:
            for response in child_responses:
                if (
                    response.url in candidates
                    and response.request.resource_type == "document"
                    and response.frame.parent_frame == page.main_frame
                    and _is_pdf_response(response)
                ):
                    return initial_response, response, None
    finally:
        page.remove_listener("response", on_response)
        page.remove_listener("download", on_download)
    remaining_ms = int((deadline - time.monotonic()) * 1000)
    if remaining_ms > 0:
        response, download = _click_article_pdf(
            page,
            article_number,
            timeout_ms=remaining_ms,
            expected_identity=expected_identity,
            check_cancelled=check_cancelled,
        )
        if response is not None or download is not None:
            if diagnostics is not None:
                diagnostics.update(
                    {
                        "browser_pdf_response": "ieee_article_click",
                        "article_url": f"https://ieeexplore.ieee.org/document/{article_number}",
                        "stamp_initial_status": initial_response.status
                        if initial_response
                        else None,
                    }
                )
            return initial_response, response, download
    return initial_response, None, None


def _click_article_pdf(
    page: Any,
    article_number: str,
    *,
    timeout_ms: int,
    expected_identity: Any,
    check_cancelled: Callable[[], None] | None,
) -> tuple[Any, Any]:
    """Use the same article's visible PDF link, including a publisher popup."""
    from playwright.sync_api import Error as PlaywrightError

    deadline = time.monotonic() + timeout_ms / 1000
    context = page.context
    responses: list[Any] = []
    downloads: list[Any] = []
    pages = [page]

    def remaining() -> int:
        if check_cancelled is not None:
            check_cancelled()
        return max(1, int((deadline - time.monotonic()) * 1000))

    def on_response(response: Any) -> None:
        if any(
            _article_number(response.url, path) == article_number
            for path in ("/stamp/stamp.jsp", "/stampPDF/getPDF.jsp")
        ) and _is_pdf_response(response):
            responses.append(response)

    def on_download(download: Any) -> None:
        if any(
            _article_number(download.url, path) == article_number
            for path in ("/stamp/stamp.jsp", "/stampPDF/getPDF.jsp")
        ):
            downloads.append(download)

    def on_page(new_page: Any) -> None:
        pages.append(new_page)
        new_page.on("download", on_download)

    context.on("response", on_response)
    context.on("page", on_page)
    page.on("download", on_download)
    try:
        page.goto(
            f"https://ieeexplore.ieee.org/document/{article_number}",
            wait_until="domcontentloaded",
            timeout=remaining(),
        )
        while time.monotonic() < deadline:
            raise_for_paywall(
                page.content(),
                metadata=expected_identity,
                source_url=page.url,
                provider="ieee",
            )
            controls = page.locator('a[href*="/stamp/stamp.jsp"]')
            chosen = None
            for index in range(controls.count()):
                control = controls.nth(index)
                target = urljoin(page.url, control.get_attribute("href") or "")
                if (
                    stamp_article_number(target) == article_number
                    and control.is_visible()
                ):
                    chosen = control
                    break
            if chosen is not None:
                try:
                    chosen.click(timeout=remaining())
                except PlaywrightError as exc:
                    if "Download is starting" not in str(exc):
                        raise
                break
            page.wait_for_timeout(min(100, remaining()))
        else:
            return None, None
        while time.monotonic() < deadline:
            if downloads:
                return None, downloads[0]
            for response in responses:
                if (
                    response.request.resource_type == "document"
                    and response.frame.page in pages
                ):
                    return response, None
            for active_page in pages:
                if stamp_article_number(active_page.url) != article_number:
                    continue
                try:
                    html = active_page.content()
                except PlaywrightError:
                    continue  # A just-opened popup can still be navigating.
                raise_for_paywall(
                    html,
                    metadata=expected_identity,
                    source_url=active_page.url,
                    provider="ieee",
                )
            page.wait_for_timeout(min(50, remaining()))
        return None, None
    finally:
        context.remove_listener("response", on_response)
        context.remove_listener("page", on_page)
        for active_page in pages:
            active_page.remove_listener("download", on_download)


def _is_pdf_response(response: Any) -> bool:
    return bool(
        200 <= response.status < 300
        and response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        == "application/pdf"
    )
