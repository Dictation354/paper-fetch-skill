"""Worker-scope and workspace-change matching rules."""

from __future__ import annotations

from fnmatch import fnmatchcase


def matches_forbidden(path: str, forbidden: list[str]) -> bool:
    normalized = path.strip("/")
    for item in forbidden:
        pattern = item.strip()
        if not pattern:
            continue
        if pattern.endswith("/"):
            base = pattern.strip("/")
            if normalized == base or normalized.startswith(base + "/"):
                return True
            continue
        if normalized == pattern.strip("/") or normalized.startswith(
            pattern.strip("/") + "/"
        ):
            return True
    return False


def forbidden_changes(
    before: set[str],
    after: set[str],
    forbidden: list[str],
) -> list[str]:
    return sorted(path for path in after - before if matches_forbidden(path, forbidden))


def matches_scope(path: str, scope: list[str]) -> bool:
    normalized = path.strip("/")
    for item in scope:
        pattern = item.strip().strip("/")
        if not pattern:
            continue
        if fnmatchcase(normalized, pattern):
            return True
        if pattern.endswith("/**"):
            base = pattern[:-3].strip("/")
            if normalized == base or normalized.startswith(base + "/"):
                return True
        if pattern.endswith("/"):
            base = pattern.strip("/")
            if normalized == base or normalized.startswith(base + "/"):
                return True
        elif normalized == pattern or normalized.startswith(pattern + "/"):
            return True
    return False


def disallowed_changes(
    before: set[str],
    after: set[str],
    allowed: list[str],
) -> list[str]:
    return sorted(path for path in after - before if not matches_scope(path, allowed))


__all__ = [
    "disallowed_changes",
    "forbidden_changes",
    "matches_forbidden",
    "matches_scope",
]
