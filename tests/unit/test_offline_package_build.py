from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "build-offline-package.sh"


class OfflinePackageBuildTests(unittest.TestCase):
    def test_flaresolverr_wheelhouse_builds_source_only_dependencies(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        start = script.index('log "Bundling FlareSolverr dependency wheelhouse"')
        end = script.index('log "Copying patched FlareSolverr source snapshot"', start)
        block = script[start:end]

        self.assertIn("-m pip wheel", block)
        self.assertIn("--wheel-dir", block)
        self.assertNotIn("--only-binary=:all:", block)


if __name__ == "__main__":
    unittest.main()
