"""Small source contracts with arbitrary identifiers, labels and prose."""

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pytest

from paper_fetch.extraction.html.object_links import prepare_retained_object_links
from paper_fetch.providers._html_section_markdown import (
    render_container_markdown,
    render_clean_text_from_html,
)
from paper_fetch.extraction.html.tables import render_table_inline_text
from paper_fetch.extraction.markdown_render.formulas import render_inline_latex_markdown
from paper_fetch.models import article_from_markdown


@pytest.mark.parametrize("identity", ["note-Z73", "custom.figure.241"])
def test_explicit_aliases_and_popup_callouts_retain_source_links(identity):
    soup = BeautifulSoup(
        f'<article><h3 id="{identity}" data-legacy-id="old-{identity}">Protocol</h3><p><a data-rid="{identity}" href="#">see protocol</a> (<a href="#old-{identity}">12</a>)</p></article>',
        "lxml",
    )
    prepare_retained_object_links(soup, "https://publisher.example/paper")
    output = render_clean_text_from_html(soup.p)
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(output), "lxml"
    )
    assert [a["href"] for a in rendered.select("a")] == [
        "https://publisher.example/paper#" + identity
    ] * 2
    assert "(12)" in rendered.get_text()


def test_table_paragraphs_links_and_bold_remain_semantic():
    soup = BeautifulSoup(
        '<td><p>productive</p><p>vocabulary <strong>42</strong> <a href="https://example.org/data set">source</a></p></td>',
        "html.parser",
    )
    output = render_table_inline_text(soup.td)
    assert "productive<br>vocabulary" in output
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(output), "lxml"
    )
    assert rendered.strong.get_text() == "42"
    assert rendered.a["href"] == "https://example.org/data%20set"


def test_script_children_use_html_emphasis():
    soup = BeautifulSoup(
        "<p>x<sub><em>j</em></sub> and y<sub><strong>z</strong></sub></p>", "lxml"
    )
    output = render_clean_text_from_html(soup.p)
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(output), "lxml"
    )
    assert rendered.select_one("sub em").get_text() == "j"
    assert rendered.select_one("sub strong").get_text() == "z"


def test_explicit_list_label_replaces_internal_counter():
    soup = BeautifulSoup(
        '<article><ol><li value="79" data-list-item-label="Q)"><p>Choice.</p><p>Continuation.</p><ul><li>Nested.</li></ul></li></ol></article>',
        "lxml",
    )
    lines = []
    render_container_markdown(soup.article, lines, level=2)
    output = "\n".join(lines)
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(output), "lxml"
    )
    assert rendered.li.get_text().strip().startswith("Q) Choice.")
    assert rendered.select_one("li li").get_text().strip() == "Nested."
    assert "79." not in output


def test_currency_is_inline_literal_with_source_value():
    assert render_inline_latex_markdown(r"\$47.25") == r"\$47.25"


def test_pdf_body_and_metadata_abstract_have_separate_rendering():
    body = "# Converter title\n\nAbstract. Source abstract.\n\n## References\n\nEntry."
    article = article_from_markdown(
        source="mdpi_pdf",
        metadata={"title": "Paper", "abstract": "<p>Abstract. Source abstract.</p>"},
        doi="10.0000/example",
        markdown_text=body,
    )
    output = article.to_ai_markdown(max_tokens="full_text", include_refs="all")
    assert body in output
    assert "**Abstract.**" not in output
    assert "<p>" not in article.metadata.abstract


