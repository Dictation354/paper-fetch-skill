"""Scope-bounded regular file reads and per-DOI sidecar file locks."""

from __future__ import annotations

import hashlib
import os
import stat
from hashlib import sha1
from pathlib import Path

from filelock import FileLock

LOCK_DIRNAME = ".paper-fetch-locks"


def cache_lock_dir(download_dir: Path) -> Path:
    return download_dir / LOCK_DIRNAME


def fetch_envelope_lock_path(download_dir: Path, doi: str) -> Path:
    digest = sha1(str(doi or "").encode("utf-8", errors="ignore")).hexdigest()[:16]
    return cache_lock_dir(download_dir) / f"fetch-envelope-{digest}.lock"


def cache_file_lock(path: Path) -> FileLock:
    path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(path))


def _scoped_file(download_dir: Path, path_text: str) -> Path | None:
    root_alias = download_dir.expanduser().absolute()
    try:
        root = root_alias.resolve(strict=True)
    except OSError:
        return None
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        working_directory_candidate = path.absolute()
        if any(
            working_directory_candidate.is_relative_to(candidate_root)
            for candidate_root in (root_alias, root)
        ):
            path = working_directory_candidate
        else:
            path = root_alias / path
    try:
        absolute = path.absolute()
        for candidate_root in (root_alias, root):
            try:
                relative = absolute.relative_to(candidate_root)
            except ValueError:
                continue
            lexical_root = candidate_root
            break
        else:
            return None
        current = lexical_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return None
        resolved = absolute.resolve(strict=True)
        resolved.relative_to(root)
        mode = resolved.lstat().st_mode
    except (OSError, ValueError):
        return None
    if not stat.S_ISREG(mode):
        return None
    return resolved


def read_scoped_file(
    download_dir: Path,
    path_text: str,
    *,
    max_bytes: int | None = None,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
) -> tuple[Path, bytes] | None:
    """Open a scope-owned regular file without following a final symlink."""

    resolved = _scoped_file(download_dir, path_text)
    if resolved is None:
        return None
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(resolved, flags)
    except OSError:
        return None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            return None
        size = int(before.st_size)
        if expected_size is not None and size != int(expected_size):
            return None
        if max_bytes is not None and size > max(0, int(max_bytes)):
            return None
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
        ):
            return None
        payload = b"".join(chunks)
        normalized_hash = str(expected_sha256 or "").strip().lower()
        if normalized_hash and hashlib.sha256(payload).hexdigest() != normalized_hash:
            return None
        return resolved, payload
    except OSError:
        return None
    finally:
        os.close(descriptor)


__all__ = [
    "LOCK_DIRNAME",
    "_scoped_file",
    "cache_file_lock",
    "cache_lock_dir",
    "fetch_envelope_lock_path",
    "read_scoped_file",
]
