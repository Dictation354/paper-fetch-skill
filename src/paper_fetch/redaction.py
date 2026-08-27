"""Dependency-light credential-name and diagnostic-text redaction rules."""

from __future__ import annotations

from collections.abc import Iterable
import functools
import re


_CREDENTIAL_NAME_TOKENS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "COOKIE",
    "MAILTO",
)
_SENSITIVE_CONFIGURATION_NAMES = frozenset(
    {
        "PAPER_FETCH_AMS_STORAGE_STATE_JSON",
        "PAPER_FETCH_WILEY_STORAGE_STATE_JSON",
    }
)
_DIAGNOSTIC_URL_IN_TEXT_RE = re.compile(
    r"(?P<base>(?:https?://|/)[^\s\"'<>?]+)\?[^\s\"'<>]*",
    re.IGNORECASE,
)
_DIAGNOSTIC_FRAGMENT_IN_TEXT_RE = re.compile(
    r"(?P<base>(?:https?://|/)[^\s\"'<>#]+)#[^\s\"'<>]*",
    re.IGNORECASE,
)
_BASE_DIAGNOSTIC_SECRET_NAMES = frozenset(
    {
        "x-amz-signature",
        "signature",
        "token",
        "api_key",
        "api-key",
        "apikey",
        "access_key",
        "access-key",
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "password",
    }
)


def is_sensitive_configuration_name(name: str) -> bool:
    """Return whether an environment/configuration name may hold a secret."""

    normalized = str(name or "").upper()
    return (
        any(token in normalized for token in _CREDENTIAL_NAME_TOKENS)
        or normalized in _SENSITIVE_CONFIGURATION_NAMES
    )


@functools.cache
def _diagnostic_secret_assignment_re(
    additional_names: tuple[str, ...],
) -> re.Pattern[str]:
    names = _BASE_DIAGNOSTIC_SECRET_NAMES | frozenset(additional_names)
    name_pattern = "|".join(
        re.escape(name) for name in sorted(names, key=len, reverse=True)
    )
    return re.compile(
        rf"(?P<name>\b(?:{name_pattern})\b[\"']?\s*[=:]\s*[\"']?\s*)"
        r"(?:bearer\s+)?[^\s&;,\"'<>}\]]+",
        re.IGNORECASE,
    )


def redact_text_for_diagnostics(
    value: str,
    *,
    additional_secret_names: Iterable[str] = (),
) -> str:
    """Remove URL queries/fragments and credential assignments from text."""

    text = str(value or "")
    text = _DIAGNOSTIC_URL_IN_TEXT_RE.sub(
        lambda match: f"{match.group('base')}?[redacted]",
        text,
    )
    text = _DIAGNOSTIC_FRAGMENT_IN_TEXT_RE.sub(
        lambda match: match.group("base"),
        text,
    )
    normalized_names = tuple(
        sorted(
            {
                str(name).strip().lower()
                for name in additional_secret_names
                if str(name).strip()
            }
        )
    )
    return _diagnostic_secret_assignment_re(normalized_names).sub(
        lambda match: f"{match.group('name')}[redacted]",
        text,
    )


__all__ = ["is_sensitive_configuration_name", "redact_text_for_diagnostics"]
