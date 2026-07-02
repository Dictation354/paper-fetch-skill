# ruff: noqa: F403,F405
from __future__ import annotations

from ._mcp_support import *


class McpAsyncToolTests(unittest.IsolatedAsyncioTestCase):
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
        }

        handler.emit(record)
        await asyncio.sleep(0.05)

        self.assertEqual(
            ctx.session.messages[0]["data"],
            {
                "event": "official_provider_result",
                "provider": "wiley",
                "note": "message with spaces",
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

        self.assertFalse(result.isError)
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

        self.assertFalse(result.isError)
        self.assertEqual(
            ctx.progress,
            [
                (0, 2, "Starting batch_check"),
                (1, 2, "Checked 1 of 2 queries"),
                (2, 2, "Checked 2 of 2 queries"),
                (2, 2, "batch_check complete"),
            ],
        )
        self.assertTrue(
            any(
                message["data"]["event"] == "batch_check_item"
                for message in ctx.session.messages
            )
        )

    async def test_batch_check_tool_async_rejects_too_many_queries(self) -> None:
        result = await mcp_tools.batch_check_tool_async(
            queries=[f"10.1000/{index}" for index in range(51)],
            mode="metadata",
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn(
            "queries must contain at most 50 entries.",
            result.structuredContent["reason"],
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

        self.assertFalse(result.isError)
        self.assertEqual(
            ctx.progress,
            [
                (0, 2, "Starting batch_resolve"),
                (1, 2, "Resolved 1 of 2 queries"),
                (2, 2, "Resolved 2 of 2 queries"),
                (2, 2, "batch_resolve complete"),
            ],
        )
        self.assertTrue(
            any(
                message["data"]["event"] == "batch_resolve_item"
                for message in ctx.session.messages
            )
        )

    async def test_batch_resolve_tool_async_rejects_too_many_queries(self) -> None:
        result = await mcp_tools.batch_resolve_tool_async(
            queries=[f"10.1000/{index}" for index in range(51)],
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn(
            "queries must contain at most 50 entries.",
            result.structuredContent["reason"],
        )
