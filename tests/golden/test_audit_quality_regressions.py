"""Source-backed audit regressions; historical captures are not live evidence."""

from pathlib import Path
import re

from bs4 import BeautifulSoup
import pytest

from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.golden_criteria import golden_criteria_asset
from tests.support.replay import build_article_from_fixture
from tests.support.reviewed_publisher_content import _words
from paper_fetch.models import article_from_markdown

ROOT = Path(__file__).resolve().parents[1] / "fixtures/golden_criteria"


def test_gan_panel_table_rows_survive_final_rendering():
    fixture = golden_corpus_fixture_for_doi("10.48550/arxiv.1406.2661v1")
    from paper_fetch.providers._arxiv_html import _extract_arxiv_html_markdown

    source = golden_criteria_asset(
        fixture.doi,
        next(
            key
            for key in fixture.sample["assets"]
            if "official-reacquisition-2026-09-19/raw_sources/" in key
            and key.endswith(".html")
        ),
    ).read_text()
    soup = BeautifulSoup(source, "lxml")
    extraction = _extract_arxiv_html_markdown(
        source,
        "https://arxiv.org/html/1406.2661v1",
        metadata={"title": fixture.title, "arxiv_id": "1406.2661v1"},
    )
    from paper_fetch.providers.arxiv import ArxivClient
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    atom = BeautifulSoup(
        (
            ROOT
            / "10.48550_arxiv.1406.2661v1/acquisition/source-completion-2026-09-18/002-http_response_entity.xml"
        ).read_bytes(),
        "xml",
    )
    authors = [
        author.find("name").get_text(" ", strip=True)
        for author in atom.find_all("author")
    ]
    assert len(authors) == 8
    client = ArxivClient(FixtureHtmlTransport({}), {})
    payload = client._payload_with_api_metadata(
        RawFulltextPayload(
            provider="arxiv",
            content=ProviderContent(
                route_kind="html",
                content_type="text/html",
                body=source.encode(),
                source_url="https://arxiv.org/html/1406.2661v1",
                markdown_text=extraction.markdown_text,
                merged_metadata=extraction.merged_metadata,
            ),
        ),
        derived_metadata={"arxiv_id": "1406.2661v1"},
        api_metadata={"authors": authors},
        metadata_warnings=[],
    )
    enriched_article = client.to_article_model({"doi": fixture.doi}, payload)
    assert enriched_article.metadata.authors == authors
    article = article_from_markdown(
        doi=fixture.doi,
        source="arxiv_html",
        metadata={"title": fixture.title},
        markdown_text=extraction.markdown_text,
    )
    md = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    for figure_id in ["S3.F1", "S5.F2"]:
        figure = soup.find(id=figure_id)
        for row in figure.select("table tr"):
            labels = [
                c.get_text(" ", strip=True) for c in row.find_all("td", recursive=False)
            ]
            labels = [label for label in labels if label]
            if labels:
                assert any(
                    all(label in line for label in labels)
                    for line in md.splitlines()
                    if line.startswith("|")
                )
    assert not any(line.strip() == "|" for line in md.splitlines())
    assert any(
        line.count("![") >= 4 for line in md.splitlines() if line.startswith("|")
    )


def test_forest_body_order_and_extended_table_entry_match_source():
    fixture = golden_corpus_fixture_for_doi("10.1038/s41586-020-1941-5")
    soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
    article = build_article_from_fixture(fixture)
    md = article.to_ai_markdown(max_tokens="full_text")
    assert (
        md.index("Arising from:")
        < md.index("Planting and removal")
        < md.index("The record length")
        < md.index("## Reporting summary")
    )
    assert not article.metadata.abstract
    caption = soup.select_one(".c-article-table__figcaption").get_text(" ", strip=True)
    assert caption in md
    assert "https://www.nature.com/articles/s41586-020-1941-5/tables/1" in md

    from paper_fetch.providers.springer import SpringerClient
    from paper_fetch.providers._springer_markdown import extract_html_payload
    from paper_fetch.runtime import RuntimeContext
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    transport = FixtureHtmlTransport({})
    with RuntimeContext(env={}, transport=transport) as context:
        prepared, entries, warnings, assets = SpringerClient(
            transport, {}
        )._prepare_html_with_inline_tables(
            str(soup),
            fixture.source_url,
            context=context,
            asset_profile="body",
        )
    assert not entries and not warnings and not assets
    extraction = extract_html_payload(prepared, fixture.source_url, title=fixture.title)
    prepared_article = article_from_markdown(
        doi=fixture.doi,
        source="springer_html",
        metadata={"title": fixture.title},
        markdown_text=extraction["markdown_text"],
        abstract_sections=extraction["abstract_sections"],
        section_hints=extraction["section_hints"],
    )
    prepared_md = prepared_article.to_ai_markdown(
        asset_profile="body", max_tokens="full_text"
    )
    assert caption in prepared_md
    assert "https://www.nature.com/articles/s41586-020-1941-5/tables/1" in prepared_md


