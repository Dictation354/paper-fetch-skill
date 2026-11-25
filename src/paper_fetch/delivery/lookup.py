"""Read completed paper receipts from a project's retained reading artifacts."""

from __future__ import annotations

import json
import re
import stat
from collections import defaultdict
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..capability_scope import PUBLIC_CAPABILITY_SCOPE
from ..manifest import ArtifactVerificationStatus, ManifestRecord, parse_manifest_record
from ..models import TRUNCATION_WARNING
from ..models.markdown import INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN
from ..models.tokens import estimate_tokens
from ..publisher_identity import normalize_doi
from ..utils import sanitize_filename
from ..workflow.acceptance import OverallAcceptanceStatus
from ._scoped_fs import read_scoped_file
from .receipts import (
    reading_body_artifact,
    receipt_from_record,
    section_index_artifact,
)


def _manifest_files(root: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in (root / ".paper-fetch-results").glob("*/*/manifest.json"):
        manifest = read_scoped_file(root, str(path))
        if manifest is None:
            continue
        try:
            data = json.loads(manifest[1])
        except ValueError:
            continue
        if isinstance(data, dict):
            yield manifest[0], data


def _accepted_record(data: dict[str, Any]) -> ManifestRecord | None:
    try:
        record = parse_manifest_record(data)
    except ValueError:
        return None
    if (
        record.acceptance.target == "paper"
        and record.acceptance.overall
        in {OverallAcceptanceStatus.COMPLETE, OverallAcceptanceStatus.DEGRADED}
        and record.acceptance.content.has_fulltext
        and TRUNCATION_WARNING not in record.warnings
    ):
        return record
    return None


def _legacy_result(doi: str, source: str, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": "paper-fetch/legacy-lookup",
        "status": "found",
        "doi": doi,
        "source": source,
        **fields,
        "acceptance": "historical_unverified",
    }


def _legacy_sidecar(
    root: Path,
    path: Path,
    dois: set[str],
    *,
    fingerprint: str | None,
) -> dict[str, Any] | None:
    sidecar = read_scoped_file(root, str(path))
    if sidecar is None:
        return None
    try:
        data = json.loads(sidecar[1])
    except ValueError:
        return None
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data["version"] != (8 if fingerprint else 2)
    ):
        return None
    scope_keys = ("credential_scope", "capability_scope")
    if fingerprint is not None:
        scopes = [data.get(key) for key in scope_keys]
        if (
            data.get("request_fingerprint") != fingerprint
            or PUBLIC_CAPABILITY_SCOPE not in scopes
            or any(scope not in (None, PUBLIC_CAPABILITY_SCOPE) for scope in scopes)
        ):
            return None
    elif "request_fingerprint" in data or any(
        key in data and data[key] != PUBLIC_CAPABILITY_SCOPE for key in scope_keys
    ):
        return None
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return None
    quality = payload.get("quality")
    markdown = payload.get("markdown")
    source = payload.get("source")
    stored_doi = payload.get("doi")
    doi = normalize_doi(stored_doi) if isinstance(stored_doi, str) else ""
    if (
        doi not in dois
        or payload.get("has_fulltext") is not True
        or payload.get("content_kind") != "fulltext"
        or not isinstance(markdown, str)
        or not markdown.strip()
        or TRUNCATION_WARNING in markdown
        or not isinstance(source, str)
        or not source.strip()
        or not isinstance(quality, dict)
        or quality.get("has_fulltext") is not True
        or quality.get("content_kind") != "fulltext"
    ):
        return None
    for warnings in (payload.get("warnings"), quality.get("warnings")):
        if not isinstance(warnings, list) or TRUNCATION_WARNING in warnings:
            return None
    return _legacy_result(
        doi,
        source,
        sidecar_path=str(sidecar[0]),
        sidecar_version=data["version"],
        body_json_pointer="/payload/markdown",
    )


def _mtime(path: Path) -> float:
    try:
        info = path.lstat()
    except OSError:
        return float("-inf")
    return info.st_mtime if stat.S_ISREG(info.st_mode) else float("-inf")


