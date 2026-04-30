#!/usr/bin/env bash
# One-command installer for the full paper-fetch runtime.
#
# Usage:
#   ./install.sh                 # create ./.venv, install the package, then install browser-heavy runtime pieces
#   ./install.sh --system        # install into the current python3 environment instead of ./.venv
#   ./install.sh --lite          # install only the Python package and config scaffold
#   ./install.sh --skip-env-file # do not create ~/.config/paper-fetch/.env from .env.example

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PAPER_FETCH_INSTALL_VENV_DIR:-$REPO_DIR/.venv}"
USE_SYSTEM=0
INSTALL_HEAVY=1
COPY_ENV_FILE=1
UPGRADE_PIP=1
EDITABLE=0
FORMULA_ARGS=()
DEFAULT_ENV_FILE=""

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '2,9p' "$0"
    cat <<'EOF'

Options:
  --venv-dir <path>             Use a custom virtualenv directory.
  --editable                    Install the Python package in editable mode.
  --skip-pip-upgrade            Do not upgrade pip before installing.
  --skip-flaresolverr-setup     Skip repo-local FlareSolverr source setup.
  --skip-playwright-install     Skip Playwright Chromium browser install.
  --no-node                     Skip the Node mathml-to-latex formula fallback.
  -h, --help                    Show this help.
EOF
}

while (($#)); do
    case "$1" in
        --system)
            USE_SYSTEM=1
            ;;
        --venv-dir)
            shift
            [ "$#" -gt 0 ] || die "--venv-dir requires a path"
            VENV_DIR="$1"
            ;;
        --lite)
            INSTALL_HEAVY=0
            ;;
        --skip-env-file)
            COPY_ENV_FILE=0
            ;;
        --editable)
            EDITABLE=1
            ;;
        --skip-pip-upgrade)
            UPGRADE_PIP=0
            ;;
        --skip-flaresolverr-setup|--skip-playwright-install|--no-node)
            FORMULA_ARGS+=("$1")
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

if [ "$UPGRADE_PIP" = "1" ]; then
    log "Upgrading pip"
    "$PYTHON_BIN" -m pip install --quiet --upgrade pip
fi

log "Installing paper-fetch-skill Python package"
if [ "$EDITABLE" = "1" ]; then
    "$PYTHON_BIN" -m pip install --quiet --editable "$REPO_DIR"
else
    "$PYTHON_BIN" -m pip install --quiet "$REPO_DIR"
fi

if [ -f "$REPO_DIR/.env.example" ]; then
    DEFAULT_ENV_FILE="$("$PYTHON_BIN" - <<'PY'
from paper_fetch.config import DEFAULT_USER_ENV_FILE
print(DEFAULT_USER_ENV_FILE)
PY
)"
fi

if [ "$COPY_ENV_FILE" = "1" ] && [ -n "$DEFAULT_ENV_FILE" ] && [ -f "$REPO_DIR/.env.example" ]; then
    if [ ! -f "$DEFAULT_ENV_FILE" ]; then
        log "Creating default runtime config at $DEFAULT_ENV_FILE"
        mkdir -p "$(dirname "$DEFAULT_ENV_FILE")"
        cp "$REPO_DIR/.env.example" "$DEFAULT_ENV_FILE"
        warn "Edit $DEFAULT_ENV_FILE before using provider API keys in live fetches."
    fi
fi

if [ "$INSTALL_HEAVY" = "1" ]; then
    log "Installing browser-heavy runtime pieces"
    PAPER_FETCH_INSTALL_PYTHON_BIN="$PYTHON_BIN" \
    PYTHON_BIN="$PYTHON_BIN" \
        bash "$REPO_DIR/install-formula-tools.sh" "${FORMULA_ARGS[@]}"
else
    warn "Skipped Playwright Chromium, FlareSolverr, and external formula backends because --lite was set."
fi

echo
echo "Installation complete."
if [ "$USE_SYSTEM" = "1" ]; then
    echo "Commands are installed in the current python3 environment."
else
    echo "Activate the repo environment with: source $VENV_DIR/bin/activate"
    echo "Or run commands directly from: $VENV_DIR/bin/"
fi
if [ -n "$DEFAULT_ENV_FILE" ]; then
    echo "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=\"...\" to $DEFAULT_ENV_FILE before fetching Elsevier papers."
else
    echo "Elsevier setup: request a key at https://dev.elsevier.com/, then add ELSEVIER_API_KEY=\"...\" to your PAPER_FETCH_ENV_FILE or user config before fetching Elsevier papers."
fi
echo "Smoke test: $PYTHON_BIN -m paper_fetch.cli --query \"10.1186/1471-2105-11-421\""
