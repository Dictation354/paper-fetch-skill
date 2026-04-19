"""PDF fallback helpers for browser-workflow and direct-HTTP providers."""

from __future__ import annotations

import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, RequestFailure
from ..utils import normalize_text
from ._pdf_candidates import extract_pdf_candidate_urls_from_html
from ._html_access_signals import detect_html_block, summarize_html
from ._pdf_common import (
    PdfFetchFailure,
    PdfFetchResult,
    filename_from_headers,
    looks_like_pdf_payload,
    pdf_fetch_result_from_bytes,
    sanitize_storage_state,
)

PdfFallbackResult = PdfFetchResult
PdfFallbackFailure = PdfFetchFailure


def _build_cookie_seeded_opener(
    seed_urls: list[str] | None,
    *,
    headers: Mapping[str, str],
    timeout: int,
    browser_cookies: list[dict[str, Any]] | None = None,
) -> urllib.request.OpenerDirector | None:
    normalized_seed_urls = [normalize_text(url) for url in seed_urls or [] if normalize_text(url)]
    if not normalized_seed_urls and not any(isinstance(cookie, dict) for cookie in browser_cookies or []):
        return None

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    seed_headers = {
        key: value
        for key, value in dict(headers).items()
        if str(key).lower() != "accept"
    }
    seed_headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

    for seed_url in normalized_seed_urls:
        request_headers = dict(seed_headers)
        cookie_header = _cookie_header_for_url(browser_cookies, seed_url)
        if cookie_header:
            request_headers["Cookie"] = cookie_header
        request = urllib.request.Request(seed_url, headers=request_headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                response.read(1024)
        except Exception:
            continue

    return opener


def _request_with_opener(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with opener.open(request, timeout=timeout) as response:
            return {
                "status_code": int(getattr(response, "status", response.getcode())),
                "headers": {str(key).lower(): str(value) for key, value in response.headers.items()},
                "body": response.read(),
                "url": str(response.geturl() or url),
            }
    except urllib.error.HTTPError as exc:
        raise RequestFailure(
            exc.code,
            f"HTTP {exc.code} for {url}",
            body=exc.read(),
            headers={str(key).lower(): str(value) for key, value in exc.headers.items()},
            url=str(exc.geturl() or url),
        ) from exc
    except urllib.error.URLError as exc:
        raise RequestFailure(
            None,
            f"Failed to download PDF fallback candidate: {exc.reason or exc}",
            url=url,
        ) from exc


def _response_to_pdf_result(
    response: Any,
    *,
    artifact_dir: Path,
    source_url: str,
    final_url: str,
) -> PdfFetchResult | None:
    if response is None:
        return None
    response_headers = response.headers if response is not None else {}
    content_type = normalize_text(str(response_headers.get("content-type") or "")).lower()
    if not looks_like_pdf_payload(content_type, response.body(), final_url):
        return None
    return pdf_fetch_result_from_bytes(
        artifact_dir=artifact_dir,
        source_url=source_url,
        final_url=final_url,
        pdf_bytes=response.body(),
        suggested_filename=filename_from_headers(response_headers),
    )


def _cookie_header_for_url(browser_cookies: list[dict[str, Any]] | None, url: str) -> str | None:
    parsed_url = urllib.parse.urlparse(normalize_text(url))
    host = normalize_text(parsed_url.hostname).lower()
    path = normalize_text(parsed_url.path) or "/"
    scheme = normalize_text(parsed_url.scheme).lower()
    if not host:
        return None

    matched_pairs: list[str] = []
    for cookie in browser_cookies or []:
        if not isinstance(cookie, dict):
            continue
        name = normalize_text(str(cookie.get("name") or ""))
        value = str(cookie.get("value") or "")
        if not name:
            continue

        cookie_domain = normalize_text(str(cookie.get("domain") or "")).lower().lstrip(".")
        if not cookie_domain:
            cookie_url = normalize_text(str(cookie.get("url") or ""))
            cookie_domain = normalize_text(urllib.parse.urlparse(cookie_url).hostname).lower()
        if cookie_domain and host != cookie_domain and not host.endswith(f".{cookie_domain}"):
            continue

        cookie_path = normalize_text(str(cookie.get("path") or "")) or "/"
        if not path.startswith(cookie_path):
            continue

        if bool(cookie.get("secure")) and scheme != "https":
            continue

        matched_pairs.append(f"{name}={value}")

    return "; ".join(matched_pairs) if matched_pairs else None


def _download_to_pdf_result(
    download: Any,
    *,
    artifact_dir: Path,
    source_url: str,
    final_url: str,
) -> PdfFetchResult:
    download_path = artifact_dir / "downloaded.pdf"
    download.save_as(str(download_path))
    return pdf_fetch_result_from_bytes(
        artifact_dir=artifact_dir,
        source_url=source_url,
        final_url=final_url,
        pdf_bytes=download_path.read_bytes(),
        suggested_filename=getattr(download, "suggested_filename", None),
    )


def fetch_pdf_with_playwright(
    candidate_urls: list[str],
    *,
    artifact_dir: Path,
    browser_cookies: list[dict[str, Any]] | None = None,
    browser_user_agent: str | None = None,
    headless: bool = True,
    storage_state_path: Path | None = None,
    seed_urls: list[str] | None = None,
) -> PdfFallbackResult:
    if not candidate_urls:
        raise PdfFallbackFailure("empty_pdf_attempts", "No PDF fallback candidates were attempted.")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised by missing dependency integration tests
        raise PdfFallbackFailure("missing_playwright", "playwright is not installed; cannot use PDF fallback.") from exc

    artifact_dir.mkdir(parents=True, exist_ok=True)
    last_failure: PdfFallbackFailure | None = None
    sanitized_storage_state_path: Path | None = None
    active_user_agent = browser_user_agent or "paper-fetch-skill/pdf-fallback"

    if browser_cookies:
        try:
            return fetch_pdf_over_http(
                HttpTransport(),
                candidate_urls,
                headers={"User-Agent": active_user_agent},
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                artifact_dir=artifact_dir,
                browser_cookies=list(browser_cookies),
            )
        except PdfFallbackFailure as exc:
            last_failure = exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context_kwargs: dict[str, Any] = {
            "user_agent": active_user_agent,
            "locale": "en-US",
            "viewport": {"width": 1440, "height": 1600},
            "accept_downloads": True,
        }
        if storage_state_path is not None:
            sanitized_storage_state_path = sanitize_storage_state(storage_state_path)
            context_kwargs["storage_state"] = str(sanitized_storage_state_path)
        context = browser.new_context(**context_kwargs)

        try:
            if browser_cookies:
                try:
                    context.add_cookies(browser_cookies)
                except Exception as exc:
                    raise PdfFallbackFailure(
                        "invalid_browser_context_seed",
                        f"Failed to seed browser-context PDF fallback with cookies: {exc}",
                    ) from exc

            page = context.new_page()
            for seed_url in [normalize_text(url) for url in seed_urls or [] if normalize_text(url)]:
                try:
                    page.goto(seed_url, wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    continue
            for url in candidate_urls:
                initial_response = None
                try:
                    with page.expect_download(timeout=30000) as download_info:
                        try:
                            initial_response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        except PlaywrightError as exc:
                            if "Download is starting" not in str(exc):
                                raise
                    download = download_info.value
                except PlaywrightTimeoutError:
                    response = initial_response
                    if response is None:
                        try:
                            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        except Exception:
                            response = None
                    if response is not None:
                        try:
                            pdf_result = _response_to_pdf_result(
                                response,
                                artifact_dir=artifact_dir,
                                source_url=url,
                                final_url=page.url,
                            )
                            if pdf_result is not None:
                                return pdf_result
                        except PdfFallbackFailure as exc:
                            last_failure = exc
                            continue
                    title = normalize_text(page.title())
                    html = page.content()
                    current_url = normalize_text(page.url)
                    html_base_url = current_url
                    parsed_current_url = urllib.parse.urlparse(current_url)
                    if parsed_current_url.scheme not in {"http", "https"} or not normalize_text(parsed_current_url.netloc):
                        html_base_url = url
                    discovered = extract_pdf_candidate_urls_from_html(html, html_base_url)
                    http_retry_candidates: list[str] = []
                    for candidate in [urllib.parse.urljoin(html_base_url or "", url), *discovered]:
                        normalized_candidate = normalize_text(candidate)
                        if normalized_candidate and normalized_candidate not in http_retry_candidates:
                            http_retry_candidates.append(normalized_candidate)
                    if http_retry_candidates:
                        try:
                            context_cookies = context.cookies()
                        except Exception:
                            context_cookies = list(browser_cookies or [])
                        http_headers = {"User-Agent": active_user_agent}
                        referer = normalize_text(html_base_url)
                        if referer:
                            http_headers["Referer"] = referer
                        try:
                            return fetch_pdf_over_http(
                                HttpTransport(),
                                http_retry_candidates,
                                headers=http_headers,
                                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                                artifact_dir=artifact_dir,
                                browser_cookies=context_cookies,
                            )
                        except PdfFallbackFailure as exc:
                            last_failure = exc
                    summary = summarize_html(html)
                    detected = detect_html_block(title, summary, None)
                    (artifact_dir / "pdf.failure.html").write_text(html, encoding="utf-8")
                    try:
                        page.screenshot(path=str(artifact_dir / "pdf.failure.png"), full_page=True)
                    except Exception:
                        pass
                    last_failure = PdfFallbackFailure(
                        detected.reason if detected is not None else "pdf_download_not_triggered",
                        detected.message if detected is not None else "Browser context did not trigger a PDF download.",
                        details={"source_url": url, "final_url": page.url},
                    )
                    continue
                except Exception as exc:
                    last_failure = PdfFallbackFailure(
                        "pdf_download_failed",
                        f"Failed to trigger PDF fallback download: {exc}",
                        details={"source_url": url},
                    )
                    continue

                try:
                    return _download_to_pdf_result(
                        download,
                        artifact_dir=artifact_dir,
                        source_url=url,
                        final_url=page.url,
                    )
                except PdfFallbackFailure as exc:
                    last_failure = exc
                    continue
        finally:
            context.close()
            browser.close()
            if sanitized_storage_state_path is not None:
                sanitized_storage_state_path.unlink(missing_ok=True)

    if last_failure is None:
        last_failure = PdfFallbackFailure("empty_pdf_attempts", "No PDF fallback candidates were attempted.")
    raise last_failure


def fetch_pdf_over_http(
    transport: HttpTransport,
    candidate_urls: list[str],
    *,
    headers: Mapping[str, str] | None = None,
    timeout: int = DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    artifact_dir: Path | None = None,
    seed_urls: list[str] | None = None,
    browser_cookies: list[dict[str, Any]] | None = None,
) -> PdfFetchResult:
    if not candidate_urls:
        raise PdfFetchFailure("empty_pdf_attempts", "No PDF fallback candidates were attempted.")

    request_headers = {"Accept": "application/pdf,*/*;q=0.8", **dict(headers or {})}
    last_failure: PdfFetchFailure | None = None
    opener = _build_cookie_seeded_opener(
        seed_urls,
        headers=request_headers,
        timeout=timeout,
        browser_cookies=browser_cookies,
    )

    for url in candidate_urls:
        per_request_headers = dict(request_headers)
        cookie_header = _cookie_header_for_url(browser_cookies, url)
        if cookie_header:
            per_request_headers["Cookie"] = cookie_header
        try:
            response = (
                _request_with_opener(opener, url, headers=per_request_headers, timeout=timeout)
                if opener is not None
                else transport.request(
                    "GET",
                    url,
                    headers=per_request_headers,
                    timeout=timeout,
                    retry_on_transient=True,
                )
            )
        except RequestFailure as exc:
            last_failure = PdfFetchFailure(
                "pdf_download_failed",
                f"Failed to download PDF fallback candidate: {exc}",
                details={"source_url": url},
            )
            continue

        final_url = str(response.get("url") or url)
        response_headers = response.get("headers") or {}
        pdf_bytes = response.get("body", b"")
        if not isinstance(pdf_bytes, (bytes, bytearray)) or not looks_like_pdf_payload(
            str(response_headers.get("content-type") or ""),
            bytes(pdf_bytes),
            final_url,
        ):
            last_failure = PdfFetchFailure(
                "downloaded_file_not_pdf",
                "Direct PDF fallback candidate did not return a PDF file.",
                details={"source_url": url, "final_url": final_url},
            )
            continue

        try:
            return pdf_fetch_result_from_bytes(
                artifact_dir=artifact_dir,
                source_url=url,
                final_url=final_url,
                pdf_bytes=bytes(pdf_bytes),
                suggested_filename=filename_from_headers(response_headers),
            )
        except PdfFetchFailure as exc:
            last_failure = exc
            continue

    if last_failure is None:
        last_failure = PdfFetchFailure("empty_pdf_attempts", "No PDF fallback candidates were attempted.")
    raise last_failure
