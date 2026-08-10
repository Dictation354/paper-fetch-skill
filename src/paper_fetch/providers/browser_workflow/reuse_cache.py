"""Short-lived in-process reuse for accepted browser HTML and DOI routes."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import threading
from typing import Any
import urllib.parse
from collections.abc import Iterable, Mapping

from cachetools import TTLCache

from ...provider_catalog import provider_domains
from ...publisher_identity import normalize_doi
from ...utils import normalize_text
from ..browser_runtime import BrowserFetchedHtml, BrowserRuntimeConfig


DEFAULT_BROWSER_PREFLIGHT_REUSE_MAXSIZE = 16
DEFAULT_BROWSER_PREFLIGHT_REUSE_TTL_SECONDS = 60
DEFAULT_BROWSER_DOI_ROUTE_HINT_MAXSIZE = 32
DEFAULT_BROWSER_DOI_ROUTE_HINT_TTL_SECONDS = 60

_PREFLIGHT_CONTEXT_KEY = ("browser_workflow", "preflight_html_producer")


def normalize_browser_cache_url(value: str | None) -> str:
    raw = normalize_text(value)
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        return ""
    scheme = parsed.scheme.lower()
    host = normalize_text(parsed.hostname).lower()
    if scheme not in {"http", "https"} or not host:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    netloc_host = f"[{host}]" if ":" in host else host
    netloc = netloc_host if port is None or default_port else f"{netloc_host}:{port}"
    return urllib.parse.urlunsplit(
        (scheme, netloc, parsed.path or "/", parsed.query, "")
    )


def _provider_url_allowed(provider: str, value: str | None) -> bool:
    normalized = normalize_browser_cache_url(value)
    if not normalized:
        return False
    host = normalize_text(urllib.parse.urlsplit(normalized).hostname).lower()
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in (
            normalize_text(item).lower() for item in provider_domains(provider)
        )
        if domain
    )


def _preflight_target_url_allowed(
    provider: str,
    doi: str,
    value: str | None,
) -> bool:
    if _provider_url_allowed(provider, value):
        return True
    normalized = normalize_browser_cache_url(value)
    if not normalized:
        return False
    parsed = urllib.parse.urlsplit(normalized)
    return parsed.hostname == "doi.org" and normalize_doi(
        urllib.parse.unquote(parsed.path).lstrip("/")
    ) == normalize_doi(doi)


def browser_runtime_fingerprint(config: BrowserRuntimeConfig) -> str:
    """Return a non-secret digest for reuse compatibility checks."""

    values = (
        normalize_text(config.provider).lower(),
        normalize_text(config.backend).lower(),
        "1" if config.headless else "0",
        normalize_text(config.user_agent),
        normalize_text(config.binary_path),
        normalize_text(config.cdp_endpoint),
        "1" if config.external_new_context else "0",
        normalize_text(str(config.profile_dir or "")),
        normalize_text(str(config.user_data_dir or "")),
        normalize_text(str(config.storage_state_path or "")),
        "1" if config.persist_storage_state else "0",
    )
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()


def mark_browser_preflight_producer(
    context: Any,
    *,
    target_url: str,
    save_storage_state: bool,
) -> None:
    setter = getattr(context, "set_session_cache", None)
    if not callable(setter):
        return
    setter(
        _PREFLIGHT_CONTEXT_KEY,
        {
            "target_url": normalize_browser_cache_url(target_url),
            "save_storage_state": bool(save_storage_state),
        },
        copy_value=True,
    )


def browser_preflight_producer(context: Any) -> Mapping[str, Any] | None:
    getter = getattr(context, "get_session_cache", None)
    if not callable(getter):
        return None
    value = getter(_PREFLIGHT_CONTEXT_KEY, copy_value=True)
    return value if isinstance(value, Mapping) else None


def _copy_html_result(value: BrowserFetchedHtml) -> BrowserFetchedHtml:
    return replace(
        value,
        response_headers=dict(value.response_headers or {}),
        browser_context_seed=dict(value.browser_context_seed or {}),
        screenshot_b64=None,
        image_payload=None,
        diagnostics=(
            dict(value.diagnostics) if isinstance(value.diagnostics, Mapping) else None
        ),
        staged_storage_state=None,
    )


def accepted_storage_state_was_committed(
    result: BrowserFetchedHtml,
    runtime: BrowserRuntimeConfig,
) -> bool:
    if not runtime.persist_storage_state or result.staged_storage_state is not None:
        return False
    diagnostics = result.diagnostics
    runtime_trace = (
        diagnostics.get("browser_runtime_trace")
        if isinstance(diagnostics, Mapping)
        else None
    )
    save_result = (
        runtime_trace.get("storage_state_save")
        if isinstance(runtime_trace, Mapping)
        else None
    )
    return bool(isinstance(save_result, Mapping) and save_result.get("saved"))


class BrowserPreflightReuseCache:
    """Thread-safe, bounded, one-shot cache of accepted browser HTML."""

    def __init__(
        self,
        *,
        maxsize: int = DEFAULT_BROWSER_PREFLIGHT_REUSE_MAXSIZE,
        ttl_seconds: float = DEFAULT_BROWSER_PREFLIGHT_REUSE_TTL_SECONDS,
        timer: Any | None = None,
    ) -> None:
        kwargs = {
            "maxsize": max(1, int(maxsize)),
            "ttl": max(0.001, float(ttl_seconds)),
        }
        if timer is not None:
            kwargs["timer"] = timer
        self._cache: TTLCache[tuple[str, str, str, str], BrowserFetchedHtml] = TTLCache(
            **kwargs
        )
        self._lock = threading.RLock()

    @staticmethod
    def _key(
        provider: str,
        doi: str,
        target_url: str,
        runtime: BrowserRuntimeConfig,
    ) -> tuple[str, str, str, str] | None:
        provider_key = normalize_text(provider).lower()
        normalized_doi = normalize_doi(doi)
        normalized_url = normalize_browser_cache_url(target_url)
        if not provider_key or not normalized_doi or not normalized_url:
            return None
        return (
            provider_key,
            normalized_doi,
            normalized_url,
            browser_runtime_fingerprint(runtime),
        )

    def store(
        self,
        *,
        provider: str,
        doi: str,
        target_url: str,
        runtime: BrowserRuntimeConfig,
        result: BrowserFetchedHtml,
    ) -> bool:
        key = self._key(provider, doi, target_url, runtime)
        if (
            key is None
            or not _preflight_target_url_allowed(provider, doi, target_url)
            or not _provider_url_allowed(provider, result.final_url)
            or not normalize_text(result.html)
            or not accepted_storage_state_was_committed(result, runtime)
        ):
            return False
        with self._lock:
            self._cache[key] = _copy_html_result(result)
        return True

    def consume(
        self,
        *,
        provider: str,
        doi: str,
        candidate_urls: Iterable[str],
        runtime: BrowserRuntimeConfig,
    ) -> tuple[BrowserFetchedHtml | None, dict[str, Any]]:
        provider_key = normalize_text(provider).lower()
        normalized_doi = normalize_doi(doi)
        fingerprint = browser_runtime_fingerprint(runtime)
        candidates = [
            normalized
            for item in candidate_urls
            if (normalized := normalize_browser_cache_url(item))
        ]
        matching_other_runtime = False
        with self._lock:
            # Accessing keys expires stale TTL entries before the lookup.
            active_keys = list(self._cache.keys())
            for candidate in candidates:
                key = (provider_key, normalized_doi, candidate, fingerprint)
                cached = self._cache.pop(key, None)
                if cached is not None:
                    return _copy_html_result(cached), {
                        "state": "hit",
                        "consumed": True,
                        "target_url": candidate,
                        "runtime_fingerprint": fingerprint,
                    }
                matching_other_runtime = matching_other_runtime or any(
                    existing[:3] == key[:3] and existing[3] != fingerprint
                    for existing in active_keys
                )
        return None, {
            "state": "miss",
            "consumed": False,
            "reason": (
                "runtime_fingerprint_mismatch"
                if matching_other_runtime
                else "not_found_or_expired"
            ),
            "runtime_fingerprint": fingerprint,
        }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


class BrowserDoiRouteHintCache:
    """Short-lived exact-DOI hint for a previously accepted provider URL."""

    def __init__(
        self,
        *,
        maxsize: int = DEFAULT_BROWSER_DOI_ROUTE_HINT_MAXSIZE,
        ttl_seconds: float = DEFAULT_BROWSER_DOI_ROUTE_HINT_TTL_SECONDS,
        timer: Any | None = None,
    ) -> None:
        kwargs = {
            "maxsize": max(1, int(maxsize)),
            "ttl": max(0.001, float(ttl_seconds)),
        }
        if timer is not None:
            kwargs["timer"] = timer
        self._cache: TTLCache[tuple[str, str], str] = TTLCache(**kwargs)
        self._lock = threading.RLock()

    def store(self, *, provider: str, doi: str, url: str) -> bool:
        provider_key = normalize_text(provider).lower()
        normalized_doi = normalize_doi(doi)
        normalized_url = normalize_browser_cache_url(url)
        normalized_path = urllib.parse.unquote(
            urllib.parse.urlsplit(normalized_url).path
        ).lower()
        if (
            not provider_key
            or not normalized_doi
            or not _provider_url_allowed(provider_key, normalized_url)
            or "/doi/abs/" in normalized_path
            or "/doi/abstract/" in normalized_path
        ):
            return False
        with self._lock:
            self._cache[(provider_key, normalized_doi)] = normalized_url
        return True

    def reorder(
        self,
        *,
        provider: str,
        doi: str,
        candidate_urls: Iterable[str],
    ) -> tuple[list[str], dict[str, Any]]:
        candidates: list[str] = []
        for value in candidate_urls:
            normalized = normalize_browser_cache_url(value) or normalize_text(value)
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        key = (normalize_text(provider).lower(), normalize_doi(doi))
        with self._lock:
            hint = self._cache.get(key)
        if not hint or not _provider_url_allowed(provider, hint):
            return candidates, {
                "state": "miss",
                "source": "doi_route_hint",
                "reordered": False,
            }
        reordered = [
            hint,
            *(candidate for candidate in candidates if candidate != hint),
        ]
        return reordered, {
            "state": "hit",
            "source": "doi_route_hint",
            "reordered": reordered != candidates,
            "hint_url": hint,
        }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


DEFAULT_BROWSER_PREFLIGHT_REUSE_CACHE = BrowserPreflightReuseCache()
DEFAULT_BROWSER_DOI_ROUTE_HINT_CACHE = BrowserDoiRouteHintCache()


__all__ = [
    "DEFAULT_BROWSER_DOI_ROUTE_HINT_CACHE",
    "DEFAULT_BROWSER_PREFLIGHT_REUSE_CACHE",
    "BrowserDoiRouteHintCache",
    "BrowserPreflightReuseCache",
    "accepted_storage_state_was_committed",
    "browser_preflight_producer",
    "browser_runtime_fingerprint",
    "mark_browser_preflight_producer",
    "normalize_browser_cache_url",
]
