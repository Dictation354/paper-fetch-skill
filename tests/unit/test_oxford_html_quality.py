"""Small structural cases for Oxford and its shared HTML renderers."""

from bs4 import BeautifulSoup, Comment
import pytest

from paper_fetch.extraction.html.inline import render_html_inline_node
from paper_fetch.extraction.markdown_render.formulas import (
    normalize_tex_formula_text,
    render_html_formula_container,
)
from paper_fetch.formula.convert import normalize_latex
from paper_fetch.providers._html_section_markdown import (
    render_clean_text_from_html,
    render_container_markdown,
    render_figure_markdown,
)
from paper_fetch.providers._oxfordacademic_html import extract_markdown
from tests.support.oxford_html import build_oxford_html_article

URL = "https://academic.oup.com/journal/article/1/2/example/3"


def extract(html):
    return extract_markdown(html, URL, metadata={}, asset_profile="none")


def test_toolbar_removed_before_nested_list_rendering_and_prose_retained():
    result = extract("""<article>
      <div class="toolbar-wrap"><ul id="Toolbar"><li>PDF</li>
      <li>Cite<div id="getCitation"><p>Citation popup</p></div></li></ul></div>
      <div class="js-citation-modal">Detached citation popup</div>
      <ul id="ShareDrop"><li>Share popup</li></ul>
      <h2>Results</h2><p>Share PDF results and Cite evidence.</p>
      </article>""")
    assert result.markdown_text == "## Results\n\nShare PDF results and Cite evidence."


def test_comments_ignored_in_containers_blocks_and_inline_nodes():
    soup = BeautifulSoup(
        """<article><!-- container-template -->
        <p>Before <!-- block-template --><span>and <!-- inline-template -->after</span>.</p>
        </article>""",
        "lxml",
    )
    lines = []
    render_container_markdown(soup.article, lines, level=2)
    assert "\n".join(lines).strip() == "Before and after."
    assert render_clean_text_from_html(Comment("template")) == ""
    assert render_html_inline_node(Comment("template")) == ""


def test_supplementary_links_resolve_relative_urls_without_downloading():
    result = extract("""<article><p>Body</p></article>
      <div class="dataSuppLink"><a href="../suppl_file/data.docx">Supplementary data</a> - docx file</div>
      <div class="dataSuppLink"><a href="../suppl_file/data.docx">Supplementary data</a> - docx file</div>""")
    assert (
        result.markdown_text.count(
            "[Supplementary data](https://academic.oup.com/journal/article/1/2/suppl_file/data.docx)"
        )
        == 1
    )
    assert result.extracted_assets == []


def test_download_slide_control_retains_original_image_asset_only():
    original = "https://oup.silverchair-cdn.com/journal/paperf1.jpeg"
    result = extract_markdown(
        f'<article><h2>Results</h2><figure id="f1">'
        '<img src="https://oup.silverchair-cdn.com/journal/m_paperf1.jpeg">'
        "<figcaption>Figure 1. Source caption.</figcaption>"
        f'<a href="/DownloadFile/DownloadImage.aspx?image={original}">Download slide</a>'
        "</figure></article>",
        URL,
        metadata={},
        asset_profile="all",
    )
    assert len(result.extracted_assets) == 1
    asset = result.extracted_assets[0]
    assert (asset.get("full_size_url") or asset["url"]) == original
    assert "Download slide" not in result.markdown_text


def test_structured_abstract_preserves_inline_format_language_and_paragraphs():
    html = r"""<article><section class="abstract" lang="en"><h2>Abstract</h2>
      <p>CO<sub>2</sub> and m<sup>2</sup>, <span class="inline-formula">|$x_i$|</span>.</p>
      <p>Second paragraph.</p><p>Second paragraph.</p></section>
      <h2>Results</h2><p>Body text.</p></article>"""
    result = extract(html)
    block = result.abstract_sections[0]
    assert block["language"] == "en" and block["order"] == 0
    assert block["source_selector"]
    assert (
        block["text"] == "CO<sub>2</sub> and m<sup>2</sup>, $x_i$.\n\nSecond paragraph."
    )
    article = build_oxford_html_article(html, URL)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="none", max_tokens="full_text"
    )
    assert block["text"] in markdown
    assert markdown.count("CO<sub>2</sub>") == 1


