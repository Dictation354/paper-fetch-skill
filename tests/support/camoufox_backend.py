"""Shared test support; contains no collected tests."""

from __future__ import annotations
from unittest import mock


class _Response:
    status = 200
    headers = {"content-type": "text/html"}

    def all_headers(self):
        return dict(self.headers)


class _Page:
    def __init__(self) -> None:
        self.url = "https://example.test/article"
        self.goto_kwargs: dict[str, object] = {}
        self.route_handler = None
        self.wait_for_function = mock.Mock()
        self.wait_for_selector = mock.Mock()
        self.wait_for_timeout = mock.Mock()

    def goto(self, url: str, **kwargs):
        self.url = url
        self.goto_kwargs = dict(kwargs)
        return _Response()

    def route(self, _pattern: str, handler) -> None:
        self.route_handler = handler

    def content(self) -> str:
        return "<html><head><title>Article</title></head><body><main>Full text</main></body></html>"

    def title(self) -> str:
        return "Article"

    def evaluate(self, _script: str):
        return "Mozilla/5.0 Firefox/152.0"

    def close(self) -> None:
        pass


class _Context:
    def __init__(self) -> None:
        self.page = _Page()
        self.added_cookies: list[dict[str, object]] = []
        self.events: list[str] = []
        self.route_handler = None

    def add_cookies(self, cookies):
        self.events.append("add_cookies")
        self.added_cookies.extend(cookies)

    def route(self, _pattern: str, handler) -> None:
        self.route_handler = handler

    def new_page(self):
        self.events.append("new_page")
        return self.page

    def cookies(self, _urls=None):
        return []

    def close(self) -> None:
        pass
