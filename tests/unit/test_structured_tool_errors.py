from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_KEYS = {
    "code",
    "message",
    "provider",
    "manifest",
    "task_id",
    "retryable",
    "details",
}
SIGNAL_CODES = {
    "MANIFEST_NOT_FOUND",
    "MANIFEST_DISCOVERY_FAILED",
    "MANIFEST_SCHEMA_INVALID",
    "MANIFEST_PROVIDER_CONFLICT",
    "MANIFEST_CODE_DRIFT",
    "SCAFFOLD_OUTPUT_EXISTS",
    "SCAFFOLD_TEMPLATE_RENDER_FAILED",
    "SCAFFOLD_FORBIDDEN_FLAG_COMBINATION",
    "UNSUITABLE_DOI_SAMPLE",
    "HTTP_FORBIDDEN",
    "HTTP_RATE_LIMITED",
    "CHALLENGE_DETECTED",
    "BROWSER_RUNTIME_REQUIRED",
    "NON_PDF_FALLBACK_CONTENT",
    "ACCESS_GATE_CAPTURED",
    "EMPTY_ARTICLE_SHELL",
    "NETWORK_TRANSIENT",
    "EXPECTED_SNAPSHOT_FAILED",
    "EXPECTED_OUTCOME_PENDING",
    "FIXTURE_NOT_FOUND",
    "TASK_BRIEF_INVALID",
    "WORKER_MODIFIED_FORBIDDEN_FILE",
    "DISCOVERY_RETRY_EXHAUSTED",
    "TASK_RETRY_EXHAUSTED",
    "GLOBAL_LINT_FAILED",
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def _stderr_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode != 0
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert REQUIRED_KEYS <= set(payload)
    assert isinstance(payload["details"], dict)
    return payload


def test_scaffold_forbidden_manifest_flags_emit_structured_error(
    tmp_path: Path,
) -> None:
    result = _run(
        "scripts/scaffold_provider.py",
        "--from-manifest",
        str(tmp_path / "provider.yml"),
        "--name",
        "mdpi",
        "--output-dir",
        str(tmp_path),
    )

    payload = _stderr_json(result)
    assert payload["code"] == "SCAFFOLD_FORBIDDEN_FLAG_COMBINATION"
    assert payload["manifest"] == str(tmp_path / "provider.yml")
    assert "--from-manifest cannot be combined with --name" in str(payload["message"])


def test_scaffold_manifest_schema_error_keeps_legacy_fields(tmp_path: Path) -> None:
    manifest = tmp_path / "invalid.yml"
    manifest.write_text("schema_version: 1\nname: invalid\n", encoding="utf-8")

    result = _run(
        "scripts/scaffold_provider.py",
        "--from-manifest",
        str(manifest),
        "--output-dir",
        str(tmp_path / "out"),
    )

    payload = _stderr_json(result)
    assert payload["code"] == "MANIFEST_SCHEMA_INVALID"
    assert payload["status"] == "MANIFEST_SCHEMA_INVALID"
    assert payload["reason"]


def test_capture_missing_doi_emits_structured_schema(tmp_path: Path) -> None:
    result = _run(
        "scripts/capture_fixture.py",
        "--purpose",
        "structure",
        "--output-dir",
        str(tmp_path),
    )

    payload = _stderr_json(result)
    assert payload["code"] == "UNSUITABLE_DOI_SAMPLE"
    assert payload["purpose"] == "structure"
    assert payload["details"]["purpose"] == "structure"


def test_capture_bad_manifest_yaml_emits_manifest_schema_code(tmp_path: Path) -> None:
    manifest = tmp_path / "bad.yml"
    manifest.write_text("name: [broken\n", encoding="utf-8")

    result = _run(
        "scripts/capture_fixture.py",
        "--from-manifest",
        str(manifest),
        "--purpose",
        "structure",
        "--output-dir",
        str(tmp_path),
    )

    payload = _stderr_json(result)
    assert payload["code"] == "MANIFEST_SCHEMA_INVALID"
    assert payload["manifest"] == str(manifest)


def test_snapshot_missing_fixture_emits_structured_schema(tmp_path: Path) -> None:
    result = _run(
        "scripts/snapshot_expected.py",
        "--doi",
        "10.0000/probe",
        "--output-dir",
        str(tmp_path),
    )

    payload = _stderr_json(result)
    assert payload["code"] == "FIXTURE_NOT_FOUND"
    assert payload["details"]["doi"] == "10.0000/probe"


def test_coordinator_state_conflict_emits_structured_schema(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    first = _run(
        "scripts/onboard_from_manifests.py",
        "next",
        "--provider",
        "mdpi",
        "--state",
        str(state),
    )
    assert first.returncode == 0

    result = _run(
        "scripts/onboard_from_manifests.py",
        "next",
        "--provider",
        "arxiv",
        "--state",
        str(state),
    )

    payload = _stderr_json(result)
    assert payload["code"] == "TASK_BRIEF_INVALID"
    assert payload["provider"] == "arxiv"
    assert payload["details"]["active_provider"] == "mdpi"


def test_failure_recovery_has_signal_sections_for_all_codes() -> None:
    text = (REPO_ROOT / "onboarding" / "failure-recovery.md").read_text(
        encoding="utf-8"
    )
    for code in SIGNAL_CODES:
        section = f"## Signal: {code}"
        assert section in text
        tail = text.split(section, 1)[1].split("\n## Signal:", 1)[0]
        assert "diagnosis:" in tail
        assert "action:" in tail
        assert "retryable:" in tail
