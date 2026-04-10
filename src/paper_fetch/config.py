"""Runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
ROOT_DIR = SRC_DIR.parent
DEFAULT_ENV_FILE = ROOT_DIR / ".env"
DEFAULT_USER_CONFIG_DIR = Path.home() / ".config" / "paper-fetch"
DEFAULT_USER_ENV_FILE = DEFAULT_USER_CONFIG_DIR / ".env"
DEFAULT_XDG_DATA_HOME = Path.home() / ".local" / "share"
DEFAULT_USER_DATA_DIR = DEFAULT_XDG_DATA_HOME / "paper-fetch"
DEFAULT_MCP_DOWNLOAD_DIR = DEFAULT_USER_DATA_DIR / "downloads"
DEFAULT_CLI_DOWNLOAD_DIR = Path("live-downloads")

DEFAULT_USER_AGENT = "paper-fetch-skill/0.2"
USER_AGENT_ENV_VAR = "PAPER_FETCH_SKILL_USER_AGENT"
ENV_FILE_ENV_VAR = "PAPER_FETCH_ENV_FILE"
DOWNLOAD_DIR_ENV_VAR = "PAPER_FETCH_DOWNLOAD_DIR"
XDG_DATA_HOME_ENV_VAR = "XDG_DATA_HOME"


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple .env file without external dependencies."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value

    return values


def normalize_env_file_path(value: str | os.PathLike[str] | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


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
    - repo-local .env
    """
    process_env = dict(base_env or os.environ)
    explicit_env_file = normalize_env_file_path(env_file)
    configured_env_file = normalize_env_file_path(process_env.get(ENV_FILE_ENV_VAR))

    merged: dict[str, str] = {}
    candidates: list[Path] = [DEFAULT_ENV_FILE, DEFAULT_USER_ENV_FILE]
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
    active_env = env or os.environ
    configured = str(active_env.get(DOWNLOAD_DIR_ENV_VAR, "")).strip()
    if not configured:
        return None
    return Path(configured).expanduser()


def resolve_user_data_dir(env: Mapping[str, str] | None = None) -> Path:
    active_env = env or os.environ
    configured = str(active_env.get(XDG_DATA_HOME_ENV_VAR, "")).strip()
    base_dir = Path(configured).expanduser() if configured else DEFAULT_XDG_DATA_HOME
    return base_dir / "paper-fetch"


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
