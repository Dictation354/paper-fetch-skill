from __future__ import annotations

import os

import pytest

from tests.golden_corpus import (
    GOLDEN_CORPUS_SHARD_COUNT,
    GoldenCorpusFixture,
    build_article_from_fixture,
    expected_summary_from_article,
    iter_golden_corpus_fixtures,
    plan_golden_corpus_shards,
)
from paper_fetch.provider_catalog import provider_names


FULL_GOLDEN_ENV = "PAPER_FETCH_RUN_FULL_GOLDEN"
GOLDEN_SHARD_ENV = "PAPER_FETCH_GOLDEN_SHARD"


GOLDEN_CORPUS_FIXTURES = iter_golden_corpus_fixtures()


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
