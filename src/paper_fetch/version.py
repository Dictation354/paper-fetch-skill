"""Resolve the package version from the canonical project metadata."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
import tomllib

DIST_NAME = "paper-fetch-skill"


def package_version() -> str:
    """Return the source checkout or installed distribution version."""

    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        project = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get(
            "project", {}
        )
        version = project.get("version") if isinstance(project, dict) else None
        if version:
            return str(version)
    except (OSError, tomllib.TOMLDecodeError):
        pass
    try:
        return importlib.metadata.version(DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


__version__ = package_version()

__all__ = ["DIST_NAME", "__version__", "package_version"]
