from __future__ import annotations
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from tests.block_fixtures import block_asset
from tests.support._atypon_browser_workflow_provider_support import (
    AssetTransport,
    _typed_raw_payload,
)
import re
import pytest
from pathlib import Path
from unittest import mock
from bs4 import BeautifulSoup
from paper_fetch.http import RequestFailure
from paper_fetch.providers import _annualreviews_html, browser_runtime
from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
from paper_fetch.providers.annualreviews import AnnualreviewsClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers
from tests.support.captured_images import download_captured_images
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._browser_workflow_deps import install_browser_workflow_deps


HTML_DOI = "10.1146/annurev-control-030123-013355"
REFERENCES_DOI = "10.1146/annurev-environ-102511-084654"
PDF_FALLBACK_DOI = "10.1146/annurev-med-120811-171056"
FORMULA_DOI = "10.1146/annurev-neuro-062111-150343"
SUPPLEMENTARY_DOI = "10.1146/annurev-neuro-062111-150343"
HTML_SOURCE_URL = f"https://www.annualreviews.org/content/journals/{HTML_DOI}"
EMPTY_SHELL_DOI = "10.1146/annurev.pp.19.060168.001235"


def _fixture_source_url(doi: str) -> str:
    sample = golden_criteria_sample_for_doi(doi)
    return str(sample.get("source_url") or sample.get("landing_url") or "")


def _render_markdown_for_fixture(doi: str) -> str:
    if doi == PDF_FALLBACK_DOI:
        pdf_path = golden_criteria_asset(doi, "original.pdf")
        pdf_result = pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url=_fixture_source_url(doi),
            final_url=_fixture_source_url(doi),
            pdf_bytes=pdf_path.read_bytes(),
        )
        return pdf_result.markdown_text

    html = golden_criteria_asset(doi, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    markdown, _extraction = AnnualreviewsClient(None, {}).extract_markdown(
        html,
        _fixture_source_url(doi),
        metadata={"doi": doi, "title": ""},
    )
    return markdown


def _runtime_config(tmpdir: str, doi: str) -> browser_runtime.BrowserRuntimeConfig:
    tmp = Path(tmpdir)
    return browser_runtime.BrowserRuntimeConfig(
        provider="annualreviews",
        doi=doi,
        artifact_dir=tmp / "artifacts",
        headless=True,
        user_agent="paper-fetch-test/1",
    )


def test_pdf_fallback_contract_uses_pdf_magic_and_annualreviews_pdf_source() -> None:
    # route-contract: pdf_fallback annualreviews_pdf application/pdf PDF magic bytes reject HTML wrapper not a PDF text/html
    body = golden_criteria_asset(PDF_FALLBACK_DOI, "original.pdf").read_bytes()
    raw_payload = RawFulltextPayload(
        provider="annualreviews",
        source_url=f"https://www.annualreviews.org/doi/pdf/{PDF_FALLBACK_DOI}",
        content_type="application/pdf",
        body=body,
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=f"https://www.annualreviews.org/doi/pdf/{PDF_FALLBACK_DOI}",
            content_type="application/pdf",
            body=body,
            markdown_text="# Annual Reviews PDF\n\nBody text",
        ),
        trace=trace_from_markers(["fulltext:annualreviews_pdf_fallback_ok"]),
    )

    assert body.startswith(b"%PDF")
    assert (
        AnnualreviewsClient(None, {}).article_source_for_payload(raw_payload)
        == "annualreviews_pdf"
    )


def test_markdown_contract_structure_fixture() -> None:
    # markdown-review: purpose=structure doi=10.1146/annurev-control-030123-013355
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "## Abstract" in markdown
    assert "## References" in markdown
    assert re.search(r"(?m)^1\. Shah D, Yang B, Kriegman S", markdown)
    assert not re.search(r"(?m)^- Shah D, Yang B, Kriegman S", markdown)
    assert "Article metrics loading..." not in markdown
    assert "Download as PowerPoint" not in markdown


def test_markdown_contract_table_fixture() -> None:
    # markdown-review: purpose=table doi=10.1146/annurev-control-030123-013355
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "**Table 1**" in markdown
    assert "**Table 2**" in markdown
    assert (
        "| Reference | Soft, rigid, or hybrid?<sup>a</sup> | DOFs for SC<sup>b</sup> | "
        "Open-loop control<sup>c</sup> | Closed-loop control<sup>d</sup> |"
    ) in markdown
    assert (
        "| Hwang et al. (31)<sup>e</sup> | Hybrid | 1 | Shape and gait<sup>f</sup> | NA |"
        in markdown
    )
    assert "Reference\nSoft, rigid, or hybrid?" not in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown


def test_neuroscience_fixture_preserves_text_and_ion_formatting() -> None:
    # Original neuroscience HTML is text/format evidence, not a numbered equation.
    markdown = _render_markdown_for_fixture(FORMULA_DOI)
    assert (
        "The NMDA spike as a hallmark of electrogenesis in thin dendrites." in markdown
    )
    assert "I-V curve" in markdown
    assert "g max" in markdown
    assert "Na<sup>+</sup>" in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown


def test_markdown_contract_supplementary_fixture() -> None:
    # markdown-review: purpose=supplementary doi=10.1146/annurev-neuro-062111-150343
    markdown = _render_markdown_for_fixture(SUPPLEMENTARY_DOI)
    assert "Supplemental Figure 1" in markdown
    assert "Supplemental Videos 1\u20134" in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown


def test_markdown_contract_figure_fixture() -> None:
    # markdown-review: purpose=figure doi=10.1146/annurev-control-030123-013355
    markdown = _render_markdown_for_fixture(HTML_DOI)
    assert "Figure" in markdown
    assert "Download as PowerPoint" not in markdown
    assert "Article metrics loading..." not in markdown
    assert re.search(r"(?:!\[Figure|\*\*Figure|Figure\s+\d+)", markdown)


def test_markdown_contract_references_fixture() -> None:
    # markdown-review: purpose=references doi=10.1146/annurev-environ-102511-084654
    markdown = _render_markdown_for_fixture(REFERENCES_DOI)
    assert "## References" in markdown
    assert re.search(r"(?m)^1\. Gladwell M\. 2000\.", markdown)
    assert re.search(r"(?m)^2\. Grodzins M\. 1957\.", markdown)
    assert "Gladwell M. 1. 2000" not in markdown
    assert not re.search(r"(?m)^- Gladwell M\.", markdown)
    assert "Reference" in markdown
    assert "Google Scholar" not in markdown
    assert "Related Articles from Annual Reviews" not in markdown


def test_markdown_contract_pdf_fallback_fixture() -> None:
    # markdown-review: purpose=pdf_fallback doi=10.1146/annurev-med-120811-171056
    markdown = _render_markdown_for_fixture(PDF_FALLBACK_DOI)
    assert "#" in markdown
    assert "Access Denied" not in markdown


def test_extracts_authors_references_and_body_figure_assets() -> None:
    html = golden_criteria_asset(HTML_DOI, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    markdown, extraction = AnnualreviewsClient(None, {}).extract_markdown(
        html,
        HTML_SOURCE_URL,
        metadata={"doi": HTML_DOI, "title": ""},
    )

    assert extraction["extracted_authors"] == [
        "Stephanie J. Woodman",
        "Rebecca Kramer-Bottiglio",
    ]
    assert len(extraction["references"]) >= 100
    assert len(extraction["extracted_assets"]) >= 5
    assert "![Figure" in markdown


def test_article_model_uses_extracted_html_title_instead_of_doi_placeholder() -> None:
    html = golden_criteria_asset(HTML_DOI, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    client = AnnualreviewsClient(None, {})
    markdown, extraction = client.extract_markdown(
        html,
        HTML_SOURCE_URL,
        metadata={"doi": HTML_DOI, "title": HTML_DOI},
    )
    raw_payload = RawFulltextPayload(
        provider="annualreviews",
        source_url=HTML_SOURCE_URL,
        content_type="text/html",
        body=html.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=HTML_SOURCE_URL,
            content_type="text/html",
            body=html.encode("utf-8"),
            markdown_text=markdown,
            diagnostics={
                "extraction": extraction,
                "availability_diagnostics": extraction.get("availability_diagnostics"),
            },
        ),
        trace=trace_from_markers(["fulltext:annualreviews_html_ok"]),
    )

    article = client.to_article_model(
        {"doi": HTML_DOI, "title": HTML_DOI, "authors": []},
        raw_payload,
    )
    rendered = article.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )

    title = (
        "Stretchable Shape Sensing and Computation for General Shape-Changing Robots"
    )
    assert article.metadata.title == title
    assert f'title: "{title}"' in rendered
    assert f"# {title}" in rendered
    assert f"## {title}" not in rendered


