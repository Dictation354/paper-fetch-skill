"""Serial acceptance through the production CLI, requiring an observed challenge."""

import json
from contextlib import suppress
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

pytestmark = [pytest.mark.live, pytest.mark.browser]


def _walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


@pytest.mark.skipif(
    os.environ.get("PAPER_FETCH_RUN_LIVE") != "1",
    reason="explicit live acceptance only",
)
@pytest.mark.parametrize(
    "provider,doi",
    [("pnas", "10.1073/pnas.2406303121"), ("elsevier", "10.1016/j.rse.2025.114648")],
)
def test_byparr_navigation_via_cli(tmp_path, provider, doi):
    expected_source = "pnas" if provider == "pnas" else "elsevier_html"
    output = Path(
        os.environ.get("PAPER_FETCH_BYPARR_LIVE_OUTPUT", str(tmp_path / "acceptance"))
    )
    output = output / provider
    output.mkdir(parents=True, exist_ok=False)
    state = output / "fresh-state"
    state.mkdir()
    config = output / "empty.env"
    config.write_text('ELSEVIER_API_KEY=""\n')
    env = {
        **os.environ,
        "PAPER_FETCH_ENV_FILE": str(config),
        "ELSEVIER_API_KEY": "",
        "PAPER_FETCH_CHROME_BINARY_PATH": "",
        "XDG_DATA_HOME": str(state),
        f"PAPER_FETCH_{provider.upper()}_BROWSER_BACKEND": "byparr",
        "PAPER_FETCH_BROWSER_TIMEOUT_MS": "180000",
    }
    from tests._environment import (
        PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR,
        PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR,
    )

    for key in ("PAPER_FETCH_BROWSER_PROFILE_DIR", "PAPER_FETCH_BROWSER_USER_DATA_DIR"):
        env.pop(key, None)
    from paper_fetch.providers.browser_runtime.byparr_engine import engine_name

    if env.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR) and engine_name() == "camoufox":
        env["PAPER_FETCH_BROWSER_BINARY_PATH"] = env[
            PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR
        ]
    if env.get(PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR):
        env["XDG_CACHE_HOME"] = env[PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR]
    command = [
        sys.executable,
        "-m",
        "paper_fetch.cli",
        "fetch",
        "--query",
        doi,
        "--format",
        "json",
        "--save-markdown",
        "--output-dir",
        str(output / "article"),
        "--artifact-mode",
        "all",
        "--asset-profile",
        "body" if provider == "pnas" else "none",
        "--manifest",
        str(output / "manifest.json"),
        "--progress",
        "jsonl",
    ]
    if provider == "pnas":
        command.extend(
            ["--require-local-body-assets", "--require-full-size-body-assets"]
        )
    # The single-fetch CLI does not use the MCP result cache. A new subprocess,
    # empty output directory and fresh provider state force actual acquisition.
    (output / "request.json").write_text(
        json.dumps(
            {
                "command": command,
                "doi": doi,
                "elsevier_api": False,
                "result_cache": False,
                "asset_profile": "none",
                "fresh_state": str(state),
            },
            indent=2,
        )
    )
    started_at = time.monotonic()
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=300
    )
    (output / "stdout.log").write_text(result.stdout)
    (output / "stderr.log").write_text(result.stderr)
    payloads = []
    for path in output.rglob("*.json"):
        with suppress(OSError, ValueError):
            payloads.append(json.loads(path.read_text()))
    nodes = [node for payload in payloads for node in _walk(payload)]
    navigations = [node for node in nodes if "documents" in node and "events" in node]
    events = [
        event.get("message", "") for node in navigations for event in node["events"]
    ]
    from tests.support.live_acceptance import (
        fetch_browser_diagnostics,
        _asset_performance_summary,
    )
    from paper_fetch.models.codec import article_from_payload

    articles = [
        payload
        for payload in payloads
        if isinstance(payload, dict)
        and payload.get("source") == expected_source
        and "sections" in payload
    ]
    article = article_from_payload(articles[0]) if articles else None
    report = {
        "doi": doi,
        "preflight": None,
        "preflight_seconds": 0,
        "fetch_wall_seconds": round(time.monotonic() - started_at, 3),
        **fetch_browser_diagnostics(output / "article", provider=provider, doi=doi),
        "assets": _asset_performance_summary(article) if article else None,
        "exit_code": result.returncode,
        "challenge_observed": any(
            event.get("kind") == "challenge_detected"
            for node in navigations
            for event in node["events"]
        ),
        "checkbox_clicked": any(
            (
                "Checkbox clicked successfully" in event
                or "Clicked the challenge checkbox (attempt " in event
            )
            for event in events
        ),
        "documents": [doc for node in navigations for doc in node["documents"]],
        "byparr_events": events,
        "source_html": any(node.get("source") == expected_source for node in nodes),
        "route_browser_html": any(
            node.get("route") == "browser_html"
            or node.get("route_id") == "browser_html"
            for node in nodes
        ),
        "backend_byparr": any(
            node.get("browser_backend") == "byparr" for node in nodes
        ),
        "content_fulltext": any(
            isinstance(node.get("content"), dict)
            and node["content"].get("status") == "fulltext"
            for node in nodes
        ),
        "doi_matches": any(
            node.get("doi") == doi and node.get("source") == expected_source
            for node in nodes
        ),
        "markdown_written": any((output / "article").rglob("*.md")),
    }
    (output / "acceptance.json").write_text(json.dumps(report, indent=2))
    assert result.returncode == 0, f"CLI failed; evidence: {output}"
    assert (
        report["source_html"]
        and report["route_browser_html"]
        and report["backend_byparr"]
    ), report
    assert (
        report["doi_matches"]
        and report["content_fulltext"]
        and report["markdown_written"]
    ), report
    if provider == "pnas":
        assert article is not None
        assert len(article.assets) == 4
        assert all(
            asset.path and asset.download_tier == "full_size"
            for asset in article.assets
        )
    assert any(
        doc.get("status") == 200
        and (
            "sciencedirect.com/science/article/"
            if provider == "elsevier"
            else "pnas.org/doi/"
        )
        in doc.get("url", "")
        for doc in report["documents"]
    ), report
    report["challenge_click_recovery"] = bool(
        report["challenge_observed"]
        and report["checkbox_clicked"]
        and any(doc.get("status") == 200 for doc in report["documents"])
    )
    (output / "acceptance.json").write_text(json.dumps(report, indent=2))
