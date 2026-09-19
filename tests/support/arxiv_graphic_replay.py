"""Offline arXiv graphic extraction/assembly from the seven captured articles."""

from pathlib import Path

from paper_fetch.models import FetchEnvelope
from paper_fetch.providers._arxiv_html import _extract_arxiv_html_markdown
from paper_fetch.providers.arxiv import ArxivClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.golden_criteria import golden_criteria_asset
from tests.support._paper_fetch_support import FixtureHtmlTransport
from tests.support.acquired_publisher_inputs import _record

GRAPHIC_IDS = {
    "1406.2661v1": tuple(f"S3.F1.g{i}" for i in range(1, 5)),
    "2006.11239v2": (
        "S4.F5.pic1",
        "S4.F5.pic2",
        "S4.F5.pic3",
        "A4.F10.pic1",
        "A4.F10.pic2",
    ),
    "2605.06659v1": ("S3.F1.g1",),
    "2605.06663v1": (
        "S1.F1.g1",
        "S3.F2.g1",
        "S5.F3.g1",
        "S5.F4.g1",
        "S5.F5.g1",
        "A1.F7.g1",
        "A1.F8.g1",
        "A1.F9.g1",
        "A1.F10.g1",
        "A2.F11.g1",
        "A2.F12.g1",
        "A2.F13.g1",
    ),
    "2605.06665v1": (
        "S1.F1.g1",
        "S5.SS1.g1",
        "S5.SS1.g2",
        "A3.F4.sf1.g1",
        "A3.F4.sf2.g1",
        "A3.F4.sf3.g1",
        "A3.F4.sf4.g1",
    ),
    "2605.06666v1": ("S0.F3.g1", "S1.F1.g1", "S1.F2.g1"),
    "2605.06667v1": ("S4.F3.g1", "S4.F4.g1"),
}


def graphic_source(arxiv_id: str) -> Path:
    return golden_criteria_asset(
        "10.48550/arxiv." + arxiv_id,
        "acquisition/source-completion-2026-09-18/001-http_response_entity.html",
    )


def graphic_payload(arxiv_id: str):
    record, body = _record(
        "10.48550/arxiv." + arxiv_id,
        "acquisition/source-completion-2026-09-18/001-http_response_entity.html",
    )
    source_url = record["final_url"]
    extracted = _extract_arxiv_html_markdown(
        body.decode(),
        source_url,
        metadata={"doi": "10.48550/arxiv." + arxiv_id, "arxiv_id": arxiv_id},
    )
    payload = RawFulltextPayload(
        provider="arxiv",
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=body,
            markdown_text=extracted.markdown_text,
            merged_metadata=extracted.merged_metadata,
            extracted_assets=extracted.extracted_assets,
            diagnostics={
                "extraction": extracted.diagnostics.get("extraction"),
                "availability_diagnostics": extracted.diagnostics,
            },
        ),
    )
    return ArxivClient(FixtureHtmlTransport({}), {}), extracted, payload


def graphic_article(client, extracted, payload, downloaded_assets=None):
    article = client.to_article_model(
        extracted.merged_metadata,
        payload,
        downloaded_assets=downloaded_assets,
    )
    markdown = article.to_ai_markdown(
        include_refs="all",
        max_tokens="full_text",
        asset_profile="body",
    )
    return article, markdown


def graphic_acceptance(article, markdown, *, require_local):
    return evaluate_fetch_acceptance(
        FetchEnvelope(
            doi=article.doi,
            source=article.source,
            has_fulltext=True,
            article=article,
            markdown=markdown,
        ),
        asset_profile="body",
        require_local_body_assets=require_local,
    )
