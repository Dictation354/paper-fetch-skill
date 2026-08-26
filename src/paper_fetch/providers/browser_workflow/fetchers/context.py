"""Browser context helpers for browser workflow fetchers."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable, Mapping

from pathlib import Path

from ....logging_utils import emit_structured_log
from ....http import (
    BrowserNetworkGuard,
    RequestErrorCategory,
    RequestFailure,
    SafeRemoteUrlPolicy,
    guarded_browser_request_get,
    hosts_from_urls,
    provider_allowed_hosts,
    url_origin,
)
from ....runtime import RuntimeContext
from ....runtime_browser import browser_context_options
from ....utils import dedupe_normalized, normalize_text
from ..._pdf_candidates import BROWSER_WORKFLOW_PDF_URL_TOKENS
from ...browser_runtime.seed import parse_optional_int
from ...browser_runtime.context import open_browser_context
from ...browser_runtime.types import BrowserRuntimeConfig
from .diagnostics import (
    _compact_failure_diagnostic,
    _context_failure_diagnostic as _build_context_failure_diagnostic,
    _copy_failure_diagnostic,
)
import contextlib

logger = logging.getLogger("paper_fetch.providers.browser_workflow")
_RUNTIME_SHARED_PAGE_SESSION_KEY = ("browser_workflow", "shared_page_session")
_RUNTIME_FIGURE_PAGE_SESSION_KEY = (
    "browser_workflow",
    "shared_figure_page_session",
)
_BROWSER_MAX_REDIRECTS = 5


@dataclass(frozen=True)
class BrowserDocumentFetcherOptions:
    """Browser runtime and URL-policy options shared by document fetchers."""

    runtime_config: BrowserRuntimeConfig | None = None
    remote_url_policy: SafeRemoteUrlPolicy | None = None


class _SharedBrowserPageSession:
    """Lazily owned browser context/page shared by serial document fetchers."""

    def __init__(
        self,
        *,
        preserve_seed_page: bool = False,
        seed_page_ready_waiter: Callable[[Any, Any, str], bool] | None = None,
    ) -> None:
        self.preserve_seed_page = bool(preserve_seed_page)
        self.seed_page_ready_waiter = seed_page_ready_waiter
        self.manager: Any | None = None
        self.context: Any | None = None
        self.page: Any | None = None
        self.ready_seed_urls: set[str] = set()
        self.cookies_seeded = False
        self.navigation_count = 0
        self._closed = False

    def bind(
        self,
        *,
        manager: Any | None,
        context: Any,
        page: Any,
    ) -> None:
        self.manager = manager
        self.context = context
        self.page = page
        self._closed = False

    def mark_seed_ready(self, seed_url: str) -> None:
        normalized_url = normalize_text(seed_url)
        if normalized_url:
            self.ready_seed_urls.add(normalized_url)

    def seed_is_ready(self, seed_url: str) -> bool:
        return normalize_text(seed_url) in self.ready_seed_urls

    def mark_navigation(self) -> int:
        self.navigation_count += 1
        return self.navigation_count

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for value in (self.page, self.context, self.manager):
            if value is not None:
                with contextlib.suppress(Exception):
                    value.close()
        self.page = None
        self.context = None
        self.manager = None
        self.ready_seed_urls.clear()
        self.cookies_seeded = False
        self.navigation_count = 0


def _runtime_shared_page_session(
    runtime_context: RuntimeContext | None,
) -> _SharedBrowserPageSession | None:
    if runtime_context is None:
        return None
    value = runtime_context.get_session_cache(
        _RUNTIME_SHARED_PAGE_SESSION_KEY,
        copy_value=False,
    )
    return value if isinstance(value, _SharedBrowserPageSession) else None


def _runtime_figure_page_session(
    runtime_context: RuntimeContext | None,
    *,
    create: bool = False,
) -> _SharedBrowserPageSession | None:
    if runtime_context is None:
        return None
    value = runtime_context.get_session_cache(
        _RUNTIME_FIGURE_PAGE_SESSION_KEY,
        copy_value=False,
    )
    if isinstance(value, _SharedBrowserPageSession):
        return value
    if not create:
        return None
    session = _SharedBrowserPageSession(preserve_seed_page=True)
    runtime_context.set_session_cache(
        _RUNTIME_FIGURE_PAGE_SESSION_KEY,
        session,
        copy_value=False,
    )
    return session


def _replace_runtime_shared_page_session(
    runtime_context: RuntimeContext | None,
    session: _SharedBrowserPageSession,
) -> Any | None:
    if runtime_context is None:
        return None
    previous = runtime_context.get_session_cache(
        _RUNTIME_SHARED_PAGE_SESSION_KEY,
        copy_value=False,
    )
    runtime_context.set_session_cache(
        _RUNTIME_SHARED_PAGE_SESSION_KEY,
        session,
        copy_value=False,
    )
    return previous


def _restore_runtime_shared_page_session(
    runtime_context: RuntimeContext | None,
    session: _SharedBrowserPageSession,
    previous: Any | None,
) -> None:
    if runtime_context is None:
        return
    current = runtime_context.get_session_cache(
        _RUNTIME_SHARED_PAGE_SESSION_KEY,
        copy_value=False,
    )
    if current is not session:
        return
    runtime_context.set_session_cache(
        _RUNTIME_SHARED_PAGE_SESSION_KEY,
        previous,
        copy_value=False,
    )


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
    browser_config: BrowserRuntimeConfig | None = None,
) -> tuple[Any | None, Any | None, Any]:
    if browser_config is not None:
        from dataclasses import replace

        active_config = replace(
            browser_config,
            headless=headless,
            user_agent=None,
            persist_storage_state=False,
        )
        manager, browser_context = open_browser_context(
            active_config,
            runtime_context=(
                runtime_context
                if runtime_context is not None and use_runtime_shared_browser
                else None
            ),
        )
        return manager, None, browser_context
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
    del runtime_context
    return normalize_text(cdp_endpoint) or None


def _resolve_browser_env(
    cdp_endpoint: str | None,
    *,
    runtime_context: RuntimeContext | None,
    binary_path: str | Path | None = None,
    profile_dir: str | Path | None = None,
    user_data_dir: str | Path | None = None,
) -> dict[str, str | None]:
    return {
        "binary_path": normalize_text(str(binary_path or "")) or None,
        "cdp_endpoint": _resolve_cdp_endpoint(
            cdp_endpoint, runtime_context=runtime_context
        ),
        "profile_dir": normalize_text(str(profile_dir or "")) or None,
        "user_data_dir": normalize_text(str(user_data_dir or "")) or None,
    }


class _BaseBrowserDocumentFetcher:
    browser_stream_discovery = True

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
        browser_options: BrowserDocumentFetcherOptions | None = None,
    ) -> None:
        options = browser_options or BrowserDocumentFetcherOptions()
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
        self._browser_config = options.runtime_config
        self._remote_url_policy = options.remote_url_policy or SafeRemoteUrlPolicy()
        self._network_guard: BrowserNetworkGuard | None = None
        self._network_guard_installed_on: Any | None = None
        self._shared_page_session = _runtime_shared_page_session(runtime_context)
        self._browser_manager = None
        self._context = None
        self._page = None
        self._warmed_seed_urls: set[str] = set()
        self._last_failure_by_url: dict[str, dict[str, Any]] = {}
        self._last_context_failure: dict[str, Any] = {}

    def failure_for(self, source_url: str) -> dict[str, Any] | None:
        diagnostic = self._last_failure_by_url.get(normalize_text(source_url))
        return dict(diagnostic) if diagnostic else None

    def record_stream_failure(self, source_url: str, **values: Any) -> None:
        self._record_failure(source_url, **values)

    def __call__(
        self, source_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def close(self) -> None:
        if self._shared_page_session is not None:
            self._page = None
            self._context = None
            self._browser_manager = None
            return
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

    def _has_browser_credentials(self) -> bool:
        seed = self._current_seed()
        browser_config = self._browser_config
        return bool(
            list(seed.get("browser_cookies") or [])
            or (
                browser_config
                and (
                    browser_config.storage_state_path
                    or browser_config.profile_dir
                    or browser_config.user_data_dir
                )
            )
            or self._profile_dir
            or self._user_data_dir
        )

    def _credential_origin(self) -> tuple[str, str, int] | None:
        if not self._has_browser_credentials():
            return None
        seed = self._current_seed()
        origin_url = normalize_text(str(seed.get("browser_final_url") or ""))
        if not origin_url:
            origin_url = next(iter(self._seed_urls()), "")
        return url_origin(origin_url)

    def _configure_network_guard(self, source_url: str) -> BrowserNetworkGuard:
        provider = normalize_text(
            self._browser_config.provider if self._browser_config is not None else ""
        ).lower()
        declared_hosts = provider_allowed_hosts(provider) if provider else ()
        seed_urls = [
            *self._seed_urls(),
            normalize_text(str(self._current_seed().get("browser_final_url") or "")),
        ]
        fallback_hosts = hosts_from_urls([*seed_urls, source_url])
        credential_origin = self._credential_origin()
        if self._has_browser_credentials() and credential_origin is None:
            raise RequestFailure(
                None,
                "Credentialed browser asset fetch has no authenticated origin.",
                url=source_url,
                error_category=RequestErrorCategory.UNSAFE_REDIRECT,
            )
        guard = BrowserNetworkGuard(
            allowed_hosts=declared_hosts or fallback_hosts,
            policy=self._remote_url_policy,
            credential_origin=credential_origin,
        )
        guard.validate(source_url, resolve_dns=True)
        self._network_guard = guard
        return guard

    def _browser_target_is_allowed(self, source_url: str) -> bool:
        try:
            self._configure_network_guard(source_url)
        except Exception as exc:
            self._record_failure(
                source_url,
                reason="unsafe_browser_url",
                error_type=exc.__class__.__name__,
            )
            return False
        return True

    def _install_network_guard(self) -> None:
        guard = self._network_guard
        if guard is None or self._context is None:
            raise RequestFailure(
                None,
                "Browser context cannot be opened without a network guard.",
                error_category=RequestErrorCategory.UNSAFE_REDIRECT,
            )
        if self._context is self._network_guard_installed_on:
            return
        guard.install_on_context(self._context)
        self._network_guard_installed_on = self._context

    def _validate_browser_url(
        self,
        url: str,
        *,
        previous_url: str | None = None,
        resolve_dns: bool = False,
    ) -> bool:
        guard = self._network_guard
        if guard is None:
            return False
        try:
            guard.validate(
                url,
                previous_url=previous_url,
                resolve_dns=resolve_dns,
            )
        except Exception:
            return False
        return True

    def _is_same_page_origin(self, url: str, *, page: Any | None = None) -> bool:
        active_page = page if page is not None else self._page
        page_url = normalize_text(str(getattr(active_page, "url", "") or ""))
        return bool(page_url and url_origin(page_url) == url_origin(url))

    def _context_request_get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: int,
    ) -> Any | None:
        """Follow APIRequestContext redirects under the shared URL policy."""

        context = self._context
        guard = self._network_guard
        if context is None or guard is None:
            return None
        try:
            return guarded_browser_request_get(
                context.request,
                url,
                guard=guard,
                headers=headers,
                timeout_ms=timeout,
                max_redirects=_BROWSER_MAX_REDIRECTS,
            )
        except Exception:
            return None

    def _stream_descriptor(
        self,
        source_url: str,
        *,
        status: int = 200,
        headers: Mapping[str, str] | None = None,
        dimensions: Mapping[str, Any] | None = None,
        previous_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Describe a browser-authorized URL for pinned direct streaming."""

        normalized_url = normalize_text(source_url)
        if not normalized_url or not self._validate_browser_url(
            normalized_url,
            previous_url=previous_url,
            resolve_dns=True,
        ):
            self._record_failure(
                source_url,
                reason="unsafe_browser_final_url",
            )
            return None
        cookies: list[dict[str, Any]] = []
        if self._context is not None:
            with contextlib.suppress(Exception):
                raw_cookies = self._context.cookies()
                if isinstance(raw_cookies, list):
                    cookies = [
                        dict(cookie)
                        for cookie in raw_cookies
                        if isinstance(cookie, Mapping)
                    ]
        descriptor: dict[str, Any] = {
            "status_code": int(status),
            "headers": dict(headers or {}),
            "url": normalized_url,
            "_paper_fetch_browser_stream_url": normalized_url,
            "_paper_fetch_browser_cookies": cookies,
        }
        if isinstance(dimensions, Mapping):
            descriptor["dimensions"] = dict(dimensions)
        return descriptor

    def _ensure_context(self, source_url: str | None = None):
        if self._context is not None:
            self._install_network_guard()
            return self._context
        shared_session = self._shared_page_session
        if shared_session is not None and shared_session.context is not None:
            self._browser_manager = shared_session.manager
            self._context = shared_session.context
            self._page = shared_session.page
            self._install_network_guard()
            return self._context

        active_user_agent = normalize_text(
            self._current_seed().get("browser_user_agent")
        ) or normalize_text(self._browser_user_agent)
        try:
            browser_config_kwargs = (
                {"browser_config": self._browser_config}
                if self._browser_config is not None
                else {}
            )
            manager, _unused_browser, active_context = _new_browser_context(
                runtime_context=self._runtime_context,
                headless=self._headless,
                user_agent=active_user_agent,
                use_runtime_shared_browser=self._use_runtime_shared_browser,
                binary_path=self._binary_path,
                cdp_endpoint=self._cdp_endpoint,
                profile_dir=self._profile_dir,
                user_data_dir=self._user_data_dir,
                **browser_config_kwargs,
            )
            self._browser_manager = manager
            self._context = active_context
            context = self._context
            if context is None:
                return None
            self._install_network_guard()
            self._sync_context_cookies()
            self._page = context.new_page()
            if shared_session is not None:
                shared_session.bind(
                    manager=self._browser_manager,
                    context=context,
                    page=self._page,
                )
            self._last_context_failure = {}
        except Exception as exc:
            self._last_context_failure = self._context_failure_diagnostic(exc)
            if source_url:
                self._record_failure(source_url, **self._last_context_failure)
            if shared_session is not None:
                if shared_session.context is not None:
                    shared_session.close()
                else:
                    for value in (
                        self._page,
                        self._context,
                        self._browser_manager,
                    ):
                        if value is not None:
                            with contextlib.suppress(Exception):
                                value.close()
                self._page = None
                self._context = None
                self._browser_manager = None
            else:
                self.close()
            return None
        return self._context

    def _ensure_page(self, source_url: str | None = None):
        if self._page is not None:
            self._install_network_guard()
            return self._page
        if self._ensure_context(source_url) is None:
            return None
        return self._page

    def _sync_context_cookies(self) -> None:
        if self._context is None:
            return
        shared_session = self._shared_page_session
        if shared_session is not None and shared_session.cookies_seeded:
            return
        cookies = list(self._current_seed().get("browser_cookies") or [])
        if not cookies:
            return
        with contextlib.suppress(Exception):
            self._context.add_cookies(cookies)
            if shared_session is not None:
                shared_session.cookies_seeded = True

    def _seed_urls(self) -> list[str]:
        return dedupe_normalized(self._seed_urls_getter())

    def _warm_seed_urls(
        self,
        *,
        force: bool,
        timeout_ms: int = 30000,
        max_urls: int | None = None,
    ) -> None:
        page = self._page
        if page is None:
            return
        if timeout_ms <= 0:
            return
        warmed_count = 0
        for seed_url in self._seed_urls():
            shared_session = self._shared_page_session
            if shared_session is not None and shared_session.seed_is_ready(seed_url):
                self._warmed_seed_urls.add(seed_url)
                continue
            if not force and seed_url in self._warmed_seed_urls:
                continue
            if max_urls is not None and warmed_count >= max_urls:
                break
            try:
                if not self._validate_browser_url(seed_url, resolve_dns=True):
                    warmed_count += 1
                    continue
                page.goto(seed_url, wait_until="domcontentloaded", timeout=timeout_ms)
                final_url = normalize_text(str(getattr(page, "url", "") or ""))
                if final_url and not self._validate_browser_url(
                    final_url,
                    previous_url=seed_url,
                    resolve_dns=True,
                ):
                    warmed_count += 1
                    continue
                if (
                    shared_session is not None
                    and shared_session.seed_page_ready_waiter is not None
                    and not shared_session.seed_page_ready_waiter(
                        page, self._context, seed_url
                    )
                ):
                    warmed_count += 1
                    continue
                self._warmed_seed_urls.add(seed_url)
                if shared_session is not None:
                    shared_session.mark_seed_ready(seed_url)
                warmed_count += 1
            except Exception:
                warmed_count += 1
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
        close_after_call: bool = True,
    ) -> None:
        self._fetcher_factory = fetcher_factory
        self._log_event = log_event
        self.requires_caller_thread = bool(requires_caller_thread)
        self._close_after_call = bool(close_after_call)
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
        except Exception as exc:
            if not self._close_after_call and _looks_like_thread_ownership_error(exc):
                self._close_after_call = True
                self._close_fetcher_for_current_thread(fetcher)
            raise
        finally:
            if self._close_after_call:
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


def _looks_like_thread_ownership_error(exc: Exception) -> bool:
    text = normalize_text(str(exc)).lower()
    return "thread" in text and (
        "owner" in text or "same" in text or "greenlet" in text or "sync" in text
    )
