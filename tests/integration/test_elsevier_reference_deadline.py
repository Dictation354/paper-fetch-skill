"""Real HTTP retry/cancellation under Elsevier's remaining enrichment budget."""

import contextlib
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler
from types import SimpleNamespace

import pytest
from urllib3.connection import HTTPConnection

from paper_fetch.http import (
    HttpRequestPolicy,
    HttpStreamOptions,
    HttpTransport,
    RequestCancelledError,
    RequestFailure,
)
from paper_fetch.http.transport import request_timeout_limit
from paper_fetch.http.url_policy import SafeRemoteUrlPolicy, ValidatedRemoteUrl
from paper_fetch.providers import _elsevier_reference_completion as completion
from paper_fetch.providers._elsevier_reference_completion import (
    _ReferenceDeadlineExceeded,
    _RequestTransport,
)
from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers.elsevier import ElsevierClient
from paper_fetch.runtime import RuntimeContext


class _LocalHttpSocket(socket.socket):
    def sendall(self, data, flags=0):
        if os.name == "nt":
            return super().sendall(data, flags)
        pending = memoryview(data)
        while pending:
            pending = pending[os.write(self.fileno(), pending) :]
        return None


@pytest.fixture
def endpoint(monkeypatch):
    cancelled = threading.Event()
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(self.path)
            if self.path == "/drip-headers":
                with contextlib.suppress(ConnectionError):
                    self.wfile.write(b"HTTP/1.0 200 OK\r\nX-Drip: ")
                    for _ in range(20):
                        self.wfile.write(b"x")
                        time.sleep(0.05)
                    self.wfile.write(b"\r\nContent-Length: 2\r\n\r\n{}")
                return
            if self.path.startswith("/drip-"):
                self.send_response(200)
                if self.path in {"/drip-chunked", "/drip-chunk-extension"}:
                    self.send_header("Transfer-Encoding", "chunked")
                elif self.path == "/drip-fixed":
                    self.send_header("Content-Length", "60")
                self.end_headers()
                with contextlib.suppress(ConnectionError):
                    if self.path == "/drip-chunk-extension":
                        self.wfile.write(b"3c;extension=")
                    elif self.path == "/drip-chunked":
                        self.wfile.write(b"3c\r\n")
                    for _ in range(60):
                        self.wfile.write(b"x")
                        time.sleep(0.04)
                    if self.path == "/drip-chunked":
                        self.wfile.write(b"\r\n0\r\n\r\n")
                return
            self.send_response(200 if self.path == "/ok" else 429)
            if self.path != "/ok":
                self.send_header("Retry-After", "5")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
            if self.path == "/cancel":
                cancelled.set()

    base = "http://reference.test"
    threads = []
    original_validate = SafeRemoteUrlPolicy.validate
    original_connect = HTTPConnection._new_conn

    def validate_local(self, url, **kwargs):
        if url.startswith(base + "/"):
            return ValidatedRemoteUrl(url, "http", "reference.test", 80, ("127.0.0.1",))
        return original_validate(self, url, **kwargs)

    def connect(self):
        if self.host != "reference.test":
            return original_connect(self)
        client_end, server_end = socket.socketpair()
        client, server = (
            _LocalHttpSocket(end.family, end.type, end.proto, fileno=end.detach())
            for end in (client_end, server_end)
        )

        def handle():
            with server:
                Handler(server, ("127.0.0.1", 0), None)

        thread = threading.Thread(target=handle, daemon=True)
        threads.append(thread)
        thread.start()
        return client

    # Keep the real urllib3 and http.client framing while using a local socket pair.
    monkeypatch.setattr(SafeRemoteUrlPolicy, "validate", validate_local)
    monkeypatch.setattr(HTTPConnection, "_new_conn", connect)
    try:
        yield base, calls, cancelled
    finally:
        for thread in threads:
            thread.join(timeout=3)


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


