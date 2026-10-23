"""Same-node selection contracts with mocked validator/converter boundaries."""

from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
import pytest

from paper_fetch.formula import convert
from paper_fetch.formula.validation import (
    TexValidation,
    TexValidationSession,
    conversion_mathml,
    formula_validation_session,
    select_formula_latex,
    capture_formula_diagnostics,
)
from paper_fetch.extraction.html.formula_rules import mathml_element_from_html_node


def test_valid_source_tex_is_verbatim_and_never_converted(monkeypatch):
    source = "x  + y % keep spaces  \n+ z"
    monkeypatch.setattr(
        convert,
        "convert_mathml_element_to_latex",
        lambda *a, **k: pytest.fail("unexpected conversion"),
    )
    selected = select_formula_latex(
        source, ET.fromstring("<math><mi>x</mi></math>"), display_mode=False
    )
    assert selected.final_latex == source
    assert selected.valid and not selected.backend


def test_failed_source_uses_sanitized_copy_and_validates_each_backend(monkeypatch):
    original = ET.fromstring(
        r'<math alttext="\sc X"><semantics><mi mathvariant="small-caps">X</mi><annotation encoding="application/x-tex">\sc X</annotation></semantics></math>'
    )
    raw = ET.tostring(original)
    calls = []

    def backend(mathml, *, backend, display_mode):
        calls.append(backend)
        assert not any(n.tag == "annotation" or n.get("alttext") for n in mathml.iter())
        latex = r"\bad" if backend == "texmath" else "X"
        return convert.FormulaConversionResult(
            backend, "ok", latex, "", None, 0, display_mode
        )

    monkeypatch.delenv("MATHML_CONVERTER_BACKEND", raising=False)
    monkeypatch.setattr(convert, "convert_mathml_element_to_latex", backend)
    monkeypatch.setattr(
        TexValidationSession,
        "validate",
        lambda self, tex, display: TexValidation(
            tex == "X", None if tex == "X" else "bad TeX"
        ),
    )
    with formula_validation_session() as session:
        result = select_formula_latex(
            r"\sc X", original, display_mode=False, node_id="eq1"
        )
        assert result.valid and result.final_latex == "X"
        assert result.backend == "mathml-to-latex"
        assert result.style_degradations[0] == "small-caps"
        assert result.node_id == "eq1"
        assert len(result.validation_errors) == 2
        assert (
            select_formula_latex(r"\sc X", original, display_mode=False, node_id="eq1")
            is result
        )
        assert len(session.selections) == 1
        from paper_fetch.models import SemanticLosses

        losses = SemanticLosses()
        capture_formula_diagnostics(losses, count_fallbacks=True)
        capture_formula_diagnostics(losses, count_fallbacks=True)
        assert losses.formula_fallback_count == 1
    assert calls == ["texmath", "mathml-to-latex"]
    assert ET.tostring(original) == raw
    assert not conversion_mathml(original).get("alttext")


@pytest.mark.parametrize("mathml", [None, ET.fromstring("<math><mi>x</mi></math>")])
def test_all_failed_or_unavailable_preserves_original(monkeypatch, mathml):
    monkeypatch.setattr(
        TexValidationSession, "validate", lambda *a: TexValidation(False, "bad TeX")
    )
    monkeypatch.setattr(
        convert,
        "convert_mathml_element_to_latex",
        lambda *a, **k: convert.FormulaConversionResult(
            k["backend"], "ok", r"\bad", "", None, 0, False
        ),
    )
    result = select_formula_latex(r"\broken{", mathml, display_mode=False)
    assert result.final_latex == r"\broken{"
    assert not result.valid and result.validation_errors
    monkeypatch.setattr(
        TexValidationSession,
        "validate",
        lambda *a: TexValidation(False, "unavailable", available=False),
    )
    monkeypatch.setattr(
        convert,
        "convert_mathml_element_to_latex",
        lambda *a, **k: pytest.fail("cannot validate fallback"),
    )
    result = select_formula_latex(r"\broken{", mathml, display_mode=False)
    assert result.final_latex == r"\broken{"
    assert result.validation_errors == ["unavailable"]


@pytest.mark.parametrize(
    "payload",
    [
        "<math><mi>x</mi></math><math><mi>y</mi></math>",
        '<math><mi>x</mi></math><script type="math/mml"><math><mi>y</mi></math></script>',
    ],
)
def test_html_ambiguous_mathml_is_not_paired(payload):
    node = BeautifulSoup(
        f'<span class="inline-formula">{payload}</span>', "html.parser"
    ).span
    assert mathml_element_from_html_node(node) is None
