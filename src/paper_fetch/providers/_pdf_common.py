"""Shared PDF validation and Markdown conversion helpers."""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..utils import normalize_text


@dataclass(frozen=True)
class PdfFetchResult:
    source_url: str
    final_url: str
    pdf_bytes: bytes
    markdown_text: str
    suggested_filename: str | None = None


class PdfFetchFailure(Exception):
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


def filename_from_headers(headers: Mapping[str, str] | None) -> str | None:
    content_disposition = str((headers or {}).get("content-disposition") or "")
    if not content_disposition:
        return None
    match = _CONTENT_DISPOSITION_FILENAME_PATTERN.search(content_disposition)
    if not match:
        return None
    return normalize_text(match.group(1)) or None


def render_pdf_markdown(pdf_path: Path) -> str:
    try:
        import pymupdf4llm
    except Exception as exc:  # pragma: no cover - exercised by missing dependency integration tests
        raise PdfFetchFailure("missing_pymupdf4llm", "pymupdf4llm is not installed; cannot use PDF fallback.") from exc
    return str(pymupdf4llm.to_markdown(str(pdf_path)) or "")


def looks_like_pdf_payload(content_type: str | None, payload: bytes, final_url: str | None = None) -> bool:
    normalized_content_type = normalize_text(content_type).lower()
    normalized_final_url = normalize_text(final_url).lower()
    return payload.startswith(b"%PDF-") or "application/pdf" in normalized_content_type or normalized_final_url.endswith(".pdf")


def pdf_fetch_result_from_bytes(
    *,
    artifact_dir: Path | None,
    source_url: str,
    final_url: str,
    pdf_bytes: bytes,
    suggested_filename: str | None = None,
) -> PdfFetchResult:
    temp_dir_cm = tempfile.TemporaryDirectory(prefix="paper_fetch_pdf_") if artifact_dir is None else nullcontext(None)
    with temp_dir_cm as temp_dir:
        active_dir = Path(temp_dir) if temp_dir is not None else artifact_dir
        assert active_dir is not None
        active_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = active_dir / "downloaded.pdf"
        pdf_path.write_bytes(pdf_bytes)
        if not pdf_bytes.startswith(b"%PDF-"):
            pdf_path.unlink(missing_ok=True)
            raise PdfFetchFailure(
                "downloaded_file_not_pdf",
                "PDF fallback did not produce a PDF file.",
                details={"source_url": source_url, "suggested_filename": suggested_filename},
            )

        markdown_text = render_pdf_markdown(pdf_path)
        if not normalize_text(markdown_text):
            raise PdfFetchFailure(
                "empty_pdf_markdown",
                "PDF fallback produced empty Markdown.",
                details={"source_url": source_url, "final_url": final_url},
            )

        return PdfFetchResult(
            source_url=source_url,
            final_url=final_url,
            pdf_bytes=pdf_bytes,
            markdown_text=markdown_text,
            suggested_filename=suggested_filename,
        )
