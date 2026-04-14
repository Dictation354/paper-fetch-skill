#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.flaresolverr-source-headless}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/flaresolverr_source_common.sh"
flaresolverr_source_load_env "${ENV_FILE}"

if [[ ! -d "${FLARESOLVERR_REPO_DIR}/.git" ]]; then
  echo "Missing repo clone: ${FLARESOLVERR_REPO_DIR}" >&2
  exit 1
fi

if [[ ! -d "${FLARESOLVERR_VENV_DIR}" ]]; then
  echo "Missing virtualenv: ${FLARESOLVERR_VENV_DIR}" >&2
  exit 1
fi

if [[ ! -x "${FLARESOLVERR_CHROME_DIR}/chrome" ]]; then
  echo "Missing bundled Chrome: ${FLARESOLVERR_CHROME_DIR}/chrome" >&2
  exit 1
fi

if [[ "${HEADLESS}" == "true" ]]; then
  if ! command -v Xvfb >/dev/null 2>&1; then
    echo "Xvfb is required when HEADLESS=true." >&2
    exit 1
  fi
  x11_unix_opts="$(findmnt -n -o OPTIONS /tmp/.X11-unix 2>/dev/null || true)"
  if [[ "${x11_unix_opts}" == *"ro"* ]]; then
    echo "/tmp/.X11-unix is mounted read-only on this host, so official Xvfb mode cannot create a new X socket." >&2
    echo "On WSLg, use the official WSLg environment file instead:" >&2
    echo "  bash ${ROOT_DIR}/run_flaresolverr_source.sh ${ROOT_DIR}/.env.flaresolverr-source-wslg" >&2
    exit 1
  fi
fi

tracked_changes="$(git -C "${FLARESOLVERR_REPO_DIR}" status --porcelain --untracked-files=no)"
if [[ -n "${tracked_changes}" ]]; then
  echo "Tracked source changes detected; rerun setup_flaresolverr_source.sh to restore official source mode." >&2
  printf '%s\n' "${tracked_changes}" >&2
  exit 1
fi

flaresolverr_source_ensure_chrome_link

source "${FLARESOLVERR_VENV_DIR}/bin/activate"
export LOG_LEVEL
export HEADLESS
export TZ
export HOST="${FLARESOLVERR_HOST}"
export PORT="${FLARESOLVERR_PORT}"

cd "${FLARESOLVERR_REPO_DIR}"
python -u "${FLARESOLVERR_REPO_DIR}/src/flaresolverr.py"
