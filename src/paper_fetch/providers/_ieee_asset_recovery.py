"""IEEE direct-first asset recovery through the selected browser backend."""

from __future__ import annotations

import contextlib
import json
import re
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from ..extraction.html import decode_html
from ..extraction.html.signals import detect_html_block, summarize_visible_html
from ..extraction.html.assets.figures import figure_download_candidates
from ..http.headers import header_value
from ..models import AssetProfile
from ..publisher_identity import normalize_doi
from ..runtime import RuntimeContext
from ..utils import normalize_text
from ._ieee_metadata import IeeeLandingAttempt, _landing_metadata_has_multimedia_scope
from ._ieee_url import IEEE_BASE_URL, IEEE_MULTIMEDIA_URL_TEMPLATE
from .browser_runtime.types import BrowserRuntimeConfig
from .browser_workflow.asset_download import (
    BrowserAssetDownloadPlan,
    BrowserAssetRecoveryContext,
    download_browser_backed_related_assets,
)
from .browser_workflow.fetchers import (
    BrowserDocumentFetcherOptions,
    _MemoizedImageDocumentFetcher,
    _SharedBrowserPageSession,
    _replace_runtime_shared_page_session,
    _restore_runtime_shared_page_session,
)
from .browser_workflow.shared import default_browser_workflow_deps
from .browser_workflow.fetchers.image import (
    _ImageFetchBudget,
    _looks_like_image_response_payload,
)
from .browser_workflow.fetchers.context import (
    _browser_response_headers,
    _browser_response_status,
)

IEEE_ASSET_ARTICLE_READY_TIMEOUT_SECONDS = 15.0
IEEE_ASSET_ARTICLE_READY_POLL_MS = 250
_IEEE_ARTICLE_SEED_READINESS_SCRIPT = """
articleNumber => {
  const article = document.querySelector('#article');
  const articleMarkup = article ? (article.outerHTML || article.textContent || '') : '';
  let restDocumentSeen = false;
  try {
    restDocumentSeen = performance.getEntriesByType('resource')
      .some(entry => entry.name.includes('/rest/document/' + articleNumber + '/'));
  } catch (error) {
    restDocumentSeen = false;
  }
  return {
    articlePresent: Boolean(article),
    articleMatches: Boolean(article && articleNumber && articleMarkup.includes(articleNumber)),
    restDocumentSeen,
  };
}
"""


