from __future__ import annotations

from pathlib import Path
from unittest import mock

from paper_fetch import publisher_identity
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    SOURCE_PROVIDER_MAP,
    default_asset_profile_for_provider,
    provider_base_domains,
    provider_html_path_templates,
    provider_pdf_path_templates,
)
from paper_fetch.providers import _aip_html, browser_runtime
from paper_fetch.providers._atypon_browser_workflow_profiles import (
    build_html_candidates,
    build_pdf_candidates,
    publisher_profile,
)
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.aip import AipClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.browser_workflow import BrowserWorkflowClient
from tests.unit._browser_workflow_deps import install_browser_workflow_deps


AIP_STRUCTURE_DOI = "10.1063/5.0129134"
AIP_STRUCTURE_LANDING = (
    "https://pubs.aip.org/aip/adv/article/12/12/125205/2820011/"
    "On-chip-on-demand-delivery-of-K-for-in-vitro"
)
AIP_TABLE_FORMULA_DOI = "10.1063/5.0188905"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_aip_cold_html_retry_reuses_transient_seed_without_persisting_state(
    tmp_path,
) -> None:
    client = AipClient(transport=None, env={})
    state_path = tmp_path / "aip-storage-state.json"
    runtime = browser_runtime.BrowserRuntimeConfig(
        provider="aip",
        doi=AIP_STRUCTURE_DOI,
        artifact_dir=tmp_path / "artifacts",
        headless=True,
        user_agent=None,
        backend="camoufox",
        storage_state_path=state_path,
    )
    seed = {
        "browser_cookies": [
            {
                "name": "__cf_bm",
                "value": "transient-session",
                "domain": ".aip.org",
                "path": "/",
            }
        ],
        "browser_final_url": AIP_STRUCTURE_LANDING,
    }
    first_stage = browser_runtime.BrowserStagedStorageState(
        path=state_path,
        provider="aip",
        filter_url=AIP_STRUCTURE_LANDING,
        payload={"cookies": list(seed["browser_cookies"]), "origins": []},
    )
    second_stage = browser_runtime.BrowserStagedStorageState(
        path=state_path,
        provider="aip",
        filter_url=AIP_STRUCTURE_LANDING,
        payload={"cookies": list(seed["browser_cookies"]), "origins": []},
    )
    mocked_browser = mock.Mock(
        side_effect=[
            browser_runtime.BrowserFetchedHtml(
                source_url=AIP_STRUCTURE_LANDING,
                final_url=AIP_STRUCTURE_LANDING,
                html="<html><head><title>AIP article</title></head></html>",
                response_status=200,
                response_headers={"content-type": "text/html"},
                title="AIP article",
                summary="AIP article",
                browser_context_seed=seed,
                staged_storage_state=first_stage,
            ),
            browser_runtime.BrowserFetchedHtml(
                source_url=AIP_STRUCTURE_LANDING,
                final_url=AIP_STRUCTURE_LANDING,
                html="<html><body><article>Full article</article></body></html>",
                response_status=200,
                response_headers={"content-type": "text/html"},
                title="AIP article",
                summary="Full article",
                browser_context_seed=seed,
                staged_storage_state=second_stage,
            ),
        ]
    )
    mocked_extractor = mock.Mock(
        side_effect=[
            HtmlExtractionFailure(
                "article_container_not_found",
                "Could not identify the main article container.",
            ),
            (
                "# AIP article\n\n## Results\n\n" + ("Body text " * 120),
                {
                    "title": "AIP article",
                    "availability_diagnostics": {"content_kind": "fulltext"},
                },
            ),
        ]
    )
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(return_value=runtime),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=mocked_browser,
        extract_atypon_browser_workflow_markdown=mocked_extractor,
    )

    with mock.patch(
        "paper_fetch.providers.browser_runtime.paths.commit_staged_storage_state",
        return_value={"saved": True, "reason": "saved"},
    ) as commit_state:
        raw_payload = client.fetch_raw_fulltext(
            AIP_STRUCTURE_DOI,
            {
                "doi": AIP_STRUCTURE_DOI,
                "title": "AIP article",
                "landing_page_url": AIP_STRUCTURE_LANDING,
            },
        )

    assert mocked_browser.call_count == 2
    assert "browser_context_seed" not in mocked_browser.call_args_list[0].kwargs
    assert mocked_browser.call_args_list[0].args[0][0] == AIP_STRUCTURE_LANDING
    assert mocked_browser.call_args_list[1].args[0][0] == (
        f"https://pubs.aip.org/doi/full/{AIP_STRUCTURE_DOI}"
    )
    assert mocked_browser.call_args_list[1].args[0][-1] == AIP_STRUCTURE_LANDING
    retry_seed = mocked_browser.call_args_list[1].kwargs["browser_context_seed"]
    assert retry_seed["browser_cookies"][0]["name"] == "__cf_bm"
    assert retry_seed["browser_cookies"][0]["value"] == "transient-session"
    commit_state.assert_not_called()
    assert not state_path.exists()
    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "html"
    attempts = raw_payload.content.diagnostics["html_attempts"]
    assert [attempt["result"] for attempt in attempts] == [
        "extraction_failure",
        "success",
    ]
    assert attempts[0]["failure_code"] == "empty_article_shell"
    assert raw_payload.content.diagnostics["browser_runtime_trace"][
        "storage_state_save"
    ] == {
        "attempted": False,
        "staged": False,
        "saved": False,
        "path": None,
        "reason": "provider_runtime_fingerprint_boundary",
    }


