from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from paper_fetch.mcp._instructions import DEFAULT_FETCH_NOTES, DEFAULT_FETCH_VALUES, ERROR_CONTRACT, SKILL_ENVIRONMENT_VARIABLES
from tests.paths import REPO_ROOT, SKILL_DIR

STATIC_SKILL_DIR = SKILL_DIR
STATIC_SKILL_PATH = SKILL_DIR / "SKILL.md"


def write_fake_python(path: Path, log_path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$0 $@" >> "{log_path}"\n'
        'if [ "$1" = "-c" ]; then\n'
        '  printf "%s\\n" "$0"\n'
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def write_fake_mcp_cli(path: Path, log_path: Path) -> None:
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$0 $@" >> "{log_path}"\n'
        'if [ "$1" = "mcp" ] && [ "$2" = "get" ]; then\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def copy_installer_fixture(repo_dir: Path) -> None:
    (repo_dir / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "scripts" / "install-claude-skill.sh", repo_dir / "scripts" / "install-claude-skill.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "install-codex-skill.sh", repo_dir / "scripts" / "install-codex-skill.sh")
    shutil.copy2(
        REPO_ROOT / "scripts" / "run-codex-paper-fetch-mcp.sh",
        repo_dir / "scripts" / "run-codex-paper-fetch-mcp.sh",
    )
    shutil.copytree(STATIC_SKILL_DIR, repo_dir / "skills" / "paper-fetch-skill", dirs_exist_ok=True)
    shutil.copy2(REPO_ROOT / "pyproject.toml", repo_dir / "pyproject.toml")


def iter_skill_markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def read_skill_bundle(root: Path) -> str:
    return "\n\n".join(path.read_text(encoding="utf-8") for path in iter_skill_markdown_files(root))


def assert_skill_bundle_matches_repo(testcase: unittest.TestCase, installed_root: Path) -> None:
    expected_files = [path.relative_to(STATIC_SKILL_DIR).as_posix() for path in iter_skill_markdown_files(STATIC_SKILL_DIR)]
    actual_files = [path.relative_to(installed_root).as_posix() for path in iter_skill_markdown_files(installed_root)]

    testcase.assertEqual(actual_files, expected_files)
    for relative_path in expected_files:
        testcase.assertEqual(
            (installed_root / relative_path).read_text(encoding="utf-8"),
            (STATIC_SKILL_DIR / relative_path).read_text(encoding="utf-8"),
        )


class StaticSkillTests(unittest.TestCase):
    def test_static_skill_frontmatter_is_valid_yaml(self) -> None:
        text = STATIC_SKILL_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---\n", 2)[1]

        metadata = yaml.safe_load(frontmatter)

        self.assertEqual(metadata["name"], "paper-fetch-skill")
        self.assertIn("description", metadata)

    def test_static_skill_entrypoint_stays_thin_and_points_at_references(self) -> None:
        text = STATIC_SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("resolve_paper", text)
        self.assertIn("fetch_paper", text)
        self.assertIn("list_cached", text)
        self.assertIn("get_cached", text)
        self.assertIn("batch_check", text)
        self.assertIn("summarize_paper", text)
        self.assertIn("verify_citation_list", text)
        self.assertIn("token_estimate_breakdown", text)
        self.assertIn("citation list", text)
        self.assertIn('do not conclude "unreadable" just because there is no local pdf', text.lower())
        self.assertIn("references/environment.md", text)
        self.assertIn("references/cli-fallback.md", text)
        self.assertIn("references/failure-handling.md", text)
        self.assertLessEqual(len(text.splitlines()), 80)

    def test_static_skill_bundle_covers_runtime_contract(self) -> None:
        text = read_skill_bundle(STATIC_SKILL_DIR)

        self.assertIn("paper-fetch --query", text)
        self.assertIn("## Error Contract", text)
        self.assertNotIn("not thread-safe", text)
        for key, value in DEFAULT_FETCH_VALUES:
            self.assertIn(f"`{key}={value}`", text)
        for note in DEFAULT_FETCH_NOTES:
            self.assertIn(note, text)
        for name, _description in SKILL_ENVIRONMENT_VARIABLES:
            self.assertIn(f"`{name}`", text)
        for status, _description in ERROR_CONTRACT:
            self.assertIn(f"`{status}`", text)
        self.assertNotIn("${", text)
        self.assertNotIn(str(REPO_ROOT), text)
        self.assertNotIn(".venv", text)
        self.assertNotIn(".env", text)


class InstallerSmokeTests(unittest.TestCase):
    def run_installer(
        self,
        *,
        script_name: str,
        args: list[str] | None = None,
        extra_env: dict[str, str] | None = None,
        fake_codex: bool = False,
        fake_claude: bool = False,
        create_repo_env: bool = False,
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
        if create_repo_env:
            (repo_dir / ".env").write_text("ELSEVIER_API_KEY=dev\n", encoding="utf-8")
        fake_bin_dir.mkdir(parents=True, exist_ok=True)
        home_dir.mkdir(parents=True, exist_ok=True)
        codex_home.mkdir(parents=True, exist_ok=True)
        write_fake_python(fake_bin_dir / "python3", log_path)
        if fake_codex:
            write_fake_mcp_cli(fake_bin_dir / "codex", log_path)
        if fake_claude:
            write_fake_mcp_cli(fake_bin_dir / "claude", log_path)

        env = os.environ.copy()
        env["PATH"] = f"{fake_bin_dir}{os.pathsep}{env.get('PATH', '')}"
        env["HOME"] = str(home_dir)
        env["CODEX_HOME"] = str(codex_home)
        if extra_env:
            env.update(extra_env)

        subprocess.run(
            ["bash", str(repo_dir / "scripts" / script_name), *(args or [])],
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

        installed_root = sandbox / "home" / ".claude" / "skills" / "paper-fetch-skill"
        installed_skill = installed_root / "SKILL.md"
        self.assertTrue(installed_skill.exists())
        assert_skill_bundle_matches_repo(self, installed_root)
        self.assertFalse((repo_dir / ".venv").exists())
        self.assertFalse((repo_dir / ".env").exists())
        self.assertIn("-m pip install --quiet .", log_path.read_text(encoding="utf-8"))
        self.assertFalse((installed_root / "agents").exists())

    def test_claude_installer_can_register_mcp_server(self) -> None:
        _, _, log_path = self.run_installer(
            script_name="install-claude-skill.sh",
            args=["--register-mcp", "--env-file", "/tmp/paper-fetch.env", "--mcp-scope", "project"],
            fake_claude=True,
        )

        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("claude mcp remove -s project paper-fetch", log_text)
        self.assertIn(
            "claude mcp add -s project -e PAPER_FETCH_ENV_FILE=/tmp/paper-fetch.env paper-fetch --",
            log_text,
        )
        self.assertIn("-m paper_fetch.mcp.server", log_text)

    def test_codex_installer_adds_openai_manifest_shim(self) -> None:
        repo_dir, sandbox, log_path = self.run_installer(script_name="install-codex-skill.sh")

        skill_dir = sandbox / "codex-home" / "skills" / "paper-fetch-skill"
        installed_skill = skill_dir / "SKILL.md"
        manifest_path = skill_dir / "agents" / "openai.yaml"

        self.assertTrue(installed_skill.exists())
        assert_skill_bundle_matches_repo(self, skill_dir)
        self.assertTrue(manifest_path.exists())
        manifest_text = manifest_path.read_text(encoding="utf-8")
        self.assertIn('display_name: "Paper Fetch Skill"', manifest_text)
        self.assertIn("$paper-fetch-skill", manifest_text)
        self.assertIn("full-text availability", manifest_text)
        self.assertFalse((repo_dir / ".venv").exists())
        self.assertFalse((repo_dir / ".env").exists())
        self.assertIn("-m pip install --quiet .", log_path.read_text(encoding="utf-8"))

    def test_codex_installer_can_register_mcp_server(self) -> None:
        _, _, log_path = self.run_installer(
            script_name="install-codex-skill.sh",
            args=["--register-mcp", "--env-file", "/tmp/paper-fetch.env"],
            fake_codex=True,
        )

        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("codex mcp remove paper-fetch", log_text)
        self.assertIn("codex mcp add --env PAPER_FETCH_MCP_PYTHON_BIN=", log_text)
        self.assertIn("--env PAPER_FETCH_ENV_FILE=/tmp/paper-fetch.env", log_text)
        self.assertIn("paper-fetch --", log_text)
        self.assertIn("scripts/run-codex-paper-fetch-mcp.sh", log_text)

    def test_claude_installer_does_not_auto_bind_repo_env_for_mcp_registration(self) -> None:
        _, _, log_path = self.run_installer(
            script_name="install-claude-skill.sh",
            args=["--register-mcp", "--mcp-scope", "project"],
            fake_claude=True,
            create_repo_env=True,
        )

        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("claude mcp add -s project paper-fetch --", log_text)
        self.assertNotIn("PAPER_FETCH_ENV_FILE=", log_text)

    def test_codex_installer_does_not_auto_bind_repo_env_for_mcp_registration(self) -> None:
        _, _, log_path = self.run_installer(
            script_name="install-codex-skill.sh",
            args=["--register-mcp"],
            fake_codex=True,
            create_repo_env=True,
        )

        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("codex mcp add --env PAPER_FETCH_MCP_PYTHON_BIN=", log_text)
        self.assertIn("paper-fetch --", log_text)
        self.assertIn("scripts/run-codex-paper-fetch-mcp.sh", log_text)
        self.assertNotIn("PAPER_FETCH_ENV_FILE=", log_text)


if __name__ == "__main__":
    unittest.main()
