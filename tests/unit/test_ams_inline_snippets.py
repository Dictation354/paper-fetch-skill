"""Caption paragraphs copied from the four original AMS replays; no full article."""

from bs4 import BeautifulSoup
import pytest
from paper_fetch.providers._ams_dom import _render_ams_inline_text
from tests.golden_criteria import golden_criteria_scenario_asset


@pytest.mark.parametrize(
    "scenario,forbidden,expected",
    [
        (
            "ams_caption_aies-d-23-0093_1",
            ("σ 2",),
            ("Gaussian (*μ*, *σ*<sup>2</sup>)",),
        ),
        (
            "ams_caption_jpo-d-23-0234_1",
            ("γ 1", "A N", "ϕ ON", "ϕ 2", "</sub>(blue)"),
            (
                "*γ*<sub>1</sub>",
                "*A*<sub>N</sub>",
                "*ϕ*<sub>ON</sub>",
                (
                    "$\\overset{\\cdot}{q}(q, \\phi_{2})$ (blue)",
                    "$\\overset{\\cdot}{q}(q,\\phi_{2})$ (blue)",
                    "$\\overset{˙}{q}{({q,\\phi_{2}})}$ (blue)",
                ),
                "*ϕ*<sub>OFF</sub> (blue)",
            ),
        ),
        (
            "ams_caption_waf-d-24-0019_1",
            ("α 3 and β 3",),
            ("*α*<sub>3</sub> and *β*<sub>3</sub>",),
        ),
        (
            "ams_caption_jtech-d-24-0028_1",
            ("m s −1", "m s -1"),
            ("m s<sup>−1</sup>", "W m<sup>−2</sup>"),
        ),
    ],
)
def test_caption_inline_markup_from_source_paragraphs(scenario, forbidden, expected):
    html = golden_criteria_scenario_asset(scenario, "original.html").read_text()
    soup = BeautifulSoup(html, "lxml")
    text = "\n".join(_render_ams_inline_text(p) for p in soup.find_all("p"))
    for value in forbidden:
        assert value not in text
    for value in expected:
        assert (
            any(item in text for item in value)
            if isinstance(value, tuple)
            else value in text
        )
