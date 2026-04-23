"""Science provider client."""

from __future__ import annotations

from typing import Any, Mapping

from ..metadata_types import ProviderMetadata
from . import _science_html, _science_pnas


class ScienceClient(_science_pnas.BrowserWorkflowClient):
    name = "science"

    def html_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        landing_page_url = str(metadata.get("landing_page_url") or "") or None
        return _science_html.build_html_candidates(doi, landing_page_url)

    def pdf_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        return _science_html.build_pdf_candidates(doi, _science_pnas.extract_pdf_url_from_crossref(metadata))

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: ProviderMetadata,
    ) -> tuple[str, dict[str, Any]]:
        return _science_html.extract_markdown(html_text, final_url, metadata=metadata)

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        return _science_pnas.browser_workflow_article_from_payload(
            self,
            _science_pnas.merge_provider_owned_authors(metadata, raw_payload),
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
