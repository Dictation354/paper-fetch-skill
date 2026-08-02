#!/usr/bin/env bash
# Build Linux x86_64 self-extracting installers and macOS arm64 runtime tarballs.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
BUILD_DIR="${PAPER_FETCH_OFFLINE_BUILD_DIR:-$REPO_DIR/.offline-build}"
OUTPUT_DIR="$REPO_DIR/dist"
PACKAGE_NAME=""
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALLER_MANIFEST_FILE="$REPO_DIR/installer/manifest.json"
MACOS_MINIMUM_OS_VERSION="15.0"
CAMOUFOX_PYTHON_PACKAGE_VERSION=""
PAPER_FETCH_OFFLINE_TOOLING_REVISION="${PAPER_FETCH_OFFLINE_TOOLING_REVISION:-}"
STAGING_OWNERSHIP_MARKER_NAME=".paper-fetch-offline-staging-owner"
STAGING_OWNERSHIP_MARKER_MAGIC="paper-fetch-offline-staging-v1"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/build-offline-package.sh [--output-dir <path>] [--package-name <name>]

Builds a CPython 3.11-3.14 offline runtime package containing:
  - preinstalled Python runtime under runtime/site-packages
  - command wrappers under bin/
  - private Python launcher under runtime/paper-fetch-python
  - texmath under formula-tools/
  - image-tools directory and installer wrapper for optional Ghostscript/libvips converters
  - the full browser and PDF extras; browser binaries are not bundled
Linux x86_64 builds produce a self-extracting .sh installer. macOS arm64 builds
produce a .tar.gz bundle with a macOS 15.0 deployment target.
EOF
}

while (($#)); do
  case "$1" in
    --output-dir)
      shift
      [ "$#" -gt 0 ] || die "--output-dir requires a path"
      OUTPUT_DIR="$1"
      ;;
    --package-name)
      shift
      [ "$#" -gt 0 ] || die "--package-name requires a value"
      PACKAGE_NAME="$1"
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

detect_python_tag() {
  "$PYTHON_BIN" - <<'PY'
import sys
import sysconfig

if sys.implementation.name != "cpython":
    raise SystemExit(1)
if sys.abiflags or sysconfig.get_config_var("Py_GIL_DISABLED"):
    raise SystemExit(1)

expected_soabi = f"cpython-{sys.version_info.major}{sys.version_info.minor}"
soabi = str(sysconfig.get_config_var("SOABI") or "")
if not soabi.startswith(f"{expected_soabi}-"):
    raise SystemExit(1)

print(f"cp{sys.version_info.major}{sys.version_info.minor}")
PY
}

locked_camoufox_version() {
  "$PYTHON_BIN" - "$REPO_DIR/uv.lock" <<'PY'
from __future__ import annotations

from pathlib import Path
import sys
import tomllib

lock_path = Path(sys.argv[1])
with lock_path.open("rb") as handle:
    lock = tomllib.load(handle)
matches = [
    str(package.get("version") or "").strip()
    for package in lock.get("package", [])
    if str(package.get("name") or "").casefold() == "camoufox"
]
if len(matches) != 1 or not matches[0]:
    raise SystemExit(
        "uv.lock must contain exactly one versioned Camoufox package; "
        f"found {len(matches)}"
    )
print(matches[0])
PY
}

detect_python_arch() {
  "$PYTHON_BIN" - <<'PY'
import platform

machine = platform.machine().lower()
aliases = {
    "aarch64": "arm64",
    "amd64": "x86_64",
}
print(aliases.get(machine, machine))
PY
}

is_supported_python_tag() {
  case "$1" in
    cp311|cp312|cp313|cp314) return 0 ;;
    *) return 1 ;;
  esac
}

detect_platform() {
  case "$(uname -s)" in
    Linux) printf 'linux\n' ;;
    Darwin) printf 'macos\n' ;;
    *) return 1 ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64) printf 'x86_64\n' ;;
    arm64|aarch64) printf 'arm64\n' ;;
    *) return 1 ;;
  esac
}

check_target() {
  local platform arch python_tag python_arch minimum_os_version=""
  platform="$(detect_platform)" || die "Offline package build supports Linux and macOS only."
  arch="$(detect_arch)" || die "Offline package build supports x86_64 and arm64 only."
  case "$platform:$arch" in
    linux:x86_64) ;;
    linux:arm64) die "Offline package build currently targets Linux x86_64 only." ;;
    macos:arm64) minimum_os_version="$MACOS_MINIMUM_OS_VERSION" ;;
    macos:x86_64) die "Offline macOS package build currently targets Apple Silicon arm64 only." ;;
    *) die "Unsupported offline package target: $platform/$arch." ;;
  esac
  python_tag="$(detect_python_tag)" \
    || die "Offline package build requires a standard GIL CPython 3.11, 3.12, 3.13, or 3.14 ABI."
  is_supported_python_tag "$python_tag" \
    || die "Offline package build requires standard CPython 3.11, 3.12, 3.13, or 3.14; detected $python_tag."
  python_arch="$(detect_python_arch)" \
    || die "Could not determine the build interpreter architecture."
  [ "$python_arch" = "$arch" ] \
    || die "Build interpreter architecture $python_arch does not match the target host architecture $arch."
  printf '%s %s %s %s\n' "$platform" "$arch" "$python_tag" "$minimum_os_version"
}

