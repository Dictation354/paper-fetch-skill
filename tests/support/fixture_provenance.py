"""Independent source evidence: declarations and checksums alone are not captures."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from urllib.parse import urlsplit

from tests.paths import REPO_ROOT


def rejected_source_hashes():
    from tests.golden_criteria import golden_criteria_manifest

    return {
        row["sha256"]: row["classification"]
        for row in golden_criteria_manifest()["rejected_sources"]
    }


def capture_index(root=REPO_ROOT):
    """Index exact entities, retaining the record that supplies network evidence.

    HTTP success is not required: a challenge is a real response, but never
    evidence of full text. Article identity/content are separately reviewed.
    """
    index = defaultdict(list)
    for provenance in sorted(
        (root / "tests/fixtures").glob("**/acquisition/provenance.json")
    ):
        for record in json.loads(provenance.read_text(encoding="utf-8"))["records"]:
            path = provenance.parent.parent / record["body_file"]
            if not path.is_file():
                continue
            body = path.read_bytes()
            digest = hashlib.sha256(body).hexdigest()
            if digest != record.get("sha256") or len(body) != record.get("size"):
                continue
            url = str(record.get("requested_url") or record.get("source_url") or "")
            # Legacy provenance may explicitly lack HTTP metadata. It still
            # needs an acquisition method and timestamp, not just a hash.
            if (
                not body
                or urlsplit(url).scheme not in {"http", "https"}
                or not record.get("capture_kind")
                or not record.get("captured_at_utc")
                or not record.get("doi")
            ):
                continue
            index[(str(record["doi"]).casefold(), digest)].append(
                {
                    "provenance": provenance.relative_to(root).as_posix(),
                    "body_file": record["body_file"],
                    "capture_kind": record["capture_kind"],
                    "captured_at_utc": record["captured_at_utc"],
                    "requested_url": url,
                    "final_url": record.get("final_url"),
                    "status_code": record.get("status_code"),
                }
            )
    return index


def source_evidence(record, index, rejected):
    body = record.absolute_path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    origin = record.origin_kind
    rejection = rejected.get(digest)
    if rejection:
        status = rejection
    elif origin in {"synthetic", "contract_scenario", "unverified"}:
        status = origin
    elif record.absolute_path.suffix in {".md", ".json"}:
        status = "derived_or_auxiliary"
    elif index.get((record.doi.casefold(), digest)):
        status = "verified_capture"
    else:
        status = "unverified"
    return {
        "path": record.fixture_path,
        "doi": record.doi,
        "declared_origin": origin,
        "sha256": digest,
        "status": status,
        "evidence": index.get((record.doi.casefold(), digest), []),
    }
