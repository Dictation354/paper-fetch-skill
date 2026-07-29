from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paper_fetch.http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.copernicus import CopernicusClient
from paper_fetch.providers._article_markdown_copernicus import parse_copernicus_xml
from paper_fetch.providers._article_markdown_jats import parse_jats_xml

from tests.unit._paper_fetch_support import (
    RecordingTransport,
    fulltext_pdf_bytes,
    http_response,
)


DOI = "10.5194/acp-24-1-2024"
LANDING_URL = "https://acp.copernicus.org/articles/24/1/2024/"
XML_URL = "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024.xml"
PDF_URL = "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024.pdf"
MARKDOWN_REVIEWED_FIXTURES = {
    "structure": "10.5194_acp-24-1-2024",
    "figure": "10.5194_acp-24-1-2024",
    "references": "10.5194_acp-24-1-2024",
    "pdf_fallback": "10.5194_acp-1-1-2001",
}


def _landing_html(
    *, xml_url: str = XML_URL, pdf_url: str = PDF_URL, body: str = ""
) -> bytes:
    return f"""
    <html>
      <head>
        <title>Copernicus Article</title>
        <meta name="citation_title" content="Copernicus XML Test Article"/>
        <meta name="citation_doi" content="{DOI}"/>
        <meta name="citation_author" content="Alice Example"/>
        <meta name="citation_abstract" content="This abstract describes a Copernicus article with public XML."/>
        <meta name="citation_xml_url" content="{xml_url}"/>
        <meta name="citation_pdf_url" content="{pdf_url}"/>
      </head>
      <body>{body}</body>
    </html>
    """.encode()


def _article_body_text() -> str:
    sentence = (
        "Copernicus XML body text contains enough research narrative to qualify as full text "
        "with methods, observations, seasonal comparisons, and interpretation. "
    )
    return sentence * 10


