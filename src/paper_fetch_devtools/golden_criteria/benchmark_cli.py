"""CLI for the parallel golden-criteria live benchmark."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
import sys
from typing import Any

from .benchmark import (
    DEFAULT_CONCURRENCIES,
    DEFAULT_REPETITIONS,
    SAME_PROVIDER_PROBE_SAMPLES,
    run_parallel_live_benchmark,
    timestamped_benchmark_output_dir,
)


def build_parser(benchmark_catalog: Mapping[str, Any]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare one golden paper batch across bounded live-fetch concurrency levels."
        )
    )
    parser.add_argument(
        "--concurrencies",
        nargs="+",
        type=int,
        default=None,
        help=(
            "Ordered concurrency levels to compare (1-8; default: "
            + " ".join(str(value) for value in DEFAULT_CONCURRENCIES)
            + ")."
        ),
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=None,
        help=(
            "How many times to run each concurrency level "
            f"(default: {DEFAULT_REPETITIONS})."
        ),
    )
    parser.add_argument(
        "--same-provider-probe",
        choices=sorted(SAME_PROVIDER_PROBE_SAMPLES),
        help=(
            "Run the fixed same-provider capability probe. Wiley uses three "
            "golden samples at concurrency 1 and 2 for two repetitions."
        ),
    )
    parser.add_argument(
        "--providers",
        nargs="*",
        choices=sorted(benchmark_catalog),
        help="Optional provider subset in the requested execution order.",
    )
    parser.add_argument(
        "--sample-ids",
        nargs="*",
        help="Optional golden sample IDs or DOI strings; overrides the default suite.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(timestamped_benchmark_output_dir()),
        help="Output directory for the benchmark matrix and per-trial artifacts.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    benchmark_catalog: Mapping[str, Any],
) -> int:
    parser = build_parser(benchmark_catalog)
    args = parser.parse_args(argv)
    if args.same_provider_probe is not None:
        conflicting = [
            option
            for option, value in (
                ("--concurrencies", args.concurrencies),
                ("--repetitions", args.repetitions),
                ("--providers", args.providers),
                ("--sample-ids", args.sample_ids),
            )
            if value is not None
        ]
        if conflicting:
            parser.error(
                "--same-provider-probe cannot be combined with "
                + ", ".join(conflicting)
            )
    report = run_parallel_live_benchmark(
        benchmark_catalog=benchmark_catalog,
        output_dir=Path(args.output_dir),
        providers=args.providers,
        sample_ids=args.sample_ids,
        concurrencies=args.concurrencies,
        repetitions=args.repetitions,
        same_provider_probe=args.same_provider_probe,
    )
    output_root = Path(report.output_dir)
    sys.stdout.write(f"wrote benchmark json to {output_root / 'benchmark.json'}\n")
    sys.stdout.write(f"wrote benchmark markdown to {output_root / 'benchmark.md'}\n")
    for summary in report.summary_by_concurrency:
        sys.stdout.write(
            f"concurrency={summary.concurrency} "
            f"wall={summary.median_wall_seconds:.3f}s "
            f"throughput={summary.median_papers_per_second:.3f} papers/s "
            f"speedup={summary.speedup_vs_baseline:.3f}x "
            f"non_complete={summary.non_complete_results}\n"
        )
    if report.failures:
        sys.stdout.write(f"unexpected failures: {len(report.failures)}\n")
    if report.comparisons:
        sys.stdout.write(f"cross-concurrency drift: {len(report.comparisons)}\n")
    probe = getattr(report, "same_provider_probe", None)
    if probe is not None:
        sys.stdout.write(
            f"same-provider probe {probe['provider']}: {probe['verdict']} "
            f"overlap={str(probe['overlap_observed']).lower()}\n"
        )
    return 0 if report.success else 1


__all__ = ["build_parser", "main"]