def test_golden_replay_rewrites_downloaded_figure_assets_to_local_paths(
    tmp_path,
) -> None:
    html = golden_criteria_asset(HTML_DOI, "original.html").read_text()
    client = AnnualreviewsClient(None, {})
    metadata = {"doi": HTML_DOI}
    markdown, extraction = client.extract_markdown(
        html, HTML_SOURCE_URL, metadata=metadata
    )
    assets = _annualreviews_html.extract_scoped_html_assets(
        html, HTML_SOURCE_URL, asset_profile="body"
    )
    figures = [a for a in assets if a["kind"] == "figure"]
    assert len(figures) == 5
    downloaded = download_captured_images(HTML_DOI, figures, tmp_path)
    raw = _typed_raw_payload(
        provider="annualreviews",
        source_url=HTML_SOURCE_URL,
        content_type="text/html",
        body=html.encode(),
        route="html",
        markdown_text=markdown,
        browser_context_seed={},
    )
    article = client.to_article_model(metadata, raw, downloaded_assets=downloaded)
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    for asset in downloaded:
        assert Path(asset["path"]).is_file()
        assert rendered.count(f"]({asset['path']})") == 1
        assert f"]({asset['url']})" not in rendered


def test_supplementary_fixture_discovers_five_official_files_and_filters_scope():
    html = golden_criteria_asset(SUPPLEMENTARY_DOI, "original.html").read_text()
    source_url = _fixture_source_url(SUPPLEMENTARY_DOI)
    soup = BeautifulSoup(html, "lxml")
    section = soup.select_one("#supplementary_data")
    original = section.select_one("a[href]")
    import copy

    section.append(copy.copy(original))
    for href in (
        original["href"].replace(SUPPLEMENTARY_DOI, "10.1146/wrong-doi"),
        "https://evil.test" + original["href"],
        original["href"].replace(".pdf?", ".ppt?"),
        "/content/journals/multimedia/" + SUPPLEMENTARY_DOI,
    ):
        link = copy.copy(original)
        link["href"] = href
        section.append(link)
    outside = copy.copy(original)
    outside["href"] = outside["href"].replace("supmat.pdf", "outside.pdf")
    soup.body.append(outside)
    assets = _annualreviews_html.extract_scoped_html_assets(
        str(soup), source_url, asset_profile="all"
    )
    supplements = [a for a in assets if a["kind"] == "supplementary"]
    assert len(supplements) == 5
    assert len({a["url"] for a in supplements}) == 5
    assert sum(".pdf?" in a["url"] for a in supplements) == 1
    assert sum(".mpg?" in a["url"] for a in supplements) == 4
    assert supplements[1]["heading"] == "Supplemental Video 1"
    assert "subthreshold" in supplements[1]["caption"]
    for profile in ("body", "none"):
        assert not [
            a
            for a in _annualreviews_html.extract_scoped_html_assets(
                str(soup), source_url, asset_profile=profile
            )
            if a["kind"] == "supplementary"
        ]


