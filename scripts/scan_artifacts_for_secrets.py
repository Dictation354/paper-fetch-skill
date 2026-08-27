#!/usr/bin/env python3
"""Fail closed when upload candidates contain configured secret values."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from urllib.parse import quote, quote_plus


REPO_ROOT = Path(__file__).resolve().parents[1]
_REDACTION_RULES = runpy.run_path(
    str(REPO_ROOT / "src" / "paper_fetch" / "redaction.py")
)
is_sensitive_configuration_name = _REDACTION_RULES["is_sensitive_configuration_name"]
redact_text_for_diagnostics = _REDACTION_RULES["redact_text_for_diagnostics"]


def _lower_percent_escapes(value: str) -> str:
    return re.sub(r"%[0-9A-F]{2}", lambda match: match.group(0).lower(), value)


def secret_variants(value: str) -> tuple[str, ...]:
    """Return raw and common URL-encoded forms without logging any of them."""

    raw = str(value or "")
    if not raw:
        return ()
    variants = {
        raw,
        quote(raw, safe=""),
        quote_plus(raw, safe=""),
    }
    variants.update(_lower_percent_escapes(item) for item in tuple(variants))
    return tuple(sorted((item for item in variants if item), key=len, reverse=True))


def _selected_secret_values(
    env: Mapping[str, str],
    names: Iterable[str] | None,
) -> dict[str, tuple[bytes, ...]]:
    selected = (
        {str(name) for name in names}
        if names is not None
        else {str(name) for name in env if is_sensitive_configuration_name(str(name))}
    )
    patterns: dict[str, tuple[bytes, ...]] = {}
    for name in sorted(selected):
        value = str(env.get(name) or "")
        if not value:
            continue
        patterns[name] = tuple(
            variant.encode("utf-8") for variant in secret_variants(value)
        )
    return patterns


def _iter_regular_files(roots: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser().resolve(strict=False)
        if resolved.is_file() and not resolved.is_symlink():
            if resolved not in seen:
                seen.add(resolved)
                yield resolved
            continue
        if not resolved.is_dir():
            continue
        for path in sorted(resolved.rglob("*")):
            if path.is_file() and not path.is_symlink():
                resolved_path = path.resolve(strict=False)
                if resolved_path not in seen:
                    seen.add(resolved_path)
                    yield resolved_path


def _matching_names(path: Path, patterns: Mapping[str, tuple[bytes, ...]]) -> set[str]:
    if not patterns:
        return set()
    maximum = max(len(pattern) for values in patterns.values() for pattern in values)
    matched: set[str] = set()
    tail = b""
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            payload = tail + block
            for name, values in patterns.items():
                if name not in matched and any(value in payload for value in values):
                    matched.add(name)
            tail = payload[-max(0, maximum - 1) :] if maximum > 1 else b""
    return matched


def _safe_report_path(
    path: Path,
    patterns: Mapping[str, tuple[bytes, ...]],
) -> str:
    value = str(path)
    for variants in patterns.values():
        for variant in variants:
            value = value.replace(variant.decode("utf-8"), "[redacted]")
    return redact_text_for_diagnostics(value)


def scan_artifacts(
    roots: Iterable[Path],
    *,
    env: Mapping[str, str],
    env_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    root_list = [Path(root) for root in roots]
    patterns = _selected_secret_values(env, env_names)
    matches: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    scanned_files = 0
    for path in _iter_regular_files(root_list):
        scanned_files += 1
        try:
            names = _matching_names(path, patterns)
        except OSError as exc:
            errors.append(
                {
                    "path": _safe_report_path(path, patterns),
                    "error_type": type(exc).__name__,
                }
            )
            continue
        matches.extend(
            {
                "env_var": name,
                "path": _safe_report_path(path, patterns),
            }
            for name in sorted(names)
        )
    missing_roots = [
        _safe_report_path(root.expanduser().resolve(strict=False), patterns)
        for root in root_list
        if not root.expanduser().resolve(strict=False).exists()
    ]
    status = "error" if errors or missing_roots else "blocked" if matches else "clean"
    return {
        "schema_version": 1,
        "status": status,
        "scanned_file_count": scanned_files,
        "scanned_secret_name_count": len(patterns),
        "matches": matches,
        "errors": errors,
        "missing_roots": missing_roots,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument(
        "--env-var",
        action="append",
        dest="env_vars",
        help="Scan for this environment value (repeatable); values are never printed.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = scan_artifacts(
        args.root,
        env=os.environ,
        env_names=args.env_vars,
    )
    sys.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")
    return 0 if report["status"] == "clean" else 1


if __name__ == "__main__":
    raise SystemExit(main())
