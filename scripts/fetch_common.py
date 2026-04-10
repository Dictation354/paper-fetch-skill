#!/usr/bin/env python3
"""Shared helpers used by the fetch workflow and publisher clients."""

from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from hashlib import sha1
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_ENV_FILE = ROOT_DIR / ".env"

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90
DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_CACHE_CAPACITY = 128
DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1024 * 1024
DEFAULT_USER_AGENT = "paper-fetch-skill/0.2"
USER_AGENT_ENV_VAR = "PAPER_FETCH_SKILL_USER_AGENT"
TEXTUAL_CONTENT_TYPES = (
    "text/",
    "application/xml",
    "text/xml",
    "application/json",
    "application/jats+xml",
)
SENSITIVE_CACHE_HEADER_NAMES = {
    "authorization",
    "wiley-tdm-client-token",
    "x-els-apikey",
    "x-els-insttoken",
    "cr-clickthrough-client-token",
    "proxy-authorization",
}
UNSTABLE_CACHE_HEADER_NAMES = {
    "x-els-reqid",
}
SENSITIVE_QUERY_PARAM_NAMES = {
    "api_key",
    "apikey",
    "token",
    "auth",
    "authorization",
    "mailto",
}
REDACTED_CACHE_VALUE = "***"


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple .env file without external dependencies."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value

    return values


def build_runtime_env(
    base_env: Mapping[str, str] | None = None,
    *,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, str]:
    """Merge file-based defaults with the current process environment."""
    merged = load_env_file(env_file)
    merged.update(dict(base_env or os.environ))
    return merged


class RequestFailure(Exception):
    """HTTP or transport failure."""

    def __init__(
        self,
        status_code: int | None,
        message: str,
        *,
        body: bytes = b"",
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})
        self.url = url
        self.retry_after_seconds = retry_after_seconds