def _paths_by_mtime(paths: Iterator[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: (_mtime(path), path.name), reverse=True)


_SIDECAR_SUFFIX = ".fetch-envelope.json"


def _legacy_sidecars(dois: set[str], root: Path) -> Iterator[dict[str, Any]]:
    stems = defaultdict(set)
    for doi in dois:
        stems[sanitize_filename(doi)].add(doi)
    fingerprinted = []
    flat = []
    for path in root.glob(f"*{_SIDECAR_SUFFIX}"):
        name = path.name.removesuffix(_SIDECAR_SUFFIX)
        stem, _, suffix_hash = name.rpartition(".")
        if stem in stems and re.fullmatch(r"[0-9a-f]{64}", suffix_hash):
            fingerprinted.append((path, stem, suffix_hash))
        if name in stems:
            flat.append((path, name, None))
    fingerprinted.sort(key=lambda item: (_mtime(item[0]), item[0].name), reverse=True)
    for path, stem, fingerprint in (*fingerprinted, *flat):
        if stems[stem] and (
            receipt := _legacy_sidecar(root, path, stems[stem], fingerprint=fingerprint)
        ):
            stems[stem].remove(receipt["doi"])
            yield receipt


def _manifest_time(data: dict[str, Any], path: Path) -> float:
    completed_at = data.get("completed_at")
    if isinstance(completed_at, str):
        try:
            completed = datetime.fromisoformat(completed_at)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=UTC)
            return completed.timestamp()
        except (ValueError, OverflowError, OSError):
            pass
    return _mtime(path)


_PARTIAL_CONTENT = ("abstract_only", "metadata_only")


def _v2_doi(data: dict[str, Any]) -> str:
    acceptance = data.get("acceptance")
    if "acceptance" in data:
        if not isinstance(acceptance, dict):
            return ""
        identity = acceptance.get("identity")
        doi = identity.get("doi") if isinstance(identity, dict) else None
    else:
        doi = data.get("doi")
    return normalize_doi(doi) if isinstance(doi, str) else ""


def _read_manifest_body(
    root: Path, manifest: Path, body_path: str, **verification: Any
) -> tuple[Path, bytes] | None:
    relative = Path(body_path).expanduser()
    for candidate in dict.fromkeys((manifest.parent / relative, root / relative)):
        body = read_scoped_file(root, str(candidate), **verification)
        if (
            body is not None
            and body[1].strip()
            and TRUNCATION_WARNING.encode() not in body[1]
        ):
            return body
    return None


def _legacy_v2_body(
    doi: str, root: Path, path: Path, data: dict[str, Any]
) -> tuple[Path, bytes] | None:
    warnings = data.get("warnings", [])
    stored_doi = data.get("doi")
    if (
        (
            stored_doi is not None
            and (not isinstance(stored_doi, str) or normalize_doi(stored_doi) != doi)
        )
        or data.get("target") not in (None, "paper")
        or data.get("has_fulltext") is False
        or data.get("content_kind") in _PARTIAL_CONTENT
        or data.get("truncated") is True
        or not isinstance(warnings, list)
        or TRUNCATION_WARNING in warnings
    ):
        return None

    acceptance = data.get("acceptance")
    if isinstance(acceptance, dict):
        content = acceptance.get("content")
        artifacts = data.get("output_artifacts")
        if (
            acceptance.get("target") != "paper"
            or acceptance.get("overall") not in ("complete", "degraded")
            or not isinstance(content, dict)
            or content.get("has_fulltext") is not True
            or content.get("content_kind") in _PARTIAL_CONTENT
            or not isinstance(artifacts, list)
        ):
            return None
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not (
                artifact.get("role") == "reading_markdown"
                or artifact.get("kind") in ("reading_markdown", "markdown")
            ):
                continue
            body_path = artifact.get("path")
            if not isinstance(body_path, str) or not body_path:
                continue
            verification = {}
            if artifact.get("verification_status") == "verified":
                size = artifact.get("expected_size", artifact.get("size"))
                sha256 = artifact.get("expected_sha256", artifact.get("sha256"))
                if (
                    type(size) is not int
                    or size < 0
                    or not isinstance(sha256, str)
                    or not re.fullmatch(r"[0-9a-fA-F]{64}", sha256)
                ):
                    continue
                verification = {"expected_size": size, "expected_sha256": sha256}
            if body := _read_manifest_body(root, path, body_path, **verification):
                return body
        return None

    if not (data.get("has_fulltext") is True or data.get("content_kind") == "fulltext"):
        return None
    output_paths = data.get("output_paths")
    body_path = data.get("body_path") or (
        output_paths.get("markdown") if isinstance(output_paths, dict) else None
    )
    if body_path is None:
        body_path = str(path.with_name("body.md"))
    if not isinstance(body_path, str):
        return None
    return _read_manifest_body(root, path, body_path)


