from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import sys

from coverage import Coverage


@dataclass(frozen=True)
class CoverageFocus:
    name: str
    include: tuple[str, ...]


FOCUS_AREAS = (
    CoverageFocus("workflow", ("src/paper_fetch/workflow/*.py",)),
    CoverageFocus(
        "HTTP/cache",
        (
            "src/paper_fetch/http/*.py",
            "src/paper_fetch/mcp/*cache*.py",
            "src/paper_fetch/workflow/session_cache.py",
        ),
    ),
    CoverageFocus(
        "PDF fallback",
        (
            "src/paper_fetch/providers/_pdf_*.py",
            "src/paper_fetch/providers/browser_workflow/pdf_fallback.py",
        ),
    ),
    CoverageFocus(
        "browser runtime",
        ("src/paper_fetch/providers/browser_runtime/*.py",),
    ),
    CoverageFocus(
        "installer",
        (
            "src/paper_fetch/formula/install.py",
            "src/paper_fetch/image_tools/install.py",
        ),
    ),
)


def report_focus_areas(*, data_file: Path = Path(".coverage")) -> None:
    coverage = Coverage(data_file=str(data_file))
    coverage.load()
    for area in FOCUS_AREAS:
        print(f"\nCoverage focus: {area.name}")
        coverage.report(include=list(area.include), show_missing=True, skip_empty=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report branch coverage for risk-focused production areas."
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=Path(".coverage"),
        help="Coverage data file produced by pytest-cov (default: .coverage).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report_focus_areas(data_file=args.data_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
