"""Opt-in serial publisher audit; only fresh accepted clicks count as success."""

import contextlib
import hashlib
import json
import os
import shutil
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path
from zipfile import ZipFile

import pytest

from paper_fetch.browser_preflight import static_browser_capabilities
from paper_fetch.http import HttpTransport
from paper_fetch.http.cache import redact_url_for_cache, redact_url_for_diagnostics
from paper_fetch.provider_catalog import provider_names
from paper_fetch.providers._registry import browser_asset_policy
from paper_fetch.providers.browser_workflow.client import BrowserWorkflowClient
from paper_fetch.providers.browser_workflow.fetchers import file as file_fetchers
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper, resolve_paper
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.live._runtime_env import build_isolated_live_env

# Baseline papers and the files declared by their publisher attachment controls.
SAMPLES = {
    "acs": ("10.1021/acsomega.4c03987", ["ao4c03987_si_001.pdf"]),
    "aip": ("10.1063/5.0129134", ["125205_1_epaps.zip"]),
    "ams": ("10.1175/jcli-d-23-0738.1", ["10.1175_JCLI-D-23-0738.s1.pdf"]),
    "annualreviews": (
        "10.1146/annurev-neuro-062111-150343",
        ["ne36_schiller_supmat.pdf", *(f"schiller_video{i}.mpg" for i in range(1, 5))],
    ),
    "elsevier": (
        "10.1016/j.ecolind.2024.112140",
        ["1-s2.0-S1470160X24005971-mmc1.docx"],
    ),
    "ieee": ("10.1109/RITA.2026.3668995", ["supp1-3668995.pdf"]),
    "iop": ("10.1088/1748-9326/ab7d02", ["ERL_15_5_054014_suppdata.pdf"]),
    "mdpi": ("10.3390/s23010001", ["sensors-2080372-supplementary.xlsx"]),
    "pnas": (
        "10.1073/pnas.2322622121",
        ["pnas.2322622121.sapp.pdf", "pnas.2322622121.sd01.xlsx"],
    ),
    "royalsocietypublishing": ("10.1098/rsos.150470", ["rsos150470supp1.pdf"]),
    "rsc": ("10.1039/d5gc03562g", ["d5gc03562g1_suppl.pdf"]),
    "science": ("10.1126/science.aei2575", ["science.aei2575_sm.pdf"]),
    "tandf": ("10.1080/15481603.2026.2667034", ["tgrs_a_2667034_sm1980.docx"]),
    "wiley": ("10.1111/gcb.16414", ["gcb16414-sup-0001-FigureS1.docx"]),
}


@pytest.mark.parametrize(
    "provider",
    sorted(
        name
        for name in provider_names()
        if browser_asset_policy(name).click_supplements
    ),
)
def test_live_supplement_click(provider, monkeypatch):
    if os.environ.get("PAPER_FETCH_RUN_SUPPLEMENT_CLICK") != "1":
        pytest.skip(
            "Set PAPER_FETCH_RUN_SUPPLEMENT_CLICK=1; shared browser state requires -n 0"
        )
    assert os.environ.get("PYTEST_XDIST_WORKER") is None, (
        "run live audit serially (-n 0)"
    )
    doi, expected_files = SAMPLES[provider]
    root = Path(
        os.environ.get(
            "PAPER_FETCH_LIVE_ARTIFACT_DIR", ".paper-fetch-runs/supplement-click-live"
        )
    )
    output = root / provider
    output.mkdir(parents=True, exist_ok=False)
    env, isolation = build_isolated_live_env()
    env["PAPER_FETCH_BROWSER_HEADLESS"] = "true"
    env.setdefault("PAPER_FETCH_BROWSER_TIMEOUT_MS", "600000")
    if provider == "elsevier":
        env["ELSEVIER_API_KEY"] = ""  # Exercise the ScienceDirect browser route.
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
                route=response.route_diagnostics,
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
            runtime.initialize_deadline(600)
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
            report["events"] = list(article.trace)
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
            names = []
            for record in report["files"]:
                path = Path(record["path"])
                if provider == "science":
                    assert record["size"] == 6221008 and record["pages"] == 60
                    assert (
                        record["sha256"]
                        == "a748d58ca85feffc32d3aab72e5479834642d7603d6676317330197c19dcbd50"
                    )
                    names.append(Path(record["click"]["original_href"]).name)
                elif provider == "mdpi":
                    with ZipFile(path) as archive:
                        names.extend(archive.namelist())
                elif provider == "pnas":
                    assert path.name == Path(record["click"]["original_href"]).name
                    if path.suffix == ".xlsx":
                        with ZipFile(path) as workbook:
                            assert "xl/workbook.xml" in workbook.namelist()
                    else:
                        assert path.read_bytes().startswith(b"%PDF-")
                    names.append(path.name)
                else:
                    names.append(path.name)
            assert sorted(names) == sorted(expected_files)
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