def _legacy_manifests(
    dois: set[str],
    root: Path,
    manifests: list[tuple[str, Path, dict[str, Any], ManifestRecord | None]],
) -> Iterator[dict[str, Any]]:
    for doi, path, data, record in sorted(
        manifests,
        key=lambda item: (_manifest_time(item[2], item[1]), item[1]),
        reverse=True,
    ):
        if doi not in dois:
            continue
        source = data.get("source")
        if record is None:
            body_file = _legacy_v2_body(doi, root, path, data)
        else:
            body = reading_body_artifact(record)
            if body is None:
                continue
            section_paths = [path.with_name("sections.json")]
            if (sections := section_index_artifact(record)) is not None:
                section_path = Path(sections.path).expanduser()
                section_paths.extend((root / section_path, path.parent / section_path))
            if any(
                candidate.is_symlink() or candidate.exists()
                for candidate in section_paths
            ):
                continue
            verified = body.verification_status == ArtifactVerificationStatus.VERIFIED
            body_file = _read_manifest_body(
                root,
                path,
                body.path,
                expected_size=body.size if verified else None,
                expected_sha256=body.sha256 if verified else None,
            )
            source = record.acceptance.provenance.source
        if body_file is not None:
            dois.remove(doi)
            yield _legacy_result(
                doi,
                source
                if isinstance(source, str) and source.strip()
                else "legacy_markdown",
                body_path=str(body_file[0]),
                manifest_path=str(path),
            )


_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)^---\r?\n", re.MULTILINE | re.DOTALL)
_MARKDOWN_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*#*\s*$")
_RENDERED_REFERENCES = re.compile(
    r"^## References \(\d+ total, showing \d+\)\r?$", re.M
)


def _has_legacy_markdown_body(markdown: str) -> bool:
    excluded_level = 0
    for line in markdown.splitlines():
        line = line.strip()
        if heading := _MARKDOWN_HEADING.fullmatch(line):
            level = len(heading[1])
            if not excluded_level or level <= excluded_level:
                excluded_level = (
                    level
                    if heading[2].casefold()
                    in {"abstract", "summary", "references", "bibliography"}
                    else 0
                )
        elif line and not excluded_level:
            if not INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN.match(line):
                return True
    return False


def _legacy_markdown_has_complete_body(markdown: str, value: str) -> bool:
    text = _RENDERED_REFERENCES.split(markdown, maxsplit=1)[0].lstrip()
    if text.startswith("# "):
        text = text.partition("\n")[2]
    if not _has_legacy_markdown_body(text):
        return False
    try:
        token_estimate = int(value)
    except ValueError:
        return True
    # Quality sums separately rounded abstract and body estimates, excluding refs.
    return token_estimate <= 0 or estimate_tokens(text) + 1 >= token_estimate


