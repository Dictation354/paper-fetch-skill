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
PURGE_INSTALL_ROOT=""
OFFLINE_ENV_FILE=""
REUSE_ENV_FILE=0
INSTALLER_MANIFEST_FILE=""
HOST_PLATFORM=""
HOST_ARCH=""

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
OFFLINE_ENV_KEYS=()
SHELL_ENV_KEYS=()
ACTIVATE_ENV_KEYS=()

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

load_installer_manifest() {
  derive_env_key_sets
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
  done < <("$PYTHON_BIN" -I -c '
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
  for value in "${values[@]:7}"; do
    case "$value" in
      "[mcp.env_keys]")
        section="$value"
        continue
        ;;
    esac
    case "$section" in
      "[mcp.env_keys]") loaded_mcp_env_keys+=("$value") ;;
    esac
  done
  if [ "${#loaded_mcp_env_keys[@]}" -gt 0 ]; then
    MCP_ENV_KEYS=("${loaded_mcp_env_keys[@]}")
  fi
  normalize_mcp_env_keys
  derive_env_key_sets

  [ -n "$MANAGED_BEGIN" ] || die "installer manifest is missing managed_blocks.offline.begin"
  [ -n "$MANAGED_END" ] || die "installer manifest is missing managed_blocks.offline.end"
  [ -n "$CODEX_MANAGED_BEGIN" ] || die "installer manifest is missing managed_blocks.codex.begin"
  [ -n "$CODEX_MANAGED_END" ] || die "installer manifest is missing managed_blocks.codex.end"
  [ -n "$SKILL_NAME" ] || die "installer manifest is missing skill.name"
  [ -n "$MCP_NAME" ] || die "installer manifest is missing mcp.name"
  [ "${#MCP_ENV_KEYS[@]}" -gt 0 ] || die "installer manifest is missing mcp.env_keys"
  [ "${#OFFLINE_ENV_KEYS[@]}" -gt 0 ] || die "installer manifest mcp.env_keys does not provide offline environment keys"
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
  --user-config           Also merge the offline runtime block into the platform user config.
                          Linux: ~/.config/paper-fetch/.env
                          macOS: ~/Library/Application Support/paper-fetch/.env
  --no-user-config        Do not touch the platform user config. This is the default.
  --reuse-env-file <path> Use an existing offline.env without modifying it.
  --skip-smoke            Skip local command smoke checks after installation.
  --uninstall             Remove user-level shell, skill, and MCP integration without deleting the install directory.
  --purge                 Remove user-level integration and delete the install directory.
  -h, --help              Show this help.

Environment:
  PAPER_FETCH_BROWSER_HEADLESS Set to false for a headful managed browser runtime.
EOF
}

normalize_mcp_env_keys() {
  local key seen_headless=0
  local filtered=()
  for key in "${MCP_ENV_KEYS[@]}"; do
    case "$key" in
      PLAYWRIGHT_BROWSERS_PATH)
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

derive_env_key_sets() {
  local key
  SHELL_ENV_KEYS=("${MCP_ENV_KEYS[@]}")
  ACTIVATE_ENV_KEYS=("${MCP_ENV_KEYS[@]}")
  OFFLINE_ENV_KEYS=()
  for key in "${MCP_ENV_KEYS[@]}"; do
    if [ "$key" != "PAPER_FETCH_ENV_FILE" ]; then
      OFFLINE_ENV_KEYS+=("$key")
    fi
  done
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
  "$PYTHON_BIN" -I -c '
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

canonical_path() {
  "$PYTHON_BIN" -I - "$1" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).resolve(strict=False))
PY
}

check_target_is_not_home_or_ancestor() {
  local canonical_target="$1"
  local action="$2"
  local canonical_home

  case "$canonical_target" in
    /) die "Refusing to $action unsafe directory: $canonical_target" ;;
  esac

  [ -n "${HOME:-}" ] || die "HOME is required to validate the $action directory."
  canonical_home="$(canonical_path "$HOME")"
  case "$canonical_home/" in
    "$canonical_target/"*)
      die "Refusing to $action HOME or an ancestor of HOME: $canonical_target"
      ;;
  esac
}

