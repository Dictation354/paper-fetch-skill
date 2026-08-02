from __future__ import annotations

from unittest import mock

from paper_fetch.http import HttpTransport
from paper_fetch.providers import springer
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset
from ._paper_fetch_support import fulltext_pdf_bytes


BRIEFING_DOI = "10.1038/s41561-022-00983-6"
BRIEFING_URL = f"https://www.nature.com/articles/{BRIEFING_DOI}"
BRIEFING_HTML = golden_criteria_asset(BRIEFING_DOI, "original.html").read_bytes()
BRIEFING_HTML_WITH_TYPE = BRIEFING_HTML.replace(
    b"</head>",
    b'<meta name="citation_article_type" content="Research Briefing"></head>',
)


def _response(*, url: str, body: bytes) -> dict[str, object]:
    return {
        "status_code": 200,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "body": body,
        "url": url,
    }


def test_springer_discards_cookie_error_session_and_retries_once() -> None:
    transport = HttpTransport()
    context = RuntimeContext(env={}, transport=transport)
    client = springer.SpringerClient(transport=transport, env={})
    first_opener = object()
    second_opener = object()
    try:
        with (
            mock.patch.object(
                springer,
                "build_cookie_seeded_opener",
                side_effect=[first_opener, second_opener],
            ) as build_opener,
            mock.patch.object(
                springer,
                "request_with_opener",
                side_effect=[
                    _response(
                        url=(
                            f"{BRIEFING_URL}?error=cookies_not_supported"
                            "&code=secret-value"
                        ),
                        body=b"<html><title>Preview</title></html>",
                    ),
                    _response(url=BRIEFING_URL, body=BRIEFING_HTML),
                ],
            ) as request,
        ):
            result = client._fetch_html_landing(BRIEFING_URL, context=context)
    finally:
        context.close()
        transport.close()

    assert result.final_url == BRIEFING_URL
    assert len(result.html_text) > 1000
    assert build_opener.call_count == 2
    assert request.call_args_list[0].args[0] is first_opener
    assert request.call_args_list[1].args[0] is second_opener


def test_springer_second_cookie_error_stops_after_exactly_one_retry() -> None:
    transport = HttpTransport()
    context = RuntimeContext(env={}, transport=transport)
    client = springer.SpringerClient(transport=transport, env={})
    preview_url = f"{BRIEFING_URL}?error=cookies_not_supported&code=redacted-value"
    try:
        with (
            mock.patch.object(
                springer,
                "build_cookie_seeded_opener",
                side_effect=[object(), object()],
            ) as build_opener,
            mock.patch.object(
                springer,
                "request_with_opener",
                side_effect=[
                    _response(
                        url=preview_url,
                        body=b"<html><body>Preview one</body></html>",
                    ),
                    _response(
                        url=preview_url,
                        body=b"<html><body>Preview two</body></html>",
                    ),
                ],
            ) as request,
        ):
            result = client._fetch_html_landing(BRIEFING_URL, context=context)
    finally:
        context.close()
        transport.close()

    assert result.final_url == preview_url
    assert build_opener.call_count == 2
    assert request.call_count == 2


