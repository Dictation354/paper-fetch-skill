#!/usr/bin/env bash
# Verify an offline installer or macOS tarball in a temporary installation.

set -euo pipefail

PACKAGE_PATH="${1:-}"
VERIFY_MODE="${2:-}"
SKIP_FETCH_SMOKE="${PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE:-0}"
HOST_PYTHON_BIN="${PAPER_FETCH_OFFLINE_PYTHON_BIN:-python3}"
TARGET_PLATFORM=""
VERIFY_SHELL="/bin/bash"
SHELL_STARTUP_NAME=".bashrc"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

if [ -z "$PACKAGE_PATH" ]; then
  die "Usage: scripts/verify-offline-package.sh <offline-installer.sh|offline-bundle.tar.gz> [--archive-preflight-only]"
fi
case "$VERIFY_MODE" in
  ""|--archive-preflight-only) ;;
  *) die "Unknown verifier option: $VERIFY_MODE" ;;
esac

PACKAGE_PATH="$(cd "$(dirname "$PACKAGE_PATH")" && pwd)/$(basename "$PACKAGE_PATH")"
[ -f "$PACKAGE_PATH" ] || die "Package not found: $PACKAGE_PATH"
command -v "$HOST_PYTHON_BIN" >/dev/null 2>&1 \
  || die "$HOST_PYTHON_BIN is required for safe offline archive handling."

TMP_ROOT="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

EXTRACT_ROOT="$TMP_ROOT/extracted"
INSTALLER_PATH="$PACKAGE_PATH"
BUNDLE_SOURCE_ROOT=""

extract_offline_archive_safely() {
  local archive="$1"
  local destination="$2"

  "$HOST_PYTHON_BIN" - "$archive" "$destination" <<'PY'
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import posixpath
import stat
import sys
import tarfile


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"unsafe offline archive: {message}")


def normalized_member_name(value: str, *, label: str) -> str:
    if not value or "\x00" in value:
        fail(f"{label} is empty or contains NUL")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        fail(f"{label} contains control characters: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("/"):
        fail(f"{label} is absolute: {value!r}")
    if ".." in path.parts:
        fail(f"{label} contains '..': {value!r}")
    parts = tuple(part for part in path.parts if part not in ("", "."))
    if not parts:
        fail(f"{label} has no usable path components: {value!r}")
    return posixpath.join(*parts)


def normalized_link_target(member_name: str, link_name: str, *, hard: bool) -> str:
    if not link_name or "\x00" in link_name:
        fail(f"link target for {member_name!r} is empty or contains NUL")
    if any(ord(character) < 32 or ord(character) == 127 for character in link_name):
        fail(f"link target for {member_name!r} contains control characters")
    link_path = PurePosixPath(link_name)
    if link_path.is_absolute() or link_name.startswith("/"):
        fail(f"link target for {member_name!r} is absolute: {link_name!r}")
    base = "" if hard else posixpath.dirname(member_name)
    target = posixpath.normpath(posixpath.join(base, link_name))
    if target in ("", ".") or target == ".." or target.startswith("../"):
        fail(f"link target for {member_name!r} escapes the archive: {link_name!r}")
    return target


archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2])
destination.mkdir(parents=True, exist_ok=True)

if not hasattr(tarfile, "data_filter"):
    fail("Python tarfile.data_filter is required; use a maintained CPython 3.11+")

try:
    with tarfile.open(archive_path, mode="r:*") as bundle:
        members = bundle.getmembers()
        if not members:
            fail("archive is empty")

        normalized: dict[str, tarfile.TarInfo] = {}
        top_levels: set[str] = set()
        for member in members:
            name = normalized_member_name(member.name, label="member name")
            if name in normalized:
                fail(f"duplicate member path: {name!r}")
            normalized[name] = member
            top_levels.add(PurePosixPath(name).parts[0])
            if not (
                member.isdir()
                or member.isreg()
                or member.issym()
                or member.islnk()
            ):
                fail(f"special file is not allowed: {name!r}")

        if len(top_levels) != 1:
            fail(
                "expected exactly one top-level directory; found "
                + ", ".join(sorted(top_levels))
            )
        top_level = next(iter(top_levels))

        for name, member in normalized.items():
            if not (member.issym() or member.islnk()):
                continue
            target = normalized_link_target(
                name,
                member.linkname,
                hard=member.islnk(),
            )
            if PurePosixPath(target).parts[0] != top_level:
                fail(
                    f"link target for {name!r} leaves top-level directory "
                    f"{top_level!r}: {member.linkname!r}"
                )
            if member.islnk():
                target_member = normalized.get(target)
                if target_member is None or not target_member.isreg():
                    fail(
                        f"hardlink target for {name!r} is not a regular "
                        f"archive member: {member.linkname!r}"
                    )

        bundle.extractall(destination, filter="data")
