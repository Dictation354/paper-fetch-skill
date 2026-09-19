"""Shared test support; contains no collected tests."""

from unittest import mock
from contextlib import ExitStack
from paper_fetch import service
from tests.support._paper_fetch_support import FixtureProvider


def _fetch_through_service(
    client, fixture, metadata, *, output_dir=None, asset_profile="none"
):
    resolved = service.ResolvedQuery(
        query=fixture.doi,
        query_kind="doi",
        doi=fixture.doi,
        landing_url=fixture.source_url,
        provider_hint=fixture.provider,
        confidence=1.0,
    )
    crossref = FixtureProvider(
        metadata={**metadata, "provider": "crossref", "official_provider": False}
    )
    crossref.fetch_raw_fulltext = mock.Mock(
        side_effect=AssertionError("Cross-provider fulltext")
    )
    crossref.download_related_assets = mock.Mock(
        side_effect=AssertionError("Cross-provider assets")
    )
    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.object(service, "resolve_paper", return_value=resolved)
        )
        stack.enter_context(
            mock.patch.object(client, "fetch_metadata", return_value=metadata)
        )
        return service.fetch_paper(
            fixture.doi,
            modes={"article"},
            strategy=service.FetchStrategy(
                allow_metadata_only_fallback=True, asset_profile=asset_profile
            ),
            context=service.RuntimeContext(
                env={},
                download_dir=output_dir,
                clients={fixture.provider: client, "crossref": crossref},
            ),
        )
