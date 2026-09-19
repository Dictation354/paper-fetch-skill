from __future__ import annotations
import tempfile
from pathlib import Path
from unittest import mock
from bs4 import BeautifulSoup
from paper_fetch.provider_catalog import PROVIDER_CATALOG, SOURCE_PROVIDER_MAP
from paper_fetch.http import RequestFailure
from paper_fetch.providers import _annualreviews_html, browser_runtime
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.annualreviews import AnnualreviewsClient
from paper_fetch.providers.browser_workflow.profile import (
    BrowserWorkflowBootstrapResult,
)
from tests.support._atypon_browser_workflow_provider_support import (
    AssetTransport,
    _typed_raw_payload,
    png_header,
)
from tests.support._browser_workflow_deps import install_browser_workflow_deps


HTML_DOI = "10.1146/annurev-control-030123-013355"
REFERENCES_DOI = "10.1146/annurev-environ-102511-084654"
PDF_FALLBACK_DOI = "10.1146/annurev-med-120811-171056"
FORMULA_DOI = "10.1146/annurev-neuro-062111-150343"
SUPPLEMENTARY_DOI = "10.1146/annurev-neuro-062111-150343"
HTML_SOURCE_URL = f"https://www.annualreviews.org/content/journals/{HTML_DOI}"
EMPTY_SHELL_DOI = "10.1146/annurev.pp.19.060168.001235"


def _runtime_config(tmpdir: str, doi: str) -> browser_runtime.BrowserRuntimeConfig:
    tmp = Path(tmpdir)
    return browser_runtime.BrowserRuntimeConfig(
        provider="annualreviews",
        doi=doi,
        artifact_dir=tmp / "artifacts",
        headless=True,
        user_agent="paper-fetch-test/1",
    )


def test_provider_bundle_round_trip() -> None:
    bundle = provider_bundle("annualreviews")
    assert bundle.catalog.name == "annualreviews"
    assert bundle.catalog.display_name == "Annual Reviews"
    assert bundle.html_rules is not None
    assert bundle.html_rules.name == "annualreviews"
    assert SOURCE_PROVIDER_MAP["annualreviews_html"] == "annualreviews"
    assert SOURCE_PROVIDER_MAP["annualreviews_pdf"] == "annualreviews"


def test_provider_catalog_is_readable() -> None:
    assert PROVIDER_CATALOG["annualreviews"].name == "annualreviews"
    assert any(
        route.browser_required or route.browser_optional
        for route in PROVIDER_CATALOG["annualreviews"].routes
    )


def test_landing_html_and_article_html_candidates_cover_manifest_route() -> None:
    # route-contract: landing_html article_html annualreviews_html 10.1146_annurev-control-030123-013355
    client = AnnualreviewsClient(None, {})
    candidates = client.html_candidates(
        HTML_DOI,
        {"landing_page_url": HTML_SOURCE_URL},
    )

    assert candidates[0] == HTML_SOURCE_URL
    assert f"https://www.annualreviews.org/content/journals/{HTML_DOI}" in candidates
    assert f"https://www.annualreviews.org/doi/{HTML_DOI}" in candidates
    assert f"https://doi.org/{HTML_DOI}" in candidates


def test_abstract_only_and_metadata_only_contract_are_provider_managed() -> None:
    # route-contract: abstract_only metadata_only provider-managed degradation after HTML/PDF failure
    assert "abstract_only" in AnnualreviewsClient.route_order
    assert "metadata_only" in AnnualreviewsClient.route_order
    assert PROVIDER_CATALOG["annualreviews"].provider_managed_abstract_only is True


