#!/usr/bin/env bash
# Install the static paper-fetch skill for Claude Code.
#
# Usage:
#   ./scripts/install-claude-skill.sh              # user-scope skill (~/.claude/skills/...)
#   ./scripts/install-claude-skill.sh --project    # project-scope skill (./.claude/skills/...)
#   ./scripts/install-claude-skill.sh --register-mcp [--env-file .env]
#   ./scripts/install-claude-skill.sh --check        # read-only drift check
#   ./scripts/install-claude-skill.sh --uninstall  # remove the installed skill entry

set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_skill_install_common.sh"

PF_HOST="claude"
PF_RESTART_NAME="Claude Code"
PF_SUPPORTS_MCP_SCOPE=1

pf_host_register_mcp() {
    command -v claude >/dev/null 2>&1 || pf_skill_die "claude not found on PATH; cannot auto-register MCP. Install Claude Code CLI or rerun without --register-mcp."

    local python_bin
    python_bin="$(python3 -c 'import sys; print(sys.executable)')"

    if [ -n "$PF_MCP_ENV_FILE" ] && [ ! -f "$PF_MCP_ENV_FILE" ]; then
        pf_skill_warn "MCP env file $PF_MCP_ENV_FILE does not exist yet; registration will still point to it."
    fi

    pf_skill_log "Registering Claude MCP server '$PF_MCP_NAME' (scope: $PF_MCP_SCOPE)"
    claude mcp remove -s "$PF_MCP_SCOPE" "$PF_MCP_NAME" >/dev/null 2>&1 || true

    local args=(mcp add -s "$PF_MCP_SCOPE")
    if [ -n "$PF_MCP_ENV_FILE" ]; then
        args+=(-e "PAPER_FETCH_ENV_FILE=$PF_MCP_ENV_FILE")
    fi
    args+=(-- "$PF_MCP_NAME" "$python_bin" -m paper_fetch.mcp.server)
    claude "${args[@]}"
}

pf_host_unregister_mcp() {
    if command -v claude >/dev/null 2>&1; then
        claude mcp remove -s "$PF_MCP_SCOPE" "$PF_MCP_NAME" >/dev/null 2>&1 || true
        pf_skill_log "Removed Claude MCP server '$PF_MCP_NAME' (scope: $PF_MCP_SCOPE)"
    fi
}

pf_host_print_registered_note() {
    echo "  2. Claude MCP server '$PF_MCP_NAME' is registered at scope '$PF_MCP_SCOPE' and will launch via the current python3 environment."
}

pf_skill_main "$@"
