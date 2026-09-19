"""Legacy captured SVG bytes; HTTP 200 is an injected replay envelope."""

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.models import article_from_markdown
from tests.golden_criteria import golden_criteria_asset
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response


def test_original_science_svg_is_bound_to_figure_and_saved_unchanged(tmp_path):
    doi = "10.1126/science.adz3492"
    source = "https://www.science.org/doi/full/" + doi
    soup = BeautifulSoup(
        golden_criteria_asset(doi, "original.html").read_text(), "lxml"
    )
    original = soup.select_one('img[aria-labelledby="f1"]')
    url = urljoin(source, original["src"])
    assert url.endswith("/assets/graphic/science.adz3492-f1.svg")
    body = golden_criteria_asset(doi, "body_assets/science.adz3492-f1.svg").read_bytes()
    assert b'viewBox="0 0 696 1069.901"' in body
    assert len(body) == 316329
    transport = FixtureHtmlTransport({url: http_response(url, body, "image/svg+xml")})
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=doi,
        assets=[
            {"kind": "figure", "heading": "Figure 1", "url": url, "section": "body"}
        ],
        output_dir=tmp_path,
        user_agent="offline SVG replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            candidate_builder=lambda *_a, **_k: [url], asset_download_concurrency=1
        ),
    )
    assert not result["asset_failures"]
    assert len(result["assets"]) == 1
    asset = result["assets"][0]
    assert Path(asset["path"]).read_bytes() == body
    assert Path(asset["path"]).suffix == ".svg"
    article = article_from_markdown(
        source="science",
        doi=doi,
        metadata={"title": "New demand goals for energy and climate resilience"},
        markdown_text=f"![Figure 1]({url})",
        assets=result["assets"],
    )
    rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    assert rendered.count(f"]({asset['path']})") == 1