@pytest.mark.parametrize("failed_index", [None, 2])
def test_supplementary_files_download_and_render_with_partial_failures(
    tmp_path, failed_index
):
    html = golden_criteria_asset(SUPPLEMENTARY_DOI, "original.html").read_text()
    source_url = _fixture_source_url(SUPPLEMENTARY_DOI)
    # Keep the real supplementary region; body image downloading has separate coverage.
    soup = BeautifulSoup(html, "lxml")
    for image in soup.select("img"):
        image.decompose()
    html = str(soup)
    assets = _annualreviews_html.extract_scoped_html_assets(
        html, source_url, asset_profile="all"
    )
    supplements = [a for a in assets if a["kind"] == "supplementary"]
    assert len(supplements) == 5
    responses = {}
    for index, asset in enumerate(supplements):
        url = asset["url"]
        responses[("GET", url)] = (
            RequestFailure(404, "Missing supplement", url=url)
            if index == failed_index
            else {
                "status_code": 200,
                "headers": {
                    "content-type": "application/pdf" if index == 0 else "video/mpeg"
                },
                "body": b"%PDF-1.7 supplemental PDF"
                if index == 0
                else b"\x00\x00\x01\xba" + b"video" * 30,
                "url": url,
            }
        )
    transport = AssetTransport(responses)
    client = AnnualreviewsClient(transport=transport, env={})
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(
            return_value=_runtime_config(str(tmp_path), SUPPLEMENTARY_DOI)
        ),
        ensure_runtime_ready=mock.Mock(),
        _build_shared_browser_image_fetcher=mock.Mock(return_value=None),
        _build_shared_browser_file_fetcher=mock.Mock(return_value=None),
    )
    markdown, _ = client.extract_markdown(
        html, source_url, metadata={"doi": SUPPLEMENTARY_DOI}
    )
    raw = _typed_raw_payload(
        provider="annualreviews",
        source_url=source_url,
        content_type="text/html",
        body=html.encode(),
        route="html",
        markdown_text=markdown,
        browser_context_seed={},
    )
    result = client.download_related_assets(
        SUPPLEMENTARY_DOI,
        {"doi": SUPPLEMENTARY_DOI},
        raw,
        tmp_path,
        asset_profile="all",
    )
    assert len(result["assets"]) == (5 if failed_index is None else 4)
    assert len(result["asset_failures"]) == int(failed_index is not None)
    if failed_index is not None:
        assert (
            result["asset_failures"][0]["source_url"]
            == supplements[failed_index]["url"]
        )
    article = client.to_article_model(
        {"doi": SUPPLEMENTARY_DOI},
        raw,
        downloaded_assets=result["assets"],
        asset_failures=result["asset_failures"],
    )
    rendered = article.to_ai_markdown(asset_profile="all", max_tokens="full_text")
    for downloaded in result["assets"]:
        path = Path(downloaded["path"])
        assert path.read_bytes() == responses[("GET", downloaded["source_url"])]["body"]
        matching = [
            a
            for a in article.assets
            if a.kind == "supplementary" and a.path == str(path)
        ]
        assert len(matching) == 1
        assert str(path) in rendered
    transport.calls.clear()
    for profile in ("body", "none"):
        scoped = client.download_related_assets(
            SUPPLEMENTARY_DOI,
            {"doi": SUPPLEMENTARY_DOI},
            raw,
            tmp_path,
            asset_profile=profile,
        )
        assert not scoped["assets"]
    assert not transport.calls


def test_real_numbered_equation_images_preserve_identity_and_position() -> None:
    # m0001/m0002 in sec2-1; the GIFs were visually reviewed, see reviewed-equations.json.
    doi = "10.1146/annurev-control-090419-075625"
    markdown = _render_markdown_for_fixture(doi)
    base = "https://www.annualreviews.org/docserver/ahah/fulltext/control/3/1/"
    for label, asset in (("1.", "eq-075625-001.gif"), ("2.", "eq-075625-007.gif")):
        marker = f"![Formula]({base}{asset})"
        assert f"{label}\n\n{marker}" in markdown
        assert markdown.count(marker) == 1
    assert (
        markdown.index("We formulate the system dynamics in discrete time as")
        < markdown.index("eq-075625-001.gif")
        < markdown.index("is the system state")
    )
    assert (
        markdown.index("eq-075625-001.gif")
        < markdown.index("eq-075625-007.gif")
        < markdown.index("where the expected value is taken")
    )
    import hashlib
    import json

    source = json.loads(golden_criteria_asset(doi, "source.json").read_text())
    for name, record in source["assets"].items():
        assert (
            hashlib.sha256(golden_criteria_asset(doi, name).read_bytes()).hexdigest()
            == record["sha256"]
        )


def test_real_empty_shell_does_not_promote_page_chrome_to_fulltext() -> None:
    html = block_asset(EMPTY_SHELL_DOI, "raw.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    source_url = f"https://www.annualreviews.org/content/journals/{EMPTY_SHELL_DOI}"

    (
        article_html,
        _title,
        _container_text_length,
        _section_hints,
        _abstract_sections,
        container_evidence,
    ) = _annualreviews_html._cleaned_article_html(html, source_url)

    assert container_evidence.selector == "main"
    assert container_evidence.scope == "page"
    assert container_evidence.synthetic is True
    assert "Most Read This Month" not in article_html
    assert "Most Cited" not in article_html
    assert (
        "untrusted_article_container"
        in _annualreviews_html.blocking_fallback_signals(html)
    )
    try:
        AnnualreviewsClient(None, {}).extract_markdown(
            html,
            source_url,
            metadata={"doi": EMPTY_SHELL_DOI},
        )
    except HtmlExtractionFailure as exc:
        assert exc.reason == "insufficient_body"
    else:
        raise AssertionError("Annual Reviews empty shell was accepted as full text")
