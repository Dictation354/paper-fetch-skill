from __future__ import annotations

from unittest import mock

from paper_fetch import publisher_identity
from paper_fetch.providers import _acs_html
from paper_fetch.providers.browser_runtime.backends import camoufox as camoufox_backend
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    default_asset_profile_for_provider,
    provider_base_domains,
    provider_html_path_templates,
    provider_pdf_path_templates,
)
from paper_fetch.providers._atypon_browser_workflow_profiles import (
    build_html_candidates,
    build_pdf_candidates,
    publisher_profile,
)
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.acs import AcsClient
from paper_fetch.providers.atypon_browser_workflow import (
    extract_atypon_browser_workflow_markdown,
)
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from paper_fetch.providers.browser_workflow import BrowserWorkflowClient
from paper_fetch.providers.browser_workflow.fetchers.readiness import (
    atypon_body_ready_selectors,
)
from tests.golden_criteria import golden_criteria_asset


ACS_SAMPLE_DOI = "10.1021/acsomega.4c03987"
ACS_SAMPLE_LANDING = f"https://pubs.acs.org/doi/{ACS_SAMPLE_DOI}"
ACS_FORMULA_DOI = "10.1021/acsomega.3c06992"


def test_acs_asset_extraction_promotes_largest_srcset_rendition() -> None:
    preview_url = "https://acs.example/figure-preview.png"
    original_url = "https://acs.example/figure-original.png"
    assets = _acs_html.scoped_asset_extractor(
        f"""
        <figure id="fig1">
          <img src="{preview_url}" srcset="{preview_url} 320w, {original_url} 1600w">
          <figcaption>Figure 1. Example.</figcaption>
        </figure>
        """,
        ACS_SAMPLE_LANDING,
        asset_profile="body",
    )

    figure = next(asset for asset in assets if asset["kind"] == "figure")
    assert figure["full_size_url"] == original_url


def test_acs_provider_bundle_declares_routing_and_browser_workflow() -> None:
    bundle = provider_bundle("acs")
    catalog = PROVIDER_CATALOG["acs"]

    assert bundle.catalog == catalog
    assert catalog.domains == ("www.acs.org", "pubs.acs.org", "acs.org")
    assert catalog.doi_prefixes == ("10.1021/",)
    assert catalog.base_domains == ("pubs.acs.org",)
    assert any(
        route.browser_required or route.browser_optional for route in catalog.routes
    )
    assert default_asset_profile_for_provider("acs") == "body"
    assert bundle.sources == ("acs",)
    assert bundle.html_rules is not None
    assert bundle.html_rules.availability.no_signals is True


def test_acs_provider_candidates_use_acs_publications_base_host() -> None:
    assert provider_base_domains("acs") == ("pubs.acs.org",)
    assert provider_html_path_templates("acs") == ("/doi/full/{doi}", "/doi/{doi}")
    assert provider_pdf_path_templates("acs") == (
        "/doi/epdf/{doi}",
        "/doi/pdf/{doi}",
        "/doi/pdf/{doi}?download=true",
    )
    assert build_html_candidates("acs", ACS_SAMPLE_DOI)[:2] == [
        f"https://pubs.acs.org/doi/full/{ACS_SAMPLE_DOI}",
        ACS_SAMPLE_LANDING,
    ]
    assert build_pdf_candidates("acs", ACS_SAMPLE_DOI, None)[:3] == [
        f"https://pubs.acs.org/doi/epdf/{ACS_SAMPLE_DOI}",
        f"https://pubs.acs.org/doi/pdf/{ACS_SAMPLE_DOI}",
        f"https://pubs.acs.org/doi/pdf/{ACS_SAMPLE_DOI}?download=true",
    ]


