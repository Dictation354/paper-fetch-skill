from __future__ import annotations

from functools import cache
from pathlib import Path
import re
from unittest import mock

from bs4 import BeautifulSoup, NavigableString, Tag
import pytest

from paper_fetch import auth, browser_preflight, publisher_identity
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    SOURCE_PROVIDER_MAP,
    default_asset_profile_for_provider,
    provider_base_domains,
    provider_html_path_templates,
    provider_pdf_path_templates,
)
from paper_fetch.providers import _tandf_html
from paper_fetch.providers._atypon_browser_workflow_profiles import (
    build_html_candidates,
    build_pdf_candidates,
    publisher_profile,
)
from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.browser_workflow import BrowserWorkflowClient
from paper_fetch.providers.tandf import TandfClient
from paper_fetch.tracing import trace_from_markers


STRUCTURE_DOI = "10.1080/15481603.2026.2667034"
TABLE_DOI = "10.1080/10942912.2019.1597882"
FORMULA_DOI = "10.1080/08839514.2024.2375110"
MULTILINGUAL_DOI = "10.1080/19455224.2025.2547671"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _fixture_path(doi: str, filename: str = "original.html") -> Path:
    return (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / doi.replace("/", "_", 1)
        / filename
    )


@cache
def _extract_fixture(doi: str) -> tuple[str, dict]:
    source_url = f"https://www.tandfonline.com/doi/full/{doi}"
    html_text = _fixture_path(doi).read_text(encoding="utf-8")
    return TandfClient(None, {}).extract_markdown(
        html_text,
        source_url,
        metadata={"doi": doi},
    )


@cache
def _render_article_markdown(doi: str) -> str:
    source_url = f"https://www.tandfonline.com/doi/full/{doi}"
    html_text = _fixture_path(doi).read_text(encoding="utf-8")
    metadata = {
        "doi": doi,
        "authors": [],
        "references": [],
        "fulltext_links": [],
        "landing_page_url": source_url,
    }
    markdown, extraction = TandfClient(None, {}).extract_markdown(
        html_text,
        source_url,
        metadata=metadata,
    )
    payload = RawFulltextPayload(
        provider="tandf",
        source_url=source_url,
        content_type="text/html",
        body=html_text.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            markdown_text=markdown,
            diagnostics={
                "extraction": extraction,
                "availability_diagnostics": extraction["availability_diagnostics"],
            },
        ),
        trace=trace_from_markers(["fulltext:tandf_html_ok"]),
    )
    article = TandfClient(None, {}).to_article_model(metadata, payload)
    return article.to_ai_markdown(include_refs="all", max_tokens="full_text")


def test_tandf_provider_bundle_declares_routes_sources_and_browser_runtime() -> None:
    bundle = provider_bundle("tandf")
    catalog = PROVIDER_CATALOG["tandf"]

    assert bundle.catalog == catalog
    assert catalog.domains == ("tandfonline.com", "www.tandfonline.com")
    assert catalog.domain_suffixes == ("tandfonline.com",)
    assert catalog.doi_prefixes == ("10.1080/",)
    assert provider_base_domains("tandf") == ("www.tandfonline.com",)
    assert catalog.requires_browser_runtime is True
    assert catalog.provider_managed_abstract_only is True
    assert catalog.status_order == 19
    assert default_asset_profile_for_provider("tandf") == "body"
    assert SOURCE_PROVIDER_MAP["tandf_html"] == "tandf"
    assert SOURCE_PROVIDER_MAP["tandf_pdf"] == "tandf"
    assert bundle.sources == ("tandf_html", "tandf_pdf")
    assert bundle.html_rules is not None
    assert bundle.html_rules.availability.no_signals is True


def test_tandf_builtin_auth_and_preflight_target_use_verified_open_article() -> None:
    target = auth.AUTH_TARGETS["tandf"]

    assert target.doi == STRUCTURE_DOI
    assert target.url == f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}"
    assert browser_preflight._preflight_target("tandf", None) == target