def _legacy_markdown(dois: set[str], root: Path) -> Iterator[dict[str, Any]]:
    for path in _paths_by_mtime(root.glob("*.md")) if dois else ():
        md_file = read_scoped_file(root, str(path))
        if md_file is None:
            continue
        try:
            markdown = md_file[1].decode("utf-8")
        except UnicodeDecodeError:
            continue
        if not (frontmatter := _FRONTMATTER.match(markdown)):
            continue
        fields = {}
        for line in frontmatter[1].splitlines():
            key, colon, value = line.partition(":")
            key = key.rstrip()
            if colon and key in {
                "doi",
                "content_kind",
                "has_fulltext",
                "token_estimate",
                "truncated",
                "source",
            }:
                fields[key] = (
                    re.split(r"\s+#", value.strip(), maxsplit=1)[0].strip("'\"").strip()
                )
        body = markdown[frontmatter.end() :]
        doi = normalize_doi(fields.get("doi"))
        kind = fields.get("content_kind", "").lower()
        has_fulltext = fields.get("has_fulltext", "").lower()
        if (
            doi in dois
            and (kind == "fulltext" or has_fulltext == "true")
            and has_fulltext != "false"
            and kind not in _PARTIAL_CONTENT
            and fields.get("truncated", "").lower() not in {"true", "yes", "1"}
            and TRUNCATION_WARNING not in body
            and _legacy_markdown_has_complete_body(
                body, fields.get("token_estimate", "")
            )
        ):
            dois.remove(doi)
            yield _legacy_result(
                doi,
                fields.get("source") or "legacy_markdown",
                body_path=str(md_file[0]),
            )


def lookup_receipts(
    dois: Sequence[str], output_dirs: Sequence[Path], *, include_legacy: bool = False
) -> dict[str, dict[str, Any]]:
    unresolved = set(dois)
    if not unresolved:
        return {}
    roots = dict.fromkeys(
        directory.expanduser().absolute() for directory in output_dirs
    )
    candidates = []
    historical: dict[
        Path, list[tuple[str, Path, dict[str, Any], ManifestRecord | None]]
    ] = defaultdict(list)
    for root in roots:
        for path, data in _manifest_files(root):
            if data.get("schema_version") == 2:
                if include_legacy and (doi := _v2_doi(data)) in unresolved:
                    historical[root].append((doi, path, data, None))
                continue
            record = _accepted_record(data)
            if (
                record is None
                or (doi := normalize_doi(record.acceptance.identity.doi))
                not in unresolved
            ):
                continue
            candidates.append((record, doi, path, root))
            if include_legacy:
                historical[root].append((doi, path, data, record))

    results = {}
    for record, doi, path, root in sorted(
        candidates, key=lambda item: item[0].completed_at, reverse=True
    ):
        if doi not in unresolved:
            continue
        body = reading_body_artifact(record)
        sections = section_index_artifact(record)
        if (
            body is not None
            and sections is not None
            and body.verification_status == ArtifactVerificationStatus.VERIFIED
            and sections.verification_status == ArtifactVerificationStatus.VERIFIED
            and read_scoped_file(
                root, body.path, expected_size=body.size, expected_sha256=body.sha256
            )
            is not None
            and read_scoped_file(
                root,
                sections.path,
                expected_size=sections.size,
                expected_sha256=sections.sha256,
            )
            is not None
        ):
            results[doi] = receipt_from_record(record, path)
            unresolved.remove(doi)

    if include_legacy:
        for root in roots:
            if not unresolved:
                break
            for receipt in _legacy_sidecars(unresolved, root):
                doi = receipt["doi"]
                results[doi] = receipt
                unresolved.remove(doi)
            for receipt in _legacy_manifests(unresolved, root, historical[root]):
                results[receipt["doi"]] = receipt
            for receipt in _legacy_markdown(unresolved, root):
                results[receipt["doi"]] = receipt

    return results


def lookup_receipt(
    doi: str, output_dirs: Sequence[Path], *, include_legacy: bool = False
) -> dict[str, Any] | None:
    return lookup_receipts((doi,), output_dirs, include_legacy=include_legacy).get(doi)


__all__ = ["lookup_receipt", "lookup_receipts"]