def test_acs_provider_identity_matches_domain_publisher_and_doi() -> None:
    assert publisher_identity.infer_provider_from_url(ACS_SAMPLE_LANDING) == "acs"
    assert (
        publisher_identity.infer_provider_from_url("https://www.acs.org/pressroom.html")
        == "acs"
    )
    assert (
        publisher_identity.infer_provider_from_publisher("American Chemical Society")
        == "acs"
    )
    assert publisher_identity.infer_provider_from_doi(ACS_SAMPLE_DOI) == "acs"


def test_acs_browser_client_profile_and_author_fallback() -> None:
    client = AcsClient(transport=None, env={})
    html = """
    <html><head>
      <meta name="citation_author" content="Ada Lovelace" />
      <meta name="citation_author" content="Grace Hopper" />
    </head><body></body></html>
    """

    assert isinstance(client, BrowserWorkflowClient)
    assert client.profile.name == "acs"
    assert client.article_source() == "acs"
    assert client.provider_label() == "ACS"
    assert (
        client.html_candidates(
            ACS_SAMPLE_DOI, {"landing_page_url": ACS_SAMPLE_LANDING}
        )[0]
        == ACS_SAMPLE_LANDING
    )
    assert client.profile.fallback_author_extractor is not None
    assert client.profile.fallback_author_extractor(html) == [
        "Ada Lovelace",
        "Grace Hopper",
    ]


def test_acs_profile_exposes_provider_owned_hooks_for_article_html_pdf_fallback_and_abstract_only() -> (
    None
):
    profile = publisher_profile("acs")

    assert profile.dom_hooks.before_block_normalization is not None
    assert profile.dom_hooks.body_container is not None
    assert profile.scoped_asset_extractor is not None
    assert profile.finalize_extraction is not None


def test_acs_silverchair_browser_waits_for_article_body() -> None:
    assert atypon_body_ready_selectors("acs") == (
        ".article-body",
        ".widget-ArticleFulltext",
    )


def test_acs_provider_owned_cleanup_removes_copy_chrome_and_extracts_references() -> (
    None
):
    html = """
    <article>
      <h1>ACS title <span class="article__copy">Click to copy article link Article link copied!</span></h1>
      <div property="articleBody">
        <div class="NLM_sec">
          <div class="article_content-title">
            <h2>1. Introduction</h2>
            <div class="article__copy">Click to copy section link Section link copied!</div>
          </div>
          <p>Body text remains.</p>
        </div>
        <div class="NLM_back">
          <div class="refs-header-label"><h2>References</h2></div>
          <ol id="references">
            <li>
              <div class="NLM_citation references__item" data-doi="10.1021/example">
                <span><span class="NLM_string-name">Liu, L.</span>
                <span class="NLM_article-title">Catalyst paper</span>.
                <i>Chem. Rev.</i> <span class="NLM_year">2018</span>,
                <span class="refDoi">DOI: 10.1021/example</span></span>
                <div class="links-group"><a class="google-scholar">Google Scholar</a></div>
                <div class="casRecord"><div class="casContent">CAS duplicate</div></div>
              </div>
            </li>
          </ol>
        </div>
      </div>
    </article>
    """
    markdown, extraction = _acs_html.finalize_extraction(
        html,
        ACS_SAMPLE_LANDING,
        "# ACS title Click to copy article link Article link copied!\n\n"
        "## Abstract\n\n## Abstract\n\nBody text.",
        {},
    )

    assert "Click to copy" not in markdown
    assert markdown.count("## Abstract") == 1
    assert extraction["references"] == [
        {
            "label": "1.",
            "raw": "Liu, L. Catalyst paper. Chem. Rev. 2018, DOI: 10.1021/example",
            "doi": "10.1021/example",
            "year": "2018",
        }
    ]
    assert "Google Scholar" not in extraction["references"][0]["raw"]
    assert "CAS duplicate" not in extraction["references"][0]["raw"]


