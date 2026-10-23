"""Minimal Oxford DOM ownership, rendition selection and fallback contracts."""

from collections import Counter
from pathlib import Path
from urllib.parse import quote

import pytest

from paper_fetch.models import FetchEnvelope
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from paper_fetch.quality.assets import build_asset_quality_summary
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._atypon_browser_workflow_provider_support import png_header
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response
from tests.support.oxford_html import build_oxford_html_payload

URL = "https://academic.oup.com/example/article/1"
PREVIEW = "https://oup.silverchair-cdn.com/paper/m_f1.png?Signature=preview&Expires=1"
ORIGINAL = "https://oup.silverchair-cdn.com/paper/f1.png?Signature=original&Expires=2"


def figure_html(original=ORIGINAL):
    control = (
        f'<a href="/DownloadFile/DownloadImage.aspx?image={original}">Download slide</a>'
        if original
        else ""
    )
    return f'''<article><h2>Results</h2><p>{"Body evidence. " * 50}</p>
      <div class="fig fig-section" id="f1"><figure>
      <div class="graphic-wrap"><img src="{PREVIEW}" alt="Figure 1"></div>
      <figcaption><span class="fig-label">Figure 1.</span> Source caption.</figcaption></figure>{control}</div>
      <p>After figure.</p></article>'''


@pytest.mark.parametrize("mode", ["original", "fallback", "preview_only", "failed"])
def test_one_owned_image_downloads_original_then_only_its_preview(tmp_path, mode):
    original = "" if mode == "preview_only" else ORIGINAL
    payload = build_oxford_html_payload(figure_html(original), URL, "10.1093/example")
    assets = payload.content.extracted_assets
    assert len(assets) == 1
    asset = assets[0]
    assert asset["url"] == (original or PREVIEW)
    assert asset["preview_url"] == PREVIEW
    assert asset["heading"] == "Figure 1."
    assert payload.content.markdown_text.count(f"]({original or PREVIEW})") == 1
    remote_article = OxfordAcademicClient(
        FixtureHtmlTransport({}), {}
    ).to_article_model({}, payload)
    remote_markdown = remote_article.to_ai_markdown(
        asset_profile="body", max_tokens="full_text"
    )
    assert remote_markdown.count(f"]({original or PREVIEW})") == 1
    assert remote_markdown.count("Source caption.") == 1

    body = png_header(1200, 900) + b"oxford-original"
    responses = {}
    if mode == "original":
        responses[ORIGINAL] = http_response(ORIGINAL, body, "image/png")
    elif mode != "failed":
        responses[PREVIEW] = http_response(PREVIEW, body, "image/png")
    transport = FixtureHtmlTransport(responses)
    client = OxfordAcademicClient(transport, {})
    result = client.download_related_assets(
        "10.1093/example", {}, payload, tmp_path, asset_profile="body"
    )
    expected = (
        [ORIGINAL]
        if mode == "original"
        else ([PREVIEW] if mode == "preview_only" else [ORIGINAL, PREVIEW])
    )
    assert [call["url"] for call in transport.calls] == expected
    article = client.to_article_model(
        {},
        payload,
        downloaded_assets=result["assets"],
        asset_failures=result["asset_failures"],
    )
    markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    assert len(article.assets) == 1
    assert markdown.count("![") == 1
    assert markdown.count("**Figure 1.** Source caption.") == 1
    assert "## Figures" not in markdown
    assert markdown.index("![") < markdown.index("After figure.")
    if mode == "failed":
        assert result["assets"] == []
        assert len(result["asset_failures"]) == 1
        return
    downloaded = result["assets"][0]
    assert Path(downloaded["path"]).read_bytes() == body
    assert downloaded["downloaded_bytes"] == len(body)
    assert markdown.count(f"]({downloaded['path']})") == 1
    assert not result["asset_failures"]
    fallback = mode != "original"
    assert downloaded["download_tier"] == ("preview" if fallback else "full_size")
    if fallback:
        assert downloaded["preview_accepted"] is False
        assert downloaded["recovery_attempts"][-1]["provider"] == "oxfordacademic"
        assert downloaded["recovery_attempts"][-1]["stage"] == "preview_fallback"
        assert article.assets[0].preview_accepted is False
    summary = build_asset_quality_summary(
        article.assets, asset_profile="body", archive_enabled=True
    )
    article.quality.asset_summary = summary
    report = evaluate_fetch_acceptance(
        FetchEnvelope(
            doi=article.doi,
            source=article.source,
            has_fulltext=article.quality.has_fulltext,
            content_kind=article.quality.content_kind,
            has_abstract=article.quality.has_abstract,
            article=article,
            quality=article.quality,
            markdown=markdown,
        ),
        asset_profile="body",
    )
    assert report.fetch.status == "ok"
    assert report.content.status == "fulltext"
    assert report.asset.status == ("degraded" if fallback else "complete")
    if fallback:
        assert "asset_fidelity_degraded" in summary.issue_codes
        assert report.overall == "degraded"
        assert "preview_fallback" not in markdown


