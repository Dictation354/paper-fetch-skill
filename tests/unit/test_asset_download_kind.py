from __future__ import annotations

from pathlib import Path

from paper_fetch.extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
)


def test_figure_kind_candidate_response_and_failure_template_round_trip() -> None:
    asset = {
        "kind": "figure",
        "heading": "Figure 1",
        "caption": "Caption",
        "download_url": "https://example.test/download.png",
        "full_size_url": "https://example.test/full.png",
        "url": "https://example.test/preview.png",
        "section": "body",
    }

    assert FIGURE_KIND.candidate_url_resolver(asset) == [
        "https://example.test/download.png",
        "https://example.test/full.png",
        "https://example.test/preview.png",
    ]
    assert FIGURE_KIND.upgrade_targets is not None
    assert FIGURE_KIND.upgrade_targets("https://example.test/preview.png", asset) == [
        "https://example.test/full.png",
        "https://example.test/download.png",
        "https://example.test/preview.png",
    ]
    assert FIGURE_KIND.accepts_response(
        "application/octet-stream", b"\x89PNG\r\n\x1a\npayload"
    )
    assert not FIGURE_KIND.accepts_response("text/html", b"<html></html>")

    failure = FIGURE_KIND.failure_template(
        asset,
        "https://example.test/preview.png",
        reason="image_fetch_error",
        status=403,
        content_type="text/html",
        final_url="https://example.test/login",
        error_type="RuntimeError",
        error_message="context closed",
    )

    assert failure == {
        "kind": "figure",
        "heading": "Figure 1",
        "caption": "Caption",
        "source_url": "https://example.test/preview.png",
        "reason": "image_fetch_error",
        "section": "body",
        "status": 403,
        "content_type": "text/html",
        "final_url": "https://example.test/login",
        "error_type": "RuntimeError",
        "error_message": "context closed",
    }


def test_supplementary_kind_candidate_response_and_failure_template_round_trip() -> (
    None
):
    asset = {
        "kind": "supplementary",
        "heading": "",
        "caption": "Supplement caption",
        "download_url": "https://example.test/supplement.pdf",
        "url": "https://example.test/landing",
        "filename_hint": "supplement.pdf",
        "asset_kind": "source_data",
        "section": "supplementary",
    }

    assert SUPPLEMENTARY_KIND.candidate_url_resolver(asset) == [
        "https://example.test/supplement.pdf",
        "https://example.test/landing",
    ]
    assert SUPPLEMENTARY_KIND.upgrade_targets is None
    assert SUPPLEMENTARY_KIND.accepts_response("application/pdf", b"%PDF-1.7\n")
    assert not SUPPLEMENTARY_KIND.accepts_response(
        "text/html",
        b"<html><title>Access denied</title><body>cloudflare challenge</body></html>",
    )
    assert SUPPLEMENTARY_KIND.output_subdir(asset) == Path("source_data")

    failure = SUPPLEMENTARY_KIND.failure_template(
        asset,
        "https://example.test/supplement.pdf",
        reason="cloudflare_challenge",
        status=403,
        content_type="text/html",
        final_url="https://example.test/login",
        body=b"<html><title>Access denied</title><body>Blocked by gate</body></html>",
        extra={"source_ref": "S1"},
    )

    assert failure["kind"] == "supplementary"
    assert failure["heading"] == "supplement.pdf"
    assert failure["caption"] == "Supplement caption"
    assert failure["source_url"] == "https://example.test/supplement.pdf"
    assert failure["reason"] == "cloudflare_challenge"
    assert failure["section"] == "supplementary"
    assert failure["status"] == 403
    assert failure["content_type"] == "text/html"
    assert failure["final_url"] == "https://example.test/login"
    assert failure["filename_hint"] == "supplement.pdf"
    assert failure["source_ref"] == "S1"
    assert "Access denied" in failure["title_snippet"]
