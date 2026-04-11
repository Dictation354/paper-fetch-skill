from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fitz

from paper_fetch import cli as paper_fetch_cli
from paper_fetch import service as paper_fetch
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.models import Asset, ArticleModel, FetchEnvelope, Metadata, Quality, Reference, RenderOptions, Section, article_from_markdown
from paper_fetch.providers import html_generic
from paper_fetch.providers.base import RawFulltextPayload
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.utils import empty_asset_results


class StubProvider:
    def __init__(
        self,
        metadata=None,
        raw_payload=None,
        raw_error=None,
        article=None,
        article_factory=None,
        related_assets=None,
        related_asset_factory=None,
        related_asset_error=None,
    ):
        self._metadata = metadata
        self._raw_payload = raw_payload
        self._raw_error = raw_error
        self._article = article
        self._article_factory = article_factory
        self._related_assets = related_assets
        self._related_asset_factory = related_asset_factory
        self._related_asset_error = related_asset_error

    def fetch_metadata(self, query):
        if isinstance(self._metadata, Exception):
            raise self._metadata
        return self._metadata

    def fetch_raw_fulltext(self, doi, metadata):
        if self._raw_error:
            raise self._raw_error
        return self._raw_payload

    def to_article_model(self, metadata, raw_payload):
        if self._article_factory is not None:
            return self._article_factory(metadata, raw_payload)
        return self._article

    def download_related_assets(self, doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
        if self._related_asset_error:
            raise self._related_asset_error
        if self._related_asset_factory is not None:
            return self._related_asset_factory(doi, metadata, raw_payload, output_dir, asset_profile=asset_profile)
        if self._related_assets is not None:
            return self._related_assets
        return empty_asset_results()


class StubHtmlClient:
    def __init__(self, article=None, error=None):
        self.article = article
        self.error = error

    def fetch_article_model(self, landing_url, *, metadata=None, expected_doi=None, download_dir=None, asset_profile="none"):
        if self.error:
            raise self.error
        return self.article


class FixtureHtmlTransport(HttpTransport):
    def __init__(self, responses):
        self.responses = responses

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=20,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        if url not in self.responses:
            raise html_generic.RequestFailure(404, f"Missing fixture response for {url}")
        response = dict(self.responses[url])
        response.setdefault("status_code", 200)
        response.setdefault("headers", {})
        response.setdefault("url", url)
        return response


def build_envelope(article: ArticleModel, *, include_markdown: bool = True) -> FetchEnvelope:
    modes = {"article"}
    if include_markdown:
        modes.add("markdown")
    return paper_fetch.build_fetch_envelope(article, modes=modes, render=RenderOptions())


def fetch_paper_model(
    query: str,
    *,
    allow_html_fallback: bool = True,
    allow_downloads: bool = True,
    asset_profile: str = "none",
    output_dir: Path | None = None,
    clients=None,
    html_client=None,
    transport=None,
    env=None,
) -> ArticleModel:
    envelope = paper_fetch.fetch_paper(
        query,
        modes={"article"},
        strategy=paper_fetch.FetchStrategy(
            allow_html_fallback=allow_html_fallback,
            allow_metadata_only_fallback=True,
            asset_profile=asset_profile,
        ),
        download_dir=output_dir if allow_downloads else None,
        clients=clients,
        html_client=html_client,
        transport=transport,
        env=env,
    )
    assert envelope.article is not None
    return envelope.article


def sample_article() -> paper_fetch.ArticleModel:
    return ArticleModel(
        doi="10.1016/test",
        source="elsevier_xml",
        metadata=Metadata(
            title="Example Article",
            authors=["Alice Example", "Bob Example"],
            abstract="Example abstract",
            journal="Example Journal",
            published="2026-01-01",
        ),
        sections=[
            Section(heading="Introduction", level=2, kind="body", text="Introduction text " * 30),
            Section(heading="Discussion", level=2, kind="body", text="Discussion text " * 30),
        ],
        references=[],
        assets=[],
        quality=Quality(has_fulltext=True, token_estimate=600, warnings=[]),
    )


def sample_html_article() -> paper_fetch.ArticleModel:
    article = sample_article()
    article.source = "html_generic"
    return article


def build_pdf_bytes(lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    y = 72
    for line in lines:
        if y > 760:
            page = document.new_page()
            y = 72
        page.insert_text((72, y), line)
        y += 14
    payload = document.tobytes()
    document.close()
    return payload


def fulltext_pdf_bytes() -> bytes:
    paragraph = "This study evaluates landscape responses using repeated satellite observations across multiple seasons."
    lines = ["Abstract"]
    lines.extend([paragraph] * 14)
    lines.append("Introduction")
    lines.extend([paragraph] * 18)
    lines.append("Methods")
    lines.extend([paragraph] * 18)
    lines.append("Results")
    lines.extend([paragraph] * 18)
    lines.append("Discussion")
    lines.extend([paragraph] * 18)
    lines.append("References")
    lines.extend([paragraph] * 6)
    return build_pdf_bytes(lines)


def short_pdf_bytes() -> bytes:
    return build_pdf_bytes(["Journal cover", "Author information", "Downloaded PDF"])


class PaperFetchTests(unittest.TestCase):
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
            figure_path = asset_dir / "figure 1.png"
            supplement_path = asset_dir / "supplement data.pdf"
            figure_path.write_bytes(b"figure")
            supplement_path.write_bytes(b"supplement")

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

            paper_fetch_cli.save_markdown_to_disk(envelope, output_dir=output_dir)

            rendered = (output_dir / "10.1016_test.md").read_text(encoding="utf-8")
            self.assertIn("![Figure 1](10.1016_test_assets/figure%201.png)", rendered)
            self.assertIn("[Supplementary Data](10.1016_test_assets/supplement%20data.pdf)", rendered)
            self.assertIn("[Remote Appendix](https://example.test/appendix.pdf)", rendered)
            self.assertNotIn(str(figure_path), rendered)
            self.assertNotIn(str(supplement_path), rendered)

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

    def test_fetch_paper_model_prefers_raw_xml_pipeline(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        official_article.source = "elsevier_xml"
        official_article.quality.has_fulltext = True
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1016/test",
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                            metadata={"reason": "Downloaded full text from the official Elsevier API."},
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "authors": ["Alice Example"],
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)

    def test_fetch_paper_model_uses_official_pipeline_for_resolved_elsevier_url(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
            query_kind="url",
            doi="10.1016/test",
            landing_url="https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
            title="Example Article",
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                resolved.query,
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                            metadata={"reason": "Downloaded full text from the official Elsevier API."},
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": resolved.landing_url,
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("resolve:url", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)

    def test_fetch_paper_model_downloads_related_assets_for_official_xml(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()

        def write_related_assets(doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir(parents=True, exist_ok=True)
            figure_path = asset_dir / "figure-1.png"
            supplement_path = asset_dir / "supplement.pdf"
            figure_path.write_bytes(b"fake-image")
            supplement_path.write_bytes(b"%PDF-1.7 fake supplement")
            return {
                "assets": [
                    {
                        "asset_type": "image",
                        "path": str(figure_path),
                    },
                    {
                        "asset_type": "supplementary",
                        "path": str(supplement_path),
                    },
                ],
                "asset_failures": [],
            }

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=official_article,
                            related_asset_factory=write_related_assets,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
                asset_dir = Path(tmpdir) / "10.1016_test_assets"
                self.assertTrue((asset_dir / "figure-1.png").exists())
                self.assertTrue((asset_dir / "supplement.pdf").exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIn("download:elsevier_assets_saved_profile_all", article.quality.source_trail)

    def test_fetch_paper_model_skips_related_asset_downloads_when_no_download_is_set(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        related_asset_calls: list[str] = []

        def write_related_assets(doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
            related_asset_calls.append(doi)
            return empty_asset_results()

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    allow_downloads=False,
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=official_article,
                            related_asset_factory=write_related_assets,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(related_asset_calls, [])
        self.assertNotIn("download:elsevier_assets_saved", article.quality.source_trail)

    def test_fetch_paper_model_skips_related_asset_downloads_for_profile_none(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        related_asset_calls: list[str] = []

        def write_related_assets(doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
            related_asset_calls.append(asset_profile)
            return empty_asset_results()

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="none",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=official_article,
                            related_asset_factory=write_related_assets,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(related_asset_calls, [])
        self.assertIn("download:elsevier_assets_skipped_profile_none", article.quality.source_trail)

    def test_fetch_paper_model_treats_request_failure_during_asset_download_as_warning(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=sample_article(),
                            related_asset_error=RequestFailure(503, "HTTP 503 for https://example.test/asset"),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertIn("download:elsevier_assets_failed", article.quality.source_trail)
        self.assertTrue(any("HTTP 503" in warning for warning in article.quality.warnings))

    def test_fetch_paper_model_treats_oserror_during_asset_download_as_warning(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=sample_article(),
                            related_asset_error=OSError("disk full"),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertIn("download:elsevier_assets_failed", article.quality.source_trail)
        self.assertTrue(any("disk full" in warning for warning in article.quality.warnings))

    def test_fetch_paper_model_does_not_swallow_programming_errors_during_asset_download(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(AttributeError):
                    fetch_paper_model(
                        "10.1016/test",
                        asset_profile="all",
                        output_dir=Path(tmpdir),
                        clients={
                            "elsevier": StubProvider(
                                metadata={
                                    "provider": "elsevier",
                                    "official_provider": True,
                                    "doi": "10.1016/test",
                                    "title": "Example Article",
                                    "landing_page_url": "https://example.test/article",
                                    "fulltext_links": [],
                                    "references": [],
                                },
                                raw_payload=RawFulltextPayload(
                                    provider="elsevier",
                                    source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                    content_type="text/xml",
                                    body=b"<xml/>",
                                    metadata={"reason": "Downloaded full text from the official Elsevier API."},
                                ),
                                article=sample_article(),
                                related_asset_error=AttributeError("buggy asset pipeline"),
                            ),
                            "crossref": StubProvider(
                                metadata={
                                    "provider": "crossref",
                                    "official_provider": False,
                                    "doi": "10.1016/test",
                                    "title": "Example Article",
                                    "landing_page_url": "https://example.test/article",
                                    "fulltext_links": [],
                                    "references": [],
                                }
                            ),
                        },
                        html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                    )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_fetch_metadata_uses_crossref_signal_without_public_crossref_source(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )

        metadata, provider_name, source_trail = paper_fetch.fetch_metadata_for_resolved_query(
            resolved,
            clients={
                "elsevier": StubProvider(
                    metadata={
                        "provider": "elsevier",
                        "official_provider": True,
                        "doi": "10.1006/jaer.1996.0085",
                        "title": "Official Elsevier Title",
                        "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                        "authors": ["Alice Example"],
                        "fulltext_links": [],
                        "references": [],
                    }
                ),
                "crossref": StubProvider(
                    metadata={
                        "provider": "crossref",
                        "official_provider": False,
                        "doi": "10.1006/jaer.1996.0085",
                        "title": "Crossref Title",
                        "publisher": "Elsevier BV",
                        "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                        "authors": ["Alice Example"],
                        "fulltext_links": [],
                        "references": [],
                    }
                ),
            },
            strategy=paper_fetch.FetchStrategy(preferred_providers=["elsevier"]),
        )

        self.assertEqual(provider_name, "elsevier")
        self.assertEqual(metadata["title"], "Official Elsevier Title")
        self.assertIn("route:crossref_signal_ok", source_trail)
        self.assertIn("route:signal_domain_elsevier", source_trail)
        self.assertIn("route:signal_publisher_elsevier", source_trail)
        self.assertIn("route:probe_elsevier_positive", source_trail)
        self.assertIn("route:provider_selected_elsevier", source_trail)
        self.assertIn("metadata:elsevier_ok", source_trail)
        self.assertNotIn("metadata:crossref_ok", source_trail)

    def test_fetch_metadata_records_unknown_probe_and_uses_crossref_public_metadata(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            provider_hint="springer",
            confidence=1.0,
        )

        metadata, provider_name, source_trail = paper_fetch.fetch_metadata_for_resolved_query(
            resolved,
            clients={
                "springer": StubProvider(
                    metadata=paper_fetch.ProviderFailure("not_configured", "SPRINGER_META_API_KEY is not configured.")
                ),
                "crossref": StubProvider(
                    metadata={
                        "provider": "crossref",
                        "official_provider": False,
                        "doi": "10.1007/test",
                        "title": "Crossref Fallback",
                        "landing_page_url": "https://example.test/article",
                        "authors": [],
                        "fulltext_links": [],
                        "references": [],
                    }
                ),
            },
            strategy=paper_fetch.FetchStrategy(),
        )

        self.assertEqual(provider_name, "springer")
        self.assertEqual(metadata["title"], "Crossref Fallback")
        self.assertIn("route:probe_springer_unknown", source_trail)
        self.assertIn("route:provider_selected_springer", source_trail)
        self.assertIn("metadata:crossref_ok", source_trail)

    def test_fetch_paper_model_routes_10_1006_doi_to_elsevier_via_crossref_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = paper_fetch.fetch_paper(
                "10.1006/jaer.1996.0085",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(
                    allow_html_fallback=False,
                    preferred_providers=["elsevier"],
                ),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Official Elsevier Title",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1006%2Fjaer.1996.0085",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Crossref Title",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            ).article
        finally:
            paper_fetch.resolve_paper = original_resolve

        assert article is not None
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("route:crossref_signal_ok", article.quality.source_trail)
        self.assertIn("route:provider_selected_elsevier", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertNotIn("metadata:crossref_ok", article.quality.source_trail)

    def test_fetch_paper_model_weak_negative_metadata_probe_still_attempts_official_fulltext(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1006/jaer.1996.0085",
                allow_html_fallback=False,
                clients={
                    "elsevier": StubProvider(
                        metadata=paper_fetch.ProviderFailure("no_result", "Elsevier metadata probe missed."),
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1006%2Fjaer.1996.0085",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Crossref Title",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("route:probe_elsevier_negative", article.quality.source_trail)
        self.assertIn("route:provider_selected_elsevier", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_attempt", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)

    def test_fetch_paper_crossref_only_strategy_skips_official_probes(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            envelope = paper_fetch.fetch_paper(
                "10.1016/test",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(
                    allow_html_fallback=False,
                    preferred_providers=["crossref"],
                ),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Official Elsevier Title",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=sample_article(),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Crossref Title",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        assert envelope.article is not None
        self.assertEqual(envelope.article.source, "crossref_meta")
        self.assertIn("metadata:crossref_ok", envelope.article.quality.source_trail)
        self.assertNotIn("route:probe_elsevier_positive", envelope.article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_attempt", envelope.article.quality.source_trail)

    def test_fetch_paper_returns_fixed_envelope_shape_with_public_source_mapping(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        official_article = sample_article()
        official_article.source = "wiley"
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            envelope = paper_fetch.fetch_paper(
                "10.1111/test",
                modes={"markdown"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "wiley": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_payload=RawFulltextPayload(
                            provider="wiley",
                            source_url="https://example.test/wiley.pdf",
                            content_type="application/pdf",
                            body=b"%PDF-1.4",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/wiley",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(
            set(envelope.to_dict().keys()),
            {"doi", "source", "has_fulltext", "warnings", "source_trail", "token_estimate", "article", "markdown", "metadata"},
        )
        self.assertEqual(envelope.source, "wiley_tdm")
        self.assertIsNone(envelope.article)
        self.assertIsNone(envelope.metadata)
        self.assertTrue(envelope.markdown)
        self.assertTrue(envelope.has_fulltext)

    def test_fetch_paper_only_populates_envelope_metadata_when_requested(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            without_metadata = paper_fetch.fetch_paper(
                "10.1016/test",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
            with_metadata = paper_fetch.fetch_paper(
                "10.1016/test",
                modes={"article", "metadata"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIsNone(without_metadata.metadata)
        self.assertIsNotNone(with_metadata.metadata)
        self.assertEqual(with_metadata.metadata.title, with_metadata.article.metadata.title)

    def test_fetch_paper_raises_when_metadata_only_fallback_is_disabled(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with self.assertRaises(paper_fetch.PaperFetchFailure):
                paper_fetch.fetch_paper(
                    "10.1016/test",
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(
                        allow_html_fallback=False,
                        allow_metadata_only_fallback=False,
                    ),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_error=paper_fetch.ProviderFailure("no_result", "No full text."),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_fetch_paper_model_records_rate_limited_fulltext_trail(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1016/test",
                allow_html_fallback=False,
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_error=paper_fetch.ProviderFailure(
                            "rate_limited",
                            "HTTP 429 for https://api.elsevier.com/content/article/doi/10.1016%2Ftest (Retry-After: 3s)",
                            retry_after_seconds=3,
                        ),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertIn("fulltext:elsevier_rate_limited", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertTrue(any("Retry-After: 3s" in warning for warning in article.quality.warnings))

    def test_merge_metadata_preserves_explicit_blank_primary_scalar(self) -> None:
        merged = paper_fetch.merge_metadata(
            {"abstract": "", "title": "Primary Title"},
            {"abstract": "Crossref abstract", "title": "Secondary Title"},
        )

        self.assertIsNone(merged["abstract"])
        self.assertEqual(merged["title"], "Primary Title")

    def test_merge_metadata_dedupes_semantic_author_names(self) -> None:
        merged = paper_fetch.merge_metadata(
            {"authors": ["Zhang, San", "Alice Example"]},
            {"authors": ["San Zhang", "Alice Example"]},
        )

        self.assertEqual(merged["authors"], ["Zhang, San", "Alice Example"])

    def test_wiley_pdf_is_downloaded_and_extracted_into_fulltext(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1111/test",
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=RawFulltextPayload(
                                provider="wiley",
                                source_url="https://example.test/wiley.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                metadata={"reason": "Downloaded full text from the configured Wiley TDM endpoint."},
                                needs_local_copy=True,
                            ),
                            article_factory=WileyClient(HttpTransport(), {}).to_article_model,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley PDF Article",
                                "landing_page_url": "https://example.test/wiley",
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
                downloaded = Path(tmpdir) / "10.1111_test.pdf"
                self.assertTrue(downloaded.exists())
                self.assertTrue(downloaded.read_bytes().startswith(b"%PDF"))
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "wiley")
        self.assertTrue(article.quality.has_fulltext)
        self.assertTrue(any("downloaded as PDF/binary" in warning for warning in article.quality.warnings))
        self.assertTrue(any("extracted from PDF" in warning for warning in article.quality.warnings))
        self.assertIn("fulltext:wiley_pdf_extract_ok", article.quality.source_trail)
        self.assertIn("download:wiley_saved", article.quality.source_trail)

    def test_binary_downloads_follow_payload_semantics_not_provider_name(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="custompdf",
                                source_url="https://example.test/custom.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                metadata={"reason": "Downloaded full text from a custom PDF endpoint."},
                                needs_local_copy=True,
                            ),
                            article=official_article,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
                downloaded = Path(tmpdir) / "10.1016_test.pdf"
                self.assertTrue(downloaded.exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIn("download:custompdf_saved", article.quality.source_trail)
        self.assertNotIn("download:elsevier_saved", article.quality.source_trail)

    def test_wiley_pdf_can_be_processed_without_download_side_effects(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1111/test",
                    allow_downloads=False,
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=RawFulltextPayload(
                                provider="wiley",
                                source_url="https://example.test/wiley.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                metadata={"reason": "Downloaded full text from the configured Wiley TDM endpoint."},
                                needs_local_copy=True,
                            ),
                            article_factory=WileyClient(HttpTransport(), {}).to_article_model,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley PDF Article",
                                "landing_page_url": "https://example.test/wiley",
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
                )
                downloaded = Path(tmpdir) / "10.1111_test.pdf"
                self.assertFalse(downloaded.exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("download:wiley_skipped", article.quality.source_trail)
        self.assertTrue(any("--no-download" in warning for warning in article.quality.warnings))

    def test_wiley_pdf_extraction_failure_falls_back_to_html(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1111/test",
                allow_downloads=False,
                clients={
                    "wiley": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_payload=RawFulltextPayload(
                            provider="wiley",
                            source_url="https://example.test/wiley.pdf",
                            content_type="application/pdf",
                            body=short_pdf_bytes(),
                            metadata={"reason": "Downloaded full text from the configured Wiley TDM endpoint."},
                            needs_local_copy=True,
                        ),
                        article_factory=WileyClient(HttpTransport(), {}).to_article_model,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Wiley PDF Article",
                            "landing_page_url": "https://example.test/wiley",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(article=sample_html_article()),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "html_generic")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_pdf_extract_fail", article.quality.source_trail)
        self.assertIn("fallback:html_ok", article.quality.source_trail)
        self.assertTrue(any("did not produce enough usable article text" in warning for warning in article.quality.warnings))

    def test_springer_html_fallback_downloads_figure_assets_when_enabled(self) -> None:
        landing_url = "https://www.nature.com/articles/example"
        figure_page_url = "https://www.nature.com/articles/example/figures/1"
        preview_image_url = "https://media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png"
        full_image_url = "https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png"
        preview_bytes = b"preview-image"
        full_bytes = b"full-size-image"
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            landing_url=landing_url,
            provider_hint="springer",
            confidence=1.0,
        )
        html_client = html_generic.HtmlGenericClient(
            FixtureHtmlTransport(
                {
                    landing_url: {
                        "headers": {"content-type": "text/html; charset=utf-8"},
                        "body": (
                            b"<html><head>"
                            b'<meta name="citation_title" content="HTML Springer Article" />'
                            b'<meta name="citation_doi" content="10.1007/test" />'
                            b"</head><body>"
                            b'<div class="c-article-section__figure-item">'
                            b'<picture class="c-article-section__figure-picture">'
                            b'<img aria-describedby="figure-1-desc" src="//media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" alt="Preview image" />'
                            b"</picture>"
                            b'<div class="c-article-section__figure-link"><a href="/articles/example/figures/1" aria-label="Full size image figure 1">Full size image</a></div>'
                            b"</div>"
                            b'<div class="c-article-section__figure-description" id="figure-1-desc"><p>Figure showing a woodland canopy.</p></div>'
                            b"</body></html>"
                        ),
                    },
                    figure_page_url: {
                        "headers": {"content-type": "text/html; charset=utf-8"},
                        "body": (
                            b"<html><head>"
                            b'<meta name="twitter:image" content="https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />'
                            b"</head><body>"
                            b'<img src="//media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />'
                            b"</body></html>"
                        ),
                    },
                    preview_image_url: {
                        "headers": {"content-type": "image/png"},
                        "body": preview_bytes,
                    },
                    full_image_url: {
                        "headers": {"content-type": "image/png"},
                        "body": full_bytes,
                    },
                }
            ),
            {},
        )
        original_resolve = paper_fetch.resolve_paper
        original_extract = html_generic.extract_article_markdown
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            html_generic.extract_article_markdown = lambda html, url: "\n".join(
                [
                    "# HTML Springer Article",
                    "",
                    "## Introduction",
                    ("Important body text for HTML fallback. " * 30).strip(),
                    "",
                    "## Results",
                    ("More important body text for HTML fallback. " * 30).strip(),
                ]
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1007/test",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "springer": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_error=paper_fetch.ProviderFailure("no_result", "Official XML unavailable."),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1007/test",
                                "title": "HTML Springer Article",
                                "landing_page_url": landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    html_client=html_client,
                )
                markdown = article.to_ai_markdown(asset_profile="body")
                self.assertEqual(article.source, "html_generic")
                self.assertTrue(article.quality.has_fulltext)
                self.assertEqual(len(article.assets), 1)
                self.assertEqual(article.assets[0].section, "body")
                self.assertIsNotNone(article.assets[0].path)
                asset_path = Path(article.assets[0].path or "")
                self.assertTrue(asset_path.exists())
                self.assertEqual(asset_path.parent.name, "10.1007_test_assets")
                self.assertEqual(asset_path.read_bytes(), full_bytes)
                self.assertIn("![Figure showing a woodland canopy.]", markdown)
                self.assertIn(str(asset_path), markdown)
        finally:
            paper_fetch.resolve_paper = original_resolve
            html_generic.extract_article_markdown = original_extract

        self.assertIn("fallback:html_ok", article.quality.source_trail)
        self.assertIn("download:html_assets_saved_profile_body", article.quality.source_trail)

    def test_wiley_pdf_extraction_failure_returns_metadata_only_without_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1111/test",
                allow_html_fallback=False,
                allow_downloads=False,
                clients={
                    "wiley": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_payload=RawFulltextPayload(
                            provider="wiley",
                            source_url="https://example.test/wiley.pdf",
                            content_type="application/pdf",
                            body=short_pdf_bytes(),
                            metadata={"reason": "Downloaded full text from the configured Wiley TDM endpoint."},
                            needs_local_copy=True,
                        ),
                        article_factory=WileyClient(HttpTransport(), {}).to_article_model,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Wiley PDF Article",
                            "landing_page_url": "https://example.test/wiley",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_pdf_extract_fail", article.quality.source_trail)
        self.assertIn("fallback:html_disabled", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertTrue(any("Full text was not available" in warning for warning in article.quality.warnings))

    def test_token_budget_truncates_lower_priority_sections(self) -> None:
        article = sample_article()
        article.metadata.abstract = "Abstract text " * 20
        article.sections = [
            Section(heading="Introduction", level=2, kind="body", text="Intro " * 150),
            Section(heading="Methods", level=2, kind="body", text="Methods " * 150),
            Section(heading="Discussion", level=2, kind="body", text="Discussion " * 150),
        ]
        markdown = article.to_ai_markdown(max_tokens=450)

        self.assertIn("**Abstract.**", markdown)
        self.assertIn("## Introduction", markdown)
        self.assertNotIn("## Discussion", markdown)
        self.assertNotIn("Output truncated to satisfy token budget.", article.quality.warnings)

    def test_to_ai_markdown_omits_blank_frontmatter_and_does_not_mutate_warnings(self) -> None:
        article = ArticleModel(
            doi=None,
            source="crossref_meta",
            metadata=Metadata(),
            sections=[Section(heading="Introduction", level=2, kind="body", text="Intro " * 200)],
            references=[],
            assets=[],
            quality=Quality(has_fulltext=True, token_estimate=200, warnings=["Existing warning"]),
        )

        markdown = article.to_ai_markdown(max_tokens=60)

        self.assertNotIn('title: ""', markdown)
        self.assertNotIn("authors:", markdown)
        self.assertNotIn("journal:", markdown)
        self.assertNotIn("published:", markdown)
        self.assertIn("# Untitled Article", markdown)
        self.assertEqual(article.quality.warnings, ["Existing warning"])

    def test_to_ai_markdown_defaults_to_captions_only_without_supplementary_links(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure.", url="downloads/figure-1.png"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", url="downloads/supplement.csv"),
        ]

        markdown = article.to_ai_markdown()

        self.assertIn("## Figures", markdown)
        self.assertIn("- Figure 1: Overview figure.", markdown)
        self.assertNotIn("![Figure 1](downloads/figure-1.png)", markdown)
        self.assertNotIn("## Supplementary Materials", markdown)
        self.assertNotIn("[Supplementary Data](downloads/supplement.csv)", markdown)

    def test_to_ai_markdown_body_profile_renders_body_assets_only(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Body figure.", path="downloads/figure-1.png", section="body"),
            Asset(kind="figure", heading="Figure A1", caption="Appendix figure.", path="downloads/figure-a1.png", section="appendix"),
            Asset(kind="table", heading="Table 1", caption="Body table.", path="downloads/table-1.png", section="body"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", path="downloads/supplement.csv"),
        ]

        markdown = article.to_ai_markdown(asset_profile="body")

        self.assertIn("![Figure 1](downloads/figure-1.png)", markdown)
        self.assertIn("## Tables", markdown)
        self.assertIn("![Table 1](downloads/table-1.png)", markdown)
        self.assertNotIn("Figure A1", markdown)
        self.assertNotIn("## Supplementary Materials", markdown)

    def test_to_ai_markdown_full_text_defaults_to_all_references(self) -> None:
        article = sample_article()
        article.references = [
            Reference(raw="Reference 1"),
            Reference(raw="Reference 2"),
            Reference(raw="Reference 3"),
        ]

        markdown = article.to_ai_markdown()

        self.assertIn("## References (3 total, showing 3)", markdown)
        self.assertIn("- Reference 3", markdown)

    def test_to_ai_markdown_full_text_respects_explicit_include_refs(self) -> None:
        article = sample_article()
        article.references = [Reference(raw=f"Reference {index}") for index in range(1, 13)]

        markdown = article.to_ai_markdown(include_refs="top10")

        self.assertIn("## References (12 total, showing 10)", markdown)
        self.assertIn("- Reference 10", markdown)
        self.assertNotIn("- Reference 11", markdown)

    def test_to_ai_markdown_full_text_matches_large_budget_rendering(self) -> None:
        article = sample_article()
        article.references = [Reference(raw=f"Reference {index}") for index in range(1, 4)]
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure.", path="downloads/figure-1.png", section="body"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", path="downloads/supplement.csv"),
        ]

        full_text_markdown = article.to_ai_markdown(include_refs="all", asset_profile="all", max_tokens="full_text")
        large_budget_markdown = article.to_ai_markdown(include_refs="all", asset_profile="all", max_tokens=100000)

        self.assertEqual(full_text_markdown, large_budget_markdown)

    def test_to_ai_markdown_inline_figures_fall_back_to_captions_without_links(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure."),
        ]

        markdown = article.to_ai_markdown(include_figures="inline", max_tokens=600)

        self.assertIn("## Figures", markdown)
        self.assertIn("- Figure 1: Overview figure.", markdown)
        self.assertNotIn("![Figure 1]", markdown)

    def test_build_fetch_envelope_default_markdown_uses_captions_only_and_no_supplementary_links(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure.", url="downloads/figure-1.png"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", url="downloads/supplement.csv"),
        ]

        envelope = paper_fetch.build_fetch_envelope(article, modes={"article", "markdown"}, render=RenderOptions())

        assert envelope.markdown is not None
        self.assertIn("- Figure 1: Overview figure.", envelope.markdown)
        self.assertNotIn("![Figure 1](downloads/figure-1.png)", envelope.markdown)
        self.assertNotIn("[Supplementary Data](downloads/supplement.csv)", envelope.markdown)

    def test_article_from_markdown_preserves_code_fences_and_ascii_tables(self) -> None:
        article = article_from_markdown(
            source="html_generic",
            metadata={"title": "Structured Article"},
            doi="10.1000/test",
            markdown_text="\n".join(
                [
                    "# Structured Article",
                    "",
                    "## Methods",
                    "",
                    "```python",
                    "if  value:",
                    "    print('kept')",
                    "```",
                    "",
                    "| col_a | col_b |",
                    "| --- | --- |",
                    "| 1 | 2 |",
                ]
            ),
        )

        self.assertEqual(article.sections[0].heading, "Methods")
        self.assertIn("```python", article.sections[0].text)
        self.assertIn("    print('kept')", article.sections[0].text)
        self.assertIn("| col_a | col_b |", article.sections[0].text)


if __name__ == "__main__":
    unittest.main()
