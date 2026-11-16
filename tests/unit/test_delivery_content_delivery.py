from __future__ import annotations


from paper_fetch.delivery.fetch_cache import cached_request_matches
from paper_fetch.delivery.requests import FetchPaperRequest


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
