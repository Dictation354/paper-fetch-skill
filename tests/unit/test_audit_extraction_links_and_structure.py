"""Minimal mechanisms from the November extraction audit."""

from bs4 import BeautifulSoup

from paper_fetch.extraction.html.object_links import prepare_retained_object_links
from paper_fetch.markdown.images import short_image_alt
from paper_fetch.providers._article_markdown_jats import parse_jats_xml
from paper_fetch.providers._acs_html import (
    acs_before_block_normalization,
    render_acs_table,
)
from paper_fetch.providers._html_section_markdown import render_container_markdown


def test_explicit_footnote_alias_and_unresolved_script_controls():
    soup = BeautifulSoup(
        '<article><a href="javascript:;" reveal-id="note"><sup>a</sup></a>'
        '<a href="javascript:;"><sub>b</sub></a><span id="fn-note"></span></article>',
        "lxml",
    )
    prepare_retained_object_links(
        soup, "https://example.org/paper", aliases={"note": "fn-note"}
    )
    first, second = soup.select("a")
    assert first["href"] == "https://example.org/paper#fn-note"
    assert not second.get("href")
    assert second.sub.get_text() == "b"


def test_explicit_reference_alias_and_root_relative_links():
    soup = BeautifulSoup(
        '<article><a href="#core-R1">1</a><div id="R1"></div>'
        '<a href="/articles/p#ref">source</a></article>',
        "lxml",
    )
    prepare_retained_object_links(
        soup, "https://example.org/paper", aliases={"core-R1": "R1"}
    )
    assert [a["href"] for a in soup.select("a")] == [
        "https://example.org/paper#R1",
        "https://example.org/articles/p#ref",
    ]


def test_source_figure_language_and_roman_table_number():
    assert short_image_alt("figure", "Figura 3. Full caption") == "Figura 3"
    assert short_image_alt("table", "TABLE II Full caption") == "Table II"
    soup = BeautifulSoup(
        '<section><figure data-paper-fetch-object-kind="table" '
        'data-paper-fetch-inline-src="table.png" data-paper-fetch-inline-alt="Table II">'
        '<b class="fig-label">TABLE II</b><figcaption>Full caption</figcaption>'
        "</figure></section>",
        "lxml",
    )
    lines = []
    render_container_markdown(soup.section, lines, level=2)
    markdown = "\n".join(lines)
    assert "![Table II](table.png)" in markdown
    assert markdown.count("Full caption") == 1


def test_blockquote_retains_nested_paragraph_structure():
    soup = BeautifulSoup(
        "<section><blockquote><p>First <i>quote</i>.</p><p>Second.</p></blockquote></section>",
        "lxml",
    )
    lines = []
    render_container_markdown(soup.section, lines, level=2)
    assert "> First *quote*.\n>\n> Second." in "\n".join(lines)


def test_consecutive_pure_code_joins_and_stops_at_prose_list_and_section():
    source = b"""<article><body><sec><title>Code</title>
      <p><monospace>&gt; command(</monospace></p><p><monospace>+   x = 1)</monospace></p>
      <p>Explanation.</p><p><monospace>&gt; next()</monospace></p>
      <list><list-item><p><monospace>  child()</monospace></p></list-item></list>
      <sec><title>Next</title><p><monospace>&gt; final()</monospace></p></sec>
    </sec></body></article>"""
    result = parse_jats_xml(source, source_url="https://example.org/paper")
    assert "```\n> command(\n+   x = 1)\n```" in result.markdown_text
    assert "```\n> next()\n```" in result.markdown_text
    assert result.markdown_text.index("Explanation.") < result.markdown_text.index(
        "## Next"
    )


def test_acs_segments_share_label_and_lift_spanning_model_once():
    soup = BeautifulSoup(
        """<article><div class="table-wrap"><div>Table 2</div>
      <table><thead><tr><th></th><th colspan="2">y = a + bx</th></tr>
      <tr><th>no.</th><th>a</th><th>b</th></tr></thead>
      <tbody><tr><td>1</td><td>0.5</td><td>0.7</td></tr></tbody></table>
      <table><tr><th>no.</th><th>a</th><th>b</th></tr><tr><td>2</td><td>0.8</td><td>0.9</td></tr></table>
    </div></article>""",
        "lxml",
    )
    acs_before_block_normalization(soup.article)
    assert len(soup.select(".table-wrap")) == 1
    markdown = render_acs_table(
        soup.select_one(".table-wrap"), label="Table 2", caption="Source caption"
    )
    assert markdown.count("**Table 2**") == 1
    assert markdown.count("y = a + bx") == 1
    assert "| no. | a" in markdown
    assert (
        "0.5" in markdown
        and "0.7" in markdown
        and "0.8" in markdown
        and "0.9" in markdown
    )


def test_frontiers_shared_entry_preserves_six_filename_identities():
    from paper_fetch.models import ArticleModel, Asset, Metadata, Section
    from paper_fetch.providers.frontiers import _retain_frontiers_supplementary_section

    article = ArticleModel(
        doi=None,
        source="frontiers_xml",
        metadata=Metadata(title="Paper"),
        sections=[
            Section(
                heading="Supplementary Material",
                level=2,
                kind="supplementary",
                text="Author statement.\n\n- [Source dataset](https://example.org/data)",
            )
        ],
        assets=[
            Asset(
                kind="supplementary",
                heading="Supplementary material",
                anchor_key=f"SM{i}",
                source_href=f"Table_{i}.docx",
                original_url="https://example.org/p#supplementary",
            )
            for i in range(1, 7)
        ],
    )
    _retain_frontiers_supplementary_section(article)
    markdown = article.to_ai_markdown(asset_profile="all", max_tokens="full_text")
    assert markdown.count("## Supplementary") == 1
    assert "[Source dataset](https://example.org/data)" in markdown
    for i in range(1, 7):
        assert markdown.count(f"[Table_{i}.docx]") == 1


def test_arxiv_frontmatter_resource_icons_keep_links_and_scientific_images():
    from paper_fetch.providers._arxiv_graphics import prepare_arxiv_graphics

    soup = BeautifulSoup(
        '<article><table><tr><td><img class="ltx_img_square" src="badge.png"/></td><td><a href="https://example.org/code">Code</a></td></tr></table><figure><img class="ltx_img_square" src="panel.png"/></figure></article>',
        "lxml",
    )
    prepare_arxiv_graphics(soup.article, "https://arxiv.org/html/v1/")
    assert soup.a["href"] == "https://example.org/code"
    assert [image["src"] for image in soup.select("img")] == [
        "https://arxiv.org/html/v1/panel.png"
    ]
