# ruff: noqa: F403,F405
from __future__ import annotations

from contextvars import copy_context
from paper_fetch.config import BROWSER_AUTO_PREPARE_ENV_VAR
from paper_fetch.mcp import log_bridge as mcp_log_bridge
from paper_fetch.mcp.batch import run_blocking_call
from paper_fetch.mcp.log_bridge import PaperFetchLogBridge
from paper_fetch.runtime import RuntimeContext

from ._mcp_support import *


class McpAsyncToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocking_cancel_grace_fences_late_artifact_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "late.pdf"
            started = threading.Event()
            release = threading.Event()
            late_finished = threading.Event()
            late_error: list[Exception] = []
            cancelled = threading.Event()
            context = RuntimeContext(
                env={},
                download_dir=Path(tmpdir),
                cancel_check=cancelled.is_set,
            )

            def worker() -> None:
                started.set()
                assert release.wait(timeout=2)
                try:
                    assert context.artifact_store is not None
                    context.artifact_store.write_bytes_file(target, b"late")
                except Exception as error:
                    late_error.append(error)
                finally:
                    late_finished.set()

            task = asyncio.create_task(
                run_blocking_call(
                    worker,
                    cancel_event=cancelled,
                    cancel_fence=context.fence_commits,
                    cancel_grace_seconds=0.03,
                )
            )
            await wait_for_threading_event(started, 1.0)
            cancelled_at = time.monotonic()
            task.cancel()
            asyncio.get_running_loop().call_later(0.005, task.cancel)
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertGreaterEqual(time.monotonic() - cancelled_at, 0.02)
            release.set()
            await wait_for_threading_event(late_finished, 1.0)
            context.close()

            self.assertFalse(target.exists())
            self.assertEqual(len(late_error), 1)
            self.assertIsInstance(late_error[0], mcp_tools.RequestCancelledError)

    async def test_overlapping_log_bridges_do_not_cross_talk_or_leak_level(
        self,
    ) -> None:
        logger = logging.getLogger("paper_fetch.service")
        original_level = logger.level
        first = FakeContext()
        first.request_id = "request-one"
        second = FakeContext()
        second.request_id = "request-two"
        both_entered = asyncio.Event()
        entered_count = 0
        entered_lock = asyncio.Lock()

        async def run_request(ctx, query: str) -> None:
            nonlocal entered_count
            with PaperFetchLogBridge(ctx=ctx, loop=asyncio.get_running_loop()):
                async with entered_lock:
                    entered_count += 1
                    if entered_count == 2:
                        both_entered.set()
                await both_entered.wait()
                logging.getLogger("paper_fetch.service").debug(
                    "request scoped log",
                    extra={
                        "structured_data": {
                            "event": "request_scoped",
                            "query": query,
                        }
                    },
                )
                await asyncio.sleep(0.02)

        await asyncio.gather(
            run_request(first, "10.1000/one"),
            run_request(second, "10.1000/two"),
        )
        await asyncio.sleep(0.05)

        self.assertEqual(
            [message["data"]["query"] for message in first.session.messages],
            ["10.1000/one"],
        )
        self.assertEqual(
            [message["data"]["query"] for message in second.session.messages],
            ["10.1000/two"],
        )
        self.assertEqual(first.session.messages[0]["related_request_id"], "request-one")
        self.assertEqual(
            second.session.messages[0]["related_request_id"], "request-two"
        )
        self.assertEqual(logger.level, original_level)

    async def test_exited_log_target_rejects_late_copied_context_worker(self) -> None:
        logger = logging.getLogger("paper_fetch.service")
        original_level = logger.level
        first = FakeContext()
        first.request_id = "request-one"
        second = FakeContext()
        second.request_id = "request-two"
        first_entered = asyncio.Event()
        second_entered = asyncio.Event()
        first_exited = asyncio.Event()
        release_late_worker = threading.Event()
        late_worker_started = threading.Event()
        late_worker_finished = threading.Event()
        overlap_handler_counts: list[list[int]] = []
        after_first_exit_handler_counts: list[list[int]] = []
        worker_threads: list[threading.Thread] = []

        def router_handler_counts() -> list[int]:
            return [
                sum(
                    handler is mcp_log_bridge._GLOBAL_LOG_ROUTER
                    for handler in logging.getLogger(logger_name).handlers
                )
                for logger_name in mcp_log_bridge._FETCH_LOGGER_NAMES
            ]

        async def run_first_request() -> None:
            with PaperFetchLogBridge(ctx=first, loop=asyncio.get_running_loop()):
                worker_context = copy_context()

                def late_worker() -> None:
                    late_worker_started.set()
                    assert release_late_worker.wait(timeout=2)
                    worker_context.run(
                        logger.debug,
                        "late request scoped log",
                        extra={
                            "structured_data": {
                                "event": "request_scoped",
                                "query": "10.1000/late-one",
                            }
                        },
                    )
                    late_worker_finished.set()

                worker = threading.Thread(target=late_worker, daemon=True)
                worker_threads.append(worker)
                worker.start()
                self.assertTrue(
                    await wait_for_threading_event(late_worker_started, 1.0)
                )
                first_entered.set()
                await second_entered.wait()
            first_exited.set()

        async def run_second_request() -> None:
            await first_entered.wait()
            with PaperFetchLogBridge(ctx=second, loop=asyncio.get_running_loop()):
                overlap_handler_counts.append(router_handler_counts())
                second_entered.set()
                await first_exited.wait()
                after_first_exit_handler_counts.append(router_handler_counts())
                logger.debug(
                    "active request scoped log",
                    extra={
                        "structured_data": {
                            "event": "request_scoped",
                            "query": "10.1000/two",
                        }
                    },
                )
                release_late_worker.set()
                self.assertTrue(
                    await wait_for_threading_event(late_worker_finished, 1.0)
                )
                await asyncio.sleep(0.05)

        await asyncio.gather(run_first_request(), run_second_request())
        for worker in worker_threads:
            worker.join(timeout=1)

        self.assertEqual(first.session.messages, [])
        self.assertEqual(
            [message["data"]["query"] for message in second.session.messages],
            ["10.1000/two"],
        )
        expected_active_handler_counts = [
            1 for _logger_name in mcp_log_bridge._FETCH_LOGGER_NAMES
        ]
        self.assertEqual(overlap_handler_counts, [expected_active_handler_counts])
        self.assertEqual(
            after_first_exit_handler_counts,
            [expected_active_handler_counts],
        )
        self.assertEqual(
            router_handler_counts(),
            [0 for _logger_name in mcp_log_bridge._FETCH_LOGGER_NAMES],
        )
        self.assertEqual(mcp_log_bridge._ROUTER_REFCOUNT, 0)
        self.assertEqual(logger.level, original_level)

    async def test_log_handler_does_not_construct_message_for_closed_loop(self) -> None:
        ctx = FakeContext()
        ctx.session.send_log_message = mock.Mock(
            side_effect=AssertionError("closed loop must not receive a coroutine")
        )
        closed_loop = asyncio.new_event_loop()
        closed_loop.close()
        handler = mcp_tools.StructuredLogNotificationHandler(
            ctx=ctx,
            loop=closed_loop,
        )
        record = logging.LogRecord(
            name="paper_fetch.service",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg="closed-loop log",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        ctx.session.send_log_message.assert_not_called()

    async def test_fetch_paper_auto_prepare_defaults_off_and_request_can_enable(
        self,
    ) -> None:
        observed: list[str] = []

        def fake_envelope(request, **kwargs):
            observed.append(kwargs["env"][BROWSER_AUTO_PREPARE_ENV_VAR])
            return sample_envelope(
                modes=set(request.requested_modes()),
                doi=request.query,
            )

        deps = mcp_test_deps(
            build_runtime_env=lambda env=None: dict(env or {}),
            fetch_paper_envelope=fake_envelope,
        )
        first = await mcp_tools.fetch_paper_tool_async(
            query="10.1000/default-off",
            no_download=True,
            download_dir=None,
            deps=deps,
        )
        second = await mcp_tools.fetch_paper_tool_async(
            query="10.1000/explicit-on",
            no_download=True,
            browser_auto_prepare=True,
            download_dir=None,
            deps=deps,
        )

        self.assertFalse(first.is_error)
        self.assertFalse(second.is_error)
        self.assertEqual(observed, ["false", "true"])

    async def test_structured_log_notification_handler_prefers_structured_data_with_spaces(
        self,
    ) -> None:
        ctx = FakeContext()
        handler = mcp_tools.StructuredLogNotificationHandler(
            ctx=ctx, loop=asyncio.get_running_loop()
        )
        record = logging.LogRecord(
            name="paper_fetch.service",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg="official_provider_result provider=wiley note=message with spaces",
            args=(),
            exc_info=None,
        )
        record.structured_data = {
            "event": "official_provider_result",
            "provider": "wiley",
            "note": "message with spaces",
            "url": "https://publisher.example/file?X-Amz-Signature=secret",
            "headers": {"Wiley-TDM-Client-Token": "private-token"},
        }

        handler.emit(record)
        await asyncio.sleep(0.05)

        self.assertEqual(
            ctx.session.messages[0]["data"],
            {
                "event": "official_provider_result",
                "provider": "wiley",
                "note": "message with spaces",
                "url": "https://publisher.example/file",
                "headers": {"Wiley-TDM-Client-Token": "***"},
                "logger": "paper_fetch.service",
            },
        )

    async def test_fetch_paper_tool_async_reports_progress_and_bridges_logs(
        self,
    ) -> None:
        ctx = FakeContext()
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            logging.getLogger("paper_fetch.service").debug(
                "fetch_stage query=%s attempt=%s", query, 1
            )
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with (
            mock.patch.object(
                mcp_tools,
                "build_runtime_env",
                return_value={"PAPER_FETCH_HTTP_DISK_CACHE": "1"},
            ),
            mock.patch.object(
                mcp_tools,
                "resolve_mcp_download_dir",
                return_value=Path("/tmp/downloads"),
            ),
            mock.patch.object(
                mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
            ),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            result = await mcp_tools.fetch_paper_tool_async(
                query="10.1000/example",
                ctx=ctx,
            )
            await asyncio.sleep(0.05)

        self.assertFalse(result.is_error)
        self.assertEqual(
            ctx.progress,
            [
                (0, 4, "Validating fetch_paper request"),
                (1, 4, "Fetching paper content"),
                (3, 4, "Shaping MCP result"),
                (4, 4, "fetch_paper complete"),
            ],
        )
        self.assertEqual(ctx.session.messages[0]["data"]["event"], "fetch_stage")
        self.assertEqual(ctx.session.messages[0]["data"]["query"], "10.1000/example")
        self.assertEqual(captured["context"].artifact_mode, "markdown-assets")
        self.assertIsNone(captured["context"].transport.disk_cache_dir)
        self.assertEqual(result.structured_content["status"], "ok")
        self.assertEqual(
            result.structured_content["acceptance"],
            {
                "overall": "degraded",
                "identity": "resolved",
                "fetch": "ok",
                "content": "fulltext",
                "asset": "not_requested",
                "output": "complete",
                "provenance": "complete",
                "acquisition": {
                    "provider": "elsevier",
                    "route": "xml_api",
                    "representation": "xml",
                    "transport": "api",
                    "fallback_used": False,
                },
                "has_fulltext": True,
                "has_abstract": True,
                "token_estimate": 128,
            },
        )

    async def test_fetch_paper_tool_async_sets_cancellation_flag_for_worker_transport(
        self,
    ) -> None:
        started = threading.Event()
        cancelled_seen = threading.Event()

        def fake_fetch_paper(query, **kwargs):
            started.set()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                context = kwargs["context"]
                transport = context.transport if context is not None else None
                if transport is not None and transport.cancelled:
                    cancelled_seen.set()
                    raise mcp_tools.RequestCancelledError("Request cancelled.")
                time.sleep(0.01)
            return sample_envelope(modes={"article", "markdown"})

        with mock.patch.object(
            mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
        ):
            task = asyncio.create_task(
                mcp_tools.fetch_paper_tool_async(query="10.1000/example")
            )
            await wait_for_threading_event(started, 1.0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await wait_for_threading_event(cancelled_seen, 1.0)

        self.assertTrue(cancelled_seen.is_set())

    async def test_batch_resolve_tool_async_sets_cancellation_flag_for_worker_transport(
        self,
    ) -> None:
        started = threading.Event()
        cancelled_seen = threading.Event()

        def fake_resolve(query, *, context=None):
            started.set()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                transport = context.transport if context is not None else None
                if transport is not None and transport.cancelled:
                    cancelled_seen.set()
                    raise mcp_tools.RequestCancelledError("Request cancelled.")
                time.sleep(0.01)
            return sample_resolved_query(query)

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", side_effect=fake_resolve
        ):
            task = asyncio.create_task(
                mcp_tools.batch_resolve_tool_async(
                    queries=["10.1000/one", "10.1000/two"],
                    concurrency=1,
                )
            )
            await wait_for_threading_event(started, 1.0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await wait_for_threading_event(cancelled_seen, 1.0)

        self.assertTrue(cancelled_seen.is_set())

    async def test_batch_check_tool_async_reports_per_query_progress(self) -> None:
        ctx = FakeContext()

        def fake_probe(query, *, context=None):
            logging.getLogger("paper_fetch.http").debug(
                "batch_check_item query=%s status=%s", query, "ok"
            )
            return sample_probe_result(query, doi=query, title=f"Title for {query}")

        with mock.patch.object(
            mcp_tools, "service_probe_has_fulltext", side_effect=fake_probe
        ):
            result = await mcp_tools.batch_check_tool_async(
                queries=["10.1000/one", "10.1000/two"],
                mode="metadata",
                ctx=ctx,
            )
            await asyncio.sleep(0.05)

        self.assertFalse(result.is_error)
        self.assertEqual(
            ctx.progress,
            [
                (0, 2, "Starting batch_check"),
                (
                    1,
                    2,
                    "Checked terminal 1 of 2 queries (completed=1, not_scheduled=0)",
                ),
                (
                    2,
                    2,
                    "Checked terminal 2 of 2 queries (completed=2, not_scheduled=0)",
                ),
                (2, 2, "batch_check terminalized (terminal=2, not_scheduled=0)"),
            ],
        )
        self.assertTrue(
            any(
                message["data"]["event"] == "batch_check_item"
                for message in ctx.session.messages
            )
        )

    async def test_batch_check_applies_browser_prepare_request_override(self) -> None:
        observed: list[str] = []

        def fake_probe(query, *, context=None):
            observed.append(context.env[BROWSER_AUTO_PREPARE_ENV_VAR])
            return sample_probe_result(query, doi=query, title="Title")

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(
                mcp_tools,
                "service_probe_has_fulltext",
                side_effect=fake_probe,
            ),
        ):
            result = await mcp_tools.batch_check_tool_async(
                queries=["10.1000/one"],
                mode="metadata",
                browser_auto_prepare=True,
            )

        self.assertFalse(result.is_error)
        self.assertEqual(observed, ["true"])

    async def test_batch_check_tool_async_rejects_too_many_queries(self) -> None:
        result = await mcp_tools.batch_check_tool_async(
            queries=[f"10.1000/{index}" for index in range(51)],
            mode="metadata",
        )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "error")
        self.assertIn(
            "queries must contain at most 50 entries.",
            result.structured_content["reason"],
        )

    async def test_batch_resolve_tool_async_reports_per_query_progress(self) -> None:
        ctx = FakeContext()

        def fake_resolve(query, *, context=None):
            logging.getLogger("paper_fetch.service").debug(
                "batch_resolve_item query=%s status=%s", query, "ok"
            )
            return sample_resolved_query(query)

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", side_effect=fake_resolve
        ):
            result = await mcp_tools.batch_resolve_tool_async(
                queries=["10.1000/one", "10.1000/two"],
                ctx=ctx,
            )
            await asyncio.sleep(0.05)

        self.assertFalse(result.is_error)
        self.assertEqual(
            ctx.progress,
            [
                (0, 2, "Starting batch_resolve"),
                (
                    1,
                    2,
                    "Resolved terminal 1 of 2 queries (completed=1, not_scheduled=0)",
                ),
                (
                    2,
                    2,
                    "Resolved terminal 2 of 2 queries (completed=2, not_scheduled=0)",
                ),
                (
                    2,
                    2,
                    "batch_resolve terminalized (terminal=2, not_scheduled=0)",
                ),
            ],
        )
        self.assertTrue(
            any(
                message["data"]["event"] == "batch_resolve_item"
                for message in ctx.session.messages
            )
        )

    async def test_batch_resolve_tool_async_aborts_with_retry_after_details(
        self,
    ) -> None:
        ctx = FakeContext()
        seen_queries: list[str] = []

        def fake_resolve(query, *, context=None):
            seen_queries.append(query)
            if query == "10.1000/two":
                raise ProviderFailure(
                    "rate_limited",
                    "Slow down.",
                    retry_after_seconds=5,
                )
            return sample_resolved_query(query)

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", side_effect=fake_resolve
        ):
            result = await mcp_tools.batch_resolve_tool_async(
                queries=["10.1000/one", "10.1000/two", "10.1000/three"],
                concurrency=1,
                ctx=ctx,
            )

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["schema_version"], 2)
        self.assertTrue(result.structured_content["aborted"])
        self.assertEqual(
            result.structured_content["abort_reason"]["status"], "rate_limited"
        )
        self.assertEqual(
            result.structured_content["abort_reason"]["code"], "rate_limited"
        )
        self.assertEqual(
            result.structured_content["abort_reason"]["retry_after_seconds"], 5
        )
        self.assertEqual(seen_queries, ["10.1000/one", "10.1000/two"])
        self.assertEqual(
            ctx.progress[-1],
            (3, 3, "batch_resolve terminalized (terminal=3, not_scheduled=1)"),
        )

    async def test_batch_resolve_tool_async_rejects_too_many_queries(self) -> None:
        result = await mcp_tools.batch_resolve_tool_async(
            queries=[f"10.1000/{index}" for index in range(51)],
        )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "error")
        self.assertIn(
            "queries must contain at most 50 entries.",
            result.structured_content["reason"],
        )
