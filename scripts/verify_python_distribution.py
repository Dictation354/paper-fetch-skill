#!/usr/bin/env python3
"""Verify the complete, exact inventory of wheel and sdist artifacts."""

from __future__ import annotations

import argparse
import base64
from configparser import ConfigParser
import csv
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
from typing import Any
import zipfile

from packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import Version


_PACKAGE_DATA_SUFFIXES = {".json", ".mjs", ".pyi"}
_FORBIDDEN_PARTS = {"__pycache__", "node_modules", "paper_fetch_devtools", "tests"}
_WHEEL_DIST_INFO_FILES = {
    "METADATA",
    "RECORD",
    "WHEEL",
    "entry_points.txt",
    "licenses/LICENSE",
    "top_level.txt",
}
_SDIST_TOP_LEVEL_FILES = {
    "LICENSE",
    "MANIFEST.in",
    "PKG-INFO",
    "README.md",
    "pyproject.toml",
    "setup.cfg",
}
_SDIST_EGG_INFO_FILES = {
    "PKG-INFO",
    "SOURCES.txt",
    "dependency_links.txt",
    "entry_points.txt",
    "requires.txt",
    "top_level.txt",
}
_SDIST_SOURCE_MANIFEST_TOP_LEVEL = {
    "LICENSE",
    "MANIFEST.in",
    "README.md",
    "pyproject.toml",
}


def _load_inventory(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("distribution inventory schema_version must be 1")
    for field in ("distribution", "console_scripts", "package_data", "static_skill"):
        if field not in payload:
            raise ValueError(f"distribution inventory is missing {field}")
    return payload


def _assert_exact(label: str, actual: set[str], expected: set[str]) -> None:
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"{label} inventory mismatch: missing={missing}, extra={extra}"
        )


def _assert_safe_members(members: set[str], label: str) -> None:
    for member in members:
        path = PurePosixPath(member)
        if not member or "\\" in member or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"{label} contains unsafe path: {member}")
        if _FORBIDDEN_PARTS.intersection(path.parts) or path.suffix == ".pyc":
            raise ValueError(f"{label} contains forbidden build/source path: {member}")


def _parse_console_scripts(payload: str) -> dict[str, str]:
    parser = ConfigParser()
    parser.read_file(io.StringIO(payload))
    if not parser.has_section("console_scripts"):
        return {}
    return dict(parser.items("console_scripts"))


def _distribution_stem(name: str, version: Version) -> str:
    normalized_name = canonicalize_name(name).replace("-", "_")
    return f"{normalized_name}-{version}"


def _assert_distribution_metadata(
    payload: bytes,
    *,
    expected_name: str,
    expected_version: Version,
    label: str,
) -> None:
    metadata = BytesParser().parsebytes(payload, headersonly=True)
    actual_name = str(metadata.get("Name") or "").strip()
    actual_version = str(metadata.get("Version") or "").strip()
    if canonicalize_name(actual_name) != canonicalize_name(expected_name):
        raise ValueError(
            f"{label} distribution name mismatch: "
            f"expected={expected_name!r}, actual={actual_name!r}"
        )
    try:
        parsed_version = Version(actual_version)
    except ValueError as exc:
        raise ValueError(f"{label} has invalid Version: {actual_version!r}") from exc
    if parsed_version != expected_version:
        raise ValueError(
            f"{label} version mismatch: "
            f"expected={expected_version}, actual={parsed_version}"
        )


def _assert_inventory_distribution(inventory: dict[str, Any], actual: str) -> None:
    expected = str(inventory["distribution"])
    if canonicalize_name(actual) != canonicalize_name(expected):
        raise ValueError(
            f"archive distribution mismatch: expected={expected!r}, actual={actual!r}"
        )


