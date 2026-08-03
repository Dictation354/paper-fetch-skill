"""Shared publisher HTML access-signal detection helpers."""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any

from ...utils import normalize_text
from ...quality.reason_codes import (
    ABSTRACT_ONLY,
    AWS_WAF_CHALLENGE,
    CLOUDFLARE_CHALLENGE,
    EMPTY_ARTICLE_SHELL,
    INSUFFICIENT_BODY,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_NOT_FOUND,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
)
from .html_tags import HTML_DROP_TAGS
from .parsing import choose_parser
from .ui_tokens import SPRINGER_PREVIEW_PHRASE

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

CHALLENGE_PATTERNS = (
    "just a moment",
    "verify you are human",
    "checking your browser",
    "challenge-error-text",
    "attention required",
    "cloudflare",
    "radware bot manager",
    "perfdrive",
    "confirm you are a human",
    "confirm you are human",
    "complete the security check",
    "h-captcha",
    "not a robot",
    "aws waf",
    "awswaf",
)
CLIENT_CHALLENGE_TITLE = "client challenge"
GENERIC_CHALLENGE_HTML_PATTERNS = ("_fs-ch-",)
AWS_WAF_HTML_PATTERNS = (
    "token.awswaf.com",
    "awswaf.com",
    "awswaf",
)
AWS_WAF_HEADER_NAMES = frozenset({"x-amzn-waf-action"})
CLOUDFLARE_CHALLENGE_TITLE_TOKENS = tuple(
    token
    for token in CHALLENGE_PATTERNS
    if token in {"just a moment", "attention required", "checking your browser"}
)
ACCESS_DENIED_TOKEN = "access denied"
LOGIN_GATE_TOKENS = ("sign in", "sign-in", "log in", "login")
ACCESS_GATE_CHECK_ACCESS_LABEL = "check access"
ACCESS_GATE_ACCESS_PROVIDED_BY_LABEL = "access provided by"
ACCESS_GATE_BUY_NOW_LABEL = "buy now"
ACCESS_GATE_VIEW_OPTIONS_LABEL = "view access options"
ACCESS_GATE_INSTITUTIONAL_LOGIN_LABEL = "institutional login"
ACCESS_GATE_LABELS = (
    ACCESS_GATE_CHECK_ACCESS_LABEL,
    ACCESS_GATE_ACCESS_PROVIDED_BY_LABEL,
    ACCESS_GATE_BUY_NOW_LABEL,
    ACCESS_GATE_VIEW_OPTIONS_LABEL,
    ACCESS_GATE_INSTITUTIONAL_LOGIN_LABEL,
)
MARKDOWN_ACCESS_NOISE_LABELS = (
    ACCESS_GATE_ACCESS_PROVIDED_BY_LABEL,
    "buy article",
    ACCESS_GATE_VIEW_OPTIONS_LABEL,
    "you have full access to this",
)
MARKDOWN_SHORT_ACCESS_GATE_TOKENS = (
    *LOGIN_GATE_TOKENS,
    ACCESS_GATE_VIEW_OPTIONS_LABEL,
    ACCESS_GATE_CHECK_ACCESS_LABEL,
    ACCESS_GATE_BUY_NOW_LABEL,
)
COMMON_ACCESS_BLOCK_TOKENS = (
    "unable to complete your request",
    "your request has been blocked",
    "verify you are human",
    "captcha",
    ACCESS_DENIED_TOKEN,
)
SUPPLEMENTARY_BLOCKING_TITLE_TOKENS = (
    *CLOUDFLARE_CHALLENGE_TITLE_TOKENS,
    *LOGIN_GATE_TOKENS,
    ACCESS_DENIED_TOKEN,
)
SUPPLEMENTARY_BLOCKING_BODY_TOKENS = (
    *(
        token
        for token in CHALLENGE_PATTERNS
        if token in {"checking your browser", "cloudflare"}
    ),
    "enable javascript and cookies",
    "please sign in",
    ACCESS_GATE_INSTITUTIONAL_LOGIN_LABEL,
    ACCESS_DENIED_TOKEN,
)
ASSET_ACCESS_BLOCK_LABELS = (
    "unauthorized",
    "forbidden",
    "authentication",
    "authorization",
    "permission",
    ACCESS_DENIED_TOKEN,
    "access gate",
    "license",
)
ASSET_BLOCKING_REASON_TOKENS = ASSET_ACCESS_BLOCK_LABELS
ACCESS_GATE_PATTERNS = (
    ACCESS_GATE_CHECK_ACCESS_LABEL,
    "purchase access",
    "purchase digital access to this article",
    "institutional access",
    "log in to your account",
    "login to your account",
    "subscribe to continue",
    "access through your institution",
    "rent or buy",
    "purchase this article",
    "purchase article",
    "access the full article",
    "get full access to this article",
    "get access",
    "access this article",
    "buy article pdf",
    ACCESS_GATE_BUY_NOW_LABEL,
    "sign in to access",
    ACCESS_GATE_VIEW_OPTIONS_LABEL,
    "view all access options to continue reading this article",
    ACCESS_GATE_INSTITUTIONAL_LOGIN_LABEL,
    SPRINGER_PREVIEW_PHRASE,
)
NOT_FOUND_PATTERNS = (
    "doi not found",
    "page not found",
    "article not found",
    "content not found",
)
FAILURE_MESSAGES = {
    AWS_WAF_CHALLENGE: "Encountered an AWS WAF challenge page while loading publisher HTML.",
    CLOUDFLARE_CHALLENGE: "Encountered a challenge or CAPTCHA page while loading publisher HTML.",
    PUBLISHER_NOT_FOUND: "Publisher page was not found for this DOI.",
    PUBLISHER_ACCESS_DENIED: "Publisher denied access to the full-text page.",
    PUBLISHER_PAYWALL: "Publisher paywall or access gate detected on the page.",
    REDIRECTED_TO_ABSTRACT: "Publisher redirected the full-text URL to an abstract page.",
    ABSTRACT_ONLY: "Publisher HTML only exposed abstract-level content without article body text.",
    INSUFFICIENT_BODY: "HTML extraction did not produce enough article body text.",
    EMPTY_ARTICLE_SHELL: "Publisher HTML returned an empty article shell without a body DOM.",
    STRUCTURED_ARTICLE_NOT_FULLTEXT: "Structured full text did not indicate complete article availability.",
    STRUCTURED_MISSING_BODY_SECTIONS: "Structured full text did not include article body sections beyond the abstract and references.",
}