class ProviderFailure(Exception):
    """Provider-specific failure with a stable category."""

    def __init__(self, code: str, message: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds


@dataclass
class RawFulltextPayload:
    provider: str
    source_url: str
    content_type: str
    body: bytes
    metadata: dict[str, Any] = field(default_factory=dict)
    needs_local_copy: bool = False


class HttpTransport:
    """Minimal HTTP transport that avoids third-party dependencies.

    The in-memory cache is not thread-safe. When you parallelize work across
    threads or workers, instantiate one transport per thread/worker instead of
    sharing a single object.
    """

    def __init__(
        self,
        *,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        cache_capacity: int = DEFAULT_CACHE_CAPACITY,
        max_cacheable_body_bytes: int = DEFAULT_MAX_CACHEABLE_BODY_BYTES,
    ) -> None:
        self.cache_ttl = max(0, int(cache_ttl))
        self.cache_capacity = max(0, int(cache_capacity))
        self.max_cacheable_body_bytes = max(0, int(max_cacheable_body_bytes))
        self._cache: OrderedDict[tuple[str, str, tuple[tuple[str, str], ...]], tuple[float, dict[str, Any]]] = OrderedDict()

    def _build_cache_key(self, method: str, url: str, headers: Mapping[str, str]) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
        if method.upper() != "GET" or self.cache_ttl <= 0 or self.cache_capacity <= 0:
            return None
        normalized_headers = tuple(
            sorted(
                (str(key).lower(), self._normalize_header_value_for_cache(str(key), str(value)))
                for key, value in headers.items()
            )
        )
        return (method.upper(), redact_url_for_cache(url), normalized_headers)

    def _normalize_header_value_for_cache(self, key: str, value: str) -> str:
        normalized_key = key.lower()
        if normalized_key in SENSITIVE_CACHE_HEADER_NAMES:
            return REDACTED_CACHE_VALUE
        if normalized_key in UNSTABLE_CACHE_HEADER_NAMES:
            return "<volatile>"
        return value

    def _clone_response(self, response: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status_code": response.get("status_code"),
            "headers": dict(response.get("headers") or {}),
            "body": response.get("body", b""),
            "url": response.get("url"),
        }

    def _load_cached_response(self, cache_key: tuple[str, str, tuple[tuple[str, str], ...]] | None) -> dict[str, Any] | None:
        if cache_key is None:
            return None
        cached_entry = self._cache.get(cache_key)
        if cached_entry is None:
            return None
        expires_at, response = cached_entry
        if expires_at <= time.monotonic():
            self._cache.pop(cache_key, None)
            return None
        self._cache.move_to_end(cache_key)
        return self._clone_response(response)

    def _store_cached_response(
        self,
        cache_key: tuple[str, str, tuple[tuple[str, str], ...]] | None,
        response: Mapping[str, Any],
    ) -> None:
        if cache_key is None:
            return
        if not self._is_cacheable_response(response):
            return
        self._cache[cache_key] = (time.monotonic() + self.cache_ttl, self._clone_response(response))
        self._cache.move_to_end(cache_key)
        while len(self._cache) > self.cache_capacity:
            self._cache.popitem(last=False)

    def _is_cacheable_response(self, response: Mapping[str, Any]) -> bool:
        if self.max_cacheable_body_bytes <= 0:
            return False
        body = response.get("body", b"")
        if not isinstance(body, (bytes, bytearray)) or len(body) > self.max_cacheable_body_bytes:
            return False
        content_type = str((response.get("headers") or {}).get("content-type") or "")
        return is_textual_content_type(content_type)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        retry_on_rate_limit: bool = False,
        rate_limit_retries: int = 1,
        max_rate_limit_wait_seconds: int = 5,
    ) -> dict[str, Any]:
        if query:
            encoded_query = urllib.parse.urlencode(query, doseq=True)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{encoded_query}"

        request_headers = {key: value for key, value in (headers or {}).items() if value is not None}
        cache_key = self._build_cache_key(method, url, request_headers)
        cached_response = self._load_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        attempts_remaining = max(0, int(rate_limit_retries))
        while True:
            request = urllib.request.Request(url=url, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = response.read()
                    response_payload = {
                        "status_code": response.status,
                        "headers": {key.lower(): value for key, value in response.headers.items()},
                        "body": payload,
                        "url": redact_url_for_cache(response.geturl()),
                    }
                    self._store_cached_response(cache_key, response_payload)
                    return response_payload
            except urllib.error.HTTPError as exc:
                body = exc.read()
                headers_map = {key.lower(): value for key, value in exc.headers.items()}
                retry_after_seconds = parse_retry_after_seconds(headers_map.get("retry-after"))
                if (
                    exc.code == 429
                    and retry_on_rate_limit
                    and attempts_remaining > 0
                    and retry_after_seconds is not None
                    and retry_after_seconds <= max_rate_limit_wait_seconds
                ):
                    attempts_remaining -= 1
                    time.sleep(max(0, retry_after_seconds))
                    continue
                raise RequestFailure(
                    exc.code,
                    build_http_error_message(exc.code, url, retry_after_seconds=retry_after_seconds),
                    body=body,
                    headers=headers_map,
                    url=redact_url_for_cache(exc.geturl() or url),
                    retry_after_seconds=retry_after_seconds,
                ) from exc
            except urllib.error.URLError as exc:
                raise RequestFailure(
                    None,
                    f"Network error for {redact_url_for_cache(url)}: {exc.reason}",
                    url=redact_url_for_cache(url),
                ) from exc


def build_user_agent(env: Mapping[str, str]) -> str:
    base = env.get(USER_AGENT_ENV_VAR, "").strip() or DEFAULT_USER_AGENT
    mailto = env.get("CROSSREF_MAILTO", "").strip()
    if mailto and "mailto:" not in base and "@" not in base:
        return f"{base} (mailto:{mailto})"
    return base


def redact_url_for_cache(url: str) -> str:
    if not url:
        return url
    parsed = urllib.parse.urlsplit(url)
    if not parsed.query:
        return url
    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = urllib.parse.urlencode(
        [
            (
                key,
                REDACTED_CACHE_VALUE if key.lower() in SENSITIVE_QUERY_PARAM_NAMES else value,
            )
            for key, value in query_items
        ],
        doseq=True,
    )
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, redacted_query, parsed.fragment))


