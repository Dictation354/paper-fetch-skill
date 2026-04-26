"""Runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values
from platformdirs import user_config_path, user_data_path

APP_NAME = "paper-fetch"
DEFAULT_USER_CONFIG_DIR = user_config_path(APP_NAME, appauthor=False)
DEFAULT_USER_ENV_FILE = DEFAULT_USER_CONFIG_DIR / ".env"
DEFAULT_USER_DATA_DIR = user_data_path(APP_NAME, appauthor=False)
DEFAULT_XDG_DATA_HOME = DEFAULT_USER_DATA_DIR.parent
DEFAULT_MCP_DOWNLOAD_DIR = DEFAULT_USER_DATA_DIR / "downloads"
DEFAULT_CLI_DOWNLOAD_DIR = Path("live-downloads")
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VENDOR_FLARESOLVERR_DIR = DEFAULT_REPO_ROOT / "vendor" / "flaresolverr"
DEFAULT_FLARESOLVERR_URL = "http://127.0.0.1:8191/v1"

DEFAULT_USER_AGENT = "paper-fetch-skill/0.2"
USER_AGENT_ENV_VAR = "PAPER_FETCH_SKILL_USER_AGENT"
ENV_FILE_ENV_VAR = "PAPER_FETCH_ENV_FILE"
DOWNLOAD_DIR_ENV_VAR = "PAPER_FETCH_DOWNLOAD_DIR"
XDG_DATA_HOME_ENV_VAR = "XDG_DATA_HOME"
FLARESOLVERR_URL_ENV_VAR = "FLARESOLVERR_URL"
FLARESOLVERR_ENV_FILE_ENV_VAR = "FLARESOLVERR_ENV_FILE"
FLARESOLVERR_SOURCE_DIR_ENV_VAR = "FLARESOLVERR_SOURCE_DIR"
FLARESOLVERR_MIN_INTERVAL_SECONDS_ENV_VAR = "FLARESOLVERR_MIN_INTERVAL_SECONDS"
FLARESOLVERR_MAX_REQUESTS_PER_HOUR_ENV_VAR = "FLARESOLVERR_MAX_REQUESTS_PER_HOUR"
FLARESOLVERR_MAX_REQUESTS_PER_DAY_ENV_VAR = "FLARESOLVERR_MAX_REQUESTS_PER_DAY"


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    return {
        str(key): value
        for key, value in dotenv_values(path, interpolate=False).items()
        if key and value is not None
    }


def normalize_env_file_path(value: str | os.PathLike[str] | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def _active_env(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if env is None else env


def build_runtime_env(
    base_env: Mapping[str, str] | None = None,
    *,
    env_file: Path | None = None,
) -> dict[str, str]:
    """Merge runtime env using process vars plus layered .env fallbacks.

    Precedence, highest to lowest:
    - process environment / base_env
    - explicit env_file arg or PAPER_FETCH_ENV_FILE
    - ~/.config/paper-fetch/.env
    """
    process_env = dict(_active_env(base_env))
    explicit_env_file = normalize_env_file_path(env_file)
    configured_env_file = normalize_env_file_path(process_env.get(ENV_FILE_ENV_VAR))

    merged: dict[str, str] = {}
    candidates: list[Path] = [DEFAULT_USER_ENV_FILE]
    for candidate in (configured_env_file, explicit_env_file):
        if candidate is not None and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        merged.update(load_env_file(candidate))
    merged.update(process_env)
    return merged


def build_user_agent(env: Mapping[str, str]) -> str:
    base = env.get(USER_AGENT_ENV_VAR, "").strip() or DEFAULT_USER_AGENT
    mailto = env.get("CROSSREF_MAILTO", "").strip()
    if mailto and "mailto:" not in base and "@" not in base:
        return f"{base} (mailto:{mailto})"
    return base


def _configured_download_dir(env: Mapping[str, str] | None = None) -> Path | None:
    active_env = _active_env(env)
    configured = str(active_env.get(DOWNLOAD_DIR_ENV_VAR, "")).strip()
    if not configured:
        return None
    return Path(configured).expanduser()


def resolve_user_data_dir(env: Mapping[str, str] | None = None) -> Path:
    active_env = _active_env(env)
    configured = str(active_env.get(XDG_DATA_HOME_ENV_VAR, "")).strip()
    if configured:
        return Path(configured).expanduser() / APP_NAME
    return DEFAULT_USER_DATA_DIR


def resolve_cli_download_dir(env: Mapping[str, str] | None = None) -> Path:
    configured = _configured_download_dir(env)
    if configured is not None:
        return configured
    preferred = resolve_user_data_dir(env) / "downloads"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
    except OSError:
        return DEFAULT_CLI_DOWNLOAD_DIR
    return preferred


def resolve_mcp_download_dir(env: Mapping[str, str] | None = None) -> Path:
    configured = _configured_download_dir(env)
    return configured or (resolve_user_data_dir(env) / "downloads")


def resolve_repo_root() -> Path:
    return DEFAULT_REPO_ROOT


def resolve_flaresolverr_source_dir(env: Mapping[str, str] | None = None) -> Path:
    active_env = _active_env(env)
    configured = str(active_env.get(FLARESOLVERR_SOURCE_DIR_ENV_VAR, "")).strip()
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_VENDOR_FLARESOLVERR_DIR


def resolve_flaresolverr_env_file(env: Mapping[str, str] | None = None) -> Path | None:
    active_env = _active_env(env)
    configured = str(active_env.get(FLARESOLVERR_ENV_FILE_ENV_VAR, "")).strip()
    if not configured:
        return None
    return Path(configured).expanduser()


def resolve_flaresolverr_url(env: Mapping[str, str] | None = None) -> str:
    active_env = _active_env(env)
    return str(active_env.get(FLARESOLVERR_URL_ENV_VAR, "")).strip() or DEFAULT_FLARESOLVERR_URL


def configured_int_env(name: str, env: Mapping[str, str] | None = None) -> int | None:
    active_env = _active_env(env)
    raw = str(active_env.get(name, "")).strip()
    if not raw:
        return None
    return int(raw)
