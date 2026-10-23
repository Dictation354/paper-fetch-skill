from __future__ import annotations
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
import subprocess
from pathlib import Path
from unittest import mock
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

    def test_scoped_runtime_env_reaches_implicit_formula_conversion(self) -> None:
        raw_mathml = (
            '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
        )
        captured_env: dict[str, str] = {}

        def fake_texmath(raw, *, display_mode, env):
            captured_env.update(env)
            return formula_conversion.FormulaConversionResult(
                backend="texmath",
                status="ok",
                latex="x",
                raw_mathml=raw,
                error=None,
                duration_ms=1,
                display_mode=display_mode,
            )

        runtime_env = {
            "PAPER_FETCH_FORMULA_TOOLS_DIR": "/prepared/formula-tools",
        }
        with (
            mock.patch.object(
                formula_conversion,
                "convert_with_texmath",
                side_effect=fake_texmath,
            ),
            formula_conversion.formula_runtime_env(runtime_env),
        ):
            result = formula_conversion.convert_mathml_string(
                raw_mathml,
                display_mode=False,
                backend="texmath",
            )

        self.assertEqual(result.status, "ok")
        self.assertEqual(captured_env, runtime_env)

    def test_normalize_latex_preserves_source_scenario_samples(self) -> None:
        samples = json.loads(
            golden_criteria_scenario_asset(
                "formula_latex_normalization", "samples.json"
            ).read_text(encoding="utf-8")
        )
        for sample in samples:
            with self.subTest(sample=sample["name"]):
                self.assertEqual(
                    formula_conversion.normalize_latex(sample["input"]), sample["input"]
                )

    def test_normalize_latex_preserves_source_commands_and_spacing(self) -> None:
        for source in (
            r"\updelta Q + \upDelta P + \updeltaQ",
            r"\mspace{6mu}x + \mspace{ -1.5 mu }y + \mspace{2pt}z",
            "S\u200bO + " + r"a\hspace{0pt}b + c\hspace*{ 0.0 em }d",
            r"F_{c r i t} = \sum_{t_{p}}^{S O S_{y 0}} R_{f} + \mathcal{ℴ}",
            r"P(SPI \unicode{x2A7D} - 1.64) + \unicode{U+03B1}x",
            r"\mathop\sum_{i=1}^n x + \mathop{custom}",
            r"x\textbackslash\_NDVI + \text{\textbackslash\_NDVI}",
            r"s \left(\right. s + 1 \left.\right)",
        ):
            with self.subTest(source=source):
                self.assertEqual(formula_conversion.normalize_latex(source), source)

    def test_normalize_latex_removes_only_outer_delimiters(self) -> None:
        source = "\\begin{equation}\n x % comment\n + \\text{two  spaces} + \\hbox{$y$}\n\\end{equation}"
        for opener, closer in (
            ("$", "$"),
            ("$$", "$$"),
            (r"\(", r"\)"),
            (r"\[", r"\]"),
        ):
            with self.subTest(opener=opener):
                normalized = formula_conversion.normalize_latex(
                    f" {opener}\n{source}\n{closer} "
                )
                self.assertEqual(normalized, source)
                self.assertEqual(formula_conversion.normalize_latex(normalized), source)
        self.assertEqual(formula_conversion.normalize_latex(None), "")
        self.assertEqual(formula_conversion.normalize_latex("$$ $$"), "")

    def test_mathml_conversion_repairs_stay_private(self) -> None:
        source = (
            r"F_{c r i t} + x\textbackslash\_NDVI + s \left(\right. s + 1 \left.\right)"
        )
        self.assertEqual(formula_conversion.normalize_latex(source), source)
        self.assertEqual(
            formula_conversion._normalize_mathml_latex(source),
            r"F_{crit} + x\_NDVI + s(s + 1)",
        )

    def test_backend_registry_preserves_public_backend_groups(self) -> None:
        self.assertEqual(
            formula_conversion.SUPPORTED_BACKENDS,
            {"auto", "texmath", "mathml-to-latex", "mml2tex"},
        )
        self.assertEqual(
            formula_conversion.AUTO_BACKENDS, ("texmath", "mathml-to-latex")
        )

    def test_backend_registry_resolves_aliases(self) -> None:
        self.assertEqual(
            formula_conversion.resolve_backend(backend="mathml_to_latex"),
            "mathml-to-latex",
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
