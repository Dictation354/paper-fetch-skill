from __future__ import annotations

import concurrent.futures
import io
import socket
import threading
import tomllib
import unittest
import urllib.error
import warnings
from unittest import mock

from paper_fetch import http as http_module
from paper_fetch import utils
from paper_fetch.providers import base as provider_base
from tests.paths import REPO_ROOT

warnings.filterwarnings(
    "ignore",
    message=r"Implicitly cleaning up <HTTPError 429: 'HTTP 429'>",
    category=ResourceWarning,
)


class FakeHTTPResponse:
    def __init__(self, body: bytes, url: str, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._stream = io.BytesIO(body)
        self._url = url
        self.status = status
        self.headers = headers or {"content-type": "text/plain"}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

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
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            first = transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})
            second = transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertEqual(call_count, 1)
        self.assertEqual(first["body"], b"ok")
        self.assertEqual(second["body"], b"ok")

    def test_cache_key_redacts_sensitive_query_params_and_header_values(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b'{"ok":true}', request.full_url, headers={"content-type": "application/json"})

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            transport.request(
                "GET",
                "https://example.test/article",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "UnitTest/1.0",
                    "Accept-Language": "en-US",
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
                    "User-Agent": "AnotherUserAgent/9.9",
                    "Accept-Language": "en-US",
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
        self.assertIn(("accept", "application/json"), cached_headers)
        self.assertIn(("accept-language", "en-US"), cached_headers)
        self.assertIn(("x-els-apikey", "***"), cached_headers)
        self.assertNotIn(("user-agent", "UnitTest/1.0"), cached_headers)
        self.assertFalse(any(key == "x-els-reqid" for key, _ in cached_headers))

    def test_cache_key_distinguishes_accept_language_and_authorization_presence(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b'{"ok":true}', request.full_url, headers={"content-type": "application/json"})

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            transport.request(
                "GET",
                "https://example.test/article",
                headers={"Accept": "application/json", "Accept-Language": "en-US"},
            )
            transport.request(
                "GET",
                "https://example.test/article",
                headers={"Accept": "application/json", "Accept-Language": "zh-CN"},
            )
            transport.request(
                "GET",
                "https://example.test/article",
                headers={"Accept": "application/json", "Accept-Language": "zh-CN", "Authorization": "Bearer secret"},
            )

        self.assertEqual(call_count, 3)
        self.assertEqual(len(transport._cache), 3)

    def test_pdf_payloads_are_not_cached(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0
        pdf_body = b"%PDF-" + (b"x" * 4096)

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(pdf_body, request.full_url, headers={"content-type": "application/pdf"})

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            transport.request("GET", "https://example.test/article.pdf", headers={"Accept": "*/*"})
            transport.request("GET", "https://example.test/article.pdf", headers={"Accept": "*/*"})

        self.assertEqual(call_count, 2)
        self.assertEqual(len(transport._cache), 0)

    def test_oversized_response_body_raises_and_is_not_cached(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128, max_response_bytes=4)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b"abcde", request.full_url)

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            for _ in range(2):
                with self.assertRaises(http_module.RequestFailure) as context:
                    transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertEqual(call_count, 2)
        self.assertEqual(len(transport._cache), 0)
        self.assertIn("Response body exceeded 4 bytes", str(context.exception))

    def test_retry_after_is_respected_once_for_rate_limited_requests(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0
        rate_limited_error = build_http_error(
            "https://example.test/article",
            status=429,
            headers={"Retry-After": "1"},
            body=b"rate limited",
        )
        original_close = rate_limited_error.close
        rate_limited_error.close = mock.Mock(side_effect=original_close)

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise rate_limited_error
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch.object(http_module.time, "sleep") as mocked_sleep:
                response = transport.request(
                    "GET",
                    "https://example.test/article",
                    headers={"Accept": "text/plain"},
                    retry_on_rate_limit=True,
                )

        self.assertEqual(call_count, 2)
        self.assertEqual(response["body"], b"ok")
        mocked_sleep.assert_called_once_with(1)
        rate_limited_error.close.assert_called_once_with()

    def test_transient_http_5xx_is_retried_with_exponential_backoff(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise build_http_error("https://example.test/article", status=503, body=b"transient")
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch.object(http_module.time, "sleep") as mocked_sleep:
                response = transport.request(
                    "GET",
                    "https://example.test/article",
                    headers={"Accept": "text/plain"},
                    retry_on_transient=True,
                )

        self.assertEqual(call_count, 3)
        self.assertEqual(response["body"], b"ok")
        self.assertEqual(mocked_sleep.call_args_list, [mock.call(0.5), mock.call(1.0)])

    def test_timeout_urlerror_is_retried_with_exponential_backoff(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise urllib.error.URLError(socket.timeout("timed out"))
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch.object(http_module.time, "sleep") as mocked_sleep:
                response = transport.request(
                    "GET",
                    "https://example.test/article",
                    headers={"Accept": "text/plain"},
                    retry_on_transient=True,
                )

        self.assertEqual(call_count, 3)
        self.assertEqual(response["body"], b"ok")
        self.assertEqual(mocked_sleep.call_args_list, [mock.call(0.5), mock.call(1.0)])

    def test_direct_socket_timeout_is_retried_with_exponential_backoff(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise socket.timeout("timed out")
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch.object(http_module.time, "sleep") as mocked_sleep:
                response = transport.request(
                    "GET",
                    "https://example.test/article",
                    headers={"Accept": "text/plain"},
                    retry_on_transient=True,
                )

        self.assertEqual(call_count, 3)
        self.assertEqual(response["body"], b"ok")
        self.assertEqual(mocked_sleep.call_args_list, [mock.call(0.5), mock.call(1.0)])

    def test_non_timeout_urlerror_is_not_retried(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            raise urllib.error.URLError(OSError("connection reset"))

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch.object(http_module.time, "sleep") as mocked_sleep:
                with self.assertRaises(http_module.RequestFailure):
                    transport.request(
                        "GET",
                        "https://example.test/article",
                        headers={"Accept": "text/plain"},
                        retry_on_transient=True,
                    )

        self.assertEqual(call_count, 1)
        mocked_sleep.assert_not_called()

    def test_http_error_wrapper_is_closed_when_request_failure_is_raised(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        server_error = build_http_error(
            "https://example.test/article",
            status=500,
            headers={},
            body=b"server error",
        )
        original_close = server_error.close
        server_error.close = mock.Mock(side_effect=original_close)

        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=server_error):
            with self.assertRaises(http_module.RequestFailure):
                transport.request(
                    "GET",
                    "https://example.test/article",
                    headers={"Accept": "text/plain"},
                )

        server_error.close.assert_called_once_with()

    def test_concurrent_get_requests_keep_cache_consistent(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=4)
        call_count = 0
        call_lock = threading.Lock()

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            with call_lock:
                call_count += 1
            return FakeHTTPResponse(
                request.full_url.encode("utf-8"),
                request.full_url,
                headers={"content-type": "text/plain"},
            )

        urls = [f"https://example.test/article/{index % 6}" for index in range(48)]
        with mock.patch.object(http_module.urllib.request, "urlopen", side_effect=fake_urlopen):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                responses = list(
                    executor.map(
                        lambda url: transport.request("GET", url, headers={"Accept": "text/plain"}),
                        urls,
                    )
                )

        self.assertEqual([item["body"] for item in responses], [url.encode("utf-8") for url in urls])
        self.assertLessEqual(len(transport._cache), 4)
        self.assertTrue(call_count >= len({*urls}))

    def test_map_request_failure_returns_rate_limited_provider_failure(self) -> None:
        failure = http_module.RequestFailure(
            429,
            "HTTP 429 for https://example.test/article (Retry-After: 4s)",
            retry_after_seconds=4,
        )

        mapped = provider_base.map_request_failure(failure)

        self.assertEqual(mapped.code, "rate_limited")
        self.assertEqual(mapped.retry_after_seconds, 4)

    def test_sanitize_filename_truncates_long_values_with_stable_hash_suffix(self) -> None:
        long_name = "10.1016/" + ("a" * 260)

        sanitized = utils.sanitize_filename(long_name)

        self.assertLessEqual(len(sanitized), 180)
        self.assertRegex(sanitized, r"_[0-9a-f]{8}$")

    def test_sanitize_filename_uses_hash_fallback_for_non_ascii_titles(self) -> None:
        sanitized = utils.sanitize_filename("这是一个非常长的中文标题" * 30)

        self.assertRegex(sanitized, r"^fulltext_[0-9a-f]{8}$")

    def test_dedupe_authors_uses_semantic_name_key(self) -> None:
        authors = utils.dedupe_authors(["Zhang, San", "San Zhang", "Alice Example"])

        self.assertEqual(authors, ["Zhang, San", "Alice Example"])

    def test_runtime_dependencies_are_declared_explicitly_and_not_patch_pinned(self) -> None:
        with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
            pyproject = tomllib.load(handle)

        dependencies = list(pyproject["project"]["dependencies"])

        self.assertIn("pydantic>=2,<3", dependencies)
        self.assertTrue(all("==" not in dependency for dependency in dependencies))


if __name__ == "__main__":
    unittest.main()