install_manifest_is_owned() {
  local manifest="$1"
  [ -f "$manifest" ] || return 1

  "$PYTHON_BIN" -I - "$manifest" <<'PY' >/dev/null 2>&1
from __future__ import annotations

import json
from pathlib import Path
import sys

try:
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError):
    raise SystemExit(1)

target = manifest.get("target")
owned = (
    manifest.get("schema_version") == 3
    and manifest.get("project") == "paper-fetch-skill"
    and manifest.get("entrypoint") == "install-offline.sh"
    and isinstance(target, dict)
    and isinstance(target.get("platform"), str)
    and isinstance(target.get("arch"), str)
    and isinstance(target.get("python_tag"), str)
)
raise SystemExit(0 if owned else 1)
PY
}

directory_is_empty() {
  local first_entry
  first_entry="$(find "$1" -mindepth 1 -maxdepth 1 -print -quit)"
  [ -z "$first_entry" ]
}

check_install_target() {
  local canonical_install_root canonical_bundle_root target_manifest

  canonical_install_root="$(canonical_path "$INSTALL_ROOT")"
  canonical_bundle_root="$(canonical_path "$BUNDLE_ROOT")"
  check_target_is_not_home_or_ancestor "$canonical_install_root" "install into"

  if [ "$canonical_install_root" = "$canonical_bundle_root" ]; then
    return 0
  fi
  if [ ! -e "$INSTALL_ROOT" ] && [ ! -L "$INSTALL_ROOT" ]; then
    return 0
  fi
  [ -d "$INSTALL_ROOT" ] \
    || die "Refusing to install into a non-directory target: $INSTALL_ROOT"
  if directory_is_empty "$canonical_install_root"; then
    return 0
  fi

  target_manifest="$canonical_install_root/offline-manifest.json"
  install_manifest_is_owned "$target_manifest" \
    || die "Refusing to replace a non-empty unowned install directory: $canonical_install_root"
  [ -s "$canonical_install_root/runtime/python-bin" ] \
    || die "Refusing to replace a non-empty directory without the runtime/python-bin installer marker: $canonical_install_root"
}

check_platform() {
  require_file "$BUNDLE_ROOT/offline-manifest.json"

  local manifest_platform manifest_arch manifest_minimum_os_version host_os_version
  HOST_PLATFORM="$(host_platform)" || die "This offline bundle supports Linux and macOS only; detected $(uname -s)."
  HOST_ARCH="$(host_arch)" || die "This offline bundle supports x86_64 and arm64 only; detected $(uname -m)."
  manifest_platform="$(offline_manifest_value target.platform)"
  manifest_arch="$(offline_manifest_value target.arch)"
  [ -n "$manifest_platform" ] || die "offline-manifest.json is missing target.platform."
  [ -n "$manifest_arch" ] || die "offline-manifest.json is missing target.arch."

  case "$HOST_PLATFORM:$HOST_ARCH" in
    linux:x86_64|macos:arm64) ;;
    linux:arm64) die "Linux offline bundles currently support x86_64 only; detected arm64." ;;
    macos:x86_64) die "macOS offline bundles currently support Apple Silicon arm64 only; detected x86_64." ;;
    *) die "Unsupported offline target host: $HOST_PLATFORM/$HOST_ARCH." ;;
  esac

  [ "$HOST_PLATFORM" = "$manifest_platform" ] \
    || die "bundle targets $manifest_platform; detected $HOST_PLATFORM."
  [ "$HOST_ARCH" = "$manifest_arch" ] \
    || die "bundle targets $manifest_arch; detected $HOST_ARCH."

  if [ "$HOST_PLATFORM" = "macos" ]; then
    manifest_minimum_os_version="$(offline_manifest_value target.minimum_os_version)"
    [ -n "$manifest_minimum_os_version" ] \
      || die "offline-manifest.json is missing target.minimum_os_version for macOS."
    command -v sw_vers >/dev/null 2>&1 \
      || die "sw_vers is required to verify the macOS version."
    host_os_version="$(sw_vers -productVersion)"
    "$PYTHON_BIN" -I - "$host_os_version" "$manifest_minimum_os_version" <<'PY' \
      || die "This bundle requires macOS $manifest_minimum_os_version or newer; detected macOS $host_os_version."
