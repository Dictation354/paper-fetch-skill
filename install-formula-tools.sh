#!/usr/bin/env bash
# Install formula conversion backends for paper-fetch-skill.
#
# Preferred order:
#   1. texmath (compiled locally via cabal or stack, or reused from PATH)
#   2. mathml-to-latex (Node fallback)
#   3. built-in Python MathML renderer

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_NODE=1

for arg in "$@"; do
    case "$arg" in
        --no-node) INSTALL_NODE=0 ;;
        -h|--help)
            sed -n '2,8p' "$0"
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

FORMULA_TOOLS_DIR="$REPO_DIR/.formula-tools"
FORMULA_TOOLS_BIN_DIR="$FORMULA_TOOLS_DIR/bin"
TEXMATH_TARGET="$FORMULA_TOOLS_BIN_DIR/texmath"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }

mkdir -p "$FORMULA_TOOLS_BIN_DIR"

have_working_texmath() {
    local candidate="$1"
    [ -n "$candidate" ] && [ -x "$candidate" ] && "$candidate" --help >/dev/null 2>&1
}

run_with_log() {
    local log_file="$1"
    shift
    if "$@" >"$log_file" 2>&1; then
        rm -f "$log_file"
        return 0
    fi
    return 1
}

reuse_texmath_from_path() {
    local system_texmath
    system_texmath="$(command -v texmath 2>/dev/null || true)"
    if ! have_working_texmath "$system_texmath"; then
        return 1
    fi
    if [ "$system_texmath" != "$TEXMATH_TARGET" ]; then
        ln -sf "$system_texmath" "$TEXMATH_TARGET"
    fi
    log "Using existing texmath at $system_texmath"
    return 0
}

install_texmath_with_cabal() {
    if ! command -v cabal >/dev/null 2>&1; then
        return 1
    fi

    local log_file
    log_file="$(mktemp "${TMPDIR:-/tmp}/texmath-cabal.XXXXXX.log")"
    log "Attempting to install texmath with cabal"
    if ! cabal update >>"$log_file" 2>&1; then
        warn "cabal update failed; continuing with the local package index."
    fi
    if run_with_log \
        "$log_file" \
        cabal install texmath -fexecutable \
            --installdir="$FORMULA_TOOLS_BIN_DIR" \
            --install-method=copy \
            --overwrite-policy=always \
            --package-env=none
    then
        return 0
    fi

    warn "cabal texmath install failed. Build log: $log_file"
    return 1
}

install_texmath_with_stack() {
    if ! command -v stack >/dev/null 2>&1; then
        return 1
    fi

    local log_file
    log_file="$(mktemp "${TMPDIR:-/tmp}/texmath-stack.XXXXXX.log")"
    log "Attempting to install texmath with stack"
    if run_with_log \
        "$log_file" \
        stack install texmath \
            --flag texmath:executable \
            --local-bin-path "$FORMULA_TOOLS_BIN_DIR"
    then
        return 0
    fi

    warn "stack texmath install failed. Build log: $log_file"
    return 1
}

ensure_mathml_to_latex() {
    if [ "$INSTALL_NODE" != "1" ]; then
        warn "Skipping mathml-to-latex fallback because --no-node was set."
        return 1
    fi
    if ! command -v node >/dev/null 2>&1; then
        warn "node not found; mathml-to-latex fallback is unavailable."
        return 1
    fi

    if [ -d "$REPO_DIR/node_modules/mathml-to-latex" ] && [ -d "$REPO_DIR/node_modules/katex" ]; then
        log "Using existing mathml-to-latex Node dependencies"
        return 0
    fi

    local log_file
    log_file="$(mktemp "${TMPDIR:-/tmp}/mathml-to-latex.XXXXXX.log")"
    log "Installing Node dependencies for mathml-to-latex fallback"
    if run_with_log "$log_file" bash -lc "cd \"$REPO_DIR\" && npm install --omit=dev --silent"; then
        return 0
    fi

    warn "npm install for mathml-to-latex failed. Build log: $log_file"
    return 1
}

if have_working_texmath "$TEXMATH_TARGET"; then
    log "Formula backend ready: texmath ($TEXMATH_TARGET)"
    exit 0
fi

if reuse_texmath_from_path; then
    log "Formula backend ready: texmath"
    exit 0
fi

if install_texmath_with_cabal || install_texmath_with_stack; then
    if have_working_texmath "$TEXMATH_TARGET"; then
        log "Formula backend ready: texmath ($TEXMATH_TARGET)"
        exit 0
    fi
    warn "texmath build reported success but the installed binary could not be executed."
fi

warn "texmath is unavailable; falling back to mathml-to-latex."
if ensure_mathml_to_latex; then
    log "Formula backend ready: mathml-to-latex"
    exit 0
fi

warn "No external MathML-to-LaTeX backend is available. The built-in Python renderer will be used."
