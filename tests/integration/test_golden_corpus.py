from __future__ import annotations

from collections import Counter
import os

import pytest

from tests.golden_corpus import (
    GOLDEN_CORPUS_SHARD_COUNT,
    GoldenCorpusFixture,
    build_article_from_fixture,
    expected_summary_from_article,
    golden_contract_for_fixture,
    iter_golden_corpus_fixtures,
    iter_golden_corpus_representative_fixtures,
    lightweight_positive_summary_from_fixture,
    plan_golden_corpus_shards,
)
from tests.golden_corpus_adapters import golden_corpus_adapter
from paper_fetch.provider_catalog import provider_names


FULL_GOLDEN_ENV = "PAPER_FETCH_RUN_FULL_GOLDEN"
GOLDEN_SHARD_ENV = "PAPER_FETCH_GOLDEN_SHARD"


GOLDEN_CORPUS_FIXTURES = iter_golden_corpus_fixtures()
REPRESENTATIVE_GOLDEN_CORPUS_FIXTURES = iter_golden_corpus_representative_fixtures()


def _exact_golden_fixtures() -> tuple[GoldenCorpusFixture, ...]:
    selected = os.environ.get(GOLDEN_SHARD_ENV, "").strip().lower()
    if os.environ.get(FULL_GOLDEN_ENV) == "1" or selected == "all":
        return GOLDEN_CORPUS_FIXTURES
    if not selected:
        return ()
    try:
        shard_index = int(selected)
    except ValueError as exc:
        raise ValueError(
            f"{GOLDEN_SHARD_ENV} must be all or an integer shard index"
        ) from exc
    shards = plan_golden_corpus_shards(GOLDEN_CORPUS_FIXTURES)
    if shard_index < 0 or shard_index >= len(shards):
        raise ValueError(f"{GOLDEN_SHARD_ENV} must be between 0 and {len(shards) - 1}")
    return shards[shard_index]


EXACT_GOLDEN_CORPUS_FIXTURES = _exact_golden_fixtures()


def _fixture_id(fixture: GoldenCorpusFixture) -> str:
    return f"{fixture.provider}:{fixture.doi}"


def test_golden_corpus_uses_declared_providers() -> None:
    assert GOLDEN_CORPUS_FIXTURES
    assert {fixture.provider for fixture in GOLDEN_CORPUS_FIXTURES} <= set(
        provider_names()
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
    representatives = Counter(
        fixture.provider for fixture in REPRESENTATIVE_GOLDEN_CORPUS_FIXTURES
    )
    assert set(representatives) == {
        fixture.provider for fixture in GOLDEN_CORPUS_FIXTURES
    }
    assert set(representatives.values()) == {1}


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
    not EXACT_GOLDEN_CORPUS_FIXTURES,
    reason=(
        f"Set {GOLDEN_SHARD_ENV}=0..{GOLDEN_CORPUS_SHARD_COUNT - 1} for one "
        f"provider shard or {GOLDEN_SHARD_ENV}=all for all exact fixtures."
    ),
)
@pytest.mark.parametrize("fixture", EXACT_GOLDEN_CORPUS_FIXTURES, ids=_fixture_id)
def test_golden_corpus_expected_summary_matches_current_extractor(
    fixture: GoldenCorpusFixture,
) -> None:
    article = build_article_from_fixture(fixture)
    actual = expected_summary_from_article(article)
    expected = fixture.load_expected()

    assert actual["expected_content_kind"] == "fulltext"
    assert expected["expected_content_kind"] == "fulltext"
    assert actual == expected
