"""Independent complete captures verify Science cells and Springer Methods ethics."""

from pathlib import Path
import re

from bs4 import BeautifulSoup
import pytest

from tests.paths import REPO_ROOT
from tests.support.verified_source_inputs import (
    build_verified_source_article,
    inspect_original,
)


def captured_article(doi, provider, suffix):
    path = (
        Path("tests/fixtures/golden_criteria")
        / doi.replace("/", "_")
        / "acquisition"
        / suffix
    )
    body = (REPO_ROOT / path).read_bytes()
    url = (
        ("https://www.nature.com/articles/" + doi.split("/")[-1])
        if provider == "springer"
        else "https://www.science.org/doi/full/" + doi
    )
    identity = inspect_original(body, provider, doi, url)
    assert identity and identity["identity"] == "matched"
    article = build_verified_source_article(
        dict(
            sample_id=doi.replace("/", "_"),
            doi=doi,
            provider=provider,
            format="html",
            source=str(path),
            source_url=url,
            identity=identity,
        )
    )
    return BeautifulSoup(body.decode(), "lxml"), article


def plain(text):
    return " ".join(re.sub(r"[*_`]", "", text).replace("<br>", " ").split())


def table_cell_plain(text):
    text = re.sub(r"<sup>([0-9, ]+)</sup>", r"(\1)", text)
    return re.sub(r"\s*([(),])\s*", r"\1", plain(text))


def test_science_table_three_keeps_every_source_field_and_missing_tail():
    soup, article = captured_article(
        "10.1126/sciadv.abj3309",
        "science",
        "source-completion-2026-09-18/001-browser_rendered_dom.html",
    )
    table = soup.select("table")[2]
    rows = [
        [
            table_cell_plain(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        for row in table.find_all("tr")
    ]
    assert [len(row) for row in rows] == [3, 3, 3, 2]
    assert not table.select("[rowspan], [colspan]")
    assert rows[-1] == [
        "Recent deforestation",
        "Percentage of the cell deforested at year",
    ]
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    start = markdown.index(
        next(
            line
            for line in markdown.splitlines()
            if line.startswith("|") and "Representation in the" in line
        )
    )
    lines = markdown[start:].splitlines()
    rendered = []
    for line in lines:
        if not line.startswith("|"):
            break
        if re.fullmatch(r"[| :\-]+", line):
            continue
        rendered.append([table_cell_plain(cell) for cell in line.strip("|").split("|")])
    assert rendered == [*rows[:-1], [*rows[-1], ""]]
    assert "data row 3 supplies 2 of 3 cells" in markdown
    losses = article.quality.semantic_losses
    assert (
        losses.table_fallback_count
        == losses.table_layout_degraded_count
        == losses.table_semantic_loss_count
        == 0
    )


@pytest.mark.parametrize(
    "doi, heading",
    [
        ("10.1038/s41467-022-32108-3", "Ethics compliance"),
        ("10.1038/s41522-026-01027-2", "Ethics statement"),
    ],
)
def test_springer_methods_ethics_full_source_paragraph_and_order(doi, heading):
    soup, article = captured_article(
        doi, "springer", "template-gaps-2026-09-16/article-response.html"
    )
    node = next(
        node for node in soup.select("h3") if node.get_text(strip=True) == heading
    )
    assert any(
        parent.name == "section" and parent.get("data-title") == "Methods"
        for parent in node.parents
    )
    source_paragraphs = []
    for sibling in node.next_siblings:
        if getattr(sibling, "name", "") in {"h2", "h3", "h4"}:
            break
        if getattr(sibling, "name", "") == "p":
            source_paragraphs.append(sibling.get_text(" ", strip=True))
    section = next(
        section for section in article.sections if section.heading == heading
    )
    assert section.kind == "body"
    assert plain(section.text) == plain(" ".join(source_paragraphs))
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    following = node.find_next("h3").get_text(strip=True)
    preceding = node.find_previous(["h2", "h3"])
    preceding_level = "## " if preceding.name == "h2" else "### "
    assert markdown.index(
        preceding_level + preceding.get_text(strip=True)
    ) < markdown.index("### " + heading)
    assert (
        markdown.index("## Methods")
        < markdown.index("### " + heading)
        < markdown.index("### " + following)
    )
    assert "## Ethics declarations" not in markdown
    assert "### Competing interests" not in markdown
    if "32108" in doi:
        assert "46 years" in section.text
        assert "Australian Bird and Bat Banding Scheme" in section.text
    else:
        assert "AHAUXMSQ2024053" in section.text
