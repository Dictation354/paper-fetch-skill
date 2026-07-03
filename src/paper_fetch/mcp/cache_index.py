"""Helpers for MCP-visible cached download indexing."""

from __future__ import annotations

import json
import mimetypes
from hashlib import sha1
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from filelock import FileLock

from ..artifacts import ArtifactStore
from ..http.content_types import STRUCTURED_TEXT_MIME_TYPES, content_type_base
from ..utils import sanitize_filename

INDEX_FILENAME = ".paper-fetch-mcp-cache.json"
LOCK_DIRNAME = ".paper-fetch-locks"
INDEX_LOCK_FILENAME = "cache-index.lock"
INDEX_VERSION = 1
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
    if path.name == f"{base}.md":
        return "markdown"
    return "primary_payload"


def _build_entry(*, doi: str, kind: str, path: Path) -> dict[str, Any]:
    stat = path.stat()
    resolved = path.resolve()
    mime = guess_mime_type(resolved)
    return {
        "id": _entry_id(doi=doi, kind=kind, path=resolved),
        "doi": doi,
        "kind": kind,
        "path": str(resolved),
        "mime": mime,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


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


def _write_index_unlocked(download_dir: Path, entries: list[dict[str, Any]]) -> None:
    index_path = cache_index_path(download_dir)
    if not download_dir.exists():
        return
    payload = {
        "version": INDEX_VERSION,
        "entries": _dedupe_entries(entries),
    }
    ArtifactStore.from_download_dir(download_dir).write_json_file(index_path, payload)


def _normalize_existing_entry(download_dir: Path, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    doi = str(raw.get("doi") or "").strip()
    path_text = str(raw.get("path") or "").strip()
    if not doi or not path_text:
        return None
    path = Path(path_text)
    if not path.is_absolute():
        path = (download_dir / path).resolve()
    if not path.exists() or not path.is_file():
        return None
    kind = str(raw.get("kind") or "").strip() or _entry_kind_for_path(path, doi=doi)
    return _build_entry(doi=doi, kind=kind, path=path)


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
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != INDEX_VERSION
    ):
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
    entries: list[dict[str, Any]] = []
    changed = False
    for raw in raw_entries:
        entry = _normalize_existing_entry(download_dir, raw)
        if entry is None:
            changed = True
            continue
        entries.append(entry)
    deduped = _dedupe_entries(entries)
    if changed or deduped != raw_entries:
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
    if not download_dir.exists():
        return []
    normalized_doi = str(doi or "").strip()
    if not normalized_doi:
        return []
    base = sanitize_filename(normalized_doi)
    entries: list[dict[str, Any]] = []
    found_paths: set[Path] = set()

    for path in sorted(download_dir.glob(f"{base}.*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        kind = _entry_kind_for_path(path, doi=normalized_doi)
        entries.append(_build_entry(doi=normalized_doi, kind=kind, path=path))
        found_paths.add(path.resolve())

    asset_dir = download_dir / f"{base}_assets"
    if asset_dir.is_dir():
        for path in sorted(asset_dir.rglob("*")):
            if not path.is_file():
                continue
            entries.append(_build_entry(doi=normalized_doi, kind="asset", path=path))
            found_paths.add(path.resolve())

    if include_loose_markdown:
        for path in sorted(download_dir.glob("*.md")):
            if not path.is_file() or path.name.endswith(".part"):
                continue
            if path.resolve() not in found_paths:
                entries.append(
                    _build_entry(doi=normalized_doi, kind="markdown", path=path)
                )

    return _dedupe_entries(entries)


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
    doi = str(envelope.get("doi") or "").strip()
    return doi or None


def _discover_rescan_dois(
    download_dir: Path, seed_entries: list[dict[str, Any]]
) -> list[str]:
    dois = {
        str(entry.get("doi") or "").strip()
        for entry in seed_entries
        if str(entry.get("doi") or "").strip()
    }
    for path in sorted(download_dir.glob("*.fetch-envelope.json")):
        doi = _doi_from_fetch_envelope_sidecar(path)
        if doi:
            dois.add(doi)
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
            download_dir, repair=False, cache_mode=CACHE_INDEX_MODE_INDEX
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
        entries: list[dict[str, Any]] = []
        for doi in _discover_rescan_dois(download_dir, seed_entries):
            entries.extend(
                scan_cached_files(download_dir, doi, include_loose_markdown=False)
            )
        deduped = _dedupe_entries(entries)
        if deduped or cache_index_path(download_dir).exists():
            _write_index_unlocked(download_dir, deduped)
        return CacheIndexResult(
            entries=deduped,
            index_status=CACHE_INDEX_STATUS_OK,
            index_version=INDEX_VERSION,
            cache_mode=CACHE_INDEX_MODE_RESCAN,
        )


def refresh_cache_index_for_doi_result(
    download_dir: Path, doi: str
) -> CacheIndexResult:
    normalized_doi = str(doi or "").strip()
    if not normalized_doi or not download_dir.exists():
        return CacheIndexResult(
            entries=[],
            index_status=CACHE_INDEX_STATUS_MISSING,
            index_version=None,
            index_reason="download directory does not exist or DOI is empty",
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        )
    with cache_file_lock(cache_index_lock_path(download_dir)):
        refreshed = scan_cached_files(download_dir, normalized_doi)
        existing = _read_cache_index_unlocked(
            download_dir, repair=True, cache_mode=CACHE_INDEX_MODE_REFRESH
        )
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
        merged = _dedupe_entries(retained + refreshed)
        index_exists = cache_index_path(download_dir).exists()
        if merged or index_exists:
            _write_index_unlocked(download_dir, merged)
        return CacheIndexResult(
            entries=refreshed,
            index_status=CACHE_INDEX_STATUS_OK,
            index_version=INDEX_VERSION if merged or index_exists else None,
            cache_mode=CACHE_INDEX_MODE_REFRESH,
        )


def refresh_cache_index_for_doi(download_dir: Path, doi: str) -> list[dict[str, Any]]:
    return refresh_cache_index_for_doi_result(download_dir, doi).entries


def find_cached_entry(download_dir: Path, entry_id: str) -> dict[str, Any] | None:
    for entry in list_cache_entries(download_dir):
        if entry.get("id") == entry_id:
            return entry
    return None


def preferred_cached_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    markdown_entries = [entry for entry in entries if entry.get("kind") == "markdown"]
    primary_entries = [
        entry for entry in entries if entry.get("kind") == "primary_payload"
    ]
    assets = [entry for entry in entries if entry.get("kind") == "asset"]

    def newest(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None
        return max(candidates, key=lambda item: float(item.get("mtime") or 0.0))

    return {
        "markdown": newest(markdown_entries),
        "primary_payload": newest(primary_entries),
        "assets": sorted(assets, key=lambda item: str(item.get("path") or "")),
    }
