#!/usr/bin/env python3
"""Update consecutive-failure state for the non-blocking provider canary."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


WARNING_THRESHOLD = 3


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "routes": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("provider canary state schema_version must be 1")
    if not isinstance(payload.get("routes"), dict):
        raise ValueError("provider canary state routes must be a mapping")
    return payload


def update_state(
    previous: Mapping[str, Any], report: Mapping[str, Any]
) -> tuple[dict[str, Any], tuple[str, ...]]:
    if report.get("schema_version") != 1 or not isinstance(report.get("results"), list):
        raise ValueError("provider canary report is invalid")
    previous_routes = previous.get("routes")
    if not isinstance(previous_routes, Mapping):
        previous_routes = {}

    routes: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    seen: set[str] = set()
    for result in report["results"]:
        if not isinstance(result, Mapping):
            raise ValueError("provider canary result must be a mapping")
        key = str(result.get("key") or "").strip().lower()
        if not key or key in seen:
            raise ValueError("provider canary result keys must be unique and non-empty")
        seen.add(key)
        old = previous_routes.get(key)
        old_count = (
            int(old.get("consecutive_failures", 0)) if isinstance(old, Mapping) else 0
        )
        passed = result.get("passed") is True
        consecutive_failures = 0 if passed else old_count + 1
        routes[key] = {
            "consecutive_failures": consecutive_failures,
            "last_passed": passed,
            "last_reason": str(result.get("reason") or "unknown"),
        }
        if consecutive_failures >= WARNING_THRESHOLD:
            warnings.append(
                f"{key} failed {consecutive_failures} consecutive scheduled canaries"
            )
    state = {
        "schema_version": 1,
        "updated_at": datetime.now(UTC).isoformat(),
        "routes": routes,
    }
    return state, tuple(warnings)


def write_state(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    state, warnings = update_state(load_state(args.state), report)
    write_state(args.state, state)
    for warning in warnings:
        print(f"::warning title=Provider public canary::{warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
