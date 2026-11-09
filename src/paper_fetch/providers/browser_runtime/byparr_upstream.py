"""Load Byparr's unchanged solver with the host's deadline and protocol imports.

The standalone src.utils owns FastAPI/geo setup and uses Python 3.14 syntax;
the embedded controller only needs its timer and logger, on CPython 3.11+.
"""

from __future__ import annotations

import logging
from pathlib import Path
import time
from types import ModuleType

from byparr_engine import playwright_api

logger = logging.getLogger("paper_fetch.byparr.upstream")
api = playwright_api(asynchronous=True)
PlaywrightError = api.Error
PlaywrightTimeoutError = api.TimeoutError


class TimeoutTimer:
    def __init__(self, *, deadline: float):
        self.deadline = deadline

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())


def load_challenge(runtime: Path) -> ModuleType:
    source = (runtime / "upstream/src/challenge.py").read_text()
    replacements = {
        "from invisible_playwright.async_api import Error as PlaywrightError": "from byparr_upstream import PlaywrightError",
        "from invisible_playwright.async_api import TimeoutError as PlaywrightTimeoutError": "from byparr_upstream import PlaywrightTimeoutError",
        "from src.utils import TimeoutTimer, logger": "from byparr_upstream import TimeoutTimer, logger",
    }
    for original, replacement in replacements.items():
        if source.count(original) != 1:
            raise RuntimeError("Pinned Byparr challenge import contract changed")
        source = source.replace(original, replacement)
    module = ModuleType("byparr_challenge")
    exec(
        compile(source, str(runtime / "upstream/src/challenge.py"), "exec"),
        module.__dict__,
    )
    return module
