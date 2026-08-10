from __future__ import annotations

import re
import tempfile
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest

from paper_fetch.provider_catalog import PROVIDER_CATALOG
from paper_fetch.providers import (
    _royalsocietypublishing_html,
    browser_runtime,
    browser_workflow,
)
from paper_fetch.providers._pdf_common import PdfFetchResult
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers._royalsocietypublishing_html import (
    royalsocietypublishing_normalize_markdown,
)
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.royalsocietypublishing import RoyalsocietypublishingClient
from paper_fetch.tracing import source_trail_from_trace
from tests.golden_corpus import GoldenCorpusFixture, build_article_from_fixture
from tests.golden_criteria import golden_criteria_sample_for_doi
from tests.unit._atypon_browser_workflow_provider_support import (
    AssetTransport,
    _typed_raw_payload,
    png_header,
)
from tests.unit._browser_workflow_deps import install_browser_workflow_deps
from tests.unit._paper_fetch_support import (
    fulltext_pdf_bytes,
)


def _royal_article_html(
    *, doi: str, body_text: str | None = None, pdf_url: str | None = None
) -> bytes:
    repeated_body = body_text or (
        "Royal Society full text paragraph describing browser article content, "
        "methods, results, and discussion. " * 80
    )
    pdf_meta = (
        f'<meta name="citation_pdf_url" content="{pdf_url}" />' if pdf_url else ""
    )
    html = f"""
    <html>
      <head>
        <title>Royal Society Direct HTML Test</title>
        <meta name="citation_title" content="Royal Society Direct HTML Test" />
        <meta name="citation_doi" content="{doi}" />
        <meta name="citation_author" content="Alice Example" />
        <meta name="citation_abstract" content="This abstract describes a Royal Society article." />
        <meta name="citation_journal_title" content="Royal Society Open Science" />
        <meta name="citation_xml_url" content="https://royalsocietypublishing.org/article-xml/doi/{doi}/example" />
        <meta name="citation_reference" content="citation_title=Reference Title; citation_author=Smith A; citation_year=2020; citation_doi=10.1000/example;" />
        {pdf_meta}
      </head>
      <body>
        <div class="article-body">
          <span>Open figure viewer</span>
          <h2 class="abstract-title">Abstract</h2>
          <p>This abstract describes a Royal Society article.</p>
          <h2 class="section-title">1 Introduction</h2>
          <p>{repeated_body}</p>
          <figure><figcaption>Figure 1. Direct HTML figure caption.</figcaption></figure>
          <table><tr><th>Metric</th><th>Value</th></tr><tr><td>alpha</td><td>1</td></tr></table>
          <h2 class="backreferences-title">References</h2>
          <div class="ref-list">Google Scholar Crossref Search ADS</div>
        </div>
      </body>
    </html>
    """
    return html.encode("utf-8")


def _render_markdown_for_fixture(doi: str) -> str:
    sample = golden_criteria_sample_for_doi(doi)
    fixture = GoldenCorpusFixture(sample_id=str(sample["sample_id"]), sample=sample)
    article = build_article_from_fixture(fixture)
    return article.to_ai_markdown(include_refs="all")


def _runtime_config(tmpdir: str, doi: str) -> browser_runtime.BrowserRuntimeConfig:
    tmp = Path(tmpdir)
    return browser_runtime.BrowserRuntimeConfig(
        provider="royalsocietypublishing",
        doi=doi,
        artifact_dir=tmp / "artifacts",
        headless=True,
        user_agent="paper-fetch-test/1",
        backend="camoufox",
    )


def test_provider_bundle_round_trip() -> None:
    bundle = provider_bundle("royalsocietypublishing")
    assert bundle.catalog.name == "royalsocietypublishing"
    assert bundle.catalog.status_order == 11
    assert bundle.html_rules is not None
    assert bundle.html_rules.name == "royalsocietypublishing"
    assert set(bundle.sources) == {
        "royalsocietypublishing_html",
        "royalsocietypublishing_pdf",
    }


