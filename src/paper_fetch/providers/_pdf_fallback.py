"""Browser-context PDF fallback for browser-workflow providers."""

from __future__ import annotations

import os
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import re

from ..utils import normalize_text
from ._science_pnas_html import detect_html_block, summarize_html


@dataclass(frozen=True)
class PdfFallbackResult:
    source_url: str
    final_url: str
    pdf_bytes: bytes
    markdown_text: str
    suggested_filename: str | None = None


class PdfFallbackFailure(Exception):
    def __init__(self, kind: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.details = dict(details or {})


_CONTENT_DISPOSITION_FILENAME_PATTERN = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', flags=re.IGNORECASE)


def sanitize_storage_state(path: Path) -> Path:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cookies = payload.get("cookies", []) or []
    filtered_cookies = [
        cookie
        for cookie in cookies
        if cookie.get("name") not in {"_cfuvid", "__cf_bm", "cf_clearance"}
        and not str(cookie.get("name", "")).startswith("cf_chl_")
    ]
    payload["cookies"] = filtered_cookies

    fd, temp_path = tempfile.mkstemp(prefix="playwright_state_", suffix=".json")
    temp_file = Path(temp_path)
    os.close(fd)
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return temp_file


def _filename_from_headers(headers: Mapping[str, str] | None) -> str | None:
    content_disposition = str((headers or {}).get("content-disposition") or "")
    if not content_disposition:
        return None
    match = _CONTENT_DISPOSITION_FILENAME_PATTERN.search(content_disposition)
    if not match:
        return None
    return normalize_text(match.group(1)) or None


def _render_pdf_markdown(pdf_path: Path) -> str:
    try:
        import pymupdf4llm
    except Exception as exc:  # pragma: no cover - exercised by missing dependency integration tests
        raise PdfFallbackFailure("missing_pymupdf4llm", "pymupdf4llm is not installed; cannot use PDF fallback.") from exc
    return str(pymupdf4llm.to_markdown(str(pdf_path)) or "")


def _result_from_pdf_bytes(
    *,
    artifact_dir: Path,
    source_url: str,
    final_url: str,
    pdf_bytes: bytes,
    suggested_filename: str | None = None,
) -> PdfFallbackResult:
    pdf_path = artifact_dir / "downloaded.pdf"
    pdf_path.write_bytes(pdf_bytes)
    if not pdf_bytes.startswith(b"%PDF-"):
        pdf_path.unlink(missing_ok=True)
        raise PdfFallbackFailure(
            "downloaded_file_not_pdf",
            "Browser-context PDF fallback did not produce a PDF file.",
            details={"source_url": source_url, "suggested_filename": suggested_filename},
        )

    markdown_text = _render_pdf_markdown(pdf_path)
    if not normalize_text(markdown_text):
        raise PdfFallbackFailure(
            "empty_pdf_markdown",
            "PDF fallback produced empty Markdown.",
            details={"source_url": source_url, "final_url": final_url},
        )

    return PdfFallbackResult(
        source_url=source_url,
        final_url=final_url,
        pdf_bytes=pdf_bytes,
        markdown_text=markdown_text,
        suggested_filename=suggested_filename,
    )


def fetch_pdf_with_playwright(
    candidate_urls: list[str],
    *,
    artifact_dir: Path,
    browser_cookies: list[dict[str, Any]] | None = None,
    browser_user_agent: str | None = None,
    headless: bool = True,
    storage_state_path: Path | None = None,
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

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context_kwargs: dict[str, Any] = {
            "user_agent": browser_user_agent or "paper-fetch-skill/pdf-fallback",
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
            for url in candidate_urls:
                try:
                    with page.expect_download(timeout=30000) as download_info:
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        except PlaywrightError as exc:
                            if "Download is starting" not in str(exc):
                                raise
                    download = download_info.value
                except PlaywrightTimeoutError:
                    try:
                        response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    except Exception:
                        response = None
                    response_headers = response.headers if response is not None else {}
                    content_type = normalize_text(str(response_headers.get("content-type") or "")).lower()
                    if response is not None and ("application/pdf" in content_type or str(page.url).lower().endswith(".pdf")):
                        try:
                            return _result_from_pdf_bytes(
                                artifact_dir=artifact_dir,
                                source_url=url,
                                final_url=page.url,
                                pdf_bytes=response.body(),
                                suggested_filename=_filename_from_headers(response_headers),
                            )
                        except PdfFallbackFailure as exc:
                            last_failure = exc
                            continue
                    title = normalize_text(page.title())
                    html = page.content()
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

                download_path = artifact_dir / "downloaded.pdf"
                download.save_as(str(download_path))
                try:
                    return _result_from_pdf_bytes(
                        artifact_dir=artifact_dir,
                        source_url=url,
                        final_url=page.url,
                        pdf_bytes=download_path.read_bytes(),
                        suggested_filename=download.suggested_filename,
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
