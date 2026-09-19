from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
from scripts import resolve_offline_dependencies as module


REPO_ROOT = Path(__file__).resolve().parents[2]


def _record(name: str, version: str, digest: str) -> dict[str, str]:
    normalized = name.replace("-", "_")
    return {
        "name": name,
        "version": version,
        "filename": f"{normalized}-{version}-py3-none-any.whl",
        "sha256": digest,
    }


def _fragment(
    target: str,
    *,
    version: str = "1.0",
    digest: str = "a" * 64,
    source_sha: str = "1" * 40,
) -> dict:
    platform_name, arch, python_tag = target.rsplit("-", 2)
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-07-19T00:00:00Z",
        "source": {
            "tag": "v3.1.3",
            "commit": source_sha,
            "project_name": "paper-fetch-skill",
            "project_version": "3.1.3",
        },
        "target": {
            "key": target,
            "platform": platform_name,
            "arch": arch,
            "python_tag": python_tag,
        },
        "dependencies": [_record("example", version, digest)],
        "support_wheels": [_record("pip", "26.1", "b" * 64)],
    }


def _merge(tmp_path: Path, *fragments: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    paths = []
    targets = []
    for index, fragment in enumerate(fragments):
        path = tmp_path / f"fragment-{index}.json"
        path.write_text(json.dumps(fragment), encoding="utf-8")
        paths.append(path)
        targets.append(fragment["target"]["key"])
    output = tmp_path / "dependency-manifest.json"
    result = module.merge_snapshots(
        argparse.Namespace(
            fragment=paths,
            expected_target=targets,
            output=output,
        )
    )
    assert result == 0
    return output


def test_verify_cli_runs_without_resolver_site_packages(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshot"
    (snapshot_root / "runtime-wheels").mkdir(parents=True)
    (snapshot_root / "support-wheels").mkdir()
    fragment = _fragment("linux-x86_64-cp311")
    fragment["dependencies"] = []
    fragment["support_wheels"] = []
    manifest = _merge(tmp_path / "manifest", fragment)

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(REPO_ROOT / "scripts" / "resolve_offline_dependencies.py"),
            "verify",
            "--manifest",
            str(manifest),
            "--target",
            "linux-x86_64-cp311",
            "--snapshot-root",
            str(snapshot_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
