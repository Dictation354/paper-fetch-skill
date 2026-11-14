from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json


from paper_fetch.mcp.batch_fetch import batch_fetch_tool_async
from paper_fetch.mcp.content_delivery import content_snapshot, formula_locations
from paper_fetch.mcp.content_store import (
    ContentSnapshot,
    ContentStore,
    read_content_tool,
)
from paper_fetch.mcp.fetch_cache import cached_request_matches
from paper_fetch.mcp.fetch_tool import build_fetch_tool_result, fetch_paper_tool_async
from paper_fetch.mcp.schemas import FetchPaperRequest, ReadContentRequest
from paper_fetch.models import TRUNCATION_WARNING
from tests.support._mcp_support import (
    mcp_test_deps,
    sample_envelope,
    sample_resolved_query,
)


def read(store, ref, **kwargs):
    return store.read(ReadContentRequest(content_id=ref["content_id"], **kwargs))


def all_text(store, ref, view, max_chars=13):
    chunks = []
    offset = 0
    while True:
        p = read(store, ref, view=view, offset=offset, max_chars=max_chars)
        assert p["status"] == "ok"
        assert p["offset"] == offset
        assert p["returned_chars"] == len(p["text"])
        chunks.append(p["text"])
        offset = p["next_offset"]
        if p["eof"]:
            assert offset == p["total_chars"]
            return "".join(chunks)


def test_long_unicode_snapshots_roundtrip_and_json_can_be_reassembled():
    envelope = sample_envelope(modes={"article", "markdown"})
    envelope.markdown = "## 中文😀\n\n" + "中文𐐷😀 $x$\n" * 2000
    envelope.article.quality.semantic_losses.formula_diagnostics = [
        {"node_id": "f1", "final_latex": "x"}
    ]
    request = FetchPaperRequest(
        query=envelope.doi,
        strategy={"asset_profile": "none"},
    )
    store = ContentStore()
    snapshot = content_snapshot(envelope, request)
    p = build_fetch_tool_result(
        envelope, request, content_store=store
    ).structured_content
    assert not {"article", "markdown", "trace", "quality"} & p.keys()
    assert p["metadata"]["title"] == envelope.article.metadata.title
    for view, expected in snapshot.views.items():
        assert p["content_ref"]["views"][view]["total_chars"] == len(expected)
        value = all_text(store, p["content_ref"], view, max_chars=97)
        assert value == expected
        if view != "markdown":
            assert isinstance(json.loads(value), dict)
    diagnostics = json.loads(all_text(store, p["content_ref"], "diagnostics", 20000))
    assert diagnostics["acceptance"]["identity"]["status"] == "resolved"
    assert diagnostics["formula_locations"][0]["status"] == "ambiguous"


def test_idle_refresh_lru_eviction_and_instance_isolation():
    clock = [0.0]
    store = ContentStore(max_bytes=6, idle_ttl=10, timer=lambda: clock[0])
    a, b = store.register_many(
        [ContentSnapshot({"markdown": "aaa"}), ContentSnapshot({"markdown": "bbb"})]
    )
    clock[0] = 9
    assert read(store, a)["status"] == "ok"
    c = store.register_many([ContentSnapshot({"markdown": "ccc"})])[0]
    assert read(store, b)["code"] == "content_handle_expired"
    assert read(ContentStore(), a)["code"] == "content_handle_expired"
    clock[0] = 11
    assert read(store, a)["text"] == "aaa"
    clock[0] = 20
    assert read(store, c)["code"] == "content_handle_expired"
    assert read(store, a)["status"] == "ok"
    clock[0] = 31
    assert read(store, a)["code"] == "content_handle_expired"


def test_capacity_uses_utf8_and_admits_batch_without_eviction_of_new_handles():
    store = ContentStore(max_bytes=8)
    old = store.register_many([ContentSnapshot({"markdown": "old"})])[0]
    a, b, c = store.register_many(
        [
            ContentSnapshot({"markdown": "😀"}),
            ContentSnapshot({"markdown": "中文"}),
            ContentSnapshot({"markdown": "abcd"}),
        ]
    )
    assert b is None
    assert read(store, old)["code"] == "content_handle_expired"
    assert read(store, a)["text"] == "😀"
    assert read(store, c)["text"] == "abcd"
    assert store.register_many([ContentSnapshot({"markdown": "😀😀😀"})]) == [None]
    assert read(store, a)["text"] == "😀"


def test_read_errors_and_eof_preserve_render_truncation():
    store = ContentStore()
    ref = store.register_many([ContentSnapshot({"markdown": "a😀"}, True)])[0]
    assert read(store, ref, view="article")["code"] == "content_view_unavailable"
    assert read(store, ref, offset=3)["code"] == "content_range_out_of_bounds"
    p = read(store, ref, offset=2)
    assert p["text"] == "" and p["eof"] and p["render_truncated"]
    for arguments in (
        {"max_chars": 0},
        {"max_chars": 20001},
        {"offset": -1},
        {"offset": True},
        {"max_chars": "5"},
        {"extra": 1},
    ):
        p = read_content_tool(store, content_id=ref["content_id"], **arguments)
        assert p.is_error and p.structured_content["code"] == "validation_error"


