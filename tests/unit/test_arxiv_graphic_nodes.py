"""Minimal LaTeXML node and title boundaries; not publisher content evidence."""

import base64
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from paper_fetch.providers._arxiv_authors import _clean_official_html_latexml_noise
from paper_fetch.providers._arxiv_graphics import (
    INLINE_SVG_PREFIX,
    prepare_arxiv_graphics,
)
from paper_fetch.providers._arxiv_metadata import _extract_arxiv_html_frontmatter
from paper_fetch.providers._arxiv_references import _render_arxiv_table_cell


def test_graphic_nodes_keep_identity_and_source_relative_repeated_positions():
    soup = BeautifulSoup(
        """<article><section><figure id="F1"><object id="F1.g1" data="v/images/a.svg" type="image/svg+xml"></object><img src="v/images/b.png"></figure><figure id="F2"><img src="v/images/b.png"></figure><object id="F3" data="document.html"></object></section></article>""",
        "lxml",
    )
    prepare_arxiv_graphics(soup.article, "https://arxiv.org/html/v")
    assert soup.find(id="F1.g1")["src"] == "https://arxiv.org/html/v/images/a.svg"
    assert len(soup.select('img[src="https://arxiv.org/html/v/images/b.png"]')) == 2
    assert soup.find(id="F3").name == "object"


def test_inline_svg_preserves_vector_foreignobject_mathml_and_excludes_inline_glyphs():
    soup = BeautifulSoup(
        """<article><section><svg class="ltx_picture" id="glyph"></svg><figure><svg class="ltx_picture" id="F1.pic1" viewBox="0 0 30 20"><path d="M 1 2 L 3 4"/><foreignObject><span><math><mi>x</mi></math></span></foreignObject></svg></figure></section></article>""",
        "lxml",
    )
    prepare_arxiv_graphics(soup.article, "https://arxiv.org/html/v")
    assert soup.find(id="glyph").name == "svg"
    image = soup.find(id="F1.pic1")
    root = ET.fromstring(base64.b64decode(image["src"][len(INLINE_SVG_PREFIX) :]))
    assert root.attrib["viewBox"] == "0 0 30 20"
    assert root.find("{http://www.w3.org/2000/svg}path").attrib["d"] == "M 1 2 L 3 4"
    assert root.find(".//{http://www.w3.org/1999/xhtml}span") is not None
    assert root.find(".//{http://www.w3.org/1998/Math/MathML}mi").text == "x"


def test_title_excludes_pubnotes_and_only_empty_frontmatter_table_is_removed():
    soup = BeautifulSoup(
        """<article class="ltx_document"><h1 class="ltx_title_document">Actual title<span class="ltx_pubnotes">Thanks to A</span></h1><table id="empty" class="ltx_tabular"><tr><td><span class="ltx_rule"></span></td></tr></table><table id="meaningful" class="ltx_tabular"><tr><td>Information</td></tr></table><section><table id="body" class="ltx_tabular"><tr><td></td></tr></table></section></article>""",
        "lxml",
    )
    front = _extract_arxiv_html_frontmatter(
        soup, soup.article, "https://arxiv.org/html/v", metadata={}
    )
    assert front["title"] == "Actual title"
    _clean_official_html_latexml_noise(soup.article)
    assert soup.find(id="empty") is None
    assert soup.find(id="meaningful") is not None
    assert soup.find(id="body") is not None


def test_table_cell_retains_annotated_image_and_neighbor_text():
    soup = BeautifulSoup(
        '<td>Panel A<img src="old.svg" data-paper-fetch-inline-src="https://arxiv.org/a.svg" data-paper-fetch-inline-alt="Figure 1.a">after</td>',
        "html.parser",
    )
    rendered = _render_arxiv_table_cell(soup.td)
    assert "https://arxiv.org/a.svg" in rendered
    assert "old.svg" not in rendered
    assert "Panel A" in rendered and "after" in rendered
