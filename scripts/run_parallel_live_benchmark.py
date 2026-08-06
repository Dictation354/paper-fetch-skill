#!/usr/bin/env python3
"""Run the multi-paper parallel golden live benchmark."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from paper_fetch_devtools.golden_criteria.benchmark_cli import main  # noqa: E402
from tests.provider_benchmark_samples import (  # noqa: E402
    PROVIDER_BENCHMARK_SAMPLES,
)


if __name__ == "__main__":
    raise SystemExit(main(benchmark_catalog=PROVIDER_BENCHMARK_SAMPLES))
