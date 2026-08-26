"""Helpers for DOI-safe MCP-visible cached download indexing."""

from __future__ import annotations

import json
import hashlib
import os
import stat
import mimetypes
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from filelock import FileLock

from ..artifacts import ArtifactStore
from ..capability_scope import PUBLIC_CAPABILITY_SCOPE
from ..http.content_types import STRUCTURED_TEXT_MIME_TYPES, content_type_base
from ..models import AcquisitionProvenance, coerce_acquisition_provenance
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


def _credential_scope(value: Any) -> str:
    return str(value or "").strip() or PUBLIC_CAPABILITY_SCOPE


def cache_entry_visible_for_scopes(
    entry: Mapping[str, Any], allowed_scopes: Sequence[str]
) -> bool:
    """Return whether an index entry is readable by an exact scope or public."""

    raw_scope = entry.get("credential_scope")
    if not isinstance(raw_scope, str) or not raw_scope.strip():
        # Index entries written before capability visibility metadata are
        # ambiguous. Fail closed until a lock-free DOI refresh proves their
        # current sidecar scope and upgrades the entry.
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


def _stat_fingerprint(path: Path) -> dict[str, int]:
    current = path.stat()
    return {
        "device": int(current.st_dev),
        "inode": int(current.st_ino),
        "size": int(current.st_size),
        "mtime_ns": int(current.st_mtime_ns),
    }


def _optional_stat_fingerprint(path: Path) -> dict[str, int] | None:
    try:
        return _stat_fingerprint(path)
    except OSError:
        return None


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


def _credential_scope_from_entry(entry: Mapping[str, Any] | None) -> str | None:
    if entry is None:
        return None
    raw_scope = entry.get("credential_scope")
    if not isinstance(raw_scope, str) or not raw_scope.strip():
        return None
    return _credential_scope(raw_scope)


def _fetch_envelope_scopes_for_doi(
    download_dir: Path,
    doi: str,
) -> frozenset[str]:
    """Return every valid sidecar scope that may own DOI-local artifacts."""

    base = sanitize_filename(doi)
    paths = [
        download_dir / f"{base}.fetch-envelope.json",
        *sorted(download_dir.glob(f"{base}.*.fetch-envelope.json")),
    ]
    scopes: set[str] = set()
    for path in dict.fromkeys(paths):
        identity = _fetch_envelope_sidecar_identity(path)
        if identity is not None and identity[0] == doi:
            scopes.add(identity[1])
    return frozenset(scopes)


