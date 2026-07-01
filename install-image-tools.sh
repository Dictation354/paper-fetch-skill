#!/usr/bin/env bash
# Install image conversion backends for paper-fetch-skill.
#
# Preferred order:
#   1. Ghostscript for EPS Download Figure conversion
#   2. libvips for TIFF Download Figure conversion

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PAPER_FETCH_INSTALL_PYTHON_BIN:-${PYTHON_BIN:-python3}}"

PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
  "${PYTHON_BIN}" -m paper_fetch.image_tools.install --target-dir "$REPO_DIR/.image-tools" "$@"
