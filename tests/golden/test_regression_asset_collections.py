"""New real collections: source discovery, provider download and article links."""

import hashlib
import json
from pathlib import Path

import pytest

from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.extraction.image_payloads import (
    image_dimensions_from_bytes,
    image_mime_type_from_bytes,
)
from paper_fetch.providers import frontiers, ieee, _ieee_html
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support._paper_fetch_support import FixtureHtmlTransport


PREFIX = "acquisition/regression-2026-09-16/"


@pytest.mark.parametrize(
    "doi,count", [("10.3389/fpls.2020.01216", 5), ("10.1109/ACCESS.2024.3352924", 23)]
)
def test_real_collection_provider_download_and_final_article_links(
    doi, count, tmp_path
):
    row = json.loads(golden_criteria_asset(doi, PREFIX + "collection.json").read_text())
    records = json.loads(
        golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
    )["records"]
    responses = {}
    for r in records:
        if not r.get("requested_url") or r.get("status_code") != 200:
            continue
        responses[r["requested_url"]] = _response(
            r, golden_criteria_asset(doi, r["body_file"]).read_bytes()
        )
        if r.get("final_url"):
            responses[r["final_url"]] = responses[r["requested_url"]]
    assert len(row["targets"]) == count
    for t in row["targets"]:
        r, b = _record(doi, t["record"])
        responses[t["download_url"]] = _response(r, b)
        assert image_mime_type_from_bytes(b).startswith("image/")
        assert image_dimensions_from_bytes(b) == (
            t["validation"]["width"],
            t["validation"]["height"],
        )
        if PREFIX in t["record"]:
            assert r["status_code"] == 200
            assert t["validation"]["browser_decode"]["nonuniform_pixels"] > 100
            assert t["validation"]["sha256"] == hashlib.sha256(b).hexdigest()
            assert t["download_tier"] == "full_size"
    transport = FixtureHtmlTransport(responses)
    metadata = {"doi": doi, "landing_page_url": row["source_url"]}
    if row["provider"] == "frontiers":
        client = frontiers.FrontiersClient(transport, {})
        routes = client.route_candidates(doi, {})
        route = next(r for r in routes if r.xml_url == row["source_url"])
        payload = client._fetch_xml_payload(route, doi, metadata)
        with RuntimeContext(env={}, transport=transport) as context:
            result = client.download_related_assets(
                doi, metadata, payload, tmp_path, asset_profile="body", context=context
            )
        # DOI suffix 01216 is not the publisher's internal article id 569407.
        assert all("/Articles/01216/" not in c["url"] for c in transport.calls)
        assert "/Articles/01216/" not in payload.content.markdown_text
        assert all("/Articles/569407/" in a["download_url"] for a in result["assets"])
    else:
        source = Path(row["source_input"]).read_text()
        extraction = _ieee_html._extract_ieee_html(
            source, row["source_url"], metadata=metadata
        )
        client = ieee.IeeeClient(transport, {})
        selected = [
            a for a in extraction.extracted_assets if a["kind"] in {"figure", "table"}
        ]
        assert {a["url"] for a in selected} == {
            t["download_url"] for t in row["targets"]
        }
        result = download_assets(
            FIGURE_KIND,
            transport,
            article_id=doi,
            assets=selected,
            output_dir=tmp_path,
            user_agent="offline replay",
            asset_profile="body",
            options=AssetDownloadOptions(provider_name="ieee"),
        )
        payload = RawFulltextPayload(
            provider="ieee",
            content=ProviderContent(
                route_kind="html",
                source_url=row["source_url"],
                body=source.encode(),
                content_type="text/html",
                markdown_text=extraction.markdown_text,
                merged_metadata=metadata,
                extracted_assets=extraction.extracted_assets,
            ),
        )
    assert not result["asset_failures"]
    assert len(result["assets"]) == count
    expected_hashes = {
        t["validation"].get("sha256")
        or hashlib.sha256(
            golden_criteria_asset(doi, t["record"]).read_bytes()
        ).hexdigest()
        for t in row["targets"]
    }
    assert {
        hashlib.sha256(Path(a["path"]).read_bytes()).hexdigest()
        for a in result["assets"]
    } == expected_hashes
    article = client.to_article_model(
        metadata, payload, downloaded_assets=result["assets"]
    )
    assert article.quality.has_fulltext
    assert article.doi == doi.lower()
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    for a in result["assets"]:
        assert rendered.count(a["path"]) == 1
        assert any(x.path == a["path"] for x in article.assets)
