"""Unmodified archived TeX and image members; no synthetic source tarball."""

from paper_fetch.providers._arxiv_source_archive import (
    _extract_arxiv_source_figure_references,
)
from tests.golden_criteria import golden_criteria_asset


def test_original_tex_resolves_nested_figure_paths_and_exact_bytes():
    doi = "10.48550/arxiv.2606.00587v2"
    names = [
        "figs/Near_peak_Event.png",
        "figs/lz_growth.png",
        "figs/Parallel_Trend.png",
        "figs/bitcoin_miners_price_elasticity.png",
        "figs/NP_Risk_Index_Response.png",
        "extended_data/elec-price-hashprice.png",
        "extended_data/np-risk-hashprice-ercot.png",
    ]
    files = {
        name: golden_criteria_asset(
            doi, "acquisition/source-members/" + name
        ).read_bytes()
        for name in ["sn-article.tex", *names]
    }
    tex = files["sn-article.tex"].decode()
    for name in names:
        assert "{" + name + "}" in tex
        assert len(files[name]) > 1000
    figures = _extract_arxiv_source_figure_references(files)
    assert [figure["source_path"] for figure in figures] == names
    for figure in figures:
        assert figure["body"] == files[figure["source_path"]]
    assert (
        "Threshold-like wholesale-electricity-price responsiveness"
        in figures[3]["caption"]
    )
    assert figures[3]["label"] == "fig3"

    assert figures[5]["caption"].startswith(
        "Growth-adjusted Bitcoin-mining load in relation to logged electricity prices"
    )
    assert figures[5]["label"] == "edf:elec-price-hashprice"
    assert figures[6]["caption"].startswith(
        "Growth-adjusted Bitcoin-mining load in relation to logged hashprice"
    )
    assert figures[6]["label"] == "edf:np-risk-hashprice-ercot"
