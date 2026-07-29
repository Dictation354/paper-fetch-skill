from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from paper_fetch.providers.frontiers import FrontiersClient
from paper_fetch.reason_codes import PDF_FALLBACK
from tests.unit._atypon_browser_workflow_provider_support import png_header
from tests.unit._paper_fetch_support import (
    FixtureHtmlTransport,
    fulltext_pdf_bytes,
    http_response,
)


DOI = "10.3389/fmars.2023.1101972"
LEGACY_FULL_URL = f"https://www.frontiersin.org/articles/{DOI}/full"
CANONICAL_FULL_URL = (
    f"https://www.frontiersin.org/journals/marine-science/articles/{DOI}/full"
)
XML_URL = f"https://www.frontiersin.org/journals/marine-science/articles/{DOI}/xml"
PDF_URL = f"https://www.frontiersin.org/journals/marine-science/articles/{DOI}/pdf"
IMAGE_URL = "https://www.frontiersin.org/files/Articles/1101972/xml-images/fmars-10-1101972-g001.webp"
SUPPLEMENT_URL = (
    "https://www.frontiersin.org/files/Articles/1101972/supplementary-material/"
    "Table_1.docx"
)


def _landing_html() -> bytes:
    return f"""<!doctype html>
<html>
  <head>
    <title>Frontiers | Ocean acidification and warming modify stimulatory benthos effects</title>
    <meta name="citation_doi" content="{DOI}">
    <meta name="citation_title" content="Ocean acidification and warming modify stimulatory benthos effects">
    <meta name="citation_journal_title" content="Frontiers in Marine Science">
    <meta name="citation_pdf_url" content="{PDF_URL}">
    <meta property="og:url" content="{CANONICAL_FULL_URL}">
  </head>
  <body><main class="ArticleDetailsV4__main">Frontiers article page</main></body>
</html>
""".encode()


