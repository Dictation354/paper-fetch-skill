"""Identity acceptance mechanism with bounded evidence and converter boundary mocks."""

from unittest import mock
import pytest
from paper_fetch.providers import _pdf_common
from tests.support._paper_fetch_support import build_pdf_bytes


@pytest.mark.parametrize(
    "identity",
    [
        {"doi": "10.1000/requested"},
        {"doi": "10.1000/requested", "title": ""},
        {"doi": "10.1000/requested", "title": "   "},
        {
            "doi": "10.1000/requested",
            "title": "Ocean circulation and its changing regional patterns",
        },
    ],
)
@pytest.mark.parametrize(
    "opening", ["Ocean", "Unrelated lecture notes", "Unrelated lecture notes " * 30]
)
@pytest.mark.parametrize("allow_pdf_only", [True, False])
def test_insufficient_identity_rejects_before_converter_and_cleans_temp(
    identity, allow_pdf_only, opening, tmp_path
):
    with mock.patch.object(
        _pdf_common, "_render_pdf_markdown_result_with_cache"
    ) as render:
        with pytest.raises(_pdf_common.PdfFetchFailure) as error:
            _pdf_common.pdf_fetch_result_from_bytes(
                pdf_bytes=build_pdf_bytes([opening]),
                artifact_dir=tmp_path,
                source_url="https://example.org/a.pdf",
                final_url="https://example.org/a.pdf",
                expected_identity=identity,
                allow_pdf_only=allow_pdf_only,
            )
    assert error.value.kind == "pdf_identity_unverified"
    render.assert_not_called()
    assert not list(tmp_path.glob("*.pdf"))


@pytest.mark.parametrize(
    "identity,lines,method",
    [
        ({"doi": "10.1000/requested"}, ["doi:10.1000/requested"], "doi"),
        (
            {
                "doi": "10.1000/requested",
                "title": "A detailed study of ocean circulation",
            },
            ["A detailed study of ocean circulation"],
            "pdf_opening_title",
        ),
        (
            {
                "doi": "10.1000/requested",
                "title": "A detailed study of ocean circulation",
            },
            ["Authors. A detailed study of ocean circulatiom. Abstract."],
            "pdf_opening_title",
        ),
        (None, ["No requested identity at the low level"], None),
    ],
)
def test_independent_doi_title_fallback_and_no_target_contract(
    identity, lines, method, tmp_path
):
    with (
        mock.patch.object(
            _pdf_common,
            "_pdf_identity_evidence",
            return_value={
                "doi": "10.1000/requested" if method == "doi" else None,
                "opening_text": "\n".join(lines),
            },
        ),
        mock.patch.object(
            _pdf_common,
            "_render_pdf_markdown_result_with_cache",
            return_value=(
                _pdf_common.PdfMarkdownRenderResult(
                    markdown_text="Unmodified converter output."
                ),
                "miss",
            ),
        ),
    ):
        result = _pdf_common.pdf_fetch_result_from_bytes(
            pdf_bytes=build_pdf_bytes(lines),
            artifact_dir=tmp_path,
            source_url="https://example.org/a.pdf",
            final_url="https://example.org/a.pdf",
            expected_identity=identity,
        )
    assert result.markdown_text == "Unmodified converter output."
    if method:
        assert result.diagnostics["identity"]["status"] == "match"
        assert method in result.diagnostics["identity"]["method"]


def test_short_title_candidate_is_cleaned_and_next_candidate_is_used(tmp_path):
    from paper_fetch.providers import _pdf_fallback
    from tests.support._paper_fetch_support import RecordingTransport

    urls = ["https://example.org/short.pdf", "https://example.org/right.pdf"]
    transport = RecordingTransport(
        {
            ("GET", url): {
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "url": url,
                "body": build_pdf_bytes([text]),
            }
            for url, text in zip(urls, ["Ocean", "doi:10.1000/right"], strict=True)
        }
    )
    with mock.patch.object(
        _pdf_common,
        "_render_pdf_markdown_result_with_cache",
        return_value=(
            _pdf_common.PdfMarkdownRenderResult(markdown_text="Converter output."),
            "miss",
        ),
    ) as convert:
        result = _pdf_fallback.fetch_pdf_over_http(
            transport,
            urls,
            artifact_dir=tmp_path,
            request=_pdf_fallback.PdfRequestContext(
                expected_identity={
                    "doi": "10.1000/right",
                    "title": "Ocean circulation and its changing regional patterns",
                },
            ),
        )
    assert result.source_url == urls[1]
    assert [call["url"] for call in transport.calls] == urls
    convert.assert_called_once()
    assert len(list(tmp_path.glob("*.pdf"))) == 1
