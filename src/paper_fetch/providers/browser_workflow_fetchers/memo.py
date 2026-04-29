"""Memoized wrappers for browser workflow fetchers."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future
from typing import Any, Callable, Mapping

from ...logging_utils import emit_structured_log
from ...utils import normalize_text
from .diagnostics import _copy_failure_diagnostic
from .image import _copy_image_payload

logger = logging.getLogger("paper_fetch.providers.browser_workflow")


class _MemoizedImageDocumentFetcher:
    def __init__(self, fetcher: Any) -> None:
        self._fetcher = fetcher
        self._lock = threading.Lock()
        self._payload_by_url: dict[str, dict[str, Any]] = {}
        self._failure_by_url: dict[str, dict[str, Any]] = {}
        self._inflight_by_url: dict[str, Future[dict[str, Any] | None]] = {}

    def __call__(
        self, image_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        normalized_url = normalize_text(image_url)
        if not normalized_url:
            return self._fetcher(image_url, asset)
        with self._lock:
            cached_payload = self._payload_by_url.get(normalized_url)
            if cached_payload is not None:
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_image_candidate_cache",
                    state="hit_payload",
                    url=normalized_url,
                )
                return _copy_image_payload(cached_payload)
            if normalized_url in self._failure_by_url:
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_image_candidate_cache",
                    state="hit_failure",
                    url=normalized_url,
                )
                return None
            future = self._inflight_by_url.get(normalized_url)
            if future is None:
                future = Future()
                self._inflight_by_url[normalized_url] = future
                owner = True
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_image_candidate_cache",
                    state="miss",
                    url=normalized_url,
                )
            else:
                owner = False
        if not owner:
            payload = future.result()
            return _copy_image_payload(payload) if payload is not None else None

        try:
            payload = self._fetcher(normalized_url, asset)
            copied_payload = (
                _copy_image_payload(payload) if isinstance(payload, Mapping) else None
            )
            reporter = getattr(self._fetcher, "failure_for", None)
            failure = reporter(normalized_url) if callable(reporter) else None
            copied_failure = (
                _copy_failure_diagnostic(failure)
                if isinstance(failure, Mapping)
                else None
            )
            if copied_payload is None and copied_failure is None:
                copied_failure = {
                    "source_url": normalized_url,
                    "reason": "image_fetch_error",
                }
        except Exception as exc:
            with self._lock:
                future = self._inflight_by_url.pop(normalized_url)
            future.set_exception(exc)
            raise

        with self._lock:
            if copied_payload is not None:
                self._payload_by_url[normalized_url] = copied_payload
            else:
                self._failure_by_url[normalized_url] = copied_failure or {
                    "source_url": normalized_url,
                    "reason": "image_fetch_error",
                }
            future = self._inflight_by_url.pop(normalized_url)
        future.set_result(copied_payload)
        return (
            _copy_image_payload(copied_payload) if copied_payload is not None else None
        )

    def failure_for(self, image_url: str) -> dict[str, Any] | None:
        normalized_url = normalize_text(image_url)
        with self._lock:
            cached_failure = self._failure_by_url.get(normalized_url)
            if cached_failure is not None:
                return _copy_failure_diagnostic(cached_failure)
            cached_payload = self._payload_by_url.get(normalized_url)
            if cached_payload is not None:
                return None
        reporter = getattr(self._fetcher, "failure_for", None)
        if not callable(reporter):
            return None
        failure = reporter(normalized_url)
        return (
            _copy_failure_diagnostic(failure) if isinstance(failure, Mapping) else None
        )

    def close(self) -> None:
        close_fetcher = getattr(self._fetcher, "close", None)
        if callable(close_fetcher):
            close_fetcher()


class _MemoizedFigurePageFetcher:
    def __init__(self, fetcher: Callable[[str], tuple[str, str] | None]) -> None:
        self._fetcher = fetcher
        self._lock = threading.Lock()
        self._values_by_url: dict[str, tuple[str, str] | None] = {}
        self._inflight_by_url: dict[str, Future[tuple[str, str] | None]] = {}

    def __call__(self, figure_page_url: str) -> tuple[str, str] | None:
        normalized_url = normalize_text(figure_page_url)
        if not normalized_url:
            return None
        with self._lock:
            if normalized_url in self._values_by_url:
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_figure_page_cache",
                    state="hit",
                    url=normalized_url,
                )
                return self._values_by_url[normalized_url]
            future = self._inflight_by_url.get(normalized_url)
            if future is None:
                future = Future()
                self._inflight_by_url[normalized_url] = future
                owner = True
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_figure_page_cache",
                    state="miss",
                    url=normalized_url,
                )
            else:
                owner = False
        if not owner:
            return future.result()

        try:
            value = self._fetcher(normalized_url)
        except Exception as exc:
            with self._lock:
                future = self._inflight_by_url.pop(normalized_url)
            future.set_exception(exc)
            raise

        with self._lock:
            self._values_by_url[normalized_url] = value
            future = self._inflight_by_url.pop(normalized_url)
        future.set_result(value)
        return value