def _artifact_credential_scope(
    path: Path,
    *,
    kind: str,
    cached_entry: Mapping[str, Any] | None,
    sidecar_scopes: frozenset[str],
    artifact_write_scope: str | None = None,
    proven_artifact_paths: frozenset[str] = frozenset(),
) -> str | None:
    """Resolve artifact visibility without guessing from the latest canonical.

    An unchanged entry keeps its already-proven scope. A commit may relabel a
    changed entry or a path explicitly proven by its envelope. Otherwise only a
    previously unseen path may inherit a unique sidecar scope; legacy entries and
    multiple variants remain ambiguous and therefore invisible.
    """

    cached_scope = _credential_scope_from_entry(cached_entry)
    if (
        cached_scope is not None
        and cached_entry is not None
        and _entry_matches_stat(cached_entry, path)
    ):
        return cached_scope

    normalized_write_scope = (
        _credential_scope(artifact_write_scope)
        if artifact_write_scope is not None
        else None
    )
    if normalized_write_scope is not None:
        if (
            cached_entry is not None
            and _entry_has_stat_fingerprint(cached_entry)
            and not _entry_matches_stat(cached_entry, path)
        ):
            return normalized_write_scope
        if cached_scope is not None or str(path.resolve()) in proven_artifact_paths:
            return normalized_write_scope
        if cached_entry is None and sidecar_scopes == frozenset(
            {normalized_write_scope}
        ):
            return normalized_write_scope
        return None

    if cached_entry is None and len(sidecar_scopes) == 1:
        return next(iter(sidecar_scopes))
    if kind == "markdown" and cached_entry is None and not sidecar_scopes:
        # A newly discovered, self-identifying local Markdown file has no remote
        # credential provenance. Legacy registered entries are not covered by
        # this branch and remain fail closed when their scope metadata is absent.
        return PUBLIC_CAPABILITY_SCOPE
    return None


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
    *,
    preserve_stale_for_scan: bool = False,
) -> dict[str, Any] | None:
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
        if (
            preserve_stale_for_scan
            and raw.get("identity_proof")
            in {
                IDENTITY_PROOF_MARKDOWN_FRONT_MATTER,
                IDENTITY_PROOF_MARKDOWN_REGISTRATION,
            }
            and isinstance(raw.get("content_sha256"), str)
        ):
            return dict(raw)
        if (
            not _entry_has_stat_fingerprint(raw)
            and raw.get("identity_proof")
            in {
                IDENTITY_PROOF_MARKDOWN_FRONT_MATTER,
                IDENTITY_PROOF_MARKDOWN_REGISTRATION,
            }
            and isinstance(raw.get("content_sha256"), str)
        ):
            # Version-2 manifests predate the additive stat fields. Keep their
            # proven entry until the next lock-free refresh upgrades it.
            return dict(raw)
        if not _entry_matches_stat(raw, path):
            return None
        registered = _registered_markdown_entry(path, doi=doi, raw=raw)
        if registered is not None:
            return registered
        return _markdown_entry_from_front_matter(
            path,
            expected_doi=doi,
            cached_entry=raw,
        )

    kind = _entry_kind_for_path(path, doi=doi)
    if (
        preserve_stale_for_scan
        and raw_kind == kind
        and raw.get("identity_proof")
        in {IDENTITY_PROOF_FETCH_ENVELOPE, IDENTITY_PROOF_DOI_FILENAME}
    ):
        return dict(raw)
    if (
        raw_kind == kind
        and not _entry_has_stat_fingerprint(raw)
        and raw.get("identity_proof")
        in {IDENTITY_PROOF_FETCH_ENVELOPE, IDENTITY_PROOF_DOI_FILENAME}
    ):
        return dict(raw)
    if (
        raw_kind == kind
        and _entry_matches_stat(raw, path)
        and raw.get("identity_proof")
        in {IDENTITY_PROOF_FETCH_ENVELOPE, IDENTITY_PROOF_DOI_FILENAME}
    ):
        return dict(raw)
    if not _path_proves_non_markdown_doi(download_dir, path, doi=doi, kind=kind):
        return None
    proof = (
        IDENTITY_PROOF_FETCH_ENVELOPE
        if kind == "fetch_envelope"
        else IDENTITY_PROOF_DOI_FILENAME
    )
    # A changed non-sidecar file is no longer proven to belong to the scope in
    # its old stat fingerprint. Refresh keeps it ambiguous; an explicit commit
    # uses a stale-preserving snapshot and may bind the change to its write scope.
    normalized_entry_scope = None
    if kind == "fetch_envelope":
        sidecar_identity = _fetch_envelope_sidecar_identity(path)
        if sidecar_identity is None or sidecar_identity[0] != doi:
            return None
        normalized_entry_scope = sidecar_identity[1]
    return _build_entry(
        doi=doi,
        kind=kind,
        path=path,
        identity_proof=proof,
        credential_scope=normalized_entry_scope,
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
    download_dir: Path,
    raw_entries: list[Any],
    *,
    preserve_stale_for_scan: bool = False,
) -> list[dict[str, Any]]:
    entries = [
        entry
        for raw in raw_entries
        if (
            entry := _normalize_existing_entry(
                download_dir,
                raw,
                preserve_stale_for_scan=preserve_stale_for_scan,
            )
        )
        is not None
    ]
    return _dedupe_entries(entries)


