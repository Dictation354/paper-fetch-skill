from __future__ import annotations
from pathlib import Path
import re
from paper_fetch.providers import _iop_html
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.iop import IopClient
from paper_fetch.tracing import trace_from_markers


IOP_SAMPLE_DOI = "10.1088/1748-9326/ab7d02"
IOP_SAMPLE_LANDING = f"https://iopscience.iop.org/article/{IOP_SAMPLE_DOI}"
IOP_SAMPLE_TITLE = (
    "Quantifying the role of internal variability in the temperature we expect "
    "to observe in the coming decades"
)
IOP_TABLE_FORMULA_DOI = "10.1088/2058-9565/ac3460"
IOP_TABLE_FORMULA_LANDING = (
    f"https://iopscience.iop.org/article/{IOP_TABLE_FORMULA_DOI}"
)
IOP_TABLE_FORMULA_TITLE = "Quantum pattern recognition in photonic circuits"
IOP_PDF_FALLBACK_DOI = "10.1088/1748-9326/aa9f73"
IOP_CURRENT_SUPPLEMENTARY_DOI = "10.1088/2752-5295/ae2d89"
IOP_CURRENT_SUPPLEMENTARY_LANDING = (
    f"https://iopscience.iop.org/article/{IOP_CURRENT_SUPPLEMENTARY_DOI}"
)
IOP_TEST_SIGNED_SUPPLEMENTARY_URL = (
    "https://iop-supplements.example.test/path/erclae2d89supp1.docx"
    "?X-Amz-Signature=test"
)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _golden_fixture_text(doi: str, filename: str) -> str:
    path = (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / doi.replace("/", "_")
        / filename
    )
    return path.read_text(encoding="utf-8", errors="ignore")


def _golden_fixture_bytes(doi: str, filename: str) -> bytes:
    path = (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / doi.replace("/", "_")
        / filename
    )
    return path.read_bytes()


def test_iop_real_article_replay_does_not_promote_figure_controls_or_qr_to_supplementary() -> (
    None
):
    html = _golden_fixture_text(IOP_SAMPLE_DOI, "original.html")

    assets = _iop_html.extract_scoped_html_assets(
        html,
        IOP_SAMPLE_LANDING,
        asset_profile="all",
    )
    index_urls = _iop_html.extract_supplementary_index_urls(
        html,
        IOP_SAMPLE_LANDING,
        doi=IOP_SAMPLE_DOI,
    )

    assert assets
    assert all(asset["kind"] == "figure" for asset in assets)
    assert index_urls == [f"{IOP_SAMPLE_LANDING}/data"]
    assert not any("wechat" in str(asset).lower() for asset in assets)


def test_iop_real_replay_covers_table_and_formula_purposes() -> None:
    html = _golden_fixture_text(IOP_TABLE_FORMULA_DOI, "original.html")
    client = IopClient(None, {})
    markdown, extraction = client.extract_markdown(
        html,
        IOP_TABLE_FORMULA_LANDING,
        metadata={
            "doi": IOP_TABLE_FORMULA_DOI,
            "title": IOP_TABLE_FORMULA_DOI,
        },
    )

    assert markdown.startswith(f"# {IOP_TABLE_FORMULA_TITLE}\n")
    assert f"# {IOP_TABLE_FORMULA_DOI}" not in markdown
    assert extraction["title"] == IOP_TABLE_FORMULA_TITLE
    assert extraction["availability_diagnostics"]["accepted"] is True

    raw_payload = RawFulltextPayload(
        provider="iop",
        source_url=IOP_TABLE_FORMULA_LANDING,
        content_type="text/html",
        body=html.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=IOP_TABLE_FORMULA_LANDING,
            content_type="text/html",
            body=html.encode("utf-8"),
            markdown_text=markdown,
            diagnostics={
                "extraction": extraction,
                "availability_diagnostics": extraction.get("availability_diagnostics"),
            },
        ),
        trace=trace_from_markers(["fulltext:iop_html_ok"]),
        merged_metadata={"doi": IOP_TABLE_FORMULA_DOI, "title": IOP_TABLE_FORMULA_DOI},
    )
    article = client.to_article_model(
        {"doi": IOP_TABLE_FORMULA_DOI, "title": IOP_TABLE_FORMULA_DOI},
        raw_payload,
    )
    article_markdown = article.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    assert f'title: "{IOP_TABLE_FORMULA_TITLE}"' in article_markdown
    assert f'title: "{IOP_TABLE_FORMULA_DOI}"' not in article_markdown
    assert f"# {IOP_TABLE_FORMULA_TITLE}" in article_markdown

    # markdown-review: purpose=table doi=10.1088/2058-9565/ac3460
    assert "Table 1" in markdown
    assert "| Mean" in markdown
    assert re.search(r"\*\*Table 1\.\*\*.*Fidelities achieved", markdown)
    assert "Article metrics" not in markdown

    # markdown-review: purpose=formula doi=10.1088/2058-9565/ac3460
    assert "$$" in markdown
    assert r"\begin{equation}" in markdown
    assert r"\vert {\psi }_{\text{in}}\rangle" in markdown
    assert r"initial state $\vert {\psi }_{\text{I}}\rangle" in markdown
    assert r"initial state \vert {\psi }_{\text{I}}\rangle" not in markdown
    assert "![Formula]" not in markdown
    assert "qstac3460eqn1.gif" not in markdown
    assert "Download PDF" not in markdown

    assets = _iop_html.extract_scoped_html_assets(
        html,
        IOP_TABLE_FORMULA_LANDING,
        asset_profile="body",
    )
    asset_urls = [asset.get("url", "") for asset in assets]
    assert [asset["kind"] for asset in assets] == ["figure", "figure"]
    assert all(asset.get("preview_accepted") is True for asset in assets)
    assert any("qstac3460f1_online.jpg" in url for url in asset_urls)
    assert any("qstac3460f2_online.jpg" in url for url in asset_urls)
    assert any(
        str(asset.get("full_size_url", "")).endswith("qstac3460f1_hr.jpg")
        for asset in assets
    )
    assert any(
        str(asset.get("full_size_url", "")).endswith("qstac3460f2_hr.jpg")
        for asset in assets
    )
    assert not any(
        "qstac3460eqn" in url or "qstac3460ieqn" in url for url in asset_urls
    )


def test_iop_real_pdf_fallback_fixture_records_iop_pdf_source() -> None:
    body = _golden_fixture_bytes(IOP_PDF_FALLBACK_DOI, "original.pdf")
    markdown = _golden_fixture_text(IOP_PDF_FALLBACK_DOI, "extracted.md")

    assert body.startswith(b"%PDF")

    # markdown-review: purpose=pdf_fallback doi=10.1088/1748-9326/aa9f73
    assert 'source: "iop_pdf"' in markdown
    assert "## **Abstract**" in markdown
    assert "Radware Bot Manager" not in markdown
    assert "hCaptcha" not in markdown
