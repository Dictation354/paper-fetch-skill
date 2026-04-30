#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.flaresolverr-source-headless}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# shellcheck disable=SC1091
source "${ROOT_DIR}/flaresolverr_source_common.sh"
flaresolverr_source_load_env "${ENV_FILE}"
PATCH_BRANCH_NAME="paper-fetch/${FLARESOLVERR_RELEASE_VERSION}"

mkdir -p "${FLARESOLVERR_DOWNLOAD_DIR}" "${ROOT_DIR}/run_logs"

source_has_image_payload_patch() {
  grep -q "returnImagePayload" "${FLARESOLVERR_REPO_DIR}/src/dtos.py" 2>/dev/null \
    && grep -q "imagePayload" "${FLARESOLVERR_REPO_DIR}/src/flaresolverr_service.py" 2>/dev/null
}

tracked_source_changes() {
  git -C "${FLARESOLVERR_REPO_DIR}" status --porcelain --untracked-files=no
}

ensure_patched_checkout_branch() {
  if git -C "${FLARESOLVERR_REPO_DIR}" symbolic-ref -q HEAD >/dev/null; then
    return
  fi
  if git -C "${FLARESOLVERR_REPO_DIR}" show-ref --verify --quiet "refs/heads/${PATCH_BRANCH_NAME}"; then
    return
  fi
  git -C "${FLARESOLVERR_REPO_DIR}" branch "${PATCH_BRANCH_NAME}" HEAD
  git -C "${FLARESOLVERR_REPO_DIR}" checkout "${PATCH_BRANCH_NAME}" >/dev/null
}

if [[ ! -d "${FLARESOLVERR_REPO_DIR}/.git" ]]; then
  mkdir -p "$(dirname "${FLARESOLVERR_REPO_DIR}")"
  git clone --depth 1 --branch "${FLARESOLVERR_RELEASE_VERSION}" \
    https://github.com/FlareSolverr/FlareSolverr.git \
    "${FLARESOLVERR_REPO_DIR}"
  git -C "${FLARESOLVERR_REPO_DIR}" checkout -B "${PATCH_BRANCH_NAME}" >/dev/null
else
  if source_has_image_payload_patch; then
    ensure_patched_checkout_branch
    echo "Reusing existing patched FlareSolverr source checkout: ${FLARESOLVERR_REPO_DIR}"
  else
    source_changes="$(tracked_source_changes)"
    if [[ -n "${source_changes}" ]]; then
      echo "Existing FlareSolverr checkout has tracked local changes and is missing the paper-fetch image payload patch." >&2
      echo "Refusing to reset it. Commit or stash those changes, or point FLARESOLVERR_REPO_DIR at a clean checkout." >&2
      printf '%s\n' "${source_changes}" >&2
      exit 1
    fi
    git -C "${FLARESOLVERR_REPO_DIR}" fetch --depth 1 origin \
      "refs/tags/${FLARESOLVERR_RELEASE_VERSION}:refs/tags/${FLARESOLVERR_RELEASE_VERSION}"
    if git -C "${FLARESOLVERR_REPO_DIR}" show-ref --verify --quiet "refs/heads/${PATCH_BRANCH_NAME}"; then
      git -C "${FLARESOLVERR_REPO_DIR}" checkout "${PATCH_BRANCH_NAME}" >/dev/null
    else
      git -C "${FLARESOLVERR_REPO_DIR}" checkout -B "${PATCH_BRANCH_NAME}" "${FLARESOLVERR_RELEASE_VERSION}" >/dev/null
    fi
  fi
fi

if [[ ! -d "${FLARESOLVERR_VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${FLARESOLVERR_VENV_DIR}"
fi

source "${FLARESOLVERR_VENV_DIR}/bin/activate"
pip install --upgrade pip setuptools wheel
pip install -r "${FLARESOLVERR_REPO_DIR}/requirements.txt"

mkdir -p "${FLARESOLVERR_RELEASE_DIR}"
if [[ ! -f "${FLARESOLVERR_ARCHIVE_PATH}" ]]; then
  curl --fail --show-error --silent --location \
    --retry 5 --retry-delay 2 --retry-all-errors \
    --connect-timeout 20 --max-time 600 \
    "${FLARESOLVERR_ARCHIVE_URL}" \
    -o "${FLARESOLVERR_ARCHIVE_PATH}"
fi

if [[ ! -x "${FLARESOLVERR_CHROME_DIR}/chrome" ]]; then
  tar -xzf "${FLARESOLVERR_ARCHIVE_PATH}" -C "${FLARESOLVERR_RELEASE_DIR}"
fi

flaresolverr_source_ensure_chrome_link

RETURN_IMAGE_PAYLOAD_PATCH="${ROOT_DIR}/patches/return-image-payload.patch"
if [[ -f "${RETURN_IMAGE_PAYLOAD_PATCH}" ]]; then
  if source_has_image_payload_patch; then
    echo "FlareSolverr image payload patch is already present."
  else
    git -C "${FLARESOLVERR_REPO_DIR}" apply --check "${RETURN_IMAGE_PAYLOAD_PATCH}"
    git -C "${FLARESOLVERR_REPO_DIR}" apply "${RETURN_IMAGE_PAYLOAD_PATCH}"
    git -C "${FLARESOLVERR_REPO_DIR}" add src/dtos.py src/flaresolverr_service.py
    if ! git -C "${FLARESOLVERR_REPO_DIR}" diff --cached --quiet; then
      git -C "${FLARESOLVERR_REPO_DIR}" \
        -c user.name="paper-fetch-skill" \
        -c user.email="paper-fetch-skill@example.invalid" \
        commit -m "Add repo-local image payload export" >/dev/null
    fi
  fi
fi

echo
echo "FlareSolverr source workflow is prepared."
echo "Repo: ${FLARESOLVERR_REPO_DIR}"
echo "Venv: ${FLARESOLVERR_VENV_DIR}"
echo "Chrome bundle: ${FLARESOLVERR_CHROME_DIR}/chrome"
echo "Default env: ${ENV_FILE}"
