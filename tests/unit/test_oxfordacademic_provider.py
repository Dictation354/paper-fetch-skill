from __future__ import annotations
import re
from pathlib import Path
import pytest
from paper_fetch.http import HttpTransport
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.provider_catalog import SOURCE_PROVIDER_MAP
from paper_fetch.providers import _oxfordacademic_html
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from tests.support._atypon_browser_workflow_provider_support import png_header
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response


HTML_DOI = "10.1093/bioinformatics/btaa161"
FIGURE_DOI = "10.1093/bioinformatics/btaa823"
PDF_DOI = "10.1093/bioinformatics/btaa153"


def test_provider_bundle_is_registered() -> None:
    bundle = provider_bundle("oxfordacademic")

    assert bundle.client_factory is OxfordAcademicClient
    assert SOURCE_PROVIDER_MAP["oxfordacademic_html"] == "oxfordacademic"
    assert SOURCE_PROVIDER_MAP["oxfordacademic_pdf"] == "oxfordacademic"
    assert bundle.html_rules is not None
    assert bundle.html_rules.name == "oxfordacademic"


def test_client_pdf_candidates_keep_article_pdf_url_and_doi_templates() -> None:
    source_url = (
        "https://academic.oup.com/bioinformatics/article-pdf/36/11/3401/50670770/"
        "bioinformatics_36_11_3401.pdf"
    )
    client = OxfordAcademicClient(HttpTransport(), {})

    candidates = client.pdf_candidates(
        PDF_DOI, {"doi": PDF_DOI, "source_url": source_url}
    )

    assert candidates[0] == source_url
    assert f"https://academic.oup.com/doi/pdf/{PDF_DOI}" in candidates


def test_html_asset_download_supports_none_body_and_all_profiles(
    tmp_path: Path,
) -> None:
    source_url = "https://academic.oup.com/bioinformatics/article/36/11/3409/5802463"
    figure_url = "https://academic.oup.com/article/figure/f1.png"
    supplementary_url = "https://academic.oup.com/article/supplement/s1.zip"
    transport = FixtureHtmlTransport(
        {
            figure_url: http_response(
                figure_url,
                png_header(16, 12) + b"oxford-figure",
                "image/png",
            ),
            supplementary_url: http_response(
                supplementary_url,
                b"PK\x03\x04oxford-supplement",
                "application/zip",
            ),
        }
    )
    client = OxfordAcademicClient(transport, {})
    assets = [
        {
            "kind": "figure",
            "heading": "Figure 1",
            "url": figure_url,
            "original_url": figure_url,
            "section": "body",
        },
        {
            "kind": "supplementary",
            "heading": "Supplementary data",
            "url": supplementary_url,
            "original_url": supplementary_url,
            "section": "supplementary",
        },
    ]
    raw_payload = RawFulltextPayload(
        provider="oxfordacademic",
        source_url=source_url,
        content_type="text/html",
        body=b"<article>body</article>",
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=b"<article>body</article>",
            markdown_text=f"# Example\n\n![Figure 1]({figure_url})",
            merged_metadata={"doi": HTML_DOI, "title": "Example"},
            extracted_assets=assets,
        ),
    )

    none_result = client.download_related_assets(
        HTML_DOI,
        {"doi": HTML_DOI},
        raw_payload,
        tmp_path / "none",
        asset_profile="none",
    )
    body_result = client.download_related_assets(
        HTML_DOI,
        {"doi": HTML_DOI},
        raw_payload,
        tmp_path / "body",
        asset_profile="body",
    )
    all_result = client.download_related_assets(
        HTML_DOI,
        {"doi": HTML_DOI},
        raw_payload,
        tmp_path / "all",
        asset_profile="all",
    )

    assert none_result == {"assets": [], "asset_failures": []}
    assert [item["kind"] for item in body_result["assets"]] == ["figure"]
    assert {item["kind"] for item in all_result["assets"]} == {
        "figure",
        "supplementary",
    }
    article = client.to_article_model(
        {"doi": HTML_DOI, "title": "Example"},
        raw_payload,
        downloaded_assets=body_result["assets"],
    )
    rendered = article.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    assert str(body_result["assets"][0]["path"]) in rendered


