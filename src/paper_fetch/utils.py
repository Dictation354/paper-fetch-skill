"""Shared non-transport helpers."""

from __future__ import annotations

import re
import urllib.parse
from hashlib import sha1
from pathlib import Path
from typing import Any


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def safe_text(value: Any) -> str:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_html_tags(value: str | None) -> str | None:
    if not value:
        return value
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def first_list_item(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def date_parts_to_string(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    parts = node.get("date-parts")
    if not isinstance(parts, list) or not parts:
        return None
    first = parts[0]
    if not isinstance(first, list) or not first:
        return None
    return "-".join(str(part) for part in first)


def sanitize_filename(value: str) -> str:
    original = value or ""
    digest = sha1(original.encode("utf-8", errors="ignore")).hexdigest()[:8]
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", original)
    filename = re.sub(r"_+", "_", filename).strip("._-")
    if not filename:
        return f"fulltext_{digest}"

    max_length = 180
    if len(filename) <= max_length:
        return filename

    suffix = f"_{digest}"
    truncated = filename[:max_length].rstrip("._-")
    truncated = truncated[: max(1, max_length - len(suffix))].rstrip("._-")
    return f"{truncated or 'fulltext'}{suffix}"


def canonical_author_key(name: str) -> str:
    normalized = normalize_author_name(name)
    if not normalized:
        return ""
    if "," in normalized:
        parts = [part.strip() for part in normalized.split(",") if part.strip()]
        if len(parts) >= 2:
            normalized = " ".join(parts[1:] + [parts[0]])
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_author_name(name: str) -> str:
    text = (name or "").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def dedupe_authors(authors: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for author in authors:
        normalized_author = normalize_author_name(author)
        key = canonical_author_key(normalized_author)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized_author)
    return deduped


def extension_from_content_type(content_type: str | None, source_url: str | None = None) -> str:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    known = {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/xml": ".xml",
        "application/xml": ".xml",
        "application/jats+xml": ".xml",
        "application/json": ".json",
        "text/html": ".html",
    }
    if normalized in known:
        return known[normalized]
    if source_url:
        guessed = Path(urllib.parse.urlparse(source_url).path).suffix
        if guessed:
            return guessed
    return ".bin"


def build_output_path(
    output_dir: Path | None,
    doi: str | None,
    title: str | None,
    content_type: str | None,
    source_url: str | None,
) -> Path | None:
    if output_dir is None:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(doi or title or "article")
    extension = extension_from_content_type(content_type, source_url)
    return output_dir / f"{base_name}{extension}"


def save_payload(output_path: Path | None, body: bytes) -> str | None:
    if output_path is None:
        return None
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")
    try:
        tmp_path.write_bytes(body)
        tmp_path.replace(output_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return str(output_path)


def empty_asset_results() -> dict[str, list[dict[str, Any]]]:
    return {
        "assets": [],
        "asset_failures": [],
    }


def build_asset_output_path(
    asset_dir: Path,
    source_href: str | None,
    content_type: str | None,
    source_url: str | None,
    used_names: set[str],
) -> Path:
    candidate_name = ""
    for value in (source_url, source_href):
        if not value:
            continue
        name = Path(urllib.parse.urlparse(value).path).name
        if name:
            candidate_name = name
            break

    stem = sanitize_filename(Path(candidate_name).stem or "asset")
    suffix = Path(candidate_name).suffix or extension_from_content_type(content_type, source_url or source_href)
    filename = f"{stem}{suffix}"

    counter = 2
    while filename in used_names or (asset_dir / filename).exists():
        filename = f"{stem}_{counter}{suffix}"
        counter += 1

    used_names.add(filename)
    return asset_dir / filename
