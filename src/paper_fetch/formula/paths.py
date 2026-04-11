"""Path helpers for optional external formula backends."""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path
from typing import Mapping

from ..config import ROOT_DIR, resolve_user_data_dir

FORMULA_TOOLS_DIR_ENV_VAR = "PAPER_FETCH_FORMULA_TOOLS_DIR"
FORMULA_NODE_SCRIPT_NAME = "mathml_to_latex_cli.mjs"
BUNDLED_FORMULA_RESOURCES_PACKAGE = "paper_fetch.resources.formula"


def normalize_optional_path(value: str | os.PathLike[str] | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def repo_root() -> Path | None:
    candidate = ROOT_DIR
    if (candidate / "install-formula-tools.sh").exists() and (candidate / "src" / "paper_fetch").exists():
        return candidate
    return None


def repo_formula_tools_dir() -> Path | None:
    root = repo_root()
    return root / ".formula-tools" if root is not None else None


def default_user_formula_tools_dir(env: Mapping[str, str] | None = None) -> Path:
    active_env = env or os.environ
    configured = normalize_optional_path(active_env.get(FORMULA_TOOLS_DIR_ENV_VAR))
    if configured is not None:
        return configured
    return resolve_user_data_dir(active_env) / "formula-tools"


def formula_tools_search_dirs(env: Mapping[str, str] | None = None) -> list[Path]:
    active_env = env or os.environ
    candidates: list[Path] = []

    explicit = normalize_optional_path(active_env.get(FORMULA_TOOLS_DIR_ENV_VAR))
    if explicit is not None:
        candidates.append(explicit)

    repo_dir = repo_formula_tools_dir()
    if repo_dir is not None and repo_dir not in candidates:
        candidates.append(repo_dir)

    user_dir = resolve_user_data_dir(active_env) / "formula-tools"
    if user_dir not in candidates:
        candidates.append(user_dir)

    return candidates


def formula_tools_subpaths(relative_path: str | Path, env: Mapping[str, str] | None = None) -> list[Path]:
    relative = Path(relative_path)
    return [root / relative for root in formula_tools_search_dirs(env)]


def mathml_to_latex_script_candidates(env: Mapping[str, str] | None = None) -> list[Path]:
    active_env = env or os.environ
    candidates: list[Path] = []

    configured = normalize_optional_path(active_env.get("MATHML_TO_LATEX_SCRIPT"))
    if configured is not None:
        candidates.append(configured)

    for candidate in formula_tools_subpaths(FORMULA_NODE_SCRIPT_NAME, active_env):
        if candidate not in candidates:
            candidates.append(candidate)

    root = repo_root()
    if root is not None:
        repo_script = root / "scripts" / FORMULA_NODE_SCRIPT_NAME
        if repo_script not in candidates:
            candidates.append(repo_script)

    return candidates


def bundled_formula_resources() -> object:
    return files(BUNDLED_FORMULA_RESOURCES_PACKAGE)
