"""Capture supplementary bytes initiated by an existing page control."""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
import time
from typing import Any
from collections.abc import Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit

from ....asset_budget import DEFAULT_ASSET_MAX_BYTES_PER_ASSET, AssetBudgetExceeded
from ....extraction.html.assets import supplementary_response_block_reason
from ....http import RequestCancelledError
from ....http.cache import redact_url_for_cache
from .context import _browser_response_headers, _browser_response_status
from .readiness import wait_for_atypon_body_dom_ready

_CLICK_TIMEOUT_SECONDS = 60.0


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


def _ieee_filename_control(page, asset):
    filename = str(asset.get("filename_hint") or "")
    if not filename:
        return None
    scope = page.locator(
        "#multimedia, #media, xpl-document-multimedia, xpl-document-media, "
        "xpl-document-media-list, .multimedia, .media-list, "
        "[id*='supplement']"
    )
    controls = scope.locator(
        "button:not([data-url]), a:not([href]), a[href='#'], a[href^='javascript:']"
    ).filter(has_text=filename)
    visible = [
        controls.nth(index)
        for index in range(controls.count())
        if controls.nth(index).is_visible()
    ]
    if len(visible) == 1:
        return visible[0]
    # IEEE's desktop media list can attach its action to the filename label.
    # Restrict this to the known attachment name in the media component; the
    # resulting request must still match that attachment's JSON file URL.
    labels = scope.get_by_text(filename)
    visible = [
        labels.nth(index)
        for index in range(labels.count())
        if labels.nth(index).is_visible()
    ]
    if len(visible) == 1:
        return visible[0]
    media_doi = str(asset.get("doi") or "")
    if not media_doi:
        return None
    # Translated PDFs may show only their multimedia DOI and a PDF icon.
    # Bind the existing icon to the exact DOI provided by multimedia discovery.
    items = scope.locator(".media-item").filter(
        has=page.get_by_text(re.compile(r"^" + re.escape(media_doi) + r"$", re.I))
    )
    icons = items.locator("a[class*='stats-Multimedia_']:visible")
    return icons.first if icons.count() == 1 else None


def _page_link(page, urls, asset, provider, remaining_ms):
    if provider == "ieee" and not asset.get("filename_hint"):
        asset = {**asset, "filename_hint": urlsplit(urls[0]).path.rsplit("/", 1)[-1]}
    # Compare resolved hrefs, retaining the original DOM node. Never create an
    # anchor or assign a generated download URL to a publisher control.
    selector = "a[href], button[data-url], a[data-url]"
    match = """(nodes, options) => {
        const {urls, preferVisible} = options;
        let node;
        for (const visibleOnly of (preferVisible ? [true, false] : [false])) {
            for (const url of urls) {
                node = nodes.find(node => {
                    if (visibleOnly && (!Array.from(node.getClientRects()).some(
                        rect => rect.width > 0 && rect.height > 0
                    ) || getComputedStyle(node).visibility === 'hidden')) return false;
                    const value = node.getAttribute('href') || node.getAttribute('data-url');
                    try { return url === new URL(value, document.baseURI).href; }
                    catch { return false; }
                });
                if (node) break;
            }
            if (node) break;
        }
        if (!node) return null;
        const attribute = node.getAttribute('href') ? 'href' : 'data-url';
        return {tag: node.tagName.toLowerCase(), attribute,
                value: node.getAttribute(attribute)};
    }"""
    nodes = page.locator(selector)

    def find_link():
        try:
            return nodes.evaluate_all(
                match, {"urls": urls, "preferVisible": provider == "mdpi"}
            )
        except Exception as exc:
            # MDPI can replace its document while its article scripts start.
            # Only this transient navigation error is retried, within the same
            # click deadline; unrelated locator failures remain explicit.
            if "Execution context was destroyed" not in str(exc):
                raise
            return None

    found = find_link()
    tab_opened = False
    # Article links can be populated after DOMContentLoaded (notably MDPI).
    # Wait for the original URL within this request's existing deadline.
    while found is None:
        if provider == "ieee":
            control = _ieee_filename_control(page, asset)
            if control is not None:
                return control, True
            if not tab_opened:
                tab_name = re.compile(
                    r"^(Media|Multimedia|Supplemental Items|Supplemental Material|Supplementary Material)$",
                    re.I,
                )
                tabs = page.get_by_role("tab", name=tab_name)
                if not tabs.count():
                    tabs = page.get_by_text(tab_name)
                for index in range(tabs.count()):
                    if tabs.nth(index).is_visible():
                        tabs.nth(index).click(timeout=remaining_ms())
                        tab_opened = True
                        break
        page.wait_for_timeout(min(100, remaining_ms()))
        found = find_link()
    # Re-resolve by the original href after a publisher redraws its DOM.
    selector = f"{found['tag']}[{found['attribute']}={json.dumps(found['value'])}]"
    visible = page.locator(selector + ":visible")
    return (visible if visible.count() else page.locator(selector)).first, False


