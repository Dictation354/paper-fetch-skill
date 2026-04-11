#!/usr/bin/env bash
# Install the static paper-fetch skill for Codex.
#
# Usage:
#   ./scripts/install-codex-skill.sh              # user-scope skill (~/.codex/skills/…)
#   ./scripts/install-codex-skill.sh --project    # project-scope skill (./.codex/skills/…)
#   ./scripts/install-codex-skill.sh --register-mcp [--env-file .env]
#   ./scripts/install-codex-skill.sh --uninstall  # remove the installed skill entry

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_NAME="paper-fetch-skill"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SCOPE="user"
UNINSTALL=0
REGISTER_MCP=0
MCP_NAME="paper-fetch"
MCP_ENV_FILE=""

if [ "$SCOPE" = "user" ]; then
    SKILL_DIR="$CODEX_HOME_DIR/skills/$SKILL_NAME"
else
    SKILL_DIR="$REPO_DIR/.codex/skills/$SKILL_NAME"
fi

SOURCE_SKILL_DIR="$REPO_DIR/skills/$SKILL_NAME"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

abspath() {
    local path="$1"
    case "$path" in
        "~") printf '%s\n' "$HOME" ;;
        "~/"*) printf '%s\n' "$HOME/${path#~/}" ;;
        /*) printf '%s\n' "$path" ;;
        *) printf '%s\n' "$REPO_DIR/$path" ;;
    esac
}

register_mcp() {
    command -v codex >/dev/null 2>&1 || die "codex not found on PATH; cannot auto-register MCP. Install Codex CLI or rerun without --register-mcp."

    local python_bin
    python_bin="$(python3 -c 'import sys; print(sys.executable)')"

    if [ -n "$MCP_ENV_FILE" ] && [ ! -f "$MCP_ENV_FILE" ]; then
        warn "MCP env file $MCP_ENV_FILE does not exist yet; registration will still point to it."
    fi

    log "Registering Codex MCP server '$MCP_NAME'"
    codex mcp remove "$MCP_NAME" >/dev/null 2>&1 || true

    local args=(mcp add)
    if [ -n "$MCP_ENV_FILE" ]; then
        args+=(--env "PAPER_FETCH_ENV_FILE=$MCP_ENV_FILE")
    fi
    args+=("$MCP_NAME" -- "$python_bin" -m paper_fetch.mcp.server)
    codex "${args[@]}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --project)
            SCOPE="project"
            ;;
        --user)
            SCOPE="user"
            ;;
        --register-mcp)
            REGISTER_MCP=1
            ;;
        --env-file)
            shift
            [ "$#" -gt 0 ] || die "--env-file requires a path"
            MCP_ENV_FILE="$1"
            ;;
        --mcp-name)
            shift
            [ "$#" -gt 0 ] || die "--mcp-name requires a value"
            MCP_NAME="$1"
            ;;
        --uninstall)
            UNINSTALL=1
            ;;
        -h|--help)
            sed -n '2,9p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
    esac
    shift
done

if [ "$SCOPE" = "user" ]; then
    SKILL_DIR="$CODEX_HOME_DIR/skills/$SKILL_NAME"
else
    SKILL_DIR="$REPO_DIR/.codex/skills/$SKILL_NAME"
fi

if [ -n "$MCP_ENV_FILE" ]; then
    MCP_ENV_FILE="$(abspath "$MCP_ENV_FILE")"
fi

if [ "$UNINSTALL" = "1" ]; then
    rm -rf "$SKILL_DIR"
    log "Removed $SKILL_DIR"
    if [ "$REGISTER_MCP" = "1" ] && command -v codex >/dev/null 2>&1; then
        codex mcp remove "$MCP_NAME" >/dev/null 2>&1 || true
        log "Removed Codex MCP server '$MCP_NAME'"
    fi
    exit 0
fi

command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH"
[ -f "$SOURCE_SKILL_DIR/SKILL.md" ] || die "Missing static skill source at $SOURCE_SKILL_DIR/SKILL.md"

log "Installing package into the current python3 environment"
cd "$REPO_DIR"
if ! python3 -m pip install --quiet .; then
    die "python3 -m pip install . failed. Activate a writable virtual environment or run scripts/dev-bootstrap.sh first."
fi

log "Copying static skill to $SKILL_DIR"
mkdir -p "$SKILL_DIR/agents"
cp "$SOURCE_SKILL_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"
cat > "$SKILL_DIR/agents/openai.yaml" <<'EOF'
interface:
  display_name: "Paper Fetch Skill"
  short_description: "Fetch AI-friendly paper text by DOI, URL, or title"
  default_prompt: "Use $paper-fetch-skill whenever you need the text, readability, or full-text availability of a specific paper or a citation list of identifiable papers."
EOF

if [ "$REGISTER_MCP" = "1" ]; then
    register_mcp
fi

echo
echo "Next steps:"
echo "  1. Restart Codex so it rescans installed skills."
if [ "$REGISTER_MCP" = "1" ]; then
    echo "  2. Codex MCP server '$MCP_NAME' is registered and will launch via the current python3 environment."
else
    echo "  2. If you want MCP tools too, rerun with --register-mcp or register a stdio server that runs 'paper-fetch-mcp'."
fi
echo "  3. Re-run this installer after upgrading the repo to install the new package build."
