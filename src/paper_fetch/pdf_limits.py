"""Shared PDF transfer and validation limits."""

from __future__ import annotations

import os

from .utils import normalize_text

PDF_MAX_BYTES_ENV_VAR = "PAPER_FETCH_PDF_MAX_BYTES"
DEFAULT_PDF_MAX_BYTES = 150 * 1024 * 1024


def pdf_max_bytes() -> int:
    value = normalize_text(os.environ.get(PDF_MAX_BYTES_ENV_VAR))
    if not value:
        return DEFAULT_PDF_MAX_BYTES
    try:
        parsed = int(value)
    except ValueError:
        return DEFAULT_PDF_MAX_BYTES
    return parsed if parsed > 0 else DEFAULT_PDF_MAX_BYTES


__all__ = [
    "DEFAULT_PDF_MAX_BYTES",
    "PDF_MAX_BYTES_ENV_VAR",
    "pdf_max_bytes",
]
