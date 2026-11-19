from __future__ import annotations

import json
from unittest import mock

import pytest

from paper_fetch.delivery.fetch_cache import FetchCache
from paper_fetch.delivery.requests import FetchPaperRequest
from paper_fetch.models import FetchEnvelope
from paper_fetch.models.codec import (
    article_from_payload,
    envelope_from_payload,
    trace_from_payload,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import TraceContext, trace_event
from tests.support.fetch_fixtures import sample_envelope


def test_envelope_round_trip_has_one_quality_and_acquisition_owner():
    envelope = sample_envelope(modes={"article", "markdown", "metadata"})
    envelope.trace = [
        trace_event("fulltext", "elsevier", "fail", context=TraceContext(attempt=1)),
        trace_event("fulltext", "elsevier", "ok", context=TraceContext(attempt=2)),
    ]
    value = envelope.to_dict()
    assert (
        not {"has_fulltext", "warnings", "source_trail", "token_estimate"}
        & value.keys()
    )
    assert not {"quality", "acquisition", "trace"} & value["article"].keys()
    decoded = envelope_from_payload(value)
    assert decoded.to_dict() == value
    assert decoded.quality is decoded.article.quality
    assert [event.attempt for event in decoded.trace] == [1, 2]
    standalone = article_from_payload(envelope.article.to_dict())
    assert standalone.to_dict() == envelope.article.to_dict()


def test_removed_model_projections_and_string_trace_are_rejected():
    with pytest.raises(TypeError):
        FetchEnvelope(doi=None, source="test", has_fulltext=True)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        trace_from_payload(["fulltext:legacy_ok"])
    value = sample_envelope(modes={"markdown"}).to_dict()
    with pytest.raises(ValueError):
        envelope_from_payload({**value, "has_fulltext": True})
    with pytest.raises(ValueError):
        envelope_from_payload({**value, "source_trail": []})


def test_old_cache_versions_are_ignored_and_bytes_preserved(tmp_path):
    envelope = sample_envelope(modes={"markdown"})
    cache = FetchCache(tmp_path)
    request = FetchPaperRequest(query=envelope.doi or "", prefer_cache=True)
    cache.write_fetch_envelope(envelope, request)
    for path in tmp_path.glob("*.fetch-envelope.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        value["version"] = 7
        path.write_text(json.dumps(value), encoding="utf-8")
    before = {
        path: path.read_bytes() for path in tmp_path.glob("*.fetch-envelope.json")
    }
    with RuntimeContext(env={}, download_dir=tmp_path) as context:
        loaded = cache.load_fetch_envelope(
            request,
            resolve_paper_fn=mock.Mock(),
            context=context,
        )
    assert loaded is None
    assert all(path.read_bytes() == value for path, value in before.items())
