"""Wiley body images captured from serial image navigations in one owned browser session."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import threading
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urldefrag

from ..asset_budget import AssetBudget, AssetBudgetExceeded, current_asset_budget
from ..extraction.image_payloads import (
    image_dimensions_from_bytes,
    image_mime_type_from_bytes,
)
from ..extraction.html.signals import CHALLENGE_PATTERNS
from ..http import (
    RequestCancelledError,
    redact_text_for_diagnostics,
)
from .browser_workflow.fetchers.context import _BaseBrowserDocumentFetcher

_FAILURE_BODY_LIMIT = 64 * 1024
_FAILURE_HEADERS = frozenset(
    {
        "content-type",
        "content-length",
        "server",
        "cf-ray",
        "cf-mitigated",
        "cf-cache-status",
        "retry-after",
        "x-amzn-waf-action",
    }
)


# URL equality preserves path case, asset UUIDs and query strings. A figure's
# identity never depends on response order or a basename shared by other papers.
def asset_urls(asset: Mapping[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            urldefrag(str(asset.get(field) or ""))[0]
            for field in ("download_url", "full_size_url", "url", "preview_url")
            if asset.get(field)
        )
    )


_LOADED = r"""urls => [...document.images].some(img => {
    const current = img.currentSrc || img.src;
    return current && urls.includes(new URL(current, location.href).href.split('#')[0])
        && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0;
})"""


class WileyPageAssetFetcher(_BaseBrowserDocumentFetcher):
    """Caller-thread, request-scoped raw capture; one navigation per candidate."""

    browser_backend = "camoufox"

    def __init__(self, *, assets: list[dict[str, Any]], **kwargs) -> None:
        super().__init__(**kwargs)
        # Always own a fresh asset context/page, while reusing the runtime's
        # browser manager. Do not borrow or close another fetcher's page session.
        self._shared_page_session = None
        self._page: Any = None
        self.requires_caller_thread = True
        self._owner = threading.get_ident()
        self._allowed = {url for asset in assets for url in asset_urls(asset)}
        self._responses: dict[str, tuple[dict[str, Any], Any]] = {}
        self._attempted: set[str] = set()
        self._deadlines: dict[tuple[str, ...], float] = {}
        self._opened = False
        self._closed = False
        self._listening = False
        self._active_url: str | None = None
        self._requests: set[Any] = set()
        self._started_at = 0.0
        self._recovery_attempts: dict[str, list[dict[str, Any]]] = {}
        self._capture_error: Exception | None = None
        self._budget: AssetBudget | None = None
        self._ready_at: float | None = None
        self._last_image_at: float | None = None
        self.navigation_count = 0
        # All candidates for a logical body asset share this window. This is
        # intentionally independent of supplementary-file/HTTP route timeouts.
        self._timeout = 30.0

    def _check(self) -> None:
        if threading.get_ident() != self._owner:
            raise RuntimeError("Wiley asset page must stay on its owning thread")
        if self._runtime_context is not None:
            self._runtime_context.raise_if_cancelled()
        if self._capture_error is not None:
            raise self._capture_error
        if self._budget is not None:
            self._budget.raise_if_cancelled()

    def _remaining(self, deadline: float) -> float:
        self._check()
        remaining = max(0.0, deadline - time.monotonic())
        if self._runtime_context is not None:
            remaining = self._runtime_context.remaining_seconds(remaining)
        return remaining

    def _track_request(self, request) -> None:
        if self._closed or self._active_url is None:
            return
        if (
            request.frame != self._page.main_frame
            or not request.is_navigation_request()
        ):
            return
        previous = request.redirected_from
        if previous is not None:
            if previous not in self._requests:
                return
        elif urldefrag(request.url)[0] != self._active_url:
            return
        self._requests.add(request)

    def _capture(self, request) -> None:
        """Accept only requests started in this navigation, including redirects.

        A site's own re-navigation to the candidate after a challenge is allowed;
        late completions/redirects from the previous candidate are not.
        """
        url = self._active_url
        if self._closed or url is None or request not in self._requests:
            return
        if url in self._responses:
            return
        reservation = None
        try:
            self._check()
            response = request.response()
            if response is None:
                return
            if 300 <= response.status < 400:
                return  # The browser follows this request's tracked redirect chain.
            if response.status != 200:
                self._record_failed_response(url, response)
                return
            headers = dict(response.all_headers())
            length = headers.get("content-length", "")
            assert self._budget is not None
            reservation = self._budget.reserve_transient(
                declared_bytes=int(length) if length.isdigit() else None,
            )
            body = response.body()
            reservation.consume(len(body))
            reservation.reconcile_actual()
            mime = image_mime_type_from_bytes(body)
            dimensions = image_dimensions_from_bytes(body)
            if not mime or dimensions is None:
                reservation.rollback()
                reservation = None
                self._record_failed_response(url, response)
                if not self._is_challenge(url):
                    self._record_failure(url, reason="wiley_page_invalid_image")
                return
            reservation.validate_pixels(*dimensions)
            self._responses[url] = (
                {
                    "url": response.url,
                    "status_code": response.status,
                    "headers": {
                        **headers,
                        "content-type": mime,
                        "content-length": str(len(body)),
                    },
                    "body": body,
                    "_paper_fetch_final_fetcher": "camoufox",
                },
                reservation,
            )
            reservation = None
        except (RequestCancelledError, AssetBudgetExceeded) as exc:
            self._capture_error = exc
        except Exception as exc:
            self._record_failure(
                url,
                reason="wiley_page_response_unavailable",
                error_type=type(exc).__name__,
            )
        finally:
            if reservation is not None:
                reservation.rollback()

    def _record_failed_response(self, url: str, response: Any) -> None:
        """Keep bounded evidence from the received response, never refetch it."""
        diagnostic: dict[str, Any] = {"body_state": "unavailable"}
        reservation = None
        try:
            headers = {
                str(key).lower(): str(value)
                for key, value in response.all_headers().items()
            }
            diagnostic["headers"] = {
                key: redact_text_for_diagnostics(value)[:256]
                for key, value in headers.items()
                if key in _FAILURE_HEADERS
            }
            # A Cloudflare server/ray header alone does not prove a challenge.
            diagnostic["cf_mitigated_challenge"] = (
                headers.get("cf-mitigated", "").strip().lower() == "challenge"
            )
            length = headers.get("content-length", "")
            declared = int(length) if length.isdigit() else None
            if declared is not None and declared > _FAILURE_BODY_LIMIT:
                diagnostic["body_state"] = "skipped_declared_size"
                return
            self._check()
            assert self._budget is not None
            reservation = self._budget.reserve_transient(declared_bytes=declared)
            body = response.body()
            reservation.consume(len(body))
            self._check()
            diagnostic["body_bytes"] = len(body)
            diagnostic["body_sha256"] = hashlib.sha256(body).hexdigest()
            prefix = (
                body[:_FAILURE_BODY_LIMIT].decode("utf-8", errors="replace").lower()
            )
            diagnostic["body_state"] = "inspected"
            diagnostic["body_scan_truncated"] = len(body) > _FAILURE_BODY_LIMIT
            # Store only fixed markers, not text, tokens, scripts or user data.
            diagnostic["body_markers"] = [
                marker
                for marker in (
                    *CHALLENGE_PATTERNS,
                    "/cdn-cgi/challenge-platform/",
                    "cf-chl-",
                    "_cf_chl_opt",
                    "access denied",
                )
                if marker in prefix
            ]
        except (RequestCancelledError, AssetBudgetExceeded):
            diagnostic["body_state"] = "cancelled_or_budget_exceeded"
            raise
        except Exception as exc:
            diagnostic["diagnostic_error_type"] = type(exc).__name__
        finally:
            if reservation is not None:
                reservation.rollback()
            self._record_failure(
                url,
                reason="wiley_page_image_response",
                status=response.status,
                response_diagnostic=diagnostic,
            )
            if self._is_challenge(url):
                self._recovery_attempts.setdefault(url, []).append(
                    {
                        "stage": "browser_challenge",
                        "reason": "cloudflare_challenge",
                        "status": response.status,
                        "response_diagnostic": diagnostic,
                        "elapsed_seconds": round(
                            time.monotonic() - self._started_at, 3
                        ),
                    }
                )

    def _is_challenge(self, url: str) -> bool:
        diagnostic = (self.failure_for(url) or {}).get("response_diagnostic", {})
        return bool(
            diagnostic.get("cf_mitigated_challenge")
            or any(
                marker != "access denied"
                for marker in diagnostic.get("body_markers", [])
            )
        )

    def _open(self, source_url: str) -> bool:
        if self._opened:
            return self._page is not None
        self._opened = True
        self._budget = (
            getattr(self._runtime_context, "asset_budget", None)
            or current_asset_budget()
            or AssetBudget()
        )
        page = self._ensure_page(source_url)
        if page is None:
            return False
        # Both listeners precede the first navigation; seed cookies are installed
        # once by _ensure_context, never over the browser's later cookie state.
        page.on("request", self._track_request)
        page.on("requestfinished", self._capture)
        self._listening = True
        self._ready_at = time.monotonic()
        return True

    def _loaded_response(self, url: str) -> dict[str, Any] | None:
        if url not in self._responses:
            return None
        response, reservation = self._responses[url]
        final_url = urldefrag(response["url"])[0]
        if urldefrag(self._page.url)[0] != final_url:
            return None
        # Firefox image documents retain the original navigation URL in
        # currentSrc after an HTTP redirect, while src/location use the final URL.
        if not self._page.evaluate(_LOADED, [url, final_url]):
            return None
        self._check()
        self._responses.pop(url)
        reservation.rollback()  # Normal downloader now owns/stages these bytes.
        self._last_failure_by_url.pop(url, None)
        self._last_image_at = time.monotonic()
        attempts = self._recovery_attempts.get(url, [])
        if attempts:
            attempts.append(
                {
                    "stage": "browser",
                    "reason": "recovered",
                    "status": 200,
                    "elapsed_seconds": round(self._last_image_at - self._started_at, 3),
                }
            )
            response["_paper_fetch_recovery_attempts"] = list(attempts)
        return response

    def __call__(
        self, source_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        if threading.get_ident() != self._owner:
            raise RuntimeError("Wiley asset page must stay on its owning thread")
        url = urldefrag(source_url)[0]
        if (
            self._closed
            or url not in self._allowed
            or url not in asset_urls(asset)
            or url in self._attempted
        ):
            return None
        self._attempted.add(url)
        key = tuple(asset_urls(asset))
        deadline = self._deadlines.setdefault(key, time.monotonic() + self._timeout)
        try:
            self._check()
            if self._remaining(deadline) <= 0:
                prior_failure = next(
                    (
                        failure
                        for candidate in asset_urls(asset)
                        if (failure := self.failure_for(candidate))
                    ),
                    None,
                )
                self._record_failure(
                    url,
                    reason=(prior_failure or {}).get(
                        "reason", "wiley_page_image_not_loaded"
                    ),
                    candidate_not_navigated=True,
                    recovery_attempts=[{"stage": "full_size", **prior_failure}]
                    if prior_failure
                    else [],
                )
                return None
            if not self._open(url):
                self._check()
                if not self.failure_for(url):
                    self._record_failure(url, reason="wiley_asset_page_unavailable")
                return None
            remaining = self._remaining(deadline)
            if remaining <= 0:
                self._record_failure(url, reason="wiley_page_image_not_loaded")
                return None
            self._active_url = url
            self._started_at = time.monotonic()
            self.navigation_count += 1
            navigation_error = None
            try:
                self._page.goto(
                    url, wait_until="commit", timeout=max(1, int(remaining * 1000))
                )
            except (RequestCancelledError, AssetBudgetExceeded):
                raise
            except Exception as exc:
                # goto can time out/abort even when the image itself has arrived.
                # Check response + DOM evidence before treating it as a failure.
                navigation_error = type(exc).__name__
            while True:
                self._check()
                if (
                    self._runtime_context is not None
                    and self._runtime_context.remaining_seconds() <= 0
                ):
                    self.close()
                    return None
                try:
                    response = self._loaded_response(url)
                    if response is not None:
                        prior = []
                        for candidate in asset_urls(asset):
                            if candidate == url:
                                continue
                            failure = self.failure_for(candidate)
                            if failure:
                                prior.append({"stage": "full_size", **failure})
                        if prior:
                            response["_paper_fetch_recovery_attempts"] = [
                                *prior,
                                *response.get("_paper_fetch_recovery_attempts", []),
                            ]
                        return response
                except (RequestCancelledError, AssetBudgetExceeded):
                    raise
                except Exception:
                    # A site-initiated verification redirect can destroy the DOM
                    # execution context; continue within the same deadline.
                    pass
                if self.failure_for(url) and not self._is_challenge(url):
                    return None
                remaining = self._remaining(deadline)
                if remaining <= 0:
                    break
                self._page.wait_for_timeout(min(100, remaining * 1000))
            failure = self.failure_for(url) or {}
            failure.pop("source_url", None)
            self._record_failure(
                url,
                **{
                    **failure,
                    "reason": "cloudflare_challenge"
                    if self._is_challenge(url)
                    else "wiley_page_image_not_loaded",
                    "navigation_error_type": navigation_error,
                    "recovery_attempts": list(self._recovery_attempts.get(url, [])),
                },
            )
            return None
        except (RequestCancelledError, AssetBudgetExceeded):
            self.close()
            raise
        except Exception as exc:
            self._record_failure(
                url, reason="wiley_page_image_error", error_type=type(exc).__name__
            )
            return None
        finally:
            self._active_url = None
            self._requests.clear()
            for _, reservation in self._responses.values():
                reservation.rollback()
            self._responses.clear()
            if self._runtime_context is not None and not self._closed:
                try:
                    if self._runtime_context.remaining_seconds() <= 0:
                        self.close()
                except RequestCancelledError:
                    self.close()
                    raise

    def close(self) -> None:
        if self._closed:
            return
        if threading.get_ident() != self._owner:
            raise RuntimeError("Wiley asset cleanup must stay on its owning thread")
        self._closed = True
        if self._listening and self._page is not None:
            with contextlib.suppress(Exception):
                self._page.remove_listener("requestfinished", self._capture)
            with contextlib.suppress(Exception):
                self._page.remove_listener("request", self._track_request)
        self._requests.clear()
        for _, reservation in self._responses.values():
            reservation.rollback()
        self._responses.clear()
        super().close()
        logging.getLogger(__name__).info(
            "Wiley page assets: navigations=%s failures=%s ready_to_last_image_seconds=%s",
            self.navigation_count,
            len(self._last_failure_by_url),
            (self._last_image_at - self._ready_at)
            if self._last_image_at is not None and self._ready_at is not None
            else None,
        )
