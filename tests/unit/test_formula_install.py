from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.formula import install as formula_install
from paper_fetch.formula import paths as formula_paths


class FormulaInstallTests(unittest.TestCase):
    def test_bundled_formula_resources_are_packaged(self) -> None:
        root = formula_paths.bundled_formula_resources()

        self.assertTrue(root.joinpath("mathml_to_latex_cli.mjs").is_file())
        self.assertTrue(root.joinpath("package.json").is_file())
        self.assertTrue(root.joinpath("package-lock.json").is_file())

    def test_stage_bundled_node_workspace_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "formula-tools"
            formula_install.stage_bundled_node_workspace(target_dir)

            self.assertTrue((target_dir / "mathml_to_latex_cli.mjs").exists())
            self.assertTrue((target_dir / "mathml_to_latex_worker.mjs").exists())
            self.assertTrue((target_dir / "package.json").exists())
            self.assertTrue((target_dir / "package-lock.json").exists())

    def test_texmath_target_path_uses_exe_on_windows(self) -> None:
        target_dir = Path("tools")
        expected = target_dir / "bin" / "texmath.exe"
        original_os_name = formula_install.os.name
        try:
            formula_install.os.name = "nt"
            self.assertEqual(formula_install.texmath_target_path(target_dir), expected)
        finally:
            formula_install.os.name = original_os_name

    def test_formula_tools_search_dirs_include_explicit_override_and_user_dir(self) -> None:
        env = {"PAPER_FETCH_FORMULA_TOOLS_DIR": "~/custom-formula-tools", "XDG_DATA_HOME": "/tmp/pf-xdg"}

        dirs = formula_paths.formula_tools_search_dirs(env)

        self.assertEqual(dirs[0], Path("~/custom-formula-tools").expanduser())
        self.assertIn(Path("/tmp/pf-xdg") / "paper-fetch" / "formula-tools", dirs)

    def test_run_with_log_closes_mkstemp_file_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fd, log_path = tempfile.mkstemp(dir=tmpdir)
            completed = subprocess.CompletedProcess(["tool"], 0)

            with (
                mock.patch.object(formula_install.tempfile, "mkstemp", return_value=(fd, log_path)),
                mock.patch.object(formula_install.os, "close", wraps=formula_install.os.close) as close,
                mock.patch.object(formula_install.subprocess, "run", return_value=completed),
            ):
                self.assertTrue(formula_install._run_with_log("texmath-cabal-", ["tool"]))

            close.assert_called_once_with(fd)
            self.assertFalse(Path(log_path).exists())

    def test_run_with_log_keeps_success_when_cleanup_hits_windows_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fd, log_path = tempfile.mkstemp(dir=tmpdir)
            completed = subprocess.CompletedProcess(["tool"], 0)

            with (
                mock.patch.object(formula_install.tempfile, "mkstemp", return_value=(fd, log_path)),
                mock.patch.object(formula_install.subprocess, "run", return_value=completed),
                mock.patch.object(Path, "unlink", side_effect=PermissionError("locked")),
                mock.patch.object(formula_install, "warn") as warn,
            ):
                self.assertTrue(formula_install._run_with_log("texmath-cabal-", ["tool"]))

            warn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