validate_package_name() {
  local package_name="$1"
  [ -n "$package_name" ] || die "Unsafe package name: <empty>"
  case "$package_name" in
    [A-Za-z0-9]*)
      case "$package_name" in
        *[!A-Za-z0-9._-]*)
          die "Unsafe package name: $package_name"
          ;;
      esac
      ;;
    *)
      die "Unsafe package name: $package_name"
      ;;
  esac
}

validate_tooling_revision() {
  [ -z "$PAPER_FETCH_OFFLINE_TOOLING_REVISION" ] && return 0
  [[ "$PAPER_FETCH_OFFLINE_TOOLING_REVISION" =~ ^[0-9A-Fa-f]{40}$ ]] \
    || die "PAPER_FETCH_OFFLINE_TOOLING_REVISION must be a 40-character hexadecimal Git revision."
}

canonical_path() {
  "$PYTHON_BIN" -c \
    'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=False))' \
    "$1"
}

path_is_same_or_ancestor() {
  "$PYTHON_BIN" - "$1" "$2" <<'PY'
from pathlib import Path
import sys

candidate = Path(sys.argv[1])
protected = Path(sys.argv[2])
try:
    protected.relative_to(candidate)
except ValueError:
    raise SystemExit(1)
PY
}

path_is_strict_descendant() {
  [ "$1" != "$2" ] && path_is_same_or_ancestor "$2" "$1"
}

validate_build_directory() {
  local build_dir="$1"
  local home_dir

  [ "$build_dir" != "/" ] \
    || die "Unsafe offline build directory: $build_dir"
  [ -n "${HOME:-}" ] \
    || die "HOME must be set to validate the offline build directory."
  home_dir="$(canonical_path "$HOME")" \
    || die "Could not canonicalize HOME for offline build safety checks."
  if path_is_same_or_ancestor "$build_dir" "$home_dir"; then
    die "Offline build directory must not be HOME or one of its ancestors: $build_dir"
  fi
  if path_is_same_or_ancestor "$build_dir" "$REPO_DIR"; then
    die "Offline build directory must not be the repository or one of its ancestors: $build_dir"
  fi
}

directory_is_empty() {
  "$PYTHON_BIN" - "$1" <<'PY'
from pathlib import Path
import sys

directory = Path(sys.argv[1])
raise SystemExit(next(directory.iterdir(), None) is not None)
PY
}

staging_marker_value() {
  local staging="$1"
  local package_name="$2"
  printf '%s\nrepo=%s\nstaging=%s\npackage=%s' \
    "$STAGING_OWNERSHIP_MARKER_MAGIC" \
    "$REPO_DIR" \
    "$staging" \
    "$package_name"
}

staging_is_owned() {
  local staging="$1"
  local package_name="$2"
  local marker="$staging/$STAGING_OWNERSHIP_MARKER_NAME"
  local actual expected

  [ -f "$marker" ] && [ ! -L "$marker" ] || return 1
  actual="$(<"$marker")"
  expected="$(staging_marker_value "$staging" "$package_name")"
  [ "$actual" = "$expected" ]
}

prepare_owned_staging() {
  local requested_staging="$1"
  local package_name="$2"
  local staging marker

  [ ! -L "$requested_staging" ] \
    || die "Offline staging path must not be a symbolic link: $requested_staging"
  staging="$(canonical_path "$requested_staging")" \
    || die "Could not canonicalize offline staging path: $requested_staging"
  path_is_strict_descendant "$staging" "$BUILD_DIR" \
    || die "Offline staging path must be a strict child of the build directory: $staging"
  if [ -e "$staging" ] && [ ! -d "$staging" ]; then
    die "Offline staging path exists but is not a directory: $staging"
  fi

  if [ -d "$staging" ]; then
    if directory_is_empty "$staging"; then
      :
    elif staging_is_owned "$staging" "$package_name"; then
      rm -rf "$staging"
    else
      die "Refusing to remove non-empty offline staging without a valid ownership marker: $staging"
    fi
  fi

  mkdir -p "$staging"
  marker="$staging/$STAGING_OWNERSHIP_MARKER_NAME"
  staging_marker_value "$staging" "$package_name" > "$marker"
  printf '%s\n' "$staging"
}

[ -z "$PACKAGE_NAME" ] || validate_package_name "$PACKAGE_NAME"
validate_tooling_revision

project_version() {
  "$PYTHON_BIN" -c 'import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])' "$REPO_DIR/pyproject.toml"
}