@pytest.mark.parametrize("downloaded_count", [2, 1, 0], ids=["all", "partial", "none"])
def test_html_preview_images_stay_inline_after_model_rendering(
    tmp_path: Path,
    downloaded_count: int,
) -> None:
    source_url = "https://academic.oup.com/example"
    assets = [
        {
            "kind": "figure",
            "heading": f"Figure {number}",
            "url": f"https://oup.silverchair-cdn.com/article/f{number}.jpeg",
            "original_url": f"https://oup.silverchair-cdn.com/article/f{number}.jpeg",
            "preview_url": f"https://oup.silverchair-cdn.com/article/m_f{number}.jpeg",
            "section": "body",
        }
        for number in (1, 2)
    ]
    markdown = "## Results\n\n" + "\n\n".join(
        f"Before figure {number}.\n\n![Figure {number}]({asset['preview_url']})"
        f"\n\nAfter figure {number}."
        for number, asset in enumerate(assets, 1)
    )
    raw_payload = RawFulltextPayload(
        provider="oxfordacademic",
        source_url=source_url,
        content_type="text/html",
        body=b"<article>body</article>",
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=b"<article>body</article>",
            markdown_text=markdown,
            extracted_assets=assets,
        ),
    )
    downloaded_assets = []
    for number, asset in enumerate(assets[:downloaded_count], 1):
        path = tmp_path / f"figure-{number}.png"
        path.write_bytes(png_header(16, 12) + b"oxford-figure")
        downloaded_assets.append({**asset, "path": str(path)})
    failures = (
        [{"kind": "figure", "url": assets[1]["url"], "reason": "download_failed"}]
        if downloaded_count == 1
        else []
    )

    article = OxfordAcademicClient(HttpTransport(), {}).to_article_model(
        {"doi": HTML_DOI, "title": "Example"},
        raw_payload,
        downloaded_assets=downloaded_assets or None,
        asset_failures=failures,
    )
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )

    assert article.quality.asset_failures == failures
    assert sum(bool(asset.path) for asset in article.assets) == downloaded_count
    for number, asset in enumerate(assets, 1):
        if number <= downloaded_count:
            target = downloaded_assets[number - 1]["path"]
            assert asset["preview_url"] not in rendered
            assert rendered.count(f"]({target})") == 1
        else:
            target = asset["preview_url"]
            assert str(tmp_path / f"figure-{number}.png") not in rendered
        assert (
            f"Before figure {number}.\n\n![Figure {number}]({target})"
            f"\n\nAfter figure {number}."
        ) in rendered


def test_oxford_reference_meta_fallback_strips_citation_keys() -> None:
    metadata = _oxfordacademic_html.merge_metadata_with_html(
        {"doi": HTML_DOI},
        """
        <html><head>
          <meta name="citation_reference"
                content="citation_author=Allison  P.D.; citation_title=Survival Analysis Using SAS: A Practical Guide; citation_year=1995;">
        </head><body><article><h2>References</h2></article></body></html>
        """,
        "https://academic.oup.com/example",
        doi=HTML_DOI,
    )

    references = metadata.get("references")

    assert isinstance(references, list)
    assert (
        references[0]["raw"]
        == "Allison P.D. (1995). Survival Analysis Using SAS: A Practical Guide"
    )
    assert references[0]["title"] == "Survival Analysis Using SAS: A Practical Guide"
    assert references[0]["year"] == "1995"
    assert not re.search(r"\bcitation_[A-Za-z0-9_]+=", str(references))


def test_oxford_attachment_identity_preserves_non_signature_parameters() -> None:
    url = "https://oup.silverchair-cdn.com/oup/backfile/supp.pdf"
    html = f"""
    <article><a href="{url}?part=1&amp;Signature=old">Supplementary figure</a>
    <a href="javascript:;">Supplementary Data</a>
    <a href="https://academic.oup.com/article-pdf/1/main.pdf">Download PDF</a>
    <a href="https://example.org/reference.pdf">Reference</a></article>
    <div class="dataSuppLink"><a href="{url}?part=1&amp;Signature=new&amp;Expires=123">File 1</a></div>
    <div class="dataSuppLink"><a href="{url}?part=2&amp;Signature=second">File 2</a></div>
    """
    result = _oxfordacademic_html.extract_markdown(
        html, "https://academic.oup.com/article/1", metadata={}
    )
    assets = [a for a in result.extracted_assets if a["kind"] == "supplementary"]
    assert [a["url"] for a in assets] == [
        url + "?part=1&Signature=new&Expires=123",
        url + "?part=2&Signature=second",
    ]