def test_tandf_candidates_cover_html_pdf_and_same_site_landing_url() -> None:
    landing = f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}?scroll=top"
    client = TandfClient(None, {})

    assert provider_html_path_templates("tandf") == (
        "/doi/full/{doi}",
        "/doi/abs/{doi}",
        "/doi/{doi}",
    )
    assert provider_pdf_path_templates("tandf") == (
        "/doi/epdf/{doi}",
        "/doi/pdf/{doi}",
    )
    assert build_html_candidates("tandf", STRUCTURE_DOI) == [
        f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}",
        f"https://www.tandfonline.com/doi/abs/{STRUCTURE_DOI}",
        f"https://www.tandfonline.com/doi/{STRUCTURE_DOI}",
    ]
    assert build_pdf_candidates("tandf", STRUCTURE_DOI, None) == [
        f"https://www.tandfonline.com/doi/epdf/{STRUCTURE_DOI}",
        f"https://www.tandfonline.com/doi/pdf/{STRUCTURE_DOI}",
    ]
    assert (
        client.html_candidates(STRUCTURE_DOI, {"landing_page_url": landing})[0]
        == landing
    )
    assert (
        client.html_candidates(
            STRUCTURE_DOI,
            {"landing_page_url": "https://example.org/not-tandf"},
        )[0]
        == f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}"
    )


def test_tandf_provider_identity_is_narrow_and_deterministic() -> None:
    landing = f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}"

    assert publisher_identity.infer_provider_from_url(landing) == "tandf"
    assert publisher_identity.infer_provider_from_doi(STRUCTURE_DOI) == "tandf"
    assert (
        publisher_identity.infer_provider_from_publisher("Taylor & Francis Group")
        == "tandf"
    )
    assert (
        publisher_identity.infer_provider_from_publisher("Informa UK Limited")
        == "tandf"
    )
    assert (
        publisher_identity.infer_provider_from_url(
            "https://www.taylorfrancis.com/books/example"
        )
        is None
    )
    assert publisher_identity.infer_provider_from_doi("10.1002/example") == "wiley"


def test_tandf_browser_profile_and_provider_owned_hooks() -> None:
    client = TandfClient(None, {})
    profile = publisher_profile("tandf")
    html = """
    <html><head>
      <meta name="citation_author" content="Ada Lovelace" />
      <meta name="citation_author" content="Grace Hopper" />
    </head><body></body></html>
    """

    assert isinstance(client, BrowserWorkflowClient)
    assert client.profile.name == "tandf"
    assert client.article_source() == "tandf_html"
    assert client.provider_label() == "Taylor & Francis Online"
    assert client.route_order == (
        "article_html",
        "pdf_fallback",
        "abstract_only",
        "metadata_only",
    )
    assert client.profile.fallback_author_extractor is not None
    assert client.profile.fallback_author_extractor(html) == [
        "Ada Lovelace",
        "Grace Hopper",
    ]
    assert profile.dom_hooks.before_block_normalization is not None
    assert profile.dom_hooks.body_container is not None
    assert profile.dom_hooks.asset_body_container is not None
    assert profile.dom_hooks.asset_figure_extraction is not None
    assert profile.prepare_browser_page is _tandf_html.prepare_browser_page
    assert profile.extract_asset_html_scopes is not None
    assert profile.scoped_asset_extractor is not None
    assert profile.finalize_extraction is not None
    assert _tandf_html.tandf_classify_heading("Cited by", None) == "ancillary"
    assert _tandf_html.tandf_classify_heading("Related articles", None) == "ancillary"


