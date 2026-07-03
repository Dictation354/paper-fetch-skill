from __future__ import annotations

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from paper_fetch.runtime import RuntimeContext


WORKER_COUNT = 6


def _parse_cache_key(context: RuntimeContext, role: str) -> tuple[Any, ...]:
    return context.build_parse_cache_key(
        provider="unit",
        role=role,
        source="https://example.test/article",
        body="<article>body</article>",
        parser="unit-test",
    )


class RuntimeParseCacheTests(unittest.TestCase):
    def test_parse_cache_accessors_copy_mutable_values_by_default(self) -> None:
        context = RuntimeContext(env={})
        key = _parse_cache_key(context, "copy-accessors")

        original = {"authors": ["Alice Example"]}
        stored = context.set_parse_cache(key, original)
        stored["authors"].append("Returned Mutation")
        original["authors"].append("Original Mutation")

        cached = context.get_parse_cache(key)
        cached["authors"].append("Cached Mutation")

        self.assertEqual(context.get_parse_cache(key), {"authors": ["Alice Example"]})

    def test_get_or_set_parse_cache_is_atomic_and_returns_copies(self) -> None:
        context = RuntimeContext(env={})
        key = _parse_cache_key(context, "atomic-copy")
        ready = threading.Barrier(WORKER_COUNT + 1)
        factory_started = threading.Event()
        release_factory = threading.Event()
        calls_lock = threading.Lock()
        factory_calls = 0

        def factory() -> dict[str, list[str]]:
            nonlocal factory_calls
            with calls_lock:
                factory_calls += 1
            factory_started.set()
            if not release_factory.wait(timeout=5):
                raise TimeoutError("factory was not released")
            return {"authors": ["Alice Example"]}

        def worker(index: int) -> dict[str, list[str]]:
            ready.wait(timeout=5)
            cached = context.get_or_set_parse_cache(key, factory)
            cached["authors"].append(f"worker-{index}")
            return cached

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
            futures = [executor.submit(worker, index) for index in range(WORKER_COUNT)]
            ready.wait(timeout=5)
            self.assertTrue(factory_started.wait(timeout=5))
            release_factory.set()
            results = [future.result(timeout=5) for future in futures]

        self.assertEqual(factory_calls, 1)
        self.assertEqual(
            context.get_parse_cache(key),
            {"authors": ["Alice Example"]},
        )
        self.assertEqual(len({id(result) for result in results}), WORKER_COUNT)
        self.assertEqual(
            len({id(result["authors"]) for result in results}),
            WORKER_COUNT,
        )
        for index, result in enumerate(results):
            self.assertEqual(result, {"authors": ["Alice Example", f"worker-{index}"]})

    def test_get_or_set_parse_cache_copy_value_false_reuses_shared_object(self) -> None:
        context = RuntimeContext(env={})
        key = _parse_cache_key(context, "atomic-shared")
        ready = threading.Barrier(WORKER_COUNT + 1)
        factory_started = threading.Event()
        release_factory = threading.Event()
        calls_lock = threading.Lock()
        factory_calls = 0
        shared_payload = object()

        def factory() -> object:
            nonlocal factory_calls
            with calls_lock:
                factory_calls += 1
            factory_started.set()
            if not release_factory.wait(timeout=5):
                raise TimeoutError("factory was not released")
            return shared_payload

        def worker() -> object:
            ready.wait(timeout=5)
            return context.get_or_set_parse_cache(key, factory, copy_value=False)

        with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
            futures = [executor.submit(worker) for _ in range(WORKER_COUNT)]
            ready.wait(timeout=5)
            self.assertTrue(factory_started.wait(timeout=5))
            release_factory.set()
            results = [future.result(timeout=5) for future in futures]

        self.assertEqual(factory_calls, 1)
        self.assertTrue(all(result is shared_payload for result in results))
        self.assertIs(context.get_parse_cache(key, copy_value=False), shared_payload)


if __name__ == "__main__":
    unittest.main()
