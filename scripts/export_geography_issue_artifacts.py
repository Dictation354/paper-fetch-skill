#!/usr/bin/env python3
"""Export issue-flagged geography live-report outputs into a dedicated folder."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_issue_artifact_exports():
    from paper_fetch.geography_issue_artifacts import (
        default_issue_artifact_output_dir,
        export_geography_issue_artifacts,
    )

    return default_issue_artifact_output_dir, export_geography_issue_artifacts


def build_parser() -> argparse.ArgumentParser:
    default_issue_artifact_output_dir, _ = _load_issue_artifact_exports()
    parser = argparse.ArgumentParser(description="Export issue-flagged geography live artifacts without MCP.")
    parser.add_argument(
        "--report-json",
        default=str(REPO_ROOT / "live-downloads" / "reports" / "geography-live-report.json"),
        help="Path to the geography live JSON report.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_issue_artifact_output_dir()),
        help="Directory where per-DOI issue artifacts will be written.",
    )
    parser.add_argument(
        "--issue-flags",
        nargs="*",
        help="Optional subset of issue flags to export. Defaults to every non-empty issue row.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of issue rows to export after filtering.",
    )
    return parser


def main() -> int:
    _, export_geography_issue_artifacts = _load_issue_artifact_exports()
    parser = build_parser()
    args = parser.parse_args()
    summary = export_geography_issue_artifacts(
        report_json_path=Path(args.report_json),
        output_dir=Path(args.output_dir),
        issue_flags=args.issue_flags,
        limit=args.limit,
    )
    sys.stdout.write(f"wrote issue artifacts to {summary['output_dir']}\n")
    sys.stdout.write(f"selected={summary['total_selected']} exported={summary['exported']} failed={summary['failed']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