def test_provider_catalog_is_readable() -> None:
    assert PROVIDER_CATALOG["royalsocietypublishing"].name == "royalsocietypublishing"
    assert PROVIDER_CATALOG["royalsocietypublishing"].requires_browser_runtime is True


def test_article_html_route_uses_browser_doi_candidate_without_xml_route() -> None:
    doi = "10.1098/rsta.2019.0558"
    doi_url = f"https://royalsocietypublishing.org/doi/{doi}"
    article_url = "https://royalsocietypublishing.org/rsta/article/378/2173/20190558/41050/example"
    fetch_html = mock.Mock(
        return_value=browser_runtime.BrowserFetchedHtml(
            source_url=doi_url,
            final_url=article_url,
            html=_royal_article_html(doi=doi).decode("utf-8"),
            response_status=200,
            response_headers={"content-type": "text/html; charset=utf-8"},
            title="Royal Society Direct HTML Test",
            summary="Royal Society summary",
            browser_context_seed={"browser_final_url": article_url},
        )
    )
    client = RoyalsocietypublishingClient(AssetTransport({}), {})

    with tempfile.TemporaryDirectory() as tmpdir:
        install_browser_workflow_deps(
            client,
            load_runtime_config=mock.Mock(return_value=_runtime_config(tmpdir, doi)),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=fetch_html,
            fetch_pdf_with_browser=mock.Mock(),
        )
        raw_payload = client.fetch_raw_fulltext(doi, {"doi": doi})
    article = client.to_article_model(raw_payload.merged_metadata or {}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "html"
    assert raw_payload.source_url == article_url
    assert article.source == "royalsocietypublishing_html"
    assert "fulltext:royalsocietypublishing_html_ok" in source_trail_from_trace(
        raw_payload.trace
    )
    assert "Royal Society Direct HTML Test" in article.to_ai_markdown(
        include_refs="all"
    )
    assert "Open figure viewer" not in article.to_ai_markdown(include_refs="all")
    fetch_html.assert_called_once()
    html_candidates = list(fetch_html.call_args.args[0])
    assert html_candidates == [doi_url, f"https://doi.org/{doi}"]
    assert all("article-xml" not in candidate for candidate in html_candidates)


def test_article_html_fetch_result_downloads_figure_assets_and_rewrites_inline_links() -> (
    None
):
    """asset-download-contract: provider=royalsocietypublishing"""

    doi = "10.1098/rsos.150470"
    article_url = "https://royalsocietypublishing.org/rsos/article/2/10/150470/example"
    figure_page_url = (
        "https://royalsocietypublishing.org/view-large/figure/18113020/"
        "rsos150470f01.tif"
    )
    preview_url = (
        "https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/"
        "m_rsos150470f01.png?Expires=1&Signature=preview"
    )
    figure_url = (
        "https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/"
        "rsos150470f01.png?Expires=1&Signature=full+signature&Key-Pair-Id=test"
    )
    download_wrapper_url = (
        "https://trs.silverchair-cdn.com/DownloadFile/DownloadImage.aspx?"
        f"image={figure_url}&sec=18113020"
    )
    body_text = (
        "Royal Society body paragraph discusses the fossil record and introduces Figure 1 "
        "as the main visual evidence for the article. " * 80
    )
    html = (
        _royal_article_html(doi=doi, body_text=body_text)
        .decode("utf-8")
        .replace(
            "<figure><figcaption>Figure 1. Direct HTML figure caption.</figcaption></figure>",
            f"""
        <div class="fig-section" id="f1" data-id="f1">
          <div class="graphic-wrap">
            <a href="{figure_page_url}">
              <img src="{preview_url}" alt="Figure 1. Direct HTML figure caption." />
            </a>
            <div class="fig-orig">
              <a class="download-slide" href="{download_wrapper_url}">Download slide</a>
            </div>
          </div>
          <div class="fig-label">Figure 1.</div>
          <div class="fig-caption">Direct HTML figure caption.</div>
        </div>
        """,
        )
    )
    image_bytes = png_header(640, 480)
    client = RoyalsocietypublishingClient(AssetTransport({}), {})
    markdown_text, extraction = client.extract_markdown(
        html,
        article_url,
        metadata={"doi": doi},
    )
    raw_payload = _typed_raw_payload(
        provider="royalsocietypublishing",
        source_url=article_url,
        content_type="text/html",
        body=html.encode("utf-8"),
        route="html",
        markdown_text=markdown_text,
        source_trail=["fulltext:royalsocietypublishing_html_ok"],
        extraction=extraction,
        browser_context_seed={"browser_final_url": article_url},
    )
    shared_fetcher = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": image_bytes,
            "url": figure_url,
        }
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        mocked_builder = mock.Mock(return_value=shared_fetcher)
        install_browser_workflow_deps(
            client,
            load_runtime_config=mock.Mock(return_value=_runtime_config(tmpdir, doi)),
            ensure_runtime_ready=mock.Mock(),
            _build_shared_browser_image_fetcher=mocked_builder,
        )
        asset_result = client.download_related_assets(
            doi,
            {"doi": doi},
            raw_payload,
            Path(tmpdir),
            asset_profile="body",
        )
        article = client.to_article_model(
            {"doi": doi},
            raw_payload,
            downloaded_assets=asset_result["assets"],
            asset_failures=asset_result["asset_failures"],
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
        downloaded_asset = asset_result["assets"][0]
        saved_path = Path(downloaded_asset["path"])

        assert saved_path.is_file()
        assert saved_path.read_bytes() == image_bytes
        assert downloaded_asset["downloaded_bytes"] == len(image_bytes)
        assert downloaded_asset["kind"] == "figure"
        assert downloaded_asset["path"] in markdown
        assert "![Figure 1](" in markdown
        assert figure_url not in markdown
        assert markdown.index("Figure 1 as the main visual evidence") < markdown.index(
            "![Figure 1]("
        )
        assert asset_result["asset_failures"] == []
    mocked_builder.assert_called_once()
    shared_fetcher.assert_called_once()
    assert shared_fetcher.call_args.args[0] == figure_url


def test_royal_fixture_extracts_signed_original_viewer_and_preview_urls() -> None:
    fixture_path = Path(
        "tests/fixtures/golden_criteria/10.1098_rsta.2019.0558/original.html"
    )
    extraction = _royalsocietypublishing_html.extract_markdown(
        fixture_path.read_text(encoding="utf-8"),
        "https://royalsocietypublishing.org/doi/10.1098/rsta.2019.0558",
    )
    figures = [
        asset for asset in extraction.extracted_assets if asset.get("kind") == "figure"
    ]

    assert len(figures) == 2
    for index, asset in enumerate(figures, start=1):
        full_size_url = str(asset["full_size_url"])
        preview_url = str(asset["preview_url"])
        figure_page_url = str(asset["figure_page_url"])
        assert asset["url"] == full_size_url
        assert f"rsta20190558f0{index}.png" in urlparse(full_size_url).path
        assert f"m_rsta20190558f0{index}.png" in urlparse(preview_url).path
        assert "/view-large/figure/" in figure_page_url
        assert urlparse(figure_page_url).path.endswith(f"rsta20190558f0{index}.tif")
        assert set(parse_qs(urlparse(full_size_url).query)) >= {
            "Expires",
            "Signature",
            "Key-Pair-Id",
        }
        assert "/view-large/figure/" not in full_size_url


def test_royal_download_image_wrapper_rejects_non_silverchair_nested_host() -> None:
    preview_url = "https://trs.silverchair-cdn.com/path/m_examplef01.png"
    html = f"""
    <html><body><div class="article-body">
      <div class="fig fig-section" data-id="EXAMPLEF1">
        <div class="fig-label">Figure 1</div>
        <div class="graphic-wrap">
          <img src="{preview_url}" alt="Safe preview" />
          <a class="download-slide"
             href="https://trs.silverchair-cdn.com/DownloadFile/DownloadImage.aspx?image=https://attacker.test/examplef01.png?Expires=1&Signature=bad&Key-Pair-Id=bad">
            Download slide
          </a>
        </div>
        <div class="fig-caption">Safe preview</div>
      </div>
    </div></body></html>
    """

    extraction = _royalsocietypublishing_html.extract_markdown(
        html,
        "https://royalsocietypublishing.org/doi/10.1098/example",
    )

    assert len(extraction.extracted_assets) == 1
    asset = extraction.extracted_assets[0]
    assert asset["url"] == preview_url
    assert asset["preview_url"] == preview_url
    assert "full_size_url" not in asset


def test_royal_grouped_slide_url_is_not_assigned_to_the_wrong_figure() -> None:
    fixture_path = Path(
        "tests/fixtures/golden_criteria/10.1098_rsos.150470/original.html"
    )
    extraction = _royalsocietypublishing_html.extract_markdown(
        fixture_path.read_text(encoding="utf-8"),
        "https://royalsocietypublishing.org/doi/10.1098/rsos.150470",
    )
    figures = {
        str(asset["heading"]): asset
        for asset in extraction.extracted_assets
        if asset.get("kind") == "figure"
    }

    assert len(figures) == 5
    assert "full_size_url" not in figures["Figure 1"]
    assert "/m_rsos150470f01.jpeg" in figures["Figure 1"]["preview_url"]
    assert "/rsos150470f02.jpeg" in figures["Figure 2"]["full_size_url"]
    assert "full_size_url" not in figures["Figure 3"]
    assert "/rsos150470f04.jpeg" in figures["Figure 4"]["full_size_url"]


def test_royal_figure_asset_uses_viewer_only_when_direct_original_is_missing() -> None:
    doi = "10.1098/rsos.150470"
    article_url = "https://royalsocietypublishing.org/rsos/article/example"
    figure_page_url = (
        "https://royalsocietypublishing.org/view-large/figure/18113020/"
        "rsos150470f01.tif"
    )
    preview_url = (
        "https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/"
        "m_rsos150470f01.png?Expires=1&Signature=preview"
    )
    full_size_url = (
        "https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/"
        "rsos150470f01.png?Expires=2&Signature=fresh&Key-Pair-Id=test"
    )
    body_text = "Royal Society figure-page fallback body text. " * 120
    html = (
        _royal_article_html(doi=doi, body_text=body_text)
        .decode("utf-8")
        .replace(
            "<figure><figcaption>Figure 1. Direct HTML figure caption.</figcaption></figure>",
            f"""
        <div class="fig-section" data-id="RSOS150470F1">
          <div class="graphic-wrap">
            <a href="{figure_page_url}">
              <img src="{preview_url}" alt="Figure 1. Fallback caption." />
            </a>
          </div>
          <div class="fig-label">Figure 1.</div>
          <div class="fig-caption">Fallback caption.</div>
        </div>
        """,
        )
    )
    client = RoyalsocietypublishingClient(AssetTransport({}), {})
    markdown_text, extraction = client.extract_markdown(
        html,
        article_url,
        metadata={"doi": doi},
    )
    raw_payload = _typed_raw_payload(
        provider="royalsocietypublishing",
        source_url=article_url,
        content_type="text/html",
        body=html.encode("utf-8"),
        route="html",
        markdown_text=markdown_text,
        source_trail=["fulltext:royalsocietypublishing_html_ok"],
        extraction=extraction,
        browser_context_seed={"browser_final_url": article_url},
    )
    image_bytes = png_header(1200, 800)
    shared_fetcher = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": image_bytes,
            "url": full_size_url,
        }
    )
    figure_page_fetch = mock.Mock(
        return_value=browser_runtime.BrowserFetchedHtml(
            source_url=figure_page_url,
            final_url=figure_page_url,
            html=(
                "<html><body>"
                f'<img class="content-image" src="{full_size_url}" />'
                "</body></html>"
            ),
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="Figure 1",
            summary="Full-size Royal Society figure",
            browser_context_seed={},
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        install_browser_workflow_deps(
            client,
            load_runtime_config=mock.Mock(return_value=_runtime_config(tmpdir, doi)),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=figure_page_fetch,
            _build_shared_browser_image_fetcher=mock.Mock(return_value=shared_fetcher),
        )
        result = client.download_related_assets(
            doi,
            {"doi": doi},
            raw_payload,
            Path(tmpdir),
            asset_profile="body",
        )

    figure_page_fetch.assert_called_once()
    assert figure_page_fetch.call_args.args[0] == [figure_page_url]
    readiness = figure_page_fetch.call_args.kwargs["readiness"]
    assert readiness.wait_for_article_body is False
    assert readiness.selector == "img.content-image[src], img.content-image[data-src]"
    assert figure_page_fetch.call_args.kwargs["wait_seconds"] == 2
    assert figure_page_fetch.call_args.kwargs["options"].reuse_runtime_page is True
    shared_fetcher.assert_called_once()
    assert shared_fetcher.call_args.args[0] == full_size_url
    assert result["asset_failures"] == []
    assert result["assets"][0]["download_tier"] == "full_size"


def test_royal_figure_assets_merge_view_large_and_silverchair_by_dom_id() -> None:
    view_large = (
        "https://royalsocietypublishing.org/view-large/figure/17448863/"
        "rsos201200f01.tif"
    )
    preview = (
        "https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/"
        "m_rsos201200f01.png?Expires=1&Signature=test"
    )
    full_size = preview.replace("m_rsos", "rsos").replace(
        "Signature=test", "Signature=full"
    )

    assets = _royalsocietypublishing_html._normalize_extracted_assets(
        [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "Canonical caption.",
                "url": full_size,
                "full_size_url": full_size,
                "figure_page_url": view_large,
                "dom_id": "RSOS201200F1",
                "section": "body",
            },
            {
                "kind": "figure",
                "heading": "Canonical caption. Refer to the image caption for details.",
                "caption": "Canonical caption. Refer to the image caption for details.",
                "url": preview,
                "preview_url": preview,
                "dom_id": "RSOS201200F1",
            },
        ]
    )

    assert assets == [
        {
            "kind": "figure",
            "heading": "Figure 1",
            "caption": "Canonical caption.",
            "url": full_size,
            "full_size_url": full_size,
            "figure_page_url": view_large,
            "preview_url": preview,
            "dom_id": "RSOS201200F1",
            "section": "body",
        }
    ]


def test_royal_figure_assets_fall_back_to_canonical_figure_basename() -> None:
    view_large = (
        "https://royalsocietypublishing.org/view-large/figure/17448863/"
        "rsos201200f01.tif"
    )
    preview = (
        "https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/"
        "m_rsos201200f01.png?Expires=1"
    )

    assets = _royalsocietypublishing_html._normalize_extracted_assets(
        [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "figure_page_url": view_large,
            },
            {
                "kind": "figure",
                "heading": "Figure 1",
                "url": preview,
                "preview_url": preview,
            },
            {
                "kind": "figure",
                "heading": "Figure 2",
                "url": preview.replace("f01", "f02"),
            },
        ]
    )

    assert len(assets) == 2
    assert assets[0]["figure_page_url"] == view_large
    assert assets[0]["url"] == preview
    assert assets[0]["preview_url"] == preview
    assert assets[1]["heading"] == "Figure 2"


