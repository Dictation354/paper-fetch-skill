from __future__ import annotations

from paper_fetch.providers import browser_workflow
from paper_fetch.providers.browser_workflow import fetchers, html_extraction, shared


def test_browser_workflow_namespace_reexports_core_helpers() -> None:
    assert (
        browser_workflow.build_browser_workflow_html_candidates
        is shared.build_browser_workflow_html_candidates
    )
    assert (
        browser_workflow._cached_browser_workflow_markdown
        is html_extraction._cached_browser_workflow_markdown
    )
    assert (
        browser_workflow._build_shared_browser_image_fetcher
        is fetchers._build_shared_browser_image_fetcher
    )


def test_browser_workflow_namespace_uses_canonical_child_modules() -> None:
    assert (
        shared.build_browser_workflow_pdf_candidates
        is browser_workflow.build_browser_workflow_pdf_candidates
    )
    assert (
        fetchers._choose_browser_seed_url is browser_workflow._choose_browser_seed_url
    )
