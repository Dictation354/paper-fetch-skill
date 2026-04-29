from __future__ import annotations

import json
import tempfile
import urllib.parse
import unittest
from pathlib import Path
from typing import Mapping
from unittest import mock

from paper_fetch.quality.issues import collect_issue_flags
from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.providers import (
    _flaresolverr,
    browser_workflow,
    pnas as pnas_provider,
    science as science_provider,
    wiley as wiley_provider,
)
from paper_fetch.providers.science_pnas import asset_scopes as science_pnas_asset_scopes
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers
from tests.block_fixtures import block_asset
from tests.golden_criteria import (
    golden_criteria_asset,
    golden_criteria_dir_for_doi,
    golden_criteria_scenario_asset,
)
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.unit._paper_fetch_support import build_envelope, fulltext_pdf_bytes


SCIENCE_SAMPLE = provider_benchmark_sample("science")
PNAS_SAMPLE = provider_benchmark_sample("pnas")
WILEY_REGRESSION_FIXTURE = golden_criteria_asset("10.1111/gcb.16998", "original.html")
PNAS_REGRESSION_FIXTURE = golden_criteria_asset("10.1073/pnas.2309123120", "original.html")
PNAS_COMMENTARY_FIXTURE = golden_criteria_asset("10.1073/pnas.2317456120", "commentary.html")
SCIENCE_FRONTMATTER_REGRESSION_FIXTURE = golden_criteria_asset("10.1126/science.abp8622", "original.html")
SCIENCE_DATALAYER_AUTHOR_FIXTURE = golden_criteria_asset("10.1126/science.adp0212", "original.html")
SCIENCE_PAYWALL_SAMPLE_RAW = block_asset("10.1126/science.aeg3511", "raw.html")
SCIENCE_PAYWALL_SAMPLE_MARKDOWN = block_asset("10.1126/science.aeg3511", "extracted.md")
SCIENCE_FULLTEXT_FALLBACK_MARKDOWN = golden_criteria_asset("10.1126/science.aeg3511", "extracted.md")
SCIENCE_ADL6155_ROOT_CAUSE_FIXTURE = golden_criteria_asset("10.1126/sciadv.adl6155", "original.html")
SCIENCE_ADL6155_METADATA = golden_criteria_asset("10.1126/sciadv.adl6155", "article.json")
SCIENCE_ADL6155_ASSET_DIR = golden_criteria_dir_for_doi("10.1126/sciadv.adl6155") / "body_assets"
PNAS_PAYWALL_SAMPLE_RAW = block_asset("10.1073/pnas.2509692123", "raw.html")
PNAS_PAYWALL_SAMPLE_MARKDOWN = block_asset("10.1073/pnas.2509692123", "extracted.md")
PNAS_FULLTEXT_FALLBACK_MARKDOWN = golden_criteria_asset("10.1073/pnas.2406303121", "extracted.md")
WILEY_2004GB002273_ROOT_CAUSE_FIXTURE = golden_criteria_asset("10.1029/2004GB002273", "original.html")
WILEY_2004GB002273_METADATA = golden_criteria_asset("10.1029/2004GB002273", "article.json")
WILEY_2004GB002273_ASSET_DIR = golden_criteria_dir_for_doi("10.1029/2004GB002273") / "body_assets"