def _xml_fixture(
    *, body_text: str | None = None, graphic_href: str | None = None
) -> bytes:
    body = body_text or _article_body_text()
    graphic = (
        graphic_href
        or "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024-f01.png"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink"
         xmlns:mml="http://www.w3.org/1998/Math/MathML"
         article-type="research-article">
  <front>
    <journal-meta>
      <journal-title-group><journal-title>Atmospheric Chemistry and Physics</journal-title></journal-title-group>
      <publisher><publisher-name>Copernicus Publications</publisher-name></publisher>
    </journal-meta>
    <article-meta>
      <article-id pub-id-type="doi">{DOI}</article-id>
      <title-group><article-title>Copernicus XML Test Article</article-title></title-group>
      <contrib-group>
        <contrib contrib-type="author"><name><surname>Example</surname><given-names>Alice</given-names></name></contrib>
        <contrib contrib-type="author"><name><surname>Researcher</surname><given-names>Bob</given-names></name></contrib>
      </contrib-group>
      <pub-date><day>2</day><month>January</month><year>2024</year></pub-date>
      <permissions><license><license-p><ext-link xlink:href="https://creativecommons.org/licenses/by/4.0/">CC BY</ext-link></license-p></license></permissions>
      <abstract><title>Abstract</title><p>This abstract describes a Copernicus article with public XML and scientific findings.</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec id="s1"><label>1</label><title>Introduction</title>
      <p>{body}</p>
      <disp-formula id="eq1"><label>1</label><mml:math display="block"><mml:mrow><mml:mi>x</mml:mi><mml:mo>=</mml:mo><mml:mn>1</mml:mn></mml:mrow></mml:math></disp-formula>
      <fig id="fig1"><label>Figure 1</label><caption><p>Observed seasonal variation.</p></caption><graphic xlink:href="{graphic}"/></fig>
      <table-wrap id="tab1"><label>Table 1</label><caption><p>Seasonal means.</p></caption>
        <table><thead><tr><th>Season</th><th>Value</th></tr></thead><tbody><tr><td>Winter</td><td>1</td></tr><tr><td>Summer</td><td>2</td></tr></tbody></table>
      </table-wrap>
    </sec>
    <sec id="s2"><label>2</label><title>Results</title><p>{body}</p></sec>
  </body>
  <back>
    <notes notes-type="dataavailability"><title>Data availability</title><p>Data are available in a repository.</p></notes>
    <app-group><supplementary-material><p>Supplement at <inline-supplementary-material xlink:href="https://doi.org/10.5194/acp-24-1-2024-supplement" xlink:title="pdf">supplement</inline-supplementary-material>.</p></supplementary-material></app-group>
    <ref-list>
      <ref id="r1"><label>1</label><mixed-citation>Smith, A.: Reference title, 2020, <ext-link xlink:href="https://doi.org/10.1000/example">https://doi.org/10.1000/example</ext-link>.</mixed-citation></ref>
    </ref-list>
  </back>
</article>
""".encode()


def _abstract_only_xml_fixture(*, body: str = "<body/>") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article">
  <front>
    <journal-meta>
      <journal-title-group><journal-title>Atmospheric Chemistry and Physics</journal-title></journal-title-group>
    </journal-meta>
    <article-meta>
      <article-id pub-id-type="doi">{DOI}</article-id>
      <title-group><article-title>Copernicus Abstract Only Article</article-title></title-group>
      <abstract><p>This XML exposes metadata and an abstract but no usable body text.</p></abstract>
    </article-meta>
  </front>
  {body}
</article>
""".encode()


class CopernicusProviderTests(unittest.TestCase):
    def test_doi_org_landing_url_keeps_doi_slash_unescaped(self) -> None:
        client = CopernicusClient(RecordingTransport({}), {})

        self.assertEqual(
            client._resolve_landing_url("10.5194/not-pattern", {}),
            "https://doi.org/10.5194/not-pattern",
        )

    def test_xml_main_path_builds_fulltext_article_and_records_request_options(
        self,
    ) -> None:
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, _xml_fixture(), "application/xml"
                ),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )
        article = client.to_article_model({"doi": DOI}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "xml")
        self.assertEqual(article.source, "copernicus_xml")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:copernicus_xml_ok", article.quality.source_trail)
        self.assertTrue(article.metadata.authors)
        self.assertTrue(article.references)
        self.assertTrue([asset for asset in article.assets if asset.kind == "figure"])
        self.assertTrue([asset for asset in article.assets if asset.kind == "table"])
        table_assets = [
            asset
            for asset in raw_payload.content.extracted_assets
            if asset.get("kind") == "table"
        ]
        self.assertEqual(table_assets[0]["table_render_kind"], "structured")
        landing_call, xml_call = transport.calls[:2]
        self.assertIn("text/html", landing_call["headers"]["Accept"])
        self.assertIn("application/xml", xml_call["headers"]["Accept"])
        self.assertEqual(xml_call["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(xml_call["retry_on_transient"])

    def test_xml_candidate_can_be_discovered_from_landing_link(self) -> None:
        linked_xml_url = "https://acp.copernicus.org/articles/24/1/2024/linked.xml"
        landing = _landing_html(
            xml_url="",
            body=f'<a class="download-xml" href="{linked_xml_url}">XML</a>',
        )
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(LANDING_URL, landing, "text/html"),
                ("GET", linked_xml_url): http_response(
                    linked_xml_url, _xml_fixture(), "application/xml"
                ),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )

        self.assertEqual(raw_payload.source_url, linked_xml_url)
        self.assertEqual(raw_payload.content.route_kind, "xml")

    def test_xml_response_relative_url_is_normalized_for_relative_assets(self) -> None:
        relative_response_url = "/articles/24/1/2024/acp-24-1-2024.xml"
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    relative_response_url,
                    _xml_fixture(graphic_href="acp-24-1-2024-f01.png"),
                    "application/xml",
                ),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )
        article = client.to_article_model({"doi": DOI}, raw_payload)
        figure_assets = [asset for asset in article.assets if asset.kind == "figure"]

        self.assertEqual(raw_payload.source_url, XML_URL)
        self.assertTrue(figure_assets)
        self.assertEqual(
            figure_assets[0].original_url,
            "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024-f01.png",
        )

    def test_xml_assets_download_from_canonical_original_url(self) -> None:
        """asset-download-contract: provider=copernicus"""

        figure_url = (
            "https://acp.copernicus.org/articles/24/1/2024/acp-24-1-2024-f01.png"
        )
        figure_body = b"\x89PNG\r\n\x1a\nfigure"
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, _xml_fixture(graphic_href=figure_url), "application/xml"
                ),
                ("GET", figure_url): http_response(
                    figure_url, figure_body, "image/png"
                ),
            }
        )
        client = CopernicusClient(transport, {})

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.fetch_result(
                DOI,
                {"doi": DOI, "landing_page_url": LANDING_URL},
                Path(tmpdir),
                asset_profile="body",
            )
            downloaded_asset = result.artifacts.assets[0]
            markdown = result.article.to_ai_markdown(
                asset_profile="body", max_tokens="full_text"
            )
            self.assertTrue(Path(downloaded_asset["path"]).is_file())
            self.assertEqual(Path(downloaded_asset["path"]).read_bytes(), figure_body)
            self.assertIn(downloaded_asset["path"], markdown)
            self.assertNotIn(figure_url, markdown)

        self.assertTrue(result.artifacts.assets)
        self.assertEqual(result.artifacts.assets[0]["original_url"], figure_url)
        self.assertEqual(
            result.artifacts.assets[0]["downloaded_bytes"], len(figure_body)
        )
        self.assertIn(
            ("GET", figure_url),
            [(call["method"], call["url"]) for call in transport.calls],
        )

    def test_xml_failure_skips_landing_html_and_falls_back_to_pdf(self) -> None:
        html_body = (
            "<article><h1>Copernicus XML Test Article</h1>"
            "<h2>Abstract</h2><p>This abstract describes a Copernicus article.</p>"
            "<h2>Introduction</h2><p>" + _article_body_text() + "</p>"
            "<h2>Results</h2><p>" + _article_body_text() + "</p></article>"
        )
        pdf_bytes = fulltext_pdf_bytes()
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(body=html_body), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, b"<html>not xml</html>", "text/html"
                ),
                ("GET", PDF_URL): http_response(PDF_URL, pdf_bytes, "application/pdf"),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )
        article = client.to_article_model({"doi": DOI}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(article.source, "copernicus_pdf")
        self.assertIn("fulltext:copernicus_xml_fail", article.quality.source_trail)
        self.assertIn(
            "fulltext:copernicus_pdf_fallback_ok", article.quality.source_trail
        )

    def test_abstract_only_short_body_xml_falls_back_to_pdf(self) -> None:
        pdf_bytes = fulltext_pdf_bytes()
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL,
                    _abstract_only_xml_fixture(
                        body="<body><sec><p>Too short.</p></sec></body>"
                    ),
                    "application/xml",
                ),
                ("GET", PDF_URL): http_response(PDF_URL, pdf_bytes, "application/pdf"),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertTrue(
            any(
                "did not expose enough body text" in warning
                for warning in raw_payload.warnings
            )
        )
        self.assertIn(
            ("GET", PDF_URL),
            [(call["method"], call["url"]) for call in transport.calls],
        )

    def test_xml_without_body_paragraphs_falls_back_to_pdf(self) -> None:
        pdf_bytes = fulltext_pdf_bytes()
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL,
                    _abstract_only_xml_fixture(
                        body="<body><sec><title>Introduction</title></sec></body>"
                    ),
                    "application/xml",
                ),
                ("GET", PDF_URL): http_response(PDF_URL, pdf_bytes, "application/pdf"),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertTrue(
            any(
                "did not expose body paragraphs" in warning
                for warning in raw_payload.warnings
            )
        )

    def test_empty_body_xml_falls_back_to_pdf(self) -> None:
        pdf_bytes = fulltext_pdf_bytes()
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, _abstract_only_xml_fixture(), "application/xml"
                ),
                ("GET", PDF_URL): http_response(PDF_URL, pdf_bytes, "application/pdf"),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertTrue(
            any(
                "missing article metadata or body sections" in warning
                for warning in raw_payload.warnings
            )
        )

    def test_landing_failure_continues_with_doi_derived_xml_candidate(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): RequestFailure(
                    503, "landing unavailable", url=LANDING_URL
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, _xml_fixture(), "application/xml"
                ),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )
        article = client.to_article_model({"doi": DOI}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "xml")
        self.assertTrue(
            any(
                "DOI-derived XML/PDF candidates" in warning
                for warning in raw_payload.warnings
            )
        )
        self.assertIn("fulltext:copernicus_landing_fail", article.quality.source_trail)
        self.assertIn("fulltext:copernicus_xml_ok", article.quality.source_trail)
        self.assertIn(
            ("GET", XML_URL),
            [(call["method"], call["url"]) for call in transport.calls],
        )

    def test_landing_failure_continues_with_doi_derived_pdf_candidate(self) -> None:
        pdf_bytes = fulltext_pdf_bytes()
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): RequestFailure(
                    503, "landing unavailable", url=LANDING_URL
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, b"<html>not xml</html>", "text/html"
                ),
                ("GET", PDF_URL): http_response(PDF_URL, pdf_bytes, "application/pdf"),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )
        article = client.to_article_model({"doi": DOI}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertIn("fulltext:copernicus_landing_fail", article.quality.source_trail)
        self.assertIn("fulltext:copernicus_xml_fail", article.quality.source_trail)
        self.assertIn(
            "fulltext:copernicus_pdf_fallback_ok", article.quality.source_trail
        )
        self.assertIn(
            ("GET", PDF_URL),
            [(call["method"], call["url"]) for call in transport.calls],
        )

    def test_fulltext_failures_raise_for_metadata_fallback(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(pdf_url=""), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, b"<html>not xml</html>", "text/html"
                ),
                ("GET", PDF_URL): RequestFailure(404, "missing PDF", url=PDF_URL),
            }
        )
        client = CopernicusClient(transport, {})

        with self.assertRaises(ProviderFailure) as raised:
            client.fetch_raw_fulltext(
                DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
            )

        self.assertIn(
            "Copernicus XML route was not usable", raised.exception.warnings[0]
        )
        self.assertIn(
            "Copernicus PDF fallback was not usable", raised.exception.warnings[-1]
        )
        self.assertIn("fulltext:copernicus_xml_fail", raised.exception.source_trail)
        self.assertIn("fulltext:copernicus_pdf_fail", raised.exception.source_trail)

    def test_pdf_fallback_is_text_only_artifact_path(self) -> None:
        pdf_bytes = fulltext_pdf_bytes()
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, b"<html>not xml</html>", "text/html"
                ),
                ("GET", PDF_URL): http_response(PDF_URL, pdf_bytes, "application/pdf"),
            }
        )
        client = CopernicusClient(transport, {})

        result = client.fetch_result(
            DOI,
            {"doi": DOI, "landing_page_url": LANDING_URL},
            None,
            asset_profile="body",
        )

        self.assertEqual(result.article.source, "copernicus_pdf")
        self.assertTrue(result.artifacts.text_only)
        self.assertFalse(result.artifacts.allow_related_assets)
        self.assertIn(
            "download:copernicus_assets_skipped_text_only",
            [event.marker() for event in result.artifacts.skip_trace],
        )

    def test_pdf_fallback_uses_doi_derived_candidate_when_landing_omits_pdf_meta(
        self,
    ) -> None:
        pdf_bytes = fulltext_pdf_bytes()
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(pdf_url=""), "text/html"
                ),
                ("GET", XML_URL): http_response(
                    XML_URL, b"<html>not xml</html>", "text/html"
                ),
                ("GET", PDF_URL): http_response(PDF_URL, pdf_bytes, "application/pdf"),
            }
        )
        client = CopernicusClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
        )

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(raw_payload.source_url, PDF_URL)
        self.assertIn(
            ("GET", PDF_URL),
            [(call["method"], call["url"]) for call in transport.calls],
        )

    def test_xml_request_failures_continue_to_pdf_before_metadata_fallback(
        self,
    ) -> None:
        transport = RecordingTransport(
            {
                ("GET", LANDING_URL): http_response(
                    LANDING_URL, _landing_html(pdf_url=""), "text/html"
                ),
                ("GET", XML_URL): RequestFailure(503, "temporary outage", url=XML_URL),
                ("GET", PDF_URL): RequestFailure(404, "missing PDF", url=PDF_URL),
            }
        )
        client = CopernicusClient(transport, {})

        with self.assertRaises(ProviderFailure) as raised:
            client.fetch_raw_fulltext(
                DOI, {"doi": DOI, "landing_page_url": LANDING_URL}
            )

        self.assertTrue(
            any(
                "Copernicus XML route was not usable" in warning
                for warning in raised.exception.warnings
            )
        )
        self.assertIn(
            ("GET", PDF_URL),
            [(call["method"], call["url"]) for call in transport.calls],
        )

    def test_xml_renderer_extracts_core_jats_structures(self) -> None:
        """rule: rule-copernicus-xml-jats-rendering"""
        extraction = parse_copernicus_xml(
            _xml_fixture(), source_url=XML_URL, base_metadata={"doi": DOI}
        )
        generic_extraction = parse_jats_xml(
            _xml_fixture(), source_url=XML_URL, base_metadata={"doi": DOI}
        )

        self.assertIsNotNone(extraction)
        assert extraction is not None
        self.assertIsNotNone(generic_extraction)
        self.assertEqual(extraction.metadata["doi"], DOI)
        self.assertIn("Introduction", extraction.markdown_text)
        self.assertIn("$$", extraction.markdown_text)
        self.assertIn("| Season | Value |", extraction.markdown_text)
        self.assertNotIn("<article", extraction.markdown_text)
        self.assertTrue(
            [asset for asset in extraction.assets if asset["kind"] == "figure"]
        )
        self.assertTrue(
            [asset for asset in extraction.assets if asset["kind"] == "supplementary"]
        )
        self.assertEqual(extraction.references[0]["doi"], "10.1000/example")
        self.assertIn("Data availability", extraction.markdown_text)
        table_assets = [
            asset for asset in extraction.assets if asset["kind"] == "table"
        ]
        self.assertTrue(table_assets)
        self.assertEqual(table_assets[0]["table_render_kind"], "structured")

    def test_generic_jats_assets_preserve_alternatives_graphic_tables_and_nested_supplements(
        self,
    ) -> None:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <front><article-meta>
    <article-id pub-id-type="doi">{DOI}</article-id>
    <title-group><article-title>JATS asset variants</article-title></title-group>
  </article-meta></front>
  <body><sec><title>Results</title><p>{_article_body_text()}</p>
    <fig id="fig-multi"><label>Figure 2</label><caption><p>Two panels.</p></caption>
      <graphic xlink:href="panel-a.png" mimetype="image" mime-subtype="png"/>
      <inline-graphic xlink:href="panel-b.svg" mimetype="image" mime-subtype="svg+xml"/>
    </fig>
    <table-wrap id="table-graphic"><label>Table 2</label>
      <caption><p>Table supplied as an image.</p></caption>
      <graphic xlink:href="table-2.png" mimetype="image" mime-subtype="png"/>
    </table-wrap>
  </sec></body>
  <back><app-group><supplementary-material>
    <media xlink:href="data/supplement-1.csv" mimetype="text" mime-subtype="csv"/>
    <p>Nested file
      <inline-supplementary-material>
        <ext-link xlink:href="https://example.test/supplement-2.zip">archive</ext-link>
      </inline-supplementary-material>
    </p>
  </supplementary-material></app-group></back>
