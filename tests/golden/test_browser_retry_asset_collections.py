"""Real Wiley and T&F browser captures: original bytes and final article links."""

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
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.browser_workflow.asset_download import (
    plan_browser_asset_download,
)
from tests.support.acquired_article_assets import CLIENTS
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset
from tests.paths import REPO_ROOT
from tests.support._paper_fetch_support import FixtureHtmlTransport
from tests.support.acquired_publisher_inputs import _record, _response


PREFIX = "acquisition/browser-retry-2026-09-16/"


@pytest.mark.parametrize(
    "doi,total,new,prefix",
    [
        ("10.1111/gcb.16414", 6, 6, PREFIX),
        ("10.1029/2004gb002273", 15, 14, PREFIX),
        ("10.1080/15481603.2026.2667034", 9, 8, PREFIX),
        (
            "10.1080/15481603.2026.2667034",
            9,
            8,
            "acquisition/known-gaps-jpeg-2026-09-16/",
        ),
    ],
)
def test_browser_original_images_download_and_article_links(
    doi, total, new, prefix, tmp_path
):
    row = json.loads(golden_criteria_asset(doi, prefix + "collection.json").read_text())
    html = (REPO_ROOT / row["source_input"]).read_bytes()
    assert hashlib.sha256(html).hexdigest() == row["source_sha256"]
    assert len(row["targets"]) == total
    assert row["new_verified_files"] == new
    responses = {}
    for target in row["targets"]:
        record, body = _record(doi, target["record"])
        assert target["state"] == "file_verified"
        assert hashlib.sha256(body).hexdigest() == record["sha256"]
        assert image_mime_type_from_bytes(body).startswith("image/")
        validation = target["validation"]
        assert image_dimensions_from_bytes(body) == (
            validation["width"],
            validation["height"],
        )
        if target["record"].startswith(prefix):
            if row["provider"] == "tandf" and prefix == PREFIX:
                assert record["capture_kind"] == "downloaded_provider_artifact"
                assert record["status_code"] is None
                assert record["final_url"] == target["download_url"]
                assert image_mime_type_from_bytes(body) == "image/png"
            else:
                assert record["capture_kind"] == "http_response_entity"
                assert record["status_code"] == 200
            if row["provider"] == "tandf" and prefix != PREFIX:
                assert image_mime_type_from_bytes(body) == "image/jpeg"
                assert validation["browser_decode"]["different_channels"] == 0
                previous, png = _record(doi, validation["pixel_comparison_record"])
                assert previous["sha256"] == validation["pixel_comparison_sha256"]
                assert image_mime_type_from_bytes(png) == "image/png"
                assert image_dimensions_from_bytes(png) == image_dimensions_from_bytes(
                    body
                )
            assert record["requested_url"] == target["download_url"]
            assert target["download_tier"] == (
                "preview" if target["file_role"] == "formula" else "full_size"
            )
            assert validation["browser_decode"]["nonuniform_pixels"] > 100
        responses[target["download_url"]] = _response(record, body)
        if record["status_code"] is None:
            # Explicit offline envelope for browser pixel exports; provenance
            # keeps the original HTTP status unknown.
            responses[target["download_url"]]["status_code"] = 200
    transport = FixtureHtmlTransport(responses)
    client = CLIENTS[row["provider"]](transport, {})
    metadata = {"doi": doi, "landing_page_url": row["source_url"]}
    markdown, extraction = client.extract_markdown(
        html.decode(), row["source_url"], metadata=metadata
    )
    with RuntimeContext(env={}, transport=transport) as context:
        plan = plan_browser_asset_download(
            article_id=doi,
            output_dir=tmp_path,
            html_text=html.decode(),
            source_url=row["source_url"],
            profile={"client": client, "context": context, "asset_profile": "body"},
            deps=client.deps,
        )
    assert {a["url"] for a in plan.body_assets} == set(responses)
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=doi,
        assets=plan.body_assets,
        output_dir=tmp_path,
        user_agent="offline captured browser replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            candidate_builder=plan.candidate_builder, provider_name=row["provider"]
        ),
    )
    assert not result["asset_failures"]
    assert len(result["assets"]) == total
    for asset in result["assets"]:
        assert asset["download_tier"] == (
            "preview" if asset["kind"] == "formula" else "full_size"
        )
    if doi == "10.1029/2004gb002273":
        formula = next(a for a in plan.body_assets if a["kind"] == "formula")
        assert not formula.get("full_size_url")
        assert formula["url"].endswith("gbc1137-math-0001.gif")
        assert row["new_full_size_files"] == 13
        assert row["new_preview_files"] == 1
    assert {
        hashlib.sha256(Path(a["path"]).read_bytes()).hexdigest()
        for a in result["assets"]
    } == {
        hashlib.sha256(response["body"]).hexdigest() for response in responses.values()
    }
    payload = RawFulltextPayload(
        provider=row["provider"],
        content=ProviderContent(
            route_kind="html",
            source_url=row["source_url"],
            content_type="text/html",
            body=html,
            markdown_text=markdown,
            merged_metadata=metadata,
            diagnostics={"extraction": extraction},
        ),
    )
    article = client.to_article_model(
        metadata, payload, downloaded_assets=result["assets"]
    )
    assert article.doi == doi
    assert article.quality.has_fulltext
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    for asset in result["assets"]:
        assert asset["path"] in rendered
        assert any(a.path == asset["path"] for a in article.assets)