def test_empty_shell_html_failure_continues_to_annualreviews_pdf_fallback() -> None:
    client = AnnualreviewsClient(None, {})
    source_url = f"https://www.annualreviews.org/content/journals/{EMPTY_SHELL_DOI}"
    pdf_url = f"https://www.annualreviews.org/doi/pdf/{EMPTY_SHELL_DOI}"
    pdf_payload = _typed_raw_payload(
        provider="annualreviews",
        source_url=pdf_url,
        content_type="application/pdf",
        body=b"%PDF-1.7\n% test payload",
        route="pdf_fallback",
        markdown_text="# Transpiration and Leaf Temperature\n\n## Body\n\n"
        + ("Recovered PDF body text. " * 100),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        runtime = _runtime_config(tmpdir, EMPTY_SHELL_DOI)
        bootstrap = BrowserWorkflowBootstrapResult(
            normalized_doi=EMPTY_SHELL_DOI,
            runtime=runtime,
            landing_page_url=source_url,
            html_candidates=[source_url],
            pdf_candidates=[pdf_url],
            html_failure_reason="insufficient_body",
            html_failure_message="HTML extraction did not produce enough article body text.",
        )
        mocked_pdf = mock.Mock(return_value=pdf_payload)
        install_browser_workflow_deps(
            client,
            bootstrap_browser_workflow=mock.Mock(return_value=bootstrap),
            fetch_seeded_browser_pdf_payload=mocked_pdf,
        )

        result = client.fetch_raw_fulltext(
            EMPTY_SHELL_DOI,
            {
                "doi": EMPTY_SHELL_DOI,
                "title": "Transpiration and Leaf Temperature",
                "landing_page_url": source_url,
            },
        )

    mocked_pdf.assert_called_once()
    assert mocked_pdf.call_args.kwargs["html_failure_reason"] == "insufficient_body"
    assert result is pdf_payload
    assert client.article_source_for_payload(result) == "annualreviews_pdf"


def test_annualreviews_table_uses_shared_span_and_header_normalization() -> None:
    soup = BeautifulSoup(
        """
<div class="table-container">
  <table class="html-fulltext-inline-table">
    <thead>
      <tr><th rowspan="2">Region</th><th colspan="2">Period</th></tr>
      <tr><th>Mean</th><th>Trend</th></tr>
    </thead>
    <tbody>
      <tr><td rowspan="2">Asia</td><td>10</td><td>+1</td></tr>
      <tr><td>11</td><td>+2</td></tr>
    </tbody>
  </table>
  <div class="tabFoot"><p>Source note.</p></div>
</div>
""",
        "html.parser",
    )
    table_container = soup.select_one(".table-container")
    table = soup.select_one("table")
    assert table_container is not None
    assert table is not None

    markdown = _annualreviews_html._markdown_table_block(table, table_container)

    assert "| Region | Period / Mean | Period / Trend |" in markdown
    assert "| Asia" in markdown
    assert markdown.count("| Asia") == 2
    assert "Source note." in markdown


def test_annualreviews_asset_extraction_promotes_largest_srcset_rendition() -> None:
    preview_url = "https://www.annualreviews.org/figure-preview.png"
    original_url = "https://www.annualreviews.org/figure-original.png"
    html = f"""
    <html><body><div id="itemFullTextId">
      <div class="articleSection">
        <div class="sectionDivider"><div class="tl-main-part title">Results</div></div>
        <p>{"Annual Reviews body text. " * 100}</p>
        <figure id="fig1">
          <img src="{preview_url}" srcset="{preview_url} 320w, {original_url} 1600w">
          <figcaption>Figure 1. Example.</figcaption>
        </figure>
      </div>
    </div></body></html>
    """

    assets = _annualreviews_html.extract_scoped_html_assets(
        html,
        HTML_SOURCE_URL,
        asset_profile="body",
    )

    figure = next(asset for asset in assets if asset["kind"] == "figure")
    assert figure["full_size_url"] == original_url


def test_download_related_assets_fetches_annualreviews_body_figure() -> None:
    """asset-download-contract: provider=annualreviews"""

    figure_url = (
        "https://www.annualreviews.org/docserver/fulltext/control/8/1/as801.f1.png"
    )
    html = f"""
<html><body>
  <div id="itemFullTextId">
    <div class="articleSection">
      <div class="sectionDivider"><div class="tl-main-part title"><a>1. Results</a></div></div>
      <p>{"Annual Reviews body text " * 80}</p>
      <div class="figure html-fulltext-responsive-figure" id="f1">
        <div class="caption"><span class="label">Figure 1</span> Annual Reviews figure caption.</div>
        <div class="image"><a class="media-link" href="{figure_url}"><img src="{figure_url}" alt="Figure 1" /></a></div>
      </div>
    </div>
  </div>
</body></html>
"""
    image_body = png_header(640, 480)
    client = AnnualreviewsClient(
        transport=AssetTransport(
            {
                ("GET", figure_url): RequestFailure(
                    403,
                    "Browser session required.",
                    url=figure_url,
                )
            }
        ),
        env={},
    )
    shared_fetcher = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": image_body,
            "url": figure_url,
        }
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_payload = _typed_raw_payload(
            provider="annualreviews",
            source_url=HTML_SOURCE_URL,
            content_type="text/html",
            body=html.encode("utf-8"),
            route="html",
            markdown_text="# Annual Reviews Figure\n\n## Results\n\n"
            + ("Body text " * 120),
            browser_context_seed={},
        )
        mocked_builder = mock.Mock(return_value=shared_fetcher)
        install_browser_workflow_deps(
            client,
            load_runtime_config=mock.Mock(
                return_value=_runtime_config(tmpdir, HTML_DOI)
            ),
            ensure_runtime_ready=mock.Mock(),
            _build_shared_browser_image_fetcher=mocked_builder,
        )

        result = client.download_related_assets(
            HTML_DOI,
            {"doi": HTML_DOI, "title": "Annual Reviews Figure"},
            raw_payload,
            Path(tmpdir),
            asset_profile="body",
        )
        saved_path = Path(result["assets"][0]["path"])
        saved_exists = saved_path.is_file()
        saved_bytes = saved_path.read_bytes()

    mocked_builder.assert_called_once()
    shared_fetcher.assert_called_once()
    assert shared_fetcher.call_args.args[0] == figure_url
    assert result["asset_failures"] == []
    assert len(result["assets"]) == 1
    assert result["assets"][0]["kind"] == "figure"
    assert result["assets"][0]["downloaded_bytes"] == len(image_body)
    assert saved_exists
    assert saved_bytes == image_body
