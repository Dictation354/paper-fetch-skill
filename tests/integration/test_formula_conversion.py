from __future__ import annotations
import sys
import os
import tempfile
import unittest
import stat
from pathlib import Path
import pytest
from paper_fetch.formula import convert as formula_conversion


class FormulaConversionTests(unittest.TestCase):
    def tearDown(self) -> None:
        formula_conversion.clear_conversion_cache()

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


if __name__ == "__main__":
    unittest.main()
