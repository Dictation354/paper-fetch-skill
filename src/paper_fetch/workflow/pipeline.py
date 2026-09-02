"""Fetch service execution shared by CLI and protocol adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..models import FetchEnvelope, OutputMode, RenderOptions
from ..runtime import RuntimeContext
from .types import FetchStrategy


FetchPaperFn = Callable[..., FetchEnvelope]


@dataclass(frozen=True)
class FetchPipelineRequest:
    query: str
    modes: set[OutputMode]
    strategy: FetchStrategy
    render: RenderOptions


@dataclass(frozen=True)
class FetchPipeline:
    fetch_paper_fn: FetchPaperFn

    def run(
        self,
        request: FetchPipelineRequest,
        *,
        context: RuntimeContext,
    ) -> FetchEnvelope:
        return self.fetch_paper_fn(
            request.query,
            modes=request.modes,
            strategy=request.strategy,
            render=request.render,
            context=context,
        )


__all__ = ["FetchPipeline", "FetchPipelineRequest"]
