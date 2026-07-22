#!/usr/bin/env bash
# Offline installer for CPython ABI-specific Linux/macOS runtime payloads.

set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PAPER_FETCH_OFFLINE_PYTHON_BIN:-python3}"
PRESET="headless"
MERGE_USER_CONFIG=0
RUN_SMOKE=1
UNINSTALL=0
PURGE=0
INSTALL_ROOT=""
OFFLINE_ENV_FILE=""
REUSE_ENV_FILE=0
INSTALLER_MANIFEST_FILE=""

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
  PAPER_FETCH_DOWNLOAD_DIR
  PAPER_FETCH_FORMULA_TOOLS_DIR
  PAPER_FETCH_IMAGE_TOOLS_DIR
  MATHML_TO_LATEX_NODE_BIN
  PAPER_FETCH_BROWSER_HEADLESS
)
OFFLINE_ENV_KEYS=(
  PAPER_FETCH_DOWNLOAD_DIR
  PAPER_FETCH_FORMULA_TOOLS_DIR
  PAPER_FETCH_IMAGE_TOOLS_DIR
  MATHML_TO_LATEX_NODE_BIN
  PAPER_FETCH_BROWSER_HEADLESS
  PYTHONUTF8
  PYTHONIOENCODING
)
SHELL_ENV_KEYS=(
  PAPER_FETCH_ENV_FILE
  PAPER_FETCH_DOWNLOAD_DIR
  PAPER_FETCH_FORMULA_TOOLS_DIR
  PAPER_FETCH_IMAGE_TOOLS_DIR
  MATHML_TO_LATEX_NODE_BIN
  PAPER_FETCH_BROWSER_HEADLESS
  PYTHONUTF8
  PYTHONIOENCODING
)
ACTIVATE_ENV_KEYS=(
  PAPER_FETCH_ENV_FILE
  PAPER_FETCH_DOWNLOAD_DIR
  PAPER_FETCH_FORMULA_TOOLS_DIR
  PAPER_FETCH_IMAGE_TOOLS_DIR
  MATHML_TO_LATEX_NODE_BIN
  PAPER_FETCH_BROWSER_HEADLESS
  PYTHONUTF8
  PYTHONIOENCODING
)

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

load_installer_manifest() {
  INSTALLER_MANIFEST_FILE="$BUNDLE_ROOT/installer/manifest.json"
  if [ ! -f "$INSTALLER_MANIFEST_FILE" ] && [ -n "$INSTALL_ROOT" ]; then
    INSTALLER_MANIFEST_FILE="$INSTALL_ROOT/installer/manifest.json"
  fi
  if [ ! -f "$INSTALLER_MANIFEST_FILE" ]; then
    if [ "$UNINSTALL" = "1" ] || [ "$PURGE" = "1" ]; then
      return 0
    fi
    die "Missing installer manifest: $INSTALLER_MANIFEST_FILE"
  fi
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if [ "$UNINSTALL" = "1" ] || [ "$PURGE" = "1" ]; then
      return 0
    fi
    die "$PYTHON_BIN was not found on PATH; cannot read installer manifest."
  fi

  local values=()
  local value
  while IFS= read -r value; do
    values+=("$value")
  done < <("$PYTHON_BIN" -c '
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
print("installer_manifest_values")
print(manifest["managed_blocks"]["offline"]["begin"])
print(manifest["managed_blocks"]["offline"]["end"])
print(manifest["managed_blocks"]["codex"]["begin"])
print(manifest["managed_blocks"]["codex"]["end"])
print(manifest["skill"]["name"])
print(manifest["mcp"]["name"])
print("[mcp.env_keys]")
for key in manifest["mcp"]["env_keys"]:
    print(key)
env_sets = manifest.get("env_sets", {})
for section in ("offline_env_keys", "shell_env_keys", "activate_env_keys"):
    print(f"[env_sets.{section}]")
    for key in env_sets.get(section, []):
        print(key)
' "$INSTALLER_MANIFEST_FILE")

  [ "${values[0]:-}" = "installer_manifest_values" ] || die "Invalid installer manifest payload from $INSTALLER_MANIFEST_FILE"
  MANAGED_BEGIN="${values[1]:-}"
  MANAGED_END="${values[2]:-}"
  CODEX_MANAGED_BEGIN="${values[3]:-}"
  CODEX_MANAGED_END="${values[4]:-}"
  SKILL_NAME="${values[5]:-}"
  MCP_NAME="${values[6]:-}"
  local section=""
  local loaded_mcp_env_keys=()
  local loaded_offline_env_keys=()
  local loaded_shell_env_keys=()
  local loaded_activate_env_keys=()
  for value in "${values[@]:7}"; do
    case "$value" in
      "[mcp.env_keys]"|"[env_sets.offline_env_keys]"|"[env_sets.shell_env_keys]"|"[env_sets.activate_env_keys]")
        section="$value"
        continue
        ;;
    esac
    case "$section" in
      "[mcp.env_keys]") loaded_mcp_env_keys+=("$value") ;;
      "[env_sets.offline_env_keys]") loaded_offline_env_keys+=("$value") ;;
      "[env_sets.shell_env_keys]") loaded_shell_env_keys+=("$value") ;;
      "[env_sets.activate_env_keys]") loaded_activate_env_keys+=("$value") ;;
    esac
  done
  if [ "${#loaded_mcp_env_keys[@]}" -gt 0 ]; then
    MCP_ENV_KEYS=("${loaded_mcp_env_keys[@]}")
  fi
  if [ "${#loaded_offline_env_keys[@]}" -gt 0 ]; then
    OFFLINE_ENV_KEYS=("${loaded_offline_env_keys[@]}")
  fi
  if [ "${#loaded_shell_env_keys[@]}" -gt 0 ]; then
    SHELL_ENV_KEYS=("${loaded_shell_env_keys[@]}")
  fi
  if [ "${#loaded_activate_env_keys[@]}" -gt 0 ]; then
    ACTIVATE_ENV_KEYS=("${loaded_activate_env_keys[@]}")
  fi
  normalize_mcp_env_keys

  [ -n "$MANAGED_BEGIN" ] || die "installer manifest is missing managed_blocks.offline.begin"
  [ -n "$MANAGED_END" ] || die "installer manifest is missing managed_blocks.offline.end"
  [ -n "$CODEX_MANAGED_BEGIN" ] || die "installer manifest is missing managed_blocks.codex.begin"
  [ -n "$CODEX_MANAGED_END" ] || die "installer manifest is missing managed_blocks.codex.end"
  [ -n "$SKILL_NAME" ] || die "installer manifest is missing skill.name"
  [ -n "$MCP_NAME" ] || die "installer manifest is missing mcp.name"
  [ "${#MCP_ENV_KEYS[@]}" -gt 0 ] || die "installer manifest is missing mcp.env_keys"
  [ "${#OFFLINE_ENV_KEYS[@]}" -gt 0 ] || die "installer manifest is missing env_sets.offline_env_keys"
  [ "${#SHELL_ENV_KEYS[@]}" -gt 0 ] || die "installer manifest is missing env_sets.shell_env_keys"
  [ "${#ACTIVATE_ENV_KEYS[@]}" -gt 0 ] || die "installer manifest is missing env_sets.activate_env_keys"
}

