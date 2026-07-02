from __future__ import annotations

from collections import Counter
import os

import pytest

from tests.golden_corpus import (
    GoldenCorpusFixture,
    build_article_from_fixture,
    expected_summary_from_article,
    golden_contract_for_fixture,
    iter_golden_corpus_fixtures,
    iter_golden_corpus_representative_fixtures,
    lightweight_positive_summary_from_fixture,
)
from tests.golden_corpus_adapters import golden_corpus_adapter


FULL_GOLDEN_ENV = "PAPER_FETCH_RUN_FULL_GOLDEN"


GOLDEN_CORPUS_FIXTURES = iter_golden_corpus_fixtures()
REPRESENTATIVE_GOLDEN_CORPUS_FIXTURES = iter_golden_corpus_representative_fixtures()


def _fixture_id(fixture: GoldenCorpusFixture) -> str:
    return f"{fixture.provider}:{fixture.doi}"


def test_golden_corpus_is_balanced_across_publishers() -> None:
    assert len(GOLDEN_CORPUS_FIXTURES) == 132
    assert Counter(fixture.provider for fixture in GOLDEN_CORPUS_FIXTURES) == Counter(
        {
            "acs": 3,
            "aip": 2,
            "ams": 11,
            "annualreviews": 4,
            "arxiv": 4,
            "copernicus": 12,
            "elsevier": 11,
            "ieee": 8,
            "iop": 3,
            "mdpi": 9,
            "oxfordacademic": 3,
            "plos": 8,
            "pnas": 11,
            "royalsocietypublishing": 7,
            "science": 12,
            "springer": 13,
            "wiley": 11,
        }
    )


@pytest.mark.parametrize("fixture", GOLDEN_CORPUS_FIXTURES, ids=_fixture_id)
def test_golden_corpus_lightweight_contracts_hold_across_full_corpus(
    fixture: GoldenCorpusFixture,
) -> None:
    expected = fixture.load_expected()
    actual = lightweight_positive_summary_from_fixture(fixture)
    contract = golden_contract_for_fixture(fixture)

    assert fixture.route_kind == contract.route_kind
    assert fixture.content_type.startswith(contract.content_prefix)
    assert fixture.source_url
    assert actual["doi"] == fixture.doi

    for field_name in actual["validated_fields"]:
        if expected["has"][field_name]:
            assert actual["has"][field_name], f"Expected {field_name} for {fixture.doi}"

    if (
        fixture.provider in {"ams", "science", "pnas", "wiley"}
        and fixture.route_kind == "html"
    ):
        assert list(actual["blocking_fallback_signals"]) == [], (
            f"Positive fixture leaked paywall signals for {fixture.doi}"
        )
        assert actual["source_candidate_hit"], (
            f"Expected generated HTML candidates to include source URL for {fixture.doi}"
        )


def test_golden_corpus_representative_fixtures_cover_primary_fulltext_paths_by_provider() -> (
    None
):
    assert len(REPRESENTATIVE_GOLDEN_CORPUS_FIXTURES) == 17
    assert Counter(
        fixture.provider for fixture in REPRESENTATIVE_GOLDEN_CORPUS_FIXTURES
    ) == Counter(
        {
            "acs": 1,
            "aip": 1,
            "ams": 1,
            "annualreviews": 1,
            "arxiv": 1,
            "copernicus": 1,
            "elsevier": 1,
            "ieee": 1,
            "iop": 1,
            "mdpi": 1,
            "oxfordacademic": 1,
            "plos": 1,
            "pnas": 1,
            "royalsocietypublishing": 1,
            "science": 1,
            "springer": 1,
            "wiley": 1,
        }
    )


@pytest.mark.parametrize(
    "fixture", REPRESENTATIVE_GOLDEN_CORPUS_FIXTURES, ids=_fixture_id
)
def test_golden_corpus_representative_fixture_matches_primary_fulltext_path(
    fixture: GoldenCorpusFixture,
) -> None:
    article = build_article_from_fixture(fixture)
    actual = expected_summary_from_article(article)
    expected = fixture.load_expected()
    contract = golden_contract_for_fixture(fixture)
    adapter = golden_corpus_adapter(fixture.provider)

    assert article.source == contract.source
    assert contract.primary_marker in article.quality.source_trail
    assert article.quality.content_kind == "fulltext"
    assert actual["expected_content_kind"] == "fulltext"
    assert expected["expected_content_kind"] == "fulltext"

    for field_name, expected_present in expected["has"].items():
        if expected_present:
            assert actual["has"][field_name], f"Expected {field_name} for {fixture.doi}"

    for count_name, expected_count in expected["counts"].items():
        if (
            adapter.representative_count_fields is not None
            and count_name not in adapter.representative_count_fields
        ):
            continue
        if expected_count > 0:
            assert actual["counts"][count_name] > 0, (
                f"Expected positive {count_name} count for {fixture.doi}"
            )


@pytest.mark.skipif(
    os.environ.get(FULL_GOLDEN_ENV) != "1",
    reason=f"Set {FULL_GOLDEN_ENV}=1 to run full 132-fixture golden corpus regression.",
)
@pytest.mark.parametrize("fixture", GOLDEN_CORPUS_FIXTURES, ids=_fixture_id)
def test_golden_corpus_expected_summary_matches_current_extractor(
    fixture: GoldenCorpusFixture,
) -> None:
    article = build_article_from_fixture(fixture)
    actual = expected_summary_from_article(article)
    expected = fixture.load_expected()

    assert actual["expected_content_kind"] == "fulltext"
    assert expected["expected_content_kind"] == "fulltext"
    assert actual == expected