@pytest.mark.parametrize(
    "doi", ["10.1098/rsos.150470", "10.1080/10942912.2019.1597882"]
)
def test_multiline_publisher_title_forms_one_complete_h1(doi):
    from markdown_it import MarkdownIt
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from paper_fetch.providers.royalsocietypublishing import (
        RoyalsocietypublishingClient,
    )
    from paper_fetch.providers.tandf import TandfClient
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    fixture = golden_corpus_fixture_for_doi(doi)
    source = fixture.raw_path.read_text()
    soup = BeautifulSoup(source, "lxml")
    title = soup.h1.get_text(" ", strip=True)
    client_cls = (
        RoyalsocietypublishingClient if doi.startswith("10.1098/") else TandfClient
    )
    client = client_cls(FixtureHtmlTransport({}), {})
    metadata = {"doi": doi, "title": title}
    markdown, extraction = client.extract_markdown(
        source, fixture.source_url, metadata=metadata
    )
    article = client.to_article_model(
        metadata,
        RawFulltextPayload(
            provider=client.name,
            content=ProviderContent(
                route_kind="html",
                content_type="text/html",
                body=source.encode(),
                source_url=fixture.source_url,
                markdown_text=markdown,
                merged_metadata=metadata,
                diagnostics={"extraction": extraction},
            ),
        ),
    )
    rendered = article.to_ai_markdown(max_tokens="full_text").split("\n---\n", 1)[1]
    tokens = MarkdownIt().parse(rendered)
    titles = [
        tokens[i + 1].content
        for i, token in enumerate(tokens)
        if token.type == "heading_open" and token.tag == "h1"
    ]
    assert titles == [" ".join(title.split())]


@pytest.mark.parametrize(
    "doi, prefix",
    [("10.1021/acsomega.4c03987", "4.1."), ("10.1021/acsomega.3c06992", "2.1.")],
)
def test_acs_original_multiline_section_is_one_final_heading(doi, prefix):
    from markdown_it import MarkdownIt
    from paper_fetch.providers.acs import AcsClient
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    fixture = golden_corpus_fixture_for_doi(doi)
    source = (
        (
            ROOT
            / "10.1021_acsomega.4c03987/acquisition/template-browser-2026-09-16/000-browser_rendered_dom.html"
        ).read_text()
        if doi.endswith("4c03987")
        else fixture.raw_path.read_text()
    )
    soup = BeautifulSoup(source, "lxml")
    heading = next(
        node for node in soup.select("h2,h3,h4") if node.get_text().startswith(prefix)
    )
    expected = " ".join(heading.get_text(" ", strip=True).split())
    client = AcsClient(FixtureHtmlTransport({}), {})
    metadata = {"doi": doi, "title": fixture.title}
    markdown, extraction = client.extract_markdown(
        source, fixture.source_url, metadata=metadata
    )
    article = client.to_article_model(
        metadata,
        RawFulltextPayload(
            provider="acs",
            content=ProviderContent(
                route_kind="html",
                content_type="text/html",
                source_url=fixture.source_url,
                body=source.encode(),
                markdown_text=markdown,
                merged_metadata=metadata,
                diagnostics={"extraction": extraction},
            ),
        ),
    )
    tokens = MarkdownIt().parse(article.to_ai_markdown(max_tokens="full_text"))
    headings = [
        tokens[i + 1].content
        for i, token in enumerate(tokens)
        if token.type == "heading_open"
    ]
    assert expected in headings


