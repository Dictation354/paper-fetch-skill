from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from paper_fetch.publisher_identity import normalize_doi
from paper_fetch.logging_utils import redact_log_value
from tests.support.live_acceptance import (
    fetch_browser_diagnostics,
    _asset_performance_summary,
)
from paper_fetch.models.codec import article_from_payload
from tests.live._runtime_env import (
    build_isolated_live_env,
    is_machine_readable_no_access,
    require_local_browser_or_skip,
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

    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest(
                "Set PAPER_FETCH_RUN_LIVE=1 to run live MCP smoke tests."
            )
        cls.env, cls.runtime_env_tempdir = build_isolated_live_env()

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
        provider: str,
        args: dict[str, object] | None = None,
        env_override: dict[str, str] | None = None,
    ) -> tuple[object, list[tuple[float, float | None, str | None]], list[object]]:
        progress_updates: list[tuple[float, float | None, str | None]] = []
        log_messages: list[object] = []

        async def progress_callback(progress, total, message) -> None:
            progress_updates.append((progress, total, message))

        async def logging_callback(params) -> None:
            log_messages.append(params.data)

        artifact_root = (
            Path(
                os.environ.get(
                    "PAPER_FETCH_LIVE_ARTIFACT_DIR",
                    ".paper-fetch-runs/live-publisher-acceptance",
                )
            )
            / "mcp"
            / self._testMethodName
        )
        # A fresh directory per invocation also keeps compatibility aliases and
        # repeated runs from overwriting subprocess evidence.
        artifact_root.mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="fetch-", dir=artifact_root)).resolve()
        self.fetch_output_dir = output
        started_at = time.monotonic()
        fetch_started_at = None
        result = None
        fetch_exception = None
        try:
            server = StdioServerParameters(
                command=sys.executable,
                args=["-m", "paper_fetch.mcp.server"],
                cwd=str(REPO_ROOT),
                env={
                    **self.env,
                    **(env_override or {}),
                    "PYTHONPATH": str(SRC_DIR),
                    "PAPER_FETCH_DOWNLOAD_DIR": str(output / "downloads"),
                },
            )
            with (output / "stderr.log").open("w", encoding="utf-8") as errlog:
                async with stdio_client(server, errlog=errlog) as (
                    read_stream,
                    write_stream,
                ):
                    async with ClientSession(
                        read_stream, write_stream, logging_callback=logging_callback
                    ) as session:
                        await session.initialize()
                        fetch_started_at = time.monotonic()
                        result = await session.call_tool(
                            "fetch_paper",
                            {"query": query, "artifact_mode": "all", **(args or {})},
                            progress_callback=progress_callback,
                        )
                        fetch_seconds = round(time.monotonic() - fetch_started_at, 3)
        except Exception as exc:
            fetch_exception = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            payload = getattr(result, "structured_content", None) or {}
            article = article_from_payload(payload.get("article"))
            (output / "fetch-result.json").write_text(
                json.dumps(
                    redact_log_value(
                        {
                            **fetch_browser_diagnostics(
                                output / "downloads", provider=provider, doi=query
                            ),
                            "preflight": None,
                            "preflight_seconds": 0,
                            "preflight_navigation_count": 0,
                            "total_seconds": round(time.monotonic() - started_at, 3),
                            "fetch_wall_seconds": fetch_seconds
                            if result is not None
                            else (
                                round(time.monotonic() - fetch_started_at, 3)
                                if fetch_started_at
                                else 0
                            ),
                            "is_error": getattr(result, "is_error", True),
                            "exception": fetch_exception,
                            "result": payload,
                            "assets": _asset_performance_summary(article)
                            if article
                            else None,
                            "progress": progress_updates,
                            "logs": log_messages,
                        }
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
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
            require_local_browser_or_skip(self, self.env, provider=sample.provider)

        result, progress_updates, log_messages = await self._call_fetch(
            query=sample.doi,
            provider=sample.provider,
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

    async def test_pnas_camoufox_live_via_mcp_reports_progress_and_logs(self) -> None:
        self.env["PAPER_FETCH_PNAS_BROWSER_BACKEND"] = "camoufox"
        await self._pnas_doi_live_via_mcp_reports_progress_and_logs()

    async def test_pnas_byparr_live_via_mcp_reports_progress_and_logs(
        self,
    ) -> None:
        self.env["PAPER_FETCH_PNAS_BROWSER_BACKEND"] = "byparr"
        await self._pnas_doi_live_via_mcp_reports_progress_and_logs()

    async def _pnas_doi_live_via_mcp_reports_progress_and_logs(self) -> None:
        self._require_env(*PNAS_SAMPLE.required_env)
        require_local_browser_or_skip(self, self.env, provider="pnas")
        result, progress_updates, log_messages = await self._call_fetch(
            query=PNAS_SAMPLE.doi,
            provider="pnas",
            args={
                "modes": ["article"],
                "strategy": {
                    "allow_metadata_only_fallback": False,
                    "preferred_providers": ["pnas"],
                    "asset_profile": "body",
                    "require_local_body_assets": True,
                    "require_full_size_body_assets": True,
                },
            },
        )
        report_path = self.fetch_output_dir / "fetch-result.json"
        report = json.loads(report_path.read_text())
        report.update(
            fetch_browser_diagnostics(
                self.fetch_output_dir / "downloads",
                provider="pnas",
                doi=PNAS_SAMPLE.doi,
            )
        )
        report.update({"provider": "pnas", "doi": normalize_doi(PNAS_SAMPLE.doi)})
        report_path.write_text(
            json.dumps(redact_log_value(report), ensure_ascii=False, indent=2) + "\n"
        )
        structured_content = result.structured_content or {}
        if is_machine_readable_no_access(structured_content):
            self.skipTest("PNAS live MCP fetch reached a legal access boundary.")
        self.assertFalse(result.is_error, structured_content)
        self.assertEqual(
            normalize_doi(structured_content["doi"]), normalize_doi(PNAS_SAMPLE.doi)
        )
        self.assertTrue(structured_content["has_fulltext"])
        assets = (structured_content.get("article") or {}).get("assets") or []
        self.assertEqual(len(assets), 4)
        self.assertTrue(
            all(
                asset.get("path") and asset.get("download_tier") == "full_size"
                for asset in assets
            )
        )
        self.assertEqual(structured_content["acceptance"]["asset"], "complete")
        self.assertEqual(structured_content["acceptance"]["overall"], "complete")
        self.assertEqual(progress_updates[-1], (4, 4, "fetch_paper complete"))
        self.assertTrue(
            any(
                isinstance(message, dict)
                and str(message.get("event", "")).startswith("official_provider_")
                for message in log_messages
            )
        )
        if report["fetch_wall_seconds"] > 45:
            warnings.warn(
                f"PNAS MCP fetch exceeded the observational 45 second target: {report['fetch_wall_seconds']:.3f}s",
                RuntimeWarning,
                stacklevel=1,
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