class _IeeePreviewWarmImageFetcher:
    """Recover originals through IEEE's article links in the shared session."""

    def __init__(
        self,
        fetcher: _MemoizedImageDocumentFetcher,
        shared_page_session: _SharedBrowserPageSession | None = None,
    ) -> None:
        self._fetcher = fetcher
        self.browser_backend = fetcher.browser_backend
        self.requires_caller_thread = fetcher.requires_caller_thread
        self._warm_lock = threading.Lock()
        self._preview_warm_attempted = False
        self._shared_page_session = shared_page_session
        self._article_failures: dict[str, dict[str, Any]] = {}

    def __call__(
        self, image_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        normalized_url = normalize_text(image_url)
        preview_url = normalize_text(
            str(asset.get("preview_url") or asset.get("url") or "")
        )
        with self._warm_lock:
            if (
                not self._preview_warm_attempted
                and preview_url
                and normalized_url
                and preview_url != normalized_url
            ):
                self._preview_warm_attempted = True
                self._fetcher(preview_url, asset)
            if normalized_url and normalized_url != preview_url:
                payload = self._fetch_article_original(normalized_url)
                if payload is not None:
                    return payload
            return self._fetcher(normalized_url or image_url, asset)

    def _fetch_article_original(self, image_url: str) -> dict[str, Any] | None:
        session = self._shared_page_session
        if session is None or session.page is None or session.context is None:
            return None
        page = session.page
        budget = _ImageFetchBudget(10.0)
        popup = None
        figure = False
        try:
            # Match the actual original URL, including table links without a
            # data-fig-id. An asset label alone cannot establish this identity.
            entry = page.locator("#article a[href]").evaluate_all(
                """(nodes, target) => {
                    const node = nodes.find(n => n.href === target && n.querySelector('img'));
                    return node ? {href: node.getAttribute('href'),
                                   figure: Boolean(node.dataset.figId)} : null;
                }""",
                image_url,
            )
            if not isinstance(entry, Mapping):
                self._article_failures[image_url] = {
                    "reason": "article_image_entry_missing"
                }
                return None
            figure = bool(entry.get("figure"))
            link = page.locator(f"#article a[href={json.dumps(entry['href'])}]").first
            with session.context.expect_event(
                "response",
                predicate=lambda response: (
                    response.url == image_url
                    and response.request.resource_type
                    == ("image" if figure else "document")
                ),
                timeout=budget.timeout_ms(10000),
            ) as response_info:
                if figure:
                    link.click(timeout=budget.timeout_ms(10000))
                else:
                    # Plain table links navigate the document. Use the browser's
                    # native new-tab action to keep the seeded article intact.
                    with page.expect_popup(
                        timeout=budget.timeout_ms(10000)
                    ) as popup_info:
                        link.click(
                            modifiers=["ControlOrMeta"],
                            timeout=budget.timeout_ms(10000),
                        )
                    popup = popup_info.value
            response = response_info.value
            headers = _browser_response_headers(response)
            status = _browser_response_status(response)
            body = response.body()
            content_type = header_value(headers, "content-type")
            if (
                status is None
                or not 200 <= status < 300
                or not content_type.lower().startswith("image/")
                or not _looks_like_image_response_payload(content_type, body, image_url)
            ):
                self._article_failures[image_url] = {
                    "reason": "article_original_invalid_response",
                    "status": status,
                    "content_type": content_type,
                }
                return None
            return {
                "status_code": status,
                "headers": headers,
                "body": body,
                "url": response.url,
            }
        except Exception as exc:
            self._article_failures[image_url] = {
                "reason": "article_original_load_failed",
                "error_type": type(exc).__name__,
            }
            return None
        finally:
            if popup is not None:
                with contextlib.suppress(Exception):
                    popup.close()
            if figure:
                with contextlib.suppress(Exception):
                    close = page.locator(
                        '.close-container button[aria-label="Close modal"]'
                    ).first
                    if close.is_visible():
                        close.click(timeout=1000)

    def failure_for(self, image_url: str) -> dict[str, Any] | None:
        failure = self._fetcher.failure_for(image_url)
        article_failure = self._article_failures.get(image_url)
        if article_failure is not None:
            return {
                **(failure or article_failure),
                "recovery_attempts": [
                    {"stage": "article_original", **article_failure},
                    *list((failure or {}).get("recovery_attempts") or []),
                ],
            }
        return failure

    def close(self) -> None:
        self._fetcher.close()


def _ieee_article_seed_page_is_ready(page: Any, context: Any, seed_url: str) -> bool:
    """Wait for IEEE's initial HTTP 202 verification to populate page state."""

    article_match = re.search(r"/document/([^/?#]+)", seed_url)
    article_number = normalize_text(article_match.group(1) if article_match else "")
    deadline = time.monotonic() + IEEE_ASSET_ARTICLE_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        title = ""
        html = ""
        try:
            title = normalize_text(str(page.title() or ""))
        except Exception:
            title = ""
        try:
            html = str(page.content() or "")
        except Exception:
            html = ""
        readiness: Mapping[str, Any] = {}
        try:
            evaluated = page.evaluate(
                _IEEE_ARTICLE_SEED_READINESS_SCRIPT,
                article_number,
            )
            if isinstance(evaluated, Mapping):
                readiness = evaluated
        except Exception:
            readiness = {}
        if bool(readiness.get("articleMatches")):
            detected = detect_html_block(
                title,
                summarize_visible_html(html),
                None,
            )
            if detected is None:
                return True
        try:
            page.wait_for_timeout(IEEE_ASSET_ARTICLE_READY_POLL_MS)
        except Exception:
            return False
    return False


def download_ieee_assets_with_browser(
    *,
    transport: Any,
    article_id: str,
    output_dir: Path,
    asset_profile: AssetProfile,
    body_assets: list[dict[str, Any]],
    supplementary_assets: list[dict[str, Any]],
    merged_metadata: Mapping[str, Any],
    article_number: str,
    canonical_landing_url: str,
    seed_urls: list[str],
    concurrency: int,
    user_agent: str,
    content: Any,
    browser_runtime_config: BrowserRuntimeConfig,
    runtime_context: RuntimeContext | None,
    download_assets_fn: Callable[..., Any],
    split_assets_fn: Callable[..., Any],
) -> dict[str, list[dict[str, Any]]]:
    from . import _ieee_supplementary as supplementary

    deps = replace(
        default_browser_workflow_deps(),
        download_assets=download_assets_fn,
        split_body_and_supplementary_assets=split_assets_fn,
    )
    shared_page_session = _SharedBrowserPageSession(
        preserve_seed_page=True,
        seed_page_ready_waiter=_ieee_article_seed_page_is_ready,
    )
    previous_shared_page_session = _replace_runtime_shared_page_session(
        runtime_context,
        shared_page_session,
    )
    seed = dict(content.browser_context_seed if content.browser_context_seed else {})
    discovery_failures: list[dict[str, Any]] = []
    if (
        asset_profile == "all"
        and article_number
        and _landing_metadata_has_multimedia_scope(merged_metadata)
    ):
        multimedia_url = IEEE_MULTIMEDIA_URL_TEMPLATE.format(
            article_number=article_number
        )
        discovery_attempt = IeeeLandingAttempt(
            normalized_doi=normalize_doi(article_id),
            landing_url=canonical_landing_url,
            response_url=canonical_landing_url,
            html_text="",
            merged_metadata=dict(merged_metadata),
            article_number=article_number,
            landing_metadata=dict(merged_metadata),
            browser_context_seed=seed,
        )
        discovered_assets = supplementary.fetch_ieee_multimedia_assets(
            transport,
            discovery_attempt,
            multimedia_url=multimedia_url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": canonical_landing_url,
                "User-Agent": user_agent,
                "Origin": IEEE_BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
            runtime_context=runtime_context,
        )
        if not discovered_assets:
            discovery_fetcher = deps._build_shared_browser_file_fetcher(
                browser_context_seed_getter=lambda: seed,
                seed_urls_getter=lambda: seed_urls,
                browser_user_agent=normalize_text(
                    str(seed.get("browser_user_agent") or "")
                )
                or None,
                headless=browser_runtime_config.headless,
                runtime_context=runtime_context,
                use_runtime_shared_browser=True,
                browser_options=BrowserDocumentFetcherOptions(
                    runtime_config=browser_runtime_config
                ),
                thread_local=False,
            )
            try:
                response = discovery_fetcher(
                    multimedia_url, {"referer_url": canonical_landing_url}
                )
                if response:
                    payload = json.loads(
                        decode_html(
                            bytes(response.get("body") or b""),
                            content_type=header_value(
                                response.get("headers"), "content-type"
                            ),
                        )
                    )
                    if isinstance(payload, Mapping):
                        discovered_assets = supplementary._supplementary_assets_from_ieee_multimedia_payload(
                            payload,
                            normalize_text(str(response.get("url") or ""))
                            or multimedia_url,
                        )
            except (TypeError, ValueError):
                discovered_assets = []
            finally:
                discovery_fetcher.close()
            if not discovered_assets:
                failure_for = getattr(discovery_fetcher, "failure_for", None)
                failure = failure_for(multimedia_url) if callable(failure_for) else None
                discovery_failures.append(
                    {
                        "kind": "supplementary",
                        "source_url": multimedia_url,
                        "reason": "multimedia_discovery_failed",
                        "diagnostic": {
                            "stage": "multimedia_discovery",
                            "browser_backend": "camoufox",
                            "browser_attempted": True,
                            **(dict(failure) if isinstance(failure, Mapping) else {}),
                        },
                    }
                )
        if discovered_assets:
            supplementary.cache_ieee_multimedia_assets(
                runtime_context,
                article_number=article_number,
                multimedia_url=multimedia_url,
                assets=discovered_assets,
            )
            existing_keys = {
                supplementary._supplementary_asset_key(existing)
                for existing in supplementary_assets
            }
            supplementary_assets = [
                *supplementary_assets,
                *[
                    asset
                    for asset in discovered_assets
                    if supplementary._supplementary_asset_key(asset)
                    not in existing_keys
                ],
            ]

    if not body_assets and not supplementary_assets:
        _restore_runtime_shared_page_session(
            runtime_context,
            shared_page_session,
            previous_shared_page_session,
        )
        shared_page_session.close()
        return {"assets": [], "asset_failures": discovery_failures}

    plan = BrowserAssetDownloadPlan(
        article_id=article_id,
        output_dir=output_dir,
        asset_profile=asset_profile,
        body_assets=body_assets,
        supplementary_assets=supplementary_assets if asset_profile == "all" else [],
        fetch_policy="direct_then_browser",
        candidate_builder=figure_download_candidates,
    )
    recovery = BrowserAssetRecoveryContext(
        runtime=browser_runtime_config,
        provider="ieee",
        user_agent=user_agent,
        browser_context_seed=seed,
        browser_cookies=list(seed.get("browser_cookies") or []),
        active_seed_urls=seed_urls,
        runtime_context=runtime_context,
    )

    def image_fetcher_factory(**request: Any):
        if not request.get("attempt_body_assets"):
            return None
        memoized_fetcher = _MemoizedImageDocumentFetcher(
            deps._build_shared_browser_image_fetcher(
                browser_context_seed_getter=request["browser_context_seed_getter"],
                seed_urls_getter=request["seed_urls_getter"],
                browser_user_agent=request.get("browser_user_agent"),
                headless=request.get("headless", True),
                runtime_context=runtime_context,
                use_runtime_shared_browser=True,
                browser_options=BrowserDocumentFetcherOptions(
                    runtime_config=request.get("browser_config")
                ),
            )
        )
        memoized_fetcher.browser_backend = "camoufox"
        return _IeeePreviewWarmImageFetcher(memoized_fetcher, shared_page_session)

    def file_fetcher_factory(**request: Any):
        if not request.get("attempt_supplementary_assets"):
            return None
        fetcher = deps._build_shared_browser_file_fetcher(
            browser_context_seed_getter=request["browser_context_seed_getter"],
            seed_urls_getter=request["seed_urls_getter"],
            browser_user_agent=request.get("browser_user_agent"),
            headless=request.get("headless", True),
            runtime_context=runtime_context,
            use_runtime_shared_browser=True,
            browser_options=BrowserDocumentFetcherOptions(
                runtime_config=request.get("browser_config")
            ),
            thread_local=True,
        )
        fetcher.browser_backend = "camoufox"
        return fetcher

    try:
        recovered = download_browser_backed_related_assets(
            plan,
            recovery,
            image_fetcher_factory=image_fetcher_factory,
            file_fetcher_factory=file_fetcher_factory,
            download_settings={
                "transport": transport,
                "asset_download_concurrency": concurrency,
                "serial_browser_assets": True,
            },
            deps=deps,
        )
    finally:
        _restore_runtime_shared_page_session(
            runtime_context,
            shared_page_session,
            previous_shared_page_session,
        )
        shared_page_session.close()
    recovered["asset_failures"] = [
        *list(recovered.get("asset_failures") or []),
        *discovery_failures,
    ]
    return recovered


__all__ = ["download_ieee_assets_with_browser"]