def _read_cache_index_unlocked(
    download_dir: Path,
    *,
    repair: bool,
    cache_mode: str,
    preserve_stale_for_scan: bool = False,
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
        migrated = _normalized_index_entries(
            download_dir,
            raw_entries,
            preserve_stale_for_scan=preserve_stale_for_scan,
        )
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

    deduped = _normalized_index_entries(
        download_dir,
        raw_entries,
        preserve_stale_for_scan=preserve_stale_for_scan,
    )
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
    download_dir: Path,
    doi: str,
    *,
    include_loose_markdown: bool = True,
    cached_entries: Sequence[Mapping[str, Any]] = (),
    markdown_cache: dict[Path, dict[str, Any] | None] | None = None,
    artifact_write_scope: str | None = None,
    proven_artifact_paths: Sequence[Path | str] = (),
) -> list[dict[str, Any]]:
    """Scan one explicit cache scope for files whose DOI ownership is provable."""

    if not download_dir.exists():
        return []
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        return []
    base = sanitize_filename(normalized_doi)
    sidecar_scopes = _fetch_envelope_scopes_for_doi(download_dir, normalized_doi)
    entries: list[dict[str, Any]] = []
    checked_markdown_paths: set[Path] = set()
    cached_by_path = {str(entry.get("path") or ""): entry for entry in cached_entries}
    normalized_proven_paths = frozenset(
        str(path)
        for candidate in proven_artifact_paths
        if (
            path := _scoped_file(
                download_dir,
                str(Path(candidate).expanduser().resolve(strict=False)),
            )
        )
        is not None
    )
    parsed_markdown = markdown_cache if markdown_cache is not None else {}

    def markdown_entry(path: Path) -> dict[str, Any] | None:
        if path not in parsed_markdown:
            parsed_markdown[path] = _markdown_entry_from_front_matter(
                path,
                cached_entry=cached_by_path.get(str(path)),
            )
        return parsed_markdown[path]

    for path in sorted(download_dir.glob(f"{base}.*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        kind = _entry_kind_for_path(path, doi=normalized_doi)
        if kind == "markdown":
            scoped_path = _scoped_file(download_dir, str(path.resolve()))
            if scoped_path is None:
                continue
            checked_markdown_paths.add(scoped_path)
            entry = markdown_entry(scoped_path)
            if entry is not None and entry.get("doi") == normalized_doi:
                entry = dict(entry)
                entry_scope = _artifact_credential_scope(
                    scoped_path,
                    kind="markdown",
                    cached_entry=cached_by_path.get(str(scoped_path)),
                    sidecar_scopes=sidecar_scopes,
                    artifact_write_scope=artifact_write_scope,
                    proven_artifact_paths=normalized_proven_paths,
                )
                if entry_scope is None:
                    entry.pop("credential_scope", None)
                else:
                    entry["credential_scope"] = entry_scope
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
        non_markdown_scope: str | None
        if kind == "fetch_envelope":
            sidecar_identity = _fetch_envelope_sidecar_identity(path)
            if sidecar_identity is None or sidecar_identity[0] != normalized_doi:
                continue
            non_markdown_scope = sidecar_identity[1]
        else:
            non_markdown_scope = _artifact_credential_scope(
                path.resolve(),
                kind=kind,
                cached_entry=cached_by_path.get(str(path.resolve())),
                sidecar_scopes=sidecar_scopes,
                artifact_write_scope=artifact_write_scope,
                proven_artifact_paths=normalized_proven_paths,
            )
        entries.append(
            _build_entry(
                doi=normalized_doi,
                kind=kind,
                path=path,
                identity_proof=proof,
                credential_scope=non_markdown_scope,
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
                    credential_scope=_artifact_credential_scope(
                        resolved_path,
                        kind="asset",
                        cached_entry=cached_by_path.get(str(resolved_path)),
                        sidecar_scopes=sidecar_scopes,
                        artifact_write_scope=artifact_write_scope,
                        proven_artifact_paths=normalized_proven_paths,
                    ),
                )
            )

    if include_loose_markdown:
        for path in sorted(download_dir.glob("*.md")):
            if not path.is_file() or path.name.endswith(".part"):
                continue
            scoped_path = _scoped_file(download_dir, str(path.resolve()))
            if scoped_path is None or scoped_path in checked_markdown_paths:
                continue
            entry = markdown_entry(scoped_path)
            if entry is not None and entry.get("doi") == normalized_doi:
                entry = dict(entry)
                entry_scope = _artifact_credential_scope(
                    scoped_path,
                    kind="markdown",
                    cached_entry=cached_by_path.get(str(scoped_path)),
                    sidecar_scopes=sidecar_scopes,
                    artifact_write_scope=artifact_write_scope,
                    proven_artifact_paths=normalized_proven_paths,
                )
                if entry_scope is None:
                    entry.pop("credential_scope", None)
                else:
                    entry["credential_scope"] = entry_scope
                entries.append(entry)

    return _dedupe_entries(entries)


def scan_cached_files_for_dois(
    download_dir: Path,
    dois: Sequence[str],
    *,
    cached_entries: Sequence[Mapping[str, Any]] = (),
) -> dict[str, list[dict[str, Any]]]:
    """Scan a DOI set while opening every loose Markdown file at most once.

    Parsed Markdown identities outside the requested set are returned as
    opportunistic index upserts. Callers still expose results only for the DOI set
    they were asked to refresh.
    """

    normalized_dois = tuple(
        dict.fromkeys(normalized for doi in dois if (normalized := normalize_doi(doi)))
    )
    if not normalized_dois or not download_dir.exists():
        return {doi: [] for doi in normalized_dois}
    cached_by_path = {str(entry.get("path") or ""): entry for entry in cached_entries}
    markdown_cache: dict[Path, dict[str, Any] | None] = {}
    loose_by_doi: dict[str, list[dict[str, Any]]] = {doi: [] for doi in normalized_dois}
    for path in sorted(download_dir.glob("*.md")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        scoped_path = _scoped_file(download_dir, str(path.resolve()))
        if scoped_path is None:
            continue
        entry = _markdown_entry_from_front_matter(
            scoped_path,
            cached_entry=cached_by_path.get(str(scoped_path)),
        )
        if entry is not None:
            entry = dict(entry)
            entry_scope = _artifact_credential_scope(
                scoped_path,
                kind="markdown",
                cached_entry=cached_by_path.get(str(scoped_path)),
                sidecar_scopes=_fetch_envelope_scopes_for_doi(
                    download_dir, str(entry["doi"])
                ),
            )
            if entry_scope is None:
                entry.pop("credential_scope", None)
            else:
                entry["credential_scope"] = entry_scope
        markdown_cache[scoped_path] = entry
        if entry is not None:
            loose_by_doi.setdefault(str(entry["doi"]), []).append(entry)

    scanned: dict[str, list[dict[str, Any]]] = {}
    requested = set(normalized_dois)
    for doi, loose_entries in loose_by_doi.items():
        targeted_entries = (
            scan_cached_files(
                download_dir,
                doi,
                include_loose_markdown=False,
                cached_entries=cached_entries,
                markdown_cache=markdown_cache,
            )
            if doi in requested
            else []
        )
        # DOI-targeted entries know the canonical sidecar capability scope and
        # therefore win over the same loose Markdown identity.
        scanned[doi] = _dedupe_entries([*loose_entries, *targeted_entries])
    return scanned


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
            download_dir,
            repair=True,
            cache_mode=CACHE_INDEX_MODE_RESCAN,
            preserve_stale_for_scan=True,
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
        initial_index_fingerprint = _optional_stat_fingerprint(
            cache_index_path(download_dir)
        )
    discovered_dois = _discover_rescan_dois(download_dir, seed_entries)
    scanned = scan_cached_files_for_dois(
        download_dir,
        discovered_dois,
        cached_entries=seed_entries,
    )
    scanned_entries = _dedupe_entries(
        [
            *(entry for entries in scanned.values() for entry in entries),
            *(
                entry
                for entry in seed_entries
                if entry.get("kind") == "markdown"
                and entry.get("identity_proof") == IDENTITY_PROOF_MARKDOWN_REGISTRATION
                and _entry_matches_stat(entry, Path(str(entry.get("path") or "")))
            ),
        ]
    )
    with cache_file_lock(cache_index_lock_path(download_dir)):
        current = _read_cache_index_unlocked(
            download_dir,
            repair=True,
            cache_mode=CACHE_INDEX_MODE_RESCAN,
        )
        if current.index_status not in {
            CACHE_INDEX_STATUS_OK,
            CACHE_INDEX_STATUS_REPAIRED,
            CACHE_INDEX_STATUS_MISSING,
        }:
            if (
                _optional_stat_fingerprint(cache_index_path(download_dir))
                != initial_index_fingerprint
            ):
                return CacheIndexResult(
                    entries=scanned_entries,
                    index_status=current.index_status,
                    index_version=current.index_version,
                    index_reason=current.index_reason,
                    cache_mode=CACHE_INDEX_MODE_RESCAN,
                )
            # Explicit rescan is the repair path for an unchanged unsupported or
            # malformed manifest. It may replace that original manifest, but not
            # a different invalid manifest written while the scan was in flight.
            current = CacheIndexResult(
                entries=[],
                index_status=CACHE_INDEX_STATUS_MISSING,
                index_version=None,
                cache_mode=CACHE_INDEX_MODE_RESCAN,
            )

        # A rescan deliberately happens outside the global lock. Preserve entries
        # inserted or updated after the initial snapshot, including updates for a
        # DOI that was itself being rescanned. Stat fingerprints make this an
        # exact comparison without reading or hashing file contents under lock.
        snapshot_by_id = {str(entry.get("id") or ""): entry for entry in seed_entries}
        concurrent_updates = [
            entry
            for entry in current.entries
            if snapshot_by_id.get(str(entry.get("id") or "")) != entry
        ]
        valid_scanned_entries = [
            entry
            for entry in scanned_entries
            if _entry_matches_stat(entry, Path(str(entry.get("path") or "")))
        ]
        entries = _dedupe_entries([*valid_scanned_entries, *concurrent_updates])
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
    acquisition: AcquisitionProvenance | None = None,
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
        or (acquisition is not None and normalized_acquisition is None)
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
            # The entry was already built and hashed outside the global lock.
            # An invalid manifest is repaired incrementally without scanning here.
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
    """Incrementally upsert DOI-local artifacts without a global Markdown scan."""

    normalized_doi = normalize_doi(doi)
    if not normalized_doi or not download_dir.exists():
        return []
    with cache_file_lock(cache_index_lock_path(download_dir)):
        snapshot = _read_cache_index_unlocked(
            download_dir,
            repair=True,
            cache_mode=CACHE_INDEX_MODE_REFRESH,
            preserve_stale_for_scan=True,
        )
    normalized_scope = _credential_scope(credential_scope)
    scanned = []
    for entry in scan_cached_files(
        download_dir,
        normalized_doi,
        include_loose_markdown=False,
        cached_entries=snapshot.entries,
        artifact_write_scope=normalized_scope,
        proven_artifact_paths=proven_artifact_paths,
    ):
        scanned.append(dict(entry))
    with cache_file_lock(cache_index_lock_path(download_dir)):
        current = _read_cache_index_unlocked(
            download_dir,
            repair=True,
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        )
        if current.index_status not in {
            CACHE_INDEX_STATUS_OK,
            CACHE_INDEX_STATUS_REPAIRED,
            CACHE_INDEX_STATUS_MISSING,
        }:
            return scanned
        valid_scanned = [
            entry
            for entry in scanned
            if _entry_matches_stat(entry, Path(str(entry.get("path") or "")))
        ]
        if commit_guard is not None:
            commit_guard()
        scanned_by_id = {str(entry.get("id") or ""): entry for entry in valid_scanned}
        for entry in current.entries:
            entry_id = str(entry.get("id") or "")
            if (
                entry_id in scanned_by_id
                and entry.get("kind") == "markdown"
                and entry.get("identity_proof") == IDENTITY_PROOF_MARKDOWN_REGISTRATION
            ):
                # Retain explicit Markdown provenance while updating the scope
                # inherited from the sidecar committed in this same operation.
                preserved = dict(entry)
                scanned_scope = _credential_scope_from_entry(scanned_by_id[entry_id])
                if scanned_scope is None:
                    preserved.pop("credential_scope", None)
                else:
                    preserved["credential_scope"] = scanned_scope
                scanned_by_id[entry_id] = preserved
        # Freshly scanned DOI-local artifacts are ordered last so their final
        # capability scope replaces stale index metadata. Unrelated concurrent
        # entries remain intact.
        merged = _dedupe_entries([*current.entries, *scanned_by_id.values()])
        if merged or cache_index_path(download_dir).exists():
            _write_index_unlocked(
                download_dir,
                merged,
                commit_guard=commit_guard,
            )
    return valid_scanned


def refresh_cache_index_for_dois_result(
    download_dir: Path,
    dois: Sequence[str],
) -> dict[str, CacheIndexResult]:
    """Refresh a DOI set with one lock-free filesystem scan and atomic merge."""

    normalized_dois = tuple(
        dict.fromkeys(normalized for doi in dois if (normalized := normalize_doi(doi)))
    )
    if not normalized_dois or not download_dir.exists():
        return {
            doi: CacheIndexResult(
                entries=[],
                index_status=CACHE_INDEX_STATUS_MISSING,
                index_version=None,
                index_reason="download directory does not exist or DOI is empty",
                cache_mode=CACHE_INDEX_MODE_REFRESH,
            )
            for doi in normalized_dois
        }

    with cache_file_lock(cache_index_lock_path(download_dir)):
        snapshot = _read_cache_index_unlocked(
            download_dir,
            repair=True,
            cache_mode=CACHE_INDEX_MODE_REFRESH,
            preserve_stale_for_scan=True,
        )
    refreshed_by_doi = scan_cached_files_for_dois(
        download_dir,
        normalized_dois,
        cached_entries=snapshot.entries,
    )

    with cache_file_lock(cache_index_lock_path(download_dir)):
        current = _read_cache_index_unlocked(
            download_dir,
            repair=True,
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        )
        if current.index_status not in {
            CACHE_INDEX_STATUS_OK,
            CACHE_INDEX_STATUS_REPAIRED,
            CACHE_INDEX_STATUS_MISSING,
        }:
            return {
                doi: CacheIndexResult(
                    entries=refreshed_by_doi[doi],
                    index_status=current.index_status,
                    index_version=current.index_version,
                    index_reason=current.index_reason,
                    cache_mode=CACHE_INDEX_MODE_REFRESH,
                )
                for doi in normalized_dois
            }
        requested = set(normalized_dois)
        repaired = current.index_status == CACHE_INDEX_STATUS_REPAIRED or (
            snapshot.index_status == CACHE_INDEX_STATUS_REPAIRED
        )
        repair_reason = current.index_reason or snapshot.index_reason
        retained = [
            entry for entry in current.entries if entry.get("doi") not in requested
        ]
        opportunistic = [
            entry
            for doi, entries in refreshed_by_doi.items()
            if doi not in requested
            for entry in entries
            if _entry_matches_stat(entry, Path(str(entry.get("path") or "")))
        ]
        snapshot_by_id = {
            str(entry.get("id") or ""): entry for entry in snapshot.entries
        }
        results: dict[str, CacheIndexResult] = {}
        merged_refreshed: list[dict[str, Any]] = []
        for doi in normalized_dois:
            valid_refreshed = [
                entry
                for entry in refreshed_by_doi[doi]
                if _entry_matches_stat(entry, Path(str(entry.get("path") or "")))
            ]
            refreshed_by_id = {
                str(entry.get("id") or ""): entry for entry in valid_refreshed
            }
            registered: list[dict[str, Any]] = []
            for entry in current.entries:
                if not (
                    entry.get("doi") == doi
                    and entry.get("kind") == "markdown"
                    and entry.get("identity_proof")
                    == IDENTITY_PROOF_MARKDOWN_REGISTRATION
                    and _entry_matches_stat(entry, Path(str(entry.get("path") or "")))
                ):
                    continue
                preserved = dict(entry)
                refreshed_entry = refreshed_by_id.get(str(entry.get("id") or ""))
                if refreshed_entry is not None:
                    refreshed_scope = _credential_scope_from_entry(refreshed_entry)
                    if refreshed_scope is None:
                        preserved.pop("credential_scope", None)
                    else:
                        preserved["credential_scope"] = refreshed_scope
                registered.append(preserved)
            concurrent_updates = [
                entry
                for entry in current.entries
                if entry.get("doi") == doi
                and snapshot_by_id.get(str(entry.get("id") or "")) != entry
            ]
            refreshed = _dedupe_entries(
                [*valid_refreshed, *registered, *concurrent_updates]
            )
            merged_refreshed.extend(refreshed)
            results[doi] = CacheIndexResult(
                entries=refreshed,
                index_status=(
                    CACHE_INDEX_STATUS_REPAIRED if repaired else CACHE_INDEX_STATUS_OK
                ),
                index_version=INDEX_VERSION,
                index_reason=(repair_reason if repaired else None),
                cache_mode=CACHE_INDEX_MODE_REFRESH,
            )
        # Existing concurrent/explicit registrations win over opportunistically
        # parsed front matter for the same path; requested refreshed entries then
        # replace their old snapshot.
        merged = _dedupe_entries([*opportunistic, *retained, *merged_refreshed])
        index_exists = cache_index_path(download_dir).exists()
        if merged or index_exists:
            _write_index_unlocked(download_dir, merged)
        if not merged and not index_exists:
            results = {
                doi: CacheIndexResult(
                    entries=result.entries,
                    index_status=result.index_status,
                    index_version=None,
                    index_reason=result.index_reason,
                    cache_mode=result.cache_mode,
                )
                for doi, result in results.items()
            }
        return results


def refresh_cache_index_for_doi_result(
    download_dir: Path, doi: str
) -> CacheIndexResult:
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        return CacheIndexResult(
            entries=[],
            index_status=CACHE_INDEX_STATUS_MISSING,
            index_version=None,
            index_reason="download directory does not exist or DOI is empty",
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        )
    return refresh_cache_index_for_dois_result(download_dir, [normalized_doi]).get(
        normalized_doi,
        CacheIndexResult(
            entries=[],
            index_status=CACHE_INDEX_STATUS_MISSING,
            index_version=None,
            index_reason="download directory does not exist or DOI is empty",
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        ),
    )


def refresh_cache_index_for_doi(download_dir: Path, doi: str) -> list[dict[str, Any]]:
    return refresh_cache_index_for_doi_result(download_dir, doi).entries


def refresh_cache_index_for_dois(
    download_dir: Path, dois: Sequence[str]
) -> dict[str, list[dict[str, Any]]]:
    return {
        doi: result.entries
        for doi, result in refresh_cache_index_for_dois_result(
            download_dir, dois
        ).items()
    }


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
    "cache_entry_visible_for_scopes",
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
    "refresh_cache_index_for_dois",
    "refresh_cache_index_for_dois_result",
    "register_cache_files_for_doi",
    "register_markdown_entry",
    "rescan_cache_index",
    "scan_cached_files",
    "scan_cached_files_for_dois",
    "scoped_cache_index_resource_uri",
    "scoped_cached_resource_uri",
    "scoped_cached_resource_uri_prefix",
]