@pytest.mark.parametrize("marker", ["5.", "-"])
def test_semantic_insertion_keeps_list_continuations_and_display_math(marker):
    from paper_fetch.extraction.html._runtime import _filtered_body_blocks
    from paper_fetch.providers._arxiv_html import (
        _inject_arxiv_semantic_blocks,
        _clean_arxiv_html_markdown_noise,
    )

    indent = " " * (len(marker) + 1)
    continuation = "Continuation belongs to the same choice."
    equation = r"\begin{aligned}" + "\na &= b\\\\\nc &= d\n" + r"\end{aligned}"
    text = (
        f"## Method\n\n{marker} Original choice.\n\n{indent}{continuation}"
        f"\n\n{indent}$$\n"
        + "\n".join(indent + line for line in equation.splitlines())
        + f"\n{indent}$$\n\nPAPER_FETCH_TABLE_PLACEHOLDER_0001"
    )
    result, _, _ = _inject_arxiv_semantic_blocks(
        text,
        entries=[
            {
                "placeholder": "PAPER_FETCH_TABLE_PLACEHOLDER_0001",
                "markdown": "| Label | Value |\n| --- | --- |\n| sample | 28 |",
            }
        ],
    )
    result = _clean_arxiv_html_markdown_noise(result)
    from paper_fetch.providers.atypon_browser_workflow.postprocess import (
        _postprocess_browser_workflow_markdown,
    )

    result = _postprocess_browser_workflow_markdown(
        result,
        title="Experiment",
        publisher="pnas",
        figure_assets=[
            {
                "kind": "figure",
                "heading": "Figure 8",
                "url": "https://publisher.example/chart.png",
            }
        ],
    )
    result = _filtered_body_blocks(result, {"title": "Experiment"})["body_text"]
    article = article_from_markdown(
        source="arxiv_html",
        doi="10.0000/example",
        metadata={"title": "Experiment"},
        markdown_text=result,
    )
    output = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).enable("table").render(output),
        "lxml",
    )
    assert continuation in rendered.li.get_text()
    assert r"\begin{aligned}" in rendered.li.get_text()
    assert f"\n{indent}$$\n{indent}" + r"\begin{aligned}" in output
    assert f"\n{indent}" + r"\end{aligned}" + f"\n{indent}$$" in output


@pytest.mark.parametrize("operators", ["[[ and [ ,", "[  versus ] and"])
def test_citation_normalization_preserves_literal_bracket_spacing(operators):
    import xml.etree.ElementTree as ET
    from paper_fetch.providers._article_markdown_common import render_inline_text

    prose = f"Operators {operators} remain part of the API."
    markdown = render_inline_text(ET.fromstring(f"<p>{prose}</p>"))
    article = article_from_markdown(
        source="plos_xml",
        metadata={"title": "Methods"},
        doi="10.0000/test",
        markdown_text=markdown,
    )
    output = article.to_ai_markdown(max_tokens="full_text")
    actual = BeautifulSoup(MarkdownIt("commonmark").render(output), "lxml").get_text()
    assert " ".join(prose.split()) in " ".join(actual.split())


@pytest.mark.parametrize("distance", ["83", "249"])
def test_literal_comparison_remains_visible_in_list(distance):
    import xml.etree.ElementTree as ET
    from paper_fetch.providers._article_markdown_common import render_inline_text

    text = render_inline_text(ET.fromstring(f"<p>&gt;{distance} km of coverage.</p>"))
    output = MarkdownIt("commonmark").render("- " + text)
    rendered = BeautifulSoup(output, "lxml")
    assert rendered.li.get_text().strip() == f">{distance} km of coverage."
    assert rendered.blockquote is None


def test_caption_action_link_does_not_swallow_following_paragraph():
    soup = BeautifulSoup(
        '<article><figure><figcaption>Figure 8: Measurement.</figcaption><div class="c-article-section__figure-description"><p>Caption explanation.</p><a href="/viewer">PowerPoint slide</a></div><img src="/chart.png"/></figure><p>Following scientific paragraph.</p></article>',
        "lxml",
    )
    lines = []
    render_container_markdown(soup.article, lines, level=2)
    from paper_fetch.providers.html_springer_nature import (
        postprocess_springer_nature_markdown,
    )

    output = postprocess_springer_nature_markdown("\n".join(lines))
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(output), "lxml"
    )
    assert any(
        p.get_text() == "Following scientific paragraph." for p in rendered.select("p")
    )
    assert "Caption explanation." in rendered.get_text()


def test_normalized_math_inside_source_wrapper_stays_opaque():
    soup = BeautifulSoup(
        '<p>Value <span class="inline-formula"><span data-paper-fetch-markdown="1">$q_{r}$</span>, then <span class="inline-formula"><span data-paper-fetch-markdown="1">$s$</span>.</span></span></p>',
        "lxml",
    )
    output = render_clean_text_from_html(soup.p)
    assert "$q_{r}$" in output and "$s$" in output
    assert "[Formula unavailable]" not in output


@pytest.mark.parametrize(
    "callout", ["#ref-92", "#", "https://publisher.example/doi/full/10.0000/test#"]
)
def test_source_cross_reference_cannot_become_figure_rendition(callout):
    from paper_fetch.extraction.html.assets import extract_figure_assets

    source = "https://publisher.example/doi/full/10.0000/test"
    soup = BeautifulSoup(
        f'<article><figure id="Fig7"><figcaption>Figure 7. Illustration from <a href="{callout}" aria-label="Open figure in viewer">92</a>.</figcaption><img src="/images/chart-large.jpg"/></figure><li id="ref-92">Reference.</li></article>',
        "lxml",
    )
    prepare_retained_object_links(soup, source)
    assets = extract_figure_assets(str(soup.figure), source)
    assert assets[0]["url"] == "https://publisher.example/images/chart-large.jpg"


