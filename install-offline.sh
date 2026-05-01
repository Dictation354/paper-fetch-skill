#!/usr/bin/env bash
# Offline installer for the Linux x86_64 CPython ABI-specific bundle.

set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PAPER_FETCH_OFFLINE_PYTHON_BIN:-python3}"
XVFB_BIN="${PAPER_FETCH_OFFLINE_XVFB_BIN:-Xvfb}"
PRESET="headless"
MERGE_USER_CONFIG=0
RUN_SMOKE=1
UNINSTALL=0
OFFLINE_ENV_FILE="$BUNDLE_ROOT/offline.env"
REUSE_ENV_FILE=0

MANAGED_BEGIN="# BEGIN paper-fetch offline managed"
MANAGED_END="# END paper-fetch offline managed"
CODEX_MANAGED_BEGIN="# BEGIN paper-fetch installer managed"
CODEX_MANAGED_END="# END paper-fetch installer managed"
SKILL_NAME="paper-fetch-skill"
MCP_NAME="paper-fetch"
MCP_ENV_KEYS=(
  PYTHONUTF8
  PYTHONIOENCODING
  PAPER_FETCH_ENV_FILE
  PAPER_FETCH_MCP_PYTHON_BIN
  PAPER_FETCH_DOWNLOAD_DIR
  PAPER_FETCH_FORMULA_TOOLS_DIR
  PLAYWRIGHT_BROWSERS_PATH
  FLARESOLVERR_URL
  FLARESOLVERR_ENV_FILE
  FLARESOLVERR_SOURCE_DIR
)

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  ./install-offline.sh [--preset=headless|wslg] [--user-config] [--reuse-env-file <path>]
  ./install-offline.sh --uninstall

Options:
  --preset=headless|wslg  Select the bundled FlareSolverr preset. Default: headless.
  --user-config           Also merge the offline runtime block into ~/.config/paper-fetch/.env.
  --no-user-config        Do not touch ~/.config/paper-fetch/.env. This is the default.
  --reuse-env-file <path> Use an existing offline.env without modifying it.
  --skip-smoke            Skip local command smoke checks after installation.
  --uninstall             Remove user-level shell, skill, and MCP integration without deleting this bundle.
  -h, --help              Show this help.
EOF
}