usage() {
  cat <<'EOF'
Usage:
  ./install-offline.sh [--install-dir <path>] [--preset=headless|headful] [--user-config] [--reuse-env-file <path>]
  ./install-offline.sh [--install-dir <path>] --uninstall
  ./install-offline.sh [--install-dir <path>] --purge

Options:
  --install-dir <path>    Install runtime files here. Default: ~/.local/share/paper-fetch-skill.
  --preset=headless|headful
                            Select managed browser headless/headful runtime env. Default: headless.
  --user-config           Also merge the offline runtime block into ~/.config/paper-fetch/.env.
  --no-user-config        Do not touch ~/.config/paper-fetch/.env. This is the default.
  --reuse-env-file <path> Use an existing offline.env without modifying it.
  --skip-smoke            Skip local command smoke checks after installation.
  --uninstall             Remove user-level shell, skill, and MCP integration without deleting the install directory.
  --purge                 Remove user-level integration and delete the install directory.
  -h, --help              Show this help.

Environment:
  PAPER_FETCH_BROWSER_HEADLESS Set to false for a headful managed browser runtime.
  CLOAKBROWSER_CDP_ENDPOINT Optional endpoint for an already-running Chrome/CloakBrowser.
                            Used only with explicit PAPER_FETCH_BROWSER_BACKEND=cloakbrowser.
EOF
}

normalize_mcp_env_keys() {
  local key seen_headless=0
  local filtered=()
  for key in "${MCP_ENV_KEYS[@]}"; do
    case "$key" in
      PLAYWRIGHT_BROWSERS_PATH|CLOAKBROWSER_BINARY_PATH|CLOAKBROWSER_PROFILE_DIR|CLOAKBROWSER_USER_DATA_DIR)
        continue
        ;;
      PAPER_FETCH_BROWSER_HEADLESS)
        seen_headless=1
        ;;
    esac
    filtered+=("$key")
  done
  if [ "$seen_headless" != "1" ]; then
    filtered+=(PAPER_FETCH_BROWSER_HEADLESS)
  fi
  MCP_ENV_KEYS=("${filtered[@]}")
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
    --install-dir=*)
      INSTALL_ROOT="$(normalize_path "${1#*=}")"
      ;;
    --install-dir)
      shift
      [ "$#" -gt 0 ] || die "--install-dir requires a path"
      INSTALL_ROOT="$(normalize_path "$1")"
      ;;
    --preset=*)
      PRESET="${1#*=}"
      ;;
    --preset)
      shift
      [ "$#" -gt 0 ] || die "--preset requires headless or headful"
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
    --purge)
      UNINSTALL=1
      PURGE=1
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

if [ -z "$INSTALL_ROOT" ]; then
  [ -n "${HOME:-}" ] || die "HOME is required for the default install directory."
  INSTALL_ROOT="$HOME/.local/share/paper-fetch-skill"
fi

if [ "$REUSE_ENV_FILE" != "1" ]; then
  OFFLINE_ENV_FILE="$INSTALL_ROOT/offline.env"
fi

if [ "$UNINSTALL" != "1" ]; then
  case "$PRESET" in
    headless|headful) ;;
    *) die "--preset must be headless or headful" ;;
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

mcp_name_regex() {
  printf '%s' "$MCP_NAME" | sed 's/[][\\.^$*+?{}|()]/\\&/g'
}

