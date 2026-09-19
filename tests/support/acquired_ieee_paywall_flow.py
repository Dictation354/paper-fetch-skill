"""Shared test support; contains no collected tests."""

from paper_fetch.providers._ieee_metadata import (
    _merge_ieee_metadata,
    _parse_landing_metadata,
)
from tests.golden_criteria import golden_criteria_asset


DOI = "10.1109/TBME.2024.3434477"

URL = "https://ieeexplore.ieee.org/document/10612240/"


def _captured_landing():
    raw = golden_criteria_asset(
        DOI, "acquisition/paywall-2026-09-15/final.dom.html"
    ).read_text()
    metadata = _merge_ieee_metadata({"doi": DOI}, _parse_landing_metadata(raw), URL)
    return raw, metadata
