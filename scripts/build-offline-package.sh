#!/usr/bin/env bash
# Build the Linux x86_64 CPython 3.11 offline tarball.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${PAPER_FETCH_OFFLINE_BUILD_DIR:-$REPO_DIR/.offline-build}"
OUTPUT_DIR="$REPO_DIR/dist"
PACKAGE_NAME="paper-fetch-skill-offline-linux-x86_64-cp311"
PYTHON_BIN="${PYTHON_BIN:-python3}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/build-offline-package.sh [--output-dir <path>] [--package-name <name>]

Builds a Linux x86_64 CPython 3.11 tar.gz bundle containing:
  - source snapshot
  - project wheel and Python dependency wheelhouse
  - Playwright Chromium under ms-playwright/
  - texmath under formula-tools/
  - patched FlareSolverr source snapshot, Chrome bundle, and wheelhouse
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

check_target() {
  [ "$(uname -s)" = "Linux" ] || die "Offline package build currently targets Linux only."
  case "$(uname -m)" in
    x86_64|amd64) ;;
    *) die "Offline package build currently targets x86_64 only." ;;
  esac
  "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)' \
    || die "Offline package build requires CPython 3.11.x."
}

project_version() {
  "$PYTHON_BIN" -c 'import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])' "$REPO_DIR/pyproject.toml"
}

copy_source_snapshot() {
  local staging="$1"
  log "Copying source snapshot"
  mkdir -p "$staging"
  tar \
    --exclude='./.git' \
    --exclude='./.venv' \
    --exclude='./.offline-build' \
    --exclude='./.formula-tools' \
    --exclude='./.pytest_cache' \
    --exclude='./.ruff_cache' \
    --exclude='./build' \
    --exclude='./dist' \
    --exclude='./live-downloads' \
    --exclude='./**/__pycache__' \
    --exclude='./*.egg-info' \
    --exclude='./vendor/flaresolverr/.work' \
    --exclude='./vendor/flaresolverr/.venv-flaresolverr' \
    --exclude='./vendor/flaresolverr/.flaresolverr' \
    --exclude='./vendor/flaresolverr/run_logs' \
    --exclude='./vendor/flaresolverr/probe_outputs' \
    -C "$REPO_DIR" -cf - . | tar -C "$staging" -xf -
}

build_project_wheelhouse() {
  local staging="$1"
  local project_dist="$BUILD_DIR/project-dist"
  local wheelhouse="$staging/wheelhouse"
  rm -rf "$project_dist"
  mkdir -p "$project_dist" "$wheelhouse" "$staging/dist"

  log "Building project wheel"
  "$PYTHON_BIN" -m pip wheel --no-deps --wheel-dir "$project_dist" "$REPO_DIR"

  shopt -s nullglob
  local wheels=("$project_dist"/paper_fetch_skill-*.whl)
  shopt -u nullglob
  [ "${#wheels[@]}" -eq 1 ] || die "Expected one built project wheel, found ${#wheels[@]}."
  cp "${wheels[0]}" "$staging/dist/"

  log "Downloading project dependency wheelhouse"
  "$PYTHON_BIN" -m pip download \
    --dest "$wheelhouse" \
    --only-binary=:all: \
    "${wheels[0]}"
}

create_build_venv() {
  local staging="$1"
  local build_venv="$BUILD_DIR/build-venv"
  rm -rf "$build_venv"
  "$PYTHON_BIN" -m venv "$build_venv"
  "$build_venv/bin/python" -m pip install --quiet --upgrade pip >&2
  "$build_venv/bin/python" -m pip install \
    --no-index \
    --find-links "$staging/wheelhouse" \
    "$staging"/dist/paper_fetch_skill-*.whl >&2
  printf '%s\n' "$build_venv/bin/python"
}

bundle_formula_tools() {
  local staging="$1"
  local build_python="$2"
  log "Bundling formula tools"
  "$build_python" -m paper_fetch.formula.install --target-dir "$staging/formula-tools" --no-node
  "$staging/formula-tools/bin/texmath" --help >/dev/null
  "$build_python" - "$staging/formula-tools" <<'PY'
from pathlib import Path
import sys

from paper_fetch.formula.install import stage_bundled_node_workspace

stage_bundled_node_workspace(Path(sys.argv[1]))
PY
}

bundle_playwright() {
  local staging="$1"
  local build_python="$2"
  log "Bundling Playwright Chromium"
  PLAYWRIGHT_BROWSERS_PATH="$staging/ms-playwright" "$build_python" -m playwright install chromium
}

