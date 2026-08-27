from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import mock

from paper_fetch.providers import aip as aip_provider
from paper_fetch.providers import acs, ams, annualreviews, iop, mdpi
from paper_fetch.providers import pnas as pnas_provider
from paper_fetch.providers import royalsocietypublishing, science, tandf, wiley
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
)
from paper_fetch.providers.browser_workflow import bootstrap as bootstrap_module
from paper_fetch.providers.browser_workflow import html_extraction
from paper_fetch.providers.browser_workflow.reuse_cache import (
    BrowserDoiRouteHintCache,
    BrowserPreflightReuseCache,
    mark_browser_preflight_producer,
)
from paper_fetch.providers.browser_workflow.shared import default_browser_workflow_deps
from paper_fetch.runtime import RuntimeContext


def _runtime(provider: str, doi: str, *, headless: bool = True) -> BrowserRuntimeConfig:
    return BrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=Path("/tmp/paper-fetch-reuse-tests"),
        headless=headless,
        user_agent=None,
        backend="camoufox",
        user_data_dir=Path(f"/tmp/paper-fetch-reuse-tests/{provider}"),
        persist_storage_state=True,
    )


def _accepted_html(url: str) -> BrowserFetchedHtml:
    return BrowserFetchedHtml(
        source_url=url,
        final_url=url,
        html="<html><body><article>Accepted browser article</article></body></html>",
        response_status=200,
        response_headers={"content-type": "text/html"},
        title="Accepted article",
        summary="Accepted browser article",
        browser_context_seed={"browser_final_url": url},
        diagnostics={
            "browser_runtime_trace": {
                "navigation_count": 1,
                "storage_state_save": {
                    "attempted": True,
                    "saved": True,
                    "reason": "saved",
                },
            }
        },
    )


def _deps(runtime: BrowserRuntimeConfig, browser_fetch: mock.Mock):
    def extract_markdown(_html, _url, _publisher, *, metadata):
        title = str(metadata.get("title") or "Accepted article")
        return f"# {title}\n\n## Results\n\n" + ("Body text. " * 200), {
            "title": title,
            "availability_diagnostics": {"accepted": True},
        }

    return replace(
        default_browser_workflow_deps(),
        load_runtime_config=mock.Mock(return_value=runtime),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=browser_fetch,
        extract_atypon_browser_workflow_markdown=extract_markdown,
    )


def test_preflight_cache_is_one_shot_ttl_and_runtime_fingerprint_scoped() -> None:
    clock = [10.0]
    cache = BrowserPreflightReuseCache(ttl_seconds=60, timer=lambda: clock[0])
    doi = "10.1073/pnas.2406303121"
    url = f"https://www.pnas.org/doi/{doi}"
    runtime = _runtime("pnas", doi)
    accepted = _accepted_html(url)

    assert cache.store(
        provider="pnas",
        doi=doi,
        target_url=url,
        runtime=runtime,
        result=accepted,
    )
    mismatch, mismatch_diagnostic = cache.consume(
        provider="pnas",
        doi=doi,
        candidate_urls=[url],
        runtime=replace(runtime, headless=False),
    )
    assert mismatch is None
    assert mismatch_diagnostic["reason"] == "runtime_fingerprint_mismatch"

    hit, hit_diagnostic = cache.consume(
        provider="pnas",
        doi=doi,
        candidate_urls=[url],
        runtime=runtime,
    )
    assert hit is not None
    assert hit_diagnostic["state"] == "hit"
    second, _diagnostic = cache.consume(
        provider="pnas",
        doi=doi,
        candidate_urls=[url],
        runtime=runtime,
    )
    assert second is None

    assert cache.store(
        provider="pnas",
        doi=doi,
        target_url=url,
        runtime=runtime,
        result=accepted,
    )
    clock[0] += 61
    expired, expired_diagnostic = cache.consume(
        provider="pnas",
        doi=doi,
        candidate_urls=[url],
        runtime=runtime,
    )
    assert expired is None
    assert expired_diagnostic["reason"] == "not_found_or_expired"


