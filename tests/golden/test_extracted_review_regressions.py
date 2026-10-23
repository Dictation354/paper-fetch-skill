"""Complete captured-source replays for the 2026-10-21 extraction fixes."""

import pytest

from paper_fetch.artifacts import ArtifactStore
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.golden_criteria import golden_criteria_asset
from tests.support.replay import build_article_from_fixture, persisted_fixture_markdown


DOIS = (
    "10.1111/gcb.16561",
    "10.1175/bams-d-24-0223.1",
    "10.1038/d41586-022-01795-9",
    "10.1038/d41586-023-01829-w",
    "10.1088/1681-7575/ae1dfc",
    "10.1088/1748-9326/ab7d02",
    "10.1088/2058-9565/ac3460",
    "10.1109/TCOMM.2024.3395332",
    "10.48550/arxiv.0811.2625v2",
    "10.48550/arxiv.2006.11239v2",
    "10.48550/arxiv.2605.06556v1",
    "10.48550/arxiv.2606.00587v2",
)


@pytest.mark.parametrize("doi", DOIS)
def test_reviewed_complete_output_matches_captured_adapter_replay(doi, tmp_path):
    fixture = golden_corpus_fixture_for_doi(doi)
    article = build_article_from_fixture(fixture)
    markdown = persisted_fixture_markdown(fixture, article)
    output = ArtifactStore.from_download_dir(tmp_path).write_text_file(
        tmp_path / "extracted.md",
        markdown,
    )
    assert output.read_text() == golden_criteria_asset(doi, "extracted.md").read_text()
    if fixture.provider == "iop":
        assert "Download figure:" not in markdown
    if fixture.sample_id.startswith("10.1038_d41586"):
        assert ". Credit:" in markdown
    if fixture.sample_id == "10.1109_TCOMM.2024.3395332":
        assert r"**TABLE I** Threshold Values of $\Gamma _{ic}$" in markdown
        assert r"**TABLE II** $|P({\mathcal {D}}_{j}^{i})|$" in markdown
    if fixture.sample_id == "10.48550_arxiv.2606.00587v2":
        assert r"\$75/MWh" in markdown
        assert r"\$0.15/TH/s/day" in markdown
    if fixture.sample_id == "10.48550_arxiv.2006.11239v2":
        assert (
            r"$\|\tilde{\boldsymbol{\mu}}-\tilde{\boldsymbol{\mu}}_{\theta}\|^{2}$"
            in markdown
        )