def fetch_file_with_page_click(fetcher, file_url: str, asset: Mapping[str, Any]):
    page, context = fetcher._page, fetcher._context
    provider = getattr(fetcher._browser_config, "provider", "")
    prefix = "wiley_supplement" if provider == "wiley" else "supplement_click"
    article_url = str(fetcher._current_seed().get("browser_final_url") or "")
    if not article_url:
        article_url = next(iter(fetcher._seed_urls()), "")
    click_page_url = str(
        asset.get("source_page_url") or asset.get("referer_url") or article_url
    )
    route = {
        "mode": "page_click",
        "click_page_url": redact_url_for_cache(click_page_url),
        "original_href": redact_url_for_cache(
            str(asset.get("source_href") or file_url)
        ),
    }
    if page is None or context is None:
        fetcher._record_failure(file_url, reason=f"{prefix}_page_unavailable", **route)
        return None
    deadline = time.monotonic() + _CLICK_TIMEOUT_SECONDS
    phase = "article_not_ready"
    response = None
    pending_response = None
    finished = set()
    downloads = []
    popups: list[Any] = []
    listeners = []
    armed = False
    targets: set[str] = set()
    matched_requests = set()
    request_urls = set()

    def matches_target(url):
        if url in targets:
            return True
        if provider != "ieee":
            return False
        # IEEE's existing media controls append tracking query parameters.
        # Match the full origin and file path, never a basename or MIME alone.
        parsed = urlsplit(url)
        return any(
            (parsed.scheme, parsed.netloc, parsed.path)
            == (expected.scheme, expected.netloc, expected.path)
            for expected in map(urlsplit, targets)
        )

    def remaining_ms():
        remaining = deadline - time.monotonic()
        if fetcher._runtime_context is not None:
            remaining = fetcher._runtime_context.remaining_seconds(remaining)
        if remaining <= 0:
            raise TimeoutError("Supplementary click deadline exceeded.")
        return max(1, int(remaining * 1000))

    def set_phase(value):
        nonlocal phase
        phase = value

    def owns_request(request):
        # Responses from background prefetches, other pages, and previous
        # attachments are excluded even when they have a plausible MIME type.
        try:
            request_page = request.frame.page
            if request_page not in [page, *popups]:
                capture_popup(request_page)
                if request_page not in popups:
                    return False
        except Exception:
            return False
        return request_root(request) in matched_requests

    def request_root(request):
        while request.redirected_from is not None:
            request = request.redirected_from
        return request

    def capture_request(request):
        if not armed:
            return
        if request.redirected_from is None and request.url in targets:
            try:
                request_page = request.frame.page
                if request_page not in [page, *popups]:
                    capture_popup(request_page)
                if request_page in [page, *popups]:
                    matched_requests.add(request)
            except Exception:
                # Popup navigation can precede frame creation. Keep a pending
                # root; response/download capture still requires an owned page.
                if request.is_navigation_request():
                    matched_requests.add(request)
        root = request_root(request)
        if root in matched_requests:
            request_urls.add(request.url)

    def capture_response(candidate):
        nonlocal response, pending_response
        if (
            armed
            and request_root(candidate.request) in matched_requests
            and not 300 <= candidate.status < 400
        ):
            if owns_request(candidate.request):
                response = candidate
            else:
                # Firefox can deliver a redirected popup download before its
                # Page/frame exists. A download from an owned page must confirm
                # this response before it can supply any bytes or headers.
                pending_response = candidate

    def capture_finished(request):
        if armed and request_root(request) in matched_requests:
            finished.add(request)

    def capture_download(candidate):
        nonlocal response
        if armed and candidate.url in request_urls:
            downloads.append(candidate)
            if pending_response is not None and pending_response.url == candidate.url:
                response = pending_response

    def listen(owner, event, callback):
        owner.on(event, callback)
        listeners.append((owner, event, callback))

    def capture_owned_popup(popup):
        nonlocal response
        if armed and popup not in popups:
            popups.append(popup)
            listen(popup, "download", capture_download)
            listen(popup, "popup", capture_owned_popup)
            if pending_response is not None and owns_request(pending_response.request):
                response = pending_response

    def capture_popup(popup):
        if armed and popup.opener() in [page, *popups]:
            capture_owned_popup(popup)

    def record_failure(reason, *, body=b"", **details):
        headers = _browser_response_headers(response) if response is not None else {}
        fetcher._record_response_failure(
            file_url,
            status=_browser_response_status(response) if response is not None else None,
            content_type=headers.get("content-type", ""),
            final_url=str(response.url) if response is not None else str(page.url),
            body=body,
            reason=reason,
        )
        diagnostic = dict(fetcher.failure_for(file_url) or {})
        diagnostic.pop("source_url", None)
        fetcher._record_failure(file_url, **{**diagnostic, **route, **details})

    try:
        if click_page_url and page.url != click_page_url:
            # A publisher's pending scripts must not prevent use of an already
            # rendered attachment control. Link/body readiness is checked below.
            page.goto(click_page_url, wait_until="commit", timeout=remaining_ms())
        click_page_url = str(page.url)
        route["click_page_url"] = redact_url_for_cache(click_page_url)
        urls = list(
            dict.fromkeys(
                urljoin(click_page_url, str(value))
                for value in (
                    asset.get("source_href"),
                    asset.get("original_url"),
                    file_url,
                    asset.get("url"),
                    asset.get("download_url"),
                )
                if value
            )
        )
        if provider == "wiley":
            link = _wiley_link(page, urls, remaining_ms, set_phase)
            filename_control = False
        else:
            phase = "link_missing"
            link, filename_control = _page_link(
                page, urls, asset, provider, remaining_ms
            )
        click_page_url = str(page.url)
        route["click_page_url"] = redact_url_for_cache(click_page_url)
        raw_href = link.get_attribute(
            "href", timeout=remaining_ms()
        ) or link.get_attribute("data-url", timeout=remaining_ms())
        if filename_control:
            if not raw_href or raw_href.startswith(("javascript:", "#")):
                raw_href = str(asset.get("source_href") or file_url)
            route["attachment_label"] = link.inner_text(timeout=remaining_ms()) or str(
                asset.get("doi") or asset.get("filename_hint") or ""
            )
        if not raw_href:
            raise ValueError("Supplementary control has no target URL.")
        target = urljoin(click_page_url, raw_href)
        targets.update(urls if provider == "ieee" and filename_control else [target])
        if target not in urls and not (
            provider == "ieee" and filename_control and matches_target(target)
        ):
            raise ValueError("Supplementary control target changed.")
        visible_link = link
        if provider != "wiley" and not filename_control:
            value = json.dumps(raw_href)
            visible_link = page.locator(
                f"a[href={value}]:visible, a[data-url={value}]:visible, "
                f"button[data-url={value}]:visible"
            ).first
        if provider == "mdpi" and not link.is_visible():
            modal = link.locator("xpath=ancestor::*[@id='supplementaryModal']")
            if modal.count():
                controls = page.locator("[data-reveal-id='supplementaryModal']")
                for index in range(controls.count()):
                    if controls.nth(index).is_visible():
                        controls.nth(index).click(timeout=remaining_ms())
                        break
                visible_link.wait_for(state="visible", timeout=remaining_ms())
        if provider == "annualreviews" and not link.is_visible():
            tab = page.locator("a[href='#supplementary_data']:visible").first
            if not tab.count():
                hidden_tab = page.locator("a[href='#supplementary_data']").first
                menu = hidden_tab.locator(
                    "xpath=ancestor::li[contains(concat(' ', normalize-space(@class), ' '), ' dropdown ')][1]"
                )
                menu.locator("[data-toggle='dropdown']").first.click(
                    timeout=remaining_ms()
                )
            tab.click(timeout=remaining_ms())
            visible_link.wait_for(state="visible", timeout=remaining_ms())
        link = visible_link
        # Aliases are only used to verify the existing control's identity.
        # Capture exclusively its actual clicked URL and ensuing redirects.
        targets.clear()
        targets.add(target)
        route.update(
            original_href=redact_url_for_cache(raw_href),
            click_target_url=redact_url_for_cache(target),
        )
        # Context listeners capture the popup's first response as well as
        # same-page navigation; install them before activating the link.
        listen(context, "response", capture_response)
        listen(context, "request", capture_request)
        listen(context, "requestfinished", capture_finished)
        listen(context, "page", capture_popup)
        listen(page, "download", capture_download)
        # The owning page's popup event also identifies rel=noopener windows.
        listen(page, "popup", capture_owned_popup)
        armed = True
        phase = "download_timeout"
        if (
            provider == "wiley"
            and link.get_attribute("target", timeout=remaining_ms()) != "_blank"
        ):
            # Wiley can hide the accordion during its opening animation.
            link.evaluate("(node) => node.click()", timeout=remaining_ms())
        else:
            # A trusted pointer action gives target=_blank its user activation;
            # a synthetic DOM click can be silently blocked by Firefox.
            link.click(no_wait_after=True, timeout=remaining_ms())
        while True:
            remaining_ms()
            if response is None and pending_response is not None:
                # A popup navigation request can lack a frame permanently.
                # Its committed URL plus its already verified opener confirms
                # ownership, including a challenge HTML response with no file.
                if any(
                    owner.url == pending_response.url and owner.url in request_urls
                    for owner in [page, *popups]
                ):
                    response = pending_response
            download = next(
                (
                    item
                    for item in downloads
                    if item.url in targets
                    or (response is not None and item.url == response.url)
                ),
                None,
            )
            # A download manager handoff need not finish the page request.
            # download.path() supplies the complete file; deadline/cancellation
            # and byte limits are checked before accepting it below.
            if response is not None and (
                download is not None or response.request in finished
            ):
                headers = _browser_response_headers(response)
                status = _browser_response_status(response)
                if download is not None:
                    path = download.path()
                    remaining_ms()
                    if path is None:
                        record_failure(f"{prefix}_download_failed")
                        return None
                    maximum = DEFAULT_ASSET_MAX_BYTES_PER_ASSET
                    budget = getattr(fetcher._runtime_context, "asset_budget", None)
                    if budget is not None:
                        maximum = budget.max_bytes_per_asset
                    if Path(path).stat().st_size > maximum:
                        record_failure("asset_bytes_per_asset_exceeded")
                        return None
                    body = Path(path).read_bytes()
                    route["capture_event"] = "download"
                elif "attachment" in headers.get("content-disposition", "").lower():
                    # Do not treat an unfinished download as an inline response.
                    page.wait_for_timeout(min(50, remaining_ms()))
                    continue
                else:
                    body = response.body()
                    route["capture_event"] = "inline_response"
                remaining_ms()
                reason = supplementary_response_block_reason(
                    headers.get("content-type", ""), body
                )
                if reason or not body or (status is not None and status >= 400):
                    record_failure(
                        reason
                        or (
                            "empty_response_body"
                            if not body
                            else f"{prefix}_download_failed"
                        ),
                        body=body,
                    )
                    return None
                maximum = DEFAULT_ASSET_MAX_BYTES_PER_ASSET
                budget = getattr(fetcher._runtime_context, "asset_budget", None)
                if budget is not None:
                    maximum = budget.max_bytes_per_asset
                if len(body) > maximum:
                    record_failure("asset_bytes_per_asset_exceeded")
                    return None
                route["final_url"] = redact_url_for_cache(str(response.url))
                fetcher._last_failure_by_url.pop(file_url, None)
                return {
                    "status_code": status,
                    "headers": headers,
                    "body": body,
                    "url": str(response.url),
                    "_paper_fetch_asset_route_diagnostics": dict(route),
                    "_paper_fetch_recovery_attempts": [
                        {"stage": "page_click", **route}
                    ],
                }
            page.wait_for_timeout(min(50, remaining_ms()))
    except (RequestCancelledError, AssetBudgetExceeded):
        raise
    except Exception as exc:
        body = b""
        if response is not None:
            with contextlib.suppress(Exception):
                body = response.body()
        else:
            with contextlib.suppress(Exception):
                body = page.content().encode()
        block_reason = (
            supplementary_response_block_reason("text/html", body) if body else None
        )
        record_failure(
            block_reason or f"{prefix}_{phase}", body=body, error_message=str(exc)
        )
        return None
    finally:
        armed = False
        for owner, event, callback in reversed(listeners):
            with contextlib.suppress(Exception):
                owner.remove_listener(event, callback)
        for download in downloads:
            with contextlib.suppress(Exception):
                download.cancel()
            with contextlib.suppress(Exception):
                download.delete()
        for popup in popups:
            with contextlib.suppress(Exception):
                popup.close()
        # Restoration and cleanup stay on the owning thread and within the
        # original request deadline. A cancelled request is never navigated.
        with contextlib.suppress(Exception):
            if article_url and page.url != article_url:
                page.goto(article_url, wait_until="commit", timeout=remaining_ms())
