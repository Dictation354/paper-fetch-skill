#!/usr/bin/env python3
"""Create by-issue folder views for geography issue artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paper_fetch.geography_issue_artifacts import default_issue_artifact_output_dir, materialize_issue_type_view


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Group geography issue artifacts into per-issue folders.")
    parser.add_argument(
        "--artifact-root",
        default=str(default_issue_artifact_output_dir()),
        help="Root directory produced by export_geography_issue_artifacts.py.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove existing per-issue link folders before rebuilding them.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    summary = materialize_issue_type_view(
        artifact_root=Path(args.artifact_root),
        clean=not args.no_clean,
    )
    sys.stdout.write(f"created {len(summary['issue_dirs'])} issue folders under {summary['artifact_root']}\n")
    for item in summary["issue_dirs"]:
        sys.stdout.write(f"{item['issue_flag']}: {item['count']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
