from __future__ import annotations

from dataclasses import replace
from pathlib import Path

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


def _frontiers_xml() -> bytes:
    body = " ".join(
        [
            "Frontiers XML full text includes reproducible article body content, methods, results, and discussion.",
            "The sediment functioning experiment reports macrofauna survival, oxygen fluxes, and nutrient cycling.",
        ]
        * 18
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
      <table-wrap id="t1">
        <label>Table 1</label>
        <caption><p>Experimental seawater temperature conditions.</p></caption>
        <table>
          <thead><tr><th>Variable</th><th>Low</th><th>High</th></tr></thead>
          <tbody><tr><td>seawater temperature</td><td>16</td><td>20</td></tr></tbody>
        </table>
      </table-wrap>
    </sec>
    <sec id="s2">
      <title>Results</title>
      <p>The Frontiers XML parser should preserve result paragraphs and references.</p>
    </sec>
    <sec id="s10" sec-type="supplementary-material">
      <title>Supplementary material</title>
      <p>The Supplementary Material for this article can be found online.</p>
      <supplementary-material xlink:href="Table_1.docx" id="SM1" mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"/>
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
    assert "| Variable | Low | High |" in markdown
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
    assert article.metadata.journal == "Frontiers in Marine Science"
    assert article.assets[0].original_url == IMAGE_URL


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