installer_manifest_value() {
  "$PYTHON_BIN" -c '
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
value = data
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
' "$INSTALLER_MANIFEST_FILE" "$1"
}

copy_runtime_assets() {
  local staging="$1"
  log "Copying runtime installer assets"
  mkdir -p "$staging/installer" "$staging/skills"
  cp "$REPO_DIR/install-offline.sh" "$staging/install-offline.sh"
  chmod +x "$staging/install-offline.sh"
  cp "$REPO_DIR/.env.example" "$staging/.env.example"
  cp "$REPO_DIR/LICENSE" "$staging/LICENSE"
  cp "$INSTALLER_MANIFEST_FILE" "$staging/installer/manifest.json"
  cp -a "$REPO_DIR/skills/paper-fetch-skill" "$staging/skills/"
}

build_project_runtime() {
  local staging="$1"
  local package_name="$2"
  local build_support="$staging/.paper-fetch-build-support"
  local project_dist="$build_support/project-dist"
  local wheelhouse="$build_support/runtime-wheelhouse"
  local site_packages="$staging/runtime/site-packages"

  staging_is_owned "$staging" "$package_name" \
    || die "Offline staging ownership changed before runtime assembly: $staging"
  rm -rf "$build_support" "$site_packages"
  mkdir -p "$project_dist" "$wheelhouse" "$site_packages"

  log "Building project wheel"
  "$PYTHON_BIN" -m pip wheel --no-deps --wheel-dir "$project_dist" "$REPO_DIR"

  shopt -s nullglob
  local wheels=("$project_dist"/paper_fetch_skill-*.whl)
  shopt -u nullglob
  [ "${#wheels[@]}" -eq 1 ] || die "Expected one built project wheel, found ${#wheels[@]}."

  log "Downloading binary dependency wheelhouse"
  "$PYTHON_BIN" -m pip download \
    --dest "$wheelhouse" \
    --only-binary=:all: \
    "${wheels[0]}[full]" \
    "camoufox==$CAMOUFOX_PYTHON_PACKAGE_VERSION"

  shopt -s nullglob
  local camoufox_wheels=("$wheelhouse"/camoufox-*.whl)
  shopt -u nullglob
  [ "${#camoufox_wheels[@]}" -eq 1 ] \
    || die "Expected one Camoufox dependency wheel, found ${#camoufox_wheels[@]}."

  "$PYTHON_BIN" - "${camoufox_wheels[0]}" "$CAMOUFOX_PYTHON_PACKAGE_VERSION" <<'PY'
from __future__ import annotations

from email.parser import BytesParser
from pathlib import Path
import sys
from zipfile import ZipFile

wheel = Path(sys.argv[1])
expected_version = sys.argv[2]
with ZipFile(wheel) as archive:
    candidates = []
    for name in archive.namelist():
        if not name.endswith(".dist-info/METADATA"):
            continue
        metadata = BytesParser().parsebytes(archive.read(name))
        if str(metadata.get("Name") or "").casefold() == "camoufox":
            candidates.append(str(metadata.get("Version") or ""))

if len(candidates) != 1:
    raise SystemExit(
        "Camoufox wheel must contain exactly one Camoufox distribution; "
        f"found {len(candidates)} in {wheel.name}"
    )
if candidates[0] != expected_version:
    raise SystemExit(
        f"Camoufox dependency wheel must be exactly {expected_version}; "
        f"found {candidates[0] or '<missing>'} in {wheel.name}"
    )
PY

  log "Installing project runtime into package"
  PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
  "$PYTHON_BIN" -m pip install \
    --target "$site_packages" \
    --no-index \
    --find-links "$wheelhouse" \
    --only-binary=:all: \
    "${wheels[0]}[full]"

  "$PYTHON_BIN" - "$site_packages" "$CAMOUFOX_PYTHON_PACKAGE_VERSION" <<'PY'
from __future__ import annotations

from importlib.metadata import distributions
from pathlib import Path
import sys

site_packages = Path(sys.argv[1])
expected_version = sys.argv[2]
matches = [
    distribution
    for distribution in distributions(path=[str(site_packages)])
    if str(distribution.metadata.get("Name") or "").casefold() == "camoufox"
]
if len(matches) != 1:
    raise SystemExit(
        "Installed runtime must contain exactly one Camoufox distribution; "
        f"found {len(matches)}"
    )
if matches[0].version != expected_version:
    raise SystemExit(
        f"Installed Camoufox runtime must be exactly {expected_version}; "
        f"found {matches[0].version or '<missing>'}"
    )
PY

  log "Precompiling Python runtime bytecode"
  "$PYTHON_BIN" -m compileall -q "$site_packages"

  PYTHONPATH="$site_packages${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -X utf8 -c 'import camoufox; import playwright; import pymupdf; import paper_fetch; import paper_fetch.mcp.server; from paper_fetch.runtime_browser import BrowserContextManager; assert hasattr(camoufox, "Camoufox"); assert BrowserContextManager is not None'

  staging_is_owned "$staging" "$package_name" \
    || die "Offline staging ownership changed during runtime assembly: $staging"
  rm -rf "$build_support"
}