def parse_retry_after_seconds(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return max(0, int(normalized))
    try:
        parsed = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = (parsed - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(delta))


def build_http_error_message(status_code: int | None, url: str, *, retry_after_seconds: int | None = None) -> str:
    message = f"HTTP {status_code} for {redact_url_for_cache(url)}"
    if retry_after_seconds is not None:
        message += f" (Retry-After: {retry_after_seconds}s)"
    return message


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def strip_html_tags(value: str | None) -> str | None:
    if not value:
        return value
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def first_list_item(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def date_parts_to_string(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    parts = node.get("date-parts")
    if not isinstance(parts, list) or not parts:
        return None
    first = parts[0]
    if not isinstance(first, list) or not first:
        return None
    return "-".join(str(part) for part in first)


def sanitize_filename(value: str) -> str:
    original = value or ""
    digest = sha1(original.encode("utf-8", errors="ignore")).hexdigest()[:8]
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", original)
    filename = re.sub(r"_+", "_", filename).strip("._-")
    if not filename:
        return f"fulltext_{digest}"

    max_length = 180
    if len(filename) <= max_length:
        return filename

    suffix = f"_{digest}"
    truncated = filename[:max_length].rstrip("._-")
    truncated = truncated[: max(1, max_length - len(suffix))].rstrip("._-")
    return f"{truncated or 'fulltext'}{suffix}"


def canonical_author_key(name: str) -> str:
    normalized = normalize_author_name(name)
    if not normalized:
        return ""
    if "," in normalized:
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
        if len(parts) >= 2:
            normalized = " ".join(parts[1:] + [parts[0]])
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_author_name(name: str) -> str:
    text = (name or "").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def dedupe_authors(authors: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for author in authors:
        normalized_author = normalize_author_name(author)
        key = canonical_author_key(normalized_author)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized_author)
    return deduped


def extension_from_content_type(content_type: str | None, source_url: str | None = None) -> str:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    known = {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/xml": ".xml",
        "application/xml": ".xml",
        "application/jats+xml": ".xml",
        "application/json": ".json",
        "text/html": ".html",
    }
    if normalized in known:
        return known[normalized]
    if source_url:
        guessed = Path(urllib.parse.urlparse(source_url).path).suffix
        if guessed:
            return guessed
    return ".bin"


def build_output_path(
    output_dir: Path | None,
    doi: str | None,
    title: str | None,
    content_type: str | None,
    source_url: str | None,
) -> Path | None:
    if output_dir is None:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(doi or title or "article")
    extension = extension_from_content_type(content_type, source_url)
    return output_dir / f"{base_name}{extension}"


def save_payload(output_path: Path | None, body: bytes) -> str | None:
    if output_path is None:
        return None
    output_path.write_bytes(body)
    return str(output_path)


def build_text_preview(body: bytes, content_type: str | None) -> str | None:
    normalized = (content_type or "").split(";", 1)[0].lower()
    if normalized and not is_textual_content_type(normalized):
        return None
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500] or None


def is_xml_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    return normalized in {"application/xml", "text/xml", "application/jats+xml"} or normalized.endswith("+xml")


def is_textual_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    if not normalized:
        return False
    return any(normalized.startswith(prefix) or normalized == prefix for prefix in TEXTUAL_CONTENT_TYPES) or normalized.endswith("+xml")


def empty_asset_results() -> dict[str, list[dict[str, Any]]]:
    return {
        "assets": [],
        "asset_failures": [],
    }


def build_asset_output_path(
    asset_dir: Path,
    source_href: str | None,
    content_type: str | None,
    source_url: str | None,
    used_names: set[str],
) -> Path:
    candidate_name = ""
    for value in (source_url, source_href):
        if not value:
            continue
        name = Path(urllib.parse.urlparse(value).path).name
        if name:
            candidate_name = name
            break

    stem = sanitize_filename(Path(candidate_name).stem or "asset")
    suffix = Path(candidate_name).suffix or extension_from_content_type(content_type, source_url or source_href)
    filename = f"{stem}{suffix}"

    counter = 2
    while filename in used_names or (asset_dir / filename).exists():
        filename = f"{stem}_{counter}{suffix}"
        counter += 1

    used_names.add(filename)
    return asset_dir / filename


def map_request_failure(exc: RequestFailure) -> ProviderFailure:
    if exc.status_code in {401, 403}:
        return ProviderFailure("no_access", str(exc))
    if exc.status_code == 404:
        return ProviderFailure("no_result", str(exc))
    if exc.status_code == 429:
        return ProviderFailure("rate_limited", str(exc), retry_after_seconds=exc.retry_after_seconds)
    if exc.status_code in {400, 406, 422}:
        return ProviderFailure("error", str(exc))
    if exc.status_code is None:
        return ProviderFailure("error", str(exc))
    if exc.status_code >= 500:
        return ProviderFailure("error", str(exc))
    return ProviderFailure("error", str(exc))


def combine_provider_failures(failures: list[tuple[str, ProviderFailure]]) -> ProviderFailure:
    priority = {
        "no_access": 0,
        "no_result": 1,
        "rate_limited": 2,
        "error": 3,
        "not_configured": 4,
        "not_supported": 5,
    }
    selected_label, selected_failure = min(
        failures,
        key=lambda item: priority.get(item[1].code, 99),
    )
    message = "; ".join(f"{label}: {failure.message}" for label, failure in failures)
    if len(failures) == 1:
        message = f"{selected_label}: {selected_failure.message}"
    return ProviderFailure(
        selected_failure.code,
        message,
        retry_after_seconds=selected_failure.retry_after_seconds,
    )


class ProviderClient:
    """Provider interface used by the fetch workflow."""

    name = "provider"

    def fetch_metadata(self, query: Mapping[str, str | None]) -> dict[str, Any]:
        raise ProviderFailure("not_supported", f"{self.name} metadata retrieval is not available.")

    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, Any]) -> RawFulltextPayload:
        raise ProviderFailure("not_supported", f"{self.name} raw full-text retrieval is not available.")

    def fetch_fulltext(self, doi: str, metadata: Mapping[str, Any], output_dir: Path | None) -> dict[str, Any]:
        raise ProviderFailure("not_supported", f"{self.name} full-text retrieval is not available.")
