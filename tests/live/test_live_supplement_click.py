"""Opt-in serial publisher audit; only fresh accepted clicks count as success."""

from dataclasses import asdict
from collections import deque
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import pytest

from paper_fetch.browser_preflight import static_browser_capabilities
from paper_fetch.http import HttpTransport
from paper_fetch.http.cache import redact_url_for_cache, redact_url_for_diagnostics
from paper_fetch.providers.browser_workflow.client import BrowserWorkflowClient
from paper_fetch.providers.browser_workflow.asset_download import (
    _CLICK_SUPPLEMENT_PROVIDERS,
)
from paper_fetch.providers.browser_workflow.fetchers import file as file_fetchers
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper, resolve_paper
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.live._runtime_env import build_isolated_live_env
from tests.provider_benchmark_samples import provider_benchmark_sample

DOI_OVERRIDES = {
    "science": "10.1126/sciadv.aea9165",
    "ieee": "10.1109/RITA.2026.3668995",
    "mdpi": "10.3390/s23010001",
    "royalsocietypublishing": "10.1098/rsif.2019.0334",
    "annualreviews": "10.1146/annurev-neuro-062111-150343",
    "iop": "10.1088/2752-5295/ae2d89",
}


@pytest.mark.parametrize("provider", sorted(_CLICK_SUPPLEMENT_PROVIDERS))
def test_live_supplement_click(provider, monkeypatch):
    if os.environ.get("PAPER_FETCH_RUN_SUPPLEMENT_CLICK") != "1":
        pytest.skip(
            "Set PAPER_FETCH_RUN_SUPPLEMENT_CLICK=1; shared browser state requires -n 0"
        )
    assert os.environ.get("PYTEST_XDIST_WORKER") is None, (
        "run live audit serially (-n 0)"
    )
    doi = DOI_OVERRIDES.get(provider, provider_benchmark_sample(provider).doi)
    root = Path(
        os.environ.get(
            "PAPER_FETCH_LIVE_ARTIFACT_DIR", ".paper-fetch-runs/supplement-click-live"
        )
    )
    output = root / provider
    output.mkdir(parents=True, exist_ok=False)
    env, isolation = build_isolated_live_env()
    env["PAPER_FETCH_BROWSER_HEADLESS"] = "true"
    # An explicitly selected existing legal session may be copied into the
    # isolated profile; attachment files and HTTP/artifact caches stay fresh.
    state_root = os.environ.get("PAPER_FETCH_LIVE_STORAGE_STATE_SOURCE")
    reused_state = False
    if state_root:
        source = Path(state_root) / f"{provider}-camoufox" / "storage-state.json"
        if source.is_file():
            target = (
                Path(env["XDG_DATA_HOME"])
                / "paper-fetch"
                / "publisher-browser-profiles"
                / f"{provider}-camoufox"
                / "storage-state.json"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o600)
            reused_state = True
    started = time.monotonic()
    report = {
        "provider": provider,
        "doi": doi,
        "success": False,
        "asset_profile": "all",
        "fresh_output": str(output.resolve()),
        "storage_state_reused": reused_state,
        "clicks": [],
        "files": [],
    }
    original = file_fetchers.fetch_file_with_page_click

    def capture(fetcher, url, asset):
        row = {
            "target_url": redact_url_for_cache(url),
            "filename_hint": asset.get("filename_hint"),
            "attachment_doi": asset.get("doi"),
            "source_href": redact_url_for_cache(str(asset.get("source_href") or "")),
        }
        report["clicks"].append(row)
        events = deque(maxlen=100)
        listeners = []

        def listen(owner, event, callback):
            owner.on(event, callback)
            listeners.append((owner, event, callback))

        def record_download(download):
            events.append(
                {"event": "download", "url": redact_url_for_diagnostics(download.url)}
            )

        def record_popup(popup):
            events.append(
                {"event": "popup", "url": redact_url_for_diagnostics(popup.url)}
            )
            listen(popup, "download", record_download)

        listen(
            fetcher._context,
            "request",
            lambda request: events.append(
                {
                    "event": "request",
                    "url": redact_url_for_diagnostics(request.url),
                }
            ),
        )
        listen(
            fetcher._context,
            "response",
            lambda response: events.append(
                {
                    "event": "response",
                    "url": redact_url_for_diagnostics(response.url),
                    "status": response.status,
                }
            ),
        )
        listen(fetcher._context, "page", record_popup)
        listen(fetcher._page, "download", record_download)
        for event in ("requestfinished", "requestfailed"):
            listen(
                fetcher._context,
                event,
                lambda request, event=event: events.append(
                    {
                        "event": event,
                        "url": redact_url_for_diagnostics(request.url),
                    }
                ),
            )
        try:
            response = original(fetcher, url, asset)
        finally:
            row["events"] = list(events)
            for owner, event, callback in reversed(listeners):
                owner.remove_listener(event, callback)
        row["failure"] = fetcher.failure_for(url)
        if response is None and provider == "ieee":
            with contextlib.suppress(Exception):
                row["media_controls"] = fetcher._page.locator(
                    "#media, xpl-document-media-list"
                ).evaluate_all(
                    """nodes => nodes.map(node => ({
                        tag: node.tagName.toLowerCase(), id: node.id,
                        text: node.innerText.slice(0, 4000),
                        controls: Array.from(node.querySelectorAll(
                            'a, button, [role="button"], .media-item, .media-file, span'
                        )).map(item => ({tag:item.tagName.toLowerCase(),
                            text:item.textContent.trim().slice(0, 300),
                            class:item.className,
                            visible:!!item.getClientRects().length})).slice(0, 80)
                    }))"""
                )
                row["controls"] = fetcher._page.locator("a, button").evaluate_all(
                    """nodes => nodes.filter(node =>
                        /media|supplement|download|\\.zip|\\.pdf/i.test(node.textContent)
                    ).map(node => ({
                        tag: node.tagName.toLowerCase(),
                        text: node.textContent.trim().slice(0, 250),
                        href: node.getAttribute('href') || '',
                        visible: !!node.getClientRects().length,
                        parents: Array.from((function* () {
                            let parent = node.parentElement;
                            for (let i=0; parent && i<5; i++, parent=parent.parentElement)
                                yield {tag:parent.tagName.toLowerCase(), id:parent.id,
                                       class:parent.className};
                        })())
                    }))"""
                )
                for control in row["controls"]:
                    control["href"] = redact_url_for_diagnostics(control["href"])
        if response is not None:
            body = bytes(response["body"])
            row.update(
                route=response.get("_paper_fetch_asset_route_diagnostics"),
                size=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                content_type=response["headers"].get("content-type"),
            )
        return response

    monkeypatch.setattr(file_fetchers, "fetch_file_with_page_click", capture)
    # Exercise browser assets even when AMS acquired its article over HTTP.
    monkeypatch.setattr(
        BrowserWorkflowClient, "_direct_http_asset_mode", lambda *_: False
    )
    try:
        report["static_browser_capabilities"] = static_browser_capabilities(
            env, provider=provider
        )
        with RuntimeContext(
            env=env,
            transport=HttpTransport(),
            download_dir=output,
            artifact_mode="all",
            asset_profile="all",
        ) as runtime:
            runtime.initialize_deadline(240)
            resolved = resolve_paper(doi, context=runtime)
            report["identity"] = resolved.to_dict()
            assert resolved.doi.lower() == doi.lower(), report["identity"]
            envelope = fetch_paper(
                doi,
                modes={"article"},
                context=runtime,
                strategy=FetchStrategy(
                    preferred_providers=[provider],
                    asset_profile="all",
                    allow_metadata_only_fallback=False,
                ),
            )
            report["acceptance"] = evaluate_fetch_acceptance(
                envelope, asset_profile="all", expected_doi=doi
            ).model_dump(mode="json")
            assert envelope.article is not None
            article = envelope.article
            report["source"] = article.source
            report["source_trail"] = list(article.quality.source_trail)
            report["asset_failures"] = list(article.quality.asset_failures)
            report["assets"] = [asdict(asset) for asset in article.assets]
            supplements = [
                asset for asset in article.assets if asset.kind == "supplementary"
            ]
            for asset in supplements:
                if not asset.path:
                    continue
                path = Path(asset.path)
                body = path.read_bytes()
                digest = hashlib.sha256(body).hexdigest()
                matches = [
                    row
                    for row in report["clicks"]
                    if row.get("sha256") == digest
                    and row.get("size") == len(body)
                    and row.get("route", {}).get("mode") == "page_click"
                ]
                assert matches, f"No fresh click evidence for {path}"
                assert len(body) == asset.downloaded_bytes > 0
                assert asset.content_type == matches[-1]["content_type"]
                record = {
                    "path": str(path.resolve()),
                    "size": len(body),
                    "sha256": digest,
                    "content_type": asset.content_type,
                    "click": matches[-1]["route"],
                }
                if provider == "science" and body.startswith(b"%PDF"):
                    import pymupdf

                    with pymupdf.open(stream=body, filetype="pdf") as document:
                        record["pages"] = len(document)
                report["files"].append(record)
            assert supplements and len(report["files"]) == len(supplements), (
                "No complete freshly downloaded supplementary assets"
            )
            assert not any(
                failure.get("kind") == "supplementary"
                for failure in article.quality.asset_failures
            ), "Supplementary acceptance failed"
            assert report["acceptance"]["asset"]["status"] == "complete", report[
                "acceptance"
            ]
            if provider == "science":
                assert any(record.get("pages") == 43 for record in report["files"]), (
                    "Expected Science 43-page supplement"
                )
            if provider == "science":
                previous = os.environ.get("PAPER_FETCH_SCIENCE_SUPPLEMENT_REFERENCE")
                if previous:
                    reference = Path(previous)
                    expected_sha = hashlib.sha256(reference.read_bytes()).hexdigest()
                    report["reference"] = {
                        "path": str(reference.resolve()),
                        "size": reference.stat().st_size,
                        "sha256": expected_sha,
                    }
                    assert any(
                        record["sha256"] == expected_sha for record in report["files"]
                    ), (
                        "Science supplement differs from the previous 43-page acquisition"
                    )
            report["success"] = True
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report["seconds"] = round(time.monotonic() - started, 3)
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
        )
        isolation.cleanup()
