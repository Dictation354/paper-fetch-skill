"""Playwright context helpers for browser workflow fetchers."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from ...config import build_user_agent
from ...runtime import RuntimeContext
from ...utils import normalize_text
from .diagnostics import _compact_failure_diagnostic


def _looks_like_pdf_navigation_url(url: str | None) -> bool:
    normalized = normalize_text(url).lower()
    if not normalized:
        return False
    return any(
        token in normalized
        for token in ("/doi/pdf", "/doi/pdfdirect", "/doi/epdf", "/fullpdf", ".pdf")
    )


def _choose_playwright_seed_url(*candidates: str | None) -> str | None:
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


def _new_playwright_context(
    *,
    runtime_context: RuntimeContext | None,
    headless: bool,
    user_agent: str,
    use_runtime_shared_browser: bool = True,
) -> tuple[Any | None, Any | None, Any]:
    context_kwargs = {
        "user_agent": user_agent,
        "locale": "en-US",
        "viewport": {"width": 1440, "height": 1600},
    }
    if runtime_context is not None and use_runtime_shared_browser:
        return (
            None,
            None,
            runtime_context.new_playwright_context(headless=headless, **context_kwargs),
        )

    from playwright.sync_api import sync_playwright

    manager = sync_playwright().start()
    browser = None
    try:
        browser = manager.chromium.launch(headless=headless)
        return manager, browser, browser.new_context(**context_kwargs)
    except Exception:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        try:
            manager.stop()
        except Exception:
            pass
        raise


class _BasePlaywrightDocumentFetcher:
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        challenge_recovery: Callable[
            [str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None
        ]
        | None = None,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
    ) -> None:
        self._browser_context_seed_getter = browser_context_seed_getter
        self._seed_urls_getter = seed_urls_getter
        self._browser_user_agent = browser_user_agent
        self._headless = headless
        self._challenge_recovery = challenge_recovery
        self._runtime_context = runtime_context
        self._use_runtime_shared_browser = use_runtime_shared_browser
        self._playwright_manager = None
        self._browser = None
        self._context = None
        self._page = None
        self._warmed_seed_urls: set[str] = set()
        self._last_failure_by_url: dict[str, dict[str, Any]] = {}
        self._recovery_attempts_by_url: dict[str, list[dict[str, Any]]] = {}

    def failure_for(self, source_url: str) -> dict[str, Any] | None:
        diagnostic = self._last_failure_by_url.get(normalize_text(source_url))
        return dict(diagnostic) if diagnostic else None

    def close(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright_manager is not None:
            try:
                self._playwright_manager.stop()
            except Exception:
                pass
            self._playwright_manager = None

    def _current_seed(self) -> Mapping[str, Any]:
        seed = self._browser_context_seed_getter()
        return seed if isinstance(seed, Mapping) else {}

    def _ensure_context(self):
        if self._context is not None:
            return self._context

        active_user_agent = (
            normalize_text(self._current_seed().get("browser_user_agent"))
            or normalize_text(self._browser_user_agent)
            or build_user_agent({})
        )
        try:
            self._playwright_manager, self._browser, self._context = (
                _new_playwright_context(
                    runtime_context=self._runtime_context,
                    headless=self._headless,
                    user_agent=active_user_agent,
                    use_runtime_shared_browser=self._use_runtime_shared_browser,
                )
            )
            self._sync_context_cookies()
            self._page = self._context.new_page()
        except Exception:
            self.close()
            return None
        return self._context

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        if self._ensure_context() is None:
            return None
        return self._page

    def _sync_context_cookies(self) -> None:
        if self._context is None:
            return
        cookies = list(self._current_seed().get("browser_cookies") or [])
        if not cookies:
            return
        try:
            self._context.add_cookies(cookies)
        except Exception:
            pass

    def _seed_urls(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in self._seed_urls_getter() or []:
            normalized = normalize_text(candidate)
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

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
        recovery_attempts = self._recovery_attempts_by_url.get(normalized_url) or []
        if recovery_attempts:
            diagnostic["recovery_attempts"] = list(recovery_attempts)
        if diagnostic:
            self._last_failure_by_url[normalized_url] = diagnostic

    def _record_recovery_payload(
        self, source_url: str, recovery: Mapping[str, Any]
    ) -> None:
        del source_url, recovery

    def _recovery_diagnostic(self, recovery: Mapping[str, Any]) -> dict[str, Any]:
        return _compact_failure_diagnostic(recovery)

    def _attempt_challenge_recovery(
        self,
        source_url: str,
        asset: Mapping[str, Any],
        failure: Mapping[str, Any],
    ) -> bool:
        normalized_url = normalize_text(source_url)
        if not normalized_url or self._challenge_recovery is None:
            return False
        try:
            recovery = self._challenge_recovery(normalized_url, asset, failure)
        except Exception as exc:
            recovery = {
                "status": "error",
                "reason": normalize_text(str(exc)) or exc.__class__.__name__,
            }
        if not isinstance(recovery, Mapping):
            return False
        self._record_recovery_payload(normalized_url, recovery)
        compact = self._recovery_diagnostic(recovery)
        if compact:
            self._recovery_attempts_by_url.setdefault(normalized_url, []).append(
                compact
            )
            previous = self.failure_for(normalized_url) or {}
            previous.pop("source_url", None)
            self._record_failure(normalized_url, **previous)
        if normalize_text(str(recovery.get("status") or "")).lower() != "ok":
            return False
        self._sync_context_cookies()
        self._warm_seed_urls(force=True)
        return True