def test_preflight_cache_rejects_failed_or_uncommitted_html() -> None:
    cache = BrowserPreflightReuseCache()
    doi = "10.1073/pnas.2406303121"
    url = f"https://www.pnas.org/doi/{doi}"
    runtime = _runtime("pnas", doi)
    accepted = _accepted_html(url)

    assert not cache.store(
        provider="pnas",
        doi=doi,
        target_url=url,
        runtime=runtime,
        result=replace(accepted, html=""),
    )
    assert not cache.store(
        provider="pnas",
        doi=doi,
        target_url=url,
        runtime=runtime,
        result=replace(accepted, diagnostics={}),
    )
    assert not cache.store(
        provider="pnas",
        doi=doi,
        target_url="https://attacker.example/doi/10.1073/pnas.2406303121",
        runtime=runtime,
        result=accepted,
    )
    assert not cache.store(
        provider="pnas",
        doi=doi,
        target_url="https://www.pnas.org:invalid/doi/10.1073/pnas.2406303121",
        runtime=runtime,
        result=accepted,
    )
    assert not cache.store(
        provider="pnas",
        doi=doi,
        target_url="https://doi.org/10.1073/pnas.different",
        runtime=runtime,
        result=accepted,
    )
    assert len(cache) == 0


def test_preflight_cache_accepts_exact_doi_resolver_target() -> None:
    cache = BrowserPreflightReuseCache()
    doi = "10.1073/pnas.2406303121"
    resolver = f"https://doi.org/{doi}"
    final_url = f"https://www.pnas.org/doi/{doi}"
    runtime = _runtime("pnas", doi)
    accepted = replace(
        _accepted_html(final_url),
        source_url=resolver,
        screenshot_b64="not-reused",
        image_payload={"bodyB64": "not-reused"},
    )

    assert cache.store(
        provider="pnas",
        doi=doi,
        target_url=resolver,
        runtime=runtime,
        result=accepted,
    )
    hit, diagnostic = cache.consume(
        provider="pnas",
        doi=doi,
        candidate_urls=[resolver],
        runtime=runtime,
    )

    assert hit is not None
    assert diagnostic["state"] == "hit"
    assert hit.screenshot_b64 is None
    assert hit.image_payload is None


def test_empty_shell_retry_requires_changed_candidate_profile_or_storage() -> None:
    current_state = {"state_fingerprint": "same", "storage_state_changed": False}
    fast_policy = html_extraction.BrowserHtmlFetchPolicy(
        disable_media=True,
        wait_seconds=0,
        warm_wait_seconds=0,
        max_timeout_ms=15000,
        attempt=1,
    )
    html_result = _accepted_html("https://pubs.acs.org/doi/10.1021/example")

    profile_retry = html_extraction._empty_shell_retry_decision(
        policy=fast_policy,
        html_candidates=[html_result.source_url],
        html_result=html_result,
        page_state=current_state,
        prior_attempts=[],
    )
    identical_stop = html_extraction._empty_shell_retry_decision(
        policy=fast_policy,
        html_candidates=[html_result.source_url],
        html_result=html_result,
        page_state=current_state,
        prior_attempts=[{"page_state": dict(current_state)}],
    )
    candidate_retry = html_extraction._empty_shell_retry_decision(
        policy=replace(fast_policy, disable_media=False),
        html_candidates=[
            html_result.source_url,
            "https://pubs.acs.org/doi/full/10.1021/example",
        ],
        html_result=html_result,
        page_state={"state_fingerprint": "changed", "storage_state_changed": False},
        prior_attempts=[],
    )

    assert profile_retry == {
        "retry": True,
        "reason": "browser_fetch_profile_changed",
        "attempt": 1,
        "candidate_changed": False,
        "profile_changed": True,
        "storage_state_changed": False,
        "identical_page_state": False,
    }
    assert identical_stop["retry"] is False
    assert identical_stop["reason"] == "identical_route_profile_storage_and_page"
    assert candidate_retry["retry"] is True
    assert candidate_retry["reason"] == "candidate_url_changed"


