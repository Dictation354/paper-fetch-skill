#!/usr/bin/env python3
"""Benchmark MathML-to-LaTeX backends against local XML samples."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from paper_fetch.formula.convert import (
    BENCHMARK_BACKENDS,
    collect_formula_samples,
    convert_mathml_string,
)

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent


def validate_latex(latex: str, *, display_mode: bool, env: dict[str, str]) -> tuple[bool, str | None]:
    node_bin = env.get("MATHML_TO_LATEX_NODE_BIN", "node").strip() or "node"
    validator_script = env.get("LATEX_VALIDATOR_SCRIPT", str(SCRIPT_DIR / "validate_latex_cli.mjs"))
    args = [node_bin, validator_script]
    if display_mode:
        args.append("--display")
    try:
        process = subprocess.run(
            args,
            input=latex,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=ROOT_DIR,
            env=env,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)
    if process.returncode == 0:
        return True, None
    return False, (process.stderr or process.stdout or "validation failed").strip()


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[item["backend"]].append(item)

    summary: dict[str, Any] = {}
    for backend, items in grouped.items():
        total = len(items)
        converted = sum(1 for item in items if item["status"] == "ok")
        validated = sum(1 for item in items if item["validation_status"] == "ok")
        avg_duration = round(sum(item["duration_ms"] for item in items) / total, 2) if total else 0
        summary[backend] = {
            "total": total,
            "converted": converted,
            "validated": validated,
            "conversion_rate": round(converted / total, 4) if total else 0,
            "validation_rate": round(validated / total, 4) if total else 0,
            "avg_duration_ms": avg_duration,
            "failures": [
                {
                    "sample_id": item["sample_id"],
                    "status": item["status"],
                    "error": item["error"],
                    "validation_error": item["validation_error"],
                }
                for item in items
                if item["status"] != "ok" or item["validation_status"] != "ok"
            ][:20],
        }
    return summary


def choose_winner(summary: dict[str, Any]) -> str | None:
    ranked = sorted(
        summary.items(),
        key=lambda item: (
            item[1]["validation_rate"],
            item[1]["conversion_rate"],
            -item[1]["avg_duration_ms"],
            item[0] == "mathml-to-latex",
        ),
        reverse=True,
    )
    return ranked[0][0] if ranked else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xml",
        action="append",
        dest="xml_paths",
        help="XML files to benchmark. Defaults to all live-downloads/*.xml files.",
    )
    parser.add_argument(
        "--per-file-limit",
        type=int,
        default=40,
        help="Maximum number of formulas to extract per XML file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / ".formula-benchmarks" / "formula_backend_report.json",
        help="Path to write the benchmark JSON report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = dict(os.environ)
    xml_paths = [Path(item) for item in args.xml_paths] if args.xml_paths else sorted((ROOT_DIR / "live-downloads").glob("*.xml"))
    samples = collect_formula_samples(xml_paths, per_file_limit=args.per_file_limit)
    results: list[dict[str, Any]] = []

    for sample in samples:
        for backend in BENCHMARK_BACKENDS:
            conversion = convert_mathml_string(
                sample.raw_mathml,
                display_mode=sample.display_mode,
                env=env,
                backend=backend,
            )
            validation_status = "skipped"
            validation_error = None
            if conversion.status == "ok" and conversion.latex:
                valid, validation_error = validate_latex(conversion.latex, display_mode=sample.display_mode, env=env)
                validation_status = "ok" if valid else "failed"
            results.append(
                {
                    "sample_id": sample.sample_id,
                    "source_path": sample.source_path,
                    "source_provider": sample.source_provider,
                    "display_mode": sample.display_mode,
                    "backend": backend,
                    "status": conversion.status,
                    "latex": conversion.latex,
                    "error": conversion.error,
                    "duration_ms": conversion.duration_ms,
                    "validation_status": validation_status,
                    "validation_error": validation_error,
                }
            )

    summary = build_summary(results)
    winner = choose_winner(summary)
    report = {
        "samples": len(samples),
        "winner": winner,
        "summary": summary,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"winner": winner, "samples": len(samples), "summary": summary}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
