#!/usr/bin/env bash
# Install the static paper-fetch skill for the Antigravity CLI (agy).
#
# Usage:
#   ./scripts/install-antigravity-skill.sh              # user-scope skill (~/.gemini/antigravity-cli/skills/...)
#   ./scripts/install-antigravity-skill.sh --project    # project-scope skill (./.agents/skills/...)
#   ./scripts/install-antigravity-skill.sh --register-mcp [--env-file .env]
#   ./scripts/install-antigravity-skill.sh --uninstall  # remove the installed skill entry
#
# Override the global Antigravity config directory with ANTIGRAVITY_HOME
# (defaults to ~/.gemini/antigravity-cli).

set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_skill_install_common.sh"

PF_HOST="antigravity"
PF_RESTART_NAME="the Antigravity CLI (agy)"
# Antigravity reads project-scope skills/MCP from .agents/, not .antigravity/.
PF_PROJECT_SKILLS_PARENT=".agents"

# Antigravity has no `mcp add` CLI subcommand; MCP servers are configured via a
# mcp_config.json file. User scope writes the global config; project scope writes
# the workspace .agents/mcp_config.json.
pf_antigravity_mcp_config_path() {
    if [ "$PF_SCOPE" = "user" ]; then
        printf '%s/mcp_config.json\n' "$(pf_skill_user_base)"
    else
        printf '%s/.agents/mcp_config.json\n' "$PF_REPO_DIR"
    fi
}

pf_host_register_mcp() {
    local python_bin config_path
    python_bin="$(python3 -c 'import sys; print(sys.executable)')"
    config_path="$(pf_antigravity_mcp_config_path)"

    if [ -n "$PF_MCP_ENV_FILE" ] && [ ! -f "$PF_MCP_ENV_FILE" ]; then
        pf_skill_warn "MCP env file $PF_MCP_ENV_FILE does not exist yet; registration will still point to it."
    fi

    pf_skill_log "Registering Antigravity MCP server '$PF_MCP_NAME' in $config_path"
    mkdir -p "$(dirname "$config_path")"

    PF_CONFIG_PATH="$config_path" \
    PF_MCP_NAME="$PF_MCP_NAME" \
    PF_PYTHON_BIN="$python_bin" \
    PF_MCP_ENV_FILE="$PF_MCP_ENV_FILE" \
    python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["PF_CONFIG_PATH"])
name = os.environ["PF_MCP_NAME"]

data = {}
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Existing {path} is not valid JSON: {exc}")
if not isinstance(data, dict):
    raise SystemExit(f"Existing {path} must contain a JSON object")

servers = data.setdefault("mcpServers", {})
if not isinstance(servers, dict):
    raise SystemExit(f"'mcpServers' in {path} must be a JSON object")

entry = {
    "command": os.environ["PF_PYTHON_BIN"],
    "args": ["-X", "utf8", "-m", "paper_fetch.mcp.server"],
}
env_file = os.environ.get("PF_MCP_ENV_FILE") or ""
if env_file:
    entry["env"] = {"PAPER_FETCH_ENV_FILE": env_file}

servers[name] = entry
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
}

pf_host_unregister_mcp() {
    local config_path
    config_path="$(pf_antigravity_mcp_config_path)"
    [ -f "$config_path" ] || return 0

    PF_CONFIG_PATH="$config_path" \
    PF_MCP_NAME="$PF_MCP_NAME" \
    python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["PF_CONFIG_PATH"])
name = os.environ["PF_MCP_NAME"]
try:
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
except json.JSONDecodeError:
    raise SystemExit(0)
if not isinstance(data, dict):
    raise SystemExit(0)

servers = data.get("mcpServers")
if isinstance(servers, dict):
    servers.pop(name, None)
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
    pf_skill_log "Removed Antigravity MCP server '$PF_MCP_NAME' from $config_path"
}

pf_host_print_registered_note() {
    echo "  2. Antigravity MCP server '$PF_MCP_NAME' is registered in $(pf_antigravity_mcp_config_path) and will launch via the current python3 environment."
    echo "     Browser backend: Camoufox by default; first fetch may download its runtime."
    echo "     Use PAPER_FETCH_BROWSER_BACKEND=cloakbrowser only for deprecated compatibility."
}

pf_skill_main "$@"