def test_pnas_preflight_then_fetch_reuses_html_without_second_navigation(
    monkeypatch,
) -> None:
    doi = "10.1073/pnas.2406303121"
    canonical = f"https://www.pnas.org/doi/{doi}"
    runtime = _runtime("pnas", doi)
    browser_fetch = mock.Mock(return_value=_accepted_html(canonical))
    deps = _deps(runtime, browser_fetch)
    client = pnas_provider.PnasClient(None, {}, deps=deps)
    reuse_cache = BrowserPreflightReuseCache()
    route_cache = BrowserDoiRouteHintCache()
    monkeypatch.setattr(
        bootstrap_module, "DEFAULT_BROWSER_PREFLIGHT_REUSE_CACHE", reuse_cache
    )
    monkeypatch.setattr(
        html_extraction, "DEFAULT_BROWSER_PREFLIGHT_REUSE_CACHE", reuse_cache
    )
    monkeypatch.setattr(
        bootstrap_module, "DEFAULT_BROWSER_DOI_ROUTE_HINT_CACHE", route_cache
    )
    monkeypatch.setattr(
        html_extraction, "DEFAULT_BROWSER_DOI_ROUTE_HINT_CACHE", route_cache
    )

    preflight_context = RuntimeContext(env={})
    fetch_context = RuntimeContext(env={})
    try:
        mark_browser_preflight_producer(
            preflight_context,
            target_url=f"https://www.pnas.org/doi/full/{doi}",
            save_storage_state=True,
        )
        preflight = bootstrap_module.bootstrap_browser_workflow(
            client,
            doi,
            {
                "doi": doi,
                "title": "Preflight title",
                "landing_page_url": f"https://www.pnas.org/doi/full/{doi}",
            },
            context=preflight_context,
            deps=deps,
        )
        formal = bootstrap_module.bootstrap_browser_workflow(
            client,
            doi,
            {
                "doi": doi,
                "title": "Formal metadata title",
                "landing_page_url": canonical,
            },
            context=fetch_context,
            deps=deps,
        )
    finally:
        preflight_context.close()
        fetch_context.close()

    assert preflight.html_payload is not None
    assert formal.html_payload is not None
    assert browser_fetch.call_count == 1
    assert browser_fetch.call_args.args[0] == [
        canonical,
        f"https://www.pnas.org/doi/full/{doi}",
        f"https://doi.org/{doi}",
    ]
    kwargs = browser_fetch.call_args.kwargs
    assert kwargs["wait_seconds"] == 8
    assert kwargs["options"].readiness_budget_seconds == 8.0
    assert kwargs["options"].blocked_resource_types == frozenset(
        {"image", "font", "media"}
    )
    assert kwargs["readiness"].wait_for_article_body is True
    assert kwargs["readiness"].selector is None
    assert deps.extract_atypon_browser_workflow_markdown is not None
    assert formal.html_payload.content is not None
    assert formal.html_payload.content.markdown_text.startswith(
        "# Formal metadata title"
    )
    assert formal.html_payload.content.diagnostics["preflight_reuse"]["state"] == "hit"
    assert "browser:preflight_reuse_hit" in [
        event.marker() for event in formal.html_payload.trace
    ]


def test_aip_preflight_html_is_not_reused_across_runtime_contexts(monkeypatch) -> None:
    doi = "10.1063/5.0129134"
    url = f"https://pubs.aip.org/doi/full/{doi}"
    runtime = _runtime("aip", doi)
    browser_fetch = mock.Mock(return_value=_accepted_html(url))
    deps = _deps(runtime, browser_fetch)
    client = aip_provider.AipClient(None, {}, deps=deps)
    reuse_cache = BrowserPreflightReuseCache()
    monkeypatch.setattr(
        bootstrap_module, "DEFAULT_BROWSER_PREFLIGHT_REUSE_CACHE", reuse_cache
    )
    monkeypatch.setattr(
        html_extraction, "DEFAULT_BROWSER_PREFLIGHT_REUSE_CACHE", reuse_cache
    )

    first_context = RuntimeContext(env={})
    second_context = RuntimeContext(env={})
    try:
        mark_browser_preflight_producer(
            first_context,
            target_url=url,
            save_storage_state=True,
        )
        first = bootstrap_module.bootstrap_browser_workflow(
            client,
            doi,
            {"doi": doi, "title": "AIP", "landing_page_url": url},
            context=first_context,
            deps=deps,
        )
        second = bootstrap_module.bootstrap_browser_workflow(
            client,
            doi,
            {"doi": doi, "title": "AIP", "landing_page_url": url},
            context=second_context,
            deps=deps,
        )
    finally:
        first_context.close()
        second_context.close()

    assert first.html_payload is not None
    assert second.html_payload is not None
    assert browser_fetch.call_count == 2
    assert all(
        call.kwargs["config"].persist_storage_state is False
        and call.kwargs["config"].profile_dir is None
        and call.kwargs["config"].user_data_dir is None
        and call.kwargs["config"].storage_state_path is None
        for call in browser_fetch.call_args_list
    )
    assert len(reuse_cache) == 0
    assert second.html_payload.content is not None
    assert second.html_payload.content.diagnostics["preflight_reuse"] == {
        "state": "disabled",
        "reason": "provider_runtime_fingerprint_boundary",
    }


