"""Small source fragments for Elsevier rendering and navigation contracts."""

import re

from bs4 import BeautifulSoup
import pytest

from paper_fetch.models import SemanticLosses, article_from_markdown
from paper_fetch.providers import _elsevier_html as html
from paper_fetch.providers._elsevier_navigation import finalize_markdown
from paper_fetch.providers._elsevier_xml_rules import format_elsevier_reference
from paper_fetch.providers._html_section_markdown import render_container_markdown


def render(source, *, navigation=False):
    soup = BeautifulSoup(source, "lxml")
    losses = SemanticLosses()
    html._prepare_dom(soup, "https://www.sciencedirect.com/article/one", losses)
    if navigation:
        html._prepare_navigation(soup.body, soup, [])
    html._prepare_figures(soup.body, soup)
    lines = []
    render_container_markdown(
        soup.body,
        lines,
        level=2,
        preserve_heading_levels=True,
        render_table_cell=html._render_table_cell,
    )
    return finalize_markdown("\n".join(lines)), losses


def test_display_figure_math_caption_blocks_and_placeholder():
    md, _ = render("""<span class="display"><figure id="fig1"><img src="a.jpg"/>
    <span class="captions"><p>Figure 1. A <math><mi>x</mi></math> measurement.</p>
    <div>Fuente: Original.</div></span></figure></span>
    <figure><img src="b.jpg" alt="Unlabelled Image"><span class="captions">Unlabelled Image</span></figure>""")
    assert "measurement." in md and "$x$" in md
    assert "measurement.\n\nFuente:" in md
    assert "Unlabelled Image" not in md
    assert md.count("![") == 2


def test_equation_label_comes_only_from_source_and_image_fallback_is_counted():
    md, losses = render("""<span class="display"><span class="formula" id="eq0010">
    <math><mi>x</mi></math></span></span>
    <span class="display"><span class="formula" id="eq0020"><span class="label">(7)</span>
    <math><mi>y</mi></math></span></span>
    <span class="display"><span class="formula"><img src="equation.png"></span></span>""")
    assert "Equation 10" not in md and "Equation 20" not in md
    assert "(7)" in md and "equation.png" in md
    assert losses.formula_fallback_count == 1


def test_real_paragraph_ids_underline_and_topics_keep_prose_together():
    md, _ = render("""<div id="p0030">The <u>same</u> sentence has
    <a href="/topics/science/temperature">temperature</a> data.</div>""")
    assert md.strip() == "The same sentence has temperature data."


def test_table_callback_reaches_nested_sections_lists_and_default_is_unchanged():
    source = """<section><h2>Results</h2><ul><li><div><table>
    <tr><th>A</th></tr><tr><td>x<br>y<sub>2</sub> <a href="https://example.org/">source</a>
    <math><mi>z</mi></math></td></tr></table></div></li></ul></section>"""
    md, _ = render(source)
    assert "x<br>y<sub>2</sub>" in md
    assert "[source](https://example.org/)" in md and "$z$" in md
    lines = []
    render_container_markdown(BeautifulSoup(source, "lxml").body, lines, level=2)
    assert "x<br>y" not in "\n".join(lines)


@pytest.mark.parametrize(
    "body", ["Writer. Source.", "Writer. Source. https://doi.org/10.1000/test"]
)
def test_reference_doi_once_before_annotation(body):
    raw = format_elsevier_reference(
        1, body, "Writer, 2024", doi="10.1000/test", keys=["bib1"]
    )
    assert raw.startswith('1. <a id="elsevier-bib1"></a>Writer.')
    assert raw.count("10.1000/test") == 1
    assert raw.endswith("[Writer, 2024]")


