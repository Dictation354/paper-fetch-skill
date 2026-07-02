"""Browser context helpers for browser workflow fetchers."""

from __future__ import annotations

import logging
import threading
from typing import Any
from collections.abc import Callable, Mapping

from pathlib import Path

from ....config import (
    CLOAKBROWSER_BINARY_PATH_ENV_VAR,
    CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR,
    CLOAKBROWSER_PROFILE_DIR_ENV_VAR,
    CLOAKBROWSER_USER_DATA_DIR_ENV_VAR,
    build_runtime_env,
)
from ....logging_utils import emit_structured_log
from ....runtime import RuntimeContext
from ....runtime_browser import browser_context_options
from ....utils import dedupe_normalized, normalize_text
from ..._pdf_candidates import BROWSER_WORKFLOW_PDF_URL_TOKENS
from ...browser_runtime.seed import parse_optional_int
from .diagnostics import (
    _compact_failure_diagnostic,
    _context_failure_diagnostic as _build_context_failure_diagnostic,
    _copy_failure_diagnostic,
)
import contextlib

logger = logging.getLogger("paper_fetch.providers.browser_workflow")


def _looks_like_pdf_navigation_url(url: str | None) -> bool:
    normalized = normalize_text(url).lower()
    if not normalized:
        return False
    return any(token in normalized for token in BROWSER_WORKFLOW_PDF_URL_TOKENS)


def _choose_browser_seed_url(*candidates: str | None) -> str | None:
    normalized_candidates = [
        normalize_text(candidate)
        for candidate in candidates
        if normalize_text(candidate)
    ]
    for candidate in normalized_candidates:
        if not _looks_like_pdf_navigation_url(candidate):
            return candidate
    return normalized_candidates[0] if normalized_candidates else None