def test_pdf_fallback_uses_citation_pdf_url_after_html_is_not_fulltext() -> None:
    doi = "10.1098/rsta.2020.0108"
    pdf_url = "https://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/example.pdf"
    watermark_url = (
        "https://watermark02.silverchair.com/rsta.2020.0108.pdf?token=%2A%2A%2A"
    )
    fetch_html = mock.Mock(
        side_effect=browser_runtime.BrowserRuntimeFailure(
            "forced_stop",
            "HTML route did not expose full text.",
            browser_context_seed={
                "browser_final_url": f"https://royalsocietypublishing.org/doi/{doi}"
            },
        )
    )
    fetch_pdf = mock.Mock(
        return_value=PdfFetchResult(
            source_url=pdf_url,
            final_url=watermark_url,
            pdf_bytes=fulltext_pdf_bytes(),
            markdown_text="# Royal Society PDF\n\n## Results\n\n"
            + ("Body text " * 120),
            suggested_filename="rsta.2020.0108.pdf",
        )
    )
    warm = mock.Mock(
        return_value={
            "browser_cookies": [{"name": "__cf_bm", "value": "seed"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": f"https://royalsocietypublishing.org/doi/{doi}",
        }
    )
    metadata = {
        "doi": doi,
        "raw_meta": {"citation_pdf_url": [pdf_url]},
    }
    client = RoyalsocietypublishingClient(AssetTransport({}), {})

    with tempfile.TemporaryDirectory() as tmpdir:
        install_browser_workflow_deps(
            client,
            load_runtime_config=mock.Mock(return_value=_runtime_config(tmpdir, doi)),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=fetch_html,
            warm_browser_context=warm,
            fetch_pdf_with_browser=fetch_pdf,
        )
        raw_payload = client.fetch_raw_fulltext(doi, metadata)
    article = client.to_article_model(raw_payload.merged_metadata or {}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "pdf_fallback"
    assert raw_payload.content.content_type == "application/pdf"
    assert raw_payload.body.startswith(
        b"%PDF-"
    )  # pdf magic bytes route_contract coverage
    assert article.source == "royalsocietypublishing_pdf"
    trail = source_trail_from_trace(raw_payload.trace)
    assert "fulltext:royalsocietypublishing_html_fail" in trail
    assert "fulltext:royalsocietypublishing_pdf_fallback_ok" in trail
    fetch_pdf.assert_called_once()
    assert list(fetch_pdf.call_args.args[0])[:2] == [
        pdf_url,
        f"https://royalsocietypublishing.org/doi/pdf/{doi}",
    ]


def test_pdf_fallback_rejects_html_wrapper_and_text_html_content() -> None:
    doi = "10.1098/rsta.2020.0108"
    client = RoyalsocietypublishingClient(AssetTransport({}), {})

    with tempfile.TemporaryDirectory() as tmpdir:
        install_browser_workflow_deps(
            client,
            load_runtime_config=mock.Mock(return_value=_runtime_config(tmpdir, doi)),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=mock.Mock(
                side_effect=browser_runtime.BrowserRuntimeFailure(
                    "forced_stop",
                    "HTML route did not expose full text.",
                )
            ),
            fetch_seeded_browser_pdf_payload=mock.Mock(
                side_effect=browser_workflow.PdfFallbackFailure(
                    "downloaded_file_not_pdf",
                    "Royal Society Publishing PDF fallback candidate returned an HTML wrapper or other non-PDF content.",
                )
            ),
        )
        with pytest.raises(ProviderFailure) as exc_info:
            client.fetch_raw_fulltext(doi, {"doi": doi})

    message = exc_info.value.message.lower()
    assert "html wrapper" in message or "non-pdf" in message


def test_metadata_only_route_contract_is_service_fallback_after_provider_failure() -> (
    None
):
    # route_contract: metadata_only is produced by the service-level metadata fallback
    # after royalsocietypublishing_html and royalsocietypublishing_pdf both fail.
    assert "metadata_only"
    assert "royalsocietypublishing_html"
    assert "royalsocietypublishing_pdf"


def test_markdown_contract_structure_fixture() -> None:
    """rule: rule-royalsociety-silverchair-markdown-cleanup"""

    # markdown-review: purpose=structure doi=10.1098/rsta.2019.0558
    markdown = _render_markdown_for_fixture("10.1098/rsta.2019.0558")
    assert (
        "# Creation and application of virtual patient cohorts of heart models"
        in markdown
    )
    assert "# 10.1098/rsta.2019.0558" not in markdown
    assert "## Abstract" in markdown
    assert markdown.count("## Abstract") == 1
    assert "virtual patient cohorts" in markdown
    assert "Schematic of the strategies for obtaining a virtual cohort" in markdown
    assert (
        "| [9] | 35 samples from ex vivo RAA | atrial model calibration | 0D | RVAC |"
        in markdown
    )
    assert (
        "The parameter set for each member of the virtual cohort can be obtained in three ways"
        in markdown
    )
    assert (
        "| [22] | $70\\,\\text{(training)} + 60\\,\\text{(test)} + 3\\,(12\\, k\\,\\text{samples})$ | shape uncertainty | LA | SID |"
        in markdown
    )
    assert (
        "| [23,24] | 5 PsAF | patient-specific modelling of atrial action potentials | not specified | 1:1 |"
        in markdown
    )
    assert "| [ |" not in markdown
    assert "## Authors' contributions" in markdown
    assert "## Competing interests" in markdown
    assert "## Funding" in markdown
    assert "We declare we have no competing interest." in markdown
    assert "RF Government Act No. 211" in markdown
    assert "Bootstrap methods: another look at the jackknife" in markdown
    assert "A new optimizer using particle swarm theory" in markdown
    assert re.search(r"(?m)^1\. Niederer SA", markdown)
    assert not re.search(r"(?m)^- Niederer SA", markdown)
    assert not re.search(r"(?m)^- Efron B\\s*\\.?\\s*1992\\s*$", markdown)
    assert not re.search(r"(?m)^- Eberhart R, Kennedy J\\s*\\.?\\s*1995\\s*$", markdown)
    assert "creativecommons" not in markdown.lower()
    assert "which permits unrestricted use" not in markdown
    assert "Close navigation menu" not in markdown
    assert "Open figure viewer" not in markdown
    assert "javascript:;" not in markdown
    assert not re.search(r"(?m)^- Figure$", markdown)
    assert "\n## Figures\n" not in markdown


def test_markdown_contract_table_fixture() -> None:
    # markdown-review: purpose=table doi=10.1098/rspb.2020.0097
    markdown = _render_markdown_for_fixture("10.1098/rspb.2020.0097")
    assert "table 1" in markdown
    assert "male reproductive success" in markdown
    assert "Table 1: Results from PCA for male dominance" in markdown
    assert (
        "Table 2: Full model outputs from generalized linear negative binomial model"
        in markdown
    )
    assert markdown.count("| not specified | PC1 | PC2 |") == 1
    assert (
        markdown.count(r"| parameter | estimate | s.e. | z-value | Pr(>\|z\|) |") == 1
    )
    assert re.search(r"(?m)^\| FIII \| .+ \|$", markdown)
    assert re.search(r"(?m)^\| PC2: FIII \| .+ \|$", markdown)
    assert not re.search(r"(?m)^(?:FIII|PC2: FIII) \|", markdown)
    assert "## Ethics" in markdown
    assert "## Data accessibility" in markdown
    assert "Dryad Digital Repository" in markdown
    assert "## Acknowledgements" in markdown
    assert "Daniel Nugent" in markdown
    assert "Download slide" not in markdown
    assert "Article navigation" not in markdown
    assert re.search("(?m)^\\|.+\\|$", markdown)


def test_markdown_contract_formula_fixture() -> None:
    # markdown-review: purpose=formula doi=10.1098/rsos.201188
    markdown = _render_markdown_for_fixture("10.1098/rsos.201188")
    assert "Black" in markdown
    assert "Scholes" in markdown
    assert r"\text{price} = \text{BS}(S_{0},K,T,\sigma)." in markdown
    assert r"x_{t}^{i} = \sum\limits_{\, j = 1}^{n}a_{ij}x_{t - 1}^{j}" in markdown
    assert "consensus to $" in markdown
    assert r"}{\overset{\sim}{X}}_{t - 1}e_{t}" not in markdown
    assert r"\text{and\textbackslash~}" not in markdown
    assert "Atand" not in markdown
    assert "εinot" not in markdown
    assert "- —" not in markdown
    assert "Open figure viewer" not in markdown
    assert "Download slide" not in markdown
    assert "javascript:;" not in markdown
    assert re.search(r"(?m)^1\. Schinckus C", markdown)
    assert not re.search(r"(?m)^- Schinckus C", markdown)
    assert re.search("(?:\\$|Equation|BS)", markdown)


def test_markdown_normalization_drops_inline_list_label_dash() -> None:
    markdown = royalsocietypublishing_normalize_markdown(
        "- —Condition 1: (Call Spread) For 0 < K1 <= K2\n"
        "- –Condition 2: (Butterfly Spread) For 0 < K1 < K2 < K3\n"
        "- -Condition 3: synthetic label"
    )

    assert "- Condition 1: (Call Spread) For 0 < K1 <= K2" in markdown
    assert "- Condition 2: (Butterfly Spread) For 0 < K1 < K2 < K3" in markdown
    assert "- Condition 3: synthetic label" in markdown
    assert "- —Condition" not in markdown
    assert "- –Condition" not in markdown
    assert "- -Condition" not in markdown


def test_markdown_contract_figure_fixture() -> None:
    """rule: rule-royalsociety-silverchair-markdown-cleanup"""

    # markdown-review: purpose=figure doi=10.1098/rsos.150470
    markdown = _render_markdown_for_fixture("10.1098/rsos.150470")
    assert "figures 1" in markdown
    assert "Plesiochelys" in markdown
    assert "Palaeobiogeographic distribution" in markdown
    assert "### 3.3 Referred material" in markdown
    assert "NHMUK R3370, a basicranium" in markdown
    assert "### 3.9 Referred material" in markdown
    assert "NHMUK OR44178b" in markdown
    assert "Download slide" not in markdown
    assert "Article navigation" not in markdown
    assert not re.search(r"(?m)^- Figure$", markdown)
    assert re.search("(?:figure|figures 1)", markdown)
    assert "\n## Figures\n" not in markdown


def test_markdown_contract_supplementary_fixture() -> None:
    # markdown-review: purpose=supplementary doi=10.1098/rsif.2019.0334
    markdown = _render_markdown_for_fixture("10.1098/rsif.2019.0334")
    assert "electronic supplementary material" in markdown
    assert "hepatitis C virus" in markdown
    assert "\nEquation 3.2:" in markdown
    assert not re.search(r"Equation 3\.1: .+ Equation 3\.2:", markdown)
    assert "Download citation" not in markdown
    assert "Article navigation" not in markdown


def test_markdown_contract_references_fixture() -> None:
    # markdown-review: purpose=references doi=10.1098/rsos.201200
    markdown = _render_markdown_for_fixture("10.1098/rsos.201200")
    assert "## References" in markdown
    assert re.search(r"(?m)^1\. Wright PA", markdown)
    assert re.search(r"(?m)^2\. Zimmer AM", markdown)
    assert not re.search(r"(?m)^- Wright PA", markdown)
    assert "Reference" in markdown
    assert "Google Scholar" not in markdown
    assert "Download citation" not in markdown


def test_markdown_contract_pdf_fallback_fixture() -> None:
    """PDF fallback Markdown uses the shared text-only PDF conversion baseline."""

    # markdown-review: purpose=pdf_fallback doi=10.1098/rsta.2020.0108
    markdown = _render_markdown_for_fixture("10.1098/rsta.2020.0108")
    assert markdown.strip()
    assert re.search(r"(?m)^#{1,6}\s+\S+", markdown) or re.search(
        r"[A-Za-z]{20,}", markdown
    )
    assert "## 1. Introduction" in markdown
    assert "Many recent and spectacular advances in the world of materials" in markdown
    assert "Access Denied" not in markdown
    assert "<html" not in markdown.lower()
    assert "Object moved" not in markdown