def png_header(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")


def _typed_raw_payload(
    *,
    provider: str,
    source_url: str,
    content_type: str,
    body: bytes,
    route: str,
    markdown_text: str | None = None,
    source_trail: list[str] | None = None,
    extraction: Mapping[str, object] | None = None,
    availability_diagnostics: Mapping[str, object] | None = None,
    browser_context_seed: Mapping[str, object] | None = None,
    suggested_filename: str | None = None,
) -> RawFulltextPayload:
    diagnostics: dict[str, object] = {}
    if extraction is not None:
        diagnostics["extraction"] = dict(extraction)
    if availability_diagnostics is not None:
        diagnostics["availability_diagnostics"] = dict(availability_diagnostics)
    return RawFulltextPayload(
        provider=provider,
        source_url=source_url,
        content_type=content_type,
        body=body,
        content=ProviderContent(
            route_kind=route,
            source_url=source_url,
            content_type=content_type,
            body=body,
            markdown_text=markdown_text,
            diagnostics=diagnostics,
            browser_context_seed=dict(browser_context_seed or {}),
            suggested_filename=suggested_filename,
        ),
        trace=trace_from_markers(source_trail or []),
    )


def _payload_route(raw_payload: RawFulltextPayload) -> str | None:
    return raw_payload.content.route_kind if raw_payload.content is not None else None


def _payload_source_trail(raw_payload: RawFulltextPayload) -> list[str]:
    return [event.marker() for event in raw_payload.trace if event.marker()]


class AssetTransport:
    def __init__(self, responses: dict[tuple[str, str], dict[str, object] | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=20,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "query": dict(query or {}),
                "timeout": timeout,
                "retry_on_rate_limit": retry_on_rate_limit,
                "retry_on_transient": retry_on_transient,
            }
        )
        key = (method, url)
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {method} {url}")
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response


class SciencePnasProviderTests(unittest.TestCase):
    def _metadata_from_golden_criteria(self, article_path: Path, doi: str) -> dict[str, object]:
        article_payload = json.loads(article_path.read_text(encoding="utf-8"))
        metadata = dict(article_payload.get("metadata") or {})
        metadata["doi"] = doi
        metadata["references"] = list(article_payload.get("references") or [])
        return metadata

    def _map_local_assets_by_basename(
        self,
        extracted_assets: list[dict[str, object]],
        *,
        asset_dir: Path,
    ) -> list[dict[str, object]]:
        local_by_name = {
            path.name: str(path.resolve())
            for path in asset_dir.iterdir()
            if path.is_file()
        }
        downloaded_assets: list[dict[str, object]] = []
        for asset in extracted_assets:
            candidate_names: list[str] = []
            for field in ("full_size_url", "url", "preview_url", "figure_page_url", "source_url"):
                raw_value = str(asset.get(field) or "").strip()
                if not raw_value:
                    continue
                parsed = urllib.parse.urlparse(raw_value if not raw_value.startswith("//") else f"https:{raw_value}")
                basename = Path(urllib.parse.unquote(parsed.path)).name
                if basename:
                    candidate_names.append(basename)
                    if "." not in basename:
                        candidate_names.append(f"{basename}.html")
            local_path = next((local_by_name[name] for name in candidate_names if name in local_by_name), None)
            if not local_path:
                continue
            downloaded_asset = dict(asset)
            downloaded_asset["path"] = local_path
            downloaded_assets.append(downloaded_asset)
        return downloaded_assets

    def _runtime_config(self, tmpdir: str, provider: str, doi: str) -> _flaresolverr.FlareSolverrRuntimeConfig:
        tmp = Path(tmpdir)
        return _flaresolverr.FlareSolverrRuntimeConfig(
            provider=provider,
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=tmp / ".env.flaresolverr",
            source_dir=tmp / "vendor" / "flaresolverr",
            artifact_dir=tmp / "artifacts",
            headless=True,
        )

    def _build_browser_html_raw_payload(
        self,
        client,
        *,
        html: str,
        landing_url: str,
        extraction_metadata: Mapping[str, object],
        source_trail: list[str] | None = None,
    ) -> tuple[str, dict[str, object], RawFulltextPayload]:
        markdown_text, extraction = client.extract_markdown(
            html,
            landing_url,
            metadata=extraction_metadata,
        )
        raw_payload = _typed_raw_payload(
            provider=client.name,
            source_url=landing_url,
            content_type="text/html",
            body=html.encode("utf-8"),
            route="html",
            markdown_text=markdown_text,
            source_trail=list(source_trail or [f"fulltext:{client.name}_html_ok"]),
            extraction=extraction,
        )
        return markdown_text, extraction, raw_payload

    def _build_browser_fixture_article(
        self,
        client,
        *,
        html: str,
        landing_url: str,
        article_metadata: Mapping[str, object],
        extraction_metadata: Mapping[str, object] | None = None,
        downloaded_assets: list[dict[str, object]] | None = None,
        asset_failures: list[dict[str, object]] | None = None,
        source_trail: list[str] | None = None,
    ):
        _, extraction, raw_payload = self._build_browser_html_raw_payload(
            client,
            html=html,
            landing_url=landing_url,
            extraction_metadata=extraction_metadata or article_metadata,
            source_trail=source_trail,
        )
        article = client.to_article_model(
            dict(article_metadata),
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        return article, extraction, raw_payload

    def _assert_issue_flag_absent(self, provider: str, article, flag: str, *, status: str = "fulltext") -> None:
        self.assertNotIn(flag, collect_issue_flags(provider, build_envelope(article), status=status))

    def _assert_provider_owned_author_case(
        self,
        *,
        client,
        html_fixture: Path,
        doi: str,
        title: str,
        landing_url: str,
        expected_authors: list[str],
    ) -> None:
        article, _, _ = self._build_browser_fixture_article(
            client,
            html=html_fixture.read_text(encoding="utf-8"),
            landing_url=landing_url,
            article_metadata={"doi": doi, "title": title, "authors": []},
            extraction_metadata={"doi": doi, "title": title},
        )
        self.assertEqual(article.metadata.authors[: len(expected_authors)], expected_authors)
        self._assert_issue_flag_absent(client.name, article, "empty_authors")

    def test_science_provider_prefers_html_route(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(browser_workflow, "fetch_html_with_direct_playwright") as mocked_direct,
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=SCIENCE_SAMPLE.landing_url,
                        final_url=SCIENCE_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=SCIENCE_SAMPLE.title,
                        summary="Example summary",
                        browser_context_seed={},
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "extract_science_pnas_markdown",
                    return_value=(f"# {SCIENCE_SAMPLE.title}\n\n## Discussion\n\n" + ("Body text " * 120), {"title": SCIENCE_SAMPLE.title}),
                ),
                mock.patch.object(browser_workflow, "fetch_pdf_with_playwright") as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                )
                article = client.to_article_model(
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                )

        mocked_pdf.assert_not_called()
        mocked_direct.assert_not_called()
        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(article.source, "science")
        self.assertIn("fulltext:science_html_ok", article.quality.source_trail)

    def test_science_provider_rewrites_inline_figure_links_to_downloaded_local_assets(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "science-figure-1.png"
            asset_path.write_bytes(b"science-figure")
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=b"<html></html>",
                route="html",
                markdown_text="\n\n".join(
                    [
                        f"# {SCIENCE_SAMPLE.title}",
                        "## Results",
                        ("Body text " * 80).strip(),
                        "![Figure 1](https://www.science.org/images/figure-1.jpg)",
                        "**Figure 1.** Caption body for the science figure.",
                    ]
                ),
                source_trail=["fulltext:science_html_ok"],
            )

            article = client.to_article_model(
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                raw_payload,
                downloaded_assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Caption body for the science figure.",
                        "path": str(asset_path),
                        "source_url": "https://www.science.org/images/figure-1.jpg",
                        "section": "body",
                    }
                ],
            )

        body_markdown = article.to_ai_markdown(asset_profile="none")
        self.assertIn(f"![Figure 1]({asset_path})", body_markdown)
        self.assertNotIn("![Figure 1](https://www.science.org/images/figure-1.jpg)", body_markdown)

        markdown = article.to_ai_markdown(asset_profile="body")
        self.assertIn(f"![Figure 1]({asset_path})", markdown)
        self.assertNotIn("![Figure 1](https://www.science.org/images/figure-1.jpg)", markdown)
        self.assertEqual(article.assets[0].path, str(asset_path))

    def test_science_provider_uses_extracted_dom_abstract_and_restores_lead_body_text(self) -> None:
        """rule: rule-provider-owned-authors"""
        scenario = json.loads(
            golden_criteria_scenario_asset("provider_dom_abstract_fallback", "payload.json").read_text(
                encoding="utf-8"
            )
        )
        client = science_provider.ScienceClient(transport=None, env={})
        raw_payload = _typed_raw_payload(
            provider=str(scenario["provider"]),
            source_url=str(scenario["source_url"]),
            content_type="text/html",
            body=str(scenario["body_html"]).encode("utf-8"),
            route="html",
            markdown_text=str(scenario["markdown_text"]),
            source_trail=["fulltext:science_html_ok"],
            extraction=scenario["extraction"],
        )

        article = client.to_article_model(
            {
                "doi": str(scenario["doi"]),
                "title": str(scenario["title"]),
                "abstract": str(scenario["metadata_abstract"]),
            },
            raw_payload,
        )

        self.assertEqual(article.metadata.abstract, "Short DOM abstract.")
        self.assertEqual(article.sections[0].heading, "Main Text")
        self.assertIn("Lead body paragraph", article.sections[0].text)
        self.assertEqual(article.sections[1].heading, "Results")

    def test_provider_owned_html_signals_populate_final_article_authors(self) -> None:
        """rule: rule-provider-owned-authors"""
        cases = (
            {
                "provider": "science",
                "client": science_provider.ScienceClient(transport=None, env={}),
                "html_fixture": SCIENCE_DATALAYER_AUTHOR_FIXTURE,
                "doi": "10.1126/science.adp0212",
                "title": "Anthropogenic amplification of precipitation variability over the past century",
                "landing_url": "https://www.science.org/doi/full/10.1126/science.adp0212",
                "expected_authors": ["Wenxia Zhang", "Tianjun Zhou", "Peili Wu"],
            },
            {
                "provider": "wiley",
                "client": wiley_provider.WileyClient(transport=None, env={}),
                "html_fixture": WILEY_REGRESSION_FIXTURE,
                "doi": "10.1111/gcb.16998",
                "title": "Drought thresholds that impact vegetation reveal the divergent responses of vegetation growth to drought across China",
                "landing_url": "https://onlinelibrary.wiley.com/doi/10.1111/gcb.16998",
                "expected_authors": ["Mingze Sun", "Xiangyi Li", "Hao Xu"],
            },
            {
                "provider": "pnas",
                "client": pnas_provider.PnasClient(transport=None, env={}),
                "html_fixture": PNAS_REGRESSION_FIXTURE,
                "doi": "10.1073/pnas.2309123120",
                "title": "Amazon deforestation causes strong regional warming",
                "landing_url": "https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
                "expected_authors": ["Edward W. Butt", "Jessica C. A. Baker", "Francisco G. Silva Bezerra"],
            },
        )

        for case in cases:
            with self.subTest(provider=case["provider"], doi=case["doi"]):
                self._assert_provider_owned_author_case(
                    client=case["client"],
                    html_fixture=case["html_fixture"],
                    doi=case["doi"],
                    title=case["title"],
                    landing_url=case["landing_url"],
                    expected_authors=case["expected_authors"],
                )

    def test_science_provider_falls_back_to_dom_authors_when_datalayer_is_missing(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.test-dom-authors"
        title = "Science DOM Author Fallback"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        html = """
        <html>
          <body>
            <main class="article__fulltext">
              <article class="article-view">
                <h1>Science DOM Author Fallback</h1>
                <div class="contributors">
                  <div property="author">
                    <span property="givenName">Jamie</span>
                    <span property="familyName">Farrell</span>
                    <a href="https://orcid.org/0000-0000-0000-0001">https://orcid.org/0000-0000-0000-0001</a>
                  </div>
                  <div property="author"><span property="name">Taylor Example</span></div>
                  <div property="author">Jordan Example <a href="https://orcid.org/0000-0000-0000-0002">ORCID</a></div>
                  <div property="author">+12 authors</div>
                  <div property="author">Authors Info &amp; Affiliations</div>
                </div>
                <div id="abstracts">
                  <div class="core-container">
                    <section id="abstract" role="doc-abstract">
                      <h2>Abstract</h2>
                      <div role="paragraph">This abstract is long enough to remain stable in the final Science article model.</div>
                    </section>
                  </div>
                </div>
                <section class="article__body" data-extent="bodymatter" property="articleBody">
                  <h2>Results</h2>
                  <p>This body paragraph is long enough to satisfy availability checks and verify DOM author fallback.</p>
                  <p>This second body paragraph keeps the sample deterministic and clearly separated from the abstract.</p>
                </section>
              </article>
            </main>
          </body>
        </html>
        """
        markdown_text, extraction = client.extract_markdown(
            html,
            landing_url,
            metadata={"doi": doi, "title": title},
        )
        raw_payload = _typed_raw_payload(
            provider="science",
            source_url=landing_url,
            content_type="text/html",
            body=html.encode("utf-8"),
            route="html",
            markdown_text=markdown_text,
            source_trail=["fulltext:science_html_ok"],
            extraction=extraction,
        )

        article = client.to_article_model(
            {"doi": doi, "title": title},
            raw_payload,
        )

        self.assertEqual(article.metadata.authors, ["Jamie Farrell", "Taylor Example", "Jordan Example"])

    def test_pnas_provider_renders_headingless_commentary_without_synthetic_title_section(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2317456120"
        title = "Amazon deforestation implications in local/regional climate change"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        article, _, _ = self._build_browser_fixture_article(
            client,
            html=PNAS_COMMENTARY_FIXTURE.read_text(encoding="utf-8"),
            landing_url=landing_url,
            article_metadata={"doi": doi, "title": title, "authors": []},
            extraction_metadata={"doi": doi, "title": title},
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertIsNone(article.metadata.abstract)
        self.assertEqual(article.metadata.authors, ["Paulo Artaxo"])
        self.assertEqual(article.sections[0].heading, "")
        self.assertEqual(article.sections[0].kind, "body")
        self.assertIn("# Amazon deforestation implications in local/regional climate change", rendered)
        self.assertNotIn("## Amazon deforestation implications in local/regional climate change", rendered)
        self.assertNotIn("## Full Text", rendered)

    def test_science_provider_keeps_frontmatter_sections_but_only_one_abstract_in_final_article(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.abp8622"
        title = "The drivers and impacts of Amazon forest degradation"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        article, _, _ = self._build_browser_fixture_article(
            client,
            html=SCIENCE_FRONTMATTER_REGRESSION_FIXTURE.read_text(encoding="utf-8"),
            landing_url=landing_url,
            article_metadata={"doi": doi, "title": title},
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(article.metadata.authors[:3], ["David M. Lapola", "Patricia Pinho", "Jos Barlow"])
        self.assertGreater(len(article.metadata.authors), 3)
        self.assertIn("Policies to tackle degradation", article.metadata.abstract or "")
        self.assertEqual([section.heading for section in article.sections if section.kind == "abstract"], ["Abstract"])
        self.assertEqual(
            [section.heading for section in article.sections[:4]],
            ["Abstract", "Losing the Amazon", "Structured Abstract", "Main Text"],
        )
        self.assertEqual(article.sections[1].kind, "body")
        self.assertEqual(article.sections[2].kind, "body")
        self.assertEqual(rendered.count("## Abstract"), 1)
        self.assertIn("## Losing the Amazon", rendered)
        self.assertIn("## Structured Abstract", rendered)
        self._assert_issue_flag_absent("science", article, "abstract_inflated")
        self._assert_issue_flag_absent("science", article, "empty_authors")

    def test_science_provider_replay_for_adl6155_keeps_materials_and_methods_wrapper_heading(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/sciadv.adl6155"
        landing_url = f"https://www.science.org/doi/{doi}"
        html = SCIENCE_ADL6155_ROOT_CAUSE_FIXTURE.read_text(encoding="utf-8")
        metadata = self._metadata_from_golden_criteria(SCIENCE_ADL6155_METADATA, doi)
        metadata.setdefault("title", "A two-fold increase of carbon cycle sensitivity to tropical temperature variations")
        metadata.setdefault("landing_page_url", landing_url)

        extracted_assets = html_assets.extract_html_assets(html, landing_url, asset_profile="body")
        downloaded_assets = self._map_local_assets_by_basename(
            extracted_assets,
            asset_dir=SCIENCE_ADL6155_ASSET_DIR,
        )
        self.assertEqual(len(downloaded_assets), len(extracted_assets))

        article, _, _ = self._build_browser_fixture_article(
            client,
            html=html,
            landing_url=landing_url,
            article_metadata=metadata,
            downloaded_assets=downloaded_assets,
        )
        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("## MATERIALS AND METHODS", rendered)
        self.assertIn("### Experimental design", rendered)
        self.assertLess(rendered.index("## MATERIALS AND METHODS"), rendered.index("### Experimental design"))

    def test_wiley_provider_deduplicates_near_matching_abstract_in_final_article_render(self) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1111/gcb.16998"
        title = "Drought thresholds that impact vegetation reveal the divergent responses of vegetation growth to drought across China"
        landing_url = f"https://onlinelibrary.wiley.com/doi/{doi}"
        html = WILEY_REGRESSION_FIXTURE.read_text(encoding="utf-8")
        _, extraction, raw_payload = self._build_browser_html_raw_payload(
            client,
            html=html,
            landing_url=landing_url,
            extraction_metadata={"doi": doi, "title": title},
        )

        article = client.to_article_model(
            {"doi": doi, "title": title, "abstract": extraction.get("abstract_text")},
            raw_payload,
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(rendered.count("## Abstract"), 1)
        self.assertEqual(len([section for section in article.sections if section.kind == "abstract"]), 1)
        self._assert_issue_flag_absent("wiley", article, "abstract_inflated")

    def test_wiley_provider_replay_for_2004gb002273_body_assets_avoid_trailing_figures_noise(self) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1029/2004GB002273"
        landing_url = "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2004GB002273"
        html = WILEY_2004GB002273_ROOT_CAUSE_FIXTURE.read_text(encoding="utf-8")
        metadata = self._metadata_from_golden_criteria(WILEY_2004GB002273_METADATA, doi)
        metadata.setdefault("title", "Terrestrial mechanisms of interannual CO2 variability")
        metadata.setdefault("landing_page_url", landing_url)

        extracted_assets = html_assets.extract_html_assets(html, landing_url, asset_profile="body")
        downloaded_assets = self._map_local_assets_by_basename(
            extracted_assets,
            asset_dir=WILEY_2004GB002273_ASSET_DIR,
        )
        extracted_figures = [asset for asset in extracted_assets if asset.get("kind") == "figure"]
        downloaded_figures = [asset for asset in downloaded_assets if asset.get("kind") == "figure"]
        self.assertEqual(len(downloaded_figures), len(extracted_figures))

        article, _, _ = self._build_browser_fixture_article(
            client,
            html=html,
            landing_url=landing_url,
            article_metadata=metadata,
            downloaded_assets=downloaded_assets,
        )
        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertNotIn("\n## Figures\n", rendered)
        self.assertNotIn("Open in figure viewer", rendered)
        self.assertNotIn("PowerPoint", rendered)

    def test_pnas_provider_keeps_frontmatter_once_and_filters_collateral_noise_in_final_render(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2309123120"
        title = "Amazon deforestation causes strong regional warming"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        html = PNAS_REGRESSION_FIXTURE.read_text(encoding="utf-8")
        _, extraction, raw_payload = self._build_browser_html_raw_payload(
            client,
            html=html,
            landing_url=landing_url,
            extraction_metadata={"doi": doi, "title": title},
        )
        article = client.to_article_model(
            {"doi": doi, "title": title, "abstract": extraction.get("abstract_text")},
            raw_payload,
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(rendered.count("## Significance"), 1)
        self.assertEqual(rendered.count("## Abstract"), 1)
        self.assertNotIn("community water fluoridation", rendered.lower())
        self.assertNotIn("tattoo ink", rendered.lower())
        self.assertNotIn("negative social ties", rendered.lower())
        self.assertNotIn("sign up for pnas alerts", rendered.lower())

    def test_science_provider_falls_back_to_pdf_with_browser_seed(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            seed = {
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".science.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            preflight_seed = {
                "browser_cookies": [{"name": "sessionid", "value": "warm", "domain": ".science.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    side_effect=_flaresolverr.FlareSolverrFailure(
                        "redirected_to_abstract",
                        "Abstract redirect",
                        browser_context_seed=seed,
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "warm_browser_context_with_flaresolverr",
                    return_value={
                        "browser_cookies": [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
                        "browser_user_agent": "Mozilla/5.0",
                        "browser_final_url": f"https://www.science.org/doi/{SCIENCE_SAMPLE.doi}",
                    },
                ) as mocked_warm,
                mock.patch.object(
                    browser_workflow,
                    "fetch_pdf_with_playwright",
                    return_value=mock.Mock(
                        source_url=f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                        final_url=f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                )
                article = client.to_article_model(
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                )

        mocked_warm.assert_called_once()
        mocked_pdf.assert_called_once()
        self.assertEqual(
            mocked_pdf.call_args.kwargs["browser_cookies"],
            [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
        )
        self.assertEqual(
            mocked_pdf.call_args.kwargs["seed_urls"],
            [SCIENCE_SAMPLE.landing_url],
        )
        self.assertIn(
            f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
            list(mocked_pdf.call_args.args[0]),
        )
        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "science")
        self.assertIn("fulltext:science_pdf_fallback_ok", article.quality.source_trail)

    def test_pnas_provider_prefers_html_route(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            with (
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_direct_playwright",
                    side_effect=browser_workflow.SciencePnasHtmlFailure("playwright_direct_failed", "Direct preflight failed."),
                ),
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=PNAS_SAMPLE.landing_url,
                        final_url=PNAS_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=PNAS_SAMPLE.title,
                        summary="Example summary",
                        browser_context_seed={},
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "extract_science_pnas_markdown",
                    return_value=(f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120), {"title": PNAS_SAMPLE.title}),
                ),
                mock.patch.object(browser_workflow, "fetch_pdf_with_playwright") as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                )
                article = client.to_article_model(
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                )

        mocked_pdf.assert_not_called()
        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(article.source, "pnas")
        self.assertIn("fulltext:pnas_html_ok", article.quality.source_trail)

    def test_pnas_direct_playwright_html_preflight_skips_flaresolverr(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        seed = {
            "browser_cookies": [{"name": "sessionid", "value": "direct", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        with (
            mock.patch.object(
                browser_workflow,
                "fetch_html_with_direct_playwright",
                return_value=_flaresolverr.FetchedPublisherHtml(
                    source_url=PNAS_SAMPLE.landing_url,
                    final_url=PNAS_SAMPLE.landing_url,
                    html="<html><body><main>PNAS direct full text</main></body></html>",
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title=PNAS_SAMPLE.title,
                    summary="PNAS direct full text",
                    browser_context_seed=seed,
                ),
            ) as mocked_direct,
            mock.patch.object(browser_workflow, "load_runtime_config") as mocked_runtime,
            mock.patch.object(browser_workflow, "fetch_html_with_flaresolverr") as mocked_flaresolverr,
            mock.patch.object(
                browser_workflow,
                "extract_science_pnas_markdown",
                return_value=(f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120), {"title": PNAS_SAMPLE.title}),
            ),
        ):
            raw_payload = client.fetch_raw_fulltext(
                PNAS_SAMPLE.doi,
                {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
            )

        mocked_direct.assert_called_once()
        mocked_runtime.assert_not_called()
        mocked_flaresolverr.assert_not_called()
        self.assertIsNotNone(raw_payload.content)
        assert raw_payload.content is not None
        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(raw_payload.content.fetcher, "playwright_direct")
        self.assertEqual(raw_payload.content.browser_context_seed, seed)
        self.assertIn("fulltext:pnas_html_ok", _payload_source_trail(raw_payload))

    def test_pnas_direct_playwright_html_preflight_falls_back_to_flaresolverr(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            with (
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_direct_playwright",
                    side_effect=browser_workflow.SciencePnasHtmlFailure("insufficient_body", "Direct body was not sufficient."),
                ) as mocked_direct,
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime) as mocked_runtime,
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=PNAS_SAMPLE.landing_url,
                        final_url=PNAS_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=PNAS_SAMPLE.title,
                        summary="Example summary",
                        browser_context_seed={},
                    ),
                ) as mocked_flaresolverr,
                mock.patch.object(
                    browser_workflow,
                    "extract_science_pnas_markdown",
                    return_value=(f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120), {"title": PNAS_SAMPLE.title}),
                ),
            ):
                raw_payload = client.fetch_raw_fulltext(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                )

        mocked_direct.assert_called_once()
        mocked_runtime.assert_called_once()
        mocked_flaresolverr.assert_called_once()
        self.assertIsNotNone(raw_payload.content)
        assert raw_payload.content is not None
        self.assertEqual(raw_payload.content.fetcher, "flaresolverr")

    def test_pnas_provider_fetch_result_recovers_pdf_when_html_article_is_abstract_only(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2509692123"
        title = "A discrete serotonergic circuit involved in the generation of tinnitus behavior"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        html_payload = _typed_raw_payload(
            provider="pnas",
            source_url=landing_url,
            content_type="text/html",
            body=PNAS_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=PNAS_PAYWALL_SAMPLE_MARKDOWN.read_text(encoding="utf-8"),
            source_trail=["fulltext:pnas_html_ok"],
            browser_context_seed={
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            },
        )
        pdf_payload = _typed_raw_payload(
            provider="pnas",
            source_url=f"https://www.pnas.org/doi/pdf/{doi}",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            route="pdf_fallback",
            markdown_text=PNAS_FULLTEXT_FALLBACK_MARKDOWN.read_text(encoding="utf-8"),
            source_trail=[
                "fulltext:pnas_html_ok",
                "fulltext:pnas_abstract_only",
                "fulltext:pnas_pdf_fallback_ok",
            ],
            suggested_filename="archive.pdf",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", doi)
            with (
                mock.patch.object(client, "fetch_raw_fulltext", return_value=html_payload),
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(browser_workflow, "fetch_seeded_browser_pdf_payload", return_value=pdf_payload) as mocked_pdf,
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        mocked_pdf.assert_called_once()
        self.assertEqual(result.article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:pnas_html_ok", result.article.quality.source_trail)
        self.assertIn("fulltext:pnas_abstract_only", result.article.quality.source_trail)
        self.assertIn("fulltext:pnas_pdf_fallback_ok", result.article.quality.source_trail)
        self.assertTrue(
            any(
                "attempting PDF fallback" in warning
                for warning in mocked_pdf.call_args.kwargs["warnings"]
            )
        )

    def test_science_provider_fetch_result_recovers_pdf_for_paywall_sample_markdown(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.aeg3511"
        title = "Magma plumbing beneath Yellowstone"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        markdown_text = SCIENCE_PAYWALL_SAMPLE_MARKDOWN.read_text(encoding="utf-8")
        html_text = SCIENCE_PAYWALL_SAMPLE_RAW.read_text(encoding="utf-8")
        diagnostics = assess_html_fulltext_availability(
            markdown_text,
            {
                "title": title,
                "doi": doi,
                "abstract": markdown_text.split("## Access the full article", 1)[0].split("## Abstract", 1)[1].strip(),
            },
            provider="science",
            html_text=html_text,
            title=title,
            final_url=landing_url,
        )
        html_payload = _typed_raw_payload(
            provider="science",
            source_url=landing_url,
            content_type="text/html",
            body=SCIENCE_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=markdown_text,
            source_trail=["fulltext:science_html_ok"],
            availability_diagnostics=diagnostics.to_dict(),
            browser_context_seed={
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".science.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            },
        )
        pdf_payload = _typed_raw_payload(
            provider="science",
            source_url=f"https://www.science.org/doi/epdf/{doi}",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            route="pdf_fallback",
            markdown_text=SCIENCE_FULLTEXT_FALLBACK_MARKDOWN.read_text(encoding="utf-8"),
            source_trail=[
                "fulltext:science_html_ok",
                "fulltext:science_abstract_only",
                "fulltext:science_pdf_fallback_ok",
            ],
            suggested_filename="science-paywall.pdf",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", doi)
            with (
                mock.patch.object(client, "fetch_raw_fulltext", return_value=html_payload),
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(browser_workflow, "fetch_seeded_browser_pdf_payload", return_value=pdf_payload) as mocked_pdf,
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        mocked_pdf.assert_called_once()
        self.assertEqual(result.article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:science_html_ok", result.article.quality.source_trail)
        self.assertIn("fulltext:science_abstract_only", result.article.quality.source_trail)
        self.assertIn("fulltext:science_pdf_fallback_ok", result.article.quality.source_trail)

    def test_pnas_provider_fetch_result_returns_abstract_only_when_pdf_recovery_fails(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2509692123"
        title = "A discrete serotonergic circuit involved in the generation of tinnitus behavior"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        html_payload = _typed_raw_payload(
            provider="pnas",
            source_url=landing_url,
            content_type="text/html",
            body=PNAS_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=PNAS_PAYWALL_SAMPLE_MARKDOWN.read_text(encoding="utf-8"),
            source_trail=["fulltext:pnas_html_ok"],
            browser_context_seed={
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", doi)
            with (
                mock.patch.object(client, "fetch_raw_fulltext", return_value=html_payload),
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_seeded_browser_pdf_payload",
                    side_effect=browser_workflow.PdfFallbackFailure("pdf_download_failed", "PNAS PDF fallback failed."),
                ),
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        self.assertEqual(result.article.source, "pnas")
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertIn("fulltext:pnas_html_ok", result.article.quality.source_trail)
        self.assertIn("fulltext:pnas_abstract_only", result.article.quality.source_trail)
        self.assertNotIn("fulltext:pnas_pdf_fallback_ok", result.article.quality.source_trail)
        self.assertTrue(any("returning abstract-only content" in warning for warning in result.article.quality.warnings))

    def test_science_provider_fetch_result_returns_abstract_only_when_pdf_recovery_fails(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.aeg3511"
        title = "Magma plumbing beneath Yellowstone"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        html_text = SCIENCE_PAYWALL_SAMPLE_RAW.read_text(encoding="utf-8")
        markdown_text = SCIENCE_PAYWALL_SAMPLE_MARKDOWN.read_text(encoding="utf-8")
        diagnostics = assess_html_fulltext_availability(
            markdown_text,
            {
                "title": title,
                "doi": doi,
                "abstract": markdown_text.split("## Access the full article", 1)[0].split("## Abstract", 1)[1].strip(),
            },
            provider="science",
            html_text=html_text,
            title=title,
            final_url=landing_url,
        )
        html_payload = _typed_raw_payload(
            provider="science",
            source_url=landing_url,
            content_type="text/html",
            body=SCIENCE_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=markdown_text,
            source_trail=["fulltext:science_html_ok"],
            availability_diagnostics=diagnostics.to_dict(),
            browser_context_seed={
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".science.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", doi)
            with (
                mock.patch.object(client, "fetch_raw_fulltext", return_value=html_payload),
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_seeded_browser_pdf_payload",
                    side_effect=browser_workflow.PdfFallbackFailure("pdf_download_failed", "Science PDF fallback failed."),
                ),
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        self.assertEqual(result.article.source, "science")
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertIn("fulltext:science_html_ok", result.article.quality.source_trail)
        self.assertIn("fulltext:science_abstract_only", result.article.quality.source_trail)
        self.assertNotIn("fulltext:science_pdf_fallback_ok", result.article.quality.source_trail)
        self.assertTrue(any("returning abstract-only content" in warning for warning in result.article.quality.warnings))

    def test_wiley_provider_fetch_result_returns_abstract_only_when_pdf_recovery_fails(self) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1111/gcb.16998"
        title = "Wiley Abstract Only Example"
        landing_url = f"https://onlinelibrary.wiley.com/doi/full/{doi}"
        html_payload = _typed_raw_payload(
            provider="wiley",
            source_url=landing_url,
            content_type="text/html",
            body=b"<html></html>",
            route="html",
            markdown_text=f"# {title}\n\n## Abstract\n\nWiley abstract only.",
            source_trail=["fulltext:wiley_html_ok"],
            browser_context_seed={
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".wiley.com", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(client, "fetch_raw_fulltext", return_value=html_payload),
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_seeded_browser_pdf_payload",
                    side_effect=browser_workflow.PdfFallbackFailure("pdf_download_failed", "Wiley PDF fallback failed."),
                ),
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        self.assertEqual(result.article.source, "wiley_browser")
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertIn("fulltext:wiley_html_ok", result.article.quality.source_trail)
        self.assertIn("fulltext:wiley_abstract_only", result.article.quality.source_trail)
        self.assertNotIn("fulltext:wiley_pdf_fallback_ok", result.article.quality.source_trail)
        self.assertTrue(any("returning abstract-only content" in warning for warning in result.article.quality.warnings))

    def test_pnas_provider_falls_back_to_pdf_with_browser_seed(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            seed = {
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            preflight_seed = {
                "browser_cookies": [{"name": "sessionid", "value": "warm", "domain": ".pnas.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            with (
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_direct_playwright",
                    side_effect=browser_workflow.SciencePnasHtmlFailure("playwright_direct_failed", "Direct preflight failed."),
                ),
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    side_effect=_flaresolverr.FlareSolverrFailure(
                        "redirected_to_abstract",
                        "Abstract redirect",
                        browser_context_seed=seed,
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "warm_browser_context_with_flaresolverr",
                    return_value={
                        "browser_cookies": [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
                        "browser_user_agent": "Mozilla/5.0",
                        "browser_final_url": f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
                    },
                ) as mocked_warm,
                mock.patch.object(
                    browser_workflow,
                    "fetch_pdf_with_playwright",
                    return_value=mock.Mock(
                        source_url=f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
                        final_url=f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                )
                article = client.to_article_model(
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                )

        mocked_warm.assert_called_once()
        mocked_pdf.assert_called_once()
        kwargs = mocked_pdf.call_args.kwargs
        self.assertEqual(
            kwargs["browser_cookies"],
            [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
        )
        self.assertEqual(kwargs["seed_urls"], [f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}"])
        self.assertEqual(
            list(mocked_pdf.call_args.args[0])[:3],
            [
                f"https://www.pnas.org/doi/epdf/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}?download=true",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
            ],
        )
        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "pnas")
        self.assertIn("fulltext:pnas_pdf_fallback_ok", article.quality.source_trail)

    def test_science_provider_download_related_assets_body_profile_ignores_supplementary(self) -> None:
        html = """
<article>
  <figure>
    <img src="https://www.science.org/images/large/figure1.png" alt="Figure 1 alt" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <section id="supplementary-materials" class="core-supplementary-materials">
    <h2>Supplementary Materials</h2>
    <a href="https://www.science.org/doi/suppl/10.1126/science.sample/suppl_file/appendix.pdf">Download</a>
  </section>
</article>
"""
        figure_url = "https://www.science.org/images/large/figure1.png"
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": b"figure-1",
                "url": figure_url,
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed={},
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(browser_workflow, "fetch_html_with_flaresolverr") as mocked_fetch,
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_fetch.assert_not_called()
        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assertEqual(transport.calls, [])
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], figure_url)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["kind"], "figure")
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(saved_bytes, b"figure-1")

    def test_science_provider_download_related_assets_all_profile_downloads_supplementary_via_file_fetcher(self) -> None:
        figure_url = "https://www.science.org/images/large/figure1.png"
        supplementary_url = "https://www.science.org/doi/suppl/10.1126/science.sample/suppl_file/appendix.pdf"
        html = f"""
<article>
  <figure>
    <img src="{figure_url}" alt="Figure 1 alt" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <section id="supplementary-materials" class="core-supplementary-materials">
    <h2>Supplementary Materials</h2>
    <a href="{supplementary_url}">Download</a>
  </section>
</article>
"""
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_image_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": b"figure-1",
                "url": figure_url,
            }
        )
        shared_file_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "body": b"%PDF-1.7 supplementary",
                "url": supplementary_url,
            }
        )
        challenge_html = {
            "status_code": 403,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head><title>Just a moment...</title></head>"
                b"<body>Checking your browser before accessing</body></html>"
            ),
            "url": supplementary_url,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed={},
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(html_assets, "_build_cookie_seeded_opener", return_value=object()) as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener", return_value=challenge_html) as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_image_fetcher,
                ) as mocked_image_builder,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_file_fetcher",
                    return_value=shared_file_fetcher,
                ) as mocked_file_builder,
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="all",
                )

        mocked_opener.assert_called_once()
        mocked_request.assert_called_once()
        mocked_image_builder.assert_called_once()
        mocked_file_builder.assert_called_once()
        self.assertEqual(transport.calls, [])
        shared_image_fetcher.assert_called_once()
        shared_file_fetcher.assert_called_once()
        self.assertEqual(shared_file_fetcher.call_args.args[0], supplementary_url)
        self.assertEqual(
            [asset["kind"] for asset in result["assets"]],
            ["figure", "supplementary"],
        )
        self.assertEqual(result["assets"][1]["download_tier"], "supplementary_file")
        self.assertEqual(result["asset_failures"], [])

    def test_pnas_provider_download_related_assets_uses_figure_page_and_falls_back_to_preview(self) -> None:
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url = "https://www.pnas.org/images/preview/figure1.png"
        full_size_url = "https://www.pnas.org/images/original/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        initial_seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        warmed_seed = {
            "browser_cookies": [{"name": "sessionid", "value": "warm", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": figure_page_url,
        }
        shared_fetcher = mock.Mock(
            side_effect=[
                None,
                {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"preview-image",
                    "url": preview_url,
                },
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=initial_seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=figure_page_url,
                        final_url=figure_page_url,
                        html=(
                            "<html><head>"
                            f"<meta property='og:image' content='{full_size_url}' />"
                            "</head><body></body></html>"
                        ),
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Figure page",
                        summary="Figure page summary",
                        browser_context_seed=warmed_seed,
                    ),
                ) as mocked_fetch,
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_fetch.assert_called_once()
        self.assertEqual(mocked_fetch.call_args.args[0], [figure_page_url])
        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assertEqual(transport.calls, [])
        self.assertEqual([call.args[0] for call in shared_fetcher.call_args_list], [full_size_url, preview_url])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(saved_bytes, b"preview-image")

    def test_pnas_provider_download_related_assets_uses_shared_playwright_primary_path_before_preview(self) -> None:
        """rule: rule-browser-primary-image-download-path"""
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url = "https://www.pnas.org/images/preview/figure1.png"
        full_size_url = "https://www.pnas.org/images/original/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        initial_seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/jpeg"},
                "body": b"\xff\xd8\xffprimary-image",
                "url": full_size_url,
                "dimensions": {"width": 1200, "height": 800},
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=initial_seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=figure_page_url,
                        final_url=figure_page_url,
                        html=(
                            "<html><head>"
                            f"<meta property='og:image' content='{full_size_url}' />"
                            "</head><body></body></html>"
                        ),
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Figure page",
                        summary="Figure page summary",
                        browser_context_seed=initial_seed,
                    ),
                ),
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assertEqual(transport.calls, [])
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], full_size_url)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(saved_bytes, b"\xff\xd8\xffprimary-image")

    def test_pnas_provider_reuses_cached_figure_page_for_repeated_assets(self) -> None:
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url_one = "https://www.pnas.org/images/preview/figure1-a.png"
        preview_url_two = "https://www.pnas.org/images/preview/figure1-b.png"
        full_size_url = "https://www.pnas.org/images/original/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url_one}" alt="Preview figure one" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url_two}" alt="Preview figure two" />
    <figcaption>Figure 2 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": full_size_url,
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=figure_page_url,
                        final_url=figure_page_url,
                        html=(
                            "<html><head>"
                            f"<meta property='og:image' content='{full_size_url}' />"
                            "</head><body></body></html>"
                        ),
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Figure page",
                        summary="Figure page summary",
                        browser_context_seed=seed,
                    ),
                ) as mocked_fetch,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ),
            ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        self.assertEqual(mocked_fetch.call_count, 1)
        self.assertEqual(shared_fetcher.call_count, 1)
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual([asset["download_url"] for asset in result["assets"]], [full_size_url, full_size_url])

    def test_science_provider_reuses_cached_image_candidate_for_repeated_assets(self) -> None:
        full_size_url = "https://www.science.org/images/original/figure1.png"
        preview_url_one = "https://www.science.org/images/preview/figure1-a.png"
        preview_url_two = "https://www.science.org/images/preview/figure1-b.png"
        html = "<article><p>Body text</p></article>"
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": full_size_url,
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed={},
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(browser_workflow, "fetch_html_with_flaresolverr") as mocked_fetch,
                mock.patch.object(
                    science_pnas_asset_scopes,
                    "extract_scoped_html_assets",
                    return_value=[
                        {
                            "kind": "figure",
                            "heading": "Figure 1",
                            "caption": "Figure 1 caption",
                            "url": full_size_url,
                            "preview_url": preview_url_one,
                            "full_size_url": full_size_url,
                            "section": "body",
                        },
                        {
                            "kind": "figure",
                            "heading": "Figure 2",
                            "caption": "Figure 2 caption",
                            "url": full_size_url,
                            "preview_url": preview_url_two,
                            "full_size_url": full_size_url,
                            "section": "body",
                        },
                    ],
                ),
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ),
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        mocked_fetch.assert_not_called()
        self.assertEqual(shared_fetcher.call_count, 1)
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual([asset["download_url"] for asset in result["assets"]], [full_size_url, full_size_url])

    def test_science_provider_records_preview_dimensions_and_acceptance(self) -> None:
        preview_url = "https://www.science.org/images/preview/figure1.png"
        html = f"""
<article>
  <figure>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        image_body = png_header(640, 480)
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": image_body,
                "url": preview_url,
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed={},
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(browser_workflow, "fetch_html_with_flaresolverr") as mocked_fetch,
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        mocked_fetch.assert_not_called()
        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assertEqual(transport.calls, [])
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], preview_url)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(result["assets"][0]["width"], 640)
        self.assertEqual(result["assets"][0]["height"], 480)
        self.assertTrue(result["assets"][0]["preview_accepted"])

    def test_science_provider_records_asset_failure_when_shared_playwright_preview_fails(self) -> None:
        preview_url = "https://www.science.org/images/preview/figure1.png"
        html = f"""
<article>
  <figure>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "initial", "domain": ".science.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": SCIENCE_SAMPLE.landing_url,
        }
        refreshed_seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "refreshed", "domain": ".science.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": SCIENCE_SAMPLE.landing_url,
        }
        first_fetcher = mock.Mock(return_value=None)
        retry_fetcher = mock.Mock(return_value=None)
        first_fetcher.failure_for = mock.Mock(
            return_value={
                "status": 403,
                "content_type": "text/html; charset=UTF-8",
                "title_snippet": "Just a moment...",
                "body_snippet": "Just a moment...",
                "reason": "cloudflare_challenge",
            }
        )
        retry_fetcher.failure_for = mock.Mock(
            return_value={
                "status": 403,
                "content_type": "text/html; charset=UTF-8",
                "title_snippet": "Just a moment...",
                "body_snippet": "Just a moment...",
                "reason": "cloudflare_challenge",
                "recovery_attempts": [
                    {
                        "status": "failed",
                        "url": SCIENCE_SAMPLE.landing_url,
                        "reason": "cloudflare_challenge",
                    }
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "warm_browser_context_with_flaresolverr",
                    return_value=refreshed_seed,
                ) as mocked_warm,
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    side_effect=[first_fetcher, retry_fetcher],
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        self.assertEqual(mocked_builder.call_count, 2)
        mocked_warm.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assertEqual(transport.calls, [])
        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["asset_failures"]), 1)
        self.assertEqual(result["asset_failures"][0]["source_url"], preview_url)
        self.assertEqual(result["asset_failures"][0]["status"], 403)
        self.assertEqual(result["asset_failures"][0]["title_snippet"], "Just a moment...")
        self.assertEqual(result["asset_failures"][0]["reason"], "cloudflare_challenge")
        self.assertEqual(result["asset_failures"][0]["recovery_attempts"][0]["status"], "failed")

    def test_shared_playwright_image_fetcher_recovers_after_cloudflare_challenge(self) -> None:
        image_url = "https://onlinelibrary.wiley.com/cms/asset/full/figure1.jpg"
        figure_page_url = "https://onlinelibrary.wiley.com/doi/figure/10.1111/example"
        challenge_recovery = mock.Mock(
            return_value={
                "status": "ok",
                "url": figure_page_url,
                "title_snippet": "Figure page",
            }
        )
        fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=lambda: {
                "browser_cookies": [{"name": "cf_clearance", "value": "seed", "domain": ".wiley.com", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
                "browser_final_url": figure_page_url,
            },
            seed_urls_getter=lambda: [figure_page_url],
            browser_user_agent="Mozilla/5.0",
            challenge_recovery=challenge_recovery,
        )
        fetcher._ensure_page = mock.Mock(return_value=object())
        fetcher._sync_context_cookies = mock.Mock()
        fetcher._warm_seed_urls = mock.Mock()

        def side_effect(current_url: str):
            if fetcher.failure_for(current_url) is None:
                fetcher._record_failure(
                    current_url,
                    status=403,
                    content_type="text/html; charset=UTF-8",
                    title_snippet="Just a moment...",
                    body_snippet="Just a moment...",
                    reason="cloudflare_challenge",
                )
                return None
            return {
                "status_code": 200,
                "headers": {"content-type": "image/jpeg"},
                "body": b"\xff\xd8\xffrecovered-image",
                "url": current_url,
            }

        fetcher._fetch_with_page = mock.Mock(side_effect=side_effect)

        try:
            result = fetcher(image_url, {"figure_page_url": figure_page_url})
        finally:
            fetcher.close()

        self.assertIsNotNone(result)
        assert result is not None
        challenge_recovery.assert_called_once()
        self.assertEqual(challenge_recovery.call_args.args[0], image_url)
        self.assertEqual(challenge_recovery.call_args.args[2]["status"], 403)
        self.assertEqual(fetcher._warm_seed_urls.call_args_list[0].kwargs["force"], False)
        self.assertEqual(fetcher._warm_seed_urls.call_args_list[1].kwargs["force"], True)
        self.assertEqual(result["url"], image_url)

    def test_pnas_provider_downloads_preview_through_shared_playwright_when_no_full_size_candidate(self) -> None:
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url = "https://www.pnas.org/images/preview/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(320, 240),
                "url": preview_url,
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=figure_page_url,
                        final_url=figure_page_url,
                        html="<html><body><p>Figure page without direct full-size URL.</p></body></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Figure page",
                        summary="Figure page summary",
                        browser_context_seed=seed,
                    ),
                ),
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_bytes = Path(result["assets"][0]["path"]).read_bytes()

        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assertEqual(transport.calls, [])
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], preview_url)
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(result["assets"][0]["width"], 320)
        self.assertEqual(result["assets"][0]["height"], 240)
        self.assertEqual(saved_bytes, png_header(320, 240))

    def test_browser_workflow_download_related_assets_retries_after_partial_failures(self) -> None:
        figure_url = "https://www.pnas.org/images/large/figure1.png"
        html = f"""
<article>
  <figure>
    <img src="{figure_url}" alt="Figure 1" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        client = pnas_provider.PnasClient(transport=AssetTransport({}), env={})
        initial_seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "initial", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        refreshed_seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "refreshed", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        failing_fetcher = mock.Mock(return_value=None)
        successful_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": figure_url,
                "dimensions": {"width": 640, "height": 480},
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=initial_seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "warm_browser_context_with_flaresolverr",
                    return_value=refreshed_seed,
                ) as mocked_warm,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    side_effect=[failing_fetcher, successful_fetcher],
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        self.assertEqual(mocked_builder.call_count, 2)
        mocked_warm.assert_called_once()
        self.assertEqual(
            mocked_builder.call_args_list[1].kwargs["browser_context_seed_getter"]()["browser_cookies"][0]["value"],
            "refreshed",
        )
        failing_fetcher.assert_called_once()
        successful_fetcher.assert_called_once()
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["download_url"], figure_url)

    def test_browser_workflow_retries_only_failed_supplementary_assets(self) -> None:
        doi = "10.5555/retry-supplement"
        article_url = "https://example.test/article"
        figure_asset = {
            "kind": "figure",
            "heading": "Figure 1",
            "caption": "Figure caption",
            "url": "https://example.test/figure1.png",
            "section": "body",
        }
        supplementary_asset = {
            "kind": "supplementary",
            "heading": "Supplement 1",
            "url": "https://example.test/supplement.docx",
            "section": "supplementary",
        }
        figure_result = {
            "assets": [
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "caption": "Figure caption",
                    "download_url": "https://example.test/figure1.png",
                    "source_url": "https://example.test/figure1.png",
                    "section": "body",
                }
            ],
            "asset_failures": [],
        }
        supplementary_failure = {
            "assets": [],
            "asset_failures": [
                {
                    "kind": "supplementary",
                    "heading": "Supplement 1",
                    "source_url": "https://example.test/supplement.docx",
                    "section": "supplementary",
                    "reason": "cloudflare_challenge",
                }
            ],
        }
        supplementary_success = {
            "assets": [
                {
                    "kind": "supplementary",
                    "heading": "Supplement 1",
                    "download_url": "https://example.test/supplement.docx",
                    "source_url": "https://example.test/supplement.docx",
                    "section": "supplementary",
                    "download_tier": "supplementary_file",
                }
            ],
            "asset_failures": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", doi)
            client = browser_workflow.BrowserWorkflowClient(AssetTransport({}), {})
            client.name = "science"
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=article_url,
                content_type="text/html",
                body=b"<html></html>",
                route="html",
                browser_context_seed={"browser_final_url": article_url},
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "_cached_browser_workflow_assets",
                    return_value=[figure_asset, supplementary_asset],
                ),
                mock.patch.object(
                    browser_workflow,
                    "warm_browser_context_with_flaresolverr",
                    return_value={"browser_final_url": article_url},
                ) as mocked_warm,
                mock.patch.object(
                    browser_workflow,
                    "download_figure_assets_with_image_document_fetcher",
                    return_value=figure_result,
                ) as mocked_figures,
                mock.patch.object(
                    browser_workflow,
                    "download_supplementary_assets",
                    side_effect=[supplementary_failure, supplementary_success],
                ) as mocked_supplementary,
            ):
                result = client.download_related_assets(
                    doi,
                    {"doi": doi, "title": "Retry Supplement"},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="all",
                )

        mocked_warm.assert_called_once()
        mocked_figures.assert_called_once()
        self.assertEqual(mocked_figures.call_args.kwargs["assets"], [figure_asset])
        self.assertEqual(mocked_supplementary.call_count, 2)
        self.assertEqual(mocked_supplementary.call_args_list[0].kwargs["assets"], [supplementary_asset])
        self.assertEqual(mocked_supplementary.call_args_list[1].kwargs["assets"], [supplementary_asset])
        self.assertEqual(
            [(asset["kind"], asset["download_url"]) for asset in result["assets"]],
            [
                ("figure", "https://example.test/figure1.png"),
                ("supplementary", "https://example.test/supplement.docx"),
            ],
        )
        self.assertEqual(result["asset_failures"], [])

    def test_browser_workflow_retries_only_failed_body_assets(self) -> None:
        doi = "10.5555/retry-figure"
        article_url = "https://example.test/article"
        first_figure = {
            "kind": "figure",
            "heading": "Figure 1",
            "caption": "Figure caption",
            "url": "https://example.test/figure1.png",
            "section": "body",
        }
        second_figure = {
            "kind": "figure",
            "heading": "Figure 2",
            "caption": "Second figure caption",
            "url": "https://example.test/figure2.png",
            "section": "body",
        }
        supplementary_asset = {
            "kind": "supplementary",
            "heading": "Supplement 1",
            "url": "https://example.test/supplement.docx",
            "section": "supplementary",
        }
        initial_body_result = {
            "assets": [
                {
                    "kind": "figure",
                    "heading": "Figure 2",
                    "caption": "Second figure caption",
                    "download_url": "https://example.test/figure2.png",
                    "source_url": "https://example.test/figure2.png",
                    "section": "body",
                }
            ],
            "asset_failures": [
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "caption": "Figure caption",
                    "source_url": "https://example.test/figure1.png",
                    "section": "body",
                    "reason": "cloudflare_challenge",
                }
            ],
        }
        retry_body_result = {
            "assets": [
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "caption": "Figure caption",
                    "download_url": "https://example.test/figure1.png",
                    "source_url": "https://example.test/figure1.png",
                    "section": "body",
                }
            ],
            "asset_failures": [],
        }
        supplementary_result = {
            "assets": [
                {
                    "kind": "supplementary",
                    "heading": "Supplement 1",
                    "download_url": "https://example.test/supplement.docx",
                    "source_url": "https://example.test/supplement.docx",
                    "section": "supplementary",
                    "download_tier": "supplementary_file",
                }
            ],
            "asset_failures": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", doi)
            client = browser_workflow.BrowserWorkflowClient(AssetTransport({}), {})
            client.name = "science"
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=article_url,
                content_type="text/html",
                body=b"<html></html>",
                route="html",
                browser_context_seed={"browser_final_url": article_url},
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "_cached_browser_workflow_assets",
                    return_value=[first_figure, second_figure, supplementary_asset],
                ),
                mock.patch.object(
                    browser_workflow,
                    "warm_browser_context_with_flaresolverr",
                    return_value={"browser_final_url": article_url},
                ) as mocked_warm,
                mock.patch.object(
                    browser_workflow,
                    "download_figure_assets_with_image_document_fetcher",
                    side_effect=[initial_body_result, retry_body_result],
                ) as mocked_figures,
                mock.patch.object(
                    browser_workflow,
                    "download_supplementary_assets",
                    return_value=supplementary_result,
                ) as mocked_supplementary,
            ):
                result = client.download_related_assets(
                    doi,
                    {"doi": doi, "title": "Retry Figure"},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="all",
                )

        mocked_warm.assert_called_once()
        self.assertEqual(mocked_figures.call_count, 2)
        self.assertEqual(mocked_figures.call_args_list[0].kwargs["assets"], [first_figure, second_figure])
        self.assertEqual(mocked_figures.call_args_list[1].kwargs["assets"], [first_figure])
        mocked_supplementary.assert_called_once()
        self.assertEqual(mocked_supplementary.call_args.kwargs["assets"], [supplementary_asset])
        self.assertEqual(
            sorted((asset["kind"], asset["download_url"]) for asset in result["assets"]),
            [
                ("figure", "https://example.test/figure1.png"),
                ("figure", "https://example.test/figure2.png"),
                ("supplementary", "https://example.test/supplement.docx"),
            ],
        )
        self.assertEqual(result["asset_failures"], [])

    def test_wiley_provider_download_related_assets_uses_shared_playwright_primary_path(self) -> None:
        full_size_url = "https://onlinelibrary.wiley.com/cms/asset/full/figure1.jpg"
        html = f"""
<article>
  <figure>
    <img src="{full_size_url}" alt="Figure 1" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        client = wiley_provider.WileyClient(transport=AssetTransport({}), env={})
        seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".wiley.com", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": "https://onlinelibrary.wiley.com/doi/10.1111/gcb.16011",
        }
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/jpeg"},
                "body": b"\xff\xd8\xffprimary-image",
                "url": full_size_url,
                "dimensions": {"width": 1400, "height": 900},
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", "10.1111/gcb.16011")
            raw_payload = _typed_raw_payload(
                provider="wiley",
                source_url="https://onlinelibrary.wiley.com/doi/10.1111/gcb.16011",
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text="# Title\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    "10.1111/gcb.16011",
                    {"doi": "10.1111/gcb.16011", "title": "Title"},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_bytes = Path(result["assets"][0]["path"]).read_bytes()

        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], full_size_url)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(saved_bytes, b"\xff\xd8\xffprimary-image")

    def test_wiley_provider_download_related_assets_reuses_shared_playwright_fetcher_across_assets(self) -> None:
        first_url = "https://onlinelibrary.wiley.com/cms/asset/full/figure1.jpg"
        second_url = "https://onlinelibrary.wiley.com/cms/asset/full/figure2.jpg"
        html = f"""
<article>
  <figure>
    <img src="{first_url}" alt="Figure 1" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <figure>
    <img src="{second_url}" alt="Figure 2" />
    <figcaption>Figure 2 caption</figcaption>
  </figure>
</article>
"""
        client = wiley_provider.WileyClient(transport=AssetTransport({}), env={})
        seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".wiley.com", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": "https://onlinelibrary.wiley.com/doi/10.1111/gcb.16011",
        }
        shared_fetcher = mock.Mock(
            side_effect=[
                {
                    "status_code": 200,
                    "headers": {"content-type": "image/jpeg"},
                    "body": b"\xff\xd8\xfffigure-one",
                    "url": first_url,
                    "dimensions": {"width": 1200, "height": 800},
                },
                {
                    "status_code": 200,
                    "headers": {"content-type": "image/jpeg"},
                    "body": b"\xff\xd8\xfffigure-two",
                    "url": second_url,
                    "dimensions": {"width": 1400, "height": 900},
                },
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", "10.1111/gcb.16011")
            raw_payload = _typed_raw_payload(
                provider="wiley",
                source_url="https://onlinelibrary.wiley.com/doi/10.1111/gcb.16011",
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text="# Title\n\n## Results\n\n" + ("Body text " * 120),
                browser_context_seed=seed,
            )
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(html_assets, "_build_cookie_seeded_opener") as mocked_opener,
                mock.patch.object(html_assets, "_request_with_opener") as mocked_request,
                mock.patch.object(
                    browser_workflow,
                    "_build_shared_playwright_image_fetcher",
                    return_value=shared_fetcher,
                ) as mocked_builder,
            ):
                result = client.download_related_assets(
                    "10.1111/gcb.16011",
                    {"doi": "10.1111/gcb.16011", "title": "Title"},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(shared_fetcher.call_count, 2)
        self.assertEqual(shared_fetcher.call_args_list[0].args[0], first_url)
        self.assertEqual(shared_fetcher.call_args_list[1].args[0], second_url)
        shared_fetcher.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
