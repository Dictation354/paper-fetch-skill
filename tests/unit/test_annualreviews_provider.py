from __future__ import annotations

import re
import tempfile
from pathlib import Path
from unittest import mock

from bs4 import BeautifulSoup

from paper_fetch.provider_catalog import PROVIDER_CATALOG, SOURCE_PROVIDER_MAP
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.http import RequestFailure
from paper_fetch.providers import _annualreviews_html, browser_runtime
from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.annualreviews import AnnualreviewsClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.browser_workflow.profile import (
    BrowserWorkflowBootstrapResult,
)
from paper_fetch.tracing import trace_from_markers
from tests.block_fixtures import block_asset
from tests.golden_corpus import GoldenCorpusFixture, build_article_from_fixture
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.unit._atypon_browser_workflow_provider_support import (
    AssetTransport,
    _typed_raw_payload,
    png_header,
)
from tests.unit._browser_workflow_deps import install_browser_workflow_deps


HTML_DOI = "10.1146/annurev-control-030123-013355"
REFERENCES_DOI = "10.1146/annurev-environ-102511-084654"
PDF_FALLBACK_DOI = "10.1146/annurev-med-120811-171056"
FORMULA_DOI = "10.1146/annurev-neuro-062111-150343"
SUPPLEMENTARY_DOI = "10.1146/annurev-neuro-062111-150343"
HTML_SOURCE_URL = f"https://www.annualreviews.org/content/journals/{HTML_DOI}"
EMPTY_SHELL_DOI = "10.1146/annurev.pp.19.060168.001235"


def _fixture_source_url(doi: str) -> str:
    sample = golden_criteria_sample_for_doi(doi)
    return str(sample.get("source_url") or sample.get("landing_url") or "")


def _render_markdown_for_fixture(doi: str) -> str:
    if doi == PDF_FALLBACK_DOI:
        pdf_path = golden_criteria_asset(doi, "original.pdf")
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=_fixture_source_url(doi),
            final_url=_fixture_source_url(doi),
            pdf_bytes=pdf_path.read_bytes(),
        )
        return pdf_result.markdown_text

    html = golden_criteria_asset(doi, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    markdown, _extraction = AnnualreviewsClient(None, {}).extract_markdown(
        html,
        _fixture_source_url(doi),
        metadata={"doi": doi, "title": ""},
    )
    return markdown


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


def test_pdf_fallback_contract_uses_pdf_magic_and_annualreviews_pdf_source() -> None:
    # route-contract: pdf_fallback annualreviews_pdf application/pdf PDF magic bytes reject HTML wrapper not a PDF text/html
    body = golden_criteria_asset(PDF_FALLBACK_DOI, "original.pdf").read_bytes()
    raw_payload = RawFulltextPayload(
        provider="annualreviews",
        source_url=f"https://www.annualreviews.org/doi/pdf/{PDF_FALLBACK_DOI}",
        content_type="application/pdf",
        body=body,
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=f"https://www.annualreviews.org/doi/pdf/{PDF_FALLBACK_DOI}",
            content_type="application/pdf",
            body=body,
            markdown_text="# Annual Reviews PDF\n\nBody text",
        ),
        trace=trace_from_markers(["fulltext:annualreviews_pdf_fallback_ok"]),
    )

    assert body.startswith(b"%PDF")
    assert (
        AnnualreviewsClient(None, {}).article_source_for_payload(raw_payload)
        == "annualreviews_pdf"
    )


def test_abstract_only_and_metadata_only_contract_are_provider_managed() -> None:
    # route-contract: abstract_only metadata_only provider-managed degradation after HTML/PDF failure
    assert "abstract_only" in AnnualreviewsClient.route_order
    assert "metadata_only" in AnnualreviewsClient.route_order
    assert PROVIDER_CATALOG["annualreviews"].provider_managed_abstract_only is True


