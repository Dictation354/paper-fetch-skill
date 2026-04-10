from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "formula_conversion.py"
SPEC = importlib.util.spec_from_file_location("formula_conversion", MODULE_PATH)
formula_conversion = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = formula_conversion
SPEC.loader.exec_module(formula_conversion)


class FormulaConversionTests(unittest.TestCase):
    def test_stringify_mathml_omits_tail_text(self) -> None:
        root = ET.fromstring('<root><math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math> trailing</root>')
        math_node = list(root)[0]

        raw_mathml = formula_conversion.stringify_mathml(math_node)

        self.assertEqual(raw_mathml, '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>')

    def test_looks_like_mathml_element_excludes_tex_math(self) -> None:
        tex_math_node = ET.fromstring("<tex-math>x^2</tex-math>")
        math_node = ET.fromstring('<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>')

        self.assertFalse(formula_conversion.looks_like_mathml_element(tex_math_node))
        self.assertTrue(formula_conversion.looks_like_mathml_element(math_node))

    def test_extract_formula_samples_from_xml_strips_tail_text(self) -> None:
        xml_body = """<?xml version="1.0"?>
<article>
  <body>
    <p>Formula <math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math> trailing text.</p>
  </body>
</article>
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir) / "sample.xml"
            xml_path.write_text(xml_body, encoding="utf-8")

            samples = formula_conversion.extract_formula_samples_from_xml(xml_path)

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].raw_mathml, '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>')

    def test_default_texmath_falls_back_to_mathml_to_latex(self) -> None:
        raw_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        original_texmath = formula_conversion.convert_with_texmath
        original_mathml = formula_conversion.convert_with_mathml_to_latex
        try:
            formula_conversion.convert_with_texmath = lambda *args, **kwargs: formula_conversion.FormulaConversionResult(
                backend="texmath",
                status="failed",
                latex="",
                raw_mathml=raw_mathml,
                error="texmath missing",
                duration_ms=1,
                display_mode=False,
            )
            formula_conversion.convert_with_mathml_to_latex = lambda *args, **kwargs: formula_conversion.FormulaConversionResult(
                backend="mathml-to-latex",
                status="ok",
                latex="x",
                raw_mathml=raw_mathml,
                error=None,
                duration_ms=2,
                display_mode=False,
            )

            result = formula_conversion.convert_mathml_string(raw_mathml, display_mode=False, env={})
        finally:
            formula_conversion.convert_with_texmath = original_texmath
            formula_conversion.convert_with_mathml_to_latex = original_mathml

        self.assertEqual(result.backend, "mathml-to-latex")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.latex, "x")

    def test_explicit_texmath_does_not_hide_failure(self) -> None:
        raw_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        original_texmath = formula_conversion.convert_with_texmath
        original_mathml = formula_conversion.convert_with_mathml_to_latex
        try:
            formula_conversion.convert_with_texmath = lambda *args, **kwargs: formula_conversion.FormulaConversionResult(
                backend="texmath",
                status="failed",
                latex="",
                raw_mathml=raw_mathml,
                error="texmath missing",
                duration_ms=1,
                display_mode=False,
            )
            formula_conversion.convert_with_mathml_to_latex = lambda *args, **kwargs: formula_conversion.FormulaConversionResult(
                backend="mathml-to-latex",
                status="ok",
                latex="x",
                raw_mathml=raw_mathml,
                error=None,
                duration_ms=2,
                display_mode=False,
            )

            result = formula_conversion.convert_mathml_string(
                raw_mathml,
                display_mode=False,
                env={"MATHML_CONVERTER_BACKEND": "texmath"},
            )
        finally:
            formula_conversion.convert_with_texmath = original_texmath
            formula_conversion.convert_with_mathml_to_latex = original_mathml

        self.assertEqual(result.backend, "texmath")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error, "texmath missing")


if __name__ == "__main__":
    unittest.main()