offline_manifest_value() {
  "$PYTHON_BIN" -c '
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
value = data
for part in sys.argv[2].split("."):
    value = value.get(part, "") if isinstance(value, dict) else ""
print(value)
' "$BUNDLE_ROOT/offline-manifest.json" "$1"
}

host_platform() {
  case "$(uname -s)" in
    Linux) printf 'linux\n' ;;
    Darwin) printf 'macos\n' ;;
    *) return 1 ;;
  esac
}

host_arch() {
  case "$(uname -m)" in
    x86_64|amd64) printf 'x86_64\n' ;;
    arm64|aarch64) printf 'arm64\n' ;;
    *) return 1 ;;
  esac
}

file_mode() {
  stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true
}

check_platform() {
  require_file "$BUNDLE_ROOT/offline-manifest.json"

  local platform arch manifest_platform manifest_arch
  platform="$(host_platform)" || die "This offline bundle supports Linux and macOS only; detected $(uname -s)."
  arch="$(host_arch)" || die "This offline bundle supports x86_64 and arm64 only; detected $(uname -m)."
  manifest_platform="$(offline_manifest_value target.platform)"
  manifest_arch="$(offline_manifest_value target.arch)"
  [ -n "$manifest_platform" ] || die "offline-manifest.json is missing target.platform."
  [ -n "$manifest_arch" ] || die "offline-manifest.json is missing target.arch."

  case "$platform:$arch" in
    linux:x86_64|macos:x86_64|macos:arm64) ;;
    linux:arm64) die "Linux offline bundles currently support x86_64 only; detected arm64." ;;
    *) die "Unsupported offline target host: $platform/$arch." ;;
  esac

  [ "$platform" = "$manifest_platform" ] || die "bundle targets $manifest_platform; detected $platform."
  [ "$arch" = "$manifest_arch" ] || die "bundle targets $manifest_arch; detected $arch."
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

write_runtime_python_file() {
  local resolved_python
  resolved_python="$(command -v "$PYTHON_BIN")"
  mkdir -p "$INSTALL_ROOT/runtime"
  printf '%s\n' "$resolved_python" > "$INSTALL_ROOT/runtime/python-bin"
}

verify_checksums() {
  require_file "$BUNDLE_ROOT/sha256sums.txt"
  log "Verifying bundled file checksums"
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$BUNDLE_ROOT" && sha256sum --check sha256sums.txt --quiet)
  elif command -v shasum >/dev/null 2>&1; then
    (cd "$BUNDLE_ROOT" && shasum -a 256 --check sha256sums.txt >/dev/null)
  else
    die "sha256sum or shasum is required to verify the offline bundle."
  fi
}

verify_skill_bundle_integrity() {
  local runtime_root="$1"
  local skill_dir="$2"
  local phase="$3"
  local verifier="$runtime_root/runtime/site-packages/paper_fetch/skill_integrity.py"

  require_file "$runtime_root/offline-manifest.json"
  require_file "$verifier"
  log "Verifying $phase skill bundle manifest"
  "$runtime_root/runtime/paper-fetch-python" -X utf8 \
    -m paper_fetch.skill_integrity verify \
    --manifest "$runtime_root/offline-manifest.json" \
    --skill-dir "$skill_dir" >/dev/null
}

check_preset_requirements() {
  host_platform >/dev/null || die "This offline bundle supports Linux and macOS only; detected $(uname -s)."
}

check_bundle_assets() {
  require_dir "$BUNDLE_ROOT/runtime/site-packages"
  require_file "$BUNDLE_ROOT/runtime/site-packages/paper_fetch/__init__.py"
  require_file "$BUNDLE_ROOT/runtime/paper-fetch-python"
  require_file "$BUNDLE_ROOT/bin/paper-fetch"
  require_file "$BUNDLE_ROOT/bin/paper-fetch-mcp"
  require_file "$BUNDLE_ROOT/bin/paper-fetch-install-formula-tools"
  require_file "$BUNDLE_ROOT/bin/paper-fetch-install-image-tools"
  [ -x "$BUNDLE_ROOT/runtime/paper-fetch-python" ] || die "Bundled private Python launcher is not executable: $BUNDLE_ROOT/runtime/paper-fetch-python"
  [ -x "$BUNDLE_ROOT/bin/paper-fetch" ] || die "Bundled CLI wrapper is not executable: $BUNDLE_ROOT/bin/paper-fetch"
  [ -x "$BUNDLE_ROOT/bin/paper-fetch-mcp" ] || die "Bundled MCP wrapper is not executable: $BUNDLE_ROOT/bin/paper-fetch-mcp"
  [ -x "$BUNDLE_ROOT/bin/paper-fetch-install-formula-tools" ] || die "Bundled formula installer wrapper is not executable: $BUNDLE_ROOT/bin/paper-fetch-install-formula-tools"
  [ -x "$BUNDLE_ROOT/bin/paper-fetch-install-image-tools" ] || die "Bundled image installer wrapper is not executable: $BUNDLE_ROOT/bin/paper-fetch-install-image-tools"
  require_file "$BUNDLE_ROOT/formula-tools/bin/texmath"
  [ -x "$BUNDLE_ROOT/formula-tools/bin/texmath" ] || die "Bundled texmath is not executable: $BUNDLE_ROOT/formula-tools/bin/texmath"

  require_file "$BUNDLE_ROOT/skills/$SKILL_NAME/SKILL.md"
}

