"""Historical signed bodies with separately captured publisher image bytes."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.models import FetchEnvelope
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._paper_fetch_support import FixtureHtmlTransport
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support.signed_image_replay import extract_signed_fixture_payload
from tests.paths import REPO_ROOT


@pytest.mark.parametrize(
    "provider,doi,count",
    [
        ("acs", "10.1021/acsomega.3c06992", 8),
        ("oxfordacademic", "10.1093/bioinformatics/btaa823", 9),
        ("royalsocietypublishing", "10.1098/rsif.2019.0334", 5),
    ],
)
def test_historical_body_uses_captured_current_assets(provider, doi, count, tmp_path):
    sample = golden_criteria_sample_for_doi(doi)
    row = {"provider": provider, "doi": doi, "source_url": sample["source_url"]}
    provenance = json.loads(
        golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
    )
    captures = []
    for record in provenance["records"]:
        if "assets-2026-09-15/" not in record.get(
            "original_body_file", record["body_file"]
        ):
            continue
        url = record["requested_url"]
        if ".silverchair-cdn.com/" not in url or Path(
            urlsplit(url).path
        ).name.startswith("m_"):
            continue
        captures.append(
            _record(doi, record.get("original_body_file", record["body_file"]))
        )
    assert len(captures) == count
    transport = FixtureHtmlTransport(
        {record["requested_url"]: _response(record, body) for record, body in captures}
    )
    source = REPO_ROOT / captures[0][0]["source_input"]
    assert all(
        record["source_input"] == str(source.relative_to(REPO_ROOT))
        for record, _ in captures
    )
    _, _, _, fresh_assets, candidate_builder = extract_signed_fixture_payload(
        row, source, transport, tmp_path
    )
    urls = {r["requested_url"] for r, _ in captures}
    selected = [
        a
        for a in fresh_assets
        if urls.intersection(v for v in a.values() if isinstance(v, str))
    ]
    assert len(selected) == count
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=doi,
        assets=selected,
        output_dir=tmp_path,
        user_agent="offline captured replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            candidate_builder=candidate_builder,
            provider_name=provider,
            asset_download_concurrency=1,
        ),
    )
    assert not result["asset_failures"]
    assert len(result["assets"]) == count
    client, metadata, old_payload, _, _ = extract_signed_fixture_payload(
        row, golden_criteria_asset(doi, "original.html"), transport, tmp_path
    )
    old_urls = {
        im.url
        for im in iter_markdown_images(old_payload.content.markdown_text)
        if "Expires=" in im.url
    }
    article = client.to_article_model(
        metadata, old_payload, downloaded_assets=result["assets"]
    )
    markdown = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="body"
    )
    assert article.quality.has_fulltext
    assert all(url not in markdown for url in old_urls)
    expected_hashes = {record["sha256"] for record, _ in captures}
    for asset in result["assets"]:
        path = Path(asset["path"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() in expected_hashes
        assert str(path) in markdown
    envelope = FetchEnvelope(
        doi=doi,
        source=article.source,
        has_fulltext=True,
        article=article,
        markdown=markdown,
    )
    acceptance = evaluate_fetch_acceptance(
        envelope, asset_profile="body", require_local_body_assets=True
    )
    assert acceptance.asset.status == "complete"
    assert acceptance.asset.body_local == count
    assert acceptance.asset.local_body_assets_satisfied


def test_royal_historical_body_uses_both_captured_viewers_and_keeps_missing_scope(
    tmp_path,
):
    from tests.support.signed_image_replay import replay_royal_captured_viewer_assets

    article, markdown, captures, calls = replay_royal_captured_viewer_assets(tmp_path)
    assert article.quality.has_fulltext
    for capture in captures:
        path = capture["asset"]["path"]
        assert markdown.count(f"]({path})") == 1
        assert any(call["url"] == capture["requested_candidate"] for call in calls)
        assert (
            hashlib.sha256(Path(path).read_bytes()).hexdigest()
            == capture["record"]["sha256"]
        )
    assert {capture["source_dom_id"] for capture in captures} == {
        "RSOS150470F1",
        "RSOS150470F2",
    }
    envelope = FetchEnvelope(
        doi=article.doi,
        source=article.source,
        has_fulltext=True,
        article=article,
        markdown=markdown,
    )
    acceptance = evaluate_fetch_acceptance(
        envelope, asset_profile="body", require_local_body_assets=True
    )
    assert acceptance.asset.body_local == 2
    assert acceptance.asset.body_discovered == 5
    assert acceptance.asset.status == "degraded"
    assert not acceptance.asset.local_body_assets_satisfied
