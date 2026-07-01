#!/usr/bin/env bash
# Verify an offline installer or macOS tarball in a temporary installation.

set -euo pipefail

PACKAGE_PATH="${1:-}"
SKIP_FETCH_SMOKE="${PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE:-0}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

if [ -z "$PACKAGE_PATH" ]; then
  die "Usage: scripts/verify-offline-package.sh <offline-installer.sh|offline-bundle.tar.gz>"
fi

PACKAGE_PATH="$(cd "$(dirname "$PACKAGE_PATH")" && pwd)/$(basename "$PACKAGE_PATH")"
[ -f "$PACKAGE_PATH" ] || die "Package not found: $PACKAGE_PATH"

TMP_ROOT="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

EXTRACT_ROOT="$TMP_ROOT/extracted"
INSTALLER_PATH="$PACKAGE_PATH"
case "$PACKAGE_PATH" in
  *.tar.gz|*.tgz)
    mkdir -p "$EXTRACT_ROOT"
    log "Extracting offline bundle"
    tar -xzf "$PACKAGE_PATH" -C "$EXTRACT_ROOT"
    extracted_count=0
    bundle_root=""
    while IFS= read -r extracted_dir; do
      extracted_count=$((extracted_count + 1))
      bundle_root="$extracted_dir"
    done < <(find "$EXTRACT_ROOT" -mindepth 1 -maxdepth 1 -type d | sort)
    [ "$extracted_count" -eq 1 ] || die "Expected exactly one top-level directory in offline bundle."
    INSTALLER_PATH="$bundle_root/install-offline.sh"
    [ -x "$INSTALLER_PATH" ] || die "Offline bundle is missing executable install-offline.sh."
    ;;
  *.sh) ;;
  *) die "Unsupported offline package extension: $PACKAGE_PATH" ;;
esac

INSTALL_ROOT="$TMP_ROOT/install-root"
RUNTIME_PYTHON="$INSTALL_ROOT/runtime/paper-fetch-python"
mkdir -p "$INSTALL_ROOT/src" "$INSTALL_ROOT/tests" "$INSTALL_ROOT/wheelhouse" "$INSTALL_ROOT/dist"
printf 'ELSEVIER_API_KEY="secret"\nUSER_NOTE="keep"\n' > "$INSTALL_ROOT/offline.env"

GUARD_DIR="$(mktemp -d)"
FAKE_HOME="$TMP_ROOT/home"
FAKE_CLI_LOG="$TMP_ROOT/mcp-cli.log"
mkdir -p "$FAKE_HOME"
for name in curl git npm npx playwright; do
  cat > "$GUARD_DIR/$name" <<'EOF'
#!/usr/bin/env bash
echo "offline installer attempted a blocked network/build command: $(basename "$0") $*" >&2
exit 97
EOF
  chmod +x "$GUARD_DIR/$name"
done
for name in codex claude; do
  cat > "$GUARD_DIR/$name" <<'EOF'
#!/usr/bin/env bash
{
  printf '%s' "$(basename "$0")"
  for arg in "$@"; do
    printf ' %s' "$arg"
  done
  printf '\n'
} >> "$PAPER_FETCH_FAKE_CLI_LOG"
exit 0
EOF
  chmod +x "$GUARD_DIR/$name"
done

log "Running installer with network/build command guard"
export HOME="$FAKE_HOME"
export SHELL="/bin/bash"
export PAPER_FETCH_FAKE_CLI_LOG="$FAKE_CLI_LOG"
PATH="$GUARD_DIR:$PATH" "$INSTALLER_PATH" --install-dir "$INSTALL_ROOT" --preset=headless --no-user-config

log "Verifying installed runtime package layout"
[ -d "$INSTALL_ROOT/runtime/site-packages/paper_fetch" ] || die "Offline install is missing installed paper_fetch runtime."
[ -x "$RUNTIME_PYTHON" ] || die "Offline install is missing private Python launcher."
[ ! -e "$INSTALL_ROOT/bin/python" ] || die "Offline install should not expose a generic Python wrapper."
[ -x "$INSTALL_ROOT/install-offline.sh" ] || die "Offline install is missing installed installer."
[ ! -d "$INSTALL_ROOT/src" ] || die "Offline install should not include the source tree."
[ ! -d "$INSTALL_ROOT/tests" ] || die "Offline install should not include tests."
[ ! -d "$INSTALL_ROOT/wheelhouse" ] || die "Offline install should not include the build wheelhouse."
[ ! -d "$INSTALL_ROOT/dist" ] || die "Offline install should not include dist."
grep -F -q 'ELSEVIER_API_KEY="secret"' "$INSTALL_ROOT/offline.env"
grep -F -q 'USER_NOTE="keep"' "$INSTALL_ROOT/offline.env"
expected_browser_user_agent='PAPER_FETCH_BROWSER_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"'
grep -F -q "$expected_browser_user_agent" "$INSTALL_ROOT/offline.env" || die "Offline install did not enable default browser UA."
if grep -E -q '^[[:space:]]*#.*PAPER_FETCH_BROWSER_USER_AGENT' "$INSTALL_ROOT/offline.env"; then
  die "Offline install left default browser UA commented."
