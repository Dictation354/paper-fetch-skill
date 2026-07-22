"""Failure predicates for IEEE selected-browser recovery."""

from __future__ import annotations

import re

from ..extraction.html.assets import browser_asset_recovery_allowed
from ..utils import normalize_text
from ._pdf_fallback import PdfFetchFailure
from .base import ProviderFailure


def pdf_browser_recovery_allowed(failure: PdfFetchFailure) -> bool:
    details = failure.details
    status_value = details.get("status")
    try:
        status = int(status_value) if status_value is not None else None
    except (TypeError, ValueError):
        status = None
    return browser_asset_recovery_allowed(
        status=status,
        content_type=normalize_text(str(details.get("content_type") or "")),
        reason=normalize_text(str(details.get("reason") or failure.message)),
        error_category=normalize_text(str(details.get("error_category") or "")),
    )


def html_browser_recovery_allowed(failure: ProviderFailure | None) -> bool:
    if failure is None:
        return True
    if failure.code == "rate_limited":
        return False
    status_match = re.search(r"\bHTTP\s+(\d{3})\b", failure.message, re.IGNORECASE)
    return status_match is None or int(status_match.group(1)) in {401, 403}


__all__ = ["html_browser_recovery_allowed", "pdf_browser_recovery_allowed"]
