from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from paper_fetch.manifest_writer import RunManifestStore
from paper_fetch.workflow.batch_lifecycle import (
    BatchLifecycleOverwriteError,
    prepare_batch_run,
)


RUN_ID = UUID("00000000-0000-0000-0000-000000000123")
NOW = datetime(2026, 7, 26, tzinfo=UTC)


@dataclass(frozen=True)
class Item:
    index: int
    query: str
    attempt: int


def _item(index: int, query: str, attempt: int) -> Item:
    return Item(index=index, query=query, attempt=attempt)


def test_in_memory_preparation_uses_ordered_inputs_and_first_attempts() -> None:
    prepared = prepare_batch_run(
        store=None,
        queries=["10.1000/one", "10.1000/two"],
        request_parameters={"modes": ["article", "markdown"]},
        tool_version="4.0.0",
        requested_run_id=RUN_ID,
        resume=False,
        overwrite=False,
        clock=lambda: NOW,
        uuid_factory=lambda: RUN_ID,
        item_factory=_item,
    )

    assert prepared.run_id == RUN_ID
    assert prepared.manifest.events_path == "<memory>"
    assert [item.index for item in prepared.items] == [1, 2]
    assert [item.attempt for item in prepared.items] == [1, 1]
    assert prepared.reused_count == 0
    assert prepared.append_events is False


def test_durable_preparation_protects_existing_manifest_and_events(
    tmp_path: Path,
) -> None:
    store = RunManifestStore.for_new_run(
        manifest_path=tmp_path / "run-manifest.json",
        events_path=tmp_path / "batch-results.jsonl",
    )
    store.manifest_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(BatchLifecycleOverwriteError, match="run manifest"):
        prepare_batch_run(
            store=store,
            queries=["10.1000/one"],
            request_parameters={},
            tool_version="4.0.0",
            requested_run_id=RUN_ID,
            resume=False,
            overwrite=False,
            clock=lambda: NOW,
            uuid_factory=lambda: RUN_ID,
            item_factory=_item,
        )
