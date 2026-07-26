#!/usr/bin/env python3
"""Synchronize and validate generated release-version artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import sys
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
INNO_INSTALLER = REPO_ROOT / "installer" / "paper-fetch-skill.iss"
CHANGELOGS = (REPO_ROOT / "CHANGELOG.md", REPO_ROOT / "CHANGELOG_CN.md")
INNO_VERSION_PATTERN = re.compile(r'(?m)^#define AppVersion "[^"]+"$')


@dataclass(frozen=True)
class VersionFacts:
    version: str

    @property
    def inno_definition(self) -> str:
        return f'#define AppVersion "{self.version}"'

    @property
    def changelog_prefix(self) -> str:
        return f"## {self.version} - "


def project_version_facts() -> VersionFacts:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    version = str(payload["project"]["version"]).strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[A-Za-z0-9.-]+)?", version):
        raise ValueError(f"Unsupported project version: {version!r}")
    return VersionFacts(version=version)


def synchronized_version_issues(facts: VersionFacts) -> list[str]:
    issues: list[str] = []
    inno = INNO_INSTALLER.read_text(encoding="utf-8")
    if facts.inno_definition not in inno:
        issues.append(
            f"{INNO_INSTALLER.relative_to(REPO_ROOT)} does not declare "
            f"{facts.inno_definition}"
        )
    for changelog in CHANGELOGS:
        text = changelog.read_text(encoding="utf-8")
        if facts.changelog_prefix not in text:
            issues.append(
                f"{changelog.relative_to(REPO_ROOT)} has no "
                f"{facts.changelog_prefix}YYYY-MM-DD section"
            )
    return issues


def write_generated_version(facts: VersionFacts) -> None:
    inno = INNO_INSTALLER.read_text(encoding="utf-8")
    updated, substitutions = INNO_VERSION_PATTERN.subn(facts.inno_definition, inno)
    if substitutions != 1:
        raise ValueError("Inno installer must contain exactly one AppVersion default")
    INNO_INSTALLER.write_text(updated, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Only validate drift.")
    mode.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the installer default before validation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    del args.check
    try:
        facts = project_version_facts()
        if args.write:
            write_generated_version(facts)
        issues = synchronized_version_issues(facts)
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"Version synchronization failed: {exc}", file=sys.stderr)
        return 2
    if issues:
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print(
        f"Version {facts.version} is synchronized "
        f"({date.today().isoformat()} validation)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
