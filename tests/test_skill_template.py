from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_SKILL_PATH = REPO_ROOT / "skills" / "paper-fetch-skill" / "SKILL.md"


def write_fake_python(path: Path, log_path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$0 $@" >> "{log_path}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def copy_installer_fixture(repo_dir: Path) -> None:
    (repo_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (repo_dir / "skills" / "paper-fetch-skill").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "scripts" / "install-claude-skill.sh", repo_dir / "scripts" / "install-claude-skill.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "install-codex-skill.sh", repo_dir / "scripts" / "install-codex-skill.sh")
    shutil.copy2(STATIC_SKILL_PATH, repo_dir / "skills" / "paper-fetch-skill" / "SKILL.md")
    shutil.copy2(REPO_ROOT / "pyproject.toml", repo_dir / "pyproject.toml")


class StaticSkillTests(unittest.TestCase):
    def test_static_skill_covers_mcp_first_contract(self) -> None:
        text = STATIC_SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("resolve_paper", text)
        self.assertIn("fetch_paper", text)
        self.assertIn("paper-fetch --query", text)
        self.assertNotIn("${", text)
        self.assertNotIn(str(REPO_ROOT), text)
        self.assertNotIn(".venv", text)
        self.assertNotIn(".env", text)


class InstallerSmokeTests(unittest.TestCase):
    def run_installer(
        self,
        *,
        script_name: str,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[Path, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        sandbox = Path(temp_dir.name)
        repo_dir = sandbox / "repo"
        fake_bin_dir = sandbox / "bin"
        home_dir = sandbox / "home"
        codex_home = sandbox / "codex-home"
        log_path = sandbox / "python.log"

        copy_installer_fixture(repo_dir)
        fake_bin_dir.mkdir(parents=True, exist_ok=True)
        home_dir.mkdir(parents=True, exist_ok=True)
        codex_home.mkdir(parents=True, exist_ok=True)
        write_fake_python(fake_bin_dir / "python3", log_path)

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["HOME"] = str(home_dir)
        env["CODEX_HOME"] = str(codex_home)
        if extra_env:
            env.update(extra_env)

        subprocess.run(
            ["bash", str(repo_dir / "scripts" / script_name)],
            cwd=repo_dir,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return repo_dir, sandbox, log_path

    def test_claude_installer_copies_static_skill_without_repo_bootstrap_side_effects(self) -> None:
        repo_dir, sandbox, log_path = self.run_installer(script_name="install-claude-skill.sh")

        installed_skill = sandbox / "home" / ".claude" / "skills" / "paper-fetch-skill" / "SKILL.md"
        self.assertTrue(installed_skill.exists())
        self.assertEqual(installed_skill.read_text(encoding="utf-8"), STATIC_SKILL_PATH.read_text(encoding="utf-8"))
        self.assertFalse((repo_dir / ".venv").exists())
        self.assertFalse((repo_dir / ".env").exists())
        self.assertIn("-m pip install --quiet .", log_path.read_text(encoding="utf-8"))
        self.assertFalse((installed_skill.parent / "agents").exists())

    def test_codex_installer_adds_openai_manifest_shim(self) -> None:
        repo_dir, sandbox, log_path = self.run_installer(script_name="install-codex-skill.sh")

        skill_dir = sandbox / "codex-home" / "skills" / "paper-fetch-skill"
        installed_skill = skill_dir / "SKILL.md"
        manifest_path = skill_dir / "agents" / "openai.yaml"

        self.assertTrue(installed_skill.exists())
        self.assertEqual(installed_skill.read_text(encoding="utf-8"), STATIC_SKILL_PATH.read_text(encoding="utf-8"))
        self.assertTrue(manifest_path.exists())
        manifest_text = manifest_path.read_text(encoding="utf-8")
        self.assertIn('display_name: "Paper Fetch Skill"', manifest_text)
        self.assertIn("$paper-fetch-skill", manifest_text)
        self.assertFalse((repo_dir / ".venv").exists())
        self.assertFalse((repo_dir / ".env").exists())
        self.assertIn("-m pip install --quiet .", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