def test_nested_subpanels_keep_individual_explicit_urls_and_signatures():
    previews = [PREVIEW, PREVIEW.replace("m_f1", "m_f1b")]
    originals = [ORIGINAL, ORIGINAL.replace("f1.png", "f1b.png") + "&crop=left"]
    panels = "".join(
        f'<div class="graphic-wrap"><img src="{preview}">'
        f'<a href="/DownloadFile/DownloadImage.aspx?image={quote(original, safe="")}">Download slide</a></div>'
        for preview, original in zip(previews, originals, strict=True)
    )
    payload = build_oxford_html_payload(
        f'<article><div class="fig fig-section" id="f1"><figure>{panels}'
        "<figcaption>Figure 1. Panels.</figcaption></figure></div></article>",
        URL,
    )
    assets = payload.content.extracted_assets
    assert [asset["url"] for asset in assets] == originals
    assert [asset["preview_url"] for asset in assets] == previews
    assert Counter(asset["dom_id"] for asset in assets) == {"f1": 2}
    for original in originals:
        assert payload.content.markdown_text.count(f"]({original})") == 1


def test_preview_filename_never_synthesizes_an_original():
    payload = build_oxford_html_payload(figure_html(""), URL)
    asset = payload.content.extracted_assets[0]
    assert not asset.get("full_size_url")
    assert asset["url"] == PREVIEW


def test_only_failed_figure_requests_its_preview(tmp_path):
    second_original = ORIGINAL.replace("f1.png", "f2.png")
    second_preview = PREVIEW.replace("m_f1.png", "m_f2.png")
    html = figure_html() + figure_html().replace(ORIGINAL, second_original).replace(
        PREVIEW, second_preview
    )
    html = html.replace("</article><article>", "")
    payload = build_oxford_html_payload(html, URL)
    body = png_header(1200, 900) + b"image"
    transport = FixtureHtmlTransport(
        {
            ORIGINAL: http_response(ORIGINAL, body, "image/png"),
            second_preview: http_response(second_preview, body, "image/png"),
        }
    )
    result = OxfordAcademicClient(transport, {}).download_related_assets(
        "10.1093/example", {}, payload, tmp_path, asset_profile="body"
    )
    assert Counter(call["url"] for call in transport.calls) == {
        ORIGINAL: 1,
        second_original: 1,
        second_preview: 1,
    }
    assert [asset["download_tier"] for asset in result["assets"]] == [
        "full_size",
        "preview",
    ]
    assert sum(asset["downloaded_bytes"] for asset in result["assets"]) == 2 * len(body)
    assert not result["asset_failures"]


def test_subpanel_without_original_cannot_borrow_another_panels_candidate():
    original = ORIGINAL.replace("/paper/", "/paper/full/")
    payload = build_oxford_html_payload(
        f'<article><figure><div class="graphic-wrap"><img src="{PREVIEW}" '
        f'data-hi-res-src="{original}"></div><div class="graphic-wrap">'
        f'<img src="{PREVIEW.replace("m_f1", "m_f1b")}"></div></figure></article>',
        URL,
    )
    assets = payload.content.extracted_assets
    assert len(assets) == 2
    assert assets[0]["full_size_url"] == original
    assert not assets[1].get("full_size_url")
