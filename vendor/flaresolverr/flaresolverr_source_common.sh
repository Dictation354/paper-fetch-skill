#!/usr/bin/env bash

flaresolverr_source_trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

flaresolverr_source_strip_quotes() {
  local value="$1"
  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

flaresolverr_source_load_env() {
  local env_file="$1"
  local raw_line line key value

  FLARESOLVERR_ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  FLARESOLVERR_ENV_FILE="${env_file}"
  FLARESOLVERR_REPO_DIR="${FLARESOLVERR_ROOT_DIR}/.work/FlareSolverr"
  FLARESOLVERR_VENV_DIR="${FLARESOLVERR_ROOT_DIR}/.venv-flaresolverr"
  FLARESOLVERR_DOWNLOAD_DIR="${FLARESOLVERR_ROOT_DIR}/.flaresolverr"
  FLARESOLVERR_RELEASE_VERSION="v3.4.6"
  FLARESOLVERR_HOST="127.0.0.1"
  FLARESOLVERR_PORT="8191"
  LOG_LEVEL="info"
  HEADLESS="true"
  TZ="Asia/Shanghai"
  STARTUP_WAIT_SECONDS="30"
  FLARESOLVERR_LOG_FILE="${FLARESOLVERR_ROOT_DIR}/run_logs/flaresolverr-source.log"
  FLARESOLVERR_PID_FILE="${FLARESOLVERR_ROOT_DIR}/run_logs/flaresolverr-source.pid"
  PROBE_OUTPUT_ROOT="${FLARESOLVERR_ROOT_DIR}/probe_outputs"

  if [[ -f "${env_file}" ]]; then
    while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
      line="$(flaresolverr_source_trim "${raw_line}")"
      [[ -z "${line}" || "${line}" == \#* ]] && continue
      [[ "${line}" != *=* ]] && continue

      key="$(flaresolverr_source_trim "${line%%=*}")"
      value="$(flaresolverr_source_trim "${line#*=}")"
      value="$(flaresolverr_source_strip_quotes "${value}")"

      case "${key}" in
        FLARESOLVERR_REPO_DIR) FLARESOLVERR_REPO_DIR="${value}" ;;
        FLARESOLVERR_VENV_DIR) FLARESOLVERR_VENV_DIR="${value}" ;;
        FLARESOLVERR_DOWNLOAD_DIR) FLARESOLVERR_DOWNLOAD_DIR="${value}" ;;
        FLARESOLVERR_RELEASE_VERSION) FLARESOLVERR_RELEASE_VERSION="${value}" ;;
        FLARESOLVERR_HOST) FLARESOLVERR_HOST="${value}" ;;
        FLARESOLVERR_PORT) FLARESOLVERR_PORT="${value}" ;;
        LOG_LEVEL) LOG_LEVEL="${value}" ;;
        HEADLESS) HEADLESS="${value}" ;;
        TZ) TZ="${value}" ;;
        STARTUP_WAIT_SECONDS) STARTUP_WAIT_SECONDS="${value}" ;;
        FLARESOLVERR_LOG_FILE) FLARESOLVERR_LOG_FILE="${value}" ;;
        FLARESOLVERR_PID_FILE) FLARESOLVERR_PID_FILE="${value}" ;;
        PROBE_OUTPUT_ROOT) PROBE_OUTPUT_ROOT="${value}" ;;
      esac
    done < "${env_file}"
  fi

  case "${FLARESOLVERR_REPO_DIR}" in
    /*) ;;
    *) FLARESOLVERR_REPO_DIR="${FLARESOLVERR_ROOT_DIR}/${FLARESOLVERR_REPO_DIR}" ;;
  esac
  case "${FLARESOLVERR_VENV_DIR}" in
    /*) ;;
    *) FLARESOLVERR_VENV_DIR="${FLARESOLVERR_ROOT_DIR}/${FLARESOLVERR_VENV_DIR}" ;;
  esac
  case "${FLARESOLVERR_DOWNLOAD_DIR}" in
    /*) ;;
    *) FLARESOLVERR_DOWNLOAD_DIR="${FLARESOLVERR_ROOT_DIR}/${FLARESOLVERR_DOWNLOAD_DIR}" ;;
  esac
  case "${FLARESOLVERR_LOG_FILE}" in
    /*) ;;
    *) FLARESOLVERR_LOG_FILE="${FLARESOLVERR_ROOT_DIR}/${FLARESOLVERR_LOG_FILE}" ;;
  esac
  case "${FLARESOLVERR_PID_FILE}" in
    /*) ;;
    *) FLARESOLVERR_PID_FILE="${FLARESOLVERR_ROOT_DIR}/${FLARESOLVERR_PID_FILE}" ;;
  esac
  case "${PROBE_OUTPUT_ROOT}" in
    /*) ;;
    *) PROBE_OUTPUT_ROOT="${FLARESOLVERR_ROOT_DIR}/${PROBE_OUTPUT_ROOT}" ;;
  esac

  FLARESOLVERR_ARCHIVE_URL="https://github.com/FlareSolverr/FlareSolverr/releases/download/${FLARESOLVERR_RELEASE_VERSION}/flaresolverr_linux_x64.tar.gz"
  FLARESOLVERR_RELEASE_DIR="${FLARESOLVERR_DOWNLOAD_DIR}/${FLARESOLVERR_RELEASE_VERSION}"
  FLARESOLVERR_ARCHIVE_PATH="${FLARESOLVERR_RELEASE_DIR}/flaresolverr_linux_x64.tar.gz"
  FLARESOLVERR_BUNDLE_DIR="${FLARESOLVERR_RELEASE_DIR}/flaresolverr"
  FLARESOLVERR_CHROME_DIR="${FLARESOLVERR_BUNDLE_DIR}/_internal/chrome"
  FLARESOLVERR_SERVICE_URL="http://${FLARESOLVERR_HOST}:${FLARESOLVERR_PORT}/v1"
}

flaresolverr_source_ensure_chrome_link() {
  mkdir -p "${FLARESOLVERR_REPO_DIR}/src"

  if [[ -e "${FLARESOLVERR_REPO_DIR}/src/chrome" || -L "${FLARESOLVERR_REPO_DIR}/src/chrome" ]]; then
    local current_target=""
    current_target="$(readlink -f "${FLARESOLVERR_REPO_DIR}/src/chrome" 2>/dev/null || true)"
    if [[ "${current_target}" != "${FLARESOLVERR_CHROME_DIR}" ]]; then
      rm -rf "${FLARESOLVERR_REPO_DIR}/src/chrome"
    fi
  fi

  if [[ ! -e "${FLARESOLVERR_REPO_DIR}/src/chrome" ]]; then
    ln -s "${FLARESOLVERR_CHROME_DIR}" "${FLARESOLVERR_REPO_DIR}/src/chrome"
  fi
}

flaresolverr_source_probe_direct() {
  local service_url="$1"
  curl --noproxy '*' --fail --show-error --silent \
    --connect-timeout 2 --max-time 5 \
    -X POST "${service_url}" \
    -H 'Content-Type: application/json' \
    -d '{"cmd":"sessions.list"}'
}

flaresolverr_source_find_listener_pid() {
  ss -ltnp 2>/dev/null | awk -v addr="${FLARESOLVERR_HOST}:${FLARESOLVERR_PORT}" '
    index($0, addr) {
      if (match($0, /pid=[0-9]+/)) {
        pid_field = substr($0, RSTART, RLENGTH)
        sub(/^pid=/, "", pid_field)
        print pid_field
        exit
      }
    }
  '
}