def _verify_wheel_record(
    archive: zipfile.ZipFile,
    *,
    record_path: str,
    members: set[str],
) -> None:
    rows = list(csv.reader(io.StringIO(archive.read(record_path).decode("utf-8"))))
    if any(len(row) != 3 for row in rows):
        raise ValueError("wheel RECORD must contain exactly three columns per row")
    recorded_names = [row[0] for row in rows]
    if len(recorded_names) != len(set(recorded_names)):
        raise ValueError("wheel RECORD contains duplicate member names")
    _assert_exact("wheel RECORD", set(recorded_names), members)

    for member, hash_spec, size_text in rows:
        if member == record_path:
            if hash_spec or size_text:
                raise ValueError("wheel RECORD self-entry must omit hash and size")
            continue
        try:
            algorithm, encoded_digest = hash_spec.split("=", 1)
        except ValueError as exc:
            raise ValueError(f"wheel RECORD has invalid hash for {member}") from exc
        if algorithm != "sha256":
            raise ValueError(f"wheel RECORD must use sha256 for {member}")
        payload = archive.read(member)
        actual_digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
        actual_digest_text = actual_digest.rstrip(b"=").decode("ascii")
        if encoded_digest != actual_digest_text or size_text != str(len(payload)):
            raise ValueError(f"wheel RECORD digest/size mismatch for {member}")


def _expected_archive_directories(files: set[str]) -> set[str]:
    return {
        parent.as_posix()
        for name in files
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }


def verify_wheel(
    path: Path,
    inventory: dict[str, Any],
    *,
    expected_package_members: set[str],
) -> None:
    distribution, version, _build, _tags = parse_wheel_filename(path.name)
    distribution_name = str(distribution)
    _assert_inventory_distribution(inventory, distribution_name)
    stem = _distribution_stem(distribution_name, version)
    dist_info = f"{stem}.dist-info"
    data_dir = f"{stem}.data"
    expected_dist_info = {f"{dist_info}/{name}" for name in _WHEEL_DIST_INFO_FILES}
    expected_static = {
        f"{data_dir}/data/share/paper-fetch-skill/{name}"
        for name in inventory["static_skill"]
    }
    expected_members = expected_package_members | expected_dist_info | expected_static

    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("wheel contains duplicate member names")
        for info in infos:
            mode = info.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if info.is_dir() or kind not in {0, stat.S_IFREG}:
                raise ValueError(
                    f"wheel contains non-regular archive member: {info.filename}"
                )
        members = set(names)
        _assert_safe_members(members, "wheel")
        _assert_exact("wheel archive", members, expected_members)
        package_members = {name for name in members if name.startswith("paper_fetch/")}
        package_data = {
            name
            for name in package_members
            if PurePosixPath(name).suffix in _PACKAGE_DATA_SUFFIXES
        }
        static_skill = {
            name.removeprefix(f"{data_dir}/data/share/paper-fetch-skill/")
            for name in expected_static
        }
        metadata_path = f"{dist_info}/METADATA"
        entry_points_path = f"{dist_info}/entry_points.txt"
        record_path = f"{dist_info}/RECORD"
        _assert_distribution_metadata(
            archive.read(metadata_path),
            expected_name=distribution_name,
            expected_version=version,
            label="wheel METADATA",
        )
        console_scripts = _parse_console_scripts(
            archive.read(entry_points_path).decode("utf-8")
        )
        _verify_wheel_record(
            archive,
            record_path=record_path,
            members=members,
        )

    _assert_exact("wheel package payload", package_members, expected_package_members)
    _assert_exact("wheel package data", package_data, set(inventory["package_data"]))
    _assert_exact("wheel static skill", static_skill, set(inventory["static_skill"]))
    if console_scripts != inventory["console_scripts"]:
        raise ValueError(
            "wheel console script inventory mismatch: "
            f"expected={inventory['console_scripts']}, actual={console_scripts}"
        )


