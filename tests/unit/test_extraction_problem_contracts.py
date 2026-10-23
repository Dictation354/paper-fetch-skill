"""Minimal contracts for the extraction defects listed in problems.md."""

from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from paper_fetch.extraction.html.inline import render_html_inline_node
from paper_fetch.extraction.markdown_render import MarkdownList, render_list
from paper_fetch.models.sections import section_kind_for_heading
from paper_fetch.providers._article_markdown_common import render_inline_text
from paper_fetch.providers._article_markdown_math import render_mathml_expression
from paper_fetch.providers._article_markdown_copernicus import parse_copernicus_xml
from paper_fetch.providers._article_markdown_elsevier import render_elsevier_blocks
from paper_fetch.providers._arxiv_authors import _normalize_official_html_latexml_notes
from paper_fetch.providers._arxiv_graphics import (
    prepare_arxiv_graphics,
    INLINE_SVG_PREFIX,
)
from paper_fetch.providers._html_section_markdown import render_container_markdown
from paper_fetch.providers._science_html import science_before_block_normalization
from paper_fetch.providers._wiley_html import wiley_before_block_normalization
from paper_fetch.providers._ams_dom import _normalize_ams_dom


def test_citation_cleanup_keeps_formula_and_code_character_data():
    from paper_fetch.markdown.citations import (
        clean_citation_markers,
        normalize_inline_citation_markdown,
    )

    text = "value $x\\ {}$, literal `a_ b * c` and [x_y](https://example.org/a_b)."
    assert clean_citation_markers(text) == text
    assert normalize_inline_citation_markdown(text) == text
    adjacent = r"See \[@@PF_CITE:12@@\] and [Table 4](#t4)."
    normalized = normalize_inline_citation_markdown(adjacent)
    assert "@@PF_CITE" not in normalized
    assert "<sup>12</sup>" in normalized
    assert "[Table 4](#t4)" in normalized
    indented = "1. first\n\n   continuation<sup>9</sup>.\n2. second"
    assert "\n   continuation<sup>9</sup>." in normalize_inline_citation_markdown(
        indented
    )


def test_source_spacing_after_scripts_survives_linked_prose():
    spaced = BeautifulSoup(
        '<p><i>K</i><sub>DP</sub> (<a href="#fig7">Fig. 7b</a>)</p>', "lxml"
    )
    assert "</sub> (" in render_html_inline_node(spaced.p)
    adjacent = BeautifulSoup("<p>f<sub>n</sub>(x)</p>", "lxml")
    assert render_html_inline_node(adjacent.p) == "f<sub>n</sub>(x)"


def test_equation_number_belongs_to_its_formula_wrapper():
    from paper_fetch.providers.atypon_browser_workflow.formulas import _equation_label

    soup = BeautifulSoup(
        '<div class="formula-wrap"><div class="disp-formula" id="jumplink-d1"></div><span class="label">(1)</span></div><div class="formula-wrap"><div class="disp-formula" id="jumplink-d1-1"></div></div>',
        "lxml",
    )
    first, second = soup.select(".disp-formula")
    assert _equation_label(first) == "Equation 1."
    assert _equation_label(second) == ""


def test_tandf_layout_list_keeps_bullets_numbering_and_inline_semantics():
    from paper_fetch.providers._tandf_html import tandf_before_block_normalization

    soup = BeautifulSoup(
        '<section><table class="listgroup"><tr><td>•</td><td><p>Highlight <i>x</i>.</p></td></tr></table><table class="listgroup"><tr><td>(3)</td><td><p><i>X</i><sup>2</sup>*D_LST.</p></td></tr></table></section>',
        "lxml",
    )
    tandf_before_block_normalization(soup.section)
    lines = []
    render_container_markdown(soup.section, lines, level=2)
    markdown = "\n".join(lines)
    assert "- Highlight *x*." in markdown
    assert r"3. *X*<sup>2</sup>\*D\_LST." in markdown


def test_aip_editor_badge_is_not_part_of_the_article_title():
    from paper_fetch.providers._aip_html import _strip_aip_title_badges

    assert (
        _strip_aip_title_badges(
            "Paper ![Image](/Themes/Client/app/img/editorspick-icon.svg)"
        )
        == "Paper"
    )


