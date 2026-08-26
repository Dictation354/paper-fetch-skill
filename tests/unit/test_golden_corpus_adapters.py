from __future__ import annotations

from tests.golden_corpus import (
    GOLDEN_CORPUS_SHARD_COUNT,
    golden_corpus_replay_inventory,
    iter_golden_corpus_fixtures,
    iter_golden_corpus_representative_fixtures,
    plan_golden_corpus_shards,
)
from tests.golden_corpus_adapters import adapter_provider_names, golden_corpus_adapter


def test_golden_corpus_adapters_cover_all_fixture_providers() -> None:
    fixture_providers = {fixture.provider for fixture in iter_golden_corpus_fixtures()}

    assert fixture_providers == set(adapter_provider_names())


def test_golden_corpus_adapters_declare_contracts_for_all_fixture_routes() -> None:
    for fixture in iter_golden_corpus_fixtures():
        contract = golden_corpus_adapter(fixture.provider).contract_for_fixture(fixture)

        assert fixture.route_kind == contract.route_kind
        assert fixture.content_type.startswith(contract.content_prefix)


def test_golden_corpus_adapters_provide_one_representative_per_provider() -> None:
    representatives = iter_golden_corpus_representative_fixtures()

    assert {fixture.provider for fixture in representatives} == set(
        adapter_provider_names()
    )


def test_golden_corpus_inventory_separates_non_replay_evidence() -> None:
    inventory = golden_corpus_replay_inventory()

    assert inventory.count("real_replay") == 140
    assert inventory.count("synthetic") == 2
    assert inventory.count("unit_only") == 0
    assert inventory.count("manifest_only") == 15
    assert inventory.count("unexecutable") == 0
    assert all(
        record.fixture is None
        for record in inventory.records
        if record.category != "real_replay"
    )


def test_exact_fixture_shards_cover_every_fixture_once_without_splitting_provider() -> (
    None
):
    fixtures = iter_golden_corpus_fixtures()
    shards = plan_golden_corpus_shards(fixtures)

    assert len(shards) == GOLDEN_CORPUS_SHARD_COUNT
    assert [len(shard) for shard in shards] == [36, 35, 35, 34]
    assert [sorted({fixture.provider for fixture in shard}) for shard in shards] == [
        ["acs", "aip", "elsevier", "ieee", "mdpi"],
        ["annualreviews", "arxiv", "oxfordacademic", "springer", "wiley"],
        ["ams", "copernicus", "frontiers", "iop", "plos"],
        ["pnas", "royalsocietypublishing", "science", "tandf"],
    ]
    flattened = [fixture.sample_id for shard in shards for fixture in shard]
    assert len(flattened) == len(set(flattened)) == len(fixtures) == 140
    provider_to_shards: dict[str, set[int]] = {}
    for shard_index, shard in enumerate(shards):
        for fixture in shard:
            provider_to_shards.setdefault(fixture.provider, set()).add(shard_index)
    assert all(len(indices) == 1 for indices in provider_to_shards.values())