def test_navigation_section_and_list_object_ownership_and_table_target():
    md, _ = render(
        """<section id="sec1"><h2>Results</h2><p>See <a href="#fig1">Fig. 1</a>,
    <a href="#eq1">equation</a>, <a href="#note1">note</a> and <a href="#inline1">inline</a>.</p>
    <ul><li>Item<figure id="fig1"><img src="one.jpg"><figcaption>Caption.</figcaption></figure>
    <span class="display" id="eq1"><span class="formula"><math><mi>x</mi></math></span></span></li></ul>
    <table><tr><td id="inline1">Cell</td></tr></table><p id="note1">A note.</p></section>""",
        navigation=True,
    )
    assert md.index("## Results") < md.index('id="elsevier-sec1"')
    assert re.search(r'(?m)^  <a id="elsevier-fig1"></a>Caption', md)
    assert 'id="elsevier-inline1"' in md and "[inline](#elsevier-inline1)" in md
    targets = re.findall(r'<a id="([^"]+)"></a>', md)
    assert len(targets) == len(set(targets))
    for key in re.findall(r"\]\(#([^\s)]+)\)", md):
        assert targets.count(key) == 1


def test_finalizer_skips_literals_external_links_and_removes_unretained_targets():
    literal = "`[literal](#elsevier-missing)`\n\n$$\n[a](#elsevier-missing)\n$$\n\n[external](https://example.org/#elsevier-missing)"
    md = finalize_markdown(
        '[lost](#elsevier-missing) [kept](#elsevier-one)\n\n<a id="elsevier-one"></a>Text.\n<a id="elsevier-one"></a>Again.\n'
        + literal
        + '\n\n<a id="elsevier-cut"></a>'
    )
    assert md.startswith("lost [kept](#elsevier-one)")
    assert md.count('id="elsevier-one"') == 1
    assert 'id="elsevier-cut"' not in md
    assert literal in md


@pytest.mark.parametrize("refs", ["all", "none", "top1"])
@pytest.mark.parametrize("budget", ["full_text", 500, 90, 10])
def test_final_article_navigation_respects_reference_selection_and_budget(refs, budget):
    text = """## Results

See [first](#elsevier-ref1) and [second](#elsevier-ref2).

## References

1. <a id="elsevier-ref1"></a>First source.

2. <a id="elsevier-ref2"></a>Second source.
"""
    article = article_from_markdown(
        source="elsevier_html",
        metadata={
            "title": "Article",
            "references": [
                {"raw": '1. <a id="elsevier-ref1"></a>First source.'},
                {"raw": '2. <a id="elsevier-ref2"></a>Second source.'},
            ],
        },
        doi="10.1000/one",
        markdown_text=text,
    )
    md = article.to_ai_markdown(include_refs=refs, max_tokens=budget)
    if budget == "full_text":
        assert ("[second](#elsevier-ref2)" in md) == (refs == "all")
        assert ("[first](#elsevier-ref1)" in md) == (refs != "none")
    for key in re.findall(r"\]\(#([^\s)]+)\)", md):
        assert md.count(f'id="{key}"') == 1


def test_xml_article_notes_keep_source_labels_and_table_notes_stay_out():
    from pathlib import Path
    from paper_fetch.providers._article_markdown_elsevier_document import (
        build_article_structure,
    )

    xml = b"""<article><head><footnote id="f1"><label>1</label><note-para>Permanent address.</note-para></footnote></head>
    <body><sections><section><section-title>Results</section-title><para>Observations.</para></section></sections>
    <table><table-footnote><label>a</label><note-para>Table only.</note-para></table-footnote></table>
    <article-footnote><label>*</label><note-para>Special issue.</note-para></article-footnote></body></article>"""
    structure = build_article_structure(
        provider="elsevier",
        metadata={"title": "Test"},
        xml_body=xml,
        xml_path=Path("a.xml"),
        assets=[],
    )
    body = "\n".join(structure.body_lines)
    notes = body.split("### Article notes", 1)[1]
    assert "1 " in notes and "Permanent address." in notes
    assert "* Special issue." in notes and "Table only." not in notes


@pytest.mark.parametrize(
    "partial",
    [
        '<a id="elsevier-cut',
        '<a id="elsevier-cut">',
        '<a id="elsevier-cut"></a...',
        '<a id="elsevier-cut"></a>',
    ],
)
def test_budget_drops_incomplete_or_orphan_generated_anchors(partial):
    assert "<a" not in finalize_markdown("Text.\n\n" + partial)


