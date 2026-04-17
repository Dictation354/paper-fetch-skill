from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from paper_fetch.config import build_runtime_env, resolve_flaresolverr_source_dir, resolve_flaresolverr_url
from paper_fetch.providers._flaresolverr import health_check
from paper_fetch.providers.base import ProviderFailure
from tests.provider_benchmark_samples import provider_benchmark_sample, source_trail_matches
from tests.paths import REPO_ROOT, SRC_DIR


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"
ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
SPRINGER_SAMPLE = provider_benchmark_sample("springer")
SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


class LiveMcpServerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest("Set PAPER_FETCH_RUN_LIVE=1 to run live MCP smoke tests.")
        cls.env = build_runtime_env()

    def _require_env(self, *keys: str) -> None:
        missing = [key for key in keys if not self.env.get(key, "").strip()]
        if missing:
            self.skipTest(f"Missing required environment variables for live test: {', '.join(missing)}")

    def _require_flaresolverr(self) -> None:
        env_file = Path(self.env["FLARESOLVERR_ENV_FILE"]).expanduser()
        if not env_file.exists():
            self.skipTest(f"Configured FLARESOLVERR_ENV_FILE does not exist: {env_file}")
        source_dir = resolve_flaresolverr_source_dir(self.env)
        if not source_dir.exists():
            self.skipTest(f"Repo-local vendor/flaresolverr was not found: {source_dir}")
        try:
            health_check(resolve_flaresolverr_url(self.env))
        except ProviderFailure as exc:
            self.skipTest(f"Local FlareSolverr health check failed: {exc.message}")

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
                async with stdio_client(server, errlog=errlog) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream, logging_callback=logging_callback) as session:
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
        needs_flaresolverr: bool = False,
        env_override: dict[str, str] | None = None,
    ) -> None:
        self._require_env(*sample.required_env)
        if needs_flaresolverr:
            self._require_flaresolverr()

        result, progress_updates, log_messages = await self._call_fetch(
            query=sample.doi,
            args=args,
            env_override=env_override,
        )

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["source"], sample.expected_source)
        self.assertTrue(result.structuredContent["has_fulltext"])
        self.assertTrue(
            source_trail_matches(
                result.structuredContent["source_trail"],
                sample.accepted_live_source_trail_groups,
            ),
            result.structuredContent["source_trail"],
        )
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
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
        )

    async def test_springer_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=SPRINGER_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
        )

    async def test_wiley_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=WILEY_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
            env_override={
                "FLARESOLVERR_URL": "",
                "FLARESOLVERR_ENV_FILE": "",
                "FLARESOLVERR_SOURCE_DIR": "",
                "FLARESOLVERR_MIN_INTERVAL_SECONDS": "",
                "FLARESOLVERR_MAX_REQUESTS_PER_HOUR": "",
                "FLARESOLVERR_MAX_REQUESTS_PER_DAY": "",
            },
        )

    async def test_science_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=SCIENCE_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
            needs_flaresolverr=True,
        )

    async def test_pnas_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            sample=PNAS_SAMPLE,
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
            needs_flaresolverr=True,
        )


if __name__ == "__main__":
    unittest.main()
