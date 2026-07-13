"""Runtime configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping

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

DEFAULT_USER_AGENT = "paper-fetch-skill/3.1.0"
DEFAULT_PUBLISHER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

CONFIG_SOURCE_PROCESS_ENV = "process_env"
CONFIG_SOURCE_EXPLICIT_ENV_FILE = "explicit_env_file"
CONFIG_SOURCE_ENV_VAR_FILE = "env_var_file"
CONFIG_SOURCE_USER_CONFIG = "user_config"
CONFIG_SOURCE_DEFAULT = "default"
CONFIG_SOURCE_UNSET = "unset"
CONFIG_SOURCE_PRECEDENCE = (
    CONFIG_SOURCE_PROCESS_ENV,
    CONFIG_SOURCE_EXPLICIT_ENV_FILE,
    CONFIG_SOURCE_ENV_VAR_FILE,
    CONFIG_SOURCE_USER_CONFIG,
    CONFIG_SOURCE_DEFAULT,
)
USER_AGENT_ENV_VAR = "PAPER_FETCH_SKILL_USER_AGENT"
BROWSER_USER_AGENT_ENV_VAR = "PAPER_FETCH_BROWSER_USER_AGENT"
ENV_FILE_ENV_VAR = "PAPER_FETCH_ENV_FILE"
DOWNLOAD_DIR_ENV_VAR = "PAPER_FETCH_DOWNLOAD_DIR"
XDG_DATA_HOME_ENV_VAR = "XDG_DATA_HOME"
HTTP_POOL_NUM_POOLS_ENV_VAR = "PAPER_FETCH_HTTP_POOL_NUM_POOLS"
HTTP_POOL_MAXSIZE_ENV_VAR = "PAPER_FETCH_HTTP_POOL_MAXSIZE"
HTTP_PER_HOST_CONCURRENCY_ENV_VAR = "PAPER_FETCH_HTTP_PER_HOST_CONCURRENCY"
HTTP_DISK_CACHE_DIR_ENV_VAR = "PAPER_FETCH_HTTP_DISK_CACHE_DIR"
HTTP_DISK_CACHE_ENV_VAR = "PAPER_FETCH_HTTP_DISK_CACHE"
HTTP_METADATA_CACHE_TTL_ENV_VAR = "PAPER_FETCH_HTTP_METADATA_CACHE_TTL"
HTTP_DISK_CACHE_MAX_ENTRIES_ENV_VAR = "PAPER_FETCH_HTTP_DISK_CACHE_MAX_ENTRIES"
HTTP_DISK_CACHE_MAX_BYTES_ENV_VAR = "PAPER_FETCH_HTTP_DISK_CACHE_MAX_BYTES"
HTTP_DISK_CACHE_MAX_AGE_DAYS_ENV_VAR = "PAPER_FETCH_HTTP_DISK_CACHE_MAX_AGE_DAYS"
ASSET_DOWNLOAD_CONCURRENCY_ENV_VAR = "PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY"
DEFAULT_ASSET_DOWNLOAD_CONCURRENCY = 4
CLOAKBROWSER_HEADLESS_ENV_VAR = "CLOAKBROWSER_HEADLESS"
CLOAKBROWSER_BINARY_PATH_ENV_VAR = "CLOAKBROWSER_BINARY_PATH"
CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR = "CLOAKBROWSER_CDP_ENDPOINT"
CDP_EXTERNAL_NEW_CONTEXT_ENV_VAR = "PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT"
CLOAKBROWSER_PROFILE_DIR_ENV_VAR = "CLOAKBROWSER_PROFILE_DIR"
CLOAKBROWSER_USER_DATA_DIR_ENV_VAR = "CLOAKBROWSER_USER_DATA_DIR"
CLOAKBROWSER_TIMEOUT_MS_ENV_VAR = "CLOAKBROWSER_TIMEOUT_MS"
AMS_STORAGE_STATE_JSON_ENV_VAR = "PAPER_FETCH_AMS_STORAGE_STATE_JSON"
WILEY_STORAGE_STATE_JSON_ENV_VAR = "PAPER_FETCH_WILEY_STORAGE_STATE_JSON"
WILEY_PROFILE_DIR_ENV_VAR = "PAPER_FETCH_WILEY_PROFILE_DIR"


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


@dataclass(frozen=True)
class RuntimeEnvResolution:
    """Merged runtime values plus non-secret source metadata."""

    values: dict[str, str]
    sources: dict[str, str]
    layers: tuple[dict[str, object], ...]


def resolve_runtime_env(
    base_env: Mapping[str, str] | None = None,
    *,
    env_file: Path | None = None,
) -> RuntimeEnvResolution:
    """Resolve runtime env and retain the winning source for each key."""

    process_env = dict(_active_env(base_env))
    explicit_env_file = normalize_env_file_path(env_file)
    configured_env_file = normalize_env_file_path(process_env.get(ENV_FILE_ENV_VAR))

    candidates: list[tuple[Path, str]] = []

    def add_candidate(path: Path | None, source: str) -> None:
        if path is None:
            return
        for index, (existing, _) in enumerate(candidates):
            if existing == path:
                candidates[index] = (path, source)
                return
        candidates.append((path, source))

    add_candidate(DEFAULT_USER_ENV_FILE, CONFIG_SOURCE_USER_CONFIG)
    add_candidate(configured_env_file, CONFIG_SOURCE_ENV_VAR_FILE)
    add_candidate(explicit_env_file, CONFIG_SOURCE_EXPLICIT_ENV_FILE)

    merged: dict[str, str] = {}
    sources: dict[str, str] = {}
    for candidate, source in candidates:
        loaded = load_env_file(candidate)
        merged.update(loaded)
        sources.update(dict.fromkeys(loaded, source))
    merged.update(process_env)
    sources.update(dict.fromkeys(process_env, CONFIG_SOURCE_PROCESS_ENV))

    layers = (
        {
            "source": CONFIG_SOURCE_PROCESS_ENV,
            "present": bool(process_env),
        },
        {
            "source": CONFIG_SOURCE_EXPLICIT_ENV_FILE,
            "present": bool(
                explicit_env_file is not None and explicit_env_file.is_file()
            ),
        },
        {
            "source": CONFIG_SOURCE_ENV_VAR_FILE,
            "present": bool(
                configured_env_file is not None and configured_env_file.is_file()
            ),
        },
        {
            "source": CONFIG_SOURCE_USER_CONFIG,
            "present": DEFAULT_USER_ENV_FILE.is_file(),
        },
        {"source": CONFIG_SOURCE_DEFAULT, "present": True},
    )
    return RuntimeEnvResolution(values=merged, sources=sources, layers=layers)


def build_runtime_env(
    base_env: Mapping[str, str] | None = None,
    *,
    env_file: Path | None = None,
) -> dict[str, str]:
    """Merge runtime env using process vars plus layered .env fallbacks.

    Precedence, highest to lowest:
    - process environment / base_env
    - explicit env_file arg
    - file named by PAPER_FETCH_ENV_FILE
    - ~/.config/paper-fetch/.env
    - built-in defaults applied by individual consumers
    """
    return resolve_runtime_env(base_env, env_file=env_file).values


def runtime_configuration_report(
    names: list[str] | tuple[str, ...] | set[str] | frozenset[str],
    *,
    base_env: Mapping[str, str] | None = None,
    env_file: Path | None = None,
    default_names: set[str] | frozenset[str] = frozenset(),
    sensitive_names: set[str] | frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Return source/presence facts without exposing configuration values."""

    resolution = resolve_runtime_env(base_env, env_file=env_file)
    values: list[dict[str, object]] = []
    for name in sorted(set(names)):
        source = resolution.sources.get(name)
        if source is None:
            source = (
                CONFIG_SOURCE_DEFAULT if name in default_names else CONFIG_SOURCE_UNSET
            )
        present = bool(str(resolution.values.get(name, "")).strip())
        values.append(
            {
                "name": name,
                "source": source,
                "present": present,
                "uses_default": source == CONFIG_SOURCE_DEFAULT,
                "sensitive": name in sensitive_names,
            }
        )
    return {
        "precedence": list(CONFIG_SOURCE_PRECEDENCE),
        "layers": [dict(layer) for layer in resolution.layers],
        "values": values,
    }


