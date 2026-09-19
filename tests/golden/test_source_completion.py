"""Newly verified originals: exact captures, identity, and fulltext replay scope."""

import hashlib
import json

from bs4 import BeautifulSoup
import pytest

from tests.paths import REPO_ROOT
from tests.fixture_catalog import fixture_catalog
from tests.support.fixture_provenance import (
    capture_index,
    rejected_source_hashes,
    source_evidence,
)
from tests.support.verified_source_inputs import (
    build_verified_source_article,
    ieee_fragment_identity,
    inspect_original,
    pdf_landing_identity,
)


from tests.golden_criteria import source_selections, golden_criteria_manifest

ROWS = source_selections()
VERIFIED = [row for row in ROWS if row.get("source_status") == "verified_capture"]
FULLTEXT = [row for row in VERIFIED if row["status"] == "verified_article_source"]


def test_current_source_selections_are_complete_and_resolvable():
    samples = golden_criteria_manifest()["samples"]
    assert len({row["sample_id"] for row in ROWS}) == len(ROWS)
    for row in ROWS:
        sample = samples[row["sample_id"]]
        assert row["doi"] == sample["doi"]
        assert row["provider"] == sample["publisher"]
        assert row["status"]
        if row.get("source_status") == "verified_capture":
            assert row["source"] in fixture_catalog()
            assert row["source_evidence"]


@pytest.mark.parametrize("row", VERIFIED, ids=lambda row: row["sample_id"])
def test_verified_original_has_same_identity_capture(row):
    body = (REPO_ROOT / row["source"]).read_bytes()
    assert hashlib.sha256(body).hexdigest() == row["source_sha256"]
    matched_records = []
    for evidence in row["source_evidence"]:
        records = json.loads((REPO_ROOT / evidence["provenance"]).read_text())[
            "records"
        ]
        matched_records.extend(
            record
            for record in records
            if record.get("doi", "").casefold() == row["doi"].casefold()
            and record.get("sha256") == row["source_sha256"]
            and record.get("size") == len(body)
            and record.get("captured_at_utc")
            and record.get("capture_kind")
        )
    assert matched_records
    if row["status"] in {"verified_abstract_page", "verified_ancillary_page"}:
        # These six original pages establish excerpt/template provenance only.
        arxiv_id = row["doi"].split("arxiv.", 1)[1]
        soup = BeautifulSoup(body, "lxml")
        assert arxiv_id in soup.title.get_text()
        assert any(
            f"/{arxiv_id}" in record["requested_url"] for record in matched_records
        )
    elif row.get("identity_companion"):
        landing = (REPO_ROOT / row["identity_companion"]).read_bytes()
        assert hashlib.sha256(landing).hexdigest() == row["identity_companion_sha256"]
        companion_evidence = source_evidence(
            fixture_catalog()[row["identity_companion"]],
            capture_index(),
            rejected_source_hashes(),
        )
        assert companion_evidence["status"] == "verified_capture"
        if row["format"] == "pdf":
            identity = pdf_landing_identity(
                body,
                row["provider"],
                row["doi"],
                row["source_url"],
                landing,
                row["identity"]["companion_url"],
            )
            assert identity and identity["all_pages_readable"]
        else:
            identity = ieee_fragment_identity(
                body, row["doi"], row["source_url"], landing
            )
        assert identity and identity["identity"] == "matched"
    else:
        identity = inspect_original(
            body, row["provider"], row["doi"], row["source_url"]
        )
        assert identity and identity["identity"] == "matched"
        if identity["format"] == "pdf":
            assert identity["all_pages_readable"] and identity["pages"] > 0


@pytest.mark.parametrize("row", FULLTEXT, ids=lambda row: row["sample_id"])
def test_verified_html_xml_original_replays_as_fulltext(row):
    article = build_verified_source_article(row)
    assert article.doi.casefold() == row["doi"].casefold()
    assert article.quality.has_fulltext
    assert article.quality.content_kind == "fulltext"
    assert any(
        section.text.strip() for section in article.sections if section.kind == "body"
    )
