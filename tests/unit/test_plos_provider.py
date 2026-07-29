from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

import pytest
import yaml

from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.plos import (
    PLOS_JOURNAL_PATHS,
    PlosClient,
    _fetch_plos_redirected_response,
)
from paper_fetch.reason_codes import PDF_FALLBACK
from tests.golden_corpus import (
    build_article_from_fixture,
    golden_corpus_fixture_for_doi,
)
from tests.golden_criteria import golden_criteria_asset
from tests.unit._atypon_browser_workflow_provider_support import png_header
from tests.unit._paper_fetch_support import FixtureHtmlTransport, http_response


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "onboarding" / "manifests" / "plos.yml"
STRUCTURE_DOI = "10.1371/journal.pone.0263725"
TABLE_DOI = "10.1371/journal.pone.0304873"
FORMULA_DOI = "10.1371/journal.pone.0126635"
FIGURE_DOI = "10.1371/journal.pone.0015338"
SUPPLEMENTARY_DOI = "10.1371/journal.pone.0218513"
REFERENCES_DOI = "10.1371/journal.pone.0026949"
PDF_FALLBACK_DOI = "10.1371/journal.pbio.0040298"
STRUCTURE_XML_URL = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0263725&type=manuscript"
FIGURE_XML_URL = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0015338&type=manuscript"
PDF_FALLBACK_XML_URL = "https://journals.plos.org/plosbiology/article/file?id=10.1371/journal.pbio.0040298&type=manuscript"
PDF_FALLBACK_URL = "https://journals.plos.org/plosbiology/article/file?id=10.1371/journal.pbio.0040298&type=printable"


def _markdown_for(doi: str) -> str:
    return golden_criteria_asset(doi, "extracted.md").read_text(encoding="utf-8")


def test_plos_xml_route_replays_jats_fixture_as_fulltext() -> None:
    fixture = golden_corpus_fixture_for_doi(STRUCTURE_DOI)

    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )

    assert article.source == "plos_xml"
    assert "fulltext:plos_xml_ok" in article.quality.source_trail
    assert article.quality.content_kind == "fulltext"
    assert "## Abstract" in markdown
    assert "Download PDF" not in markdown