prepare_flaresolverr() {
  local staging="$1"
  local build_python="$2"
  local flaresolverr_build="$BUILD_DIR/flaresolverr-build"
  local flare_env="$BUILD_DIR/flaresolverr-build.env"
  local flare_repo="$flaresolverr_build/FlareSolverr"
  local flare_downloads="$flaresolverr_build/downloads"
  local flare_version="v3.4.6"

  rm -rf "$flaresolverr_build"
  mkdir -p "$flaresolverr_build"
  cat > "$flare_env" <<EOF
FLARESOLVERR_REPO_DIR="$flare_repo"
FLARESOLVERR_VENV_DIR="$flaresolverr_build/.venv-flaresolverr"
FLARESOLVERR_DOWNLOAD_DIR="$flare_downloads"
FLARESOLVERR_RELEASE_VERSION="$flare_version"
FLARESOLVERR_HOST="127.0.0.1"
FLARESOLVERR_PORT="8191"
LOG_LEVEL="info"
HEADLESS="true"
TZ="Asia/Shanghai"
STARTUP_WAIT_SECONDS="30"
FLARESOLVERR_LOG_FILE="$flaresolverr_build/flaresolverr-source.log"
FLARESOLVERR_PID_FILE="$flaresolverr_build/flaresolverr-source.pid"
PROBE_OUTPUT_ROOT="$flaresolverr_build/probe_outputs"
EOF

  log "Preparing patched FlareSolverr source"
  PYTHON_BIN="$build_python" bash "$REPO_DIR/vendor/flaresolverr/setup_flaresolverr_source.sh" "$flare_env"

  git -C "$flare_repo" diff --check HEAD~1..HEAD
  grep -q "returnImagePayload" "$flare_repo/src/dtos.py"
  grep -q "imagePayload" "$flare_repo/src/flaresolverr_service.py"

  log "Bundling FlareSolverr dependency wheelhouse"
  mkdir -p "$staging/vendor/flaresolverr/wheelhouse"
  "$PYTHON_BIN" -m pip download \
    --dest "$staging/vendor/flaresolverr/wheelhouse" \
    --only-binary=:all: \
    -r "$flare_repo/requirements.txt"

  log "Copying patched FlareSolverr source snapshot"
  rm -rf "$staging/vendor/flaresolverr/.work" "$staging/vendor/flaresolverr/.flaresolverr"
  mkdir -p "$staging/vendor/flaresolverr/.work/FlareSolverr"
  tar --exclude='./.git' -C "$flare_repo" -cf - . \
    | tar -C "$staging/vendor/flaresolverr/.work/FlareSolverr" -xf -

  mkdir -p "$staging/vendor/flaresolverr/.flaresolverr/$flare_version"
  tar -C "$flare_downloads/$flare_version" -cf - . \
    | tar -C "$staging/vendor/flaresolverr/.flaresolverr/$flare_version" -xf -
}

write_manifest_and_checksums() {
  local staging="$1"
  local version="$2"
  local git_revision
  git_revision="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || true)"

  log "Writing manifest and checksums"
  "$PYTHON_BIN" - "$staging" "$version" "$git_revision" <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from datetime import UTC, datetime

staging = Path(sys.argv[1])
version = sys.argv[2]
git_revision = sys.argv[3] or None

project_wheels = sorted(path.name for path in (staging / "dist").glob("paper_fetch_skill-*.whl"))
wheelhouse = sorted(path.name for path in (staging / "wheelhouse").glob("*.whl"))
flaresolverr_wheelhouse = sorted(path.name for path in (staging / "vendor/flaresolverr/wheelhouse").glob("*.whl"))

payload = {
    "schema_version": 1,
    "name": "paper-fetch-skill-offline",
    "project": "paper-fetch-skill",
    "version": version,
    "built_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "git_revision": git_revision,
    "target": {
        "platform": "linux",
        "arch": "x86_64",
        "python_tag": "cp311",
    },
    "entrypoint": "install-offline.sh",
    "components": {
        "source_snapshot": ".",
        "project_wheels": [f"dist/{name}" for name in project_wheels],
        "wheelhouse_count": len(wheelhouse),
        "playwright_browsers": "ms-playwright",
        "formula_tools": "formula-tools",
        "flaresolverr": {
            "source_snapshot": "vendor/flaresolverr/.work/FlareSolverr",
            "release_version": "v3.4.6",
            "browser_bundle": "vendor/flaresolverr/.flaresolverr/v3.4.6/flaresolverr/_internal/chrome",
            "wheelhouse_count": len(flaresolverr_wheelhouse),
            "patch": "return-image-payload",
        },
    },
}

(staging / "offline-manifest.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + os.linesep,
    encoding="utf-8",
)
PY

  (
    cd "$staging"
    find . -type f ! -name sha256sums.txt -print0 \
      | sort -z \
      | xargs -0 sha256sum > sha256sums.txt
  )
}

create_archive() {
  local staging_parent="$1"
  local package_name="$2"
  local output_dir="$3"
  mkdir -p "$output_dir"
  log "Creating tar.gz archive"
  tar -C "$staging_parent" -czf "$output_dir/$package_name.tar.gz" "$package_name"
  printf '%s\n' "$output_dir/$package_name.tar.gz"
}

main() {
  local staging="$BUILD_DIR/$PACKAGE_NAME"
  local version build_python

  check_target
  version="$(project_version)"
  rm -rf "$staging"
  mkdir -p "$BUILD_DIR"

  copy_source_snapshot "$staging"
  build_project_wheelhouse "$staging"
  build_python="$(create_build_venv "$staging")"
  bundle_formula_tools "$staging" "$build_python"
  bundle_playwright "$staging" "$build_python"
  prepare_flaresolverr "$staging" "$build_python"
  write_manifest_and_checksums "$staging" "$version"
  create_archive "$BUILD_DIR" "$PACKAGE_NAME" "$OUTPUT_DIR"
}

main "$@"
