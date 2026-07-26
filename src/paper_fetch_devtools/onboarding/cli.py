"""Compatibility loader for the modular onboarding command package."""

from __future__ import annotations

from pathlib import Path
from typing import Any


_PARTS_DIR = Path(__file__).with_name("parts")
_IMPLEMENTATION_PARTS = (
    "bootstrap.py",
    "discovery.py",
    "coordinator.py",
    "state_machine.py",
    "review_artifacts.py",
    "recovery.py",
    "worker_runtime.py",
    "commands.py",
    "summary.py",
    "parser.py",
)


def execute_compatibility_entrypoint(namespace: dict[str, Any]) -> None:
    """Execute the migrated command in the caller's module namespace.

    Existing tests and downstream tooling patch command-module globals.  Using
    the caller namespace preserves that contract while the implementation is
    physically owned by ``paper_fetch_devtools.onboarding``.
    """

    for filename in _IMPLEMENTATION_PARTS:
        path = _PARTS_DIR / filename
        source = path.read_bytes()
        exec(compile(source, str(path), "exec"), namespace, namespace)


__all__ = ["execute_compatibility_entrypoint"]