@pytest.mark.parametrize("inside_card", [False, True])
def test_author_footnotes_use_explicit_target_ids(inside_card):
    note = '<div class="footnote" content-id="afn1"><div class="footnote-content">Equal contribution.</div></div>'
    html = f"""<article><div class="info-card-author">
      <div class="info-card-name">Ada One<span class="info-card-footnote"><a data-open="afn1">*</a></span></div>
      {note if inside_card else ""}</div>
      <div class="info-card-author"><div class="info-card-name">Bo Two<span class="info-card-footnote"><a href="#afn1">*</a></span></div></div>
      {"" if inside_card else note}
      <div class="footnote" content-id="afn2"><div class="footnote-content">Unlinked note.</div></div>
      <p>Body</p></article>"""
    markdown = extract(html).markdown_text
    assert markdown.count("Ada One, Bo Two: Equal contribution.") == 1
    assert "Unlinked note." in markdown
    assert "Two: Unlinked" not in markdown


def test_reference_dois_repaired_only_from_links_and_distinct_dois_survive():
    result = extract("""<article><div class="ref-list"><div class="ref">
      <span class="label">1.</span><div class="mixed-citation">
      Author. Title. 2023; 50, doi: 10. 1029/2023ABC.
      <a href="https://doi.org/10.1029/2023ABC">10.1029/2023ABC</a>
      Other <a href="https://doi.org/10.1029/2023ABC2">10.1029/2023ABC2</a>.
      Unlinked 10. 1234/example.</div></div></div></article>""")
    reference = result.metadata["references"][0]
    assert reference["label"] == "1."
    assert reference["raw"].count("10.1029/2023ABC") == 2  # two distinct DOIs
    assert "10.1029/2023ABC2" in reference["raw"]
    assert "10. 1234/example" in reference["raw"]
    assert "10. 1029" not in reference["raw"]


def test_figure_caption_dedup_is_local_and_keeps_labels_and_subcaptions():
    soup = BeautifulSoup(
        """<article><figure><figcaption>Figure 1. Same caption.</figcaption>
      <div class="caption">Same caption.</div><div class="fig-caption">Figure 2. Same caption.</div>
      <div class="caption">(a) Subpanel text.</div></figure>
      <figure><figcaption>Figure 3. Same caption.</figcaption></figure></article>""",
        "lxml",
    )
    lines = []
    for figure in soup.find_all("figure"):
        render_figure_markdown(figure, lines)
    markdown = "\n".join(lines)
    assert markdown.count("Same caption.") == 3
    for number in (1, 2, 3):
        assert f"**Figure {number}.** Same caption." in markdown
    assert "(a) Subpanel text." in markdown


@pytest.mark.parametrize("operator", [r"\sum", r"\prod", r"\int", r"\bigcup"])
def test_source_mathop_is_preserved_and_normalization_is_idempotent(operator):
    raw = rf"\mathop \mathop {operator} \limits_{{i=1}}^n x_i"
    normalized = normalize_latex(raw)
    assert normalized == raw
    assert normalize_latex(normalized) == normalized
    custom = r"\mathop{\mathrm{arg\,max}}_{x} f(x)"
    assert normalize_latex(custom) == custom


def test_tex_wrappers_and_equation_environment_preserve_mathematical_pipes():
    assert (
        normalize_tex_formula_text(r"|$|x| + \left|y\right|$|⁠")
        == r"$|x| + \left|y\right|$"
    )
    soup = BeautifulSoup(
        r"""<div class="disp-formula"><div class="mathjax-tex">
      $$\begin{equation}\mathop \sum_{i=1}^n |x_i|\end{equation}$$
      </div></div>""",
        "lxml",
    )
    result = render_html_formula_container(soup.div)
    assert (
        result
        == "\n\n$$\n"
        + r"\begin{equation}\mathop \sum_{i=1}^n |x_i|\end{equation}"
        + "\n$$\n\n"
    )
