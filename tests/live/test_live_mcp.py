from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from collections.abc import Mapping

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from paper_fetch.publisher_identity import normalize_doi
from tests.live._runtime_env import (
    build_isolated_live_env,
    is_machine_readable_no_access,
    preflight_selected_browser_or_skip,
    require_selected_browser_or_skip,
)
from tests.provider_benchmark_samples import (
    provider_benchmark_sample,
)
from tests.paths import REPO_ROOT, SRC_DIR


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"
ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
SPRINGER_SAMPLE = provider_benchmark_sample("springer")
SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")
AMS_SAMPLE = provider_benchmark_sample("ams")
IEEE_SAMPLE = provider_benchmark_sample("ieee")
ARXIV_SAMPLE = provider_benchmark_sample("arxiv")
COPERNICUS_SAMPLE = provider_benchmark_sample("copernicus")


class LiveMcpServerTests(unittest.IsolatedAsyncioTestCase):
    runtime_env_tempdir: tempfile.TemporaryDirectory | None = None
    preflight_cache: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest(
                "Set PAPER_FETCH_RUN_LIVE=1 to run live MCP smoke tests."
            )
        cls.env, cls.runtime_env_tempdir = build_isolated_live_env()
        cls.preflight_cache = {}

    @classmethod
    def tearDownClass(cls) -> None:
        runtime_env_tempdir = getattr(cls, "runtime_env_tempdir", None)
        if runtime_env_tempdir is not None:
            runtime_env_tempdir.cleanup()

    def _require_env(self, *keys: str) -> None:
        missing = [key for key in keys if not self.env.get(key, "").strip()]
        if missing:
            self.skipTest(
                f"Missing required environment variables for live test: {', '.join(missing)}"
            )

    async def _call_fetch(
        self,
        *,
        query: str,
        args: dict[str, object] | None = None,
        env_override: dict[str, str] | None = None,
    ) -> tuple[object, list[tuple[float, float | None, str | None]], list[object]]:
        progress_updates: list[tuple[float, float | None, str | None]] = []
        log_messages: list[object] = []

        async def progress_callback(progress, total, message) -> None:
            progress_updates.append((progress, total, message))

        async def logging_callback(params) -> None:
            log_messages.append(params.data)

        with tempfile.TemporaryDirectory() as tmpdir:
            server = StdioServerParameters(
                command=sys.executable,
                args=["-m", "paper_fetch.mcp.server"],
                cwd=str(REPO_ROOT),
                env={
                    **os.environ,
                    **self.env,
                    **(env_override or {}),
                    "PYTHONPATH": str(SRC_DIR),
                    "PAPER_FETCH_DOWNLOAD_DIR": str(Path(tmpdir) / "downloads"),
                },
            )

            with tempfile.TemporaryFile(mode="w+") as errlog:
                async with stdio_client(server, errlog=errlog) as (
                    read_stream,
                    write_stream,
                ):
                    async with ClientSession(
                        read_stream, write_stream, logging_callback=logging_callback
                    ) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "fetch_paper",
                            {"query": query, **(args or {})},
                            progress_callback=progress_callback,
                        )
        return result, progress_updates, log_messages

    async def _assert_live_fetch(
        self,
        *,
        sample,
        expected_log_prefix: str,
        args: dict[str, object] | None = None,
        needs_browser_runtime: bool = False,
        env_override: dict[str, str] | None = None,
    ) -> None:
        self._require_env(*sample.required_env)
        if needs_browser_runtime:
            await asyncio.to_thread(
                preflight_selected_browser_or_skip,
                self,
                provider=sample.provider,
                env=self.env,
                cache=self.preflight_cache,
            )

        result, progress_updates, log_messages = await self._call_fetch(
            query=sample.doi,
            args=args,
            env_override=env_override,
        )

        structured_content = getattr(result, "structured_content", None) or {}
        if is_machine_readable_no_access(structured_content):
            self.skipTest(
                f"{sample.provider} live MCP route reached a legal access boundary; "
                "configure entitlement/authentication before retrying."
            )

        self.assertFalse(
            result.is_error,
            {
                "content": getattr(result, "content", None),
                "structured_content": getattr(result, "structured_content", None),
            },
        )
        self.assertEqual(
            normalize_doi(result.structured_content["doi"]),
            normalize_doi(sample.doi),
        )
        self.assertTrue(result.structured_content["has_fulltext"])
        self.assertTrue(
            sample.accepts_live_result(
                source=result.structured_content["source"],
                source_trail=result.structured_content["source_trail"],
            ),
            result.structured_content["source_trail"],
        )
        acceptance = result.structured_content["acceptance"]
        self.assertEqual(acceptance["fetch"], "ok")
        self.assertEqual(acceptance["content"], "fulltext")
        self.assertEqual(acceptance["identity"], "resolved")
        self.assertEqual(acceptance["output"], "complete")
        self.assertEqual(progress_updates[-1], (4, 4, "fetch_paper complete"))
        self.assertTrue(
            any(
                isinstance(message, dict)
                and str(message.get("event", "")).startswith(expected_log_prefix)
                for message in log_messages
            )
        )

    async def test_elsevier_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=ELSEVIER_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
        )

    async def test_springer_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=SPRINGER_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
        )

    async def test_wiley_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=WILEY_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
            needs_browser_runtime=True,
        )

    async def test_science_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=SCIENCE_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
            needs_browser_runtime=True,
        )

    async def test_pnas_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        self._require_env(*PNAS_SAMPLE.required_env)
        require_selected_browser_or_skip(self, self.env)
        progress_updates: list[tuple[float, float | None, str | None]] = []
        log_messages: list[object] = []

        async def progress_callback(progress, total, message) -> None:
            progress_updates.append((progress, total, message))

        async def logging_callback(params) -> None:
            log_messages.append(params.data)

        started_at = time.monotonic()
        with tempfile.TemporaryDirectory() as tmpdir:
            server = StdioServerParameters(
                command=sys.executable,
                args=["-m", "paper_fetch.mcp.server"],
                cwd=str(REPO_ROOT),
                env={
                    **os.environ,
                    **self.env,
                    "PYTHONPATH": str(SRC_DIR),
                    "PAPER_FETCH_DOWNLOAD_DIR": str(Path(tmpdir) / "downloads"),
                },
            )
            with tempfile.TemporaryFile(mode="w+") as errlog:
                async with stdio_client(server, errlog=errlog) as (
                    read_stream,
                    write_stream,
                ):
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        logging_callback=logging_callback,
                    ) as session:
                        await session.initialize()
                        preflight = await session.call_tool(
                            "browser_preflight",
                            {"provider": "pnas", "detail": "full"},
                        )
                        self.assertFalse(preflight.is_error)
                        preflight_payload = preflight.structured_content or {}
                        result_payload = preflight_payload["results"][0]
                        if result_payload["status"] in {"challenge", "auth_required"}:
                            self.skipTest(
                                "PNAS live MCP preflight reached a legal access boundary."
                            )
                        self.assertEqual(result_payload["status"], "ready")

                        result = await session.call_tool(
                            "fetch_paper",
                            {
                                "query": PNAS_SAMPLE.doi,
                                "modes": ["article"],
                                "artifact_mode": "all",
                                "strategy": {
                                    "allow_metadata_only_fallback": False,
                                    "preferred_providers": ["pnas"],
                                    "asset_profile": "body",
                                },
                            },
                            progress_callback=progress_callback,
                        )

        total_seconds = round(time.monotonic() - started_at, 3)
        structured_content = result.structured_content or {}
        if is_machine_readable_no_access(structured_content):
            self.skipTest(
                "PNAS live MCP fetch reached a legal access boundary after preflight."
            )
        self.assertFalse(result.is_error)
        self.assertEqual(
            normalize_doi(structured_content["doi"]),
            normalize_doi(PNAS_SAMPLE.doi),
        )
        source_trail = list(structured_content["source_trail"])
        self.assertIn("browser:preflight_reuse_hit", source_trail)
        self.assertIn("fulltext:pnas_html_ok", source_trail)
        self.assertNotIn("fulltext:pnas_pdf_fallback_ok", source_trail)
        self.assertEqual(structured_content["acceptance"]["asset"], "complete")
        self.assertEqual(structured_content["acceptance"]["overall"], "complete")
        diagnostics = result_payload.get("diagnostics")
        trace = (
            diagnostics.get("browser_runtime_trace")
            if isinstance(diagnostics, Mapping)
            else None
        )
        trace_payload = dict(trace) if isinstance(trace, Mapping) else {}
        self.assertEqual(int(trace_payload.get("navigation_count") or 0), 1)
        self.assertEqual(progress_updates[-1], (4, 4, "fetch_paper complete"))
        self.assertTrue(
            any(
                isinstance(message, dict)
                and str(message.get("event", "")).startswith("official_provider_")
                for message in log_messages
            )
        )
        performance_warning = None
        if total_seconds > 45:
            performance_warning = (
                "PNAS MCP preflight+fetch exceeded the observational 45 second "
                f"target: {total_seconds:.3f}s"
            )
            warnings.warn(performance_warning, RuntimeWarning, stacklevel=1)
        artifact_root = Path(
            os.environ.get(
                "PAPER_FETCH_LIVE_ARTIFACT_DIR",
                ".paper-fetch-runs/live-publisher-acceptance",
            )
        )
        artifact_root.mkdir(parents=True, exist_ok=True)
        (artifact_root / "pnas-mcp-preflight-reuse.json").write_text(
            json.dumps(
                {
                    "provider": "pnas",
                    "doi": normalize_doi(PNAS_SAMPLE.doi),
                    "preflight_reuse_hit": True,
                    "preflight_navigation_count": 1,
                    "fetch_html_navigation_count": 0,
                    "total_seconds": total_seconds,
                    "performance_warning": performance_warning,
                    "browser_runtime_trace": trace_payload,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    async def test_ams_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=AMS_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
            needs_browser_runtime=True,
        )

    async def test_ieee_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=IEEE_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
            needs_browser_runtime=True,
        )

    async def test_arxiv_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=ARXIV_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
        )

    async def test_copernicus_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=COPERNICUS_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {}},
        )


if __name__ == "__main__":
    unittest.main()
