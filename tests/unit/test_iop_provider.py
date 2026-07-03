from __future__ import annotations

from pathlib import Path
import re

from paper_fetch import publisher_identity
from paper_fetch.extraction.html.signals import detect_html_access_signals
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    SOURCE_PROVIDER_MAP,
    default_asset_profile_for_provider,
    provider_base_domains,
    provider_html_path_templates,
    provider_pdf_path_templates,
)
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers import _iop_html
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.iop import IopClient
from paper_fetch.quality.html_availability import HtmlQualityAssessor
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


def _iop_article_html() -> str:
    body = " ".join(
        [
            "Internal climate variability can shift observed decadal temperature "
            "trends while forced warming remains detectable across model ensembles."
        ]
        * 50
    )
    return f"""
<html>
  <head>
    <title>{IOP_SAMPLE_TITLE}</title>
    <meta name="citation_title" content="{IOP_SAMPLE_TITLE}" />
    <meta name="citation_author" content="Ada Example" />
    <meta name="citation_pdf_url" content="/article/{IOP_SAMPLE_DOI}/pdf" />
    <meta name="citation_reference" content="citation_journal_title=Example Journal; citation_title=Example meta reference; citation_author=Smith A; citation_publication_date=2020; citation_doi=10.1234/example;" />
  </head>
  <body>
    <header class="iopscience-nav">IOPscience navigation Download PDF</header>
    <main>
      <article id="article">
        <h1>{IOP_SAMPLE_TITLE}</h1>
        <section id="abstracts">
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>This article quantifies how internal variability changes the temperature we expect to observe over the coming decades.</p>
          </section>
        </section>
        <section property="articleBody">
          <h2 class="header-anchor">1. Introduction</h2>
          <p>{body}</p>
          <figure>
            <img src="/article/figure/example.png" alt="Figure 1" />
            <figcaption>Figure 1. Figure 1. Example IOP figure caption. Download figure: Standard image High-resolution image</figcaption>
          </figure>
          <h2 class="header-anchor">2. Results</h2>
          <p>{body}</p>
          <p>Supplementary table 1 is available at stacks.iop.org/ERL/15/054014/mmedia.</p>
          <section data-title="References">
            <h2>References</h2>
            <ol>
              <li>Smith A 2020 Example reference Environmental Research Letters 15 012001.</li>
            </ol>
          </section>
        </section>
      </article>
    </main>
    <aside class="article-metrics">Article metrics Export citation</aside>
  </body>
</html>
"""


def _iop_loaded_article_with_residual_challenge_html() -> str:
    body = " ".join(
        [
            "Observed warming remains detectable while internal variability shifts "
            "the exact decadal sequence of temperatures in model ensembles."
        ]
        * 45
    )
    return f"""
<html>
  <head>
    <title>{IOP_SAMPLE_TITLE}</title>
    <meta name="citation_title" content="{IOP_SAMPLE_TITLE}" />
    <meta name="citation_author" content="Ada Example" />
    <meta name="citation_pdf_url" content="/article/{IOP_SAMPLE_DOI}/pdf" />
    <meta name="citation_reference" content="citation_journal_title=Example Journal; citation_title=Example meta reference; citation_author=Smith A; citation_publication_date=2020; citation_doi=10.1234/example;" />
  </head>
  <body>
    <div class="challenge-residue">
      Radware Bot Manager validate.perfdrive.com confirm you are a human
    </div>
    <main>
      <article>
        <h1>{IOP_SAMPLE_TITLE}</h1>
        <div class="article-content">
          <div class="article-abstract">
            <h2 id="artAbst">Abstract</h2>
            <div class="article-text" itemprop="description">
              <p>This article quantifies the role of internal variability.</p>
            </div>
          </div>
          <p><small>Export citation and abstract</small></p>
          <div itemprop="articleBody" class="wd-jnl-art-full-text article-text">
            <h2 class="header-anchor">1. Introduction</h2>
            <p>{body}</p>
            <h2 class="header-anchor">2. Results</h2>
            <p>{body}</p>
          </div>
        </div>
      </article>
    </main>
  </body>
</html>
"""


