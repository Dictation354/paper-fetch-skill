"""Capture supplementary bytes initiated by an existing page control."""

from __future__ import annotations

import contextlib
import json
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import (
    SplitResult,
    parse_qs,
    parse_qsl,
    unquote,
    urldefrag,
    urljoin,
    urlsplit,
)

from ....asset_budget import DEFAULT_ASSET_MAX_BYTES_PER_ASSET, AssetBudgetExceeded
from ....extraction.html.assets import supplementary_response_block_reason
from ....extraction.html.assets.state import AssetBinaryPayload, AssetFetchResponse
from ....http import RequestCancelledError
from ....http.cache import redact_url_for_cache
from ....publisher_identity import DOI_PATTERN
from ..._registry import BrowserAssetPolicy, browser_asset_policy
from ...browser_runtime.navigation import (
    managed_action,
    navigate_page,
    refetch_browser_response,
)
from .context import _browser_response_headers, _browser_response_status

_CLICK_TIMEOUT_SECONDS = 60.0


def _http_origin(url: SplitResult) -> tuple[str, str | None, int]:
    port = url.port
    return (
        url.scheme,
        url.hostname,
        port if port is not None else (443 if url.scheme == "https" else 80),
    )


def _verified_supplement_filename(target: str, download_url: str) -> str:
    try:
        source = urlsplit(target)
        final = urlsplit(download_url)
        if (
            final.path != "/action/downloadSupplement"
            or source.scheme not in {"http", "https"}
            or not source.hostname
            or _http_origin(source) != _http_origin(final)
            or not source.path.startswith("/doi/suppl/")
        ):
            return ""
        doi, separator, filename = source.path.removeprefix("/doi/suppl/").rpartition(
            "/suppl_file/"
        )
        doi, filename = (
            unquote(doi, errors="strict"),
            unquote(filename, errors="strict"),
        )
        if (
            not separator
            or DOI_PATTERN.fullmatch(doi) is None
            or not filename
            or "/" in filename
            or "\\" in filename
        ):
            return ""
        query = parse_qs(final.query, keep_blank_values=True, errors="strict")
        dois = query.get("doi", [])
        if (
            len(dois) == 1
            and dois[0].casefold() == doi.casefold()
            and query.get("file") == [filename]
        ):
            return filename
    except ValueError:
        return ""
    return ""


