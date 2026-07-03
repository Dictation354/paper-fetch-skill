"""Path helpers for optional external image conversion tools."""

from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path
from collections.abc import Mapping

from ..config import resolve_user_data_dir

IMAGE_TOOLS_DIR_ENV_VAR = "PAPER_FETCH_IMAGE_TOOLS_DIR"
IMAGE_TOOL_TIMEOUT_SECONDS_ENV_VAR = "PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS"
DEFAULT_IMAGE_TOOL_TIMEOUT_SECONDS = 120
GHOSTSCRIPT_EXECUTABLE_NAMES = ("gs", "gswin64c.exe", "gswin32c.exe", "gs.exe")
VIPS_EXECUTABLE_NAMES = ("vips", "vips.exe")
_IMAGE_TOOL_CANDIDATE_CACHE_SIZE = 64


def _env_text(env: Mapping[str, str], name: str) -> str:
    return str(env.get(name) or "")


def _path_fingerprint(path: Path) -> tuple[str, bool, int, int]:
    try:
        stat_result = path.stat()
    except OSError:
        return (str(path), False, 0, 0)
    return (
        str(path),
        True,
        int(stat_result.st_mtime_ns),
        int(stat_result.st_size),
    )


def normalize_optional_path(value: str | os.PathLike[str] | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def repo_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[3]
    if (candidate / "install.sh").exists() and (
        candidate / "src" / "paper_fetch"
    ).exists():
        return candidate
    return None


def repo_image_tools_dir() -> Path | None:
    root = repo_root()
    return root / ".image-tools" if root is not None else None


def default_user_image_tools_dir(env: Mapping[str, str] | None = None) -> Path:
    active_env = env or os.environ
    configured = normalize_optional_path(active_env.get(IMAGE_TOOLS_DIR_ENV_VAR))
    if configured is not None:
        return configured
    return resolve_user_data_dir(active_env) / "image-tools"


def image_tool_timeout_seconds(env: Mapping[str, str] | None = None) -> int:
    active_env = env or os.environ
    value = str(active_env.get(IMAGE_TOOL_TIMEOUT_SECONDS_ENV_VAR) or "").strip()
    if not value:
        return DEFAULT_IMAGE_TOOL_TIMEOUT_SECONDS
    try:
        parsed = int(value)
    except ValueError:
        return DEFAULT_IMAGE_TOOL_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_IMAGE_TOOL_TIMEOUT_SECONDS


def image_tools_search_dirs(env: Mapping[str, str] | None = None) -> list[Path]:
    active_env = env or os.environ
    candidates: list[Path] = []

    explicit = normalize_optional_path(active_env.get(IMAGE_TOOLS_DIR_ENV_VAR))
    if explicit is not None:
        candidates.append(explicit)

    repo_dir = repo_image_tools_dir()
    if repo_dir is not None and repo_dir not in candidates:
        candidates.append(repo_dir)

    user_dir = resolve_user_data_dir(active_env) / "image-tools"
    if user_dir not in candidates:
        candidates.append(user_dir)

    return candidates


def _subpath_candidates(root: Path, names: tuple[str, ...]) -> list[Path]:
    candidates: list[Path] = []
    relative_dirs = (
        Path("bin"),
        Path("ghostscript-runtime/root/usr/bin"),
        Path("ghostscript/bin"),
        Path("gs/bin"),
        Path("vips/bin"),
        Path("libvips/bin"),
    )
    for directory in relative_dirs:
        for name in names:
            candidate = root / directory / name
            if candidate not in candidates:
                candidates.append(candidate)
    for pattern in ("vips-dev-*/bin", "vips-*/bin", "ghostscript-*/bin"):
        for directory in root.glob(pattern):
            for name in names:
                candidate = directory / name
                if candidate not in candidates:
                    candidates.append(candidate)
    return candidates


@lru_cache(maxsize=_IMAGE_TOOL_CANDIDATE_CACHE_SIZE)
def _binary_candidates_cached(
    cache_key: tuple[object, ...],
    *,
    configured: str,
    roots: tuple[str, ...],
    names: tuple[str, ...],
    path: str | None,
) -> tuple[str, ...]:
    del cache_key
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))

    for root_text in roots:
        for candidate in _subpath_candidates(Path(root_text), names):
            if candidate not in candidates:
                candidates.append(candidate)

    for name in names:
        system = shutil.which(name, path=path)
        if system:
            candidate = Path(system)
            if candidate not in candidates:
                candidates.append(candidate)
    return tuple(str(candidate) for candidate in candidates)


def _binary_candidates(
    *,
    env: Mapping[str, str] | None,
    configured_env_name: str,
    names: tuple[str, ...],
) -> list[Path]:
    active_env = env or os.environ
    configured = normalize_optional_path(active_env.get(configured_env_name))
    roots = tuple(image_tools_search_dirs(active_env))
    path_value = active_env.get("PATH")
    cache_key = (
        configured_env_name,
        tuple(names),
        str(configured or ""),
        _env_text(active_env, IMAGE_TOOLS_DIR_ENV_VAR),
        _env_text(active_env, "XDG_DATA_HOME"),
        _env_text(active_env, "PATH"),
        tuple(_path_fingerprint(root) for root in roots),
    )
    return [
        Path(candidate)
        for candidate in _binary_candidates_cached(
            cache_key,
            configured=str(configured or ""),
            roots=tuple(str(root) for root in roots),
            names=names,
            path=path_value,
        )
    ]


def _clear_image_tool_path_caches() -> None:
    _binary_candidates_cached.cache_clear()


def ghostscript_binary_candidates(env: Mapping[str, str] | None = None) -> list[Path]:
    return _binary_candidates(
        env=env,
        configured_env_name="PAPER_FETCH_GHOSTSCRIPT_BIN",
        names=GHOSTSCRIPT_EXECUTABLE_NAMES,
    )


def vips_binary_candidates(env: Mapping[str, str] | None = None) -> list[Path]:
    return _binary_candidates(
        env=env,
        configured_env_name="PAPER_FETCH_VIPS_BIN",
        names=VIPS_EXECUTABLE_NAMES,
    )


__all__ = [
    "DEFAULT_IMAGE_TOOL_TIMEOUT_SECONDS",
    "GHOSTSCRIPT_EXECUTABLE_NAMES",
    "IMAGE_TOOLS_DIR_ENV_VAR",
    "IMAGE_TOOL_TIMEOUT_SECONDS_ENV_VAR",
    "VIPS_EXECUTABLE_NAMES",
    "default_user_image_tools_dir",
    "ghostscript_binary_candidates",
    "image_tool_timeout_seconds",
    "image_tools_search_dirs",
    "normalize_optional_path",
    "repo_image_tools_dir",
    "repo_root",
    "vips_binary_candidates",
]