mcp_python_bin() {
  printf '%s\n' "$INSTALL_ROOT/runtime/paper-fetch-python"
}

mathml_node_bin() {
  local bundled_node="$INSTALL_ROOT/runtime/site-packages/playwright/driver/node"
  if [ -x "$bundled_node" ]; then
    printf '%s\n' "$bundled_node"
  else
    command -v node || printf 'node\n'
  fi
}

browser_headless_value() {
  if [ "$PRESET" = "headful" ]; then
    printf 'false\n'
  else
    printf 'true\n'
  fi
}

installer_env_value() {
  local key="$1"
  case "$key" in
    PYTHONUTF8) printf '1\n' ;;
    PYTHONIOENCODING) printf 'utf-8\n' ;;
    PAPER_FETCH_ENV_FILE) printf '%s\n' "$OFFLINE_ENV_FILE" ;;
    PAPER_FETCH_DOWNLOAD_DIR) printf '%s\n' "$INSTALL_ROOT/downloads" ;;
    PAPER_FETCH_FORMULA_TOOLS_DIR) printf '%s\n' "$INSTALL_ROOT/formula-tools" ;;
    PAPER_FETCH_IMAGE_TOOLS_DIR) printf '%s\n' "$INSTALL_ROOT/image-tools" ;;
    MATHML_TO_LATEX_NODE_BIN) mathml_node_bin ;;
    PAPER_FETCH_BROWSER_HEADLESS) browser_headless_value ;;
    *) die "Unknown installer env key: $key" ;;
  esac
}

mcp_env_value() {
  installer_env_value "$1"
}

copy_installed_skill() {
  local destination="$1"
  local source="$INSTALL_ROOT/skills/$SKILL_NAME"

  require_file "$source/SKILL.md"
  rm -rf "$destination"
  mkdir -p "$destination"
  cp -a "$source/." "$destination/"
}

antigravity_home() {
  printf '%s\n' "${ANTIGRAVITY_HOME:-$HOME/.gemini/antigravity-cli}"
}

install_skills() {
  [ -n "${HOME:-}" ] || die "HOME is required to install Codex, Claude, and Antigravity skills."

  local codex_skill="$HOME/.codex/skills/$SKILL_NAME"
  local claude_skill="$HOME/.claude/skills/$SKILL_NAME"
  local antigravity_skill
  antigravity_skill="$(antigravity_home)/skills/$SKILL_NAME"

  log "Installing Codex skill to $codex_skill"
  copy_installed_skill "$codex_skill"
  log "Installing Claude Code skill to $claude_skill"
  copy_installed_skill "$claude_skill"
  log "Installing Antigravity skill to $antigravity_skill"
  copy_installed_skill "$antigravity_skill"
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
  local key
  printf '%s\n' "$MANAGED_BEGIN"
  printf 'export PATH=%s:%s:%s:$PATH\n' "$(quote_env_value "$INSTALL_ROOT/bin")" "$(quote_env_value "$INSTALL_ROOT/formula-tools/bin")" "$(quote_env_value "$INSTALL_ROOT/image-tools/bin")"
  for key in "${SHELL_ENV_KEYS[@]}"; do
    printf 'export %s=%s\n' "$key" "$(quote_env_value "$(installer_env_value "$key")")"
  done
  printf '%s\n' "$MANAGED_END"
}

write_fish_shell_block() {
  local key
  printf '%s\n' "$MANAGED_BEGIN"
  printf 'set -gx PATH %s %s %s $PATH\n' "$(quote_env_value "$INSTALL_ROOT/bin")" "$(quote_env_value "$INSTALL_ROOT/formula-tools/bin")" "$(quote_env_value "$INSTALL_ROOT/image-tools/bin")"
  for key in "${SHELL_ENV_KEYS[@]}"; do
    printf 'set -gx %s %s\n' "$key" "$(quote_env_value "$(installer_env_value "$key")")"
  done
  printf '%s\n' "$MANAGED_END"
}

