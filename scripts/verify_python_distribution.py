#!/usr/bin/env python3
"""Verify the minimum trust boundary for wheel and sdist archives."""

from __future__ import annotations

import argparse
import base64
from configparser import ConfigParser
import csv
from email.parser import BytesParser
import hashlib
import io
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile

from packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import Version


_DISTRIBUTION = "paper-fetch-skill"
_REQUIRED_CONSOLE_SCRIPTS = {
    "paper-fetch": "paper_fetch.cli:main",
    "paper-fetch-mcp": "paper_fetch.mcp.server:main",
    "paper-fetch-install-formula-tools": "paper_fetch.formula.install:main",
    "paper-fetch-install-image-tools": "paper_fetch.image_tools.install:main",
}
_REQUIRED_PACKAGE_PATHS = {
    "paper_fetch/__init__.py",
    "paper_fetch/models/__init__.pyi",
    "paper_fetch/resources/arxiv/author_boundaries.json",
    "paper_fetch/resources/formula/mathml_to_latex_cli.mjs",
    "paper_fetch/resources/formula/mathml_to_latex_worker.mjs",
    "paper_fetch/resources/formula/package-lock.json",
    "paper_fetch/resources/formula/package.json",
    "paper_fetch/resources/journal_routes/journal-routes-v1.json",
    "paper_fetch/resources/manifest/manifest-record-v2.schema.json",
}
_REQUIRED_SKILL_PATHS = {
    "share/paper-fetch-skill/skills/paper-fetch-skill/SKILL.md",
    "share/paper-fetch-skill/skills/paper-fetch-skill/agents/openai.yaml",
    "share/paper-fetch-skill/skills/paper-fetch-skill/references/tool-contract.md",
}
_FORBIDDEN_PARTS = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "onboarding",
    "paper_fetch_devtools",
    "tests",
}


def _assert_safe_members(members: set[str], label: str) -> None:
    for member in members:
        path = PurePosixPath(member)
        if not member or "\\" in member or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"{label} contains unsafe path: {member}")
        if _FORBIDDEN_PARTS.intersection(path.parts) or path.suffix == ".pyc":
            raise ValueError(f"{label} contains forbidden build/source path: {member}")
        if any(part == ".env" or part.startswith(".env.") for part in path.parts):
            raise ValueError(f"{label} contains local environment data: {member}")


def _parse_console_scripts(payload: str) -> dict[str, str]:
    parser = ConfigParser()
    parser.read_file(io.StringIO(payload))
    if not parser.has_section("console_scripts"):
        return {}
    return dict(parser.items("console_scripts"))


def _assert_console_scripts(payload: bytes, label: str) -> None:
    actual = _parse_console_scripts(payload.decode("utf-8"))
    missing = {
        name: target
        for name, target in _REQUIRED_CONSOLE_SCRIPTS.items()
        if actual.get(name) != target
    }
    if missing:
        raise ValueError(f"{label} is missing required console scripts: {missing}")


def _assert_distribution_metadata(
    payload: bytes,
    *,
    expected_version: Version,
    label: str,
) -> None:
    metadata = BytesParser().parsebytes(payload, headersonly=True)
    name = str(metadata.get("Name") or "").strip()
    version = str(metadata.get("Version") or "").strip()
    if canonicalize_name(name) != canonicalize_name(_DISTRIBUTION):
        raise ValueError(f"{label} has unexpected distribution name: {name!r}")
    if Version(version) != expected_version:
        raise ValueError(
            f"{label} version mismatch: expected={expected_version}, actual={version!r}"
        )


def _require_suffixes(members: set[str], suffixes: set[str], label: str) -> None:
    missing = [
        suffix
        for suffix in sorted(suffixes)
        if not any(name == suffix or name.endswith(f"/{suffix}") for name in members)
    ]
    if missing:
        raise ValueError(f"{label} is missing required payloads: {missing}")


def _only_member_ending(members: set[str], suffix: str, label: str) -> str:
    matches = sorted(name for name in members if name.endswith(suffix))
    if len(matches) != 1:
        raise ValueError(f"{label} expected one {suffix!r}, found {matches}")
    return matches[0]