fi

log "Verifying user shell, skill, and MCP registration"
grep -F -q "export PAPER_FETCH_ENV_FILE=\"$INSTALL_ROOT/offline.env\"" "$FAKE_HOME/.bashrc"
grep -F -q "export CLOAKBROWSER_HEADLESS=\"true\"" "$FAKE_HOME/.bashrc"
grep -F -q "$INSTALL_ROOT/bin" "$FAKE_HOME/.bashrc"
grep -F -q "$INSTALL_ROOT/formula-tools/bin" "$FAKE_HOME/.bashrc"
grep -F -q "$INSTALL_ROOT/image-tools/bin" "$FAKE_HOME/.bashrc"
[ -f "$FAKE_HOME/.codex/skills/paper-fetch-skill/SKILL.md" ] || die "Codex skill was not installed."
[ -f "$FAKE_HOME/.claude/skills/paper-fetch-skill/SKILL.md" ] || die "Claude skill was not installed."
grep -F -q "codex mcp remove paper-fetch" "$FAKE_CLI_LOG"
grep -F -q "codex mcp add" "$FAKE_CLI_LOG"
grep -F -q "claude mcp remove -s user paper-fetch" "$FAKE_CLI_LOG"
grep -F -q "claude mcp add -s user" "$FAKE_CLI_LOG"
grep -F -q "PAPER_FETCH_ENV_FILE=$INSTALL_ROOT/offline.env" "$FAKE_CLI_LOG"
grep -F -q "PAPER_FETCH_FORMULA_TOOLS_DIR=$INSTALL_ROOT/formula-tools" "$FAKE_CLI_LOG"
grep -F -q "PAPER_FETCH_IMAGE_TOOLS_DIR=$INSTALL_ROOT/image-tools" "$FAKE_CLI_LOG"
grep -F -q "MATHML_TO_LATEX_NODE_BIN=" "$FAKE_CLI_LOG"
grep -F -q "CLOAKBROWSER_HEADLESS=true" "$FAKE_CLI_LOG"

# shellcheck disable=SC1091
source "$INSTALL_ROOT/activate-offline.sh"

log "Verifying command entrypoints"
paper-fetch --help >/dev/null
texmath --help >/dev/null
paper-fetch-install-image-tools --target-dir "$INSTALL_ROOT/image-tools" >/dev/null

log "Verifying browser runtime package entrypoint"
"$RUNTIME_PYTHON" - <<'PY'
import cloakbrowser
import playwright

from paper_fetch.runtime_browser import BrowserContextManager

assert hasattr(cloakbrowser, "ensure_binary")
assert BrowserContextManager is not None
PY

log "Verifying provider_status payload entrypoint"
"$RUNTIME_PYTHON" - <<'PY'
from paper_fetch.mcp.fetch_tool import provider_status_payload

payload = provider_status_payload()
assert "providers" in payload, payload
assert payload["providers"], payload
PY

if [ "$SKIP_FETCH_SMOKE" != "1" ]; then
  log "Running paper-fetch DOI smoke"
  paper-fetch --query "10.1186/1471-2105-11-421" --format json --output "$TMP_ROOT/fetch-smoke.json"
  "$RUNTIME_PYTHON" - "$TMP_ROOT/fetch-smoke.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload.get("doi") or payload.get("metadata", {}).get("doi"), payload.keys()
PY
fi

log "Verifying user-level uninstall"
: > "$FAKE_CLI_LOG"
PATH="$GUARD_DIR:$PATH" "$INSTALL_ROOT/install-offline.sh" --install-dir "$INSTALL_ROOT" --uninstall
[ -f "$FAKE_HOME/.bashrc" ] || die "Bash startup file was removed."
if grep -F -q "# BEGIN paper-fetch offline managed" "$FAKE_HOME/.bashrc"; then
  die "Managed shell block was not removed from .bashrc."
fi
[ ! -d "$FAKE_HOME/.codex/skills/paper-fetch-skill" ] || die "Codex skill was not removed."
[ ! -d "$FAKE_HOME/.claude/skills/paper-fetch-skill" ] || die "Claude skill was not removed."
grep -F -q "codex mcp remove paper-fetch" "$FAKE_CLI_LOG"
grep -F -q "claude mcp remove -s user paper-fetch" "$FAKE_CLI_LOG"
[ -f "$INSTALL_ROOT/offline.env" ] || die "Uninstall removed offline.env."
[ -x "$RUNTIME_PYTHON" ] || die "Uninstall removed private Python launcher."
[ ! -e "$INSTALL_ROOT/bin/python" ] || die "Uninstall should not restore a generic Python wrapper."
[ -d "$INSTALL_ROOT/runtime/site-packages" ] || die "Uninstall removed package runtime."

log "Verifying purge removes the install directory"
PATH="$GUARD_DIR:$PATH" "$INSTALLER_PATH" --install-dir "$INSTALL_ROOT" --purge
[ ! -e "$INSTALL_ROOT" ] || die "Purge did not remove the install directory."

log "Offline package verification completed"