def test_concurrent_reading_keeps_snapshots_intact():
    store = ContentStore()
    ref = store.register_many([ContentSnapshot({"markdown": "文😀" * 100})])[0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(lambda _: all_text(store, ref, "markdown"), range(8)))
    assert values == ["文😀" * 100] * 8


def test_only_requested_body_views_are_retained_and_capacity_does_not_change_acceptance():
    envelope = sample_envelope(modes={"article", "markdown"})
    request = FetchPaperRequest(query=envelope.doi, modes=["markdown"])
    assert set(content_snapshot(envelope, request).views) == {"markdown", "diagnostics"}
    inline = build_fetch_tool_result(envelope, request).structured_content
    p = build_fetch_tool_result(
        envelope, request, content_store=ContentStore(max_bytes=1)
    ).structured_content
    assert p["content_ref"] is None
    assert p["warnings"][-1] == "content_store_capacity_exceeded"
    assert p["acceptance"] == inline["acceptance"]
    assert "article" not in p and "markdown" not in p
    assert p["output_artifacts"] == []
    envelope.markdown = "Quoted literal: " + TRUNCATION_WARNING
    assert not content_snapshot(envelope, request).render_truncated
    envelope.quality.warnings.append(TRUNCATION_WARNING)
    assert content_snapshot(envelope, request).render_truncated


def test_handle_delivery_uses_expanded_request_cache_semantics():
    request = FetchPaperRequest(query="10.1000/example", modes=["markdown"])
    cached = {
        "target": request.target,
        "modes": request.modes,
        "strategy": request.strategy.cache_request_payload(),
        "include_refs": request.include_refs,
        "max_tokens": request.max_tokens,
    }
    assert cached_request_matches(cached, request)
    assert not cached_request_matches(
        {**cached, "max_tokens": 1},
        request,
    )


def test_followups_only_read_handle_and_do_not_prepare_or_write(monkeypatch, tmp_path):
    calls = []

    def fetch(request, **_):
        calls.append(request.query)
        return sample_envelope(modes=request.requested_modes())

    store = ContentStore()
    result = asyncio.run(
        fetch_paper_tool_async(
            query="10.1000/example",
            modes=["markdown"],
            no_download=True,
            prefer_cache=False,
            artifact_mode="none",
            strategy={"asset_profile": "none"},
            download_dir=tmp_path,
            content_store=store,
            deps=mcp_test_deps(fetch_paper_envelope=fetch),
        )
    )
    assert not result.is_error

    def forbidden(*_, **__):
        raise AssertionError("read_content must only read the snapshot")

    monkeypatch.setattr(
        "paper_fetch.runtime.RuntimeContext.prepare_fetch_browser", forbidden
    )
    monkeypatch.setattr(
        "paper_fetch.workflow.rendering.save_markdown_to_disk", forbidden
    )
    monkeypatch.setattr("paper_fetch.http.HttpTransport.request", forbidden)
    for _ in range(3):
        assert (
            all_text(store, result.structured_content["content_ref"], "markdown")
            == "# Example Article\n\nExample body.\n"
        )
    assert calls == ["10.1000/example"]
    assert list(tmp_path.iterdir()) == []


def test_batch_aliases_share_handle_and_new_batch_capacity_is_explicit(tmp_path):
    calls = []

    def fetch(request, **_):
        calls.append(request.query)
        return sample_envelope(modes=request.requested_modes(), doi=request.query)

    deps = mcp_test_deps(
        fetch_paper_envelope=fetch, service_resolve_paper=sample_resolved_query
    )
    store = ContentStore()
    result = asyncio.run(
        batch_fetch_tool_async(
            queries=[
                "10.1000/example",
                "https://doi.org/10.1000/example",
                "10.1000/second",
            ],
            modes=["markdown"],
            no_download=True,
            artifact_mode="none",
            strategy={"asset_profile": "none"},
            content_store=store,
            deps=deps,
        )
    )
    assert not result.is_error
    p = result.structured_content
    assert p["execution_count"] == 2
    a, b, c = p["results"]
    assert [item["index"] for item in p["results"]] == [1, 2, 3]
    assert a["content_ref"] == b["content_ref"]
    assert a["content_ref"] != c["content_ref"]
    assert all("content" not in item for item in p["results"])
    assert all_text(store, a["content_ref"], "markdown")
    assert len(calls) == 2
    limited = asyncio.run(
        batch_fetch_tool_async(
            queries=["10.1000/example", "https://doi.org/10.1000/example"],
            modes=["markdown"],
            no_download=True,
            artifact_mode="none",
            strategy={"asset_profile": "none"},
            content_store=ContentStore(max_bytes=1),
            deps=deps,
        )
    )
    assert not limited.is_error
    for item in limited.structured_content["results"]:
        assert item["content_ref"] is None
        assert item["warnings"][-1] == "content_store_capacity_exceeded"
        assert item["acceptance"] == a["acceptance"]


