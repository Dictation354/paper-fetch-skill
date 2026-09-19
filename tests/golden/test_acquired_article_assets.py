"""Real HTML extraction, candidate selection, bytes and final article assembly.

One captured figure is selected per article. Other candidate responses are
injected as missing; this is neither an all-assets nor a live-browser claim.
"""

from tests.support.acquired_article_assets import CLIENTS
import hashlib
import re
from pathlib import Path
import pytest
from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.extraction.image_payloads import image_mime_type_from_bytes
from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.providers import _annualreviews_html, _mdpi_assets
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.browser_workflow.asset_download import (
    plan_browser_asset_download,
)
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support.representative_asset_bytes import OLD, NEW


CASES = [row for row in OLD + NEW if row[0] in CLIENTS] + [
    ("mdpi", "10.3390/math11030657", "figure-1.png")
]
CAPTION_ANCHORS = {
    "ams": "The boundary of the domain of interest is colored in red",
    "iop": "Core optical circuit for QT made up of three beam splitters",
    "pnas": "SARS-CoV-2 human challenge study",
    "aip": "Image of the ion pump with the adapter",
    "annualreviews": "Illustration of the vision of general shape-changing robots",
    "science": "Sensitivity of AGR to tropical MAT",
    "tandf": "Study region and data",
    "wiley": "emission and atmospheric",
    "acs": "",
    "mdpi": "Trends of technical efficiency change of enterprises",
}


@pytest.mark.parametrize("case", CASES, ids=lambda row: row[0])
def test_original_article_figure_candidates_download_and_assembly(case, tmp_path):
    provider, doi, filename, *tokens = case
    sample = golden_criteria_sample_for_doi(doi)
    source_url = sample["source_url"]
    html = golden_criteria_asset(doi, "original.html").read_text()
    if not tokens:
        record, _ = _record(doi, "acquisition/" + filename)
        if record.get("source_input"):
            html = (
                Path(record["source_input"])
                if record["source_input"].startswith("tests/")
                else golden_criteria_asset(doi, record["source_input"])
            ).read_text()
    metadata = {
        "doi": doi,
        "title": parse_html_metadata(html, source_url)["title"],
        "landing_page_url": source_url,
    }
    transport = FixtureHtmlTransport({})
    client = CLIENTS[provider](transport, {})
    markdown, extraction = client.extract_markdown(html, source_url, metadata=metadata)
    with RuntimeContext(env={}, transport=transport) as context:
        profile = {"client": client, "context": context, "asset_profile": "body"}
        if provider in {"annualreviews", "mdpi"}:
            # These download overrides use their own scoped extractors.
            owner = _annualreviews_html if provider == "annualreviews" else _mdpi_assets
            profile["assets"] = owner.extract_scoped_html_assets(
                html, source_url, asset_profile="body"
            )
        plan = plan_browser_asset_download(
            article_id=doi,
            output_dir=tmp_path,
            html_text=html,
            source_url=source_url,
            profile=profile,
            deps=client.deps,
        )
    if tokens:
        token = tokens[0]
        selected = [asset for asset in plan.body_assets if token in str(asset)]
        assert len(selected) == 1
        asset = selected[0]
        url = next(
            str(asset[key])
            for key in ("url", "source_url", "original_url", "download_url")
            if token in str(asset.get(key) or "")
        )
        body = golden_criteria_asset(doi, "body_assets/" + filename).read_bytes()
        response = http_response(url, body, image_mime_type_from_bytes(body))
    else:
        record, body = _record(doi, "acquisition/" + filename)
        url = record["requested_url"]
        selected = [asset for asset in plan.body_assets if url in asset.values()]
        assert len(selected) == 1
        asset = selected[0]
        response = _response(record, body)
    transport.responses[url] = response
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=doi,
        assets=selected,
        output_dir=tmp_path,
        user_agent="offline replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            candidate_builder=plan.candidate_builder,
            asset_download_concurrency=1,
            provider_name=provider,
        ),
    )
    assert not result["asset_failures"], result
    assert len(result["assets"]) == 1
    downloaded = result["assets"][0]
    path = Path(downloaded["path"])
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(body).digest()
    payload = RawFulltextPayload(
        provider=provider,
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=html.encode(),
            markdown_text=markdown,
            merged_metadata=metadata,
            diagnostics={"extraction": extraction},
            extracted_assets=plan.body_assets,
        ),
    )
    article = client.to_article_model(
        metadata, payload, downloaded_assets=result["assets"]
    )
    rendered = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="body"
    )
    assert article.quality.has_fulltext
    assert str(path) in rendered
    assert f"]({url})" not in rendered
    final = [item for item in article.assets if item.path == str(path)]
    assert len(final) == 1
    assert final[0].caption == downloaded.get("caption")
    assert final[0].caption
    anchor = CAPTION_ANCHORS[provider] or final[0].caption
    assert anchor in final[0].caption
    plain = re.sub(r"[\s*_]+", " ", rendered)
    assert anchor in plain
    assert any(call["url"] == url for call in transport.calls)
