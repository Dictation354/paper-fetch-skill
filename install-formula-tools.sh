#!/usr/bin/env bash
# Install formula conversion backends for paper-fetch-skill.
#
# Preferred order:
#   1. texmath (compiled locally via cabal or stack, or reused from PATH)
#   2. mathml-to-latex (Node fallback)
#   3. built-in Python MathML renderer

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PAPER_FETCH_INSTALL_PYTHON_BIN:-${PYTHON_BIN:-python3}}"
RUN_FLARESOLVERR_SETUP="true"
RUN_PLAYWRIGHT_INSTALL="true"
FORWARDED_ARGS=()

while (($#)); do
  case "$1" in
    --skip-flaresolverr-setup)
      RUN_FLARESOLVERR_SETUP="false"
      ;;
    --skip-playwright-install)
      RUN_PLAYWRIGHT_INSTALL="false"
      ;;
    *)
      FORWARDED_ARGS+=("$1")
      ;;
  esac
  shift
done

if [[ "${RUN_FLARESOLVERR_SETUP}" == "true" ]]; then
  if [[ ! -x "${REPO_DIR}/vendor/flaresolverr/setup_flaresolverr_source.sh" ]]; then
    echo "Missing repo-local FlareSolverr setup script under vendor/flaresolverr." >&2
    exit 1
  fi
  if grep -q 'HEADLESS="true"' "${REPO_DIR}/vendor/flaresolverr/.env.flaresolverr-source-headless" 2>/dev/null; then
    if ! command -v Xvfb >/dev/null 2>&1; then
      echo "Warning: Xvfb was not found. Headless FlareSolverr preset requires the xvfb package." >&2
    fi
  fi
  PYTHON_BIN="${PYTHON_BIN}" bash "${REPO_DIR}/vendor/flaresolverr/setup_flaresolverr_source.sh"
fi

if [[ "${RUN_PLAYWRIGHT_INSTALL}" == "true" ]]; then
  "${PYTHON_BIN}" -m playwright install chromium
fi

PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
  "${PYTHON_BIN}" -m paper_fetch.formula.install --target-dir "$REPO_DIR/.formula-tools" "${FORWARDED_ARGS[@]}"
