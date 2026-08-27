from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote

import yaml

from paper_fetch.redaction import is_sensitive_configuration_name
from scripts.scan_artifacts_for_secrets import scan_artifacts
from tests.live._runtime_env import SecretSafeEnvironment


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_artifact_scanner_reports_only_variable_name_and_path(tmp_path: Path) -> None:
    sentinel = "paper-fetch sentinel/+?=value"
    raw_path = tmp_path / "raw.txt"
    encoded_path = tmp_path / "encoded.txt"
    raw_path.write_text(f"failure={sentinel}\n", encoding="utf-8")
    encoded_path.write_text(quote(sentinel, safe=""), encoding="utf-8")

    report = scan_artifacts(
        [tmp_path],
        env={"ELSEVIER_API_KEY": sentinel},
        env_names=["ELSEVIER_API_KEY"],
    )

    assert report["status"] == "blocked"
    assert report["matches"] == [
        {"env_var": "ELSEVIER_API_KEY", "path": str(encoded_path)},
        {"env_var": "ELSEVIER_API_KEY", "path": str(raw_path)},
    ]
    rendered = json.dumps(report, ensure_ascii=False)
    assert sentinel not in rendered
    assert quote(sentinel, safe="") not in rendered


def test_explicit_secret_selection_ignores_unrelated_runner_defaults(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "third-party.whl"
    artifact.write_bytes(b"ordinary-root-package-content")

    report = scan_artifacts(
        [artifact],
        env={
            "GITHUB_TOKEN": "github-token-that-is-not-present",
            "PGPASSWORD": "root",
        },
        env_names=["GITHUB_TOKEN"],
    )

    assert report["status"] == "clean"
    assert report["scanned_secret_name_count"] == 1


def test_controlled_pytest_failure_junit_cannot_render_live_secret(
    tmp_path: Path,
) -> None:
    sentinel = "paper-fetch-junit/+?=sentinel"
    junit_path = tmp_path / "pytest-junit.xml"
    test_path = tmp_path / "test_controlled_failure.py"
    test_path.write_text(
        """
import os
from tests.live._runtime_env import SecretSafeEnvironment

def test_controlled_failure():
    env = SecretSafeEnvironment({"ELSEVIER_API_KEY": os.environ["ELSEVIER_API_KEY"]})
    raise AssertionError(f"controlled failure env={env!r}")
""".lstrip(),
        encoding="utf-8",
    )
    process_env = dict(os.environ)
    process_env["ELSEVIER_API_KEY"] = sentinel
    process_env["PYTHONPATH"] = os.pathsep.join(
        (str(REPO_ROOT / "src"), str(REPO_ROOT))
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_path),
            "-q",
            "--confcutdir",
            str(tmp_path),
            f"--junitxml={junit_path}",
        ],
        cwd=tmp_path,
        env=process_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    persisted = junit_path.read_text(encoding="utf-8")
    combined = completed.stdout + completed.stderr + persisted
    assert sentinel not in combined
    assert quote(sentinel, safe="") not in combined
    report = scan_artifacts(
        [junit_path],
        env={"ELSEVIER_API_KEY": sentinel},
        env_names=["ELSEVIER_API_KEY"],
    )
    assert report["status"] == "clean"


def test_live_environment_repr_never_contains_values() -> None:
    sentinel = "do-not-render-this-value"
    env = SecretSafeEnvironment(
        {"ELSEVIER_API_KEY": sentinel, "VISIBLE": "also-hidden"}
    )

    rendered = repr(env)

    assert rendered == "SecretSafeEnvironment(keys=[ELSEVIER_API_KEY, VISIBLE])"
    assert sentinel not in rendered


def test_provider_canary_upload_is_gated_by_secret_scan() -> None:
    workflow = (REPO_ROOT / ".github/workflows/provider-canary.yml").read_text(
        encoding="utf-8"
    )

    assert "scripts/scan_artifacts_for_secrets.py" in workflow
    assert "steps.secret_scan.outcome == 'success'" in workflow


def test_every_workflow_artifact_upload_is_gated_by_secret_scan() -> None:
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    upload_count = 0
    for path in sorted(workflow_dir.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in workflow.get("jobs", {}).items():
            steps = job.get("steps", []) if isinstance(job, dict) else []
            for index, step in enumerate(steps):
                if not str(step.get("uses") or "").startswith(
                    "actions/upload-artifact@"
                ):
                    continue
                upload_count += 1
                scans = [
                    candidate
                    for candidate in steps[:index]
                    if "scripts/scan_artifacts_for_secrets.py"
                    in str(candidate.get("run") or "")
                    and candidate.get("id")
                ]
                assert scans, f"{path.name}:{job_name} upload has no secret scan"
                scan_id = scans[-1]["id"]
                condition = str(step.get("if") or "")
                assert f"steps.{scan_id}.outcome == 'success'" in condition, (
                    f"{path.name}:{job_name} upload is not gated by {scan_id}"
                )

    assert upload_count == 10


def test_workflow_artifact_scans_name_injected_secrets_explicitly() -> None:
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    scan_count = 0
    for path in sorted(workflow_dir.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in workflow.get("jobs", {}).items():
            steps = job.get("steps", []) if isinstance(job, dict) else []
            for step in steps:
                command = str(step.get("run") or "")
                if "scripts/scan_artifacts_for_secrets.py" not in command:
                    continue
                scan_count += 1
                env = step.get("env") or {}
                sensitive_names = {
                    str(name)
                    for name in env
                    if is_sensitive_configuration_name(str(name))
                }
                assert sensitive_names, f"{path.name}:{job_name} scan has no secret"
                for name in sensitive_names:
                    assert f"--env-var {name}" in command, (
                        f"{path.name}:{job_name} scan does not explicitly select {name}"
                    )

    assert scan_count == 12


def test_release_publication_and_attestation_follow_secret_scan() -> None:
    stable = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    rolling = (REPO_ROOT / ".github/workflows/rolling-release.yml").read_text(
        encoding="utf-8"
    )

    stable_scan = stable.index("Scan stable release artifacts for secret values")
    assert stable_scan < stable.index("Attest release artifacts")
    assert stable_scan < stable.index("Publish immutable release assets")
    assert stable.count("steps.secret_scan_release_assets.outcome == 'success'") >= 2

    rolling_scan = rolling.index("Scan rolling release artifacts for secret values")
    assert rolling_scan < rolling.index("Publish rolling prerelease")
    assert "steps.secret_scan_release_assets.outcome == 'success'" in rolling
