#!/usr/bin/env python3
"""Run the golden criteria live review pipeline without MCP."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paper_fetch_devtools.golden_criteria.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