from __future__ import annotations

import re
import sys


def version_tuple(value: str) -> tuple[int, ...]:
    parts = value.strip().split(".")
    if not parts or any(re.fullmatch(r"\d+", part) is None for part in parts):
        raise SystemExit(1)
    return tuple(int(part) for part in parts)


detected = version_tuple(sys.argv[1])
minimum = version_tuple(sys.argv[2])
width = max(len(detected), len(minimum))
detected += (0,) * (width - len(detected))
minimum += (0,) * (width - len(minimum))
raise SystemExit(0 if detected >= minimum else 1)
PY
  fi
}

check_python() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "python3 was not found on PATH."
  require_file "$BUNDLE_ROOT/offline-manifest.json"

  local probe version implementation tag interpreter_arch soabi abi_flags gil_disabled
  local manifest_tag expected_soabi_prefix
  probe="$("$PYTHON_BIN" -I -c '
# PAPER_FETCH_INTERPRETER_PROBE
import platform
import sys
import sysconfig

version = ".".join(map(str, sys.version_info[:3]))
implementation = sys.implementation.name
tag = (
    f"cp{sys.version_info.major}{sys.version_info.minor}"
    if implementation == "cpython"
    else implementation
)
machine = platform.machine().lower()
machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
soabi = str(sysconfig.get_config_var("SOABI") or "")
abi_flags = str(getattr(sys, "abiflags", "") or "-")
gil_disabled = "1" if sysconfig.get_config_var("Py_GIL_DISABLED") else "0"
print("|".join((version, implementation, tag, machine, soabi, abi_flags, gil_disabled)))
')"
  IFS='|' read -r version implementation tag interpreter_arch soabi abi_flags gil_disabled <<< "$probe"
  manifest_tag="$("$PYTHON_BIN" -I -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("target", {}).get("python_tag", ""))' "$BUNDLE_ROOT/offline-manifest.json")"
  [ -n "$manifest_tag" ] || die "offline-manifest.json is missing target.python_tag."

  [ "$implementation" = "cpython" ] \
    || die "Offline bundles require standard GIL CPython; detected $implementation $version."
  case "$tag" in
    cp311|cp312|cp313|cp314) ;;
    *) die "Offline bundles require standard GIL CPython 3.11, 3.12, 3.13, or 3.14; detected $version ($tag)." ;;
  esac
  [ "$tag" = "$manifest_tag" ] || die "bundle requires CPython $manifest_tag; detected Python $version ($tag)."
  [ "$interpreter_arch" = "$HOST_ARCH" ] \
    || die "bundle requires Python interpreter architecture $HOST_ARCH; detected $interpreter_arch Python $version."
  [ "$abi_flags" = "-" ] && [ "$gil_disabled" = "0" ] \
    || die "Offline bundles require standard GIL CPython without debug or free-threaded ABI flags; detected SOABI ${soabi:-<empty>}."
  expected_soabi_prefix="cpython-${tag#cp}-"
  case "$soabi" in
    "$expected_soabi_prefix"*) ;;
    *) die "Offline bundles require standard SOABI ${expected_soabi_prefix}*; detected ${soabi:-<empty>}." ;;
  esac
}

