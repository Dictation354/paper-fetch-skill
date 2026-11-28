"""Shared test support; contains no collected tests."""

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from paper_fetch import service
from paper_fetch.auth import ams_profile_path
from paper_fetch.config import BROWSER_PROFILE_DIR_ENV_VAR
from tests.support._paper_fetch_support import FixtureProvider
from tests.support.publisher_profiles import write_verified_ams_profile


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
        runtime_env = {}
        if fixture.provider == "ams":
            # Captured responses exercise provider behavior after authentication.
            profile = Path(stack.enter_context(TemporaryDirectory()))
            runtime_env[BROWSER_PROFILE_DIR_ENV_VAR] = str(profile)
            write_verified_ams_profile(ams_profile_path(runtime_env))
            stack.enter_context(mock.patch.object(client, "env", runtime_env))
        stack.enter_context(
            mock.patch.object(service, "resolve_paper", return_value=resolved)
        )
        stack.enter_context(
            mock.patch.object(client, "fetch_metadata", return_value=metadata)
        )
        context = stack.enter_context(
            service.RuntimeContext(
                env=runtime_env,
                download_dir=output_dir,
                clients={fixture.provider: client, "crossref": crossref},
            )
        )
        return service.fetch_paper(
            fixture.doi,
            modes={"article"},
            strategy=service.FetchStrategy(
                allow_metadata_only_fallback=True, asset_profile=asset_profile
            ),
            context=context,
        )
