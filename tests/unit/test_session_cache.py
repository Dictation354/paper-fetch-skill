from __future__ import annotations

import unittest

from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.session_cache import (
    RESOLVED_QUERY_KEY,
    cached_call,
    get_cached,
)


class SessionCacheTests(unittest.TestCase):
    def test_cached_call_misses_then_hits_cached_value(self) -> None:
        context = RuntimeContext(env={})
        calls = {"count": 0}

        def factory() -> dict[str, list[int]]:
            calls["count"] += 1
            return {"calls": [calls["count"]]}

        first = cached_call(RESOLVED_QUERY_KEY, ("10.1000/example",), context, factory)
        first["calls"].append(99)
        second = cached_call(RESOLVED_QUERY_KEY, ("10.1000/example",), context, factory)

        self.assertEqual(calls["count"], 1)
        self.assertEqual(second, {"calls": [1]})

    def test_get_cached_returns_none_for_missing_and_cached_value_for_hit(self) -> None:
        context = RuntimeContext(env={})

        self.assertIsNone(get_cached(RESOLVED_QUERY_KEY, ("missing",), context))
        cached_call(
            RESOLVED_QUERY_KEY, ("present",), context, lambda: {"query": "present"}
        )

        self.assertEqual(
            get_cached(RESOLVED_QUERY_KEY, ("present",), context), {"query": "present"}
        )


if __name__ == "__main__":
    unittest.main()
