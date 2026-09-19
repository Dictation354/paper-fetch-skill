"""Shared test support; contains no collected tests."""

from __future__ import annotations
from pathlib import Path
from paper_fetch.providers.browser_runtime import (
    BrowserRuntimeConfig,
)


def _runtime_config(tmp_path: Path, *, provider: str, doi: str) -> BrowserRuntimeConfig:
    return BrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=tmp_path / "artifacts" / provider,
        headless=True,
        user_agent=None,
    )