def test_mathml_numeric_and_operator_variants_keep_source_typeface():
    expression = render_mathml_expression(
        ET.fromstring(
            '<math><mn mathvariant="bold">1</mn><mo>+</mo><mn>10</mn><mo mathvariant="italic">exp</mo><mi>x</mi><mtext mathvariant="italic">Land ocean</mtext></math>'
        )
    )
    assert r"\mathbf{1}" in expression
    assert r"\mathit{exp}" in expression
    assert r"\mathrm{10}" not in expression
    assert r"\textit{Land ocean}" in expression


def test_copernicus_embedded_html_keeps_scripts_without_changing_literals():
    extracted = parse_copernicus_xml(
        b"<article><front><article-meta><abstract><p>OH + C&lt;sub&gt;3&lt;/sub&gt;H, &lt;i&gt;n&lt;/i&gt; and a_b.</p></abstract></article-meta></front></article>",
        source_url="https://acp.copernicus.org/a.xml",
    )
    assert (
        extracted.abstract_sections[0]["text"] == r"OH + C<sub>3</sub>H, *n* and a\_b."
    )


def test_acs_table_note_resolves_supplement_path_against_publisher_origin():
    from paper_fetch.providers._acs_html import acs_before_block_normalization

    soup = BeautifulSoup(
        '<section><div class="table-wrap"><table><tr><td>x</td></tr></table><div class="table-wrap-foot">See <a href="/acsodf/article-supplement/1/pdf/example/">Table S1</a>.</div></div></section>',
        "lxml",
    )
    acs_before_block_normalization(soup.section)
    assert (
        "[Table S1](https://pubs.acs.org/acsodf/article-supplement/1/pdf/example/)"
        in soup.get_text()
    )


def test_inline_container_keeps_display_fences_and_list_continuation():
    soup = BeautifulSoup(
        r'<section><ol><li>before <span class="display-equation"><tex-math>\begin{align*}x&amp;=1\end{align*}</tex-math></span> after</li></ol></section>',
        "lxml",
    )
    lines = []
    render_container_markdown(soup.section, lines, level=2)
    assert lines == [
        "1. before",
        "",
        "   $$",
        r"   \begin{align*}x&=1\end{align*}",
        "   $$",
        "",
        "   after",
        "",
    ]


def test_arxiv_normalization_preserves_display_node_until_html_rendering():
    from paper_fetch.providers._arxiv_authors import (
        _normalize_official_html_latexml_math_nodes,
    )

    soup = BeautifulSoup(
        r'<section><p>before <math class="ltx_Math" display="block"><annotation encoding="application/x-tex">\begin{split}x&amp;=1\end{split}</annotation></math> after</p></section>',
        "lxml",
    )
    assert _normalize_official_html_latexml_math_nodes(soup.section) == 1
    lines = []
    render_container_markdown(soup.section, lines, level=2)
    assert lines == [
        "before\n$$\n" + r"\begin{split}x&=1\end{split}" + "\n$$\nafter",
        "",
    ]


def test_arxiv_equation_cell_establishes_display_context_for_inline_math():
    from paper_fetch.providers._arxiv_authors import _arxiv_math_markdown

    soup = BeautifulSoup(
        r'<table><tr><td class="ltx_eqn_cell"><math display="inline" alttext="\begin{split}x&amp;=1\end{split}"/></td></tr></table>',
        "lxml",
    )
    assert (
        _arxiv_math_markdown(soup.math)
        == "\n\n$$\n" + r"\begin{split}x&=1\end{split}" + "\n$$\n\n"
    )


def test_empty_script_base_and_visible_fences_preserve_source_structure():
    expression = render_mathml_expression(
        ET.fromstring(
            '<math><msup><mrow/><mo>′</mo></msup><mfenced open="{" close=""><mi>x</mi></mfenced></math>'
        )
    )
    assert "{}^{′}" in expression
    assert r"\{x" in expression
    assert (
        render_mathml_expression(
            ET.fromstring("<math><mo>{</mo><mi>x</mi><mo>}</mo></math>")
        )
        == r"\{x\}"
    )


def test_multiple_list_paragraphs_keep_indented_formula_and_nested_item():
    lines = render_list(
        MarkdownList(items=["first\n\n$$\nx=1\n$$\n\n- child"], ordered=True)
    )
    assert lines == ["1. first", "", "   $$", "   x=1", "   $$", "", "   - child", ""]


