from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _job_block(workflow: str, job_name: str) -> str:
    marker = f"  {job_name}:"
    start = workflow.index(marker)
    next_job = workflow.find("\n  ", start + len(marker))
    while next_job != -1:
        candidate = workflow[next_job + 1 :].splitlines()[0]
        if candidate.startswith("  ") and not candidate.startswith("    ") and candidate.endswith(":"):
            return workflow[start:next_job]
        next_job = workflow.find("\n  ", next_job + 1)
    return workflow[start:]


class CiReleaseWorkflowTests(unittest.TestCase):
    def test_workflow_dispatch_can_explicitly_publish_release(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("publish_release:", workflow)
        self.assertIn('description: "Publish GitHub Release with offline packages"', workflow)

    def test_workflow_dispatch_can_run_only_windows_offline_job(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("run_offline_windows_only:", workflow)
        self.assertIn('description: "Run only the Windows offline installer packaging job"', workflow)

        for job_name in (
            "lint",
            "unit",
            "integration",
            "package-smoke",
            "offline-linux-x86-64",
            "release-offline-packages",
            "full-golden",
            "live-mcp",
        ):
            block = _job_block(workflow, job_name)
            self.assertIn("!inputs.run_offline_windows_only", block, job_name)

        windows_block = _job_block(workflow, "offline-windows-x86-64")
        self.assertNotIn("!inputs.run_offline_windows_only", windows_block)

    def test_release_job_waits_for_complete_offline_ci(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        block = _job_block(workflow, "release-offline-packages")

        for job_name in (
            "lint",
            "unit",
            "integration",
            "package-smoke",
            "offline-linux-x86-64",
            "offline-windows-x86-64",
        ):
            self.assertIn(f"- {job_name}", block)

    def test_release_job_only_runs_for_tag_or_explicit_manual_release(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        block = _job_block(workflow, "release-offline-packages")

        self.assertIn("github.event_name == 'push'", block)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", block)
        self.assertIn("github.event_name == 'workflow_dispatch'", block)
        self.assertIn("inputs.publish_release", block)
        self.assertIn("tag_name: ${{ github.ref_name }}", block)

    def test_release_job_downloads_and_publishes_all_offline_assets(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        block = _job_block(workflow, "release-offline-packages")

        self.assertIn("actions/download-artifact@v4", block)
        self.assertIn("pattern: paper-fetch-skill-*", block)
        self.assertIn("merge-multiple: true", block)
        self.assertIn("softprops/action-gh-release@v2", block)
        self.assertIn("contents: write", block)
        self.assertIn("fail_on_unmatched_files: true", block)

        for asset_name in (
            "paper-fetch-skill-offline-linux-x86_64-cp311.tar.gz",
            "paper-fetch-skill-offline-linux-x86_64-cp312.tar.gz",
            "paper-fetch-skill-offline-linux-x86_64-cp313.tar.gz",
            "paper-fetch-skill-offline-linux-x86_64-cp314.tar.gz",
            "paper-fetch-skill-windows-x86_64-setup.exe",
        ):
            self.assertIn(asset_name, block)

        self.assertIn('if [ "$actual_count" -ne "${#expected[@]}" ]', block)

    def test_windows_offline_job_builds_and_verifies_setup_installer(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        block = _job_block(workflow, "offline-windows-x86-64")

        self.assertIn('python-version: "3.13"', block)
        self.assertNotIn("matrix:", block)
        self.assertIn("choco install innosetup", block)
        self.assertIn("paper-fetch-skill-windows-x86_64-setup.exe", block)
        for setup_arg in ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"):
            self.assertIn(setup_arg, block)
        self.assertIn("Start-Process -FilePath $setup", block)
        self.assertIn("-Wait -PassThru", block)
        self.assertIn("$setupProcess.ExitCode", block)
        self.assertIn("Get-Content $setupLog", block)
        self.assertNotIn("& $setup /VERYSILENT", block)
        self.assertNotIn("$LASTEXITCODE", block)
        self.assertIn("runtime/python.exe", block)
        self.assertIn("bin/paper-fetch.cmd", block)
        self.assertIn("bin/flaresolverr-up.cmd", block)
        self.assertIn("codex mcp add", block)
        self.assertIn("claude mcp add -s user", block)


if __name__ == "__main__":
    unittest.main()