def test_tandf_browser_page_preparation_hydrates_official_csv_table() -> None:
    link = mock.Mock()
    link.get_attribute.side_effect = lambda name: (
        "/action/downloadTable?id=t0001&doi=10.1080%2Fsample&downloadType=CSV"
        if name == "href"
        else None
    )
    link.evaluate.return_value = "t0001-table-wrapper"
    links = mock.Mock()
    links.count.return_value = 1
    links.nth.return_value = link
    page = mock.Mock()
    page.locator.return_value = links
    page.evaluate.side_effect = [
        {
            "results": [
                {
                    "ok": True,
                    "status": 200,
                    "contentType": "text/csv;charset=UTF-8",
                    "text": '"Material","Value"\n"Buffer","200"',
                    "caption": "Table 1. Example (Citation 2011)",
                }
            ],
            "timedOut": False,
            "concurrency": 1,
        },
        True,
        {"total": 1, "truncated": False, "tables": []},
    ]

    result = _tandf_html.prepare_browser_page(page, timeout_ms=5_000)

    assert result == {
        "attempted": True,
        "table_controls": 1,
        "tables_hydrated": 1,
        "csv_tables_hydrated": 1,
        "embedded_tables": 1,
        "embedded_tables_hydrated": 0,
        "table_failures": 0,
        "truncated": False,
        "table_fetch_concurrency": 1,
    }
    batch_args = page.evaluate.call_args_list[0].args[1]
    assert batch_args["entries"] == [
        {
            "href": "/action/downloadTable?id=t0001&doi=10.1080%2Fsample&downloadType=CSV",
            "tableId": "t0001",
        }
    ]
    assert batch_args["perTableTimeoutMs"] == 2_000
    assert batch_args["concurrency"] == 4
    assert 0 < batch_args["totalTimeoutMs"] <= 5_000
    batch_script = page.evaluate.call_args_list[0].args[0]
    assert "Promise.all" in batch_script
    assert "targetUrl.origin !== window.location.origin" in batch_script
    assert page.evaluate.call_args_list[1].args[1] == {
        "tableId": "t0001",
        "caption": "Table 1. Example (2011)",
        "rows": [["Material", "Value"], ["Buffer", "200"]],
    }


def test_tandf_browser_page_preparation_uses_bounded_embedded_table_fallback() -> None:
    links = mock.Mock()
    links.count.return_value = 0
    page = mock.Mock()
    page.locator.return_value = links
    page.evaluate.side_effect = [
        {
            "total": 1,
            "truncated": False,
            "tables": [
                {
                    "tableId": "ut0001",
                    "caption": "Algorithm",
                    "rows": [["Step"], ["Build the model"]],
                }
            ],
        },
        True,
    ]

    result = _tandf_html.prepare_browser_page(page, timeout_ms=5_000)

    assert result["tables_hydrated"] == 1
    assert result["csv_tables_hydrated"] == 0
    assert result["embedded_tables_hydrated"] == 1
    assert page.evaluate.call_args_list[1].args[1] == {
        "tableId": "ut0001",
        "caption": "Algorithm",
        "rows": [["Step"], ["Build the model"]],
    }


def test_tandf_batch_results_keep_input_order_and_failed_table_fallback() -> None:
    def link(table_id: str):
        value = mock.Mock()
        value.get_attribute.side_effect = lambda name: (
            f"/action/downloadTable?id={table_id}&downloadType=CSV"
            if name == "href"
            else None
        )
        value.evaluate.return_value = f"{table_id}-table-wrapper"
        return value

    links = mock.Mock()
    links.count.return_value = 2
    links.nth.side_effect = [link("t0001"), link("t0002")]
    page = mock.Mock()
    page.locator.return_value = links
    page.evaluate.side_effect = [
        {
            "results": [
                {
                    "ok": True,
                    "status": 200,
                    "contentType": "text/csv",
                    "text": "A,B\n1,2",
                    "caption": "First",
                },
                {"ok": False, "status": 504, "error": "AbortError"},
            ],
            "timedOut": False,
            "concurrency": 2,
        },
        True,
        {
            "total": 1,
            "truncated": False,
            "tables": [
                {
                    "tableId": "t0002",
                    "caption": "Second fallback",
                    "rows": [["C", "D"], ["3", "4"]],
                }
            ],
        },
        True,
    ]

    result = _tandf_html.prepare_browser_page(page, timeout_ms=5_000)

    assert result["table_fetch_concurrency"] == 2
    assert result["csv_tables_hydrated"] == 1
    assert result["embedded_tables_hydrated"] == 1
    assert result["tables_hydrated"] == 2
    assert result["table_failures"] == 1
    injected = [
        call.args[1]
        for call in (page.evaluate.call_args_list[1], page.evaluate.call_args_list[3])
    ]
    assert [entry["tableId"] for entry in injected] == ["t0001", "t0002"]
    assert injected[0]["rows"] == [["A", "B"], ["1", "2"]]
    assert injected[1]["rows"] == [["C", "D"], ["3", "4"]]


