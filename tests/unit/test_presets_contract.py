from __future__ import annotations

import contextlib
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch import cli as paper_fetch_cli
from paper_fetch import service as paper_fetch_service
from paper_fetch.artifacts import ArtifactStore
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.fulltext import _provider_fetch_result
from tests.paths import REPO_ROOT, SKILL_DIR
from tests.unit._mcp_support import (
    create_cached_fetch_envelope,
    mcp_tools,
    sample_article as mcp_sample_article,
    sample_envelope,
    sample_probe_result,
    sample_resolved_query,
)
from tests.unit._paper_fetch_support import sample_article as cli_sample_article


PRESETS_PATH = SKILL_DIR / "references" / "presets.md"
CLI_REFERENCE_PATH = SKILL_DIR / "references" / "cli-workflow.md"
CLI_DOC_PATH = REPO_ROOT / "docs" / "cli.md"


def _fenced_blocks(path: Path, language: str) -> list[str]:
    blocks: list[str] = []
    active: list[str] | None = None
    opening = f"```{language}"
    for line in path.read_text(encoding="utf-8").splitlines():
        if active is None:
            if line.strip() == opening:
                active = []
            continue
        if line.strip() == "```":
            blocks.append("\n".join(active))
            active = None
            continue
        active.append(line)
    return blocks


def _cli_fetch(*_args, **kwargs):
    article = cli_sample_article()
    return paper_fetch_service.build_fetch_envelope(
        article, modes=kwargs["modes"], render=kwargs["render"]
    )


class _LocalAssetProvider:
    def fetch_raw_fulltext(self, doi, metadata, *, context=None):
        del doi, metadata, context
        return RawFulltextPayload(
            provider="example",
            source_url="https://example.test/article.xml",
            content_type="text/xml",
            body=b"<article />",
            content=ProviderContent(
                route_kind="official",
                source_url="https://example.test/article.xml",
                content_type="text/xml",
                body=b"<article />",
            ),
        )

    def to_article_model(
        self,
        metadata,
        raw_payload,
        *,
        downloaded_assets=None,
        asset_failures=None,
        context=None,
    ):
        del metadata, raw_payload, downloaded_assets, asset_failures, context
        return mcp_sample_article()

    def download_related_assets(
        self,
        doi,
        metadata,
        raw_payload,
        output_dir,
        *,
        asset_profile="all",
        context=None,
    ):
        del doi, metadata, raw_payload, context
        assert output_dir is not None
        body_path = output_dir / "assets" / "body.png"
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(b"body")
        assets = [{"kind": "figure", "path": str(body_path), "section": "body"}]
        if asset_profile == "all":
            supplementary_path = output_dir / "assets" / "supplementary.zip"
            supplementary_path.write_bytes(b"supplementary")
            assets.append(
                {
                    "kind": "supplementary",
                    "path": str(supplementary_path),
                    "section": "supplementary",
                }
            )
        return {"assets": assets, "asset_failures": []}

    def asset_download_failure_warning(self, exc):
        return str(exc)


