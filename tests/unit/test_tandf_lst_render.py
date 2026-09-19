"""Local formula classification and hidden MathML contracts."""

from bs4 import BeautifulSoup
import pytest
from paper_fetch.extraction.html.formula_rules import (
    display_formula_nodes,
    is_display_formula_node,
    is_formula_container,
)
from paper_fetch.models import SemanticLosses
from paper_fetch.providers import _tandf_html
from paper_fetch.providers.atypon_browser_workflow.formulas import (
    _normalize_display_formula_blocks,
    _normalize_inline_math_nodes,
)


@pytest.mark.parametrize(
    "html,display",
    [
        ('<span class="NLM_disp-formula"><math><mi>x</mi></math></span>', False),
        (
            '<div class="disp-formula"><span class="inline-equation"><math><mi>x</mi></math></span></div>',
            False,
        ),
        (
            '<div class="disp-formula"><math display="inline"><mi>x</mi></math></div>',
            False,
        ),
        ('<span class="display-equation"><math><mi>x</mi></math></span>', True),
        ('<span class="hidden"><math display="block"><mi>x</mi></math></span>', True),
        (
            '<span aria-hidden="true"><math display="inline"><mi>x</mi></math></span>',
            False,
        ),
    ],
)
def test_shared_nearest_formula_classification(html, display):
    soup = BeautifulSoup(html, "lxml")
    assert is_display_formula_node(soup.math) is display


@pytest.mark.parametrize(
    "html",
    [
        '<span class="ref-lnk disp-formula"><a data-label="equation">Eq. (3)</a></span>',
        '<a class="display-equation" href="#eq3">Eq. (3)</a>',
        '<xref class="disp-formula" ref-type="disp-formula" rid="eq3">Eq. (3)</xref>',
    ],
)
def test_shared_formula_references_are_prose(html):
    soup = BeautifulSoup(f"<div>{html}</div>", "lxml")
    assert not display_formula_nodes(soup.div)
    assert not is_formula_container(soup.div.contents[0])
    losses = SemanticLosses()
    _normalize_display_formula_blocks(soup.div, losses)
    _normalize_inline_math_nodes(soup.div, losses)
    assert soup.div.get_text() == "Eq. (3)"
    assert losses == SemanticLosses()


def test_tandf_preserves_unique_hidden_math():
    soup = BeautifulSoup(
        '<div><span class="hidden" id="unique"><math><mi>x</mi></math></span><span class="hidden" id="M1"><math><mi>y</mi></math></span></div>',
        "lxml",
    )
    _tandf_html.tandf_before_block_normalization(soup.div)
    assert len(soup.find_all("math")) == 2
