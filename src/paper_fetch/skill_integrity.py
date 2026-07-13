"""Build and verify the static skill bundle file manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any


SKILL_BUNDLE_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class SkillManifestError(ValueError):
    """Raised when a skill manifest is missing or structurally unsafe."""


def sha256_file(path: Path) -> str:
    """Return a streaming SHA256 digest for one regular file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if (
        not text
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise SkillManifestError(f"unsafe skill manifest path: {value!r}")
    return path.as_posix()


def _skill_files(skill_dir: Path) -> list[Path]:
    if not skill_dir.is_dir():
        raise SkillManifestError(f"skill directory does not exist: {skill_dir}")
    symlinks = sorted(
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_symlink()
    )
    if symlinks:
        raise SkillManifestError(
            "skill bundle must not contain symbolic links: " + ", ".join(symlinks)
        )
    return sorted(path for path in skill_dir.rglob("*") if path.is_file())


def build_skill_bundle_manifest(
    skill_dir: Path,
    *,
    name: str,
    root: str,
) -> dict[str, Any]:
    """Build the canonical complete file list for a staged skill directory."""

    safe_root = _safe_relative_path(root)
    files = [
        {
            "path": path.relative_to(skill_dir).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in _skill_files(skill_dir)
    ]
    if not files:
        raise SkillManifestError(f"skill directory is empty: {skill_dir}")
    if not any(item["path"] == "SKILL.md" for item in files):
        raise SkillManifestError(f"skill directory is missing SKILL.md: {skill_dir}")
    return {
        "schema_version": SKILL_BUNDLE_SCHEMA_VERSION,
        "name": str(name),
        "root": safe_root,
        "files": files,
    }


def _manifest_skill_bundle(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    value = manifest.get("skill_bundle")
    if not isinstance(value, Mapping):
        raise SkillManifestError("offline manifest is missing skill_bundle")
    if value.get("schema_version") != SKILL_BUNDLE_SCHEMA_VERSION:
        raise SkillManifestError(
            f"unsupported skill_bundle schema_version: {value.get('schema_version')!r}"
        )
    if not str(value.get("name") or "").strip():
        raise SkillManifestError("skill_bundle is missing name")
    _safe_relative_path(value.get("root"))
    if not isinstance(value.get("files"), list) or not value["files"]:
        raise SkillManifestError("skill_bundle is missing files")
    return value


def read_offline_manifest(path: Path) -> dict[str, Any]:
    """Read an offline manifest as a JSON object."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise SkillManifestError(
            f"cannot read offline manifest {path}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise SkillManifestError(
            f"invalid offline manifest JSON {path}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise SkillManifestError(f"offline manifest must contain an object: {path}")
    return payload


def _expected_files(skill_bundle: Mapping[str, Any]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for index, item in enumerate(skill_bundle["files"]):
        if not isinstance(item, Mapping):
            raise SkillManifestError(f"skill_bundle.files[{index}] must be an object")
        relative = _safe_relative_path(item.get("path"))
        digest = str(item.get("sha256") or "").strip().lower()
        if not _SHA256_RE.fullmatch(digest):
            raise SkillManifestError(
                f"skill_bundle.files[{index}] has an invalid sha256"
            )
        if relative in expected:
            raise SkillManifestError(f"duplicate skill manifest path: {relative}")
        expected[relative] = digest
    if "SKILL.md" not in expected:
        raise SkillManifestError("skill_bundle.files is missing SKILL.md")
    return expected


def verify_skill_bundle(
    manifest_path: Path,
    *,
    skill_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify an exact skill directory against an offline manifest."""

    manifest_path = manifest_path.expanduser().resolve()
    manifest = read_offline_manifest(manifest_path)
    skill_bundle = _manifest_skill_bundle(manifest)
    expected = _expected_files(skill_bundle)
    if skill_dir is None:
        skill_dir = manifest_path.parent / _safe_relative_path(skill_bundle["root"])
    skill_dir = skill_dir.expanduser().resolve()

    missing_files: list[str] = []
    hash_mismatches: list[dict[str, str]] = []
    symlink_files: list[str] = []
    actual_paths: set[str] = set()
    if skill_dir.is_dir():
        for path in sorted(skill_dir.rglob("*")):
            relative = path.relative_to(skill_dir).as_posix()
            if path.is_symlink():
                symlink_files.append(relative)
                continue
            if path.is_file():
                actual_paths.add(relative)
    else:
        missing_files.extend(sorted(expected))

    for relative, expected_digest in expected.items():
        path = skill_dir / relative
        if relative not in actual_paths:
            if relative not in missing_files:
                missing_files.append(relative)
            continue
        actual_digest = sha256_file(path)
        if actual_digest != expected_digest:
            hash_mismatches.append(
                {
                    "path": relative,
                    "expected_sha256": expected_digest,
                    "actual_sha256": actual_digest,
                }
            )

    unexpected_files = sorted(actual_paths - set(expected))
    missing_files.sort()
    ready = not (missing_files or hash_mismatches or unexpected_files or symlink_files)
    return {
        "status": "ready" if ready else "drift",
        "reason_code": (
            "skill_bundle_verified" if ready else "skill_bundle_integrity_drift"
        ),
        "manifest_path": str(manifest_path),
        "skill_root": str(skill_dir),
        "skill_name": str(skill_bundle["name"]),
        "expected_file_count": len(expected),
        "actual_file_count": len(actual_paths),
        "verified_file_count": len(expected)
        - len(missing_files)
        - len(hash_mismatches),
        "missing_files": missing_files,
        "unexpected_files": unexpected_files,
        "symlink_files": symlink_files,
        "hash_mismatches": hash_mismatches,
    }


def require_valid_skill_bundle(
    manifest_path: Path,
    *,
    skill_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify a skill directory and raise a concise error on any drift."""

    result = verify_skill_bundle(manifest_path, skill_dir=skill_dir)
    if result["status"] != "ready":
        details: list[str] = []
        for key in ("missing_files", "unexpected_files", "symlink_files"):
            values = result[key]
            if values:
                details.append(f"{key}={','.join(values)}")
        mismatches = result["hash_mismatches"]
        if mismatches:
            details.append(
                "hash_mismatches=" + ",".join(str(item["path"]) for item in mismatches)
            )
        raise SkillManifestError(
            f"skill bundle integrity check failed at {result['skill_root']}: "
            + "; ".join(details)
        )
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a skill bundle manifest.")
    build.add_argument("--skill-dir", required=True, type=Path)
    build.add_argument("--name", required=True)
    build.add_argument("--root", required=True)

    verify = subparsers.add_parser("verify", help="Verify a skill bundle manifest.")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--skill-dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_skill_bundle_manifest(
                args.skill_dir,
                name=args.name,
                root=args.root,
            )
        else:
            result = require_valid_skill_bundle(
                args.manifest,
                skill_dir=args.skill_dir,
            )
    except SkillManifestError as error:
        sys.stderr.write(f"{error}\n")
        return 2
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SKILL_BUNDLE_SCHEMA_VERSION",
    "SkillManifestError",
    "build_skill_bundle_manifest",
    "main",
    "read_offline_manifest",
    "require_valid_skill_bundle",
    "sha256_file",
    "verify_skill_bundle",
]
