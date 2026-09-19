"""Local contracts exposed by full source replays, without replay in unit."""

import pytest
from paper_fetch.providers._ieee_metadata import build_ieee_article_model
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.quality.access_boundary import html_paywall_diagnostics


def test_ieee_pdf_preserves_opaque_converter_whitespace():
    raw = "\n\n## Unmodified converter output\n\n" + "Body text. " * 200 + " \n\n"
    metadata = {"doi": "10.1109/example", "title": "Converter contract"}
    article = build_ieee_article_model(
        metadata,
        RawFulltextPayload(
            provider="ieee",
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url="https://example.org/article.pdf",
                content_type="application/pdf",
                body=b"%PDF-",
                markdown_text=raw,
                merged_metadata=metadata,
            ),
        ),
    )
    assert article.sections[0].text == raw
    assert raw in article.to_ai_markdown(max_tokens="full_text")


@pytest.mark.parametrize("active", ["false", "true"])
def test_science_collateral_access_message_respects_active_pane(active):
    doi = "10.1126/science.adz3492"
    html = f'''<meta name="citation_doi" content="{doi}">
    <div id="core-collateral-fulltext-options" data-active-pane="{active}">
    <h4>Log in to view the full text</h4><div class="seamlessAccessDenial"></div></div>'''
    diagnostics = html_paywall_diagnostics(
        html, metadata={"doi": doi}, provider="science"
    )
    assert bool(diagnostics.get("confirmed_article_paywall")) == (active == "true")