@pytest.mark.parametrize("doi", ["10.1111/cas.16117", "10.1111/cas.16395"])
def test_wiley_references_have_one_number_per_citation(doi):
    from paper_fetch.providers._wiley_html import finalize_extraction
    from paper_fetch.models.builders import build_references

    source = golden_criteria_asset(
        doi,
        "acquisition/provenance-repair-2026-09-17/000-browser_rendered_dom.html"
        if doi.endswith("16117")
        else "original.html",
    ).read_text()
    _, extraction = finalize_extraction(
        source, "https://onlinelibrary.wiley.com/doi/" + doi, "", {}
    )
    references = build_references(extraction["references"])
    original = BeautifulSoup(source, "lxml").select("li[data-bib-id]")
    assert len(references) == len(original)
    for index, reference in enumerate(references, 1):
        assert reference.raw.startswith(f"{index}. ")
        assert not re.match(r"^\d+\.\s+\d+\s", reference.raw)


@pytest.mark.parametrize(
    "doi, title",
    [
        (
            "10.5194/acp-1-1-2001",
            "298 K rate coefficients for the reaction of OH with <i>i</i> - C<sub>3</sub> H<sub>7</sub> I, <i>n</i> - C<sub>3</sub> H<sub>7</sub> I and C<sub>3</sub> H<sub>8</sub>",
        ),
        (
            "10.5194/bg-1-1-2004",
            "A field-based method for simultaneous measurements of the δ<sup>18</sup> O and δ<sup>13</sup> C of soil CO<sub>2</sub> efflux",
        ),
    ],
)
def test_copernicus_pdf_identity_accepts_publisher_title_markup(
    doi, title, monkeypatch, tmp_path
):
    from paper_fetch.providers import copernicus, _pdf_common
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    fixture = golden_corpus_fixture_for_doi(doi)
    body = fixture.raw_path.read_bytes()
    results = []
    monkeypatch.setattr(
        _pdf_common,
        "render_pdf_markdown_result",
        lambda *a, **kw: _pdf_common.PdfMarkdownRenderResult(
            markdown_text="Opaque converter output", assets=[]
        ),
    )

    def captured_pdf(_transport, candidates, **kwargs):
        result = _pdf_common.pdf_fetch_result_from_bytes(
            artifact_dir=tmp_path,
            source_url=candidates[0],
            final_url=candidates[0],
            pdf_bytes=body,
            expected_identity=kwargs["expected_identity"],
        )
        results.append(result)
        return result

    monkeypatch.setattr(copernicus, "fetch_pdf_over_http", captured_pdf)
    attempt = copernicus.CopernicusLandingAttempt(
        doi,
        fixture.source_url,
        fixture.source_url,
        "",
        {},
        {"doi": doi, "title": title},
        [],
        [fixture.source_url],
    )
    payload = copernicus.CopernicusClient(
        FixtureHtmlTransport({}), {}
    )._fetch_pdf_payload(attempt, xml_failure_message="No XML", warnings=[])
    assert results[0].diagnostics["identity"]["status"] == "match"
    assert results[0].diagnostics["identity"]["method"] == "pdf_opening_title"
    assert payload.content.markdown_text == "Opaque converter output"
    assert payload.content.body == body
    assert payload.content.merged_metadata["title"] == title


def test_copernicus_empty_xrefs_match_original_target_labels():
    from paper_fetch.providers._article_markdown_copernicus import parse_copernicus_xml

    fixture = golden_corpus_fixture_for_doi("10.5194/hess-28-1-2024")
    source = fixture.raw_path.read_bytes()
    soup = BeautifulSoup(source, "xml")
    result = parse_copernicus_xml(source, source_url=fixture.source_url)
    assert "(Fig.)" not in result.markdown_text
    assert "(Table)" not in result.markdown_text
    assert "(Fig. Figure" not in result.markdown_text
    assert "(Table Table" not in result.markdown_text
    assert "(Fig. 1)" in result.markdown_text
    assert "(Table 1)" in result.markdown_text
    xrefs = [
        n
        for n in soup.select('xref[ref-type="fig"], xref[ref-type="table"]')
        if not n.get_text(strip=True)
    ]
    assert len(xrefs) >= 11
    for node in xrefs:
        label = soup.find(id=node["rid"]).find("label").get_text(strip=True)
        assert re.sub(r"^(?:Figure|Table)\s+", "", label) in result.markdown_text


