"""Helpers for DOI-safe MCP-visible cached download indexing."""

from __future__ import annotations

import json
import hashlib
import os
import stat
import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from filelock import FileLock

from ..artifacts import ArtifactStore
from ..http.content_types import STRUCTURED_TEXT_MIME_TYPES, content_type_base
from ..publisher_identity import normalize_doi
from ..utils import sanitize_filename
from .markdown_frontmatter import read_markdown_front_matter

INDEX_FILENAME = ".paper-fetch-mcp-cache.json"
LOCK_DIRNAME = ".paper-fetch-locks"
INDEX_LOCK_FILENAME = "cache-index.lock"
INDEX_VERSION = 2
LEGACY_INDEX_VERSIONS = frozenset({1})
CACHE_INDEX_RESOURCE_URI = "resource://paper-fetch/cache-index"
CACHED_RESOURCE_URI_PREFIX = "resource://paper-fetch/cached/"
CACHED_RESOURCE_TEMPLATE = "resource://paper-fetch/cached/{entry_id}"
SCOPED_CACHE_INDEX_RESOURCE_PREFIX = f"{CACHE_INDEX_RESOURCE_URI}/"
SCOPED_CACHED_RESOURCE_URI_PREFIX = "resource://paper-fetch/cached-dir/"
SCOPED_CACHED_RESOURCE_TEMPLATE = (
    "resource://paper-fetch/cached-dir/{scope_id}/{entry_id}"
)
CACHE_INDEX_STATUS_OK = "ok"
CACHE_INDEX_STATUS_MISSING = "missing"
CACHE_INDEX_STATUS_REPAIRED = "repaired"
CACHE_INDEX_STATUS_NEEDS_REPAIR = "needs_repair"
CACHE_INDEX_STATUS_INVALID = "invalid"
CACHE_INDEX_STATUS_VERSION_MISMATCH = "version_mismatch"
CACHE_INDEX_MODE_INDEX = "index"
CACHE_INDEX_MODE_REFRESH = "refresh"
CACHE_INDEX_MODE_RESCAN = "rescan"

IDENTITY_PROOF_DOI_FILENAME = "doi_filename"
IDENTITY_PROOF_FETCH_ENVELOPE = "fetch_envelope_payload"
IDENTITY_PROOF_MARKDOWN_FRONT_MATTER = "yaml_front_matter"
IDENTITY_PROOF_MARKDOWN_REGISTRATION = "explicit_registration"

_CONTENT_KINDS = frozenset({"fulltext", "abstract_only", "metadata_only"})
_TEXT_MIME_TYPES = {
    *STRUCTURED_TEXT_MIME_TYPES,
    "image/svg+xml",
}


@dataclass(frozen=True)
class CacheIndexResult:
    entries: list[dict[str, Any]]
    index_status: str
    index_version: int | str | None
    expected_index_version: int = INDEX_VERSION
    index_reason: str | None = None
    cache_mode: str = CACHE_INDEX_MODE_INDEX

    def metadata(self) -> dict[str, Any]:
        return {
            "cache_mode": self.cache_mode,
            "index_status": self.index_status,
            "index_version": self.index_version,
            "expected_index_version": self.expected_index_version,
            "index_reason": self.index_reason,
        }


def cache_index_path(download_dir: Path) -> Path:
    return download_dir / INDEX_FILENAME


def cache_lock_dir(download_dir: Path) -> Path:
    return download_dir / LOCK_DIRNAME


def cache_index_lock_path(download_dir: Path) -> Path:
    return cache_lock_dir(download_dir) / INDEX_LOCK_FILENAME


def fetch_envelope_lock_path(download_dir: Path, doi: str) -> Path:
    digest = sha1(str(doi or "").encode("utf-8", errors="ignore")).hexdigest()[:16]
    return cache_lock_dir(download_dir) / f"fetch-envelope-{digest}.lock"


def cache_file_lock(path: Path) -> FileLock:
    path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(path))


def cached_resource_uri(entry_id: str) -> str:
    return f"{CACHED_RESOURCE_URI_PREFIX}{entry_id}"


