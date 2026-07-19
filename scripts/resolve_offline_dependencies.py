#!/usr/bin/env python3
"""Resolve, inventory, merge, compare, and verify offline wheel snapshots."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from typing import Any

from packaging.utils import canonicalize_name, parse_wheel_filename


SCHEMA_VERSION = 1
SUPPORT_REQUIREMENTS = ("pip", "setuptools", "wheel")


class SnapshotError(RuntimeError):
    """Raised when a dependency snapshot is incomplete or inconsistent."""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _dependency_digest(payload: dict[str, Any]) -> str:
    stable_payload = {
        "source": payload["source"],
        "targets": {
            key: {
                "platform": target["platform"],
                "arch": target["arch"],
                "python_tag": target["python_tag"],
                "dependencies": target["dependencies"],
            }
            for key, target in sorted(payload["targets"].items())
        },
    }
    return hashlib.sha256(_canonical_json(stable_payload)).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"Cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SnapshotError(f"Expected a JSON object in {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _project_metadata(project_root: Path) -> tuple[str, str]:
    pyproject = project_root / "pyproject.toml"
    try:
        payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = payload["project"]
        name = canonicalize_name(str(project["name"]))
        version = str(project["version"])
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise SnapshotError(
            f"Cannot read project metadata from {pyproject}: {exc}"
        ) from exc
    if not name or not version:
        raise SnapshotError(f"Project name/version is empty in {pyproject}")
    return name, version


def _host_platform() -> str:
    value = platform.system().lower()
    mapping = {"darwin": "macos", "linux": "linux", "windows": "windows"}
    try:
        return mapping[value]
    except KeyError as exc:
        raise SnapshotError(
            f"Unsupported resolver platform: {platform.system()}"
        ) from exc


def _host_arch() -> str:
    value = platform.machine().lower()
    if value in {"amd64", "x86_64"}:
        return "x86_64"
    if value in {"aarch64", "arm64"}:
        return "arm64"
    raise SnapshotError(f"Unsupported resolver architecture: {platform.machine()}")


def _python_tag() -> str:
    if sys.implementation.name != "cpython":
        raise SnapshotError("Offline dependency snapshots require CPython")
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SnapshotError(
            f"Command failed with exit code {completed.returncode}: "
            + " ".join(command)
        )


def _wheel_record(path: Path) -> dict[str, str]:
    try:
        distribution, version, _build, _tags = parse_wheel_filename(path.name)
    except ValueError as exc:
        raise SnapshotError(f"Invalid wheel filename {path.name}: {exc}") from exc
    return {
        "name": canonicalize_name(str(distribution)),
        "version": str(version),
        "filename": path.name,
        "sha256": _sha256(path),
    }


def _wheel_records(directory: Path) -> list[dict[str, str]]:
    records = [_wheel_record(path) for path in sorted(directory.glob("*.whl"))]
    seen: dict[str, str] = {}
    for record in records:
        previous = seen.get(record["name"])
        if previous is not None:
            raise SnapshotError(
                f"Wheel snapshot contains duplicate distribution {record['name']}: "
                f"{previous}, {record['filename']}"
            )
        seen[record["name"]] = record["filename"]
    return sorted(records, key=lambda item: (item["name"], item["filename"]))


def _validate_fragment(value: dict[str, Any], *, source: Path) -> None:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotError(
            f"Unsupported dependency snapshot schema in {source}: "
            f"{value.get('schema_version')!r}"
        )
    if not isinstance(value.get("source"), dict):
        raise SnapshotError(f"Snapshot source is missing in {source}")
    target = value.get("target")
    if not isinstance(target, dict) or not target.get("key"):
        raise SnapshotError(f"Snapshot target is missing in {source}")
    for key in ("dependencies", "support_wheels"):
        records = value.get(key)
        if not isinstance(records, list):
            raise SnapshotError(f"Snapshot {key} is missing in {source}")


def resolve_snapshot(args: argparse.Namespace) -> int:
    project_root = args.project_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SnapshotError(
            f"Refusing to overwrite non-empty output directory: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    actual_platform = _host_platform()
    actual_arch = _host_arch()
    actual_python_tag = _python_tag()
    actual_target = f"{actual_platform}-{actual_arch}-{actual_python_tag}"
    if args.target != actual_target:
        raise SnapshotError(
            f"Resolver target mismatch: requested {args.target}, running on {actual_target}"
        )

    project_name, project_version = _project_metadata(project_root)
    runtime_wheels = output_dir / "runtime-wheels"
    support_wheels = output_dir / "support-wheels"
    runtime_wheels.mkdir()
    support_wheels.mkdir()

    with tempfile.TemporaryDirectory(prefix="paper-fetch-project-wheel-") as tmpdir:
        project_dist = Path(tmpdir)
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(project_dist),
                str(project_root),
            ]
        )
        project_wheels = sorted(project_dist.glob("*.whl"))
        if len(project_wheels) != 1:
            raise SnapshotError(
                f"Expected one project wheel for {project_name}, found {len(project_wheels)}"
            )
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(runtime_wheels),
                "--only-binary=:all:",
                str(project_wheels[0]),
            ]
        )

    downloaded_project_wheels = [
        wheel
        for wheel in runtime_wheels.glob("*.whl")
        if _wheel_record(wheel)["name"] == project_name
    ]
    if len(downloaded_project_wheels) != 1:
        raise SnapshotError(
            "Resolved wheelhouse must contain exactly one project wheel; "
            f"found {len(downloaded_project_wheels)}"
        )
    downloaded_project_wheels[0].unlink()

    constraints = output_dir / "runtime-constraints.txt"
    dependency_records = _wheel_records(runtime_wheels)
    constraints.write_text(
        "".join(
            f"{record['name']}=={record['version']}\n" for record in dependency_records
        ),
        encoding="utf-8",
    )
    support_command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(support_wheels),
        "--only-binary=:all:",
    ]
    if dependency_records:
        support_command.extend(["--constraint", str(constraints)])
    support_command.extend(SUPPORT_REQUIREMENTS)
    _run(support_command)

    support_records = _wheel_records(support_wheels)
    runtime_versions = {
        record["name"]: record["version"] for record in dependency_records
    }
    for record in support_records:
        runtime_version = runtime_versions.get(record["name"])
        if runtime_version is not None and runtime_version != record["version"]:
            raise SnapshotError(
                f"Build support wheel {record['name']}=={record['version']} conflicts "
                f"with runtime dependency {runtime_version}"
            )

    fragment = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "source": {
            "tag": args.source_tag,
            "commit": args.source_sha,
            "project_name": project_name,
            "project_version": project_version,
        },
        "target": {
            "key": args.target,
            "platform": actual_platform,
            "arch": actual_arch,
            "python_tag": actual_python_tag,
        },
        "dependencies": dependency_records,
        "support_wheels": support_records,
    }
    _write_json(output_dir / "fragment.json", fragment)
    return 0


def merge_snapshots(args: argparse.Namespace) -> int:
    fragments: list[tuple[Path, dict[str, Any]]] = []
    for path in args.fragment:
        resolved = path.expanduser().resolve()
        value = _load_json(resolved)
        _validate_fragment(value, source=resolved)
        fragments.append((resolved, value))
    if not fragments:
        raise SnapshotError("At least one dependency fragment is required")

    source = fragments[0][1]["source"]
    targets: dict[str, dict[str, Any]] = {}
    for path, fragment in fragments:
        if fragment["source"] != source:
            raise SnapshotError(f"Source metadata differs in {path}")
        target = fragment["target"]
        key = str(target["key"])
        if key in targets:
            raise SnapshotError(f"Duplicate dependency target: {key}")
        targets[key] = {
            "platform": target["platform"],
            "arch": target["arch"],
            "python_tag": target["python_tag"],
            "dependencies": fragment["dependencies"],
            "support_wheels": fragment["support_wheels"],
        }

    expected = set(args.expected_target)
    actual = set(targets)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise SnapshotError(
            f"Dependency target set mismatch; missing={missing}, extra={extra}"
        )

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "source": source,
        "targets": {key: targets[key] for key in sorted(targets)},
    }
    manifest["dependency_set_sha256"] = _dependency_digest(manifest)
    _write_json(args.output.expanduser().resolve(), manifest)
    return 0


def _validate_manifest(value: dict[str, Any], *, source: Path) -> None:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotError(
            f"Unsupported dependency manifest schema in {source}: "
            f"{value.get('schema_version')!r}"
        )
    if not isinstance(value.get("source"), dict) or not isinstance(
        value.get("targets"), dict
    ):
        raise SnapshotError(f"Dependency manifest is incomplete: {source}")
    try:
        expected_digest = _dependency_digest(value)
    except (AttributeError, KeyError, TypeError) as exc:
        raise SnapshotError(f"Dependency manifest is malformed: {source}") from exc
    if value.get("dependency_set_sha256") != expected_digest:
        raise SnapshotError(
            f"Dependency manifest digest mismatch in {source}: expected {expected_digest}"
        )


def compare_snapshots(args: argparse.Namespace) -> int:
    candidate_path = args.candidate.expanduser().resolve()
    candidate = _load_json(candidate_path)
    _validate_manifest(candidate, source=candidate_path)

    baseline_path = args.baseline.expanduser().resolve()
    if args.force:
        changed = True
        reason = "forced_refresh"
    elif not baseline_path.is_file():
        changed = True
        reason = "baseline_missing"
    else:
        try:
            baseline = _load_json(baseline_path)
            _validate_manifest(baseline, source=baseline_path)
        except SnapshotError as exc:
            print(f"Ignoring invalid dependency baseline: {exc}", file=sys.stderr)
            changed = True
            reason = "baseline_invalid"
        else:
            changed = (
                candidate["dependency_set_sha256"] != baseline["dependency_set_sha256"]
            )
            reason = "dependency_set_changed" if changed else "unchanged"

    result = {
        "changed": changed,
        "reason": reason,
        "dependency_set_sha256": candidate["dependency_set_sha256"],
        "source_tag": candidate["source"]["tag"],
        "source_sha": candidate["source"]["commit"],
        "project_version": candidate["source"]["project_version"],
    }
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as handle:
            for key, value in result.items():
                rendered = str(value).lower() if isinstance(value, bool) else str(value)
                handle.write(f"{key}={rendered}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _records_by_filename(records: object, *, label: str) -> dict[str, dict[str, str]]:
    if not isinstance(records, list):
        raise SnapshotError(f"Manifest {label} must be a list")
    result: dict[str, dict[str, str]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("filename"), str):
            raise SnapshotError(f"Manifest {label} contains an invalid wheel record")
        result[record["filename"]] = record
    return result


def _verify_wheel_directory(
    directory: Path,
    expected_records: object,
    *,
    label: str,
) -> None:
    expected = _records_by_filename(expected_records, label=label)
    actual_paths = {path.name: path for path in directory.glob("*.whl")}
    if set(actual_paths) != set(expected):
        raise SnapshotError(
            f"{label} wheel set mismatch; "
            f"missing={sorted(set(expected) - set(actual_paths))}, "
            f"extra={sorted(set(actual_paths) - set(expected))}"
        )
    for filename, record in expected.items():
        digest = _sha256(actual_paths[filename])
        if digest != record.get("sha256"):
            raise SnapshotError(
                f"{label} wheel hash mismatch for {filename}: "
                f"expected {record.get('sha256')}, got {digest}"
            )


def verify_snapshot(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.expanduser().resolve()
    manifest = _load_json(manifest_path)
    _validate_manifest(manifest, source=manifest_path)
    target = manifest["targets"].get(args.target)
    if not isinstance(target, dict):
        raise SnapshotError(f"Target {args.target!r} is absent from {manifest_path}")

    snapshot_root = args.snapshot_root.expanduser().resolve()
    _verify_wheel_directory(
        snapshot_root / "runtime-wheels",
        target.get("dependencies"),
        label="runtime",
    )
    _verify_wheel_directory(
        snapshot_root / "support-wheels",
        target.get("support_wheels"),
        label="support",
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve", help="Resolve one platform/ABI snapshot")
    resolve.add_argument("--project-root", type=Path, required=True)
    resolve.add_argument("--output-dir", type=Path, required=True)
    resolve.add_argument("--target", required=True)
    resolve.add_argument("--source-tag", required=True)
    resolve.add_argument("--source-sha", required=True)
    resolve.set_defaults(handler=resolve_snapshot)

    merge = subparsers.add_parser("merge", help="Merge target fragments")
    merge.add_argument("--fragment", type=Path, nargs="+", required=True)
    merge.add_argument("--expected-target", nargs="+", required=True)
    merge.add_argument("--output", type=Path, required=True)
    merge.set_defaults(handler=merge_snapshots)

    compare = subparsers.add_parser("compare", help="Compare candidate and baseline")
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--github-output", type=Path)
    compare.add_argument("--force", action="store_true")
    compare.set_defaults(handler=compare_snapshots)

    verify = subparsers.add_parser("verify", help="Verify a frozen target wheelhouse")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--target", required=True)
    verify.add_argument("--snapshot-root", type=Path, required=True)
    verify.set_defaults(handler=verify_snapshot)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except SnapshotError as exc:
        print(f"dependency snapshot error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
