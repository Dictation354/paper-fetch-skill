#!/usr/bin/env bash
# Install formula conversion backends for paper-fetch-skill.
#
# Preferred order:
#   1. texmath (compiled locally via cabal or stack, or reused from PATH)
#   2. mathml-to-latex (Node fallback)
#   3. built-in Python MathML renderer

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m paper_fetch.formula.install --target-dir "$REPO_DIR/.formula-tools" "$@"
