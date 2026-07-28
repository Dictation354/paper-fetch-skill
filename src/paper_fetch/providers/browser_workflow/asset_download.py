"""Browser workflow asset download planning and retry helpers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any
from collections.abc import Callable, Mapping

from ...extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    extract_scoped_html_assets,
)
from ...extraction.html.assets.download import browser_asset_recovery_allowed
from ...models import AssetProfile
from ...http import RequestCancelledError
from ...utils import dedupe_normalized, empty_asset_results, normalize_text
from ..browser_runtime import (
    BrowserHtmlReadiness,
    BrowserRuntimeFailure,
    merge_browser_context_seeds,
)
from .assets import _download_asset_match_tokens, _merge_download_attempt_results
from .shared import BrowserWorkflowDeps

_FIGURE_PAGE_BROWSER_WAIT_SECONDS = 2
_SILVERCHAIR_FIGURE_PAGE_BROWSER_WAIT_SECONDS = 5
_SILVERCHAIR_FIGURE_PAGE_READY_SELECTOR = (
    "img.content-image[src], img.content-image[data-src]"
)
_SILVERCHAIR_FIGURE_PAGE_PROVIDERS = frozenset({"acs", "royalsocietypublishing"})


@dataclass(frozen=True)
class BrowserAssetDownloadPlan:
    article_id: str
    output_dir: Path
    asset_profile: AssetProfile
    body_assets: list[dict[str, Any]]
    supplementary_assets: list[dict[str, Any]]
    fetch_policy: str = "browser_first"
    candidate_builder: Any | None = None


@dataclass(frozen=True)
class BrowserAssetRecoveryContext:
    runtime: Any
    provider: str
    user_agent: str
    browser_context_seed: Mapping[str, Any]
    browser_cookies: list[dict[str, Any]]
    active_seed_urls: list[str]
    runtime_context: Any | None = None


@dataclass
class BrowserAssetDownloadResult:
    body_results: list[dict[str, Any]]
    supplementary_results: list[dict[str, Any]]
    failures: list[dict[str, Any]]


def plan_browser_asset_download(
    *,
    article_id,
    output_dir,
    html_text,
    source_url,
    profile,
    deps: BrowserWorkflowDeps,
) -> BrowserAssetDownloadPlan:
    asset_profile = _asset_profile_from_plan_profile(profile)
    article_assets = _article_assets_from_plan_profile(
        profile,
        html_text=html_text,
        source_url=source_url,
        asset_profile=asset_profile,
        deps=deps,
    )
    body_assets, supplementary_assets = deps.split_body_and_supplementary_assets(
        article_assets
    )
    return BrowserAssetDownloadPlan(
        article_id=normalize_text(str(article_id or "")),
        output_dir=Path(output_dir),
        asset_profile=asset_profile,
        body_assets=[dict(asset) for asset in body_assets],
        supplementary_assets=[dict(asset) for asset in supplementary_assets],
    )


def run_browser_asset_download_attempt(
    plan: BrowserAssetDownloadPlan,
    recovery: BrowserAssetRecoveryContext,
    *,
    image_fetcher_factory,
    file_fetcher_factory,
    opener_requester,
    deps: BrowserWorkflowDeps,
) -> BrowserAssetDownloadResult:
    _raise_if_cancelled(recovery.runtime_context)
    return _run_browser_asset_download_attempt(
        plan,
        recovery,
        current_seed=recovery.browser_context_seed,
        attempt_body_assets=plan.body_assets,
        attempt_supplementary_assets=plan.supplementary_assets,
        image_fetcher_factory=image_fetcher_factory,
        file_fetcher_factory=file_fetcher_factory,
        opener_requester=opener_requester,
        deps=deps,
    )


def retry_failed_browser_assets(
    plan: BrowserAssetDownloadPlan,
    previous: BrowserAssetDownloadResult,
    recovery: BrowserAssetRecoveryContext,
    *,
    image_fetcher_factory,
    file_fetcher_factory,
    opener_requester,
    deps: BrowserWorkflowDeps,
) -> BrowserAssetDownloadResult:
    _raise_if_cancelled(recovery.runtime_context)
    failed_body_assets = deps._assets_matching_download_failures(
        plan.body_assets,
        previous.failures,
        retry_scope="body",
    )
    failed_supplementary_assets = deps._assets_matching_download_failures(
        plan.supplementary_assets,
        previous.failures,
        retry_scope="supplementary",
    )
    if not failed_body_assets and not failed_supplementary_assets:
        return previous
    if recovery.runtime is None:
        return previous

    _raise_if_cancelled(recovery.runtime_context)
    refreshed_seed = deps.refresh_browser_context_seed(
        _seed_urls_for(recovery, recovery.browser_context_seed),
        publisher=recovery.provider,
        config=recovery.runtime,
        browser_context_seed=recovery.browser_context_seed,
        runtime_context=recovery.runtime_context,
    )
    retry_result = _run_browser_asset_download_attempt(
        plan,
        recovery,
        current_seed=refreshed_seed,
        attempt_body_assets=failed_body_assets,
        attempt_supplementary_assets=failed_supplementary_assets,
        image_fetcher_factory=image_fetcher_factory,
        file_fetcher_factory=file_fetcher_factory,
        opener_requester=opener_requester,
        deps=deps,
    )
    merged = _merge_download_attempt_results(
        _result_mapping(previous),
        _result_mapping(retry_result),
    )
    return _download_result_from_mapping(merged, deps=deps)


def download_browser_backed_related_assets(
    plan: BrowserAssetDownloadPlan,
    recovery: BrowserAssetRecoveryContext,
    *,
    image_fetcher_factory,
    file_fetcher_factory,
    opener_requester,
    deps: BrowserWorkflowDeps,
    refresh_once: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """Run one bounded browser-aware asset attempt and one optional seed refresh."""

    result = run_browser_asset_download_attempt(
        plan,
        recovery,
        image_fetcher_factory=image_fetcher_factory,
        file_fetcher_factory=file_fetcher_factory,
        opener_requester=opener_requester,
        deps=deps,
    )
    recovery_allowed = plan.fetch_policy != "direct_then_browser" or any(
        _asset_failure_allows_browser_recovery(failure) for failure in result.failures
    )
    if refresh_once and result.failures and recovery_allowed:
        result = retry_failed_browser_assets(
            plan,
            result,
            recovery,
            image_fetcher_factory=image_fetcher_factory,
            file_fetcher_factory=file_fetcher_factory,
            opener_requester=opener_requester,
            deps=deps,
        )
    return {
        "assets": [*result.body_results, *result.supplementary_results],
        "asset_failures": result.failures,
    }


def _asset_failure_allows_browser_recovery(failure: Mapping[str, Any]) -> bool:
    diagnostic = failure.get("diagnostic")
    details = diagnostic if isinstance(diagnostic, Mapping) else {}
    status_value = failure.get("status", failure.get("status_code"))
    if status_value is None:
        status_value = details.get("status", details.get("status_code"))
    try:
        status = int(status_value) if status_value is not None else None
    except (TypeError, ValueError):
        status = None
    return browser_asset_recovery_allowed(
        status=status,
        content_type=normalize_text(
            str(failure.get("content_type") or details.get("content_type") or "")
        ),
        reason=normalize_text(
            str(failure.get("reason") or details.get("reason") or "")
        ),
        error_category=normalize_text(
            str(failure.get("error_category") or details.get("error_category") or "")
        ),
    )


def _tier_candidate_builder(
    base_builder: Any, *, preview: bool
) -> Callable[..., list[str]]:
    def build(*args: Any, **kwargs: Any) -> list[str]:
        asset = kwargs.get("asset")
        candidates = list(base_builder(*args, **kwargs))
        if not isinstance(asset, Mapping):
            return candidates
        preview_url = normalize_text(
            str(asset.get("preview_url") or asset.get("url") or "")
        )
        full_size_url = normalize_text(
            str(
                asset.get("download_url")
                or asset.get("full_size_url")
                or asset.get("original_url")
                or ""
            )
        )
        if not preview_url or preview_url == full_size_url:
            return [] if preview else candidates
        if preview:
            return [candidate for candidate in candidates if candidate == preview_url]
        full_candidates = [
            candidate for candidate in candidates if candidate != preview_url
        ]
        return full_candidates or candidates

    return build


def _assets_matching_any_failure(
    assets: list[dict[str, Any]], failures: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    failure_tokens = [_download_asset_match_tokens(failure) for failure in failures]
    return [
        asset
        for asset in assets
        if any(
            _download_asset_match_tokens(asset) & tokens
            for tokens in failure_tokens
            if tokens
        )
    ]


def _annotate_split_browser_recovery(
    result: Mapping[str, Any], direct_failures: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    assets = [dict(asset) for asset in list(result.get("assets") or [])]
    for asset in assets:
        asset_tokens = _download_asset_match_tokens(asset)
        direct_failure = next(
            (
                failure
                for failure in direct_failures
                if asset_tokens & _download_asset_match_tokens(failure)
            ),
            None,
        )
        if direct_failure is None:
            continue
        browser_backend = normalize_text(str(asset.get("browser_backend") or ""))
        final_fetcher = normalize_text(
            str(asset.get("final_fetcher") or browser_backend or "selected_browser")
        )
        asset["recovery_attempts"] = [
            {
                key: value
                for key, value in {
                    "stage": "direct",
                    "status": direct_failure.get("status"),
                    "content_type": direct_failure.get("content_type"),
                    "reason": direct_failure.get("reason"),
                    "error_category": direct_failure.get("error_category"),
                }.items()
                if value not in (None, "")
            },
            {
                key: value
                for key, value in {
                    "stage": "browser",
                    "browser_backend": browser_backend or None,
                    "content_type": asset.get("content_type"),
                    "reason": "recovered",
                    "final_fetcher": final_fetcher,
                }.items()
                if value not in (None, "")
            },
        ]
    return {
        "assets": assets,
        "asset_failures": [
            dict(failure) for failure in list(result.get("asset_failures") or [])
        ],
    }


def _asset_profile_from_plan_profile(profile: Any) -> AssetProfile:
    value: Any
    if isinstance(profile, Mapping):
        value = profile.get("asset_profile", profile.get("profile", "all"))
    else:
        value = getattr(profile, "asset_profile", None)
        if value is None:
            value = profile
    if value not in {"none", "body", "all"}:
        return "all"
    return value


def _article_assets_from_plan_profile(
    profile: Any,
    *,
    html_text: str,
    source_url: str,
    asset_profile: AssetProfile,
    deps: BrowserWorkflowDeps,
) -> list[dict[str, Any]]:
    if isinstance(profile, Mapping):
        if "assets" in profile:
            return [dict(asset) for asset in list(profile.get("assets") or [])]
        client = profile.get("client")
        context = profile.get("context")
    else:
        assets = getattr(profile, "assets", None)
        if assets is not None:
            return [dict(asset) for asset in list(assets or [])]
        client = getattr(profile, "client", None)
        context = getattr(profile, "context", None)

    if client is not None and context is not None:
        return deps._cached_browser_workflow_assets(
            client,
            html_text,
            source_url,
            asset_profile=asset_profile,
            context=context,
        )
    return extract_scoped_html_assets(
        html_text,
        source_url,
        asset_profile=asset_profile,
    )


def _run_browser_asset_download_attempt(
    plan: BrowserAssetDownloadPlan,
    recovery: BrowserAssetRecoveryContext,
    *,
    current_seed: Mapping[str, Any],
    attempt_body_assets: list[dict[str, Any]],
    attempt_supplementary_assets: list[dict[str, Any]],
    image_fetcher_factory,
    file_fetcher_factory,
    opener_requester,
    deps: BrowserWorkflowDeps,
) -> BrowserAssetDownloadResult:
    _raise_if_cancelled(recovery.runtime_context)
    attempt_seed = merge_browser_context_seeds(
        {"browser_cookies": recovery.browser_cookies},
        current_seed,
    )
    attempt_seed_lock = threading.Lock()
    attempt_settings = _attempt_settings(opener_requester)

    def attempt_seed_snapshot() -> dict[str, Any]:
        with attempt_seed_lock:
            return merge_browser_context_seeds(attempt_seed)

    def raw_figure_page_fetcher(figure_page_url: str) -> tuple[str, str] | None:
        if recovery.runtime is None:
            return None
        provider = normalize_text(recovery.provider).lower()
        wait_for_selector = (
            _SILVERCHAIR_FIGURE_PAGE_READY_SELECTOR
            if provider in _SILVERCHAIR_FIGURE_PAGE_PROVIDERS
            else None
        )
        try:
            html_result = deps.fetch_html_with_browser(
                [figure_page_url],
                publisher=recovery.provider,
                config=recovery.runtime,
                readiness=BrowserHtmlReadiness(
                    wait_for_article_body=False,
                    selector=wait_for_selector,
                ),
                wait_seconds=(
                    _SILVERCHAIR_FIGURE_PAGE_BROWSER_WAIT_SECONDS
                    if wait_for_selector
                    else _FIGURE_PAGE_BROWSER_WAIT_SECONDS
                ),
                runtime_context=recovery.runtime_context,
            )
        except BrowserRuntimeFailure:
            return None
        with attempt_seed_lock:
            attempt_seed.update(
                merge_browser_context_seeds(
                    attempt_seed, html_result.browser_context_seed
                )
            )
        return html_result.html, html_result.final_url

    figure_page_fetcher_factory = attempt_settings.get("figure_page_fetcher_factory")
    figure_page_fetcher = (
        figure_page_fetcher_factory(raw_figure_page_fetcher)
        if callable(figure_page_fetcher_factory)
        else raw_figure_page_fetcher
    )

    def seed_urls_getter() -> list[str]:
        return _seed_urls_for(recovery, attempt_seed_snapshot())

    def seeded_asset_headers(seed_snapshot: Mapping[str, Any]) -> dict[str, str]:
        seed_urls = _seed_urls_for(recovery, seed_snapshot)
        referer = normalize_text(str(seed_snapshot.get("browser_final_url") or ""))
        if not referer and seed_urls:
            referer = seed_urls[-1]
        return {"Referer": referer} if referer else {}

    def seeded_asset_user_agent(seed_snapshot: Mapping[str, Any]) -> str:
        if recovery.runtime is not None and recovery.runtime.backend == "camoufox":
            return normalize_text(
                str(seed_snapshot.get("browser_user_agent") or "")
            ) or normalize_text(recovery.user_agent)
        return recovery.user_agent

    image_document_fetcher = _build_attempt_document_fetcher(
        recovery,
        attempt_seed=attempt_seed,
        assets=attempt_body_assets,
        assets_kwarg="attempt_body_assets",
        seed_urls_getter=seed_urls_getter,
        fetcher_factory=image_fetcher_factory,
    )
    file_document_fetcher = _build_attempt_document_fetcher(
        recovery,
        attempt_seed=attempt_seed,
        assets=attempt_supplementary_assets,
        assets_kwarg="attempt_supplementary_assets",
        seed_urls_getter=seed_urls_getter,
        fetcher_factory=file_fetcher_factory,
    )
    try:

        def download_body_assets() -> Mapping[str, Any]:
            _raise_if_cancelled(recovery.runtime_context)
            if not attempt_body_assets:
                return empty_asset_results()
            seed_snapshot = attempt_seed_snapshot()
            base_candidate_builder = (
                plan.candidate_builder
                or deps._browser_workflow_image_download_candidates
            )
            common_kwargs = {
                "article_id": plan.article_id,
                "output_dir": plan.output_dir,
                "user_agent": seeded_asset_user_agent(seed_snapshot),
                "asset_profile": plan.asset_profile,
                "headers": seeded_asset_headers(seed_snapshot),
                "browser_context_seed": seed_snapshot,
                "seed_urls": _seed_urls_for(recovery, seed_snapshot),
                "figure_page_fetcher": figure_page_fetcher,
            }
            if plan.fetch_policy != "direct_then_browser" or not serial_browser_assets:
                return deps.download_assets(
                    FIGURE_KIND,
                    attempt_settings.get("transport"),
                    assets=attempt_body_assets,
                    candidate_builder=base_candidate_builder,
                    image_document_fetcher=image_document_fetcher,
                    asset_download_concurrency=attempt_settings.get(
                        "asset_download_concurrency"
                    ),
                    fetch_policy=plan.fetch_policy,
                    **common_kwargs,
                )

            full_candidate_builder = _tier_candidate_builder(
                base_candidate_builder, preview=False
            )
            direct_result = deps.download_assets(
                FIGURE_KIND,
                attempt_settings.get("transport"),
                assets=attempt_body_assets,
                candidate_builder=full_candidate_builder,
                image_document_fetcher=None,
                asset_download_concurrency=attempt_settings.get(
                    "asset_download_concurrency"
                ),
                fetch_policy="direct_then_browser",
                **common_kwargs,
            )
            eligible_failures = [
                dict(failure)
                for failure in list(direct_result.get("asset_failures") or [])
                if _asset_failure_allows_browser_recovery(failure)
            ]
            browser_assets = deps._assets_matching_download_failures(
                attempt_body_assets,
                eligible_failures,
                retry_scope="body",
            )
            merged_result = dict(direct_result)
            if browser_assets:
                browser_result = deps.download_assets(
                    FIGURE_KIND,
                    attempt_settings.get("transport"),
                    assets=browser_assets,
                    candidate_builder=full_candidate_builder,
                    image_document_fetcher=image_document_fetcher,
                    asset_download_concurrency=1,
                    fetch_policy="browser_first",
                    **common_kwargs,
                )
                browser_result = _annotate_split_browser_recovery(
                    browser_result, eligible_failures
                )
                merged_result = _merge_download_attempt_results(
                    direct_result, browser_result
                )

            preview_assets = [
                asset
                for asset in _assets_matching_any_failure(
                    attempt_body_assets,
                    [
                        dict(failure)
                        for failure in list(merged_result.get("asset_failures") or [])
                    ],
                )
                if normalize_text(
                    str(asset.get("preview_url") or asset.get("url") or "")
                )
            ]
            if not preview_assets:
                return merged_result
            preview_result = deps.download_assets(
                FIGURE_KIND,
                attempt_settings.get("transport"),
                assets=preview_assets,
                candidate_builder=_tier_candidate_builder(
                    base_candidate_builder, preview=True
                ),
                image_document_fetcher=image_document_fetcher,
                asset_download_concurrency=1,
                fetch_policy="direct_then_browser",
                **common_kwargs,
            )
            return _merge_download_attempt_results(merged_result, preview_result)

        def download_supplementary_assets() -> Mapping[str, Any]:
            _raise_if_cancelled(recovery.runtime_context)
            if not attempt_supplementary_assets:
                return empty_asset_results()
            supplementary_kwargs: dict[str, Any] = {}
            if callable(attempt_settings.get("cookie_opener_builder")):
                supplementary_kwargs["cookie_opener_builder"] = attempt_settings[
                    "cookie_opener_builder"
                ]
            if callable(attempt_settings.get("opener_requester")):
                supplementary_kwargs["opener_requester"] = attempt_settings[
                    "opener_requester"
                ]
            seed_snapshot = attempt_seed_snapshot()
            common_kwargs = {
                "article_id": plan.article_id,
                "output_dir": plan.output_dir,
                "user_agent": seeded_asset_user_agent(seed_snapshot),
                "asset_profile": plan.asset_profile,
                "headers": seeded_asset_headers(seed_snapshot),
                "browser_context_seed": seed_snapshot,
                "seed_urls": _seed_urls_for(recovery, seed_snapshot),
                **supplementary_kwargs,
            }
            if plan.fetch_policy != "direct_then_browser" or not serial_browser_assets:
                return deps.download_assets(
                    SUPPLEMENTARY_KIND,
                    attempt_settings.get("transport"),
                    assets=attempt_supplementary_assets,
                    file_document_fetcher=file_document_fetcher,
                    asset_download_concurrency=attempt_settings.get(
                        "asset_download_concurrency"
                    ),
                    fetch_policy=plan.fetch_policy,
                    **common_kwargs,
                )

            direct_result = deps.download_assets(
                SUPPLEMENTARY_KIND,
                attempt_settings.get("transport"),
                assets=attempt_supplementary_assets,
                file_document_fetcher=None,
                asset_download_concurrency=attempt_settings.get(
                    "asset_download_concurrency"
                ),
                fetch_policy="direct_then_browser",
                **common_kwargs,
            )
            eligible_failures = [
                dict(failure)
                for failure in list(direct_result.get("asset_failures") or [])
                if _asset_failure_allows_browser_recovery(failure)
            ]
            browser_assets = deps._assets_matching_download_failures(
                attempt_supplementary_assets,
                eligible_failures,
                retry_scope="supplementary",
            )
            if not browser_assets:
                return direct_result
            browser_result = deps.download_assets(
                SUPPLEMENTARY_KIND,
                attempt_settings.get("transport"),
                assets=browser_assets,
                file_document_fetcher=file_document_fetcher,
                asset_download_concurrency=1,
                fetch_policy="browser_first",
                **common_kwargs,
            )
            browser_result = _annotate_split_browser_recovery(
                browser_result, eligible_failures
            )
            return _merge_download_attempt_results(direct_result, browser_result)

        serial_browser_assets = bool(
            attempt_settings.get("serial_browser_assets")
            or _requires_caller_thread(image_document_fetcher)
            or _requires_caller_thread(file_document_fetcher)
        )
        if (
            attempt_body_assets
            and attempt_supplementary_assets
            and not serial_browser_assets
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                body_future = executor.submit(download_body_assets)
                supplementary_future = executor.submit(download_supplementary_assets)
                body_result = body_future.result()
                supplementary_result = supplementary_future.result()
        else:
            body_result = download_body_assets()
            supplementary_result = download_supplementary_assets()
        return BrowserAssetDownloadResult(
            body_results=[
                dict(asset) for asset in list(body_result.get("assets") or [])
            ],
            supplementary_results=[
                dict(asset) for asset in list(supplementary_result.get("assets") or [])
            ],
            failures=[
                *[
                    dict(failure)
                    for failure in list(body_result.get("asset_failures") or [])
                ],
                *[
                    dict(failure)
                    for failure in list(
                        supplementary_result.get("asset_failures") or []
                    )
                ],
            ],
        )
    finally:
        for fetcher in (image_document_fetcher, file_document_fetcher):
            close_fetcher = getattr(fetcher, "close", None)
            if callable(close_fetcher):
                close_fetcher()


def _raise_if_cancelled(runtime_context: Any | None) -> None:
    cancel_check = getattr(runtime_context, "cancel_check", None)
    if callable(cancel_check) and cancel_check() is True:
        raise RequestCancelledError("Request cancelled.")


def _build_attempt_document_fetcher(
    recovery: BrowserAssetRecoveryContext,
    *,
    attempt_seed: dict[str, Any],
    assets: list[dict[str, Any]],
    assets_kwarg: str,
    seed_urls_getter: Callable[[], list[str]],
    fetcher_factory,
) -> Callable[[str, Mapping[str, Any]], dict[str, Any] | None] | None:
    if not assets or not callable(fetcher_factory):
        return None
    return fetcher_factory(
        **{assets_kwarg: assets},
        browser_context_seed_getter=lambda: attempt_seed,
        seed_urls_getter=seed_urls_getter,
        browser_user_agent=attempt_seed.get("browser_user_agent")
        or getattr(recovery.runtime, "user_agent", None),
        headless=getattr(recovery.runtime, "headless", True),
        binary_path=getattr(recovery.runtime, "binary_path", None),
        cdp_endpoint=getattr(recovery.runtime, "cdp_endpoint", None),
        profile_dir=getattr(recovery.runtime, "profile_dir", None),
        user_data_dir=getattr(recovery.runtime, "user_data_dir", None),
        browser_config=recovery.runtime,
    )


def _requires_caller_thread(fetcher: Any) -> bool:
    return bool(getattr(fetcher, "requires_caller_thread", False))


def _seed_urls_for(
    recovery: BrowserAssetRecoveryContext,
    current_seed: Mapping[str, Any],
) -> list[str]:
    return dedupe_normalized(
        [
            *recovery.active_seed_urls,
            normalize_text(str(current_seed.get("browser_final_url") or "")),
        ]
    )


def _attempt_settings(opener_requester: Any) -> dict[str, Any]:
    if isinstance(opener_requester, Mapping):
        return dict(opener_requester)
    settings: dict[str, Any] = {}
    if callable(opener_requester):
        settings["opener_requester"] = opener_requester
    for name in (
        "transport",
        "asset_download_concurrency",
        "figure_page_fetcher_factory",
        "cookie_opener_builder",
    ):
        value = getattr(opener_requester, name, None)
        if value is not None:
            settings[name] = value
    return settings


def _result_mapping(
    result: BrowserAssetDownloadResult,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "assets": [
            *[dict(asset) for asset in result.body_results],
            *[dict(asset) for asset in result.supplementary_results],
        ],
        "asset_failures": [dict(failure) for failure in result.failures],
    }


def _download_result_from_mapping(
    result: Mapping[str, Any],
    *,
    deps: BrowserWorkflowDeps,
) -> BrowserAssetDownloadResult:
    body_results, supplementary_results = deps.split_body_and_supplementary_assets(
        [dict(asset) for asset in list(result.get("assets") or [])]
    )
    return BrowserAssetDownloadResult(
        body_results=body_results,
        supplementary_results=supplementary_results,
        failures=[
            dict(failure) for failure in list(result.get("asset_failures") or [])
        ],
    )
