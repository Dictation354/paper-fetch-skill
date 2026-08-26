"""Shared fetch orchestration for CLI and protocol adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..artifacts import DEFAULT_ARTIFACT_MODE, ArtifactMode
from ..http import HttpTransport
from ..models import FetchEnvelope, OutputMode, RenderOptions
from ..runtime import RuntimeContext
from .rendering import save_markdown_to_disk
from .types import FetchStrategy


FetchPaperFn = Callable[..., FetchEnvelope]
LoadCachedEnvelope = Callable[[RuntimeContext], FetchEnvelope | None]
WriteCachedEnvelope = Callable[[FetchEnvelope], None]
MarkdownSavedHook = Callable[[FetchEnvelope, Path], None]


@dataclass(frozen=True)
class FetchPipelineCacheHooks:
    load: LoadCachedEnvelope | None = None
    write: WriteCachedEnvelope | None = None


@dataclass(frozen=True)
class MarkdownSaveSpec:
    output_dir: Path
    render: RenderOptions
    filename: str | None = None
    request_label: str = "save_markdown"
    on_saved: MarkdownSavedHook | None = None
    overwrite: bool = True


@dataclass(frozen=True)
class FetchPipelineRequest:
    query: str
    modes: set[OutputMode]
    strategy: FetchStrategy
    render: RenderOptions
    env: Mapping[str, str] | None = None
    download_dir: Path | None = None
    artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE
    no_download: bool = False
    transport: HttpTransport | None = None
    clients: Mapping[str, object] | None = None
    cancel_check: Callable[[], bool] | None = None
    fetch_cache: Any | None = None
    context: RuntimeContext | None = None
    cache_hooks: FetchPipelineCacheHooks = field(
        default_factory=FetchPipelineCacheHooks
    )
    markdown_save: MarkdownSaveSpec | None = None


@dataclass(frozen=True)
class FetchPipelineResult:
    envelope: FetchEnvelope
    saved_markdown_path: Path | None = None
    cache_hit: bool = False


@dataclass(frozen=True)
class FetchPipeline:
    fetch_paper_fn: FetchPaperFn

    def runtime_context(self, request: FetchPipelineRequest) -> RuntimeContext:
        if request.context is not None:
            return request.context
        artifact_mode: ArtifactMode = (
            "none" if request.no_download else request.artifact_mode
        )
        return RuntimeContext(
            env=request.env,
            transport=request.transport,
            clients=request.clients,
            download_dir=None if request.no_download else request.download_dir,
            artifact_mode=artifact_mode,
            cancel_check=request.cancel_check,
            fetch_cache=request.fetch_cache,
        )

    def fetch_with_context(
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

    def run(self, request: FetchPipelineRequest) -> FetchPipelineResult:
        context = self.runtime_context(request)
        owns_context = request.context is None
        try:
            cache_hit = False
            cached_envelope = (
                request.cache_hooks.load(context)
                if request.cache_hooks.load is not None
                else None
            )
            if cached_envelope is not None:
                envelope = cached_envelope
                cache_hit = True
            else:
                envelope = self.fetch_with_context(request, context=context)
                if request.cache_hooks.write is not None:
                    context.raise_if_cancelled()
                    request.cache_hooks.write(envelope)

            saved_markdown_path = None
            if request.markdown_save is not None:
                context.raise_if_cancelled()
                saved_markdown_path = save_markdown_to_disk(
                    envelope,
                    output_dir=request.markdown_save.output_dir,
                    render=request.markdown_save.render,
                    markdown_filename=request.markdown_save.filename,
                    request_label=request.markdown_save.request_label,
                    overwrite=request.markdown_save.overwrite,
                    commit_guard=context.commit_guard,
                )
                if (
                    saved_markdown_path is not None
                    and request.markdown_save.on_saved is not None
                ):
                    context.raise_if_cancelled()
                    request.markdown_save.on_saved(envelope, saved_markdown_path)

            return FetchPipelineResult(
                envelope=envelope,
                saved_markdown_path=saved_markdown_path,
                cache_hit=cache_hit,
            )
        finally:
            if owns_context:
                context.close()


__all__ = [
    "FetchPipeline",
    "FetchPipelineCacheHooks",
    "FetchPipelineRequest",
    "FetchPipelineResult",
    "MarkdownSaveSpec",
]
