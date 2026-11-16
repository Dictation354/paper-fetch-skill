#!/usr/bin/env bash
# Install the static paper-fetch skill for Codex.
#
# Usage:
#   ./scripts/install-codex-skill.sh              # user-scope skill (~/.agents/skills/...)
#   ./scripts/install-codex-skill.sh --project    # project-scope skill (./.agents/skills/...)
#   ./scripts/install-codex-skill.sh --check        # read-only user-scope drift check
#   ./scripts/install-codex-skill.sh --project --check
#   ./scripts/install-codex-skill.sh --uninstall  # remove the installed skill entry

set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_skill_install_common.sh"

PF_HOST="codex"
PF_RESTART_NAME="Codex"
PF_PROJECT_SKILLS_PARENT=".agents"

pf_skill_main "$@"
