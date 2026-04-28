from __future__ import annotations

import subprocess
import sys
import unittest

from tests.paths import REPO_ROOT


class ExtractionRulesDocTests(unittest.TestCase):
    def test_extraction_rules_documentation_contract_is_valid(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/validate_extraction_rules.py"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
