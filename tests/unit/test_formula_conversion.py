from __future__ import annotations

import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
import subprocess
import stat
import sys
from pathlib import Path
from unittest import mock

import pytest

from paper_fetch.formula import convert as formula_conversion
from tests.golden_criteria import golden_criteria_scenario_asset


class FormulaConversionTests(unittest.TestCase):
    def tearDown(self) -> None:
        formula_conversion.clear_conversion_cache()

    def test_stringify_mathml_omits_tail_text(self) -> None:
        root = ET.fromstring(
            '<root><math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math> trailing</root>'
        )
        math_node = list(root)[0]

        raw_mathml = formula_conversion.stringify_mathml(math_node)

        self.assertEqual(
            raw_mathml,
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>',
        )

    def test_looks_like_mathml_element_excludes_tex_math(self) -> None:
        tex_math_node = ET.fromstring("<tex-math>x^2</tex-math>")
        math_node = ET.fromstring(
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )

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
        self.assertEqual(
            samples[0].raw_mathml,
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>',
        )

    def test_infer_source_provider_uses_provider_catalog(self) -> None:
        elsevier_root = ET.fromstring("<full-text-retrieval-response />")
        jats_root = ET.fromstring("<article />")
        unknown_root = ET.fromstring("<payload />")

        self.assertEqual(
            formula_conversion.infer_source_provider(
                elsevier_root,
                Path("/tmp/10.1016_example/original.xml"),
            ),
            "elsevier",
        )
        self.assertEqual(
            formula_conversion.infer_source_provider(
                jats_root,
                Path("/tmp/10.5194_acp-24-1-2024/original.xml"),
            ),
            "copernicus",
        )
        self.assertEqual(
            formula_conversion.infer_source_provider(
                jats_root,
                Path("/tmp/10.1038_example/original.xml"),
            ),
            "springer",
        )
        self.assertEqual(
            formula_conversion.infer_source_provider(
                unknown_root,
                Path("/tmp/payload.xml"),
            ),
            "unknown",
        )

    def test_normalize_latex_repairs_identifier_escaped_underscores(self) -> None:
        """rule: rule-formula-latex-normalization"""
        samples = json.loads(
            golden_criteria_scenario_asset(
                "formula_latex_normalization", "samples.json"
            ).read_text(encoding="utf-8")
        )
        sample = next(
            item for item in samples if item["name"] == "identifier_escaped_underscores"
        )

        normalized = formula_conversion.normalize_latex(sample["input"])

        for token in sample["must_not_include"]:
            self.assertNotIn(token, normalized)
        for token in sample["must_include"]:
            self.assertIn(token, normalized)

    def test_normalize_latex_scenario_samples_are_katex_compatible(self) -> None:
        """rule: rule-formula-latex-normalization"""
        samples = json.loads(
            golden_criteria_scenario_asset(
                "formula_latex_normalization", "samples.json"
            ).read_text(encoding="utf-8")
        )

        for sample in samples:
            with self.subTest(sample=sample["name"]):
                normalized = formula_conversion.normalize_latex(sample["input"])
                if "expected" in sample:
                    self.assertEqual(normalized, sample["expected"])
                for token in sample.get("must_not_include", []):
                    self.assertNotIn(token, normalized)
                for token in sample.get("must_include", []):
                    self.assertIn(token, normalized)

    def test_normalize_latex_does_not_globally_replace_textbackslash(self) -> None:
        normalized = formula_conversion.normalize_latex(r"\text{\textbackslash\_NDVI}")

        self.assertEqual(normalized, r"\text{\textbackslash\_NDVI}")

    def test_normalize_latex_rewrites_upgreek_macros(self) -> None:
        normalized = formula_conversion.normalize_latex(
            r"\updelta Q + \upDelta P + \updeltaQ"
        )

        self.assertEqual(normalized, r"\delta Q + \Delta P + \updeltaQ")

    def test_normalize_latex_rewrites_mspace_for_katex(self) -> None:
        normalized = formula_conversion.normalize_latex(
            r"\mspace{6mu}x + \mspace{ -1.5 mu }y + \mspace{2pt}z"
        )

        self.assertEqual(normalized, r"\mkern6mu x + \mkern-1.5mu y + \mspace{2pt}z")

    def test_normalize_latex_removes_only_zero_width_spacing(self) -> None:
        normalized = formula_conversion.normalize_latex(
            "S\u200bO + " + r"a\hspace{0pt}b + c\hspace*{ 0.0 em }d + e\hspace{1pt}f"
        )

        self.assertEqual(normalized, r"SO + ab + cd + e\hspace{1pt}f")

    def test_normalize_latex_removes_texmath_empty_delimiter_artifacts(self) -> None:
        normalized = formula_conversion.normalize_latex(
            r"s \left(\right. s + 1 \left.\right) + \left(\right. D + 1 \left.\right)"
        )

        self.assertEqual(normalized, "s(s + 1) + (D + 1)")

    def test_normalize_latex_compacts_split_math_identifiers(self) -> None:
        normalized = formula_conversion.normalize_latex(
            r"F_{c r i t} = \sum_{t_{p}}^{S O S_{y 0}} R_{f} + \mathcal{ℴ}"
        )

        self.assertEqual(
            normalized, r"F_{crit} = \sum\limits_{t_{p}}^{SOS_{y0}} R_{f} + \mathcal{O}"
        )

    def test_normalize_latex_rewrites_unicode_commands_for_katex(self) -> None:
        normalized = formula_conversion.normalize_latex(
            r"P(SPI \unicode{x2A7D} - 1.64) + \unicode{U+03B1}x"
        )

        self.assertEqual(normalized, "P(SPI \\leqslant - 1.64) + \u03b1x")
        self.assertNotIn(r"\unicode", normalized)

    def test_backend_registry_preserves_public_backend_groups(self) -> None:
        self.assertEqual(
            formula_conversion.SUPPORTED_BACKENDS,
            {"auto", "texmath", "mathml-to-latex", "mml2tex", "legacy"},
        )
        self.assertEqual(
            formula_conversion.BENCHMARK_BACKENDS,
            ("texmath", "mathml-to-latex", "mml2tex"),
        )
        self.assertEqual(
            formula_conversion.AUTO_BACKENDS, ("texmath", "mathml-to-latex")
        )

    def test_backend_registry_resolves_aliases_and_legacy_strategy(self) -> None:
        self.assertEqual(
            formula_conversion.resolve_backend(backend="mathml_to_latex"),
            "mathml-to-latex",
        )
        with self.assertRaisesRegex(RuntimeError, "Legacy conversion is not available"):
            formula_conversion.convert_mathml_string(
                '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>',
                display_mode=False,
                env={},
                backend="legacy",
            )

    def test_auto_backend_uses_registry_order_without_texmath_default_fallback(
        self,
    ) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        calls: list[str] = []
        original_texmath = formula_conversion.convert_with_texmath
        original_mathml = formula_conversion.convert_with_mathml_to_latex
        try:
            formula_conversion.convert_with_texmath = lambda *args, **kwargs: (
                calls.append("texmath")
                or formula_conversion.FormulaConversionResult(
                    backend="texmath",
                    status="failed",
                    latex="",
                    raw_mathml=raw_mathml,
                    error="texmath missing",
                    duration_ms=1,
                    display_mode=False,
                )
            )
            formula_conversion.convert_with_mathml_to_latex = lambda *args, **kwargs: (
                calls.append("mathml-to-latex")
                or formula_conversion.FormulaConversionResult(
                    backend="mathml-to-latex",
                    status="ok",
                    latex="x",
                    raw_mathml=raw_mathml,
                    error=None,
                    duration_ms=2,
                    display_mode=False,
                )
            )

            result = formula_conversion.convert_mathml_string(
                raw_mathml,
                display_mode=False,
                env={},
                backend="auto",
            )
        finally:
            formula_conversion.convert_with_texmath = original_texmath
            formula_conversion.convert_with_mathml_to_latex = original_mathml

        self.assertEqual(calls, ["texmath", "mathml-to-latex"])
        self.assertEqual(result.backend, "mathml-to-latex")
        self.assertEqual(result.status, "ok")

    def test_default_texmath_falls_back_to_mathml_to_latex(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        original_texmath = formula_conversion.convert_with_texmath
        original_mathml = formula_conversion.convert_with_mathml_to_latex
        try:
            formula_conversion.convert_with_texmath = lambda *args, **kwargs: (
                formula_conversion.FormulaConversionResult(
                    backend="texmath",
                    status="failed",
                    latex="",
                    raw_mathml=raw_mathml,
                    error="texmath missing",
                    duration_ms=1,
                    display_mode=False,
                )
            )
            formula_conversion.convert_with_mathml_to_latex = lambda *args, **kwargs: (
                formula_conversion.FormulaConversionResult(
                    backend="mathml-to-latex",
                    status="ok",
                    latex="x",
                    raw_mathml=raw_mathml,
                    error=None,
                    duration_ms=2,
                    display_mode=False,
                )
            )

            result = formula_conversion.convert_mathml_string(
                raw_mathml, display_mode=False, env={}
            )
        finally:
            formula_conversion.convert_with_texmath = original_texmath
            formula_conversion.convert_with_mathml_to_latex = original_mathml

        self.assertEqual(result.backend, "mathml-to-latex")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.latex, "x")

    def test_conversion_cache_reuses_result_for_same_backend_payload_and_config(
        self,
    ) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
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

            first = formula_conversion.convert_mathml_string(
                raw_mathml, display_mode=False, env={}, backend="texmath"
            )
            second = formula_conversion.convert_mathml_string(
                raw_mathml, display_mode=False, env={}, backend="texmath"
            )
        finally:
            formula_conversion.convert_with_texmath = original_texmath

        self.assertEqual(calls, 1)
        self.assertEqual(first.latex, "x")
        self.assertEqual(second.latex, "x")
        self.assertEqual(second.duration_ms, 0)

    def test_formula_timing_collector_records_uncached_and_cache_hit_calls(
        self,
    ) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
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

    def test_texmath_cache_avoids_duplicate_subprocess_run(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            texmath_bin = Path(tmpdir) / (
                "texmath.exe" if os.name == "nt" else "texmath"
            )
            texmath_bin.write_bytes(b"")
            calls: list[list[str]] = []

            def fake_run(args, **_kwargs):
                command = [str(item) for item in args]
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, "x", "")

            with mock.patch.object(
                formula_conversion.subprocess, "run", side_effect=fake_run
            ):
                first = formula_conversion.convert_mathml_string(
                    raw_mathml,
                    display_mode=False,
                    env={"TEXMATH_BIN": str(texmath_bin)},
                    backend="texmath",
                )
                second = formula_conversion.convert_mathml_string(
                    raw_mathml,
                    display_mode=False,
                    env={"TEXMATH_BIN": str(texmath_bin)},
                    backend="texmath",
                )

        self.assertEqual(first.status, "ok")
        self.assertEqual(second.status, "ok")
        self.assertEqual(second.duration_ms, 0)
        self.assertEqual(len(calls), 1)

    def test_mathml_to_latex_worker_success_avoids_cli_process(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        original_command = formula_conversion._resolve_mathml_to_latex_command
        original_worker_command = (
            formula_conversion._resolve_mathml_to_latex_worker_command
        )
        original_worker_for = formula_conversion._mathml_worker_for
        original_run_command = formula_conversion._run_command

        class FakeWorker:
            def convert(self, _raw_mathml, *, timeout_seconds):
                return "x"

        try:
            formula_conversion._resolve_mathml_to_latex_command = lambda _env: (
                "node",
                "/tmp/cli.mjs",
                None,
                None,
            )
            formula_conversion._resolve_mathml_to_latex_worker_command = lambda _env: (
                "node",
                "/tmp/worker.mjs",
                None,
                None,
            )
            formula_conversion._mathml_worker_for = lambda **_kwargs: FakeWorker()
            formula_conversion._run_command = lambda *args, **kwargs: (
                _ for _ in ()
            ).throw(AssertionError("CLI fallback should not run"))

            result = formula_conversion.convert_with_mathml_to_latex(
                raw_mathml,
                display_mode=False,
                env={},
            )
        finally:
            formula_conversion._resolve_mathml_to_latex_command = original_command
            formula_conversion._resolve_mathml_to_latex_worker_command = (
                original_worker_command
            )
            formula_conversion._mathml_worker_for = original_worker_for
            formula_conversion._run_command = original_run_command

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.latex, "x")

    def test_mathml_to_latex_worker_failure_falls_back_to_cli(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        original_command = formula_conversion._resolve_mathml_to_latex_command
        original_worker_command = (
            formula_conversion._resolve_mathml_to_latex_worker_command
        )
        original_worker_for = formula_conversion._mathml_worker_for
        original_run_command = formula_conversion._run_command

        class FailingWorker:
            def convert(self, _raw_mathml, *, timeout_seconds):
                raise RuntimeError("worker crashed")

        try:
            formula_conversion._resolve_mathml_to_latex_command = lambda _env: (
                "node",
                "/tmp/cli.mjs",
                None,
                None,
            )
            formula_conversion._resolve_mathml_to_latex_worker_command = lambda _env: (
                "node",
                "/tmp/worker.mjs",
                None,
                None,
            )
            formula_conversion._mathml_worker_for = lambda **_kwargs: FailingWorker()
            formula_conversion._run_command = lambda *args, **kwargs: (
                subprocess.CompletedProcess(args[0], 0, "x", "")
            )

            result = formula_conversion.convert_with_mathml_to_latex(
                raw_mathml,
                display_mode=False,
                env={},
            )
        finally:
            formula_conversion._resolve_mathml_to_latex_command = original_command
            formula_conversion._resolve_mathml_to_latex_worker_command = (
                original_worker_command
            )
            formula_conversion._mathml_worker_for = original_worker_for
            formula_conversion._run_command = original_run_command

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.latex, "x")

    def test_mathml_to_latex_cli_permission_error_returns_failed_result(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        original_command = formula_conversion._resolve_mathml_to_latex_command
        original_run_command = formula_conversion._run_command
        try:
            formula_conversion._resolve_mathml_to_latex_command = lambda _env: (
                "C:/Program Files/WindowsApps/OpenAI.Codex/app/resources/node.exe",
                "C:/PaperFetchSkill/formula-tools/mathml_to_latex_cli.mjs",
                None,
                None,
            )
            formula_conversion._run_command = lambda *args, **kwargs: (
                _ for _ in ()
            ).throw(PermissionError(5, "Access is denied"))

            result = formula_conversion.convert_with_mathml_to_latex(
                raw_mathml,
                display_mode=False,
                env={"MATHML_TO_LATEX_WORKER": "0"},
            )
        finally:
            formula_conversion._resolve_mathml_to_latex_command = original_command
            formula_conversion._run_command = original_run_command

        self.assertEqual(result.backend, "mathml-to-latex")
        self.assertEqual(result.status, "failed")
        self.assertIn("mathml-to-latex node executable failed", result.error or "")
        self.assertIn("WindowsApps", result.error or "")
        self.assertIn("Access is denied", result.error or "")

    def test_texmath_default_fallback_reports_mathml_node_permission_error(
        self,
    ) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        original_texmath = formula_conversion.convert_with_texmath
        original_command = formula_conversion._resolve_mathml_to_latex_command
        original_run_command = formula_conversion._run_command
        try:
            formula_conversion.convert_with_texmath = lambda *args, **kwargs: (
                formula_conversion.FormulaConversionResult(
                    backend="texmath",
                    status="failed",
                    latex="",
                    raw_mathml=raw_mathml,
                    error="texmath returned empty output",
                    duration_ms=1,
                    display_mode=False,
                )
            )
            formula_conversion._resolve_mathml_to_latex_command = lambda _env: (
                "C:/Program Files/WindowsApps/OpenAI.Codex/app/resources/node.exe",
                "C:/PaperFetchSkill/formula-tools/mathml_to_latex_cli.mjs",
                None,
                None,
            )
            formula_conversion._run_command = lambda *args, **kwargs: (
                _ for _ in ()
            ).throw(PermissionError(5, "Access is denied"))

            result = formula_conversion.convert_mathml_string(
                raw_mathml,
                display_mode=False,
                env={"MATHML_TO_LATEX_WORKER": "0"},
            )
        finally:
            formula_conversion.convert_with_texmath = original_texmath
            formula_conversion._resolve_mathml_to_latex_command = original_command
            formula_conversion._run_command = original_run_command

        self.assertEqual(result.backend, "texmath")
        self.assertEqual(result.status, "failed")
        self.assertIn(
            "texmath failed: texmath returned empty output", result.error or ""
        )
        self.assertIn("mathml-to-latex node executable failed", result.error or "")
        self.assertIn("WindowsApps", result.error or "")

    def test_mathml_to_latex_worker_is_disabled_on_windows(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        original_supported = formula_conversion._PERSISTENT_MATHML_WORKER_SUPPORTED
        original_command = formula_conversion._resolve_mathml_to_latex_command
        original_worker_for = formula_conversion._mathml_worker_for
        original_run_command = formula_conversion._run_command
        try:
            formula_conversion._PERSISTENT_MATHML_WORKER_SUPPORTED = False
            formula_conversion._resolve_mathml_to_latex_command = lambda _env: (
                "node",
                "/tmp/cli.mjs",
                None,
                None,
            )
            formula_conversion._mathml_worker_for = lambda **_kwargs: (
                _ for _ in ()
            ).throw(
                AssertionError(
                    "Windows must use CLI fallback instead of the persistent worker"
                )
            )
            formula_conversion._run_command = lambda *args, **kwargs: (
                subprocess.CompletedProcess(args[0], 0, "x", "")
            )

            result = formula_conversion.convert_with_mathml_to_latex(
                raw_mathml,
                display_mode=False,
                env={"MATHML_TO_LATEX_WORKER": "1"},
            )
        finally:
            formula_conversion._PERSISTENT_MATHML_WORKER_SUPPORTED = original_supported
            formula_conversion._resolve_mathml_to_latex_command = original_command
            formula_conversion._mathml_worker_for = original_worker_for
            formula_conversion._run_command = original_run_command

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.latex, "x")

    def test_external_formula_command_replaces_invalid_utf8_output(self) -> None:
        process = formula_conversion._run_command(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "sys.stdout.buffer.write(b'latex\\xb2\\n'); "
                    "sys.stderr.buffer.write(b'err\\xd0\\n')"
                ),
            ],
            input_text="",
        )

        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stdout, "latex\ufffd\n")
        self.assertEqual(process.stderr, "err\ufffd\n")

    @pytest.mark.allow_subprocess
    def test_texmath_exe_under_formula_tools_is_discovered(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            tools_dir = Path(tmpdir) / "formula-tools"
            texmath = tools_dir / "bin" / "texmath.exe"
            texmath.parent.mkdir(parents=True)
            texmath.write_text("#!/usr/bin/env bash\nprintf 'x\\n'\n", encoding="utf-8")
            texmath.chmod(
                texmath.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )

            result = formula_conversion.convert_with_texmath(
                raw_mathml,
                display_mode=False,
                env={
                    "PAPER_FETCH_FORMULA_TOOLS_DIR": str(tools_dir),
                    "PATH": os.environ.get("PATH", ""),
                },
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.latex, "x")

    def test_explicit_texmath_does_not_hide_failure(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        original_texmath = formula_conversion.convert_with_texmath
        original_mathml = formula_conversion.convert_with_mathml_to_latex
        try:
            formula_conversion.convert_with_texmath = lambda *args, **kwargs: (
                formula_conversion.FormulaConversionResult(
                    backend="texmath",
                    status="failed",
                    latex="",
                    raw_mathml=raw_mathml,
                    error="texmath missing",
                    duration_ms=1,
                    display_mode=False,
                )
            )
            formula_conversion.convert_with_mathml_to_latex = lambda *args, **kwargs: (
                formula_conversion.FormulaConversionResult(
                    backend="mathml-to-latex",
                    status="ok",
                    latex="x",
                    raw_mathml=raw_mathml,
                    error=None,
                    duration_ms=2,
                    display_mode=False,
                )
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
