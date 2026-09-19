# ruff: noqa: F403, F405
# ruff: noqa: F403, F405
"""Shared test support; contains no collected tests."""

from __future__ import annotations
from paper_fetch.providers import (
    _ieee_html,
)
from tests.support._ieee_provider_support import *


class _FakeIeeeBrowserResponse:
    def __init__(
        self,
        url: str,
        body: bytes,
        *,
        status: int | None = 200,
        content_type: str | None = "text/html;charset=utf-8",
    ) -> None:
        self.url = url
        self.status = status
        self.headers = (
            {"content-type": content_type} if content_type is not None else {}
        )
        self._body = body
        self.body_calls = 0

    def body(self) -> bytes:
        self.body_calls += 1
        return self._body

    def all_headers(self) -> dict[str, str]:
        return dict(self.headers)


class _FakeIeeeBrowserLocator:
    def __init__(self, page: _FakeIeeeBrowserPage) -> None:
        self._page = page

    def count(self) -> int:
        return int(_ieee_html._find_ieee_article(self._page.html_text) is not None)


class _FakeIeeeBrowserPage:
    def __init__(
        self,
        document_url: str,
        *,
        initial_responses: list[_FakeIeeeBrowserResponse] | None = None,
        delayed_responses: list[_FakeIeeeBrowserResponse] | None = None,
        html_text: str = "<html><body>IEEE document shell</body></html>",
        delayed_html_text: str | None = None,
    ) -> None:
        self.url = document_url
        self.html_text = html_text
        self.initial_responses = list(initial_responses or [])
        self.delayed_responses = list(delayed_responses or [])
        self.delayed_html_text = delayed_html_text
        self.closed = False
        self._response_handler = None
        self.route_pattern = ""
        self.route_handler = None

    def route(self, pattern, handler):
        self.route_pattern = pattern
        self.route_handler = handler

    def on(self, event_name, handler):
        assert event_name == "response"
        self._response_handler = handler

    def _emit(self, responses: list[_FakeIeeeBrowserResponse]) -> None:
        if self._response_handler is None:
            return
        for response in responses:
            self._response_handler(response)

    def goto(self, url, **kwargs):
        assert url == self.url
        del kwargs
        self._emit(self.initial_responses)
        return mock.Mock(status=200)

    def wait_for_timeout(self, timeout):
        assert timeout > 0
        delayed, self.delayed_responses = self.delayed_responses, []
        self._emit(delayed)
        if self.delayed_html_text is not None:
            self.html_text, self.delayed_html_text = self.delayed_html_text, None

    def locator(self, selector):
        assert selector == "#article"
        return _FakeIeeeBrowserLocator(self)

    def content(self):
        return self.html_text

    def title(self):
        return "IEEE Dynamic Article"

    def evaluate(self, expression):
        assert expression == "() => navigator.userAgent"
        return "Mozilla/5.0 Fake IEEE Browser"

    def close(self):
        self.closed = True


class _FakeIeeeBrowserContext:
    def __init__(self, page: _FakeIeeeBrowserPage) -> None:
        self.page = page
        self.closed = False
        self.route_pattern = ""
        self.route_handler = None

    def route(self, pattern, handler):
        self.route_pattern = pattern
        self.route_handler = handler

    def new_page(self):
        return self.page

    def cookies(self, urls=None):
        del urls
        return []

    def close(self):
        self.closed = True
