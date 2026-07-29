from __future__ import annotations

import json

import pytest

from paper_fetch.metadata.crossref import CrossrefLookupClient
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.reason_codes import IDENTITY_MISMATCH


class _ResponseTransport:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def request(self, _method: str, url: str, **_kwargs):
        return {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "body": self.body,
            "url": url,
        }


def _lookup(body: bytes) -> CrossrefLookupClient:
    return CrossrefLookupClient(_ResponseTransport(body), {})


def test_crossref_invalid_json_preserves_stable_error_category() -> None:
    with pytest.raises(ProviderFailure) as raised:
        _lookup(b"<html>not JSON</html>").fetch_metadata({"doi": "10.1000/expected"})

    assert raised.value.error_category == "invalid_json"
    assert "<html>not JSON</html>" in raised.value.message


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"status": "ok"},
        {"message": []},
    ],
)
def test_crossref_schema_mismatch_is_not_reported_as_invalid_json(payload) -> None:
    with pytest.raises(ProviderFailure) as raised:
        _lookup(json.dumps(payload).encode()).fetch_metadata(
            {"doi": "10.1000/expected"}
        )

    assert raised.value.error_category == "response_schema_mismatch"


def test_crossref_endpoint_doi_mismatch_is_rejected() -> None:
    payload = {
        "message": {
            "DOI": "10.1000/different",
            "title": ["Different article"],
        }
    }

    with pytest.raises(ProviderFailure) as raised:
        _lookup(json.dumps(payload).encode()).fetch_metadata(
            {"doi": "10.1000/expected"}
        )

    assert raised.value.code == IDENTITY_MISMATCH