def _page_link(page, urls, asset, policy: BrowserAssetPolicy, remaining_ms):
    # Compare resolved hrefs, retaining the original DOM node. Never create an
    # anchor or assign a generated download URL to a publisher control.
    if policy.supplement_exact_href and asset.get("source_href"):
        value = json.dumps(asset["source_href"])
        selector = f"a[href={value}]"
        if policy.supplement_control_scope:
            selector = f"{policy.supplement_control_scope} {selector}:visible"
        # Attribute reads/activation auto-wait on the same exact selector.
        return page.locator(selector).first, False

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
    parent = (
        page.locator(policy.supplement_control_scope)
        if policy.supplement_control_scope
        else page
    )
    nodes = parent.locator(selector)

    def find_link():
        try:
            return nodes.evaluate_all(
                match, {"urls": urls, "preferVisible": policy.supplement_prefer_visible}
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
        if policy.supplement_missing_link is not None:
            control, tab_opened = policy.supplement_missing_link(
                page, urls, asset, remaining_ms, tab_opened
            )
            if control is not None:
                return control, True
        page.wait_for_timeout(min(100, remaining_ms()))
        found = find_link()
    # Re-resolve by the original href after a publisher redraws its DOM.
    selector = f"{found['tag']}[{found['attribute']}={json.dumps(found['value'])}]"
    visible = parent.locator(selector + ":visible")
    return (visible if visible.count() else parent.locator(selector)).first, False


def fetch_file_with_page_click(fetcher, file_url: str, asset: Mapping[str, Any]):
    page, context = fetcher._page, fetcher._context
    provider = getattr(fetcher._browser_config, "provider", "")
    policy = browser_asset_policy(provider)
    prefix = policy.supplement_failure_prefix
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
    redirect_targets: dict[str, set[Any]] = {}
    matched_requests = set()
    request_urls = set()

    def matches_target(url):
        if url in targets:
            return True
        if not policy.supplement_ignore_tracking_query:
            return False
        # IEEE's existing media controls append tracking query parameters.
        # Match the full origin and file path, never a basename or MIME alone.
        parsed = urlsplit(url)
        return any(
            (parsed.scheme, parsed.netloc, parsed.path)
            == (expected.scheme, expected.netloc, expected.path)
            for expected in map(urlsplit, targets)
        )

    def remaining_ms(*, transfer_started=False):
        # An admitted download can finish after the link activation window.
        remaining = (
            _CLICK_TIMEOUT_SECONDS if transfer_started else deadline - time.monotonic()
        )
        runtime = fetcher._runtime_context
        if runtime is not None:
            remaining = runtime.browser_remaining_seconds(
                runtime.remaining_seconds(remaining)
            )
        if remaining <= 0:
            raise TimeoutError("Supplementary click deadline exceeded.")
        return max(1, int(remaining * 1000))

    def set_phase(value):
        nonlocal phase
        phase = value

    def request_page(request):
        try:
            owner = request.frame.page
        except Exception:
            return None  # Popup navigation can precede frame creation.
        if owner not in [page, *popups]:
            capture_popup(owner)
        return owner

    def owns_request(request):
        return request_page(request) in [page, *popups]

    def request_root(request):
        while request.redirected_from is not None:
            request = request.redirected_from
        return request

    def clicked_url(url):
        if url in targets:
            return True
        parameter = policy.supplement_added_query_parameter
        if not parameter:
            return False
        actual = urlsplit(url)
        query = parse_qsl(actual.query, keep_blank_values=True)
        remaining = [(key, value) for key, value in query if key != parameter]
        if len(query) != len(remaining) + 1:
            return False
        return any(
            actual._replace(query="") == expected._replace(query="")
            and remaining == parse_qsl(expected.query, keep_blank_values=True)
            for expected in map(urlsplit, targets)
        )

    def capture_request(request):
        if not armed:
            return
        root = request_root(request)
        if root not in matched_requests and root is request:
            clicked = clicked_url(request.url)
            if not clicked and request.url not in redirect_targets:
                return
            # Register a candidate before opener() can dispatch nested events.
            # A known unrelated page can never contribute a response.
            if clicked:
                matched_requests.add(root)
            owner = request_page(request)
            if owner is not None and owner not in [page, *popups]:
                matched_requests.discard(root)
                return
            redirect_owners = redirect_targets.get(request.url, set())
            if (owner is not None and owner in redirect_owners) or (
                None in redirect_owners and request.is_navigation_request()
            ):
                matched_requests.add(root)
        if root in matched_requests:
            request_urls.add(request.url)

    def capture_response(candidate):
        nonlocal response, pending_response
        if not armed or request_root(candidate.request) not in matched_requests:
            return
        owner = request_page(candidate.request)
        if owner is not None and owner not in [page, *popups]:
            return
        if 300 <= candidate.status < 400:
            location = candidate.headers.get("location")
            # The browser can report the popup's entire redirect chain before it
            # has a frame. Keep its Location for the next navigation. A
            # frameless final response still needs an owned page or download.
            if location and (
                owner is not None or candidate.request.is_navigation_request()
            ):
                url = urldefrag(urljoin(candidate.url, location)).url
                redirect_targets.setdefault(url, set()).add(owner)
            return
        if owner is not None:
            response = candidate
        elif candidate.request.is_navigation_request():
            pending_response = candidate

    def capture_finished(request):
        if armed and request_root(request) in matched_requests:
            finished.add(request)

    def download_match(candidate):
        owner = candidate.page
        if owner not in [page, *popups]:
            return False, ""
        url = candidate.url
        linked = (
            clicked_url(url)
            or url in request_urls
            or owner in redirect_targets.get(url, ())
            or (response is not None and url == response.url)
        )
        # Chromium's HTML download handoff can expose only the final URL.
        filename = (
            _verified_supplement_filename(target, url)
            if policy.supplement_download_query_fallback
            else ""
        )
        return linked, filename

    def capture_download(candidate):
        nonlocal response
        if armed and any(download_match(candidate)):
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
            navigate_page(
                page, click_page_url, wait_until="commit", timeout=remaining_ms()
            )
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
        if policy.supplement_link is not None:
            link = policy.supplement_link(page, urls, remaining_ms, set_phase)
            filename_control = False
        else:
            phase = "link_missing"
            link, filename_control = _page_link(page, urls, asset, policy, remaining_ms)
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
        targets.update(
            urls
            if policy.supplement_ignore_tracking_query and filename_control
            else [target]
        )
        if target not in urls and not (
            policy.supplement_ignore_tracking_query
            and filename_control
            and matches_target(target)
        ):
            raise ValueError("Supplementary control target changed.")
        visible_link = link
        if (
            policy.supplement_link is None
            and not filename_control
            and not policy.supplement_exact_href
        ):
            value = json.dumps(raw_href)
            visible_link = page.locator(
                f"a[href={value}]:visible, a[data-url={value}]:visible, "
                f"button[data-url={value}]:visible"
            ).first
        if policy.supplement_reveal is not None:
            policy.supplement_reveal(page, link, visible_link, remaining_ms)
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
        with managed_action(page, timeout_ms=remaining_ms()):
            if policy.supplement_activate is not None:
                policy.supplement_activate(page, link, remaining_ms)
            else:
                # A trusted pointer action gives target=_blank its user activation;
                # a synthetic DOM click can be silently blocked by the browser.
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
            download = None
            verified_filename = ""
            for item in downloads:
                if response is not None and item.url != response.url:
                    continue
                linked, filename = download_match(item)
                if linked or (filename and download is None):
                    download, verified_filename = item, filename
                    if linked:
                        break
            # A download manager handoff need not finish the page request.
            # A local path or save_as() supplies the complete file; deadline/cancellation
            # and byte limits are checked before accepting it below.
            if download is not None or (
                response is not None and response.request in finished
            ):
                headers = (
                    _browser_response_headers(response) if response is not None else {}
                )
                status = (
                    _browser_response_status(response) if response is not None else None
                )
                if download is not None:
                    final_url = str(download.url)
                    shared_browser = (
                        getattr(
                            getattr(fetcher, "_browser_config", None), "backend", None
                        )
                        == "scrapling"
                    )
                    with (
                        tempfile.TemporaryDirectory(
                            prefix="paper-fetch-scrapling-download-"
                        )
                        if shared_browser
                        else contextlib.nullcontext()
                    ) as directory:
                        if directory is not None:
                            path = Path(directory) / "download"
                            download.save_as(str(path))
                        else:
                            path = download.path()
                        remaining_ms(transfer_started=True)
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
                else:
                    assert response is not None
                    final_url = str(response.url)
                    if "attachment" in headers.get("content-disposition", "").lower():
                        # Wait for the download event within the existing deadline.
                        page.wait_for_timeout(min(50, remaining_ms()))
                        continue
                    route["capture_event"] = "inline_response"
                    mime_type = (
                        headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    )
                    if mime_type == "text/plain" and status == 200:
                        # Chromium can transcode a binary file served as text.
                        with refetch_browser_response(
                            context, response, timeout_ms=remaining_ms()
                        ) as refreshed:
                            headers = _browser_response_headers(refreshed)
                            body = refreshed.body()
                        route["bytes_transport"] = "browser_request"
                    else:
                        body = response.body()
                remaining_ms(transfer_started=download is not None)
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
                route["final_url"] = redact_url_for_cache(final_url)
                fetcher._last_failure_by_url.pop(file_url, None)
                return AssetFetchResponse(
                    payload=AssetBinaryPayload(
                        body=body,
                        downloaded_bytes=len(body),
                    ),
                    filename_hint=verified_filename,
                    recovery_attempts=[{"stage": "page_click", **route}],
                    route_diagnostics=dict(route),
                    diagnostics={
                        "status_code": status,
                        "headers": headers,
                        "url": final_url,
                    },
                )
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
                navigate_page(
                    page, article_url, wait_until="commit", timeout=remaining_ms()
                )
