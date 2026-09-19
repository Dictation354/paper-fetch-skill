"""Shared test support; contains no collected tests."""

import hashlib
import json
from tests.golden_criteria import golden_criteria_asset
from tests.golden_corpus import GoldenCorpusFixture
from tests.paths import REPO_ROOT
from tests.support.test_evidence import evidence_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class CapturedSourceFixture(GoldenCorpusFixture):
    """Replay a separately recorded entity without replacing historical inputs."""

    @property
    def raw_path(self):
        return REPO_ROOT / self.sample["captured_source_path"]


@evidence_cache
def capture_records(doi):
    return json.loads(
        golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
    )["records"]


def captured_body(doi, record):
    body = golden_criteria_asset(doi, record["body_file"]).read_bytes()
    assert len(body) == record["size"]
    assert hashlib.sha256(body).hexdigest() == record["sha256"]
    return body


def _record(doi, filename):
    records = capture_records(doi)
    record = next(
        (r for r in records if r.get("original_body_file", r["body_file"]) == filename),
        None,
    )
    if record is None:
        record = next(r for r in records if r["body_file"] == filename)
    return record, captured_body(doi, record)


def capture_url_identity(url, *, provider=None):
    """Exact by default; ignore only known expiring signatures for opted-in CDNs."""
    if provider not in {"acs", "aip", "oxfordacademic", "royalsocietypublishing"}:
        return url
    parts = urlsplit(url)
    cdn = {
        "acs": "acs",
        "aip": "aipp",
        "oxfordacademic": "oup",
        "royalsocietypublishing": "trs",
    }[provider]
    if parts.hostname != cdn + ".silverchair-cdn.com":
        return url
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in {"expires", "signature", "key-pair-id", "policy"}
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _response(record, body):
    return {
        "status_code": record["status_code"],
        "headers": record["response_headers"],
        "url": record["final_url"],
        "body": body,
    }
