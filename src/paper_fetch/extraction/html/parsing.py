"""Shared HTML parser selection helpers."""

from __future__ import annotations

import importlib.util


def choose_parser() -> str:
    """Prefer lxml when installed, while keeping BeautifulSoup fallback behavior."""

    return "lxml" if importlib.util.find_spec("lxml") is not None else "html.parser"