write_runtime_python_file() {
  local resolved_python
  resolved_python="$(command -v "$PYTHON_BIN")"
  mkdir -p "$INSTALL_ROOT/runtime"
  printf '%s\n' "$resolved_python" > "$INSTALL_ROOT/runtime/python-bin"
}

verify_checksums() {
  require_file "$BUNDLE_ROOT/sha256sums.txt"
  log "Validating bundled payload inventory"
  "$PYTHON_BIN" -I - "$BUNDLE_ROOT" <<'PY'
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"unsafe offline checksum inventory: {message}")


bundle_root = Path(sys.argv[1])
checksum_path = bundle_root / "sha256sums.txt"
try:
    checksum_mode = checksum_path.lstat().st_mode
except OSError as exc:
    fail(f"cannot inspect sha256sums.txt: {exc}")
if stat.S_ISLNK(checksum_mode) or not stat.S_ISREG(checksum_mode):
    fail("sha256sums.txt must be a real regular file")

try:
    checksum_lines = checksum_path.read_text(encoding="utf-8").splitlines()
except (OSError, UnicodeError) as exc:
    fail(f"cannot read sha256sums.txt: {exc}")

entry_pattern = re.compile(r"([0-9A-Fa-f]{64})  (\./.+)\Z")
expected: set[str] = set()
for line_number, line in enumerate(checksum_lines, start=1):
    match = entry_pattern.fullmatch(line)
    if match is None:
        fail(f"line {line_number} is not '<sha256>  ./<relative-path>'")
    inventory_path = match.group(2)
    relative_text = inventory_path[2:]
    if "\\" in relative_text or any(
        ord(character) < 32 or ord(character) == 127
        for character in relative_text
    ):
        fail(f"line {line_number} contains an unsafe path: {inventory_path!r}")
    parts = relative_text.split("/")
    normalized = PurePosixPath(relative_text).as_posix()
    if (
        not relative_text
        or relative_text.startswith("/")
        or any(part in ("", ".", "..") for part in parts)
        or normalized != relative_text
    ):
        fail(f"line {line_number} is not a normalized relative path: {inventory_path!r}")
    if relative_text == "sha256sums.txt":
        fail("sha256sums.txt must not list itself")
    if relative_text in expected:
        fail(f"duplicate path on line {line_number}: {inventory_path!r}")

    cursor = bundle_root
    for part in parts:
        cursor /= part
        try:
            mode = cursor.lstat().st_mode
        except OSError as exc:
            fail(f"listed payload path is missing: {inventory_path!r}: {exc}")
        if stat.S_ISLNK(mode):
            fail(f"payload symlink is not allowed: {inventory_path!r}")
    if not stat.S_ISREG(mode):
        fail(f"listed payload path is not a regular file: {inventory_path!r}")
    expected.add(relative_text)

actual: set[str] = set()
for current_root, directory_names, file_names in os.walk(
    bundle_root,
    topdown=True,
    followlinks=False,
):
    current = Path(current_root)
    for name in directory_names:
        candidate = current / name
        try:
            mode = candidate.lstat().st_mode
        except OSError as exc:
            fail(f"cannot inspect payload directory {candidate}: {exc}")
        if stat.S_ISLNK(mode):
            relative = candidate.relative_to(bundle_root).as_posix()
            fail(f"payload symlink is not allowed: './{relative}'")
        if not stat.S_ISDIR(mode):
            relative = candidate.relative_to(bundle_root).as_posix()
            fail(f"payload path is not a directory: './{relative}'")
    for name in file_names:
        candidate = current / name
        relative = candidate.relative_to(bundle_root).as_posix()
        try:
            mode = candidate.lstat().st_mode
        except OSError as exc:
            fail(f"cannot inspect payload file './{relative}': {exc}")
        if stat.S_ISLNK(mode):
            fail(f"payload symlink is not allowed: './{relative}'")
        if not stat.S_ISREG(mode):
            fail(f"payload path is not a regular file: './{relative}'")
        if candidate == checksum_path:
            continue
        actual.add(relative)

