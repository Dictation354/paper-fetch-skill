"""Read completed paper receipts from a project's retained reading artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..manifest import ArtifactVerificationStatus, ManifestRecord, parse_manifest_record
from ..models import TRUNCATION_WARNING
from ..publisher_identity import normalize_doi
from ..workflow.acceptance import OverallAcceptanceStatus
from ._scoped_fs import read_scoped_file
from .receipts import (
    reading_body_artifact,
    receipt_from_record,
    section_index_artifact,
)


def lookup_receipt(doi: str, output_dir: Path) -> dict[str, Any] | None:
    root = output_dir.expanduser().absolute()
    candidates: list[tuple[ManifestRecord, Path]] = []
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
            candidates.append((record, manifest[0]))

    for record, path in sorted(
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
    return None


__all__ = ["lookup_receipt"]