def test_aip_provider_bundle_declares_routing_sources_and_browser_runtime() -> None:
    bundle = provider_bundle("aip")
    catalog = PROVIDER_CATALOG["aip"]

    assert bundle.catalog == catalog
    assert catalog.domains == ("pubs.aip.org",)
    assert catalog.doi_prefixes == ("10.1063/",)
    assert provider_base_domains("aip") == ("pubs.aip.org",)
    assert catalog.requires_browser_runtime is True
    assert default_asset_profile_for_provider("aip") == "body"
    assert SOURCE_PROVIDER_MAP["aip_html"] == "aip"
    assert SOURCE_PROVIDER_MAP["aip_pdf"] == "aip"
    assert bundle.sources == ("aip_html", "aip_pdf")
    assert bundle.html_rules is not None
    assert bundle.html_rules.availability.no_signals is True


def test_aip_candidates_cover_article_html_pdf_fallback_and_landing_url() -> None:
    # route-contract: article_html aip_html pdf_fallback aip_pdf 10.1063_5.0129134
    client = AipClient(None, {})
    metadata = {"doi": AIP_STRUCTURE_DOI, "landing_page_url": AIP_STRUCTURE_LANDING}

    assert provider_html_path_templates("aip") == ("/doi/full/{doi}", "/doi/{doi}")
    assert provider_pdf_path_templates("aip") == ("/doi/epdf/{doi}", "/doi/pdf/{doi}")
    assert build_html_candidates("aip", AIP_STRUCTURE_DOI)[:2] == [
        f"https://pubs.aip.org/doi/full/{AIP_STRUCTURE_DOI}",
        f"https://pubs.aip.org/doi/{AIP_STRUCTURE_DOI}",
    ]
    assert build_pdf_candidates("aip", AIP_STRUCTURE_DOI, None)[:2] == [
        f"https://pubs.aip.org/doi/epdf/{AIP_STRUCTURE_DOI}",
        f"https://pubs.aip.org/doi/pdf/{AIP_STRUCTURE_DOI}",
    ]
    assert (
        client.html_candidates(AIP_STRUCTURE_DOI, metadata)[0] == AIP_STRUCTURE_LANDING
    )


def test_aip_provider_identity_matches_domain_publisher_and_doi() -> None:
    assert publisher_identity.infer_provider_from_url(AIP_STRUCTURE_LANDING) == "aip"
    assert publisher_identity.infer_provider_from_doi(AIP_STRUCTURE_DOI) == "aip"
    assert publisher_identity.infer_provider_from_publisher("AIP Publishing") == "aip"
    assert (
        publisher_identity.infer_provider_from_publisher(
            "American Institute of Physics"
        )
        == "aip"
    )


def test_aip_browser_client_profile_and_author_fallback() -> None:
    client = AipClient(transport=None, env={})
    html = """
    <html><head>
      <meta name="citation_author" content="Ada Lovelace" />
      <meta name="citation_author" content="Grace Hopper" />
    </head><body></body></html>
    """

    assert isinstance(client, BrowserWorkflowClient)
    assert client.profile.name == "aip"
    assert client.article_source() == "aip_html"
    assert client.provider_label() == "AIP Publishing"
    assert client.profile.fallback_author_extractor is not None
    assert client.profile.fallback_author_extractor(html) == [
        "Ada Lovelace",
        "Grace Hopper",
    ]


def test_aip_profile_exposes_provider_owned_hooks_for_article_html_pdf_fallback_and_abstract_only() -> (
    None
):
    profile = publisher_profile("aip")

    assert profile.dom_hooks.before_block_normalization is not None
    assert profile.dom_hooks.body_container is not None
    assert profile.markdown_hooks.classify_heading is not None
    assert (
        profile.markdown_hooks.classify_heading("SUPPLEMENTARY MATERIAL", None)
        == "body_heading"
    )
    assert (
        profile.markdown_hooks.classify_heading("AUTHOR DECLARATIONS", None)
        == "body_heading"
    )
    assert profile.scoped_asset_extractor is not None
    assert profile.finalize_extraction is not None


