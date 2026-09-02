#!/usr/bin/env bash
# Install the static paper-fetch skill for Codex.
#
# Usage:
#   ./scripts/install-codex-skill.sh              # user-scope skill (~/.codex/skills/...)
#   ./scripts/install-codex-skill.sh --project    # project-scope skill (./.codex/skills/...)
#   ./scripts/install-codex-skill.sh --register-mcp [--env-file .env]
#   ./scripts/install-codex-skill.sh --check        # read-only user-scope drift check
#   ./scripts/install-codex-skill.sh --project --check
#   ./scripts/install-codex-skill.sh --uninstall  # remove the installed skill entry

set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_skill_install_common.sh"

PF_HOST="codex"
PF_RESTART_NAME="Codex"

pf_host_register_mcp() {
    command -v codex >/dev/null 2>&1 || pf_skill_die "codex not found on PATH; cannot auto-register MCP. Install Codex CLI or rerun without --register-mcp."

    local python_bin
    python_bin="$(python3 -c 'import sys; print(sys.executable)')"

    if [ -n "$PF_MCP_ENV_FILE" ] && [ ! -f "$PF_MCP_ENV_FILE" ]; then
        pf_skill_warn "MCP env file $PF_MCP_ENV_FILE does not exist yet; registration will still point to it."
    fi

    pf_skill_log "Registering Codex MCP server '$PF_MCP_NAME'"
    codex mcp remove "$PF_MCP_NAME" >/dev/null 2>&1 || true

    local args=(mcp add)
    if [ -n "$PF_MCP_ENV_FILE" ]; then
        args+=(--env "PAPER_FETCH_ENV_FILE=$PF_MCP_ENV_FILE")
    fi
    args+=("$PF_MCP_NAME" -- "$python_bin" -X utf8 -m paper_fetch.mcp.server)
    codex "${args[@]}"
}

pf_host_unregister_mcp() {
    if command -v codex >/dev/null 2>&1; then
        codex mcp remove "$PF_MCP_NAME" >/dev/null 2>&1 || true
        pf_skill_log "Removed Codex MCP server '$PF_MCP_NAME'"
    fi
}

pf_host_print_registered_note() {
    echo "  2. Codex MCP server '$PF_MCP_NAME' is registered and will launch via the current python3 environment."
    echo "     Browser-backed providers require a prepared Camoufox runtime."
    echo "     Ordinary MCP tools do not install or repair it; run 'python -m camoufox fetch' explicitly before use."
}

pf_skill_main "$@"
