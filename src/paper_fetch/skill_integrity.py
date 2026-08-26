"""Build and verify the static skill bundle file manifest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any


SKILL_BUNDLE_SCHEMA_VERSION = 2
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


@dataclass(frozen=True)
class _SkillInventory:
    regular_files: tuple[Path, ...]
    symlink_files: tuple[str, ...]
    special_files: tuple[str, ...]


def _inspect_skill_dir(skill_dir: Path) -> _SkillInventory:
    regular_files: list[Path] = []
    symlink_files: list[str] = []
    special_files: list[str] = []
    if skill_dir.is_symlink():
        return _SkillInventory((), (".",), ())
    if not skill_dir.is_dir():
        return _SkillInventory((), (), ())

    def walk(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            raise SkillManifestError(
                f"cannot inspect skill directory {directory}: {error}"
            ) from error
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(skill_dir).as_posix()
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as error:
                raise SkillManifestError(
                    f"cannot inspect skill path {path}: {error}"
                ) from error
            if stat.S_ISLNK(mode):
                symlink_files.append(relative)
            elif stat.S_ISDIR(mode):
                walk(path)
            elif stat.S_ISREG(mode):
                regular_files.append(path)
            else:
                special_files.append(relative)

    walk(skill_dir)
    return _SkillInventory(
        tuple(regular_files),
        tuple(symlink_files),
        tuple(special_files),
    )


def _bundle_content_sha256(files: Mapping[str, str]) -> str:
    canonical = [
        {"path": path, "sha256": digest} for path, digest in sorted(files.items())
    ]
    return hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _build_file_digests(skill_dir: Path) -> dict[str, str]:
    inventory = _inspect_skill_dir(skill_dir)
    if not skill_dir.is_dir():
        raise SkillManifestError(f"skill directory does not exist: {skill_dir}")
    if inventory.symlink_files:
        raise SkillManifestError(
            "skill bundle must not contain symbolic links: "
            + ", ".join(inventory.symlink_files)
        )
    if inventory.special_files:
        raise SkillManifestError(
            "skill bundle must contain only regular files: "
            + ", ".join(inventory.special_files)
        )
    return {
        path.relative_to(skill_dir).as_posix(): sha256_file(path)
        for path in inventory.regular_files
    }


def build_skill_bundle_manifest(
    skill_dir: Path,
    *,
    name: str,
    root: str,
) -> dict[str, Any]:
    """Build the canonical complete file list for a staged skill directory."""

    safe_root = _safe_relative_path(root)
    file_digests = _build_file_digests(skill_dir)
    files = [
        {"path": path, "sha256": digest}
        for path, digest in sorted(file_digests.items())
    ]
    if not files:
        raise SkillManifestError(f"skill directory is empty: {skill_dir}")
    if not any(item["path"] == "SKILL.md" for item in files):
        raise SkillManifestError(f"skill directory is missing SKILL.md: {skill_dir}")
    content_sha256 = _bundle_content_sha256(file_digests)
    return {
        "schema_version": SKILL_BUNDLE_SCHEMA_VERSION,
        "name": str(name),
        "root": safe_root,
        "content_sha256": content_sha256,
        "content_version": f"sha256:{content_sha256}",
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
    expected_content_sha256 = _bundle_content_sha256(expected)
    declared_content_sha256 = (
        str(skill_bundle.get("content_sha256") or "").strip().lower()
    )
    declared_content_version = str(skill_bundle.get("content_version") or "").strip()
    if declared_content_sha256 != expected_content_sha256:
        raise SkillManifestError("skill_bundle content_sha256 does not match files")
    if declared_content_version != f"sha256:{expected_content_sha256}":
        raise SkillManifestError("skill_bundle content_version does not match files")
    return expected


def verify_skill_directory(
    skill_bundle: Mapping[str, Any],
    *,
    skill_dir: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Verify one directory against a validated content-addressed definition."""

    expected = _expected_files(skill_bundle)
    skill_dir = Path(os.path.abspath(skill_dir.expanduser()))
    inventory = _inspect_skill_dir(skill_dir)
    actual_paths = {
        path.relative_to(skill_dir).as_posix() for path in inventory.regular_files
    }
    missing_files = sorted(set(expected) - actual_paths)
    unexpected_files = sorted(actual_paths - set(expected))
    hash_mismatches: list[dict[str, str]] = []
    actual_digests: dict[str, str] = {}
    for relative in sorted(actual_paths):
        digest = sha256_file(skill_dir / relative)
        actual_digests[relative] = digest
        expected_digest = expected.get(relative)
        if expected_digest is not None and digest != expected_digest:
            hash_mismatches.append(
                {
                    "path": relative,
                    "expected_sha256": expected_digest,
                    "actual_sha256": digest,
                }
            )
    ready = not (
        missing_files
        or hash_mismatches
        or unexpected_files
        or inventory.symlink_files
        or inventory.special_files
    )
    expected_content_sha256 = str(skill_bundle["content_sha256"])
    actual_content_sha256 = _bundle_content_sha256(actual_digests)
    if not skill_dir.is_dir():
        reason_code = "skill_bundle_missing"
    elif ready:
        reason_code = "skill_bundle_verified"
    else:
        reason_code = "skill_bundle_integrity_drift"
    return {
        "status": "ready" if ready else "drift",
        "reason_code": reason_code,
        "manifest_path": str(manifest_path) if manifest_path is not None else None,
        "skill_root": str(skill_dir),
        "skill_name": str(skill_bundle["name"]),
        "expected_content_sha256": expected_content_sha256,
        "expected_content_version": str(skill_bundle["content_version"]),
        "actual_content_sha256": actual_content_sha256,
        "actual_content_version": f"sha256:{actual_content_sha256}",
        "expected_file_count": len(expected),
        "actual_file_count": len(actual_paths),
        "verified_file_count": len(expected)
        - len(missing_files)
        - len(hash_mismatches),
        "missing_files": missing_files,
        "unexpected_files": unexpected_files,
        "symlink_files": list(inventory.symlink_files),
        "special_files": list(inventory.special_files),
        "hash_mismatches": hash_mismatches,
    }


