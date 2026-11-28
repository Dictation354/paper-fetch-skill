"""Live publisher acceptance through the default production browser runtime."""

import json
import os
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

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
def test_scrapling_navigation_via_cli(tmp_path, provider, doi):
    output = Path(
        os.environ.get(
            "PAPER_FETCH_SCRAPLING_LIVE_OUTPUT", str(tmp_path / "acceptance")
        )
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
        "PAPER_FETCH_BROWSER_BINARY_PATH": "",
        "PAPER_FETCH_BROWSER_HEADLESS": "",
        "XDG_DATA_HOME": str(state),
        "PAPER_FETCH_BROWSER_TIMEOUT_MS": "120000",
    }
    for key in ("PAPER_FETCH_BROWSER_PROFILE_DIR", "PAPER_FETCH_BROWSER_USER_DATA_DIR"):
        env[key] = ""
    command = [
        sys.executable,
        "-m",
        "paper_fetch.cli",
        "fetch",
        "--query",
        doi,
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
        command.extend(["--format", "both"])
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
                "asset_profile": "body" if provider == "pnas" else "none",
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
    navigations = [
        record
        for node in nodes
        for record in node.get("navigations", [])
        if isinstance(record, dict)
    ]
    from tests.support.live_acceptance import (
        fetch_browser_diagnostics,
    )

    receipt = json.loads(result.stdout)
    route = receipt["acquisition"]["route"]
    report = {
        "doi": doi,
        "route": route,
        "fetch_wall_seconds": round(time.monotonic() - started_at, 3),
        **fetch_browser_diagnostics(output / "article", provider=provider, doi=doi),
        "exit_code": result.returncode,
        "navigations": navigations,
        "body_path": receipt.get("body_path"),
    }
    (output / "acceptance.json").write_text(json.dumps(report, indent=2))
    assert result.returncode == 0, f"CLI failed; evidence: {output}"
    assert route in (
        {"browser_html", "browser_pdf"} if provider == "elsevier" else {"browser_html"}
    )
    assert receipt["identity"]["doi"] == doi
    assert receipt["target_satisfied"] is True
    assert receipt["acceptance"]["has_fulltext"] is True
    assert Path(receipt["body_path"]).is_file()
    assert any(
        node.get("browser_backend") == "scrapling"
        and node.get("chromium_version")
        and node.get("headless") is True
        for node in nodes
    )
    if provider == "pnas":
        articles = [
            entry
            for entry in nodes
            if entry.get("source") == "pnas" and "sections" in entry
        ]
        assets = articles[0]["assets"]
        assert len(assets) == 4
        assert all(
            asset.get("path") and asset.get("download_tier") == "full_size"
            for asset in assets
        )
