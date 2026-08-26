from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict, dataclass
import glob
import json
import math
from pathlib import Path
import sys
from typing import Any

from coverage import Coverage


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "quality" / "coverage-focus.json"


@dataclass(frozen=True)
class CoverageFocus:
    name: str
    include: tuple[str, ...]
    minimum_branch_percent: int


@dataclass(frozen=True)
class CoverageFocusResult:
    name: str
    include: tuple[str, ...]
    minimum_branch_percent: int
    branch_covered: int
    branch_total: int
    branch_percent: float
    measured_branch_percent: int
    passed: bool


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"coverage focus config must be an object: {path}")
    return payload


def load_focus_areas(path: Path = DEFAULT_CONFIG) -> tuple[CoverageFocus, ...]:
    payload = _load_json(path)
    if payload.get("schema_version") != 2:
        raise ValueError("coverage focus config schema_version must be 2")
    if payload.get("metric") != "pure_branch_exits":
        raise ValueError("coverage focus config metric must be pure_branch_exits")
    raw_areas = payload.get("areas")
    if not isinstance(raw_areas, list) or not raw_areas:
        raise ValueError("coverage focus config areas must be a non-empty list")
    areas: list[CoverageFocus] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_areas):
        if not isinstance(raw, dict):
            raise ValueError(f"coverage focus area {index} must be an object")
        name = str(raw.get("name") or "").strip()
        include = raw.get("include")
        minimum = raw.get("minimum_branch_percent")
        if not name or name in names:
            raise ValueError("coverage focus area names must be non-empty and unique")
        if (
            not isinstance(include, list)
            or not include
            or not all(isinstance(item, str) and item.strip() for item in include)
        ):
            raise ValueError(f"coverage focus area {name} include must be non-empty")
        if not isinstance(minimum, int) or not 0 <= minimum <= 100:
            raise ValueError(
                f"coverage focus area {name} minimum_branch_percent is invalid"
            )
        names.add(name)
        areas.append(
            CoverageFocus(
                name=name,
                include=tuple(include),
                minimum_branch_percent=minimum,
            )
        )
    return tuple(areas)


FOCUS_AREAS = load_focus_areas()


def _matched_source_files(include: tuple[str, ...]) -> tuple[Path, ...]:
    matched: dict[Path, None] = {}
    for pattern in include:
        candidate = Path(pattern).expanduser()
        anchored_pattern = (
            candidate if candidate.is_absolute() else REPO_ROOT / candidate
        )
        pattern_matches = tuple(
            sorted(
                path.resolve()
                for raw_path in glob.glob(str(anchored_pattern), recursive=True)
                if (path := Path(raw_path)).is_file()
            )
        )
        if not pattern_matches:
            raise ValueError(f"coverage include pattern matched no files: {pattern}")
        matched.update(dict.fromkeys(pattern_matches))
    return tuple(matched)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def report_focus_areas(
    *,
    data_file: Path = Path(".coverage"),
    areas: tuple[CoverageFocus, ...] = FOCUS_AREAS,
    show_details: bool = True,
) -> tuple[CoverageFocusResult, ...]:
    # The caller supplies exact include patterns. Ignore repository-wide source
    # filtering here so the same gate can prove its fail behavior against a
    # temporary branch fixture in devtools tests.
    coverage = Coverage(data_file=str(data_file), config_file=False)
    coverage.load()
    if not coverage.get_data().has_arcs():
        raise ValueError(
            "focus coverage requires branch data from pytest-cov --cov-branch"
        )
    measured_files = {
        Path(filename).resolve() for filename in coverage.get_data().measured_files()
    }
    results: list[CoverageFocusResult] = []
    for area in areas:
        source_files = _matched_source_files(area.include)
        unmeasured = tuple(path for path in source_files if path not in measured_files)
        if unmeasured:
            raise ValueError(
                f"coverage focus {area.name} has unmeasured files: "
                + ", ".join(_display_path(path) for path in unmeasured)
            )
        file_counts: list[tuple[Path, int, int]] = []
        for source_file in source_files:
            branch_stats = coverage.branch_stats(str(source_file))
            branch_total = sum(total for total, _taken in branch_stats.values())
            branch_covered = sum(taken for _total, taken in branch_stats.values())
            file_counts.append((source_file, branch_covered, branch_total))
        branch_covered = sum(covered for _path, covered, _total in file_counts)
        branch_total = sum(total for _path, _covered, total in file_counts)
        if branch_total <= 0:
            raise ValueError(f"coverage focus {area.name} has no measurable branches")
        percentage = branch_covered * 100 / branch_total
        measured = math.floor(percentage)
        result = CoverageFocusResult(
            name=area.name,
            include=area.include,
            minimum_branch_percent=area.minimum_branch_percent,
            branch_covered=branch_covered,
            branch_total=branch_total,
            branch_percent=percentage,
            measured_branch_percent=measured,
            passed=measured >= area.minimum_branch_percent,
        )
        results.append(result)
        if show_details:
            print(f"\nCoverage focus: {area.name}")
            for path, covered, total in file_counts:
                file_percentage = covered * 100 / total if total else 0.0
                print(
                    f"  {_display_path(path)}: {covered}/{total} "
                    f"pure branches ({file_percentage:.3f}%)"
                )
            state = "PASS" if result.passed else "FAIL"
            print(
                f"Focus gate {state}: pure branches={branch_covered}/{branch_total} "
                f"({percentage:.3f}%, floor={measured}%) "
                f"minimum={area.minimum_branch_percent}%"
            )
    return tuple(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enforce branch coverage baselines for risk-focused production areas."
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=Path(".coverage"),
        help="Coverage data file produced by pytest-cov (default: .coverage).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Machine-readable focus baseline configuration.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable gate results without per-file tables.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        areas = load_focus_areas(args.config)
        results = report_focus_areas(
            data_file=args.data_file,
            areas=areas,
            show_details=not args.json,
        )
    except (OSError, ValueError) as exc:
        print(f"Coverage focus gate failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        payload = {
            "status": "OK" if all(result.passed for result in results) else "ERROR",
            "results": [asdict(result) for result in results],
        }
        print(json.dumps(payload, sort_keys=True))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