def _verify_wheel_record(
    archive: zipfile.ZipFile,
    *,
    record_path: str,
    members: set[str],
) -> None:
    rows = list(csv.reader(io.StringIO(archive.read(record_path).decode("utf-8"))))
    if any(len(row) != 3 for row in rows):
        raise ValueError("wheel RECORD must contain three columns per row")
    recorded_names = [row[0] for row in rows]
    if len(recorded_names) != len(set(recorded_names)):
        raise ValueError("wheel RECORD contains duplicate member names")
    if set(recorded_names) != members:
        raise ValueError("wheel RECORD does not describe the complete archive")

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
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
        if encoded_digest != digest.rstrip(b"=").decode("ascii"):
            raise ValueError(f"wheel RECORD digest mismatch for {member}")
        if size_text != str(len(payload)):
            raise ValueError(f"wheel RECORD size mismatch for {member}")


def verify_wheel(path: Path) -> None:
    distribution, version, _build, _tags = parse_wheel_filename(path.name)
    if canonicalize_name(str(distribution)) != canonicalize_name(_DISTRIBUTION):
        raise ValueError(f"unexpected wheel distribution: {distribution}")

    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("wheel contains duplicate member names")
        for info in infos:
            kind = stat.S_IFMT(info.external_attr >> 16)
            if info.is_dir() or kind not in {0, stat.S_IFREG}:
                raise ValueError(
                    f"wheel contains non-regular archive member: {info.filename}"
                )
        members = set(names)
        _assert_safe_members(members, "wheel")
        _require_suffixes(members, _REQUIRED_PACKAGE_PATHS, "wheel")
        _require_suffixes(members, _REQUIRED_SKILL_PATHS, "wheel")
        metadata_path = _only_member_ending(members, ".dist-info/METADATA", "wheel")
        entry_points_path = _only_member_ending(
            members, ".dist-info/entry_points.txt", "wheel"
        )
        record_path = _only_member_ending(members, ".dist-info/RECORD", "wheel")
        _assert_distribution_metadata(
            archive.read(metadata_path),
            expected_version=version,
            label="wheel METADATA",
        )
        _assert_console_scripts(archive.read(entry_points_path), "wheel")
        _verify_wheel_record(archive, record_path=record_path, members=members)


def verify_sdist(path: Path) -> None:
    distribution, version = parse_sdist_filename(path.name)
    if canonicalize_name(str(distribution)) != canonicalize_name(_DISTRIBUTION):
        raise ValueError(f"unexpected sdist distribution: {distribution}")

    with tarfile.open(path, "r:gz") as archive:
        archive_members = archive.getmembers()
        names = [member.name.rstrip("/") for member in archive_members]
        if len(names) != len(set(names)):
            raise ValueError("sdist contains duplicate member names")
        unsupported = [
            member.name
            for member in archive_members
            if not (member.isfile() or member.isdir())
        ]
        if unsupported:
            raise ValueError(
                f"sdist contains non-regular archive members: {unsupported}"
            )
        members = set(names)
        _assert_safe_members(members, "sdist")
        roots = {PurePosixPath(name).parts[0] for name in members}
        if len(roots) != 1:
            raise ValueError(f"sdist must contain one archive root: {sorted(roots)}")
        root = next(iter(roots))

        _require_suffixes(
            members,
            {f"src/{path}" for path in _REQUIRED_PACKAGE_PATHS},
            "sdist",
        )
        _require_suffixes(
            members,
            {
                "skills/paper-fetch-skill/SKILL.md",
                "skills/paper-fetch-skill/agents/openai.yaml",
                "skills/paper-fetch-skill/references/tool-contract.md",
            },
            "sdist",
        )
        metadata_path = f"{root}/PKG-INFO"
        if metadata_path not in members:
            raise ValueError("sdist is missing root PKG-INFO")
        entry_points_path = _only_member_ending(
            members, ".egg-info/entry_points.txt", "sdist"
        )
        metadata_handle = archive.extractfile(metadata_path)
        entry_points_handle = archive.extractfile(entry_points_path)
        if metadata_handle is None or entry_points_handle is None:
            raise ValueError("sdist metadata payload is not a regular file")
        _assert_distribution_metadata(
            metadata_handle.read(), expected_version=version, label="sdist PKG-INFO"
        )
        _assert_console_scripts(entry_points_handle.read(), "sdist")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    verify_wheel(args.wheel)
    verify_sdist(args.sdist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