def test_elsevier_list_label_stays_with_its_paragraphs():
    node = ET.fromstring(
        "<sections><para>before<list><list-item><label>1.</label><para>first</para><para>second</para></list-item></list>after</para></sections>"
    )
    rendered = "\n".join(render_elsevier_blocks(node, heading_level=2))
    assert (
        rendered.index("before")
        < rendered.index("1. first")
        < rendered.index("   second")
        < rendered.index("after")
    )


def test_copernicus_footnote_keeps_sentence_tail_and_notes():
    extracted = parse_copernicus_xml(
        b'<article><body><sec><title>Methods</title><p>start<fn id="f1"><p>note text</p></fn> end.</p></sec></body></article>',
        source_url="https://example.org/a.xml",
    )
    assert "start<sup>1</sup> end." in extracted.markdown_text
    assert extracted.markdown_text.index("end.") < extracted.markdown_text.index(
        "## Notes"
    )
    assert extracted.markdown_text.count("note text") == 1
    assert section_kind_for_heading("Notes") == "body"


def test_copernicus_prefixed_citation_and_equation_xref():
    xml = b'<article><body><sec><title>Methods</title><p><xref ref-type="bibr" rid="r"><named-content content-type="pre">e.g., </named-content></xref>; Eq. (<xref ref-type="disp-formula" rid="e"/>).</p><disp-formula id="e"><label>3</label><tex-math>x=1</tex-math></disp-formula></sec></body><back><ref-list><ref id="r"><label>Smith(2020)</label><mixed-citation>Smith 2020</mixed-citation></ref></ref-list></back></article>'
    extracted = parse_copernicus_xml(xml, source_url="https://example.org/a.xml")
    assert (
        "e.g., [Smith (2020)](https://example.org/a.xml#r)" in extracted.markdown_text
    )
    assert "Eq. (3)." in extracted.markdown_text


def test_arxiv_notes_have_one_marker_and_precede_bibliography():
    soup = BeautifulSoup(
        '<article><section><p>before<span class="ltx_note ltx_role_footnote"><sup class="ltx_note_mark">1</sup><span class="ltx_note_content"><sup class="ltx_note_mark">1</sup><span class="ltx_tag ltx_tag_note">1</span>note</span></span> after</p></section><section class="ltx_bibliography"><h2>References</h2></section></article>',
        "lxml",
    )
    assert _normalize_official_html_latexml_notes(soup.article) == 1
    assert soup.p.get_text() == "before1 after"
    assert soup.article.get_text().count("note") == 1
    assert soup.article.get_text().index("Notes") < soup.article.get_text().index(
        "References"
    )
    assert soup.select_one(".ltx_tag_note") is None


def test_arxiv_appendix_foreignobject_uses_existing_svg_route():
    soup = BeautifulSoup(
        '<article><section><div class="ltx_para"><span class="ltx_inline-block"><svg id="example" class="ltx_picture"><foreignObject><p>answer</p></foreignObject></svg></span></div></section></article>',
        "lxml",
    )
    prepare_arxiv_graphics(soup.article, "https://arxiv.org/html/v1")
    assert soup.find(id="example")["src"].startswith(INLINE_SVG_PREFIX)


def test_html_inline_runs_and_emphasis_stay_together():
    soup = BeautifulSoup(
        "<section>When <em>L</em> is <sup>2</sup>.<p>next</p></section>", "lxml"
    )
    lines = []
    render_container_markdown(soup.section, lines, level=2)
    assert lines == ["When *L* is <sup>2</sup>.", "", "next", ""]
    generated_table = BeautifulSoup("<section></section>", "lxml").section
    generated_table.append("| A | B |\n| --- | --- |\n| 1 | 2 |")
    table_lines = []
    render_container_markdown(generated_table, table_lines, level=2)
    assert table_lines == ["| A | B |\n| --- | --- |\n| 1 | 2 |", ""]
    assert (
        render_html_inline_node(BeautifulSoup("<p><i>A</i><i>B</i></p>", "lxml").p)
        == "<em>A</em><em>B</em>"
    )
    assert (
        render_html_inline_node(BeautifulSoup("<p>pH<i>, Abra alba</i></p>", "lxml").p)
        == "pH<em>, Abra alba</em>"
    )
    assert (
        render_inline_text(ET.fromstring("<p><bold>Title.</bold>Text</p>"))
        == "<strong>Title.</strong>Text"
    )


