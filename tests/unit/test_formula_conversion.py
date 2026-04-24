from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from paper_fetch.formula import convert as formula_conversion


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

    def test_normalize_latex_repairs_identifier_escaped_underscores(self) -> None:
        normalized = formula_conversion.normalize_latex(
            r"\text{M\textbackslash\_NDVI}_{i} + \text{M\textbackslash\_VSDI}_{\text{wet},i}"
        )

        self.assertNotIn(r"textbackslash\_", normalized)
        self.assertIn(r"\text{M\_NDVI}_{i}", normalized)
        self.assertIn(r"\text{M\_VSDI}_{\text{wet},i}", normalized)

    def test_normalize_latex_does_not_globally_replace_textbackslash(self) -> None:
        normalized = formula_conversion.normalize_latex(r"\text{\textbackslash\_NDVI}")

        self.assertEqual(normalized, r"\text{\textbackslash\_NDVI}")

    def test_normalize_latex_rewrites_upgreek_macros(self) -> None:
        normalized = formula_conversion.normalize_latex(r"\updelta Q + \upDelta P + \updeltaQ")

        self.assertEqual(normalized, r"\delta Q + \Delta P + \updeltaQ")

    def test_normalize_latex_rewrites_mspace_for_katex(self) -> None:
        normalized = formula_conversion.normalize_latex(
            r"\mspace{6mu}x + \mspace{ -1.5 mu }y + \mspace{2pt}z"
        )

        self.assertEqual(normalized, r"\mkern6mu x + \mkern-1.5mu y + \mspace{2pt}z")

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
