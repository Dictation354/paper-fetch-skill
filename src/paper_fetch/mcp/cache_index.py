"""Helpers for DOI-safe MCP-visible cached download indexing."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from filelock import FileLock

from ..artifacts import ArtifactStore
from ..capability_scope import PUBLIC_CAPABILITY_SCOPE
from ..models import (
    EXTRACTION_REVISION,
    AcquisitionProvenance,
    coerce_acquisition_provenance,
)
from ..publisher_identity import normalize_doi
from ..utils import sanitize_filename
from .markdown_frontmatter import (
    read_markdown_front_matter,
    read_markdown_front_matter_file,
)

INDEX_FILENAME = ".paper-fetch-mcp-cache.json"
LOCK_DIRNAME = ".paper-fetch-locks"
INDEX_LOCK_FILENAME = "cache-index.lock"
INDEX_VERSION = 2
FETCH_ENVELOPE_CACHE_VERSION = 5
FETCH_ENVELOPE_EXTRACTION_REVISION = EXTRACTION_REVISION
CACHE_INDEX_STATUS_OK = "ok"
CACHE_INDEX_STATUS_MISSING = "missing"
CACHE_INDEX_STATUS_INVALID = "invalid"
CACHE_INDEX_STATUS_VERSION_MISMATCH = "version_mismatch"

IDENTITY_PROOF_DOI_FILENAME = "doi_filename"
IDENTITY_PROOF_FETCH_ENVELOPE = "fetch_envelope_payload"
IDENTITY_PROOF_MARKDOWN_FRONT_MATTER = "yaml_front_matter"
IDENTITY_PROOF_MARKDOWN_REGISTRATION = "explicit_registration"

_CONTENT_KINDS = frozenset({"fulltext", "abstract_only", "metadata_only"})


def _credential_scope(value: Any) -> str:
    return str(value or "").strip() or PUBLIC_CAPABILITY_SCOPE


def cache_entry_visible_for_scopes(
    entry: Mapping[str, Any], allowed_scopes: Sequence[str]
) -> bool:
    """Return whether an index entry is readable by an exact scope or public."""

    raw_scope = entry.get("credential_scope")
    if not isinstance(raw_scope, str) or not raw_scope.strip():
        # Entries without current capability visibility metadata are ambiguous.
        return False
    allowed = {_credential_scope(scope) for scope in allowed_scopes}
    scope = _credential_scope(raw_scope)
    return scope == PUBLIC_CAPABILITY_SCOPE or scope in allowed


@dataclass(frozen=True)
class CacheIndexResult:
    entries: list[dict[str, Any]]
    index_status: str
    index_version: int | str | None
    expected_index_version: int = INDEX_VERSION
    index_reason: str | None = None

    def metadata(self) -> dict[str, Any]:
        return {
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


def _stat_fingerprint(path: Path) -> dict[str, int]:
    current = path.stat()
    return {
        "device": int(current.st_dev),
        "inode": int(current.st_ino),
        "size": int(current.st_size),
        "mtime_ns": int(current.st_mtime_ns),
    }


def _entry_matches_stat(entry: Mapping[str, Any], path: Path) -> bool:
    try:
        current = _stat_fingerprint(path)
    except OSError:
        return False
    return all(entry.get(key) == value for key, value in current.items())


def _entry_has_stat_fingerprint(entry: Mapping[str, Any]) -> bool:
    return all(isinstance(entry.get(key), int) for key in _stat_fingerprint_fields())


def _stat_fingerprint_fields() -> tuple[str, ...]:
    return ("device", "inode", "size", "mtime_ns")


@dataclass(frozen=True, slots=True)
class CacheEntryMetadata:
    """Optional Markdown facts kept together at the index construction boundary."""

    source: str | None = None
    acquisition: AcquisitionProvenance | None = None
    has_fulltext: bool | None = None
    content_kind: str | None = None
    completed_at: str | None = None
    content_sha256: str | None = None
    front_matter_sha256: str | None = None


def _build_entry(
    *,
    doi: str,
    kind: str,
    path: Path,
    identity_proof: str,
    metadata: CacheEntryMetadata | None = None,
    credential_scope: str | None = PUBLIC_CAPABILITY_SCOPE,
) -> dict[str, Any]:
    entry_metadata = metadata or CacheEntryMetadata()
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
        "mtime_ns": stat.st_mtime_ns,
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "identity_proof": identity_proof,
    }
    if credential_scope is not None:
        entry["credential_scope"] = _credential_scope(credential_scope)
    if kind == "markdown":
        entry.update(
            {
                "source": entry_metadata.source,
                "acquisition": (
                    asdict(entry_metadata.acquisition)
                    if entry_metadata.acquisition is not None
                    else None
                ),
                "has_fulltext": entry_metadata.has_fulltext,
                "content_kind": entry_metadata.content_kind,
                "completed_at": entry_metadata.completed_at
                or _mtime_as_completed_at(stat.st_mtime),
                "content_sha256": entry_metadata.content_sha256
                or _file_sha256(resolved),
                "front_matter_sha256": entry_metadata.front_matter_sha256,
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
    path: Path,
    *,
    expected_doi: str | None = None,
    cached_entry: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if (
        cached_entry is not None
        and cached_entry.get("identity_proof") == IDENTITY_PROOF_MARKDOWN_FRONT_MATTER
        and _entry_matches_stat(cached_entry, path)
        and (expected_doi is None or cached_entry.get("doi") == expected_doi)
        and isinstance(cached_entry.get("content_sha256"), str)
        and isinstance(cached_entry.get("front_matter_sha256"), str)
    ):
        return dict(cached_entry)
    opened = read_markdown_front_matter_file(path)
    if opened is None:
        return None
    front_matter = opened.front_matter
    if front_matter is None:
        return None
    if expected_doi is not None and front_matter.doi != expected_doi:
        return None
    return _build_entry(
        doi=front_matter.doi,
        kind="markdown",
        path=path,
        identity_proof=IDENTITY_PROOF_MARKDOWN_FRONT_MATTER,
        metadata=CacheEntryMetadata(
            source=front_matter.source,
            acquisition=front_matter.acquisition,
            has_fulltext=front_matter.has_fulltext,
            content_kind=front_matter.content_kind,
            completed_at=front_matter.completed_at,
            content_sha256=opened.content_sha256,
            front_matter_sha256=opened.front_matter_sha256,
        ),
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
    if _entry_matches_stat(raw, path):
        current_digest = registered_digest
    else:
        try:
            current_digest = _file_sha256(path)
        except OSError:
            return None
    if current_digest != registered_digest:
        return None
    completed_at = raw.get("completed_at")
    raw_acquisition = raw.get("acquisition")
    acquisition = coerce_acquisition_provenance(raw_acquisition)
    if raw_acquisition is not None and acquisition is None:
        return None
    return _build_entry(
        doi=doi,
        kind="markdown",
        path=path,
        identity_proof=IDENTITY_PROOF_MARKDOWN_REGISTRATION,
        metadata=CacheEntryMetadata(
            source=source.strip(),
            acquisition=acquisition,
            has_fulltext=has_fulltext,
            content_kind=content_kind,
            completed_at=completed_at if isinstance(completed_at, str) else None,
            content_sha256=current_digest,
        ),
        credential_scope=(
            _credential_scope(raw.get("credential_scope"))
            if "credential_scope" in raw
            else None
        ),
    )


def _fetch_envelope_sidecar_identity(path: Path) -> tuple[str, str] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("version") != FETCH_ENVELOPE_CACHE_VERSION
        or payload.get("extraction_revision") != FETCH_ENVELOPE_EXTRACTION_REVISION
    ):
        return None
    envelope = payload.get("payload")
    if not isinstance(envelope, dict):
        return None
    doi = normalize_doi(str(envelope.get("doi") or ""))
    if not doi:
        return None
    return doi, _credential_scope(payload.get("credential_scope"))


def _doi_from_fetch_envelope_sidecar(path: Path) -> str | None:
    identity = _fetch_envelope_sidecar_identity(path)
    return identity[0] if identity is not None else None


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


def _normalize_existing_entry(
    download_dir: Path,
    raw: Any,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    doi = normalize_doi(str(raw.get("doi") or ""))
    scope = raw.get("credential_scope")
    path_text = str(raw.get("path") or "").strip()
    if not doi or not isinstance(scope, str) or not scope.strip() or not path_text:
        return None
    path = _scoped_file(download_dir, path_text)
    if path is None or not _entry_has_stat_fingerprint(raw):
        return None

    raw_kind = str(raw.get("kind") or "").strip()
    if raw_kind == "markdown":
        if not _entry_matches_stat(raw, path):
            return None
        if raw.get("identity_proof") == IDENTITY_PROOF_MARKDOWN_REGISTRATION:
            return _registered_markdown_entry(path, doi=doi, raw=raw)
        if raw.get("identity_proof") == IDENTITY_PROOF_MARKDOWN_FRONT_MATTER:
            return _markdown_entry_from_front_matter(
                path,
                expected_doi=doi,
                cached_entry=raw,
            )
        return None

    kind = _entry_kind_for_path(path, doi=doi)
    if raw_kind != kind or not _entry_matches_stat(raw, path):
        return None
    if kind == "fetch_envelope":
        identity = _fetch_envelope_sidecar_identity(path)
        if identity is None or identity != (doi, _credential_scope(scope)):
            return None
        return dict(raw)
    proof = raw.get("identity_proof")
    if proof not in {IDENTITY_PROOF_DOI_FILENAME, IDENTITY_PROOF_FETCH_ENVELOPE}:
        return None
    if proof == IDENTITY_PROOF_DOI_FILENAME and not _path_proves_non_markdown_doi(
        download_dir, path, doi=doi, kind=kind
    ):
        return None
    return dict(raw)


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
) -> CacheIndexResult:
    return CacheIndexResult(
        entries=[],
        index_status=status,
        index_version=_coerce_index_version(version),
        index_reason=reason,
    )


def _normalized_index_entries(
    download_dir: Path,
    raw_entries: list[Any],
) -> list[dict[str, Any]]:
    entries = [
        entry
        for raw in raw_entries
        if (
            entry := _normalize_existing_entry(
                download_dir,
                raw,
            )
        )
        is not None
    ]
    return _dedupe_entries(entries)


def _read_cache_index_unlocked(
    download_dir: Path,
) -> CacheIndexResult:
    index_path = cache_index_path(download_dir)
    if not index_path.exists():
        return _index_error_result(
            status=CACHE_INDEX_STATUS_MISSING,
            reason="cache index does not exist",
        )
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_INVALID,
            reason="cache index is not readable JSON",
        )
    if not isinstance(payload, dict):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_INVALID,
            reason="cache index root must be a JSON object",
        )
    version = payload.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_VERSION_MISMATCH,
            reason=f"cache index version {version!r} does not match {INDEX_VERSION}",
            version=version,
        )
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return _index_error_result(
            status=CACHE_INDEX_STATUS_INVALID,
            reason="cache index entries must be a list",
            version=version,
        )

    if version != INDEX_VERSION:
        return _index_error_result(
            status=CACHE_INDEX_STATUS_VERSION_MISMATCH,
            reason=f"cache index version {version!r} does not match {INDEX_VERSION}",
            version=version,
        )

    deduped = _normalized_index_entries(download_dir, raw_entries)
    if deduped != raw_entries:
        return _index_error_result(
            status=CACHE_INDEX_STATUS_INVALID,
            reason="cache index contains stale, mismatched, or invalid entries",
            version=version,
        )
    return CacheIndexResult(
        entries=deduped,
        index_status=CACHE_INDEX_STATUS_OK,
        index_version=version,
    )


def read_cache_index(download_dir: Path) -> CacheIndexResult:
    with cache_file_lock(cache_index_lock_path(download_dir)):
        return _read_cache_index_unlocked(download_dir)


def _list_cache_entries_unlocked(download_dir: Path) -> list[dict[str, Any]]:
    return _read_cache_index_unlocked(download_dir).entries


def list_cache_entries(download_dir: Path) -> list[dict[str, Any]]:
    with cache_file_lock(cache_index_lock_path(download_dir)):
        return _list_cache_entries_unlocked(download_dir)


def register_markdown_entry(
    download_dir: Path,
    doi: str,
    path: Path,
    *,
    source: str,
    acquisition: AcquisitionProvenance,
    has_fulltext: bool,
    content_kind: str,
    completed_at: str | None = None,
    credential_scope: str = PUBLIC_CAPABILITY_SCOPE,
    commit_guard: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    """Register a just-saved Markdown path using the DOI known by the fetch result."""

    normalized_doi = normalize_doi(doi)
    normalized_source = str(source or "").strip()
    normalized_acquisition = coerce_acquisition_provenance(acquisition)
    normalized_kind = str(content_kind or "").strip().lower()
    scoped_path = _scoped_file(download_dir, str(path))
    if (
        not normalized_doi
        or not normalized_source
        or not isinstance(has_fulltext, bool)
        or normalized_kind not in _CONTENT_KINDS
        or scoped_path is None
        or scoped_path.suffix.lower() != ".md"
        or normalized_acquisition is None
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
        metadata=CacheEntryMetadata(
            source=normalized_source,
            acquisition=normalized_acquisition,
            has_fulltext=has_fulltext,
            content_kind=normalized_kind,
            completed_at=completed_at,
        ),
        credential_scope=credential_scope,
    )
    with cache_file_lock(cache_index_lock_path(download_dir)):
        existing = _read_cache_index_unlocked(download_dir)
        if existing.index_status in {
            CACHE_INDEX_STATUS_OK,
            CACHE_INDEX_STATUS_MISSING,
        }:
            entries = existing.entries
        else:
            entries = []
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


def register_cache_files_for_doi(
    download_dir: Path,
    doi: str,
    *,
    credential_scope: str = PUBLIC_CAPABILITY_SCOPE,
    proven_artifact_paths: Sequence[Path | str] = (),
    commit_guard: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    """Register only files explicitly proven by the completed write path."""

    normalized_doi = normalize_doi(doi)
    if not normalized_doi or not download_dir.exists():
        return []
    normalized_scope = _credential_scope(credential_scope)
    registered: list[dict[str, Any]] = []
    for candidate in proven_artifact_paths:
        path = _scoped_file(download_dir, str(candidate))
        if path is None or path.suffix.lower() == ".md":
            continue
        kind = _entry_kind_for_path(path, doi=normalized_doi)
        if kind == "fetch_envelope_variant":
            continue
        proof = IDENTITY_PROOF_FETCH_ENVELOPE
        if kind == "fetch_envelope":
            identity = _fetch_envelope_sidecar_identity(path)
            if identity != (normalized_doi, normalized_scope):
                continue
        registered.append(
            _build_entry(
                doi=normalized_doi,
                kind=kind,
                path=path,
                identity_proof=proof,
                credential_scope=normalized_scope,
            )
        )

    with cache_file_lock(cache_index_lock_path(download_dir)):
        current = _read_cache_index_unlocked(download_dir)
        if current.index_status in {
            CACHE_INDEX_STATUS_OK,
            CACHE_INDEX_STATUS_MISSING,
        }:
            current_entries = current.entries
        else:
            current_entries = []
        registered_paths = {str(entry["path"]) for entry in registered}
        retained = [
            entry
            for entry in current_entries
            if str(entry.get("path") or "") not in registered_paths
        ]
        if commit_guard is not None:
            commit_guard()
        if registered or cache_index_path(download_dir).exists():
            _write_index_unlocked(
                download_dir,
                [*retained, *registered],
                commit_guard=commit_guard,
            )
    return registered


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
    "CACHE_INDEX_STATUS_INVALID",
    "CACHE_INDEX_STATUS_MISSING",
    "CACHE_INDEX_STATUS_OK",
    "CACHE_INDEX_STATUS_VERSION_MISMATCH",
    "IDENTITY_PROOF_MARKDOWN_FRONT_MATTER",
    "IDENTITY_PROOF_MARKDOWN_REGISTRATION",
    "INDEX_FILENAME",
    "INDEX_VERSION",
    "LOCK_DIRNAME",
    "CacheIndexResult",
    "cache_entry_visible_for_scopes",
    "cache_file_lock",
    "cache_index_lock_path",
    "cache_index_path",
    "cache_lock_dir",
    "fetch_envelope_lock_path",
    "find_cached_entry",
    "guess_mime_type",
    "list_cache_entries",
    "preferred_cached_entries",
    "read_cache_index",
    "read_scoped_file",
    "register_cache_files_for_doi",
    "register_markdown_entry",
]
