#!/usr/bin/env bash
# One-shot installer for the paper-fetch-skill Codex skill.
#
# Usage:
#   ./install-codex.sh              # user-scope skill (~/.codex/skills/…)
#   ./install-codex.sh --project    # project-scope skill (./.codex/skills/…)
#   ./install-codex.sh --no-node    # skip Node fallback (mathml-to-latex will not be installed)
#   ./install-codex.sh --uninstall  # remove the installed skill entry

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="paper-fetch-skill"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SCOPE="user"
INSTALL_NODE=1
UNINSTALL=0

for arg in "$@"; do
    case "$arg" in
        --project) SCOPE="project" ;;
        --user)    SCOPE="user" ;;
        --no-node) INSTALL_NODE=0 ;;
        --uninstall) UNINSTALL=1 ;;
        -h|--help)
            sed -n '2,9p' "$0"
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [ "$SCOPE" = "user" ]; then
    SKILL_DIR="$CODEX_HOME_DIR/skills/$SKILL_NAME"
else
    SKILL_DIR="$REPO_DIR/.codex/skills/$SKILL_NAME"
fi

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

if [ "$UNINSTALL" = "1" ]; then
    if [ -e "$SKILL_DIR" ] || [ -L "$SKILL_DIR" ]; then
        rm -rf "$SKILL_DIR"
        log "Removed $SKILL_DIR"
    else
        warn "Nothing to remove at $SKILL_DIR"
    fi
    exit 0
fi

# ---------- 1. check prerequisites ----------
command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH"
PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
log "Using python3 ($PY_VER) at $(command -v python3)"

# ---------- 2. Python venv + deps ----------
VENV_DIR="$REPO_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    log "Creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi
log "Installing Python dependencies"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

# ---------- 3. .env bootstrap ----------
if [ ! -f "$REPO_DIR/.env" ]; then
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
    warn "Created $REPO_DIR/.env from template - edit it to add your API keys."
fi

# ---------- 4. formula backends ----------
FORMULA_INSTALL_ARGS=()
if [ "$INSTALL_NODE" != "1" ]; then
    FORMULA_INSTALL_ARGS+=(--no-node)
fi
bash "$REPO_DIR/install-formula-tools.sh" "${FORMULA_INSTALL_ARGS[@]}"

# ---------- 5. render Codex skill ----------
log "Installing skill to $SKILL_DIR"
mkdir -p "$SKILL_DIR/agents"

PY_BIN="$VENV_DIR/bin/python"
SCRIPT="$REPO_DIR/scripts/paper_fetch.py"
"$PY_BIN" "$REPO_DIR/scripts/render_skill_template.py" \
    --repo-dir "$REPO_DIR" \
    --skill-dir "$SKILL_DIR" \
    --venv-dir "$VENV_DIR" \
    > "$SKILL_DIR/SKILL.md"

if [ -f "$REPO_DIR/agents/openai.yaml" ]; then
    cp "$REPO_DIR/agents/openai.yaml" "$SKILL_DIR/agents/openai.yaml"
else
    cat > "$SKILL_DIR/agents/openai.yaml" <<'EOF'
interface:
  display_name: "Paper Fetch Skill"
  short_description: "Fetch AI-friendly paper text by DOI, URL, or title"
  default_prompt: "Use $paper-fetch-skill when you need the text of a specific paper and only have a DOI, URL, or title."
EOF
fi

log "Done."

if [ "$SCOPE" = "project" ]; then
    warn "Project-scope install writes to $SKILL_DIR, but Codex typically auto-discovers skills from $CODEX_HOME_DIR/skills."
fi

echo
echo "Next steps:"
echo "  1. Edit $REPO_DIR/.env and fill in API keys you have."
echo "  2. Restart Codex so it picks up the new skill."
echo "  3. If you move this repo later, re-run ./install-codex.sh so the skill paths stay valid."
echo "  4. Test: $PY_BIN $SCRIPT --query '10.1038/s41586-020-2649-2'"