def test_pnas_body_siblings_retain_acknowledgments_in_source_order():
    from paper_fetch.providers.atypon_browser_workflow.profile import (
        _select_content_nodes,
    )

    soup = BeautifulSoup(
        '<article><section id="abstract"><h2>Abstract</h2><p>Summary.</p></section><section id="bodymatter"><p>Discovery.</p></section><section role="doc-acknowledgments"><h2>Acknowledgments</h2><p>Grant Q-729.</p></section><section class="data-availability"><h2>Data Availability</h2><p>Repository.</p></section></article>',
        "lxml",
    )
    selected = _select_content_nodes(soup.article, publisher="pnas")
    text = " ".join(node.get_text(" ", strip=True) for node in selected)
    assert (
        text.index("Discovery.")
        < text.index("Grant Q-729.")
        < text.index("Repository.")
    )


def test_jats_back_sections_keep_funding_and_acknowledgment_order():
    from paper_fetch.providers._article_markdown_jats import parse_jats_xml

    extraction = parse_jats_xml(
        b'<article><front><article-meta><title-group><article-title>Study</article-title></title-group></article-meta></front><body><sec><title>Results</title><p>Discovery.</p></sec></body><back><sec sec-type="funding-information"><title>Funding</title><p>Grant Z-83.</p></sec><ack><title>Acknowledgments</title><p>Field support.</p></ack></back></article>',
        source_url="https://publisher.example/study",
    )
    text = extraction.markdown_text
    assert (
        text.index("Discovery.")
        < text.index("## Funding")
        < text.index("Grant Z-83.")
        < text.index("## Acknowledgments")
        < text.index("Field support.")
    )


def test_table_link_keeps_source_superscript_label():
    soup = BeautifulSoup(
        '<td>Method<a href="#note-T"><sup><em>b</em></sup></a></td>', "html.parser"
    )
    output = render_table_inline_text(soup.td)
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(output), "lxml"
    )
    assert rendered.select_one("a sup em").get_text() == "b"


def test_currency_and_literal_brackets_do_not_hide_following_sections():
    article = article_from_markdown(
        source="springer_html",
        doi="10.0000/example",
        metadata={"title": "Budget"},
        markdown_text="Costs reached $47 million.\n\n## Results\n\nCosts reached $83 million.\n\n## Discussion\n\nLiteral \\[ values.\n\n## Conclusion\n\nEnd \\] values.",
    )
    assert [section.heading for section in article.sections] == [
        "",
        "Results",
        "Discussion",
        "Conclusion",
    ]
    assert "$47 million" in article.sections[0].text


def test_author_math_markers_do_not_enter_names():
    from paper_fetch.providers._arxiv_authors import (
        _candidate_arxiv_author_text_from_person_node,
    )

    source = BeautifulSoup(
        '<span class="ltx_personname">Lin Example<math alttext="a"><mi>a</mi></math></span>',
        "lxml",
    )
    assert _candidate_arxiv_author_text_from_person_node(source.span) == "Lin Example"


def test_footnote_controls_keep_source_superscript_after_repeated_normalization():
    from paper_fetch.providers._tandf_html import _normalize_tandf_reference_controls

    source = BeautifulSoup(
        '<p>Value<a data-label="footnote" href="#note-41"><span class="off-screen">Footnote</span><sup>41</sup></a></p>',
        "lxml",
    )
    _normalize_tandf_reference_controls(source)
    _normalize_tandf_reference_controls(source)
    assert source.sup.get_text() == "41"
    assert source.a.get_text() == "41"
    assert source.a["href"] == "#note-41"


def test_figure_insertion_reads_source_ids_from_partial_callout_labels():
    from paper_fetch.extraction.html.figure_links import inject_inline_figure_links

    output = inject_inline_figure_links(
        "## Method\n\nSee [panels](https://publisher.example/paper#object-Q) and [detail](https://publisher.example/paper#object-R).",
        figure_assets=[
            {
                "kind": "figure",
                "heading": "Figure 12",
                "dom_id": "object-Q",
                "url": "https://publisher.example/plot.png",
            },
            {
                "kind": "figure",
                "heading": "Figure 13",
                "dom_id": "object-R",
                "url": "https://publisher.example/detail.png",
            },
        ],
        clean_markdown_fn=lambda text: text,
    )
    assert output.index(
        "![Figure 12](https://publisher.example/plot.png)"
    ) < output.index("![Figure 13](https://publisher.example/detail.png)")
