#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/dev-preflight.sh [--fast] [--skip-integration] [--skip-typecheck] [--with-golden]

Runs the local preflight gate:
  - ruff format check
  - ruff lint
  - full production-package mypy
  - version consistency gate
  - unit tests
  - integration tests

Options:
  --with-golden     Run all three layers (required before release).
  --fast              Run ruff, mypy, and unit tests only.
  --skip-integration Skip integration tests.
  --skip-typecheck   Skip mypy.
  -h, --help         Show this help.
USAGE
}

run_integration=1
run_typecheck=1
run_golden=0

while (($#)); do
  case "$1" in
    --with-golden)
      run_golden=1
      ;;
    --fast)
      run_integration=0
      ;;
    --skip-integration)
      run_integration=0
      ;;
    --skip-typecheck)
      run_typecheck=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "$run_golden" == "1" && "$run_integration" == "0" ]]; then
  echo "--with-golden conflicts with --fast / --skip-integration" >&2
  exit 2
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

require_module() {
  local module="$1"
  if ! "$PYTHON_BIN" -m "$module" --version >/dev/null 2>&1; then
    echo "Missing Python module '$module' for $PYTHON_BIN." >&2
    echo "Run scripts/dev-bootstrap.sh, activate .venv, or set PYTHON_BIN to a prepared interpreter." >&2
    exit 1
  fi
}

require_module ruff
require_module pytest
if [[ "$run_typecheck" == "1" ]]; then
  require_module mypy
fi

export PYTHONPATH="${PYTHONPATH:-src}"

"$PYTHON_BIN" -m ruff format --check .
"$PYTHON_BIN" -m ruff check .

if [[ "$run_typecheck" == "1" ]]; then
  PYTHONPATH=src "$PYTHON_BIN" -m mypy src/paper_fetch
fi
"$PYTHON_BIN" scripts/sync_version.py --check

PYTHONPATH=src "$PYTHON_BIN" -m pytest tests/unit -q --durations=30

if [[ "$run_integration" == "1" ]]; then
  PYTHONPATH=src "$PYTHON_BIN" -m pytest tests/integration -q --durations=30
fi

if [[ "$run_golden" == "1" ]]; then
  PYTHONPATH=src "$PYTHON_BIN" -m pytest tests/golden -q --durations=30
fi
