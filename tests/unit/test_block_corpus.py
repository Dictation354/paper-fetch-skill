from __future__ import annotations

import pytest

from tests.block_fixtures import BlockFixture, execute_block_fixture, iter_block_samples


BLOCK_FIXTURES = iter_block_samples()


def _fixture_id(fixture: BlockFixture) -> str:
    return f"{fixture.provider}:{fixture.doi}:{fixture.provider_route}"


@pytest.mark.parametrize("fixture", BLOCK_FIXTURES, ids=_fixture_id)
def test_block_raw_response_matches_current_extractor_rejection_contract(
    fixture: BlockFixture,
) -> None:
    result = execute_block_fixture(fixture)

    assert result.accepted is False
    assert result.reason == fixture.expected_reason
    assert result.failure_code == fixture.expected_failure_code
    assert result.content_kind == fixture.expected_content_kind
    assert result.provider_route == fixture.provider_route
    assert result.source_identity == fixture.source_identity
    assert result.content_kind != "fulltext"
