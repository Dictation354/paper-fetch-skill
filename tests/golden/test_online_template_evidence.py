"""Real publisher responses for the remaining template gaps.

Historical article HTML keeps its unknown HTTP envelope. Newly captured satellite
pages and images replay their actual response envelopes. No failure is injected.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers import _springer_html as springer_html
from paper_fetch.providers.springer import SpringerClient
from tests.golden_criteria import golden_criteria_asset
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support.captured_images import download_captured_images

CAPTURE = "acquisition/template-gaps-2026-09-16/"


def _assert_original_expandable_boxes(doi, headings, sentences, tmp_path):
    record, body = _record(doi, CAPTURE + "article-response.html")
    assert record["status_code"] == 200
    soup = BeautifulSoup(body, "lxml")
    assert soup.select_one('meta[name="citation_doi"]')["content"] == doi
    boxes = soup.select(
        '[data-expandable-box-container] [data-expandable-box][aria-hidden="true"]'
    )
    assert len(boxes) == len(headings)
    assert [b.find("h3").get_text(" ", strip=True) for b in boxes] == headings
    payload = springer_html.extract_html_payload(body.decode(), record["requested_url"])
    markdown = payload["markdown_text"]
    assets = springer_html.extract_html_assets(
        body.decode(), record["requested_url"], asset_profile="body"
    )
    box_images = [a for a in assets if "Figa_HTML" in str(a.get("url", ""))]
    if not sentences:
        assert len(box_images) == 1
        assets = download_captured_images(doi, box_images, tmp_path)
    metadata = springer_html.parse_html_metadata(body.decode(), record["requested_url"])
    raw = RawFulltextPayload(
        provider="springer",
        content=ProviderContent(
            route_kind="html",
            source_url=record["requested_url"],
            content_type="text/html",
            body=body,
            markdown_text=markdown,
            merged_metadata=metadata,
            extracted_assets=springer_html.extract_html_assets(
                body.decode(), record["requested_url"], asset_profile="body"
            ),
            diagnostics={"extraction": payload},
        ),
    )
    article = SpringerClient(FixtureHtmlTransport({}), {}).to_article_model(
        metadata,
        raw,
        downloaded_assets=assets if not sentences else [],
    )
    rendered = article.to_ai_markdown(max_tokens="full_text", asset_profile="body")
    if not sentences:
        local = f"]({assets[0]['path']})"
        assert rendered.count(local) == 1
        assert rendered.index(headings[0]) < rendered.index(local)
        assert rendered.index(local) < rendered.index("## Temperature of individuals")
    for heading in headings:
        assert markdown.count(heading) == 1
        assert rendered.count(heading) == 1
    for sentence in sentences:
        assert any(sentence in b.get_text(" ", strip=True) for b in boxes)
        assert sentence in markdown
        assert sentence in rendered
    # Every long prose fragment in the real boxes survives, including the end.
    # Inline citations/emphasis split text nodes, so compare words without markup.
    normalized = re.sub(r"\W+", " ", markdown).casefold()
    for box in boxes:
        for node in box.select("p"):
            for fragment in node.stripped_strings:
                if len(fragment) >= 100:
                    assert re.sub(r"\W+", " ", fragment).casefold() in normalized


def test_original_old_nature_table_pages_recover_all_four_real_images(tmp_path):
    doi = "10.1038/nature13376"
    url = "https://www.nature.com/articles/nature13376"
    body = golden_criteria_asset(doi, "original.html").read_bytes()
    # This historical source predates response capture: only this envelope is injected.
    responses = {url: http_response(url, body, "text/html")}
    originals = {}
    for number in range(1, 5):
        record, satellite = _record(doi, CAPTURE + f"table{number}-response.html")
        assert record["status_code"] == 200
        soup = BeautifulSoup(satellite, "lxml")
        assert f"Extended Data Table {number}" in soup.h1.get_text(" ", strip=True)
        assert soup.select_one('a[href="/articles/nature13376"]')
        assert not soup.select_one(".c-article-table-container table")
        responses[record["requested_url"]] = _response(record, satellite)
        image_record, image_body = _record(
            doi, CAPTURE + f"table{number}-image-response.bin"
        )
        assert image_record["status_code"] == 200
        assert len(image_body) > 40_000
        originals[image_record["requested_url"]] = image_body
    client = SpringerClient(FixtureHtmlTransport(responses), {})
    metadata = springer_html.parse_html_metadata(body.decode(), url)
    metadata.update(doi=doi, landing_page_url=url, fulltext_links=[])
    raw = client.fetch_raw_fulltext(doi, metadata)
    tables = [a for a in raw.content.extracted_assets if a["kind"] == "table"]
    assert len(tables) == 4
    assert {a["url"] for a in tables} == set(originals)
    downloaded = download_captured_images(doi, tables, tmp_path)
    article = client.to_article_model(metadata, raw, downloaded_assets=downloaded)
    rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    positions = []
    for number, asset in enumerate(downloaded, 1):
        assert Path(asset["path"]).read_bytes() == originals[asset["download_url"]]
        assert rendered.count(f"]({asset['path']})") == 1
        assert f"Extended Data Table {number}" in rendered
        positions.append(rendered.index(f"]({asset['path']})"))
    assert positions == sorted(positions)
    assert "Table body unavailable" not in rendered


def test_original_science_pure_code_statement_survives_acknowledgments():
    from paper_fetch.providers.science import ScienceClient
    from tests.support.reviewed_publisher_content import _words

    doi = "10.1126/science.abo2812"
    record, body = _record(
        doi, "acquisition/template-browser-2026-09-16/000-browser_rendered_dom.html"
    )
    html = body.decode()
    soup = BeautifulSoup(html, "lxml")
    assert (
        springer_html.parse_html_metadata(html, record["requested_url"])["doi"] == doi
    )
    statements = [
        p
        for p in soup.select('#acknowledgments div[role="paragraph"]')
        if p.b and p.b.get_text() == "Code availability:"
    ]
    assert len(statements) == 1
    original = statements[0]
    label = original.b.extract().get_text().rstrip(":")
    expected = _words(original.get_text(" ", strip=True))
    assert expected.startswith(
        _words("R scripts that were used to process hydroclimate")
    )
    client = ScienceClient(FixtureHtmlTransport({}), {})
    metadata = springer_html.parse_html_metadata(html, record["requested_url"])
    markdown, extraction = client.extract_markdown(
        html, record["requested_url"], metadata=metadata
    )
    raw = RawFulltextPayload(
        provider="science",
        content=ProviderContent(
            route_kind="html",
            source_url=record["requested_url"],
            content_type="text/html",
            body=body,
            markdown_text=markdown,
            merged_metadata=metadata,
            diagnostics={
                "extraction": extraction,
                "availability_diagnostics": extraction.get("availability_diagnostics"),
            },
            extracted_assets=list(extraction.get("extracted_assets") or []),
        ),
    )
    article = client.to_article_model(metadata, raw)
    matching = [s for s in article.sections if s.heading == label]
    assert len(matching) == 1
    assert matching[0].kind == "code_availability"
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert rendered.count("## Code availability") == 1
    assert _words(rendered).count(expected) == 1
    assert (
        "[https://codeocean.com/capsule/0322198/tree/v1](https://codeocean.com/capsule/0322198/tree/v1)"
        in rendered
    )
    assert "## Acknowledgments" not in rendered
    assert not any(
        expected in _words(s.text) for s in article.sections if s.kind == "body"
    )


def test_original_ieee_table_wins_over_formula_candidate_with_same_preview():
    from dataclasses import asdict
    from paper_fetch.extraction.html.assets import extract_formula_assets
    from paper_fetch.providers import _ieee_html, ieee

    doi = "10.1109/TBME.2024.3434477"
    record, body = _record(doi, "acquisition/ieee-flow-2026-09-15/rest-body.html")
    assert record["status_code"] == 200
    assert "/document/10612240/" in record["requested_url"]
    url = record["requested_url"]
    html = body.decode()
    soup = BeautifulSoup(html, "lxml")
    image = soup.find(
        "img", src=lambda value: value and "edgar.t3-3434477-small.gif" in value
    )
    assert image["alt"].startswith(
        "Table III- The Equation of the Linear Line of Best Fit"
    )
    candidates = extract_formula_assets(html, url)
    table_candidates = _ieee_html._extract_ieee_body_media_assets(html, url)
    table = next(a for a in table_candidates if a.get("heading") == "TABLE III")
    assert any(a["url"] == table["preview_url"] for a in candidates)
    assert table["kind"] == "table"
    metadata = {"doi": doi}
    extraction = _ieee_html._extract_ieee_html(html, url, metadata=metadata)
    matching = [a for a in extraction.extracted_assets if "edgar.t3-3434477" in str(a)]
    assert len(matching) == 1
    assert matching[0]["kind"] == "table"
    assert matching[0]["heading"] == "TABLE III"
    assert matching[0]["preview_url"] == table["preview_url"]
    payload = RawFulltextPayload(
        provider="ieee",
        content=ProviderContent(
            route_kind="html",
            source_url=url,
            content_type="text/html",
            body=body,
            markdown_text=extraction.markdown_text,
            merged_metadata=metadata,
            extracted_assets=extraction.extracted_assets,
            diagnostics={"extraction": asdict(extraction)},
        ),
    )
    article = ieee.IeeeClient(FixtureHtmlTransport({}), {}).to_article_model(
        metadata, payload
    )
    rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    original_caption = "The Fits With the Smallest Errors Are Shown in Bold"
    assert original_caption in matching[0]["caption"]
    assert rendered.count(original_caption) == 1
    assert len([a for a in article.assets if "edgar.t3-3434477" in str(a)]) == 1


def test_original_expandable_boxes_survive_hidden_interface_cleanup(tmp_path):
    _assert_original_expandable_boxes(
        "10.1038/s41467-022-32108-3",
        [
            "Box 1 Birds use their bills for thermoregulation",
            "Box 2 Hypotheses underlying latitudinal gradients in bill length and body size",
        ],
        [
            "Birds can dissipate heat via their bills because they are unfeathered (non-insulated) with a network of blood vessels close to the surface.",
            "These hypotheses are not mutually exclusive and generate similar predictions; however, they differ in their capacity to explain latitudinal patterns in bill length and body size across shorebirds with diverse movement ecology.",
        ],
        tmp_path,
    )


def test_original_image_only_box_preserves_title_and_local_bitmap(tmp_path):
    _assert_original_expandable_boxes(
        "10.1038/s42003-021-02908-2",
        [
            "Box 1 Keywords in biological studies that correlate temperature and physiological events. These indices are explained by representative literature"
        ],
        [],
        tmp_path,
    )
