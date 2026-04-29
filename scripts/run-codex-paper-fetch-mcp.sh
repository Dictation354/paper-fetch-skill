#!/usr/bin/env bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PAPER_FETCH_MCP_PYTHON_BIN:-python3}"
WSLG_PRESET="$REPO_DIR/vendor/flaresolverr/.env.flaresolverr-source-wslg"
HEADLESS_PRESET="$REPO_DIR/vendor/flaresolverr/.env.flaresolverr-source-headless"
OFFLINE_ENV_FILE="$REPO_DIR/offline.env"

unset_legacy_rate_limit_env() {
    unset FLARESOLVERR_MIN_INTERVAL_SECONDS
    unset FLARESOLVERR_MAX_REQUESTS_PER_HOUR
    unset FLARESOLVERR_MAX_REQUESTS_PER_DAY
}

is_wsl() {
    [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null
}

default_xdg_runtime_dir() {
    printf '/run/user/%s\n' "$(id -u)"
}

ensure_wslg_env() {
    if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
        local candidate
        candidate="$(default_xdg_runtime_dir)"
        if [ -d "$candidate" ]; then
            export XDG_RUNTIME_DIR="$candidate"
        fi
    fi

    if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -n "${XDG_RUNTIME_DIR:-}" ]; then
        for candidate in wayland-0 wayland-1; do
            if [ -S "$XDG_RUNTIME_DIR/$candidate" ]; then
                export WAYLAND_DISPLAY="$candidate"
                break
            fi
        done
    fi

    if [ -z "${DISPLAY:-}" ]; then
        export DISPLAY=":0"
    fi
}

choose_flaresolverr_preset() {
    if [ -n "${PAPER_FETCH_MCP_FLARESOLVERR_ENV_FILE:-}" ]; then
        printf '%s\n' "$PAPER_FETCH_MCP_FLARESOLVERR_ENV_FILE"
        return
    fi

    if ! is_wsl; then
        printf '%s\n' "${FLARESOLVERR_ENV_FILE:-}"
        return
    fi

    if [ -f "$WSLG_PRESET" ] && { [ -n "${WAYLAND_DISPLAY:-}" ] || [ -n "${DISPLAY:-}" ]; }; then
        printf '%s\n' "$WSLG_PRESET"
        return
    fi

    if [ -f "$HEADLESS_PRESET" ]; then
        printf '%s\n' "$HEADLESS_PRESET"
        return
    fi

    printf '%s\n' "${FLARESOLVERR_ENV_FILE:-}"
}

load_offline_env_if_present() {
    if [ -f "$OFFLINE_ENV_FILE" ] && [ -z "${PAPER_FETCH_ENV_FILE:-}" ]; then
        export PAPER_FETCH_ENV_FILE="$OFFLINE_ENV_FILE"
        set -a
        # shellcheck disable=SC1090
        source "$OFFLINE_ENV_FILE"
        set +a
    fi

    if [ -d "$REPO_DIR/ms-playwright" ] && [ -z "${PLAYWRIGHT_BROWSERS_PATH:-}" ]; then
        export PLAYWRIGHT_BROWSERS_PATH="$REPO_DIR/ms-playwright"
    fi
}

main() {
    local preset
    load_offline_env_if_present
    unset_legacy_rate_limit_env
    if is_wsl; then
        ensure_wslg_env
    fi
    preset="$(choose_flaresolverr_preset)"
    if [ -n "$preset" ]; then
        export FLARESOLVERR_ENV_FILE="$preset"
    fi

    exec "$PYTHON_BIN" -m paper_fetch.mcp.server "$@"
}

main "$@"