class PresetStaticContractTests(unittest.TestCase):
    def test_reference_defines_exactly_five_presets_and_two_matrices(self) -> None:
        text = PRESETS_PATH.read_text(encoding="utf-8")
        preset_headings = (
            "### 1. 临时阅读",
            "### 2. 可缓存阅读",
            "### 3. 单篇本地归档",
            "### 4. 批量可读性分诊",
            "### 5. 批量本地归档",
        )

        self.assertEqual(
            [line for line in text.splitlines() if line.startswith("### ")],
            list(preset_headings),
        )
        self.assertEqual(text.count("## CLI 输出/落盘矩阵"), 1)
        self.assertEqual(text.count("## MCP 输出/落盘矩阵"), 1)
        self.assertIn("完全不落盘", text)
        self.assertIn("只写可复用 cache", text)
        self.assertIn("文本归档", text)
        self.assertIn("正文图归档", text)
        self.assertIn("补充材料归档", text)

    def test_mcp_fetch_examples_set_the_complete_saving_contract(self) -> None:
        payloads = [json.loads(block) for block in _fenced_blocks(PRESETS_PATH, "json")]
        fetch_payloads = [payload for payload in payloads if "query" in payload]
        required_fields = {
            "modes",
            "strategy",
            "include_refs",
            "max_tokens",
            "prefer_cache",
            "no_download",
            "artifact_mode",
            "save_markdown",
            "markdown_output_dir",
            "markdown_filename",
            "download_dir",
        }

        self.assertEqual(len(fetch_payloads), 3)
        for payload in fetch_payloads:
            with self.subTest(payload=payload):
                self.assertTrue(required_fields.issubset(payload))
                self.assertEqual(
                    set(payload["strategy"]),
                    {
                        "allow_metadata_only_fallback",
                        "preferred_providers",
                        "asset_profile",
                        "inline_image_budget",
                    },
                )
                self.assertIn(
                    payload["strategy"]["asset_profile"], {"none", "body", "all"}
                )
                self.assertIn(payload["include_refs"], {"none", "top10", "all"})
        temporary, cacheable, archive = fetch_payloads
        self.assertEqual(
            (
                temporary["save_markdown"],
                temporary["no_download"],
                temporary["artifact_mode"],
                temporary["strategy"]["asset_profile"],
                temporary["prefer_cache"],
            ),
            (False, True, "none", "none", False),
        )
        self.assertEqual(
            (
                cacheable["save_markdown"],
                cacheable["no_download"],
                cacheable["artifact_mode"],
                cacheable["strategy"]["asset_profile"],
                cacheable["prefer_cache"],
            ),
            (False, False, "none", "none", True),
        )
        self.assertEqual(
            (
                archive["save_markdown"],
                archive["no_download"],
                archive["artifact_mode"],
                archive["strategy"]["asset_profile"],
                archive["prefer_cache"],
            ),
            (True, True, "none", "none", True),
        )
        self.assertEqual(archive["markdown_output_dir"], archive["download_dir"])

    def test_all_cli_fetch_examples_select_artifact_and_asset_profiles(self) -> None:
        for path in (PRESETS_PATH, CLI_REFERENCE_PATH, CLI_DOC_PATH):
            for block in _fenced_blocks(path, "bash"):
                if not any(
                    invocation in block
                    for invocation in (
                        "paper-fetch --query",
                        "paper-fetch fetch --query",
                    )
                ):
                    continue
                with self.subTest(path=path, block=block):
                    self.assertIn("--artifact-mode", block)
                    self.assertIn("--asset-profile", block)

        docs_text = CLI_DOC_PATH.read_text(encoding="utf-8")
        command_rows = [
            line
            for line in docs_text.splitlines()
            if line.startswith(
                ("| `paper-fetch --query", "| `paper-fetch fetch --query")
            )
        ]
        self.assertTrue(command_rows)
        self.assertTrue(all("--artifact-mode" in row for row in command_rows))
        self.assertTrue(all("--asset-profile" in row for row in command_rows))

    def test_local_first_order_scope_and_batch_probe_are_explicit(self) -> None:
        text = PRESETS_PATH.read_text(encoding="utf-8")
        decision_tree = (
            "已核验本地 fulltext → 同 scope 精确 DOI cache → "
            "严格请求匹配的 prefer-cache → 正常 fetch"
        )

        self.assertIn(decision_tree, text)
        self.assertLess(
            text.index("1. **已核验本地 fulltext**"),
            text.index("2. **同 scope 精确 DOI cache**"),
        )
        self.assertLess(
            text.index("2. **同 scope 精确 DOI cache**"),
            text.index("3. **严格请求匹配的 prefer-cache**"),
        )
        self.assertLess(
            text.index("3. **严格请求匹配的 prefer-cache**"),
            text.index("4. **正常 fetch**"),
        )
        self.assertIn("get_cached(doi=<normalized-doi>, download_dir=<scope>)", text)
        self.assertIn("始终传相同的 `download_dir`", text)
        self.assertIn("[1..50]", text)
        self.assertIn("[51..100]", text)
        self.assertIn("[101..113]", text)
        self.assertIn("原始输入固定 1-based `index`", text)
        self.assertIn('`batch_check(mode="metadata")` 是 likely probe', text)
        for path in (PRESETS_PATH, CLI_REFERENCE_PATH, CLI_DOC_PATH):
            for block in _fenced_blocks(path, "bash"):
                commands = [line.strip() for line in block.splitlines()]
                with self.subTest(path=path, block=block):
                    self.assertFalse(any(line.startswith("jq ") for line in commands))
                    self.assertFalse(
                        any(line.startswith("python ") for line in commands)
                    )