def test_real_empty_shell_does_not_promote_page_chrome_to_fulltext() -> None:
    html = block_asset(EMPTY_SHELL_DOI, "raw.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    source_url = f"https://www.annualreviews.org/content/journals/{EMPTY_SHELL_DOI}"

    (
        article_html,
        _title,
        _container_text_length,
        _section_hints,
        _abstract_sections,
        container_evidence,
    ) = _annualreviews_html._cleaned_article_html(html, source_url)

    assert container_evidence.selector == "main"
    assert container_evidence.scope == "page"
    assert container_evidence.synthetic is True
    assert "Most Read This Month" not in article_html
    assert "Most Cited" not in article_html
    assert (
        "untrusted_article_container"
        in _annualreviews_html.blocking_fallback_signals(html)
    )
    try:
        AnnualreviewsClient(None, {}).extract_markdown(
            html,
            source_url,
            metadata={"doi": EMPTY_SHELL_DOI},
        )
    except HtmlExtractionFailure as exc:
        assert exc.reason == "insufficient_body"
    else:
        raise AssertionError("Annual Reviews empty shell was accepted as full text")


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


def test_markdown_contract_structure_fixture() -> None:
    # markdown-review: purpose=structure doi=10.1146/annurev-control-030123-013355
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "## Abstract" in markdown
    assert "## References" in markdown
    assert re.search(r"(?m)^1\. Shah D, Yang B, Kriegman S", markdown)
    assert not re.search(r"(?m)^- Shah D, Yang B, Kriegman S", markdown)
    assert "Article metrics loading..." not in markdown
    assert "Download as PowerPoint" not in markdown


def test_markdown_contract_table_fixture() -> None:
    # markdown-review: purpose=table doi=10.1146/annurev-control-030123-013355
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "## Table 1" in markdown
    assert "## Table 2" in markdown
    assert (
        "| Reference | Soft, rigid, or hybrid? a | DOFs for SC b | "
        "Open-loop control c | Closed-loop control d |"
    ) in markdown
    assert "| Hwang et al. (31) e | Hybrid | 1 | Shape and gait f | NA |" in markdown
    assert "Reference\nSoft, rigid, or hybrid?" not in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown


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


def test_markdown_contract_formula_fixture() -> None:
    # markdown-review: purpose=formula doi=10.1146/annurev-neuro-062111-150343
    markdown = _render_markdown_for_fixture(FORMULA_DOI)
    assert (
        "The NMDA spike as a hallmark of electrogenesis in thin dendrites." in markdown
    )
    assert "I-V curve" in markdown
    assert "g max" in markdown
    assert "Na<sup>+</sup>" in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown


def test_markdown_contract_supplementary_fixture() -> None:
    # markdown-review: purpose=supplementary doi=10.1146/annurev-neuro-062111-150343
    markdown = _render_markdown_for_fixture(SUPPLEMENTARY_DOI)
    assert "Supplemental Figure 1" in markdown
    assert "Supplemental Videos 1\u20134" in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown


def test_markdown_contract_figure_fixture() -> None:
    # markdown-review: purpose=figure doi=10.1146/annurev-control-030123-013355
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "Figure" in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown
    assert re.search(r"(?:!\[Figure|\*\*Figure|Figure\s+\d+)", markdown)


def test_markdown_contract_references_fixture() -> None:
    # markdown-review: purpose=references doi=10.1146/annurev-environ-102511-084654
    markdown = _render_markdown_for_fixture(REFERENCES_DOI)
    assert "## References" in markdown
    assert re.search(r"(?m)^1\. Gladwell M\. 2000\.", markdown)
    assert re.search(r"(?m)^2\. Grodzins M\. 1957\.", markdown)
    assert "Gladwell M. 1. 2000" not in markdown
    assert not re.search(r"(?m)^- Gladwell M\.", markdown)
    assert "Reference" in markdown
    assert "Google Scholar" not in markdown
    assert "Related Articles from Annual Reviews" not in markdown


def test_markdown_contract_pdf_fallback_fixture() -> None:
    # markdown-review: purpose=pdf_fallback doi=10.1146/annurev-med-120811-171056
    markdown = _render_markdown_for_fixture(PDF_FALLBACK_DOI)
    assert "#" in markdown
    assert "Access Denied" not in markdown


def test_extracts_authors_references_and_body_figure_assets() -> None:
    html = golden_criteria_asset(HTML_DOI, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    markdown, extraction = AnnualreviewsClient(None, {}).extract_markdown(
        html,
        HTML_SOURCE_URL,
        metadata={"doi": HTML_DOI, "title": ""},
    )

    assert extraction["extracted_authors"] == [
        "Stephanie J. Woodman",
        "Rebecca Kramer-Bottiglio",
    ]
    assert len(extraction["references"]) >= 100
    assert len(extraction["extracted_assets"]) >= 5
    assert "![Figure" in markdown


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


def test_article_model_uses_extracted_html_title_instead_of_doi_placeholder() -> None:
    html = golden_criteria_asset(HTML_DOI, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    client = AnnualreviewsClient(None, {})
    markdown, extraction = client.extract_markdown(
        html,
        HTML_SOURCE_URL,
        metadata={"doi": HTML_DOI, "title": HTML_DOI},
    )
    raw_payload = RawFulltextPayload(
        provider="annualreviews",
        source_url=HTML_SOURCE_URL,
        content_type="text/html",
        body=html.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=HTML_SOURCE_URL,
            content_type="text/html",
            body=html.encode("utf-8"),
            markdown_text=markdown,
            diagnostics={
                "extraction": extraction,
                "availability_diagnostics": extraction.get("availability_diagnostics"),
            },
        ),
        trace=trace_from_markers(["fulltext:annualreviews_html_ok"]),
    )

    article = client.to_article_model(
        {"doi": HTML_DOI, "title": HTML_DOI, "authors": []},
        raw_payload,
    )
    rendered = article.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )

    title = (
        "Stretchable Shape Sensing and Computation for General Shape-Changing Robots"
    )
    assert article.metadata.title == title
    assert f'title: "{title}"' in rendered
    assert f"# {title}" in rendered
    assert f"## {title}" not in rendered


def test_golden_replay_rewrites_downloaded_figure_assets_to_local_paths() -> None:
    sample = golden_criteria_sample_for_doi(HTML_DOI)
    article = build_article_from_fixture(
        GoldenCorpusFixture(sample_id=str(sample["sample_id"]), sample=sample)
    )
    markdown = article.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    local_asset = (
        "tests/fixtures/golden_criteria/10.1146_annurev-control-030123-013355/"
        "body_assets/annualreviews-figure-1.png"
    )

    assert local_asset in markdown
    assert (
        "https://www.annualreviews.org/docserver/fulltext/control/8/1/as801.f1.png"
        not in markdown
    )
    assert Path(local_asset).is_file()


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