def test_iop_provider_bundle_declares_routing_sources_and_browser_runtime() -> None:
    bundle = provider_bundle("iop")
    catalog = PROVIDER_CATALOG["iop"]

    assert bundle.catalog == catalog
    assert catalog.domains == ("iopscience.iop.org",)
    assert catalog.doi_prefixes == ("10.1088/",)
    assert provider_base_domains("iop") == ("iopscience.iop.org",)
    assert provider_html_path_templates("iop") == ("/article/{doi}",)
    assert provider_pdf_path_templates("iop") == ("/article/{doi}/pdf",)
    assert catalog.requires_playwright is True
    assert catalog.requires_browser_runtime is True
    assert default_asset_profile_for_provider("iop") == "body"
    assert SOURCE_PROVIDER_MAP["iop_html"] == "iop"
    assert SOURCE_PROVIDER_MAP["iop_pdf"] == "iop"
    assert bundle.sources == ("iop_html", "iop_pdf")
    assert bundle.html_rules is not None
    assert bundle.html_rules.availability.text_marker_signal_set is not None


def test_iop_provider_identity_matches_domain_publisher_and_doi() -> None:
    assert publisher_identity.infer_provider_from_url(IOP_SAMPLE_LANDING) == "iop"
    assert publisher_identity.infer_provider_from_doi(IOP_SAMPLE_DOI) == "iop"
    assert publisher_identity.infer_provider_from_publisher("IOP Publishing") == "iop"
    assert (
        publisher_identity.infer_provider_from_publisher(
            "Institute of Physics Publishing"
        )
        == "iop"
    )


def test_iop_candidates_cover_article_html_pdf_fallback_and_doi_org() -> None:
    # route-contract: article_html iop_html pdf_fallback iop_pdf 10.1088_1748-9326_ab7d02
    client = IopClient(None, {})
    metadata = {
        "doi": IOP_SAMPLE_DOI,
        "landing_page_url": IOP_SAMPLE_LANDING,
        "fulltext_links": [
            {
                "url": f"https://iopscience.iop.org/article/{IOP_SAMPLE_DOI}/pdf",
                "content_type": "application/pdf",
            }
        ],
    }

    html_candidates = client.html_candidates(IOP_SAMPLE_DOI, metadata)
    pdf_candidates = client.pdf_candidates(IOP_SAMPLE_DOI, metadata)

    assert html_candidates[0] == IOP_SAMPLE_LANDING
    assert f"https://doi.org/{IOP_SAMPLE_DOI}" in html_candidates
    assert f"{IOP_SAMPLE_LANDING}/pdf" in pdf_candidates
    assert pdf_candidates.count(f"{IOP_SAMPLE_LANDING}/pdf") == 1


def test_iop_rejects_radware_hcaptcha_html_challenge() -> None:
    """rule: rule-iop-body-challenge-cleanup"""
    challenge_html = """
    <html><head><title>Radware Bot Manager Captcha</title></head>
    <body>
      We apologize for the inconvenience. Please confirm you are a human.
      <div class="h-captcha" data-sitekey="example"></div>
      validate.perfdrive.com
    </body></html>
    """

    signals = detect_html_access_signals(
        "Radware Bot Manager Captcha",
        challenge_html,
        200,
    )
    assert signals == ["cloudflare_challenge"]

    diagnostics = HtmlQualityAssessor("iop").assess(
        "",
        {"doi": IOP_SAMPLE_DOI},
        html_text=challenge_html,
        title="Radware Bot Manager Captcha",
        final_url=IOP_SAMPLE_LANDING,
        response_status=200,
    )
    assert diagnostics.accepted is False
    assert "iop_radware_challenge" in diagnostics.blocking_fallback_signals
    assert "iop_captcha_challenge" in diagnostics.blocking_fallback_signals


