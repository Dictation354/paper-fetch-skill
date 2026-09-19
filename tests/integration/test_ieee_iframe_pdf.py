"""Real offline browser: IEEE iframe PDF has no click/download event."""

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from paper_fetch.providers import _pdf_common, _pdf_fallback
from paper_fetch.providers.browser_runtime.types import BrowserRuntimeConfig
from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR
from tests.support._paper_fetch_support import fulltext_pdf_bytes


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
    tmp_path, monkeypatch, case
):
    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, utils

    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    monkeypatch.setattr(
        utils,
        "installed_verstr",
        lambda: json.loads(version_file.read_text())["version"],
    )
    monkeypatch.setattr(utils, "get_path", lambda file: str(version_file.parent / file))
    doi = "10.1109/MPER.1985.5526567"
    landing = "https://ieeexplore.ieee.org/document/5526567/"
    stamp = "https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=5526567"
    target = "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?arnumber=5526567"
    payload = fulltext_pdf_bytes(
        doi="10.1109/other.123456"
        if case in {"wrong_identity", "click_wrong_identity"}
        else doi
    )
    requests = []
    downloads = []
    responses = []

    def route_response(route):
        request = route.request
        requests.append((request.url, request.headers))
        if request.url.rstrip("/") == landing.rstrip("/"):
            control = (
                (
                    f'<a href="{stamp}&tp=" target="_blank">PDF</a>'
                    if case == "click_popup"
                    else f'<a href="{stamp}&tp=">PDF</a>'
                )
                if case.startswith("click_")
                else ""
            )
            route.fulfill(
                body=f"<html><body>Article landing {control}</body></html>",
                content_type="text/html",
                headers={"set-cookie": "article_warm=1; Path=/; Secure"},
            )
        elif request.url == stamp and case.startswith("click_"):
            route.fulfill(status=502, body="Bad gateway", content_type="text/html")
        elif request.url == stamp + "&tp=":
            route.fulfill(
                body=f'<iframe src="{target}"></iframe>', content_type="text/html"
            )
        elif request.url == stamp and case in {"direct_pdf", "download"}:
            route.fulfill(
                body=payload,
                content_type="application/pdf",
                headers={"content-disposition": "attachment; filename=article.pdf"}
                if case == "download"
                else {},
            )
        elif request.url == stamp:
            route.fulfill(
                body=f'<html><body><iframe src="{target}"></iframe></body></html>',
                content_type="text/html",
            )
        elif request.url == target:
            route.fulfill(
                body=b"<html>No PDF</html>" if case == "not_pdf" else payload,
                content_type="text/html" if case == "not_pdf" else "application/pdf",
            )
        else:
            route.abort()

    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        context = browser.new_context()
        context.route("**/*", route_response)
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
            mock.Mock(
                side_effect=_pdf_fallback.PdfFallbackFailure("not_pdf", "wrapper")
            ),
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
                expected_identity={"doi": doi}, provider_name="ieee", timeout_seconds=20
            ),
        )
        if case in {"pdf", "direct_pdf", "download", "click_pdf", "click_popup"}:
            result = _pdf_fallback.fetch_pdf_with_browser([stamp], **kwargs)
            assert result.pdf_bytes == payload
            assert result.source_url == (
                target if case in {"pdf", "click_pdf", "click_popup"} else stamp
            )
            if case != "download":
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
            with pytest.raises(_pdf_fallback.PdfFallbackFailure) as error:
                _pdf_fallback.fetch_pdf_with_browser([stamp], **kwargs)
            assert error.value.kind == (
                "identity_mismatch"
                if case in {"wrong_identity", "click_wrong_identity"}
                else "pdf_download_not_triggered"
            )
            assert not list(tmp_path.glob("*.pdf"))
    assert bool(downloads) is (case == "download")
    assert requests[0][0] == landing
    headers = next(headers for url, headers in requests if url == stamp)
    assert headers["referer"] == landing
    assert "article_warm=1" in headers.get("cookie", "")
    assert (stamp, 502 if case.startswith("click_") else 200) in responses
    if case not in {"direct_pdf", "download", "click_popup"}:
        assert (target, 200) in responses