def compare_skill_directories(
    expected_dir: Path,
    actual_dir: Path,
    *,
    name: str = "paper-fetch-skill",
) -> dict[str, Any]:
    """Compare source/staging/host directories with the manifest verifier."""

    bundle = build_skill_bundle_manifest(
        Path(os.path.abspath(expected_dir.expanduser())),
        name=name,
        root=f"skills/{name}",
    )
    return verify_skill_directory(bundle, skill_dir=actual_dir)


def verify_skill_bundle(
    manifest_path: Path,
    *,
    skill_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify an exact skill directory against an offline manifest."""

    manifest_path = manifest_path.expanduser().resolve()
    manifest = read_offline_manifest(manifest_path)
    skill_bundle = _manifest_skill_bundle(manifest)
    if skill_dir is None:
        skill_dir = manifest_path.parent / _safe_relative_path(skill_bundle["root"])
    return verify_skill_directory(
        skill_bundle,
        skill_dir=skill_dir,
        manifest_path=manifest_path,
    )


def require_valid_skill_bundle(
    manifest_path: Path,
    *,
    skill_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify a skill directory and raise a concise error on any drift."""

    result = verify_skill_bundle(manifest_path, skill_dir=skill_dir)
    if result["status"] != "ready":
        details: list[str] = []
        for key in (
            "missing_files",
            "unexpected_files",
            "symlink_files",
            "special_files",
        ):
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

    compare = subparsers.add_parser(
        "compare",
        help="Compare an installed skill with the repository source bundle.",
    )
    compare.add_argument("--expected-dir", required=True, type=Path)
    compare.add_argument("--skill-dir", required=True, type=Path)
    compare.add_argument("--name", default="paper-fetch-skill")
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
        elif args.command == "verify":
            result = require_valid_skill_bundle(
                args.manifest,
                skill_dir=args.skill_dir,
            )
        else:
            result = compare_skill_directories(
                args.expected_dir,
                args.skill_dir,
                name=args.name,
            )
    except SkillManifestError as error:
        sys.stderr.write(f"{error}\n")
        return 2
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    if args.command == "compare" and result.get("status") != "ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SKILL_BUNDLE_SCHEMA_VERSION",
    "SkillManifestError",
    "build_skill_bundle_manifest",
    "compare_skill_directories",
    "main",
    "read_offline_manifest",
    "require_valid_skill_bundle",
    "sha256_file",
    "verify_skill_bundle",
    "verify_skill_directory",
]
