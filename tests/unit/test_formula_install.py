from __future__ import annotations

import subprocess
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.formula import install as formula_install
from paper_fetch.formula import paths as formula_paths


class FormulaInstallTests(unittest.TestCase):
    def test_texmath_version_requires_exact_native_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            texmath = Path(tmpdir) / "texmath"
            texmath.write_bytes(b"native")
            texmath.chmod(texmath.stat().st_mode | stat.S_IXUSR)

            with mock.patch.object(
                formula_install.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [str(texmath), "--version"],
                    0,
                    stdout="",
                    stderr=f"Version {formula_install.TEXMATH_VERSION}\n",
                ),
            ):
                self.assertEqual(
                    formula_install.texmath_version(texmath),
                    formula_install.TEXMATH_VERSION,
                )
                self.assertTrue(formula_install.have_working_texmath(texmath))

    def test_texmath_version_rejects_compatibility_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            texmath = Path(tmpdir) / "texmath"
            texmath.write_bytes(b"launcher")
            texmath.chmod(texmath.stat().st_mode | stat.S_IXUSR)

            with mock.patch.object(
                formula_install.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [str(texmath), "--version"], 0, stdout="", stderr=""
                ),
            ):
                self.assertIsNone(formula_install.texmath_version(texmath))
                self.assertFalse(formula_install.have_working_texmath(texmath))

    def test_reuse_texmath_copies_portable_binary_instead_of_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "system-bin" / "texmath"
            target_dir = root / "formula-tools"
            source.parent.mkdir()
            source.write_bytes(b"native-texmath")
            source.chmod(source.stat().st_mode | stat.S_IXUSR)

            with (
                mock.patch.object(
                    formula_install.shutil, "which", return_value=str(source)
                ),
                mock.patch.object(
                    formula_install, "have_working_texmath", return_value=True
                ),
            ):
                self.assertTrue(formula_install.reuse_texmath_from_path(target_dir))

            target = formula_install.texmath_target_path(target_dir)
            self.assertEqual(target.read_bytes(), b"native-texmath")
            self.assertFalse(target.is_symlink())

    def test_cabal_install_pins_texmath_version_and_refreshes_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "formula-tools"
            with (
                mock.patch.object(
                    formula_install.shutil, "which", return_value="/usr/bin/cabal"
                ),
                mock.patch.object(
                    formula_install, "_run_with_log", return_value=True
                ) as run,
            ):
                self.assertTrue(formula_install.install_texmath_with_cabal(target_dir))

            self.assertEqual(
                run.call_args_list[0].args,
                ("texmath-cabal-update-", ["/usr/bin/cabal", "update"]),
            )
            self.assertIn(
                f"texmath-{formula_install.TEXMATH_VERSION}",
                run.call_args_list[1].args[1],
            )

    def test_stack_install_pins_texmath_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "formula-tools"
            with (
                mock.patch.object(
                    formula_install.shutil, "which", return_value="/usr/bin/stack"
                ),
                mock.patch.object(
                    formula_install, "_run_with_log", return_value=True
                ) as run,
            ):
                self.assertTrue(formula_install.install_texmath_with_stack(target_dir))

            self.assertIn(
                f"texmath-{formula_install.TEXMATH_VERSION}",
                run.call_args.args[1],
            )

    def test_bundled_formula_resources_are_packaged(self) -> None:
        root = formula_paths.bundled_formula_resources()

        self.assertTrue(root.joinpath("mathml_to_latex_cli.mjs").is_file())
        self.assertTrue(root.joinpath("package.json").is_file())
        self.assertTrue(root.joinpath("package-lock.json").is_file())

    def test_checkout_uses_bundled_formula_scripts(self) -> None:
        root = formula_paths.repo_root()
        self.assertIsNotNone(root)
        assert root is not None
        resource_dir = root / "src" / "paper_fetch" / "resources" / "formula"

        self.assertEqual(
            formula_paths.mathml_to_latex_script_candidates({})[-1],
            resource_dir / "mathml_to_latex_cli.mjs",
        )
        self.assertEqual(
            formula_paths.mathml_to_latex_worker_script_candidates({})[-1],
            resource_dir / "mathml_to_latex_worker.mjs",
        )

    def test_stage_bundled_node_workspace_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "formula-tools"
            formula_install.stage_bundled_node_workspace(target_dir)

            self.assertTrue((target_dir / "mathml_to_latex_cli.mjs").exists())
            self.assertTrue((target_dir / "mathml_to_latex_worker.mjs").exists())
            self.assertTrue((target_dir / "package.json").exists())
            self.assertTrue((target_dir / "package-lock.json").exists())

    def test_existing_mathml_to_latex_does_not_require_katex_or_npm_install(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "formula-tools"
            (target_dir / "node_modules" / "mathml-to-latex").mkdir(parents=True)

            with (
                mock.patch.object(
                    formula_install.shutil,
                    "which",
                    side_effect=lambda name: f"/usr/bin/{name}",
                ),
                mock.patch.object(formula_install, "_run_with_log") as run,
            ):
                self.assertTrue(
                    formula_install.ensure_mathml_to_latex(
                        target_dir,
                        install_node=True,
                    )
                )

            run.assert_not_called()

    def test_texmath_target_path_uses_exe_on_windows(self) -> None:
        target_dir = Path("tools")
        expected = target_dir / "bin" / "texmath.exe"
        original_os_name = formula_install.os.name
        try:
            formula_install.os.name = "nt"
            self.assertEqual(formula_install.texmath_target_path(target_dir), expected)
        finally:
            formula_install.os.name = original_os_name

    def test_formula_tools_search_dirs_include_explicit_override_and_user_dir(
        self,
    ) -> None:
        env = {
            "PAPER_FETCH_FORMULA_TOOLS_DIR": "~/custom-formula-tools",
            "XDG_DATA_HOME": "/tmp/pf-xdg",
        }

        dirs = formula_paths.formula_tools_search_dirs(env)

        self.assertEqual(dirs[0], Path("~/custom-formula-tools").expanduser())
        self.assertIn(Path("/tmp/pf-xdg") / "paper-fetch" / "formula-tools", dirs)

    def test_run_with_log_closes_mkstemp_file_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fd, log_path = tempfile.mkstemp(dir=tmpdir)
            completed = subprocess.CompletedProcess(["tool"], 0)

            with (
                mock.patch.object(
                    formula_install.tempfile, "mkstemp", return_value=(fd, log_path)
                ),
                mock.patch.object(
                    formula_install.os, "close", wraps=formula_install.os.close
                ) as close,
                mock.patch.object(
                    formula_install.subprocess, "run", return_value=completed
                ),
            ):
                self.assertTrue(
                    formula_install._run_with_log("texmath-cabal-", ["tool"])
                )

            close.assert_called_once_with(fd)
            self.assertFalse(Path(log_path).exists())

    def test_run_with_log_keeps_success_when_cleanup_hits_windows_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fd, log_path = tempfile.mkstemp(dir=tmpdir)
            completed = subprocess.CompletedProcess(["tool"], 0)

            with (
                mock.patch.object(
                    formula_install.tempfile, "mkstemp", return_value=(fd, log_path)
                ),
                mock.patch.object(
                    formula_install.subprocess, "run", return_value=completed
                ),
                mock.patch.object(
                    Path, "unlink", side_effect=PermissionError("locked")
                ),
                mock.patch.object(formula_install, "warn") as warn,
            ):
                self.assertTrue(
                    formula_install._run_with_log("texmath-cabal-", ["tool"])
                )

            warn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
