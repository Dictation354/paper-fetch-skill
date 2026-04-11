from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
            self.assertTrue((target_dir / "package.json").exists())
            self.assertTrue((target_dir / "package-lock.json").exists())

    def test_formula_tools_search_dirs_include_explicit_override_and_user_dir(self) -> None:
        env = {"PAPER_FETCH_FORMULA_TOOLS_DIR": "~/custom-formula-tools", "XDG_DATA_HOME": "/tmp/pf-xdg"}

        dirs = formula_paths.formula_tools_search_dirs(env)

        self.assertEqual(dirs[0], Path("~/custom-formula-tools").expanduser())
        self.assertIn(Path("/tmp/pf-xdg") / "paper-fetch" / "formula-tools", dirs)


if __name__ == "__main__":
    unittest.main()
