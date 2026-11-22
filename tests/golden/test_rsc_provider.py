from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import replace
from urllib.parse import urljoin, urlsplit

import pytest
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

from paper_fetch.extraction.image_payloads import image_dimensions_from_bytes
from paper_fetch.providers._pdf_common import (
    PdfFetchFailure,
    pdf_fetch_result_from_bytes,
    render_pdf_markdown,
)
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
)
from paper_fetch.providers.browser_workflow.asset_download import (
    plan_browser_asset_download,
)
from paper_fetch.providers.rsc import RscClient
from paper_fetch.runtime import RuntimeContext
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support.canonical_content import source_soup
from tests.support.replay import build_article_from_fixture, persisted_fixture_markdown
from tests.support.scientific_content import scientific_text_key

DOI = "10.1039/d5gc03562g"
HTML_DOIS = (
    "10.1039/d5sc03855c",
    "10.1039/d5mh02051d",
    "10.1039/c4sc02365j",
    DOI,
)


def _dom_key(node):
    clone = deepcopy(node)
    for script in reversed(clone.find_all(["sup", "sub"])):
        marker = "^" if script.name == "sup" else "_"
        script.replace_with(f"{marker}{{{script.get_text()}}}")
    return scientific_text_key(clone.get_text())


def _replay_client(tmp_path, sample, html):
    client = RscClient(None, {})
    config = BrowserRuntimeConfig("rsc", sample["doi"], tmp_path, True, None)
    page = BrowserFetchedHtml(
        source_url=sample["landing_url"],
        final_url=sample["source_url"],
        html=html,
        response_status=200,
        response_headers={"content-type": "text/html"},
        title=sample["title"],
        summary="",
        browser_context_seed={},
    )
    client.deps = replace(
        client.deps,
        load_runtime_config=lambda *args, **kwargs: config,
        ensure_runtime_ready=lambda config: None,
        fetch_html_with_browser=lambda *args, **kwargs: page,
    )
    return client


def test_rsc_silverchair_golden_html_keeps_sections_references_and_asset_ownership(
    tmp_path,
) -> None:
    sample = golden_criteria_sample_for_doi(DOI)
    html = golden_criteria_asset(DOI, "original.html").read_text()
    client = _replay_client(tmp_path, sample, html)
    result = client.fetch_result(
        DOI,
        {"doi": DOI, "landing_page_url": sample["landing_url"]},
        None,
        asset_profile="all",
    )
    article = result.article
    assert article.source == "rsc_html"
    assert article.quality.content_kind == "fulltext"
    assert article.acquisition.route == "browser_html"
    headings = [section.heading for section in article.sections]
    expected_headings = [
        "Introduction",
        "Results and discussion",
        "Conclusions",
        "Experimental",
    ]
    assert [
        heading for heading in headings if heading in expected_headings
    ] == expected_headings
    assert len(article.references) == 64
    assert article.references[0].doi == "10.1016/j.wasman.2007.09.011"

    extraction = result.content.diagnostics["extraction"]
    assets = extraction["extracted_assets"]
    figure = next(asset for asset in assets if asset["heading"] == "Fig. 1")
    assert figure["kind"] == "figure" and figure["section"] == "body"
    assert urlsplit(figure["url"]).path.endswith(
        "/10.1039_d5gc03562g/1/d5gc03562g-f1.png"
    )
    assert "Characterisation of the prepared photocatalysts" in figure["caption"]
    markdown = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert markdown.count("![Figure 1](") == 1
    supplements = [asset for asset in assets if asset["kind"] == "supplementary"]
    assert len(supplements) == 1
    assert supplements[0]["section"] == "supplementary"
    assert (
        supplements[0]["url"]
        == "https://pubs.rsc.org/gc/article-supplement/894100/pdf/d5gc03562g1_suppl/"
    )
    assert supplements[0]["source_page_url"] == sample["source_url"]