normalize_path() {
  local value="$1"
  case "$value" in
    "~")
      [ -n "${HOME:-}" ] || die "HOME is required to expand ~."
      printf '%s\n' "$HOME"
      ;;
    "~/"*)
      [ -n "${HOME:-}" ] || die "HOME is required to expand ~."
      printf '%s/%s\n' "$HOME" "${value#~/}"
      ;;
    /*)
      printf '%s\n' "$value"
      ;;
    *)
      printf '%s/%s\n' "$(pwd)" "$value"
      ;;
  esac
}

while (($#)); do
  case "$1" in
    --preset=*)
      PRESET="${1#*=}"
      ;;
    --preset)
      shift
      [ "$#" -gt 0 ] || die "--preset requires headless or wslg"
      PRESET="$1"
      ;;
    --user-config)
      MERGE_USER_CONFIG=1
      ;;
    --no-user-config)
      MERGE_USER_CONFIG=0
      ;;
    --reuse-env-file=*)
      OFFLINE_ENV_FILE="$(normalize_path "${1#*=}")"
      REUSE_ENV_FILE=1
      ;;
    --reuse-env-file)
      shift
      [ "$#" -gt 0 ] || die "--reuse-env-file requires a path"
      OFFLINE_ENV_FILE="$(normalize_path "$1")"
      REUSE_ENV_FILE=1
      ;;
    --skip-smoke)
      RUN_SMOKE=0
      ;;
    --uninstall)
      UNINSTALL=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
  shift
done

if [ "$UNINSTALL" != "1" ]; then
  case "$PRESET" in
    headless|wslg) ;;
    *) die "--preset must be headless or wslg" ;;
  esac
  if [ "$REUSE_ENV_FILE" = "1" ]; then
    [ -f "$OFFLINE_ENV_FILE" ] || die "Missing reusable offline env file: $OFFLINE_ENV_FILE"
  fi
fi

require_file() {
  [ -f "$1" ] || die "Missing required bundled file: $1"
}

require_dir() {
  [ -d "$1" ] || die "Missing required bundled directory: $1"
}

quote_env_value() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//\$/\\$}"
  value="${value//\`/\\\`}"
  printf '"%s"' "$value"
}

quote_toml_value() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

check_platform() {
  local kernel machine
  kernel="$(uname -s)"
  machine="$(uname -m)"
  [ "$kernel" = "Linux" ] || die "This offline bundle supports Linux only; detected $kernel."
  case "$machine" in
    x86_64|amd64) ;;
    *) die "This offline bundle supports x86_64 only; detected $machine." ;;
  esac
}

check_python() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "python3 was not found on PATH."
  require_file "$BUNDLE_ROOT/offline-manifest.json"

  local version tag manifest_tag
  version="$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  tag="$("$PYTHON_BIN" -c 'import sys; print(f"cp{sys.version_info.major}{sys.version_info.minor}" if sys.implementation.name == "cpython" else sys.implementation.name)')"
  manifest_tag="$("$PYTHON_BIN" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("target", {}).get("python_tag", ""))' "$BUNDLE_ROOT/offline-manifest.json")"
  [ -n "$manifest_tag" ] || die "offline-manifest.json is missing target.python_tag."
  [ "$tag" = "$manifest_tag" ] || die "bundle requires CPython $manifest_tag; detected Python $version ($tag)."
}

verify_checksums() {
  require_file "$BUNDLE_ROOT/sha256sums.txt"
  command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required to verify the offline bundle."
  log "Verifying bundled file checksums"
  (cd "$BUNDLE_ROOT" && sha256sum --check sha256sums.txt --quiet)
}

find_project_wheel() {
  shopt -s nullglob
  local wheels=("$BUNDLE_ROOT"/dist/paper_fetch_skill-*.whl)
  if [ "${#wheels[@]}" -eq 0 ]; then
    wheels=("$BUNDLE_ROOT"/wheelhouse/paper_fetch_skill-*.whl)
  fi
  shopt -u nullglob
  [ "${#wheels[@]}" -eq 1 ] || die "Expected exactly one paper_fetch_skill wheel, found ${#wheels[@]}."
  printf '%s\n' "${wheels[0]}"
}

check_preset_requirements() {
  if [ "$PRESET" = "headless" ]; then
    command -v "$XVFB_BIN" >/dev/null 2>&1 || die "Xvfb is required for --preset=headless. Install the system xvfb package or use --preset=wslg when DISPLAY/WAYLAND_DISPLAY is available."
    return
  fi

  if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    die "DISPLAY or WAYLAND_DISPLAY is required for --preset=wslg."
  fi
}

check_bundle_assets() {
  require_dir "$BUNDLE_ROOT/wheelhouse"
  require_dir "$BUNDLE_ROOT/ms-playwright"
  require_file "$BUNDLE_ROOT/formula-tools/bin/texmath"
  [ -x "$BUNDLE_ROOT/formula-tools/bin/texmath" ] || die "Bundled texmath is not executable: $BUNDLE_ROOT/formula-tools/bin/texmath"

  local flaresolverr_dir="$BUNDLE_ROOT/vendor/flaresolverr"
  require_dir "$flaresolverr_dir"
  require_dir "$flaresolverr_dir/wheelhouse"
  require_file "$flaresolverr_dir/.env.flaresolverr-source-$PRESET"
  require_file "$flaresolverr_dir/.work/FlareSolverr/src/flaresolverr.py"
  require_file "$flaresolverr_dir/.work/FlareSolverr/requirements.txt"
  require_file "$flaresolverr_dir/.flaresolverr/v3.4.6/flaresolverr/_internal/chrome/chrome"

  for name in \
    setup_flaresolverr_source.sh \
    start_flaresolverr_source.sh \
    run_flaresolverr_source.sh \
    stop_flaresolverr_source.sh \
    flaresolverr_source_common.sh; do
    require_file "$flaresolverr_dir/$name"
  done

  require_file "$BUNDLE_ROOT/skills/$SKILL_NAME/SKILL.md"
}

install_project_venv() {
  local project_wheel="$1"
  local venv_dir="$BUNDLE_ROOT/.venv"

  if [ ! -x "$venv_dir/bin/python" ]; then
    log "Creating Python virtual environment at $venv_dir"
    "$PYTHON_BIN" -m venv "$venv_dir"
  fi

  export PIP_NO_INDEX=1
  export PIP_FIND_LINKS="$BUNDLE_ROOT/wheelhouse"
  export PIP_DISABLE_PIP_VERSION_CHECK=1
  export PIP_NO_BUILD_ISOLATION=1
  export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
  export PLAYWRIGHT_BROWSERS_PATH="$BUNDLE_ROOT/ms-playwright"

  case "$PLAYWRIGHT_BROWSERS_PATH" in
    "$HOME"/.cache/ms-playwright|"$HOME"/.cache/ms-playwright/*)
      die "PLAYWRIGHT_BROWSERS_PATH must not point at the user cache: $PLAYWRIGHT_BROWSERS_PATH"
      ;;
  esac

  log "Installing paper-fetch-skill from bundled wheelhouse"
  "$venv_dir/bin/python" -m pip install \
    --no-index \
    --find-links "$BUNDLE_ROOT/wheelhouse" \
    --only-binary=:all: \
    "$project_wheel"

  [ -x "$venv_dir/bin/paper-fetch" ] || die "Installed CLI is missing or not executable: $venv_dir/bin/paper-fetch"
  [ -x "$venv_dir/bin/paper-fetch-mcp" ] || die "Installed MCP CLI is missing or not executable: $venv_dir/bin/paper-fetch-mcp"
}

install_flaresolverr_venv() {
  local flaresolverr_dir="$BUNDLE_ROOT/vendor/flaresolverr"
  local source_dir="$flaresolverr_dir/.work/FlareSolverr"
  local venv_dir="$flaresolverr_dir/.venv-flaresolverr"
  local preset_file="$flaresolverr_dir/.env.flaresolverr-source-$PRESET"

  if [ ! -x "$venv_dir/bin/python" ]; then
    log "Creating FlareSolverr virtual environment at $venv_dir"
    "$PYTHON_BIN" -m venv "$venv_dir"
  fi

  log "Installing FlareSolverr Python dependencies from bundled wheelhouse"
  PIP_NO_INDEX=1 \
  PIP_FIND_LINKS="$flaresolverr_dir/wheelhouse" \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  "$venv_dir/bin/python" -m pip install \
    --no-index \
    --find-links "$flaresolverr_dir/wheelhouse" \
    --only-binary=:all: \
    -r "$source_dir/requirements.txt"

  # shellcheck disable=SC1091
  source "$flaresolverr_dir/flaresolverr_source_common.sh"
  flaresolverr_source_load_env "$preset_file"
  flaresolverr_source_ensure_chrome_link
}

mcp_python_bin() {
  printf '%s\n' "$BUNDLE_ROOT/.venv/bin/python"
}

mcp_env_value() {
  local key="$1"
  case "$key" in
    PYTHONUTF8) printf '1\n' ;;
    PYTHONIOENCODING) printf 'utf-8\n' ;;
    PAPER_FETCH_ENV_FILE) printf '%s\n' "$OFFLINE_ENV_FILE" ;;
    PAPER_FETCH_MCP_PYTHON_BIN) mcp_python_bin ;;
    PAPER_FETCH_DOWNLOAD_DIR) printf '%s\n' "$BUNDLE_ROOT/downloads" ;;
    PAPER_FETCH_FORMULA_TOOLS_DIR) printf '%s\n' "$BUNDLE_ROOT/formula-tools" ;;
    PLAYWRIGHT_BROWSERS_PATH) printf '%s\n' "$BUNDLE_ROOT/ms-playwright" ;;
    FLARESOLVERR_URL) printf 'http://127.0.0.1:8191/v1\n' ;;
    FLARESOLVERR_ENV_FILE) printf '%s\n' "$BUNDLE_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET" ;;
    FLARESOLVERR_SOURCE_DIR) printf '%s\n' "$BUNDLE_ROOT/vendor/flaresolverr" ;;
    *) die "Unknown MCP env key: $key" ;;
  esac
}

copy_installed_skill() {
  local destination="$1"
  local source="$BUNDLE_ROOT/skills/$SKILL_NAME"

  require_file "$source/SKILL.md"
  rm -rf "$destination"
  mkdir -p "$destination"
  cp -a "$source/." "$destination/"
}

install_skills() {
  [ -n "${HOME:-}" ] || die "HOME is required to install Codex and Claude skills."

  local codex_skill="$HOME/.codex/skills/$SKILL_NAME"
  local claude_skill="$HOME/.claude/skills/$SKILL_NAME"

  log "Installing Codex skill to $codex_skill"
  copy_installed_skill "$codex_skill"
  log "Installing Claude Code skill to $claude_skill"
  copy_installed_skill "$claude_skill"
}

select_shell_startup_file() {
  [ -n "${HOME:-}" ] || die "HOME is required to update shell startup files."

  SHELL_STARTUP_STYLE="posix"
  case "$(basename "${SHELL:-}")" in
    bash)
      SHELL_STARTUP_TARGET="$HOME/.bashrc"
      ;;
    zsh)
      SHELL_STARTUP_TARGET="$HOME/.zshrc"
      ;;
    fish)
      SHELL_STARTUP_TARGET="$HOME/.config/fish/conf.d/paper-fetch-offline.fish"
      SHELL_STARTUP_STYLE="fish"
      ;;
    *)
      SHELL_STARTUP_TARGET="$HOME/.profile"
      warn "Unrecognized SHELL=${SHELL:-}; writing offline environment to $SHELL_STARTUP_TARGET"
      ;;
  esac
}

write_posix_shell_block() {
  printf '%s\n' "$MANAGED_BEGIN"
  printf 'export PATH=%s:%s:$PATH\n' "$(quote_env_value "$BUNDLE_ROOT/.venv/bin")" "$(quote_env_value "$BUNDLE_ROOT/formula-tools/bin")"
  printf 'export PAPER_FETCH_ENV_FILE=%s\n' "$(quote_env_value "$OFFLINE_ENV_FILE")"
  printf 'export PAPER_FETCH_DOWNLOAD_DIR=%s\n' "$(quote_env_value "$BUNDLE_ROOT/downloads")"
  printf 'export PAPER_FETCH_FORMULA_TOOLS_DIR=%s\n' "$(quote_env_value "$BUNDLE_ROOT/formula-tools")"
  printf 'export PLAYWRIGHT_BROWSERS_PATH=%s\n' "$(quote_env_value "$BUNDLE_ROOT/ms-playwright")"
  printf 'export FLARESOLVERR_SOURCE_DIR=%s\n' "$(quote_env_value "$BUNDLE_ROOT/vendor/flaresolverr")"
  printf 'export FLARESOLVERR_ENV_FILE=%s\n' "$(quote_env_value "$BUNDLE_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET")"
  printf 'export FLARESOLVERR_URL=%s\n' "$(quote_env_value "http://127.0.0.1:8191/v1")"
  printf '%s\n' "$MANAGED_END"
}

write_fish_shell_block() {
  printf '%s\n' "$MANAGED_BEGIN"
  printf 'set -gx PATH %s %s $PATH\n' "$(quote_env_value "$BUNDLE_ROOT/.venv/bin")" "$(quote_env_value "$BUNDLE_ROOT/formula-tools/bin")"
  printf 'set -gx PAPER_FETCH_ENV_FILE %s\n' "$(quote_env_value "$OFFLINE_ENV_FILE")"
  printf 'set -gx PAPER_FETCH_DOWNLOAD_DIR %s\n' "$(quote_env_value "$BUNDLE_ROOT/downloads")"
  printf 'set -gx PAPER_FETCH_FORMULA_TOOLS_DIR %s\n' "$(quote_env_value "$BUNDLE_ROOT/formula-tools")"
  printf 'set -gx PLAYWRIGHT_BROWSERS_PATH %s\n' "$(quote_env_value "$BUNDLE_ROOT/ms-playwright")"
  printf 'set -gx FLARESOLVERR_SOURCE_DIR %s\n' "$(quote_env_value "$BUNDLE_ROOT/vendor/flaresolverr")"
  printf 'set -gx FLARESOLVERR_ENV_FILE %s\n' "$(quote_env_value "$BUNDLE_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET")"
  printf 'set -gx FLARESOLVERR_URL %s\n' "$(quote_env_value "http://127.0.0.1:8191/v1")"
  printf '%s\n' "$MANAGED_END"
}

write_shell_startup_file() {
  local tmp mode

  select_shell_startup_file
  tmp="$(mktemp)"
  mode=""
  mkdir -p "$(dirname "$SHELL_STARTUP_TARGET")"
  if [ -f "$SHELL_STARTUP_TARGET" ]; then
    mode="$(stat -c '%a' "$SHELL_STARTUP_TARGET" 2>/dev/null || true)"
    awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$SHELL_STARTUP_TARGET" > "$tmp"
  else
    : > "$tmp"
  fi

  {
    printf '\n'
    if [ "$SHELL_STARTUP_STYLE" = "fish" ]; then
      write_fish_shell_block
    else
      write_posix_shell_block
    fi
  } >> "$tmp"

  mv "$tmp" "$SHELL_STARTUP_TARGET"
  if [ -n "$mode" ]; then
    chmod "$mode" "$SHELL_STARTUP_TARGET"
  fi
  log "Updated shell startup file at $SHELL_STARTUP_TARGET"
}

write_codex_config_toml() {
  [ -n "${HOME:-}" ] || die "HOME is required to update Codex MCP config."

  local codex_home="$HOME/.codex"
  local config_path="$codex_home/config.toml"
  local tmp key
  tmp="$(mktemp)"
  mkdir -p "$codex_home"

  if [ -f "$config_path" ]; then
    awk -v begin="$CODEX_MANAGED_BEGIN" -v end="$CODEX_MANAGED_END" -v old_begin="$MANAGED_BEGIN" -v old_end="$MANAGED_END" '
      $0 == begin || $0 == old_begin { skip_block = 1; next }
      $0 == end || $0 == old_end { skip_block = 0; next }
      skip_block { next }
      $0 ~ /^[[:space:]]*\[mcp_servers\.paper-fetch(\..*)?\][[:space:]]*$/ { skip_table = 1; next }
      skip_table && $0 ~ /^[[:space:]]*\[/ { skip_table = 0 }
      !skip_table { print }
    ' "$config_path" > "$tmp"
  else
    : > "$tmp"
  fi

  {
    printf '\n%s\n' "$CODEX_MANAGED_BEGIN"
    printf '[mcp_servers.paper-fetch]\n'
    printf 'command = %s\n' "$(quote_toml_value "$(mcp_python_bin)")"
    printf 'args = ["-X", "utf8", "-m", "paper_fetch.mcp.server"]\n'
    printf '\n[mcp_servers.paper-fetch.env]\n'
    for key in "${MCP_ENV_KEYS[@]}"; do
      printf '%s = %s\n' "$key" "$(quote_toml_value "$(mcp_env_value "$key")")"
    done
    printf '%s\n' "$CODEX_MANAGED_END"
  } >> "$tmp"

  mv "$tmp" "$config_path"
  log "Updated Codex MCP config at $config_path"
}

register_codex_mcp() {
  local codex_bin key
  codex_bin="$(command -v codex || true)"

  if [ -n "$codex_bin" ]; then
    log "Registering Codex MCP server '$MCP_NAME' with Codex CLI"
    "$codex_bin" mcp remove "$MCP_NAME" >/dev/null 2>&1 || true

    local args=(mcp add)
    for key in "${MCP_ENV_KEYS[@]}"; do
      args+=(--env "$key=$(mcp_env_value "$key")")
    done
    args+=("$MCP_NAME" -- "$(mcp_python_bin)" -X utf8 -m paper_fetch.mcp.server)

    if "$codex_bin" "${args[@]}"; then
      return
    fi
    warn "Codex CLI MCP registration failed; falling back to $HOME/.codex/config.toml"
  fi

  write_codex_config_toml
}

register_claude_mcp() {
  local claude_bin key
  claude_bin="$(command -v claude || true)"

  if [ -z "$claude_bin" ]; then
    log "Claude CLI not found; installed the skill and skipped Claude MCP registration"
    return
  fi

  log "Registering Claude MCP server '$MCP_NAME' with Claude CLI"
  "$claude_bin" mcp remove -s user "$MCP_NAME" >/dev/null 2>&1 || true

  local args=(mcp add -s user)
  for key in "${MCP_ENV_KEYS[@]}"; do
    args+=(-e "$key=$(mcp_env_value "$key")")
  done
  args+=("$MCP_NAME" -- "$(mcp_python_bin)" -X utf8 -m paper_fetch.mcp.server)

  if ! "$claude_bin" "${args[@]}"; then
    warn "Claude MCP registration failed and was skipped."
  fi
}

remove_managed_block_from_file() {
  local target="$1"
  local remove_if_empty="${2:-0}"
  local tmp mode

  [ -f "$target" ] || return 0
  tmp="$(mktemp)"
  mode="$(stat -c '%a' "$target" 2>/dev/null || true)"
  awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
  ' "$target" > "$tmp"

  if [ "$remove_if_empty" = "1" ] && ! grep -q '[^[:space:]]' "$tmp"; then
    rm -f "$tmp" "$target"
    log "Removed empty managed file $target"
    return 0
  fi

  mv "$tmp" "$target"
  if [ -n "$mode" ]; then
    chmod "$mode" "$target"
  fi
  log "Removed managed shell block from $target"
}

remove_shell_startup_blocks() {
  [ -n "${HOME:-}" ] || die "HOME is required for --uninstall."

  remove_managed_block_from_file "$HOME/.bashrc"
  remove_managed_block_from_file "$HOME/.zshrc"
  remove_managed_block_from_file "$HOME/.profile"
  remove_managed_block_from_file "$HOME/.config/fish/conf.d/paper-fetch-offline.fish" 1
}

remove_installed_skills() {
  [ -n "${HOME:-}" ] || die "HOME is required for --uninstall."

  local codex_skill="$HOME/.codex/skills/$SKILL_NAME"
  local claude_skill="$HOME/.claude/skills/$SKILL_NAME"

  rm -rf "$codex_skill" "$claude_skill"
  log "Removed Codex skill at $codex_skill"
  log "Removed Claude Code skill at $claude_skill"
}

remove_codex_config_toml() {
  [ -n "${HOME:-}" ] || die "HOME is required for --uninstall."

  local config_path="$HOME/.codex/config.toml"
  local tmp mode
  [ -f "$config_path" ] || return 0

  tmp="$(mktemp)"
  mode="$(stat -c '%a' "$config_path" 2>/dev/null || true)"
  awk -v begin="$CODEX_MANAGED_BEGIN" -v end="$CODEX_MANAGED_END" -v old_begin="$MANAGED_BEGIN" -v old_end="$MANAGED_END" '
    $0 == begin || $0 == old_begin { skip_block = 1; next }
    $0 == end || $0 == old_end { skip_block = 0; next }
    skip_block { next }
    $0 ~ /^[[:space:]]*\[mcp_servers\.paper-fetch(\..*)?\][[:space:]]*$/ { skip_table = 1; next }
    skip_table && $0 ~ /^[[:space:]]*\[/ { skip_table = 0 }
    !skip_table { print }
  ' "$config_path" > "$tmp"

  mv "$tmp" "$config_path"
  if [ -n "$mode" ]; then
    chmod "$mode" "$config_path"
  fi
  log "Removed Codex MCP config from $config_path"
}

unregister_codex_mcp() {
  local codex_bin
  codex_bin="$(command -v codex || true)"
  if [ -n "$codex_bin" ]; then
    log "Removing Codex MCP server '$MCP_NAME' with Codex CLI"
    "$codex_bin" mcp remove "$MCP_NAME" >/dev/null 2>&1 || true
  fi
  remove_codex_config_toml
}

unregister_claude_mcp() {
  local claude_bin
  claude_bin="$(command -v claude || true)"
  if [ -n "$claude_bin" ]; then
    log "Removing Claude MCP server '$MCP_NAME' with Claude CLI"
    "$claude_bin" mcp remove -s user "$MCP_NAME" >/dev/null 2>&1 || true
  else
    log "Claude CLI not found; skipped Claude MCP removal"
  fi
}

uninstall_user_integrations() {
  remove_installed_skills
  remove_shell_startup_blocks
  unregister_codex_mcp
  unregister_claude_mcp

  echo
  echo "Offline user-level integration removed."
  echo "Bundle files were left in place: $BUNDLE_ROOT"
}

write_managed_env_file() {
  local target="$1"
  local preset_file="$BUNDLE_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET"
  local tmp
  tmp="$(mktemp)"

  mkdir -p "$(dirname "$target")"
  if [ -f "$target" ]; then
    awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$target" > "$tmp"
  elif [ -f "$BUNDLE_ROOT/.env.example" ]; then
    cp "$BUNDLE_ROOT/.env.example" "$tmp"
  else
    : > "$tmp"
  fi

  {
    printf '\n%s\n' "$MANAGED_BEGIN"
    printf 'PAPER_FETCH_DOWNLOAD_DIR=%s\n' "$(quote_env_value "$BUNDLE_ROOT/downloads")"
    printf 'PAPER_FETCH_FORMULA_TOOLS_DIR=%s\n' "$(quote_env_value "$BUNDLE_ROOT/formula-tools")"
    printf 'PLAYWRIGHT_BROWSERS_PATH=%s\n' "$(quote_env_value "$BUNDLE_ROOT/ms-playwright")"
    printf 'FLARESOLVERR_URL=%s\n' "$(quote_env_value "http://127.0.0.1:8191/v1")"
    printf 'FLARESOLVERR_ENV_FILE=%s\n' "$(quote_env_value "$preset_file")"
    printf 'FLARESOLVERR_SOURCE_DIR=%s\n' "$(quote_env_value "$BUNDLE_ROOT/vendor/flaresolverr")"
    printf '%s\n' "$MANAGED_END"
  } >> "$tmp"

  mv "$tmp" "$target"
}

write_activate_script() {
  local target="$BUNDLE_ROOT/activate-offline.sh"
  local offline_env_literal

  if [ "$REUSE_ENV_FILE" = "1" ]; then
    offline_env_literal="$(quote_env_value "$OFFLINE_ENV_FILE")"
    cat > "$target" <<EOF
#!/usr/bin/env bash

INSTALL_ROOT="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
export PAPER_FETCH_ENV_FILE=$offline_env_literal

if [ -f "\$PAPER_FETCH_ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "\$PAPER_FETCH_ENV_FILE"
  set +a
fi

export PATH="\$INSTALL_ROOT/.venv/bin:\$INSTALL_ROOT/formula-tools/bin:\$PATH"
export PAPER_FETCH_ENV_FILE=$offline_env_literal
export PAPER_FETCH_DOWNLOAD_DIR="\$INSTALL_ROOT/downloads"
export PAPER_FETCH_FORMULA_TOOLS_DIR="\$INSTALL_ROOT/formula-tools"
export PLAYWRIGHT_BROWSERS_PATH="\$INSTALL_ROOT/ms-playwright"
export FLARESOLVERR_SOURCE_DIR="\$INSTALL_ROOT/vendor/flaresolverr"
export FLARESOLVERR_ENV_FILE="\$INSTALL_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET"
export FLARESOLVERR_URL="http://127.0.0.1:8191/v1"
export PYTHONUTF8="\${PYTHONUTF8:-1}"
export PYTHONIOENCODING="\${PYTHONIOENCODING:-utf-8}"
EOF
  else
    cat > "$target" <<'EOF'
#!/usr/bin/env bash

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PAPER_FETCH_ENV_FILE="${PAPER_FETCH_ENV_FILE:-$INSTALL_ROOT/offline.env}"

if [ -f "$PAPER_FETCH_ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PAPER_FETCH_ENV_FILE"
  set +a
fi

export PATH="$INSTALL_ROOT/.venv/bin:$INSTALL_ROOT/formula-tools/bin:$PATH"
export PAPER_FETCH_DOWNLOAD_DIR="${PAPER_FETCH_DOWNLOAD_DIR:-$INSTALL_ROOT/downloads}"
export PAPER_FETCH_FORMULA_TOOLS_DIR="${PAPER_FETCH_FORMULA_TOOLS_DIR:-$INSTALL_ROOT/formula-tools}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$INSTALL_ROOT/ms-playwright}"
export FLARESOLVERR_SOURCE_DIR="${FLARESOLVERR_SOURCE_DIR:-$INSTALL_ROOT/vendor/flaresolverr}"
export FLARESOLVERR_ENV_FILE="${FLARESOLVERR_ENV_FILE:-$INSTALL_ROOT/vendor/flaresolverr/.env.flaresolverr-source-__PRESET__}"
export FLARESOLVERR_URL="${FLARESOLVERR_URL:-http://127.0.0.1:8191/v1}"
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
EOF
    sed -i "s|__PRESET__|$PRESET|g" "$target"
  fi
  chmod +x "$target"
}

check_playwright_browser() {
  local venv_python="$BUNDLE_ROOT/.venv/bin/python"
  local executable
  executable="$("$venv_python" -c 'from pathlib import Path; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); path=p.chromium.executable_path; p.stop(); print(path)')"
  [ -x "$executable" ] || die "Bundled Playwright Chromium executable is missing or not executable: $executable"
  case "$executable" in
    "$BUNDLE_ROOT"/ms-playwright/*) ;;
    *) die "Playwright resolved Chromium outside the offline bundle: $executable" ;;
  esac
}

run_smoke_checks() {
  [ "$RUN_SMOKE" = "1" ] || return 0

  log "Running local smoke checks"
  "$BUNDLE_ROOT/.venv/bin/paper-fetch" --help >/dev/null
  "$BUNDLE_ROOT/formula-tools/bin/texmath" --help >/dev/null
  check_playwright_browser
  PYTHONUTF8=1 \
  PYTHONIOENCODING=utf-8 \
  PAPER_FETCH_ENV_FILE="$OFFLINE_ENV_FILE" \
  PAPER_FETCH_MCP_PYTHON_BIN="$BUNDLE_ROOT/.venv/bin/python" \
  PAPER_FETCH_DOWNLOAD_DIR="$BUNDLE_ROOT/downloads" \
  PAPER_FETCH_FORMULA_TOOLS_DIR="$BUNDLE_ROOT/formula-tools" \
  PLAYWRIGHT_BROWSERS_PATH="$BUNDLE_ROOT/ms-playwright" \
  FLARESOLVERR_URL="http://127.0.0.1:8191/v1" \
  FLARESOLVERR_ENV_FILE="$BUNDLE_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET" \
  FLARESOLVERR_SOURCE_DIR="$BUNDLE_ROOT/vendor/flaresolverr" \
    "$BUNDLE_ROOT/.venv/bin/python" -c 'from paper_fetch.mcp.tools import provider_status_payload; payload = provider_status_payload(); assert "providers" in payload'
}

main() {
  local project_wheel

  if [ "$UNINSTALL" = "1" ]; then
    uninstall_user_integrations
    return 0
  fi

  check_platform
  check_python
  verify_checksums
  check_preset_requirements
  check_bundle_assets
  project_wheel="$(find_project_wheel)"

  install_project_venv "$project_wheel"
  install_flaresolverr_venv

  if [ "$REUSE_ENV_FILE" = "1" ]; then
    log "Reusing offline.env without modifying it: $OFFLINE_ENV_FILE"
  else
    log "Writing repo-local offline.env"
    write_managed_env_file "$OFFLINE_ENV_FILE"
  fi
  write_activate_script

  if [ "$MERGE_USER_CONFIG" = "1" ]; then
    [ -n "${HOME:-}" ] || die "HOME is required for --user-config."
    log "Merging offline runtime block into $HOME/.config/paper-fetch/.env"
    write_managed_env_file "$HOME/.config/paper-fetch/.env"
  fi

  install_skills
  write_shell_startup_file
  register_codex_mcp
  register_claude_mcp

  run_smoke_checks

  echo
  echo "Offline installation complete."
  echo "Shell startup file updated: $SHELL_STARTUP_TARGET"
  echo "Open a new shell, or activate the current one with: source $BUNDLE_ROOT/activate-offline.sh"
  echo "FlareSolverr preset: $BUNDLE_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET"
  echo "Restart Codex and Claude Code so they rescan skills and MCP registration."
  echo "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=\"...\" to $OFFLINE_ENV_FILE before fetching Elsevier papers."
}

main "$@"
