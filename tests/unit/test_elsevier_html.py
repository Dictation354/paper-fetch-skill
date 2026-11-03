"""ScienceDirect DOM boundary scenarios."""

from paper_fetch.providers import _elsevier_html as html
from paper_fetch.providers.elsevier import ElsevierClient
from paper_fetch.providers.browser_runtime.api import load_runtime_config
from paper_fetch.providers.browser_runtime import selection
from paper_fetch.providers._payloads import build_provider_payload
from bs4 import BeautifulSoup
import pytest

DOI = "10.1016/example"
PII = "S016819232400090X"
URL = f"https://www.sciencedirect.com/science/article/pii/{PII}"


def test_candidates_prefer_known_pii_and_pdf_belongs_to_current_article():
    client = ElsevierClient(None, {})
    assert client.html_candidates(
        DOI,
        {
            "pii": PII,
            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/" + PII,
        },
    ) == [
        URL,
        "https://linkinghub.elsevier.com/retrieve/pii/" + PII,
        "https://doi.org/" + DOI,
    ]
    source = f'''<meta name="citation_doi" content="{DOI}">
    <a href="{URL}/pdfft?download=true">Download PDF</a>
    <div id="references"><a href="{URL}/pdf">Cited PDF</a></div>
    <div class="RecommendedArticles"><a href="{URL}/pdfft?recommended=1">PDF</a></div>
    <a href="/science/article/pii/S0034425726001392/pdfft">Other article PDF</a>'''
    assert html.extract_pdf_candidate_urls_from_html(source, URL, expected_doi=DOI) == [
        URL + "/pdfft?download=true"
    ]
    assert (
        html.extract_pdf_candidate_urls_from_html(
            source, URL, expected_doi="10.1016/other"
        )
        == []
    )


def test_main_response_matches_url_pii_and_doi():
    source = f'<meta name="citation_doi" content="{DOI}">'
    assert html.main_document_matches(URL, URL, source, DOI)
    assert not html.main_document_matches(URL, URL, source, "10.1016/other")
    assert not html.main_document_matches(
        URL, URL.replace(PII, "S0034425726001392"), source, DOI
    )
    assert not html.main_document_matches(URL, URL, "<html></html>", DOI)


def test_backend_and_profile_are_isolated_from_pnas(monkeypatch, tmp_path):
    monkeypatch.setattr(selection, "supported_platform", lambda: True)
    env = {
        "XDG_DATA_HOME": str(tmp_path),
        "PAPER_FETCH_PNAS_BROWSER_BACKEND": "camoufox",
    }
    other = load_runtime_config(env, provider="pnas", doi="10.1073/test")
    actual = load_runtime_config(env, provider="elsevier", doi=DOI)
    assert actual.backend == "flaresolverr"
    assert actual.user_data_dir.name == "elsevier-flaresolverr"
    assert actual.user_data_dir != other.user_data_dir


def test_article_scope_authors_captions_references_and_asset_profiles():
    source = f'''<meta name="citation_doi" content="{DOI}"><h1>Example</h1>
    <div class="author-group"><button><span class="react-xocs-alternative-link"><span class="given-name">Ana</span> <span class="surname">García</span></span><sup>1</sup></button></div>
    <div id="abstracts"><div class="abstract author-highlights"><h2>Highlights</h2><p>Highlighted finding.</p></div>
    <div class="abstract author" lang="es"><h2>Resumen</h2><p>Resumen español.</p></div></div>
    <div id="body"><section><h2>1. Results</h2><div id="para1">{"Scientific results establish the observed process through independent measurements. " * 20}</div>
    <figure><img src="low.jpg"><a class="download-link" href="high.jpg">Download high-res image</a><span class="captions"><p>Fig. 1. Observed result.</p></span></figure>
    <div id="para2">{"These observations explain the mechanism and its physical interpretation. " * 20}</div>
    <div class="Appendices"><h2>Appendix A</h2><figure><img src="appendix.jpg"><span class="captions">Appendix figure.</span></figure>
    <span class="display"><span class="e-component"><a class="download-link" href="supplement.zip">Supplementary data</a></span></span></div></section></div>
    <div id="references"><h2>References</h2><ol class="references"><li><span class="label">7</span><span class="reference"><div class="authors">A. Author</div><div class="title">Prior finding [Internet]</div><div class="host">Journal (2024) <a href="https://doi.org/10.1000/test">10.1000/test</a></div><a class="link" href="https://scholar.google.com/">Google Scholar</a></span></li></ol></div>
    <aside>Assistant recommendation</aside>'''
    markdown, extraction = html.extract_markdown(source, URL, metadata={"doi": DOI})
    assert extraction["extracted_authors"] == ["Ana García"]
    assert extraction["abstract_sections"][0]["heading"] == "Resumen"
    assert extraction["references"][0]["label"] == "7"
    assert extraction["references"][0]["doi"] == "10.1000/test"
    assert (
        "Author Prior finding [Internet] Journal" in extraction["references"][0]["raw"]
    )
    assert (
        "Google Scholar" not in markdown and "Assistant recommendation" not in markdown
    )
    assert "Observed result." in markdown
    assert "Supplementary data" in markdown
    assert html.extract_assets(source, URL, asset_profile="none") == []
    body = html.extract_assets(source, URL, asset_profile="body")
    all_assets = html.extract_assets(source, URL, asset_profile="all")
    assert any(asset["url"] == URL.rsplit("/", 1)[0] + "/high.jpg" for asset in body)
    assert any(asset.get("section") == "appendix" for asset in body)
    assert not any(asset["kind"] == "supplementary" for asset in body)
    assert sum(asset["kind"] == "supplementary" for asset in all_assets) == 1


