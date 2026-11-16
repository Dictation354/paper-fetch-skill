#!/usr/bin/env bash
# Install the static paper-fetch skill for Claude Code.
#
# Usage:
#   ./scripts/install-claude-skill.sh              # user-scope skill (~/.claude/skills/...)
#   ./scripts/install-claude-skill.sh --project    # project-scope skill (./.claude/skills/...)
#   ./scripts/install-claude-skill.sh --check        # read-only drift check
#   ./scripts/install-claude-skill.sh --uninstall  # remove the installed skill entry

set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_skill_install_common.sh"

PF_HOST="claude"
PF_RESTART_NAME="Claude Code"

pf_skill_main "$@"
