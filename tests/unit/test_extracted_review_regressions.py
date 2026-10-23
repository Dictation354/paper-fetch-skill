"""Minimal source fragments for defects found in the 2026-10-21 review."""

from bs4 import BeautifulSoup

from paper_fetch.extraction.markdown_render.table_format import (
    escape_markdown_table_cell,
)
from paper_fetch.providers._atypon_browser_workflow_postprocess import (
    normalize_equation_markdown_blocks,
)
from paper_fetch.providers._html_section_markdown import render_container_markdown
from paper_fetch.providers._ieee_html import _annotate_ieee_inline_media_blocks
from paper_fetch.providers._springer_dom import _normalized_root_html
from paper_fetch.providers.atypon_browser_workflow.normalization import (
    _normalize_special_blocks,
)


def test_browser_list_item_keeps_already_rendered_formula_link_and_scripts():
    soup = BeautifulSoup(
        r"""<article><ul><li>Uncertainty
    <span class="inline-eqn"><script type="math/tex">1 \cdot 10^{-8}</script></span>
    in section <a href="#s1">1</a>, m s<sup>−1</sup>.</li></ul></article>""",
        "html.parser",
    )
    _normalize_special_blocks(soup.article, "iop")
    lines = []
    render_container_markdown(soup.article, lines, level=2)
    markdown = "\n".join(lines)
    assert r"$1 \cdot 10^{-8}$" in markdown
    assert "[1](#s1)" in markdown
    assert "s<sup>−1</sup>" in markdown
    assert r"\$" not in markdown


def test_ieee_literal_tex_caption_is_marked_before_character_data_escaping():
    soup = BeautifulSoup(
        r"""<article><div class="figure figure-full">
    <img src="https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/1/1/example.t1-large.gif"/>
    <div class="figcaption"><b class="title">TABLE I </b>Threshold values of
    $\Gamma _{ic}$ for $M$-PSK mappings.</div></div></article>""",
        "html.parser",
    )
    _annotate_ieee_inline_media_blocks(
        soup.article, "https://ieeexplore.ieee.org/document/1"
    )
    lines = []
    render_container_markdown(soup.article, lines, level=2)
    markdown = "\n".join(lines)
    assert r"$\Gamma _{ic}$" in markdown
    assert "$M$-PSK" in markdown
    assert r"\$" not in markdown


def test_browser_postprocess_preserves_inline_fences_and_display_blocks():
    text = "Before $$\\text{for $x>1$}$$ after.\n\n$$\n\nx=1\n\n$$"
    assert normalize_equation_markdown_blocks(text) == (
        "Before $$\\text{for $x>1$}$$ after.\n\n$$\nx=1\n$$"
    )


def test_table_pipe_escaping_does_not_double_existing_tex_norm_delimiters():
    assert escape_markdown_table_cell(r"$\|x\|^2$") == r"$\|x\|^2$"
    assert escape_markdown_table_cell("A|B") == r"A\|B"
    assert escape_markdown_table_cell(r"A\|B") == r"A\|B"


def test_nature_caption_retains_css_gap_before_credit():
    _, root = _normalized_root_html("""<article><figure><figcaption>
    <p class="figure__caption"><span class="u-mr-8">Caption.</span><span>Credit: Author</span></p>
    </figcaption></figure><p><span>A</span><span>B</span></p></article>""")
    assert "Caption. Credit: Author" in root.figcaption.get_text()
    assert root.find_all("p")[-1].get_text() == "AB"