def cache_scope_id(download_dir: Path) -> str:
    digest = sha1(
        str(download_dir.expanduser().resolve()).encode("utf-8", errors="ignore")
    ).hexdigest()
    return digest[:12]


def scoped_cache_index_resource_uri(scope_id: str) -> str:
    return f"{SCOPED_CACHE_INDEX_RESOURCE_PREFIX}{scope_id}"


def scoped_cached_resource_uri(scope_id: str, entry_id: str) -> str:
    return f"{SCOPED_CACHED_RESOURCE_URI_PREFIX}{scope_id}/{entry_id}"


def scoped_cached_resource_uri_prefix(scope_id: str) -> str:
    return f"{SCOPED_CACHED_RESOURCE_URI_PREFIX}{scope_id}/"


def is_text_mime_type(mime_type: str | None) -> bool:
    normalized = content_type_base(mime_type)
    return normalized.startswith("text/") or normalized in _TEXT_MIME_TYPES


def guess_mime_type(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _entry_id(*, doi: str, kind: str, path: Path) -> str:
    digest = sha1(
        f"{doi}\0{kind}\0{path.resolve()}".encode("utf-8", errors="ignore")
    ).hexdigest()
    return digest[:16]


def _entry_kind_for_path(path: Path, *, doi: str) -> str:
    base = sanitize_filename(doi)
    if path.parent.name == f"{base}_assets":
        return "asset"
    if path.name == f"{base}.fetch-envelope.json":
        return "fetch_envelope"
    if (
        path.name.startswith(f"{base}.")
        and path.name.endswith(".fetch-envelope.json")
        and len(path.name.removeprefix(f"{base}.").removesuffix(".fetch-envelope.json"))
        == 64
    ):
        # Request-fingerprinted variants are internal candidates. The canonical
        # compatibility sidecar remains the single MCP index entry.
        return "fetch_envelope_variant"
    if path.suffix.lower() == ".md":
        return "markdown"
    return "primary_payload"


def _mtime_as_completed_at(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _build_entry(
    *,
    doi: str,
    kind: str,
    path: Path,
    identity_proof: str,
    source: str | None = None,
    has_fulltext: bool | None = None,
    content_kind: str | None = None,
    completed_at: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    stat = path.stat()
    resolved = path.resolve()
    entry: dict[str, Any] = {
        "id": _entry_id(doi=doi, kind=kind, path=resolved),
        "doi": doi,
        "kind": kind,
        "path": str(resolved),
        "mime": guess_mime_type(resolved),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "identity_proof": identity_proof,
    }
    if kind == "markdown":
        entry.update(
            {
                "source": source,
                "has_fulltext": has_fulltext,
                "content_kind": content_kind,
                "completed_at": completed_at or _mtime_as_completed_at(stat.st_mtime),
                "content_sha256": content_sha256 or _file_sha256(resolved),
            }
        )
    return entry


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        deduped[entry["id"]] = entry
    return sorted(
        deduped.values(),
        key=lambda item: (
            str(item.get("doi") or ""),
            str(item.get("kind") or ""),
            -float(item.get("mtime") or 0.0),
            str(item.get("path") or ""),
        ),
    )


def _write_index_unlocked(
    download_dir: Path,
    entries: list[dict[str, Any]],
    *,
    commit_guard: Callable[[], None] | None = None,
) -> None:
    index_path = cache_index_path(download_dir)
    if not download_dir.exists():
        return
    payload = {
        "version": INDEX_VERSION,
        "entries": _dedupe_entries(entries),
    }
    ArtifactStore.from_download_dir(download_dir).write_json_file(
        index_path,
        payload,
        commit_guard=commit_guard,
    )


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


def _markdown_entry_from_front_matter(
    path: Path, *, expected_doi: str | None = None
) -> dict[str, Any] | None:
    front_matter = read_markdown_front_matter(path)
    if front_matter is None:
        return None
    if expected_doi is not None and front_matter.doi != expected_doi:
        return None
    return _build_entry(
        doi=front_matter.doi,
        kind="markdown",
        path=path,
        identity_proof=IDENTITY_PROOF_MARKDOWN_FRONT_MATTER,
        source=front_matter.source,
        has_fulltext=front_matter.has_fulltext,
        content_kind=front_matter.content_kind,
        completed_at=front_matter.completed_at,
    )


def _registered_markdown_entry(
    path: Path, *, doi: str, raw: dict[str, Any]
) -> dict[str, Any] | None:
    if raw.get("identity_proof") != IDENTITY_PROOF_MARKDOWN_REGISTRATION:
        return None
    source = raw.get("source")
    has_fulltext = raw.get("has_fulltext")
    content_kind = raw.get("content_kind")
    registered_digest = raw.get("content_sha256")
    if not isinstance(source, str) or not source.strip():
        return None
    if not isinstance(has_fulltext, bool):
        return None
    if not isinstance(content_kind, str) or content_kind not in _CONTENT_KINDS:
        return None
    if not isinstance(registered_digest, str) or len(registered_digest) != 64:
        return None
    try:
        current_digest = _file_sha256(path)
    except OSError:
        return None
    if current_digest != registered_digest:
        return None
    completed_at = raw.get("completed_at")
    return _build_entry(
        doi=doi,
        kind="markdown",
        path=path,
        identity_proof=IDENTITY_PROOF_MARKDOWN_REGISTRATION,
        source=source.strip(),
        has_fulltext=has_fulltext,
        content_kind=content_kind,
        completed_at=completed_at if isinstance(completed_at, str) else None,
        content_sha256=current_digest,
    )


def _doi_from_fetch_envelope_sidecar(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    envelope = payload.get("payload")
    if not isinstance(envelope, dict):
        return None
    doi = normalize_doi(str(envelope.get("doi") or ""))
    return doi or None


def _path_proves_non_markdown_doi(
    download_dir: Path, path: Path, *, doi: str, kind: str
) -> bool:
    root = download_dir.expanduser().resolve()
    base = sanitize_filename(doi)
    if kind == "asset":
        try:
            path.relative_to(root / f"{base}_assets")
        except ValueError:
            return False
        return True
    if path.parent != root:
        return False
    if kind == "fetch_envelope":
        return (
            path.name == f"{base}.fetch-envelope.json"
            and _doi_from_fetch_envelope_sidecar(path) == doi
        )
    return kind == "primary_payload" and path.name.startswith(f"{base}.")


def _normalize_existing_entry(download_dir: Path, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    doi = normalize_doi(str(raw.get("doi") or ""))
    path_text = str(raw.get("path") or "").strip()
    if not doi or not path_text:
        return None
    path = _scoped_file(download_dir, path_text)
    if path is None:
        return None

    raw_kind = str(raw.get("kind") or "").strip()
    if raw_kind == "markdown" or path.suffix.lower() == ".md":
        registered = _registered_markdown_entry(path, doi=doi, raw=raw)
        if registered is not None:
            front_matter = read_markdown_front_matter(path)
            if front_matter is not None and front_matter.doi != doi:
                return None
            return registered
        return _markdown_entry_from_front_matter(path, expected_doi=doi)

    kind = _entry_kind_for_path(path, doi=doi)
    if not _path_proves_non_markdown_doi(download_dir, path, doi=doi, kind=kind):
        return None
    proof = (
        IDENTITY_PROOF_FETCH_ENVELOPE
        if kind == "fetch_envelope"
        else IDENTITY_PROOF_DOI_FILENAME
    )
    return _build_entry(
        doi=doi,
        kind=kind,
        path=path,
        identity_proof=proof,
    )


def _coerce_index_version(value: Any) -> int | str | None:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | str):
        return value
    return None


def _index_error_result(
    *,
    status: str,
    reason: str,
    version: Any = None,
    cache_mode: str,
) -> CacheIndexResult:
    return CacheIndexResult(
        entries=[],
        index_status=status,
        index_version=_coerce_index_version(version),
        index_reason=reason,
        cache_mode=cache_mode,
    )


def _normalized_index_entries(
    download_dir: Path, raw_entries: list[Any]
) -> list[dict[str, Any]]:
    entries = [
        entry
        for raw in raw_entries
        if (entry := _normalize_existing_entry(download_dir, raw)) is not None
    ]
    return _dedupe_entries(entries)


def _read_cache_index_unlocked(
    download_dir: Path,
    *,
    repair: bool,
    cache_mode: str,
) -> CacheIndexResult:
    index_path = cache_index_path(download_dir)
    if not index_path.exists():
        return _index_error_result(
            status=CACHE_INDEX_STATUS_MISSING,
            reason="cache index does not exist",
            cache_mode=cache_mode,
        )
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_INVALID,
            reason="cache index is not readable JSON",
            cache_mode=cache_mode,
        )
    if not isinstance(payload, dict):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_INVALID,
            reason="cache index root must be a JSON object",
            cache_mode=cache_mode,
        )
    version = payload.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_VERSION_MISMATCH,
            reason=f"cache index version {version!r} does not match {INDEX_VERSION}",
            version=version,
            cache_mode=cache_mode,
        )
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_INVALID,
            reason="cache index entries must be a list",
            version=version,
            cache_mode=cache_mode,
        )

    if version != INDEX_VERSION:
        if version not in LEGACY_INDEX_VERSIONS or not repair:
            return _index_error_result(
                status=CACHE_INDEX_STATUS_VERSION_MISMATCH,
                reason=(
                    f"cache index version {version!r} does not match {INDEX_VERSION}; "
                    "use cache_mode=rescan"
                ),
                version=version,
                cache_mode=cache_mode,
            )
        migrated = _normalized_index_entries(download_dir, raw_entries)
        _write_index_unlocked(download_dir, migrated)
        return CacheIndexResult(
            entries=migrated,
            index_status=CACHE_INDEX_STATUS_REPAIRED,
            index_version=INDEX_VERSION,
            index_reason=(
                f"cache index version {version} was migrated; unproven Markdown "
                "ownership was discarded"
            ),
            cache_mode=cache_mode,
        )

    deduped = _normalized_index_entries(download_dir, raw_entries)
    if deduped != raw_entries:
        if not repair:
            return CacheIndexResult(
                entries=deduped,
                index_status=CACHE_INDEX_STATUS_NEEDS_REPAIR,
                index_version=version,
                index_reason="cache index contains stale or non-normalized entries",
                cache_mode=cache_mode,
            )
        _write_index_unlocked(download_dir, deduped)
        return CacheIndexResult(
            entries=deduped,
            index_status=CACHE_INDEX_STATUS_REPAIRED,
            index_version=INDEX_VERSION,
            index_reason="cache index entries were normalized",
            cache_mode=cache_mode,
        )
    return CacheIndexResult(
        entries=deduped,
        index_status=CACHE_INDEX_STATUS_OK,
        index_version=version,
        cache_mode=cache_mode,
    )