def test_plos_runtime_xml_route_fetches_and_converts_jats_fixture() -> None:
    fixture = golden_corpus_fixture_for_doi(STRUCTURE_DOI)
    transport = FixtureHtmlTransport(
        {
            STRUCTURE_XML_URL: http_response(
                STRUCTURE_XML_URL, fixture.raw_path.read_bytes(), "application/xml"
            )
        }
    )
    client = PlosClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(STRUCTURE_DOI, {"doi": STRUCTURE_DOI})
    article = client.to_article_model({"doi": STRUCTURE_DOI}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "xml"
    assert article.source == "plos_xml"
    assert article.quality.content_kind == "fulltext"
    assert "fulltext:plos_xml_ok" in article.quality.source_trail


def test_unknown_plos_journal_code_uses_canonical_metadata_route() -> None:
    doi = "10.1371/journal.pnew.0000001"
    client = PlosClient(FixtureHtmlTransport({}), {})

    journal_path, reason = client._resolve_journal_path(
        doi,
        {
            "doi": doi,
            "landing_page_url": (f"https://journals.plos.org/plosnew/article?id={doi}"),
        },
    )

    assert journal_path == "plosnew"
    assert reason == "metadata_landing"


def test_unknown_plos_journal_code_uses_doi_resolver_without_persisting_rule() -> None:
    doi = "10.1371/journal.pnew.0000002"
    resolver_url = f"https://doi.org/{doi}"
    canonical_url = f"https://journals.plos.org/plosnew/article?id={doi}"
    resolver_response = http_response(resolver_url, b"", "text/html")
    resolver_response["url"] = canonical_url
    client = PlosClient(
        FixtureHtmlTransport({resolver_url: resolver_response}),
        {},
    )

    journal_path, reason = client._resolve_journal_path(doi, {"doi": doi})

    assert journal_path == "plosnew"
    assert reason == "doi_resolver"
    assert "pnew" not in PLOS_JOURNAL_PATHS


def test_unknown_plos_journal_code_rejects_non_plos_resolver_target() -> None:
    doi = "10.1371/journal.pwrong.0000001"
    resolver_url = f"https://doi.org/{doi}"
    resolver_response = http_response(resolver_url, b"", "text/html")
    resolver_response["url"] = "https://example.org/article"
    client = PlosClient(
        FixtureHtmlTransport({resolver_url: resolver_response}),
        {},
    )

    with pytest.raises(ProviderFailure, match="safe journal route"):
        client._resolve_journal_path(doi, {"doi": doi})


def test_plos_runtime_xml_route_follows_relative_and_signed_redirects() -> None:
    fixture = golden_corpus_fixture_for_doi(STRUCTURE_DOI)
    encoded_candidate = (
        "https://journals.plos.org/plosone/article/file"
        "?id=10.1371%2Fjournal.pone.0263725&type=manuscript"
    )
    signed_url = (
        "https://storage.googleapis.com/plos-corpus-prod/"
        "10.1371/journal.pone.0263725/1/pone.0263725.xml"
        "?X-Goog-Algorithm=GOOG4-RSA-SHA256"
        "&X-Goog-Credential=temporary-credential"
        "&X-Goog-Signature=temporary-signature"
    )
    transport = FixtureHtmlTransport(
        {
            STRUCTURE_XML_URL: http_response(
                STRUCTURE_XML_URL,
                b"",
                "text/html",
                status_code=302,
                headers={
                    "location": (
                        "/plosone/article/file"
                        "?id=10.1371%2Fjournal.pone.0263725&type=manuscript"
                    )
                },
            ),
            encoded_candidate: http_response(
                encoded_candidate,
                b"",
                "text/html",
                status_code=302,
                headers={"location": signed_url},
            ),
            signed_url: http_response(
                signed_url, fixture.raw_path.read_bytes(), "application/xml"
            ),
        }
    )
    client = PlosClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(STRUCTURE_DOI, {"doi": STRUCTURE_DOI})
    article = client.to_article_model({"doi": STRUCTURE_DOI}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "xml"
    assert article.source == "plos_xml"
    assert "fulltext:plos_xml_ok" in article.quality.source_trail
    assert "fulltext:plos_xml_fail" not in article.quality.source_trail
    assert "temporary-credential" not in raw_payload.source_url
    assert "temporary-signature" not in raw_payload.source_url
    assert "X-Goog-Credential=%2A%2A%2A" in raw_payload.source_url
    assert "X-Goog-Signature=%2A%2A%2A" in raw_payload.source_url


def test_plos_redirect_helper_rejects_invalid_redirect_chains() -> None:
    start_url = "https://journals.plos.org/plosone/article/file?id=test"
    loop_url = "https://journals.plos.org/plosone/article/file?id=loop"
    loop_transport = FixtureHtmlTransport(
        {
            start_url: http_response(
                start_url,
                b"",
                "text/html",
                status_code=302,
                headers={"location": loop_url},
            ),
            loop_url: http_response(
                loop_url,
                b"",
                "text/html",
                status_code=302,
                headers={"location": start_url},
            ),
        }
    )
    missing_location_transport = FixtureHtmlTransport(
        {
            start_url: http_response(
                start_url,
                b"",
                "text/html",
                status_code=302,
            )
        }
    )
    invalid_scheme_transport = FixtureHtmlTransport(
        {
            start_url: http_response(
                start_url,
                b"",
                "text/html",
                status_code=302,
                headers={"location": "file:///tmp/plos.xml"},
            )
        }
    )
    redirect_urls = [
        f"https://journals.plos.org/plosone/article/file?id=hop-{index}"
        for index in range(5)
    ]
    redirect_limit_transport = FixtureHtmlTransport(
        {
            redirect_urls[index]: http_response(
                redirect_urls[index],
                b"",
                "text/html",
                status_code=302,
                headers={
                    "location": (
                        redirect_urls[index + 1]
                        if index + 1 < len(redirect_urls)
                        else f"{redirect_urls[index]}-next"
                    )
                },
            )
            for index in range(len(redirect_urls))
        }
    )

    assert (
        _fetch_plos_redirected_response(loop_transport, start_url, headers={}) is None
    )
    assert (
        _fetch_plos_redirected_response(
            missing_location_transport, start_url, headers={}
        )
        is None
    )
    assert (
        _fetch_plos_redirected_response(invalid_scheme_transport, start_url, headers={})
        is None
    )
    assert (
        _fetch_plos_redirected_response(
            redirect_limit_transport, redirect_urls[0], headers={}
        )
        is None
    )


def test_plos_xml_redirect_failure_continues_to_pdf_fallback() -> None:
    fixture = golden_corpus_fixture_for_doi(PDF_FALLBACK_DOI)
    transport = FixtureHtmlTransport(
        {
            PDF_FALLBACK_XML_URL: http_response(
                PDF_FALLBACK_XML_URL,
                b"",
                "text/html",
                status_code=302,
            ),
            PDF_FALLBACK_URL: http_response(
                PDF_FALLBACK_URL, fixture.raw_path.read_bytes(), "application/pdf"
            ),
        }
    )
    client = PlosClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(PDF_FALLBACK_DOI, {"doi": PDF_FALLBACK_DOI})
    article = client.to_article_model({"doi": PDF_FALLBACK_DOI}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == PDF_FALLBACK
    assert article.source == "plos_pdf"
    assert "fulltext:plos_xml_fail" in article.quality.source_trail
    assert "fulltext:plos_pdf_fallback_ok" in article.quality.source_trail
    assert any(
        "PLOS XML redirect chain was not usable" in warning
        for warning in article.quality.warnings
    )


def test_plos_pdf_fallback_route_uses_pdf_magic_and_rejects_html_wrapper() -> None:
    fixture = golden_corpus_fixture_for_doi(PDF_FALLBACK_DOI)
    pdf_bytes = fixture.raw_path.read_bytes()

    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )

    assert pdf_bytes.startswith(b"%PDF"), (
        "PLOS pdf_fallback fixture must preserve PDF magic bytes"
    )
    assert fixture.content_type == "application/pdf"
    assert article.source == "plos_pdf"
    assert "fulltext:plos_pdf_fallback_ok" in article.quality.source_trail
    assert "Access Denied" not in markdown
    assert "<html" not in markdown.lower(), (
        "PLOS pdf_fallback must not capture an HTML wrapper"
    )


def test_plos_runtime_pdf_fallback_rejects_html_xml_candidate() -> None:
    fixture = golden_corpus_fixture_for_doi(PDF_FALLBACK_DOI)
    html_body = (
        b"<!doctype html><html><title>Not XML</title><body>Download PDF</body></html>"
    )
    transport = FixtureHtmlTransport(
        {
            PDF_FALLBACK_XML_URL: http_response(
                PDF_FALLBACK_XML_URL, html_body, "text/html"
            ),
            PDF_FALLBACK_URL: http_response(
                PDF_FALLBACK_URL, fixture.raw_path.read_bytes(), "application/pdf"
            ),
        }
    )
    client = PlosClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(PDF_FALLBACK_DOI, {"doi": PDF_FALLBACK_DOI})
    article = client.to_article_model({"doi": PDF_FALLBACK_DOI}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == PDF_FALLBACK
    assert article.source == "plos_pdf"
    assert article.quality.content_kind == "fulltext"
    assert "fulltext:plos_xml_fail" in article.quality.source_trail
    assert "fulltext:plos_pdf_fallback_ok" in article.quality.source_trail


def test_plos_metadata_only_route_contract_is_fallback_only() -> None:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract = manifest["route_contract"]["metadata_only"]

    assert "metadata_only" in manifest["main_path"]
    assert "metadata contains DOI or title" in contract["success_requires"]
    assert "fabricated body text" in contract["reject_if_any"]


def test_plos_markdown_review_loop_non_null_fixture_contracts() -> None:
    # markdown-review: purpose=structure doi=10.1371/journal.pone.0263725
    markdown = _markdown_for(STRUCTURE_DOI)
    assert "## Abstract" in markdown
    assert (
        "Social media usage to share information in communication journals" in markdown
    )
    assert "Download PDF" not in markdown

    # markdown-review: purpose=table doi=10.1371/journal.pone.0304873
    markdown = _markdown_for(TABLE_DOI)
    assert "Table" in markdown
    assert "lookup table technique" in markdown
    assert re.search(r"(?m)^\|.+\|$", markdown)
    assert "Article metrics" not in markdown

    # markdown-review: purpose=formula doi=10.1371/journal.pone.0126635
    markdown = _markdown_for(FORMULA_DOI)
    assert "Boussinesq-Burgers Equation" in markdown
    assert "Equation" in markdown
    assert "[Formula unavailable" not in markdown

    # markdown-review: purpose=figure doi=10.1371/journal.pone.0015338
    markdown = _markdown_for(FIGURE_DOI)
    assert "Figure Text Extraction in Biomedical Literature" in markdown
    assert "![Figure 1]" in markdown
    assert "[Formula unavailable" not in markdown
    assert markdown.count("![Formula](") == 4
    assert "Article metrics" not in markdown

    # markdown-review: purpose=supplementary doi=10.1371/journal.pone.0218513
    markdown = _markdown_for(SUPPLEMENTARY_DOI)
    assert "Supporting Information" in markdown
    assert "desiccation tolerance" in markdown
    assert "Download PDF" not in markdown

    # markdown-review: purpose=references doi=10.1371/journal.pone.0026949
    markdown = _markdown_for(REFERENCES_DOI)
    assert "## References" in markdown
    assert "Non-Hodgkin Lymphoma" in markdown
    assert "Google Scholar" not in markdown

    # markdown-review: purpose=pdf_fallback doi=10.1371/journal.pbio.0040298
    markdown = _markdown_for(PDF_FALLBACK_DOI)
    assert "#" in markdown
    assert "Escherichia coli" in markdown
    assert "Access Denied" not in markdown


def test_plos_asset_download_contract_resolves_figure_doi_uri(tmp_path: Path) -> None:
    fixture = golden_corpus_fixture_for_doi(FIGURE_DOI)
    image_body = png_header(8, 8) + b"plos-figure"
    transport = FixtureHtmlTransport(
        {
            FIGURE_XML_URL: http_response(
                FIGURE_XML_URL, fixture.raw_path.read_bytes(), "application/xml"
            ),
            "https://journals.plos.org/plosone/article/figure/image?size=large&id=10.1371/journal.pone.0015338.g001": http_response(
                "https://journals.plos.org/plosone/article/figure/image?size=large&id=10.1371/journal.pone.0015338.g001",
                image_body,
                "image/png",
            ),
        }
    )
    client = PlosClient(transport, {})
    raw_payload = client.fetch_raw_fulltext(FIGURE_DOI, {"doi": FIGURE_DOI})
    article = client.to_article_model({"doi": FIGURE_DOI}, raw_payload)
    body_figures = [
        asset
        for asset in article.assets
        if asset.kind == "figure"
        and asset.section == "body"
        and asset.url.startswith("info:doi/")
    ]
    first_figure = body_figures[0].__dict__
    figure_id = first_figure["url"].removeprefix("info:doi/")
    image_url = f"https://journals.plos.org/plosone/article/figure/image?size=large&id={figure_id}"
    assert raw_payload.content is not None
    raw_payload.content = replace(raw_payload.content, extracted_assets=[first_figure])

    # asset-download-contract: provider=plos
    result = client.download_related_assets(
        FIGURE_DOI,
        {"doi": FIGURE_DOI},
        raw_payload,
        tmp_path,
        asset_profile="body",
    )
    assert result["asset_failures"] == []
    assert result["assets"][0]["downloaded_bytes"] == len(image_body)
    assert result["assets"][0]["download_url"] == image_url
    path = Path(result["assets"][0]["path"])
    assert path.is_file()
    assert path.read_bytes() == image_body

    article_with_assets = client.to_article_model(
        {"doi": FIGURE_DOI},
        raw_payload,
        downloaded_assets=result["assets"],
    )
    rendered = article_with_assets.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    assert f"![Figure 1]({path})" in rendered
    assert f"![Figure 1](info:doi/{figure_id})" not in rendered


def test_plos_asset_download_follows_signed_image_redirect(tmp_path: Path) -> None:
    fixture = golden_corpus_fixture_for_doi(FIGURE_DOI)
    image_url = "https://journals.plos.org/plosone/article/figure/image?size=large&id=10.1371/journal.pone.0015338.g001"
    redirected_url = "https://storage.googleapis.com/plos-corpus-prod/10.1371/journal.pone.0015338/1/pone.0015338.g001.PNG_L"
    image_body = png_header(9, 9) + b"plos-redirected-figure"
    transport = FixtureHtmlTransport(
        {
            FIGURE_XML_URL: http_response(
                FIGURE_XML_URL, fixture.raw_path.read_bytes(), "application/xml"
            ),
            image_url: http_response(
                image_url,
                b"",
                "",
                status_code=302,
                headers={"location": redirected_url},
            ),
            redirected_url: http_response(redirected_url, image_body, "image/png"),
        }
    )
    client = PlosClient(transport, {})
    raw_payload = client.fetch_raw_fulltext(FIGURE_DOI, {"doi": FIGURE_DOI})
    article = client.to_article_model({"doi": FIGURE_DOI}, raw_payload)
    first_figure = next(
        asset.__dict__
        for asset in article.assets
        if asset.kind == "figure" and asset.heading == "Figure 1"
    )
    raw_payload.content = replace(raw_payload.content, extracted_assets=[first_figure])

    result = client.download_related_assets(
        FIGURE_DOI,
        {"doi": FIGURE_DOI},
        raw_payload,
        tmp_path,
        asset_profile="body",
    )

    assert result["asset_failures"] == []
    assert result["assets"][0]["download_url"] == image_url
    assert result["assets"][0]["source_url"] == redirected_url
    assert result["assets"][0]["downloaded_bytes"] == len(image_body)
    assert Path(result["assets"][0]["path"]).read_bytes() == image_body


def test_plos_formula_graphic_assets_are_rendered_and_downloaded(
    tmp_path: Path,
) -> None:
    fixture = golden_corpus_fixture_for_doi(FIGURE_DOI)
    formula_url = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0015338.e001&type=thumbnail"
    image_body = png_header(10, 10) + b"plos-formula"
    transport = FixtureHtmlTransport(
        {
            FIGURE_XML_URL: http_response(
                FIGURE_XML_URL, fixture.raw_path.read_bytes(), "application/xml"
            ),
            formula_url: http_response(formula_url, image_body, "image/png"),
        }
    )
    client = PlosClient(transport, {})
    raw_payload = client.fetch_raw_fulltext(FIGURE_DOI, {"doi": FIGURE_DOI})
    article = client.to_article_model({"doi": FIGURE_DOI}, raw_payload)
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )

    assert "[Formula unavailable" not in rendered
    assert "![Formula](info:doi/10.1371/journal.pone.0015338.e001)" in rendered
    formula_asset = next(
        asset.__dict__
        for asset in article.assets
        if asset.kind == "formula"
        and asset.url == "info:doi/10.1371/journal.pone.0015338.e001"
    )
    raw_payload.content = replace(raw_payload.content, extracted_assets=[formula_asset])

    result = client.download_related_assets(
        FIGURE_DOI,
        {"doi": FIGURE_DOI},
        raw_payload,
        tmp_path,
        asset_profile="body",
    )

    assert result["asset_failures"] == []
    assert result["assets"][0]["kind"] == "formula"
    assert result["assets"][0]["download_url"] == formula_url
    assert result["assets"][0]["downloaded_bytes"] == len(image_body)
    path = Path(result["assets"][0]["path"])
    assert path.read_bytes() == image_body

    article_with_assets = client.to_article_model(
        {"doi": FIGURE_DOI},
        raw_payload,
        downloaded_assets=result["assets"],
    )
    rendered_with_assets = article_with_assets.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    assert f"![Formula]({path})" in rendered_with_assets
    assert (
        "![Formula](info:doi/10.1371/journal.pone.0015338.e001)"
        not in rendered_with_assets
    )