write_shell_startup_file() {
  local tmp mode

  select_shell_startup_file
  tmp="$(mktemp)"
  mode=""
  mkdir -p "$(dirname "$SHELL_STARTUP_TARGET")"
  if [ -f "$SHELL_STARTUP_TARGET" ]; then
    mode="$(file_mode "$SHELL_STARTUP_TARGET")"
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
  local tmp key mcp_table_re
  tmp="$(mktemp)"
  mcp_table_re="^[[:space:]]*[[]mcp_servers[.]$(mcp_name_regex)([.].*)?[]][[:space:]]*$"
  mkdir -p "$codex_home"

  if [ -f "$config_path" ]; then
    awk -v begin="$CODEX_MANAGED_BEGIN" -v end="$CODEX_MANAGED_END" -v old_begin="$MANAGED_BEGIN" -v old_end="$MANAGED_END" -v mcp_table_re="$mcp_table_re" '
      $0 == begin || $0 == old_begin { skip_block = 1; next }
      $0 == end || $0 == old_end { skip_block = 0; next }
      skip_block { next }
      $0 ~ mcp_table_re { skip_table = 1; next }
      skip_table && $0 ~ /^[[:space:]]*\[/ { skip_table = 0 }
      !skip_table { print }
    ' "$config_path" > "$tmp"
  else
    : > "$tmp"
  fi

  {
    printf '\n%s\n' "$CODEX_MANAGED_BEGIN"
    printf '[mcp_servers.%s]\n' "$MCP_NAME"
    printf 'command = %s\n' "$(quote_toml_value "$(mcp_python_bin)")"
    printf 'args = ["-X", "utf8", "-m", "paper_fetch.mcp.server"]\n'
    printf '\n[mcp_servers.%s.env]\n' "$MCP_NAME"
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
  args+=(-- "$MCP_NAME" "$(mcp_python_bin)" -X utf8 -m paper_fetch.mcp.server)

  if ! "$claude_bin" "${args[@]}"; then
    warn "Claude MCP registration failed and was skipped."
  fi
}

resolve_json_python() {
  if [ -x "$(mcp_python_bin)" ]; then
    mcp_python_bin
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    printf '\n'
  fi
}

register_antigravity_mcp() {
  [ -n "${HOME:-}" ] || die "HOME is required to install the Antigravity MCP config."

  local config_path key
  config_path="$(antigravity_home)/mcp_config.json"
  mkdir -p "$(dirname "$config_path")"

  local env_pairs=()
  for key in "${MCP_ENV_KEYS[@]}"; do
    env_pairs+=("$key=$(mcp_env_value "$key")")
  done

  log "Registering Antigravity MCP server '$MCP_NAME' in $config_path"
  PF_CONFIG_PATH="$config_path" \
  PF_MCP_NAME="$MCP_NAME" \
  PF_PYTHON_BIN="$(mcp_python_bin)" \
  PF_ENV_PAIRS="$(printf '%s\n' "${env_pairs[@]}")" \
  "$(mcp_python_bin)" -X utf8 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["PF_CONFIG_PATH"])
name = os.environ["PF_MCP_NAME"]

data = {}
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Existing {path} is not valid JSON: {exc}")
if not isinstance(data, dict):
    raise SystemExit(f"Existing {path} must contain a JSON object")

servers = data.setdefault("mcpServers", {})
if not isinstance(servers, dict):
    raise SystemExit(f"'mcpServers' in {path} must be a JSON object")

env = {}
for line in os.environ.get("PF_ENV_PAIRS", "").splitlines():
    if not line:
        continue
    key, _, value = line.partition("=")
    env[key] = value

entry = {
    "command": os.environ["PF_PYTHON_BIN"],
    "args": ["-X", "utf8", "-m", "paper_fetch.mcp.server"],
}
if env:
    entry["env"] = env

servers[name] = entry
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
}

remove_managed_block_from_file() {
  local target="$1"
  local remove_if_empty="${2:-0}"
  local tmp mode

  [ -f "$target" ] || return 0
  tmp="$(mktemp)"
  mode="$(file_mode "$target")"
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
  local antigravity_skill
  antigravity_skill="$(antigravity_home)/skills/$SKILL_NAME"

  rm -rf "$codex_skill" "$claude_skill" "$antigravity_skill"
  log "Removed Codex skill at $codex_skill"
  log "Removed Claude Code skill at $claude_skill"
  log "Removed Antigravity skill at $antigravity_skill"
}

remove_codex_config_toml() {
  [ -n "${HOME:-}" ] || die "HOME is required for --uninstall."

  local config_path="$HOME/.codex/config.toml"
  local tmp mode mcp_table_re
  [ -f "$config_path" ] || return 0

  tmp="$(mktemp)"
  mode="$(file_mode "$config_path")"
  mcp_table_re="^[[:space:]]*[[]mcp_servers[.]$(mcp_name_regex)([.].*)?[]][[:space:]]*$"
  awk -v begin="$CODEX_MANAGED_BEGIN" -v end="$CODEX_MANAGED_END" -v old_begin="$MANAGED_BEGIN" -v old_end="$MANAGED_END" -v mcp_table_re="$mcp_table_re" '
    $0 == begin || $0 == old_begin { skip_block = 1; next }
    $0 == end || $0 == old_end { skip_block = 0; next }
    skip_block { next }
    $0 ~ mcp_table_re { skip_table = 1; next }
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

unregister_antigravity_mcp() {
  [ -n "${HOME:-}" ] || die "HOME is required for --uninstall."

  local config_path json_python
  config_path="$(antigravity_home)/mcp_config.json"
  [ -f "$config_path" ] || return 0

  json_python="$(resolve_json_python)"
  if [ -z "$json_python" ]; then
    warn "No python available to edit $config_path; left Antigravity MCP entry in place."
    return 0
  fi

  PF_CONFIG_PATH="$config_path" \
  PF_MCP_NAME="$MCP_NAME" \
  "$json_python" -X utf8 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["PF_CONFIG_PATH"])
name = os.environ["PF_MCP_NAME"]
try:
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
except json.JSONDecodeError:
    raise SystemExit(0)
if not isinstance(data, dict):
    raise SystemExit(0)

servers = data.get("mcpServers")
if isinstance(servers, dict):
    servers.pop(name, None)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
  log "Removed Antigravity MCP server '$MCP_NAME' from $config_path"
}

uninstall_user_integrations() {
  remove_installed_skills
  remove_shell_startup_blocks
  unregister_codex_mcp
  unregister_claude_mcp
  unregister_antigravity_mcp

  echo
  echo "Offline user-level integration removed."
  echo "Install directory was left in place: $INSTALL_ROOT"
}

purge_install_root() {
  [ -n "$INSTALL_ROOT" ] || die "INSTALL_ROOT is required for --purge."
  case "$INSTALL_ROOT" in
    /|"") die "Refusing to purge unsafe install directory: $INSTALL_ROOT" ;;
  esac
  rm -rf "$INSTALL_ROOT"
  echo "Install directory deleted: $INSTALL_ROOT"
}

