from __future__ import annotations

from typing import Any
from collections.abc import Mapping

import pytest

from paper_fetch.providers._waterfall import WaterfallStep
from paper_fetch.providers.base import ProviderClient, RawFulltextPayload
from paper_fetch.runtime import RuntimeContext


class EmptyWaterfallClient(ProviderClient):
    name = "empty_waterfall"


def test_default_fetch_raw_fulltext_without_waterfall_steps_raises() -> None:
    client = EmptyWaterfallClient()

    with pytest.raises(
        NotImplementedError, match="override fetch_raw_fulltext.*waterfall_steps"
    ):
        client.fetch_raw_fulltext("10.0000/empty", {}, context=None)


def test_default_fetch_raw_fulltext_runs_declared_waterfall_steps() -> None:
    seen: dict[str, Any] = {}

    def fetch_step(
        client: ProviderClient,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        seen["client"] = client
        seen["doi"] = doi
        seen["metadata"] = dict(metadata)
        seen["context"] = context
        return RawFulltextPayload(
            provider=client.name,
            source_url="https://example.test/fulltext",
            content_type="text/plain",
            body=b"full text",
        )

    class DeclarativeWaterfallClient(ProviderClient):
        name = "declarative_waterfall"
        waterfall_steps = (
            WaterfallStep(
                label="html",
                run=fetch_step,
                success_markers=("fulltext:declarative_waterfall_html_ok",),
            ),
        )

    runtime_context = RuntimeContext()
    client = DeclarativeWaterfallClient()
    payload = client.fetch_raw_fulltext(
        "10.0000/waterfall",
        {"title": "Waterfall"},
        context=runtime_context,
    )

    assert isinstance(payload, RawFulltextPayload)
    assert payload.provider == "declarative_waterfall"
    assert payload.body == b"full text"
    assert seen == {
        "client": client,
        "doi": "10.0000/waterfall",
        "metadata": {"title": "Waterfall"},
        "context": runtime_context,
    }
