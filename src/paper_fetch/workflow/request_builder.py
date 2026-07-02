"""Fetch pipeline request assembly helpers shared by adapters."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from ..artifacts import DEFAULT_ARTIFACT_MODE, ArtifactMode
from ..http import HttpTransport
from ..models import OutputMode, RenderOptions
from ..runtime import RuntimeContext
from .pipeline import FetchPipelineCacheHooks, FetchPipelineRequest, MarkdownSaveSpec
from .types import FetchStrategy


def build_fetch_pipeline_request(
    *,
    query: str,
    modes: Iterable[OutputMode],
    strategy: FetchStrategy,
    render: RenderOptions,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None = None,
    artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE,
    no_download: bool = False,
    transport: HttpTransport | None = None,
    clients: Mapping[str, object] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    context: RuntimeContext | None = None,
    fetch_cache: Any | None = None,
    cache_hooks: FetchPipelineCacheHooks | None = None,
    markdown_save: MarkdownSaveSpec | None = None,
) -> FetchPipelineRequest:
    runtime_env = (
        dict(context.env) if context is not None and context.env is not None else env
    )
    return FetchPipelineRequest(
        query=query,
        modes=set(modes),
        strategy=strategy,
        render=render,
        env=runtime_env,
        download_dir=download_dir,
        artifact_mode=artifact_mode,
        no_download=no_download,
        transport=context.transport if context is not None else transport,
        clients=context.clients if context is not None else clients,
        cancel_check=context.cancel_check if context is not None else cancel_check,
        fetch_cache=fetch_cache,
        cache_hooks=cache_hooks or FetchPipelineCacheHooks(),
        markdown_save=markdown_save,
    )


__all__ = ["build_fetch_pipeline_request"]
