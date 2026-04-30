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
        self.assertIn("pattern: paper-fetch-skill-offline-*", block)
        self.assertIn("merge-multiple: true", block)
        self.assertIn("softprops/action-gh-release@v2", block)
        self.assertIn("contents: write", block)
        self.assertIn("fail_on_unmatched_files: true", block)

        for asset_name in (
            "paper-fetch-skill-offline-linux-x86_64-cp311.tar.gz",
            "paper-fetch-skill-offline-linux-x86_64-cp312.tar.gz",
            "paper-fetch-skill-offline-linux-x86_64-cp313.tar.gz",
            "paper-fetch-skill-offline-linux-x86_64-cp314.tar.gz",
            "paper-fetch-skill-offline-windows-x86_64-cp311.zip",
            "paper-fetch-skill-offline-windows-x86_64-cp312.zip",
            "paper-fetch-skill-offline-windows-x86_64-cp313.zip",
            "paper-fetch-skill-offline-windows-x86_64-cp314.zip",
        ):
            self.assertIn(asset_name, block)


if __name__ == "__main__":
    unittest.main()
