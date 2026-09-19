from __future__ import annotations
from tests.golden_criteria import golden_criteria_asset
from paper_fetch.runtime import RuntimeContext
from paper_fetch.providers import springer
from paper_fetch.http import HttpTransport
from unittest import mock


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
