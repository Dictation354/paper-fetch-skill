#!/usr/bin/env bash
# Install the static paper-fetch skill for Codex.
#
# Usage:
#   ./scripts/install-codex-skill.sh              # user-scope skill (~/.codex/skills/…)
#   ./scripts/install-codex-skill.sh --project    # project-scope skill (./.codex/skills/…)
#   ./scripts/install-codex-skill.sh --uninstall  # remove the installed skill entry

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_NAME="paper-fetch-skill"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SCOPE="user"
UNINSTALL=0

for arg in "$@"; do
    case "$arg" in
        --project) SCOPE="project" ;;
        --user)    SCOPE="user" ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)
            sed -n '2,8p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

if [ "$SCOPE" = "user" ]; then
    SKILL_DIR="$CODEX_HOME_DIR/skills/$SKILL_NAME"
else
    SKILL_DIR="$REPO_DIR/.codex/skills/$SKILL_NAME"
fi

SOURCE_SKILL_DIR="$REPO_DIR/skills/$SKILL_NAME"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

if [ "$UNINSTALL" = "1" ]; then
    rm -rf "$SKILL_DIR"
    log "Removed $SKILL_DIR"
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
  default_prompt: "Use $paper-fetch-skill when you need the text of a specific paper and only have a DOI, URL, or title."
EOF

echo
echo "Next steps:"
echo "  1. Restart Codex so it rescans installed skills."
echo "  2. If you want MCP tools, register a stdio server that runs 'paper-fetch-mcp'."
echo "  3. Re-run this installer after upgrading the repo to install the new package build."
