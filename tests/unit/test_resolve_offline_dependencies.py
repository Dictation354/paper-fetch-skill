from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pytest

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


def _compare(
    tmp_path: Path,
    candidate: Path,
    baseline: Path,
    *,
    force: bool = False,
) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    github_output = tmp_path / "github-output.txt"
    assert (
        module.compare_snapshots(
            argparse.Namespace(
                candidate=candidate,
                baseline=baseline,
                github_output=github_output,
                force=force,
            )
        )
        == 0
    )
    return dict(
        line.split("=", 1)
        for line in github_output.read_text(encoding="utf-8").splitlines()
    )


def test_manifest_digest_is_stable_across_generation_and_support_wheel_changes(
    tmp_path: Path,
) -> None:
    first = _merge(tmp_path / "first", _fragment("linux-x86_64-cp311"))
    changed_fragment = _fragment("linux-x86_64-cp311")
    changed_fragment["generated_at_utc"] = "2026-07-20T00:00:00Z"
    changed_fragment["support_wheels"] = [_record("pip", "26.2", "c" * 64)]
    second = _merge(tmp_path / "second", changed_fragment)

    result = _compare(tmp_path, second, first)

    assert result["changed"] == "false"
    assert result["reason"] == "unchanged"


@pytest.mark.parametrize(
    ("fragment", "expected_reason"),
    [
        (_fragment("linux-x86_64-cp311", version="1.1"), "dependency_set_changed"),
        (_fragment("linux-x86_64-cp311", digest="d" * 64), "dependency_set_changed"),
        (
            _fragment("linux-x86_64-cp311", source_sha="2" * 40),
            "dependency_set_changed",
        ),
    ],
)
def test_compare_detects_runtime_or_source_changes(
    tmp_path: Path, fragment: dict, expected_reason: str
) -> None:
    baseline = _merge(tmp_path / "baseline", _fragment("linux-x86_64-cp311"))
    candidate = _merge(tmp_path / "candidate", fragment)

    result = _compare(tmp_path, candidate, baseline)

    assert result["changed"] == "true"
    assert result["reason"] == expected_reason


def test_compare_treats_missing_baseline_as_changed(tmp_path: Path) -> None:
    candidate = _merge(tmp_path / "candidate", _fragment("linux-x86_64-cp311"))

    result = _compare(tmp_path, candidate, tmp_path / "missing.json")

    assert result["changed"] == "true"
    assert result["reason"] == "baseline_missing"


def test_compare_force_refresh_overrides_unchanged_baseline(tmp_path: Path) -> None:
    baseline = _merge(tmp_path / "baseline", _fragment("linux-x86_64-cp311"))
    candidate = _merge(tmp_path / "candidate", _fragment("linux-x86_64-cp311"))

    result = _compare(tmp_path, candidate, baseline, force=True)

    assert result["changed"] == "true"
    assert result["reason"] == "forced_refresh"


def test_compare_repairs_invalid_baseline_and_force_bypasses_it(tmp_path: Path) -> None:
    candidate = _merge(tmp_path / "candidate", _fragment("linux-x86_64-cp311"))
    baseline = tmp_path / "corrupted.json"
    baseline.write_text("not json", encoding="utf-8")

    automatic = _compare(tmp_path / "automatic", candidate, baseline)
    forced = _compare(tmp_path / "forced", candidate, baseline, force=True)

    assert automatic["changed"] == "true"
    assert automatic["reason"] == "baseline_invalid"
    assert forced["changed"] == "true"
    assert forced["reason"] == "forced_refresh"


def test_merge_rejects_incomplete_target_matrix(tmp_path: Path) -> None:
    fragment = _fragment("linux-x86_64-cp311")
    path = tmp_path / "fragment.json"
    path.write_text(json.dumps(fragment), encoding="utf-8")

    with pytest.raises(module.SnapshotError, match="target set mismatch"):
        module.merge_snapshots(
            argparse.Namespace(
                fragment=[path],
                expected_target=["linux-x86_64-cp311", "linux-x86_64-cp312"],
                output=tmp_path / "manifest.json",
            )
        )


def test_verify_snapshot_rejects_hash_and_extra_wheel_drift(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshot"
    runtime_wheels = snapshot_root / "runtime-wheels"
    support_wheels = snapshot_root / "support-wheels"
    runtime_wheels.mkdir(parents=True)
    support_wheels.mkdir()
    runtime_path = runtime_wheels / "example-1.0-py3-none-any.whl"
    support_path = support_wheels / "pip-26.1-py3-none-any.whl"
    runtime_path.write_bytes(b"runtime")
    support_path.write_bytes(b"support")

    fragment = _fragment(
        "linux-x86_64-cp311",
        digest=module._sha256(runtime_path),
    )
    fragment["support_wheels"] = [_record("pip", "26.1", module._sha256(support_path))]
    manifest = _merge(tmp_path / "manifest", fragment)
    args = argparse.Namespace(
        manifest=manifest,
        target="linux-x86_64-cp311",
        snapshot_root=snapshot_root,
    )

    assert module.verify_snapshot(args) == 0

    runtime_path.write_bytes(b"tampered")
    with pytest.raises(module.SnapshotError, match="hash mismatch"):
        module.verify_snapshot(args)

    runtime_path.write_bytes(b"runtime")
    (runtime_wheels / "extra-1.0-py3-none-any.whl").write_bytes(b"extra")
    with pytest.raises(module.SnapshotError, match="wheel set mismatch"):
        module.verify_snapshot(args)


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


def test_resolve_rejects_target_mismatch_before_running_pip(tmp_path: Path) -> None:
    requested = "windows-x86_64-cp399"
    args = argparse.Namespace(
        project_root=REPO_ROOT,
        output_dir=tmp_path / "snapshot",
        target=requested,
        source_tag="v3.1.3",
        source_sha="1" * 40,
    )

    with pytest.raises(module.SnapshotError, match="Resolver target mismatch"):
        module.resolve_snapshot(args)


def test_resolve_downloads_full_runtime_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []
    _project_name, project_version = module._project_metadata(REPO_ROOT)
    project_wheel = f"paper_fetch_skill-{project_version}-py3-none-any.whl"

    def fake_run(command: list[str], *, cwd: Path | None = None) -> None:
        del cwd
        commands.append(command)
        if "wheel" in command and "--no-deps" in command:
            destination = Path(command[command.index("--wheel-dir") + 1])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / project_wheel).write_bytes(b"project")
            return
        destination = Path(command[command.index("--dest") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        if destination.name == "support-wheels":
            (destination / "pip-26.1.2-py3-none-any.whl").write_bytes(b"pip")
            (destination / "setuptools-80.9.0-py3-none-any.whl").write_bytes(
                b"setuptools"
            )
            (destination / "wheel-0.46.1-py3-none-any.whl").write_bytes(b"wheel")
        else:
            (destination / project_wheel).write_bytes(b"project")
            (destination / "camoufox-0.5.4-py3-none-any.whl").write_bytes(b"camoufox")

    monkeypatch.setattr(module, "_run", fake_run)
    target = f"{module._host_platform()}-{module._host_arch()}-{module._python_tag()}"

    assert (
        module.resolve_snapshot(
            argparse.Namespace(
                project_root=REPO_ROOT,
                output_dir=tmp_path / "snapshot",
                target=target,
                source_tag=f"v{project_version}",
                source_sha="1" * 40,
            )
        )
        == 0
    )

    runtime_download = next(
        command
        for command in commands
        if "download" in command and command[-1].endswith("[full]")
    )
    assert runtime_download[-1].endswith(f"{project_wheel}[full]")