def build_user_agent(env: Mapping[str, str]) -> str:
    base = env.get(USER_AGENT_ENV_VAR, "").strip() or DEFAULT_USER_AGENT
    mailto = env.get("CROSSREF_MAILTO", "").strip()
    if mailto and "mailto:" not in base and "@" not in base:
        return f"{base} (mailto:{mailto})"
    return base


def build_browser_user_agent(env: Mapping[str, str]) -> str | None:
    browser_user_agent = env.get(BROWSER_USER_AGENT_ENV_VAR, "").strip()
    if browser_user_agent:
        return browser_user_agent
    return None


def build_publisher_user_agent(env: Mapping[str, str]) -> str:
    return (
        env.get(BROWSER_USER_AGENT_ENV_VAR, "").strip() or DEFAULT_PUBLISHER_USER_AGENT
    )


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


def parse_positive_int_env(
    env: Mapping[str, str],
    name: str,
    *,
    default: int,
) -> int:
    raw_value = str(env.get(name, "")).strip()
    if not raw_value:
        return default
    try:
        return max(1, int(raw_value))
    except ValueError:
        return default


def parse_nonnegative_int_env(
    env: Mapping[str, str],
    name: str,
    *,
    default: int,
) -> int:
    raw_value = str(env.get(name, "")).strip()
    if not raw_value:
        return default
    try:
        return max(0, int(raw_value))
    except ValueError:
        return default


def resolve_asset_download_concurrency(env: Mapping[str, str] | None = None) -> int:
    return parse_positive_int_env(
        _active_env(env),
        ASSET_DOWNLOAD_CONCURRENCY_ENV_VAR,
        default=DEFAULT_ASSET_DOWNLOAD_CONCURRENCY,
    )


def env_flag_enabled(env: Mapping[str, str], name: str) -> bool:
    value = str(env.get(name, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}
