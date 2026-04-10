"""Shared test-path helpers."""

from __future__ import annotations

from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TESTS_ROOT.parent
FIXTURE_DIR = TESTS_ROOT / "fixtures"
SRC_DIR = REPO_ROOT / "src"
SKILL_DIR = REPO_ROOT / "skills" / "paper-fetch-skill"
