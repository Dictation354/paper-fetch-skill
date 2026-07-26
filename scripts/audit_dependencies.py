#!/usr/bin/env python3
"""Audit the locked dependency graph with exact, expiring vulnerability waivers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WAIVERS = REPO_ROOT / "security" / "vulnerability-waivers.json"


@dataclass(frozen=True, order=True)
class Vulnerability:
    package: str
    version: str
    vulnerability_id: str


@dataclass(frozen=True)
class VulnerabilityWaiver:
    package: str
    version: str
    vulnerability_id: str
    expires: date
    reason: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.package, self.version, self.vulnerability_id)


def parse_audit_report(payload: Any) -> list[Vulnerability]:
    if not isinstance(payload, dict):
        raise ValueError("pip-audit report must be a JSON object")
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("pip-audit report is missing dependencies")
    vulnerabilities: set[Vulnerability] = set()
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        package = str(dependency.get("name") or "").strip().lower()
        version = str(dependency.get("version") or "").strip()
        vulns = dependency.get("vulns")
        if not package or not version or not isinstance(vulns, list):
            continue
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            vulnerability_id = str(vuln.get("id") or "").strip()
            if vulnerability_id:
                vulnerabilities.add(Vulnerability(package, version, vulnerability_id))
    return sorted(vulnerabilities)


def load_waivers(path: Path, *, today: date) -> list[VulnerabilityWaiver]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported vulnerability-waiver schema")
    raw_waivers = payload.get("waivers")
    if not isinstance(raw_waivers, list):
        raise ValueError("Vulnerability waivers must be a list")
    waivers: list[VulnerabilityWaiver] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw_waivers:
        if not isinstance(item, dict):
            raise ValueError("Every vulnerability waiver must be an object")
        required = {
            "package",
            "version",
            "vulnerability_id",
            "expires",
            "reason",
        }
        if set(item) != required:
            raise ValueError(
                "Every waiver must contain exactly package, version, "
                "vulnerability_id, expires, and reason"
            )
        waiver = VulnerabilityWaiver(
            package=str(item["package"]).strip().lower(),
            version=str(item["version"]).strip(),
            vulnerability_id=str(item["vulnerability_id"]).strip(),
            expires=date.fromisoformat(str(item["expires"])),
            reason=str(item["reason"]).strip(),
        )
        if not all(
            (waiver.package, waiver.version, waiver.vulnerability_id, waiver.reason)
        ):
            raise ValueError("Vulnerability waiver fields must not be blank")
        if waiver.expires < today:
            raise ValueError(
                f"Expired vulnerability waiver: {waiver.package} "
                f"{waiver.version} {waiver.vulnerability_id}"
            )
        if waiver.key in seen:
            raise ValueError(f"Duplicate vulnerability waiver: {waiver.key!r}")
        seen.add(waiver.key)
        waivers.append(waiver)
    return waivers


def unwaived_vulnerabilities(
    vulnerabilities: list[Vulnerability],
    waivers: list[VulnerabilityWaiver],
) -> list[Vulnerability]:
    allowed = {waiver.key for waiver in waivers}
    return [
        vulnerability
        for vulnerability in vulnerabilities
        if (
            vulnerability.package,
            vulnerability.version,
            vulnerability.vulnerability_id,
        )
        not in allowed
    ]


def _run_locked_audit() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="paper-fetch-audit-") as tmpdir:
        requirements = Path(tmpdir) / "locked-requirements.txt"
        export = subprocess.run(
            [
                "uv",
                "export",
                "--locked",
                "--all-extras",
                "--format",
                "requirements-txt",
                "--no-hashes",
                "--no-emit-project",
                "--output-file",
                str(requirements),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if export.returncode != 0:
            raise RuntimeError(export.stderr.strip() or "uv export failed")
        audit = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--requirement",
                str(requirements),
                "--format",
                "json",
                "--progress-spinner",
                "off",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if audit.returncode not in {0, 1}:
            raise RuntimeError(audit.stderr.strip() or "pip-audit failed")
        return json.loads(audit.stdout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--waivers", type=Path, default=DEFAULT_WAIVERS)
    parser.add_argument(
        "--input-json",
        type=Path,
        help="Review an existing pip-audit JSON report instead of invoking tools.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    today = datetime.now(UTC).date()
    try:
        waivers = load_waivers(args.waivers, today=today)
        report = (
            json.loads(args.input_json.read_text(encoding="utf-8"))
            if args.input_json is not None
            else _run_locked_audit()
        )
        vulnerabilities = parse_audit_report(report)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Dependency audit configuration failed: {exc}", file=sys.stderr)
        return 2
    failures = unwaived_vulnerabilities(vulnerabilities, waivers)
    if failures:
        print("Unwaived dependency vulnerabilities:", file=sys.stderr)
        for failure in failures:
            print(
                f"- {failure.package}=={failure.version}: {failure.vulnerability_id}",
                file=sys.stderr,
            )
        return 1
    print(
        f"Dependency audit passed ({len(vulnerabilities)} finding(s), "
        f"{len(waivers)} active waiver(s))."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
