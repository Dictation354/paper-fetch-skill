#!/usr/bin/env python3
"""Validate and flatten stable release assets before publication.

The release uses a flat GitHub asset namespace. This module keeps that
namespace explicit, rejects missing/extra/colliding inputs, and writes a
basename-only ``SHA256SUMS`` that remains usable after download.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
from collections.abc import Iterable
from pathlib import Path


TARGET_ARTIFACTS = (
    (
        "linux-x86_64-cp311",
        "offline-Linux-3.11",
        "paper-fetch-skill-offline-linux-x86_64-cp311.sh",
    ),
    (
        "linux-x86_64-cp312",
        "offline-Linux-3.12",
        "paper-fetch-skill-offline-linux-x86_64-cp312.sh",
    ),
    (
        "linux-x86_64-cp313",
        "offline-Linux-3.13",
        "paper-fetch-skill-offline-linux-x86_64-cp313.sh",
    ),
    (
        "linux-x86_64-cp314",
        "offline-Linux-3.14",
        "paper-fetch-skill-offline-linux-x86_64-cp314.sh",
    ),
    (
        "macos-arm64-cp311",
        "offline-macOS-3.11",
        "paper-fetch-skill-offline-macos-arm64-cp311.tar.gz",
    ),
    (
        "macos-arm64-cp312",
        "offline-macOS-3.12",
        "paper-fetch-skill-offline-macos-arm64-cp312.tar.gz",
    ),
    (
        "macos-arm64-cp313",
        "offline-macOS-3.13",
        "paper-fetch-skill-offline-macos-arm64-cp313.tar.gz",
    ),
    (
        "macos-arm64-cp314",
        "offline-macOS-3.14",
        "paper-fetch-skill-offline-macos-arm64-cp314.tar.gz",
    ),
    (
        "windows-x86_64-cp313",
        "offline-Windows-3.13",
        "paper-fetch-skill-windows-x86_64-setup.exe",
    ),
)


def installer_asset_names() -> frozenset[str]:
    return frozenset(installer for _target, _artifact, installer in TARGET_ARTIFACTS)


def target_evidence_names() -> frozenset[str]:
    return frozenset(
        {
            f"paper-fetch-evidence-{target}.{suffix}"
            for target, _artifact, _installer in TARGET_ARTIFACTS
            for suffix in ("dependency-manifest.json", "sbom.cdx.json")
        }
    )


def stable_asset_names(version: str) -> frozenset[str]:
    normalized_version = version.strip()
    if (
        not normalized_version
        or "/" in normalized_version
        or "\\" in normalized_version
    ):
        raise ValueError(f"Invalid project version: {version!r}")
    return installer_asset_names()


def stable_input_names(version: str) -> frozenset[str]:
    normalized_version = version.strip()
    python_assets = {
        f"paper_fetch_skill-{normalized_version}-py3-none-any.whl",
        f"paper_fetch_skill-{normalized_version}.tar.gz",
    }
    return frozenset(
        {
            "dependency-manifest.json",
            *installer_asset_names(),
            *target_evidence_names(),
            *python_assets,
        }
    )


def stable_input_mapping(version: str) -> dict[Path, str]:
    normalized_version = version.strip()
    mapping = {
        Path("python", f"paper_fetch_skill-{normalized_version}-py3-none-any.whl"): (
            f"paper_fetch_skill-{normalized_version}-py3-none-any.whl"
        ),
        Path("python", f"paper_fetch_skill-{normalized_version}.tar.gz"): (
            f"paper_fetch_skill-{normalized_version}.tar.gz"
        ),
        Path("dependencies", "dependency-manifest.json"): ("dependency-manifest.json"),
    }
    for target, artifact, installer in TARGET_ARTIFACTS:
        mapping[Path("offline", artifact, installer)] = installer
        for suffix in ("dependency-manifest.json", "sbom.cdx.json"):
            evidence = f"paper-fetch-evidence-{target}.{suffix}"
            mapping[Path("offline", artifact, evidence)] = evidence
    expected = stable_input_names(version)
    if set(mapping.values()) != set(expected):
        raise AssertionError(
            "Stable release source mapping drifted from asset inventory"
        )
    return mapping


def _format_set_difference(
    expected: set[str] | frozenset[str], actual: set[str]
) -> str:
    return (
        f"missing={sorted(set(expected) - actual)!r}, "
        f"extra={sorted(actual - set(expected))!r}"
    )


def _regular_files(root: Path) -> dict[Path, Path]:
    if not root.is_dir():
        raise ValueError(f"Release asset input is not a directory: {root}")
    files: dict[Path, Path] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"Release asset input must not be a symlink: {relative}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"Release asset input must be a regular file: {relative}")
        files[relative] = path
    return files


def _assert_unique_basenames(relative_paths: Iterable[Path]) -> None:
    owners: dict[str, Path] = {}
    for relative in relative_paths:
        owner = owners.setdefault(relative.name, relative)
        if owner != relative:
            raise ValueError(
                "Release assets have a basename collision: "
                f"{relative.name!r} is provided by {owner} and {relative}"
            )


def _copy_exclusive(source: Path, destination: Path) -> None:
    source_mode = source.stat().st_mode
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            descriptor = -1
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(destination, stat.S_IMODE(source_mode))
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        destination.unlink(missing_ok=True)
        raise


def _fsync_directory_best_effort(directory: Path) -> bool:
    """Persist directory entries where the host exposes POSIX directory fsync."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        directory_fd = os.open(directory, flags)
    except OSError:
        return False
    try:
        os.fsync(directory_fd)
    except OSError:
        return False
    finally:
        os.close(directory_fd)
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(asset_dir: Path, expected: frozenset[str]) -> Path:
    files = _regular_files(asset_dir)
    actual = {str(relative) for relative in files}
    if actual != set(expected):
        raise ValueError(
            "Release asset directory is not the exact expected set: "
            + _format_set_difference(expected, actual)
        )
    if any(relative.parent != Path(".") for relative in files):
        raise ValueError("Release assets must use a flat basename-only namespace")

    checksum_path = asset_dir / "SHA256SUMS"
    descriptor = os.open(
        checksum_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            for name in sorted(expected):
                handle.write(f"{_sha256(asset_dir / name)}  {name}\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        checksum_path.unlink(missing_ok=True)
        raise
    return checksum_path


def prepare_stable_release(
    *, input_root: Path, output_dir: Path, version: str
) -> frozenset[str]:
    source_files = _regular_files(input_root)
    _assert_unique_basenames(source_files)
    expected_mapping = stable_input_mapping(version)
    actual = {str(relative) for relative in source_files}
    expected = {str(relative) for relative in expected_mapping}
    if actual != expected:
        raise ValueError(
            "Stable release inputs are not the exact expected nested set: "
            + _format_set_difference(expected, actual)
        )
    if output_dir.exists():
        raise ValueError(f"Release output directory already exists: {output_dir}")

    output_dir.mkdir(parents=True, mode=0o755)
    try:
        public_names = stable_asset_names(version)
        for relative, basename in sorted(
            expected_mapping.items(), key=lambda item: item[1]
        ):
            if basename in public_names:
                _copy_exclusive(source_files[relative], output_dir / basename)
        expected_names = public_names
        write_checksums(output_dir, expected_names)
        _fsync_directory_best_effort(output_dir)
    except BaseException:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    return expected_names


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    stable = subparsers.add_parser(
        "prepare-stable",
        help="validate nested stable inputs, flatten them, and write SHA256SUMS",
    )
    stable.add_argument("--input-root", type=Path, required=True)
    stable.add_argument("--output-dir", type=Path, required=True)
    stable.add_argument("--version", required=True)

    return parser


def main() -> int:
    args = _parser().parse_args()
    expected = prepare_stable_release(
        input_root=args.input_root,
        output_dir=args.output_dir,
        version=args.version,
    )
    print(f"Validated {len(expected)} release assets and wrote SHA256SUMS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
