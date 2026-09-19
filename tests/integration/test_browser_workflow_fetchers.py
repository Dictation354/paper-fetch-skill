from __future__ import annotations
import pytest
from unittest import mock
from paper_fetch.providers.browser_workflow.fetchers import context as fetcher_context
from paper_fetch.providers.browser_workflow.fetchers import file as file_fetchers
from paper_fetch.providers.browser_workflow.fetchers import image as image_fetchers


TEST_CDP_ENDPOINT = "ws://127.0.0.1:9222/devtools/browser/test"


@pytest.mark.browser
def test_wiley_picture_uses_loaded_target_at_both_viewports(monkeypatch):
    import json
    import os
    from pathlib import Path

    from paper_fetch.extraction.image_payloads import image_dimensions_from_bytes
    from paper_fetch.providers.browser_workflow.fetchers.scripts import (
        _ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT,
        _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
    )
    from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR

    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, utils

    # Pytest isolates the managed cache; read the existing executable's version
    # without asking Camoufox to discover or install a runtime in that cache.
    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    version = json.loads(version_file.read_text())["version"]
    monkeypatch.setattr(utils, "installed_verstr", lambda: version)
    # Camoufox also locates fontconfig through its managed cache, even with an
    # explicit executable. Use that executable's bundle for this offline test.
    monkeypatch.setattr(utils, "get_path", lambda file: str(version_file.parent / file))

    fixtures = Path(__file__).parents[1] / "fixtures" / "golden_criteria"
    full = (
        fixtures / "10.1371_journal.pone.0015338/body_assets/pone.0015338.g002.png"
    ).read_bytes()
    preview = (
        fixtures / "10.1063_5.0129134/body_assets/m_125205_1_f4.jpeg"
    ).read_bytes()
    target = "https://example.test/full.png"
    html = '<picture><source media="(min-width: 1600px)" srcset="/full.png"><img id="target" src="/preview.jpg"></picture>'
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {}, seed_urls_getter=lambda: []
    )
    fake = mock.Mock()
    fake.evaluate.return_value = {"ready": True}
    fetcher._wait_for_primary_image(fake, target, require_target_match=True)
    readiness_script = fake.evaluate.call_args.args[0]

    def route_asset(route):
        url = route.request.url
        if url.endswith("/article"):
            route.fulfill(body=html, content_type="text/html")
        else:
            route.fulfill(
                body=full if url == target else preview,
                content_type="image/png" if url == target else "image/jpeg",
            )

    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        for width in (1280, 1920):
            context = browser.new_context(viewport={"width": width, "height": 1080})
            context.route("https://example.test/**", route_asset)
            page = context.new_page()
            page.goto("https://example.test/article")
            page.locator("#target").evaluate("(image) => image.decode()")
            expected_src = (
                target if width == 1920 else "https://example.test/preview.jpg"
            )
            assert (
                page.locator("#target").evaluate("(image) => image.currentSrc")
                == expected_src
            )
            fetcher._page = page
            fetcher._context = context
            with mock.patch.object(
                page,
                "wait_for_timeout",
                side_effect=AssertionError("unexpected image wait"),
            ):
                warmed = fetcher._payload_from_warmed_article_image(
                    page, target, require_target_match=True
                )
                assert (warmed is not None) == (width == 1920)
                payload = fetcher._fetch_with_page(target, require_target_match=True)
            assert payload["url"] == target
            assert image_dimensions_from_bytes(payload["body"]) == (2068, 470)
            # A target declared only in picture sources is also rejected by
            # post-navigation readiness and the loaded-image canvas script.
            page.goto("https://example.test/article")
            page.locator("#target").evaluate("(image) => image.decode()")
            for script in (
                _ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT,
                _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
            ):
                result = page.evaluate(script, [target, 80, 80, False, True])
                assert bool(result.get("ok")) == (width == 1920)
            ready = page.evaluate(readiness_script, [80, 80, target, False, True])
            assert ready["ready"] == (width == 1920)
            if width == 1920:
                page.evaluate("""async () => {
                    const other = new Image(); other.src = '/other.jpg';
                    document.body.append(other); await other.decode();
                }""")
                for mode in (
                    "incomplete",
                    "zero_width",
                    "zero_height",
                    "tiny",
                    "empty",
                    "missing",
                ):
                    page.locator("#target").evaluate(
                        """(image, mode) => {
                        for (const key of ['complete', 'naturalWidth', 'naturalHeight']) delete image[key];
                        const changes = {incomplete: ['complete', false], zero_width: ['naturalWidth', 0],
                            zero_height: ['naturalHeight', 0], tiny: ['naturalWidth', 22]};
                        if (changes[mode]) Object.defineProperty(image, changes[mode][0],
                            {value: changes[mode][1], configurable: true});
                        if (mode === 'missing') image.remove();
                    }""",
                        mode,
                    )
                    candidate = "" if mode == "empty" else target
                    for script in (
                        _ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT,
                        _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
                    ):
                        result = page.evaluate(script, [candidate, 80, 80, False, True])
                        assert not result.get("ok"), (mode, result)
                    ready = page.evaluate(
                        readiness_script, [80, 80, candidate, False, True]
                    )
                    assert not ready["ready"], (mode, ready)
            context.close()