def test_science_model_continuations_merge_source_span_once():
    soup = BeautifulSoup(
        '<article><table><tbody><tr><th rowspan="2">Model</th><td rowspan="2">0.624</td><td>MAP*</td></tr><tr><td>Pdev, Woody</td></tr></tbody></table></article>',
        "lxml",
    )
    science_before_block_normalization(soup.article)
    assert len(soup.select("tbody tr")) == 1
    assert [cell.get_text() for cell in soup.select("tr > *")] == [
        "Model",
        "0.624",
        "MAP*Pdev, Woody",
    ]
    assert not soup.select("[rowspan]")


def test_wiley_legacy_paragraph_gets_existing_splitter_contract():
    soup = BeautifulSoup(
        '<article><div class="paragraph-element">before<div class="inline-equation"><span class="inline-equation__label">(1)</span></div>after X<sub>i</sub></div></article>',
        "lxml",
    )
    wiley_before_block_normalization(soup.article)
    assert soup.select_one(".paragraph-element")["role"] == "paragraph"
    assert soup.select_one(".display-equation") is not None


def test_ams_appendix_algorithm_condition_keeps_its_continuation():
    soup = BeautifulSoup(
        "<article><app><p><strong>with</strong> α=max{α|J[x]</p><p>&lt;J[y]}</p></app></article>",
        "lxml",
    )
    _normalize_ams_dom(soup.article)
    assert len(soup.select("app p")) == 1
    assert soup.app.find("br") is not None
    assert "max{α|J[x]" in soup.app.get_text()
    assert "<J[y]}" in soup.app.get_text()


def test_explicit_empty_fences_keep_difference_and_default_comma():
    assert (
        render_mathml_expression(
            ET.fromstring(
                '<math><mfenced separators=""><mi>E</mi><mo>−</mo><mi>P</mi><mi>m</mi></mfenced></math>'
            )
        )
        == "(E - Pm)"
    )
    assert (
        render_mathml_expression(
            ET.fromstring("<math><mfenced><mi>x</mi><mi>y</mi></mfenced></math>")
        )
        == "(x, y)"
    )


def test_mathml_spacing_relations_operators_and_source_variants():
    raw = '<math><mi mathvariant="script">N</mi><mo>~</mo><mi>log</mi><mi mathvariant="normal">CO</mi><mn>0.15</mn><mo> </mo><mn>0.2</mn></math>'
    latex = render_mathml_expression(ET.fromstring(raw))
    assert r"\mathcal{N}" in latex and r"\sim" in latex
    assert r"\log \mathrm{CO}" in latex
    assert r"0.15\ {}0.2" in latex
    # A missing separator in the source is not an invitation to add matrix cells.
    assert "&" not in latex
    assert (
        render_mathml_expression(ET.fromstring("<math><mi>\\alphax</mi></math>"))
        == r"\alphax"
    )


def test_source_word_boundaries_literal_text_and_nested_styles_render_visibly():
    from markdown_it import MarkdownIt

    source = "<p>para<bold>form</bold>aldehyde; Herb*MAP*YSD; _to_; $10 and $20; <italic>A</italic><italic>B</italic>; CO<inf>2</inf>.</p>"
    markdown = render_inline_text(ET.fromstring(source))
    html = MarkdownIt("commonmark", {"html": True}).render(markdown)
    rendered = BeautifulSoup(html, "html.parser")
    assert (
        rendered.get_text().strip()
        == "paraformaldehyde; Herb*MAP*YSD; _to_; $10 and $20; AB; CO2."
    )
    assert rendered.select_one("strong").get_text() == "form"
    assert [n.get_text() for n in rendered.select("em")] == ["A", "B"]
    assert rendered.sub.get_text() == "2"


def test_html_lists_keep_numbers_nested_paragraphs_and_source_labels():
    soup = BeautifulSoup(
        '<section><ol start="5"><li><p>First.</p><p>Continue.</p><ul><li>Child</li></ul></li><li data-list-item-label="B)">Second.</li></ol></section>',
        "lxml",
    )
    lines = []
    render_container_markdown(soup.section, lines, level=2)
    markdown = "\n".join(lines)
    assert "5. First.\n\n   Continue." in markdown
    assert "   - Child" in markdown
    assert "- B) Second." in markdown


def test_science_mixed_declarations_keep_links_and_stop_at_peer_label():
    soup = BeautifulSoup(
        '<article><section id="acknowledgments"><p><b>Funding:</b> Grant. <b>Data and materials availability:</b> See <a href="https://example.org/data">data</a>. <i>Source wording.</i> <b>Competing interests:</b> None.</p></section></article>',
        "lxml",
    )
    science_before_block_normalization(soup.article)
    once = str(soup)
    science_before_block_normalization(soup.article)
    assert str(soup) == once
    statement = soup.select_one(".data-availability")
    assert statement.a["href"] == "https://example.org/data"
    assert statement.i.get_text() == "Source wording."
    assert "Grant." not in statement.get_text() and "None." not in statement.get_text()


