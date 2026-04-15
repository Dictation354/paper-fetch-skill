from __future__ import annotations

import concurrent.futures
import gzip
import io
import logging
import socket
import threading
import unittest
import urllib.error
import urllib.parse
import warnings
from unittest import mock

from paper_fetch import http as http_module
from paper_fetch.providers import base as provider_base
import urllib3

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
        self.closed = False
        self.released = False

    def read(self, size: int = -1, *args, **kwargs) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:
        self.closed = True
        self._stream.close()

    def release_conn(self) -> None:
        self.released = True

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


def lower_header_map(headers: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


class RecordCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class HttpTransportCacheTests(unittest.TestCase):
    def test_get_requests_hit_in_memory_cache_for_same_url_and_headers(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

    def test_default_request_headers_add_accept_encoding_gzip(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        captured_headers: list[dict[str, str]] = []

        def fake_urlopen(request, timeout=20):
            captured_headers.append(dict(request.headers))
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertEqual(lower_header_map(captured_headers[0])["accept-encoding"], "gzip")

    def test_http_transport_emits_debug_logs_with_url_status_and_elapsed_time(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        http_logger = logging.getLogger("paper_fetch.http")
        original_level = http_logger.level
        handler = RecordCaptureHandler()
        http_logger.addHandler(handler)
        http_logger.setLevel(logging.DEBUG)

        def fake_urlopen(request, timeout=20):
            return FakeHTTPResponse(b"ok", request.full_url)

        try:
            with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
                transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})
        finally:
            http_logger.removeHandler(handler)
            http_logger.setLevel(original_level)

        rendered_logs = "\n".join(record.getMessage() for record in handler.records)
        self.assertIn("url=https://example.test/article", rendered_logs)
        self.assertIn("status=200", rendered_logs)
        self.assertIn("elapsed_ms=", rendered_logs)
        payloads = [
            record.structured_data
            for record in handler.records
            if isinstance(getattr(record, "structured_data", None), dict)
        ]
        self.assertIn(
            {
                "event": "http_request_start",
                "method": "GET",
                "url": "https://example.test/article",
                "status": "attempt",
                "elapsed_ms": 0.0,
                "attempt": 1,
            },
            payloads,
        )
        self.assertIn(
            {
                "event": "http_request_success",
                "method": "GET",
                "url": "https://example.test/article",
                "status": 200,
                "attempt": 1,
                "elapsed_ms": next(
                    payload["elapsed_ms"]
                    for payload in payloads
                    if payload.get("event") == "http_request_success"
                ),
            },
            payloads,
        )

    def test_explicit_accept_encoding_is_respected(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        captured_headers: list[dict[str, str]] = []

        def fake_urlopen(request, timeout=20):
            captured_headers.append(dict(request.headers))
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            transport.request(
                "GET",
                "https://example.test/article",
                headers={"Accept": "text/plain", "Accept-Encoding": "identity"},
            )

        self.assertEqual(lower_header_map(captured_headers[0])["accept-encoding"], "identity")

    def test_gzip_response_body_is_decompressed_before_returning(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128)
        compressed = gzip.compress(b"decompressed body")

        def fake_urlopen(request, timeout=20):
            return FakeHTTPResponse(
                compressed,
                request.full_url,
                headers={"content-type": "text/plain", "content-encoding": "gzip"},
            )

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            response = transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})
            cached_response = transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertEqual(response["body"], b"decompressed body")
        self.assertEqual(cached_response["body"], b"decompressed body")

    def test_gzip_decompressed_size_limit_is_enforced(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0, max_response_bytes=4)
        compressed = gzip.compress(b"abcde")

        def fake_urlopen(request, timeout=20):
            return FakeHTTPResponse(
                compressed,
                request.full_url,
                headers={"content-type": "text/plain", "content-encoding": "gzip"},
            )

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            with self.assertRaises(http_module.RequestFailure) as context:
                transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertIn("Response body exceeded 4 bytes", str(context.exception))

    def test_gzip_compressed_size_limit_is_enforced_before_decompression(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0, max_response_bytes=8)
        compressed = gzip.compress(bytes(range(256)) * 2)
        self.assertGreater(len(compressed), transport.max_response_bytes * http_module.DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER)

        def fake_urlopen(request, timeout=20):
            return FakeHTTPResponse(
                compressed,
                request.full_url,
                headers={"content-type": "application/octet-stream", "content-encoding": "gzip"},
            )

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            with self.assertRaises(http_module.RequestFailure) as context:
                transport.request("GET", "https://example.test/article", headers={"Accept": "*/*"})

        self.assertIn("Compressed response body exceeded 64 bytes", str(context.exception))

    def test_pdf_payloads_are_not_cached(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128)
        call_count = 0
        pdf_body = b"%PDF-" + (b"x" * 4096)

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(pdf_body, request.full_url, headers={"content-type": "application/pdf"})

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            transport.request("GET", "https://example.test/article.pdf", headers={"Accept": "*/*"})
            transport.request("GET", "https://example.test/article.pdf", headers={"Accept": "*/*"})

        self.assertEqual(call_count, 2)
        self.assertEqual(len(transport._cache), 0)

    def test_successful_pooled_response_releases_connection(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        response = FakeHTTPResponse(b"ok", "https://example.test/article")

        with mock.patch.object(transport, "_perform_request", return_value=response):
            payload = transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertEqual(payload["body"], b"ok")
        self.assertTrue(response.released)
        self.assertFalse(response.closed)

    def test_oversized_pooled_response_is_closed_without_releasing_connection(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0, max_response_bytes=4)
        response = FakeHTTPResponse(b"abcde", "https://example.test/article")

        with mock.patch.object(transport, "_perform_request", return_value=response):
            with self.assertRaises(http_module.RequestFailure):
                transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertTrue(response.closed)
        self.assertFalse(response.released)

    def test_http_error_response_releases_connection_after_request_failure(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        response = FakeHTTPResponse(
            b"server error",
            "https://example.test/article",
            status=503,
            headers={"content-type": "text/plain"},
        )

        with mock.patch.object(transport, "_perform_request", return_value=response):
            with self.assertRaises(http_module.RequestFailure):
                transport.request("GET", "https://example.test/article", headers={"Accept": "text/plain"})

        self.assertTrue(response.released)
        self.assertFalse(response.closed)

    def test_total_cache_byte_cap_evicts_oldest_entries(self) -> None:
        transport = http_module.HttpTransport(
            cache_ttl=30,
            cache_capacity=8,
            max_cacheable_body_bytes=8,
            max_total_cache_bytes=4,
        )
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            payload = b"abc" if request.full_url.endswith("/one") else b"de"
            return FakeHTTPResponse(payload, request.full_url, headers={"content-type": "text/plain"})

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            first = transport.request("GET", "https://example.test/one", headers={"Accept": "text/plain"})
            second = transport.request("GET", "https://example.test/two", headers={"Accept": "text/plain"})
            cached_second = transport.request("GET", "https://example.test/two", headers={"Accept": "text/plain"})
            third_first = transport.request("GET", "https://example.test/one", headers={"Accept": "text/plain"})

        self.assertEqual(first["body"], b"abc")
        self.assertEqual(second["body"], b"de")
        self.assertEqual(cached_second["body"], b"de")
        self.assertEqual(third_first["body"], b"abc")
        self.assertEqual(call_count, 3)
        self.assertEqual(len(transport._cache), 1)
        self.assertLessEqual(transport._cache_body_bytes, 4)

    def test_oversized_response_body_raises_and_is_not_cached(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=30, cache_capacity=128, max_response_bytes=4)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            return FakeHTTPResponse(b"abcde", request.full_url)

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

    def test_rate_limited_request_without_retry_after_uses_short_fallback_backoff(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0
        rate_limited_error = build_http_error(
            "https://example.test/article",
            status=429,
            headers={},
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            with mock.patch.object(http_module.time, "sleep") as mocked_sleep:
                response = transport.request(
                    "GET",
                    "https://example.test/article",
                    headers={"Accept": "text/plain"},
                    retry_on_rate_limit=True,
                )

        self.assertEqual(call_count, 2)
        self.assertEqual(response["body"], b"ok")
        mocked_sleep.assert_called_once_with(http_module.DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS)
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

    def test_urllib3_read_timeout_is_retried_with_exponential_backoff(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise urllib3.exceptions.ReadTimeoutError(None, request.full_url, "timed out")
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

    def test_urllib3_protocol_timeout_is_retried_with_exponential_backoff(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise urllib3.exceptions.ProtocolError("conn broken", socket.timeout("timed out"))
            return FakeHTTPResponse(b"ok", request.full_url)

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

    def test_non_timeout_urllib3_error_is_not_retried(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        call_count = 0

        def fake_urlopen(request, timeout=20):
            nonlocal call_count
            call_count += 1
            raise urllib3.exceptions.ProtocolError("conn broken", OSError("connection reset"))

        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

        with mock.patch.object(transport, "_perform_request", side_effect=server_error):
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
        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
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

    def test_same_host_requests_are_serialized_while_different_hosts_can_overlap(self) -> None:
        transport = http_module.HttpTransport(cache_ttl=0, cache_capacity=0)
        active_by_host: dict[str, int] = {}
        max_active_by_host: dict[str, int] = {}
        global_active = 0
        max_global_active = 0
        lock = threading.Lock()

        def fake_urlopen(request, timeout=20):
            nonlocal global_active, max_global_active
            host = urllib.parse.urlparse(request.full_url).hostname or ""
            with lock:
                active_by_host[host] = active_by_host.get(host, 0) + 1
                max_active_by_host[host] = max(max_active_by_host.get(host, 0), active_by_host[host])
                global_active += 1
                max_global_active = max(max_global_active, global_active)
            try:
                threading.Event().wait(0.05)
                return FakeHTTPResponse(
                    request.full_url.encode("utf-8"),
                    request.full_url,
                    headers={"content-type": "text/plain"},
                )
            finally:
                with lock:
                    active_by_host[host] -= 1
                    global_active -= 1

        urls = [
            "https://same.test/one",
            "https://same.test/two",
            "https://other.test/three",
        ]
        with mock.patch.object(transport, "_perform_request", side_effect=fake_urlopen):
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                list(executor.map(lambda url: transport.request("GET", url, headers={"Accept": "text/plain"}), urls))

        self.assertEqual(max_active_by_host["same.test"], 1)
        self.assertGreaterEqual(max_global_active, 2)

    def test_map_request_failure_returns_rate_limited_provider_failure(self) -> None:
        failure = http_module.RequestFailure(
            429,
            "HTTP 429 for https://example.test/article (Retry-After: 4s)",
            retry_after_seconds=4,
        )

        mapped = provider_base.map_request_failure(failure)

        self.assertEqual(mapped.code, "rate_limited")
        self.assertEqual(mapped.retry_after_seconds, 4)