@pytest.mark.browser
@pytest.mark.parametrize(
    "ignored_click, reclose_after_visible",
    [(False, False), (True, False), (False, True)],
)
def test_wiley_click_survives_collapsed_panel_redraw_in_browser(
    monkeypatch, ignored_click, reclose_after_visible
):
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace

    from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR

    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, pkgman, utils

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
    # Font/config resources must use the preserved runtime too, not the
    # isolated empty cache where Camoufox would try an online installation.
    monkeypatch.setattr(pkgman, "camoufox_path", lambda: version_file.parent)
    article_url = "https://example.test/article"
    file_url = "https://example.test/supplement.docx"
    body = b"PK\x03\x04real-browser-supplement"
    html = (
        """<section class="article-section__content"><h2>Results</h2><p>"""
        + "Article body. " * 120
        + """</p><p>Second paragraph.</p></section>
    <section class="article-section__supporting"><div class="accordion">
      <a class="accordion__control" aria-expanded="false" onclick="this.parentElement.innerHTML='<a href=/supplement.docx download>Supporting file</a>'">Supporting Information</a>
      <div hidden><a href="/supplement.docx" download>Supporting file</a></div>
    </div></section>"""
    )
    if ignored_click:
        # The initial control is replaced before its delayed handler is ready.
        html = html.replace(
            'onclick="this.parentElement.innerHTML=',
            "onclick=\"if (!this.dataset.ready) { const replacement = this.cloneNode(true); this.replaceWith(replacement); setTimeout(() => replacement.dataset.ready = 'true', 200); return; } this.parentElement.innerHTML=",
        )
    reclosed = []
    if reclose_after_visible:
        from playwright.sync_api import Locator

        original_wait_for = Locator.wait_for

        def wait_then_reclose(locator, **kwargs):
            result = original_wait_for(locator, **kwargs)
            if kwargs.get("state") == "visible":
                # Reproduce the live page hiding the panel after visibility
                # succeeds but before the download action starts.
                locator.evaluate(
                    "(anchor) => anchor.closest('.accordion').style.display = 'none'"
                )
                reclosed.append(not locator.is_visible())
            return result

        monkeypatch.setattr(Locator, "wait_for", wait_then_reclose)
    requests = []
    finished = []

    def route_asset(route):
        requests.append(route.request.url)
        if route.request.url == article_url:
            route.fulfill(body=html, content_type="text/html")
        else:
            route.fulfill(
                body=body,
                content_type="application/octet-stream",
                headers={
                    "Content-Disposition": 'attachment; filename="supplement.docx"'
                },
            )

    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        context = browser.new_context()
        context.route("https://example.test/**", route_asset)
        page = context.new_page()
        page.on("requestfinished", lambda request: finished.append(request.url))
        page.goto(article_url)
        fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
            browser_context_seed_getter=lambda: {"browser_final_url": article_url},
            seed_urls_getter=lambda: [article_url],
            browser_options=fetcher_context.BrowserDocumentFetcherOptions(
                runtime_config=SimpleNamespace(provider="wiley")
            ),
        )
        fetcher._page = page
        fetcher._context = context
        result = fetcher(file_url, {"kind": "supplementary"})
        assert result is not None, fetcher.failure_for(file_url)
        assert result["body"] == body
        assert result["status_code"] == 200
        assert (
            result["headers"]["content-disposition"]
            == 'attachment; filename="supplement.docx"'
        )
        assert requests.count(file_url) == 1
        assert file_url in finished, "download request does not emit requestfinished"
        assert reclosed == ([True] if reclose_after_visible else [])
        context.close()
