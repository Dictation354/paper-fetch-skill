"""Replay same-paper image bytes already recorded in acquisition provenance.

Only expiring signature parameters are ignored when matching old DOM URLs.
The replay requests the captured URL and uses its recorded HTTP envelope.
This helper neither discovers new URLs nor manufactures successful responses.
"""

from pathlib import Path

from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from tests.support._paper_fetch_support import FixtureHtmlTransport
from tests.support.acquired_publisher_inputs import (
    _response,
    captured_body,
    capture_records,
    capture_url_identity,
)


def download_captured_images(doi, assets, output_dir):
    from tests.golden_criteria import golden_criteria_sample_for_doi

    provider = golden_criteria_sample_for_doi(doi)["publisher"]
    records = [
        record
        for record in capture_records(doi)
        if record.get("status_code") == 200
        and (record.get("response_headers") or {})
        .get("content-type", "")
        .startswith("image/")
    ]
    downloaded = []
    for asset in assets:
        matches = []
        for key in ("full_size_url", "url", "preview_url"):
            if asset.get(key):
                matches = [
                    record
                    for record in records
                    if capture_url_identity(record["requested_url"], provider=provider)
                    == capture_url_identity(asset[key], provider=provider)
                ]
            if matches:
                break
        assert matches, f"No captured same-paper image for {doi}: {asset['heading']}"
        record = matches[-1]
        body = captured_body(doi, record)
        assert len(body) > 100
        url = record["requested_url"]
        transport = FixtureHtmlTransport({url: _response(record, body)})
        result = download_assets(
            FIGURE_KIND,
            transport,
            article_id=doi,
            assets=[asset],
            output_dir=output_dir,
            user_agent="offline captured image replay",
            asset_profile="body",
            options=AssetDownloadOptions(
                candidate_builder=lambda *_a, captured_url=url, **_k: [captured_url],
                asset_download_concurrency=1,
            ),
        )
        assert not result["asset_failures"], result
        assert len(result["assets"]) == 1
        actual = result["assets"][0]
        assert Path(actual["path"]).read_bytes() == body
        assert actual["download_url"] == url
        downloaded.append(actual)
    return downloaded
