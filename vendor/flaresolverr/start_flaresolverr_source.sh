#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.flaresolverr-source-headless}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/flaresolverr_source_common.sh"
flaresolverr_source_load_env "${ENV_FILE}"

mkdir -p "$(dirname "${FLARESOLVERR_LOG_FILE}")"

probe_service() {
  flaresolverr_source_probe_direct "${FLARESOLVERR_SERVICE_URL}" >/dev/null 2>&1
}

write_listener_pid() {
  local listener_pid=""
  listener_pid="$(flaresolverr_source_find_listener_pid || true)"
  if [[ -n "${listener_pid}" ]]; then
    echo "${listener_pid}" > "${FLARESOLVERR_PID_FILE}"
  fi
}

launch_detached() {
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" < /dev/null &
  else
    nohup "$@" < /dev/null &
  fi
}

if probe_service; then
  write_listener_pid
  echo "FlareSolverr is already reachable at ${FLARESOLVERR_SERVICE_URL}"
  exit 0
fi

rm -f "${FLARESOLVERR_PID_FILE}"
if [[ "${HEADLESS}" == "false" ]]; then
  if ! command -v script >/dev/null 2>&1; then
    echo "'script' is required to keep a PTY attached when HEADLESS=false." >&2
    exit 1
  fi
  launch_command="$(printf '%q ' "${ROOT_DIR}/run_flaresolverr_source.sh" "${ENV_FILE}")"
  launch_detached script -qefc "${launch_command% }" /dev/null \
    >"${FLARESOLVERR_LOG_FILE}" 2>&1
else
  launch_detached "${ROOT_DIR}/run_flaresolverr_source.sh" "${ENV_FILE}" \
    >"${FLARESOLVERR_LOG_FILE}" 2>&1
fi
echo "$!" > "${FLARESOLVERR_PID_FILE}"

for ((i = 0; i < STARTUP_WAIT_SECONDS; i++)); do
  sleep 1
  if probe_service; then
    write_listener_pid
    echo "FlareSolverr started at ${FLARESOLVERR_SERVICE_URL}"
    echo "PID: $(cat "${FLARESOLVERR_PID_FILE}")"
    exit 0
  fi
done

echo "FlareSolverr failed to start. Recent log output:" >&2
tail -n 40 "${FLARESOLVERR_LOG_FILE}" >&2 || true
exit 1
