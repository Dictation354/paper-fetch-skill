#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.flaresolverr-source-headless}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/flaresolverr_source_common.sh"
flaresolverr_source_load_env "${ENV_FILE}"

pid=""
if [[ -f "${FLARESOLVERR_PID_FILE}" ]]; then
  pid="$(cat "${FLARESOLVERR_PID_FILE}")"
fi

if [[ -z "${pid}" ]]; then
  pid="$(flaresolverr_source_find_listener_pid || true)"
fi

if [[ -z "${pid}" ]]; then
  rm -f "${FLARESOLVERR_PID_FILE}"
  echo "No running FlareSolverr process found."
  exit 0
fi

if kill -0 "${pid}" 2>/dev/null; then
  pkill -TERM -P "${pid}" 2>/dev/null || true
  kill "${pid}"
  for _ in $(seq 1 30); do
    if ! kill -0 "${pid}" 2>/dev/null; then
      rm -f "${FLARESOLVERR_PID_FILE}"
      echo "Stopped FlareSolverr PID ${pid}"
      exit 0
    fi
    sleep 1
  done
  echo "FlareSolverr PID ${pid} did not exit after 30 seconds." >&2
  exit 1
fi

rm -f "${FLARESOLVERR_PID_FILE}"
echo "Removed stale PID file."
