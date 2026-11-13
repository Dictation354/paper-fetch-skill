import json
import pytest
from paper_fetch.models import FetchEnvelope
from paper_fetch.models.codec import (
    envelope_from_payload,
    article_from_payload,
    trace_from_payload,
)
from paper_fetch.mcp.fetch_cache import FetchCache
from paper_fetch.mcp.cache_index import read_cache_index
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.tracing import trace_event, TraceContext
from tests.support._mcp_support import sample_envelope


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
        FetchEnvelope(doi=None, source="test", has_fulltext=True)
    with pytest.raises(ValueError):
        trace_from_payload(["fulltext:legacy_ok"])
    value = sample_envelope(modes={"markdown"}).to_dict()
    with pytest.raises(ValueError):
        envelope_from_payload({**value, "has_fulltext": True})
    with pytest.raises(ValueError):
        envelope_from_payload({**value, "source_trail": []})


def test_old_cache_versions_are_reported_and_bytes_preserved(tmp_path):
    envelope = sample_envelope(modes={"markdown"})
    cache = FetchCache(tmp_path)
    request = FetchPaperRequest(query=envelope.doi, preset="cacheable_read")
    cache.write_fetch_envelope(envelope, request)
    for path in tmp_path.glob("*.fetch-envelope.json"):
        value = json.loads(path.read_text())
        value["version"] = 5
        path.write_text(json.dumps(value))
    before = {
        path: path.read_bytes() for path in tmp_path.glob("*.fetch-envelope.json")
    }
    result = cache.get_payload(envelope.doi, request=request, detail="compact")
    assert result["sidecar"]["status"] == "version_mismatch"
    assert all(path.read_bytes() == value for path, value in before.items())
    index = tmp_path / ".paper-fetch-cache-index.json"
    # The index owner's filename is public through its cache record.
    from paper_fetch.mcp.cache_index import INDEX_FILENAME

    index = tmp_path / INDEX_FILENAME
    value = json.loads(index.read_text())
    value["version"] = 2
    index.write_text(json.dumps(value))
    before = index.read_bytes()
    assert read_cache_index(tmp_path).index_status == "version_mismatch"
    assert index.read_bytes() == before