def test_tandf_table_preparation_obeys_exhausted_total_deadline() -> None:
    links = mock.Mock()
    links.count.return_value = 24
    page = mock.Mock()
    page.locator.return_value = links

    result = _tandf_html.prepare_browser_page(page, timeout_ms=0)

    assert result["table_controls"] == 24
    assert result["timed_out"] is True
    links.nth.assert_not_called()
    page.evaluate.assert_not_called()


def test_tandf_article_assets_keep_body_figures_and_scope_supplement() -> None:
    html_text = _fixture_path(STRUCTURE_DOI).read_text(encoding="utf-8")
    source_url = f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}"
    body_html, supplementary_html = extract_browser_workflow_asset_html_scopes(
        html_text,
        source_url,
        "tandf",
    )
    extractor = publisher_profile("tandf").scoped_asset_extractor
    assert extractor is not None

    body_assets = extractor(
        body_html,
        source_url,
        asset_profile="body",
        supplementary_html_text=supplementary_html,
    )
    all_assets = extractor(
        body_html,
        source_url,
        asset_profile="all",
        supplementary_html_text=supplementary_html,
    )

    figures = [asset for asset in body_assets if asset["kind"] == "figure"]
    assert len(figures) == 9
    assert all(asset.get("preview_accepted") == "true" for asset in figures)
    assert all(not asset.get("full_size_url") for asset in figures)
    assert all(
        asset.get("provenance") == ["official_full_size_not_exposed"]
        for asset in figures
    )
    assert any("_f0006_c.jpg" in asset["preview_url"] for asset in figures)
    assert not [asset for asset in body_assets if asset["kind"] == "supplementary"]
    supplementary = [asset for asset in all_assets if asset["kind"] == "supplementary"]
    assert len(supplementary) == 1
    assert "preview_accepted" not in supplementary[0]
    assert supplementary[0]["url"].startswith(
        "https://www.tandfonline.com/action/downloadSupplement?"
    )
    assert supplementary[0]["url"].endswith("tgrs_a_2667034_sm1980.docx")


def test_tandf_download_related_assets_contract_marker(monkeypatch, tmp_path) -> None:
    """asset-download-contract: provider=tandf"""
    asset_path = tmp_path / "tandf-figure-1.jpeg"
    asset_path.write_bytes(b"fake-image")
    client = TandfClient(None, {})

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
        STRUCTURE_DOI,
        {"doi": STRUCTURE_DOI},
        RawFulltextPayload(
            provider="tandf",
            source_url=f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}",
            content_type="text/html",
            body=b"<html></html>",
            content=ProviderContent(
                route_kind="html",
                source_url=f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}",
                content_type="text/html",
                body=b"<html></html>",
                markdown_text="# Taylor & Francis Online",
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