def test_unsupported_elsevier_keeps_api_cache_capability(monkeypatch):
    from paper_fetch.capability_scope import capability_scopes_for_query
    from paper_fetch.providers.browser_runtime import chrome

    monkeypatch.setattr(chrome, "supported_platform", lambda: False)
    scopes = capability_scopes_for_query({"ELSEVIER_API_KEY": "key"}, DOI)
    assert len(scopes) == 2 and scopes[0].startswith("credential:")
    assert scopes[1] == "public"


def test_pdf_fallback_uses_resolved_pii_after_page_download_links():
    source = f'<meta name="citation_doi" content="{DOI}"><a href="{URL}/pdf">PDF</a>'
    candidates = html.browser_pdf_candidates(source, URL, expected_doi=DOI)
    assert candidates[0] == URL + "/pdf"
    assert candidates[1].startswith(URL + "/pdfft?")


@pytest.mark.parametrize(
    "suffix,heading",
    [("new-one", "Data availability"), ("other-two", "Source access statement")],
)
def test_unclassified_body_sibling_declarations_keep_order_once(suffix, heading):
    source = f'''<h1>Example</h1><article><div class="body-area">
    <section id="{suffix}-before"><h2>{heading}</h2><p>Earlier statement.</p></section>
    <div id="body"><section><h2>Results</h2><p>{"Scientific observations explain the measurement process. " * 35}</p></section></div>
    <div id="{suffix}-after"><h2>Later statement</h2><div><p>Access the observations here.</p></div></div>
    <aside><h2>Recommendation</h2><p>Excluded recommendation.</p></aside>
    <div class="reading-assistant"><h2>Assistant</h2><p>Excluded assistant.</p></div>
    <nav><h2>Navigation</h2><p>Excluded navigation.</p></nav>
    </div></article>'''
    markdown, _ = html.extract_markdown(source, URL, metadata={"doi": DOI})
    assert (
        markdown.index("Earlier statement.")
        < markdown.index("Scientific observations")
        < markdown.index("Access the observations here.")
    )
    assert markdown.count("Access the observations here.") == 1
    assert "Excluded" not in markdown


def test_bilingual_abstract_subsections_are_not_body_or_duplicated():
    source = f"""<h1>Example</h1><article>
    <div id="abstracts"><div class="abstract author" lang="es"><h2>Resumen</h2>
    <div class="abstract author" id="new-id"><h3>Propósito</h3><p>Una observación única.</p></div></div>
    <div class="abstract author" lang="en"><h2>Abstract</h2>
    <div class="abstract author" id="another-id"><h3>Objective</h3><p>A unique observation.</p></div></div></div>
    <div id="body"><h2>Results</h2><p>{"Scientific observations explain the measurement process. " * 35}</p></div></article>"""
    markdown, extraction = html.extract_markdown(source, URL, metadata={"doi": DOI})
    assert [
        (a["heading"], a["language"], a["order"])
        for a in extraction["abstract_sections"]
    ] == [("Resumen", "es", 0), ("Abstract", "en", 1)]
    assert "### Propósito" in extraction["abstract_sections"][0]["text"]
    raw = build_provider_payload(
        provider="elsevier",
        route_kind="html",
        source_url=URL,
        content_type="text/html",
        body=source.encode(),
        markdown_text=markdown,
        diagnostics={"extraction": extraction},
    )
    article = ElsevierClient(None, {}).to_article_model(
        {"doi": DOI, "title": "Example"}, raw
    )
    rendered = article.to_ai_markdown(max_tokens="full_text")
    for text in ["Una observación única.", "A unique observation."]:
        assert markdown.count(text) == rendered.count(text) == 1
        assert all(text not in s.text for s in article.sections if s.kind == "body")
    assert "### Objective" in rendered


def test_reference_plain_doi_keeps_block_boundaries_and_ignores_recommendations():
    source = """<article><div id="body"></div><div id="references"><ol class="references">
    <li><span class="reference"><div class="authors">A. Writer</div><div class="title">A finding</div>
    <div class="host">Journal (2024) 10.1000/plain</div><div class="ReferenceLinks"><a href="https://scholar.google.com/">Google Scholar</a></div></span></li>
    <li><span class="reference"><div>Printed DOI 10.1000/printed</div><a href="https://doi.org/10.1000/linked">Article</a></span></li>
    </ol></div><aside class="recommended-articles"><div id="references"><ol class="references"><li>10.1000/unrelated</li></ol></div></aside></article>"""
    refs = html._references(BeautifulSoup(source, "lxml"))
    assert [r["doi"] for r in refs] == ["10.1000/plain", "10.1000/linked"]
    assert "Writer A finding Journal" in refs[0]["raw"]
    assert "Google" not in refs[0]["raw"]