</article>
""".encode()

        extraction = parse_jats_xml(
            xml,
            source_url=XML_URL,
            base_metadata={"doi": DOI},
        )

        self.assertIsNotNone(extraction)
        assert extraction is not None
        figure = next(
            asset
            for asset in extraction.assets
            if asset["kind"] == "figure" and asset["key"] == "fig-multi"
        )
        self.assertEqual(
            [alternative["url"] for alternative in figure["alternatives"]],
            [
                "https://acp.copernicus.org/articles/24/1/2024/panel-a.png",
                "https://acp.copernicus.org/articles/24/1/2024/panel-b.svg",
            ],
        )
        self.assertEqual(
            [alternative["panel_index"] for alternative in figure["alternatives"]],
            [1, 2],
        )
        graphic_table = next(
            asset
            for asset in extraction.assets
            if asset["kind"] == "table" and asset["key"] == "table-graphic"
        )
        self.assertEqual(graphic_table["table_render_kind"], "fallback")
        self.assertEqual(
            graphic_table["alternatives"][0]["url"],
            "https://acp.copernicus.org/articles/24/1/2024/table-2.png",
        )
        supplements = [
            asset for asset in extraction.assets if asset["kind"] == "supplementary"
        ]
        self.assertEqual(
            {asset["source_href"] for asset in supplements},
            {
                "data/supplement-1.csv",
                "https://example.test/supplement-2.zip",
            },
        )


if __name__ == "__main__":
    unittest.main()
