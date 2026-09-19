"""Minimal T&F paired formula ownership and source fallback contracts."""

import html
import json

from bs4 import BeautifulSoup
import pytest

from paper_fetch.models import SemanticLosses
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers import _tandf_html as tandf
from paper_fetch.providers.atypon_browser_workflow.normalization import (
    _normalize_special_blocks,
)

SOURCE = "https://www.tandfonline.com/doi/full/10.1080/example"
IMAGE = "/cms/asset/source/equation.gif?token=kept"
CHTML = "<mjx-container><mjx-math><mjx-mi>unreliable glyph order</mjx-mi></mjx-math></mjx-container>"


def _pair(content=CHTML, *, display=True, data=None):
    data = json.dumps({"type": "image", "src": IMAGE}) if data is None else data
    kind = "disp-formula" if display else "inline-formula"
    label = '<span class="disp_formula_label_div">(7)</span>' if display else ""
    return f"""<span class="NLM_disp-formula-image {kind}"><img src="//:0" data-formula-source='{html.escape(data, quote=True)}'></span><span class="NLM_disp-formula {kind}">{label}<img src="//:0" data-formula-source='{{"type":"mathjax"}}'>{content}</span>"""


def _render(fragment):
    soup = BeautifulSoup(f"<article>{fragment}</article>", "lxml")
    tandf.prepare_source_images(soup.article, SOURCE)
    losses = SemanticLosses()
    _normalize_special_blocks(soup.article, "tandf", losses)
    return soup.article.get_text(" ", strip=True), losses


@pytest.mark.parametrize("display", [False, True])
@pytest.mark.parametrize(
    "content", ["<math><mi>x</mi></math>", '<script type="math/tex">x^{2}</script>']
)
def test_real_mathml_or_tex_wins_over_paired_bitmap(content, display):
    text, losses = _render(_pair(content, display=display))
    assert "$" in text and "x" in text
    assert "![Formula]" not in text and "//:0" not in text
    assert losses.formula_fallback_count == losses.formula_missing_count == 0
    if display:
        assert "Equation 7." in text


@pytest.mark.parametrize("display", [False, True])
def test_paired_bitmap_uses_official_absolute_source_once_and_keeps_reuse(display):
    text, losses = _render(
        "Before "
        + _pair(display=display)
        + " Between "
        + _pair(display=display)
        + " After"
    )
    expected = "https://www.tandfonline.com" + IMAGE
    assert [i.url for i in iter_markdown_images(text)] == [expected, expected]
    assert (
        text.index("Before")
        < text.index(expected)
        < text.index("Between")
        < text.rindex(expected)
        < text.index("After")
    )
    assert losses.formula_fallback_count == 2 and losses.formula_missing_count == 0
    assert "unreliable" not in text and "//:0" not in text


@pytest.mark.parametrize(
    "data",
    [
        "{broken",
        "[]",
        '{"type":"image","src":"//:0"}',
        '{"type":"image","src":"https://unrelated.example/equation.gif"}',
        '{"type":"image"}',
    ],
)
@pytest.mark.parametrize("display", [False, True])
def test_unavailable_paired_formula_is_reported_missing(data, display):
    text, losses = _render(_pair(display=display, data=data))
    assert text.count("[Formula unavailable]") == 1
    assert losses.formula_missing_count == 1 and losses.formula_fallback_count == 0
    assert "unreliable" not in text and "//:0" not in text


@pytest.mark.parametrize(
    "content", [CHTML, '<img src="//:0" data-formula-source="{}">']
)
def test_standalone_chtml_does_not_masquerade_as_source_formula(content):
    text, losses = _render(
        f'<span class="NLM_disp-formula inline-formula">{content}</span>'
    )
    assert text == "[Formula unavailable]"
    assert losses.formula_missing_count == 1


def test_formula_pairing_cannot_cross_intervening_prose():
    fragment = _pair(display=False).replace(
        '</span><span class="NLM_disp-formula ',
        '</span> Unrelated intervening prose. <span class="NLM_disp-formula ',
        1,
    )
    text, losses = _render(fragment)
    assert len(list(iter_markdown_images(text))) == 1
    assert text.count("[Formula unavailable]") == 1
    assert (
        text.index("equation.gif")
        < text.index("Unrelated")
        < text.index("[Formula unavailable]")
    )
    assert losses.formula_fallback_count == losses.formula_missing_count == 1


def test_asset_hook_recovers_source_and_prepare_is_idempotent_and_scoped():
    soup = BeautifulSoup(
        f'<article>{_pair()}<img src="//:0" data-formula-source=\'{{"type":"image","src":"/unrelated.gif"}}\'></article>',
        "lxml",
    )
    tandf.prepare_source_images(soup.article, SOURCE)
    original = str(soup.article)
    tandf.prepare_source_images(soup.article, "")
    assert str(soup.article) == original
    tandf.tandf_asset_body_container(soup.article)
    assert [i["src"] for i in soup.select("img")] == [
        "https://www.tandfonline.com" + IMAGE,
        "//:0",
    ]
    raw = BeautifulSoup(f"<article>{_pair()}</article>", "lxml")
    tandf.tandf_asset_body_container(raw.article)
    assert raw.select_one("img")["src"] == IMAGE


@pytest.mark.parametrize("content", ["<math><mi>x</mi></math>", CHTML])
def test_standalone_placeholder_is_consumed_before_repeated_normalization(content):
    soup = BeautifulSoup(
        '<article><span class="NLM_disp-formula inline-formula">'
        '<img src="//:0" data-formula-source=\'{"type":"mathjax"}\'>'
        f"{content}</span></article>",
        "lxml",
    )
    tandf.prepare_source_images(soup.article, SOURCE)
    losses = SemanticLosses()
    _normalize_special_blocks(soup.article, "tandf", losses)
    before = str(soup.article)
    missing_before = losses.formula_missing_count
    _normalize_special_blocks(soup.article, "tandf", losses)
    assert str(soup.article) == before
    assert losses.formula_missing_count == missing_before
