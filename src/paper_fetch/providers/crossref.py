"""Crossref provider adapter."""

from __future__ import annotations

from collections.abc import Mapping

from ..http import HttpTransport
from ..metadata.crossref import CrossrefLookupClient
from ..metadata.types import CrossrefMetadata
from ..provider_catalog import ProviderRouteSpec, ProviderSpec
from ._registry import ProviderBundle
from .base import (
    ProviderClient,
    ProviderStatusResult,
    build_provider_status_check,
    summarize_capability_status,
)
from ..reason_codes import OK


class CrossrefClient(ProviderClient):
    name = "crossref"
    official_provider = False

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.lookup = CrossrefLookupClient(transport, env)
        self.transport = self.lookup.transport
        self.user_agent = self.lookup.user_agent
        self.mailto = self.lookup.mailto

    def probe_status(self) -> ProviderStatusResult:
        notes: list[str] = []
        if not self.mailto:
            notes.append(
                "CROSSREF_MAILTO is not configured; adding one is recommended for better API etiquette."
            )
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            notes=notes,
            checks=[
                build_provider_status_check(
                    "metadata_api",
                    OK,
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
        doi_prefix: str | None = None,
        rows: int = 5,
    ) -> list[CrossrefMetadata]:
        return self.lookup.search_bibliographic_candidates(
            article_title,
            journal_title=journal_title,
            doi_prefix=doi_prefix,
            rows=rows,
        )


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=CrossrefClient,
    catalog=ProviderSpec(
        name="crossref",
        display_name="Crossref",
        official=False,
        domains=(),
        doi_prefixes=(),
        publisher_aliases=(),
        asset_default="none",
        probe_capability="metadata_api",
        provider_managed_abstract_only=False,
        status_order=0,
        html_capable=False,
        api_hosts=("api.crossref.org",),
        sensitive_headers=("cr-clickthrough-client-token",),
        routes=(ProviderRouteSpec(name="metadata", kind="metadata"),),
    ),
    sources=("crossref_meta",),
)
