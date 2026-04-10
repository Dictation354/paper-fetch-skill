#!/usr/bin/env bash
# One-shot installer for the paper-fetch-skill Claude Code skill.
#
# Usage:
#   ./install.sh              # user-scope skill (~/.claude/skills/…)
#   ./install.sh --project    # project-scope skill (./.claude/skills/…)
#   ./install.sh --no-node    # skip Node fallback (mathml-to-latex will not be installed)
#   ./install.sh --uninstall  # remove the installed skill entry

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="paper-fetch-skill"
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
            sed -n '2,10p' "$0"; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [ "$SCOPE" = "user" ]; then
    SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"
else
    SKILL_DIR="$REPO_DIR/.claude/skills/$SKILL_NAME"
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
    warn "Created $REPO_DIR/.env from template — edit it to add your API keys."
fi

# ---------- 4. formula backends ----------
FORMULA_INSTALL_ARGS=()
if [ "$INSTALL_NODE" != "1" ]; then
    FORMULA_INSTALL_ARGS+=(--no-node)
fi
bash "$REPO_DIR/install-formula-tools.sh" "${FORMULA_INSTALL_ARGS[@]}"

# ---------- 5. render SKILL.md with absolute paths ----------
log "Installing skill to $SKILL_DIR"
mkdir -p "$SKILL_DIR"

PY_BIN="$VENV_DIR/bin/python"
SCRIPT="$REPO_DIR/scripts/paper_fetch.py"
"$PY_BIN" "$REPO_DIR/scripts/render_skill_template.py" \
    --repo-dir "$REPO_DIR" \
    --skill-dir "$SKILL_DIR" \
    --venv-dir "$VENV_DIR" \
    > "$SKILL_DIR/SKILL.md"

log "Done."

# ---------- 6. sanity check: is Claude Code likely to see it? ----------
if [ "$SCOPE" = "user" ]; then
    if [ ! -d "$HOME/.claude" ]; then
        warn "$HOME/.claude does not exist yet — run Claude Code once before using the skill."
    elif [ -f "$HOME/.claude/settings.json" ] && command -v grep >/dev/null 2>&1; then
        if grep -q '"enabledPlugins"\|"disabledSkills"' "$HOME/.claude/settings.json" 2>/dev/null; then
            warn "Your ~/.claude/settings.json has skill toggles — verify '$SKILL_NAME' is not disabled."
        fi
    fi
fi

echo
echo "Next steps:"
echo "  1. Edit $REPO_DIR/.env and fill in API keys you have."
echo "  2. Restart Claude Code so it picks up the new skill."
echo "  3. If you move this repo later, re-run ./install.sh so the skill paths stay valid."
echo "  4. Test: $PY_BIN $SCRIPT --query '10.1038/s41586-020-2649-2'"
