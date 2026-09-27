"""Opt-in full-paper Wiley audit; serial headed/headless runs retain all evidence."""

from dataclasses import asdict
import hashlib
import json
import os
import re
import time
from pathlib import Path

import pytest

from paper_fetch.browser_preflight import static_browser_capabilities
from paper_fetch.extraction.image_payloads import (
    image_dimensions_from_bytes,
    image_mime_type_from_bytes,
)
from paper_fetch.http import HttpTransport
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers._wiley_page_assets import WileyPageAssetFetcher
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper, resolve_paper
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.live._runtime_env import build_isolated_live_env


def image_facts(body):
    return {
        "sha256": hashlib.sha256(body).hexdigest(),
        "size": len(body),
        "mime": image_mime_type_from_bytes(body),
        "dimensions": image_dimensions_from_bytes(body),
    }


@pytest.mark.parametrize(
    "headless,doi,expected",
    [
        (mode, "10.1111/" + suffix, expected)
        for mode in (False, True)
        for suffix, expected in [
            ("gcb.15322", {"formula": 11, "figure": 4}),
            ("gcb.16758", {"formula": 26, "figure": 5}),
            ("gcb.16414", {"formula": 0, "figure": 6}),
        ]
    ],
)
def test_wiley_live_page_assets(headless, doi, expected, monkeypatch):
    if os.environ.get("PAPER_FETCH_RUN_WILEY_PAGE_ASSETS") != "1":
        pytest.skip(
            "Set PAPER_FETCH_RUN_WILEY_PAGE_ASSETS=1; use -n 0 for shared live state"
        )
    assert os.environ.get("PYTEST_XDIST_WORKER") is None, (
        "Live Wiley matrix must run serially (-n 0)"
    )
    root = Path(
        os.environ.get(
            "PAPER_FETCH_LIVE_ARTIFACT_DIR", ".paper-fetch-runs/wiley-page-assets-live"
        )
    )
    output = root / (("headless-" if headless else "headed-") + doi.split("/")[-1])
    output.mkdir(parents=True, exist_ok=False)
    env, isolation = build_isolated_live_env()
    env["PAPER_FETCH_BROWSER_HEADLESS"] = "true" if headless else "false"
    captured, sessions, requests = {}, [], []
    original_capture = WileyPageAssetFetcher._capture
    original_call = WileyPageAssetFetcher.__call__
    original_close = WileyPageAssetFetcher.close

    def capture(self, request):
        original_capture(self, request)
        for url, (response, _) in self._responses.items():
            captured[url] = {
                "response_url": response["url"],
                **image_facts(response["body"]),
            }

    def call(self, url, asset):
        started = time.monotonic()
        record = {"url": url, "asset": dict(asset)}
        requests.append(record)
        try:
            response = original_call(self, url, asset)
            record["recovery_attempts"] = (response or {}).get(
                "_paper_fetch_recovery_attempts", []
            )
            record["failure"] = self.failure_for(url)
            record["success"] = response is not None
            return response
        finally:
            record["seconds"] = time.monotonic() - started
            record["page_id"] = id(self._page) if self._page else None
            record["context_id"] = id(self._context) if self._context else None

    def close(self):
        record = None
        if not self._closed:
            record = {
                "navigation_count": self.navigation_count,
                "failures": dict(self._last_failure_by_url),
                "recovery_attempts": dict(self._recovery_attempts),
                "ready_at": self._ready_at,
            }
            sessions.append(record)
        original_close(self)
        if record is not None:
            record["cleaned"] = (
                self._page is None
                and self._context is None
                and not self._responses
                and not self._requests
            )

    monkeypatch.setattr(WileyPageAssetFetcher, "_capture", capture)
    monkeypatch.setattr(WileyPageAssetFetcher, "__call__", call)
    monkeypatch.setattr(WileyPageAssetFetcher, "close", close)
    started = time.monotonic()
    report = {"doi": doi, "headless": headless, "expected": expected}
    try:
        report["static_browser_capabilities"] = static_browser_capabilities(
            env, provider="wiley"
        )
        with RuntimeContext(
            env=env,
            transport=HttpTransport(),
            download_dir=output,
            artifact_mode="all",
            asset_profile="body",
        ) as runtime:
            resolved = resolve_paper(doi, context=runtime)
            report["identity"] = resolved.to_dict()
            assert resolved.doi == doi
            envelope = fetch_paper(
                doi,
                modes={"article"},
                context=runtime,
                strategy=FetchStrategy(
                    preferred_providers=["wiley"],
                    asset_profile="body",
                    allow_metadata_only_fallback=False,
                ),
            )
        report["acceptance"] = evaluate_fetch_acceptance(
            envelope, asset_profile="body"
        ).model_dump(mode="json")
        article = envelope.article
        assert article is not None
        report["assets"] = [asdict(asset) for asset in article.assets]
        targets = [asset for asset in article.assets if asset.kind in expected]
        files = []
        for asset in targets:
            if asset.path:
                path = Path(asset.path)
                files.append(
                    {
                        "path": str(path),
                        "url": asset.download_url,
                        "kind": asset.kind,
                        **image_facts(path.read_bytes()),
                    }
                )
        report["files"] = files
        report["counts"] = {
            kind: sum(a.kind == kind for a in targets) for kind in expected
        }
        report["local_counts"] = {
            kind: sum(f["kind"] == kind for f in files) for kind in expected
        }
        markdown = article.to_ai_markdown(
            include_refs="all", max_tokens="full_text", asset_profile="body"
        )
        (output / "article.md").write_text(markdown)
        # Rendering and archival are independent: structured math may replace the
        # image in prose, while every discovered formula bitmap must still exist.
        report["formula_positions"] = {
            "image": sum(
                "-math-" in image.url for image in iter_markdown_images(markdown)
            ),
            "latex": len(
                re.findall(
                    r"\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\$)[^\n$]+(?<!\\)\$", markdown
                )
            ),
            "missing": article.quality.semantic_losses.formula_missing_count,
        }
        assert article.doi == doi and article.quality.has_fulltext
        assert report["counts"] == report["local_counts"] == expected
        for asset in targets:
            path = Path(asset.path)
            facts = image_facts(path.read_bytes())
            received = next(
                value
                for key, value in captured.items()
                if key == asset.download_url
                or value["response_url"] == asset.download_url
            )
            assert facts == {key: received[key] for key in facts}
            assert (
                facts["size"] > 0
                and facts["dimensions"]
                and facts["mime"].startswith("image/")
            )
            if asset.kind == "figure":
                assert asset.download_tier == "full_size"
        positions = report["formula_positions"]
        assert positions["missing"] == 0
        assert positions["image"] + positions["latex"] == expected["formula"]
        assert len(sessions) == 1 and sessions[0]["cleaned"]
        assert (
            sessions[0]["navigation_count"] == len(requests) == sum(expected.values())
        )
        assert (
            len({r["page_id"] for r in requests})
            == len({r["context_id"] for r in requests})
            == 1
        )
        assert report["acceptance"]["overall"] == "complete"
    except Exception as exc:
        report["audit_error"] = {"type": type(exc).__name__}
        raise
    finally:
        report["whole_paper_seconds"] = time.monotonic() - started
        report.update(sessions=sessions, responses=captured, requests=requests)
        (output / "page-asset-audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        isolation.cleanup()