@pytest.mark.parametrize("deadline", ["outer", "enrichment"])
def test_reference_http_retry_wait_is_bounded_by_remaining_deadline(
    endpoint, deadline, monkeypatch
):
    url, calls, _ = endpoint
    transport = HttpTransport()
    context = RuntimeContext(env={}, transport=transport)
    if deadline == "outer":
        context.deadline_monotonic = time.monotonic() + 1.2
    else:
        monkeypatch.setattr(
            completion, "DEFAULT_REFERENCE_ENRICHMENT_BUDGET_SECONDS", 1.2
        )
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


@pytest.mark.parametrize("framing", ["fixed", "chunked", "chunk-extension", "close"])
def test_reference_http_body_slow_drip_cannot_extend_deadline(endpoint, framing):
    url, calls, _ = endpoint
    transport = HttpTransport()
    try:
        with RuntimeContext(env={}, transport=transport) as context:
            context.deadline_monotonic = time.monotonic() + 0.35
            bounded = _RequestTransport(transport, context)
            started = time.monotonic()
            with pytest.raises(_ReferenceDeadlineExceeded):
                bounded.request("GET", f"{url}/drip-{framing}")
            assert time.monotonic() - started < 1
            assert calls == [f"/drip-{framing}"]
    finally:
        transport.close()


def test_reference_http_header_slow_drip_keeps_accepted_xml(endpoint, monkeypatch):
    url, calls, _ = endpoint
    doi = "10.1016/example"
    xml = f"""<full-text-retrieval-response>
    <coredata><doi>{doi}</doi><title>Example</title></coredata>
    <article><body><sections><section><section-title>Results</section-title>
    <para>{"Scientific observations explain the measured vegetation response. " * 35}</para>
    </section></sections></body><tail><bibliography><bib-reference>
    <reference><contribution><title><maintitle>A related study</maintitle></title></contribution>
    <host><issue><date>2024</date></issue></host></reference>
    </bib-reference></bibliography></tail></article>
    </full-text-retrieval-response>""".encode()
    payload = build_provider_payload(
        provider="elsevier",
        route_kind="official",
        route_name="xml_api",
        source_url=f"https://api.elsevier.com/content/article/doi/{doi}",
        content_type="text/xml",
        body=xml,
    )
    monkeypatch.setattr(completion, "DEFAULT_REFERENCE_ENRICHMENT_BUDGET_SECONDS", 0.32)
    transport = HttpTransport()

    class Crossref:
        lookup = SimpleNamespace(transport=transport)

        def fetch_metadata(self, query):
            return self.lookup.transport.request("GET", url + "/drip-headers")

    client = ElsevierClient(transport, {"ELSEVIER_API_KEY": "key"})
    monkeypatch.setattr(client, "_fetch_official_xml_payload", lambda doi: payload)
    try:
        with RuntimeContext(
            env={}, transport=transport, clients={"crossref": Crossref()}
        ) as context:
            started = time.monotonic()
            result = client.fetch_raw_fulltext(
                doi, {"doi": doi, "title": "Example"}, context=context
            )
            assert time.monotonic() - started < 0.8
            assert calls == ["/drip-headers"]
            assert result.content.body == xml
            assert result.content.diagnostics["availability_diagnostics"]["accepted"]
            assert result.content.diagnostics["reference_doi_completion"]["attempts"][
                -1
            ] == {
                "source": "crossref_parent",
                "outcome": "unavailable",
                "reason": "_ReferenceDeadlineExceeded",
            }
            assert transport.request("GET", url + "/ok")["body"] == b"{}"
    finally:
        transport.close()


def test_stream_to_file_respects_body_deadline_and_removes_staging(endpoint, tmp_path):
    url, calls, _ = endpoint
    transport = HttpTransport()
    staging = tmp_path / "unfinished"
    started = time.monotonic()
    deadline = started + 0.35
    token = request_timeout_limit.set(lambda: deadline - time.monotonic())
    try:
        with pytest.raises(RequestFailure) as caught:
            transport.stream_to_file(
                "GET",
                url + "/drip-fixed",
                staging,
                options=HttpStreamOptions(timeout=5),
            )
        assert time.monotonic() - started < 1
        assert caught.value.error_category == "timeout"
        assert not staging.exists()
        assert calls == ["/drip-fixed"]
    finally:
        request_timeout_limit.reset(token)
        transport.close()
