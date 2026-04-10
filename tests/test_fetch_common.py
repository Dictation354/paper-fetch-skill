from __future__ import annotations

import importlib.util
import io
import sys
import unittest
import urllib.error
import warnings
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "fetch_common.py"
SPEC = importlib.util.spec_from_file_location("fetch_common", MODULE_PATH)
fetch_common = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = fetch_common
SPEC.loader.exec_module(fetch_common)

warnings.filterwarnings(
    "ignore",
    message=r"Implicitly cleaning up <HTTPError 429: 'HTTP 429'>",
    category=ResourceWarning,
)


class FakeHTTPResponse:
    def __init__(self, body: bytes, url: str, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self._url = url
        self.status = status
        self.headers = headers or {"content-type": "text/plain"}

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeHTTPError(urllib.error.HTTPError):
    def read(self, *args, **kwargs):
        if getattr(self, "fp", None) is None:
            return b""
        payload = self.fp.read(*args, **kwargs)
        self.fp.close()
        self.fp = None
        return payload


def build_http_error(url: str, *, status: int, headers: dict[str, str] | None = None, body: bytes = b"") -> urllib.error.HTTPError:
    return FakeHTTPError(url, status, f"HTTP {status}", headers or {}, io.BytesIO(body))


class HttpTransportCacheTests(unittest.TestCase):
    def test_get_requests_hit_in_memory_cache_for_same_url_and_headers(self) -> None:
        transport = fetch_common.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(fetch_common.urllib.request, "urlopen", side_effect=fake_urlopen):
            first = transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})
            second = transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertEqual(call_count, 1)
        self.assertEqual(first["body"], b"ok")
        self.assertEqual(second["body"], b"ok")

    def test_cache_key_redacts_sensitive_query_params_and_header_values(self) -> None:
        transport = fetch_common.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b'{"ok":true}', request.full_url, headers={"content-type": "application/json"})

        with mock.patch.object(fetch_common.urllib.request, "urlopen", side_effect=fake_urlopen):
            transport.request(
                "GET",
                "https://example.test/article",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "UnitTest/1.0",
                    "X-ELS-APIKey": "top-secret",
                    "X-ELS-ReqId": "req-1",
                },
                query={"api_key": "springer-secret", "mailto": "alice@example.com"},
            )
            transport.request(
                "GET",
                "https://example.test/article",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "UnitTest/1.0",
                    "X-ELS-APIKey": "different-secret",
                    "X-ELS-ReqId": "req-2",
                },
                query={"api_key": "different-secret", "mailto": "bob@example.com"},
            )

        self.assertEqual(call_count, 1)
        self.assertEqual(len(transport._cache), 1)

        cache_key = next(iter(transport._cache))
        _, cached_url, cached_headers = cache_key
        self.assertNotIn("springer-secret", cached_url)
        self.assertNotIn("alice@example.com", cached_url)
        self.assertIn("api_key=%2A%2A%2A", cached_url)
        self.assertIn("mailto=%2A%2A%2A", cached_url)
        self.assertIn(("x-els-apikey", "***"), cached_headers)
        self.assertIn(("x-els-reqid", "<volatile>"), cached_headers)

    def test_pdf_payloads_are_not_cached(self) -> None:
        transport = fetch_common.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0
        pdf_body = b"%PDF-" + (b"x" * 4096)

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(pdf_body, request.full_url, headers={"content-type": "application/pdf"})

        with mock.patch.object(fetch_common.urllib.request, "urlopen", side_effect=fake_urlopen):
            transport.request("GET", "https://example.test/article.pdf", headers={"Accept": "*/*"})
            transport.request("GET", "https://example.test/article.pdf", headers={"Accept": "*/*"})

        self.assertEqual(call_count, 2)
        self.assertEqual(len(transport._cache), 0)

    def test_retry_after_is_respected_once_for_rate_limited_requests(self) -> None:
        transport = fetch_common.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise build_http_error(
                    request.full_url,
                    status=429,
                    headers={"Retry-After": "1"},
                    body=b"rate limited",
                )
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(fetch_common.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch.object(fetch_common.time, "sleep") as mocked_sleep:
                response = transport.request(
                    "GET",
                    "https://example.test/article",
                    headers={"Accept": "text/plain"},
                    retry_on_rate_limit=True,
                )

        self.assertEqual(call_count, 2)
        self.assertEqual(response["body"], b"ok")
        mocked_sleep.assert_called_once_with(1)

    def test_map_request_failure_returns_rate_limited_provider_failure(self) -> None:
        failure = fetch_common.RequestFailure(
            429,
            "HTTP 429 for https://example.test/article (Retry-After: 4s)",
            retry_after_seconds=4,
        )

        mapped = fetch_common.map_request_failure(failure)

        self.assertEqual(mapped.code, "rate_limited")
        self.assertEqual(mapped.retry_after_seconds, 4)

    def test_sanitize_filename_truncates_long_values_with_stable_hash_suffix(self) -> None:
        long_name = "10.1016/" + ("a" * 260)

        sanitized = fetch_common.sanitize_filename(long_name)

        self.assertLessEqual(len(sanitized), 180)
        self.assertRegex(sanitized, r"_[0-9a-f]{8}$")

    def test_sanitize_filename_uses_hash_fallback_for_non_ascii_titles(self) -> None:
        sanitized = fetch_common.sanitize_filename("这是一个非常长的中文标题" * 30)

        self.assertRegex(sanitized, r"^fulltext_[0-9a-f]{8}$")

    def test_dedupe_authors_uses_semantic_name_key(self) -> None:
        authors = fetch_common.dedupe_authors(["Zhang, San", "San Zhang", "Alice Example"])

        self.assertEqual(authors, ["Zhang, San", "Alice Example"])


if __name__ == "__main__":
    unittest.main()
