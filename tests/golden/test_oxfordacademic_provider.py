from __future__ import annotations
import re
from pathlib import Path
from tests.golden_criteria import golden_criteria_asset
from tests.golden_corpus import (
    build_article_from_fixture,
    golden_corpus_fixture_for_doi,
)
from paper_fetch.http import HttpTransport
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers import _oxfordacademic_html
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from tests.support.captured_images import download_captured_images


HTML_DOI = "10.1093/bioinformatics/btaa161"
FIGURE_DOI = "10.1093/bioinformatics/btaa823"
PDF_DOI = "10.1093/bioinformatics/btaa153"


def _render_markdown_for_fixture(doi: str) -> str:
    # Concrete contracts must exercise current HTML/PDF extraction, not a snapshot.
    return build_article_from_fixture(
        golden_corpus_fixture_for_doi(doi)
    ).to_ai_markdown(include_refs="all", asset_profile="all", max_tokens="full_text")


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


def test_provider_helper_extracts_markdown_from_html_fixture() -> None:
    extraction = _extract_html_fixture()

    assert "## Abstract" in extraction.markdown_text
    assert "Table 4" in extraction.markdown_text
    assert "Article metrics" not in extraction.markdown_text
    assert extraction.extracted_assets


def test_html_fixture_localizes_all_preview_images_without_duplicates(
    tmp_path: Path,
) -> None:
    source_url = "https://academic.oup.com/bioinformatics/article/37/4/497/5909988"
    html_text = golden_criteria_asset(FIGURE_DOI, "original.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    extraction = _oxfordacademic_html.extract_markdown(
        html_text, source_url, metadata={"doi": FIGURE_DOI}, asset_profile="body"
    )
    figures = [
        asset for asset in extraction.extracted_assets if asset["kind"] == "figure"
    ]
    assert len(figures) == 9
    downloaded_assets = download_captured_images(FIGURE_DOI, figures, tmp_path)
    raw_payload = RawFulltextPayload(
        provider="oxfordacademic",
        source_url=source_url,
        content_type="text/html",
        body=html_text.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.metadata,
            extracted_assets=extraction.extracted_assets,
        ),
    )

    article = OxfordAcademicClient(HttpTransport(), {}).to_article_model(
        extraction.metadata, raw_payload, downloaded_assets=downloaded_assets
    )
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )

    body = rendered.split("## References", 1)[0]
    for number, asset in enumerate(downloaded_assets, 1):
        assert asset["preview_url"] not in rendered
        assert f"![Figure {number}]({asset['path']})" in body
        assert rendered.count(f"]({asset['path']})") == 1


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
    markdown = _extract_html_fixture().markdown_text
    assert "Table 4" in markdown
    assert "Number of features selected" in markdown
    # Original btaa161-T4: quantitative and dichotomous feature counts.
    compact = re.sub(r"\s+", " ", markdown)
    assert (
        r"| Data type . / Dataset . | Quantitative . / ${\hat{\chi}}_{\text{PO}}^{2}$ . | Quantitative . / CON . | Dichotomous . / ${\hat{\chi}}_{\text{PO}}^{2}$ . | Dichotomous . / CON . |"
        in compact
    )
    assert "| 1 | 1097 | 99 | 318 | 0 |" in compact
    assert "| 5 | 758 | 1473 | 4099 | 323 |" in compact
    assert re.search(r"(?m)^\|.+\|$", markdown)
    assert "Google Scholar" not in markdown
    assert "Download Citation" not in markdown


def test_markdown_contract_formula_fixture() -> None:
    # markdown-review: purpose=formula doi=10.1093/bioinformatics/btaa161
    markdown = _extract_html_fixture().markdown_text
    # original.html jumplink-e1: baseline subscript is the letter o.
    equation = markdown.split("$$", 2)[1]
    assert r"λ(t|z) = {λ}_{o}(t)\text{exp}(\beta′z)" in equation
    assert r"Λ(t|z) = {Λ}_{o}(t)\text{exp}(\beta′z)" in equation
    assert "$$\n(1)\nwhere t > 0" in markdown
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


def test_oxford_supplements_exclude_body_pdf_and_dedupe_before_download() -> None:
    from bs4 import BeautifulSoup

    extraction = _extract_html_fixture()
    supplements = [
        a for a in extraction.extracted_assets if a["kind"] == "supplementary"
    ]
    assert len(supplements) == 1
    soup = BeautifulSoup(
        golden_criteria_asset(HTML_DOI, "original.html").read_text(), "lxml"
    )
    assert supplements[0]["url"] == soup.select_one(".dataSuppLink a")["href"]
    assert supplements[0]["heading"] == "btaa161_Supplementary_Materials"
