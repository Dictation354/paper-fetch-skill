"""Fail closed at real unit boundaries, including aliases and indirect callers.

The audit hook catches Python/shell/fork launches without an executable allowlist.
Canonical source reads are blocked regardless of which HTML/XML extractor is used.
The import finder rejects the converter before loading its heavy dependencies.
"""

from __future__ import annotations
import importlib.abc
import os
from pathlib import Path
import sys
import pytest


UNIT_NODE: str | None = None
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def reject(operation: str) -> None:
    if UNIT_NODE is not None:
        pytest.fail(
            f"unit boundary: {UNIT_NODE}: {operation}; use a minimal snippet/mock "
            "or move the real operation to integration/golden",
            pytrace=False,
        )


def _is_excerpt(path: Path) -> bool:
    from tests.fixture_catalog import fixture_catalog

    record = fixture_catalog().get(path.relative_to(FIXTURES.parents[1]).as_posix())
    return record is not None and record.origin_kind == "real_excerpt"


def audit(event: str, args: tuple) -> None:
    if UNIT_NODE is None:
        return
    if event in {
        "subprocess.Popen",
        "os.system",
        "os.fork",
        "os.forkpty",
        "os.posix_spawn",
        "os.exec",
        "os.spawn",
    }:
        reject("external process")
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(os.path.abspath(os.fsdecode(args[0])))
        if path.suffix.lower() in {
            ".html",
            ".xml",
            ".pdf",
            ".md",
            ".bin",
        } and path.is_relative_to(FIXTURES):
            if (
                "_scenarios" not in path.parts
                and ("golden_criteria" in path.parts or "block" in path.parts)
                and not _is_excerpt(path)
            ):
                reject("canonical full-paper source read")


class ConverterBoundary(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "pymupdf4llm" or fullname.startswith("pymupdf4llm."):
            reject("real PDF conversion backend")
        return None


def install() -> None:
    sys.addaudithook(audit)
    sys.meta_path.insert(0, ConverterBoundary())