def test_springer_second_cookie_error_enters_existing_pdf_waterfall() -> None:
    transport = HttpTransport()
    context = RuntimeContext(env={}, transport=transport)
    client = springer.SpringerClient(transport=transport, env={})
    preview_url = f"{BRIEFING_URL}?error=cookies_not_supported&code=redacted-value"
    preview_html = (
        "<html><head>"
        '<meta name="citation_title" content="Research Briefing">'
        f'<meta name="citation_doi" content="{BRIEFING_DOI}">'
        f'<meta name="citation_pdf_url" content="{BRIEFING_URL}.pdf">'
        "</head><body><article><h1>Research Briefing</h1></article></body></html>"
    ).encode()
    metadata = {
        "doi": BRIEFING_DOI,
        "title": "Research Briefing",
        "landing_page_url": BRIEFING_URL,
        "authors": [],
        "fulltext_links": [
            {"url": f"{BRIEFING_URL}.pdf", "content_type": "application/pdf"}
        ],
    }
    try:
        with (
            mock.patch.object(
                springer,
                "build_cookie_seeded_opener",
                side_effect=[object(), object()],
            ),
            mock.patch.object(
                springer,
                "request_with_opener",
                side_effect=[
                    _response(url=preview_url, body=preview_html),
                    _response(url=preview_url, body=preview_html),
                ],
            ) as request,
            mock.patch.object(
                springer,
                "fetch_pdf_over_http",
                return_value=mock.Mock(
                    source_url=f"{BRIEFING_URL}.pdf",
                    final_url=f"{BRIEFING_URL}.pdf",
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text="# Research Briefing\n\n## Results\n\n"
                    + ("Body text " * 120),
                    suggested_filename="research-briefing.pdf",
                ),
            ) as pdf_fallback,
        ):
            result = client.fetch_result(
                BRIEFING_DOI,
                metadata,
                None,
                context=context,
            )
    finally:
        context.close()
        transport.close()

    assert request.call_count == 2
    pdf_fallback.assert_called_once()
    assert result.article.source == "springer_pdf"
    assert "fulltext:springer_html_fail" in result.article.quality.source_trail
    assert "fulltext:springer_pdf_fallback_ok" in result.article.quality.source_trail


def test_springer_cookie_sessions_are_not_shared_between_fetches() -> None:
    transport = HttpTransport()
    first_context = RuntimeContext(env={}, transport=transport)
    second_context = RuntimeContext(env={}, transport=transport)
    client = springer.SpringerClient(transport=transport, env={})
    first_opener = object()
    second_opener = object()
    try:
        with (
            mock.patch.object(
                springer,
                "build_cookie_seeded_opener",
                side_effect=[first_opener, second_opener],
            ) as build_opener,
            mock.patch.object(
                springer,
                "request_with_opener",
                side_effect=[
                    _response(url=BRIEFING_URL, body=BRIEFING_HTML),
                    _response(url=BRIEFING_URL, body=BRIEFING_HTML),
                ],
            ) as request,
        ):
            client._fetch_html_landing(
                BRIEFING_URL,
                context=first_context,
            )
            client._fetch_html_landing(
                BRIEFING_URL,
                context=second_context,
            )
    finally:
        first_context.close()
        second_context.close()
        transport.close()

    assert build_opener.call_count == 2
    assert request.call_args_list[0].args[0] is first_opener
    assert request.call_args_list[1].args[0] is second_opener


def test_springer_cookie_recovery_stays_on_html_and_preserves_article_type() -> None:
    transport = HttpTransport()
    context = RuntimeContext(env={}, transport=transport)
    client = springer.SpringerClient(transport=transport, env={})
    metadata = {
        "doi": BRIEFING_DOI,
        "title": "Research Briefing",
        "landing_page_url": BRIEFING_URL,
        "authors": [],
        "fulltext_links": [],
    }
    try:
        with (
            mock.patch.object(
                springer,
                "build_cookie_seeded_opener",
                return_value=object(),
            ),
            mock.patch.object(
                springer,
                "request_with_opener",
                return_value=_response(
                    url=BRIEFING_URL,
                    body=BRIEFING_HTML_WITH_TYPE,
                ),
            ),
            mock.patch.object(
                client,
                "_fetch_pdf_payload_from_html_attempt",
            ) as pdf_fallback,
        ):
            prepared = client.prepare_fetch_result_payload(
                BRIEFING_DOI,
                metadata,
                asset_profile="none",
                context=context,
            )
            article = client.to_article_model(
                metadata,
                prepared.raw_payload,
                context=context,
            )
    finally:
        context.close()
        transport.close()

    assert prepared.raw_payload.content is not None
    assert prepared.raw_payload.content.route_kind == "html"
    assert article.source == "springer_html"
    assert article.metadata.article_type == "Research Briefing"
    assert "empty_authors" not in article.quality.flags
    pdf_fallback.assert_not_called()
