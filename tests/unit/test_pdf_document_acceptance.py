"""Real wrong-document/preview and synthetic supplement rejection regressions."""

import pytest
from paper_fetch.providers import _pdf_common
from tests.support._paper_fetch_support import build_pdf_bytes


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


def test_supplement_cannot_hide_behind_generic_download_url():
    # Synthetic role evidence; the real supplementary payload was removed.
    with pytest.raises(_pdf_common.PdfFetchFailure, match="supplementary"):
        _pdf_common.pdf_fetch_result_from_bytes(
            artifact_dir=None,
            source_url="https://example.org/download",
            final_url="https://example.org/download",
            pdf_bytes=build_pdf_bytes(
                ["Supplementary Information", "Supplementary methods and data"]
            ),
            allow_pdf_only=True,
        )