def test_copernicus_scientific_heading_math_is_retained():
    fixture = golden_corpus_fixture_for_doi("10.5194/acp-24-1-2024")
    source = BeautifulSoup(fixture.raw_path.read_bytes(), "xml")
    assert (
        len(
            [
                t
                for t in source.select("sec > title")
                if t.find("math") and "Singlet" in t.get_text()
            ]
        )
        == 2
    )
    article = build_article_from_fixture(fixture)
    headings = [s.heading for s in article.sections]
    assert (
        sum(
            "$" in heading and "O" in heading and ("^" in heading or "_{" in heading)
            for heading in headings
        )
        >= 2
    )


@pytest.mark.parametrize(
    "doi",
    [
        "10.1093/bioinformatics/btaa823",
        "10.1093/bioinformatics/btaa161",
        "10.1093/bioinformatics/btaa153",
    ],
)
def test_oup_final_abstract_contains_content_once(doi):
    from paper_fetch.providers._oxfordacademic_html import extract_markdown

    fixture = golden_corpus_fixture_for_doi(doi)
    path = (
        golden_criteria_asset(
            doi,
            "acquisition/source-completion-2026-09-18/001-http_response_entity.html",
        )
        if doi.endswith("153")
        else fixture.raw_path
    )
    extraction = extract_markdown(
        path.read_text(),
        "https://academic.oup.com/article",
        metadata={"doi": doi, "title": fixture.title},
    )
    article = article_from_markdown(
        doi=doi,
        source="oxfordacademic_html",
        metadata=extraction.metadata,
        markdown_text=extraction.markdown_text,
        abstract_sections=extraction.abstract_sections,
        section_hints=extraction.section_hints,
    )
    assert article.metadata.abstract and article.metadata.abstract != "Abstract"
    assert len([s for s in article.sections if s.kind == "abstract"]) == 1
    assert not any(s.text == "Abstract" for s in article.sections)


@pytest.mark.parametrize(
    "doi",
    [
        "10.1371/journal.pbio.0040298",
        "10.1371/journal.pone.0026949",
        "10.1371/journal.pcbi.1003118",
    ],
)
def test_plos_original_structured_author_names_remain_separated(doi):
    from paper_fetch.providers.plos import parse_plos_xml

    source = golden_criteria_asset(
        doi, "acquisition/source-completion-2026-09-18/001-http_response_entity.xml"
    ).read_bytes()
    soup = BeautifulSoup(source, "xml")
    extraction = parse_plos_xml(
        source, source_url="https://journals.plos.org/article/file?id=" + doi
    )
    assert extraction is not None
    originals = soup.select("ref-list > ref")
    assert len(originals) == len(extraction.references) > 0
    names_checked = 0
    for original, ref in zip(originals, extraction.references, strict=True):
        for name in original.select("name"):
            expected = " ".join(
                " ".join(c.get_text(strip=True).split())
                for c in name.find_all(recursive=False)
            )
            assert re.search(
                r"(?<!\w)" + re.escape(expected) + r"(?!\w)", ref["raw"]
            ), (expected, ref["raw"])
            names_checked += 1
    assert names_checked > 0


