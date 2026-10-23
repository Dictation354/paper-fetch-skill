"""Replay Oxford HTML through the production provider/model boundary."""

from paper_fetch.http import HttpTransport
from paper_fetch.providers import _oxfordacademic_html
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from paper_fetch.tracing import trace_from_markers


def build_oxford_html_article(html: str, source_url: str, doi: str = ""):
    extraction = _oxfordacademic_html.extract_markdown(
        html, source_url, metadata={"doi": doi}, asset_profile="none"
    )
    payload = RawFulltextPayload(
        provider="oxfordacademic",
        content=ProviderContent(
            route_kind="html",
            route_name="direct_html",
            source_url=source_url,
            content_type="text/html",
            body=extraction.html_text.encode(),
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.metadata,
            extracted_assets=extraction.extracted_assets,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                }
            },
        ),
        trace=trace_from_markers(["fulltext:oxfordacademic_html_ok"]),
    )
    return OxfordAcademicClient(HttpTransport(), {}).to_article_model(
        extraction.metadata, payload
    )