def test_table_reader_hint_removed_without_dropping_real_cell_text():
    soup = BeautifulSoup(
        '<table><tr><td><span class="screen-reader-only">Empty Cell</span></td><td>Observed<span class="screen-reader-only">Helper</span> value</td></tr></table>',
        "lxml",
    )
    html._prepare_dom(soup, URL)
    assert [n.get_text() for n in soup.select("td")] == ["", "Observed value"]


def test_heading_labels_and_front_highlights_follow_structure():
    source = f"""<h1>Example</h1><article>
    <div class="Highlights"><h2>Summary in another language</h2><p>Front finding.</p></div>
    <div id="abstracts"><div class="abstract author-highlights"><h2>Highlights</h2><p>Front bullets.</p></div>
    <div class="abstract author"><h2>Abstract</h2><p>Retained abstract.</p></div>
    <div class="graphical"><h2>Graphical abstract</h2><figure><img src="ga.jpg"></figure></div></div>
    <div id="body"><section><span class="label">3.</span><h2>Results</h2>
    <h3><span class="label">3.1.</span>3.1. Observations</h3>
    <p>{"Scientific observations explain the measurement process. " * 35}</p>
    <div class="highlights"><h4>Highlights</h4><p>Body finding.</p></div></section></div>
    <div class="highlights"><h2>Later statement</h2><p>Tail finding.</p></div></article>"""
    markdown, _ = html.extract_markdown(source, URL)
    assert "## 3. Results" in markdown and "### 3.1. Observations" in markdown
    assert "3.1. 3.1." not in markdown
    assert "Front finding." not in markdown and "Front bullets." not in markdown
    assert "Body finding." in markdown and "Tail finding." in markdown
    assert "Retained abstract." in markdown and "ga.jpg" in markdown


def test_reference_numbers_are_shared_by_extraction_and_article_without_year_counters():
    source = f"""<h1>Example</h1><article><div id="body"><h2>Results</h2>
    <p>{"Scientific observations explain the measurement process. " * 35}</p></div>
    <div id="references"><ol class="references">
    <li><span class="label">Writer, 2024</span><span class="reference" id="key-one">A. Writer. First finding (2024).</span></li>
    <li><span class="label">2023</span><span class="reference">2023 was the observation year.</span></li>
    <li><span class="label">7</span><span class="reference">B. Writer. Last finding.</span></li>
    </ol></div></article>"""
    markdown, extraction = html.extract_markdown(source, URL)
    raw = build_provider_payload(
        provider="elsevier",
        route_kind="html",
        source_url=URL,
        content_type="text/html",
        body=source.encode(),
        markdown_text=markdown,
        diagnostics={"extraction": extraction},
    )
    article = ElsevierClient(None, {}).to_article_model({"doi": DOI}, raw)
    expected = [
        '1. <a id="elsevier-key-one"></a>A. Writer. First finding (2024). [Writer, 2024]',
        "2. 2023 was the observation year. [2023]",
        "3. B. Writer. Last finding.",
    ]
    assert [r["raw"] for r in extraction["references"]] == expected
    assert [r.raw for r in article.references] == expected
    assert all(value in markdown for value in expected)


@pytest.mark.parametrize("label", ["(1)", "1.", "a)", "•"])
def test_list_label_first_paragraph_and_nested_blocks(label):
    from paper_fetch.providers._html_section_markdown import render_container_markdown
    from paper_fetch.models.markdown import normalize_markdown_text
    from tests.support.markdown_lists import ancestor, inline_text, markdown_tree

    soup = BeautifulSoup(
        f"""<div><ul><li><span class="list-label">{label}</span><span class="list-content">
    <div></div><p>Dividing observations.</p><p>A separate paragraph.</p>
    <div class="display-formula" data-paper-fetch-markdown="true">$$\nx=1\n$$</div>
    <figure><img src="figure.png"><figcaption>Fig. 1. Original caption.</figcaption></figure>
    <ul><li>Nested observation.</li></ul></span></li>
    <li><span class="list-label">•</span><span class="list-content"><p>Following observation.</p></span></li></ul></div>""",
        "lxml",
    )
    lines = []
    render_container_markdown(soup.div, lines, level=2)
    markdown = normalize_markdown_text("\n".join(lines))
    assert markdown.startswith(
        "- " + (label + " " if label != "•" else "") + "Dividing observations."
    )
    assert "•" not in markdown
    tree = markdown_tree(markdown)
    items = tree.children[0].children
    assert len(items) == 2
    assert "A separate paragraph." in inline_text(items[0])
    assert "Original caption." in inline_text(items[0])
    assert "Nested observation." in inline_text(items[0])
    assert "x=1" in inline_text(items[0])
    images = [n for n in tree.walk() if n.type == "image"]
    assert len(images) == 1 and ancestor(images[0], "list_item") is items[0]
