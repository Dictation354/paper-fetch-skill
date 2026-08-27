"""Shared compact acceptance projections for MCP fetch responses."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..publisher_identity import extract_doi, extract_doi_from_url
from ..workflow.acceptance import FetchAcceptanceReport


def expected_doi_from_query(query: str) -> str | None:
    """Return a DOI expectation only when the original query carries one."""

    return extract_doi_from_url(query) or extract_doi(query)


def compact_acceptance_payload(
    report: FetchAcceptanceReport,
) -> dict[str, Any]:
    """Project the canonical report into the bounded MCP acceptance contract."""

    return {
        "overall": report.overall.value,
        "identity": report.identity.status.value,
        "fetch": report.fetch.status.value,
        "content": report.content.status.value,
        "asset": report.asset.status.value,
        "output": report.output.status.value,
        "provenance": report.provenance.status.value,
        "acquisition": (
            asdict(report.provenance.acquisition)
            if report.provenance.acquisition is not None
            else None
        ),
        "has_fulltext": report.content.has_fulltext,
        "has_abstract": report.content.has_abstract,
        "token_estimate": report.content.token_estimate,
        "asset_summary": report.asset.model_dump(mode="json"),
    }
