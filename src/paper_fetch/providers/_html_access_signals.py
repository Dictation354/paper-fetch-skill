"""Shared publisher HTML access-signal detection helpers."""

from __future__ import annotations

import importlib.util
import re

from ..utils import normalize_text

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None

CHALLENGE_PATTERNS = (
    "just a moment",
    "verify you are human",
    "checking your browser",
    "challenge-error-text",
    "attention required",
    "cloudflare",
)
ACCESS_GATE_PATTERN_MAP = {
    "check access",
    "purchase access",
    "purchase digital access to this article",
    "institutional access",
    "log in to your account",
    "login to your account",
    "subscribe to continue",
    "access through your institution",
    "rent or buy",
    "purchase this article",
    "access the full article",
    "get full access to this article",
    "access this article",
    "buy article pdf",
    "buy now",
    "view all access options to continue reading this article",
}
PAYWALL_PATTERNS = tuple(ACCESS_GATE_PATTERN_MAP)
NOT_FOUND_PATTERNS = (
    "doi not found",
    "page not found",
    "article not found",
    "content not found",
)
FAILURE_MESSAGES = {
    "cloudflare_challenge": "Encountered a challenge or CAPTCHA page while loading publisher HTML.",
    "publisher_not_found": "Publisher page was not found for this DOI.",
    "publisher_access_denied": "Publisher denied access to the full-text page.",
    "publisher_paywall": "Publisher paywall or access gate detected on the page.",
    "redirected_to_abstract": "Publisher redirected the full-text URL to an abstract page.",
    "abstract_only": "Publisher HTML only exposed abstract-level content without article body text.",
    "insufficient_body": "HTML extraction did not produce enough article body text.",
    "structured_article_not_fulltext": "Structured full text did not indicate complete article availability.",
    "structured_missing_body_sections": "Structured full text did not include article body sections beyond the abstract and references.",
}


class SciencePnasHtmlFailure(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def summarize_html(html_text: str, limit: int = 1000) -> str:
    if BeautifulSoup is None:
        return normalize_text(re.sub(r"<[^>]+>", " ", html_text))[:limit]
    parser = "lxml" if importlib.util.find_spec("lxml") is not None else "html.parser"
    soup = BeautifulSoup(html_text, parser)
    return " ".join(soup.stripped_strings)[:limit]


def html_failure_message(reason: str) -> str:
    return FAILURE_MESSAGES.get(reason, "The full-text route was not usable.")


def matched_access_gate_patterns(text: str) -> list[str]:
    normalized = normalize_text(text).lower()
    if not normalized:
        return []
    return [pattern for pattern in ACCESS_GATE_PATTERN_MAP if pattern in normalized]


def contains_access_gate_text(text: str) -> bool:
    return bool(matched_access_gate_patterns(text))


def detect_html_access_signals(
    title: str,
    text: str,
    response_status: int | None,
    *,
    redirected_to_abstract: bool = False,
    include_paywall_text: bool = True,
    explicit_no_access: bool = False,
) -> list[str]:
    signals: list[str] = []
    if redirected_to_abstract:
        signals.append("redirected_to_abstract")

    combined = normalize_text(" ".join([title, text])).lower()
    if any(pattern in combined for pattern in CHALLENGE_PATTERNS):
        signals.append("cloudflare_challenge")
    if response_status == 404 or any(pattern in combined for pattern in NOT_FOUND_PATTERNS):
        signals.append("publisher_not_found")
    if response_status in {401, 402, 403} and "cloudflare_challenge" not in signals:
        signals.append("publisher_access_denied")
    if explicit_no_access:
        signals.append("publisher_access_denied")
    if include_paywall_text and contains_access_gate_text(combined):
        signals.append("publisher_paywall")
    return list(dict.fromkeys(signals))


def detect_html_block(title: str, text: str, response_status: int | None) -> SciencePnasHtmlFailure | None:
    signals = detect_html_access_signals(title, text, response_status)
    if not signals:
        return None
    reason = signals[0]
    return SciencePnasHtmlFailure(reason, html_failure_message(reason))