verify_macos_arm64_binary() {
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
}

sign_macos_playwright_node() {
  local staging="$1"
  local target_platform="$2"
  local playwright_node tool

  [ "$target_platform" = "macos" ] || return 0
  for tool in file lipo codesign; do
    command -v "$tool" >/dev/null 2>&1 \
      || die "$tool is required to prepare the native macOS Playwright runtime."
  done

  playwright_node="$staging/runtime/site-packages/playwright/driver/node"
  [ -x "$playwright_node" ] \
    || die "Bundled Playwright Node runtime is missing or not executable: $playwright_node"
  verify_macos_arm64_binary "$playwright_node" "Bundled Playwright Node runtime"

  log "Applying an ad-hoc signature to the bundled Playwright Node runtime"
  codesign --force --sign - --timestamp=none "$playwright_node"
  codesign --verify --strict "$playwright_node" \
    || die "Bundled Playwright Node runtime failed code-signature verification."
}

bundle_formula_tools() {
  local staging="$1"
  local formula_tools="$staging/formula-tools"
  local node_bin npm_bin texmath_bin texmath_version version_output latex_output
  log "Bundling formula tools"
  node_bin="$(command -v node || true)"
  npm_bin="$(command -v npm || true)"
  [ -n "$node_bin" ] || die "Bundling formula tools requires Node.js."
  [ -n "$npm_bin" ] || die "Bundling formula tools requires npm."

  PYTHONPATH="$staging/runtime/site-packages${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -m paper_fetch.formula.install \
      --target-dir "$formula_tools" \
      --no-node
  texmath_bin="$formula_tools/bin/texmath"
  [ -x "$texmath_bin" ] || die "Bundled texmath executable is missing: $texmath_bin"
  if [ -L "$texmath_bin" ]; then
    local resolved_texmath materialized_texmath
    resolved_texmath="$(
      "$PYTHON_BIN" -c \
        'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve(strict=True))' \
        "$texmath_bin"
    )"
    materialized_texmath="$texmath_bin.bundled"
    cp "$resolved_texmath" "$materialized_texmath"
    chmod +x "$materialized_texmath"
    mv "$materialized_texmath" "$texmath_bin"
  fi
  bundle_macos_formula_libraries "$texmath_bin" "$formula_tools"
  texmath_version="$(
    PYTHONPATH="$staging/runtime/site-packages${PYTHONPATH:+:$PYTHONPATH}" \
      "$PYTHON_BIN" -c 'from paper_fetch.formula.install import TEXMATH_VERSION; print(TEXMATH_VERSION)'
  )"
  version_output="$("$texmath_bin" --version 2>&1)"
  [ "$version_output" = "Version $texmath_version" ] \
    || die "Bundled texmath version mismatch: expected $texmath_version, got ${version_output:-<empty>}."
  latex_output="$(
    printf '%s' '<math xmlns="http://www.w3.org/1998/Math/MathML"><mfrac><msub><mi>x</mi><mn>1</mn></msub><msqrt><mrow><mi>y</mi><mo>+</mo><mn>1</mn></mrow></msqrt></mfrac></math>' \
      | "$texmath_bin" -f mathml -t tex
  )"
  [ "$latex_output" = '\frac{x_{1}}{\sqrt{y + 1}}' ] \
    || die "Bundled texmath failed the complex MathML conversion smoke test."
  latex_output="$(
    printf '%s' '<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><munderover><mo>∑</mo><mi>i</mi><mi>n</mi></munderover><msup><mi>x</mi><mi>i</mi></msup></mrow></math>' \
      | "$texmath_bin" -f mathml -t tex
  )"
  [ "$latex_output" = '\sum\limits_{i}^{n}x^{i}' ] \
    || die "Bundled texmath failed the limit-style MathML conversion smoke test."

  PYTHONPATH="$staging/runtime/site-packages${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" - "$formula_tools" <<'PY'
from pathlib import Path
import sys

from paper_fetch.formula.install import stage_bundled_node_workspace

stage_bundled_node_workspace(Path(sys.argv[1]))
PY
  "$npm_bin" ci --omit=dev --silent --prefix "$formula_tools"
  # Runtime code imports the packages directly; npm's .bin launchers are unused
  # symlinks and are excluded so the offline payload remains regular-files-only.
  rm -rf "$formula_tools/node_modules/.bin"
  printf '<math><mi>x</mi></math>' \
    | "$node_bin" "$formula_tools/mathml_to_latex_cli.mjs" \
    | grep -q 'x'
}