def test_explicit_numeric_source_label_keeps_one_list_item():
    from tests.support.markdown_lists import markdown_tree, inline_text

    md, _ = render(
        '<ul><li><span class="list-label">1)</span><span class="list-content"><p>First step.</p></span></li></ul>'
    )
    tree = markdown_tree(md)
    assert len([n for n in tree.walk() if n.type == "list_item"]) == 1
    assert inline_text(tree).startswith("1) First step.")


def test_pdf_never_enters_provider_finalizer(monkeypatch):
    from paper_fetch.providers._registry import ProviderRenderPolicy

    def fail(markdown):
        raise AssertionError("PDF entered provider finalizer")

    monkeypatch.setattr(
        "paper_fetch.provider_catalog.provider_render_policy_for_source",
        lambda source: ProviderRenderPolicy(finalize_markdown=fail),
    )
    article = article_from_markdown(
        source="elsevier_pdf",
        metadata={"title": "Article"},
        doi="10.1000/one",
        markdown_text="Exact converter output.",
    )
    assert "Exact converter output." in article.to_ai_markdown()


def test_bibliography_aliases_use_source_keys_instead_of_position():
    soup = BeautifulSoup(
        """<article><div id="body"><p>See <a href="#bb0040">prior</a>,
    <a href="#ref-id-bb0040">alias</a> and <a href="#bb0005">unknown</a>.</p></div>
    <div id="references"><ol class="references"><li><span class="label"><a id="ref-id-bb0040">Writer, 2024</a></span>
    <span class="reference" id="rf0005">A. Writer. A source.</span></li></ol></div></article>""",
        "lxml",
    )
    refs = html._references(soup)
    html._prepare_navigation(soup.select_one("#body"), soup, refs)
    lines = []
    render_container_markdown(soup.select_one("#body"), lines, level=2)
    md = finalize_markdown("\n".join(lines) + "\n## References\n\n" + refs[0]["raw"])
    assert "[prior](#elsevier-rf0005)" in md
    assert "[alias](#elsevier-rf0005)" in md
    assert "unknown." in md and "#elsevier-bb0005" not in md


def test_xml_navigation_keeps_nested_formula_and_article_note_targets():
    from pathlib import Path
    from paper_fetch.providers._article_markdown_elsevier_document import (
        build_article_structure,
    )

    xml = b"""<article><body><section id="s1"><section-title>Results</section-title>
    <para>See <cross-ref refid="eq1">equation</cross-ref> and <cross-ref refid="fn1">note</cross-ref>.</para>
    <display><formula id="eq1"><tex-math>x=1</tex-math></formula></display></section></body>
    <footnote id="fn1"><label>1</label><note-para>Source note.</note-para></footnote></article>"""
    structure = build_article_structure(
        provider="elsevier",
        metadata={"title": "Test"},
        xml_body=xml,
        xml_path=Path("a.xml"),
        assets=[],
    )
    md = finalize_markdown("\n".join(structure.body_lines))
    assert "[equation](#elsevier-eq1)" in md and "[note](#elsevier-fn1)" in md
    assert md.count('id="elsevier-eq1"') == md.count('id="elsevier-fn1"') == 1


def test_section_containing_only_subsections_keeps_its_target():
    md = finalize_markdown(
        '[parent](#elsevier-parent)\n\n## Parent\n\n<a id="elsevier-parent"></a>\n\n### Child\n\nContent.'
    )
    assert "[parent](#elsevier-parent)" in md
    assert 'id="elsevier-parent"' in md


@pytest.mark.parametrize("profile", ["all", "body", "none"])
def test_navigation_respects_omitted_supplementary_sections(profile):
    article = article_from_markdown(
        source="elsevier_html",
        metadata={"title": "Article"},
        doi="10.1000/one",
        markdown_text="""## Results

See the [attachment](#elsevier-supp).

## Supplementary materials

<a id="elsevier-supp"></a>[Source attachment](https://example.org/source.zip)
""",
    )
    md = article.to_ai_markdown(asset_profile=profile, include_supplementary=True)
    assert ("[attachment](#elsevier-supp)" in md) == (profile == "all")
    assert ('id="elsevier-supp"' in md) == (profile == "all")