def test_iop_accepts_loaded_article_body_with_residual_challenge_scripts() -> None:
    """rule: rule-iop-body-challenge-cleanup"""
    html = _iop_loaded_article_with_residual_challenge_html()

    diagnostics = HtmlQualityAssessor("iop").assess(
        "",
        {"doi": IOP_SAMPLE_DOI, "title": IOP_SAMPLE_TITLE},
        html_text=html,
        title=IOP_SAMPLE_TITLE,
        final_url=IOP_SAMPLE_LANDING,
        response_status=200,
    )

    assert diagnostics.accepted is True
    assert "cloudflare_challenge" not in diagnostics.hard_negative_signals
    assert "iop_radware_challenge" not in diagnostics.blocking_fallback_signals
    assert "iop_captcha_challenge" not in diagnostics.blocking_fallback_signals
    assert (
        "residual_challenge_outside_body_ignored" in diagnostics.soft_positive_signals
    )

    markdown, extraction = IopClient(None, {}).extract_markdown(
        html,
        IOP_SAMPLE_LANDING,
        metadata={"doi": IOP_SAMPLE_DOI, "title": IOP_SAMPLE_TITLE},
    )

    assert "## Abstract" in markdown
    assert "## 1. Introduction" in markdown
    assert "Radware Bot Manager" not in markdown
    assert "validate.perfdrive.com" not in markdown
    assert "## References" in markdown
    assert "Example meta reference" in markdown
    assert "Export citation" not in str(extraction.get("abstract_text"))
    assert extraction["references"][0]["raw"].startswith("Smith A 2020")
    assert extraction["availability_diagnostics"]["accepted"] is True


def test_iop_extract_markdown_preserves_article_sections_figure_and_references() -> (
    None
):
    """rule: rule-iop-body-challenge-cleanup"""
    markdown, extraction = IopClient(None, {}).extract_markdown(
        _iop_article_html(),
        IOP_SAMPLE_LANDING,
        metadata={"doi": IOP_SAMPLE_DOI, "title": IOP_SAMPLE_TITLE},
    )

    assert f"# {IOP_SAMPLE_TITLE}" in markdown
    assert "## Abstract" in markdown
    assert "## 1. Introduction" in markdown
    assert "Figure 1. Example IOP figure caption." in markdown
    assert "**Figure 1.** **Figure 1.**" not in markdown
    assert "Download figure:" not in markdown
    assert "## References" in markdown
    assert extraction["extracted_authors"] == ["Ada Example"]
    assert extraction["references"][0]["raw"].startswith("Smith A 2020")
    assert extraction["pdf_candidates"] == [f"{IOP_SAMPLE_LANDING}/pdf"]
    assert "Download PDF" not in markdown
    assert "Article metrics" not in markdown
    assert "Export citation" not in markdown

    # markdown-review: purpose=structure doi=10.1088/1748-9326/ab7d02
    assert "## Abstract" in markdown
    assert "Download PDF" not in markdown

    # markdown-review: purpose=figure doi=10.1088/1748-9326/ab7d02
    assert "Figure 1" in markdown
    assert "Article metrics" not in markdown

    # markdown-review: purpose=references doi=10.1088/1748-9326/ab7d02
    assert "## References" in markdown
    assert "Export citation" not in markdown

    # markdown-review: purpose=supplementary doi=10.1088/1748-9326/ab7d02
    assert "stacks.iop.org/ERL/15/054014/mmedia" in markdown
    assert "Download PDF" not in markdown


def test_iop_appendix_figure_caption_match_prevents_duplicate_append() -> None:
    markdown = """
## Appendix:

**Figure** **Figure A.1.** Visualization of four elements in a three-dimensional data cube. In our definition of connectivity these four elements are connected and could form an extreme event.

## References
"""
    caption = (
        "Figure A.1. Figure A.1. Visualization of four elements in a three-dimensional "
        "data cube. In our definition of connectivity these four elements are connected "
        "and could form an extreme event. Download figure: Standard image High-resolution image"
    )

    updated = _iop_html._append_missing_figure_captions(markdown, [caption])

    assert updated == markdown
    assert updated.count("Visualization of four elements") == 1