@pytest.mark.parametrize("missing_table", [False, True])
def test_acs_table_graphic_counts_toward_strict_local_acceptance(
    tmp_path, missing_table
):
    from paper_fetch.models import FetchEnvelope
    from paper_fetch.quality.assets import build_asset_quality_summary
    from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance

    fixture = golden_corpus_fixture_for_doi("10.1021/acsomega.4c03987")
    from paper_fetch.providers._acs_html import scoped_asset_extractor
    from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
        extract_browser_workflow_asset_html_scopes,
    )
    from paper_fetch.providers.atypon_browser_workflow.markdown import (
        extract_browser_workflow_markdown,
    )

    source = (
        ROOT
        / "10.1021_acsomega.4c03987/acquisition/template-browser-2026-09-16/000-browser_rendered_dom.html"
    ).read_text()
    url = "https://pubs.acs.org/doi/10.1021/acsomega.4c03987"
    body, _ = extract_browser_workflow_asset_html_scopes(source, url, "acs")
    assets = scoped_asset_extractor(body, url, asset_profile="body")
    markdown, extraction = extract_browser_workflow_markdown(
        source, url, "acs", metadata={"doi": fixture.doi, "title": fixture.title}
    )
    from paper_fetch.providers.acs import AcsClient
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from paper_fetch.providers.browser_workflow.assets import (
        _merge_download_attempt_results,
    )
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    for index, asset in enumerate(assets):
        if missing_table and "ao4c03987_0009" in str(asset.get("preview_url")):
            continue
        asset["path"] = str(tmp_path / f"{index}.png")
        Path(asset["path"]).write_bytes(b"local boundary")
    merged = _merge_download_attempt_results({"assets": assets}, {"assets": []})
    metadata = {"doi": fixture.doi, "title": fixture.title}
    article = AcsClient(FixtureHtmlTransport({}), {}).to_article_model(
        metadata,
        RawFulltextPayload(
            provider="acs",
            content=ProviderContent(
                route_kind="html",
                content_type="text/html",
                body=source.encode(),
                source_url=url,
                markdown_text=markdown,
                merged_metadata=metadata,
                diagnostics={"extraction": extraction},
            ),
        ),
        downloaded_assets=merged["assets"],
    )
    images = [a for a in article.assets if "ao4c03987_0009" in str(a.original_url)]
    assert len(images) == 1
    assert len(article.assets) == 10
    rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    if not missing_table:
        assert "silverchair-cdn.com" not in rendered
        assert images[0].path in rendered
    article.quality.asset_summary = build_asset_quality_summary(
        article.assets, asset_profile="body", archive_enabled=True
    )
    acceptance = evaluate_fetch_acceptance(
        FetchEnvelope(
            doi=fixture.doi, source=article.source, article=article, has_fulltext=True
        ),
        asset_profile="body",
        require_local_body_assets=True,
    )
    assert acceptance.asset.body_discovered == 10
    assert acceptance.asset.body_local == (9 if missing_table else 10)
    assert acceptance.asset.local_body_assets_satisfied is (not missing_table)
    if missing_table:
        assert acceptance.overall != "complete"


def test_science_complete_captured_bibliography_covers_reference_55():
    from paper_fetch.providers._science_html import finalize_extraction

    source = (
        ROOT
        / "10.1126_science.abo2812/acquisition/template-browser-2026-09-16/000-browser_rendered_dom.html"
    ).read_text()
    _, extraction = finalize_extraction(
        source, "https://www.science.org/doi/10.1126/science.abo2812", "", {}
    )
    assert len(extraction["references"]) == 100
    assert "Dead Sea" in extraction["references"][54]["raw"]
    assert not extraction.get("missing_reference_targets")


@pytest.mark.parametrize(
    "doi", ["10.1098/rsos.201188", "10.1098/rsta.2020.0108", "10.1098/rsos.201200"]
)
def test_royal_source_citation_fields_override_metadata_dois(doi):
    from paper_fetch.providers._royalsocietypublishing_html import (
        merge_metadata_with_html,
    )

    source = golden_criteria_asset(
        doi, "acquisition/source-completion-2026-09-18/001-browser_rendered_dom.html"
    ).read_text()
    soup = BeautifulSoup(source, "lxml")
    originals = soup.select(".ref-list .ref")
    result = merge_metadata_with_html(
        {"references": [{"raw": "10.1234/metadata", "doi": "10.1234/metadata"}]},
        source,
        "https://royalsocietypublishing.org/doi/" + doi,
    )
    assert len(originals) == len(result["references"])
    for original, reference in zip(originals, result["references"], strict=True):
        for field in original.select(".surname, .article-title, .year"):
            assert _words(field.get_text(" ", strip=True)) in _words(reference["raw"])
