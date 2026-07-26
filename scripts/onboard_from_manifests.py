#!/usr/bin/env python3
"""Compatibility entrypoint for the provider-onboarding devtool."""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from paper_fetch_devtools.onboarding.cli import (  # noqa: E402
    execute_compatibility_entrypoint,
)


execute_compatibility_entrypoint(globals())
