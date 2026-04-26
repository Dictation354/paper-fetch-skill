"""Crossref provider adapter."""

from __future__ import annotations

from typing import Any, Mapping

from ..http import HttpTransport
from ..metadata.crossref import CrossrefLookupClient
from ..metadata_types import CrossrefMetadata
from .base import (
    ProviderClient,
    ProviderStatusResult,
    build_provider_status_check,
    summarize_capability_status,
)


class CrossrefClient(ProviderClient):
    name = "crossref"
    official_provider = False

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.lookup = CrossrefLookupClient(transport, env)
        self.transport = self.lookup.transport
        self.user_agent = self.lookup.user_agent
        self.mailto = self.lookup.mailto

    def _headers(self) -> dict[str, str]:
        return self.lookup.headers()

    def _query_params(self) -> dict[str, str]:
        return self.lookup.query_params()

    def probe_status(self) -> ProviderStatusResult:
        notes: list[str] = []
        if not self.mailto:
            notes.append("CROSSREF_MAILTO is not configured; adding one is recommended for better API etiquette.")
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            notes=notes,
            checks=[
                build_provider_status_check(
                    "metadata_api",
                    "ok",
                    "Crossref metadata lookup is available without local credentials.",
                    details={"mailto_configured": bool(self.mailto)},
                )
            ],
        )

    def fetch_metadata(self, query: Mapping[str, str | None]) -> CrossrefMetadata:
        return self.lookup.fetch_metadata(query)

    def search_bibliographic_candidates(
        self,
        article_title: str,
        *,
        journal_title: str | None = None,
        rows: int = 5,
    ) -> list[CrossrefMetadata]:
        return self.lookup.search_bibliographic_candidates(
            article_title,
            journal_title=journal_title,
            rows=rows,
        )

    def _normalize_message(self, message: Mapping[str, Any], source_url: str) -> CrossrefMetadata:
        return self.lookup.normalize_message(message, source_url)
