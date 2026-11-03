"""Real HTTP retry/cancellation under Elsevier's remaining enrichment budget."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest

from paper_fetch.http import HttpRequestPolicy, HttpTransport, RequestCancelledError
from paper_fetch.providers._elsevier_reference_completion import (
    _RequestTransport,
    _ReferenceDeadlineExceeded,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.http.url_policy import SafeRemoteUrlPolicy, ValidatedRemoteUrl


@pytest.fixture
def endpoint(monkeypatch):
    cancelled = threading.Event()
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(self.path)
            self.send_response(200 if self.path == "/ok" else 429)
            if self.path != "/ok":
                self.send_header("Retry-After", "5")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
            if self.path == "/cancel":
                cancelled.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    original_validate = SafeRemoteUrlPolicy.validate

    def validate_local(self, url, **kwargs):
        if url.startswith(base + "/"):
            return ValidatedRemoteUrl(
                url, "http", "127.0.0.1", server.server_port, ("127.0.0.1",)
            )
        return original_validate(self, url, **kwargs)

    monkeypatch.setattr(SafeRemoteUrlPolicy, "validate", validate_local)
    try:
        yield base, calls, cancelled
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_reference_http_uses_shared_transport_and_propagates_retry_cancellation(
    endpoint,
):
    url, calls, cancelled = endpoint
    transport = HttpTransport()
    context = RuntimeContext(env={}, transport=transport, cancel_check=cancelled.is_set)
    context.initialize_deadline(15)
    bounded = _RequestTransport(transport, context)
    try:
        assert bounded.request("GET", url + "/ok")["body"] == b"{}"
        with pytest.raises(RequestCancelledError):
            bounded.request(
                "GET",
                url + "/cancel",
                request_policy=HttpRequestPolicy(
                    retry_on_rate_limit=True, rate_limit_retries=2
                ),
            )
        assert calls == ["/ok", "/cancel"]
    finally:
        context.close()
        transport.close()


def test_reference_http_retry_wait_is_bounded_by_remaining_deadline(endpoint):
    url, calls, _ = endpoint
    transport = HttpTransport()
    context = RuntimeContext(env={}, transport=transport)
    context.deadline_monotonic = time.monotonic() + 1.2
    bounded = _RequestTransport(transport, context)
    try:
        with pytest.raises(_ReferenceDeadlineExceeded):
            bounded.request(
                "GET",
                url + "/deadline",
                request_policy=HttpRequestPolicy(
                    retry_on_rate_limit=True, rate_limit_retries=2
                ),
            )
        assert calls == ["/deadline"]
    finally:
        context.close()
        transport.close()
