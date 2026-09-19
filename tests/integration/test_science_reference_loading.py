"""Offline browser contract for the publisher's visible bibliography controls."""

import json
import os
from pathlib import Path

import pytest

from paper_fetch.providers._science_html import (
    prepare_browser_page,
    finalize_extraction,
)
from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR


@pytest.mark.browser
@pytest.mark.parametrize("loadable", [True, False, "paged"])
def test_science_loads_visible_reference_pages_or_reports_missing_targets(
    monkeypatch, loadable
):
    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, utils

    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    monkeypatch.setattr(
        utils,
        "installed_verstr",
        lambda: json.loads(version_file.read_text())["version"],
    )
    monkeypatch.setattr(utils, "get_path", lambda file: str(version_file.parent / file))
    first = "".join(
        f'<div class="biblioentry"><div class="citations" id="R{i}"><div class="citation-content">Study {i}</div></div></div>'
        for i in range(1, 11)
    )
    more = "".join(
        f'<div class="biblioentry"><div class="citations" id="R{i}"><div class="citation-content">Study {i}</div></div></div>'
        for i in range(11, 101)
    )
    control = (
        '<button onclick="loadReferences(this)">View all references</button>'
        if loadable
        else ""
    )
    script = (
        '<script>function loadReferences(button) { button.remove(); setTimeout(() => document.querySelector("#bibliography").insertAdjacentHTML("beforeend", '
        + json.dumps(more)
        + "), 50); }</script>"
    )
    if loadable == "paged":
        script = '<script>let nextReference = 11; function loadReferences(button) { for(let j=0;j<20 && nextReference<=100;j++,nextReference++) { let id = nextReference; document.querySelector("#bibliography").insertAdjacentHTML("beforeend", `<div class="biblioentry"><div class="citations" id="R${id}"><div class="citation-content">Study ${id}</div></div></div>`); } if(nextReference>100) button.remove(); }</script>'
    html = (
        '<p>Result <a role="doc-biblioref" href="#R55">55</a>.</p><section id="bibliography">'
        + first
        + control
        + "</section>"
        + script
    )
    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        context = browser.new_context()
        context.route(
            "**/*", lambda route: route.fulfill(body=html, content_type="text/html")
        )
        page = context.new_page()
        page.goto("https://www.science.org/doi/10.1126/example")
        preparation = prepare_browser_page(page, timeout_ms=10000 if loadable else 500)
        _, extraction = finalize_extraction(page.content(), page.url, "Result 55.", {})
        assert preparation["references_before"] == 10
        assert len(extraction["references"]) == (100 if loadable else 10)
        assert preparation["missing_reference_targets"] == ([] if loadable else ["R55"])
        assert bool(extraction.get("quality_flags")) is (not loadable)
        context.close()
