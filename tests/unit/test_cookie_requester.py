from __future__ import annotations

from email.message import Message
import io
import urllib.request

import pytest

from paper_fetch.extraction.html.assets import requester
from paper_fetch.http import (
    RequestCancelledError,
    RequestErrorCategory,
    RequestFailure,
)


class _Response:
    def __init__(
        self,
        body: bytes,
        *,
        url: str = "https://publisher.example/paper.pdf",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._stream = io.BytesIO(body)
        self._url = url
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self.status = 200

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response

    def open(self, request: urllib.request.Request, *, timeout: int) -> _Response:
        del request, timeout
        return self.response


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/paper.pdf",
        "data:application/pdf;base64,JVBERg==",
        "ftp://publisher.example/paper.pdf",
        "https://user:secret@publisher.example/paper.pdf",
    ],
)
def test_requester_rejects_non_http_or_credentialed_urls(url: str) -> None:
    with pytest.raises(RequestFailure) as exc_info:
        requester.request_with_opener(
            _Opener(_Response(b"unused")),  # type: ignore[arg-type]
            url,
            headers={},
            timeout=1,
        )
    assert exc_info.value.error_category == RequestErrorCategory.UNSUPPORTED_SCHEME


def test_requester_rejects_declared_oversized_response_without_reading_all() -> None:
    response = _Response(b"small", headers={"Content-Length": "100"})
    with pytest.raises(RequestFailure) as exc_info:
        requester.request_with_opener(
            _Opener(response),  # type: ignore[arg-type]
            response.geturl(),
            headers={},
            timeout=1,
            max_response_bytes=10,
        )
    assert exc_info.value.error_category == RequestErrorCategory.RESPONSE_TOO_LARGE
    assert response._stream.tell() == 0


def test_requester_rejects_stream_that_exceeds_actual_limit() -> None:
    response = _Response(b"0123456789abcdef")
    with pytest.raises(RequestFailure) as exc_info:
        requester.request_with_opener(
            _Opener(response),  # type: ignore[arg-type]
            response.geturl(),
            headers={},
            timeout=1,
            max_response_bytes=8,
        )
    assert exc_info.value.error_category == RequestErrorCategory.RESPONSE_TOO_LARGE
    assert exc_info.value.body == b"01234567"


def test_requester_checks_cancellation_between_chunks() -> None:
    response = _Response(b"0123456789")
    with pytest.raises(RequestCancelledError):
        requester.request_with_opener(
            _Opener(response),  # type: ignore[arg-type]
            response.geturl(),
            headers={},
            timeout=1,
            max_response_bytes=100,
            cancel_check=lambda: True,
        )


def test_cookie_opener_can_be_forced_without_seed_state() -> None:
    opener = requester.build_cookie_seeded_opener(
        [],
        headers={},
        timeout=1,
        force=True,
    )
    assert opener is not None
    assert any(
        isinstance(handler, requester._SafeRedirectHandler)
        for handler in opener.handlers
    )


def test_cookie_seed_checks_cancellation_before_network() -> None:
    with pytest.raises(RequestCancelledError):
        requester.build_cookie_seeded_opener(
            ["https://publisher.example/article"],
            headers={},
            timeout=1,
            cancel_check=lambda: True,
        )


def test_cross_origin_redirect_drops_sensitive_headers() -> None:
    request = urllib.request.Request(
        "https://publisher.example/paper",
        headers={
            "Authorization": "Bearer secret",
            "Cookie": "session=secret",
            "Referer": "https://publisher.example/paper",
            "User-Agent": "paper-fetch-test",
        },
    )
    redirected = requester._SafeRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        Message(),
        "https://cdn.example/file.pdf",
    )
    assert redirected is not None
    lowered = {key.lower() for key in redirected.headers}
    assert "authorization" not in lowered
    assert "cookie" not in lowered
    assert "referer" not in lowered
    assert redirected.get_header("User-agent") == "paper-fetch-test"


def test_cookie_filter_enforces_domain_path_and_secure_scope() -> None:
    cookies = [
        {
            "name": "accepted",
            "value": "yes",
            "domain": ".publisher.example",
            "path": "/article",
            "secure": True,
        },
        {
            "name": "wrong_path",
            "value": "no",
            "domain": ".publisher.example",
            "path": "/account",
            "secure": True,
        },
        {
            "name": "wrong_domain",
            "value": "no",
            "domain": ".other.example",
            "path": "/",
        },
    ]
    assert (
        requester.cookie_header_for_url(
            cookies, "https://www.publisher.example/article/123"
        )
        == "accepted=yes"
    )
    assert (
        requester.cookie_header_for_url(
            cookies, "http://www.publisher.example/article/123"
        )
        is None
    )
