"""CLI entrypoint for the golden criteria live review pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence


def _load_live_review_exports():
    from paper_fetch_devtools.golden_criteria.live import (
        SUPPORTED_PROVIDERS,
        load_manifest,
        run_golden_criteria_live_review,
        timestamped_review_output_dir,
    )

    manifest = load_manifest()
    provider_choices = sorted(
        {
            str(sample.get("publisher") or "").strip().lower()
            for sample in (manifest.get("samples") or {}).values()
            if isinstance(sample, dict)
            and str(sample.get("fixture_family") or "golden") == "golden"
            and str(sample.get("publisher") or "").strip()
        }
    )
    return SUPPORTED_PROVIDERS, provider_choices, run_golden_criteria_live_review, timestamped_review_output_dir


def build_parser() -> argparse.ArgumentParser:
    _, provider_choices, _, timestamped_review_output_dir = _load_live_review_exports()
    parser = argparse.ArgumentParser(description="Run the golden criteria live review pipeline.")
    parser.add_argument(
        "--providers",
        nargs="*",
        choices=provider_choices,
        help="Optional provider subset. Defaults to every golden sample provider in the manifest.",
    )
    parser.add_argument(
        "--sample-ids",
        nargs="*",
        help="Optional sample-id subset. Accepts manifest sample IDs or DOI strings.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(timestamped_review_output_dir()),
        help="Output directory for generated artifacts and reports.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _, _, run_golden_criteria_live_review, _ = _load_live_review_exports()
    parser = build_parser()
    args = parser.parse_args(argv)

    report = run_golden_criteria_live_review(
        providers=args.providers,
        sample_ids=args.sample_ids,
        output_dir=Path(args.output_dir),
    )
    output_root = Path(report.output_dir)
    sys.stdout.write(f"wrote report json to {output_root / 'report.json'}\n")
    sys.stdout.write(f"wrote report markdown to {output_root / 'report.md'}\n")
    sys.stdout.write(f"wrote provider status to {output_root / 'provider-status.json'}\n")
    sys.stdout.write(f"wrote manifest snapshot to {output_root / 'manifest-snapshot.json'}\n")
    sys.stdout.write(f"processed {report.total_samples} samples\n")
    return 0
