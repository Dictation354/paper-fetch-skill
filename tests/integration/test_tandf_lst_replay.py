"""Replay the publisher HTML through provider, service, CLI and MCP outputs."""

from __future__ import annotations
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
from bs4 import BeautifulSoup
import pytest
from paper_fetch import cli, service
from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.mcp._deps import default_mcp_deps
from paper_fetch.mcp.fetch_tool import fetch_paper_payload
from paper_fetch.models import EXTRACTION_REVISION, RenderOptions
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.tandf import TandfClient
from paper_fetch.providers.browser_workflow.asset_download import (
    plan_browser_asset_download,
)
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_from_markers
from paper_fetch.workflow.types import FetchStrategy
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support.tandf_lst_render import DOI, URL, source_html


def representative_html():
    """Keep source metadata, abstract, prose, one equation and one figure.

    Full formula/reference/asset oracles live in golden/test_tandf_lst_render.py
    and golden/test_acquired_article_assets.py.
    """
    soup = BeautifulSoup(source_html(), "lxml")
    container = soup.select_one(".hlFld-Fulltext")
    abstract = str(container.select_one(".hlFld-Abstract"))
    paragraphs = [str(p) for p in container.select(".NLM_sec p")[:4]]
    formula = str(container.select_one(".NLM_disp-formula"))
    figure = str(container.select_one(".figureView"))
    container.clear()
    # Keep several source section boundaries so cache rehydration can assess
    # structure from the model without relying on transient DOM diagnostics.
    sections = "".join(
        '<div class="NLM_sec"><h2>' + heading + "</h2>" + prose + "</div>"
        for heading, prose in zip(
            ("Introduction", "Materials and methods", "Results"),
            (paragraphs[0], paragraphs[1], "".join(paragraphs[2:]) + formula + figure),
            strict=True,
        )
    )
    container.append(BeautifulSoup(abstract + sections, "html.parser"))
    return str(soup)


@pytest.fixture
def replay(monkeypatch):
    class ReplayClient(TandfClient):
        html = representative_html()

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
            # Replay the original JPEG bodies and HTTP wrappers captured by
            # normal image navigation. Only the browser operation is injected.
            plan = plan_browser_asset_download(
                article_id=doi,
                output_dir=output_dir,
                html_text=self.html,
                source_url=URL,
                profile={"client": self, "context": context, "asset_profile": "body"},
                deps=self.deps,
            )
            captured = {}
            for index in range(1, 2):
                record, body = _record(
                    DOI,
                    "acquisition/network-repair/raw-body-assets/"
                    f"tjde_a_2137254_f{index:04d}_oc.jpg",
                )
                assert record["capture_kind"] == "http_response_entity"
                assert record["status_code"] == 200
                captured[record["requested_url"]] = (record, body)
            calls = []

            def recovered_image(url, asset):
                calls.append(url)
                record, body = captured[url]
                return {
                    **_response(record, body),
                    "dimensions": {key: record[key] for key in ("width", "height")},
                }

            result = download_assets(
                FIGURE_KIND,
                RecordingTransport({}),
                article_id=doi,
                assets=plan.body_assets,
                output_dir=output_dir,
                user_agent="offline replay",
                asset_profile="body",
                options=AssetDownloadOptions(
                    candidate_builder=plan.candidate_builder,
                    image_document_fetcher=recovered_image,
                    fetch_policy="browser_first",
                    asset_download_concurrency=2,
                    provider_name="tandf",
                ),
            )
            assert not result["asset_failures"], result
            assert len(result["assets"]) == 1
            assert set(calls) == set(captured)
            for asset in result["assets"]:
                assert (
                    Path(asset["path"]).read_bytes()
                    == captured[asset["download_url"]][1]
                )
                assert asset["download_tier"] == "full_size"
            return result

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
    wire = json.loads(envelope.to_json())
    assert wire["article"]["quality"]["extraction_revision"] == EXTRACTION_REVISION
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
    assert saved["acceptance"]["overall"] == "complete", saved["acceptance"]
    assert saved["markdown"] is None  # Saved MCP replies intentionally omit body.
    texts = [
        envelope.markdown,
        out.read_text(),
        payload["markdown"],
        (mcpdir / "paper.md").read_text(),
    ]
    for text in texts:
        images = re.findall(r"!\[Figure \d+\]\(([^)]+)\)", text)
        assert len(images) == 1
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
