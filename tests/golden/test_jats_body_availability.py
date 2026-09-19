from __future__ import annotations
from paper_fetch.providers._article_markdown_jats import (
    parse_jats_xml,
)
from tests.golden_criteria import golden_criteria_asset


def test_shared_jats_renderer_normalizes_real_frontiers_and_copernicus_wrapping() -> (
    None
):
    frontiers = parse_jats_xml(
        golden_criteria_asset("10.3389/fmars.2023.1101972", "original.xml").read_bytes()
    )
    copernicus = parse_jats_xml(
        golden_criteria_asset("10.5194/acp-1-1-2001", "original.xml").read_bytes()
    )

    assert frontiers is not None
    assert copernicus is not None
    assert "; **Table 2**" in frontiers.markdown_text
    assert ";\n**Table 2**" not in frontiers.markdown_text
    assert copernicus.abstract_sections
    abstract = copernicus.abstract_sections[0]["text"]
    assert "rate constant for OH + C<sub>3</sub>" in abstract
    assert "OH\n+ C<sub>3</sub>" not in abstract
