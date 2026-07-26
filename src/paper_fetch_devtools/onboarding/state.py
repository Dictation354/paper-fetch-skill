"""Onboarding coordinator state persistence."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any


def default_state(*, agent_cli: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "agent_cli": agent_cli,
        "active_provider": None,
        "providers": {},
    }


def load_state(
    path: Path,
    *,
    agent_cli: str,
    default_factory: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    if not path.exists():
        return default_factory()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"state root must be an object: {path}")
    data.setdefault("schema_version", 1)
    data["agent_cli"] = agent_cli or data.get("agent_cli")
    data.setdefault("active_provider", None)
    providers = data.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise ValueError(f"state providers must be an object: {path}")
    return data


def write_json(
    path: Path,
    data: dict[str, Any],
    *,
    write_text: Callable[[Path, str], None],
) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


__all__ = ["default_state", "load_state", "write_json"]
