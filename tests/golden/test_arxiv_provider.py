from __future__ import annotations
from __future__ import annotations
from tests.support._paper_fetch_support import (
    RecordingTransport,
    http_response,
)
from tests.golden_criteria import (
    golden_criteria_asset,
)
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.arxiv import ArxivClient
from paper_fetch.providers import (
    _arxiv_assets,
    _arxiv_atom,
    _arxiv_html,
)
from paper_fetch.arxiv_id import canonical_arxiv_html_url, canonical_arxiv_pdf_url
from paper_fetch import service as paper_fetch
from tests.support.acquired_publisher_inputs import _record, _response
from pathlib import Path
import unittest
import tempfile
import tarfile
import io
from dataclasses import replace
from datetime import datetime
import json
import re
from types import SimpleNamespace
from unittest import mock
from xml.sax.saxutils import escape
from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.http import RequestErrorCategory
from paper_fetch.models import article_from_markdown
from paper_fetch.providers import (
    _arxiv_asset_strategy,
)
from paper_fetch.providers._html_section_markdown import render_container_markdown
from tests.golden_criteria import (
    golden_criteria_dir_for_doi,
    golden_criteria_sample_for_doi,
)
from tests.support._paper_fetch_support import (
    FixtureProvider,
)


PDF_FALLBACK_IDS = ("2006.11239v2", "1406.2661v1")
HTML_ROUTE_IDS = (
    "2605.06556v1",
    "2605.06598v1",
    "2605.06653v1",
    "2605.06659v1",
    "2605.06663v1",
    "2605.06665v1",
    "2605.06666v1",
    "2605.06667v1",
)
MARKDOWN_REVIEWED_FIXTURES = {
    "structure": "10.48550_arxiv.2605.06663v1",
    "table": "10.48550_arxiv.2605.06663v1",
    "formula": "10.48550_arxiv.2605.06653v1",
    "figure": "10.48550_arxiv.2605.06667v1",
    "references": "10.48550_arxiv.2605.06663v1",
    "pdf_fallback": "10.48550_arxiv.1406.2661v1",
}
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?"
    b"\x00\x05\xfe\x02\xfeA\xe2%\xb8\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _doi(arxiv_id: str) -> str:
    return f"10.48550/arxiv.{arxiv_id}"


def _fixture_dir(arxiv_id: str) -> Path:
    return golden_criteria_dir_for_doi(_doi(arxiv_id))


def _api_payload(arxiv_id: str) -> dict:
    return json.loads(
        golden_criteria_asset(_doi(arxiv_id), "api.json").read_text(encoding="utf-8")
    )


def _metadata(arxiv_id: str) -> dict:
    return dict(_api_payload(arxiv_id)["provider_metadata"])


def _fixture_html(arxiv_id: str) -> bytes:
    return golden_criteria_asset(_doi(arxiv_id), "original.html").read_bytes()


def _fixture_pdf(arxiv_id: str) -> bytes:
    return golden_criteria_asset(_doi(arxiv_id), "original.pdf").read_bytes()