def test_formula_locations_exact_unique_ambiguous_and_missing_do_not_rewrite_markdown():
    markdown = "# Paper\n## First\n$x$ $xy$\n```tex\n# Literal heading\n$x$\n```\n## Second\n$$\nx\n$$\n\\(z\\)\n"
    before = markdown
    p = formula_locations(
        markdown,
        [
            {"final_latex": "x"},
            {"final_latex": "z"},
            {"final_latex": "q"},
            {"final_latex": ""},
        ],
    )
    assert markdown == before
    assert [item["status"] for item in p] == [
        "ambiguous",
        "located",
        "unlocated",
        "unlocated",
    ]
    assert [c["section"] for c in p[0]["candidates"]] == ["First", "Second"]
    assert [markdown[c["start"] : c["end"]] for c in p[0]["candidates"]] == [
        "$x$",
        "$$\nx\n$$",
    ]
    assert (
        markdown[p[1]["candidates"][0]["start"] : p[1]["candidates"][0]["end"]]
        == "\\(z\\)"
    )


def test_handle_diagnostics_include_image_delivery_warnings(monkeypatch):
    warning = "A local figure was omitted from inline MCP image output."
    monkeypatch.setattr(
        "paper_fetch.mcp.fetch_tool._inline_image_contents",
        lambda *a, **k: ([], [warning]),
    )
    envelope = sample_envelope(modes={"article", "markdown"})
    store = ContentStore()
    request = FetchPaperRequest(
        query=envelope.doi,
        strategy={"asset_profile": "body"},
    )
    result = build_fetch_tool_result(envelope, request, content_store=store)
    assert warning in result.structured_content["warnings"]
    diagnostics = json.loads(
        all_text(store, result.structured_content["content_ref"], "diagnostics", 20000)
    )
    assert warning in diagnostics["response_warnings"]


def test_navigation_preserves_unicode_ranges_sections_and_literal_search():
    from paper_fetch.mcp.schemas import NavigateContentRequest

    text = "# 中文😀\nintro\n## Methods\nStraße α.B\n### Detail\nα.b\n```\n# fake\n```\n## Results\nend"
    store = ContentStore()
    ref = store.register_many([ContentSnapshot({"markdown": text})])[0]

    def navigate(**kwargs):
        return store.navigate(
            NavigateContentRequest(content_id=ref["content_id"], **kwargs)
        )

    first = navigate(mode="headings", max_results=2)
    assert [item["title"] for item in first["results"]] == ["中文😀", "Methods"]
    assert first["results"][1]["section_end"] == text.index("## Results")
    second = navigate(mode="headings", offset=first["next_offset"])
    assert [item["title"] for item in second["results"]] == ["Detail", "Results"]
    assert second["eof"]
    hit = navigate(mode="search", query="Α.b", max_results=1, context_chars=2)
    assert text[hit["results"][0]["start"] : hit["results"][0]["end"]] == "α.B"
    assert (
        hit["results"][0]["context"]
        == text[hit["results"][0]["context_start"] : hit["results"][0]["context_end"]]
    )
    tail = navigate(mode="search", query="Α.b", offset=hit["next_offset"])
    assert len(tail["results"]) == 1 and tail["eof"]
    assert navigate(mode="search", query="does not exist")["results"] == []
    assert (
        navigate(mode="headings", offset=len(text) + 1)["code"]
        == "content_range_out_of_bounds"
    )
    diagnostic = store.register_many([ContentSnapshot({"diagnostics": "{}"})])[0]
    assert (
        store.navigate(NavigateContentRequest(content_id=diagnostic["content_id"]))[
            "code"
        ]
        == "content_view_unavailable"
    )


def test_raw_provider_diagnostics_survive_envelope_cache_and_handle_projection():
    from paper_fetch.mcp.fetch_cache import payload_from_envelope
    from paper_fetch.models.codec import envelope_from_payload

    envelope = sample_envelope(modes={"article", "markdown"})
    envelope.diagnostics = envelope.article.diagnostics = {
        "pdf": {
            "bytes_transport": "browser_download",
            "final_url": "https://example.org/paper.pdf",
        },
        "html_failure": {
            "stage": "browser_context_create",
            "raw": ["raw diagnostic"] * 500,
        },
    }
    request = FetchPaperRequest(query=envelope.doi)
    cached = envelope_from_payload(payload_from_envelope(envelope, request))
    assert cached.diagnostics == envelope.diagnostics
    store = ContentStore()
    result = build_fetch_tool_result(
        cached, request, content_store=store
    ).structured_content
    assert "diagnostics" not in result
    assert (
        json.loads(all_text(store, result["content_ref"], "diagnostics"))["diagnostics"]
        == envelope.diagnostics
    )
