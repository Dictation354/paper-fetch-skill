"""PNAS provider client."""

from __future__ import annotations

from . import _pnas_html, browser_workflow


PNAS_BROWSER_PROFILE = browser_workflow.ProviderBrowserProfile(
    name="pnas",
    article_source_name=None,
    label="PNAS",
    hosts=_pnas_html.HOSTS,
    base_hosts=_pnas_html.BASE_HOSTS,
    html_path_templates=_pnas_html.HTML_PATH_TEMPLATES,
    pdf_path_templates=_pnas_html.PDF_PATH_TEMPLATES,
    crossref_pdf_position=_pnas_html.CROSSREF_PDF_POSITION,
    markdown_publisher="pnas",
    fallback_author_extractor=_pnas_html.extract_authors,
    shared_playwright_image_fetcher=True,
    direct_playwright_html_preflight=True,
)


class PnasClient(browser_workflow.BrowserWorkflowClient):
    name = PNAS_BROWSER_PROFILE.name
    profile = PNAS_BROWSER_PROFILE
