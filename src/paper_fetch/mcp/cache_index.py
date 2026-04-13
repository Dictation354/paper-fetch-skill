"""Helpers for MCP-visible cached download indexing."""

from __future__ import annotations

import json
import mimetypes
from hashlib import sha1
from pathlib import Path
from typing import Any

from ..utils import sanitize_filename

INDEX_FILENAME = ".paper-fetch-mcp-cache.json"
INDEX_VERSION = 1
CACHE_INDEX_RESOURCE_URI = "resource://paper-fetch/cache-index"
CACHED_RESOURCE_URI_PREFIX = "resource://paper-fetch/cached/"
CACHED_RESOURCE_TEMPLATE = "resource://paper-fetch/cached/{entry_id}"

_TEXT_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/jats+xml",
    "image/svg+xml",
}


def cache_index_path(download_dir: Path) -> Path:
    return download_dir / INDEX_FILENAME


def cached_resource_uri(entry_id: str) -> str:
    return f"{CACHED_RESOURCE_URI_PREFIX}{entry_id}"


def is_text_mime_type(mime_type: str | None) -> bool:
    normalized = (mime_type or "").split(";", 1)[0].strip().lower()
    return normalized.startswith("text/") or normalized in _TEXT_MIME_TYPES


def guess_mime_type(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _entry_id(*, doi: str, kind: str, path: Path) -> str:
    digest = sha1(f"{doi}\0{kind}\0{path.resolve()}".encode("utf-8", errors="ignore")).hexdigest()
    return digest[:16]


def _entry_kind_for_path(path: Path, *, doi: str) -> str:
    base = sanitize_filename(doi)
    if path.parent.name == f"{base}_assets":
        return "asset"
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


def _write_index(download_dir: Path, entries: list[dict[str, Any]]) -> None:
    index_path = cache_index_path(download_dir)
    if not download_dir.exists():
        return
    payload = {
        "version": INDEX_VERSION,
        "entries": _dedupe_entries(entries),
    }
    tmp_path = index_path.with_suffix(index_path.suffix + ".part")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(index_path)


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


def list_cache_entries(download_dir: Path) -> list[dict[str, Any]]:
    index_path = cache_index_path(download_dir)
    if not index_path.exists():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_entries = payload.get("entries") if isinstance(payload, dict) else []
    entries: list[dict[str, Any]] = []
    changed = False
    for raw in raw_entries or []:
        entry = _normalize_existing_entry(download_dir, raw)
        if entry is None:
            changed = True
            continue
        entries.append(entry)
    deduped = _dedupe_entries(entries)
    if changed or deduped != list(raw_entries or []):
        _write_index(download_dir, deduped)
    return deduped


def scan_cached_files(download_dir: Path, doi: str) -> list[dict[str, Any]]:
    if not download_dir.exists():
        return []
    normalized_doi = str(doi or "").strip()
    if not normalized_doi:
        return []
    base = sanitize_filename(normalized_doi)
    entries: list[dict[str, Any]] = []

    for path in sorted(download_dir.glob(f"{base}.*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        kind = _entry_kind_for_path(path, doi=normalized_doi)
        entries.append(_build_entry(doi=normalized_doi, kind=kind, path=path))

    asset_dir = download_dir / f"{base}_assets"
    if asset_dir.is_dir():
        for path in sorted(asset_dir.rglob("*")):
            if not path.is_file():
                continue
            entries.append(_build_entry(doi=normalized_doi, kind="asset", path=path))

    return _dedupe_entries(entries)


def refresh_cache_index_for_doi(download_dir: Path, doi: str) -> list[dict[str, Any]]:
    normalized_doi = str(doi or "").strip()
    existing = list_cache_entries(download_dir)
    retained = [entry for entry in existing if entry.get("doi") != normalized_doi]
    refreshed = scan_cached_files(download_dir, normalized_doi)
    merged = _dedupe_entries(retained + refreshed)
    index_exists = cache_index_path(download_dir).exists()
    if merged or index_exists:
        _write_index(download_dir, merged)
    return refreshed


def find_cached_entry(download_dir: Path, entry_id: str) -> dict[str, Any] | None:
    for entry in list_cache_entries(download_dir):
        if entry.get("id") == entry_id:
            return entry
    return None


def preferred_cached_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    markdown_entries = [entry for entry in entries if entry.get("kind") == "markdown"]
    primary_entries = [entry for entry in entries if entry.get("kind") == "primary_payload"]
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
