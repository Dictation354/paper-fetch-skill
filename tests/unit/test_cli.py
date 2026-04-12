from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from paper_fetch import cli as paper_fetch_cli
from paper_fetch import service as paper_fetch
from paper_fetch.models import Asset, RenderOptions
from paper_fetch.providers.base import ProviderFailure

from ._paper_fetch_support import build_envelope, sample_article


class CliTests(unittest.TestCase):
    def test_main_writes_markdown_json_and_both_to_stdout(self) -> None:
        article = sample_article()
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            paper_fetch_cli.fetch_paper = lambda *args, **kwargs: build_envelope(article)
            for output_format in ("markdown", "json", "both"):
                stdout = io.StringIO()
                stderr = io.StringIO()
                argv = [
                    "paper_fetch.py",
                    "--query",
                    "10.1016/test",
                    "--format",
                    output_format,
                ]
                original_argv = sys.argv
                sys.argv = argv
                try:
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, 0)
                self.assertEqual(stderr.getvalue(), "")
                rendered = stdout.getvalue()
                self.assertTrue(rendered)
                if output_format == "markdown":
                    self.assertIn("# Example Article", rendered)
                else:
                    payload = json.loads(rendered)
                    if output_format == "json":
                        self.assertEqual(payload["doi"], "10.1016/test")
                    else:
                        self.assertIn("article", payload)
                        self.assertIn("markdown", payload)
        finally:
            paper_fetch_cli.fetch_paper = original_fetch

    def test_main_writes_single_output_file_when_requested(self) -> None:
        article = sample_article()
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            paper_fetch_cli.fetch_paper = lambda *args, **kwargs: build_envelope(article)
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "article.md"
                stdout = io.StringIO()
                original_argv = sys.argv
                sys.argv = ["paper_fetch.py", "--query", "10.1016/test", "--output", str(output_path)]
                try:
                    with contextlib.redirect_stdout(stdout):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, 0)
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue(output_path.exists())
                self.assertIn("# Example Article", output_path.read_text(encoding="utf-8"))
        finally:
            paper_fetch_cli.fetch_paper = original_fetch

    def test_main_uses_resolved_default_download_dir_for_save_markdown(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            captured.update(kwargs)
            return build_envelope(article)

        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "downloads"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = ["paper_fetch.py", "--query", "10.1016/test", "--save-markdown"]
            try:
                with (
                    mock.patch.object(paper_fetch_cli, "build_runtime_env", return_value={}),
                    mock.patch.object(paper_fetch_cli, "resolve_cli_download_dir", return_value=default_dir),
                    mock.patch.object(paper_fetch_cli, "fetch_paper", side_effect=fake_fetch),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["download_dir"], default_dir)
            self.assertTrue((default_dir / "10.1016_test.md").exists())

    def test_save_markdown_to_disk_rewrites_local_asset_links_relative_to_saved_file(self) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir(parents=True)
            figure_path = asset_dir / "figure%201.png"
            supplement_path = asset_dir / "supplement data%.pdf"
            figure_path.write_bytes(b"figure")
            supplement_path.write_bytes(b"supplement")
            article.sections[0].text += f"\n\nAbsolute path mention: {figure_path}"

            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body figure.", path=str(figure_path), section="body"),
                Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", path=str(supplement_path)),
                Asset(
                    kind="supplementary",
                    heading="Remote Appendix",
                    caption="Hosted by publisher.",
                    url="https://example.test/appendix.pdf",
                ),
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="all"),
            )

            assert envelope.markdown is not None
            self.assertIn(str(figure_path), envelope.markdown)
            self.assertIn(str(supplement_path), envelope.markdown)

            paper_fetch_cli.save_markdown_to_disk(
                envelope,
                output_dir=output_dir,
                render=RenderOptions(asset_profile="all"),
            )

            rendered = (output_dir / "10.1016_test.md").read_text(encoding="utf-8")
            self.assertIn("![Figure 1](10.1016_test_assets/figure%25201.png)", rendered)
            self.assertIn("[Supplementary Data](10.1016_test_assets/supplement%20data%25.pdf)", rendered)
            self.assertIn("[Remote Appendix](https://example.test/appendix.pdf)", rendered)
            self.assertIn(f"Absolute path mention: {figure_path}", rendered)
            self.assertEqual(rendered.count(str(figure_path)), 1)
            self.assertNotIn(f"]({figure_path})", rendered)
            self.assertNotIn(f"]({supplement_path})", rendered)

    def test_main_rewrites_local_asset_links_for_markdown_output_file(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body figure.", path=str(figure_path), section="body")
            ]

            def fake_fetch(*args, **kwargs):
                captured.update(kwargs)
                return paper_fetch.build_fetch_envelope(article, modes=kwargs["modes"], render=kwargs["render"])

            output_path = output_dir / "article.md"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--format",
                "markdown",
                "--asset-profile",
                "body",
                "--output",
                str(output_path),
            ]
            try:
                with (
                    mock.patch.object(paper_fetch_cli, "build_runtime_env", return_value={}),
                    mock.patch.object(paper_fetch_cli, "resolve_cli_download_dir", return_value=output_dir),
                    mock.patch.object(paper_fetch_cli, "fetch_paper", side_effect=fake_fetch),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["modes"], {"article", "markdown"})
            self.assertEqual(captured["download_dir"], output_dir)
            rendered = output_path.read_text(encoding="utf-8")
            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", rendered)
            self.assertNotIn(str(figure_path), rendered)

    def test_rewrite_markdown_asset_links_only_changes_placeholder_links(self) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            supplementary_path = asset_dir / "figure-1.png.backup"
            figure_path.write_bytes(b"figure")
            supplementary_path.write_bytes(b"supplementary")
            article.sections[0].text += f"\n\nBody mentions {figure_path} and {supplementary_path}."
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body figure.", path=str(figure_path), section="body"),
                Asset(kind="supplementary", heading="Backup", caption="Archive.", path=str(supplementary_path)),
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="all"),
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="all"),
            )

            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", rewritten)
            self.assertIn("[Backup](10.1016_test_assets/figure-1.png.backup)", rewritten)
            self.assertIn(f"Body mentions {figure_path} and {supplementary_path}.", rewritten)

    def test_main_rewrites_local_asset_links_for_both_output_file(self) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body figure.", path=str(figure_path), section="body")
            ]

            def fake_fetch(*args, **kwargs):
                return paper_fetch.build_fetch_envelope(article, modes=kwargs["modes"], render=kwargs["render"])

            output_path = output_dir / "result.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--format",
                "both",
                "--asset-profile",
                "body",
                "--output",
                str(output_path),
            ]
            try:
                with (
                    mock.patch.object(paper_fetch_cli, "build_runtime_env", return_value={}),
                    mock.patch.object(paper_fetch_cli, "resolve_cli_download_dir", return_value=output_dir),
                    mock.patch.object(paper_fetch_cli, "fetch_paper", side_effect=fake_fetch),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", payload["markdown"])
            self.assertNotIn(str(figure_path), payload["markdown"])

    def test_main_defaults_to_full_text_and_asset_profile_none(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            captured.update(kwargs)
            return build_envelope(article)

        stdout = io.StringIO()
        stderr = io.StringIO()
        original_argv = sys.argv
        sys.argv = ["paper_fetch.py", "--query", "10.1016/test"]
        try:
            with (
                mock.patch.object(paper_fetch_cli, "build_runtime_env", return_value={}),
                mock.patch.object(paper_fetch_cli, "resolve_cli_download_dir", return_value=Path("/tmp/downloads")),
                mock.patch.object(paper_fetch_cli, "fetch_paper", side_effect=fake_fetch),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(captured["render"], RenderOptions(include_refs=None, asset_profile="none", max_tokens="full_text"))
        self.assertEqual(
            captured["strategy"],
            paper_fetch.FetchStrategy(
                allow_html_fallback=True,
                allow_metadata_only_fallback=True,
                preferred_providers=None,
                asset_profile="none",
            ),
        )

    def test_parse_max_tokens_accepts_full_text_and_integers(self) -> None:
        self.assertEqual(paper_fetch_cli.parse_max_tokens("full_text"), "full_text")
        self.assertEqual(paper_fetch_cli.parse_max_tokens("16000"), 16000)

    def test_compute_modes_covers_stdout_file_both_and_save_markdown(self) -> None:
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(format="markdown", output="-", save_markdown=False, no_download=False)
            ),
            {"markdown"},
        )
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(format="markdown", output="/tmp/out.md", save_markdown=False, no_download=False)
            ),
            {"article", "markdown"},
        )
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(format="both", output="-", save_markdown=False, no_download=True)
            ),
            {"article", "markdown"},
        )
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(format="json", output="-", save_markdown=True, no_download=True)
            ),
            {"article", "markdown"},
        )

    def test_exit_code_for_error_maps_specific_statuses(self) -> None:
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(paper_fetch.PaperFetchFailure("ambiguous", "Need user confirmation.")),
            2,
        )
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(ProviderFailure("no_access", "Forbidden")),
            3,
        )
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(ProviderFailure("rate_limited", "Slow down")),
            4,
        )
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(ProviderFailure("error", "Unexpected provider error")),
            1,
        )

    def test_main_reports_ambiguous_errors_as_json(self) -> None:
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            paper_fetch_cli.fetch_paper = lambda *args, **kwargs: (_ for _ in ()).throw(
                paper_fetch.PaperFetchFailure(
                    "ambiguous",
                    "Need user confirmation.",
                    candidates=[{"doi": "10.1000/a", "title": "Candidate A"}],
                )
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = ["paper_fetch.py", "--query", "ambiguous title"]
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["status"], "ambiguous")
            self.assertEqual(payload["candidates"][0]["doi"], "10.1000/a")
        finally:
            paper_fetch_cli.fetch_paper = original_fetch

    def test_main_reports_provider_failure_status_and_exit_code(self) -> None:
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            for code, expected_exit_code in (("no_access", 3), ("rate_limited", 4), ("error", 1)):
                stdout = io.StringIO()
                stderr = io.StringIO()
                paper_fetch_cli.fetch_paper = lambda *args, _code=code, **kwargs: (_ for _ in ()).throw(
                    ProviderFailure(_code, f"{_code} failure")
                )
                original_argv = sys.argv
                sys.argv = ["paper_fetch.py", "--query", "10.1016/test"]
                try:
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, expected_exit_code)
                payload = json.loads(stderr.getvalue())
                self.assertEqual(payload["status"], code)
                self.assertIn("failure", payload["reason"])
        finally:
            paper_fetch_cli.fetch_paper = original_fetch
