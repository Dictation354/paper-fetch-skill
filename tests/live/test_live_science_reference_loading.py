"""Live Science bibliography and local body image acceptance in both modes."""

from functools import wraps
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from paper_fetch.browser_preflight import static_browser_capabilities
from paper_fetch.config import BROWSER_HEADLESS_ENV_VAR
from paper_fetch.http import redact_text_for_diagnostics
from paper_fetch.providers import browser_runtime
from paper_fetch.providers.science import ScienceClient
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from paper_fetch.workflow.types import PaperFetchFailure
from tests.live._runtime_env import build_isolated_live_env


DOI = "10.1126/science.ady3136"


@pytest.mark.parametrize("mode", ["headless", "headed"])
def test_science_complete_references_and_body_images(
    monkeypatch, record_property, mode
):
    if os.environ.get("PAPER_FETCH_RUN_LIVE") != "1":
        pytest.skip("Set PAPER_FETCH_RUN_LIVE=1 for live Science acceptance.")
    root = (
        Path(
            os.environ.get(
                "PAPER_FETCH_LIVE_ARTIFACT_DIR",
                ".paper-fetch-runs/live-science-reference-loading",
            )
        )
        / mode
    )
    root.mkdir(parents=True, exist_ok=True)

    def save(name, payload):
        (root / name).write_text(
            redact_text_for_diagnostics(
                json.dumps(payload, ensure_ascii=False, indent=2)
            ),
            encoding="utf-8",
        )

    env, temporary = build_isolated_live_env()
    env[BROWSER_HEADLESS_ENV_VAR] = "true" if mode == "headless" else "false"
    browser_traces = []
    original_fetch = browser_runtime.fetch_html_with_browser

    @wraps(original_fetch)
    def observed_fetch(*args, **kwargs):
        try:
            result = original_fetch(*args, **kwargs)
        except Exception as exc:
            browser_traces.append(dict(getattr(exc, "details", None) or {}))
            raise
        else:
            browser_traces.append(dict(result.diagnostics or {}))
            return result
        finally:
            save("browser-trace.json", browser_traces)

    original_init = ScienceClient.__init__

    @wraps(original_init)
    def observed_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.deps = replace(self.deps, fetch_html_with_browser=observed_fetch)

    monkeypatch.setattr(ScienceClient, "__init__", observed_init)
    context = RuntimeContext(env=env, download_dir=root / "paper", artifact_mode="all")
    try:
        capabilities = static_browser_capabilities(env, provider="science")
        save("static-capabilities.json", capabilities)
        assert capabilities["browser_runtime"]["available"], capabilities
        try:
            envelope = fetch_paper(
                DOI,
                modes={"article"},
                strategy=FetchStrategy(
                    preferred_providers=["science"],
                    allow_metadata_only_fallback=False,
                    asset_profile="body",
                ),
                context=context,
            )
        except PaperFetchFailure as exc:
            save(
                "acceptance.json",
                {
                    "doi": DOI,
                    "mode": mode,
                    "validation": "incomplete",
                    "status": exc.status,
                    "reason": exc.reason,
                    "details": exc.details,
                    "source_trail": exc.source_trail,
                },
            )
            raise
        acceptance = evaluate_fetch_acceptance(
            envelope,
            asset_profile="body",
            expected_doi=DOI,
            requested_outputs={"article"},
            require_local_body_assets=True,
        )
        article = envelope.article
        assert article is not None
        images = [
            asset
            for asset in article.assets
            if asset.kind == "figure" and asset.section != "supplementary"
        ]
        save("article.json", article.to_dict())
        save(
            "acceptance.json",
            {
                "doi": DOI,
                "mode": mode,
                "reference_count": len(article.references),
                "body_image_count": len(images),
                "image_paths": [asset.path for asset in images],
                "acceptance": acceptance.model_dump(mode="json"),
            },
        )
        record_property("reference_count", len(article.references))
        record_property("body_image_count", len(images))
        record_property("acceptance", acceptance.to_json())
        assert len(article.references) == 71
        assert len(images) == 5
        assert all(
            asset.path and Path(asset.path).stat().st_size > 0 for asset in images
        )
        assert "reference_targets_missing" not in article.quality.flags
        assert "fulltext:science_html_ok" in article.quality.source_trail
        assert acceptance.overall == "complete", acceptance.to_json()
        assert browser_traces
    finally:
        context.close()
        temporary.cleanup()