class PresetRuntimeContractTests(unittest.TestCase):
    def test_public_cli_and_mcp_defaults_remain_unchanged(self) -> None:
        cli_args = paper_fetch_cli.build_parser().parse_args(
            ["--query", "10.1000/example"]
        )
        self.assertEqual(
            (
                cli_args.format,
                cli_args.output,
                cli_args.output_dir,
                cli_args.artifact_mode,
                cli_args.no_download,
                cli_args.save_markdown,
                cli_args.include_refs,
                cli_args.asset_profile,
                cli_args.max_tokens,
            ),
            (
                "markdown",
                "-",
                None,
                "markdown-assets",
                False,
                False,
                None,
                "body",
                "full_text",
            ),
        )

        mcp_request = mcp_tools.FetchPaperRequest(query="10.1000/example")
        self.assertEqual(
            (
                mcp_request.modes,
                mcp_request.strategy.allow_metadata_only_fallback,
                mcp_request.strategy.preferred_providers,
                mcp_request.strategy.asset_profile,
                mcp_request.include_refs,
                mcp_request.max_tokens,
                mcp_request.prefer_cache,
                mcp_request.no_download,
                mcp_request.artifact_mode,
                mcp_request.save_markdown,
                mcp_request.markdown_output_dir,
                mcp_request.markdown_filename,
            ),
            (
                ["article", "markdown"],
                True,
                None,
                None,
                None,
                "full_text",
                False,
                False,
                "markdown-assets",
                False,
                None,
                None,
            ),
        )

    def test_cli_temporary_primary_and_extra_save_products(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            temporary_dir = root / "temporary"
            temporary_stdout = io.StringIO()
            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=_cli_fetch
                ),
                contextlib.redirect_stdout(temporary_stdout),
            ):
                exit_code = paper_fetch_cli.main(
                    [
                        "--query",
                        "10.1016/test",
                        "--format",
                        "markdown",
                        "--output",
                        "-",
                        "--output-dir",
                        str(temporary_dir),
                        "--no-download",
                        "--artifact-mode",
                        "none",
                        "--asset-profile",
                        "none",
                        "--include-refs",
                        "all",
                        "--max-tokens",
                        "full_text",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("# Example Article", temporary_stdout.getvalue())
            self.assertTrue(temporary_dir.is_dir())
            self.assertEqual(
                [path for path in temporary_dir.rglob("*") if path.is_file()], []
            )

            archive_dir = root / "archive"
            output_path = archive_dir / "paper.md"
            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=_cli_fetch
                ),
            ):
                exit_code = paper_fetch_cli.main(
                    [
                        "--query",
                        "10.1016/test",
                        "--format",
                        "markdown",
                        "--output",
                        str(output_path),
                        "--output-dir",
                        str(archive_dir),
                        "--artifact-mode",
                        "none",
                        "--asset-profile",
                        "none",
                        "--include-refs",
                        "all",
                        "--max-tokens",
                        "full_text",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                {path.name for path in archive_dir.rglob("*") if path.is_file()},
                {"paper.md"},
            )

            extra_dir = root / "extra"
            json_path = extra_dir / "paper.json"
            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=_cli_fetch
                ),
            ):
                exit_code = paper_fetch_cli.main(
                    [
                        "--query",
                        "10.1016/test",
                        "--format",
                        "json",
                        "--output",
                        str(json_path),
                        "--output-dir",
                        str(extra_dir),
                        "--save-markdown",
                        "--artifact-mode",
                        "none",
                        "--asset-profile",
                        "none",
                        "--include-refs",
                        "all",
                        "--max-tokens",
                        "full_text",
                    ]
                )

            self.assertEqual(exit_code, 0)
            extra_files = {
                path.suffix for path in extra_dir.rglob("*") if path.is_file()
            }
            self.assertEqual(extra_files, {".json", ".md"})

    def test_mcp_temporary_cache_only_and_text_archive_products(self) -> None:
        def fake_fetch(query, **kwargs):
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            temporary_dir = root / "temporary"
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch
                ),
            ):
                temporary = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["article", "markdown"],
                    strategy={
                        "allow_metadata_only_fallback": True,
                        "preferred_providers": None,
                        "asset_profile": "none",
                        "inline_image_budget": None,
                    },
                    include_refs="all",
                    max_tokens="full_text",
                    prefer_cache=False,
                    no_download=True,
                    artifact_mode="none",
                    save_markdown=False,
                    markdown_output_dir=None,
                    markdown_filename=None,
                    download_dir=temporary_dir,
                )

            self.assertIsNotNone(temporary["markdown"])
            self.assertFalse(temporary_dir.exists())

            cache_dir = root / "cache"
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch
                ),
            ):
                cached = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["article", "markdown"],
                    strategy={
                        "allow_metadata_only_fallback": True,
                        "preferred_providers": None,
                        "asset_profile": "none",
                        "inline_image_budget": None,
                    },
                    include_refs="all",
                    max_tokens="full_text",
                    prefer_cache=True,
                    no_download=False,
                    artifact_mode="none",
                    save_markdown=False,
                    markdown_output_dir=None,
                    markdown_filename=None,
                    download_dir=cache_dir,
                )

            self.assertIsNotNone(cached["markdown"])
            cache_files = {path.name for path in cache_dir.rglob("*") if path.is_file()}
            cache_payloads = {
                name for name in cache_files if name.endswith(".fetch-envelope.json")
            }
            self.assertEqual(len(cache_payloads), 2)
            self.assertIn("10.1000_example.fetch-envelope.json", cache_payloads)
            self.assertTrue(
                any(
                    name.startswith("10.1000_example.")
                    and name != "10.1000_example.fetch-envelope.json"
                    for name in cache_payloads
                )
            )
            self.assertIn(".paper-fetch-mcp-cache.json", cache_files)
            self.assertEqual(
                len([name for name in cache_files if name.endswith(".lock")]), 2
            )

            archive_dir = root / "archive"
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch
                ),
            ):
                archive = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["article", "markdown"],
                    strategy={
                        "allow_metadata_only_fallback": True,
                        "preferred_providers": None,
                        "asset_profile": "none",
                        "inline_image_budget": None,
                    },
                    include_refs="all",
                    max_tokens="full_text",
                    prefer_cache=True,
                    no_download=True,
                    artifact_mode="none",
                    save_markdown=True,
                    markdown_output_dir=str(archive_dir),
                    markdown_filename="paper.md",
                    download_dir=archive_dir,
                )

            self.assertIsNone(archive["markdown"])
            self.assertIsNone(archive["article"])
            self.assertEqual(
                archive["saved_markdown_path"], str(archive_dir / "paper.md")
            )
            archive_files = {
                path.name for path in archive_dir.rglob("*") if path.is_file()
            }
            self.assertEqual(
                {"paper.md", ".paper-fetch-mcp-cache.json"},
                {name for name in archive_files if not name.endswith(".lock")},
            )
            # A missing cache scope is inspected without materializing a DOI lock;
            # only the Markdown index commit needs a lock file.
            self.assertEqual(
                len([name for name in archive_files if name.endswith(".lock")]), 1
            )

    def test_shared_asset_policy_materializes_none_body_and_all_scopes(self) -> None:
        cases = (
            ("markdown-assets", "none", set()),
            ("none", "all", set()),
            ("markdown-assets", "body", {"body.png"}),
            ("markdown-assets", "all", {"body.png", "supplementary.zip"}),
        )
        for artifact_mode, asset_profile, expected_files in cases:
            with (
                self.subTest(artifact_mode=artifact_mode, asset_profile=asset_profile),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                output_dir = Path(tmpdir)
                store = ArtifactStore.from_download_dir(
                    output_dir, artifact_mode=artifact_mode
                )
                context = RuntimeContext(
                    env={}, download_dir=output_dir, artifact_mode=artifact_mode
                )
                try:
                    _provider_fetch_result(
                        _LocalAssetProvider(),
                        doi="10.1000/example",
                        metadata={"doi": "10.1000/example"},
                        artifact_store=store,
                        asset_profile=asset_profile,
                        context=context,
                    )
                finally:
                    context.close()

                self.assertEqual(
                    {path.name for path in output_dir.rglob("*") if path.is_file()},
                    expected_files,
                )

    def test_over_fifty_metadata_probes_are_chunked_and_merged_by_original_index(
        self,
    ) -> None:
        queries = [f"10.1000/item-{index:03d}" for index in range(1, 114)]
        indexed_queries = list(enumerate(queries, start=1))
        chunks = [
            indexed_queries[offset : offset + 50]
            for offset in range(0, len(indexed_queries), 50)
        ]

        def fake_probe(query, *, context=None):
            del context
            index = int(query.rsplit("-", 1)[1])
            return sample_probe_result(
                query,
                state="likely_yes" if index % 2 else "unknown",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            collected: list[tuple[int, dict[str, object]]] = []
            original_indexes = {query: index for index, query in indexed_queries}
            with (
                mock.patch.object(
                    mcp_tools,
                    "build_runtime_env",
                    return_value={"PAPER_FETCH_DOWNLOAD_DIR": str(root / "unused")},
                ),
                mock.patch.object(
                    mcp_tools, "service_probe_has_fulltext", side_effect=fake_probe
                ),
                mock.patch.object(mcp_tools, "service_fetch_paper") as fetch,
            ):
                for chunk in chunks:
                    payload = mcp_tools.batch_check_payload(
                        queries=[query for _, query in chunk],
                        mode="metadata",
                        concurrency=4,
                    )
                    self.assertFalse(payload["aborted"])
                    for item in payload["results"]:
                        collected.append((original_indexes[item["query"]], item))

            merged = sorted(collected, key=lambda pair: pair[0])
            self.assertEqual([len(chunk) for chunk in chunks], [50, 50, 13])
            self.assertEqual([index for index, _ in merged], list(range(1, 114)))
            self.assertEqual([item["query"] for _, item in merged], queries)
            self.assertEqual(
                {item["probe_state"] for _, item in merged},
                {"likely_yes", "unknown"},
            )
            self.assertTrue(
                all(
                    item["content_kind"] is None and item["source"] is None
                    for _, item in merged
                )
            )
            self.assertEqual(list(root.rglob("*")), [])
            fetch.assert_not_called()

    def test_local_fulltext_hit_is_offline_and_request_mismatch_fetches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            markdown_path = download_dir / "local.md"
            markdown_path.write_text(
                "---\n"
                'doi: "10.1000/local"\n'
                'source: "local_archive"\n'
                "has_fulltext: true\n"
                'content_kind: "fulltext"\n'
                "---\n\n# Local full text\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("local cache lookup must not use network"),
            ) as create_connection:
                local = mcp_tools.get_cached_payload(
                    doi="10.1000/local", download_dir=download_dir
                )

            self.assertEqual(local["status"], "hit")
            self.assertEqual(
                local["preferred"]["markdown"]["path"], str(markdown_path.resolve())
            )
            create_connection.assert_not_called()

            create_cached_fetch_envelope(
                download_dir, "10.1000/mismatch", modes=["markdown"]
            )
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/mismatch"),
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    return_value=sample_envelope(
                        modes={"article"}, doi="10.1000/mismatch"
                    ),
                ) as fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/mismatch",
                    modes=["article"],
                    strategy={"asset_profile": "none"},
                    include_refs="none",
                    max_tokens="full_text",
                    prefer_cache=True,
                    no_download=False,
                    artifact_mode="none",
                    save_markdown=False,
                    download_dir=download_dir,
                )

            self.assertIsNotNone(payload["article"])
            fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