def test_doi_route_hint_is_exact_and_rejects_non_provider_hosts() -> None:
    cache = BrowserDoiRouteHintCache()
    first_doi = "10.1073/pnas.2406303121"
    second_doi = "10.1073/pnas.2406303122"
    hint = f"https://www.pnas.org/doi/{first_doi}"

    assert cache.store(provider="pnas", doi=first_doi, url=hint)
    reordered, diagnostic = cache.reorder(
        provider="pnas",
        doi=first_doi,
        candidate_urls=[f"https://doi.org/{first_doi}", hint],
    )
    assert reordered[0] == hint
    assert diagnostic["state"] == "hit"

    unchanged, other_diagnostic = cache.reorder(
        provider="pnas",
        doi=second_doi,
        candidate_urls=[f"https://doi.org/{second_doi}"],
    )
    assert unchanged == [f"https://doi.org/{second_doi}"]
    assert other_diagnostic["state"] == "miss"
    assert not cache.store(
        provider="pnas",
        doi=first_doi,
        url="https://attacker.example/doi/10.1073/pnas.2406303121",
    )
    assert not cache.store(
        provider="pnas",
        doi=first_doi,
        url=f"https://www.pnas.org/doi/abs/{first_doi}",
    )


def test_provider_resource_policies_keep_optimized_and_untouched_boundaries() -> None:
    expected = frozenset({"image", "font", "media"})
    optimized_profiles = (
        pnas_provider.PNAS_BROWSER_PROFILE,
        ams.AMS_BROWSER_PROFILE,
        mdpi.MDPI_BROWSER_PROFILE,
        royalsocietypublishing.ROYAL_SOCIETY_BROWSER_PROFILE,
        annualreviews.ANNUALREVIEWS_BROWSER_PROFILE,
        acs.ACS_BROWSER_PROFILE,
        iop.IOP_BROWSER_PROFILE,
        tandf.TANDF_BROWSER_PROFILE,
        science.SCIENCE_BROWSER_PROFILE,
    )
    assert all(
        profile.blocked_resource_types == expected for profile in optimized_profiles
    )
    assert all(profile.preflight_html_reuse for profile in optimized_profiles)
    assert all(
        profile.direct_figure_page_fallback
        for profile in (
            royalsocietypublishing.ROYAL_SOCIETY_BROWSER_PROFILE,
            annualreviews.ANNUALREVIEWS_BROWSER_PROFILE,
            acs.ACS_BROWSER_PROFILE,
        )
    )
    assert pnas_provider.PNAS_BROWSER_PROFILE.fast_html_attempt is False
    assert pnas_provider.PNAS_BROWSER_PROFILE.html_readiness_budget_seconds == 8.0
    assert pnas_provider.PNAS_BROWSER_PROFILE.doi_route_hint is True
    assert ams.AMS_BROWSER_PROFILE.doi_route_hint is True
    assert science.SCIENCE_BROWSER_PROFILE.direct_figure_page_fallback is False
    assert wiley.WILEY_BROWSER_PROFILE.blocked_resource_types == frozenset()
    assert wiley.WILEY_BROWSER_PROFILE.preflight_html_reuse is True
    assert aip_provider.AIP_BROWSER_PROFILE.blocked_resource_types == frozenset()
    assert aip_provider.AIP_BROWSER_PROFILE.preflight_html_reuse is False
    assert aip_provider.AIP_BROWSER_PROFILE.persistent_storage_state is False
