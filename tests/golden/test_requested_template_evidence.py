"""Unmodified originals collected while reviewing removal of speculative routes."""

from urllib.parse import urlsplit
from unittest import mock

import pytest
from bs4 import BeautifulSoup
from paper_fetch.extraction.image_payloads import image_dimensions_from_bytes

from paper_fetch.providers import _springer_html as springer_html
from paper_fetch.providers import springer as springer_provider
from paper_fetch.providers.acs import AcsClient
from paper_fetch.providers.royalsocietypublishing import RoyalsocietypublishingClient
from paper_fetch.providers.science import ScienceClient
from paper_fetch.runtime import RuntimeContext
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from tests.support._paper_fetch_support import FixtureHtmlTransport
from tests.support.acquired_publisher_inputs import _record
from tests.support.acquired_publisher_inputs import _response
from tests.support.captured_images import download_captured_images

SPRINGER_CAPTURE = "acquisition/requested-templates-2026-09-16/article-response.html"
SCIENCE_CAPTURE = "acquisition/template-browser-user-retry-2026-09-16/"


@pytest.mark.parametrize(
    "doi,client_type",
    [
        ("10.1021/acsomega.4c03987", AcsClient),
        ("10.1098/rsta.2019.0558", RoyalsocietypublishingClient),
    ],
)
def test_original_silverchair_article_requires_downloadimage_unwrapping(
    doi, client_type
):
    record, body = _record(
        doi, "acquisition/template-browser-2026-09-16/000-browser_rendered_dom.html"
    )
    soup = BeautifulSoup(body, "lxml")
    figure = soup.select_one(".fig-section:not(.fig-modal)")
    wrapper = figure.select_one('a[href*="DownloadImage.aspx"]')
    assert wrapper is not None
    client = client_type(FixtureHtmlTransport({}), {})
    assert client.profile.figure_page_discovery is (
        client.name == "royalsocietypublishing"
    )
    if client.name == "royalsocietypublishing":
        _, extraction = client.extract_markdown(
            body.decode(), record["requested_url"], metadata={"doi": doi}
        )
        assets = extraction["extracted_assets"]
    else:
        with RuntimeContext(env={}) as context:
            assets = client.deps._cached_browser_workflow_assets(
                client,
                body.decode(),
                record["requested_url"],
                asset_profile="body",
                context=context,
            )
    # Table graphics are also figure assets. Match the source wrapper under
    # test instead of assuming its figure is first in discovery order.
    matches = [
        a
        for a in assets
        if a.get("kind") == "figure"
        and a.get("full_size_url")
        and urlsplit(a["full_size_url"]).path in wrapper["href"]
    ]
    assert len(matches) == 1
    asset = matches[0]
    original_path = urlsplit(asset["full_size_url"]).path
    assert original_path in wrapper["href"]
    assert urlsplit(asset["preview_url"]).path != original_path
    # The original is present only inside DownloadImage. The earlier review
    # incorrectly treated the separate viewer's direct image as an article link.
    assert not any(
        original_path in str(tag.get(attr, ""))
        and "DownloadImage.aspx" not in str(tag.get(attr, ""))
        for tag in soup.find_all(True)
        for attr in (
            "src",
            "data-src",
            "srcset",
            "data-srcset",
            "href",
            "data-hi-res-src",
        )
    )


def _springer_original(doi):
    record, body = _record(doi, SPRINGER_CAPTURE)
    assert record["status_code"] == 200
    html = body.decode()
    metadata = springer_html.parse_html_metadata(html, record["requested_url"])
    assert metadata["doi"] == doi
    extraction = springer_html.extract_html_payload(
        html, record["requested_url"], title=metadata["title"]
    )
    return record, html, metadata, extraction["markdown_text"]


