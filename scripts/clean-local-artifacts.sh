#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/clean-local-artifacts.sh [--dry-run] [--days N] [PATH ...]

Remove local generated artifacts that are ignored by git.

Options:
  --dry-run   Print what would be removed without deleting anything.
  --days N    Only remove paths whose mtime is older than N days.
  -h, --help  Show this help text.

When no PATH is provided, the script targets common ignored local artifact paths.
Every target is checked with git check-ignore before deletion.
USAGE
}

dry_run=0
days=""
targets=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      dry_run=1
      shift
      ;;
    --days)
      if [ "$#" -lt 2 ]; then
        echo "error: --days requires a value" >&2
        exit 2
      fi
      days="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      targets+=("$@")
      break
      ;;
    -*)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      targets+=("$1")
      shift
      ;;
  esac
done

if [ -n "$days" ] && ! [[ "$days" =~ ^[0-9]+$ ]]; then
  echo "error: --days must be a non-negative integer" >&2
  exit 2
fi

if [ "${#targets[@]}" -eq 0 ]; then
  targets=(
    ".pytest_cache"
    ".ruff_cache"
    ".mypy_cache"
    "build"
    "dist"
    "pip-wheel-metadata"
    ".paper-fetch-runs"
    "live-downloads"
    "rollout-*.jsonl"
  )
fi

shopt -s nullglob

expanded=()
for target in "${targets[@]}"; do
  if compgen -G "$target" >/dev/null; then
    while IFS= read -r match; do
      expanded+=("$match")
    done < <(compgen -G "$target")
  elif [ -e "$target" ]; then
    expanded+=("$target")
  fi
done

if [ "${#expanded[@]}" -eq 0 ]; then
  echo "No matching local artifacts."
  exit 0
fi

removed=0
for path in "${expanded[@]}"; do
  if [ ! -e "$path" ]; then
    continue
  fi
  if ! git check-ignore -q -- "$path"; then
    echo "skip (not ignored by git): $path" >&2
    continue
  fi
  if [ -n "$days" ] && ! find "$path" -prune -mtime +"$days" -print -quit | grep -q .; then
    echo "skip (newer than ${days}d): $path"
    continue
  fi
  if [ "$dry_run" -eq 1 ]; then
    echo "would remove: $path"
  else
    rm -rf -- "$path"
    echo "removed: $path"
  fi
  removed=$((removed + 1))
done

if [ "$removed" -eq 0 ]; then
  echo "No ignored local artifacts removed."
fi
