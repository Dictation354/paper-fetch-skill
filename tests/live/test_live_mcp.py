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
from tests.paths import REPO_ROOT, SRC_DIR


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"


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
        query: str,
        required_env: tuple[str, ...],
        expected_source: str,
        expected_source_trail: str,
        expected_log_prefix: str,
        args: dict[str, object] | None = None,
        needs_flaresolverr: bool = False,
    ) -> None:
        self._require_env(*required_env)
        if needs_flaresolverr:
            self._require_flaresolverr()

        result, progress_updates, log_messages = await self._call_fetch(query=query, args=args)

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["source"], expected_source)
        self.assertTrue(result.structuredContent["has_fulltext"])
        self.assertIn(expected_source_trail, result.structuredContent["source_trail"])
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
            query="10.1016/j.rse.2025.114648",
            required_env=("ELSEVIER_API_KEY", "CROSSREF_MAILTO"),
            expected_source="elsevier_xml",
            expected_source_trail="fulltext:elsevier_article_ok",
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
        )

    async def test_springer_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            query="10.1186/1471-2105-11-421",
            required_env=("CROSSREF_MAILTO",),
            expected_source="springer_html",
            expected_source_trail="fulltext:springer_html_ok",
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
        )

    async def test_wiley_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        self._require_env(
            "CROSSREF_MAILTO",
            "FLARESOLVERR_ENV_FILE",
            "FLARESOLVERR_MIN_INTERVAL_SECONDS",
            "FLARESOLVERR_MAX_REQUESTS_PER_HOUR",
            "FLARESOLVERR_MAX_REQUESTS_PER_DAY",
        )
        self._require_flaresolverr()

        result, progress_updates, log_messages = await self._call_fetch(
            query="10.1002/ece3.9361",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
        )

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["source"], "wiley_browser")
        self.assertTrue(result.structuredContent["has_fulltext"])
        self.assertTrue(
            any(
                marker in result.structuredContent["source_trail"]
                for marker in ("fulltext:wiley_html_ok", "fulltext:wiley_pdf_fallback_ok")
            )
        )
        self.assertEqual(progress_updates[-1], (4, 4, "fetch_paper complete"))
        self.assertTrue(
            any(
                isinstance(message, dict)
                and str(message.get("event", "")).startswith("official_provider_")
                for message in log_messages
            )
        )

    async def test_nature_html_direct_live_via_mcp_reports_progress_and_logs(self) -> None:
        self._require_env("CROSSREF_MAILTO")

        result, progress_updates, log_messages = await self._call_fetch(
            query="https://www.nature.com/articles/sj.bdj.2017.900",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": True}},
        )

        self.assertFalse(result.isError)
        self.assertIn(result.structuredContent["source"], {"springer_html", "metadata_only"})
        if result.structuredContent["source"] == "springer_html":
            self.assertTrue(result.structuredContent["has_fulltext"])
            self.assertIn("fulltext:springer_html_ok", result.structuredContent["source_trail"])
        else:
            self.assertFalse(result.structuredContent["has_fulltext"])
            self.assertIn("fallback:springer_html_managed_by_provider", result.structuredContent["source_trail"])
        self.assertEqual(progress_updates[-1], (4, 4, "fetch_paper complete"))
        self.assertTrue(
            any(
                isinstance(message, dict)
                and str(message.get("event", "")).startswith("official_provider_")
                for message in log_messages
            )
        )

    async def test_science_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            query="10.1126/science.ady3136",
            required_env=(
                "CROSSREF_MAILTO",
                "FLARESOLVERR_ENV_FILE",
                "FLARESOLVERR_MIN_INTERVAL_SECONDS",
                "FLARESOLVERR_MAX_REQUESTS_PER_HOUR",
                "FLARESOLVERR_MAX_REQUESTS_PER_DAY",
            ),
            expected_source="science",
            expected_source_trail="fulltext:science_html_ok",
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
            needs_flaresolverr=True,
        )

    async def test_pnas_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        await self._assert_live_fetch(
            query="10.1073/pnas.81.23.7500",
            required_env=(
                "CROSSREF_MAILTO",
                "FLARESOLVERR_ENV_FILE",
                "FLARESOLVERR_MIN_INTERVAL_SECONDS",
                "FLARESOLVERR_MAX_REQUESTS_PER_HOUR",
                "FLARESOLVERR_MAX_REQUESTS_PER_DAY",
            ),
            expected_source="pnas",
            expected_source_trail="fulltext:pnas_pdf_fallback_ok",
            expected_log_prefix="official_provider_",
            args={"modes": ["metadata"], "strategy": {"allow_html_fallback": False}},
            needs_flaresolverr=True,
        )


if __name__ == "__main__":
    unittest.main()