def _normalized_response_headers(headers: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        return {}
    return {
        normalize_text(str(key)).lower(): str(value)
        for key, value in headers.items()
        if normalize_text(str(key))
    }


def _browser_response_headers(response: Any | None) -> dict[str, str]:
    if response is None:
        return {}
    try:
        return _normalized_response_headers(response.all_headers())
    except Exception:
        return _normalized_response_headers(getattr(response, "headers", {}) or {})


def _browser_response_status(
    response: Any | None, *, zero_as_none: bool = True
) -> int | None:
    if response is None:
        return None
    try:
        status = parse_optional_int(getattr(response, "status", None))
    except Exception:
        return None
    if zero_as_none and status == 0:
        return None
    return status


def _new_browser_context(
    *,
    runtime_context: RuntimeContext | None,
    headless: bool,
    user_agent: str | None,
    use_runtime_shared_browser: bool = True,
    binary_path: str | None = None,
    cdp_endpoint: str | None = None,
    profile_dir: str | Path | None = None,
    user_data_dir: str | Path | None = None,
) -> tuple[Any | None, Any | None, Any]:
    context_kwargs = browser_context_options(user_agent=user_agent)
    if runtime_context is not None and use_runtime_shared_browser:
        if isinstance(runtime_context, RuntimeContext):
            browser_env = _resolve_browser_env(
                cdp_endpoint,
                runtime_context=runtime_context,
                binary_path=binary_path,
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
            )
            return (
                None,
                None,
                runtime_context.new_browser_context_for_config(
                    headless=headless,
                    binary_path=browser_env["binary_path"],
                    cdp_endpoint=browser_env["cdp_endpoint"],
                    profile_dir=browser_env["profile_dir"],
                    user_data_dir=browser_env["user_data_dir"],
                    **context_kwargs,
                ),
            )
        return (
            None,
            None,
            runtime_context.new_browser_context(headless=headless, **context_kwargs),
        )

    from ....runtime_browser import BrowserContextManager

    browser_env = _resolve_browser_env(
        cdp_endpoint,
        runtime_context=runtime_context,
        binary_path=binary_path,
        profile_dir=profile_dir,
        user_data_dir=user_data_dir,
    )
    manager = BrowserContextManager(
        binary_path=browser_env["binary_path"],
        cdp_endpoint=browser_env["cdp_endpoint"],
        profile_dir=Path(browser_env["profile_dir"]).expanduser()
        if browser_env["profile_dir"]
        else None,
        user_data_dir=Path(browser_env["user_data_dir"]).expanduser()
        if browser_env["user_data_dir"]
        else None,
    )
    try:
        browser_context = manager.new_context(headless=headless, **context_kwargs)
    except Exception:
        manager.close()
        raise
    return manager, None, browser_context


def _resolve_cdp_endpoint(
    cdp_endpoint: str | None,
    *,
    runtime_context: RuntimeContext | None,
) -> str | None:
    endpoint = normalize_text(cdp_endpoint)
    if endpoint:
        return endpoint
    runtime_env = getattr(runtime_context, "env", None)
    if isinstance(runtime_env, Mapping):
        endpoint = normalize_text(runtime_env.get(CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR))
        if endpoint:
            return endpoint
    endpoint = normalize_text(
        build_runtime_env().get(CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR)
    )
    return endpoint or None


def _resolve_browser_env(
    cdp_endpoint: str | None,
    *,
    runtime_context: RuntimeContext | None,
    binary_path: str | Path | None = None,
    profile_dir: str | Path | None = None,
    user_data_dir: str | Path | None = None,
) -> dict[str, str | None]:
    runtime_env = getattr(runtime_context, "env", None)
    env = runtime_env if isinstance(runtime_env, Mapping) else build_runtime_env()
    return {
        "binary_path": normalize_text(str(binary_path or ""))
        or normalize_text(env.get(CLOAKBROWSER_BINARY_PATH_ENV_VAR))
        or None,
        "cdp_endpoint": _resolve_cdp_endpoint(
            cdp_endpoint, runtime_context=runtime_context
        ),
        "profile_dir": normalize_text(str(profile_dir or ""))
        or normalize_text(env.get(CLOAKBROWSER_PROFILE_DIR_ENV_VAR))
        or None,
        "user_data_dir": normalize_text(str(user_data_dir or ""))
        or normalize_text(env.get(CLOAKBROWSER_USER_DATA_DIR_ENV_VAR))
        or None,
    }


class _BaseBrowserDocumentFetcher:
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
        binary_path: str | None = None,
        cdp_endpoint: str | None = None,
        profile_dir: str | Path | None = None,
        user_data_dir: str | Path | None = None,
    ) -> None:
        self._browser_context_seed_getter = browser_context_seed_getter
        self._seed_urls_getter = seed_urls_getter
        self._browser_user_agent = browser_user_agent
        self._headless = headless
        self._runtime_context = runtime_context
        self._use_runtime_shared_browser = use_runtime_shared_browser
        self.requires_caller_thread = (
            runtime_context is not None and use_runtime_shared_browser
        )
        self._binary_path = normalize_text(binary_path) or None
        self._cdp_endpoint = normalize_text(cdp_endpoint) or None
        self._profile_dir = (
            Path(profile_dir).expanduser() if profile_dir is not None else None
        )
        self._user_data_dir = (
            Path(user_data_dir).expanduser() if user_data_dir is not None else None
        )
        self._browser_manager = None
        self._context = None
        self._page = None
        self._warmed_seed_urls: set[str] = set()
        self._last_failure_by_url: dict[str, dict[str, Any]] = {}
        self._last_context_failure: dict[str, Any] = {}

    def failure_for(self, source_url: str) -> dict[str, Any] | None:
        diagnostic = self._last_failure_by_url.get(normalize_text(source_url))
        return dict(diagnostic) if diagnostic else None

    def __call__(
        self, source_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def close(self) -> None:
        if self._page is not None:
            with contextlib.suppress(Exception):
                self._page.close()
            self._page = None
        if self._context is not None:
            with contextlib.suppress(Exception):
                self._context.close()
            self._context = None
        if self._browser_manager is not None:
            with contextlib.suppress(Exception):
                self._browser_manager.close()
            self._browser_manager = None

    def _current_seed(self) -> Mapping[str, Any]:
        seed = self._browser_context_seed_getter()
        return seed if isinstance(seed, Mapping) else {}

    def _ensure_context(self, source_url: str | None = None):
        if self._context is not None:
            return self._context

        active_user_agent = normalize_text(
            self._current_seed().get("browser_user_agent")
        ) or normalize_text(self._browser_user_agent)
        try:
            self._browser_manager, _unused_browser, self._context = (
                _new_browser_context(
                    runtime_context=self._runtime_context,
                    headless=self._headless,
                    user_agent=active_user_agent,
                    use_runtime_shared_browser=self._use_runtime_shared_browser,
                    binary_path=self._binary_path,
                    cdp_endpoint=self._cdp_endpoint,
                    profile_dir=self._profile_dir,
                    user_data_dir=self._user_data_dir,
                )
            )
            self._sync_context_cookies()
            context = self._context
            if context is None:
                return None
            self._page = context.new_page()
            self._last_context_failure = {}
        except Exception as exc:
            self._last_context_failure = self._context_failure_diagnostic(exc)
            if source_url:
                self._record_failure(source_url, **self._last_context_failure)
            self.close()
            return None
        return self._context

    def _ensure_page(self, source_url: str | None = None):
        if self._page is not None:
            return self._page
        if self._ensure_context(source_url) is None:
            return None
        return self._page

    def _sync_context_cookies(self) -> None:
        if self._context is None:
            return
        cookies = list(self._current_seed().get("browser_cookies") or [])
        if not cookies:
            return
        with contextlib.suppress(Exception):
            self._context.add_cookies(cookies)

    def _seed_urls(self) -> list[str]:
        return dedupe_normalized(self._seed_urls_getter())

    def _warm_seed_urls(self, *, force: bool) -> None:
        page = self._page
        if page is None:
            return
        for seed_url in self._seed_urls():
            if not force and seed_url in self._warmed_seed_urls:
                continue
            try:
                page.goto(seed_url, wait_until="domcontentloaded", timeout=30000)
                self._warmed_seed_urls.add(seed_url)
            except Exception:
                continue

    def _record_failure(self, source_url: str, **values: Any) -> None:
        normalized_url = normalize_text(source_url)
        if not normalized_url:
            return
        diagnostic = _compact_failure_diagnostic(
            {"source_url": normalized_url, **values}
        )
        if diagnostic:
            self._last_failure_by_url[normalized_url] = diagnostic

    def _context_failure_diagnostic(self, exc: Exception) -> dict[str, Any]:
        return _build_context_failure_diagnostic(exc)


class _ThreadLocalSharedDocumentFetcher:
    """Per-thread document fetcher with a shared failure cache.

    Browser sync objects must be created and closed on their owning worker
    thread, so each thread lazily builds its own ``_BaseBrowserDocumentFetcher``
    via ``fetcher_factory``. Failures are mirrored into a shared, lock-guarded
    cache so callers on other threads can still report diagnostics.
    """

    def __init__(
        self,
        *,
        fetcher_factory: Callable[[], _BaseBrowserDocumentFetcher],
        log_event: str,
        requires_caller_thread: bool = False,
    ) -> None:
        self._fetcher_factory = fetcher_factory
        self._log_event = log_event
        self.requires_caller_thread = bool(requires_caller_thread)
        self._thread_local = threading.local()
        self._lock = threading.Lock()
        self._fetchers: list[_BaseBrowserDocumentFetcher] = []
        self._failure_by_url: dict[str, dict[str, Any]] = {}

    def _get_fetcher(self) -> _BaseBrowserDocumentFetcher:
        fetcher = getattr(self._thread_local, "fetcher", None)
        if isinstance(fetcher, _BaseBrowserDocumentFetcher):
            return fetcher
        fetcher = self._fetcher_factory()
        self._thread_local.fetcher = fetcher
        with self._lock:
            self._fetchers.append(fetcher)
        emit_structured_log(
            logger,
            logging.DEBUG,
            self._log_event,
            thread=threading.current_thread().name,
        )
        return fetcher

    def __call__(
        self, source_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        normalized_url = normalize_text(source_url)
        fetcher = self._get_fetcher()
        try:
            payload = fetcher(source_url, asset)
            if normalized_url:
                if payload is None:
                    failure = fetcher.failure_for(normalized_url)
                    if isinstance(failure, Mapping):
                        with self._lock:
                            self._failure_by_url[normalized_url] = (
                                _copy_failure_diagnostic(failure)
                            )
                else:
                    with self._lock:
                        self._failure_by_url.pop(normalized_url, None)
            return payload
        finally:
            # Browser sync objects must be closed from their owning worker
            # thread. Closing these thread-local fetchers later from the caller
            # thread can leave Chromium subprocesses behind.
            self._close_fetcher_for_current_thread(fetcher)

    def failure_for(self, source_url: str) -> dict[str, Any] | None:
        fetcher = getattr(self._thread_local, "fetcher", None)
        if not isinstance(fetcher, _BaseBrowserDocumentFetcher):
            normalized_url = normalize_text(source_url)
            with self._lock:
                cached_failure = self._failure_by_url.get(normalized_url)
            return _copy_failure_diagnostic(cached_failure) if cached_failure else None
        failure = fetcher.failure_for(source_url)
        return (
            _copy_failure_diagnostic(failure) if isinstance(failure, Mapping) else None
        )

    def _close_fetcher_for_current_thread(
        self, fetcher: _BaseBrowserDocumentFetcher
    ) -> None:
        try:
            fetcher.close()
        finally:
            with self._lock:
                self._fetchers = [
                    item for item in self._fetchers if item is not fetcher
                ]
            if getattr(self._thread_local, "fetcher", None) is fetcher:
                with contextlib.suppress(AttributeError):
                    delattr(self._thread_local, "fetcher")

    def close(self) -> None:
        with self._lock:
            fetchers = list(self._fetchers)
            self._fetchers.clear()
        for fetcher in fetchers:
            fetcher.close()
