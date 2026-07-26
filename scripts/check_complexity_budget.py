#!/usr/bin/env python3
"""Reject new or worsened complexity violations against a checked-in budget."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUDGET = REPO_ROOT / "quality" / "complexity-budget.json"
VALUE_PATTERN = re.compile(r"\((\d+) > \d+\)$")


@dataclass(frozen=True, order=True)
class ComplexityViolation:
    path: str
    code: str
    symbol: str
    value: int

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "code": self.code,
            "symbol": self.symbol,
            "value": self.value,
        }


def _function_ranges(path: Path) -> list[tuple[int, int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    ranges: list[tuple[int, int, str]] = []

    def visit(
        nodes: list[ast.stmt],
        parents: tuple[str, ...] = (),
    ) -> None:
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = ".".join((*parents, node.name))
                ranges.append((node.lineno, node.end_lineno or node.lineno, symbol))
                visit(node.body, (*parents, node.name))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, (*parents, node.name))

    visit(tree.body)
    return ranges


def _symbol_for_row(path: Path, row: int) -> str:
    matches = [
        (end - start, symbol)
        for start, end, symbol in _function_ranges(path)
        if start <= row <= end
    ]
    return min(matches, default=(0, "<module>"))[1]


def collect_violations() -> list[ComplexityViolation]:
    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "src/paper_fetch",
        "--select",
        "C901,PLR0913",
        "--output-format=json",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(completed.stderr.strip() or "Ruff complexity scan failed")
    payload = json.loads(completed.stdout or "[]")
    violations: list[ComplexityViolation] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        filename = Path(str(item.get("filename") or "")).resolve()
        try:
            relative = filename.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        message = str(item.get("message") or "")
        match = VALUE_PATTERN.search(message)
        location = item.get("location")
        row = int(location.get("row") or 0) if isinstance(location, dict) else 0
        code = str(item.get("code") or "")
        if match is None or not code or row < 1:
            continue
        violations.append(
            ComplexityViolation(
                path=relative,
                code=code,
                symbol=_symbol_for_row(filename, row),
                value=int(match.group(1)),
            )
        )
    return sorted(violations)


def _budget_payload(
    violations: list[ComplexityViolation],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "policy": {
            "mccabe_max_complexity": 25,
            "max_function_arguments": 10,
            "rule": "No new over-budget symbol and no increase to an existing value.",
        },
        "violations": [violation.to_dict() for violation in violations],
    }


def _load_budget(path: Path) -> list[ComplexityViolation]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError(f"Unsupported complexity budget schema: {path}")
    values = payload.get("violations")
    if not isinstance(values, list):
        raise ValueError(f"Complexity budget has no violations list: {path}")
    return [
        ComplexityViolation(
            path=str(item["path"]),
            code=str(item["code"]),
            symbol=str(item["symbol"]),
            value=int(item["value"]),
        )
        for item in values
        if isinstance(item, dict)
    ]


def budget_regressions(
    baseline: list[ComplexityViolation],
    current: list[ComplexityViolation],
) -> list[ComplexityViolation]:
    allowed = {(item.path, item.code, item.symbol): item.value for item in baseline}
    counts = Counter((item.path, item.code, item.symbol) for item in current)
    regressions = [
        item
        for item in current
        if item.value > allowed.get((item.path, item.code, item.symbol), 0)
        or counts[(item.path, item.code, item.symbol)] > 1
    ]
    return sorted(set(regressions))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Replace the baseline with the current scan.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    current = collect_violations()
    if args.update:
        args.budget.parent.mkdir(parents=True, exist_ok=True)
        args.budget.write_text(
            json.dumps(_budget_payload(current), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Updated {args.budget} with {len(current)} violation(s).")
        return 0
    if not args.budget.is_file():
        print(f"Complexity budget is missing: {args.budget}", file=sys.stderr)
        return 2
    regressions = budget_regressions(_load_budget(args.budget), current)
    if regressions:
        print("Complexity budget regressions:", file=sys.stderr)
        for item in regressions:
            print(
                f"- {item.path}:{item.symbol} {item.code}={item.value}",
                file=sys.stderr,
            )
        return 1
    print(f"Complexity budget passed ({len(current)} known violation(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
