"""Minimal contracts for the 2026-09-19 audit fixes; no full-paper inputs."""

from bs4 import BeautifulSoup

from paper_fetch.models import article_from_markdown
from paper_fetch.models.markdown import normalize_markdown_text
from paper_fetch.providers._article_markdown_copernicus import parse_copernicus_xml
from paper_fetch.providers._arxiv_references import _render_arxiv_table_block
from paper_fetch.providers._oxfordacademic_html import extract_markdown
from paper_fetch.providers._royalsocietypublishing_html import merge_metadata_with_html
from paper_fetch.providers._science_html import finalize_extraction as science_finalize
from paper_fetch.providers._springer_markdown import extract_html_payload
from paper_fetch.providers._wiley_html import finalize_extraction as wiley_finalize
from paper_fetch.providers.plos import parse_plos_xml


def test_arxiv_image_cells_keep_rows_and_panel_labels():
    node = BeautifulSoup(
        '<table class="ltx_tabular"><tr><td><img src="https://example.org/a.png"/></td><td><img src="https://example.org/b.png"/></td></tr><tr><td>(a)</td><td>(b)</td></tr></table>',
        "lxml",
    ).table
    markdown, rendered, fallback = _render_arxiv_table_block(node)
    assert rendered and not fallback
    assert all(
        line.startswith("|") and line.endswith("|") for line in markdown.splitlines()
    )
    assert (
        next(line for line in markdown.splitlines() if "![" in line).count("![Figure]")
        == 2
    )
    assert "(a)" in markdown.splitlines()[-1] and "(b)" in markdown.splitlines()[-1]
    assert normalize_markdown_text(markdown) == markdown


def test_arxiv_equal_cells_preserve_empty_and_repeated_columns():
    node = BeautifulSoup(
        "<table><tr><th>A</th><th>B</th><th>C</th><th>D</th></tr><tr><td></td><td></td><td>IV-2SLS</td><td>IV-2SLS</td></tr><tr><td></td><td>(0.0002)</td><td>(0.0002)</td><td>(0.0002)</td></tr></table>",
        "lxml",
    ).table
    markdown, _, _ = _render_arxiv_table_block(node)
    rows = [
        [cell.strip() for cell in row.split("|")[1:-1]] for row in markdown.splitlines()
    ]
    assert rows[-2] == ["", "", "IV-2SLS", "IV-2SLS"]
    assert rows[-1] == ["", "(0.0002)", "(0.0002)", "(0.0002)"]


def test_springer_reporting_summary_stays_after_unsectioned_body():
    html = '<article><h1>Study</h1><div class="c-article-body"><div class="main-content"><div class="c-article-section__content"><p>Arising from: Earlier study.</p><p>Main result.</p></div><section data-title="Reporting summary"><h2>Reporting summary</h2><p>Research design details.</p></section></div></div></article>'
    payload = extract_html_payload(html, "https://www.nature.com/articles/example")
    article = article_from_markdown(
        doi=None,
        source="springer_html",
        metadata={"title": "Study"},
        markdown_text=payload["markdown_text"],
        abstract_sections=payload["abstract_sections"],
        section_hints=payload["section_hints"],
    )
    assert not article.metadata.abstract
    assert [(s.heading, s.kind) for s in article.sections] == [
        ("", "body"),
        ("Reporting summary", "body"),
    ]
    assert article.sections[0].text.startswith("Arising from:")


def test_springer_extended_table_retains_caption_and_official_entry():
    html = '<article><div class="c-article-body"><div class="main-content"><p>Result.</p></div><section><figure><figcaption class="c-article-table__figcaption">Extended Data Table 1 Observed water yield</figcaption><a data-test="table-link" href="/articles/example/tables/1">Full size table</a></figure></section></div></article>'
    result = extract_html_payload(html, "https://www.nature.com/articles/example")
    assert (
        "[Extended Data Table 1 Observed water yield](https://www.nature.com/articles/example/tables/1)"
        in result["markdown_text"]
    )


def test_wiley_display_bullet_is_not_part_of_reference_body():
    _, result = wiley_finalize(
        '<ol><li data-bib-id="bib1"><span class="bullet">1</span><span class="author">Reya T</span>. Study. 2001.</li></ol>',
        "https://onlinelibrary.wiley.com/article",
        "",
        {},
    )
    assert result["references"][0]["raw"] == "Reya T. Study. 2001."
    assert result["references"][0]["label"] == "1."


def test_copernicus_empty_object_xrefs_use_only_identified_target_labels():
    xml = b'<article><body><sec><title>Results</title><p>(Fig. <xref ref-type="fig" rid="f1"/>), (Table <xref ref-type="table" rid="t1"/>). <xref ref-type="fig" rid="f1">1a</xref></p><fig id="f1"><label>1</label></fig><table-wrap id="t1"><label>2</label></table-wrap></sec></body></article>'
    result = parse_copernicus_xml(
        xml, source_url="https://hess.copernicus.org/article.xml"
    )
    assert "(Fig. 1), (Table 2). 1a" in result.markdown_text