def _source_tar(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def _atom_feed_from_raw_result(raw: dict) -> bytes:
    categories = "\n".join(
        f'    <category term="{escape(str(category))}" />'
        for category in raw.get("categories", [])
    )
    authors = "\n".join(
        f"    <author><name>{escape(str(author))}</name></author>"
        for author in raw.get("authors", [])
    )
    primary_category = escape(str(raw.get("primary_category") or ""))
    comment = (
        f"    <arxiv:comment>{escape(str(raw['comment']))}</arxiv:comment>\n"
        if raw.get("comment")
        else ""
    )
    journal_ref = (
        f"    <arxiv:journal_ref>{escape(str(raw['journal_ref']))}</arxiv:journal_ref>\n"
        if raw.get("journal_ref")
        else ""
    )
    doi = (
        f"    <arxiv:doi>{escape(str(raw['doi']))}</arxiv:doi>\n"
        if raw.get("doi")
        else ""
    )
    pdf_url = escape(str(raw.get("pdf_url") or ""))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>{escape(str(raw.get("entry_id") or ""))}</id>
    <updated>{escape(str(raw.get("updated") or ""))}</updated>
    <published>{escape(str(raw.get("published") or ""))}</published>
    <title>{escape(str(raw.get("title") or ""))}</title>
    <summary>{escape(str(raw.get("summary") or ""))}</summary>
{authors}
{comment}{journal_ref}{doi}    <arxiv:primary_category term="{primary_category}" />
{categories}
    <link href="{escape(str(raw.get("entry_id") or ""))}" rel="alternate" type="text/html" />
    <link title="pdf" href="{pdf_url}" rel="related" type="application/pdf" />
  </entry>
</feed>
""".encode()


def _atom_feed_from_fixture(arxiv_id: str) -> bytes:
    return _atom_feed_from_raw_result(_api_payload(arxiv_id)["raw_result"])


def _api_atom_response(
    arxiv_id: str, *, body: bytes | None = None
) -> dict[str, object]:
    return http_response(
        _arxiv_atom.ARXIV_API_URL,
        body if body is not None else _atom_feed_from_fixture(arxiv_id),
        "application/atom+xml",
    )


# Official arXiv page fragments retrieved 2026-09-08; retained DOM and full
# ancillary lists (not the source archives or the 103 binary attachments).
ARXIV_ANCILLARY_PAGES = {
    arxiv_id: tuple(
        golden_criteria_asset(_doi(arxiv_id), name).read_text(encoding="utf-8")
        for name in ("abstract-excerpt.html", "ancillary-excerpt.html")
    )
    for arxiv_id in ("0811.2625v2", "2606.00587v2", "0905.2326v2")
}


class ReplayArxivResult:
    def __init__(self, raw: dict) -> None:
        self.entry_id = raw["entry_id"]
        self.updated = datetime.fromisoformat(raw["updated"])
        self.published = datetime.fromisoformat(raw["published"])
        self.title = raw["title"]
        self.authors = [SimpleNamespace(name=name) for name in raw["authors"]]
        self.summary = raw["summary"]
        self.comment = raw.get("comment")
        self.journal_ref = raw.get("journal_ref")
        self.doi = raw.get("doi")
        self.primary_category = raw["primary_category"]
        self.categories = list(raw["categories"])
        self.pdf_url = raw["pdf_url"]
        self._short_id = raw["short_id"]

    def get_short_id(self) -> str:
        return self._short_id


class ReplayArxivApiClient:
    def __init__(self, payloads: dict[str, dict]) -> None:
        self.payloads = payloads
        self.queries: list[list[str]] = []

    def results(self, search):
        ids = list(search.id_list)
        self.queries.append(ids)
        for arxiv_id in ids:
            payload = self.payloads.get(arxiv_id)
            if payload is not None:
                yield ReplayArxivResult(payload["raw_result"])


class FailingArxivApiClient:
    def __init__(self, message: str = "temporary API EOF") -> None:
        self.message = message
        self.queries: list[list[str]] = []

    def results(self, search):
        ids = list(search.id_list)
        self.queries.append(ids)
        raise RuntimeError(self.message)
        yield  # pragma: no cover


def _html_transport(
    arxiv_id: str,
    *,
    html_body: bytes | None = None,
    html_content_type: str = "text/html; charset=utf-8",
    api_body: bytes | None = None,
    extra_responses: dict[tuple[str, str], object] | None = None,
) -> RecordingTransport:
    html_url = canonical_arxiv_html_url(arxiv_id)
    responses: dict[tuple[str, str], object] = {
        ("GET", html_url): http_response(
            html_url,
            html_body if html_body is not None else _fixture_html(arxiv_id),
            html_content_type,
        ),
        ("GET", _arxiv_atom.ARXIV_API_URL): _api_atom_response(arxiv_id, body=api_body),
    }
    responses.update(extra_responses or {})
    return RecordingTransport(responses)


def _html_then_pdf_transport(
    arxiv_id: str,
    *,
    html_response: object | None = None,
    html_body: bytes | None = None,
    html_content_type: str = "text/html; charset=utf-8",
) -> RecordingTransport:
    metadata = _metadata(arxiv_id)
    html_url = canonical_arxiv_html_url(arxiv_id)
    pdf_url = metadata.get("pdf_url") or canonical_arxiv_pdf_url(arxiv_id)
    return RecordingTransport(
        {
            ("GET", html_url): (
                html_response
                if html_response is not None
                else http_response(
                    html_url,
                    html_body if html_body is not None else b"not an html document",
                    html_content_type,
                )
            ),
            ("GET", pdf_url): http_response(
                pdf_url, _fixture_pdf(arxiv_id), "application/pdf"
            ),
            ("GET", _arxiv_atom.ARXIV_API_URL): _api_atom_response(arxiv_id),
        }
    )


def _html_404_then_pdf_transport(arxiv_id: str) -> RecordingTransport:
    html_url = canonical_arxiv_html_url(arxiv_id)
    return _html_then_pdf_transport(
        arxiv_id,
        html_response=ProviderFailure(
            "no_result",
            f"HTTP 404 for {html_url}",
            source_trail=[],
        ),
    )


def _downloaded_html_assets(
    raw_payload, *, limit: int | None = None
) -> list[dict[str, str]]:
    downloaded_assets: list[dict[str, str]] = []
    source_assets = list(raw_payload.content.extracted_assets)
    if limit is not None:
        source_assets = source_assets[:limit]
    for asset in source_assets:
        downloaded = dict(asset)
        downloaded["path"] = f"body_assets/{str(asset['url']).rsplit('/', 1)[-1]}"
        downloaded["download_url"] = str(asset["url"])
        downloaded_assets.append(downloaded)
    return downloaded_assets


def _multiline_plain_prose_blocks(markdown_text: str) -> list[str]:
    multiline_blocks: list[str] = []
    for block in re.split(r"\n\s*\n", markdown_text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) <= 1:
            continue
        if any(
            line.startswith(("##", "#", "|", "$", "```", "~~~", "!["))
            or re.match(r"^(?:[-*+]|\d+[.)])\s+", line)
            for line in lines
        ):
            continue
        multiline_blocks.append(block)
    return multiline_blocks


class ArxivProviderTests(unittest.TestCase):
    def test_fetch_metadata_uses_replayed_arxiv_api_result(self) -> None:
        api_client = ReplayArxivApiClient(
            {"2605.06663v1": _api_payload("2605.06663v1")}
        )
        client = ArxivClient(RecordingTransport({}), {}, api_client=api_client)

        metadata = client.fetch_metadata({"doi": _doi("2605.06663v1")})

        self.assertEqual(metadata["provider"], "arxiv")
        self.assertEqual(metadata["official_provider"], True)
        self.assertEqual(metadata["doi"], _doi("2605.06663v1"))
        self.assertEqual(metadata["arxiv_id"], "2605.06663v1")
        self.assertEqual(
            metadata["landing_page_url"], "https://arxiv.org/abs/2605.06663v1"
        )
        self.assertEqual(metadata["html_url"], "https://arxiv.org/html/2605.06663v1")
        self.assertEqual(metadata["pdf_url"], "https://arxiv.org/pdf/2605.06663v1")
        self.assertNotIn("source_url", metadata)
        self.assertEqual(
            [link["url"] for link in metadata["fulltext_links"]],
            [
                "https://arxiv.org/html/2605.06663v1",
                "https://arxiv.org/pdf/2605.06663v1",
            ],
        )
        self.assertEqual(api_client.queries, [["2605.06663v1"]])

    def test_fetch_metadata_rejects_api_result_for_different_arxiv_id(self) -> None:
        api_client = ReplayArxivApiClient(
            {"2605.06663v1": _api_payload("2605.06665v1")}
        )
        client = ArxivClient(RecordingTransport({}), {}, api_client=api_client)

        with self.assertRaises(ProviderFailure) as raised:
            client.fetch_metadata({"arxiv_id": "2605.06663v1"})

        self.assertEqual(raised.exception.code, "identity_mismatch")

    def test_arxiv_route_fixtures_have_expected_html_or_pdf_assets(self) -> None:
        for arxiv_id in HTML_ROUTE_IDS:
            with self.subTest(arxiv_id=arxiv_id):
                self.assertTrue((_fixture_dir(arxiv_id) / "api.json").is_file())
                self.assertTrue((_fixture_dir(arxiv_id) / "original.html").is_file())
                self.assertFalse((_fixture_dir(arxiv_id) / "original.pdf").exists())

        for arxiv_id in PDF_FALLBACK_IDS:
            with self.subTest(arxiv_id=arxiv_id):
                self.assertTrue((_fixture_dir(arxiv_id) / "api.json").is_file())
                self.assertTrue((_fixture_dir(arxiv_id) / "original.pdf").is_file())
                self.assertFalse((_fixture_dir(arxiv_id) / "original.html").exists())

        for arxiv_id in HTML_ROUTE_IDS:
            with self.subTest(arxiv_id=arxiv_id):
                sample = golden_criteria_sample_for_doi(_doi(arxiv_id))
                self.assertEqual(sample["route_kind"], "html")
                assets = set(sample["assets"])
                self.assertTrue({"api.json", "original.html"} <= assets)
                # Exact contracts replay original HTML against expected.json.
                # A derived Markdown snapshot is optional, not source evidence.
                if "expected.json" in assets:
                    self.assertTrue(
                        (_fixture_dir(arxiv_id) / "expected.json").is_file()
                    )
        for arxiv_id in PDF_FALLBACK_IDS:
            with self.subTest(arxiv_id=arxiv_id):
                sample = golden_criteria_sample_for_doi(_doi(arxiv_id))
                self.assertEqual(sample["route_kind"], "pdf_fallback")
                assets = set(sample["assets"])
                self.assertTrue({"api.json", "original.pdf"} <= assets)
                # Exact contracts replay original HTML against expected.json.
                # A derived Markdown snapshot is optional, not source evidence.
                if "expected.json" in assets:
                    self.assertTrue(
                        (_fixture_dir(arxiv_id) / "expected.json").is_file()
                    )

    def test_html_success_requests_official_html_then_default_api_enrichment(
        self,
    ) -> None:
        arxiv_id = "2605.06663v1"
        metadata = _metadata(arxiv_id)
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        article = client.to_article_model(metadata, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(article.source, "arxiv_html")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:arxiv_html_ok", article.quality.source_trail)
        self.assertNotIn("source_url", raw_payload.content.merged_metadata)
        self.assertEqual(raw_payload.warnings, [])
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id), _arxiv_atom.ARXIV_API_URL],
        )
        self.assertEqual(
            transport.calls[-1]["query"],
            {"id_list": arxiv_id, "max_results": "1"},
        )

    def test_html_404_directly_requests_pdf_fallback(self) -> None:
        for arxiv_id in PDF_FALLBACK_IDS:
            with self.subTest(arxiv_id=arxiv_id):
                metadata = _metadata(arxiv_id)
                transport = _html_404_then_pdf_transport(arxiv_id)
                client = ArxivClient(transport, {})

                raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
                article = client.to_article_model(metadata, raw_payload)

                self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
                self.assertEqual(article.source, "arxiv_pdf")
                self.assertEqual(article.quality.content_kind, "fulltext")
                self.assertIn("fulltext:arxiv_html_fail", article.quality.source_trail)
                self.assertIn(
                    "fulltext:arxiv_pdf_fallback_ok", article.quality.source_trail
                )
                self.assertFalse(
                    any("latex" in item.lower() for item in raw_payload.warnings)
                )
                self.assertEqual(
                    [call["url"] for call in transport.calls],
                    [
                        metadata["html_url"],
                        metadata["pdf_url"],
                        _arxiv_atom.ARXIV_API_URL,
                    ],
                )
                self.assertIn("html:", raw_payload.content.html_failure_message)

                result = client.fetch_result(
                    metadata["doi"], metadata, None, asset_profile="body"
                )
                self.assertTrue(result.artifacts.text_only)
                self.assertFalse(result.artifacts.allow_related_assets)
                self.assertIn(
                    "download:arxiv_assets_skipped_text_only",
                    [event.marker() for event in result.artifacts.skip_trace],
                )

    def test_non_html_candidate_directly_requests_pdf_fallback(self) -> None:
        arxiv_id = "2006.11239v2"
        metadata = _metadata(arxiv_id)
        transport = _html_then_pdf_transport(
            arxiv_id,
            html_body=b"not an html document",
            html_content_type="application/octet-stream",
        )
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        article = client.to_article_model(metadata, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(article.source, "arxiv_pdf")
        self.assertIn("fulltext:arxiv_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:arxiv_pdf_fallback_ok", article.quality.source_trail)
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [metadata["html_url"], metadata["pdf_url"], _arxiv_atom.ARXIV_API_URL],
        )

    def test_insufficient_html_body_directly_requests_pdf_fallback(self) -> None:
        arxiv_id = "2006.11239v2"
        metadata = _metadata(arxiv_id)
        short_html = (
            b"<html><body><article class='ltx_document'><h2>Introduction</h2>"
            b"<p>Too short.</p></article></body></html>"
        )
        transport = _html_then_pdf_transport(arxiv_id, html_body=short_html)
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        article = client.to_article_model(metadata, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(article.source, "arxiv_pdf")
        self.assertTrue(
            any(
                "did not expose enough body text" in item
                for item in raw_payload.warnings
            )
        )
        self.assertIn("fulltext:arxiv_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:arxiv_pdf_fallback_ok", article.quality.source_trail)
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [metadata["html_url"], metadata["pdf_url"], _arxiv_atom.ARXIV_API_URL],
        )

    def test_polluted_html_body_directly_requests_pdf_fallback(self) -> None:
        arxiv_id = "2006.11239v2"
        metadata = _metadata(arxiv_id)
        repeated_body = " ".join(
            ["This synthetic body has enough words for the full text quality gate."]
            * 100
        )
        polluted_html = f"""
        <html><body><article class="ltx_document">
          <section><h2>Introduction</h2>
          <p>An error in the conversion from LaTeX to XML has occurred here.</p>
          <p>{repeated_body}</p></section>
        </article></body></html>
        """.encode()
        transport = _html_then_pdf_transport(arxiv_id, html_body=polluted_html)
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        article = client.to_article_model(metadata, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(article.source, "arxiv_pdf")
        self.assertTrue(
            any(
                "not classified as usable full text" in item
                for item in raw_payload.warnings
            )
        )
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [metadata["html_url"], metadata["pdf_url"], _arxiv_atom.ARXIV_API_URL],
        )

    def test_api_transient_failure_with_arxiv_doi_uses_derived_html_url(self) -> None:
        arxiv_id = "2605.06663v1"
        api_client = FailingArxivApiClient("temporary SSL EOF")
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {}, api_client=api_client)

        raw_payload = client.fetch_raw_fulltext(_doi(arxiv_id), {})

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(raw_payload.content.merged_metadata["arxiv_id"], arxiv_id)
        self.assertEqual(raw_payload.content.merged_metadata["provider"], "arxiv")
        self.assertEqual(
            raw_payload.content.merged_metadata["html_url"],
            canonical_arxiv_html_url(arxiv_id),
        )
        self.assertNotIn("source_url", raw_payload.content.merged_metadata)
        self.assertTrue(
            any(
                "arXiv API metadata retrieval failed" in warning
                for warning in raw_payload.warnings
            )
        )
        self.assertEqual(api_client.queries, [[arxiv_id]])
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id)],
        )

    def test_api_failure_uses_html_frontmatter_metadata_without_untitled_article(
        self,
    ) -> None:
        arxiv_id = "2605.06663v1"
        api_client = FailingArxivApiClient("HTTP 429: Too Many Requests")
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {}, api_client=api_client)

        raw_payload = client.fetch_raw_fulltext(_doi(arxiv_id), {})
        article = client.to_article_model({}, raw_payload)
        markdown = article.to_ai_markdown(asset_profile="none", max_tokens="full_text")

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(article.source, "arxiv_html")
        self.assertEqual(
            article.metadata.title,
            "Emo: Pretraining Mixture of Experts for Emergent Modularity",
        )
        self.assertEqual(
            article.metadata.authors[:3], ["Ryan Wang", "Akshita Bhagia", "Sewon Min"]
        )
        self.assertNotIn("# Untitled Article", markdown)
        self.assertTrue(
            any(
                "arXiv API metadata retrieval failed" in warning
                for warning in raw_payload.warnings
            )
        )
        self.assertEqual(api_client.queries, [[arxiv_id]])
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id)],
        )

    def test_api_metadata_success_takes_priority_over_html_frontmatter_metadata(
        self,
    ) -> None:
        arxiv_id = "2605.06663v1"
        payload = json.loads(json.dumps(_api_payload(arxiv_id)))
        payload["raw_result"]["title"] = "API Preferred Title"
        payload["raw_result"]["authors"] = ["API Author", "HTML Merge Author"]
        api_client = ReplayArxivApiClient({arxiv_id: payload})
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {}, api_client=api_client)

        raw_payload = client.fetch_raw_fulltext(_doi(arxiv_id), {})
        article = client.to_article_model({}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(article.metadata.title, "API Preferred Title")
        self.assertEqual(
            article.metadata.authors, ["Ryan Wang", "Akshita Bhagia", "Sewon Min"]
        )
        self.assertNotEqual(
            raw_payload.content.merged_metadata["title"],
            "Emo: Pretraining Mixture of Experts for Emergent Modularity",
        )
        self.assertEqual(api_client.queries, [[arxiv_id]])

    def test_default_api_enrichment_fills_authors_when_html_has_no_author_dom(
        self,
    ) -> None:
        arxiv_id = "2605.05255v1"
        repeated_body = " ".join(
            [
                "This synthetic arXiv article describes storm-scale machine learning experiments, reproducible evaluation protocols, and measured forecasting outcomes."
                for _ in range(80)
            ]
        )
        html_body = f"""
        <html><body><article class="ltx_document">
          <h1 class="ltx_title ltx_title_document">HTML Title Without Author Nodes</h1>
          <div id="abstract" class="ltx_abstract">
            <h6 class="ltx_title ltx_title_abstract">Abstract.</h6>
            <p>This abstract intentionally has no author-bearing DOM nearby.</p>
          </div>
          <section id="S1" class="ltx_section">
            <h2 class="ltx_title ltx_title_section">1 Introduction</h2>
            <p>{repeated_body}</p>
          </section>
          <section id="S2" class="ltx_section">
            <h2 class="ltx_title ltx_title_section">2 Experiments</h2>
            <p>{repeated_body}</p>
          </section>
          <section id="bib" class="ltx_bibliography">
            <h2 class="ltx_title ltx_title_bibliography">References</h2>
            <ul><li class="ltx_bibitem">Example Author. Example reference. 2026.</li></ul>
          </section>
        </article></body></html>
        """.encode()
        api_raw = {
            "entry_id": f"http://arxiv.org/abs/{arxiv_id}",
            "updated": "2026-05-08T12:00:00+00:00",
            "published": "2026-05-08T12:00:00+00:00",
            "title": "API Title With Complete Authors",
            "authors": ["Stuart Edris", "Amy McGovern", "Jason Hickey"],
            "summary": "API abstract for the synthetic arXiv author enrichment replay.",
            "comment": None,
            "journal_ref": None,
            "doi": None,
            "primary_category": "cs.LG",
            "categories": ["cs.LG", "physics.ao-ph"],
            "pdf_url": canonical_arxiv_pdf_url(arxiv_id),
            "short_id": arxiv_id,
        }
        transport = _html_transport(
            arxiv_id,
            html_body=html_body,
            api_body=_atom_feed_from_raw_result(api_raw),
        )
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(_doi(arxiv_id), {})
        article = client.to_article_model({}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(
            article.metadata.authors,
            ["Stuart Edris", "Amy McGovern", "Jason Hickey"],
        )
        self.assertEqual(article.metadata.title, "API Title With Complete Authors")
        self.assertEqual(raw_payload.warnings, [])
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id), _arxiv_atom.ARXIV_API_URL],
        )

    def test_pdf_without_metadata_rejected_before_api_enrichment(
        self,
    ) -> None:
        arxiv_id = "2006.11239v2"
        api_client = FailingArxivApiClient("temporary export API timeout")
        transport = _html_404_then_pdf_transport(arxiv_id)
        client = ArxivClient(transport, {}, api_client=api_client)

        with self.assertRaises(ProviderFailure) as failure:
            client.fetch_raw_fulltext(_doi(arxiv_id), {})
        self.assertIn(
            "does not establish the requested article DOI or title",
            str(failure.exception),
        )
        self.assertEqual(api_client.queries, [])
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id), canonical_arxiv_pdf_url(arxiv_id)],
        )

    def test_internal_atom_parse_failure_keeps_html_fulltext_payload(self) -> None:
        arxiv_id = "2605.06663v1"
        transport = _html_transport(
            arxiv_id,
            extra_responses={
                ("GET", _arxiv_atom.ARXIV_API_URL): http_response(
                    _arxiv_atom.ARXIV_API_URL,
                    b"<feed",
                    "application/atom+xml",
                )
            },
        )
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(_doi(arxiv_id), {})

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(raw_payload.content.merged_metadata["arxiv_id"], arxiv_id)
        self.assertTrue(
            any(
                "arXiv API metadata retrieval failed" in warning
                for warning in raw_payload.warnings
            )
        )
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id), _arxiv_atom.ARXIV_API_URL],
        )

    def test_html_route_extracts_sections_abstract_formulas_and_citations_from_fixture(
        self,
    ) -> None:
        arxiv_id = "2605.06663v1"
        metadata = _metadata(arxiv_id)
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        article = client.to_article_model(metadata, raw_payload)
        markdown = raw_payload.content.markdown_text

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(raw_payload.source_url, canonical_arxiv_html_url(arxiv_id))
        self.assertEqual(article.source, "arxiv_html")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:arxiv_html_ok", article.quality.source_trail)
        self.assertIn("## Abstract", markdown)
        self.assertIn("## 1 Introduction", markdown)
        self.assertIn("## References", markdown)
        self.assertIn("$$", markdown)
        self.assertIn("@@PF_CITE", markdown)
        self.assertGreaterEqual(len(article.sections), 5)
        self.assertGreater(len(article.references), 0)
        self.assertGreater(len(raw_payload.content.extracted_assets), 0)
        self.assertEqual(
            raw_payload.content.merged_metadata["references"][0]["year"], "2020"
        )
        self.assertIn(
            "PIQA", raw_payload.content.merged_metadata["references"][0]["raw"]
        )
        self.assertTrue(
            raw_payload.content.extracted_assets[0]["url"].startswith(
                "https://arxiv.org/html/"
            )
        )
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id), _arxiv_atom.ARXIV_API_URL],
        )
        diagnostics = raw_payload.content.diagnostics["extraction"]
        self.assertEqual(diagnostics["parser"], "latexml_html")
        self.assertGreaterEqual(diagnostics["word_count"], 500)
        self.assertGreaterEqual(diagnostics["formula_block_count"], 1)
        self.assertEqual(diagnostics["reference_count"], len(article.references))
        self.assertEqual(
            diagnostics["asset_count"], len(raw_payload.content.extracted_assets)
        )
        self.assertGreaterEqual(diagnostics["table_block_rendered_count"], 1)
        self.assertEqual(diagnostics["semantic_block_loss_count"], 0)

    def test_html_route_preserves_tables_and_cleans_error_and_alt_noise(self) -> None:
        table_cases = {
            "2605.06598v1": (
                "**Table 1.** Parameter values used for analysis and simulations.",
                "| $c_{1}=0.002$",
            ),
            "2605.06667v1": (
                "**Table 1.** Joint camera and character control.",
                "| Uni3C",
            ),
        }
        for arxiv_id, expected_fragments in table_cases.items():
            with self.subTest(arxiv_id=arxiv_id):
                extraction = _arxiv_html._extract_arxiv_html_markdown(
                    _fixture_html(arxiv_id).decode("utf-8"),
                    canonical_arxiv_html_url(arxiv_id),
                    metadata=_metadata(arxiv_id),
                )
                for expected in expected_fragments:
                    self.assertIn(expected, extraction.markdown_text)
                self.assertNotIn("Refer to caption", extraction.markdown_text)
                diagnostics = extraction.diagnostics["extraction"]
                self.assertGreaterEqual(diagnostics["table_block_rendered_count"], 1)
                self.assertEqual(diagnostics["semantic_block_loss_count"], 0)

        error_extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html("2605.06653v1").decode("utf-8"),
            canonical_arxiv_html_url("2605.06653v1"),
            metadata=_metadata("2605.06653v1"),
        )
        self.assertNotIn(r"\addsec", error_extraction.markdown_text)
        self.assertGreaterEqual(
            error_extraction.diagnostics["extraction"]["latexml_error_nodes_removed"], 1
        )
        self.assertEqual(
            error_extraction.diagnostics["extraction"]["reference_count"], 0
        )

    def test_html_route_normalizes_math_without_duplicate_fallback_text(self) -> None:
        for arxiv_id in HTML_ROUTE_IDS:
            with self.subTest(arxiv_id=arxiv_id):
                extraction = _arxiv_html._extract_arxiv_html_markdown(
                    _fixture_html(arxiv_id).decode("utf-8"),
                    canonical_arxiv_html_url(arxiv_id),
                    metadata=_metadata(arxiv_id),
                )
                self.assertNotIn(r"\hspace{0pt}", extraction.markdown_text)
                self.assertGreater(
                    extraction.diagnostics["extraction"]["math_nodes_normalized"], 0
                )

        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html("2605.06667v1").decode("utf-8"),
            canonical_arxiv_html_url("2605.06667v1"),
            metadata=_metadata("2605.06667v1"),
        )
        all_asset_captions = "\n".join(
            str(asset.get("caption") or "") for asset in extraction.extracted_assets
        )
        self.assertIn("$N_{D}$", extraction.markdown_text)
        self.assertIn("$N_{D}$", all_asset_captions)
        self.assertNotIn("N D N_{D}", extraction.markdown_text)
        self.assertNotIn("N D N_{D}", all_asset_captions)

    def test_html_route_renders_ordered_lists_as_markdown_numbers(self) -> None:
        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html("2605.06556v1").decode("utf-8"),
            canonical_arxiv_html_url("2605.06556v1"),
            metadata=_metadata("2605.06556v1"),
        )

        self.assertIn("1. Assign each state zero seats", extraction.markdown_text)
        self.assertIn(
            "2. Calculate each state’s priority value", extraction.markdown_text
        )
        self.assertNotIn("- 1.\nAssign each state", extraction.markdown_text)
        self.assertNotIn("- 1. Assign each state", extraction.markdown_text)

    def test_html_route_strips_visible_unordered_list_markers_once(self) -> None:
        for arxiv_id in ("2605.06556v1", "2605.06665v1", "2605.06667v1"):
            with self.subTest(arxiv_id=arxiv_id):
                extraction = _arxiv_html._extract_arxiv_html_markdown(
                    _fixture_html(arxiv_id).decode("utf-8"),
                    canonical_arxiv_html_url(arxiv_id),
                    metadata=_metadata(arxiv_id),
                )
                self.assertNotIn("- •", extraction.markdown_text)

        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html("2605.06667v1").decode("utf-8"),
            canonical_arxiv_html_url("2605.06667v1"),
            metadata=_metadata("2605.06667v1"),
        )
        self.assertIn("- Zero-shot joint control.", extraction.markdown_text)

    def test_html_route_inlines_single_official_html_figure_without_trailing_figures(
        self,
    ) -> None:
        arxiv_id = "2605.06556v1"
        metadata = _metadata(arxiv_id)
        client = ArxivClient(_html_transport(arxiv_id), {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        downloaded_assets = _downloaded_html_assets(raw_payload)

        article = client.to_article_model(
            metadata, raw_payload, downloaded_assets=downloaded_assets
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
        diagnostics = raw_payload.content.diagnostics["extraction"]

        self.assertIn("![Figure 1](body_assets/fig_1_tau_picture.png)", markdown)
        self.assertLess(
            markdown.index("![Figure 1](body_assets/fig_1_tau_picture.png)"),
            markdown.index("**Figure 1.**"),
        )
        self.assertNotIn("\n## Figures\n", markdown)
        self.assertNotIn("https://arxiv.org/html/", markdown)
        self.assertEqual(
            diagnostics["inline_figure_image_count"],
            len(raw_payload.content.extracted_assets),
        )
        self.assertEqual(diagnostics["inline_figure_asset_miss_count"], 0)

    def test_html_route_uses_dom_id_labels_for_captionless_panel_figures(self) -> None:
        arxiv_id = "2605.06598v1"
        metadata = _metadata(arxiv_id)
        client = ArxivClient(_html_transport(arxiv_id), {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        downloaded_assets = _downloaded_html_assets(raw_payload)

        article = client.to_article_model(
            metadata, raw_payload, downloaded_assets=downloaded_assets
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
        asset_captions = "\n".join(
            str(asset.get("caption") or "")
            for asset in raw_payload.content.extracted_assets
        )
        diagnostics = raw_payload.content.diagnostics["extraction"]

        self.assertNotIn("\n## Figures\n", markdown)
        self.assertIn("![Figure 2.2](body_assets/gc0oo4.png)", markdown)
        self.assertLess(
            markdown.index("![Figure 2.2](body_assets/gc0oo4.png)"),
            markdown.index("**Figure 2.** Phase portraits projected"),
        )
        self.assertIn(
            "Figure 2.2",
            [asset.get("heading") for asset in raw_payload.content.extracted_assets],
        )
        self.assertNotIn("Refer to caption", markdown)
        self.assertNotIn("Refer to caption", asset_captions)
        self.assertEqual(
            diagnostics["inline_figure_asset_match_count"],
            len(raw_payload.content.extracted_assets),
        )
        self.assertEqual(diagnostics["inline_figure_asset_miss_count"], 0)

    def test_html_route_extracts_multi_image_multi_caption_figures(self) -> None:
        arxiv_id = "2605.06667v1"
        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html(arxiv_id).decode("utf-8"),
            canonical_arxiv_html_url(arxiv_id),
            metadata=_metadata(arxiv_id),
        )
        assets_by_basename = {
            str(asset.get("url") or "").rsplit("/", 1)[-1]: asset
            for asset in extraction.extracted_assets
        }

        self.assertEqual(assets_by_basename["x8.png"]["heading"], "Figure 9")
        self.assertEqual(assets_by_basename["x9.png"]["heading"], "Figure 10")
        self.assertEqual(
            assets_by_basename["diff_scenes_1.jpg"]["heading"], "Figure 11"
        )
        self.assertEqual(
            assets_by_basename["diff_scenes_2.jpg"]["heading"], "Figure 12"
        )
        self.assertEqual(assets_by_basename["x10.png"]["heading"], "Figure 13")
        self.assertIn("**Figure 10.** Different cameras.", extraction.markdown_text)
        self.assertIn(
            "**Figure 12.** Different scenes and different cameras.",
            extraction.markdown_text,
        )
        self.assertIn(
            "**Figure 13.** Multi-character results.", extraction.markdown_text
        )

    def test_html_route_keeps_all_images_from_shared_caption_figures(self) -> None:
        arxiv_id = "2605.06665v1"
        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html(arxiv_id).decode("utf-8"),
            canonical_arxiv_html_url(arxiv_id),
            metadata=_metadata(arxiv_id),
        )
        basenames = {
            str(asset.get("url") or "").rsplit("/", 1)[-1]
            for asset in extraction.extracted_assets
        }

        self.assertIn("x2.png", basenames)
        self.assertIn("x3.png", basenames)
        self.assertEqual(
            [
                asset.get("heading")
                for asset in extraction.extracted_assets
                if str(asset.get("url") or "").endswith(("x2.png", "x3.png"))
            ],
            ["Figure 2", "Figure 2"],
        )

    def test_html_route_inlines_all_images_from_shared_caption_figures_once(
        self,
    ) -> None:
        arxiv_id = "2605.06665v1"
        metadata = _metadata(arxiv_id)
        client = ArxivClient(_html_transport(arxiv_id), {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        downloaded_assets = _downloaded_html_assets(raw_payload)

        article = client.to_article_model(
            metadata, raw_payload, downloaded_assets=downloaded_assets
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
        caption = "**Figure 2.** Efficiency and granularity sweeps for UniPool."
        diagnostics = raw_payload.content.diagnostics["extraction"]

        self.assertIn("![Figure 2](body_assets/x2.png)", markdown)
        self.assertIn("![Figure 2](body_assets/x3.png)", markdown)
        self.assertEqual(markdown.count(caption), 1)
        self.assertLess(
            markdown.index("![Figure 2](body_assets/x2.png)"), markdown.index(caption)
        )
        self.assertLess(
            markdown.index("![Figure 2](body_assets/x3.png)"), markdown.index(caption)
        )
        self.assertNotRegex(markdown, r"!\[[^\]]*Efficiency and granularity")
        self.assertNotIn("\n## Figures\n", markdown)
        self.assertEqual(
            diagnostics["inline_figure_asset_match_count"],
            len(raw_payload.content.extracted_assets),
        )
        self.assertEqual(diagnostics["inline_figure_asset_miss_count"], 0)

    def test_html_route_unmatched_figure_asset_stays_caption_only_and_can_append_fallback(
        self,
    ) -> None:
        soup = _arxiv_html.BeautifulSoup(
            """
            <article class="ltx_document">
              <figure id="S1.F1" class="ltx_figure">
                <figcaption>Figure 1. Caption only.</figcaption>
              </figure>
            </article>
            """,
            "html.parser",
        )
        article_node = soup.article
        asset = {
            "kind": "figure",
            "heading": "Figure 9",
            "caption": "Fallback figure.",
            "url": "https://arxiv.org/html/2605.06663v1/missing.png",
            "dom_id": "S1.F9",
            "image_id": "S1.F9.g1",
            "asset_order": "0",
            "path": "body_assets/missing.png",
            "download_url": "https://arxiv.org/html/2605.06663v1/missing.png",
            "section": "body",
        }

        diagnostics = _arxiv_assets._annotate_arxiv_inline_figure_images(
            article_node,
            [asset],
            canonical_arxiv_html_url("2605.06663v1"),
        )
        lines: list[str] = []
        render_container_markdown(
            article_node, lines, level=2, section_content_selectors=()
        )
        markdown = "\n".join(lines)
        rendered = article_from_markdown(
            source="arxiv_html",
            metadata=_metadata("2605.06663v1"),
            doi=_doi("2605.06663v1"),
            markdown_text=markdown,
            assets=[asset],
        ).to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertEqual(diagnostics["inline_figure_asset_match_count"], 0)
        self.assertEqual(diagnostics["inline_figure_asset_miss_count"], 1)
        self.assertIn("**Figure 1.** Caption only.", markdown)
        self.assertNotIn("![Figure 9]", markdown)
        self.assertIn("\n## Figures\n", rendered)
        self.assertIn("![Figure 9](body_assets/missing.png)", rendered)

    def test_html_route_normalizes_footnotes_tables_and_image_alt_noise(self) -> None:
        arxiv_id = "2605.06665v1"
        metadata = _metadata(arxiv_id)
        client = ArxivClient(_html_transport(arxiv_id), {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        downloaded_assets = _downloaded_html_assets(raw_payload)

        article = client.to_article_model(
            metadata, raw_payload, downloaded_assets=downloaded_assets
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
        image_alts = [
            match.group(1)
            for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", markdown)
        ]

        self.assertNotIn("****", raw_payload.content.markdown_text)
        self.assertNotIn("Column 1", raw_payload.content.markdown_text)
        self.assertNotIn("Column 2", raw_payload.content.markdown_text)
        self.assertNotIn("<sup>1</sup><sup>1</sup>1", raw_payload.content.markdown_text)
        self.assertIn(
            "<sup>1</sup> Appendix Table 6 reports", raw_payload.content.markdown_text
        )
        self.assertIn(
            "Main scales (default 8E / top-1 MoE) |       |",
            raw_payload.content.markdown_text,
        )
        self.assertNotIn(
            "Main scales (default 8E / top-1 MoE) | Main scales",
            raw_payload.content.markdown_text,
        )
        self.assertTrue(image_alts)
        self.assertTrue(all("$" not in alt for alt in image_alts))
        self.assertTrue(all(alt != "Figure" for alt in image_alts))
        self.assertTrue(all(len(alt) <= 40 for alt in image_alts))
        self.assertNotIn("https://arxiv.org/html/", markdown)
        self.assertNotIn("Refer to caption", markdown)

    def test_html_route_omits_bare_table_heading_for_unnumbered_tables(self) -> None:
        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html("2605.06556v1").decode("utf-8"),
            canonical_arxiv_html_url("2605.06556v1"),
            metadata=_metadata("2605.06556v1"),
        )

        self.assertNotIn("**Table**", extraction.markdown_text)
        self.assertNotIn("****", extraction.markdown_text)
        self.assertIn("| Method", extraction.markdown_text)
        self.assertIn(
            "**Table 1.** Approximate probabilities", extraction.markdown_text
        )

    def test_html_route_lifts_cross_column_table_titles_and_keeps_pipe_tables_valid(
        self,
    ) -> None:
        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html("2605.06556v1").decode("utf-8"),
            canonical_arxiv_html_url("2605.06556v1"),
            metadata=_metadata("2605.06556v1"),
        )
        markdown = extraction.markdown_text

        self.assertIn(
            r"Probability of Quota Violations Caused by Nonzero Allocation with $(1,x,y)$ uniform on $\{1<x<y\}$",
            markdown,
        )
        self.assertNotIn(
            "| Probability of Quota Violations Caused by Nonzero Allocation\nwith",
            markdown,
        )
        for block in re.split(r"\n\s*\n", markdown):
            pipe_lines = [line for line in block.splitlines() if line.startswith("|")]
            if len(pipe_lines) < 2:
                continue
            self.assertEqual(
                {line.count("|") for line in pipe_lines}, {pipe_lines[0].count("|")}
            )

    def test_html_route_collapses_plain_prose_hard_linebreaks_in_real_arxiv_fixtures(
        self,
    ) -> None:
        for arxiv_id in ("2605.06598v1", "2605.06653v1", "2605.06659v1"):
            with self.subTest(arxiv_id=arxiv_id):
                extraction = _arxiv_html._extract_arxiv_html_markdown(
                    _fixture_html(arxiv_id).decode("utf-8"),
                    canonical_arxiv_html_url(arxiv_id),
                    metadata=_metadata(arxiv_id),
                )

                self.assertEqual(
                    _multiline_plain_prose_blocks(extraction.markdown_text), []
                )

    def test_html_route_keeps_images_but_suppresses_repeated_appendix_captions(
        self,
    ) -> None:
        arxiv_id = "2605.06667v1"
        metadata = _metadata(arxiv_id)
        client = ArxivClient(_html_transport(arxiv_id), {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        downloaded_assets = _downloaded_html_assets(raw_payload, limit=5)

        article = client.to_article_model(
            metadata, raw_payload, downloaded_assets=downloaded_assets
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertNotIn("\n## Figures\n", markdown)
        self.assertIn("![Figure 4](body_assets/x4.png)", markdown)
        self.assertIn("![Figure 5](body_assets/x5.png)", markdown)
        self.assertLess(
            markdown.index("![Figure 4](body_assets/x4.png)"),
            markdown.index("**Figure 4.**"),
        )
        self.assertLess(
            markdown.index("![Figure 5](body_assets/x5.png)"),
            markdown.index("**Figure 5.**"),
        )
        self.assertEqual(
            markdown.count("Overview. ActCam enables zero-shot joint control"), 1
        )
        self.assertEqual(markdown.count("Effect of $N_{D}$ on VBench score"), 1)
        self.assertNotIn("N D N_{D}", markdown)

    def test_html_route_preserves_algorithm_listing_from_fixture(self) -> None:
        arxiv_id = "2605.06665v1"
        extraction = _arxiv_html._extract_arxiv_html_markdown(
            _fixture_html(arxiv_id).decode("utf-8"),
            canonical_arxiv_html_url(arxiv_id),
            metadata=_metadata(arxiv_id),
        )
        markdown = extraction.markdown_text

        self.assertIn(
            "**Algorithm 1.** Monte Carlo estimation of NormRouter scale constant",
            markdown,
        )
        self.assertIn("```text", markdown)
        self.assertIn("Input: Number of experts", markdown)
        self.assertIn("return", markdown)
        diagnostics = extraction.diagnostics["extraction"]
        self.assertEqual(diagnostics["listing_block_rendered_count"], 1)
        self.assertEqual(diagnostics["semantic_block_appended_count"], 0)
        self.assertEqual(extraction.warnings, [])

    def test_arxiv_html_metrics_section_remains_renderable_body_content(self) -> None:
        arxiv_id = "2605.06667v1"
        metadata = _metadata(arxiv_id)
        client = ArxivClient(_html_transport(arxiv_id), {})

        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        article = client.to_article_model(metadata, raw_payload)
        markdown = article.to_ai_markdown(asset_profile="none")
        section_hints = raw_payload.content.diagnostics["extraction"]["section_hints"]

        metrics_sections = [
            section for section in article.sections if section.heading == "Metrics."
        ]
        metrics_hints = [
            hint for hint in section_hints if hint["heading"] == "Metrics."
        ]
        self.assertTrue(metrics_sections)
        self.assertTrue(all(section.kind == "body" for section in metrics_sections))
        self.assertTrue(metrics_hints)
        self.assertTrue(all(hint["kind"] == "body" for hint in metrics_hints))
        self.assertIn("**Table 1.** Joint camera and character control.", markdown)
        self.assertIn("| Uni3C", markdown)
        self.assertIn("| ActCam", markdown)

    def test_arxiv_html_section_hints_are_limited_to_article_dom(self) -> None:
        repeated_body = " ".join(
            [
                "This synthetic arXiv article sentence describes reproducible experiments, controlled baselines, measured outcomes, and detailed analysis."
                for _ in range(70)
            ]
        )
        html = f"""
        <html>
          <body>
            <aside>
              <h2>Metrics</h2>
              <p>Article views, download counts, and citation widgets belong to page chrome.</p>
            </aside>
            <article class="ltx_document">
              <h1 class="ltx_title ltx_title_document">Synthetic arXiv DOM Rule</h1>
              <div id="abstract1" class="ltx_abstract">
                <h6 class="ltx_title ltx_title_abstract">Abstract.</h6>
                <p>This abstract summarizes the synthetic replay.</p>
              </div>
              <section id="S1" class="ltx_section">
                <h2 class="ltx_title ltx_title_section">1 Introduction</h2>
                <p>{repeated_body}</p>
              </section>
              <section id="S2" class="ltx_section">
                <h2 class="ltx_title ltx_title_section">2 Experiments</h2>
                <section id="S2.SS1" class="ltx_subsection">
                  <h3 class="ltx_title ltx_title_subsection">2.1 Setup</h3>
                  <p>{repeated_body}</p>
                  <h5 class="ltx_title ltx_title_paragraph">Metrics.</h5>
                  <p>{repeated_body}</p>
                  <figure class="ltx_table" id="S2.T1">
                    <figcaption><span class="ltx_tag ltx_tag_table">Table 1. </span>Synthetic metric scores.</figcaption>
                    <table class="ltx_tabular">
                      <tr><th>Method</th><th>Score</th></tr>
                      <tr><td>Baseline</td><td>0.51</td></tr>
                      <tr><td>ActCam</td><td>0.74</td></tr>
                    </table>
                  </figure>
                </section>
              </section>
              <section id="bib" class="ltx_bibliography">
                <h2 class="ltx_title ltx_title_bibliography">References</h2>
                <ul><li class="ltx_bibitem">Example Author. Example reference. 2026.</li></ul>
              </section>
            </article>
          </body>
        </html>
        """
        metadata = {**_metadata("2605.06667v1"), "title": "Synthetic arXiv DOM Rule"}

        extraction = _arxiv_html._extract_arxiv_html_markdown(
            html,
            canonical_arxiv_html_url("2605.06667v1"),
            metadata=metadata,
        )

        section_hints = extraction.diagnostics["extraction"]["section_hints"]
        metric_hints = [hint for hint in section_hints if hint["heading"] == "Metrics."]
        self.assertEqual([hint["kind"] for hint in metric_hints], ["body"])
        self.assertEqual(
            [hint for hint in section_hints if hint["heading"] == "Metrics"], []
        )
        self.assertIn("#### Metrics.", extraction.markdown_text)
        self.assertIn("**Table 1.** Synthetic metric scores.", extraction.markdown_text)
        self.assertIn("| ActCam", extraction.markdown_text)
        self.assertIn("0.74", extraction.markdown_text)
        self.assertNotIn("Article views", extraction.markdown_text)

    def test_html_route_downloads_body_figure_assets_for_body_profile(self) -> None:
        arxiv_id = "2605.06663v1"
        metadata = _metadata(arxiv_id)
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        source_url = f"https://arxiv.org/e-print/{arxiv_id}"
        transport.responses[("GET", source_url)] = http_response(
            source_url,
            _source_tar(
                {
                    "main.tex": (
                        rb"\documentclass{article}"
                        rb"\begin{document}\end{document}"
                    )
                }
            ),
            "application/gzip",
        )
        for asset in raw_payload.content.extracted_assets:
            for field in ("url", "full_size_url", "preview_url"):
                url = str(asset.get(field) or "")
                if url:
                    transport.responses[("GET", url)] = http_response(
                        url, PNG_1X1, "image/png"
                    )

        with (
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            result = client.fetch_result(
                metadata["doi"], metadata, Path(tmpdir), asset_profile="body"
            )
            self.assertEqual(result.content.route_kind, "html")
            self.assertGreater(len(result.article.assets), 0)
            self.assertTrue(
                all(
                    asset.path and Path(asset.path).is_file()
                    for asset in result.article.assets
                )
            )
            markdown = result.article.to_ai_markdown(asset_profile="body")
            self.assertGreater(markdown.count("!["), 0)
            non_asset_urls = {
                canonical_arxiv_html_url(arxiv_id),
                _arxiv_atom.ARXIV_API_URL,
                source_url,
            }
            asset_calls = [
                call for call in transport.calls if call["url"] not in non_asset_urls
            ]
            self.assertGreater(len(asset_calls), 0)
            self.assertTrue(
                all(
                    call["headers"]["Accept"] == _arxiv_assets.ARXIV_IMAGE_ACCEPT
                    for call in asset_calls
                )
            )
            self.assertTrue(
                all(
                    "text/html" not in call["headers"]["Accept"] for call in asset_calls
                )
            )

    def test_html_route_asset_download_limits_concurrency_and_retries_network_failures(
        self,
    ) -> None:
        arxiv_id = "2605.06663v1"
        metadata = _metadata(arxiv_id)
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        extracted_assets = [
            dict(item) for item in raw_payload.content.extracted_assets[:3]
        ]
        self.assertGreaterEqual(len(extracted_assets), 3)
        raw_payload.content = replace(
            raw_payload.content, extracted_assets=extracted_assets
        )
        first_asset, retried_asset, non_image_asset = extracted_assets
        retryable_failure = {
            "kind": "figure",
            "heading": retried_asset.get("heading", "Figure"),
            "caption": retried_asset.get("caption", ""),
            "source_url": retried_asset.get("url", ""),
            "reason": "transport failed before a response",
            "error_category": RequestErrorCategory.TLS_ERROR.value,
            "section": "body",
        }
        non_retryable_failure = {
            "kind": "figure",
            "heading": first_asset.get("heading", "Figure"),
            "caption": first_asset.get("caption", ""),
            "source_url": first_asset.get("url", ""),
            "status": 404,
            "reason": "HTTP 404 for arXiv image",
            "section": "body",
        }
        non_image_failure = {
            "kind": "figure",
            "heading": non_image_asset.get("heading", "Figure"),
            "caption": non_image_asset.get("caption", ""),
            "source_url": non_image_asset.get("url", ""),
            "status": 200,
            "content_type": "text/html; charset=utf-8",
            "reason": "Asset candidate did not return image content (content-type: text/html; charset=utf-8).",
            "section": "body",
        }
        initial_download = {
            "kind": "figure",
            "heading": first_asset.get("heading", "Figure"),
            "path": "/tmp/first.png",
            "download_url": first_asset.get("url", ""),
        }
        retry_download = {
            "kind": "figure",
            "heading": retried_asset.get("heading", "Figure"),
            "path": "/tmp/retried.png",
            "download_url": retried_asset.get("url", ""),
        }

        context = paper_fetch.RuntimeContext(
            env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "8"}
        )
        try:
            with (
                tempfile.TemporaryDirectory() as tmpdir,
                mock.patch.object(
                    _arxiv_asset_strategy,
                    "download_arxiv_source_figure_assets",
                    return_value={
                        "assets": [],
                        "asset_failures": [
                            {
                                "kind": "figure",
                                "heading": item.get("heading", "Figure"),
                                "caption": item.get("caption", ""),
                                "reason": "arxiv_source_figure_not_matched",
                            }
                            for item in extracted_assets
                        ],
                    },
                ),
                mock.patch.object(
                    html_assets,
                    "download_assets",
                    side_effect=[
                        {
                            "assets": [initial_download],
                            "asset_failures": [
                                retryable_failure,
                                non_retryable_failure,
                                non_image_failure,
                            ],
                        },
                        {"assets": [retry_download], "asset_failures": []},
                    ],
                ) as downloader,
            ):
                result = client.download_related_assets(
                    metadata["doi"],
                    metadata,
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                    context=context,
                )
        finally:
            context.close()

        self.assertEqual(result["assets"], [initial_download, retry_download])
        self.assertEqual(
            result["asset_failures"], [non_retryable_failure, non_image_failure]
        )
        self.assertEqual(
            downloader.call_args_list[0].kwargs["options"].asset_download_concurrency,
            2,
        )
        self.assertEqual(
            downloader.call_args_list[1].kwargs["options"].asset_download_concurrency,
            1,
        )
        retried_request = downloader.call_args_list[1].kwargs["assets"]
        self.assertEqual(len(retried_request), 1)
        self.assertEqual(retried_request[0]["url"], retried_asset["url"])
        self.assertIn(
            "official_full_size_not_exposed",
            retried_request[0]["provenance"],
        )
        for call in downloader.call_args_list:
            self.assertEqual(
                call.kwargs["options"].headers["Accept"],
                _arxiv_assets.ARXIV_IMAGE_ACCEPT,
            )
            self.assertNotIn("text/html", call.kwargs["options"].headers["Accept"])

    def test_html_route_asset_partial_failure_surfaces_quality_diagnostics(
        self,
    ) -> None:
        arxiv_id = "2605.06663v1"
        metadata = _metadata(arxiv_id)
        client = ArxivClient(_html_transport(arxiv_id), {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        failure = {
            "kind": "figure",
            "heading": "Figure 1",
            "source_url": "https://arxiv.org/html/2605.06663v1/x1.png",
            "reason": "Network error for arXiv image: timed out",
            "section": "body",
        }

        article = client.to_article_model(
            metadata, raw_payload, asset_failures=[failure]
        )

        self.assertTrue(
            any(
                "arXiv related assets were only partially downloaded" in warning
                for warning in article.quality.warnings
            )
        )
        self.assertEqual(article.quality.asset_failures, [failure])

    def test_html_route_asset_profile_none_skips_asset_downloads(self) -> None:
        arxiv_id = "2605.06663v1"
        metadata = _metadata(arxiv_id)
        transport = _html_transport(arxiv_id)
        client = ArxivClient(transport, {})

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.fetch_result(
                metadata["doi"], metadata, Path(tmpdir), asset_profile="none"
            )

        self.assertEqual(result.content.route_kind, "html")
        self.assertGreater(len(result.content.extracted_assets), 0)
        self.assertTrue(result.article.assets)
        self.assertTrue(all(asset.path is None for asset in result.article.assets))
        self.assertEqual(result.artifacts.assets, [])
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [canonical_arxiv_html_url(arxiv_id), _arxiv_atom.ARXIV_API_URL],
        )

    def test_html_route_recovers_missing_official_html_images_from_source_archive(
        self,
    ) -> None:
        """asset-download-contract: provider=arxiv"""

        arxiv_id = "2605.06556v1"
        metadata = _metadata(arxiv_id)
        html_body = _fixture_html(arxiv_id).replace(
            b'src="2605.06556v1/fig_1_tau_picture.png"',
            b'src=""',
        )
        source_url = f"https://arxiv.org/e-print/{arxiv_id}"
        source_record, source_archive = _record(
            metadata["doi"],
            "acquisition/template-gaps-2026-09-16/source-response.tar.gz",
        )
        with tarfile.open(fileobj=io.BytesIO(source_archive)) as archive:
            original_image = archive.extractfile("fig_1_tau_picture.png").read()
        self.assertEqual(len(original_image), 40866)
        transport = _html_transport(
            arxiv_id,
            html_body=html_body,
            extra_responses={
                ("GET", source_url): _response(source_record, source_archive)
            },
        )
        client = ArxivClient(transport, {})

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.fetch_result(
                metadata["doi"], metadata, Path(tmpdir), asset_profile="body"
            )
            self.assertEqual(result.content.route_kind, "html")
            self.assertTrue(result.artifacts.assets)
            self.assertEqual(len(result.article.assets), 1)
            asset = result.article.assets[0]
            self.assertEqual(asset.download_tier, "arxiv_source")
            self.assertEqual(asset.source_path, "fig_1_tau_picture.png")
            self.assertTrue(asset.path and Path(asset.path).is_file())
            self.assertEqual(Path(asset.path).read_bytes(), original_image)
            markdown = result.article.to_ai_markdown(asset_profile="body")
            self.assertIn("![Figure 1]", markdown)
            self.assertIn("fig_1_tau_picture.png", markdown)
            self.assertLess(
                markdown.index("![Figure 1]"),
                markdown.index("**Figure 1.**"),
            )
            self.assertNotIn("\n## Figures\n", markdown)
        self.assertIn(source_url, [call["url"] for call in transport.calls])

    def test_html_route_upgrades_existing_preview_from_official_source_archive(
        self,
    ) -> None:
        arxiv_id = "2605.06556v1"
        metadata = _metadata(arxiv_id)
        source_url = f"https://arxiv.org/e-print/{arxiv_id}"
        source_record, source_archive = _record(
            metadata["doi"],
            "acquisition/template-gaps-2026-09-16/source-response.tar.gz",
        )
        with tarfile.open(fileobj=io.BytesIO(source_archive)) as archive:
            original_image = archive.extractfile("fig_1_tau_picture.png").read()
        self.assertEqual(len(original_image), 40866)
        transport = _html_transport(
            arxiv_id,
            extra_responses={
                ("GET", source_url): _response(source_record, source_archive)
            },
        )
        client = ArxivClient(transport, {})
        raw_payload = client.fetch_raw_fulltext(metadata["doi"], metadata)
        preview = next(
            asset
            for asset in raw_payload.content.extracted_assets
            if "fig_1_tau_picture.png" in str(asset.get("url") or "")
        )
        raw_payload.content = replace(
            raw_payload.content,
            extracted_assets=[preview],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                metadata["doi"],
                metadata,
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
            )

            self.assertEqual(
                Path(result["assets"][0]["path"]).read_bytes(), original_image
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "arxiv_source")
        self.assertEqual(result["assets"][0]["source_path"], "fig_1_tau_picture.png")
        requested_urls = [call["url"] for call in transport.calls]
        self.assertIn(source_url, requested_urls)
        self.assertNotIn(preview["url"], requested_urls)

    def test_fetch_paper_uses_arxiv_provider_for_resolved_arxiv_id(self) -> None:
        arxiv_id = "2605.06663v1"
        api_client = ReplayArxivApiClient({arxiv_id: _api_payload(arxiv_id)})
        arxiv_client = ArxivClient(_html_transport(arxiv_id), {}, api_client=api_client)
        context = paper_fetch.RuntimeContext(
            env={},
            clients={
                "arxiv": arxiv_client,
                "crossref": FixtureProvider(
                    metadata=ProviderFailure("no_result", "Crossref not used.")
                ),
            },
        )

        envelope = paper_fetch.fetch_paper(
            arxiv_id,
            modes={"article", "markdown"},
            strategy=paper_fetch.FetchStrategy(preferred_providers=["arxiv"]),
            context=context,
        )

        assert envelope.article is not None
        self.assertEqual(envelope.article.source, "arxiv_html")
        self.assertEqual(envelope.article.quality.content_kind, "fulltext")
        self.assertIn(
            "route:provider_selected_arxiv", envelope.article.quality.source_trail
        )
        self.assertIn("metadata:arxiv_ok", envelope.article.quality.source_trail)
        self.assertIn(
            "fulltext:arxiv_article_ok", envelope.article.quality.source_trail
        )
        self.assertTrue(envelope.markdown)
        self.assertEqual(api_client.queries, [[arxiv_id]])

    def test_crossref_only_preferred_providers_skip_arxiv_fulltext(self) -> None:
        arxiv_id = "2605.06663v1"
        metadata = _metadata(arxiv_id)
        arxiv_client = ArxivClient(_html_transport(arxiv_id), {})
        context = paper_fetch.RuntimeContext(
            env={},
            clients={
                "arxiv": arxiv_client,
                "crossref": FixtureProvider(
                    metadata={
                        **metadata,
                        "provider": "crossref",
                        "official_provider": False,
                    }
                ),
            },
        )

        envelope = paper_fetch.fetch_paper(
            arxiv_id,
            modes={"article"},
            strategy=paper_fetch.FetchStrategy(preferred_providers=["crossref"]),
            context=context,
        )

        assert envelope.article is not None
        self.assertEqual(envelope.article.source, "crossref_meta")
        self.assertEqual(envelope.article.quality.content_kind, "abstract_only")
        self.assertNotIn(
            "fulltext:arxiv_attempt", envelope.article.quality.source_trail
        )
        self.assertEqual(arxiv_client.transport.calls, [])

    def test_no_download_returns_markdown_without_payload_artifacts(self) -> None:
        arxiv_id = "2605.06663v1"
        api_client = ReplayArxivApiClient({arxiv_id: _api_payload(arxiv_id)})
        with tempfile.TemporaryDirectory() as tmpdir:
            context = paper_fetch.RuntimeContext(
                env={},
                clients={
                    "arxiv": ArxivClient(
                        _html_transport(arxiv_id),
                        {},
                        api_client=api_client,
                    ),
                    "crossref": FixtureProvider(
                        metadata=ProviderFailure("no_result", "Crossref not used.")
                    ),
                },
                download_dir=None,
            )
            envelope = paper_fetch.fetch_paper(
                arxiv_id,
                modes={"article", "markdown"},
                strategy=paper_fetch.FetchStrategy(preferred_providers=["arxiv"]),
                context=context,
            )

            self.assertTrue(envelope.markdown)
            self.assertEqual(list(Path(tmpdir).iterdir()), [])

    def test_download_dir_saves_arxiv_html_payload_only(self) -> None:
        arxiv_id = "2605.06663v1"
        api_client = ReplayArxivApiClient({arxiv_id: _api_payload(arxiv_id)})
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            context = paper_fetch.RuntimeContext(
                env={},
                clients={
                    "arxiv": ArxivClient(
                        _html_transport(arxiv_id),
                        {},
                        api_client=api_client,
                    ),
                    "crossref": FixtureProvider(
                        metadata=ProviderFailure("no_result", "Crossref not used.")
                    ),
                },
                download_dir=output_dir,
            )
            envelope = paper_fetch.fetch_paper(
                arxiv_id,
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(
                    preferred_providers=["arxiv"], asset_profile="none"
                ),
                context=context,
            )

            self.assertEqual(envelope.source, "arxiv_html")
            saved_files = list(output_dir.iterdir())
            self.assertTrue(
                any(path.name.endswith("_original.html") for path in saved_files)
            )
            self.assertFalse(
                any(path.suffix in {".gz", ".tar"} for path in saved_files)
            )


class TestArxivAncillaryAssets(unittest.TestCase):
    def _responses(self, arxiv_id, *, fixture_id="0811.2625v2", requested_id=None):
        abstract, details = ARXIV_ANCILLARY_PAGES[fixture_id]
        abstract = abstract.replace(fixture_id, arxiv_id).replace(
            fixture_id.rsplit("v", 1)[0], arxiv_id.rsplit("v", 1)[0]
        )
        details = details.replace(fixture_id, arxiv_id)
        abs_url = f"https://arxiv.org/abs/{requested_id or arxiv_id}"
        details_url = f"https://arxiv.org/src/{arxiv_id}/anc"
        return {
            ("GET", abs_url): http_response(abs_url, abstract.encode(), "text/html"),
            ("GET", details_url): http_response(
                details_url, details.encode(), "text/html"
            ),
        }

    def _discover(self, arxiv_id, responses):
        transport = RecordingTransport(responses)
        with paper_fetch.RuntimeContext(env={}) as context:
            fixed_id, result = _arxiv_assets.discover_arxiv_ancillary_assets(
                transport, arxiv_id, user_agent="test", context=context
            )
        return fixed_id, result, transport

    def test_unversioned_request_pins_body_and_enrichment_preserves_version(self):
        arxiv_id = "2605.06663v1"
        unversioned = arxiv_id.rsplit("v", 1)[0]
        for requested in (arxiv_id, unversioned):
            with (
                self.subTest(requested=requested),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                responses = self._responses(arxiv_id, requested_id=requested)
                latest_api = _atom_feed_from_fixture(arxiv_id).replace(
                    arxiv_id.encode(), f"{unversioned}v9".encode()
                )
                transport = _html_transport(
                    arxiv_id, api_body=latest_api, extra_responses=responses
                )
                client = ArxivClient(transport, {})
                with paper_fetch.RuntimeContext(
                    env={}, download_dir=Path(tmpdir), asset_profile="all"
                ) as context:
                    raw = client.fetch_raw_fulltext(
                        _doi(requested), {"arxiv_id": requested}, context=context
                    )
                self.assertEqual(raw.content.merged_metadata["arxiv_id"], arxiv_id)
                self.assertEqual(
                    raw.content.merged_metadata["pdf_url"],
                    canonical_arxiv_pdf_url(arxiv_id),
                )
                self.assertEqual(
                    raw.content.merged_metadata["html_url"],
                    canonical_arxiv_html_url(arxiv_id),
                )
                self.assertEqual(
                    transport.calls[2]["url"], canonical_arxiv_html_url(arxiv_id)
                )
                self.assertEqual(transport.calls[-1]["query"]["id_list"], arxiv_id)

    def test_no_extra_requests_without_all_and_asset_output(self):
        arxiv_id = "2605.06663v1"
        for profile, mode, output in (
            ("none", "all", True),
            ("body", "all", True),
            ("all", "none", True),
            ("all", "all", False),
        ):
            with (
                self.subTest(profile=profile, mode=mode, output=output),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                transport = _html_transport(arxiv_id)
                client = ArxivClient(transport, {})
                with paper_fetch.RuntimeContext(
                    env={},
                    download_dir=Path(tmpdir) if output else None,
                    artifact_mode=mode,
                    asset_profile=profile,
                ) as context:
                    client.fetch_raw_fulltext(
                        _doi(arxiv_id), _metadata(arxiv_id), context=context
                    )
                self.assertEqual(
                    [call["url"] for call in transport.calls],
                    [canonical_arxiv_html_url(arxiv_id), _arxiv_atom.ARXIV_API_URL],
                )

    def test_html_downloads_notebooks_pdf_and_same_basename_paths(self):
        arxiv_id = "2605.06663v1"
        responses = self._responses(arxiv_id)
        details_url = f"https://arxiv.org/src/{arxiv_id}/anc"
        body = responses[("GET", details_url)]["body"]
        # Two nested .m paths exercise the existing flattened filename collision handling.
        body = body.replace(b"There are 2", b"There are 4").replace(
            b"</ul>",
            (
                f'<li><a class="anc-file-name" href="{details_url}/a/code.m">a/code.m</a></li><li><a class="anc-file-name" href="{details_url}/b/code.m">b/code.m</a></li></ul>'
            ).encode(),
        )
        responses[("GET", details_url)]["body"] = body
        contents = {
            "solve-sparse-opt-check-small.nb": b"Notebook[{Cell[1]}]",
            "solve-sparse-opt-check-small.pdf": b"%PDF-1.4\n%%EOF",
            "a/code.m": b"x=1;",
            "b/code.m": b"x=2;",
        }
        for path, content in contents.items():
            url = f"{details_url}/{path}"
            responses[("GET", url)] = http_response(
                url,
                content,
                "application/pdf" if path.endswith(".pdf") else "text/plain",
            )
        transport = _html_transport(arxiv_id, extra_responses=responses)
        client = ArxivClient(transport, {})
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch(
                "paper_fetch.providers.arxiv.download_arxiv_html_figure_assets",
                return_value={"assets": [], "asset_failures": []},
            ),
        ):
            result = client.fetch_result(
                _doi(arxiv_id), _metadata(arxiv_id), Path(tmpdir), asset_profile="all"
            )
            self.assertEqual(result.artifacts.asset_failures, [])
            supplementary = [
                a for a in result.article.assets if a.kind == "supplementary"
            ]
            self.assertEqual(len(supplementary), 4)
            self.assertEqual(len(result.artifacts.assets), 4)
            self.assertEqual(len({a.path for a in supplementary}), 4)
            markdown = result.article.to_ai_markdown(
                asset_profile="all", max_tokens="full_text"
            )
            self.assertIn("## Supplementary Materials", markdown)
            for asset in supplementary:
                self.assertEqual(
                    Path(asset.path).read_bytes(), contents[asset.source_path]
                )
                self.assertEqual(asset.heading, asset.source_path)
                self.assertEqual(markdown.count(f"]({asset.path})"), 1)
                self.assertEqual(
                    Path(asset.path).parent, Path(tmpdir) / f"{arxiv_id}_assets"
                )
        self.assertEqual(
            sum(
                c["url"] == canonical_arxiv_html_url(arxiv_id) for c in transport.calls
            ),
            1,
        )

    def test_pdf_figures_and_attachments_are_registered_once_and_keep_fallback(self):
        from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance

        arxiv_id = "1406.2661v1"
        for scenario in (
            "figure",
            "attachment_only",
            "download_failure",
            "discovery_failure",
        ):
            with (
                self.subTest(scenario=scenario),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                transport = _html_404_then_pdf_transport(arxiv_id)
                transport.responses.update(
                    self._responses(arxiv_id, fixture_id="2606.00587v2")
                )
                url = f"https://arxiv.org/src/{arxiv_id}/anc/supplementary_material.pdf"
                transport.responses[("GET", url)] = http_response(
                    url, _fixture_pdf(arxiv_id), "application/pdf"
                )
                if scenario == "download_failure":
                    transport.responses[("GET", url)] = http_response(
                        url, b"Access denied", "text/html"
                    )
                if scenario == "discovery_failure":
                    transport.responses[("GET", f"https://arxiv.org/abs/{arxiv_id}")][
                        "status"
                    ] = 503
                client = ArxivClient(transport, {})
                client.api_enrichment_enabled = False
                original_pdf = client._fetch_pdf_payload
                image = Path(tmpdir) / "body.png"
                image.write_bytes(PNG_1X1)

                def pdf_with_assets(
                    *args,
                    _fetch_pdf=original_pdf,
                    _image=image,
                    _scenario=scenario,
                    **kwargs,
                ):
                    payload = _fetch_pdf(*args, **kwargs)
                    payload.content = replace(
                        payload.content,
                        extracted_assets=[
                            {
                                "kind": "figure",
                                "heading": "Figure 1",
                                "path": str(_image),
                                "section": "body",
                            }
                        ]
                        if _scenario == "figure"
                        else [],
                    )
                    return payload

                with mock.patch.object(
                    client, "_fetch_pdf_payload", side_effect=pdf_with_assets
                ):
                    result = client.fetch_result(
                        _doi(arxiv_id),
                        _metadata(arxiv_id),
                        Path(tmpdir),
                        asset_profile="all",
                    )
                kinds = (
                    ["figure", "supplementary"]
                    if scenario == "figure"
                    else ["supplementary"]
                    if scenario == "attachment_only"
                    else []
                )
                self.assertEqual([a.kind for a in result.article.assets], kinds)
                self.assertEqual(len(result.artifacts.assets), len(kinds))
                self.assertEqual(result.artifacts.text_only, not kinds)
                self.assertEqual(
                    len(result.artifacts.asset_failures), int("failure" in scenario)
                )
                self.assertIn(
                    "fulltext:arxiv_html_fail", result.article.quality.source_trail
                )
                self.assertIn(
                    "fulltext:arxiv_pdf_fallback_ok",
                    result.article.quality.source_trail,
                )
                envelope = paper_fetch.build_fetch_envelope(
                    result.article,
                    modes={"article", "markdown"},
                    render=paper_fetch.RenderOptions(
                        asset_profile="all", max_tokens="full_text"
                    ),
                )
                acceptance = evaluate_fetch_acceptance(envelope, asset_profile="all")
                self.assertEqual(acceptance.overall.value, "degraded")
                self.assertIn(
                    "fulltext:arxiv_html:fail", acceptance.provenance.fallback_codes
                )
                self.assertEqual(
                    envelope.markdown.count("## Supplementary Materials"),
                    int(bool(kinds)),
                )
                self.assertEqual(
                    sum(
                        c["url"] == canonical_arxiv_pdf_url(arxiv_id)
                        for c in transport.calls
                    ),
                    1,
                )
                self.assertEqual(
                    sum(
                        c["url"] == canonical_arxiv_html_url(arxiv_id)
                        for c in transport.calls
                    ),
                    1,
                )

    def test_service_acceptance_and_asset_failures_preserve_successful_body(self):
        from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance

        arxiv_id = "2605.06663v1"
        for failure in (None, "discovery", "download"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmpdir:
                responses = self._responses(arxiv_id, fixture_id="2606.00587v2")
                url = f"https://arxiv.org/src/{arxiv_id}/anc/supplementary_material.pdf"
                responses[("GET", url)] = http_response(
                    url, _fixture_pdf("1406.2661v1"), "application/pdf"
                )
                if failure == "discovery":
                    responses[("GET", f"https://arxiv.org/abs/{arxiv_id}")][
                        "status"
                    ] = 503
                if failure == "download":
                    responses[("GET", url)] = http_response(
                        url, b"Access denied", "text/html"
                    )
                transport = _html_transport(arxiv_id, extra_responses=responses)
                # The established body fixture has figures; this test isolates supplementary
                # service assembly. Body image downloading has separate replay coverage.
                soup = _arxiv_html.BeautifulSoup(_fixture_html(arxiv_id), "html.parser")
                for node in soup.select("figure, img"):
                    node.decompose()
                transport.responses[("GET", canonical_arxiv_html_url(arxiv_id))][
                    "body"
                ] = str(soup).encode()
                client = ArxivClient(
                    transport,
                    {},
                    api_client=ReplayArxivApiClient({arxiv_id: _api_payload(arxiv_id)}),
                )
                with (
                    paper_fetch.RuntimeContext(
                        env={},
                        clients={"arxiv": client},
                        download_dir=Path(tmpdir),
                    ) as context,
                    mock.patch(
                        "paper_fetch.providers.arxiv.download_arxiv_html_figure_assets",
                        return_value={"assets": [], "asset_failures": []},
                    ),
                ):
                    envelope = paper_fetch.fetch_paper(
                        arxiv_id,
                        modes={"article", "markdown"},
                        strategy=paper_fetch.FetchStrategy(
                            preferred_providers=["arxiv"],
                            asset_profile="all",
                            require_local_body_assets=True,
                        ),
                        context=context,
                    )
                    acceptance = evaluate_fetch_acceptance(
                        envelope,
                        asset_profile="all",
                        expected_doi=_doi(arxiv_id),
                        require_local_body_assets=True,
                    )
                self.assertTrue(envelope.has_fulltext)
                self.assertTrue(envelope.markdown)
                self.assertEqual(
                    sum(
                        c["url"] == canonical_arxiv_html_url(arxiv_id)
                        for c in transport.calls
                    ),
                    1,
                )
                self.assertFalse(any("/pdf/" in c["url"] for c in transport.calls))
                if failure:
                    self.assertEqual(acceptance.overall.value, "degraded")
                    self.assertEqual(len(envelope.article.quality.asset_failures), 1)
                else:
                    self.assertEqual(acceptance.overall.value, "complete")
                    self.assertEqual(acceptance.asset.local, 1)
                    self.assertEqual(len(envelope.article.assets), 1)
                    self.assertEqual(
                        envelope.markdown.count("## Supplementary Materials"), 1
                    )

    def test_attachments_obey_shared_bytes_and_file_budgets(self):
        from paper_fetch.asset_budget import AssetBudget
        from paper_fetch.http import HttpTransport
        from tests.support.asset_budget import _FakeStreamResponse

        arxiv_id = "2605.06663v1"
        for budget, code in (
            (AssetBudget(max_bytes_per_asset=8), "asset_bytes_per_asset_exceeded"),
            (AssetBudget(max_bytes_total=20), "asset_bytes_total_exceeded"),
            (AssetBudget(max_files=0), "asset_file_limit_exceeded"),
        ):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmpdir:
                # Simulate bytes already retained for the body in the same budget.
                if code == "asset_bytes_total_exceeded":
                    reservation = budget.reserve()
                    reservation.consume(10)
                    reservation.commit()
                responses = self._responses(arxiv_id, fixture_id="2606.00587v2")
                url = f"https://arxiv.org/src/{arxiv_id}/anc/supplementary_material.pdf"
                responses[("GET", url)] = http_response(
                    url, b"%PDF-1.4\n%%EOF", "application/pdf"
                )
                transport = _html_transport(arxiv_id, extra_responses=responses)
                client = ArxivClient(transport, {})
                streaming = HttpTransport()
                response = _FakeStreamResponse(
                    b"%PDF-1.4\n%%EOF", headers={"content-type": "application/pdf"}
                )
                response._paper_fetch_final_url = url
                with (
                    paper_fetch.RuntimeContext(
                        env={}, download_dir=Path(tmpdir), asset_budget=budget
                    ) as context,
                    mock.patch(
                        "paper_fetch.providers.arxiv.download_arxiv_html_figure_assets",
                        return_value={"assets": [], "asset_failures": []},
                    ),
                    mock.patch.object(
                        streaming, "_perform_request", return_value=response
                    ),
                    mock.patch.object(transport, "_streaming_ready", True, create=True),
                    mock.patch.object(
                        transport,
                        "stream_to_file",
                        side_effect=streaming.stream_to_file,
                    ),
                ):
                    result = client.fetch_result(
                        _doi(arxiv_id),
                        _metadata(arxiv_id),
                        Path(tmpdir),
                        asset_profile="all",
                        context=context,
                    )
                self.assertEqual(result.article.quality.content_kind, "fulltext")
                self.assertEqual(result.artifacts.assets, [])
                self.assertEqual(result.artifacts.asset_failures[0]["reason"], code)
                self.assertFalse(list(Path(tmpdir).rglob("*.part")))
                self.assertEqual(
                    sum(
                        c["url"] == canonical_arxiv_html_url(arxiv_id)
                        for c in transport.calls
                    ),
                    1,
                )

    def test_real_complete_lists_and_nested_paths(self):
        for arxiv_id, count in (
            ("0811.2625v2", 2),
            ("2606.00587v2", 1),
            ("0905.2326v2", 103),
        ):
            with self.subTest(arxiv_id=arxiv_id):
                fixed_id, result, transport = self._discover(
                    arxiv_id, self._responses(arxiv_id, fixture_id=arxiv_id)
                )
                self.assertEqual(fixed_id, arxiv_id)
                self.assertEqual(result["asset_failures"], [])
                self.assertEqual(len(result["assets"]), count)
                self.assertEqual(len(transport.calls), 2)
                for item in result["assets"]:
                    self.assertEqual(item["heading"], item["source_path"])
                    self.assertEqual(
                        item["url"],
                        f"https://arxiv.org/src/{arxiv_id}/anc/{item['source_path']}",
                    )
                if count == 103:
                    self.assertEqual(result["assets"][2]["source_path"], "nb/SUGRA1.nb")
                    self.assertEqual(
                        result["assets"][-1]["source_path"], "rawData/Neq8FourLoops.m"
                    )
                if count == 2:
                    self.assertEqual(
                        [Path(a["source_path"]).suffix for a in result["assets"]],
                        [".nb", ".pdf"],
                    )
                if count == 1:
                    self.assertEqual(
                        result["assets"][0]["source_path"], "supplementary_material.pdf"
                    )


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