def test_iop_suppresses_only_non_inline_asset_captions_already_in_markdown() -> None:
    markdown = """
![Figure 1](https://content.cld.iop.org/example/f1_online.jpg)

**Figure 1.** Main figure caption already rendered next to the inline image.

## Appendix:

**Figure** **Figure A.1.** Appendix figure caption already rendered in the appendix text.
"""
    assets = [
        {
            "kind": "figure",
            "heading": "Figure 1",
            "caption": "Figure 1. Main figure caption already rendered next to the inline image.",
            "url": "https://content.cld.iop.org/example/f1_online.jpg",
        },
        {
            "kind": "figure",
            "heading": "Figure A.1",
            "caption": "Figure A.1. Appendix figure caption already rendered in the appendix text.",
            "url": "https://content.cld.iop.org/example/fA1_online.jpg",
        },
    ]

    suppressed = _iop_html.suppress_iop_asset_captions_already_in_markdown(
        assets,
        markdown,
    )

    assert suppressed[0]["caption"] == assets[0]["caption"]
    assert suppressed[1]["caption"] == ""
    assert suppressed[1]["url"].endswith("fA1_online.jpg")


def test_iop_extracts_high_resolution_candidate_from_standard_figure_url() -> None:
    html = """
    <article>
      <figure>
        <img src="https://content.cld.iop.org/journals/1748-9326/19/7/074035/revision2/erlad560bf1_lr.jpg" alt="Figure 1" />
        <figcaption>Figure 1. Example caption.</figcaption>
      </figure>
      <figure>
        <img src="https://content.cld.iop.org/journals/1748-9326/19/7/074035/revision2/erlad560bf2_online.jpg" alt="Figure 2" />
        <figcaption>Figure 2. Example caption.</figcaption>
      </figure>
      <figure>
        <img src="https://example.test/figure3_lr.jpg" alt="Figure 3" />
        <figcaption>Figure 3. Non-IOP image.</figcaption>
      </figure>
    </article>
    """

    assets = _iop_html.extract_scoped_html_assets(
        html,
        IOP_SAMPLE_LANDING,
        asset_profile="body",
    )

    assert assets[0]["url"].endswith("erlad560bf1_lr.jpg")
    assert assets[0]["preview_url"].endswith("erlad560bf1_lr.jpg")
    assert assets[0]["full_size_url"].endswith("erlad560bf1_hr.jpg")
    assert assets[1]["url"].endswith("erlad560bf2_online.jpg")
    assert assets[1]["preview_url"].endswith("erlad560bf2_online.jpg")
    assert assets[1]["full_size_url"].endswith("erlad560bf2_hr.jpg")
    assert "full_size_url" not in assets[2]


def test_iop_real_replay_covers_table_and_formula_purposes() -> None:
    """rule: rule-iop-body-challenge-cleanup"""
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


def test_iop_pdf_fallback_contract_uses_pdf_magic_and_source() -> None:
    # route-contract: pdf_fallback iop_pdf application/pdf PDF magic bytes reject HTML wrapper not a PDF text/html
    body = b"%PDF-1.7\n% IOP PDF fixture\n"
    raw_payload = RawFulltextPayload(
        provider="iop",
        source_url=f"{IOP_SAMPLE_LANDING}/pdf",
        content_type="application/pdf",
        body=body,
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=f"{IOP_SAMPLE_LANDING}/pdf",
            content_type="application/pdf",
            body=body,
            markdown_text="# IOP PDF\n\nBody text",
        ),
        trace=trace_from_markers(["fulltext:iop_pdf_fallback_ok"]),
    )

    assert body.startswith(b"%PDF")
    assert IopClient(None, {}).article_source_for_payload(raw_payload) == "iop_pdf"


def test_iop_abstract_only_and_metadata_only_contract_are_provider_managed() -> None:
    # route-contract: abstract_only metadata_only provider-managed degradation after HTML/PDF failure
    assert "abstract_only" in IopClient.route_order
    assert "metadata_only" in IopClient.route_order
    assert PROVIDER_CATALOG["iop"].provider_managed_abstract_only is True