def test_copernicus_heading_preserves_mathml_structure(monkeypatch):
    # Minimal structured formula uses the existing formula renderer boundary.
    xml = b"<article><body><sec><title>Formation of <inline-formula><math><msup><mi>O</mi><mn>2</mn></msup></math></inline-formula></title><p>Result.</p></sec></body></article>"
    from paper_fetch.providers import _article_markdown_math as math
    from paper_fetch.providers._article_markdown_math import FormulaRenderResult

    monkeypatch.setattr(
        math,
        "render_inline_formula_result",
        lambda *a, **kw: FormulaRenderResult(
            expression="O^{2}", status="ok", method="mathml"
        ),
    )
    result = parse_copernicus_xml(
        xml, source_url="https://acp.copernicus.org/article.xml"
    )
    assert "O^{2}" in result.markdown_text
    assert "O2" not in result.markdown_text


def test_oup_abstract_heading_is_not_an_abstract_block():
    html = '<div class="widget-ArticleFulltext"><h2 class="abstract-title">Abstract</h2><section class="abstract"><p>Actual abstract text.</p></section><div class="ajax-articleAbstract-exclude-regex original-slide">Download slide</div><h2>Results</h2><p>Results text.</p></div>'
    result = extract_markdown(
        html,
        "https://academic.oup.com/article",
        metadata={"title": "Study", "abstract": "Abstract"},
    )
    assert [b["text"] for b in result.abstract_sections] == ["Actual abstract text."]
    assert result.metadata.get("abstract") != "Abstract"


def test_plos_reference_names_and_author_boundaries_are_separate():
    xml = b"<article><back><ref-list><ref><element-citation><person-group><name><surname>Thomas</surname><given-names>WE</given-names></name><name><surname>Trintchina</surname><given-names>E</given-names></name></person-group>. <article-title>Study</article-title></element-citation></ref></ref-list></back></article>"
    result = parse_plos_xml(xml, source_url="https://journals.plos.org/article")
    assert "Thomas WE, Trintchina E. Study" in result.references[0]["raw"]
    mixed = (
        xml.replace(b"element-citation", b"mixed-citation")
        .replace(b"<person-group>", b"")
        .replace(b"</person-group>", b"")
    )
    result = parse_plos_xml(mixed, source_url="https://journals.plos.org/article")
    assert "Thomas WE, Trintchina E. Study" in result.references[0]["raw"]


def test_royal_html_citation_supersedes_bare_doi_metadata():
    html = '<div class="ref-list"><div class="ref"><span class="label">1</span><div class="ref-body"><span class="surname">Schinckus</span> C. <span class="year">2012</span>. <span class="article-title">Study</span>. <a href="https://doi.org/10.1234/study">DOI</a></div></div></div>'
    result = merge_metadata_with_html(
        {"references": [{"raw": "10.1234/study", "doi": "10.1234/study"}]},
        html,
        "https://royalsocietypublishing.org/article",
    )
    assert "Schinckus" in result["references"][0]["raw"]
    assert result["references"][0]["title"] == "Study"
    existing = {"references": [{"raw": "Schinckus C. Study. 2012."}]}
    assert (
        merge_metadata_with_html(
            existing,
            '<meta name="citation_reference" content="citation_doi=10.1234/study">',
            "https://royalsocietypublishing.org/article",
        )["references"]
        == existing["references"]
    )


def test_science_unloaded_cited_references_are_reported():
    html = '<article><p>Result <a role="doc-biblioref" href="#R55">55</a>.</p><section id="bibliography"><div class="biblioentry"><div class="citations" id="R1"><div class="citation-content">First reference</div></div></div></section></article>'
    _, result = science_finalize(
        html, "https://www.science.org/doi/10.1126/example", "Result 55.", {}
    )
    assert result["missing_reference_targets"] == ["R55"]
    assert "reference_targets_missing" in result["quality_flags"]
    assert result["warnings"]


def test_science_missing_reference_flag_reaches_acceptance():
    from paper_fetch.http import HttpTransport
    from paper_fetch.providers._registry import provider_bundle
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from paper_fetch.models import FetchEnvelope
    from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance

    doi = "10.1126/example"
    _, extraction = science_finalize(
        '<a role="doc-biblioref" href="#R55">55</a>',
        "https://www.science.org/doi/" + doi,
        "",
        {},
    )
    metadata = {"doi": doi, "title": "Study"}
    payload = RawFulltextPayload(
        provider="science",
        content=ProviderContent(
            route_kind="html",
            source_url="https://www.science.org/doi/" + doi,
            content_type="text/html",
            body=b"",
            merged_metadata=metadata,
            markdown_text="# Study\n\n## Results\n\n" + "Measured result. " * 600,
            diagnostics={"extraction": extraction},
        ),
    )
    client = provider_bundle("science").client_factory(HttpTransport(), {})
    article = client.to_article_model(metadata, payload)
    assert "reference_targets_missing" in article.quality.flags
    assert any("R55" in warning for warning in article.quality.warnings)
    acceptance = evaluate_fetch_acceptance(
        FetchEnvelope(
            doi=doi, source=article.source, article=article, has_fulltext=True
        ),
        asset_profile="none",
    )
    assert acceptance.overall == "degraded"
