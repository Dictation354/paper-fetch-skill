"""Real offline browser: IEEE iframe PDF has no click/download event."""

from unittest import mock

import pytest

from paper_fetch.providers import _ieee_pdf, _pdf_common, _pdf_fallback
from paper_fetch.providers.browser_runtime.types import BrowserRuntimeConfig
from tests.support._paper_fetch_support import fulltext_pdf_bytes
from tests.support.local_http import local_responses as local_responses
from tests.support.offline_chromium import prepared_browser


@pytest.mark.browser
@pytest.mark.parametrize(
    "case",
    [
        "pdf",
        "not_pdf",
        "wrong_identity",
        "direct_pdf",
        "download",
        "click_pdf",
        "click_popup",
        "click_wrong_identity",
    ],
)
def test_ieee_stamp_captures_subframe_response_without_download(
    tmp_path, monkeypatch, case, local_responses
):
    doi = "10.1109/MPER.1985.5526567"
    landing_path = "/document/5526567/"
    stamp_path = "/stamp/stamp.jsp?arnumber=5526567"
    target_path = "/stampPDF/getPDF.jsp?arnumber=5526567"
    payload = fulltext_pdf_bytes(
        doi="10.1109/other.123456"
        if case in {"wrong_identity", "click_wrong_identity"}
        else doi
    )
    requests = []
    downloads = []
    responses = []

    def server_response(path, headers):
        requests.append((origin + path, headers))
        if path.rstrip("/") == landing_path.rstrip("/"):
            target_attr = ' target="_blank"' if case == "click_popup" else ""
            control = (
                f'<a href="{stamp_path}&tp="{target_attr}>PDF</a>'
                if case.startswith("click_")
                else ""
            )
            return (
                200,
                {"Content-Type": "text/html", "Set-Cookie": "article_warm=1; Path=/"},
                f"<html><body>Article landing {control}</body></html>".encode(),
            )
        if path == stamp_path and case.startswith("click_"):
            return 502, {"Content-Type": "text/html"}, b"Bad gateway"
        if path == stamp_path and case in {"direct_pdf", "download"}:
            headers = {"Content-Type": "application/pdf"}
            if case == "download":
                headers["Content-Disposition"] = "attachment; filename=article.pdf"
            return 200, headers, payload
        if path in {stamp_path, stamp_path + "&tp="}:
            return (
                200,
                {"Content-Type": "text/html"},
                f'<html><iframe src="{target_path}"></iframe></html>'.encode(),
            )
        if path == target_path:
            if case == "not_pdf":
                return 200, {"Content-Type": "text/html"}, b"<html>No PDF</html>"
            return 200, {"Content-Type": "application/pdf"}, payload
        return 404, {}, b""

    origin = local_responses(server_response)
    monkeypatch.setattr(_ieee_pdf, "_IEEE_ORIGIN", origin)
    landing, stamp, target = [
        origin + path for path in (landing_path, stamp_path, target_path)
    ]

    with prepared_browser() as browser:
        context = browser.new_context()
        borrowed_page = context.new_page()
        page = context.new_page()
        page.on("download", lambda download: downloads.append(download))
        page.on(
            "response",
            lambda response: responses.append((response.url, response.status)),
        )
        monkeypatch.setattr(context, "new_page", lambda: page)
        monkeypatch.setattr(
            _pdf_fallback, "_open_pdf_browser_context", lambda *a, **kw: (None, context)
        )
        monkeypatch.setattr(
            _pdf_fallback,
            "fetch_pdf_over_http",
            mock.Mock(side_effect=_pdf_fallback.PdfFetchFailure("not_pdf", "wrapper")),
        )
        # Conversion is opaque to this browser contract; real byte/DOI checks run.
        monkeypatch.setattr(
            _pdf_common,
            "render_pdf_markdown_result",
            lambda *a, **kw: _pdf_common.PdfMarkdownRenderResult(
                markdown_text="Unmodified converter boundary", assets=[]
            ),
        )
        monkeypatch.setattr(
            page,
            "expect_download",
            mock.Mock(side_effect=AssertionError("no download event expected")),
        )
        monkeypatch.setattr(
            page, "click", mock.Mock(side_effect=AssertionError("no click allowed"))
        )
        config = BrowserRuntimeConfig(
            provider="ieee",
            doi=doi,
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
        )
        kwargs = dict(
            artifact_dir=tmp_path,
            browser_config=config,
            seed_urls=[landing],
            referer=landing,
            allow_pdf_only=True,
            request=_pdf_fallback.PdfRequestContext(
                expected_identity={"doi": doi},
                provider_name="ieee",
                timeout_seconds=20,
                allowed_hosts=("127.0.0.1",),
            ),
        )
        if case in {"pdf", "direct_pdf", "download", "click_pdf", "click_popup"}:
            result = _pdf_fallback.fetch_pdf_with_browser([stamp], **kwargs)
            assert result.pdf_bytes == payload
            assert result.source_url == (
                target if case in {"pdf", "click_pdf", "click_popup"} else stamp
            )
            if case == "direct_pdf" and downloads:
                assert result.diagnostics["bytes_transport"] == "browser_download"
            elif case != "download":
                assert result.final_url == result.source_url
                assert result.diagnostics["browser_pdf_response"] == (
                    "ieee_article_click"
                    if case.startswith("click_")
                    else "ieee_stamp_iframe"
                    if case == "pdf"
                    else "ieee_stamp_direct"
                )
            assert result.diagnostics["identity"]["status"] == "match"
            assert list(tmp_path.glob("*.pdf"))
        else:
            with pytest.raises(_pdf_fallback.PdfFetchFailure) as error:
                _pdf_fallback.fetch_pdf_with_browser([stamp], **kwargs)
            assert error.value.kind == (
                "identity_mismatch"
                if case in {"wrong_identity", "click_wrong_identity"}
                else "pdf_download_not_triggered"
            )
            assert not list(tmp_path.glob("*.pdf"))
        assert context.pages == [borrowed_page]
    if case != "direct_pdf":
        assert bool(downloads) is (case == "download")
    assert requests[0][0] == landing
    headers = next(headers for url, headers in requests if url == stamp)
    assert headers["referer"] == landing
    assert "article_warm=1" in headers.get("cookie", "")
    assert (stamp, 502 if case.startswith("click_") else 200) in responses
    if case not in {"direct_pdf", "download", "click_popup"}:
        assert (target, 200) in responses
    if case in {
        "pdf",
        "click_pdf",
        "click_popup",
        "wrong_identity",
        "click_wrong_identity",
    }:
        target_requests = [headers for url, headers in requests if url == target]
        assert len(target_requests) == 2
        assert all(
            "article_warm=1" in headers.get("cookie", "") for headers in target_requests
        )
        assert target_requests[0]["referer"] == target_requests[1]["referer"]
