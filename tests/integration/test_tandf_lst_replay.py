"""Replay the publisher HTML through provider, service, CLI and MCP outputs."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil

from bs4 import BeautifulSoup
import pytest

from paper_fetch import cli, service
from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.mcp._deps import default_mcp_deps
from paper_fetch.mcp.fetch_tool import fetch_paper_payload
from paper_fetch.models import RenderOptions
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.tandf import TandfClient
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_from_markers
from paper_fetch.workflow.types import FetchStrategy
from tests.golden_criteria import golden_criteria_asset
from tests.unit.test_tandf_lst_render import DOI, URL, source_html, assert_formulas


@pytest.fixture
def replay(monkeypatch):
    class ReplayClient(TandfClient):
        html = source_html()

        def fetch_metadata(self, query):
            return {
                **parse_html_metadata(self.html, URL),
                "doi": DOI,
                "provider": "tandf",
                "official_provider": True,
                "landing_page_url": URL,
                "fulltext_links": [],
                "references": [],
            }

        def fetch_raw_fulltext(self, doi, metadata, *, context=None):
            assert doi == DOI
            markdown, extraction = self.extract_markdown(
                self.html, URL, metadata=metadata
            )
            return RawFulltextPayload(
                provider="tandf",
                content=ProviderContent(
                    route_kind="html",
                    route_name="browser_html",
                    source_url=URL,
                    content_type="text/html",
                    body=self.html.encode(),
                    markdown_text=markdown,
                    diagnostics={
                        "extraction": extraction,
                        "availability_diagnostics": extraction[
                            "availability_diagnostics"
                        ],
                    },
                ),
                trace=trace_from_markers(["fulltext:tandf_html_ok"]),
            )

        def download_related_assets(
            self,
            doi,
            metadata,
            raw_payload,
            output_dir,
            *,
            asset_profile=None,
            context=None,
        ):
            # Transport stub only: real publisher URLs and asset merge/rendering.
            markdown, _ = self.extract_markdown(self.html, URL, metadata=metadata)
            urls = re.findall(r"!\[Figure \d+\]\(([^)]+)\)", markdown)
            output_dir.mkdir(parents=True, exist_ok=True)
            images = [
                *sorted(
                    golden_criteria_asset("10.1063/5.0129134", "body_assets").glob(
                        "*.jpeg"
                    )
                ),
                *sorted(
                    golden_criteria_asset("10.1126/sciadv.adl6155", "body_assets").glob(
                        "*.jpg"
                    )
                ),
            ]
            assets = []
            for i, url in enumerate(urls, 1):
                path = output_dir / Path(url).name
                shutil.copyfile(images[i - 1], path)
                assets.append(
                    {
                        "kind": "figure",
                        "heading": f"Figure {i}",
                        "url": url,
                        "path": str(path),
                        "download_url": url,
                        "download_tier": "full_size",
                        "section": "body",
                        "content_type": "image/jpeg",
                    }
                )
            return {"assets": assets, "asset_failures": []}

    client = ReplayClient(None, {})
    monkeypatch.setattr(RuntimeContext, "get_clients", lambda self: {"tandf": client})
    monkeypatch.setattr(
        service,
        "resolve_paper",
        lambda *a, **k: ResolvedQuery(
            query=DOI,
            query_kind="doi",
            doi=DOI,
            landing_url=URL,
            provider_hint="tandf",
            confidence=1.0,
        ),
    )
    monkeypatch.setattr(cli, "build_runtime_env", lambda *a, **k: {})
    return client


def test_python_cli_mcp_saved_semantics(replay, tmp_path, capsys):
    with RuntimeContext(env={}, download_dir=tmp_path / "api") as context:
        envelope = service.fetch_paper(
            DOI,
            modes={"article", "markdown"},
            strategy=FetchStrategy(
                asset_profile="body", require_full_size_body_assets=True
            ),
            render=RenderOptions(
                include_refs="all", max_tokens="full_text", asset_profile="body"
            ),
            context=context,
        )
    assert envelope.article.quality.semantic_losses.formula_missing_count == 0
    assert_formulas(envelope.markdown)
    wire = json.loads(envelope.to_json())
    assert wire["article"]["quality"]["extraction_revision"] == 5
    out = tmp_path / "cli" / "paper.md"
    manifest = out.with_suffix(".json")
    assert (
        cli.main(
            [
                "fetch",
                "--query",
                DOI,
                "--output",
                str(out),
                "--output-dir",
                str(out.parent),
                "--artifact-mode",
                "markdown-assets",
                "--asset-profile",
                "body",
                "--require-full-size-body-assets",
                "--include-refs",
                "all",
                "--max-tokens",
                "full_text",
                "--manifest",
                str(manifest),
            ]
        )
        == 0
    )
    record = json.loads(manifest.read_text())
    assert record["acceptance"]["overall"] == "complete", json.dumps(
        {
            "asset": record["asset_summary"],
            "losses": record["semantic_losses"],
            "warnings": record["warning_codes"],
            "failures": record["failure_codes"],
        }
    )
    assert (
        record["output_artifacts"][0]["sha256"]
        == hashlib.sha256(out.read_bytes()).hexdigest()
    )
    mcpdir = tmp_path / "mcp"
    payload = fetch_paper_payload(
        query=DOI,
        modes=["article", "markdown"],
        strategy={"asset_profile": "body", "require_full_size_body_assets": True},
        include_refs="all",
        max_tokens="full_text",
        artifact_mode="markdown-assets",
        download_dir=mcpdir,
        save_markdown=False,
        markdown_output_dir=str(mcpdir),
        markdown_filename="paper.md",
        deps=replace(
            default_mcp_deps(),
            build_runtime_env=lambda *a, **k: {},
            service_fetch_paper=service.fetch_paper,
        ),
    )
    assert payload["acceptance"]["overall"] == "complete"
    saved = fetch_paper_payload(
        query=DOI,
        modes=["article", "markdown"],
        strategy={"asset_profile": "body", "require_full_size_body_assets": True},
        include_refs="all",
        max_tokens="full_text",
        artifact_mode="markdown-assets",
        download_dir=mcpdir,
        prefer_cache=True,
        save_markdown=True,
        markdown_output_dir=str(mcpdir),
        markdown_filename="paper.md",
        deps=replace(
            default_mcp_deps(),
            build_runtime_env=lambda *a, **k: {},
            service_fetch_paper=service.fetch_paper,
        ),
    )
    assert saved["acceptance"]["overall"] == "complete"
    assert saved["markdown"] is None  # Saved MCP replies intentionally omit body.
    texts = [
        envelope.markdown,
        out.read_text(),
        payload["markdown"],
        (mcpdir / "paper.md").read_text(),
    ]
    for text in texts:
        assert_formulas(text)
        images = re.findall(r"!\[Figure \d+\]\(([^)]+)\)", text)
        assert len(images) == 12
        assert all(not url.startswith("https:") for url in images)

    def body(text):
        text = text[text.index("## ABSTRACT") :]
        return re.sub(r"!\[Figure (\d+)\]\([^)]+\)", r"Figure \1", text).strip()

    assert len({body(text) for text in texts}) == 1


@pytest.mark.parametrize("fallback", [False, True])
def test_real_formula_loss_cannot_report_complete(replay, tmp_path, fallback):
    soup = BeautifulSoup(replay.html, "lxml")
    formula = next(
        n
        for n in soup.select(".NLM_disp-formula.disp-formula")
        if not n.find_parent(class_="hidden")
    )
    formula.math.clear()
    if fallback:
        image = formula.find("img")
        image["src"] = "https://www.tandfonline.com/math-0001.gif"
    replay.html = str(soup)
    payload = fetch_paper_payload(
        query=DOI,
        modes=["article", "markdown"],
        strategy={"asset_profile": "none"},
        include_refs="all",
        no_download=True,
        download_dir=None,
        artifact_mode="none",
        deps=replace(
            default_mcp_deps(),
            build_runtime_env=lambda *a, **k: {},
            service_fetch_paper=service.fetch_paper,
        ),
    )
    assert payload["acceptance"]["overall"] == "degraded"
    losses = payload["article"]["quality"]["semantic_losses"]
    assert (
        losses["formula_fallback_count" if fallback else "formula_missing_count"] == 1
    )
    if not fallback:
        assert payload["markdown"].count("[Formula unavailable]") == 1
