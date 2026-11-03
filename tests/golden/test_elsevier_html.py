"""Paired ScienceDirect/Article API sources independently anchor content checks."""

from copy import deepcopy
import hashlib
import json
import re

from bs4 import BeautifulSoup
import pytest

from paper_fetch.providers import _elsevier_html
from tests.golden_criteria import golden_criteria_asset
from tests.support.reviewed_publisher_content import _words
from tests.support.elsevier_structure import assert_numbering_and_list_structure

from tests.golden_criteria import iter_manifest_samples

DOIS = [
    sample["doi"]
    for sample in iter_manifest_samples(fixture_family="golden")
    if "sciencedirect.html" in sample.get("assets", {})
]


@pytest.fixture(params=DOIS)
def article(request):
    doi = request.param
    path = golden_criteria_asset(doi, "sciencedirect.html")
    html = path.read_text()
    provenance = json.loads(path.with_name("provenance.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance["sha256"]
    source = BeautifulSoup(html, "lxml")
    xml = BeautifulSoup(golden_criteria_asset(doi, "original.xml").read_bytes(), "xml")
    md, extraction = _elsevier_html.extract_markdown(
        html, provenance["final_url"], metadata={"doi": doi}
    )
    return doi, source, xml, md, extraction, html, provenance["final_url"]


def test_authors_headings_and_paragraph_order_from_source(article, subtests):
    doi, source, xml, markdown, extraction, _, _ = article
    expected_authors = [
        " ".join(
            n.get_text(" ", strip=True) for n in person.select(".given-name, .surname")
        )
        for person in source.select(".author-group .react-xocs-alternative-link")
        if person.select_one(".surname") is not None
    ]
    assert extraction["extracted_authors"] == expected_authors
    xml_names = [
        " ".join(
            n.get_text(" ", strip=True)
            for n in person.find_all(["given-name", "surname"])
        )
        for person in xml.select("article > head > author-group > author")
    ]
    assert expected_authors == xml_names
    from paper_fetch.providers._article_markdown_elsevier_document import (
        extract_article_authors,
    )
    from paper_fetch.xml_security import parse_xml

    assert (
        extract_article_authors(
            parse_xml(golden_criteria_asset(doi, "original.xml").read_bytes())
        )
        == xml_names
    )
    headings = [
        (len(match[1]), _words(match[2]))
        for match in re.finditer(r"(?m)^(#{2,6}) (.+)$", markdown)
    ]
    cursor = 0
    for node in source.select("#body h2, #body h3, #body h4, #body h5, #body h6"):
        with subtests.test(doi=doi, heading=node.get_text(" ", strip=True)):
            target = (int(node.name[1]), _words(node.get_text(" ", strip=True)))
            index = headings.index(target, cursor)
            cursor = index + 1
    text = _words(markdown)
    cursor = 0
    # Equations have an independent structural check below. These locators
    # cover prose paragraphs directly, without using either extractor as oracle.
    for para in source.select('#body div[id^="para"], #body div[id^="p0"], #body p'):
        if (
            para.find_parent("figure") is not None
            or para.find_parent("table") is not None
        ):
            continue
        if (
            para.find(["p", "div", "table", "figure", "mjx-container", "math"])
            is not None
        ):
            continue
        key = _words(para.get_text("", strip=False))
        if len(key) < 80:
            continue
        with subtests.test(doi=doi, paragraph=para.get("id")):
            found = text.find(key, cursor)
            assert found >= 0, para.get_text(" ", strip=True)[:160]
            cursor = found + len(key)


def test_reference_labels_content_doi_and_order_from_source(article, subtests):
    doi, source, _, markdown, extraction, _, _ = article
    entries = source.select("#references ol.references > li")
    assert len(extraction["references"]) == len(entries)
    for index, (entry, actual) in enumerate(
        zip(entries, extraction["references"], strict=True), 1
    ):
        with subtests.test(doi=doi, label=actual["label"]):
            label = entry.select_one(".label")
            assert actual["label"] == (
                " ".join(label.get_text(" ", strip=True).split()) if label else None
            )
            clone = deepcopy(entry.select_one(".reference") or entry)
            for node in clone.select("a.link, svg"):
                node.decompose()
            raw = actual["raw"]
            assert raw.startswith(f"{index}. ")
            body = raw[len(f"{index}. ") :]
            if label and not re.fullmatch(r"[\[\]()\d.\s]+", label.get_text()):
                annotation = (
                    " [" + " ".join(label.get_text(" ", strip=True).split()) + "]"
                )
                assert body.endswith(annotation)
                body = body.removesuffix(annotation)
            body = re.sub(r'<a id="elsevier-[^"]+"></a>', "", body)
            if actual["doi"] and actual["doi"].lower() not in clone.get_text().lower():
                body = body.removesuffix(". " + actual["doi"])
            assert _words(clone.get_text(" ", strip=True)) == _words(body)
            doi_links = [
                a["href"].split("doi.org/", 1)[1].lower()
                for a in entry.select('a[href*="doi.org/"]')
            ]
            if doi_links and not re.search(r"\s", doi_links[0]):
                assert actual["doi"] == doi_links[0]
            assert _words(actual["raw"]) in _words(markdown)


def test_figures_tables_attachments_and_abstract_scopes_from_source(article, subtests):
    doi, source, _, markdown, extraction, html, url = article
    normalized_md = _words(markdown)
    for figure in source.select("#body figure"):
        caption = figure.select_one(".captions")
        if caption is not None:
            with subtests.test(doi=doi, figure=figure.get("id")):
                caption = deepcopy(caption)
                for label in caption.select(".label"):
                    label.decompose()
                for math_node in caption.select("[data-paper-fetch-mathml], math"):
                    math_node.replace_with(" ELSEVIERCAPTIONMATHSPLIT ")
                cursor = 0
                for fragment in caption.get_text("", strip=False).split(
                    "ELSEVIERCAPTIONMATHSPLIT"
                ):
                    key = _words(fragment)
                    if key:
                        found = normalized_md.find(key, cursor)
                        assert found >= 0, fragment
                        cursor = found + len(key)
    for table in source.select("#body table"):
        for cell in table.select("th, td"):
            if cell.find(["mjx-container", "math", "table"]) is not None:
                continue
            cell = deepcopy(cell)
            for hint in cell.select(".screen-reader-only"):
                hint.decompose()
            key = _words(cell.get_text("", strip=False))
            if key:
                with subtests.test(doi=doi, cell=cell.get("id")):
                    assert key in normalized_md
    for note in source.select(".tables .footnotes, .tables .legend"):
        with subtests.test(doi=doi, table_note=note.get_text(" ", strip=True)[:80]):
            assert _words(note.get_text("", strip=False)) in normalized_md
    body = _elsevier_html.extract_assets(html, url, asset_profile="body")
    all_assets = _elsevier_html.extract_assets(html, url, asset_profile="all")
    assert not any(a["kind"] == "supplementary" for a in body)
    for anchor in source.select(".e-component a[download][href]"):
        with subtests.test(doi=doi, attachment=anchor["href"]):
            assert any(
                a["kind"] == "supplementary" and a["url"] == anchor["href"]
                for a in all_assets
            )
    for figure in source.select("#body figure, .graphical figure"):
        high = next(
            (
                a["href"]
                for a in figure.select("a[href]")
                if "high-res" in a.get_text().lower()
            ),
            None,
        )
        if high:
            with subtests.test(doi=doi, high_resolution=high):
                assert any(a["url"] == high for a in body)
    if source.select_one(".graphical img") is not None:
        assert any(a.get("section") == "abstract" for a in body)
    if "edumed" in doi:
        assert [a["heading"] for a in extraction["abstract_sections"]] == [
            "Resumen",
            "Abstract",
        ]
        assert extraction["abstract_sections"][1]["language"] == "en"


def test_original_mathml_structure_and_equation_labels(article, subtests):
    doi, source, xml, markdown, extraction, _, _ = article
    xml_math = xml.find_all("math")
    original_math = [
        BeautifulSoup(n["data-paper-fetch-mathml"], "xml").find("math")
        for n in source.select("[data-paper-fetch-mathml]")
    ]

    def structure(node):
        return (
            node.name,
            tuple(
                (child.name, child.get_text("", strip=True))
                for child in node.find_all()
                if child.name not in {"mrow", "mstyle", "maligngroup", "malignmark"}
            ),
        )

    # MathJax source retains semantic elements; style and namespace serialization
    # differ from XML. Both raw sources independently establish these structures.
    for node in original_math:
        with subtests.test(doi=doi, math=node.get_text()[:50]):
            assert any(
                structure(node) == structure(candidate) for candidate in xml_math
            )
    for label in source.select("#body .formula > .label"):
        with subtests.test(doi=doi, equation=label.get_text()):
            assert label.get_text(strip=True) in markdown
    if original_math:
        from tests.golden_corpus import golden_corpus_fixture_for_doi
        from tests.support.canonical_content import source_formulas
        from tests.support.scientific_content import assert_mathml_formulas

        fixture = golden_corpus_fixture_for_doi(doi)
        nodes = source_formulas(fixture, xml)
        assert_mathml_formulas(nodes, markdown, subtests)
        assert "$" in markdown
        losses = extraction["semantic_losses"]
        assert losses["formula_missing_count"] == 0
        assert losses["formula_fallback_count"] == 0


def test_saved_extraction_snapshots_match_their_existing_render_paths(article):
    from tests.golden_corpus import golden_corpus_fixture_for_doi
    from tests.support.replay import (
        build_article_from_fixture,
        persisted_fixture_markdown,
    )

    doi, _, _, markdown, _, _, _ = article
    assert (
        golden_criteria_asset(doi, "sciencedirect.extracted.md").read_text() == markdown
    )
    fixture = golden_corpus_fixture_for_doi(doi)
    model = build_article_from_fixture(fixture)
    assert golden_criteria_asset(
        doi, "extracted.md"
    ).read_text() == persisted_fixture_markdown(fixture, model)


def test_final_acquisition_routes_preserve_statements_abstracts_keywords_and_dois(
    article, tmp_path, subtests
):
    from tests.support.elsevier_routes import replay_route

    doi, source, xml, _, _, html, url = article
    metadata = {
        "doi": doi,
        "title": source.select_one("h1 .title-text").get_text(" ", strip=True),
        "landing_page_url": url,
    }
    results = {
        route: replay_route(
            route=route,
            metadata=metadata,
            html_text=html,
            xml_body=golden_criteria_asset(doi, "original.xml").read_bytes(),
            output_dir=tmp_path / route,
        )
        for route in ("html", "xml")
    }
    rendered = {
        route: result.article.to_ai_markdown(
            max_tokens="full_text", include_refs="all", asset_profile="all"
        )
        for route, result in results.items()
    }
    for route, result in results.items():
        assert result.article.source == f"elsevier_{route}"
        for abstract in source.select("#abstracts > .abstract.author"):
            for paragraph in abstract.select(".u-margin-s-bottom, p"):
                if paragraph.find(["div", "figure", "ul"]) is not None:
                    continue
                key = _words(paragraph.get_text("", strip=False))
                if len(key) < 30:
                    continue
                with subtests.test(doi=doi, route=route, abstract=paragraph.get("id")):
                    assert _words(rendered[route]).count(key) == 1
                    assert all(
                        key not in _words(s.text)
                        for s in result.article.sections
                        if s.kind == "body"
                    )
    xml_article = results["xml"].article
    expected_keywords = [
        " ".join(n.get_text("", strip=False).split()) for n in xml.find_all("keyword")
    ]
    assert xml_article.metadata.keywords == expected_keywords
    assert results["html"].article.metadata.keywords == expected_keywords
    cursor = 0
    for statement in xml.find_all(
        ["data-availability", "conflict-of-interest", "acknowledgment"]
    ):
        for para in statement.find_all(["para", "simple-para"]):
            if para.find(["para", "simple-para"]) is not None:
                continue
            key = _words(para.get_text("", strip=False))
            with subtests.test(doi=doi, statement=statement.name):
                text = _words(rendered["xml"])
                assert text.count(key) == 1
                cursor = text.index(key, cursor) + len(key)
    body = source.select_one("#body")
    for sibling in body.parent.find_all(recursive=False):
        if (
            sibling.get("id") in {"body", "abstracts", "references"}
            or sibling.find("h2", recursive=False) is None
        ):
            continue
        for para in sibling.find_all("p"):
            key = _words(para.get_text("", strip=False))
            if key:
                assert _words(rendered["html"]).count(key) == 1
    original_refs = xml.find_all("bib-reference")
    web_refs = source.select("#references ol.references > li")
    assert len(xml_article.references) == len(original_refs) == len(web_refs)
    completion = results["xml"].content.diagnostics.get("reference_doi_completion", {})
    matches = {m["index"]: m for m in completion.get("matches", [])}
    for index, (node, web, actual) in enumerate(
        zip(original_refs, web_refs, xml_article.references, strict=True)
    ):
        original_doi = node.find("doi")
        web_link = web.select_one('a[href*="doi.org/"]')
        with subtests.test(doi=doi, reference=index):
            if original_doi is not None:
                assert (
                    actual.doi
                    == re.sub(r"\s+", "", original_doi.get_text(strip=True)).lower()
                )
                assert index not in matches
            elif (
                actual.doi
                and actual.doi in node.get_text(" ", strip=True).lower()
                and index not in matches
            ):
                pass
            elif web_link is not None:
                assert actual.doi
                assert actual.doi.casefold() in web_link["href"].casefold() or re.sub(
                    r"\s", "", actual.doi.casefold()
                ) in re.sub(r"\s", "", web_link["href"].casefold())
                if index in matches:
                    assert matches[index]["source"] == "elsevier_html"
    if source.select_one(".graphical figure") is not None:
        graphical = next(
            asset for asset in xml_article.assets if asset.section == "abstract"
        )
        assert graphical.render_state == "inline"
        assert rendered["xml"].count(graphical.source_url) == 1
        assert "ga1" not in " ".join(
            s.text for s in xml_article.sections if s.kind == "body"
        )
    assert "Empty Cell" not in rendered["html"]
    for route in results:
        assert all(
            ref.raw.startswith(f"{i}. ")
            for i, ref in enumerate(results[route].article.references, 1)
        )
        assert_numbering_and_list_structure(source, xml, rendered[route], route=route)


def test_source_anchored_navigation_and_specific_content_regressions(article, subtests):
    doi, source, xml, markdown, extraction, _, _ = article
    targets = re.findall(r'<a id="(elsevier-[^"]+)"></a>', markdown)
    assert len(targets) == len(set(targets))
    for target in re.findall(r"\]\(#([^\s)]+)\)", markdown):
        assert targets.count(target) == 1
    assert "Equation 10" not in markdown
    title = source.select_one("h1 .title-text").get_text(" ", strip=True)
    assert _words(extraction["title"]) == _words(title)
    assert sum(line.startswith("# ") for line in markdown.splitlines()) == 1
    if doi == "10.1016/j.rse.2026.115369":
        assert len(source.select("#body table br")) == 250
        assert markdown.count("<br>") == 250
    if doi == "10.1016/j.rse.2025.114648":
        # These five source captions were swallowed by .display classification.
        figures = source.select("#f0065, #f0070, #f0075, #f0080, #f0090")
        assert len(figures) == 5
        assert sum(len(n.select("[data-paper-fetch-mathml]")) for n in figures) == 26
        for figure in figures:
            assert f'id="elsevier-{figure["id"]}"' in markdown
    for note in source.select("#footnotes > .footnote .footnote-detail"):
        with subtests.test(article_note=doi):
            assert _words(note.get_text("", strip=False)) in _words(markdown)
            assert markdown.index("## Article notes") < markdown.index("## References")


def test_reference_corpus_membership_from_all_fifteen_sources():
    total = 0
    assert len(DOIS) == 15
    for doi in DOIS:
        source = BeautifulSoup(
            golden_criteria_asset(doi, "sciencedirect.html").read_text(), "lxml"
        )
        xml = BeautifulSoup(
            golden_criteria_asset(doi, "original.xml").read_bytes(), "xml"
        )
        count = len(source.select("#references ol.references > li"))
        assert count == len(xml.find_all("bib-reference"))
        total += count
    assert total == 938
