"""Real-source coverage plus explicitly classified mutation controls."""

from collections import Counter
import re

import pytest

from tests.golden_corpus import (
    iter_golden_corpus_fixtures,
    golden_corpus_fixture_for_doi,
)
from tests.support.canonical_content import source_soup, source_formulas, formula_route
from tests.support.replay import build_article_from_fixture
from tests.support.scientific_content import assert_mathml_formulas


def test_placeholder_mathml_is_checked_in_every_captured_paper():
    counts = Counter()
    papers = Counter()
    for fixture in iter_golden_corpus_fixtures():
        if (
            fixture.provider not in {"science", "pnas"}
            or fixture.raw_path.suffix == ".pdf"
        ):
            continue
        nodes = [
            n
            for n in source_formulas(fixture, source_soup(fixture))
            if n.get("alttext") == "No alternative text available"
        ]
        if not nodes:
            continue
        assert all(formula_route(n) == "mathml" for n in nodes)
        article = build_article_from_fixture(fixture)
        markdown = article.to_ai_markdown(
            include_refs="all", asset_profile="all", max_tokens="full_text"
        )
        assert assert_mathml_formulas(nodes, markdown) == len(nodes)
        counts[fixture.provider] += len(nodes)
        papers[fixture.provider] += 1
    assert counts == {"pnas": 325, "science": 43}
    assert papers == {"pnas": 7, "science": 5}


@pytest.mark.parametrize("doi", ["10.1126/science.adp0212", "10.1073/pnas.2406303121"])
def test_real_formula_assertions_reject_empty_or_formula_deleted_output(doi):
    fixture = golden_corpus_fixture_for_doi(doi)
    nodes = [
        n
        for n in source_formulas(fixture, source_soup(fixture))
        if n.get("alttext") == "No alternative text available"
    ]
    assert nodes
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    damaged = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$", "", markdown, flags=re.S)
    for text in ["", damaged]:
        with pytest.raises(AssertionError):
            assert_mathml_formulas(nodes, text)


def test_real_figure_bindings_reject_swapped_assets():
    from tests.support.object_content import assert_figure_bindings

    fixture = golden_corpus_fixture_for_doi("10.5194/acp-24-1-2024")
    soup = source_soup(fixture)
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    assert assert_figure_bindings(fixture, soup, article, markdown) >= 2
    images = list(re.finditer(r"!\[[^\]]*\]\(([^\s)]+)\)", markdown))
    first = images[0][1]
    second = next(m[1] for m in images if m[1] != first)
    damaged = (
        markdown.replace(first, "SWAPPEDFIGURETOKEN")
        .replace(second, first)
        .replace("SWAPPEDFIGURETOKEN", second)
    )
    with pytest.raises(AssertionError):
        assert_figure_bindings(fixture, soup, article, damaged)


def test_real_table_checks_reject_row_loss_and_whole_table_relocation():
    from tests.support.canonical_content import source_tables, source_prose_blocks
    from tests.support.object_content import assert_source_tables, rendered_tables

    fixture = golden_corpus_fixture_for_doi("10.5194/bg-21-1-2024")
    soup = source_soup(fixture)
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    tables = source_tables(fixture, soup)
    prose = [r for _, runs in source_prose_blocks(fixture, soup) for r in runs]
    assert_source_tables(tables, markdown, prose_runs=prose, provider=fixture.provider)
    group = rendered_tables(markdown)[0]
    without = markdown[: group.start] + markdown[group.end :]
    rows = markdown[group.start : group.end].splitlines()
    assert len(rows) >= 3
    del rows[2]
    row_loss = markdown[: group.start] + "\n".join(rows) + markdown[group.end :]
    for damaged in [
        row_loss,
        without,
        without + "\n\n" + markdown[group.start : group.end],
    ]:
        with pytest.raises(AssertionError):
            assert_source_tables(
                tables, damaged, prose_runs=prose, provider=fixture.provider
            )