unlisted = sorted(actual - expected)
if unlisted:
    fail("unlisted payload file(s): " + ", ".join(f"./{path}" for path in unlisted[:10]))
missing = sorted(expected - actual)
if missing:
    fail("listed payload file(s) are missing: " + ", ".join(f"./{path}" for path in missing[:10]))
PY
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
  local verifier="$runtime_root/scripts/skill_integrity.py"

  require_file "$runtime_root/offline-manifest.json"
  require_file "$verifier"
  log "Verifying $phase skill bundle manifest"
  "$runtime_root/runtime/paper-fetch-python" -X utf8 \
    "$verifier" verify \
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

check_macos_quarantine() {
  [ "$HOST_PLATFORM" = "macos" ] || return 0
  command -v xattr >/dev/null 2>&1 \
    || die "xattr is required to verify the macOS offline bundle."

  local quarantine_output
  if quarantine_output="$(xattr -r -s -v "$BUNDLE_ROOT" 2>&1)"; then
    :
  else
    die "Could not recursively inspect macOS quarantine attributes; refusing to install the bundle: $quarantine_output"
  fi
  if grep -E -q ': com\.apple\.quarantine$' <<< "$quarantine_output"; then
    die "macOS quarantine is present within the offline bundle. Run 'xattr -dr com.apple.quarantine \"$BUNDLE_ROOT\"' after verifying the release, then retry the installer."
  fi
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

resolve_managed_file_target() {
  local target="$1"
  local link depth=0
  while [ -L "$target" ]; do
    depth=$((depth + 1))
    [ "$depth" -le 32 ] || die "Refusing to edit a shell startup symlink loop: $1"
    link="$(readlink "$target")"
    case "$link" in
      /*) target="$link" ;;
      *) target="$(dirname "$target")/$link" ;;
    esac
  done
  printf '%s\n' "$target"
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
  local tmp mode edit_target

  select_shell_startup_file
  edit_target="$(resolve_managed_file_target "$SHELL_STARTUP_TARGET")"
  tmp="$(mktemp)"
  mode=""
  mkdir -p "$(dirname "$edit_target")"
  if [ -f "$edit_target" ]; then
    mode="$(file_mode "$edit_target")"
    awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$edit_target" > "$tmp"
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

  mv "$tmp" "$edit_target"
  if [ -n "$mode" ]; then
    chmod "$mode" "$edit_target"
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
  local tmp mode edit_target

  [ -f "$target" ] || [ -L "$target" ] || return 0
  edit_target="$(resolve_managed_file_target "$target")"
  [ -f "$edit_target" ] || return 0
  grep -F -x -q "$MANAGED_BEGIN" "$edit_target" || return 0
  tmp="$(mktemp)"
  mode="$(file_mode "$edit_target")"
  awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    !skip { print }
  ' "$edit_target" > "$tmp"

  if [ "$remove_if_empty" = "1" ] && ! grep -q '[^[:space:]]' "$tmp"; then
    rm -f "$tmp" "$edit_target"
    log "Removed empty managed file $target"
    return 0
  fi

  mv "$tmp" "$edit_target"
  if [ -n "$mode" ]; then
    chmod "$mode" "$edit_target"
  fi
  log "Removed managed block from $target"
}

remove_shell_startup_blocks() {
  [ -n "${HOME:-}" ] || die "HOME is required for --uninstall."

  remove_managed_block_from_file "$HOME/.bashrc"
  remove_managed_block_from_file "$HOME/.zshrc"
  remove_managed_block_from_file "$HOME/.profile"
  remove_managed_block_from_file "$HOME/.config/fish/conf.d/paper-fetch-offline.fish" 1
}

remove_user_config_blocks() {
  [ -n "${HOME:-}" ] || die "HOME is required for --uninstall."

  remove_managed_block_from_file "$HOME/.config/paper-fetch/.env" 1
  remove_managed_block_from_file \
    "$HOME/Library/Application Support/paper-fetch/.env" \
    1
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
  remove_user_config_blocks
  unregister_codex_mcp
  unregister_claude_mcp
  unregister_antigravity_mcp

  echo
  echo "Offline user-level integration removed."
  echo "Install directory was left in place: $INSTALL_ROOT"
}

purge_install_root() {
  [ -n "$PURGE_INSTALL_ROOT" ] \
    || die "Validated purge target is required for --purge."
  case "$PURGE_INSTALL_ROOT" in
    /|"") die "Refusing to purge unsafe install directory: $PURGE_INSTALL_ROOT" ;;
  esac
  rm -rf -- "$PURGE_INSTALL_ROOT"
  echo "Install directory deleted: $PURGE_INSTALL_ROOT"
}

check_purge_target() {
  [ -n "$INSTALL_ROOT" ] || die "INSTALL_ROOT is required for --purge."
  local lexical_install_root canonical_install_root target_manifest
  lexical_install_root="$("$PYTHON_BIN" -I - "$INSTALL_ROOT" <<'PY'
import os
import sys

print(os.path.abspath(sys.argv[1]))
PY
)"
  [ ! -L "$lexical_install_root" ] \
    || die "Refusing to purge through a symbolic-link install directory: $INSTALL_ROOT"
  [ -d "$INSTALL_ROOT" ] \
    || die "Refusing to purge a missing install directory: $INSTALL_ROOT"

  canonical_install_root="$(canonical_path "$INSTALL_ROOT")"
  check_target_is_not_home_or_ancestor "$canonical_install_root" "purge"

  target_manifest="$canonical_install_root/offline-manifest.json"
  install_manifest_is_owned "$target_manifest" \
    || die "Refusing to purge a directory without an owned offline-manifest.json: $canonical_install_root"
  [ -s "$canonical_install_root/runtime/python-bin" ] \
    || die "Refusing to purge a directory without the runtime/python-bin installer marker: $canonical_install_root"
  PURGE_INSTALL_ROOT="$lexical_install_root"
}

user_config_env_file() {
  [ -n "${HOME:-}" ] || die "HOME is required for --user-config."
  if [ "$HOST_PLATFORM" = "macos" ]; then
    printf '%s\n' "$HOME/Library/Application Support/paper-fetch/.env"
  else
    printf '%s\n' "$HOME/.config/paper-fetch/.env"
  fi
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
  "$runtime_python" -c 'import camoufox; import playwright; import pymupdf; from paper_fetch.providers.browser_runtime.camoufox_manager import CamoufoxBrowserManager; assert hasattr(camoufox, "Camoufox"); assert CamoufoxBrowserManager is not None'
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
  local config_env_file
  load_installer_manifest

  if [ "$UNINSTALL" = "1" ]; then
    if [ "$PURGE" = "1" ]; then
      check_purge_target
    fi
    uninstall_user_integrations
    if [ "$PURGE" = "1" ]; then
      purge_install_root
    fi
    return 0
  fi

  check_platform
  check_python
  verify_checksums
  check_macos_quarantine
  check_install_target
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
    config_env_file="$(user_config_env_file)"
    log "Merging offline runtime block into $config_env_file"
    write_managed_env_file "$config_env_file"
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
  echo "The Camoufox browser binary is not bundled or downloaded during installation."
  echo "CLI, MCP, and library requests do not download, update, or repair the Camoufox runtime."
  echo "Before moving fully offline, run '$INSTALL_ROOT/runtime/paper-fetch-python -m camoufox fetch', then 'paper-fetch browser-preflight'."
  echo "Browser backend: Camoufox."
  echo "Restart Codex, Claude Code, and the Antigravity CLI so they rescan skills and MCP registration."
  echo "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=\"...\" to $OFFLINE_ENV_FILE before fetching Elsevier papers."
}

main "$@"
