"""Request ownership and logical-result fan-out shared by CLI and MCP batches."""

from __future__ import annotations

import copy
from contextlib import suppress
from collections.abc import Callable, Iterator
from dataclasses import replace
from typing import Any, Generic, TypeVar

from ..runtime import RuntimeContext
from .batch_routing import (
    _BatchRoutingItem,
    deduplicate_batch_items,
    fanout_batch_items,
    resolve_batch_item_routing,
)
from .batch_runner import BatchItemResult, BatchRunResult, run_batch

Item = TypeVar("Item", bound=_BatchRoutingItem)
Result = TypeVar("Result")


class BatchExecutionSession(Generic[Item]):
    """Share preparation/transport while keeping every logical request isolated."""

    def __init__(
        self,
        root: RuntimeContext,
        items: list[Item],
        *,
        asset_profile: str | None = None,
        cancelled: Callable[[int], bool] | None = None,
    ):
        self.root = root
        self.duplicates: dict[int, tuple[Item, ...]] = {}
        self.cancelled = cancelled

        def cancellation(item: Item) -> Callable[[], bool]:
            return lambda: self.group_cancelled(item)

        self.contexts = {
            item.index: root.new_request_context(
                asset_profile=asset_profile,
                cancel_check=cancellation(item)
                if cancelled is not None
                else root.cancel_check,
            )
            for item in items
        }

    def group_cancelled(self, item: Item) -> bool:
        return bool(
            self.cancelled
            and all(
                self.cancelled(member.index)
                for member in fanout_batch_items(item, self.duplicates)
            )
        )

    def resolve(self, item: Item, resolver: Callable[..., Any]) -> Item:
        return resolve_batch_item_routing(
            item, context=self.contexts[item.index], resolver=resolver
        )

    @staticmethod
    def resolve_all(
        items: list[Item],
        worker: Callable[[Item], Item],
        *,
        max_workers: int,
        **options: Any,
    ) -> BatchRunResult[Item, Item]:
        return run_batch(
            items,
            worker,
            max_workers=max_workers,
            lane_key=lambda item: f"resolve:{item.index}",
            **options,
        )

    def group(
        self, items: list[Item]
    ) -> tuple[list[Item], dict[int, tuple[Item, ...]]]:
        representatives, self.duplicates = deduplicate_batch_items(items)
        return representatives, self.duplicates

    def fanout(
        self, result: BatchItemResult[Item, Result]
    ) -> Iterator[BatchItemResult[Item, Result]]:
        for position, item in enumerate(
            fanout_batch_items(result.item, self.duplicates)
        ):
            value = result.value
            if position and value is not None:
                with suppress(Exception):
                    value = copy.deepcopy(value)
            yield replace(result, item=item, lane_key=item.lane_key, value=value)

    def fence(self) -> None:
        for context in self.contexts.values():
            context.fence_commits()

    def close(self) -> None:
        for context in self.contexts.values():
            context.close()
