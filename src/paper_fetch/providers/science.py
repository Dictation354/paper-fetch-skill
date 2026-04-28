"""Science provider client."""

from __future__ import annotations

from . import _science_html, browser_workflow


SCIENCE_BROWSER_PROFILE = browser_workflow.ProviderBrowserProfile(
    name="science",
    article_source_name=None,
    label="Science",
    hosts=_science_html.HOSTS,
    base_hosts=_science_html.BASE_HOSTS,
    html_path_templates=_science_html.HTML_PATH_TEMPLATES,
    pdf_path_templates=_science_html.PDF_PATH_TEMPLATES,
    crossref_pdf_position=_science_html.CROSSREF_PDF_POSITION,
    markdown_publisher="science",
    fallback_author_extractor=_science_html.extract_authors,
    shared_playwright_image_fetcher=True,
)


class ScienceClient(browser_workflow.BrowserWorkflowClient):
    name = SCIENCE_BROWSER_PROFILE.name
    profile = SCIENCE_BROWSER_PROFILE
