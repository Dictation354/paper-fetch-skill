"""IEEE iframe candidate matching is scoped to the requested article."""

import pytest

from paper_fetch.providers._ieee_pdf import iframe_pdf_candidates


@pytest.mark.parametrize(
    "target, expected",
    [
        ("/stampPDF/getPDF.jsp?arnumber=5526567", True),
        ("/stampPDF/getPDF.jsp?arnumber=1234567", False),
        ("https://other.test/stampPDF/getPDF.jsp?arnumber=5526567", False),
        (
            "https://ieeexplore.ieee.org.other.test/stampPDF/getPDF.jsp?arnumber=5526567",
            False,
        ),
        ("/stampPDF/getPDF.jsp?arnumber=5526567&arnumber=1234567", False),
    ],
)
def test_ieee_iframe_candidate_requires_official_host_and_same_article(
    target, expected
):
    candidates = iframe_pdf_candidates(
        f'<iframe src="{target}"></iframe>',
        "https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=5526567",
    )
    assert bool(candidates) is expected
