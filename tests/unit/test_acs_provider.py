from __future__ import annotations

from unittest import mock

from paper_fetch import publisher_identity
from paper_fetch.providers import _acs_html
from paper_fetch.providers import _cloakbrowser
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
from paper_fetch.providers.browser_workflow import BrowserWorkflowClient


ACS_SAMPLE_DOI = "10.1021/acsomega.4c03987"
ACS_SAMPLE_LANDING = f"https://pubs.acs.org/doi/{ACS_SAMPLE_DOI}"


def test_acs_provider_bundle_declares_routing_and_browser_workflow() -> None:
    bundle = provider_bundle("acs")
    catalog = PROVIDER_CATALOG["acs"]

    assert bundle.catalog == catalog
    assert catalog.domains == ("www.acs.org", "pubs.acs.org", "acs.org")
    assert catalog.doi_prefixes == ("10.1021/",)
    assert catalog.base_domains == ("pubs.acs.org",)
    assert catalog.requires_browser_runtime is True
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


def test_acs_markdown_review_contract_markers() -> None:
    markdown = """
    # Functionalized Metal-Free Carbon Nanosphere Catalyst for the Selective C-N Bond Formation under Open-Air Conditions

    ## Abstract

    Functionalized metal-free carbon nanosphere catalyst smoke fixture.

    **Figure 1.** Representative carbon nanosphere catalyst workflow.

    **Table 1.**

    | s. no. | catalyst | OPD conversion (%) |
    | ------ | -------- | ------------------ |
    | 1      | ANCS     | 96                 |

    ## Supporting Information

    The Supporting Information is available free of charge at https://pubs.acs.org/doi/10.1021/acsomega.4c03987.

    ao4c03987_si_001.pdf

    ## References

    1. Representative ACS Omega reference for DOI 10.1021/acsomega.4c03987.
    """

    # markdown-review: purpose=structure doi=10.1021/acsomega.4c03987
    assert "## Abstract" in markdown
    assert "Download Citation" not in markdown

    # markdown-review: purpose=figure doi=10.1021/acsomega.4c03987
    assert "Figure" in markdown
    assert "Article Views" not in markdown

    # markdown-review: purpose=table doi=10.1021/acsomega.4c03987
    assert "Table 1" in markdown
    assert "| s. no. | catalyst | OPD conversion (%) |" in markdown
    assert "Google Scholar" not in markdown

    formula_markdown = """
    # General Equation to Estimate the Physicochemical Properties of Aliphatic Amines

    The NPOH equation uses the sum of carbon number effects.

    $$
    {\\ln{(P_{(n)})}}{= {a + b{(n - 1)} + cS_{CNE}}}
    $$
    """

    # markdown-review: purpose=formula doi=10.1021/acsomega.3c06992
    assert "NPOH equation" in formula_markdown
    assert "S_{CNE}" in formula_markdown
    assert formula_markdown.count("$$") >= 2
    assert "[Formula unavailable]" not in formula_markdown
    assert "Download Citation" not in formula_markdown

    # markdown-review: purpose=supplementary doi=10.1021/acsomega.4c03987
    assert "Supporting Information" in markdown
    assert "ao4c03987_si_001.pdf" in markdown
    assert "Download Citation" not in markdown

    pdf_markdown = """
    # General Equation to Express Changes in the Physicochemical Properties of Organic Homologues

    This PDF fallback baseline includes the NPOH equation body text.
    """

    # markdown-review: purpose=pdf_fallback doi=10.1021/acsomega.2c02828
    assert "General Equation to Express Changes" in pdf_markdown
    assert "NPOH equation" in pdf_markdown
    assert "Download Citation" not in pdf_markdown

    # markdown-review: purpose=references doi=10.1021/acsomega.4c03987
    assert "References" in markdown
    assert "Google Scholar" not in markdown


def test_acs_probe_status_uses_browser_runtime_requirements() -> None:
    with mock.patch.object(_cloakbrowser, "_dependency_available", return_value=True):
        result = AcsClient(
            transport=None,
            env={
                "PAPER_FETCH_BROWSER_BACKEND": "cloakbrowser",
                "CLOAKBROWSER_CDP_ENDPOINT": "ws://127.0.0.1:9222/devtools/browser/test",
            },
        ).probe_status()

    checks = {check.name: check for check in result.checks}
    assert result.status == "ready"
    assert checks["runtime_env"].status == "ok"
    assert checks["playwright_dependency"].status == "ok"
