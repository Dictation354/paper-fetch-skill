"""Read completed paper receipts from a project's retained reading artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from ..manifest import ArtifactVerificationStatus, ManifestRecord, parse_manifest_record
from ..models import TRUNCATION_WARNING
from ..publisher_identity import normalize_doi
from ..utils import sanitize_filename
from ..workflow.acceptance import OverallAcceptanceStatus
from ._scoped_fs import read_scoped_file
from .receipts import (
    reading_body_artifact,
    receipt_from_record,
    section_index_artifact,
)


def _accepted_candidates(doi: str, root: Path) -> Iterator[tuple[ManifestRecord, Path]]:
    for path in (root / ".paper-fetch-results").glob("*/*/manifest.json"):
        manifest = read_scoped_file(root, str(path))
        if manifest is None:
            continue
        try:
            record = parse_manifest_record(json.loads(manifest[1]))
        except ValueError:
            continue
        if (
            normalize_doi(record.acceptance.identity.doi) == doi
            and record.acceptance.target == "paper"
            and record.acceptance.overall
            in {OverallAcceptanceStatus.COMPLETE, OverallAcceptanceStatus.DEGRADED}
            and record.acceptance.content.has_fulltext
            and TRUNCATION_WARNING not in record.warnings
        ):
            yield record, manifest[0]


def _legacy_receipt(doi: str, root: Path) -> dict[str, Any] | None:
    path = root / f"{sanitize_filename(doi)}.fetch-envelope.json"
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
        or data["version"] != 2
        or "request_fingerprint" in data
    ):
        return None
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return None
    quality = payload.get("quality")
    markdown = payload.get("markdown")
    source = payload.get("source")
    stored_doi = payload.get("doi")
    if (
        not isinstance(stored_doi, str)
        or normalize_doi(stored_doi) != doi
        or payload.get("has_fulltext") is not True
        or payload.get("content_kind") != "fulltext"
        or not isinstance(markdown, str)
        or not markdown.strip()
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
    return {
        "schema_version": 1,
        "contract": "paper-fetch/legacy-lookup",
        "status": "found",
        "doi": doi,
        "source": source,
        "sidecar_path": str(sidecar[0]),
        "sidecar_version": data["version"],
        "body_json_pointer": "/payload/markdown",
        "acceptance": "historical_unverified",
    }


def lookup_receipt(
    doi: str, output_dirs: Sequence[Path], *, include_legacy: bool = False
) -> dict[str, Any] | None:
    roots = [directory.expanduser().absolute() for directory in output_dirs]
    candidates = (
        (record, path, root)
        for root in roots
        for record, path in _accepted_candidates(doi, root)
    )
    for record, path, root in sorted(
        candidates, key=lambda item: item[0].completed_at, reverse=True
    ):
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
            return receipt_from_record(record, path)
    if include_legacy:
        for root in roots:
            if receipt := _legacy_receipt(doi, root):
                return receipt
    return None


__all__ = ["lookup_receipt"]
