from __future__ import annotations
import textwrap
import unittest


SERVER_SCRIPT = textwrap.dedent(
    """
    import logging
    from pathlib import Path

    from paper_fetch.models import AcquisitionProvenance, ArticleModel, Asset, FetchEnvelope, Metadata, Quality, Section, TokenEstimateBreakdown
    from dataclasses import replace

    from paper_fetch.browser_preflight import BrowserPreflightResult
    from paper_fetch.mcp import server as mcp_server
    from paper_fetch.mcp._deps import default_mcp_deps
    from paper_fetch.mcp.server import main
    from paper_fetch.providers.base import ProviderStatusResult, build_provider_status_check
    from paper_fetch.resolve.query import ResolvedQuery
    from paper_fetch.service import HasFulltextProbeResult
    from paper_fetch.tracing import TraceContext, trace_event
    from paper_fetch.utils import sanitize_filename

    def fake_resolve(query, *, context=None):
        lookup_query = query.lookup_query if hasattr(query, "lookup_query") else query
        return ResolvedQuery(
            query=lookup_query,
            query_kind="doi",
            doi=lookup_query if lookup_query.startswith("10.") else "10.1000/example",
            landing_url="https://example.test/article",
            provider_hint="crossref",
            confidence=1.0,
            candidates=[],
            title="Example Article",
        )

    def fake_fetch(query, *, modes=None, strategy=None, render=None, context=None):
        figure_path = None
        download_dir = context.download_dir if context is not None else None
        if download_dir is not None:
            output_dir = Path(download_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            base = sanitize_filename(query)
            (output_dir / f"{base}.xml").write_text("<article />", encoding="utf-8")
            (output_dir / f"{base}.md").write_text(
                (
                    "---\\n"
                    f'doi: "{query}"\\n'
                    'source: "elsevier_xml"\\n'
                    "acquisition:\\n"
                    '  provider: "elsevier"\\n'
                    '  route: "xml_api"\\n'
                    '  representation: "xml"\\n'
                    '  transport: "api"\\n'
                    "  fallback_used: false\\n"
                    "has_fulltext: true\\n"
                    'content_kind: "fulltext"\\n'
                    "---\\n\\n# Example Article\\n\\nExample body.\\n"
                ),
                encoding="utf-8",
            )
            asset_dir = output_dir / f"{base}_assets"
            asset_dir.mkdir(parents=True, exist_ok=True)
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"PNG")

        logging.getLogger("paper_fetch.service").debug(
            "fetch_stage message=legacy-fallback",
            extra={"structured_data": {"event": "fetch_stage", "query": query, "step": "fake stage with spaces"}},
        )
        logging.getLogger("paper_fetch.http").debug("legacy_fetch_stage query=%s status=%s", query, "ok")

        article = ArticleModel(
            doi=query,
            source="elsevier_xml",
            metadata=Metadata(
                title=f"Example Article for {query}",
                authors=["Alice Example"],
                abstract="Example abstract",
                journal="Example Journal",
                published="2026-01-01",
            ),
            sections=[Section(heading="Introduction", level=2, kind="body", text="Example body.")],
            references=[],
            assets=[
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Example inline figure.",
                    path=str(figure_path) if figure_path is not None else None,
                    section="body",
                )
            ],
            quality=Quality(
                has_fulltext=True,
                token_estimate=64,
                warnings=[],
                source_trail=["source:ok"],
                token_estimate_breakdown=TokenEstimateBreakdown(abstract=16, body=48, refs=20),
            ),
            acquisition=AcquisitionProvenance(
                provider="elsevier",
                route="xml_api",
                representation="xml",
                transport="api",
                fallback_used=False,
            ),
        )
        requested_modes = set(modes or set())
        return FetchEnvelope(
            doi=query,
            source="elsevier_xml",
            has_fulltext=True,
            acquisition=article.acquisition,
            warnings=[],
            source_trail=["source:ok"],
            trace=[
                trace_event("resolve", "doi_selected", "ok"),
                trace_event(
                    "metadata",
                    "elsevier",
                    "ok",
                    context=TraceContext(
                        provider="elsevier",
                        route="metadata_api",
                    ),
                ),
                trace_event(
                    "fulltext",
                    "elsevier_xml",
                    "ok",
                    context=TraceContext(
                        provider="elsevier",
                        route="xml_api",
                    ),
                ),
            ],
            token_estimate=64,
            token_estimate_breakdown=TokenEstimateBreakdown(abstract=16, body=48, refs=20),
            article=article if "article" in requested_modes else None,
            markdown="# Example Article\\n\\nExample body.\\n" if "markdown" in requested_modes else None,
            metadata=article.metadata if "metadata" in requested_modes else None,
        )

    def fake_probe(query, *, context=None):
        return HasFulltextProbeResult(
            query=query,
            doi=query if query.startswith("10.") else "10.1000/example",
            title=f"Example Article for {query}",
            state="likely_yes",
            evidence=["crossref_fulltext_link"],
            warnings=[],
        )

    class FakeProviderClient:
        def __init__(self, result):
            self.result = result
            self.official_provider = result.official_provider

        def probe_status(self):
            return self.result

    def fake_build_clients(*, transport=None, env=None, provider_names=None):
        clients = {
            "crossref": FakeProviderClient(
                ProviderStatusResult(
                    provider="crossref",
                    status="ready",
                    available=True,
                    official_provider=False,
                    notes=["CROSSREF_MAILTO is not configured; adding one is recommended for better API etiquette."],
                    checks=[build_provider_status_check("metadata_api", "ok", "Crossref metadata lookup is available.")],
                )
            ),
            "elsevier": FakeProviderClient(
                ProviderStatusResult(
                    provider="elsevier",
                    status="not_configured",
                    available=False,
                    official_provider=True,
                    missing_env=["ELSEVIER_API_KEY"],
                    checks=[
                        build_provider_status_check(
                            "fulltext_api",
                            "not_configured",
                            "ELSEVIER_API_KEY is required for Elsevier full-text retrieval.",
                            missing_env=["ELSEVIER_API_KEY"],
                        )
                    ],
                )
            ),
            "springer": FakeProviderClient(
                ProviderStatusResult(
                    provider="springer",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "html_route",
                            "ok",
                            "Springer direct HTML route is available.",
                        ),
                    ],
                )
            ),
            "wiley": FakeProviderClient(
                ProviderStatusResult(
                    provider="wiley",
                    status="not_configured",
                    available=False,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "runtime_env",
                            "not_configured",
                            "wiley browser runtime requires Playwright and Camoufox packages.",
                        ),
                        build_provider_status_check(
                            "playwright_dependency",
                            "not_configured",
                            "Playwright Python package is not installed.",
                        ),
                    ],
                )
            ),
            "science": FakeProviderClient(
                ProviderStatusResult(
                    provider="science",
                    status="not_configured",
                    available=False,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "runtime_env",
                            "not_configured",
                            "science browser runtime requires Playwright and Camoufox packages.",
                        ),
                        build_provider_status_check(
                            "playwright_dependency",
                            "not_configured",
                            "Playwright Python package is not installed.",
                        ),
                    ],
                )
            ),
            "pnas": FakeProviderClient(
                ProviderStatusResult(
                    provider="pnas",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check("runtime_env", "ok", "pnas runtime environment is configured."),
                        build_provider_status_check(
                            "playwright_dependency",
                            "ok",
                            "Playwright Python package is importable; live browser startup is not probed.",
                        ),
                    ],
                )
            ),
            "ieee": FakeProviderClient(
                ProviderStatusResult(
                    provider="ieee",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "html_route",
                            "ok",
                            "IEEE Xplore dynamic HTML route is available.",
                        ),
                        build_provider_status_check(
                            "pdf_fallback",
                            "ok",
                            "IEEE Xplore PDF fallback is available.",
                        ),
                    ],
                )
            ),
            "arxiv": FakeProviderClient(
                ProviderStatusResult(
                    provider="arxiv",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "metadata_api",
                            "ok",
                            (
                                "arXiv API metadata route uses the internal Atom client "
                                "for default metadata enrichment."
                            ),
                        ),
                        build_provider_status_check(
                            "html_route",
                            "ok",
                            "arXiv official HTML fallback is available.",
                        ),
                        build_provider_status_check(
                            "pdf_fallback",
                            "ok",
                            "arXiv PDF fallback is available.",
                        ),
                    ],
                )
            ),
            "copernicus": FakeProviderClient(
                ProviderStatusResult(
                    provider="copernicus",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "xml_route",
                            "ok",
                            "Copernicus direct NLM/JATS XML route is available.",
                        ),
                        build_provider_status_check(
                            "pdf_fallback",
                            "ok",
                            "Copernicus PDF fallback is available.",
                        ),
                    ],
                )
            ),
            "ams": FakeProviderClient(
                ProviderStatusResult(
                    provider="ams",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "local_requirements",
                            "ok",
                            "AMS direct HTTP HTML route is available.",
                        ),
                    ],
                )
            ),
            "mdpi": FakeProviderClient(
                ProviderStatusResult(
                    provider="mdpi",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check("runtime_env", "ok", "mdpi runtime environment is configured."),
                    ],
                )
            ),
        }
        if provider_names is None:
            return clients
        return {
            name: clients[name]
            for name in provider_names
            if name in clients
        }

    def fake_browser_preflight(
        *,
        providers=None,
        target_url=None,
        storage_state_path=None,
        save_storage_state=True,
        on_result=None,
        **kwargs,
    ):
        del kwargs
        provider = list(providers or ["wiley"])[0]
        saved = False
        if storage_state_path is not None and save_storage_state:
            storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            storage_state_path.write_text('{"cookies": []}\\n', encoding="utf-8")
            saved = True
        result = BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="ready",
            reason_code="browser_preflight_ready",
            stage="complete",
            target_url=target_url or "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            final_url=target_url or "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            title="Wiley preflight sample",
            storage_state_path=storage_state_path,
            diagnostics={
                "browser_runtime_trace": {
                    "storage_state_save": {
                        "attempted": storage_state_path is not None and save_storage_state,
                        "saved": saved,
                        "path": str(storage_state_path) if storage_state_path is not None else None,
                        "reason": None,
                    }
                }
            },
        )
        if on_result is not None:
            on_result(result, 1, 1)
        return [result]

    def fake_default_mcp_deps():
        return replace(
            default_mcp_deps(),
            service_resolve_paper=fake_resolve,
            service_fetch_paper=fake_fetch,
            service_probe_has_fulltext=fake_probe,
            build_clients=fake_build_clients,
            run_browser_provider_preflight=fake_browser_preflight,
        )

    mcp_server.default_mcp_deps = fake_default_mcp_deps
    main()
    """
)


if __name__ == "__main__":
    unittest.main()
