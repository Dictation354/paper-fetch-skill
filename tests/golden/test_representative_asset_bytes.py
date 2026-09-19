"""One source-bound image per provider through download/hash/final link.

Old corpus bytes have unknown capture headers/date; their HTTP 200 envelopes are
injected. Newly acquired images retain the recorded HTTP envelope. This isolated
asset replay does not claim a successful browser/article fetch or full-size tier.
"""

from tests.support.representative_asset_bytes import NEW, OLD
import hashlib
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pytest
from paper_fetch.extraction.html.assets import (
    FIGURE_KIND,
    AssetDownloadOptions,
    download_assets,
)
from paper_fetch.extraction.image_payloads import image_mime_type_from_bytes
from paper_fetch.models import article_from_markdown
from paper_fetch.provider_catalog import SOURCE_PROVIDER_MAP
from paper_fetch.providers.plos import _plos_figure_image_url
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._paper_fetch_support import RecordingTransport, http_response
from tests.support.acquired_publisher_inputs import _record, _response


def _download_and_render(provider, doi, url, response, tmp_path):
    body = response["body"]
    transport = RecordingTransport({("GET", url): response})
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=doi,
        assets=[
            {"kind": "figure", "heading": "Figure 1", "url": url, "section": "body"}
        ],
        output_dir=tmp_path,
        user_agent="offline replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            candidate_builder=lambda *_a, **_k: [url],
            asset_download_concurrency=1,
            fetch_policy="direct_then_browser",
            provider_name=provider,
        ),
    )
    assert not result["asset_failures"]
    assert len(result["assets"]) == 1
    asset = result["assets"][0]
    path = Path(asset["path"])
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(body).digest()
    assert asset["downloaded_bytes"] == len(body)
    article = article_from_markdown(
        source=next(
            source
            for source, owner in SOURCE_PROVIDER_MAP.items()
            if owner == provider and not source.endswith("_pdf")
        ),
        doi=doi,
        metadata={"title": golden_criteria_sample_for_doi(doi).get("title", doi)},
        markdown_text=f"## Figure replay\n\n![Figure 1]({url})",
        assets=result["assets"],
    )
    rendered = article.to_ai_markdown(
        include_refs="none", max_tokens="full_text", asset_profile="body"
    )
    assert str(path) in rendered
    assert f"]({url})" not in rendered


@pytest.mark.parametrize(
    "provider,doi,filename,source_token", OLD, ids=[row[0] for row in OLD]
)
def test_existing_same_paper_image_download_and_final_link(
    provider, doi, filename, source_token, tmp_path
):
    sample = golden_criteria_sample_for_doi(doi)
    if provider == "plos":
        source = golden_criteria_asset(doi, "original.xml").read_text()
        assert "info:doi/" + source_token in source
        url = _plos_figure_image_url(source_token)
    else:
        soup = BeautifulSoup(
            golden_criteria_asset(doi, "original.html").read_text(), "html.parser"
        )
        values = [
            str(value)
            for tag in soup.find_all(True)
            for key, value in tag.attrs.items()
            if key in {"href", "src", "data-src", "data-lg-src"}
            and source_token in str(value)
        ]
        assert values
        url = urljoin(sample["source_url"], values[0])
    body = golden_criteria_asset(doi, "body_assets/" + filename).read_bytes()
    _download_and_render(
        provider,
        doi,
        url,
        http_response(url, body, image_mime_type_from_bytes(body)),
        tmp_path,
    )


@pytest.mark.parametrize("provider,doi,filename", NEW, ids=[row[0] for row in NEW])
def test_new_same_paper_image_download_and_final_link(
    provider, doi, filename, tmp_path
):
    record, body = _record(doi, "acquisition/" + filename)
    sample = golden_criteria_sample_for_doi(doi)
    source_path = (
        sample["assets"].get("original.html") or sample["assets"]["original.xml"]
    )
    if record.get("source_input"):
        source_path = (
            Path(record["source_input"])
            if record["source_input"].startswith("tests/")
            else golden_criteria_asset(doi, record["source_input"])
        )
    source = Path(source_path).read_text()
    # Signed CDN attributes are HTML-escaped in the original DOM.
    from html import unescape

    requested = record["requested_url"].removeprefix("https:")
    from urllib.parse import urlsplit

    if provider == "annualreviews":
        from paper_fetch.providers import _annualreviews_html

        # Ingenta's imagePath is relative to /docserver, not the article URL.
        candidates = _annualreviews_html.extract_scoped_html_assets(
            source, sample["source_url"], asset_profile="body"
        )
        assert any(record["requested_url"] in asset.values() for asset in candidates)
    else:
        assert requested in unescape(source) or (
            provider in {"ams", "pnas"}
            and urlsplit(record["requested_url"]).path in unescape(source)
        )
    _download_and_render(
        provider, doi, record["requested_url"], _response(record, body), tmp_path
    )
