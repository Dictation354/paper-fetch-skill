from __future__ import annotations
import tempfile
from pathlib import Path
from unittest import mock
import pytest
from bs4 import BeautifulSoup
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
from tests.support._atypon_browser_workflow_provider_support import (
    AssetTransport,
    _typed_raw_payload,
    png_header,
)
from tests.support._browser_workflow_deps import install_browser_workflow_deps
from tests.support._paper_fetch_support import (
    fulltext_pdf_bytes,
)


@pytest.mark.parametrize(
    "source_url",
    [
        "https://royalsocietypublishing.org/article/example?view=full#old",
        "",
        "file:///article.html",
    ],
)
def test_section_links_use_source_heading_ids_without_rewriting_other_links(source_url):
    html = """
    <div class="article-body">
      <h2 id="123" data-legacyid="s2">2 Methods</h2>
      <h3 data-legacyid="s3">No source ID</h3>
      <p><a href="#s2">Legacy section</a> <a href="#123">Current section</a>
      <a href="#s3">Unresolved section</a> <a href="#figure1">Figure</a>
      <a href="/article/other#s2">Another article</a>
      <a href="https://example.org/#s2">External</a></p>
      <figure id="figure1">Caption</figure>
    </div>
    """
    rendered_html = _royalsocietypublishing_html._markdown_render_html(html, source_url)
    links = [a["href"] for a in BeautifulSoup(rendered_html, "lxml").select("a")]
    expected_sections = (
        ["https://royalsocietypublishing.org/article/example?view=full#123"] * 2
        if source_url.startswith("https:")
        else ["#s2", "#123"]
    )
    assert links == [
        *expected_sections,
        "#s3",
        "#figure1",
        "/article/other#s2",
        "https://example.org/#s2",
    ]


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


def _runtime_config(tmpdir: str, doi: str) -> browser_runtime.BrowserRuntimeConfig:
    tmp = Path(tmpdir)
    return browser_runtime.BrowserRuntimeConfig(
        provider="royalsocietypublishing",
        doi=doi,
        artifact_dir=tmp / "artifacts",
        headless=True,
        user_agent="paper-fetch-test/1",
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
    assert any(
        route.browser_required or route.browser_optional
        for route in PROVIDER_CATALOG["royalsocietypublishing"].routes
    )


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


def test_metadata_only_route_contract_is_service_fallback_after_provider_failure(
    tmp_path, monkeypatch
) -> None:
    # Mechanism evidence: real provider + service, injected HTML/PDF failures.
    # No original Royal Society rejection response is claimed by this test.
    from paper_fetch import service
    from tests.support._paper_fetch_support import FixtureProvider, fetch_paper_model

    doi = "10.1098/rsta.2020.0108"
    landing = f"https://royalsocietypublishing.org/doi/{doi}"
    client = RoyalsocietypublishingClient(AssetTransport({}), {})
    html = mock.Mock(
        side_effect=browser_runtime.BrowserRuntimeFailure(
            "forced_stop", "HTML route did not expose full text."
        )
    )
    pdf = mock.Mock(
        side_effect=browser_workflow.PdfFallbackFailure(
            "downloaded_file_not_pdf",
            "Royal Society PDF candidate returned an HTML wrapper.",
        )
    )
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(return_value=_runtime_config(str(tmp_path), doi)),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=html,
        fetch_seeded_browser_pdf_payload=pdf,
    )
    monkeypatch.setattr(
        service,
        "resolve_paper",
        lambda *args, **kwargs: service.ResolvedQuery(
            query=doi,
            query_kind="doi",
            doi=doi,
            landing_url=landing,
            provider_hint="royalsocietypublishing",
            confidence=1.0,
        ),
    )
    metadata = {
        "doi": doi,
        "title": "Royal Society fallback evidence",
        "landing_page_url": landing,
        "authors": [],
        "references": [],
        "fulltext_links": [],
    }
    failure = []
    original_fetch = client.fetch_raw_fulltext

    def capture_failure(*args, **kwargs):
        try:
            return original_fetch(*args, **kwargs)
        except ProviderFailure as exc:
            failure.append(exc)
            raise

    monkeypatch.setattr(client, "fetch_raw_fulltext", capture_failure)
    article = fetch_paper_model(
        doi,
        allow_downloads=False,
        clients={
            "royalsocietypublishing": client,
            "crossref": FixtureProvider(metadata=metadata),
        },
    )
    html.assert_called_once()
    pdf.assert_called_once()
    assert len(failure) == 1
    assert failure[0].code == "no_result"
    assert any(event.code == "forced_stop" for event in failure[0].trace)
    assert "HTML wrapper" in failure[0].message
    assert article.source == "crossref_meta"
    assert article.quality.content_kind == "metadata_only"
    assert article.quality.has_fulltext is False
    assert "fulltext:royalsocietypublishing_fail" in article.quality.source_trail
    assert "fallback:metadata_only" in article.quality.source_trail


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
