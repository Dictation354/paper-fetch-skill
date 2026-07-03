#!/usr/bin/env bash
# Build Linux x86_64 self-extracting installers and macOS runtime tarballs.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${PAPER_FETCH_OFFLINE_BUILD_DIR:-$REPO_DIR/.offline-build}"
OUTPUT_DIR="$REPO_DIR/dist"
PACKAGE_NAME=""
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALLER_MANIFEST_FILE="$REPO_DIR/installer/manifest.json"

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
  - cloakbrowser Python package, which downloads/locates the Chrome binary on first browser-backed use
Linux builds produce a self-extracting .sh installer. macOS builds produce a .tar.gz bundle.
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

if sys.implementation.name != "cpython":
    raise SystemExit(1)

print(f"cp{sys.version_info.major}{sys.version_info.minor}")
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
  local platform arch python_tag
  platform="$(detect_platform)" || die "Offline package build supports Linux and macOS only."
  arch="$(detect_arch)" || die "Offline package build supports x86_64 and arm64 only."
  case "$platform:$arch" in
    linux:x86_64|macos:x86_64|macos:arm64) ;;
    linux:arm64) die "Offline package build currently targets Linux x86_64 only." ;;
    *) die "Unsupported offline package target: $platform/$arch." ;;
  esac
  python_tag="$(detect_python_tag)" \
    || die "Offline package build requires CPython 3.11, 3.12, 3.13, or 3.14."
  is_supported_python_tag "$python_tag" \
    || die "Offline package build requires CPython 3.11, 3.12, 3.13, or 3.14; detected $python_tag."
  printf '%s %s %s\n' "$platform" "$arch" "$python_tag"
}

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
  local project_dist="$BUILD_DIR/project-dist"
  local wheelhouse="$BUILD_DIR/linux-runtime-wheelhouse"
  local site_packages="$staging/runtime/site-packages"
  rm -rf "$project_dist" "$wheelhouse" "$site_packages"
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
    "${wheels[0]}"

  shopt -s nullglob
  local cloakbrowser_wheels=("$wheelhouse"/cloakbrowser-*.whl)
  shopt -u nullglob
  [ "${#cloakbrowser_wheels[@]}" -gt 0 ] || die "Dependency wheelhouse is missing cloakbrowser-*.whl."

  log "Installing project runtime into package"
  PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
  "$PYTHON_BIN" -m pip install \
    --target "$site_packages" \
    --no-index \
    --find-links "$wheelhouse" \
    --only-binary=:all: \
    "${wheels[0]}"

  log "Precompiling Python runtime bytecode"
  "$PYTHON_BIN" -m compileall -q "$site_packages"

  PYTHONPATH="$site_packages${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -X utf8 -c 'import cloakbrowser; import playwright; import paper_fetch; import paper_fetch.mcp.server; from paper_fetch.runtime_browser import BrowserContextManager; assert hasattr(cloakbrowser, "ensure_binary"); assert BrowserContextManager is not None'
}

bundle_formula_tools() {
  local staging="$1"
  log "Bundling formula tools"
  PYTHONPATH="$staging/runtime/site-packages${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -m paper_fetch.formula.install --target-dir "$staging/formula-tools" --no-node
  "$staging/formula-tools/bin/texmath" --help >/dev/null
  PYTHONPATH="$staging/runtime/site-packages${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" - "$staging/formula-tools" <<'PY'
from pathlib import Path
import sys

from paper_fetch.formula.install import stage_bundled_node_workspace

stage_bundled_node_workspace(Path(sys.argv[1]))
PY
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
It does not redistribute a browser binary for browser-backed providers; cloakbrowser downloads or locates Chrome on first use.
EOF

  printf '\n%s\n\n' "$install_line" >> "$staging/README.offline.md"

  cat >> "$staging/README.offline.md" <<'EOF'
Browser-backed providers auto-start a managed cloakbrowser Chrome when `CLOAKBROWSER_CDP_ENDPOINT` is unset.
Set `CLOAKBROWSER_CDP_ENDPOINT` only when you want to reuse an already-running browser, or set `CLOAKBROWSER_BINARY_PATH` to use a preinstalled Chrome binary.
Set `CLOAKBROWSER_HEADLESS=false` only when running with a display-capable session.

The installer writes `CLOAKBROWSER_HEADLESS=true` and `PAPER_FETCH_BROWSER_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"` into `offline.env` by default for browser-backed publisher fetches.
`activate-offline.sh` parses `offline.env` with python-dotenv and exports valid key/value pairs; it does not source the file as shell code.
EOF
}