@pytest.mark.parametrize("entrypoint", ["raw", "prepared"])
def test_current_springer_early_article_notice_requests_pdf_fallback(entrypoint):
    record, html, metadata, markdown = _springer_original("10.1038/s41419-026-09210-1")
    soup = BeautifulSoup(html, "lxml")
    notice = soup.select_one(".c-status-message")
    assert "This version is subject to further edits" in notice.get_text(
        " ", strip=True
    )
    assert not soup.select_one(".main-content").get_text(" ", strip=True)
    assert "## Abstract" in markdown
    assert "## Results" not in markdown
    diagnostics = assess_html_fulltext_availability(
        markdown,
        metadata,
        provider="springer",
        html_text=html,
        title=metadata["title"],
        final_url=record["requested_url"],
    )
    assert not diagnostics.accepted
    assert "post_abstract_body_run" not in diagnostics.strong_positive_signals
    pdf_link = soup.select_one('meta[name="citation_pdf_url"]')["content"]
    transport = FixtureHtmlTransport(
        {record["requested_url"]: _response(record, html.encode())}
    )
    client = springer_provider.SpringerClient(transport, {})
    metadata["landing_page_url"] = record["requested_url"]
    # Stop at the PDF boundary: this proves routing, not PDF download or conversion.
    with (
        RuntimeContext(env={}, transport=transport) as context,
        mock.patch.object(
            springer_provider,
            "fetch_pdf_over_http",
            side_effect=RuntimeError("observed PDF route"),
        ) as fetch_pdf,
        pytest.raises(RuntimeError, match="observed PDF route"),
    ):
        if entrypoint == "raw":
            client.fetch_raw_fulltext(metadata["doi"], metadata, context=context)
        else:
            prepared = client.prepare_fetch_result_payload(
                metadata["doi"], metadata, asset_profile="none", context=context
            )
            attempt = prepared.context["pdf_attempt"]
            assert not attempt.diagnostics.accepted
            assert attempt.html_text == html
            client.maybe_recover_fetch_result_payload(
                metadata["doi"],
                metadata,
                prepared,
                asset_profile="none",
                context=context,
            )
    fetch_pdf.assert_called_once()
    assert pdf_link in fetch_pdf.call_args.args[1]
    assert fetch_pdf.call_args.kwargs["expected_identity"] == {
        "doi": metadata["doi"],
        "title": metadata["title"],
    }


def test_original_2018_nature_unsectioned_blocks_keep_source_order():
    _, html, _, markdown = _springer_original("10.1038/s41556-018-0103-6")
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one(".main-content")
    blocks = main.find_all("div", recursive=False)
    assert len(blocks) == 8
    assert main.find("section", recursive=False) is None
    positions = []
    for block in blocks:
        paragraph = block.find("p")
        original = paragraph.get_text(" ", strip=True)
        # A literal prefix precedes citation/link markup in these source paragraphs.
        prefix = original.split(".", 1)[0][:90]
        assert markdown.count(prefix) == 1
        positions.append(markdown.index(prefix))
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    "doi", ["10.1038/s41467-019-11472-7", "10.1038/s41467-018-07899-z"]
)
def test_original_old_nature_body_and_availability_follow_source_order(doi):
    _, html, _, markdown = _springer_original(doi)
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one(".main-content")
    assert main.find("section", recursive=False) is not None
    positions = []
    for section in main.find_all("section", recursive=False):
        title = section["data-title"]
        assert markdown.count("\n## " + title + "\n") == 1
        positions.append(markdown.index("\n## " + title + "\n"))
    assert positions == sorted(positions)
    assert markdown.count("\n## Data availability\n") == 1
    assert markdown.lower().count("reporting summary") >= 1
    assert positions[-1] < markdown.index("\n## Data availability\n")


@pytest.mark.parametrize(
    "capture,dom_file,image_file",
    [
        (SCIENCE_CAPTURE, "000-browser_rendered_dom.html", "001-direct_http.jpg"),
        (
            "acquisition/template-browser-repeat4-2026-09-16/",
            "001-browser_rendered_dom.html",
            "000-direct_http.jpg",
        ),
    ],
)
def test_original_science_image_and_native_canvas_are_separate_evidence(
    tmp_path, capture, dom_file, image_file
):
    doi = "10.1126/science.abo2812"
    dom_record, dom = _record(doi, capture + dom_file)
    image_record, original = _record(doi, capture + image_file)
    canvas_record, canvas = _record(doi, capture + "002-browser_canvas_export.png")
    if capture != SCIENCE_CAPTURE:
        assert image_record["captured_at_utc"] < dom_record["captured_at_utc"]
        assert dom_record["captured_at_utc"] < canvas_record["captured_at_utc"]
    assert image_record["status_code"] == 200
    assert canvas_record["status_code"] is None
    assert canvas_record["capture_kind"] == "browser_canvas_export"
    assert canvas_record["requested_url"] == image_record["requested_url"]
    assert image_dimensions_from_bytes(original) == (4325, 2111)
    assert image_dimensions_from_bytes(canvas) == (4325, 2111)
    metadata = springer_html.parse_html_metadata(
        dom.decode(), dom_record["requested_url"]
    )
    assert metadata["doi"] == doi
    client = ScienceClient(FixtureHtmlTransport({}), {})
    with RuntimeContext(env={}) as context:
        assets = client.deps._cached_browser_workflow_assets(
            client,
            dom.decode(),
            dom_record["requested_url"],
            asset_profile="body",
            context=context,
        )
    figure = next(
        a
        for a in assets
        if a.get("kind") == "figure"
        and a.get("full_size_url") == image_record["requested_url"]
    )
    downloaded = download_captured_images(doi, [figure], tmp_path)
    assert len(downloaded) == 1
    assert downloaded[0]["downloaded_bytes"] == len(original)
    # A successful canvas export does not turn the actual HTTP200 into a challenge.
    assert downloaded[0]["download_tier"] == "full_size"