@pytest.mark.parametrize("doi", HTML_DOIS)
def test_rsc_reviewed_markdown_and_captured_images_follow_article_dom(doi, tmp_path):
    fixture = golden_corpus_fixture_for_doi(doi)
    article = build_article_from_fixture(fixture)
    snapshot = golden_criteria_asset(doi, "extracted.md")
    markdown = persisted_fixture_markdown(fixture, article)
    assert markdown == snapshot.read_text()
    assert article.source == "rsc_html"
    page = source_soup(fixture)
    body = page.select_one(".widget-ArticleFulltext")
    assert body.select_one(".fig-modal .original-slide")
    assert body.select_one(".permissionstatement-section-wrapper .license-icon")
    assert page.select_one("nav, .vt-toolbar-wrap")

    output = BeautifulSoup(MarkdownIt().render(markdown), "lxml")
    source_images = [
        img
        for img in body.select("img.content-image[data-src]")
        if not img.find_parent(class_=["fig-modal", "table-modal"])
    ]
    records = json.loads(
        golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
    )["records"]
    original_by_file = {record["body_file"]: record for record in records}
    resolved_paths = [img["src"] for img in output.select("img")]
    assert len(resolved_paths) == len(set(resolved_paths)) == len(records)
    assert set(resolved_paths) == set(original_by_file)
    for src, dest in zip(source_images, resolved_paths, strict=True):
        record = original_by_file[dest]
        assert src["data-src"] == record["source_image_url"]
        assert record["article_url"] == fixture.source_url
        data = (snapshot.parent / dest).read_bytes()
        assert len(data) == record["size"]
        assert hashlib.sha256(data).hexdigest() == record["sha256"]
        assert image_dimensions_from_bytes(data) == (record["width"], record["height"])

    for original, rendered in zip(
        body.select(".table-overflow > table"), output.select("table"), strict=True
    ):
        for expected, actual in zip(
            original.select("th, td"), rendered.select("th, td"), strict=True
        ):
            assert [img["data-src"] for img in expected.select("img")] == [
                original_by_file[img["src"]]["source_image_url"]
                for img in actual.select("img")
            ]

    client = RscClient(None, {})
    with RuntimeContext(env={}) as context:
        plan = plan_browser_asset_download(
            article_id=doi,
            output_dir=tmp_path,
            html_text=fixture.raw_path.read_text(),
            source_url=fixture.source_url,
            profile={"client": client, "context": context, "asset_profile": "all"},
            deps=client.deps,
        )
    by_preview = {asset["preview_url"]: asset["kind"] for asset in plan.body_assets}
    assert by_preview == {
        record["source_image_url"]: record["capture_kind"] for record in records
    }
    entries = [
        (urljoin(fixture.source_url, a["href"]), a.get_text(" ", strip=True))
        for a in page.select(".widget-ArticleDataSupplements a[href]")
    ]
    pdf_url = urljoin(
        fixture.source_url, page.select_one('meta[name="citation_pdf_url"]')["content"]
    )
    assert client.pdf_candidates_from_html(
        fixture.raw_path.read_text(), fixture.source_url, doi=doi
    ) == [pdf_url]
    assert pdf_url not in {url for url, _heading in entries}
    assert [(a["url"], a["heading"]) for a in plan.supplementary_assets] == entries
    article_id = urlsplit(fixture.source_url).path.split("/")[6]
    for asset, (url, _heading) in zip(plan.supplementary_assets, entries, strict=True):
        assert f"/article-supplement/{article_id}/" in url
        assert doi.split("/")[1] in url
        assert asset["source_page_url"] == fixture.source_url
        assert output.find("a", href=url)
    assert not re.search(
        r"Formula unavailable|preloader\.gif|Alt-text is not available|Creative Commons|"
        r"View large|Download slide|Open figure viewer|Skip to Main Content|"
        r"<(?:html|body|div|nav|button)\b|javascript:|license-icon",
        markdown,
        re.I,
    )