write_checksums() {
  local staging="$1"
  "$PYTHON_BIN" - "$staging" <<'PY'
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

staging = Path(sys.argv[1])
lines = []
for path in sorted(item for item in staging.rglob("*") if item.is_file() and item.name != "sha256sums.txt"):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    relative = path.relative_to(staging).as_posix()
    lines.append(f"{digest}  ./{relative}\n")
(staging / "sha256sums.txt").write_text("".join(lines), encoding="utf-8")
PY
}

write_manifest_and_checksums() {
  local staging="$1"
  local version="$2"
  local target_platform="$3"
  local target_arch="$4"
  local python_tag="$5"
  local git_revision
  git_revision="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || true)"

  log "Writing manifest and checksums"
  "$PYTHON_BIN" - "$staging" "$version" "$git_revision" "$target_platform" "$target_arch" "$python_tag" "$INSTALLER_MANIFEST_FILE" <<'PY'
from __future__ import annotations

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
installer_manifest = json.loads(Path(sys.argv[7]).read_text(encoding="utf-8"))
site_packages = staging / "runtime" / "site-packages"
installed_packages = sorted(path.name for path in site_packages.glob("*.dist-info"))
manifest_name_key = f"{target_platform}_manifest_name"

payload = {
    "schema_version": 2,
    "name": installer_manifest["packages"][manifest_name_key],
    "project": installer_manifest["project"],
    "version": version,
    "built_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "git_revision": git_revision,
    "target": {
        "platform": target_platform,
        "arch": target_arch,
        "python_tag": python_tag,
    },
    "entrypoint": "install-offline.sh",
    "components": {
        "python_runtime": "runtime/site-packages",
        "command_wrappers": "bin",
        "installed_package_count": len(installed_packages),
        "installer_manifest": "installer/manifest.json",
        "formula_tools": "formula-tools",
        "image_tools": "image-tools",
        "cloakbrowser": {
            "python_package": "runtime/site-packages",
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

create_self_extracting_installer() {
  local staging_parent="$1"
  local package_name="$2"
  local output_dir="$3"
  local output_path payload_path
  mkdir -p "$output_dir"
  output_path="$output_dir/$package_name.sh"
  payload_path="$BUILD_DIR/$package_name.payload.tar.gz"
  rm -f "$output_path" "$payload_path"

  log "Creating self-extracting shell installer"
  tar -C "$staging_parent" -czf "$payload_path" "$package_name"
  cat > "$output_path" <<'EOF'
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

exec "$payload_root/install-offline.sh" "$@"
__PAPER_FETCH_OFFLINE_PAYLOAD_BELOW__
EOF
  "$PYTHON_BIN" - "$output_path" "$package_name" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
package_name = sys.argv[2]
path.write_text(path.read_text(encoding="utf-8").replace("__PACKAGE_NAME__", package_name), encoding="utf-8")
PY
  cat "$payload_path" >> "$output_path"
  chmod +x "$output_path"
  rm -f "$payload_path"
  printf '%s\n' "$output_path"
}

create_archive() {
  local staging_parent="$1"
  local package_name="$2"
  local output_dir="$3"
  local output_path
  mkdir -p "$output_dir"
  output_path="$output_dir/$package_name.tar.gz"
  rm -f "$output_path"

  log "Creating macOS tar.gz archive"
  tar -C "$staging_parent" -czf "$output_path" "$package_name"
  printf '%s\n' "$output_path"
}

main() {
  local package_name package_prefix target_info target_platform target_arch python_tag staging version

  [ -f "$INSTALLER_MANIFEST_FILE" ] || die "Missing installer manifest: $INSTALLER_MANIFEST_FILE"
  target_info="$(check_target)"
  read -r target_platform target_arch python_tag <<< "$target_info"
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
  staging="$BUILD_DIR/$package_name"
  version="$(project_version)"
  rm -rf "$staging"
  mkdir -p "$BUILD_DIR"

  mkdir -p "$staging"
  copy_runtime_assets "$staging"
  build_project_runtime "$staging"
  bundle_formula_tools "$staging"
  bundle_image_tools "$staging"
  write_cmd_wrappers "$staging"
  write_offline_readme "$staging" "$target_platform"
  write_manifest_and_checksums "$staging" "$version" "$target_platform" "$target_arch" "$python_tag"
  if [ "$target_platform" = "macos" ]; then
    create_archive "$BUILD_DIR" "$package_name" "$OUTPUT_DIR"
  else
    create_self_extracting_installer "$BUILD_DIR" "$package_name" "$OUTPUT_DIR"
  fi
}

main "$@"
