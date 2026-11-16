#!/usr/bin/env bash
# Install the static paper-fetch skill for the Antigravity CLI (agy).
#
# Usage:
#   ./scripts/install-antigravity-skill.sh              # user-scope skill (~/.gemini/antigravity-cli/skills/...)
#   ./scripts/install-antigravity-skill.sh --project    # project-scope skill (./.agents/skills/...)
#   ./scripts/install-antigravity-skill.sh --check        # read-only drift check
#   ./scripts/install-antigravity-skill.sh --uninstall  # remove the installed skill entry
#
# Override the global Antigravity config directory with ANTIGRAVITY_HOME
# (defaults to ~/.gemini/antigravity-cli).

set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_skill_install_common.sh"

PF_HOST="antigravity"
PF_RESTART_NAME="the Antigravity CLI (agy)"
# Antigravity reads project-scope skills from .agents/, not .antigravity/.
PF_PROJECT_SKILLS_PARENT=".agents"

pf_skill_main "$@"