def test_aip_provider_owned_cleanup_removes_topics_chrome_and_extracts_references() -> (
    None
):
    html = """
    <html>
      <head>
        <meta name="citation_author" content="Ada Example" />
        <meta name="citation_reference" content="citation_author=Seitanidou M.; citation_journal_title=Adv. Healthcare Mater.; citation_year=2019; citation_volume=8; citation_pages=1900813; citation_doi=10.1002/example" />
      </head>
      <body>
        <article>
          <div class="article-navigation">Article Navigation Download Citation</div>
          <section property="articleBody">
            <h2>I. INTRODUCTION</h2>
            <p>Body text remains.</p>
          </section>
        </article>
      </body>
    </html>
    """
    markdown, extraction = _aip_html.finalize_extraction(
        html,
        AIP_STRUCTURE_LANDING,
        "# AIP title *Open Access*\n\n## Abstract\n\nAbstract text.\n\nTopics\n\nPhysics, Materials\n\n## I. INTRODUCTION\n\nBody text remains.",
        {"title": "AIP title *Open Access*"},
    )

    assert "Topics" not in markdown
    assert "Download Citation" not in markdown
    assert markdown.startswith("# AIP title\n")
    assert extraction["title"] == "AIP title"
    assert extraction["extracted_authors"] == ["Ada Example"]
    assert extraction["references"] == [
        {
            "label": "1.",
            "raw": "Seitanidou M., Adv. Healthcare Mater., 2019, 8, 1900813",
            "doi": "10.1002/example",
            "year": "2019",
        }
    ]


def test_aip_finalize_restores_retained_back_matter_sections() -> None:
    html = """
    <html><body>
      <article>
        <h2>V. SUPPLEMENTARY MATERIAL</h2>
        <div><p>See the <a href="/supplement.zip">supplementary material</a> for details.</p></div>
        <h2>ACKNOWLEDGMENTS</h2>
        <div><p>Acknowledgment text is not part of the supplementary section.</p></div>
        <div class="widget-ArticleDataSupplements">
          <h2 class="section-title supplementary-data-section-title">Supplementary Material</h2>
          <div><p>Widget download chrome.</p></div>
        </div>
      </article>
    </body></html>
    """

    markdown, _extraction = _aip_html.finalize_extraction(
        html,
        AIP_STRUCTURE_LANDING,
        "# AIP title\n\n## DATA AVAILABILITY\n\nData are available.",
        {},
    )

    assert "## V. SUPPLEMENTARY MATERIAL" in markdown
    assert "supplementary material" in markdown
    assert "Acknowledgment text is not part of the supplementary section." in markdown
    assert "Widget download chrome" not in markdown
    assert markdown.index("## V. SUPPLEMENTARY MATERIAL") < markdown.index(
        "## DATA AVAILABILITY"
    )


def test_aip_markdown_cleanup_removes_figure_modal_duplicate_blocks() -> None:
    markdown = _aip_html.aip_normalize_markdown(
        """
        ![Figure 1](body_assets/aip-figure-1.jpeg)

        **FIG. 1. (a) Image of the ion pump. Scale bar—1 cm. (b) Image of the device.**

        View large

        (a) Image of the ion pump. Scale bar—1 cm. (b) Image of the device.

        View large

        (a) Image of the ion pump. Scale bar—1 cm. (b) Image of the device.

        Close modal

        Body text remains after the figure modal content.
        """
    )

    assert "View large" not in markdown
    assert "Close modal" not in markdown
    assert markdown.count("Image of the ion pump") == 1
    assert "Body text remains after the figure modal content." in markdown


def test_aip_markdown_cleanup_handles_unlabeled_bold_caption_after_image() -> None:
    markdown = _aip_html.aip_normalize_markdown(
        """
        ![Figure](body_assets/aip-figure-1.jpeg)

        **Room temperature thermal conductivities of different materials vs their electronic bandgaps.**

        Room temperature thermal conductivities of different materials vs their electronic bandgaps.

        Room temperature thermal conductivities of different materials vs their electronic bandgaps.

        Though the inherent characteristics of the material are excellent, further studies remain necessary.
        """
    )

    assert markdown.count("Room temperature thermal conductivities") == 1
    assert "Though the inherent characteristics" in markdown


def test_aip_markdown_cleanup_handles_formula_variant_caption_duplicates() -> None:
    markdown = _aip_html.aip_normalize_markdown(
        """
        ![Figure](body_assets/aip-figure-5.jpeg)

        **The effects of biaxial strains on thermal conductivities of w-AlN. The strained κ s t r a i n is divided by the strain-less κ 0. Refer to the image caption for details.**

        The effects of biaxial strains on thermal conductivities of *w-*AlN. The strained $\\kappa_{strain}\\:$ is divided by the strain-less $\\kappa_{0}$.

        The effects of biaxial strains on thermal conductivities of *w-*AlN. The strained $\\kappa_{strain}\\:$ is divided by the strain-less $\\kappa_{0}$.

        Then the body continues.
        """
    )

    assert markdown.count("The effects of biaxial strains") == 1
    assert "Then the body continues." in markdown