def test_markdown_contract_structure_fixture() -> None:
    # markdown-review: purpose=structure doi=10.1080/15481603.2026.2667034
    markdown, extraction = _extract_fixture(STRUCTURE_DOI)

    assert "## Abstract" in markdown
    assert "## 1. Introduction" in markdown
    assert "### 4.1 Modeling approaches and comparative performance" in markdown
    assert "a 95.1% improvement over traditional Poisson regression" in markdown
    assert re.search(
        r"(?m)^\|\s*Variable abbreviation\s*\|\s*Description\s*\|", markdown
    )
    assert re.search(
        r"(?m)^\|\s*D_LST\s*\|\s*Current weekly daytime maximum LST \(°C\)",
        markdown,
    )
    assert "Sexes / Both sexes" in markdown
    assert "4340.046" in markdown
    assert "X<sup>2</sup>*D_LST_AT2" in markdown
    assert "X<sup>3</sup>*D_LST_AT3" in markdown
    assert "R<sup>2</sup> generally" in markdown
    assert "R<sup>2</sup> (below 0.30)" in markdown
    assert "## Funding" in markdown
    assert "National Natural Science Foundation of China" in markdown
    assert "Download Citation" not in markdown
    assert "Article Metrics" not in markdown
    assert "## Article highlights" not in markdown
    assert "Citation" not in markdown
    assert "()" not in markdown
    assert "(Figure 1a)" in markdown
    assert extraction["availability_diagnostics"]["accepted"] is True


def test_markdown_contract_table_fixture() -> None:
    # markdown-review: purpose=table doi=10.1080/10942912.2019.1597882
    markdown, _ = _extract_fixture(TABLE_DOI)

    assert "**Table 1.**" in markdown
    assert "| Materials used | Sample tube (µL) | Control tube (µL) |" in markdown
    assert "| Total volume" in markdown
    assert "| Compounds | AChE / IC<sub>50</sub>(nM)" in markdown
    assert "AChE / r<sup>2</sup>" in markdown
    assert "α-Amylase<sup>a</sup> / IC<sub>50</sub>(nM)" in markdown
    assert "α-Glycosidase / K<sub>i</sub>(nM)" in markdown
    assert "Ki values could not be determined for α-amylase enzyme." in markdown
    assert "determined as µM levels, which taken from literatures" in markdown
    assert (
        "Tacrine was used as a positive control for acetylcholinesterase (AChE) enzyme."
        in markdown
    )
    assert "- Compounds: IC50 (nM); AChE: r2" not in markdown
    assert "Google Scholar" not in markdown
    assert "Display Table" not in markdown
    assert "Citation" not in markdown
    assert re.search(r"(?m)^\|.+\|$", markdown)


def test_markdown_contract_formula_fixture() -> None:
    # markdown-review: purpose=formula doi=10.1080/08839514.2024.2375110
    markdown, _ = _extract_fixture(FORMULA_DOI)

    assert "## Introduction" in markdown
    assert "[Formula unavailable]" not in markdown
    assert "![Formula](//:0)" not in markdown
    assert "MathJax Logo" not in markdown
    assert "Citation" not in markdown
    assert re.search(r"(?s)\$\$.+?\$\$|\\\(.+?\\\)", markdown)
    assert re.search(
        r"(?s)\\begin\{(?:p)?matrix\}.{0,200}"
        r"\{?0\.88\}?\^\{0\.37\}.{0,100}\{?0\.82\}?\^\{0\.21\}",
        markdown,
    )
    assert "Θ˜(ℏ˜ 1)=" not in markdown
    assert "A D 2 N˜ 2=" not in markdown
    assert r"0.51^{0.22}\rangle}" not in markdown
    assert r"{\widetilde{\Theta}}_{2}(\widetilde{\hslash})) =" not in markdown
    assert "(0.15}}" not in markdown
    assert "(0.24)}0.76" not in markdown
    assert "$$." not in markdown
    assert "$$," not in markdown
    assert "0.2415.(2) Score matrix" not in markdown
    assert "\n\n(2) Score matrix" in markdown