except (OSError, tarfile.TarError) as exc:
    fail(f"could not inspect or extract archive: {exc}")

top_path = destination / top_level
try:
    mode = top_path.lstat().st_mode
except OSError as exc:
    fail(f"top-level directory is missing after extraction: {exc}")
if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
    fail(f"top-level member is not a real directory: {top_level!r}")
destination_real = destination.resolve(strict=True)
top_real = top_path.resolve(strict=True)
if os.path.commonpath((str(destination_real), str(top_real))) != str(
    destination_real
):
    fail(f"top-level directory escaped extraction root: {top_level!r}")
print(top_level)
PY
}

case "$PACKAGE_PATH" in
  *.tar.gz|*.tgz)
    mkdir -p "$EXTRACT_ROOT"
    log "Safely inspecting and extracting offline bundle"
    bundle_name="$(extract_offline_archive_safely "$PACKAGE_PATH" "$EXTRACT_ROOT")" \
      || die "Offline bundle archive safety preflight failed."
    bundle_root="$EXTRACT_ROOT/$bundle_name"
    if [ "$VERIFY_MODE" = "--archive-preflight-only" ]; then
      log "Offline bundle archive safety preflight completed"
      exit 0
    fi
    INSTALLER_PATH="$bundle_root/install-offline.sh"
    BUNDLE_SOURCE_ROOT="$bundle_root"
    [ -x "$INSTALLER_PATH" ] || die "Offline bundle is missing executable install-offline.sh."
    ;;
  *.sh)
    [ "$VERIFY_MODE" != "--archive-preflight-only" ] \
      || die "--archive-preflight-only requires a .tar.gz or .tgz bundle."
    ;;
  *) die "Unsupported offline package extension: $PACKAGE_PATH" ;;
esac

case "$(uname -s)" in
  Linux)
    TARGET_PLATFORM="linux"
    ;;
  Darwin)
    TARGET_PLATFORM="macos"
    VERIFY_SHELL="/bin/zsh"
    SHELL_STARTUP_NAME=".zshrc"
    [ -x "$VERIFY_SHELL" ] || die "macOS offline verification requires /bin/zsh."
    [ -n "$BUNDLE_SOURCE_ROOT" ] \
      || die "macOS offline verification requires a .tar.gz bundle."
    ;;
  *)
    die "Offline package verification supports Linux and macOS only."
    ;;
esac

verify_macos_macho_file() {
  local path="$1"
  local description="$2"
  local file_output architectures
  file_output="$(file -b "$path")"
  case "$file_output" in
    *Mach-O*) ;;
    *) die "$description is not a Mach-O binary: $file_output" ;;
  esac
  architectures="$(lipo -archs "$path" 2>/dev/null)" \
    || die "Could not inspect $description architecture: $path"
  [ "$architectures" = "arm64" ] \
    || die "$description must be a thin arm64 Mach-O binary; detected ${architectures:-<unknown>}: $path"
  codesign --verify --strict "$path" \
    || die "$description does not have a valid ad-hoc code signature: $path"
}

macos_contained_path() {
  local root="$1"
  local candidate="$2"
  local expected_kind="$3"

  "$HOST_PYTHON_BIN" - "$root" "$candidate" "$expected_kind" <<'PY'
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys

root = Path(os.path.abspath(sys.argv[1]))
candidate = Path(os.path.abspath(sys.argv[2]))
expected_kind = sys.argv[3]

try:
    relative = candidate.relative_to(root)
except ValueError:
    raise SystemExit("path escapes the bundle lexically")

cursor = root
try:
    for part in relative.parts:
        cursor /= part
        mode = cursor.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise SystemExit(f"symlink is not allowed: {cursor}")

    root_real = root.resolve(strict=True)
    candidate_real = candidate.resolve(strict=True)
    if os.path.commonpath((str(root_real), str(candidate_real))) != str(root_real):
        raise SystemExit("path resolves outside the bundle")

    mode = candidate.lstat().st_mode
except OSError as exc:
    raise SystemExit(f"path inspection failed: {exc}")

if expected_kind == "regular":
    if not stat.S_ISREG(mode):
        raise SystemExit("path is not a regular file")
elif expected_kind == "directory":
    if not stat.S_ISDIR(mode):
        raise SystemExit("path is not a directory")
else:
    raise SystemExit(f"unknown expected path kind: {expected_kind}")

print(candidate)
PY
}