def test_aip_article_source_tracks_pdf_fallback_payload() -> None:
    client = AipClient(None, {})
    payload = RawFulltextPayload(
        provider="aip",
        source_url=f"https://pubs.aip.org/doi/pdf/{AIP_STRUCTURE_DOI}",
        content_type="application/pdf",
        body=b"%PDF-1.7",
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=f"https://pubs.aip.org/doi/pdf/{AIP_STRUCTURE_DOI}",
            content_type="application/pdf",
            body=b"%PDF-1.7",
            markdown_text="# PDF text",
        ),
    )

    assert client.article_source_for_payload(payload) == "aip_pdf"


def test_aip_markdown_review_contract_markers() -> None:
    markdown = """
    # On-chip on-demand delivery of K<sup>+</sup> for in vitro bioelectronics

    ## Abstract

    Bioelectronic devices can actuate biological processes.

    ## I. INTRODUCTION

    Bioelectronics bridges the gap between biology and electronics.

    ![Figure 1](body_assets/aip-figure-1.jpeg)

    **Figure 1.** Six-well potassium ion pump design.

    ## SUPPLEMENTARY MATERIAL

    See the supplementary material for additional characterization.

    ## References

    1. Seitanidou M. Adv. Healthcare Mater. 2019.
    """

    # markdown-review: purpose=structure doi=10.1063/5.0129134
    assert "## Abstract" in markdown
    assert "## I. INTRODUCTION" in markdown
    assert "Download Citation" not in markdown
    assert "Article Navigation" not in markdown

    # markdown-review: purpose=figure doi=10.1063/5.0129134
    assert "Figure 1" in markdown
    assert "![Figure" in markdown
    assert "Open figure viewer" not in markdown
    assert "View large" not in markdown
    assert "Close modal" not in markdown

    # markdown-review: purpose=supplementary doi=10.1063/5.0129134
    assert "SUPPLEMENTARY MATERIAL" in markdown
    assert "supplementary material" in markdown
    assert "Download Citation" not in markdown

    # markdown-review: purpose=references doi=10.1063/5.0129134
    assert "## References" in markdown
    assert "Seitanidou" in markdown
    assert "Google Scholar" not in markdown

    markdown_text = """
    # Machine-learned atomic cluster expansion

    **Table** Comparison of the lattice parameters of w-AlN determined by different methods.

    | Method | a | c |
    | ------ | - | - |
    | ACE    | 3 | 5 |

    **Equation 1.**

    $$
    \\begin{matrix} {E = \\sum\\limits_{i}\\varepsilon_{i},} \\end{matrix}
    $$
    """

    # markdown-review: purpose=table doi=10.1063/5.0188905
    assert "Comparison of the lattice parameters" in markdown_text
    assert "| Method" in markdown_text
    assert "Google Scholar" not in markdown_text

    # markdown-review: purpose=formula doi=10.1063/5.0188905
    assert "Equation 1." in markdown_text
    assert "\\begin{matrix}" in markdown_text
    assert "$$" in markdown_text
    assert "[Formula unavailable]" not in markdown_text


def test_aip_download_related_assets_contract_marker(monkeypatch, tmp_path) -> None:
    """asset-download-contract: provider=aip"""
    asset_path = tmp_path / "aip-figure-1.jpeg"
    asset_path.write_bytes(b"fake-image")
    client = AipClient(None, {})

    def fake_download(*args, **kwargs):
        return {
            "assets": [
                {
                    "kind": "figure",
                    "path": str(asset_path),
                    "downloaded_bytes": asset_path.stat().st_size,
                }
            ],
            "asset_failures": [],
        }

    monkeypatch.setattr(
        client, "_download_browser_backed_related_assets", fake_download
    )
    result = client.download_related_assets(
        AIP_STRUCTURE_DOI,
        {"doi": AIP_STRUCTURE_DOI},
        RawFulltextPayload(
            provider="aip",
            source_url=AIP_STRUCTURE_LANDING,
            content_type="text/html",
            body=b"<html></html>",
            content=ProviderContent(
                route_kind="html",
                source_url=AIP_STRUCTURE_LANDING,
                content_type="text/html",
                body=b"<html></html>",
                markdown_text="# AIP",
            ),
        ),
        tmp_path,
        asset_profile="body",
    )

    downloaded = result["assets"][0]
    assert Path(downloaded["path"]).is_file()
    assert Path(downloaded["path"]).read_bytes() == b"fake-image"
    assert downloaded["downloaded_bytes"] == len(b"fake-image")
    assert result["asset_failures"] == []