class HtmlExtractionFailure(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details: dict[str, object] | None = None
        self.html_result: object | None = None


def summarize_html(html_text: str, limit: int = 1000) -> str:
    soup = BeautifulSoup(html_text, choose_parser())
    return " ".join(soup.stripped_strings)[:limit]


def summarize_visible_html(html_text: str, limit: int = 1000) -> str:
    """Summarize human-visible HTML without hidden challenge/script fallbacks."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html_text, choose_parser())
    for node in list(soup.find_all(HTML_DROP_TAGS)):
        node.decompose()
    return " ".join(soup.stripped_strings)[:limit]


def detect_challenge_provider(
    *,
    html_text: str = "",
    response_headers: Mapping[str, Any] | None = None,
) -> str | None:
    """Identify a challenge vendor from raw response evidence when available."""

    normalized_headers = {
        normalize_text(str(key)).lower(): normalize_text(str(value)).lower()
        for key, value in dict(response_headers or {}).items()
        if normalize_text(str(key))
    }
    normalized_html = normalize_text(html_text).lower()
    if AWS_WAF_HEADER_NAMES.intersection(normalized_headers) or any(
        pattern in normalized_html for pattern in AWS_WAF_HTML_PATTERNS
    ):
        return "aws_waf"
    return None


def html_failure_message(reason: str) -> str:
    return FAILURE_MESSAGES.get(reason, "The full-text route was not usable.")


def matched_access_gate_patterns(text: str) -> list[str]:
    normalized = normalize_text(text).lower()
    if not normalized:
        return []
    return [pattern for pattern in ACCESS_GATE_PATTERNS if pattern in normalized]


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
    html_text: str = "",
    response_headers: Mapping[str, Any] | None = None,
) -> list[str]:
    signals: list[str] = []
    if redirected_to_abstract:
        signals.append(REDIRECTED_TO_ABSTRACT)

    normalized_title = normalize_text(title).lower()
    combined = normalize_text(" ".join([title, text])).lower()
    challenge_provider = detect_challenge_provider(
        html_text=html_text,
        response_headers=response_headers,
    )
    if challenge_provider == "aws_waf":
        signals.append(AWS_WAF_CHALLENGE)
    elif (
        normalized_title == CLIENT_CHALLENGE_TITLE
        or any(pattern in combined for pattern in CHALLENGE_PATTERNS)
        or any(
            pattern in html_text.lower() for pattern in GENERIC_CHALLENGE_HTML_PATTERNS
        )
    ):
        signals.append(CLOUDFLARE_CHALLENGE)
    if response_status == 404 or any(
        pattern in combined for pattern in NOT_FOUND_PATTERNS
    ):
        signals.append(PUBLISHER_NOT_FOUND)
    if response_status in {401, 402, 403} and not {
        AWS_WAF_CHALLENGE,
        CLOUDFLARE_CHALLENGE,
    }.intersection(signals):
        signals.append(PUBLISHER_ACCESS_DENIED)
    if explicit_no_access:
        signals.append(PUBLISHER_ACCESS_DENIED)
    if include_paywall_text and contains_access_gate_text(combined):
        signals.append(PUBLISHER_PAYWALL)
    return list(dict.fromkeys(signals))


def detect_html_block(
    title: str,
    text: str,
    response_status: int | None,
    *,
    html_text: str = "",
    response_headers: Mapping[str, Any] | None = None,
) -> HtmlExtractionFailure | None:
    signals = detect_html_access_signals(
        title,
        text,
        response_status,
        html_text=html_text,
        response_headers=response_headers,
    )
    if not signals:
        return None
    reason = signals[0]
    return HtmlExtractionFailure(reason, html_failure_message(reason))
