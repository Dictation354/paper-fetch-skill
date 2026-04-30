#!/usr/bin/env bash
# Offline installer for the Linux x86_64 CPython ABI-specific bundle.

set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PAPER_FETCH_OFFLINE_PYTHON_BIN:-python3}"
XVFB_BIN="${PAPER_FETCH_OFFLINE_XVFB_BIN:-Xvfb}"
PRESET="headless"
MERGE_USER_CONFIG=0
RUN_SMOKE=1

MANAGED_BEGIN="# BEGIN paper-fetch offline managed"
MANAGED_END="# END paper-fetch offline managed"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  ./install-offline.sh [--preset=headless|wslg] [--user-config]

Options:
  --preset=headless|wslg  Select the bundled FlareSolverr preset. Default: headless.
  --user-config           Also merge the offline runtime block into ~/.config/paper-fetch/.env.
  --no-user-config        Do not touch ~/.config/paper-fetch/.env. This is the default.
  --skip-smoke            Skip local command smoke checks after installation.
  -h, --help              Show this help.
EOF
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
    --skip-smoke)
      RUN_SMOKE=0
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

case "$PRESET" in
  headless|wslg) ;;
  *) die "--preset must be headless or wslg" ;;
esac

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
export PAPER_FETCH_FORMULA_TOOLS_DIR="${PAPER_FETCH_FORMULA_TOOLS_DIR:-$INSTALL_ROOT/formula-tools}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$INSTALL_ROOT/ms-playwright}"
export FLARESOLVERR_SOURCE_DIR="${FLARESOLVERR_SOURCE_DIR:-$INSTALL_ROOT/vendor/flaresolverr}"
EOF
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
  PAPER_FETCH_ENV_FILE="$BUNDLE_ROOT/offline.env" \
  PLAYWRIGHT_BROWSERS_PATH="$BUNDLE_ROOT/ms-playwright" \
    "$BUNDLE_ROOT/.venv/bin/python" -c 'from paper_fetch.mcp.tools import provider_status_payload; payload = provider_status_payload(); assert "providers" in payload'
}

main() {
  local project_wheel

  check_platform
  check_python
  verify_checksums
  check_preset_requirements
  check_bundle_assets
  project_wheel="$(find_project_wheel)"

  install_project_venv "$project_wheel"
  install_flaresolverr_venv

  log "Writing repo-local offline.env"
  write_managed_env_file "$BUNDLE_ROOT/offline.env"
  write_activate_script

  if [ "$MERGE_USER_CONFIG" = "1" ]; then
    [ -n "${HOME:-}" ] || die "HOME is required for --user-config."
    log "Merging offline runtime block into $HOME/.config/paper-fetch/.env"
    write_managed_env_file "$HOME/.config/paper-fetch/.env"
  fi

  run_smoke_checks

  echo
  echo "Offline installation complete."
  echo "Activate it with: source $BUNDLE_ROOT/activate-offline.sh"
  echo "FlareSolverr preset: $BUNDLE_ROOT/vendor/flaresolverr/.env.flaresolverr-source-$PRESET"
  echo "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=\"...\" to $BUNDLE_ROOT/offline.env before fetching Elsevier papers."
}

main "$@"
