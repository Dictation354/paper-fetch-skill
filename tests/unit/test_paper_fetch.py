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
from paper_fetch.http import HttpTransport
from paper_fetch.models import ArticleModel, FetchEnvelope, Metadata, Quality, RenderOptions, Section, article_from_markdown
from paper_fetch.providers.base import RawFulltextPayload
from paper_fetch.providers.wiley import WileyClient


class StubProvider:
    def __init__(self, metadata=None, raw_payload=None, raw_error=None, article=None, article_factory=None):
        self._metadata = metadata
        self._raw_payload = raw_payload
        self._raw_error = raw_error
        self._article = article
        self._article_factory = article_factory

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


class StubHtmlClient:
    def __init__(self, article=None, error=None):
        self.article = article
        self.error = error

    def fetch_article_model(self, landing_url, *, metadata=None, expected_doi=None):
        if self.error:
            raise self.error
        return self.article


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

    def test_fetch_metadata_records_not_configured_source_trail(self) -> None:
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
        self.assertIn("metadata:springer_not_configured", source_trail)
        self.assertIn("metadata:crossref_ok", source_trail)

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
