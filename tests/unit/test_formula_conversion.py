from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path

from paper_fetch.formula import convert as formula_conversion


class FormulaConversionTests(unittest.TestCase):
    def tearDown(self) -> None:
        formula_conversion.clear_conversion_cache()

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

    def test_conversion_cache_reuses_result_for_same_backend_payload_and_config(self) -> None:
        raw_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        calls = 0
        original_texmath = formula_conversion.convert_with_texmath
        try:
            def fake_texmath(*args, **kwargs):
                nonlocal calls
                calls += 1
                return formula_conversion.FormulaConversionResult(
                    backend="texmath",
                    status="ok",
                    latex="x",
                    raw_mathml=raw_mathml,
                    error=None,
                    duration_ms=7,
                    display_mode=False,
                )

            formula_conversion.convert_with_texmath = fake_texmath

            first = formula_conversion.convert_mathml_string(raw_mathml, display_mode=False, env={}, backend="texmath")
            second = formula_conversion.convert_mathml_string(raw_mathml, display_mode=False, env={}, backend="texmath")
        finally:
            formula_conversion.convert_with_texmath = original_texmath

        self.assertEqual(calls, 1)
        self.assertEqual(first.latex, "x")
        self.assertEqual(second.latex, "x")
        self.assertEqual(second.duration_ms, 0)

    def test_formula_timing_collector_records_uncached_and_cache_hit_calls(self) -> None:
        raw_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        durations: list[float] = []
        original_texmath = formula_conversion.convert_with_texmath
        original_monotonic = formula_conversion.time.monotonic
        monotonic_values = iter([10.0, 10.125, 20.0, 20.05])
        try:
            formula_conversion.time.monotonic = lambda: next(monotonic_values)

            def fake_texmath(*args, **kwargs):
                return formula_conversion.FormulaConversionResult(
                    backend="texmath",
                    status="ok",
                    latex="x",
                    raw_mathml=raw_mathml,
                    error=None,
                    duration_ms=7,
                    display_mode=False,
                )

            formula_conversion.convert_with_texmath = fake_texmath

            with formula_conversion.formula_timing_collector(durations.append):
                first = formula_conversion.convert_mathml_string(
                    raw_mathml,
                    display_mode=False,
                    env={},
                    backend="texmath",
                )
                second = formula_conversion.convert_mathml_string(
                    raw_mathml,
                    display_mode=False,
                    env={},
                    backend="texmath",
                )
        finally:
            formula_conversion.convert_with_texmath = original_texmath
            formula_conversion.time.monotonic = original_monotonic

        self.assertEqual(first.status, "ok")
        self.assertEqual(second.status, "ok")
        self.assertEqual(second.duration_ms, 0)
        self.assertEqual([round(duration, 3) for duration in durations], [0.125, 0.05])

    def test_mathml_to_latex_worker_success_avoids_cli_process(self) -> None:
        raw_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        original_command = formula_conversion._resolve_mathml_to_latex_command
        original_worker_command = formula_conversion._resolve_mathml_to_latex_worker_command
        original_worker_for = formula_conversion._mathml_worker_for
        original_run_command = formula_conversion._run_command

        class FakeWorker:
            def convert(self, _raw_mathml, *, timeout_seconds):
                return "x"

        try:
            formula_conversion._resolve_mathml_to_latex_command = lambda _env: ("node", "/tmp/cli.mjs", None, None)
            formula_conversion._resolve_mathml_to_latex_worker_command = lambda _env: ("node", "/tmp/worker.mjs", None, None)
            formula_conversion._mathml_worker_for = lambda **_kwargs: FakeWorker()
            formula_conversion._run_command = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("CLI fallback should not run"))

            result = formula_conversion.convert_with_mathml_to_latex(raw_mathml, display_mode=False, env={})
        finally:
            formula_conversion._resolve_mathml_to_latex_command = original_command
            formula_conversion._resolve_mathml_to_latex_worker_command = original_worker_command
            formula_conversion._mathml_worker_for = original_worker_for
            formula_conversion._run_command = original_run_command

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.latex, "x")

    def test_mathml_to_latex_worker_failure_falls_back_to_cli(self) -> None:
        raw_mathml = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        original_command = formula_conversion._resolve_mathml_to_latex_command
        original_worker_command = formula_conversion._resolve_mathml_to_latex_worker_command
        original_worker_for = formula_conversion._mathml_worker_for
        original_run_command = formula_conversion._run_command

        class FailingWorker:
            def convert(self, _raw_mathml, *, timeout_seconds):
                raise RuntimeError("worker crashed")

        try:
            formula_conversion._resolve_mathml_to_latex_command = lambda _env: ("node", "/tmp/cli.mjs", None, None)
            formula_conversion._resolve_mathml_to_latex_worker_command = lambda _env: ("node", "/tmp/worker.mjs", None, None)
            formula_conversion._mathml_worker_for = lambda **_kwargs: FailingWorker()
            formula_conversion._run_command = lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "x", "")

            result = formula_conversion.convert_with_mathml_to_latex(raw_mathml, display_mode=False, env={})
        finally:
            formula_conversion._resolve_mathml_to_latex_command = original_command
            formula_conversion._resolve_mathml_to_latex_worker_command = original_worker_command
            formula_conversion._mathml_worker_for = original_worker_for
            formula_conversion._run_command = original_run_command

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
