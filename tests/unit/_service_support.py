# ruff: noqa: F401
from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from paper_fetch import runtime as runtime_module
from paper_fetch import service as paper_fetch
from paper_fetch.artifacts import ArtifactStore
from paper_fetch.runtime import RuntimeContext
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.providers import _springer_html as springer_html_helper
from paper_fetch.providers import pnas as pnas_provider, science as science_provider
from paper_fetch.providers.base import (
    ProviderArtifacts,
    ProviderClient,
    ProviderContent,
    ProviderFetchResult,
    RawFulltextPayload,
)
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.tracing import trace_from_markers
from paper_fetch.utils import choose_public_landing_page_url
from paper_fetch.workflow.fulltext import _provider_fetch_result

from ._logging_support import RecordCaptureHandler
from ._paper_fetch_support import (
    FixtureHtmlTransport,
    StubProvider,
    fetch_paper_model,
    fulltext_pdf_bytes,
    sample_article,
)


def _typed_payload(
    *,
    provider: str,
    source_url: str,
    content_type: str,
    body: bytes,
    route_kind: str,
    markdown_text: str | None = None,
    reason: str | None = None,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
    needs_local_copy: bool = False,
) -> RawFulltextPayload:
    return RawFulltextPayload(
        provider=provider,
        source_url=source_url,
        content_type=content_type,
        body=body,
        content=ProviderContent(
            route_kind=route_kind,
            source_url=source_url,
            content_type=content_type,
            body=body,
            markdown_text=markdown_text,
            reason=reason,
            needs_local_copy=needs_local_copy,
        ),
        warnings=list(warnings or []),
        trace=trace_from_markers(list(source_trail or [])),
        needs_local_copy=needs_local_copy,
    )


_RUNTIME_ARG_UNSET = object()


def _runtime_context_from_args(
    *,
    context: RuntimeContext | None = None,
    env=_RUNTIME_ARG_UNSET,
    transport=_RUNTIME_ARG_UNSET,
    clients=_RUNTIME_ARG_UNSET,
    download_dir=_RUNTIME_ARG_UNSET,
) -> RuntimeContext | None:
    runtime_args = {
        "env": env,
        "transport": transport,
        "clients": clients,
        "download_dir": download_dir,
    }
    explicit = {
        name: value
        for name, value in runtime_args.items()
        if value is not _RUNTIME_ARG_UNSET
    }
    if context is not None:
        if explicit:
            raise TypeError(
                "test helper cannot combine context with runtime keyword arguments"
            )
        return context
    if not explicit:
        return None
    return RuntimeContext(**explicit)


def _fetch_paper(
    query: str,
    *,
    modes=None,
    strategy=None,
    render=None,
    context: RuntimeContext | None = None,
    env=_RUNTIME_ARG_UNSET,
    transport=_RUNTIME_ARG_UNSET,
    clients=_RUNTIME_ARG_UNSET,
    download_dir=_RUNTIME_ARG_UNSET,
):
    runtime_context = _runtime_context_from_args(
        context=context,
        env=env,
        transport=transport,
        clients=clients,
        download_dir=download_dir,
    )
    return paper_fetch.fetch_paper(
        query,
        modes=modes,
        strategy=strategy,
        render=render,
        context=runtime_context,
    )


def _probe_has_fulltext(
    query: str,
    *,
    context: RuntimeContext | None = None,
    env=_RUNTIME_ARG_UNSET,
    transport=_RUNTIME_ARG_UNSET,
    clients=_RUNTIME_ARG_UNSET,
):
    runtime_context = _runtime_context_from_args(
        context=context,
        env=env,
        transport=transport,
        clients=clients,
    )
    return paper_fetch.probe_has_fulltext(query, context=runtime_context)


__all__ = [name for name in globals() if not name.startswith("__")]
