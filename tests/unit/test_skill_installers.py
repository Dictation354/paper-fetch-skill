from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]


class SkillInstallerTests(unittest.TestCase):
    def test_active_host_installers_are_shipped(self) -> None:
        self.assertTrue((REPO_ROOT / "scripts" / "install-codex-skill.sh").is_file())
        self.assertTrue((REPO_ROOT / "scripts" / "install-claude-skill.sh").is_file())

    def test_shared_installer_supports_only_active_skill_hosts(self) -> None:
        common = (REPO_ROOT / "scripts" / "_skill_install_common.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("claude) printf", common)
        self.assertIn("codex) printf", common)


if __name__ == "__main__":
    unittest.main()