write_managed_env_file() {
  local target="$1"
  local tmp key
  tmp="$(mktemp)"

  mkdir -p "$(dirname "$target")"
  if [ -f "$target" ]; then
    awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$target" > "$tmp"
  elif [ -f "$INSTALL_ROOT/.env.example" ]; then
    cp "$INSTALL_ROOT/.env.example" "$tmp"
  else
    : > "$tmp"
  fi

  {
    printf '\n%s\n' "$MANAGED_BEGIN"
    for key in "${OFFLINE_ENV_KEYS[@]}"; do
      printf '%s=%s\n' "$key" "$(quote_env_value "$(installer_env_value "$key")")"
    done
    printf '# Optional: connect to an already-running Chrome/CloakBrowser CDP endpoint.\n'
    printf '# CLOAKBROWSER_CDP_ENDPOINT="ws://127.0.0.1:9222/devtools/browser/..."\n'
    printf '# Optional: use a preinstalled Chrome/CloakBrowser binary instead of cloakbrowser download.\n'
    printf '# CLOAKBROWSER_BINARY_PATH="/absolute/path/to/chrome"\n'
    printf '%s\n' "$MANAGED_END"
  } >> "$tmp"

  mv "$tmp" "$target"
}

write_activate_script() {
  local target="$INSTALL_ROOT/activate-offline.sh"
  local default_env_line headless_value reuse_env_value key
  headless_value="$(browser_headless_value)"

  if [ "$REUSE_ENV_FILE" = "1" ]; then
    default_env_line="PAPER_FETCH_DEFAULT_ENV_FILE=$(quote_env_value "$OFFLINE_ENV_FILE")"
    reuse_env_value="1"
  else
    default_env_line='PAPER_FETCH_DEFAULT_ENV_FILE="$INSTALL_ROOT/offline.env"'
    reuse_env_value="0"
  fi

  cat > "$target" <<EOF
#!/usr/bin/env bash

if [ -n "\${BASH_SOURCE:-}" ]; then
  PAPER_FETCH_ACTIVATE_SCRIPT="\${BASH_SOURCE[0]}"
elif [ -n "\${ZSH_VERSION:-}" ]; then
  PAPER_FETCH_ACTIVATE_SCRIPT="\${(%):-%x}"
else
  PAPER_FETCH_ACTIVATE_SCRIPT="\$0"
fi
INSTALL_ROOT="\$(cd "\$(dirname "\$PAPER_FETCH_ACTIVATE_SCRIPT")" && pwd)"
unset PAPER_FETCH_ACTIVATE_SCRIPT
$default_env_line
PAPER_FETCH_REUSE_ENV_FILE="$reuse_env_value"

paper_fetch_load_env_file() {
  local env_file="\$1"
  local key value
  [ -f "\$env_file" ] || return 0
  [ -x "\$INSTALL_ROOT/runtime/paper-fetch-python" ] || return 0

  while IFS= read -r -d '' key && IFS= read -r -d '' value; do
    case "\$key" in
      ""|[!A-Za-z_]*|*[!A-Za-z0-9_]*)
        continue
        ;;
    esac
    export "\$key=\$value"
  done < <(
    PYTHONPATH="\$INSTALL_ROOT/runtime/site-packages\${PYTHONPATH:+:\$PYTHONPATH}" \\
    "\$INSTALL_ROOT/runtime/paper-fetch-python" - "\$env_file" <<'PY'
from __future__ import annotations

import re
import sys

from dotenv import dotenv_values

KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\\Z")

for key, value in dotenv_values(sys.argv[1], interpolate=False).items():
    if value is None or not key or not KEY_RE.fullmatch(str(key)):
        continue
    sys.stdout.buffer.write(str(key).encode("utf-8") + b"\\0")
    sys.stdout.buffer.write(str(value).encode("utf-8") + b"\\0")
PY
  )
}

