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
