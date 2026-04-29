#!/usr/bin/env bash
# Verify an offline tarball in a temporary extracted installation.

set -euo pipefail

PACKAGE_PATH="${1:-}"
SKIP_FETCH_SMOKE="${PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE:-0}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

if [ -z "$PACKAGE_PATH" ]; then
  die "Usage: scripts/verify-offline-package.sh <offline-package.tar.gz>"
fi

PACKAGE_PATH="$(cd "$(dirname "$PACKAGE_PATH")" && pwd)/$(basename "$PACKAGE_PATH")"
[ -f "$PACKAGE_PATH" ] || die "Package not found: $PACKAGE_PATH"

TMP_ROOT="$(mktemp -d)"
cleanup() {
  if [ -n "${EXTRACTED_ROOT:-}" ] && [ -x "$EXTRACTED_ROOT/scripts/flaresolverr-down" ]; then
    bash "$EXTRACTED_ROOT/scripts/flaresolverr-down" "$EXTRACTED_ROOT/vendor/flaresolverr/.env.flaresolverr-source-headless" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

log "Extracting $PACKAGE_PATH"
tar -xzf "$PACKAGE_PATH" -C "$TMP_ROOT"
EXTRACTED_ROOT="$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
[ -n "$EXTRACTED_ROOT" ] || die "Could not locate extracted package root."

GUARD_DIR="$(mktemp -d)"
for name in curl git npm npx playwright; do
  cat > "$GUARD_DIR/$name" <<'EOF'
#!/usr/bin/env bash
echo "offline installer attempted a blocked network/build command: $(basename "$0") $*" >&2
exit 97
EOF
  chmod +x "$GUARD_DIR/$name"
done

log "Running installer with network/build command guard"
PATH="$GUARD_DIR:$PATH" "$EXTRACTED_ROOT/install-offline.sh" --preset=headless --no-user-config

# shellcheck disable=SC1091
source "$EXTRACTED_ROOT/activate-offline.sh"

case "$PLAYWRIGHT_BROWSERS_PATH" in
  "$HOME"/.cache/ms-playwright|"$HOME"/.cache/ms-playwright/*)
    die "PLAYWRIGHT_BROWSERS_PATH points at user cache: $PLAYWRIGHT_BROWSERS_PATH"
    ;;
esac

log "Verifying command entrypoints"
paper-fetch --help >/dev/null
texmath --help >/dev/null

log "Verifying provider_status payload entrypoint"
python - <<'PY'
from paper_fetch.mcp.tools import provider_status_payload

payload = provider_status_payload()
assert "providers" in payload, payload
assert payload["providers"], payload
PY

log "Verifying bundled Playwright executable"
python - <<'PY'
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]).resolve()
manager = sync_playwright().start()
try:
    executable = Path(manager.chromium.executable_path).resolve()
finally:
    manager.stop()

assert executable.is_file(), executable
assert root in executable.parents, (root, executable)
PY

log "Starting FlareSolverr from bundled snapshot"
bash "$EXTRACTED_ROOT/scripts/flaresolverr-up" "$EXTRACTED_ROOT/vendor/flaresolverr/.env.flaresolverr-source-headless"

log "Verifying FlareSolverr sessions.list"
status_payload="$(bash "$EXTRACTED_ROOT/scripts/flaresolverr-status" "$EXTRACTED_ROOT/vendor/flaresolverr/.env.flaresolverr-source-headless")"
printf '%s\n' "$status_payload" | python -c 'import json, sys; payload=json.load(sys.stdin); assert payload.get("status") == "ok", payload'

if [ "$SKIP_FETCH_SMOKE" != "1" ]; then
  log "Running paper-fetch DOI smoke"
  paper-fetch --query "10.1186/1471-2105-11-421" --format json --output "$TMP_ROOT/fetch-smoke.json"
  python - "$TMP_ROOT/fetch-smoke.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload.get("doi") or payload.get("metadata", {}).get("doi"), payload.keys()
PY
fi

log "Offline package verification completed"