paper_fetch_export_default() {
  local key="\$1"
  local value="\$2"

  case "\$key" in
    PAPER_FETCH_ENV_FILE)
      export PAPER_FETCH_ENV_FILE="\$value"
      return 0
      ;;
    PAPER_FETCH_DOWNLOAD_DIR|PAPER_FETCH_FORMULA_TOOLS_DIR|PAPER_FETCH_IMAGE_TOOLS_DIR|MATHML_TO_LATEX_NODE_BIN)
      if [ "\$PAPER_FETCH_REUSE_ENV_FILE" = "1" ]; then
        export "\$key=\$value"
        return 0
      fi
      ;;
  esac

  case "\$key" in
    PAPER_FETCH_DOWNLOAD_DIR)
      [ -n "\${PAPER_FETCH_DOWNLOAD_DIR:-}" ] || export PAPER_FETCH_DOWNLOAD_DIR="\$value"
      ;;
    PAPER_FETCH_FORMULA_TOOLS_DIR)
      [ -n "\${PAPER_FETCH_FORMULA_TOOLS_DIR:-}" ] || export PAPER_FETCH_FORMULA_TOOLS_DIR="\$value"
      ;;
    PAPER_FETCH_IMAGE_TOOLS_DIR)
      [ -n "\${PAPER_FETCH_IMAGE_TOOLS_DIR:-}" ] || export PAPER_FETCH_IMAGE_TOOLS_DIR="\$value"
      ;;
    MATHML_TO_LATEX_NODE_BIN)
      [ -n "\${MATHML_TO_LATEX_NODE_BIN:-}" ] || export MATHML_TO_LATEX_NODE_BIN="\$value"
      ;;
    PAPER_FETCH_BROWSER_HEADLESS)
      [ -n "\${PAPER_FETCH_BROWSER_HEADLESS:-}" ] || export PAPER_FETCH_BROWSER_HEADLESS="\$value"
      ;;
    PYTHONUTF8)
      [ -n "\${PYTHONUTF8:-}" ] || export PYTHONUTF8="\$value"
      ;;
    PYTHONIOENCODING)
      [ -n "\${PYTHONIOENCODING:-}" ] || export PYTHONIOENCODING="\$value"
      ;;
  esac
}

paper_fetch_default_value() {
  local key="\$1"
  case "\$key" in
    PAPER_FETCH_ENV_FILE) printf '%s\\n' "\$PAPER_FETCH_DEFAULT_ENV_FILE" ;;
    PAPER_FETCH_DOWNLOAD_DIR) printf '%s\\n' "\$INSTALL_ROOT/downloads" ;;
    PAPER_FETCH_FORMULA_TOOLS_DIR) printf '%s\\n' "\$INSTALL_ROOT/formula-tools" ;;
    PAPER_FETCH_IMAGE_TOOLS_DIR) printf '%s\\n' "\$INSTALL_ROOT/image-tools" ;;
    MATHML_TO_LATEX_NODE_BIN)
      if [ -x "\$INSTALL_ROOT/runtime/site-packages/playwright/driver/node" ]; then
        printf '%s\\n' "\$INSTALL_ROOT/runtime/site-packages/playwright/driver/node"
      else
        command -v node 2>/dev/null || printf 'node\\n'
      fi
      ;;
    PAPER_FETCH_BROWSER_HEADLESS) printf '%s\\n' "$headless_value" ;;
    PYTHONUTF8) printf '1\\n' ;;
    PYTHONIOENCODING) printf 'utf-8\\n' ;;
  esac
}

export PATH="\$INSTALL_ROOT/bin:\$INSTALL_ROOT/formula-tools/bin:\$INSTALL_ROOT/image-tools/bin:\$PATH"
export PYTHONPATH="\$INSTALL_ROOT/runtime/site-packages\${PYTHONPATH:+:\$PYTHONPATH}"
export PAPER_FETCH_ENV_FILE="\$PAPER_FETCH_DEFAULT_ENV_FILE"
paper_fetch_load_env_file "\$PAPER_FETCH_ENV_FILE"
export PAPER_FETCH_ENV_FILE="\$PAPER_FETCH_DEFAULT_ENV_FILE"
EOF
  printf 'for PAPER_FETCH_ACTIVATE_ENV_KEY in' >> "$target"
  for key in "${ACTIVATE_ENV_KEYS[@]}"; do
    printf ' \\\n  %s' "$key" >> "$target"
  done
  cat >> "$target" <<'EOF'
; do
  paper_fetch_export_default "$PAPER_FETCH_ACTIVATE_ENV_KEY" "$(paper_fetch_default_value "$PAPER_FETCH_ACTIVATE_ENV_KEY")"
done
unset PAPER_FETCH_ACTIVATE_ENV_KEY PAPER_FETCH_DEFAULT_ENV_FILE PAPER_FETCH_REUSE_ENV_FILE
unset -f paper_fetch_load_env_file paper_fetch_export_default paper_fetch_default_value 2>/dev/null || true
EOF
  chmod +x "$target"
}

check_browser_runtime_package() {
  local runtime_python
  runtime_python="$(mcp_python_bin)"
  "$runtime_python" -c 'import cloakbrowser; import playwright; from paper_fetch.runtime_browser import BrowserContextManager; assert hasattr(cloakbrowser, "ensure_binary"); assert BrowserContextManager is not None'
}

run_smoke_checks() {
  [ "$RUN_SMOKE" = "1" ] || return 0

  local key env_args=()

  log "Running local smoke checks"
  "$INSTALL_ROOT/bin/paper-fetch" --help >/dev/null
  "$INSTALL_ROOT/formula-tools/bin/texmath" --help >/dev/null
  if [ -x "$INSTALL_ROOT/image-tools/bin/gs" ]; then
    "$INSTALL_ROOT/image-tools/bin/gs" --version >/dev/null
  fi
  if [ -x "$INSTALL_ROOT/image-tools/bin/vips" ]; then
    "$INSTALL_ROOT/image-tools/bin/vips" --version >/dev/null
  fi
  check_browser_runtime_package
  for key in "${MCP_ENV_KEYS[@]}"; do
    env_args+=("$key=$(mcp_env_value "$key")")
  done
  env "${env_args[@]}" "$(mcp_python_bin)" -c 'from paper_fetch.mcp.fetch_tool import provider_status_payload; payload = provider_status_payload(); assert "providers" in payload'
}

