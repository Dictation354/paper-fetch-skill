"""Actual installed backend processes must preserve MathML structure/spacing."""

import pytest

from paper_fetch.formula.convert import convert_mathml_string
from tests.support.mathml_backends import installed_formula_env


@pytest.mark.parametrize("backend", ["texmath", "mathml-to-latex"])
def test_real_backend_preserves_merror_children_and_physical_spacing(backend):
    raw = '<math xmlns="http://www.w3.org/1998/Math/MathML"><msup><mi>x</mi><mrow><mo>(</mo><mi>t</mi><mo>+</mo><merror><mfrac><mrow><mi>k</mi><mo>-</mo><mn>1</mn></mrow><mi>K</mi></mfrac><mo>)</mo></merror></mrow></msup><mspace width="40pt"/><mi>y</mi><mspace width="-0.5em"/><mi>z</mi></math>'
    result = convert_mathml_string(
        raw, display_mode=False, env=installed_formula_env(backend), backend=backend
    )
    assert result.status == "ok", result.error
    assert result.backend == backend
    assert result.raw_mathml == raw
    assert r"\frac{k - 1}{K})" in result.latex
    assert "x^{(t +" in result.latex
    assert r"\hspace{40pt}" in result.latex
    assert r"\hspace{-0.5em}" in result.latex
    assert "7200mu" not in result.latex
    assert "PAPERFETCH" not in result.latex


@pytest.mark.parametrize("backend", ["texmath", "mathml-to-latex"])
def test_real_backend_keeps_literal_identifiers_and_trailing_word_space(backend):
    raw = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>%</mi><mo>+</mo><mi>_</mi><mo> </mo></math>'
    result = convert_mathml_string(
        raw, display_mode=False, env=installed_formula_env(backend), backend=backend
    )
    assert result.status == "ok", result.error
    assert r"\%" in result.latex and r"\_" in result.latex
    assert result.latex.endswith(r"\ {}")
    assert result.raw_mathml == raw


@pytest.mark.parametrize("backend", ["texmath", "mathml-to-latex"])
def test_real_backend_preserves_bold_numbers_and_italic_operator(backend):
    raw = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mn mathvariant="bold">1</mn><mo>+</mo><mn>10</mn><mo mathvariant="italic">exp</mo><mi>x</mi><mtext mathvariant="italic">Land ocean</mtext></math>'
    result = convert_mathml_string(
        raw, display_mode=False, env=installed_formula_env(backend), backend=backend
    )
    assert result.status == "ok", result.error
    assert r"\mathbf{1}" in result.latex and r"\mathit{exp}" in result.latex
    assert r"\textit{Land ocean}" in result.latex
    assert result.raw_mathml == raw


@pytest.mark.parametrize("backend", ["texmath", "mathml-to-latex"])
def test_real_backend_keeps_empty_fence_numeric_boundaries_and_glyphs(backend):
    raw = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi mathvariant="script">N</mi><mo>~</mo><mi>ln</mi><mfenced separators=""><mn>2</mn><mi>π</mi><mi>t</mi></mfenced><mrow><mn>0.15</mn><mo> </mo><mn>0.2</mn></mrow><mi mathvariant="normal">NDVI</mi></math>'
    result = convert_mathml_string(
        raw, display_mode=False, env=installed_formula_env(backend), backend=backend
    )
    assert result.status == "ok", result.error
    assert result.raw_mathml == raw and result.backend == backend
    assert r"\mathcal{N}" in result.latex and r"\sim" in result.latex
    assert r"\ln" in result.latex and r"\mathrm{NDVI}" in result.latex
    assert "," not in result.latex and "0.150.2" not in result.latex
    assert r"\ " in result.latex
    assert "PAPERFETCH" not in result.latex
