# ruff: noqa: F401
from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

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
    FixtureProvider,
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


def _fetch_paper(
    query: str,
    *,
    modes=None,
    strategy=None,
    render=None,
    context: RuntimeContext | None = None,
):
    return paper_fetch.fetch_paper(
        query,
        modes=modes,
        strategy=strategy,
        render=render,
        context=context,
    )


def _probe_has_fulltext(
    query: str,
    *,
    context: RuntimeContext | None = None,
):
    return paper_fetch.probe_has_fulltext(query, context=context)


__all__ = [name for name in globals() if not name.startswith("__")]