def test_original_royal_missing_original_downloads_from_its_actual_viewer(tmp_path):
    from pathlib import Path
    from unittest import mock
    from paper_fetch.providers import browser_runtime
    from paper_fetch.providers.browser_runtime import BrowserRuntimeConfig
    from paper_fetch.extraction.html.assets.figures import (
        extract_full_size_figure_image_url,
    )
    from tests.support._atypon_browser_workflow_provider_support import (
        _typed_raw_payload,
    )
    from tests.support._browser_workflow_deps import install_browser_workflow_deps
    from tests.support.acquired_publisher_inputs import _response
    from functools import partial
    from tests.support.acquired_publisher_inputs import capture_url_identity

    _identity = partial(capture_url_identity, provider="royalsocietypublishing")

    doi = "10.1098/rsos.150470"
    capture = "acquisition/requested-viewer-missing-2026-09-16/"
    article_record, original = _record(doi, capture + "000-browser_rendered_dom.html")
    viewer_record, viewer = _record(doi, capture + "001-browser_rendered_dom.html")
    http_record, _ = _record(doi, capture + "004-http_response_entity.html")
    image_record, image = _record(doi, capture + "002-direct_http.jpeg")
    assert http_record["status_code"] == image_record["status_code"] == 200
    candidate = extract_full_size_figure_image_url(
        viewer.decode(), viewer_record["final_url"]
    )
    # The original DOM and downloaded response differ only in expiring CDN signatures.
    assert _identity(candidate) == _identity(image_record["requested_url"])
    client = RoyalsocietypublishingClient(
        FixtureHtmlTransport({candidate: _response(image_record, image)}),
        {},
    )
    metadata = springer_html.parse_html_metadata(
        original.decode(), article_record["requested_url"]
    )
    assert metadata["doi"] == doi
    markdown, extraction = client.extract_markdown(
        original.decode(), article_record["requested_url"], metadata=metadata
    )
    figure = next(
        a for a in extraction["extracted_assets"] if a.get("heading") == "Figure 2"
    )
    assert not figure.get("full_size_url")
    assert figure["figure_page_url"] == viewer_record["requested_url"]
    assert "rsos150470f02.jpeg" in image_record["requested_url"]
    fetch_viewer = mock.Mock(
        return_value=browser_runtime.BrowserFetchedHtml(
            source_url=viewer_record["requested_url"],
            final_url=viewer_record["final_url"],
            html=viewer.decode(),
            response_status=http_record["status_code"],
            response_headers=http_record["response_headers"],
            title=BeautifulSoup(viewer, "lxml").title.get_text(strip=True),
            summary="",
            browser_context_seed={},
        )
    )
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(
            return_value=BrowserRuntimeConfig(
                provider=client.name,
                doi=doi,
                artifact_dir=tmp_path,
                headless=True,
                user_agent="test",
            )
        ),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=fetch_viewer,
        _build_shared_browser_image_fetcher=mock.Mock(return_value=None),
    )
    raw = _typed_raw_payload(
        provider=client.name,
        source_url=article_record["requested_url"],
        content_type="text/html",
        body=original,
        route="html",
        markdown_text=markdown,
        extraction=extraction,
        browser_context_seed={},
    )
    result = client._download_browser_backed_related_assets(
        doi, metadata, raw, tmp_path, asset_profile="body", assets=[figure]
    )
    assert result["asset_failures"] == []
    assert len(result["assets"]) == 1
    downloaded = result["assets"][0]
    assert downloaded["download_tier"] == "full_size"
    assert Path(downloaded["path"]).read_bytes() == image
    fetch_viewer.assert_called_once()
    assert fetch_viewer.call_args.args[0] == [figure["figure_page_url"]]
    article = client.to_article_model(metadata, raw, downloaded_assets=result["assets"])
    rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    assert rendered.count(f"]({downloaded['path']})") == 1