def verify_sdist(
    path: Path,
    inventory: dict[str, Any],
    *,
    expected_package_members: set[str],
) -> None:
    distribution, version = parse_sdist_filename(path.name)
    distribution_name = str(distribution)
    _assert_inventory_distribution(inventory, distribution_name)
    root = _distribution_stem(distribution_name, version)
    egg_info = f"{canonicalize_name(distribution_name).replace('-', '_')}.egg-info"
    expected_top_level = {f"{root}/{name}" for name in _SDIST_TOP_LEVEL_FILES}
    expected_package = {f"{root}/src/{name}" for name in expected_package_members}
    expected_static = {f"{root}/{name}" for name in inventory["static_skill"]}
    expected_egg_info = {
        f"{root}/src/{egg_info}/{name}" for name in _SDIST_EGG_INFO_FILES
    }
    expected_files = (
        expected_top_level | expected_package | expected_static | expected_egg_info
    )
    expected_directories = _expected_archive_directories(expected_files)

    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name.rstrip("/") for member in members]
        if len(names) != len(set(names)):
            raise ValueError("sdist contains duplicate member names")
        unsupported = [
            member.name for member in members if not (member.isfile() or member.isdir())
        ]
        if unsupported:
            raise ValueError(
                f"sdist contains non-regular archive members: {unsupported}"
            )
        regular_names = {
            member.name.rstrip("/") for member in members if member.isfile()
        }
        directory_names = {
            member.name.rstrip("/") for member in members if member.isdir()
        }
        _assert_safe_members(regular_names | directory_names, "sdist")
        _assert_exact("sdist archive files", regular_names, expected_files)
        _assert_exact(
            "sdist archive directories", directory_names, expected_directories
        )

        root_metadata = archive.extractfile(f"{root}/PKG-INFO")
        egg_metadata = archive.extractfile(f"{root}/src/{egg_info}/PKG-INFO")
        if root_metadata is None or egg_metadata is None:
            raise ValueError("sdist is missing required PKG-INFO payload")
        for label, handle in (
            ("sdist PKG-INFO", root_metadata),
            ("sdist egg-info PKG-INFO", egg_metadata),
        ):
            _assert_distribution_metadata(
                handle.read(),
                expected_name=distribution_name,
                expected_version=version,
                label=label,
            )
        entry_points_handle = archive.extractfile(
            f"{root}/src/{egg_info}/entry_points.txt"
        )
        sources_handle = archive.extractfile(f"{root}/src/{egg_info}/SOURCES.txt")
        if entry_points_handle is None or sources_handle is None:
            raise ValueError("sdist is missing required egg-info inventory")
        console_scripts = _parse_console_scripts(
            entry_points_handle.read().decode("utf-8")
        )
        source_manifest = set(sources_handle.read().decode("utf-8").splitlines())

    names = regular_names
    package_members = {
        name.removeprefix(f"{root}/src/")
        for name in names
        if name.startswith(f"{root}/src/paper_fetch/")
    }
    package_data = {
        name
        for name in package_members
        if PurePosixPath(name).suffix in _PACKAGE_DATA_SUFFIXES
    }
    static_skill = {
        name.removeprefix(f"{root}/")
        for name in names
        if name.startswith(f"{root}/skills/paper-fetch-skill/")
    }
    _assert_exact("sdist package payload", package_members, expected_package_members)
    _assert_exact("sdist package data", package_data, set(inventory["package_data"]))
    _assert_exact("sdist static skill", static_skill, set(inventory["static_skill"]))
    expected_source_manifest = (
        _SDIST_SOURCE_MANIFEST_TOP_LEVEL
        | set(inventory["static_skill"])
        | {f"src/{name}" for name in expected_package_members}
        | {f"src/{egg_info}/{name}" for name in _SDIST_EGG_INFO_FILES}
    )
    _assert_exact("sdist SOURCES.txt", source_manifest, expected_source_manifest)
    if console_scripts != inventory["console_scripts"]:
        raise ValueError(
            "sdist console script inventory mismatch: "
            f"expected={inventory['console_scripts']}, actual={console_scripts}"
        )


def verify_source(repo_root: Path, inventory: dict[str, Any]) -> set[str]:
    package_members = {
        path.relative_to(repo_root / "src").as_posix()
        for path in (repo_root / "src" / "paper_fetch").rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and "__pycache__" not in path.parts
    }
    package_data = {
        name
        for name in package_members
        if PurePosixPath(name).suffix in _PACKAGE_DATA_SUFFIXES
    }
    static_skill = {
        path.relative_to(repo_root).as_posix()
        for path in (repo_root / "skills" / "paper-fetch-skill").rglob("*")
        if path.is_file()
    }
    _assert_exact("source package data", package_data, set(inventory["package_data"]))
    _assert_exact("source static skill", static_skill, set(inventory["static_skill"]))
    return package_members


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    inventory = _load_inventory(args.inventory)
    expected_package_members = verify_source(args.repo_root.resolve(), inventory)
    verify_wheel(
        args.wheel,
        inventory,
        expected_package_members=expected_package_members,
    )
    verify_sdist(
        args.sdist,
        inventory,
        expected_package_members=expected_package_members,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
