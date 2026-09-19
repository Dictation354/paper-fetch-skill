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
