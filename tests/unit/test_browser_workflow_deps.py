from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.providers import _pdf_fallback, browser_runtime
from paper_fetch.providers.atypon_browser_workflow import (
    extract_atypon_browser_workflow_markdown,
)
from paper_fetch.providers.browser_workflow import assets, bootstrap, fetchers
from paper_fetch.providers.browser_workflow import html_extraction, pdf_fallback
from paper_fetch.providers.browser_workflow.shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
)


def test_default_browser_workflow_deps_match_production_functions() -> None:
    deps = default_browser_workflow_deps()

    assert isinstance(deps, BrowserWorkflowDeps)
    assert deps.load_runtime_config is browser_runtime.load_runtime_config
    assert deps.ensure_runtime_ready is browser_runtime.ensure_runtime_ready
    assert deps.probe_runtime_status is browser_runtime.probe_runtime_status
    assert deps.fetch_html_with_browser is browser_runtime.fetch_html_with_browser
    assert deps.warm_browser_context is browser_runtime.warm_browser_context
    assert (
        deps.fetch_seeded_browser_pdf_payload
        is pdf_fallback.fetch_seeded_browser_pdf_payload
    )
    assert deps.fetch_pdf_with_browser is _pdf_fallback.fetch_pdf_with_playwright
    assert deps.download_assets is html_assets.download_assets
    assert (
        deps.split_body_and_supplementary_assets
        is html_assets.split_body_and_supplementary_assets
    )
    assert deps.bootstrap_browser_workflow is bootstrap.bootstrap_browser_workflow
    assert (
        deps._build_shared_browser_file_fetcher
        is fetchers._build_shared_browser_file_fetcher
    )
    assert (
        deps._build_shared_browser_image_fetcher
        is fetchers._build_shared_browser_image_fetcher
    )
    assert (
        deps.extract_atypon_browser_workflow_markdown
        is extract_atypon_browser_workflow_markdown
    )
    assert deps.pdf_browser_context_seed is browser_runtime.warm_browser_context
    assert deps.refresh_browser_context_seed is browser_runtime.warm_browser_context
    assert (
        deps._cached_browser_workflow_markdown
        is html_extraction._cached_browser_workflow_markdown
    )
    assert (
        deps._cached_browser_workflow_assets is assets._cached_browser_workflow_assets
    )
    assert (
        deps._assets_matching_download_failures
        is assets._assets_matching_download_failures
    )
    assert (
        deps._browser_workflow_image_download_candidates
        is assets._browser_workflow_image_download_candidates
    )


def test_browser_workflow_deps_replace_round_trip_and_freezes_fields() -> None:
    deps = default_browser_workflow_deps()
    sentinel = object()

    updated = replace(deps, load_runtime_config=sentinel)

    assert updated.load_runtime_config is sentinel
    assert deps.load_runtime_config is browser_runtime.load_runtime_config
    with pytest.raises(FrozenInstanceError):
        updated.load_runtime_config = deps.load_runtime_config  # type: ignore[misc]


def test_browser_workflow_deps_group_views_reference_flat_fields() -> None:
    deps = default_browser_workflow_deps()

    assert deps.runtime.load_runtime_config is deps.load_runtime_config
    assert deps.runtime.fetch_html_with_browser is deps.fetch_html_with_browser
    assert deps.html.bootstrap_browser_workflow is deps.bootstrap_browser_workflow
    assert deps.pdf.fetch_pdf_with_browser is deps.fetch_pdf_with_browser
    assert deps.assets.download_assets is deps.download_assets
    assert (
        deps.cache._cached_browser_workflow_assets
        is deps._cached_browser_workflow_assets
    )
