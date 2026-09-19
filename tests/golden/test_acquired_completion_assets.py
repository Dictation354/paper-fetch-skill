"""Captured object/Silverchair images through their provider-owned asset routes."""

from dataclasses import replace
from pathlib import Path
from paper_fetch.providers import elsevier, oxfordacademic
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._paper_fetch_support import FixtureHtmlTransport
from tests.support.acquired_publisher_inputs import _record, _response


def test_elsevier_original_xml_object_download_and_final_article(tmp_path):
    doi = "10.1016/j.envres.2018.12.059"
    record, body = _record(doi, "acquisition/figure-1-2026-09-15.jpg")
    xml = golden_criteria_asset(doi, "original.xml").read_bytes()
    references = elsevier.extract_elsevier_asset_references(xml)
    target = next(r for r in references if r["source_ref"] == "gr1")
    assert target["source_url"] == record["requested_url"]
    transport = FixtureHtmlTransport({record["requested_url"]: _response(record, body)})
    # Other object responses are injected as unavailable; only gr1 was captured.
    result = elsevier.download_elsevier_related_assets(
        transport,
        doi=doi,
        xml_body=xml,
        output_dir=tmp_path,
        headers={"X-ELS-APIKey": "offline-placeholder"},
        asset_profile="body",
        asset_download_concurrency=1,
    )
    downloaded = next(a for a in result["assets"] if a.get("source_ref") == "gr1")
    assert Path(downloaded["path"]).read_bytes() == body
    metadata = {
        "doi": doi,
        "title": "New approach to identifying proper thresholds for a heat warning system using health risk increments",
    }
    payload = RawFulltextPayload(
        provider="elsevier",
        content=ProviderContent(
            route_kind="xml",
            source_url=golden_criteria_sample_for_doi(doi)["source_url"],
            content_type="text/xml",
            body=xml,
            merged_metadata=metadata,
        ),
    )
    article = elsevier.ElsevierClient(transport, {}).to_article_model(
        metadata, payload, downloaded_assets=result["assets"]
    )
    rendered = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="body"
    )
    assert article.quality.has_fulltext
    assert downloaded["path"] in rendered
    assert "Fig. 1" in rendered
    assert "health risk increments" in rendered


def test_oxford_fresh_signed_figure_current_discovery_download_and_article(tmp_path):
    doi = "10.1093/bioinformatics/btaa823"
    page_record, page = _record(doi, "acquisition/article-2026-09-15.html")
    record, body = _record(doi, "acquisition/figure-1-2026-09-15.jpg")
    assert record["source_input"] == "acquisition/article-2026-09-15.html"
    transport = FixtureHtmlTransport(
        {
            page_record["requested_url"]: _response(page_record, page),
            record["requested_url"]: _response(record, body),
        }
    )
    client = oxfordacademic.OxfordAcademicClient(transport, {})
    metadata = {"doi": doi, "landing_page_url": page_record["requested_url"]}
    payload = client.fetch_raw_fulltext(doi, metadata)
    selected = [
        a
        for a in payload.content.extracted_assets
        if record["requested_url"] in a.values()
    ]
    assert len(selected) == 1
    # Explicit one-figure scope for this replay; the article body stays complete.
    payload = replace(
        payload, content=replace(payload.content, extracted_assets=selected)
    )
    with RuntimeContext(env={}, transport=transport) as context:
        result = client.download_related_assets(
            doi, metadata, payload, tmp_path, asset_profile="body", context=context
        )
    assert len(result["assets"]) == 1
    assert not result["asset_failures"]
    downloaded = result["assets"][0]
    assert Path(downloaded["path"]).read_bytes() == body
    article = client.to_article_model(
        metadata, payload, downloaded_assets=result["assets"]
    )
    rendered = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="body"
    )
    assert article.quality.has_fulltext
    assert downloaded["path"] in rendered
    assert "Fig. 1" in rendered
    assert article.assets[0].caption
