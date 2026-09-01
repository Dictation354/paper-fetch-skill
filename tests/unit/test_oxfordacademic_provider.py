from __future__ import annotations

import re
from pathlib import Path

from tests.golden_criteria import golden_criteria_asset

from paper_fetch.http import HttpTransport
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.provider_catalog import PROVIDER_CATALOG, SOURCE_PROVIDER_MAP
from paper_fetch.providers import _oxfordacademic_html
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from tests.unit._atypon_browser_workflow_provider_support import png_header
from tests.unit._paper_fetch_support import FixtureHtmlTransport, http_response


HTML_DOI = "10.1093/bioinformatics/btaa161"
FIGURE_DOI = "10.1093/bioinformatics/btaa823"
PDF_DOI = "10.1093/bioinformatics/btaa153"


def _render_markdown_for_fixture(doi: str) -> str:
    return golden_criteria_asset(doi, "extracted.md").read_text(
        encoding="utf-8",
        errors="ignore",
    )


def _extract_html_fixture() -> _oxfordacademic_html.OxfordAcademicExtraction:
    html_text = golden_criteria_asset(HTML_DOI, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    return _oxfordacademic_html.extract_markdown(
        html_text,
        "https://academic.oup.com/bioinformatics/article/36/11/3409/5802463",
        metadata={"doi": HTML_DOI},
    )


def test_provider_bundle_is_registered() -> None:
    bundle = provider_bundle("oxfordacademic")

    assert PROVIDER_CATALOG["oxfordacademic"].client_factory_path.endswith(
        "OxfordAcademicClient"
    )
    assert SOURCE_PROVIDER_MAP["oxfordacademic_html"] == "oxfordacademic"
    assert SOURCE_PROVIDER_MAP["oxfordacademic_pdf"] == "oxfordacademic"
    assert bundle.html_rules is not None
    assert bundle.html_rules.name == "oxfordacademic"


def test_provider_helper_extracts_markdown_from_html_fixture() -> None:
    extraction = _extract_html_fixture()

    assert "## Abstract" in extraction.markdown_text
    assert "Table 4" in extraction.markdown_text
    assert "Article metrics" not in extraction.markdown_text
    assert extraction.extracted_assets


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


def test_markdown_contract_structure_fixture() -> None:
    # markdown-review: purpose=structure doi=10.1093/bioinformatics/btaa161
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "## Abstract" in markdown
    assert "## 1 Introduction" in markdown
    assert "Download PDF" not in markdown
    assert "Article metrics" not in markdown


def test_article_html_route_contract_fixture_meets_minimum_body_shape() -> None:
    # route-contract: article_html public article container, metadata and body sections
    html_text = golden_criteria_asset(HTML_DOI, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    extraction = _oxfordacademic_html.extract_markdown(
        html_text,
        "https://academic.oup.com/bioinformatics/article/36/11/3409/5802463",
        metadata={"doi": HTML_DOI},
    )
    assert ".article-body" in html_text or "widget-ArticleFulltext" in html_text
    assert extraction.metadata.get("title") or extraction.metadata.get("doi")
    assert len(extraction.markdown_text) >= 1200
    assert extraction.section_hints
    for blocked in ("challenge page", "access gate only", "site navigation only"):
        assert blocked not in extraction.markdown_text.lower()


def test_markdown_contract_table_fixture() -> None:
    # markdown-review: purpose=table doi=10.1093/bioinformatics/btaa161
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "Table 4" in markdown
    assert "Number of features selected" in markdown
    assert re.search(r"(?m)^\|.+\|$", markdown)
    assert "Google Scholar" not in markdown
    assert "Download Citation" not in markdown


def test_markdown_contract_formula_fixture() -> None:
    # markdown-review: purpose=formula doi=10.1093/bioinformatics/btaa161
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "Equation" in markdown
    assert "Kullback" in markdown
    assert re.search(r"(?:Equation|\$\$|R\^\{2\}|I _\{YP\})", markdown)
    assert "[Formula unavailable]" not in markdown
    assert "Article metrics" not in markdown


def test_oxford_formula_paragraphs_keep_inline_prose_together() -> None:
    extraction = _extract_html_fixture()
    markdown = extraction.markdown_text

    assert "at time\n\nt\n\nfor covariate" not in markdown
    assert "\n\nz, with\n\n" not in markdown
    assert "\n\nB\n\n-spline" not in markdown
    assert "$$" in markdown
    assert "(1)" in markdown
    assert "at time t for covariate vector z, with" in markdown
    assert "cubic B-spline approximation" in markdown


def test_markdown_contract_figure_fixture() -> None:
    # markdown-review: purpose=figure doi=10.1093/bioinformatics/btaa823
    markdown = _render_markdown_for_fixture(FIGURE_DOI)
    assert "Fig. 4" in markdown
    assert "Basic TM on abstracts and full-texts" in markdown
    assert re.search(r"(?:!\[Figure|!\[Image|Fig\.\s*4)", markdown)
    assert "![Formula]" not in markdown
    assert "Article Metrics" not in markdown
    assert "Download Citation" not in markdown
    assert "Badal V.D. et al. (2015)" in markdown
    assert "Text mining for protein docking" in markdown
    assert not re.search(r"\bcitation_[A-Za-z0-9_]+=", markdown)


def test_figure_fixture_stage_asset_contract_is_inline_body_image() -> None:
    markdown = _render_markdown_for_fixture(FIGURE_DOI)
    body_before_references = markdown.split("## References", 1)[0]
    image_match = re.search(
        r"!\[(?:Figure|Image)[^\]]*\]\(([^)]+)\)", body_before_references
    )

    assert not (
        golden_criteria_asset(FIGURE_DOI, "extracted.md").parent / "body_assets"
    ).exists()
    assert image_match is not None
    assert "oup.silverchair-cdn.com" in image_match.group(1)


def test_markdown_contract_supplementary_fixture() -> None:
    # markdown-review: purpose=supplementary doi=10.1093/bioinformatics/btaa161
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "Supplementary data" in markdown
    assert "btaa161_Supplementary_Materials" in markdown
    assert "Download Citation" not in markdown
    assert "Google Scholar" not in markdown


def test_markdown_contract_references_fixture() -> None:
    # markdown-review: purpose=references doi=10.1093/bioinformatics/btaa161
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "## References" in markdown
    assert "Allison" in markdown
    assert "Allison P.D. (1995)" in markdown
    assert "Survival Analysis Using SAS" in markdown
    assert "Google Scholar" not in markdown
    assert "Download Citation" not in markdown
    assert "citation_title=" not in markdown
    assert "citation_author=" not in markdown
    assert "citation_journal_title=" not in markdown
    assert "citation_year=" not in markdown
    assert not re.search(r"\bcitation_[A-Za-z0-9_]+=", markdown)


def test_oxford_references_prefer_visible_html_reference_text() -> None:
    extraction = _extract_html_fixture()
    references = extraction.metadata.get("references")

    assert isinstance(references, list)
    assert len(references) == 43
    first = references[0]
    assert first["label"] == "1."
    assert first["raw"].startswith("Allison P.D. (1995)")
    assert "Survival Analysis Using SAS" in first["raw"]
    assert "citation_title=" not in str(references)
    assert "citation_author=" not in str(references)
    assert not re.search(r"\bcitation_[A-Za-z0-9_]+=", str(references))


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


def test_pdf_fallback_fixture_is_captured_pdf() -> None:
    # fixture-capture: purpose=pdf_fallback doi=10.1093/bioinformatics/btaa153
    body = golden_criteria_asset(PDF_DOI, "original.pdf").read_bytes()

    assert body.startswith(b"%PDF-")
    assert len(body) > 100_000


def test_markdown_contract_pdf_fallback_fixture() -> None:
    # markdown-review: purpose=pdf_fallback doi=10.1093/bioinformatics/btaa153
    markdown = _render_markdown_for_fixture(PDF_DOI)
    assert "MIXnorm: normalizing RNA-seq data from formalin-fixed" in markdown
    assert "## Abstract" in markdown
    assert "MIXnorm" in markdown
    assert "# Untitled Article" not in markdown
    assert "Google Scholar" not in markdown
    assert "View Article Abstract" not in markdown
