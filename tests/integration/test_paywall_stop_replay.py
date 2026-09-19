"""Real subscription HTML stops fetching and still lands CLI/MCP reports."""

from dataclasses import replace
import json
from unittest import mock
from paper_fetch import cli, service
from paper_fetch.mcp._deps import default_mcp_deps
from paper_fetch.mcp.fetch_tool import fetch_paper_payload
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
)
from paper_fetch.providers.tandf import TandfClient
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.runtime import RuntimeContext
from tests.block_fixtures import iter_block_samples
from tests.support._browser_workflow_deps import install_browser_workflow_deps
from tests.support._paper_fetch_support import RecordingTransport


def test_confirmed_subscription_stops_and_saves_cli_mcp(monkeypatch, tmp_path, capsys):
    fixture = next(
        f for f in iter_block_samples() if f.doi == "10.1080/01431161.2025.2516689"
    )
    requests = []
    html = fixture.raw_path.read_text()
    metadata = {
        "doi": fixture.doi,
        "title": fixture.title,
        "provider": "tandf",
        "official_provider": True,
        "landing_page_url": fixture.source_url,
    }
    client = TandfClient(RecordingTransport({}), {})
    client.fetch_metadata = mock.Mock(return_value=metadata)

    def browser(candidates, **kwargs):
        requests.append("browser_html")
        return BrowserFetchedHtml(
            source_url=candidates[0],
            final_url=fixture.source_url,
            html=html,
            response_status=200,
            response_headers={"content-type": "text/html"},
            title=fixture.title,
            summary="",
            browser_context_seed={},
        )

    forbidden = mock.Mock(
        side_effect=AssertionError("Network request after confirmed paywall")
    )
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(
            return_value=BrowserRuntimeConfig(
                provider="tandf",
                doi=fixture.doi,
                artifact_dir=tmp_path,
                headless=True,
                user_agent=None,
            )
        ),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=browser,
        fetch_pdf_with_browser=forbidden,
        fetch_seeded_browser_pdf_payload=forbidden,
        warm_browser_context=forbidden,
    )
    client.download_related_assets = forbidden
    monkeypatch.setattr(RuntimeContext, "get_clients", lambda self: {"tandf": client})
    monkeypatch.setattr(
        service,
        "resolve_paper",
        lambda *a, **k: ResolvedQuery(
            query=fixture.doi,
            query_kind="doi",
            doi=fixture.doi,
            landing_url=fixture.source_url,
            provider_hint="tandf",
            confidence=1.0,
        ),
    )
    monkeypatch.setattr(cli, "build_runtime_env", lambda *a, **k: {})

    output = tmp_path / "cli" / "paper.md"
    manifest = output.with_suffix(".json")
    assert (
        cli.main(
            [
                "fetch",
                "--query",
                fixture.doi,
                "--output",
                str(output),
                "--output-dir",
                str(output.parent),
                "--artifact-mode",
                "markdown-assets",
                "--asset-profile",
                "all",
                "--manifest",
                str(manifest),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert requests == ["browser_html"]
    assert "Complete remote-sensing time series" in output.read_text()
    record = json.loads(manifest.read_text())
    assert record["acceptance"]["overall"] == "limited"

    mcpdir = tmp_path / "mcp"
    result = fetch_paper_payload(
        query=fixture.doi,
        modes=["article", "markdown"],
        strategy={"asset_profile": "all"},
        artifact_mode="all",
        download_dir=mcpdir,
        save_markdown=True,
        markdown_output_dir=str(mcpdir),
        markdown_filename="paper.md",
        prefer_cache=False,
        deps=replace(
            default_mcp_deps(),
            build_runtime_env=lambda *a, **k: {},
            service_fetch_paper=service.fetch_paper,
        ),
    )
    assert requests == ["browser_html", "browser_html"]
    assert result["acceptance"]["overall"] == "limited"
    assert result["content_kind"] == "abstract_only"
    # Existing save_markdown semantics require full text; limited results keep
    # their structured report and received metadata instead.
    assert not (mcpdir / "paper.md").exists()
    assert "markdown_skipped_no_fulltext" in " ".join(result["source_trail"])
    assert "Complete remote-sensing time series" in json.dumps(
        result, ensure_ascii=False
    )
    forbidden.assert_not_called()
