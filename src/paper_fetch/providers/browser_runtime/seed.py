"""Browser context seed helpers shared by provider workflows."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping
import urllib.parse

from ...utils import normalize_text
from .types import BrowserContextSeed
import contextlib

CLOUDFLARE_COOKIE_NAMES = frozenset(
    {
        "_cfuvid",
        "__cf_bm",
        "cf_clearance",
    }
)
_CLOUDFLARE_COOKIE_PREFIXES = ("cf_chl_",)


def normalize_browser_cookie_for_playwright(
    cookie: dict[str, Any],
    fallback_url: str | None = None,
) -> dict[str, Any] | None:
    name = normalize_text(str(cookie.get("name") or ""))
    if not name:
        return None

    normalized: dict[str, Any] = {
        "name": name,
        "value": str(cookie.get("value") or ""),
    }
    domain = normalize_text(str(cookie.get("domain") or ""))
    path = normalize_text(str(cookie.get("path") or "")) or "/"
    if domain:
        normalized["domain"] = domain
        normalized["path"] = path
    elif fallback_url:
        normalized["url"] = fallback_url
    else:
        return None

    if cookie.get("secure") is not None:
        normalized["secure"] = bool(cookie.get("secure"))
    if cookie.get("httpOnly") is not None:
        normalized["httpOnly"] = bool(cookie.get("httpOnly"))

    expires_value = cookie.get("expiry")
    if expires_value is None:
        expires_value = cookie.get("expires")
    if expires_value is not None:
        with contextlib.suppress(TypeError, ValueError):
            normalized["expires"] = float(expires_value)

    same_site = normalize_text(str(cookie.get("sameSite") or ""))
    canonical_same_site = {
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }.get(same_site.lower())
    if canonical_same_site:
        normalized["sameSite"] = canonical_same_site
    return normalized


def normalize_browser_cookies_for_playwright(
    cookies: list[dict[str, Any]] | None,
    fallback_url: str | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for cookie in cookies or []:
        if not isinstance(cookie, dict):
            continue
        normalized_cookie = normalize_browser_cookie_for_playwright(
            cookie,
            fallback_url=fallback_url,
        )
        if normalized_cookie is not None:
            normalized.append(normalized_cookie)
    return normalized


def browser_cookie_matches_url(cookie: Mapping[str, Any], url: str | None) -> bool:
    normalized_url = normalize_text(url)
    if not normalized_url:
        return True
    parsed = urllib.parse.urlparse(normalized_url)
    host = normalize_text(parsed.hostname or "").lower()
    if not host:
        return True

    domain = normalize_text(str(cookie.get("domain") or "")).lower().lstrip(".")
    if domain:
        return host == domain or host.endswith(f".{domain}")

    cookie_url = normalize_text(str(cookie.get("url") or ""))
    if cookie_url:
        cookie_host = normalize_text(
            urllib.parse.urlparse(cookie_url).hostname or ""
        ).lower()
        return bool(
            cookie_host and (host == cookie_host or host.endswith(f".{cookie_host}"))
        )
    return True


def filter_browser_cookies_for_url(
    cookies: list[dict[str, Any]] | None,
    url: str | None,
) -> list[dict[str, Any]]:
    return [
        cookie
        for cookie in cookies or []
        if isinstance(cookie, dict) and browser_cookie_matches_url(cookie, url)
    ]


def browser_context_seed_from_mapping(
    seed: Mapping[str, Any] | None,
) -> BrowserContextSeed:
    if not isinstance(seed, Mapping):
        return {
            "browser_cookies": [],
            "browser_user_agent": None,
            "browser_final_url": None,
        }
    final_url = normalize_text(str(seed.get("browser_final_url") or "")) or None
    typed: BrowserContextSeed = {
        "browser_cookies": normalize_browser_cookies_for_playwright(
            seed.get("browser_cookies")
            if isinstance(seed.get("browser_cookies"), list)
            else None,
            fallback_url=final_url,
        ),
        "browser_user_agent": normalize_text(str(seed.get("browser_user_agent") or ""))
        or None,
        "browser_final_url": final_url,
    }
    html_fetcher = normalize_text(str(seed.get("paper_fetch_html_fetcher") or ""))
    if html_fetcher:
        typed["paper_fetch_html_fetcher"] = html_fetcher
    diagnostics = seed.get("diagnostics")
    if isinstance(diagnostics, Mapping):
        typed["diagnostics"] = dict(diagnostics)
    metadata = seed.get("metadata")
    if isinstance(metadata, Mapping):
        typed["metadata"] = dict(metadata)
    return typed


def browser_context_seed_to_mapping(
    seed: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return dict(browser_context_seed_from_mapping(seed))


def merge_browser_context_seeds(*seeds: Mapping[str, Any] | None) -> dict[str, Any]:
    merged_cookies: list[dict[str, Any]] = []
    cookie_positions: dict[tuple[str, str, str, str], int] = {}
    merged_user_agent: str | None = None
    merged_final_url: str | None = None
    merged_html_fetcher: str | None = None
    merged_diagnostics: dict[str, Any] = {}
    merged_metadata: dict[str, Any] = {}

    for seed in seeds:
        typed_seed = browser_context_seed_from_mapping(seed)
        if not typed_seed:
            continue

        cookies = typed_seed.get("browser_cookies") or []
        for cookie in cookies:
            key = (
                normalize_text(str(cookie.get("name") or "")),
                normalize_text(str(cookie.get("domain") or "")),
                normalize_text(str(cookie.get("path") or "")),
                normalize_text(str(cookie.get("url") or "")),
            )
            position = cookie_positions.get(key)
            if position is None:
                cookie_positions[key] = len(merged_cookies)
                merged_cookies.append(cookie)
            else:
                merged_cookies[position] = cookie

        user_agent = normalize_text(str(typed_seed.get("browser_user_agent") or ""))
        if user_agent:
            merged_user_agent = user_agent

        final_url = normalize_text(str(typed_seed.get("browser_final_url") or ""))
        if final_url:
            merged_final_url = final_url
        html_fetcher = normalize_text(
            str(typed_seed.get("paper_fetch_html_fetcher") or "")
        )
        if html_fetcher:
            merged_html_fetcher = html_fetcher
        diagnostics = typed_seed.get("diagnostics")
        if isinstance(diagnostics, Mapping):
            merged_diagnostics.update(diagnostics)
        metadata = typed_seed.get("metadata")
        if isinstance(metadata, Mapping):
            merged_metadata.update(metadata)

    merged: BrowserContextSeed = {
        "browser_cookies": merged_cookies,
        "browser_user_agent": merged_user_agent,
        "browser_final_url": merged_final_url,
    }
    if merged_html_fetcher:
        merged["paper_fetch_html_fetcher"] = merged_html_fetcher
    if merged_diagnostics:
        merged["diagnostics"] = merged_diagnostics
    if merged_metadata:
        merged["metadata"] = merged_metadata
    return dict(merged)


def parse_optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