def test_tandf_formula_dom_repair_preserves_complex_math_structure() -> None:
    soup = BeautifulSoup(
        _fixture_path(FORMULA_DOI).read_text(encoding="utf-8"),
        _tandf_html.choose_parser(),
    )
    container = soup.select_one(".hlFld-Fulltext")
    assert isinstance(container, Tag)

    _tandf_html.tandf_before_block_normalization(container)

    complex_inline = [
        node
        for node in container.select(".NLM_disp-formula.inline-formula")
        if node.find("mtable") is not None
    ]
    assert len(complex_inline) == 11
    assert all("disp-formula" in (node.get("class") or ()) for node in complex_inline)

    for fenced in container.find_all("mfenced"):
        descendants = fenced.find_all(True)
        if not descendants:
            continue
        trailing = descendants[-1]
        if trailing.find_parent("mfenced") is fenced:
            assert _tandf_html._mathml_operator_text(trailing) != str(
                fenced.get("close") or ")"
            )

    for fenced in container.find_all("mfenced", attrs={"open": "⟨"}):
        for row in fenced.find_all("mrow"):
            children = [child for child in row.children if isinstance(child, Tag)]
            assert not any(
                current.find("msup") is not None and following.name == "mn"
                for current, following in zip(children, children[1:], strict=False)
            )

    exponent_repairs = 0
    for superscript in container.find_all("msup"):
        children = [child for child in superscript.children if isinstance(child, Tag)]
        if len(children) < 2:
            continue
        operators = [
            _tandf_html._mathml_operator_text(node)
            for node in children[1].find_all("mo")
        ]
        if "(" in operators:
            exponent_repairs += 1
            assert operators.count("(") == operators.count(")")
    assert exponent_repairs >= 22

    for wrapper in complex_inline:
        sibling = wrapper.next_sibling
        while isinstance(sibling, Tag) and "NLM_disp-formula-image" in set(
            sibling.get("class") or ()
        ):
            sibling = sibling.next_sibling
        if isinstance(sibling, NavigableString) and sibling.strip():
            assert not re.match(r"^\s*[.,;:]", str(sibling))


def test_markdown_contract_figure_fixture() -> None:
    # markdown-review: purpose=figure doi=10.1080/15481603.2026.2667034
    markdown, _ = _extract_fixture(STRUCTURE_DOI)

    assert "Figure 1" in markdown
    assert re.search(
        r"!\[Figure 1\]\(https://www\.tandfonline\.com/cms/asset/", markdown
    )
    assert "Open figure viewer" not in markdown
    assert "View large" not in markdown
    assert "Article Metrics" not in markdown

    baseline = _fixture_path(STRUCTURE_DOI, "extracted.md").read_text(encoding="utf-8")
    local_links = re.findall(
        r"!\[Figure \d+\]\((tests/fixtures/golden_criteria/"
        r"10\.1080_15481603\.2026\.2667034/body_assets/[^)]+\.jpg)\)",
        baseline,
    )
    assert len(local_links) == 9
    assert "![Figure 1](https://www.tandfonline.com/" not in baseline
    for relative_path in local_links:
        asset_path = REPO_ROOT / relative_path
        assert asset_path.is_file()
        assert asset_path.stat().st_size > 100_000


def test_markdown_contract_supplementary_fixture() -> None:
    # markdown-review: purpose=supplementary doi=10.1080/15481603.2026.2667034
    markdown, _ = _extract_fixture(STRUCTURE_DOI)

    assert markdown.count("## Supplemental material") == 1
    assert "Supplemental data for this article can be accessed" in markdown
    assert "Download Citation" not in markdown
    assert "Article Metrics" not in markdown


def test_markdown_contract_references_fixture() -> None:
    # markdown-review: purpose=references doi=10.1080/15481603.2026.2667034
    markdown = _render_article_markdown(STRUCTURE_DOI)

    assert "## References (103 total, showing 103)" in markdown
    assert "1. Aldrich, C. 2020." in markdown
    assert "Google Scholar" not in markdown
    assert "Article Metrics" not in markdown