@pytest.mark.parametrize("doi", HTML_DOIS)
def test_rsc_abstract_headings_notes_and_formulas_keep_source_content(doi):
    fixture = golden_corpus_fixture_for_doi(doi)
    article = build_article_from_fixture(fixture)
    markdown = persisted_fixture_markdown(fixture, article)
    source = source_soup(fixture).select_one(".widget-ArticleFulltext")
    output = BeautifulSoup(MarkdownIt().render(markdown), "lxml")
    abstracts = [section for section in article.sections if section.kind == "abstract"]
    expected_title = source.select_one(".graphical-abstract-label").get_text(strip=True)
    assert [section.heading for section in abstracts] == ["Abstract", expected_title]
    for section, selector in zip(
        abstracts,
        (".abstract", ".graphical-abstract .fig-section .fig-caption"),
        strict=True,
    ):
        expected = _dom_key(source.select_one(selector))
        assert scientific_text_key(section.text) == expected
        assert markdown.count(f"## {section.heading}\n") == 1
    assert (
        scientific_text_key(markdown).count(scientific_text_key(abstracts[0].text)) == 1
    )
    headings = [
        (tag.name, tag.get_text(" ", strip=True))
        for tag in source.select(
            ".section-title, .boxed-text h3, .dataavailabilitystatement-title, .backacknowledgements-title, .footNotes-section-title"
        )
    ]
    rendered_headings = [
        (tag.name, tag.get_text(" ", strip=True))
        for tag in output.select("h2,h3,h4,h5")
    ]
    assert [heading for heading in rendered_headings if heading in headings] == headings

    for original in source.select(".formula-wrap"):
        number = original.select_one(":scope > .label").get_text(strip=True)
        formula = original.select_one(".disp-formula")
        if image := formula.select_one("img"):
            name = urlsplit(image["data-src"]).path.rsplit("/", 1)[-1]
            assert f"![Formula](body_assets/{name}) {number}" in markdown.splitlines()
        else:
            expected = _dom_key(formula)
            matches = [
                line for line in markdown.splitlines() if line.endswith(f" {number}")
            ]
            assert len(matches) == 1
            actual = matches[0].removesuffix(f" {number}")
            assert (
                _dom_key(BeautifulSoup(MarkdownIt().renderInline(actual), "lxml"))
                == expected
            )
            assert actual.count("<br>") == len(formula.select("br"))

    for image in source.select(
        "p > img.content-image, .block-child-p > img.content-image"
    ):
        name = urlsplit(image["data-src"]).path.rsplit("/", 1)[-1]
        link = f"![Formula](body_assets/{name})"
        (line,) = [line for line in markdown.splitlines() if link in line]
        before, after = line.split(link)
        for text, sibling in (
            (before, image.previous_sibling),
            (after, image.next_sibling),
        ):
            if isinstance(sibling, str):
                assert scientific_text_key(str(sibling)) in scientific_text_key(text)

    for node in source.select(
        ".table-wrap-title, .table-wrap-foot .fn, .footnote-section-wrapper .fn"
    ):
        assert _dom_key(node) in scientific_text_key(markdown)

    source_references = source.select(".js-splitview-ref-list .ref")
    for node, reference in zip(source_references, article.references, strict=True):
        for note in node.select(".ref-body > .citation + .ref-note"):
            start = note.get_text(" ", strip=True).split()[0]
            assert re.search(rf"\s{re.escape(start)}\b", reference.raw)


def test_rsc_pdf_replay_validates_bytes_identity_and_converter_passthrough(
    tmp_path,
) -> None:
    sample = golden_criteria_sample_for_doi(DOI)
    pdf_path = golden_criteria_asset(DOI, "original.pdf")
    pdf_bytes = pdf_path.read_bytes()
    capture = sample["capture"]
    citation_url, final_url = capture["pdf_request_url"], capture["pdf_final_url"]
    # Replay a same-paper page that only carries a main PDF link.
    html = f'<meta name="citation_doi" content="{DOI}"><meta name="citation_pdf_url" content="{citation_url}">'
    client = _replay_client(tmp_path, sample, html)

    def fetch_pdf(urls, *, artifact_dir, request, **kwargs):
        assert urls == [citation_url]
        assert request.browser_only
        return pdf_fetch_result_from_bytes(
            artifact_dir=artifact_dir,
            source_url=urls[0],
            final_url=final_url,
            pdf_bytes=pdf_bytes,
            bytes_transport="browser_download",
            expected_identity=request.expected_identity,
        )

    client.deps = replace(client.deps, fetch_pdf_with_browser=fetch_pdf)
    result = client.fetch_result(
        DOI,
        {
            "doi": DOI,
            "title": sample["title"],
            "landing_page_url": sample["landing_url"],
        },
        None,
    )
    article, content = result.article, result.content
    assert article.source == "rsc_pdf"
    assert article.acquisition.route == "browser_pdf"
    assert article.acquisition.transport == "browser"
    assert content.source_url == final_url
    assert content.body == pdf_bytes and content.body.startswith(b"%PDF-")
    assert hashlib.sha256(content.body).hexdigest() == capture["pdf_sha256"]
    assert content.diagnostics["pdf"]["identity"]["observed_doi"] == DOI
    assert content.diagnostics["pdf"]["identity"]["status"] == "match"
    assert content.diagnostics["pdf"]["bytes_transport"] == "browser_download"
    assert (
        article.sections[0].text
        == content.markdown_text
        == render_pdf_markdown(pdf_path)
    )

    for body, doi, reason in [
        (b"<!doctype html><title>SSO</title>", DOI, "downloaded_file_not_pdf"),
        (b"%PDF- invalid content", DOI, "invalid_pdf_structure"),
        (pdf_bytes, "10.1039/d5gc00000a", "identity_mismatch"),
    ]:
        with pytest.raises(PdfFetchFailure) as exc:
            pdf_fetch_result_from_bytes(
                artifact_dir=tmp_path,
                source_url=citation_url,
                final_url=final_url,
                pdf_bytes=body,
                bytes_transport="browser_download",
                expected_identity={"doi": doi},
            )
        assert exc.value.kind == reason
