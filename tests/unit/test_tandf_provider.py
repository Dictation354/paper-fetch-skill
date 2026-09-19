from __future__ import annotations
from functools import cache
import json
from pathlib import Path
from unittest import mock
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
    assert any(
        route.browser_required or route.browser_optional for route in catalog.routes
    )
    assert catalog.provider_managed_abstract_only is True
    assert catalog.status_order == 19
    assert default_asset_profile_for_provider("tandf") == "body"
    assert SOURCE_PROVIDER_MAP["tandf_html"] == "tandf"
    assert SOURCE_PROVIDER_MAP["tandf_pdf"] == "tandf"
    assert bundle.sources == ("tandf_html", "tandf_pdf")
    assert bundle.html_rules is not None


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
    assert result["truncated"] is True
    assert result["tables_unfinished"] == 24
    links.nth.assert_not_called()
    page.evaluate.assert_not_called()


def test_tandf_csv_tables_continue_beyond_first_batch() -> None:
    def link_for(index: int):
        table_id = f"t{index:04d}"
        link = mock.Mock()
        link.get_attribute.side_effect = lambda name: (
            f"/action/downloadTable?id={table_id}&downloadType=CSV"
            if name == "href"
            else None
        )
        link.evaluate.return_value = f"{table_id}-table-wrapper"
        return link

    links = mock.Mock()
    links.count.return_value = 25
    links.nth.side_effect = link_for
    page = mock.Mock()
    page.locator.return_value = links

    def evaluate(script, arguments):
        if script == _tandf_html._TANDF_FETCH_TABLE_CSV_BATCH_SCRIPT:
            return {
                "results": [
                    {
                        "ok": True,
                        "contentType": "text/csv",
                        "text": f"Column\n{entry['tableId']}",
                    }
                    for entry in arguments["entries"]
                ],
                "timedOut": False,
                "concurrency": min(4, len(arguments["entries"])),
            }
        if script == _tandf_html._TANDF_INJECT_TABLE_SCRIPT:
            return True
        if script == _tandf_html._TANDF_READ_EMBEDDED_TABLES_SCRIPT:
            return {"total": 0, "tables": []}
        raise AssertionError("unexpected page script")

    page.evaluate.side_effect = evaluate

    result = _tandf_html.prepare_browser_page(page, timeout_ms=10_000)

    assert result["tables_hydrated"] == 25
    assert result["csv_tables_hydrated"] == 25
    assert result["truncated"] is False
    batch_calls = [
        call
        for call in page.evaluate.call_args_list
        if call.args[0] == _tandf_html._TANDF_FETCH_TABLE_CSV_BATCH_SCRIPT
    ]
    assert [len(call.args[1]["entries"]) for call in batch_calls] == [24, 1]


def test_tandf_embedded_tables_continue_beyond_first_batch() -> None:
    links = mock.Mock()
    links.count.return_value = 0
    page = mock.Mock()
    page.locator.return_value = links

    def evaluate(script, arguments):
        if script == _tandf_html._TANDF_READ_EMBEDDED_TABLES_SCRIPT:
            start = arguments["start"]
            stop = min(25, start + arguments["batchSize"])
            return {
                "total": 25,
                "tables": [
                    {
                        "tableId": f"ut{index:04d}",
                        "caption": f"Table {index}",
                        "rows": [["Column"], [str(index)]],
                    }
                    for index in range(start, stop)
                ],
            }
        if script == _tandf_html._TANDF_INJECT_TABLE_SCRIPT:
            return True
        raise AssertionError("unexpected page script")

    page.evaluate.side_effect = evaluate

    result = _tandf_html.prepare_browser_page(page, timeout_ms=10_000)

    assert result["embedded_tables"] == 25
    assert result["embedded_tables_hydrated"] == 25
    assert result["tables_hydrated"] == 25
    assert result["truncated"] is False
    embedded_calls = [
        call
        for call in page.evaluate.call_args_list
        if call.args[0] == _tandf_html._TANDF_READ_EMBEDDED_TABLES_SCRIPT
    ]
    assert [call.args[1]["start"] for call in embedded_calls] == [0, 24]


@pytest.mark.parametrize(
    ("entry_id", "original", "promoted"),
    [
        (
            "F0002",
            "/cms/asset/3eb40468-4dd1-4d1d-83de-9b03067fd963/tjde_a_2137254_f0002_oc.jpg",
            True,
        ),
        ("F0003", "/cms/asset/original/figure.jpg", False),
        ("F0002", "https://other.example/cms/asset/figure.jpg", False),
        ("F0002", "javascript:alert(1)", False),
        ("F0002", "https://[broken/cms/asset/figure.jpg", False),
    ],
)
def test_tandf_viewer_original_survives_body_scope_cleanup(
    entry_id: str, original: str, promoted: bool
) -> None:
    preview = (
        "/cms/asset/d019a1ff-f502-4d07-9371-ab8bc365f975/tjde_a_2137254_f0002_oc.jpg"
    )
    payload = {"figures": [{"id": entry_id, "content": f'<img src="{original}"/>'}]}
    html = f'''<div class="hlFld-Fulltext"><div class="figureView">
      <div class="short-legend">Figure 2. Conceptual model.</div>
      <a data-popup-event-type="fig" data-id="F0002"><img src="{preview}"/></a>
      <button data-popup-event-type="fig" data-id="F0002">Display full size</button>
      </div></div><script>tandf.tfviewerdata={json.dumps(payload)};</script>'''
    source = "https://www.tandfonline.com/doi/full/10.1080/17538947.2022.2137254"
    body, supplementary = extract_browser_workflow_asset_html_scopes(
        html, source, "tandf"
    )
    assert "<script" not in body
    assets = _tandf_html.scoped_asset_extractor(
        body, source, asset_profile="body", supplementary_html_text=supplementary
    )
    assert len(assets) == 1
    asset = assets[0]
    assert asset["preview_url"] == "https://www.tandfonline.com" + preview
    if promoted:
        assert asset["full_size_url"] == "https://www.tandfonline.com" + original
        assert "official_full_size_not_exposed" not in asset.get("provenance", [])
    else:
        assert not asset.get("full_size_url")
        assert asset["provenance"] == ["official_full_size_not_exposed"]


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
