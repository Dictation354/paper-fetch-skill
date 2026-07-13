from __future__ import annotations

import asyncio
import copy
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from paper_fetch import cli as paper_fetch_cli
from paper_fetch import service as paper_fetch_service
from paper_fetch.mcp.fetch_cache import (
    cached_request_matches,
    request_cache_payload,
)
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.mcp.server import build_server
from paper_fetch.providers import _ams_html
from paper_fetch.providers.base import ProviderFailure
from tests.skill_bundle_links import skill_bundle_link_issues

from ._paper_fetch_support import StubProvider, build_envelope, sample_article
from ._service_support import _fetch_paper, _typed_payload


REPO_ROOT = Path(__file__).resolve().parents[2]


class Pf001CompatibilityContractTests(unittest.TestCase):
    def test_wiley_preview_is_asset_diagnostic_not_fulltext_fetch_failure(self) -> None:
        resolved = paper_fetch_service.ResolvedQuery(
            query="10.1111/preview-contract",
            query_kind="doi",
            doi="10.1111/preview-contract",
            landing_url=(
                "https://onlinelibrary.wiley.com/doi/full/10.1111/preview-contract"
            ),
            provider_hint="wiley",
            confidence=1.0,
        )

        for preview_accepted in (False, True):
            with self.subTest(preview_accepted=preview_accepted):
                with tempfile.TemporaryDirectory() as tmpdir:
                    output_dir = Path(tmpdir)
                    preview_path = output_dir / "figure-preview.png"
                    preview_path.write_bytes(b"preview")
                    article = sample_article()
                    article.doi = resolved.doi
                    article.source = "wiley_browser"
                    asset: dict[str, object] = {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Wiley preview figure",
                        "path": str(preview_path),
                        "section": "body",
                        "download_tier": "preview",
                    }
                    if preview_accepted:
                        asset.update(width=640, height=480)

                    clients = {
                        "wiley": StubProvider(
                            raw_payload=_typed_payload(
                                provider="wiley",
                                source_url=resolved.landing_url or "",
                                content_type="text/html",
                                body=b"<html></html>",
                                route_kind="html",
                                markdown_text=(
                                    "# Wiley Article\n\n## Results\n\n"
                                    + ("Body text " * 80)
                                ),
                                source_trail=["fulltext:wiley_html_ok"],
                            ),
                            article=article,
                            related_assets={
                                "assets": [asset],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": resolved.doi,
                                "title": "Wiley Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    }

                    with mock.patch.object(
                        paper_fetch_service, "resolve_paper", return_value=resolved
                    ):
                        envelope = _fetch_paper(
                            resolved.query,
                            modes={"article", "markdown"},
                            strategy=paper_fetch_service.FetchStrategy(),
                            download_dir=output_dir,
                            clients=clients,
                        )

                self.assertTrue(
                    envelope.has_fulltext,
                    "Wiley preview assets must not downgrade successful body fetches",
                )
                self.assertEqual(envelope.content_kind, "fulltext")
                self.assertIsNotNone(envelope.article)
                self.assertIsNotNone(envelope.markdown)
                self.assertIn("fulltext:wiley_article_ok", envelope.source_trail)
                fallback_warning = any(
                    "fell back to preview images" in warning
                    for warning in envelope.warnings
                )
                if preview_accepted:
                    self.assertIn(
                        "download:wiley_assets_preview_accepted",
                        envelope.source_trail,
                    )
                    self.assertFalse(fallback_warning)
                else:
                    self.assertIn(
                        "download:wiley_assets_preview_fallback",
                        envelope.source_trail,
                    )
                    self.assertTrue(fallback_warning)

    def test_ams_blank_placeholders_are_rejected_while_lazy_asset_kinds_survive(
        self,
    ) -> None:
        source_url = "https://journals.ametsoc.org/view/journals/clim/37/24/article.xml"
        html = """
        <article><section>
          <figure id="fig1">
            <img data-image-src="/images/figure-1.jpg"
                 src="/skin/site/img/Blank.svg" alt="Fig. 1." />
            <figcaption>Fig. 1. Circulation response.</figcaption>
          </figure>
          <div class="formula" id="e1">
            <img data-image-src="/images/formula-1.gif"
                 src="/skin/site/img/Blank.png" alt="e1" />
          </div>
          <figure class="tableWrap" id="tbl1">
            <span class="tableWrapLabel">Table 1.</span>
            <span class="tableWrapCaption">Observed values.</span>
            <img data-image-src="/images/table-1.jpg"
                 src="/skin/site/img/Blank.svg" alt="Table 1." />
          </figure>
        </section></article>
        """

        assets = _ams_html.scoped_asset_extractor(
            html,
            source_url,
            asset_profile="body",
        )

        self.assertEqual(
            {asset["kind"] for asset in assets},
            {"figure", "formula", "table"},
            "AMS lazy URL normalization must preserve figure/formula/table kinds",
        )
        self.assertEqual(len(assets), 3)
        for asset in assets:
            self.assertNotIn(
                "Blank.",
                str(asset.get("url") or ""),
                "AMS Blank.svg/png placeholders must never become asset URLs",
            )
            self.assertIn("/images/", str(asset.get("url") or ""))

    def test_batch_check_metadata_remains_likely_probe_not_fulltext_claim(self) -> None:
        from dataclasses import replace

        from paper_fetch.mcp import batch as mcp_batch
        from paper_fetch.mcp._deps import default_mcp_deps
        from paper_fetch.workflow.types import HasFulltextProbeResult

        probes = {
            "10.1000/likely": HasFulltextProbeResult(
                query="10.1000/likely",
                doi="10.1000/likely",
                title="Likely paper",
                state="likely_yes",
                evidence=["crossref_fulltext_link"],
                warnings=[],
            ),
            "10.1000/unknown": HasFulltextProbeResult(
                query="10.1000/unknown",
                doi="10.1000/unknown",
                title="Unknown paper",
                state="unknown",
                evidence=[],
                warnings=[],
            ),
        }
        deps = replace(
            default_mcp_deps(),
            build_runtime_env=lambda _env=None: {},
            service_probe_has_fulltext=lambda query, **_kwargs: probes[query],
        )

        payload = mcp_batch.batch_check_payload(
            queries=list(probes),
            mode="metadata",
            deps=deps,
        )

        self.assertFalse(payload["aborted"])
        self.assertEqual(
            {item["probe_state"] for item in payload["results"]},
            {"likely_yes", "unknown"},
            "metadata batch_check must expose only readability probe states",
        )
        for item in payload["results"]:
            self.assertIsNone(
                item["content_kind"],
                "metadata probes must not claim metadata-only or verified full text",
            )
            self.assertIsNone(item["source"])
            self.assertNotIn("article", item)
            self.assertNotIn("markdown", item)

    def test_cli_batch_jsonl_uses_one_based_indices_in_completion_order(self) -> None:
        submitted: list[tuple[int, str]] = []
        release_first = threading.Event()

        def run_item(item, *, deps, **_kwargs):
            submitted.append((item.index, item.query))
            started_at = deps.clock()
            if item.index == 1:
                self.assertTrue(release_first.wait(timeout=1))
                time.sleep(0.03)
            else:
                release_first.set()
            article = sample_article()
            article.doi = item.query
            return paper_fetch_cli.CliFetchOutcome(
                started_at=started_at,
                completed_at=deps.clock(),
                result=paper_fetch_cli.SingleFetchResult(build_envelope(article)),
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            results_path = output_dir / "batch-results.jsonl"
            args = SimpleNamespace(
                batch_results=str(results_path),
                batch_concurrency=2,
                format="markdown",
                asset_profile="none",
                include_refs="all",
                max_tokens="full_text",
                no_download=True,
                save_markdown_to_disk=False,
                output="-",
            )
            with (
                mock.patch.object(
                    paper_fetch_cli, "_run_batch_item", side_effect=run_item
                ),
                mock.patch.object(
                    paper_fetch_cli,
                    "build_http_transport_for_context",
                    return_value=object(),
                ),
            ):
                exit_code = paper_fetch_cli.run_batch_fetch(
                    args,
                    queries=["10.1000/first", "10.1000/second"],
                    output_dir=output_dir,
                    runtime_env={},
                    artifact_mode="markdown-assets",
                )

            result_lines = [
                json.loads(line)
                for line in results_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            sorted(submitted),
            [(1, "10.1000/first"), (2, "10.1000/second")],
        )
        self.assertEqual(
            [item["index"] for item in result_lines],
            [2, 1],
            "CLI JSONL must be written in completion order without renumbering inputs",
        )

    def test_cache_request_matcher_checks_all_request_semantics(self) -> None:
        request = FetchPaperRequest(
            query="10.1000/cache-contract",
            modes=["article", "markdown"],
            strategy={
                "allow_metadata_only_fallback": False,
                "preferred_providers": ["wiley"],
                "asset_profile": "body",
            },
            include_refs="all",
            max_tokens=4096,
        )
        cached_request = request_cache_payload(request)
        self.assertTrue(cached_request_matches(cached_request, request))

        mismatches = {
            "modes": lambda value: value.update(modes=["article"]),
            "strategy": lambda value: value["strategy"].update(asset_profile="none"),
            "include_refs": lambda value: value.update(include_refs="top10"),
            "max_tokens": lambda value: value.update(max_tokens=2048),
        }
        for field, mutate in mismatches.items():
            with self.subTest(field=field):
                candidate = copy.deepcopy(cached_request)
                mutate(candidate)
                self.assertFalse(
                    cached_request_matches(candidate, request),
                    f"cache request matching must reject a mismatched {field}",
                )

    def test_mcp_batch_stops_incremental_submission_after_rate_limit(self) -> None:
        from paper_fetch.mcp import batch as mcp_batch

        release_inflight = threading.Event()
        timer_holder: list[threading.Timer] = []
        seen_queries: list[str] = []

        def process_item(query: str) -> dict[str, object]:
            seen_queries.append(query)
            if query == "inflight":
                if not release_inflight.wait(timeout=2):
                    raise AssertionError("timed out waiting for rate-limit observation")
                return {"query": query, "status": "ok"}
            if query == "rate-limited":
                timer = threading.Timer(0.1, release_inflight.set)
                timer.daemon = True
                timer_holder.append(timer)
                timer.start()
                raise ProviderFailure("rate_limited", "Slow down.")
            raise AssertionError(
                f"MCP submitted {query!r} after observing a rate limit"
            )

        async def run_batch():
            return await mcp_batch._run_batch_async(
                queries=["inflight", "rate-limited", "must-not-start"],
                concurrency=2,
                process_item=process_item,
                ctx=None,
                progress_prefix="Checked",
            )

        results, abort_reason = asyncio.run(run_batch())
        for timer in timer_holder:
            timer.join(timeout=1)

        self.assertIsNotNone(abort_reason)
        assert abort_reason is not None
        self.assertEqual(abort_reason["status"], "rate_limited")
        self.assertCountEqual(seen_queries, ["inflight", "rate-limited"])
        self.assertEqual(len(results), 2)
        self.assertNotIn(
            "must-not-start",
            seen_queries,
            "MCP must stop incremental task submission after rate limiting",
        )

    def test_native_fastmcp_tools_list_strategy_is_object_not_host_unknown(
        self,
    ) -> None:
        tools = asyncio.run(build_server().list_native_tools())
        fetch_tool = next(tool for tool in tools if tool.name == "fetch_paper")
        native_schema = fetch_tool.inputSchema
        strategy_schema = native_schema["properties"]["strategy"]
        object_schema = None
        for branch in strategy_schema.get("anyOf", [strategy_schema]):
            candidate = branch
            reference = candidate.get("$ref")
            if reference:
                prefix = "#/$defs/"
                self.assertTrue(
                    reference.startswith(prefix),
                    f"unexpected native schema reference: {reference}",
                )
                candidate = native_schema["$defs"][reference.removeprefix(prefix)]
            if candidate.get("type") == "object":
                object_schema = candidate
                break

        self.assertIsNotNone(
            object_schema,
            (
                "Native FastMCP tools/list must expose strategy as an object; "
                "a Codex host 'unknown' label is only a host display concern"
            ),
        )
        assert object_schema is not None
        self.assertEqual(object_schema["type"], "object")
        self.assertIn("properties", object_schema)
        self.assertIn("asset_profile", object_schema["properties"])

    def test_source_skill_all_references_enter_offline_staging(self) -> None:
        build_script_path = REPO_ROOT / "scripts" / "build-offline-package.sh"
        build_script = build_script_path.read_text(encoding="utf-8").rstrip()
        entrypoint = 'main "$@"'
        self.assertTrue(
            build_script.endswith(entrypoint),
            "offline build entrypoint changed; update the staging characterization",
        )
        function_definitions = build_script.removesuffix(entrypoint)

        with tempfile.TemporaryDirectory() as tmpdir:
            staging = Path(tmpdir) / "staging"
            env = {
                **os.environ,
                "PF001_REPO_ROOT": str(REPO_ROOT),
                "PF001_STAGING": str(staging),
            }
            completed = subprocess.run(
                ["bash"],
                input=(
                    function_definitions
                    + "\n"
                    + 'REPO_DIR="$PF001_REPO_ROOT"\n'
                    + 'INSTALLER_MANIFEST_FILE="$REPO_DIR/installer/manifest.json"\n'
                    + 'copy_runtime_assets "$PF001_STAGING"\n'
                ),
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"copy_runtime_assets failed: {completed.stderr}",
            )

            source_references = (
                REPO_ROOT / "skills" / "paper-fetch-skill" / "references"
            )
            staged_references = staging / "skills" / "paper-fetch-skill" / "references"
            source_files = {
                path.relative_to(source_references): path.read_bytes()
                for path in source_references.rglob("*")
                if path.is_file()
            }
            staged_files = {
                path.relative_to(staged_references): path.read_bytes()
                for path in staged_references.rglob("*")
                if path.is_file()
            }
            staging_link_issues = skill_bundle_link_issues(
                staging / "skills" / "paper-fetch-skill"
            )

        self.assertTrue(source_files, "source skill references must not be empty")
        self.assertEqual(
            staged_files,
            source_files,
            "offline staging must recursively copy every source skill reference",
        )
        self.assertEqual(
            staging_link_issues,
            [],
            "offline staging must keep every skill-relative Markdown link valid",
        )

        windows_script = (
            REPO_ROOT / "scripts" / "build-offline-package-windows.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "Copy-Item -LiteralPath $sourceSkill -Destination $skillsDir -Recurse",
            windows_script,
            "Windows offline staging must also recursively copy the complete skill",
        )


if __name__ == "__main__":
    unittest.main()
