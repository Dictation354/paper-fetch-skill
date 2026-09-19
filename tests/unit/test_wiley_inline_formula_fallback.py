"""Wiley pairs each MathJax expression with its adjacent fallback image."""

from bs4 import BeautifulSoup
import pytest

from paper_fetch.models import SemanticLosses
from paper_fetch.providers._wiley_html import (
    extract_formula_assets,
    prepare_source_images,
)
from paper_fetch.providers.atypon_browser_workflow.formulas import (
    _normalize_inline_math_nodes,
)

SOURCE = "https://onlinelibrary.wiley.com/doi/full/10.1111/example"


@pytest.mark.parametrize("rendered", [False, True])
def test_wiley_asset_extraction_prefers_each_adjacent_official_formula_url(rendered):
    def expression(number):
        math = f'<math location="graphic/example-math-{number}.png"><mi>x</mi></math>'
        if rendered:
            math = f"<mjx-container><mjx-assistive-mml>{math}</mjx-assistive-mml></mjx-container>"
        return (
            '<span class="fallback__mathEquation" '
            f'data-altimg="/cms/asset/{number}/example-math-{number}.png"></span>'
            + math
        )

    assets = extract_formula_assets(
        f"<p>Before {expression(1)} between {expression(2)} after.</p>", SOURCE
    )
    assert [asset["url"] for asset in assets] == [
        f"https://onlinelibrary.wiley.com/cms/asset/{number}/example-math-{number}.png"
        for number in (1, 2)
    ]


def test_native_math_keeps_structured_content_after_image_preparation():
    soup = BeautifulSoup(
        '<p><span class="fallback__mathEquation" '
        'data-altimg="/cms/asset/example-math-0001.png"></span>'
        '<math location="graphic/example-math-0001.png"><mi>x</mi></math></p>',
        "html.parser",
    )
    prepare_source_images(soup, SOURCE)
    assert soup.math["data-altimg"] == (
        "https://onlinelibrary.wiley.com/cms/asset/example-math-0001.png"
    )
    losses = SemanticLosses()
    _normalize_inline_math_nodes(soup, losses)
    assert soup.get_text() == "$x$"
    assert losses.formula_fallback_count == losses.formula_missing_count == 0


def test_native_math_does_not_bind_a_different_formula_basename():
    soup = BeautifulSoup(
        '<p><span class="fallback__mathEquation" '
        'data-altimg="/cms/asset/other-math-0001.png"></span>'
        '<math location="graphic/example-math-0002.png"><mi>x</mi></math></p>',
        "html.parser",
    )
    prepare_source_images(soup, SOURCE)
    assert not soup.math.has_attr("data-altimg")


def test_adjacent_wiley_images_bind_to_their_own_inline_math():
    soup = BeautifulSoup(
        '<p>Before <span class="fallback__mathEquation" '
        'data-altimg="/cms/asset/first-math-0001.png"></span> '
        "<mjx-container><mjx-assistive-mml><math></math>"
        "</mjx-assistive-mml></mjx-container> between "
        '<span class="fallback__mathEquation" '
        'data-altimg="/cms/asset/second-math-0002.png"></span>'
        "<mjx-container><mjx-assistive-mml><math></math>"
        "</mjx-assistive-mml></mjx-container> after.</p>",
        "html.parser",
    )
    prepare_source_images(soup, SOURCE)
    losses = SemanticLosses()
    _normalize_inline_math_nodes(soup, losses)
    text = soup.get_text()
    first = "https://onlinelibrary.wiley.com/cms/asset/first-math-0001.png"
    second = "https://onlinelibrary.wiley.com/cms/asset/second-math-0002.png"
    assert text.index("Before") < text.index(first) < text.index("between")
    assert text.index("between") < text.index(second) < text.index("after.")
    assert losses.formula_fallback_count == 2
    assert losses.formula_missing_count == 0


def test_wiley_image_pair_keeps_structured_math_preferred():
    soup = BeautifulSoup(
        '<p><span class="fallback__mathEquation" '
        'data-altimg="/cms/asset/example-math-0001.png"></span>'
        "<mjx-container><mjx-assistive-mml><math><mi>x</mi></math>"
        "</mjx-assistive-mml></mjx-container></p>",
        "html.parser",
    )
    prepare_source_images(soup, SOURCE)
    losses = SemanticLosses()
    _normalize_inline_math_nodes(soup, losses)
    assert soup.get_text() == "$x$"
    assert losses.formula_fallback_count == 0


def test_wiley_fallback_does_not_cross_prose_or_an_unrelated_wrapper():
    soup = BeautifulSoup(
        '<p><span class="fallback__mathEquation" '
        'data-altimg="/cms/asset/other-math-0001.png"></span> unrelated '
        "<mjx-container><math></math></mjx-container>"
        '<span class="fallback__mathEquation" '
        'data-altimg="/cms/asset/other-math-0002.png"></span>'
        "<span>Another item</span><mjx-container><math></math></mjx-container></p>",
        "html.parser",
    )
    prepare_source_images(soup, SOURCE)
    losses = SemanticLosses()
    _normalize_inline_math_nodes(soup, losses)
    assert soup.get_text().count("[Formula unavailable]") == 2
    assert losses.formula_missing_count == 2
