from tests.support.acquired_publisher_inputs import _record
from tests.support._paper_fetch_support import build_pdf_bytes
from paper_fetch.providers import _pdf_candidates, _pdf_common
import pytest
import json
from unittest import mock
from paper_fetch.providers import _pdf_fallback
from tests.golden_criteria import golden_criteria_asset
from tests.support._paper_fetch_support import RecordingTransport


"""Real wrong-document/preview and synthetic supplement rejection regressions."""


PREFIX = "acquisition/subscription-2026-09-15/"
BAD_DOWNLOADS = [
    (
        "10.1063/5.0260731",
        "https://vergil.chemistry.gatech.edu/static/content/ci.pdf",
        "pdf_identity_unverified",
    ),
    (
        "10.1175/jas-d-26-0015.1",
        "https://journals.ametsoc.org/previewpdf/view/journals/atsc/83/9/JAS-D-26-0015.1.xml",
        "pdf_preview_only",
    ),
]


@pytest.mark.parametrize("title_mode", ["present", "missing", "blank"])
@pytest.mark.parametrize("doi,url,reason", BAD_DOWNLOADS)
def test_real_non_article_pdf_rejected_before_conversion(
    doi, url, reason, title_mode, tmp_path
):
    metadata = json.loads(
        golden_criteria_asset(doi, PREFIX + "article.json").read_text()
    )["metadata"]
    with (
        mock.patch.object(
            _pdf_common, "_render_pdf_markdown_result_with_cache"
        ) as render,
        pytest.raises(_pdf_common.PdfFetchFailure) as caught,
    ):
        _pdf_common.pdf_fetch_result_from_bytes(
            source_url="https://example.org/download",
            final_url=url,
            pdf_bytes=golden_criteria_asset(
                doi, PREFIX + "downloaded.pdf"
            ).read_bytes(),
            expected_identity={
                "doi": doi,
                **(
                    {"title": metadata["title"]}
                    if title_mode == "present"
                    else {"title": "   "}
                    if title_mode == "blank"
                    else {}
                ),
            },
            artifact_dir=tmp_path,
            allow_pdf_only=True,
        )
    assert caught.value.kind == reason
    render.assert_not_called()
    assert not list(tmp_path.glob("*.pdf"))


def test_rejected_preview_continues_to_full_article():
    doi = "10.1175/jas-d-26-0015.1"
    preview_url = BAD_DOWNLOADS[1][1]
    full_url = "https://journals.ametsoc.org/downloadpdf/article.pdf"
    transport = RecordingTransport(
        {
            ("GET", preview_url): {
                "body": golden_criteria_asset(
                    doi, PREFIX + "downloaded.pdf"
                ).read_bytes(),
                "url": preview_url,
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
            },
            ("GET", full_url): {
                "body": build_pdf_bytes(["Article body", "doi:" + doi]),
                "url": full_url,
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
            },
        }
    )
    # The second response is explicitly synthetic: this tests continuation only.
    with mock.patch.object(
        _pdf_common,
        "_render_pdf_markdown_result_with_cache",
        return_value=(
            _pdf_common.PdfMarkdownRenderResult(markdown_text="body"),
            "miss",
        ),
    ):
        result = _pdf_fallback.fetch_pdf_over_http(
            transport,
            [preview_url, full_url],
            request=_pdf_fallback.PdfRequestContext(expected_identity={"doi": doi}),
        )
    assert result.final_url == full_url
    assert [call["url"] for call in transport.calls] == [preview_url, full_url]


@pytest.mark.parametrize("with_title", [True, False])
def test_wrong_aip_lecture_continues_to_real_same_article_pdf(with_title):
    doi = "10.1063/5.0260731"
    wrong_url = BAD_DOWNLOADS[0][1]
    record, right_body = _record(
        doi, "acquisition/pdf-identity-recheck-2026-09-15-intermediate/response-008.bin"
    )
    right_url = record["final_url"]
    metadata = json.loads(
        golden_criteria_asset(doi, PREFIX + "article.json").read_text()
    )["metadata"]
    transport = RecordingTransport(
        {
            ("GET", wrong_url): {
                "status_code": 200,
                "url": wrong_url,
                "headers": {"content-type": "application/pdf"},
                "body": golden_criteria_asset(
                    doi, PREFIX + "downloaded.pdf"
                ).read_bytes(),
            },
            ("GET", right_url): {
                "status_code": record["status_code"],
                "url": right_url,
                "headers": record["response_headers"],
                "body": right_body,
            },
        }
    )
    with mock.patch.object(
        _pdf_common,
        "_render_pdf_markdown_result_with_cache",
        return_value=(
            _pdf_common.PdfMarkdownRenderResult(markdown_text="body"),
            "miss",
        ),
    ) as render:
        result = _pdf_fallback.fetch_pdf_over_http(
            transport,
            [wrong_url, right_url],
            request=_pdf_fallback.PdfRequestContext(
                expected_identity={
                    "doi": doi,
                    **({"title": metadata["title"]} if with_title else {}),
                }
            ),
        )
    assert result.pdf_bytes == right_body
    assert result.diagnostics["identity"]["status"] == "match"
    assert result.final_url == right_url
    assert render.call_count == 1


@pytest.mark.parametrize(
    "doi",
    [
        "10.1021/ja00160a040",
        "10.1021/jacs.6c10062",
        "10.1063/1.39658",
        "10.1175/jpo-d-24-0098.1",
        "10.1093/mind/lxxxix.354.263",
        "10.1073/pnas.2509692123",
        "10.1073/pnas.2607267123",
        "10.1098/rspa.1984.0023",
        "10.1126/science.aeg3511",
        "10.1038/nature12915",
        "10.1080/19455224.2025.2547671",
        "10.1111/gcb.16758",
        "10.1111/gcb.16998",
    ],
)
def test_remaining_captured_article_pdfs_pass_identity_without_conversion(doi):
    metadata = json.loads(
        golden_criteria_asset(doi, PREFIX + "article.json").read_text()
    )["metadata"]
    with mock.patch.object(
        _pdf_common,
        "_render_pdf_markdown_result_with_cache",
        return_value=(_pdf_common.PdfMarkdownRenderResult(markdown_text=""), "miss"),
    ):
        result = _pdf_common.pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url="https://example.org/article.pdf",
            final_url="https://example.org/article.pdf",
            pdf_bytes=golden_criteria_asset(
                doi, PREFIX + "downloaded.pdf"
            ).read_bytes(),
            expected_identity={"doi": doi, "title": metadata["title"]},
            allow_pdf_only=True,
        )
    assert result.diagnostics["identity"]["status"] == "match"


@pytest.mark.parametrize(
    "doi,filename,forbidden",
    [
        ("10.1063/5.0260731", "response-003.bin", "ci.pdf"),
        ("10.1063/5.0260731", "response-003.bin", "ContentPlatform_UserGuide"),
        ("10.1038/s41586-026-11124-z", "response-001.bin", "MOESM"),
        ("10.1175/jas-d-26-0015.1", "response-001.bin", "previewpdf"),
    ],
)
def test_real_html_does_not_offer_citations_supplements_or_previews_as_body(
    doi, filename, forbidden
):
    record, raw = _record(doi, PREFIX + filename)
    candidates = _pdf_candidates.extract_pdf_candidate_urls_from_html(
        raw.decode(), record["final_url"]
    )
    assert all(forbidden.casefold() not in url.casefold() for url in candidates)
