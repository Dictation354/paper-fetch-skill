"""Budgeted arXiv source-archive decoding and figure reference parsing."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import gzip
import os
from pathlib import Path
import re
import tarfile
from typing import Any
import urllib.parse
import uuid
import zipfile
from collections.abc import Mapping

from ..asset_budget import AssetBudget, AssetBudgetExceeded, AssetReservation
from ..reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    ASSET_FILE_LIMIT_EXCEEDED,
)
from ..utils import normalize_text

_ARXIV_SOURCE_MAX_MEMBERS = 128
_ARXIV_SOURCE_STREAM_CHUNK_BYTES = 64 * 1024
_ARXIV_SOURCE_MAX_MEMBER_BYTES = 32 * 1024 * 1024
_ARXIV_SOURCE_IMAGE_SUFFIXES = {
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
}
_ARXIV_SOURCE_GRAPHIC_SUFFIXES = (*sorted(_ARXIV_SOURCE_IMAGE_SUFFIXES), ".pdf")
_ARXIV_LATEX_FIGURE_ENV_PATTERN = re.compile(
    r"\\begin\{(?P<env>figure\*?)\}(?P<body>.*?)\\end\{(?P=env)\}",
    flags=re.DOTALL,
)
_ARXIV_LATEX_INCLUDEGRAPHICS_PATTERN = re.compile(
    r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{",
    flags=re.DOTALL,
)
_ARXIV_LATEX_TEXT_COMMAND_PATTERN = re.compile(
    r"\\(?:textbf|textit|emph|textrm|textsc|texttt|textsuperscript|textsubscript)\s*\{([^{}]*)\}"
)
_ARXIV_LATEX_DROP_COMMAND_PATTERN = re.compile(
    r"\\(?:label|ref|autoref|cref|Cref|cite|citet|citep|citealp|url)\*?"
    r"(?:\s*\[[^\]]*\])*\s*\{[^{}]*\}"
)


def _arxiv_source_url(arxiv_id: str) -> str:
    normalized = normalize_text(arxiv_id).strip("/")
    return f"https://arxiv.org/e-print/{urllib.parse.quote(normalized, safe='/.')}"


def _safe_arxiv_source_member_name(name: Any) -> str:
    normalized = normalize_text(str(name or "")).replace("\\", "/").lstrip("/")
    if not normalized:
        return ""
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return ""
    return "/".join(parts)


@dataclass
class _ArxivSourceMember:
    """One decoded archive member retained as a budgeted staging file."""

    path: Path
    reservation: AssetReservation
    size: int

    def cleanup(self) -> None:
        self.reservation.rollback()
        with contextlib.suppress(OSError):
            self.path.unlink(missing_ok=True)


def _cleanup_arxiv_source_members(
    files: Mapping[str, _ArxivSourceMember],
    *,
    keep_ids: set[int] | None = None,
) -> None:
    retained_ids = keep_ids or set()
    for member in files.values():
        if id(member) not in retained_ids:
            member.cleanup()


def _arxiv_source_max_members(asset_budget: AssetBudget) -> int:
    if asset_budget.max_files is None:
        return _ARXIV_SOURCE_MAX_MEMBERS
    return min(_ARXIV_SOURCE_MAX_MEMBERS, asset_budget.max_files)


def _read_bounded_stream(
    handle: Any,
    *,
    reservation: AssetReservation,
    destination: Path,
) -> int:
    """Copy one decoded member to disk with chunk-level budget accounting."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    reservation.register_staging(destination)
    written = 0
    try:
        with destination.open("xb") as output:
            while True:
                chunk = handle.read(_ARXIV_SOURCE_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                payload = bytes(chunk)
                reservation.consume(len(payload))
                output.write(payload)
                written += len(payload)
            output.flush()
            os.fsync(output.fileno())
        reservation.reconcile_actual()
        return written
    except BaseException:
        reservation.rollback()
        with contextlib.suppress(OSError):
            destination.unlink(missing_ok=True)
        raise


def _retain_arxiv_source_member(
    files: dict[str, _ArxivSourceMember],
    *,
    name: str,
    declared_size: int | None,
    handle: Any,
    staging_dir: Path,
    asset_budget: AssetBudget,
) -> None:
    if not name or name in files:
        return
    maximum = _arxiv_source_max_members(asset_budget)
    if len(files) >= maximum:
        diagnostic = {
            "boundary": "arxiv_archive_member_count",
            "max_files": maximum,
        }
        asset_budget.cancel(ASSET_FILE_LIMIT_EXCEEDED, diagnostic=diagnostic)
        raise AssetBudgetExceeded(
            ASSET_FILE_LIMIT_EXCEEDED,
            diagnostic=diagnostic,
            fatal=True,
        )
    normalized_declared = None if declared_size is None else max(0, int(declared_size))
    if (
        normalized_declared is not None
        and normalized_declared > asset_budget.max_bytes_per_asset
    ):
        diagnostic = {
            "boundary": "arxiv_archive_member_header",
            "declared_bytes": normalized_declared,
            "max_bytes_per_asset": asset_budget.max_bytes_per_asset,
        }
        asset_budget.cancel(ASSET_BYTES_PER_ASSET_EXCEEDED, diagnostic=diagnostic)
        raise AssetBudgetExceeded(
            ASSET_BYTES_PER_ASSET_EXCEEDED,
            diagnostic=diagnostic,
            fatal=True,
        )
    reservation = asset_budget.reserve_transient(declared_bytes=normalized_declared)
    staging_path = staging_dir / f".paper-fetch-arxiv-member-{uuid.uuid4().hex}.part"
    size = _read_bounded_stream(
        handle,
        reservation=reservation,
        destination=staging_path,
    )
    if size <= 0:
        reservation.rollback()
        staging_path.unlink(missing_ok=True)
        return
    files[name] = _ArxivSourceMember(staging_path, reservation, size)


def _check_arxiv_archive_member_count(
    encountered_regular_members: int,
    *,
    asset_budget: AssetBudget,
) -> None:
    """Bound archive traversal independently of retained/deduplicated files."""

    maximum = _arxiv_source_max_members(asset_budget)
    if encountered_regular_members <= maximum:
        return
    diagnostic = {
        "boundary": "arxiv_archive_member_count",
        "encountered_regular_members": encountered_regular_members,
        "max_files": maximum,
    }
    asset_budget.cancel(ASSET_FILE_LIMIT_EXCEEDED, diagnostic=diagnostic)
    raise AssetBudgetExceeded(
        ASSET_FILE_LIMIT_EXCEEDED,
        diagnostic=diagnostic,
        fatal=True,
    )


def _read_arxiv_source_files_from_path(
    path: Path,
    *,
    staging_dir: Path,
    asset_budget: AssetBudget,
) -> dict[str, _ArxivSourceMember]:
    """Stream decoded archive members to budgeted staging files.

    Declared archive sizes are treated only as an early rejection hint. Every
    decoded chunk is counted, so forged ZIP/TAR metadata and compression bombs
    cannot bypass the shared article budget.
    """

    files: dict[str, _ArxivSourceMember] = {}
    try:
        with tarfile.open(path, mode="r:*") as archive:
            encountered_regular_members = 0
            for member in archive:
                if not member.isfile():
                    continue
                encountered_regular_members += 1
                _check_arxiv_archive_member_count(
                    encountered_regular_members,
                    asset_budget=asset_budget,
                )
                name = _safe_arxiv_source_member_name(member.name)
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                with handle:
                    try:
                        _retain_arxiv_source_member(
                            files,
                            name=name,
                            declared_size=int(member.size),
                            handle=handle,
                            staging_dir=staging_dir,
                            asset_budget=asset_budget,
                        )
                    except BaseException:
                        _cleanup_arxiv_source_members(files)
                        raise
            if files:
                return files
    except tarfile.TarError:
        _cleanup_arxiv_source_members(files)
        files = {}
    try:
        with zipfile.ZipFile(path) as archive:
            encountered_regular_members = 0
            for info in archive.infolist():
                if info.is_dir():
                    continue
                encountered_regular_members += 1
                _check_arxiv_archive_member_count(
                    encountered_regular_members,
                    asset_budget=asset_budget,
                )
                name = _safe_arxiv_source_member_name(info.filename)
                with archive.open(info) as handle:
                    try:
                        _retain_arxiv_source_member(
                            files,
                            name=name,
                            declared_size=int(info.file_size),
                            handle=handle,
                            staging_dir=staging_dir,
                            asset_budget=asset_budget,
                        )
                    except BaseException:
                        _cleanup_arxiv_source_members(files)
                        raise
            if files:
                return files
    except zipfile.BadZipFile:
        _cleanup_arxiv_source_members(files)
        files = {}
    try:
        with gzip.open(path, "rb") as archive_source:
            try:
                _retain_arxiv_source_member(
                    files,
                    name="source.tex",
                    declared_size=None,
                    handle=archive_source,
                    staging_dir=staging_dir,
                    asset_budget=asset_budget,
                )
            except BaseException:
                _cleanup_arxiv_source_members(files)
                raise
    except OSError:
        _cleanup_arxiv_source_members(files)
        return {}
    source_member = files.get("source.tex")
    if source_member is None:
        return {}
    try:
        with source_member.path.open("rb") as handle:
            prefix = handle.read(8192)
    except OSError:
        _cleanup_arxiv_source_members(files)
        return {}
    if b"\\documentclass" in prefix[:4096] or b"\\begin{document}" in prefix:
        return files
    _cleanup_arxiv_source_members(files)
    return {}


def _strip_latex_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        escaped = False
        cut_at = len(line)
        for index, char in enumerate(line):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "%":
                cut_at = index
                break
        lines.append(line[:cut_at])
    return "\n".join(lines)


def _balanced_latex_brace_content(text: str, open_index: int) -> str:
    if open_index < 0 or open_index >= len(text) or text[open_index] != "{":
        return ""
    depth = 0
    escaped = False
    start = open_index + 1
    for index in range(open_index, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
            continue
        if char != "}":
            continue
        depth -= 1
        if depth == 0:
            return text[start:index]
    return ""


def _latex_command_argument(text: str, command: str) -> str:
    pattern = re.compile(
        rf"\\{re.escape(command)}\*?(?:\s*\[[^\]]*\])?\s*\{{",
        flags=re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return ""
    return _balanced_latex_brace_content(text, match.end() - 1)


def _latex_includegraphics_paths(text: str) -> list[str]:
    paths: list[str] = []
    for match in _ARXIV_LATEX_INCLUDEGRAPHICS_PATTERN.finditer(text):
        value = normalize_text(_balanced_latex_brace_content(text, match.end() - 1))
        if value:
            paths.append(value.replace("\\", "/").strip())
    return paths


def _latex_caption_to_text(text: str) -> str:
    normalized = _strip_latex_comments(text).replace("\n", " ")
    for _ in range(6):
        updated = _ARXIV_LATEX_TEXT_COMMAND_PATTERN.sub(r"\1", normalized)
        if updated == normalized:
            break
        normalized = updated
    normalized = re.sub(r"\$([^$]*)\$", r"\1", normalized)
    normalized = _ARXIV_LATEX_DROP_COMMAND_PATTERN.sub("", normalized)
    normalized = re.sub(r"\\[a-zA-Z]+\*?(?:\s*\[[^\]]*\])?", "", normalized)
    normalized = normalized.replace("\\&", "&").replace("\\%", "%")
    normalized = normalized.replace("\\_", "_").replace("\\#", "#")
    normalized = normalized.replace("~", " ")
    normalized = normalized.replace("{", "").replace("}", "")
    return normalize_text(normalized)


def _source_candidate_paths(tex_name: str, graphic_path: str) -> list[str]:
    normalized = _safe_arxiv_source_member_name(graphic_path)
    if not normalized:
        return []
    tex_dir = Path(tex_name.replace("\\", "/")).parent.as_posix()
    base_candidates = [normalized]
    if tex_dir and tex_dir != ".":
        base_candidates.append(f"{tex_dir}/{normalized}")
    candidates: list[str] = []
    for candidate in base_candidates:
        if candidate not in candidates:
            candidates.append(candidate)
        if Path(candidate).suffix:
            continue
        for suffix in _ARXIV_SOURCE_GRAPHIC_SUFFIXES:
            with_suffix = f"{candidate}{suffix}"
            if with_suffix not in candidates:
                candidates.append(with_suffix)
    return candidates


def _resolve_arxiv_source_graphic(
    files: Mapping[str, bytes | _ArxivSourceMember],
    *,
    tex_name: str,
    graphic_path: str,
) -> tuple[str, bytes | _ArxivSourceMember] | None:
    by_lower = {name.lower(): name for name in files}
    for candidate in _source_candidate_paths(tex_name, graphic_path):
        exact = files.get(candidate)
        if exact is not None:
            return candidate, exact
        actual_name = by_lower.get(candidate.lower())
        if actual_name is not None:
            return actual_name, files[actual_name]
    return None


def _extract_arxiv_source_figure_references(
    files: Mapping[str, bytes | _ArxivSourceMember],
) -> list[dict[str, Any]]:
    tex_names = sorted(
        (
            name
            for name in files
            if Path(name).suffix.lower() in {"", ".tex"}
            and not Path(name).name.startswith(".")
        ),
        key=lambda name: (Path(name).name.lower() != "main.tex", name.lower()),
    )
    figures: list[dict[str, Any]] = []
    for tex_name in tex_names:
        try:
            source = files[tex_name]
            if isinstance(source, _ArxivSourceMember):
                with source.path.open("rb") as handle:
                    tex_body = bytearray()
                    while True:
                        chunk = handle.read(_ARXIV_SOURCE_STREAM_CHUNK_BYTES)
                        if not chunk:
                            break
                        tex_body.extend(chunk)
                        if len(tex_body) > source.size:
                            raise OSError("arXiv source member changed while reading")
                tex = bytes(tex_body).decode("utf-8", errors="replace")
            else:
                tex = bytes(source).decode("utf-8", errors="replace")
        except Exception:
            continue
        tex = _strip_latex_comments(tex)
        for block_match in _ARXIV_LATEX_FIGURE_ENV_PATTERN.finditer(tex):
            block = block_match.group("body")
            caption = _latex_caption_to_text(_latex_command_argument(block, "caption"))
            label = normalize_text(_latex_command_argument(block, "label"))
            for graphic_path in _latex_includegraphics_paths(block):
                resolved = _resolve_arxiv_source_graphic(
                    files, tex_name=tex_name, graphic_path=graphic_path
                )
                if resolved is None:
                    continue
                source_path, source_body = resolved
                figure: dict[str, Any] = {
                    "source_path": source_path,
                    "caption": caption,
                    "label": label,
                }
                if isinstance(source_body, _ArxivSourceMember):
                    figure["source_member"] = source_body
                else:
                    figure["body"] = source_body
                figures.append(figure)
    return figures