same_directory() {
  local left="$1"
  local right="$2"
  [ -d "$left" ] || return 1
  [ -d "$right" ] || return 1
  [ "$(cd "$left" && pwd -P)" = "$(cd "$right" && pwd -P)" ]
}

clean_install_root_payload() {
  mkdir -p "$INSTALL_ROOT"
  rm -rf \
    "$INSTALL_ROOT/bin" \
    "$INSTALL_ROOT/runtime" \
    "$INSTALL_ROOT/formula-tools" \
    "$INSTALL_ROOT/image-tools" \
    "$INSTALL_ROOT/skills" \
    "$INSTALL_ROOT/installer" \
    "$INSTALL_ROOT/install-offline.sh" \
    "$INSTALL_ROOT/activate-offline.sh" \
    "$INSTALL_ROOT/README.offline.md" \
    "$INSTALL_ROOT/offline-manifest.json" \
    "$INSTALL_ROOT/sha256sums.txt" \
    "$INSTALL_ROOT/LICENSE" \
    "$INSTALL_ROOT/.env.example" \
    "$INSTALL_ROOT/src" \
    "$INSTALL_ROOT/tests" \
    "$INSTALL_ROOT/.github" \
    "$INSTALL_ROOT/wheelhouse" \
    "$INSTALL_ROOT/dist" \
    "$INSTALL_ROOT/pyproject.toml"
}

install_runtime_payload() {
  local env_backup=""

  mkdir -p "$INSTALL_ROOT"
  if same_directory "$BUNDLE_ROOT" "$INSTALL_ROOT"; then
    log "Using existing offline runtime directory: $INSTALL_ROOT"
    return 0
  fi

  if [ "$REUSE_ENV_FILE" != "1" ] && [ -f "$INSTALL_ROOT/offline.env" ]; then
    env_backup="$(mktemp)"
    cp "$INSTALL_ROOT/offline.env" "$env_backup"
  fi

  log "Installing runtime payload to $INSTALL_ROOT"
  clean_install_root_payload
  cp -a "$BUNDLE_ROOT/." "$INSTALL_ROOT/"

  if [ -n "$env_backup" ]; then
    cp "$env_backup" "$INSTALL_ROOT/offline.env"
    rm -f "$env_backup"
  fi
}

main() {
  load_installer_manifest

  if [ "$UNINSTALL" = "1" ]; then
    uninstall_user_integrations
    if [ "$PURGE" = "1" ]; then
      purge_install_root
    fi
    return 0
  fi

  check_platform
  check_python
  verify_checksums
  verify_skill_bundle_integrity \
    "$BUNDLE_ROOT" \
    "$BUNDLE_ROOT/skills/$SKILL_NAME" \
    "bundled pre-install"
  check_preset_requirements
  check_bundle_assets
  install_runtime_payload
  write_runtime_python_file
  verify_skill_bundle_integrity \
    "$INSTALL_ROOT" \
    "$INSTALL_ROOT/skills/$SKILL_NAME" \
    "installed runtime"

  if [ "$REUSE_ENV_FILE" = "1" ]; then
    log "Reusing offline.env without modifying it: $OFFLINE_ENV_FILE"
  else
    log "Writing install offline.env"
    write_managed_env_file "$OFFLINE_ENV_FILE"
  fi
  write_activate_script

  if [ "$MERGE_USER_CONFIG" = "1" ]; then
    [ -n "${HOME:-}" ] || die "HOME is required for --user-config."
    log "Merging offline runtime block into $HOME/.config/paper-fetch/.env"
    write_managed_env_file "$HOME/.config/paper-fetch/.env"
  fi

  install_skills
  verify_skill_bundle_integrity \
    "$INSTALL_ROOT" \
    "$HOME/.codex/skills/$SKILL_NAME" \
    "Codex post-install"
  verify_skill_bundle_integrity \
    "$INSTALL_ROOT" \
    "$HOME/.claude/skills/$SKILL_NAME" \
    "Claude post-install"
  verify_skill_bundle_integrity \
    "$INSTALL_ROOT" \
    "$(antigravity_home)/skills/$SKILL_NAME" \
    "Antigravity post-install"
  write_shell_startup_file
  register_codex_mcp
  register_claude_mcp
  register_antigravity_mcp

  run_smoke_checks

  echo
  echo "Offline installation complete."
  echo "Shell startup file updated: $SHELL_STARTUP_TARGET"
  echo "Install directory: $INSTALL_ROOT"
  echo "Open a new shell, or activate the current one with: source $INSTALL_ROOT/activate-offline.sh"
  echo "Default browser backend: Camoufox (headless: $(browser_headless_value))"
  echo "The first real fetch may download the Camoufox runtime; doctor and provider status never download it."
  echo "For a fully offline host, preinstall the complete Camoufox runtime before fetching."
  echo "Set PAPER_FETCH_BROWSER_BACKEND=cloakbrowser only for the deprecated compatibility backend."
  echo "Restart Codex, Claude Code, and the Antigravity CLI so they rescan skills and MCP registration."
  echo "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=\"...\" to $OFFLINE_ENV_FILE before fetching Elsevier papers."
}

main "$@"
