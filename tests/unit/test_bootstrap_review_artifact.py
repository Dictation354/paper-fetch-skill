from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bootstrap_review_artifact.py"
SCHEMA = REPO_ROOT / "onboarding" / "provider-review.schema.json"


def _quality_report(
    *,
    status: str,
    issues: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    issue_list = issues or []
    return {
        "schema_version": 2,
        "review_method": "agent_prompt",
        "provider": "newpub",
        "doi": "10.1234/sample",
        "sample_id": "10.1234_sample",
        "markdown_path": "tests/fixtures/golden_criteria/10.1234_sample/extracted.md",
        "prompt_path": "tests/fixtures/golden_criteria/10.1234_sample/markdown-quality-prompt.md",
        "status": status,
        "issues": issue_list,
        "blocking_issue_count": sum(
            1 for issue in issue_list if issue.get("blocking") is True
        ),
        **(
            {}
            if status == "pending_agent_review"
            else {
                "reviewed_by": "codex-agent",
                "reviewed_at": "2026-05-23T00:00:00Z",
            }
        ),
    }


def _write_manifest(path: Path) -> None:
    path.write_text(
        """
name: newpub
fixtures:
  doi_samples:
    structure:
      doi: 10.1234/sample
markdown_contract:
  structure:
    doi: 10.1234/sample
    must_include:
      - "## Abstract"
    must_not_include:
      - "Download PDF"
""",
        encoding="utf-8",
    )


def _run_bootstrap(tmp_path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--provider",
            "newpub",
            "--manifest",
            "onboarding/manifests/newpub.yml",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    review_path = tmp_path / str(payload["review_path"])
    return yaml.safe_load(review_path.read_text(encoding="utf-8"))


def test_bootstrap_review_artifact_writes_schema_valid_pending_draft(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "onboarding" / "manifests" / "newpub.yml"
    fixture_dir = tmp_path / "tests" / "fixtures" / "golden_criteria" / "10.1234_sample"
    markdown_path = fixture_dir / "extracted.md"
    quality_path = fixture_dir / "markdown-quality.json"
    manifest_path.parent.mkdir(parents=True)
    fixture_dir.mkdir(parents=True)
    markdown_path.write_text("## Abstract\nBody\n", encoding="utf-8")
    (fixture_dir / "markdown-quality-prompt.md").write_text(
        "Review prompt\n", encoding="utf-8"
    )
    quality_path.write_text(
        json.dumps(_quality_report(status="pending_agent_review")) + "\n",
        encoding="utf-8",
    )
    _write_manifest(manifest_path)

    review = _run_bootstrap(tmp_path)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    errors = sorted(
        Draft202012Validator(schema).iter_errors(review),
        key=lambda error: error.json_path,
    )
    assert not errors
    assert review["schema_version"] == 2
    fixture = review["fixtures"][0]
    assert fixture["markdown_semantic_reviewed"] is False
    assert fixture["baseline_markdown_path"] == (
        "tests/fixtures/golden_criteria/10.1234_sample/extracted.md"
    )
    assert fixture["markdown_quality_path"] == (
        "tests/fixtures/golden_criteria/10.1234_sample/markdown-quality.json"
    )
    assert fixture["baseline_markdown_sha256"]
    assert fixture["markdown_quality_sha256"]
    assert fixture["issues"] == [
        {
            "id": "agent-markdown-review-pending",
            "severity": "high",
            "summary": (
                "Markdown quality report is pending agent review; "
                "run markdown-quality-prompt.md and write pass/fail JSON."
            ),
        }
    ]
    assert "must include ## Abstract" in fixture["assertions"]
    assert "must not include Download PDF" in fixture["assertions"]


def test_bootstrap_review_artifact_copies_fail_issues_and_omits_pass_quality_issue(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "onboarding" / "manifests" / "newpub.yml"
    fixture_dir = tmp_path / "tests" / "fixtures" / "golden_criteria" / "10.1234_sample"
    manifest_path.parent.mkdir(parents=True)
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "extracted.md").write_text("## Abstract\nBody\n", encoding="utf-8")
    (fixture_dir / "markdown-quality-prompt.md").write_text(
        "Review prompt\n", encoding="utf-8"
    )
    _write_manifest(manifest_path)

    (fixture_dir / "markdown-quality.json").write_text(
        json.dumps(
            _quality_report(
                status="fail",
                issues=[
                    {
                        "id": "javascript-link",
                        "severity": "high",
                        "blocking": True,
                        "summary": "Markdown contains a javascript placeholder.",
                    }
                ],
            )
        )
        + "\n",
        encoding="utf-8",
    )

    review = _run_bootstrap(tmp_path)
    assert review["fixtures"][0]["issues"] == [
        {
            "id": "javascript-link",
            "severity": "high",
            "summary": "Markdown contains a javascript placeholder.",
        }
    ]

    (tmp_path / "onboarding" / "reviews" / "newpub.yml").unlink()
    (fixture_dir / "markdown-quality.json").write_text(
        json.dumps(_quality_report(status="pass")) + "\n",
        encoding="utf-8",
    )

    review = _run_bootstrap(tmp_path)
    assert review["fixtures"][0]["issues"] == []
