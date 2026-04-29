#!/usr/bin/env python3
"""Run the natural-geography live-only publisher report."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_geography_live_exports():
    from paper_fetch_devtools.geography.live import (
        GEOGRAPHY_PROVIDER_ORDER,
        default_report_paths,
        run_geography_live_report,
    )

    return GEOGRAPHY_PROVIDER_ORDER, default_report_paths, run_geography_live_report


def all_geography_samples():
    samples_path = REPO_ROOT / "tests" / "live" / "geography_samples.py"
    spec = importlib.util.spec_from_file_location("paper_fetch_geography_samples", samples_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load geography samples from {samples_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.all_geography_samples()


def build_parser() -> argparse.ArgumentParser:
    GEOGRAPHY_PROVIDER_ORDER, default_report_paths, _ = _load_geography_live_exports()
    json_path, markdown_path = default_report_paths()
    parser = argparse.ArgumentParser(description="Run the geography live-only publisher report without MCP.")
    parser.add_argument(
        "--providers",
        nargs="*",
        choices=GEOGRAPHY_PROVIDER_ORDER,
        help="Optional provider subset. Defaults to all five publishers.",
    )
    parser.add_argument(
        "--per-provider",
        type=int,
        default=10,
        help="How many ordered samples to attempt per provider. Defaults to 10.",
    )
    parser.add_argument(
        "--output-json",
        default=str(json_path),
        help="JSON report output path.",
    )
    parser.add_argument(
        "--output-markdown",
        default=str(markdown_path),
        help="Markdown summary output path.",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Write JSON only.",
    )
    return parser


def main() -> int:
    _, _, run_geography_live_report = _load_geography_live_exports()
    parser = build_parser()
    args = parser.parse_args()

    report = run_geography_live_report(
        all_geography_samples(),
        per_provider=args.per_provider,
        providers=args.providers,
    )

    json_output = Path(args.output_json)
    report.write_json(json_output)
    markdown_output = Path(args.output_markdown)
    if not args.no_markdown:
        report.write_markdown(markdown_output)

    sys.stdout.write(f"wrote json report to {json_output}\n")
    if not args.no_markdown:
        sys.stdout.write(f"wrote markdown summary to {markdown_output}\n")

    for summary in report.summary_by_provider:
        counts = summary.status_counts
        sys.stdout.write(
            f"{summary.provider}: attempted={summary.attempted} "
            f"fulltext={counts.get('fulltext', 0)} "
            f"metadata_only={counts.get('metadata_only', 0)} "
            f"not_configured={counts.get('not_configured', 0)} "
            f"rate_limited={counts.get('rate_limited', 0)} "
            f"no_result={counts.get('no_result', 0)} "
            f"error={counts.get('error', 0)}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