def _frontiers_xml(
    *,
    table_xml: str | None = None,
    supplementary_href: str = "Table_1.docx",
) -> bytes:
    body = " ".join(
        [
            "Frontiers XML full text includes reproducible article body content, methods, results, and discussion.",
            "The sediment functioning experiment reports macrofauna survival, oxygen fluxes, and nutrient cycling.",
        ]
        * 18
    )
    table_xml = (
        table_xml
        or """
      <table-wrap id="t1">
        <label>Table 1</label>
        <caption><p>Experimental seawater temperature conditions.</p></caption>
        <table>
          <thead>
            <tr><th colspan="3"><italic>Lanice conchilega</italic></th></tr>
          </thead>
          <tbody>
            <tr><th>Variable</th><th>Low</th><th>High</th></tr>
            <tr><td>seawater temperature</td><td>16</td><td>20</td></tr>
            <tr><th colspan="3"><italic>Abra alba</italic></th></tr>
            <tr><td>salinity</td><td>34</td><td>35</td></tr>
          </tbody>
        </table>
      </table-wrap>
"""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article">
  <front>
    <journal-meta>
      <journal-title>Frontiers in Marine Science</journal-title>
      <publisher><publisher-name>Frontiers Media S.A.</publisher-name></publisher>
    </journal-meta>
    <article-meta>
      <article-id pub-id-type="doi">{DOI}</article-id>
      <title-group>
        <article-title>Ocean acidification and warming modify stimulatory benthos effects</article-title>
      </title-group>
      <contrib-group>
        <contrib contrib-type="author"><name><given-names>Ellen</given-names><surname>Vlaminck</surname></name></contrib>
        <contrib contrib-type="author"><name><given-names>Tom</given-names><surname>Moens</surname></name></contrib>
      </contrib-group>
      <pub-date pub-type="epub"><day>20</day><month>02</month><year>2023</year></pub-date>
      <abstract><p>Many macrofauna have a stimulatory effect on sediment functioning.</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec id="s1">
      <title>Introduction</title>
      <p>{body}</p>
      <fig id="f1">
        <label>Figure 1</label>
        <caption><p>Effects of temperature and pH on survival rate.</p></caption>
        <graphic mimetype="image" mime-subtype="tiff" xlink:href="fmars-10-1101972-g001.tif"/>
      </fig>
      {table_xml}
    </sec>
    <sec id="s2">
      <title>Results</title>
      <p>The Frontiers XML parser should preserve result paragraphs and references.</p>
    </sec>
    <sec id="s10" sec-type="supplementary-material">
      <title>Supplementary material</title>
      <p>The Supplementary Material for this article can be found online.</p>
      <supplementary-material xlink:href="{supplementary_href}" id="SM1" mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"/>
    </sec>
  </body>
  <back>
    <ref-list>
      <ref id="B1"><label>1</label><mixed-citation>Example A. Frontiers reference title. 2023.</mixed-citation></ref>
    </ref-list>
  </back>
</article>
""".encode()


def _frontiers_transport(
    extra: dict[str, dict[str, object]] | None = None,
) -> FixtureHtmlTransport:
    responses: dict[str, dict[str, object]] = {
        LEGACY_FULL_URL: http_response(
            LEGACY_FULL_URL,
            b"",
            "text/html",
            status_code=302,
            headers={"location": CANONICAL_FULL_URL},
        ),
        CANONICAL_FULL_URL: http_response(
            CANONICAL_FULL_URL, _landing_html(), "text/html"
        ),
    }
    responses.update(extra or {})
    return FixtureHtmlTransport(responses)


def test_frontiers_xml_route_fetches_canonical_jats_and_rewrites_figure_url() -> None:
    transport = _frontiers_transport(
        {XML_URL: http_response(XML_URL, _frontiers_xml(), "text/xml")}
    )
    client = FrontiersClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})
    article = client.to_article_model({"doi": DOI}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "xml"
    assert raw_payload.content.merged_metadata["landing_page_url"] == CANONICAL_FULL_URL
    assert raw_payload.content.source_url == XML_URL
    markdown = raw_payload.content.markdown_text or ""
    rendered_markdown = article.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    # markdown-review: purpose=structure doi=10.3389/fmars.2023.1101972
    # markdown-review: purpose=table doi=10.3389/fmars.2023.1101972
    # markdown-review: purpose=figure doi=10.3389/fmars.2023.1101972
    # markdown-review: purpose=supplementary doi=10.3389/fmars.2023.1101972
    # markdown-review: purpose=references doi=10.3389/fmars.2023.1101972
    assert "## Abstract" in rendered_markdown
    assert (
        "Ocean acidification and warming modify stimulatory benthos effects"
        in rendered_markdown
    )
    assert "seawater temperature" in markdown
    assert re.search(r"(?m)^\|\s*Variable\s*\|\s*Low\s*\|\s*High\s*\|", markdown)
    assert re.search(r"(?m)^\*Lanice conchilega\*$", markdown)
    assert not re.search(r"(?m)^\|\s*\*Lanice conchilega\*\s*\|\s*\|\s*\|", markdown)
    assert re.search(r"(?m)^\|\s*\*Abra alba\*\s*\|\s*\|\s*\|", markdown)
    lanice_row = markdown.index("*Lanice conchilega*")
    temperature_row = markdown.index("| seawater temperature")
    abra_row = markdown.index("| *Abra alba*")
    salinity_row = markdown.index("| salinity")
    assert lanice_row < temperature_row < abra_row < salinity_row
    assert "Effects of temperature and pH" in markdown
    assert "Supplementary material" in markdown
    assert "Frontiers reference title" in rendered_markdown
    assert IMAGE_URL in markdown
    assert "Download PDF" not in rendered_markdown
    assert "Article metrics" not in rendered_markdown
    assert "Google Scholar" not in rendered_markdown
    assert "fmars-10-1101972-g001.tif" not in markdown
    assert "fulltext:frontiers_xml_ok" in article.quality.source_trail
    assert article.source == "frontiers_xml"
    assert article.quality.content_kind == "fulltext"
    assert article.quality.semantic_losses.table_layout_degraded_count == 0
    assert article.quality.semantic_losses.table_semantic_loss_count == 0
    assert "table_layout_degraded" not in article.quality.flags
    assert not any(
        "merged-cell structure" in warning for warning in article.quality.warnings
    )
    assert article.metadata.journal == "Frontiers in Marine Science"
    assert article.assets[0].original_url == IMAGE_URL


def test_frontiers_canonical_xml_route_does_not_request_landing_page() -> None:
    transport = FixtureHtmlTransport(
        {XML_URL: http_response(XML_URL, _frontiers_xml(), "text/xml")}
    )
    client = FrontiersClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(
        DOI,
        {"doi": DOI, "landing_page_url": CANONICAL_FULL_URL},
    )

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == "xml"
    assert [call["url"] for call in transport.calls] == [XML_URL]
    assert raw_payload.content.diagnostics is not None
    assert raw_payload.content.diagnostics["route_discovery"] == {
        "reason": "metadata_canonical",
        "landing_requested": False,
    }


def test_frontiers_direct_pdf_fallback_does_not_request_landing_page() -> None:
    transport = FixtureHtmlTransport(
        {
            XML_URL: http_response(
                XML_URL,
                b"<!doctype html><html>Not XML</html>",
                "text/html",
            ),
            PDF_URL: http_response(
                PDF_URL,
                fulltext_pdf_bytes(),
                "application/pdf",
            ),
        }
    )
    client = FrontiersClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(
        DOI,
        {"doi": DOI, "landing_page_url": CANONICAL_FULL_URL},
    )

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == PDF_FALLBACK
    assert [call["url"] for call in transport.calls] == [XML_URL, PDF_URL]
    assert raw_payload.content.diagnostics is not None
    assert raw_payload.content.diagnostics["route_discovery"] == {
        "reason": "metadata_canonical",
        "landing_requested": False,
    }


def test_frontiers_jats_semantically_expands_non_global_table_spans() -> None:
    table_xml = """
      <table-wrap id="t1">
        <label>Table 1</label>
        <caption><p>Span conversion example.</p></caption>
        <table>
          <thead>
            <tr>
              <th rowspan="2">Metric</th>
              <th colspan="2">Period</th>
            </tr>
            <tr><th>Low</th><th>High</th></tr>
          </thead>
          <tbody>
            <tr><td rowspan="2">CO<sub>2</sub></td><td>1</td><td>2</td></tr>
            <tr><td>3</td><td>4</td></tr>
          </tbody>
        </table>
      </table-wrap>
"""
    transport = _frontiers_transport(
        {
            XML_URL: http_response(
                XML_URL,
                _frontiers_xml(table_xml=table_xml),
                "text/xml",
            )
        }
    )
    client = FrontiersClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})
    article = client.to_article_model({"doi": DOI}, raw_payload)

    assert raw_payload.content is not None
    markdown = raw_payload.content.markdown_text or ""
    assert re.search(
        r"(?m)^\|\s*Metric\s*\|\s*Period / Low\s*\|\s*Period / High\s*\|",
        markdown,
    )
    assert re.search(r"(?m)^\|\s*CO<sub>2</sub>\s*\|\s*1\s*\|\s*2\s*\|", markdown)
    assert re.search(r"(?m)^\|\s*CO<sub>2</sub>\s*\|\s*3\s*\|\s*4\s*\|", markdown)
    assert article.quality.semantic_losses.table_layout_degraded_count == 1
    assert article.quality.semantic_losses.table_semantic_loss_count == 0
    assert "table_layout_degraded" in article.quality.flags
    assert "table_semantic_loss" not in article.quality.flags
    assert raw_payload.content.diagnostics is not None
    assert raw_payload.content.diagnostics["extraction"]["conversion_notes"] == [
        "- Table 1: Merged table spans were semantically expanded into rectangular Markdown cells; rowspan/colspan layout fidelity was reduced."
    ]


def test_frontiers_jats_supports_cals_named_table_spans() -> None:
    table_xml = """
      <table-wrap id="t1">
        <label>Table 1</label>
        <caption><p>CALS named span example.</p></caption>
        <table>
          <tgroup cols="3">
            <colspec colname="c1"/>
            <colspec colname="c2"/>
            <colspec colname="c3"/>
            <thead>
              <row>
                <entry colname="c1" morerows="1">Metric</entry>
                <entry namest="c2" nameend="c3">Period</entry>
              </row>
              <row>
                <entry colname="c2">Low</entry>
                <entry colname="c3">High</entry>
              </row>
            </thead>
            <tbody>
              <row>
                <entry colname="c1">CO<sub>2</sub></entry>
                <entry colname="c2">1</entry>
                <entry colname="c3">2</entry>
              </row>
            </tbody>
          </tgroup>
        </table>
      </table-wrap>
"""
    transport = _frontiers_transport(
        {
            XML_URL: http_response(
                XML_URL,
                _frontiers_xml(table_xml=table_xml),
                "text/xml",
            )
        }
    )
    client = FrontiersClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})
    article = client.to_article_model({"doi": DOI}, raw_payload)

    assert raw_payload.content is not None
    markdown = raw_payload.content.markdown_text or ""
    assert re.search(
        r"(?m)^\|\s*Metric\s*\|\s*Period / Low\s*\|\s*Period / High\s*\|",
        markdown,
    )
    assert re.search(
        r"(?m)^\|\s*CO<sub>2</sub>\s*\|\s*1\s*\|\s*2\s*\|",
        markdown,
    )
    assert article.quality.semantic_losses.table_layout_degraded_count == 1
    assert article.quality.semantic_losses.table_fallback_count == 0
    assert article.quality.semantic_losses.table_semantic_loss_count == 0


def test_frontiers_jats_headerless_invalid_span_keeps_first_data_row() -> None:
    table_xml = """
      <table-wrap id="t1">
        <label>Table 1</label>
        <caption><p>Headerless malformed span example.</p></caption>
        <table>
          <tbody>
            <tr><td rowspan="invalid">first row</td><td>1</td></tr>
            <tr><td>second row</td><td>2</td></tr>
          </tbody>
        </table>
      </table-wrap>
"""
    transport = _frontiers_transport(
        {
            XML_URL: http_response(
                XML_URL,
                _frontiers_xml(table_xml=table_xml),
                "text/xml",
            )
        }
    )
    client = FrontiersClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})
    article = client.to_article_model({"doi": DOI}, raw_payload)

    assert raw_payload.content is not None
    markdown = raw_payload.content.markdown_text or ""
    assert re.search(r"(?m)^\|\s*\|\s*\|$", markdown)
    assert re.search(r"(?m)^\|\s*first row\s*\|\s*1\s*\|", markdown)
    assert re.search(r"(?m)^\|\s*second row\s*\|\s*2\s*\|", markdown)
    assert article.quality.semantic_losses.table_layout_degraded_count == 1
    assert article.quality.semantic_losses.table_semantic_loss_count == 0


def test_frontiers_asset_download_resolves_xml_image_filename(tmp_path: Path) -> None:
    image_body = png_header(8, 8) + b"frontiers-figure"
    transport = _frontiers_transport(
        {
            XML_URL: http_response(XML_URL, _frontiers_xml(), "text/xml"),
            IMAGE_URL: http_response(IMAGE_URL, image_body, "image/webp"),
        }
    )
    client = FrontiersClient(transport, {})
    raw_payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})
    article = client.to_article_model({"doi": DOI}, raw_payload)
    first_figure = next(
        asset.__dict__ for asset in article.assets if asset.kind == "figure"
    )
    raw_payload.content = replace(raw_payload.content, extracted_assets=[first_figure])

    # asset-download-contract: provider=frontiers
    result = client.download_related_assets(
        DOI,
        {"doi": DOI},
        raw_payload,
        tmp_path,
        asset_profile="body",
    )

    assert result["asset_failures"] == []
    assert result["assets"][0]["download_url"] == IMAGE_URL
    assert result["assets"][0]["downloaded_bytes"] == len(image_body)
    path = Path(result["assets"][0]["path"])
    assert path.read_bytes() == image_body

    article_with_assets = client.to_article_model(
        {"doi": DOI},
        raw_payload,
        downloaded_assets=result["assets"],
    )
    rendered = article_with_assets.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    assert f"![Figure 1]({path})" in rendered
    assert IMAGE_URL not in rendered


def test_frontiers_supplementary_assets_respect_profile_and_archive_state(
    tmp_path: Path,
) -> None:
    supplement_body = b"PK\x03\x04frontiers-supplement"
    transport = FixtureHtmlTransport(
        {
            XML_URL: http_response(
                XML_URL,
                _frontiers_xml(supplementary_href=SUPPLEMENT_URL),
                "text/xml",
            ),
            SUPPLEMENT_URL: http_response(
                SUPPLEMENT_URL,
                supplement_body,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        }
    )
    client = FrontiersClient(transport, {})
    raw_payload = client.fetch_raw_fulltext(
        DOI,
        {"doi": DOI, "landing_page_url": CANONICAL_FULL_URL},
    )
    assert raw_payload.content is not None
    supplement = next(
        asset
        for asset in raw_payload.content.extracted_assets
        if asset.get("kind") == "supplementary"
    )
    raw_payload.content = replace(
        raw_payload.content,
        extracted_assets=[supplement],
    )

    body_result = client.download_related_assets(
        DOI,
        {"doi": DOI},
        raw_payload,
        tmp_path / "body",
        asset_profile="body",
    )
    all_result = client.download_related_assets(
        DOI,
        {"doi": DOI},
        raw_payload,
        tmp_path / "all",
        asset_profile="all",
    )

    assert body_result == {"assets": [], "asset_failures": []}
    assert all_result["asset_failures"] == []
    assert all_result["assets"][0]["download_url"] == SUPPLEMENT_URL
    assert all_result["assets"][0]["downloaded_bytes"] == len(supplement_body)
    assert Path(all_result["assets"][0]["path"]).read_bytes() == supplement_body
    assert [call["url"] for call in transport.calls].count(SUPPLEMENT_URL) == 1


def test_frontiers_unresolved_supplementary_asset_maps_to_landing_anchor(
    tmp_path: Path,
) -> None:
    transport = FixtureHtmlTransport(
        {XML_URL: http_response(XML_URL, _frontiers_xml(), "text/xml")}
    )
    client = FrontiersClient(transport, {})
    raw_payload = client.fetch_raw_fulltext(
        DOI,
        {"doi": DOI, "landing_page_url": CANONICAL_FULL_URL},
    )

    assert raw_payload.content is not None
    supplement = next(
        asset
        for asset in raw_payload.content.extracted_assets
        if asset.get("kind") == "supplementary"
    )
    assert supplement["archive_state"] == "not_archived"
    assert supplement["link"] == f"{CANONICAL_FULL_URL}#supplementary-material"
    raw_payload.content = replace(
        raw_payload.content,
        extracted_assets=[supplement],
    )

    result = client.download_related_assets(
        DOI,
        {"doi": DOI},
        raw_payload,
        tmp_path,
        asset_profile="all",
    )

    assert result["assets"] == []
    assert result["asset_failures"] == [
        {
            "kind": "supplementary",
            "heading": "Supplementary material",
            "source_url": "Table_1.docx",
            "section": "supplementary",
            "reason": (
                "Frontiers supplementary entry did not expose a downloadable URL."
            ),
            "archive_state": "not_archived",
        }
    ]
    assert [call["url"] for call in transport.calls] == [XML_URL]


def test_frontiers_pdf_fallback_rejects_html_xml_candidate() -> None:
    transport = _frontiers_transport(
        {
            XML_URL: http_response(
                XML_URL, b"<!doctype html><html>Not XML</html>", "text/html"
            ),
            PDF_URL: http_response(PDF_URL, fulltext_pdf_bytes(), "application/pdf"),
        }
    )
    client = FrontiersClient(transport, {})

    raw_payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})
    article = client.to_article_model({"doi": DOI}, raw_payload)

    assert raw_payload.content is not None
    assert raw_payload.content.route_kind == PDF_FALLBACK
    markdown = raw_payload.content.markdown_text or ""
    # markdown-review: purpose=pdf_fallback doi=10.3389/fmars.2023.1101972
    assert "Abstract" in markdown
    assert "Access Denied" not in markdown
    assert article.source == "frontiers_pdf"
    assert "fulltext:frontiers_xml_fail" in article.quality.source_trail
    assert "fulltext:frontiers_pdf_fallback_ok" in article.quality.source_trail


def test_frontiers_catalog_routes_domain_publisher_and_doi_signals() -> None:
    from paper_fetch import publisher_identity
    from paper_fetch.provider_catalog import PROVIDER_CATALOG, provider_for_source

    spec = PROVIDER_CATALOG["frontiers"]
    assert spec.domains == ("www.frontiersin.org", "frontiersin.org")
    assert "10.3389/" in spec.doi_prefixes
    assert publisher_identity.infer_provider_from_doi(DOI) == "frontiers"
    assert publisher_identity.infer_provider_from_url(CANONICAL_FULL_URL) == "frontiers"
    assert (
        publisher_identity.infer_provider_from_publisher("Frontiers Media S.A.")
        == "frontiers"
    )
    assert provider_for_source("frontiers_xml") == "frontiers"
    assert provider_for_source("frontiers_pdf") == "frontiers"