macos_rpaths() {
  local path="$1"
  local containment_root="$2"
  local executable_dir="$3"
  local load_commands rpath candidate resolved

  load_commands="$(otool -l "$path")" \
    || die "Could not inspect Mach-O load commands: $path"
  while IFS= read -r rpath; do
    [ -n "$rpath" ] || continue
    case "$rpath" in
      @loader_path|@loader_path/*)
        candidate="$(dirname "$path")${rpath#@loader_path}"
        ;;
      @executable_path|@executable_path/*)
        candidate="$executable_dir${rpath#@executable_path}"
        ;;
      /*)
        die "Mach-O binary has an absolute/build-host LC_RPATH: $path -> $rpath"
        ;;
      *)
        die "Mach-O binary has an unsupported LC_RPATH: $path -> $rpath"
        ;;
    esac
    resolved="$(macos_contained_path "$containment_root" "$candidate" directory)" \
      || die "Mach-O LC_RPATH does not resolve to a real bundle directory: $path -> $rpath"
    printf '%s\n' "$resolved"
  done < <(
    printf '%s\n' "$load_commands" \
      | awk '
          $1 == "cmd" && $2 == "LC_RPATH" { want_path = 1; next }
          want_path && $1 == "path" {
            line = $0
            sub(/^[[:space:]]*path[[:space:]]+/, "", line)
            sub(/[[:space:]]+\(offset[[:space:]]+[0-9]+\)$/, "", line)
            print line
            want_path = 0
          }
        '
  )
}

resolve_macos_macho_dependency() {
  local owner="$1"
  local dependency="$2"
  local containment_root="$3"
  local executable_dir="$4"
  local rpaths="$5"
  local candidate resolved rpath

  case "$dependency" in
    /System/*|/usr/lib/*)
      case "/$dependency/" in
        *"/../"*)
          die "Mach-O dependency contains a parent-directory traversal: $owner -> $dependency"
          ;;
      esac
      return 0
      ;;
    @loader_path|@loader_path/*)
      candidate="$(dirname "$owner")${dependency#@loader_path}"
      ;;
    @executable_path|@executable_path/*)
      candidate="$executable_dir${dependency#@executable_path}"
      ;;
    @rpath|@rpath/*)
      while IFS= read -r rpath; do
        [ -n "$rpath" ] || continue
        candidate="$rpath${dependency#@rpath}"
        if resolved="$(
          macos_contained_path "$containment_root" "$candidate" regular 2>/dev/null
        )"; then
          printf '%s\n' "$resolved"
          return 0
        fi
      done <<< "$rpaths"
      die "Mach-O @rpath dependency has no resolvable bundle target: $owner -> $dependency"
      ;;
    /*)
      die "Mach-O binary has a non-relocatable dependency from the build host: $owner -> $dependency"
      ;;
    *)
      die "Mach-O binary has an unsupported relative dependency: $owner -> $dependency"
      ;;
  esac

  resolved="$(macos_contained_path "$containment_root" "$candidate" regular)" \
    || die "Mach-O dependency is not a real regular file inside the bundle: $owner -> $dependency"
  printf '%s\n' "$resolved"
}

verify_macos_macho_dependencies() {
  local path="$1"
  local description="$2"
  local containment_root="$3"
  local executable_dir="$4"
  local canonical dependencies dependency install_id_output install_id rpaths resolved

  canonical="$(macos_contained_path "$containment_root" "$path" regular)" \
    || die "$description is not a real regular file inside the bundle: $path"
  if grep -F -x -q "$canonical" "$MACHO_VISITED_FILE" 2>/dev/null; then
    return 0
  fi
  printf '%s\n' "$canonical" >> "$MACHO_VISITED_FILE"

  verify_macos_macho_file "$canonical" "$description"
  rpaths="$(macos_rpaths "$canonical" "$containment_root" "$executable_dir")" \
    || die "Could not validate Mach-O LC_RPATH entries: $canonical"
  dependencies="$(otool -L "$canonical")" \
    || die "Could not inspect Mach-O dependencies: $canonical"
  if install_id_output="$(otool -D "$canonical" 2>/dev/null)"; then
    install_id="$(printf '%s\n' "$install_id_output" | awk 'NR == 2 { print; exit }')"
  else
    install_id=""
  fi

  while IFS= read -r dependency; do
    [ -n "$dependency" ] || continue
    [ -z "$install_id" ] || [ "$dependency" != "$install_id" ] || continue
    resolved="$(
      resolve_macos_macho_dependency \
        "$canonical" \
        "$dependency" \
        "$containment_root" \
        "$executable_dir" \
        "$rpaths"
    )" || die "Could not resolve Mach-O dependency closure: $canonical -> $dependency"
    [ -n "$resolved" ] || continue
    verify_macos_macho_dependencies \
      "$resolved" \
      "Bundled Mach-O dependency" \
      "$containment_root" \
      "$executable_dir"
  done < <(printf '%s\n' "$dependencies" | awk 'NR > 1 { print $1 }')
}

verify_macos_node_runtime() {
  local node="$1"
  local version_output
  verify_macos_macho_dependencies \
    "$node" \
    "Bundled Playwright Node" \
    "$BUNDLE_SOURCE_ROOT" \
    "$(dirname "$node")"

  version_output="$("$node" --version 2>&1)" \
    || die "Bundled Playwright Node runtime failed to launch."
  printf '%s\n' "$version_output" | grep -Eq '^v[0-9]+\.' \
    || die "Bundled Playwright Node returned an unexpected version: $version_output"
}

verify_macos_native_bundle() {
  [ "$TARGET_PLATFORM" = "macos" ] || return 0

  local tool texmath playwright_node library
  for tool in file lipo otool codesign; do
    command -v "$tool" >/dev/null 2>&1 \
      || die "$tool is required for native macOS offline verification."
  done

  texmath="$BUNDLE_SOURCE_ROOT/formula-tools/bin/texmath"
  playwright_node="$BUNDLE_SOURCE_ROOT/runtime/site-packages/playwright/driver/node"
  [ -x "$texmath" ] || die "macOS bundle is missing executable texmath."
  [ -x "$playwright_node" ] || die "macOS bundle is missing executable Playwright Node."

  log "Verifying native arm64 formula and Playwright binaries"
  : > "$MACHO_VISITED_FILE"
  verify_macos_macho_dependencies \
    "$texmath" \
    "Bundled texmath" \
    "$BUNDLE_SOURCE_ROOT/formula-tools" \
    "$BUNDLE_SOURCE_ROOT/formula-tools/bin"
  while IFS= read -r -d '' library; do
    verify_macos_macho_dependencies \
      "$library" \
      "Bundled formula library" \
      "$BUNDLE_SOURCE_ROOT/formula-tools" \
      "$BUNDLE_SOURCE_ROOT/formula-tools/bin"
  done < <(find "$BUNDLE_SOURCE_ROOT/formula-tools/lib" -type f -print0 2>/dev/null)
  verify_macos_node_runtime "$playwright_node"
}

check_macos_bundle_quarantine() {
  [ "$TARGET_PLATFORM" = "macos" ] || return 0
  command -v xattr >/dev/null 2>&1 \
    || die "xattr is required for native macOS offline verification."

  local quarantine_output
  if quarantine_output="$(xattr -r -s -v "$BUNDLE_SOURCE_ROOT" 2>&1)"; then
    :
  else
    die "Could not recursively inspect macOS quarantine attributes; refusing to execute bundled native code: $quarantine_output"
  fi
  if grep -E -q ': com\.apple\.quarantine$' <<< "$quarantine_output"; then
    die "macOS quarantine is present within the offline bundle; refusing to execute bundled native code. Run 'xattr -dr com.apple.quarantine \"$BUNDLE_SOURCE_ROOT\"' only after verifying the release."
  fi
}

MACHO_VISITED_FILE="$TMP_ROOT/macho-visited"
check_macos_bundle_quarantine
verify_macos_native_bundle

INSTALL_ROOT="$TMP_ROOT/install-root"
RUNTIME_PYTHON="$INSTALL_ROOT/runtime/paper-fetch-python"
ACTIVATE_SENTINEL="$TMP_ROOT/activate-env-command-ran"

GUARD_DIR="$TMP_ROOT/guard-bin"
FAKE_HOME="$TMP_ROOT/home"
FAKE_CLI_LOG="$TMP_ROOT/mcp-cli.log"
SHELL_STARTUP_FILE="$FAKE_HOME/$SHELL_STARTUP_NAME"
SHELL_STARTUP_EDIT_FILE="$SHELL_STARTUP_FILE"
USER_CONFIG_FILE=""
INSTALL_USER_CONFIG_FLAG="--no-user-config"
mkdir -p "$GUARD_DIR" "$FAKE_HOME"
mkdir -p "$FAKE_HOME/.gemini/antigravity-cli"
printf '{"mcpServers":{"keep-server":{"command":"keep"}}}\n' > "$FAKE_HOME/.gemini/antigravity-cli/mcp_config.json"
if [ "$TARGET_PLATFORM" = "macos" ]; then
  mkdir -p "$FAKE_HOME/config"
  SHELL_STARTUP_EDIT_FILE="$FAKE_HOME/config/zshrc"
  printf 'keep zsh setting\n' > "$SHELL_STARTUP_EDIT_FILE"
  ln -s "config/zshrc" "$SHELL_STARTUP_FILE"
  USER_CONFIG_FILE="$FAKE_HOME/Library/Application Support/paper-fetch/.env"
  mkdir -p "$(dirname "$USER_CONFIG_FILE")"
  printf 'USER_CONFIG_NOTE="keep"\n' > "$USER_CONFIG_FILE"
  INSTALL_USER_CONFIG_FLAG="--user-config"
fi
for name in curl git npm npx playwright; do
  cat > "$GUARD_DIR/$name" <<'EOF'
#!/usr/bin/env bash
echo "offline installer attempted a blocked network/build command: $(basename "$0") $*" >&2
exit 97
EOF
  chmod +x "$GUARD_DIR/$name"
done
for name in codex claude; do
  cat > "$GUARD_DIR/$name" <<'EOF'
#!/usr/bin/env bash
{
  printf '%s' "$(basename "$0")"
  for arg in "$@"; do
    printf ' %s' "$arg"
  done
  printf '\n'
} >> "$PAPER_FETCH_FAKE_CLI_LOG"
exit 0
EOF
  chmod +x "$GUARD_DIR/$name"
done

log "Running installer with network/build command guard"
export HOME="$FAKE_HOME"
export SHELL="$VERIFY_SHELL"
export PAPER_FETCH_FAKE_CLI_LOG="$FAKE_CLI_LOG"

if [ "$TARGET_PLATFORM" = "macos" ]; then
  QUARANTINED_NATIVE="$(
    find "$BUNDLE_SOURCE_ROOT/runtime/site-packages" \
      -type f \( -name '*.so' -o -name '*.dylib' \) -print -quit
  )"
  [ -n "$QUARANTINED_NATIVE" ] \
    || die "macOS bundle has no native runtime file for the quarantine audit."
  log "Verifying recursive macOS quarantine rejection before user writes"
  xattr -w com.apple.quarantine '0081;00000000;paper-fetch-audit;' "$QUARANTINED_NATIVE"
  QUARANTINE_LOG="$TMP_ROOT/quarantine-install.log"
  if PATH="$GUARD_DIR:$PATH" "$INSTALLER_PATH" \
    --install-dir "$INSTALL_ROOT" \
    --preset=headless \
    --skip-smoke \
    "$INSTALL_USER_CONFIG_FLAG" >"$QUARANTINE_LOG" 2>&1; then
    die "Installer accepted a quarantined native runtime file."
  fi
  if ! grep -qi "quarantine" "$QUARANTINE_LOG"; then
    cat "$QUARANTINE_LOG" >&2
    die "Quarantine rejection did not provide an actionable diagnostic."
  fi
  [ ! -e "$INSTALL_ROOT" ] \
    || die "Quarantine rejection wrote the install directory."
  [ ! -d "$FAKE_HOME/.codex/skills/paper-fetch-skill" ] \
    || die "Quarantine rejection wrote a Codex skill."
  ! grep -F -q "# BEGIN paper-fetch offline managed" "$SHELL_STARTUP_EDIT_FILE" \
    || die "Quarantine rejection modified the Zsh startup target."
  ! grep -F -q "# BEGIN paper-fetch offline managed" "$USER_CONFIG_FILE" \
    || die "Quarantine rejection modified the macOS user config."
  xattr -d com.apple.quarantine "$QUARANTINED_NATIVE"
fi

log "Running initial installer with network/build command guard"
PATH="$GUARD_DIR:$PATH" "$INSTALLER_PATH" \
  --install-dir "$INSTALL_ROOT" \
  --preset=headless \
  --skip-smoke \
  "$INSTALL_USER_CONFIG_FLAG"

log "Preparing an owned upgrade with stale runtime payload"
"$RUNTIME_PYTHON" - "$INSTALL_ROOT/offline.env" "$ACTIVATE_SENTINEL" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
sentinel = sys.argv[2]
text = env_path.read_text(encoding="utf-8")
text = text.replace('ELSEVIER_API_KEY=""', 'ELSEVIER_API_KEY="secret"')
text += 'USER_NOTE="keep"\n'
text += f'PAPER_FETCH_ACTIVATE_SENTINEL="$(touch {sentinel})"\n'
env_path.write_text(text, encoding="utf-8")
PY
mkdir -p "$INSTALL_ROOT/src" "$INSTALL_ROOT/tests" "$INSTALL_ROOT/wheelhouse" "$INSTALL_ROOT/dist"

log "Running owned upgrade with network/build command guard"
PATH="$GUARD_DIR:$PATH" "$INSTALLER_PATH" \
  --install-dir "$INSTALL_ROOT" \
  --preset=headless \
  "$INSTALL_USER_CONFIG_FLAG"

log "Verifying installed runtime package layout"
[ -d "$INSTALL_ROOT/runtime/site-packages/paper_fetch" ] || die "Offline install is missing installed paper_fetch runtime."
[ -x "$RUNTIME_PYTHON" ] || die "Offline install is missing private Python launcher."
[ ! -e "$INSTALL_ROOT/bin/python" ] || die "Offline install should not expose a generic Python wrapper."
[ -x "$INSTALL_ROOT/install-offline.sh" ] || die "Offline install is missing installed installer."
[ ! -d "$INSTALL_ROOT/src" ] || die "Offline install should not include the source tree."
[ ! -d "$INSTALL_ROOT/tests" ] || die "Offline install should not include tests."
[ ! -d "$INSTALL_ROOT/wheelhouse" ] || die "Offline install should not include the build wheelhouse."
[ ! -d "$INSTALL_ROOT/dist" ] || die "Offline install should not include dist."
grep -F -q 'ELSEVIER_API_KEY="secret"' "$INSTALL_ROOT/offline.env"
grep -F -q 'USER_NOTE="keep"' "$INSTALL_ROOT/offline.env"
grep -F -q 'MATHML_TO_LATEX_NODE_BIN=' "$INSTALL_ROOT/offline.env"
grep -F -q "PYTHONUTF8=\"1\"" "$INSTALL_ROOT/offline.env"
grep -F -q "PYTHONIOENCODING=\"utf-8\"" "$INSTALL_ROOT/offline.env"
grep -F -q 'PAPER_FETCH_BROWSER_HEADLESS="true"' "$INSTALL_ROOT/offline.env" || die "Offline install did not configure generic browser headless mode."
if grep -E -q '^[[:space:]]*PAPER_FETCH_BROWSER_USER_AGENT=' "$INSTALL_ROOT/offline.env"; then
  die "Offline install must not override the default Camoufox fingerprint user agent."
fi

log "Verifying user shell, skill, and MCP registration"
[ ! -L "$SHELL_STARTUP_FILE" ] || [ "$TARGET_PLATFORM" = "macos" ] \
  || die "Unexpected shell startup symlink on non-macOS verifier."
if [ "$TARGET_PLATFORM" = "macos" ]; then
  [ -L "$SHELL_STARTUP_FILE" ] \
    || die "Installer replaced the macOS Zsh startup symlink."
fi
grep -F -q "export PAPER_FETCH_ENV_FILE=\"$INSTALL_ROOT/offline.env\"" "$SHELL_STARTUP_FILE"
grep -F -q "export PAPER_FETCH_BROWSER_HEADLESS=\"true\"" "$SHELL_STARTUP_FILE"
grep -F -q "$INSTALL_ROOT/bin" "$SHELL_STARTUP_FILE"
grep -F -q "$INSTALL_ROOT/formula-tools/bin" "$SHELL_STARTUP_FILE"
grep -F -q "$INSTALL_ROOT/image-tools/bin" "$SHELL_STARTUP_FILE"
[ -f "$FAKE_HOME/.codex/skills/paper-fetch-skill/SKILL.md" ] || die "Codex skill was not installed."
[ -f "$FAKE_HOME/.claude/skills/paper-fetch-skill/SKILL.md" ] || die "Claude skill was not installed."
[ -f "$FAKE_HOME/.gemini/antigravity-cli/skills/paper-fetch-skill/SKILL.md" ] || die "Antigravity skill was not installed."
grep -F -q "codex mcp remove paper-fetch" "$FAKE_CLI_LOG"
grep -F -q "codex mcp add" "$FAKE_CLI_LOG"
grep -F -q "claude mcp remove -s user paper-fetch" "$FAKE_CLI_LOG"
grep -F -q "claude mcp add -s user" "$FAKE_CLI_LOG"
grep -F -q "PAPER_FETCH_ENV_FILE=$INSTALL_ROOT/offline.env" "$FAKE_CLI_LOG"
grep -F -q "PAPER_FETCH_FORMULA_TOOLS_DIR=$INSTALL_ROOT/formula-tools" "$FAKE_CLI_LOG"
grep -F -q "PAPER_FETCH_IMAGE_TOOLS_DIR=$INSTALL_ROOT/image-tools" "$FAKE_CLI_LOG"
grep -F -q "MATHML_TO_LATEX_NODE_BIN=" "$FAKE_CLI_LOG"
grep -F -q "PAPER_FETCH_BROWSER_HEADLESS=true" "$FAKE_CLI_LOG"
if [ "$TARGET_PLATFORM" = "macos" ]; then
  grep -F -q 'USER_CONFIG_NOTE="keep"' "$USER_CONFIG_FILE"
  grep -F -q "# BEGIN paper-fetch offline managed" "$USER_CONFIG_FILE"
fi

"$RUNTIME_PYTHON" - "$FAKE_HOME/.gemini/antigravity-cli/mcp_config.json" "$INSTALL_ROOT" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
install_root = Path(sys.argv[2])
data = json.loads(config_path.read_text(encoding="utf-8"))
servers = data["mcpServers"]
assert "keep-server" in servers, servers
entry = servers["paper-fetch"]
assert entry["command"] == str(install_root / "runtime" / "paper-fetch-python"), entry
assert entry["args"] == ["-X", "utf8", "-m", "paper_fetch.mcp.server"], entry
env = entry["env"]
expected = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
    "PAPER_FETCH_ENV_FILE": str(install_root / "offline.env"),
    "PAPER_FETCH_DOWNLOAD_DIR": str(install_root / "downloads"),
    "PAPER_FETCH_FORMULA_TOOLS_DIR": str(install_root / "formula-tools"),
    "PAPER_FETCH_IMAGE_TOOLS_DIR": str(install_root / "image-tools"),
    "MATHML_TO_LATEX_NODE_BIN": str(install_root / "runtime" / "site-packages" / "playwright" / "driver" / "node"),
    "PAPER_FETCH_BROWSER_HEADLESS": "true",
}
for key, value in expected.items():
    assert env.get(key) == value, (key, env)
PY

if [ "$TARGET_PLATFORM" = "macos" ]; then
  log "Verifying activation from native Zsh outside the bundle directory"
  (
    cd "$TMP_ROOT"
    "$VERIFY_SHELL" -f -c '
      source "$1"
      [ "$PAPER_FETCH_ENV_FILE" = "$2" ] || exit 41
      [ "$PAPER_FETCH_DOWNLOAD_DIR" = "$3" ] || exit 42
      [ "$PAPER_FETCH_FORMULA_TOOLS_DIR" = "$4" ] || exit 43
      [ "$MATHML_TO_LATEX_NODE_BIN" = "$5" ] || exit 44
      paper-fetch --help >/dev/null
      texmath --version >/dev/null 2>&1
    ' paper-fetch-zsh-audit \
      "$INSTALL_ROOT/activate-offline.sh" \
      "$INSTALL_ROOT/offline.env" \
      "$INSTALL_ROOT/downloads" \
      "$INSTALL_ROOT/formula-tools" \
      "$INSTALL_ROOT/runtime/site-packages/playwright/driver/node"
  ) || die "Native Zsh activation did not preserve install-local runtime paths."
fi

# shellcheck disable=SC1091
source "$INSTALL_ROOT/activate-offline.sh"
[ ! -e "$ACTIVATE_SENTINEL" ] || die "activate-offline.sh executed shell code from offline.env."
[ "${PYTHONUTF8:-}" = "1" ] || die "activate-offline.sh did not set PYTHONUTF8."
[ "${PYTHONIOENCODING:-}" = "utf-8" ] || die "activate-offline.sh did not set PYTHONIOENCODING."
[ "${MATHML_TO_LATEX_NODE_BIN:-}" = "$INSTALL_ROOT/runtime/site-packages/playwright/driver/node" ] || die "activate-offline.sh did not set bundled Node."

log "Verifying command entrypoints"
paper-fetch --help >/dev/null
test "$(texmath --version 2>&1)" = "Version 0.13.2"
test "$(
  printf '%s' '<math xmlns="http://www.w3.org/1998/Math/MathML"><mfrac><msub><mi>x</mi><mn>1</mn></msub><msqrt><mrow><mi>y</mi><mo>+</mo><mn>1</mn></mrow></msqrt></mfrac></math>' \
    | texmath -f mathml -t tex
)" = '\frac{x_{1}}{\sqrt{y + 1}}'
test "$(
  printf '%s' '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><munderover><mo>∑</mo><mi>i</mi><mi>n</mi></munderover><msup><mi>x</mi><mi>i</mi></msup></mrow></math>' \
    | texmath -f mathml -t tex
)" = '\sum\limits_{i}^{n}x^{i}'
paper-fetch-install-image-tools --target-dir "$INSTALL_ROOT/image-tools" >/dev/null

log "Verifying runtime diagnostics and installed Skill integrity"
DOCTOR_JSON="$TMP_ROOT/doctor.json"
paper-fetch doctor \
  --provider crossref \
  --detail compact \
  --json > "$DOCTOR_JSON"
"$RUNTIME_PYTHON" - "$DOCTOR_JSON" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert "provider_status" in report, report
assert "install_provenance" not in report, report
PY
for skill_dir in \
  "$INSTALL_ROOT/skills/paper-fetch-skill" \
  "$FAKE_HOME/.codex/skills/paper-fetch-skill" \
  "$FAKE_HOME/.claude/skills/paper-fetch-skill" \
  "$FAKE_HOME/.gemini/antigravity-cli/skills/paper-fetch-skill"
do
  "$RUNTIME_PYTHON" -X utf8 "$INSTALL_ROOT/scripts/skill_integrity.py" verify \
    --manifest "$INSTALL_ROOT/offline-manifest.json" \
    --skill-dir "$skill_dir" >/dev/null
done

log "Verifying browser runtime package entrypoint"
"$RUNTIME_PYTHON" - <<'PY'
import camoufox
import playwright
import pymupdf

from paper_fetch.providers.browser_runtime.camoufox_manager import CamoufoxBrowserManager

assert hasattr(camoufox, "Camoufox")
assert CamoufoxBrowserManager is not None
PY

log "Verifying provider_status payload entrypoint"
"$RUNTIME_PYTHON" - <<'PY'
from paper_fetch.mcp.fetch_tool import provider_status_payload

payload = provider_status_payload()
assert "providers" in payload, payload
assert payload["providers"], payload
PY

if [ "$SKIP_FETCH_SMOKE" != "1" ]; then
  log "Running paper-fetch DOI smoke"
  paper-fetch fetch --query "10.1186/1471-2105-11-421" --format json --output "$TMP_ROOT/fetch-smoke.json"
  "$RUNTIME_PYTHON" - "$TMP_ROOT/fetch-smoke.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload.get("doi") or payload.get("metadata", {}).get("doi"), payload.keys()
PY
fi

log "Verifying user-level uninstall"
: > "$FAKE_CLI_LOG"
PATH="$GUARD_DIR:$PATH" "$INSTALL_ROOT/install-offline.sh" --install-dir "$INSTALL_ROOT" --uninstall
[ -f "$SHELL_STARTUP_FILE" ] || die "Shell startup file was removed."
if grep -F -q "# BEGIN paper-fetch offline managed" "$SHELL_STARTUP_FILE"; then
  die "Managed shell block was not removed from $SHELL_STARTUP_FILE."
fi
if [ "$TARGET_PLATFORM" = "macos" ]; then
  [ -L "$SHELL_STARTUP_FILE" ] \
    || die "Uninstall replaced the macOS Zsh startup symlink."
  grep -F -q "keep zsh setting" "$SHELL_STARTUP_EDIT_FILE"
  grep -F -q 'USER_CONFIG_NOTE="keep"' "$USER_CONFIG_FILE"
  if grep -F -q "# BEGIN paper-fetch offline managed" "$USER_CONFIG_FILE"; then
    die "Uninstall left the managed macOS user-config block behind."
  fi
fi
[ ! -d "$FAKE_HOME/.codex/skills/paper-fetch-skill" ] || die "Codex skill was not removed."
[ ! -d "$FAKE_HOME/.claude/skills/paper-fetch-skill" ] || die "Claude skill was not removed."
[ ! -d "$FAKE_HOME/.gemini/antigravity-cli/skills/paper-fetch-skill" ] || die "Antigravity skill was not removed."
grep -F -q "codex mcp remove paper-fetch" "$FAKE_CLI_LOG"
grep -F -q "claude mcp remove -s user paper-fetch" "$FAKE_CLI_LOG"
"$RUNTIME_PYTHON" - "$FAKE_HOME/.gemini/antigravity-cli/mcp_config.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
servers = data["mcpServers"]
assert "keep-server" in servers, servers
assert "paper-fetch" not in servers, servers
PY
[ -f "$INSTALL_ROOT/offline.env" ] || die "Uninstall removed offline.env."
[ -x "$RUNTIME_PYTHON" ] || die "Uninstall removed private Python launcher."
[ ! -e "$INSTALL_ROOT/bin/python" ] || die "Uninstall should not restore a generic Python wrapper."
[ -d "$INSTALL_ROOT/runtime/site-packages" ] || die "Uninstall removed package runtime."

log "Verifying purge removes the install directory"
PATH="$GUARD_DIR:$PATH" "$INSTALLER_PATH" --install-dir "$INSTALL_ROOT" --purge
[ ! -e "$INSTALL_ROOT" ] || die "Purge did not remove the install directory."

log "Offline package verification completed"