def read_cache_index(
    download_dir: Path,
    *,
    refresh: bool = False,
    cache_mode: str | None = None,
) -> CacheIndexResult:
    with cache_file_lock(cache_index_lock_path(download_dir)):
        return _read_cache_index_unlocked(
            download_dir,
            repair=refresh,
            cache_mode=cache_mode
            or (CACHE_INDEX_MODE_REFRESH if refresh else CACHE_INDEX_MODE_INDEX),
        )


def _list_cache_entries_unlocked(download_dir: Path) -> list[dict[str, Any]]:
    return _read_cache_index_unlocked(
        download_dir, repair=True, cache_mode=CACHE_INDEX_MODE_REFRESH
    ).entries


def list_cache_entries(download_dir: Path) -> list[dict[str, Any]]:
    with cache_file_lock(cache_index_lock_path(download_dir)):
        return _list_cache_entries_unlocked(download_dir)


def scan_cached_files(
    download_dir: Path, doi: str, *, include_loose_markdown: bool = True
) -> list[dict[str, Any]]:
    """Scan one explicit cache scope for files whose DOI ownership is provable."""

    if not download_dir.exists():
        return []
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        return []
    base = sanitize_filename(normalized_doi)
    entries: list[dict[str, Any]] = []
    checked_markdown_paths: set[Path] = set()

    for path in sorted(download_dir.glob(f"{base}.*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        kind = _entry_kind_for_path(path, doi=normalized_doi)
        if kind == "markdown":
            scoped_path = _scoped_file(download_dir, str(path.resolve()))
            if scoped_path is None:
                continue
            checked_markdown_paths.add(scoped_path)
            entry = _markdown_entry_from_front_matter(
                scoped_path, expected_doi=normalized_doi
            )
            if entry is not None:
                entries.append(entry)
            continue
        if not _path_proves_non_markdown_doi(
            download_dir, path.resolve(), doi=normalized_doi, kind=kind
        ):
            continue
        proof = (
            IDENTITY_PROOF_FETCH_ENVELOPE
            if kind == "fetch_envelope"
            else IDENTITY_PROOF_DOI_FILENAME
        )
        entries.append(
            _build_entry(
                doi=normalized_doi,
                kind=kind,
                path=path,
                identity_proof=proof,
            )
        )

    asset_dir = download_dir / f"{base}_assets"
    if asset_dir.is_dir():
        for path in sorted(asset_dir.rglob("*")):
            if not path.is_file():
                continue
            resolved_path = path.resolve()
            if not _path_proves_non_markdown_doi(
                download_dir,
                resolved_path,
                doi=normalized_doi,
                kind="asset",
            ):
                continue
            entries.append(
                _build_entry(
                    doi=normalized_doi,
                    kind="asset",
                    path=resolved_path,
                    identity_proof=IDENTITY_PROOF_DOI_FILENAME,
                )
            )

    if include_loose_markdown:
        for path in sorted(download_dir.glob("*.md")):
            if not path.is_file() or path.name.endswith(".part"):
                continue
            scoped_path = _scoped_file(download_dir, str(path.resolve()))
            if scoped_path is None or scoped_path in checked_markdown_paths:
                continue
            entry = _markdown_entry_from_front_matter(
                scoped_path, expected_doi=normalized_doi
            )
            if entry is not None:
                entries.append(entry)

    return _dedupe_entries(entries)


def _discover_rescan_dois(
    download_dir: Path, seed_entries: list[dict[str, Any]]
) -> list[str]:
    dois = {
        normalize_doi(str(entry.get("doi") or ""))
        for entry in seed_entries
        if normalize_doi(str(entry.get("doi") or ""))
    }
    for path in sorted(download_dir.glob("*.fetch-envelope.json")):
        doi = _doi_from_fetch_envelope_sidecar(path)
        if doi:
            dois.add(doi)
    for path in sorted(download_dir.glob("*.md")):
        front_matter = read_markdown_front_matter(path)
        if front_matter is not None:
            dois.add(front_matter.doi)
    return sorted(dois)


def _rescan_entries_unlocked(
    download_dir: Path, seed_entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for doi in _discover_rescan_dois(download_dir, seed_entries):
        entries.extend(scan_cached_files(download_dir, doi))
    entries.extend(
        entry
        for entry in seed_entries
        if entry.get("kind") == "markdown"
        and entry.get("identity_proof") == IDENTITY_PROOF_MARKDOWN_REGISTRATION
    )
    return _dedupe_entries(entries)


def rescan_cache_index(download_dir: Path) -> CacheIndexResult:
    if not download_dir.exists():
        return CacheIndexResult(
            entries=[],
            index_status=CACHE_INDEX_STATUS_MISSING,
            index_version=None,
            index_reason="download directory does not exist",
            cache_mode=CACHE_INDEX_MODE_RESCAN,
        )
    with cache_file_lock(cache_index_lock_path(download_dir)):
        seed = _read_cache_index_unlocked(
            download_dir, repair=True, cache_mode=CACHE_INDEX_MODE_RESCAN
        )
        seed_entries = (
            seed.entries
            if seed.index_status
            in {
                CACHE_INDEX_STATUS_OK,
                CACHE_INDEX_STATUS_REPAIRED,
                CACHE_INDEX_STATUS_NEEDS_REPAIR,
            }
            else []
        )
        entries = _rescan_entries_unlocked(download_dir, seed_entries)
        if entries or cache_index_path(download_dir).exists():
            _write_index_unlocked(download_dir, entries)
        return CacheIndexResult(
            entries=entries,
            index_status=CACHE_INDEX_STATUS_OK,
            index_version=INDEX_VERSION,
            cache_mode=CACHE_INDEX_MODE_RESCAN,
        )


def register_markdown_entry(
    download_dir: Path,
    doi: str,
    path: Path,
    *,
    source: str,
    has_fulltext: bool,
    content_kind: str,
    completed_at: str | None = None,
    commit_guard: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    """Register a just-saved Markdown path using the DOI known by the fetch result."""

    normalized_doi = normalize_doi(doi)
    normalized_source = str(source or "").strip()
    normalized_kind = str(content_kind or "").strip().lower()
    scoped_path = _scoped_file(download_dir, str(path))
    if (
        not normalized_doi
        or not normalized_source
        or not isinstance(has_fulltext, bool)
        or normalized_kind not in _CONTENT_KINDS
        or scoped_path is None
        or scoped_path.suffix.lower() != ".md"
    ):
        return None
    front_matter = read_markdown_front_matter(scoped_path)
    if front_matter is not None and front_matter.doi != normalized_doi:
        return None

    entry = _build_entry(
        doi=normalized_doi,
        kind="markdown",
        path=scoped_path,
        identity_proof=IDENTITY_PROOF_MARKDOWN_REGISTRATION,
        source=normalized_source,
        has_fulltext=has_fulltext,
        content_kind=normalized_kind,
        completed_at=completed_at,
    )
    with cache_file_lock(cache_index_lock_path(download_dir)):
        existing = _read_cache_index_unlocked(
            download_dir, repair=True, cache_mode=CACHE_INDEX_MODE_REFRESH
        )
        if existing.index_status in {
            CACHE_INDEX_STATUS_OK,
            CACHE_INDEX_STATUS_REPAIRED,
            CACHE_INDEX_STATUS_MISSING,
        }:
            entries = existing.entries
        else:
            entries = _rescan_entries_unlocked(download_dir, [])
        entry_path = str(scoped_path)
        retained = [
            candidate
            for candidate in entries
            if str(candidate.get("path") or "") != entry_path
        ]
        _write_index_unlocked(
            download_dir,
            [*retained, entry],
            commit_guard=commit_guard,
        )
    return entry


def refresh_cache_index_for_doi_result(
    download_dir: Path, doi: str
) -> CacheIndexResult:
    normalized_doi = normalize_doi(doi)
    if not normalized_doi or not download_dir.exists():
        return CacheIndexResult(
            entries=[],
            index_status=CACHE_INDEX_STATUS_MISSING,
            index_version=None,
            index_reason="download directory does not exist or DOI is empty",
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        )
    with cache_file_lock(cache_index_lock_path(download_dir)):
        existing = _read_cache_index_unlocked(
            download_dir, repair=True, cache_mode=CACHE_INDEX_MODE_REFRESH
        )
        refreshed = scan_cached_files(download_dir, normalized_doi)
        registered = [
            entry
            for entry in existing.entries
            if entry.get("doi") == normalized_doi
            and entry.get("kind") == "markdown"
            and entry.get("identity_proof") == IDENTITY_PROOF_MARKDOWN_REGISTRATION
        ]
        refreshed = _dedupe_entries([*refreshed, *registered])
        if existing.index_status not in {
            CACHE_INDEX_STATUS_OK,
            CACHE_INDEX_STATUS_REPAIRED,
            CACHE_INDEX_STATUS_MISSING,
        }:
            return CacheIndexResult(
                entries=refreshed,
                index_status=existing.index_status,
                index_version=existing.index_version,
                index_reason=existing.index_reason,
                cache_mode=CACHE_INDEX_MODE_REFRESH,
            )
        retained = [
            entry for entry in existing.entries if entry.get("doi") != normalized_doi
        ]
        merged = _dedupe_entries([*retained, *refreshed])
        index_exists = cache_index_path(download_dir).exists()
        if merged or index_exists:
            _write_index_unlocked(download_dir, merged)
        return CacheIndexResult(
            entries=refreshed,
            index_status=(
                CACHE_INDEX_STATUS_REPAIRED
                if existing.index_status == CACHE_INDEX_STATUS_REPAIRED
                else CACHE_INDEX_STATUS_OK
            ),
            index_version=INDEX_VERSION if merged or index_exists else None,
            index_reason=existing.index_reason
            if existing.index_status == CACHE_INDEX_STATUS_REPAIRED
            else None,
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        )


def refresh_cache_index_for_doi(download_dir: Path, doi: str) -> list[dict[str, Any]]:
    return refresh_cache_index_for_doi_result(download_dir, doi).entries


def find_cached_entry(download_dir: Path, entry_id: str) -> dict[str, Any] | None:
    for entry in list_cache_entries(download_dir):
        if entry.get("id") == entry_id:
            return entry
    return None


def _completion_timestamp(entry: dict[str, Any]) -> float:
    completed_at = entry.get("completed_at")
    if isinstance(completed_at, str) and completed_at:
        try:
            parsed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.timestamp()
        except ValueError:
            pass
    return float(entry.get("mtime") or 0.0)


def preferred_cached_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    markdown_entries = [
        entry
        for entry in entries
        if entry.get("kind") == "markdown"
        and entry.get("identity_proof")
        in {
            IDENTITY_PROOF_MARKDOWN_FRONT_MATTER,
            IDENTITY_PROOF_MARKDOWN_REGISTRATION,
        }
    ]
    primary_entries = [
        entry for entry in entries if entry.get("kind") == "primary_payload"
    ]
    assets = [entry for entry in entries if entry.get("kind") == "asset"]

    def newest(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None
        return max(candidates, key=lambda item: float(item.get("mtime") or 0.0))

    preferred_markdown = (
        max(
            markdown_entries,
            key=lambda item: (
                bool(
                    item.get("has_fulltext") is True
                    and item.get("content_kind") == "fulltext"
                ),
                _completion_timestamp(item),
                float(item.get("mtime") or 0.0),
                str(item.get("path") or ""),
            ),
        )
        if markdown_entries
        else None
    )
    return {
        "markdown": preferred_markdown,
        "primary_payload": newest(primary_entries),
        "assets": sorted(assets, key=lambda item: str(item.get("path") or "")),
    }


__all__ = [
    "CACHED_RESOURCE_TEMPLATE",
    "CACHED_RESOURCE_URI_PREFIX",
    "CACHE_INDEX_MODE_INDEX",
    "CACHE_INDEX_MODE_REFRESH",
    "CACHE_INDEX_MODE_RESCAN",
    "CACHE_INDEX_RESOURCE_URI",
    "CACHE_INDEX_STATUS_INVALID",
    "CACHE_INDEX_STATUS_MISSING",
    "CACHE_INDEX_STATUS_NEEDS_REPAIR",
    "CACHE_INDEX_STATUS_OK",
    "CACHE_INDEX_STATUS_REPAIRED",
    "CACHE_INDEX_STATUS_VERSION_MISMATCH",
    "IDENTITY_PROOF_MARKDOWN_FRONT_MATTER",
    "IDENTITY_PROOF_MARKDOWN_REGISTRATION",
    "INDEX_FILENAME",
    "INDEX_VERSION",
    "LOCK_DIRNAME",
    "SCOPED_CACHED_RESOURCE_TEMPLATE",
    "SCOPED_CACHED_RESOURCE_URI_PREFIX",
    "SCOPED_CACHE_INDEX_RESOURCE_PREFIX",
    "CacheIndexResult",
    "cache_file_lock",
    "cache_index_lock_path",
    "cache_index_path",
    "cache_lock_dir",
    "cache_scope_id",
    "cached_resource_uri",
    "fetch_envelope_lock_path",
    "find_cached_entry",
    "guess_mime_type",
    "is_text_mime_type",
    "list_cache_entries",
    "preferred_cached_entries",
    "read_cache_index",
    "read_scoped_file",
    "refresh_cache_index_for_doi",
    "refresh_cache_index_for_doi_result",
    "register_markdown_entry",
    "rescan_cache_index",
    "scan_cached_files",
    "scoped_cache_index_resource_uri",
    "scoped_cached_resource_uri",
    "scoped_cached_resource_uri_prefix",
]
