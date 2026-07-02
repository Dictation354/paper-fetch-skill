from __future__ import annotations

import base64
from typing import Any
from collections.abc import Callable

from paper_fetch.providers import _cloakbrowser


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class _FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> None:
        self.url = url
        self.status = status
        self.headers = dict(headers or {})
        self._body = body

    def all_headers(self) -> dict[str, str]:
        return dict(self.headers)

    def body(self) -> bytes:
        return self._body


class _FakeExpectedResponse:
    def __init__(self, response: _FakeResponse) -> None:
        self.value = response

    def __enter__(self) -> _FakeExpectedResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeImageElement:
    def __init__(self, *, width: int = 1, height: int = 1) -> None:
        self.width = width
        self.height = height

    def evaluate(self, _script: str) -> dict[str, object]:
        return {"complete": True, "width": self.width, "height": self.height}


class _FakePage:
    def __init__(
        self,
        *,
        response: _FakeResponse,
        html: str = "<html></html>",
        title: str = "",
        image_element: _FakeImageElement | None = None,
        canvas_result: dict[str, object] | None = None,
    ) -> None:
        self._response = response
        self._html = html
        self._title = title
        self._image_element = image_element
        self._canvas_result = canvas_result
        self.expect_response_timeout: int | None = None

    def expect_response(
        self,
        predicate: Callable[[Any], bool],
        *,
        timeout: int,
    ) -> _FakeExpectedResponse:
        assert predicate(self._response)
        self.expect_response_timeout = timeout
        return _FakeExpectedResponse(self._response)

    def query_selector(self, selector: str) -> _FakeImageElement | None:
        assert selector == "img"
        return self._image_element

    def evaluate(self, _script: str, _args: list[object]) -> dict[str, object] | None:
        return self._canvas_result

    def content(self) -> str:
        return self._html

    def title(self) -> str:
        return self._title


def test_capture_image_payload_returns_png_for_image_response() -> None:
    image_url = "https://example.test/figure.png"
    page = _FakePage(
        response=_FakeResponse(
            url=image_url,
            headers={"content-type": "image/png"},
            body=PNG_BYTES,
        )
    )

    payload = _cloakbrowser._capture_image_payload(
        page,
        request_url=image_url,
        final_url=image_url,
    )

    assert payload is not None
    assert payload["contentType"] == "image/png"
    assert base64.b64decode(payload["bodyB64"]) == PNG_BYTES
    assert payload["url"] == image_url
    assert payload["status"] == 200


def test_capture_image_payload_uses_canvas_when_response_is_challenge() -> None:
    image_url = "https://example.test/figure.png"
    final_url = "https://example.test/challenge"
    page = _FakePage(
        response=_FakeResponse(
            url=image_url,
            status=403,
            headers={"content-type": "text/html; charset=utf-8"},
            body=b"<html><title>Just a moment...</title></html>",
        ),
        html="<html><body><img src='/figure.png'></body></html>",
        title="Just a moment...",
        image_element=_FakeImageElement(width=320, height=240),
        canvas_result={
            "ok": True,
            "status": 200,
            "dataURL": "data:image/png;base64,"
            + base64.b64encode(PNG_BYTES).decode("ascii"),
            "width": 320,
            "height": 240,
        },
    )

    payload = _cloakbrowser._capture_image_payload(
        page,
        request_url=image_url,
        final_url=final_url,
    )

    assert payload is not None
    assert payload["contentType"] == "image/png"
    assert base64.b64decode(payload["bodyB64"]) == PNG_BYTES
    assert payload["url"] == final_url
    assert payload["width"] == 320
    assert payload["height"] == 240


def test_capture_image_payload_preserves_svg() -> None:
    image_url = "https://example.test/figure.svg"
    svg_body = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="20"></svg>'
    page = _FakePage(
        response=_FakeResponse(
            url=image_url,
            headers={"content-type": "image/svg+xml"},
            body=svg_body,
        )
    )

    payload = _cloakbrowser._capture_image_payload(
        page,
        request_url=image_url,
        final_url=image_url,
    )

    assert payload is not None
    assert payload["contentType"] == "image/svg+xml"
    assert base64.b64decode(payload["bodyB64"]) == svg_body


def test_capture_image_payload_rejects_html_only() -> None:
    image_url = "https://example.test/figure.png"
    page = _FakePage(
        response=_FakeResponse(
            url=image_url,
            headers={"content-type": "text/html; charset=utf-8"},
            body=b"<html><body>Image wrapper</body></html>",
        ),
        html="<html><body>Image wrapper</body></html>",
    )

    payload = _cloakbrowser._capture_image_payload(
        page,
        request_url=image_url,
        final_url=image_url,
    )

    assert payload is None
    assert (
        page._paper_fetch_image_payload_failure["reason"]
        == "image_response_blocked_by_html_wrapper"
    )
