#!/usr/bin/env bash
# Bootstrap a repo-local development environment.
#
# Usage:
#   ./scripts/dev-bootstrap.sh              # create/update ./.venv, install deps, copy .env.example, install formula tools
#   ./scripts/dev-bootstrap.sh --system     # install into the current python3 environment instead of ./.venv
#   ./scripts/dev-bootstrap.sh --no-node    # skip the Node formula fallback install
#   ./scripts/dev-bootstrap.sh --skip-env-file

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
USE_SYSTEM=0
INSTALL_NODE=1
COPY_ENV_FILE=1

for arg in "$@"; do
    case "$arg" in
        --system) USE_SYSTEM=1 ;;
        --no-node) INSTALL_NODE=0 ;;
        --skip-env-file) COPY_ENV_FILE=0 ;;
        -h|--help)
            sed -n '2,9p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH"

if [ "$USE_SYSTEM" = "1" ]; then
    PYTHON_BIN="python3"
else
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment at $VENV_DIR"
        python3 -m venv "$VENV_DIR"
    fi
    PYTHON_BIN="$VENV_DIR/bin/python"
fi

log "Installing Python dependencies"
"$PYTHON_BIN" -m pip install --quiet --upgrade pip
"$PYTHON_BIN" -m pip install --quiet -r "$REPO_DIR/requirements.txt"
"$PYTHON_BIN" -m pip install --quiet -e "$REPO_DIR"

if [ "$COPY_ENV_FILE" = "1" ] && [ -f "$REPO_DIR/.env.example" ] && [ ! -f "$REPO_DIR/.env" ]; then
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    warn "Created $REPO_DIR/.env from template. Fill in the API keys you have before running live fetches."
fi

FORMULA_ARGS=()
if [ "$INSTALL_NODE" != "1" ]; then
    FORMULA_ARGS+=(--no-node)
fi

log "Installing formula backends"
bash "$REPO_DIR/install-formula-tools.sh" "${FORMULA_ARGS[@]}"

echo
echo "Bootstrap complete."
if [ "$USE_SYSTEM" = "1" ]; then
    echo "Using system python3 for paper-fetch commands."
else
    echo "Activate the repo environment with: source $VENV_DIR/bin/activate"
fi