def test_supplementary_uses_resolved_target_identity():
    from paper_fetch.extraction.html.assets.supplementary import (
        extract_supplementary_assets,
    )

    entries = extract_supplementary_assets(
        '<a href="supp.pdf">Supplement</a><a href="https://example.org/p/supp.pdf">Supplementary file (PDF)</a>',
        "https://example.org/p/article",
    )
    assert len(entries) == 1
    assert entries[0]["url"] == "https://example.org/p/supp.pdf"


def test_extended_data_controls_and_availability_merge_preserve_distinct_prose():
    from paper_fetch.models import article_from_markdown

    article = article_from_markdown(
        source="springer_html",
        doi=None,
        metadata={"title": "Study"},
        markdown_text="## Results\n\nMeasured result.\n\n## Data availability\n\nFirst author statement.\n\n## Data availability\n\nSecond author statement.\n\n## Extended Data\n\nSource caption.\n\n![Figure](https://example.org/ed.png)\n",
    )
    full = article.to_ai_markdown(asset_profile="all")
    assert full.count("## Data availability") == 1
    assert "First author statement." in full and "Second author statement." in full
    assert "## Extended Data" in full and "Source caption." in full
    assert "Source caption." not in article.to_ai_markdown(
        asset_profile="all", include_supplementary=False
    )
    assert "Source caption." not in article.to_ai_markdown(asset_profile="body")
    assert (
        next(s for s in article.sections if s.heading == "Extended Data").kind
        == "supplementary"
    )
    from paper_fetch.models.sections import renderable_body_sections

    assert [s.heading for s in renderable_body_sections(article.sections)] == [
        "Results"
    ]
    assert "Source caption." not in article.to_ai_markdown(
        asset_profile="all", max_tokens=24
    )


def test_downloaded_supplement_uses_persistent_target_without_rewriting_code():
    from paper_fetch.models import ArticleModel, Asset, Metadata, Section

    url = "https://example.org/supplement/file.pdf"
    article = ArticleModel(
        doi="10.1234/source",
        source="generic",
        metadata=Metadata(title="Source"),
        sections=[
            Section(
                heading="Supplementary Materials",
                level=2,
                kind="supplementary",
                text=f"Source description. [PDF]({url})\n\n`[PDF]({url})`",
            )
        ],
        assets=[
            Asset(
                kind="supplementary",
                heading="PDF",
                url=url,
                path="supplementary/file.pdf",
            )
        ],
    )
    markdown = article.to_ai_markdown(asset_profile="all")
    assert "[PDF](supplementary/file.pdf)" in markdown
    assert f"`[PDF]({url})`" in markdown
    assert markdown.count("](supplementary/file.pdf)") == 1


def test_extended_data_figure_and_table_assets_follow_supplementary_controls():
    from paper_fetch.models import ArticleModel, Asset, Metadata, Section

    article = ArticleModel(
        doi=None,
        source="springer_html",
        metadata=Metadata(title="Source"),
        sections=[
            Section(heading="Results", level=2, kind="body", text="Measured result."),
            Section(
                heading="Extended Data",
                level=2,
                kind="supplementary",
                text="Source caption.\n\n![Figure 1](https://example.org/ed.png)",
            ),
        ],
        assets=[
            Asset(
                kind="figure",
                heading="Extended Data Figure 1",
                section="supplementary",
                original_url="https://example.org/ed.png",
            ),
            Asset(
                kind="table",
                heading="Extended Data Table 1",
                section="supplementary",
                url="https://example.org/table.png",
            ),
        ],
    )
    full = article.to_ai_markdown(asset_profile="all")
    assert full.count("](https://example.org/ed.png)") == 1
    assert "## Figures" not in full
    assert "](https://example.org/table.png)" in full
    for kwargs in (
        {"asset_profile": "body"},
        {"asset_profile": "all", "include_supplementary": False},
    ):
        hidden = article.to_ai_markdown(**kwargs)
        assert "Extended Data" not in hidden
        assert "https://example.org/ed.png" not in hidden
        assert "https://example.org/table.png" not in hidden