def test_markdown_contract_pdf_fallback_fixture() -> None:
    # markdown-review: purpose=pdf_fallback doi=10.1080/15481603.2026.2667034
    pdf_path = _fixture_path(STRUCTURE_DOI, "original.pdf")
    source_url = f"https://www.tandfonline.com/doi/pdf/{STRUCTURE_DOI}"
    result = pdf_fetch_result_from_bytes(
        artifact_dir=None,
        source_url=source_url,
        final_url=source_url,
        pdf_bytes=pdf_path.read_bytes(),
    )

    assert "Quantifying cumulative heat effects" in result.markdown_text
    assert "Just a moment" not in result.markdown_text
    assert "Access Denied" not in result.markdown_text


def test_tandf_article_source_tracks_pdf_fallback_payload() -> None:
    payload = RawFulltextPayload(
        provider="tandf",
        source_url=f"https://www.tandfonline.com/doi/pdf/{STRUCTURE_DOI}",
        content_type="application/pdf",
        body=b"%PDF-1.7",
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=f"https://www.tandfonline.com/doi/pdf/{STRUCTURE_DOI}",
            content_type="application/pdf",
            body=b"%PDF-1.7",
            markdown_text="# PDF text",
        ),
    )

    assert TandfClient(None, {}).article_source_for_payload(payload) == "tandf_pdf"


@pytest.mark.parametrize(
    ("extra_html", "expected_reason"),
    [
        ("", "abstract_only"),
        (
            '<div class="needAccess"><h2>Access options</h2>'
            "<p>Purchase access or log in through your institution.</p></div>",
            "abstract_only",
        ),
        (
            '<div id="challenge-running">Just a moment. '
            "Enable JavaScript and cookies to continue.</div>",
            "cloudflare_challenge",
        ),
    ],
)
def test_tandf_abstract_gate_and_challenge_shells_never_become_fulltext(
    extra_html: str,
    expected_reason: str,
) -> None:
    abstract = " ".join(
        ["This abstract describes the study and its principal findings."] * 20
    )
    html = f"""
    <html><head><title>Boundary article</title></head><body>
      <article><div class="hlFld-Fulltext">
        <div class="hlFld-Abstract">
          <h2>Abstract</h2><p>{abstract}</p>
        </div>
        {extra_html}
      </div></article>
    </body></html>
    """

    with pytest.raises(HtmlExtractionFailure) as raised:
        TandfClient(None, {}).extract_markdown(
            html,
            "https://www.tandfonline.com/doi/abs/10.1080/boundary",
            metadata={"doi": "10.1080/boundary"},
        )

    assert raised.value.reason == expected_reason


def test_tandf_multilingual_fixture_is_authentic_and_keeps_parallel_abstracts() -> None:
    markdown, extraction = _extract_fixture(MULTILINGUAL_DOI)

    assert "The affective turn and the management of conservation" in markdown
    assert "Learning analytics summaries across two languages" not in markdown
    assert [section["heading"] for section in extraction["abstract_sections"]] == [
        "Abstract",
        "Resumen",
        "الملخص",
        "Resumo",
        "摘要",
    ]
    assert "Footnote" not in markdown
    assert "care[1]" in markdown
    assert "‘networks of care’[3]" in markdown
    assert "was also cited by the majority" in markdown
    assert (
        markdown.count(
            "They are people who also contribute to the senior leadership of their "
            "institutions."
        )
        == 1
    )
    assert "## Conclusion" in markdown
    assert "### Acknowledgements" in markdown
    assert "## Additional information" in markdown
    assert "### Notes on contributors" in markdown
    assert "**Pip Laurenson**" in markdown
    assert "is Professor of Conservation, UCL" in markdown

    rendered = _render_article_markdown(MULTILINGUAL_DOI)
    assert "### Acknowledgements" in rendered
    assert "### Notes on contributors" in rendered
    assert "**Pip Laurenson**" in rendered
    assert "I would like to thank Jill Sterrett" in rendered
    assert "## References (87 total, showing 87)" in rendered
    assert "1. The first quotation in the abstract comes from" in rendered