def test_acs_silverchair_body_excludes_loaded_figshare_viewer() -> None:
    body_html = "".join(
        f"<p>Transition-metal catalyst observation {index} describes a distinct "
        "industrial reaction condition and its measured conversion response.</p>"
        for index in range(80)
    )
    supplementary_html = "".join(
        f"<p>Supporting-information experiment S{index} records an auxiliary "
        "condition that must not replace the article extraction.</p>"
        for index in range(90)
    )
    html = f"""
    <html>
      <head>
        <title>ACS Silverchair Article</title>
        <meta name="citation_author" content="Ada Example" />
      </head>
      <body>
        <div class="page-column-wrap article-browse_content">
          <div class="article-body">
            <div class="abstract">
              <h2 class="abstract-title">Abstract</h2>
              <p>Silverchair abstract text with enough detail to remain.</p>
            </div>
            <div class="graphical-abstract">
              <h2 class="graphical-abstract-label">Visual Abstract</h2>
              <p>Abstract</p>
            </div>
            <div class="widget-ArticleFulltext">
                <div class="article-section-wrapper">
                  <h2 class="section-title">1. Introduction</h2>
                  {body_html}
              </div>
              <div class="widget-ArticleDataSupplements">
                <h2 class="supplementary-data-section-title">
                  Supporting Information
                    </h2>
                    <figshare-widget>
                      <article class="frontend-filesViewer-inlineMode-index-module__container--LzxR7">
                        {supplementary_html}
                  </article>
                </figshare-widget>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    markdown, extraction = extract_atypon_browser_workflow_markdown(
        html,
        ACS_SAMPLE_LANDING,
        "acs",
        metadata={"doi": ACS_SAMPLE_DOI, "title": "ACS Silverchair Article"},
    )

    assert extraction["availability_diagnostics"]["accepted"] is True
    assert "## 1. Introduction" in markdown
    assert "Transition-metal catalyst observation 79" in markdown
    assert "S2 experimental supporting information" not in markdown
    assert markdown.count("## Abstract") == 1
    assert "## Visual Abstract" not in markdown


def test_acs_silverchair_references_extract_structured_citations() -> None:
    html = """
    <div class="ref-list js-splitview-ref-list">
      <div class="ref false">
        <div class="ref-content">
          <div class="ref-label">1.</div>
          <div class="citation mixed-citation" id="cit1">
            Example, A.; Author, B. A complete reference title.
            <i>Chem. Rev.</i> <div class="year">2024</div>, 12, 10-20.
            <div class="pub-id-doi">
              <a href="https://doi.org/10.1021/example">DOI</a>
            </div>
            <div class="crossref-doi"><a>Crossref</a></div>
          </div>
        </div>
      </div>
    </div>
    """

    references = _acs_html.extract_references(html)

    assert references == [
        {
            "label": "1.",
            "raw": (
                "Example, A.; Author, B. A complete reference title. "
                "Chem. Rev. 2024, 12, 10-20. DOI"
            ),
            "doi": "10.1021/example",
            "year": "2024",
        }
    ]


def test_acs_silverchair_supplementary_widget_is_scoped_to_all_assets() -> None:
    html = """
    <div class="page-column-wrap article-browse_content">
      <div class="article-body">
        <div class="widget-ArticleFulltext">
          <h2>Results</h2>
          <p>Article body remains outside the supplementary widget.</p>
          <div class="widget-ArticleDataSupplements">
            <h2 class="supplementary-data-section-title">
              Supporting Information
            </h2>
            <a href="https://ndownloader.figstatic.com/files/48275169">
              Download
            </a>
            <a
              class="openInAnotherWindow js-download-file-gtm-datalayer-event"
              href="/acsodf/article-supplement/358560/pdf/ao4c03987_si_001/"
            >
              sifile1
            </a>
          </div>
        </div>
      </div>
    </div>
    """

    body_html, supplementary_html = extract_browser_workflow_asset_html_scopes(
        html,
        ACS_SAMPLE_LANDING,
        "acs",
    )
    body_assets = _acs_html.scoped_asset_extractor(
        body_html,
        ACS_SAMPLE_LANDING,
        asset_profile="body",
        supplementary_html_text=supplementary_html,
    )
    all_assets = _acs_html.scoped_asset_extractor(
        body_html,
        ACS_SAMPLE_LANDING,
        asset_profile="all",
        supplementary_html_text=supplementary_html,
    )

    assert "article-supplement" not in body_html
    assert "article-supplement" in supplementary_html
    assert [asset for asset in body_assets if asset["kind"] == "supplementary"] == []
    assert [
        asset["url"] for asset in all_assets if asset["kind"] == "supplementary"
    ] == ["https://pubs.acs.org/acsodf/article-supplement/358560/pdf/ao4c03987_si_001/"]


def test_acs_silverchair_structure_fixture_extracts_complete_current_article() -> None:
    """rule: rule-acs-silverchair-body-assets-references"""

    html = golden_criteria_asset(ACS_SAMPLE_DOI, "original.html").read_text(
        encoding="utf-8"
    )

    markdown, extraction = extract_atypon_browser_workflow_markdown(
        html,
        ACS_SAMPLE_LANDING,
        "acs",
        metadata={
            "doi": ACS_SAMPLE_DOI,
            "title": (
                "Functionalized Metal-Free Carbon Nanosphere Catalyst for the "
                "Selective C–N Bond Formation under Open-Air Conditions"
            ),
        },
    )
    body_html, supplementary_html = extract_browser_workflow_asset_html_scopes(
        html,
        ACS_SAMPLE_LANDING,
        "acs",
    )
    assets = _acs_html.scoped_asset_extractor(
        body_html,
        ACS_SAMPLE_LANDING,
        asset_profile="all",
        supplementary_html_text=supplementary_html,
    )

    assert len(markdown) > 30_000
    assert "## 1. Introduction" in markdown
    assert "## 5. Conclusions" in markdown
    assert "Open figure viewer" not in markdown
    assert "Close modal" not in markdown
    assert "View Large" not in markdown
    assert len(extraction["references"]) == 45
    assert extraction["references"][0]["year"] == "2018"
    assert sum(asset["kind"] == "figure" for asset in assets) == 8
    assert [asset["url"] for asset in assets if asset["kind"] == "supplementary"] == [
        "https://pubs.acs.org/acsodf/article-supplement/358560/pdf/ao4c03987_si_001/"
    ]


def test_acs_silverchair_formula_fixture_preserves_mathml_and_tables() -> None:
    html = golden_criteria_asset(ACS_FORMULA_DOI, "original.html").read_text(
        encoding="utf-8"
    )

    markdown, extraction = extract_atypon_browser_workflow_markdown(
        html,
        f"https://pubs.acs.org/doi/{ACS_FORMULA_DOI}",
        "acs",
        metadata={
            "doi": ACS_FORMULA_DOI,
            "title": (
                "General Equation to Estimate the Physicochemical Properties "
                "of Aliphatic Amines"
            ),
        },
    )

    assert len(markdown) > 45_000
    assert markdown.count("$$") == 42
    assert "S_{CNE}" in markdown
    assert "| *n* | PEI |" in markdown
    assert "## 3. Conclusions" in markdown
    assert len(extraction["references"]) == 20
    assert extraction["references"][0]["year"] == "2015"


def test_acs_probe_status_uses_browser_runtime_requirements() -> None:
    with mock.patch.object(
        camoufox_backend,
        "_dependency_details",
        return_value={
            "probe": "unit_test",
            "packages": {"playwright": True, "camoufox": True},
        },
    ):
        result = AcsClient(transport=None, env={}).probe_status()

    checks = {check.name: check for check in result.checks}
    assert result.status == "ready"
    assert checks["runtime_env"].status == "ok"
    assert checks["playwright_dependency"].status == "ok"