copy_macos_library_licenses() {
  local dependency="$1"
  local formula_root="$2"
  local resolved prefix license destination
  resolved="$(
    "$PYTHON_BIN" -c \
      'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve(strict=True))' \
      "$dependency"
  )"
  prefix="$(dirname "$(dirname "$resolved")")"

  shopt -s nullglob
  local licenses=("$prefix"/COPYING* "$prefix"/LICENSE*)
  shopt -u nullglob
  [ "${#licenses[@]}" -gt 0 ] || return 0

  mkdir -p "$formula_root/licenses"
  for license in "${licenses[@]}"; do
    destination="$formula_root/licenses/$(basename "$dependency")-$(basename "$license")"
    [ -f "$destination" ] || cp "$license" "$destination"
  done
}

stage_macos_formula_library() {
  local dependency="$1"
  local formula_root="$2"
  local library_dir="$formula_root/lib"
  local name target child child_name
  name="$(basename "$dependency")"
  target="$library_dir/$name"

  [ -f "$target" ] && return 0
  [ -f "$dependency" ] || die "Missing macOS formula dependency: $dependency"
  mkdir -p "$library_dir"
  cp "$dependency" "$target"
  chmod u+w "$target"
  install_name_tool -id "@rpath/$name" "$target"
  copy_macos_library_licenses "$dependency" "$formula_root"

  while IFS= read -r child; do
    case "$child" in
      /System/*|/usr/lib/*|@loader_path/*|@executable_path/*|@rpath/*) continue ;;
      /*) ;;
      *) die "Unsupported relative Mach-O dependency in $target: $child" ;;
    esac
    stage_macos_formula_library "$child" "$formula_root"
    child_name="$(basename "$child")"
    install_name_tool -change "$child" "@loader_path/$child_name" "$target"
  done < <(otool -L "$target" | awk 'NR > 1 { print $1 }')

  codesign --force --sign - --timestamp=none "$target"
}

bundle_macos_formula_libraries() {
  local texmath="$1"
  local formula_root="$2"
  local dependency name tool

  [ "$(detect_platform)" = "macos" ] || return 0
  for tool in otool install_name_tool codesign; do
    command -v "$tool" >/dev/null 2>&1 \
      || die "$tool is required to make the macOS formula bundle relocatable."
  done

  log "Bundling relocatable macOS formula libraries"
  chmod u+w "$texmath"
  while IFS= read -r dependency; do
    case "$dependency" in
      /System/*|/usr/lib/*|@loader_path/*|@executable_path/*|@rpath/*) continue ;;
      /*) ;;
      *) die "Unsupported relative Mach-O dependency in $texmath: $dependency" ;;
    esac
    stage_macos_formula_library "$dependency" "$formula_root"
    name="$(basename "$dependency")"
    install_name_tool -change "$dependency" "@loader_path/../lib/$name" "$texmath"
  done < <(otool -L "$texmath" | awk 'NR > 1 { print $1 }')

  codesign --force --sign - --timestamp=none "$texmath"
}

bundle_image_tools() {
  local staging="$1"
  log "Bundling image conversion tools"
  mkdir -p "$staging/image-tools"
  PYTHONPATH="$staging/runtime/site-packages${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -m paper_fetch.image_tools.install \
      --target-dir "$staging/image-tools" \
      --offline-bundle \
      --repo-root "$REPO_DIR"
}

write_cmd_wrappers() {
  local staging="$1"
  local bin="$staging/bin"
  local runtime="$staging/runtime"
  log "Writing command wrappers"
  mkdir -p "$bin" "$runtime"

  cat > "$runtime/paper-fetch-python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -n "${PAPER_FETCH_OFFLINE_PYTHON_BIN:-}" ]; then
  PYTHON_BIN="$PAPER_FETCH_OFFLINE_PYTHON_BIN"
elif [ -f "$INSTALL_ROOT/runtime/python-bin" ]; then
  IFS= read -r PYTHON_BIN < "$INSTALL_ROOT/runtime/python-bin"
else
  PYTHON_BIN="python3"
fi
export PYTHONPATH="$INSTALL_ROOT/runtime/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
exec "$PYTHON_BIN" "$@"
EOF

  cat > "$bin/paper-fetch" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${PAPER_FETCH_ENV_FILE:-}" ]; then
  export PAPER_FETCH_ENV_FILE="$INSTALL_ROOT/offline.env"
fi
exec "$INSTALL_ROOT/runtime/paper-fetch-python" -X utf8 -m paper_fetch.cli "$@"
EOF

  cat > "$bin/paper-fetch-mcp" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${PAPER_FETCH_ENV_FILE:-}" ]; then
  export PAPER_FETCH_ENV_FILE="$INSTALL_ROOT/offline.env"
fi
exec "$INSTALL_ROOT/runtime/paper-fetch-python" -X utf8 -m paper_fetch.mcp.server "$@"
EOF

  cat > "$bin/paper-fetch-install-formula-tools" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$INSTALL_ROOT/runtime/paper-fetch-python" -X utf8 -m paper_fetch.formula.install "$@"
EOF

  cat > "$bin/paper-fetch-install-image-tools" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$INSTALL_ROOT/runtime/paper-fetch-python" -X utf8 -m paper_fetch.image_tools.install "$@"
EOF

  chmod +x \
    "$runtime/paper-fetch-python" \
    "$bin/paper-fetch" \
    "$bin/paper-fetch-mcp" \
    "$bin/paper-fetch-install-formula-tools" \
    "$bin/paper-fetch-install-image-tools"
}

write_offline_readme() {
  local staging="$1"
  local target_platform="$2"
  local install_line
  if [ "$target_platform" = "macos" ]; then
    install_line='Unpack the release `.tar.gz` bundle, then run `./install-offline.sh` from the unpacked directory. By default it installs to `~/.local/share/paper-fetch-skill`; pass `--install-dir <path>` to use a fixed custom directory.'
  else
    install_line='Run the release `.sh` installer directly. By default it installs to `~/.local/share/paper-fetch-skill`; pass `--install-dir <path>` to use a fixed custom directory.'
  fi
  cat > "$staging/README.offline.md" <<'EOF'
# Paper Fetch Offline Package

This package includes an installed Python runtime under `runtime/site-packages`, a private Python launcher at `runtime/paper-fetch-python`, command wrappers under `bin/`, formula tools, and image-tools configuration for optional conversion tools.
The offline build does not bundle Ghostscript/libvips from the build host PATH; AMS EPS/TIFF source figure conversion falls back to webpage JPG/PNG candidates when those tools are unavailable.
The `bin/` directory exposes paper-fetch commands only; it does not include a generic `python` wrapper.
It does not redistribute the Camoufox browser binary for browser-backed providers.
`paper-fetch` does not download that binary automatically during fetch. While
still online, run `./runtime/paper-fetch-python -m camoufox fetch` to download
the Camoufox runtime, then run `./bin/paper-fetch browser-preflight` to verify
it before moving the installation to a fully offline host.
EOF

  printf '\n%s\n\n' "$install_line" >> "$staging/README.offline.md"

  cat >> "$staging/README.offline.md" <<'EOF'
Browser-backed providers use native Camoufox.
Set `PAPER_FETCH_BROWSER_HEADLESS=false` only when running with a display-capable session.

The installer writes `PAPER_FETCH_BROWSER_HEADLESS=true` into `offline.env`. It does not override Camoufox's generated Firefox user agent or fingerprint settings.
`activate-offline.sh` parses `offline.env` with python-dotenv and exports valid key/value pairs; it does not source the file as shell code.
EOF
}

write_checksums() {
  local staging="$1"
  "$PYTHON_BIN" - "$staging" "$STAGING_OWNERSHIP_MARKER_NAME" <<'PY'
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys

staging = Path(sys.argv[1])
ownership_marker = staging / sys.argv[2]
checksum_path = staging / "sha256sums.txt"
payload_files = []
for current_root, directory_names, file_names in os.walk(
    staging,
    topdown=True,
    followlinks=False,
):
    current = Path(current_root)
    for name in directory_names:
        path = current / name
        mode = path.lstat().st_mode
        relative = path.relative_to(staging).as_posix()
        if stat.S_ISLNK(mode):
            raise SystemExit(
                f"offline payload symlink is not allowed: './{relative}'"
            )
        if not stat.S_ISDIR(mode):
            raise SystemExit(
                f"offline payload path is not a directory: './{relative}'"
            )
    for name in file_names:
        path = current / name
        mode = path.lstat().st_mode
        relative = path.relative_to(staging).as_posix()
        if stat.S_ISLNK(mode):
            raise SystemExit(
                f"offline payload symlink is not allowed: './{relative}'"
            )
        if not stat.S_ISREG(mode):
            raise SystemExit(
                f"offline payload path is not a regular file: './{relative}'"
            )
        if path != checksum_path and path != ownership_marker:
            payload_files.append(path)

lines = []
for path in sorted(payload_files):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    relative = path.relative_to(staging).as_posix()
    lines.append(f"{digest}  ./{relative}\n")
checksum_path.write_text("".join(lines), encoding="utf-8")
PY
}

write_manifest_and_checksums() {
  local staging="$1"
  local version="$2"
  local target_platform="$3"
  local target_arch="$4"
  local python_tag="$5"
  local minimum_os_version="$6"
  local git_revision skill_name skill_bundle_json
  git_revision="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || true)"
  skill_name="$(installer_manifest_value skill.name)"
  skill_bundle_json="$(
    "$PYTHON_BIN" "$REPO_DIR/src/paper_fetch/skill_integrity.py" build \
      --skill-dir "$staging/skills/$skill_name" \
      --name "$skill_name" \
      --root "skills/$skill_name"
  )"

  log "Writing manifest and checksums"
  "$PYTHON_BIN" - "$staging" "$version" "$git_revision" "$target_platform" "$target_arch" "$python_tag" "$minimum_os_version" "$INSTALLER_MANIFEST_FILE" "$skill_bundle_json" "$PAPER_FETCH_OFFLINE_TOOLING_REVISION" "$CAMOUFOX_PYTHON_PACKAGE_VERSION" <<'PY'
from __future__ import annotations

from importlib.metadata import distributions
import json
import os
from pathlib import Path
import sys
from datetime import UTC, datetime

staging = Path(sys.argv[1])
version = sys.argv[2]
git_revision = sys.argv[3] or None
target_platform = sys.argv[4]
target_arch = sys.argv[5]
python_tag = sys.argv[6]
minimum_os_version = sys.argv[7] or None
installer_manifest = json.loads(Path(sys.argv[8]).read_text(encoding="utf-8"))
skill_bundle = json.loads(sys.argv[9])
tooling_revision = sys.argv[10] or None
expected_camoufox_version = sys.argv[11]
site_packages = staging / "runtime" / "site-packages"
installed_packages = sorted(path.name for path in site_packages.glob("*.dist-info"))
camoufox_distributions = [
    distribution
    for distribution in distributions(path=[str(site_packages)])
    if str(distribution.metadata.get("Name") or "").casefold() == "camoufox"
]
if len(camoufox_distributions) != 1:
    raise SystemExit(
        "Offline manifest requires exactly one installed Camoufox distribution; "
        f"found {len(camoufox_distributions)}"
    )
camoufox_version = camoufox_distributions[0].version
if camoufox_version != expected_camoufox_version:
    raise SystemExit(
        f"Offline manifest requires Camoufox {expected_camoufox_version}; "
        f"found {camoufox_version or '<missing>'}"
    )
manifest_name_key = f"{target_platform}_manifest_name"

payload = {
    "schema_version": 3,
    "name": installer_manifest["packages"][manifest_name_key],
    "project": installer_manifest["project"],
    "version": version,
    "built_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "git_revision": git_revision,
    **(
        {"tooling_revision": tooling_revision}
        if tooling_revision is not None
        else {}
    ),
    "target": {
        "platform": target_platform,
        "arch": target_arch,
        "python_tag": python_tag,
        **(
            {"minimum_os_version": minimum_os_version}
            if minimum_os_version is not None
            else {}
        ),
    },
    "entrypoint": "install-offline.sh",
    "skill_bundle": skill_bundle,
    "components": {
        "python_runtime": "runtime/site-packages",
        "command_wrappers": "bin",
        "installed_package_count": len(installed_packages),
        "installer_manifest": "installer/manifest.json",
        "formula_tools": "formula-tools",
        "image_tools": "image-tools",
        "camoufox": {
            "python_package": "runtime/site-packages",
            "python_package_version": camoufox_version,
            "browser_binary": "not_bundled",
        },
    },
}

(staging / "offline-manifest.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + os.linesep,
    encoding="utf-8",
)

PY

  write_checksums "$staging"
}

create_self_extracting_installer() (
  local staging_parent="$1"
  local package_name="$2"
  local output_dir="$3"
  local output_path
  temporary_output=""
  temporary_payload=""

  cleanup_release_temporaries() {
    [ -z "$temporary_output" ] || rm -f "$temporary_output"
    [ -z "$temporary_payload" ] || rm -f "$temporary_payload"
  }
  trap cleanup_release_temporaries EXIT
  trap 'exit 1' HUP INT TERM

  mkdir -p "$output_dir"
  output_path="$output_dir/$package_name.sh"
  temporary_output="$(mktemp "$output_dir/.$package_name.installer.XXXXXX")"
  temporary_payload="$(mktemp "$output_dir/.$package_name.payload.XXXXXX")"

  log "Creating self-extracting shell installer"
  tar \
    --exclude="$package_name/$STAGING_OWNERSHIP_MARKER_NAME" \
    -C "$staging_parent" \
    -czf "$temporary_payload" \
    "$package_name"
  cat > "$temporary_output" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

marker="__PAPER_FETCH_OFFLINE_PAYLOAD_BELOW__"
archive_line="$(awk -v marker="$marker" '$0 == marker { print NR + 1; found = 1; exit } END { if (!found) exit 1 }' "$0")" || {
  printf 'Could not locate embedded offline payload.\n' >&2
  exit 1
}

tmp_root="$(mktemp -d "${TMPDIR:-/tmp}/paper-fetch-offline.XXXXXX")"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

tail -n +"$archive_line" "$0" | tar -xzf - -C "$tmp_root"
payload_root="$tmp_root/__PACKAGE_NAME__"
if [ ! -x "$payload_root/install-offline.sh" ]; then
  printf 'Embedded offline payload is missing install-offline.sh.\n' >&2
  exit 1
fi

set +e
"$payload_root/install-offline.sh" "$@"
status=$?
set -e
exit "$status"
__PAPER_FETCH_OFFLINE_PAYLOAD_BELOW__
EOF
  "$PYTHON_BIN" - "$temporary_output" "$package_name" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
package_name = sys.argv[2]
path.write_text(path.read_text(encoding="utf-8").replace("__PACKAGE_NAME__", package_name), encoding="utf-8")
PY
  cat "$temporary_payload" >> "$temporary_output"
  chmod 0755 "$temporary_output"
  [ ! -d "$output_path" ] \
    || die "Offline installer output path must not be a directory: $output_path"
  rm -f "$temporary_payload"
  temporary_payload=""
  printf '%s\n' "$output_path"
  "$PYTHON_BIN" -c \
    'import os, sys; os.replace(sys.argv[1], sys.argv[2])' \
    "$temporary_output" \
    "$output_path"
)

create_archive() (
  local staging_parent="$1"
  local package_name="$2"
  local output_dir="$3"
  local output_path
  temporary_output=""

  cleanup_release_temporaries() {
    [ -z "$temporary_output" ] || rm -f "$temporary_output"
  }
  trap cleanup_release_temporaries EXIT
  trap 'exit 1' HUP INT TERM

  mkdir -p "$output_dir"
  output_path="$output_dir/$package_name.tar.gz"
  temporary_output="$(mktemp "$output_dir/.$package_name.archive.XXXXXX")"

  log "Creating macOS tar.gz archive"
  COPYFILE_DISABLE=1 tar \
    --exclude="$package_name/$STAGING_OWNERSHIP_MARKER_NAME" \
    -C "$staging_parent" \
    -czf "$temporary_output" \
    "$package_name"
  chmod 0644 "$temporary_output"
  [ ! -d "$output_path" ] \
    || die "Offline archive output path must not be a directory: $output_path"
  printf '%s\n' "$output_path"
  "$PYTHON_BIN" -c \
    'import os, sys; os.replace(sys.argv[1], sys.argv[2])' \
    "$temporary_output" \
    "$output_path"
)

main() {
  local package_name package_prefix target_info target_platform target_arch python_tag
  local target_minimum_os_version staging version

  [ -f "$INSTALLER_MANIFEST_FILE" ] || die "Missing installer manifest: $INSTALLER_MANIFEST_FILE"
  BUILD_DIR="$(canonical_path "$BUILD_DIR")" \
    || die "Could not canonicalize offline build directory: $BUILD_DIR"
  OUTPUT_DIR="$(canonical_path "$OUTPUT_DIR")" \
    || die "Could not canonicalize offline output directory: $OUTPUT_DIR"
  validate_build_directory "$BUILD_DIR"
  if [ -e "$BUILD_DIR" ] && [ ! -d "$BUILD_DIR" ]; then
    die "Offline build path exists but is not a directory: $BUILD_DIR"
  fi
  if [ -e "$OUTPUT_DIR" ] && [ ! -d "$OUTPUT_DIR" ]; then
    die "Offline output path exists but is not a directory: $OUTPUT_DIR"
  fi
  mkdir -p "$BUILD_DIR"

  target_info="$(check_target)"
  read -r target_platform target_arch python_tag target_minimum_os_version <<< "$target_info"
  if [ "$target_platform" = "macos" ]; then
    export MACOSX_DEPLOYMENT_TARGET="$target_minimum_os_version"
  fi
  case "$target_platform" in
    linux)
      package_prefix="$(installer_manifest_value packages.linux_offline_name_prefix)"
      package_name="${PACKAGE_NAME:-$package_prefix-$python_tag}"
      ;;
    macos)
      package_prefix="$(installer_manifest_value packages.macos_offline_name_prefix)"
      package_name="${PACKAGE_NAME:-$package_prefix-$target_arch-$python_tag}"
      ;;
    *)
      die "Unsupported offline package target: $target_platform"
      ;;
  esac
  validate_package_name "$package_name"
  staging="$(prepare_owned_staging "$BUILD_DIR/$package_name" "$package_name")"
  if path_is_same_or_ancestor "$staging" "$OUTPUT_DIR"; then
    die "Offline output directory must not equal or be inside staging: $OUTPUT_DIR"
  fi
  version="$(project_version)"
  CAMOUFOX_PYTHON_PACKAGE_VERSION="$(locked_camoufox_version)" \
    || die "Could not resolve the locked Camoufox package version from uv.lock."

  copy_runtime_assets "$staging"
  build_project_runtime "$staging" "$package_name"
  sign_macos_playwright_node "$staging" "$target_platform"
  bundle_formula_tools "$staging"
  bundle_image_tools "$staging"
  write_cmd_wrappers "$staging"
  write_offline_readme "$staging" "$target_platform"
  write_manifest_and_checksums \
    "$staging" \
    "$version" \
    "$target_platform" \
    "$target_arch" \
    "$python_tag" \
    "$target_minimum_os_version"
  if [ "$target_platform" = "macos" ]; then
    create_archive "$BUILD_DIR" "$package_name" "$OUTPUT_DIR"
  else
    create_self_extracting_installer "$BUILD_DIR" "$package_name" "$OUTPUT_DIR"
  fi
}

main "$@"
