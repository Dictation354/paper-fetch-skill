#!/usr/bin/env bash
# Run deterministic macOS contract checks from native Linux or WSL.

set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
REPO_DIR="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
PYTHON_BIN="${PAPER_FETCH_CONTRACT_PYTHON_BIN:-}"
VALIDATOR_ONLY=0
DEGRADED_CHECKOUT=0

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  scripts/test-macos-contract.sh [--python <path>] [--validator-only]

Runs the machine-readable contract validator and, unless validator-only mode
is active, deterministic fake-Darwin/shell pytest nodes. It never replaces the
native macos-15 release gate. A WSL checkout below /mnt is automatically
degraded to validator-only because DrvFS cannot prove Unix filesystem semantics.
EOF
}

while (($#)); do
  case "$1" in
    --python)
      shift
      [ "$#" -gt 0 ] || die "--python requires a path"
      PYTHON_BIN="$1"
      ;;
    --validator-only)
      VALIDATOR_ONLY=1
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

is_wsl() {
  [ -n "${WSL_DISTRO_NAME:-}" ] \
    || grep -qiE '(microsoft|wsl)' /proc/version 2>/dev/null
}

case "$REPO_DIR" in
  /mnt/[a-zA-Z]/*)
    if is_wsl; then
      DEGRADED_CHECKOUT=1
      VALIDATOR_ONLY=1
      warn "Repository is on a Windows-mounted filesystem: $REPO_DIR"
      warn "Running validator-only; clone under the WSL Linux filesystem for symlink, mode, case, and fake-Darwin pytest evidence."
    fi
    ;;
esac

select_python() {
  if [ -n "$PYTHON_BIN" ]; then
    return
  fi
  if [ "$DEGRADED_CHECKOUT" != "1" ] && [ -x "$REPO_DIR/.venv-wsl/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/.venv-wsl/bin/python"
  elif [ "$DEGRADED_CHECKOUT" != "1" ] && [ -x "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
}

select_python
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python not found: $PYTHON_BIN"
"$PYTHON_BIN" -c \
  'from pathlib import Path
import sys

executable = Path(sys.executable).resolve()
environment = Path(sys.prefix).absolute()
if sys.platform != "linux":
    raise SystemExit(
        f"WSL/Linux contract tests require native Linux Python; "
        f"got {sys.platform}: {executable}"
    )
if executable.suffix.lower() == ".exe" or str(environment).startswith("/mnt/"):
    raise SystemExit(
        f"Use a native Linux Python/virtual environment outside /mnt: {environment}"
    )
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required")'

if is_wsl; then
  log "Detected WSL development environment"
fi

cd "$REPO_DIR"
log "Validating the machine-readable macOS adaptation contract"
"$PYTHON_BIN" scripts/validate_macos_adaptation.py

if [ "$VALIDATOR_ONLY" = "1" ]; then
  exit 0
fi

log "Running deterministic WSL/Linux macOS contract pytest nodes"
TEST_NODE_OUTPUT="$(
  "$PYTHON_BIN" scripts/validate_macos_adaptation.py --print-test-nodes wsl
)" || die "Failed to select WSL/Linux macOS contract tests."
[ -n "$TEST_NODE_OUTPUT" ] || die "No WSL/Linux macOS contract tests were selected."
mapfile -t TEST_NODES <<< "$TEST_NODE_OUTPUT"
PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON_BIN" -m pytest "${TEST_NODES[@]}" -q
