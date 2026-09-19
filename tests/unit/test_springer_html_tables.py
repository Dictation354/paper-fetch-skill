from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from paper_fetch.providers import _springer_html as springer_html
from paper_fetch.providers import springer as springer_provider
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset
from tests.support._atypon_browser_workflow_provider_support import png_header


SPRINGER_CLASSIC_DOI = "10.1007/s10584-011-0143-4"
SPRINGER_CLASSIC_TITLE = "Hydrological response to climate change in a glacierized catchment in the Himalayas"
SPRINGER_CLASSIC_LANDING_URL = (
    f"https://link.springer.com/article/{SPRINGER_CLASSIC_DOI}"
)
SPRINGER_CLASSIC_TABLE_URL = f"{SPRINGER_CLASSIC_LANDING_URL}/tables/1"
SPRINGER_CLASSIC_ARTICLE_FIXTURE = golden_criteria_asset(
    SPRINGER_CLASSIC_DOI, "article.html"
)
SPRINGER_CLASSIC_TABLE_FIXTURE = golden_criteria_asset(
    SPRINGER_CLASSIC_DOI, "table1.html"
)

SPRINGER_NATURE_DOI = "10.1038/s43247-024-01295-w"
SPRINGER_NATURE_TITLE = "Hydrological drought forecasts using precipitation data depend on catchment properties and human activities"
SPRINGER_NATURE_LANDING_URL = f"https://www.nature.com/articles/{SPRINGER_NATURE_DOI}"
SPRINGER_NATURE_TABLE_URL = (
    "https://www.nature.com/articles/s43247-024-01295-w/tables/1"
)
SPRINGER_NATURE_ARTICLE_FIXTURE = golden_criteria_asset(
    SPRINGER_NATURE_DOI, "original.html"
)
SPRINGER_NATURE_TABLE_FIXTURE = golden_criteria_asset(
    SPRINGER_NATURE_DOI, "table1.html"
)
OLD_NATURE_DOI = "10.1038/nature13376"
OLD_NATURE_TITLE = "Contribution of semi-arid ecosystems to interannual variability of the global carbon cycle"
OLD_NATURE_LANDING_URL = "https://www.nature.com/articles/nature13376"
OLD_NATURE_ARTICLE_FIXTURE = golden_criteria_asset(OLD_NATURE_DOI, "original.html")
GENERIC_EXTENDED_TABLE_DOI = "10.1038/s41586-020-1941-5"
GENERIC_EXTENDED_TABLE_TITLE = "Forest age and water yield"
GENERIC_EXTENDED_TABLE_LANDING_URL = "https://www.nature.com/articles/s41586-020-1941-5"
GENERIC_EXTENDED_TABLE_URL = f"{GENERIC_EXTENDED_TABLE_LANDING_URL}/tables/1"
GENERIC_EXTENDED_TABLE_ESM_IMAGE_URL = (
    "https://media.springernature.com/lw850/springer-static/esm/"
    "art%3A10.1038%2Fs41586-020-1941-5/MediaObjects/"
    "41586_2020_1941_Tab1_ESM.jpg"
)
NATURE_HEADER_SVG_URL = (
    "https://media.springernature.com/full/nature-cms/uploads/product/nature/"
    "header-86f1267ea01eccd46b530284be10585e.svg"
)


class FakeTransport:
    def __init__(self, responses: dict[str, dict[str, object] | Exception]) -> None:
        self.responses = responses

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
        request_policy=None,
    ):
        del (
            headers,
            query,
            timeout,
            retry_on_rate_limit,
            rate_limit_retries,
            max_rate_limit_wait_seconds,
        )
        del (
            retry_on_transient,
            transient_retries,
            transient_backoff_base_seconds,
            request_policy,
        )
        key = str(url)
        if method != "GET":
            raise AssertionError(f"Unexpected method {method}")
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {key}")
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response


class SpringerHtmlTableTests(unittest.TestCase):
    def test_springer_download_related_assets_downloads_body_figure_and_rewrites_local_path(
        self,
    ) -> None:
        """asset-download-contract: provider=springer"""

        figure_url = (
            "https://media.springernature.com/full/springer-static/image/"
            "art%3A10.1038%2Fs43247-024-01295-w/MediaObjects/43247_2024_1295_Fig1_HTML.png"
        )
        image_body = png_header(640, 480)
        responses = {
            figure_url: {
                "headers": {"content-type": "image/png"},
                "body": image_body,
                "url": figure_url,
                "status_code": 200,
            }
        }
        transport = FakeTransport(responses)
        client = springer_provider.SpringerClient(transport=transport, env={})
        raw_payload = springer_provider.RawFulltextPayload(
            provider="springer",
            source_url=SPRINGER_NATURE_LANDING_URL,
            content_type="text/html",
            body=b"<html><body><article><p>Figure 1 summarizes the basin response.</p></article></body></html>",
            content=springer_provider.ProviderContent(
                route_kind="html",
                source_url=SPRINGER_NATURE_LANDING_URL,
                content_type="text/html",
                body=b"<html></html>",
                markdown_text=(
                    f"# {SPRINGER_NATURE_TITLE}\n\n"
                    "## Results\n\n"
                    "Figure 1 summarizes the basin response.\n\n"
                    f"![Figure 1]({figure_url})\n\n"
                    "**Figure 1.** Basin response."
                ),
                extracted_assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Basin response.",
                        "url": figure_url,
                        "section": "body",
                    }
                ],
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                SPRINGER_NATURE_DOI,
                {"doi": SPRINGER_NATURE_DOI, "title": SPRINGER_NATURE_TITLE},
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
            )
            saved_path = Path(result["assets"][0]["path"])
            saved_exists = saved_path.is_file()
            saved_bytes = saved_path.read_bytes()
            article = client.to_article_model(
                {"doi": SPRINGER_NATURE_DOI, "title": SPRINGER_NATURE_TITLE},
                raw_payload,
                downloaded_assets=result["assets"],
                asset_failures=result["asset_failures"],
            )
            rendered = article.to_ai_markdown(
                asset_profile="body", max_tokens="full_text"
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["kind"], "figure")
        self.assertEqual(result["assets"][0]["downloaded_bytes"], len(image_body))
        self.assertEqual(saved_bytes, image_body)
        self.assertTrue(saved_exists)
        self.assertIn(f"![Figure 1]({saved_path})", rendered)
        self.assertNotIn(figure_url, rendered)

    def test_supplementary_section_titles_derive_only_asset_scopes_from_back_matter(
        self,
    ) -> None:
        self.assertIn(
            "supplementary information",
            springer_html.SPRINGER_SUPPLEMENTARY_SECTION_TITLES,
        )
        self.assertIn(
            "extended data figures and tables",
            springer_html.SPRINGER_SUPPLEMENTARY_SECTION_TITLES,
        )
        self.assertNotIn(
            "references", springer_html.SPRINGER_SUPPLEMENTARY_SECTION_TITLES
        )
        self.assertNotIn(
            "acknowledgements",
            springer_html.SPRINGER_SUPPLEMENTARY_SECTION_TITLES,
        )

    def _article_with_inline_table(
        self, *, label: str, caption: str, table_href: str
    ) -> bytes:
        label_text = label.rstrip(".")
        body_text = (
            "Planting and removal of forest affect average streamflow, but there is ongoing debate "
            "about how this long-term difference between precipitation and evapotranspiration is "
            "modulated by forest age, local conditions, and record length across catchments."
        )
        return f"""
        <html>
          <head>
            <title>{GENERIC_EXTENDED_TABLE_TITLE}</title>
            <meta name="citation_title" content="{GENERIC_EXTENDED_TABLE_TITLE}" />
            <meta name="citation_doi" content="{GENERIC_EXTENDED_TABLE_DOI}" />
            <meta name="citation_author" content="Adriaan J. Teuling" />
          </head>
          <body>
            <article>
              <h1>{GENERIC_EXTENDED_TABLE_TITLE}</h1>
              <div class="c-article-body">
                <div class="main-content">
                  <div class="c-article-section__content"><p>{body_text}</p></div>
                  <section data-title="Extended data figures and tables">
                    <div class="c-article-section">
                      <h2 class="c-article-section__title">Extended data figures and tables</h2>
                      <div class="c-article-section__content">
                        <div class="c-article-table" data-test="inline-table" data-container-section="table">
                          <figure>
                            <figcaption class="c-article-table__figcaption">
                              <b data-test="table-caption">{label_text} {caption}</b>
                            </figcaption>
                            <a data-test="table-link" href="{table_href}">Full size table</a>
                          </figure>
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </article>
          </body>
        </html>
        """.encode()

    def _prepare_generic_extended_table_attempt(
        self, responses: dict[str, dict[str, object] | Exception]
    ):
        metadata = {
            "doi": GENERIC_EXTENDED_TABLE_DOI,
            "title": GENERIC_EXTENDED_TABLE_TITLE,
            "landing_page_url": GENERIC_EXTENDED_TABLE_LANDING_URL,
            "fulltext_links": [],
        }
        transport = FakeTransport(responses)
        client = springer_provider.SpringerClient(transport=transport, env={})
        return client._prepare_html_attempt(
            GENERIC_EXTENDED_TABLE_DOI,
            metadata,
            context=RuntimeContext(env={}, transport=transport),
        )

    def test_generic_extended_data_table_image_response_renders_table_asset(
        self,
    ) -> None:
        table_image_url = "https://media.springernature.com/full/table-1.png"
        responses = {
            GENERIC_EXTENDED_TABLE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": self._article_with_inline_table(
                    label="Extended Data Table 1",
                    caption="Observed water yield at long-term lysimeter stations",
                    table_href="/articles/s41586-020-1941-5/tables/1",
                ),
                "url": GENERIC_EXTENDED_TABLE_LANDING_URL,
                "status_code": 200,
            },
            GENERIC_EXTENDED_TABLE_URL: {
                "headers": {"content-type": "image/png"},
                "body": b"\x89PNG\r\n\x1a\ntable-image",
                "url": table_image_url,
                "status_code": 200,
            },
        }

        attempt = self._prepare_generic_extended_table_attempt(responses)

        self.assertIn(f"![Table 1]({table_image_url})", attempt.markdown_text)
        self.assertIn(
            "**Extended Data Table 1.** Observed water yield at long-term lysimeter stations",
            attempt.markdown_text,
        )
        self.assertEqual(len(attempt.inline_table_assets), 1)
        self.assertEqual(attempt.inline_table_assets[0].get("kind"), "table")
        self.assertEqual(
            attempt.inline_table_assets[0].get("heading"), "Extended Data Table 1"
        )
        self.assertEqual(attempt.inline_table_assets[0].get("url"), table_image_url)

    def test_generic_extended_data_table_html_image_fallback_renders_table_asset(
        self,
    ) -> None:
        table_image_url = "https://media.springernature.com/full/table-1-from-html.png"
        responses = {
            GENERIC_EXTENDED_TABLE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": self._article_with_inline_table(
                    label="Extended Data Table 1",
                    caption="Observed water yield at long-term lysimeter stations",
                    table_href="/articles/s41586-020-1941-5/tables/1",
                ),
                "url": GENERIC_EXTENDED_TABLE_LANDING_URL,
                "status_code": 200,
            },
            GENERIC_EXTENDED_TABLE_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": f"<html><head><meta property='og:image' content='{table_image_url}'></head><body></body></html>".encode(),
                "url": GENERIC_EXTENDED_TABLE_URL,
                "status_code": 200,
            },
        }

        attempt = self._prepare_generic_extended_table_attempt(responses)

        self.assertIn(f"![Table 1]({table_image_url})", attempt.markdown_text)
        self.assertEqual(len(attempt.inline_table_assets), 1)
        self.assertEqual(attempt.inline_table_assets[0].get("kind"), "table")
        self.assertEqual(
            attempt.inline_table_assets[0].get("caption"),
            "Observed water yield at long-term lysimeter stations",
        )

    def test_generic_extended_data_table_html_image_fallback_uses_body_esm_table_image(
        self,
    ) -> None:
        responses = {
            GENERIC_EXTENDED_TABLE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": self._article_with_inline_table(
                    label="Extended Data Table 1",
                    caption="Observed water yield at long-term lysimeter stations",
                    table_href="/articles/s41586-020-1941-5/tables/1",
                ),
                "url": GENERIC_EXTENDED_TABLE_LANDING_URL,
                "status_code": 200,
            },
            GENERIC_EXTENDED_TABLE_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": f"""
                <html><body>
                  <header>
                    <img src="{NATURE_HEADER_SVG_URL}" alt="Nature" />
                  </header>
                  <main id="content">
                    <div data-track-component="table">
                      <h1>Extended Data Table 1 Observed water yield</h1>
                      <div class="c-article-table-container">
                        <figure data-container-section="table">
                          <picture>
                            <source srcset="{GENERIC_EXTENDED_TABLE_ESM_IMAGE_URL}?as=webp" />
                            <img src="{GENERIC_EXTENDED_TABLE_ESM_IMAGE_URL}"
                                 alt="Extended Data Table 1" />
                          </picture>
                        </figure>
                      </div>
                    </div>
                  </main>
                </body></html>
                """.encode(),
                "url": GENERIC_EXTENDED_TABLE_URL,
                "status_code": 200,
            },
        }

        attempt = self._prepare_generic_extended_table_attempt(responses)

        self.assertIn(
            f"![Table 1]({GENERIC_EXTENDED_TABLE_ESM_IMAGE_URL})",
            attempt.markdown_text,
        )
        self.assertNotIn(
            "header-86f1267ea01eccd46b530284be10585e.svg",
            attempt.markdown_text,
        )
        self.assertEqual(len(attempt.inline_table_assets), 1)
        self.assertEqual(
            attempt.inline_table_assets[0].get("url"),
            GENERIC_EXTENDED_TABLE_ESM_IMAGE_URL,
        )

    def test_generic_extended_data_table_html_image_fallback_rejects_header_only_svg(
        self,
    ) -> None:
        responses = {
            GENERIC_EXTENDED_TABLE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": self._article_with_inline_table(
                    label="Extended Data Table 1",
                    caption="Observed water yield at long-term lysimeter stations",
                    table_href="/articles/s41586-020-1941-5/tables/1",
                ),
                "url": GENERIC_EXTENDED_TABLE_LANDING_URL,
                "status_code": 200,
            },
            GENERIC_EXTENDED_TABLE_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": f"""
                <html><body>
                  <header>
                    <img src="{NATURE_HEADER_SVG_URL}" alt="Nature" />
                  </header>
                  <main id="content">
                    <div data-track-component="table">
                      <h1>Extended Data Table 1 Observed water yield</h1>
                      <p>Image unavailable.</p>
                    </div>
                  </main>
                </body></html>
                """.encode(),
                "url": GENERIC_EXTENDED_TABLE_URL,
                "status_code": 200,
            },
        }

        attempt = self._prepare_generic_extended_table_attempt(responses)

        self.assertIn(
            "**Extended Data Table 1.** [Table body unavailable:",
            attempt.markdown_text,
        )
        self.assertNotIn(
            "header-86f1267ea01eccd46b530284be10585e.svg",
            attempt.markdown_text,
        )
        self.assertEqual(len(attempt.inline_table_assets), 1)
        self.assertEqual(
            attempt.inline_table_assets[0]["source_url"], GENERIC_EXTENDED_TABLE_URL
        )
        self.assertFalse(attempt.inline_table_assets[0].get("url"))

    def test_regular_table_does_not_use_image_asset_fallback(self) -> None:
        table_image_url = "https://media.springernature.com/full/table-1.png"
        responses = {
            GENERIC_EXTENDED_TABLE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": self._article_with_inline_table(
                    label="Table 1",
                    caption="Observed water yield at long-term lysimeter stations",
                    table_href="/articles/s41586-020-1941-5/tables/1",
                ).replace(b"Extended data figures and tables", b"Results"),
                "url": GENERIC_EXTENDED_TABLE_LANDING_URL,
                "status_code": 200,
            },
            GENERIC_EXTENDED_TABLE_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": f"<html><body><img src='{table_image_url}'></body></html>".encode(),
                "url": GENERIC_EXTENDED_TABLE_URL,
                "status_code": 200,
            },
        }

        attempt = self._prepare_generic_extended_table_attempt(responses)

        self.assertIn("**Table 1.** [Table body unavailable:", attempt.markdown_text)
        self.assertNotIn(f"![Table 1]({table_image_url})", attempt.markdown_text)
        self.assertEqual(attempt.inline_table_assets, [])


if __name__ == "__main__":
    unittest.main()


class SpringerOriginalFirstTests(unittest.TestCase):
    def test_original_first_and_figure_page_recovery_share_file_budget(self):
        from paper_fetch.asset_budget import AssetBudget
        from paper_fetch.providers import _springer_assets

        direct = "https://media.springernature.com/full/original.png"
        restored = "https://media.springernature.com/full/restored.png"
        preview = "https://media.springernature.com/preview.png"
        figure_page = SPRINGER_NATURE_LANDING_URL + "/figures/1"
        for scenario in (
            "direct",
            "failed",
            "missing",
            "preview",
            "cancelled",
            "duplicate",
        ):
            with (
                self.subTest(scenario=scenario),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                budget = AssetBudget(max_files=1)
                context = RuntimeContext(env={}, asset_budget=budget)
                calls = []

                def request(
                    _method,
                    url,
                    *,
                    calls=calls,
                    scenario=scenario,
                    budget=budget,
                    **kwargs,
                ):
                    calls.append(url)
                    if scenario == "cancelled":
                        budget.cancel()
                    if url == figure_page:
                        target = direct if scenario == "duplicate" else restored
                        return {
                            "url": url,
                            "body": f'<meta property="og:image" content="{target}">'.encode(),
                            "headers": {"content-type": "text/html"},
                            "status_code": 200,
                        }
                    failed = (url == direct and scenario != "direct") or (
                        url == restored and scenario == "preview"
                    )
                    return {
                        "url": url,
                        "body": b"<html>Access denied</html>"
                        if failed
                        else png_header(820, 640),
                        "headers": {
                            "content-type": "text/html" if failed else "image/png"
                        },
                        "status_code": 403 if failed else 200,
                    }

                transport = FakeTransport({})
                transport.request = request
                asset = {
                    "kind": "figure",
                    "heading": "Fig. 1",
                    "url": preview,
                    "preview_url": preview,
                    "figure_page_url": figure_page,
                }
                if scenario != "missing":
                    asset["full_size_url"] = direct
                result = _springer_assets.download_assets_for_springer(
                    transport,
                    article_id=SPRINGER_NATURE_DOI,
                    assets=[asset],
                    output_dir=Path(tmpdir),
                    user_agent="test",
                    asset_profile="body",
                    runtime_context=context,
                )
                if scenario == "cancelled":
                    self.assertNotIn(figure_page, calls)
                    self.assertFalse(result["assets"])
                    continue
                self.assertEqual(len(result["assets"]), 1)
                self.assertFalse(result["asset_failures"])
                downloaded = result["assets"][0]
                self.assertTrue(Path(downloaded["path"]).is_file())
                self.assertEqual(calls.count(direct), 0 if scenario == "missing" else 1)
                if scenario == "direct":
                    self.assertEqual(calls, [direct])
                else:
                    self.assertEqual(calls.count(figure_page), 1)
                self.assertEqual(
                    downloaded["download_tier"],
                    "preview" if scenario in {"preview", "duplicate"} else "full_size",
                )
                self.assertEqual(len(list(Path(tmpdir).rglob("*.png"))), 1)
                if scenario in {"preview", "duplicate"}:
                    self.assertIn(
                        "official_full_size_access_restricted",
                        downloaded.get("provenance", []),
                    )


# Reduced from the verified nature13006 /tables/2 satellite page: the displayed
# table number differs from the page number and the bitmap has a Figa_ESM name.
NATURE13006_URL = "https://www.nature.com/articles/nature13006"
NATURE13006_TABLE_IMAGE = (
    "https://media.springernature.com/lw403/springer-static/image/"
    "art%3A10.1038%2Fnature13006/MediaObjects/41586_2014_BFnature13006_Figa_ESM.jpg"
)
NATURE13006_TABLE_HTML = f"""
<html><head><title>Extended Data Table 1 Sensitivity | Nature</title></head><body>
<header><img src="{NATURE_HEADER_SVG_URL}"></header>
<main><header><h1>Extended Data Table 1 Sensitivity</h1>
<p class="c-article-satellite-subtitle">From: <a href="/articles/nature13006">Amazon forests</a></p></header>
<div class="c-article-table-container"><div class="c-article-table-image">
<img alt="" src="{NATURE13006_TABLE_IMAGE}"></div></div></main></body></html>
"""


def test_nature_legacy_table_image_requires_matching_page_and_article():
    from paper_fetch.providers._springer_assets import extract_springer_table_image_url

    url = NATURE13006_URL + "/tables/2"
    assert (
        extract_springer_table_image_url(
            NATURE13006_TABLE_HTML, url, label="Extended Data Table 1", table_url=url
        )
        == NATURE13006_TABLE_IMAGE
    )
    for html, final_url in [
        (
            NATURE13006_TABLE_HTML.replace(
                "Extended Data Table 1", "Extended Data Table 2"
            ),
            url,
        ),
        (NATURE13006_TABLE_HTML.replace("Extended Data Table 1", "Table 1"), url),
        (NATURE13006_TABLE_HTML.replace("%2Fnature13006", "%2Fnature13376"), url),
        (
            NATURE13006_TABLE_HTML.replace(
                'href="/articles/nature13006"', 'href="/articles/nature13376"'
            ),
            url,
        ),
        (
            NATURE13006_TABLE_HTML.replace(
                'class="c-article-table-container"', ""
            ).replace('class="c-article-table-image"', ""),
            url,
        ),
        (
            NATURE13006_TABLE_HTML.replace(
                NATURE13006_TABLE_IMAGE, NATURE_HEADER_SVG_URL
            ),
            url,
        ),
        (
            NATURE13006_TABLE_HTML.replace("<main>", "<aside>").replace(
                "</main>", "</aside>"
            ),
            url,
        ),
        (NATURE13006_TABLE_HTML, NATURE13006_URL + "/tables/3"),
        (NATURE13006_TABLE_HTML, url.replace("nature13006", "nature13376")),
    ]:
        assert (
            extract_springer_table_image_url(
                html, final_url, label="Extended Data Table 1", table_url=url
            )
            is None
        )


def test_nature_body_all_scope_downloads_and_missing_evidence(tmp_path):
    from paper_fetch.models import FetchEnvelope
    from paper_fetch.providers import _springer_assets
    from paper_fetch.quality.assets import build_asset_quality_summary
    from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance

    metadata = {
        "doi": "10.1038/nature13006",
        "title": GENERIC_EXTENDED_TABLE_TITLE,
        "landing_page_url": NATURE13006_URL,
    }
    article_html = (
        SpringerHtmlTableTests()
        ._article_with_inline_table(
            label="Extended Data Table 1",
            caption="Sensitivity",
            table_href=NATURE13006_URL + "/tables/2",
        )
        .decode()
        .replace(GENERIC_EXTENDED_TABLE_DOI, metadata["doi"])
    )
    body_table = """<h2>Results</h2><div class="c-article-table" data-test="inline-table"><figure>
        <figcaption><b data-test="table-caption">Table 1 Body results</b></figcaption>
        <a data-test="table-link" href="/articles/nature13006/tables/1">Full size table</a>
        </figure></div>"""
    extended_figure = """<div class="c-article-supplementary__item" id="Fig4">
        <h3 class="c-article-supplementary__title"><a href="/articles/nature13006/figures/4"
        data-supp-info-image="https://media.springernature.com/full/extended.png">Extended Data Figure 1 Forest</a></h3>
        <p>Extended figure caption. <a href="/articles/nature13006#Fig4">Extended Data Fig. 1</a></p></div>"""
    article_html = article_html.replace(
        '<section data-title="Extended data',
        body_table + '<section data-title="Extended data',
    )
    article_html = article_html.replace("</section>", extended_figure + "</section>")
    # The body fixture also proves ordinary tables retain their page fetch.
    for profile in ("body", "all", "none"):
        for missing in (False, True):
            out = tmp_path / f"{profile}-{missing}"
            out.mkdir()
            responses = {
                NATURE13006_URL: {
                    "body": article_html.encode(),
                    "url": NATURE13006_URL,
                    "headers": {"content-type": "text/html"},
                    "status_code": 200,
                },
                NATURE13006_URL + "/tables/1": {
                    "body": b"<html><figure><figcaption>Table 1 Body results</figcaption><table><tr><th>Metric</th><th>Value</th></tr><tr><td>Body</td><td>1</td></tr></table></figure></html>",
                    "url": NATURE13006_URL + "/tables/1",
                    "headers": {"content-type": "text/html"},
                    "status_code": 200,
                },
            }
            if profile == "all":
                responses[NATURE13006_URL + "/tables/2"] = {
                    "body": (
                        NATURE13006_TABLE_HTML.replace(
                            NATURE13006_TABLE_IMAGE, NATURE_HEADER_SVG_URL
                        )
                        if missing
                        else NATURE13006_TABLE_HTML
                    ).encode(),
                    "url": NATURE13006_URL + "/tables/2",
                    "headers": {"content-type": "text/html"},
                    "status_code": 200,
                }
                for url, fixture, mime in [
                    (
                        NATURE13006_TABLE_IMAGE,
                        golden_criteria_asset(
                            "10.1063/5.0129134", "body_assets/m_125205_1_f4.jpeg"
                        ),
                        "image/jpeg",
                    ),
                    (
                        "https://media.springernature.com/full/extended.png",
                        golden_criteria_asset(
                            "10.1371/journal.pone.0015338",
                            "body_assets/pone.0015338.e003.png",
                        ),
                        "image/png",
                    ),
                ]:
                    responses[url] = {
                        "body": fixture.read_bytes(),
                        "url": url,
                        "headers": {"content-type": mime},
                        "status_code": 200,
                    }
            transport = FakeTransport(responses)
            client = springer_provider.SpringerClient(transport=transport, env={})
            context = RuntimeContext(env={}, transport=transport, asset_profile=profile)
            payload = client.fetch_raw_fulltext(
                metadata["doi"], metadata, context=context
            )
            assert "Body" in payload.content.markdown_text
            assets = payload.content.extracted_assets
            result = client.download_related_assets(
                metadata["doi"],
                metadata,
                payload,
                out,
                asset_profile=profile,
                context=context,
            )
            if profile != "all":
                assert not assets
                assert not result["assets"] and not result["asset_failures"]
                assert "Table body unavailable" not in payload.content.markdown_text
                assert not payload.warnings
                continue
            assert len(assets) == 2
            assert {a["kind"] for a in assets} == {"figure", "table"}
            assert all(a["section"] == "supplementary" for a in assets)
            assert len(result["assets"]) == (1 if missing else 2)
            assert len(result["asset_failures"]) == int(missing)
            if missing:
                assert (
                    result["asset_failures"][0]["source_url"]
                    == NATURE13006_URL + "/tables/2"
                )
            article = client.to_article_model(
                metadata,
                payload,
                downloaded_assets=result["assets"],
                asset_failures=result["asset_failures"],
                context=context,
            )
            summary = build_asset_quality_summary(
                article.assets,
                asset_failures=result["asset_failures"],
                asset_profile=profile,
                archive_enabled=True,
            )
            assert summary.failed == int(missing)
            article.quality.asset_summary = summary
            acceptance = evaluate_fetch_acceptance(
                FetchEnvelope(
                    doi=metadata["doi"],
                    source=article.source,
                    has_fulltext=True,
                    content_kind="fulltext",
                    has_abstract=True,
                    article=article,
                    quality=article.quality,
                    trace=payload.trace,
                    markdown=article.to_ai_markdown(max_tokens="full_text"),
                ),
                asset_profile=profile,
                requested_outputs=["article", "markdown"],
                expected_doi=metadata["doi"],
            )
            assert acceptance.asset.failed == int(missing)
            assert acceptance.asset.status == ("degraded" if missing else "complete")
            if missing:
                assert acceptance.overall == "degraded"
            if not missing:
                rendered = article.to_ai_markdown(max_tokens="full_text")
                table_asset = next(a for a in result["assets"] if a["kind"] == "table")
                assert Path(table_asset["path"]).is_file()
                assert table_asset["path"] in rendered
            assert all(
                "Extended Data" not in asset.get("heading", "")
                for asset in _springer_assets.extract_html_assets(
                    article_html, NATURE13006_URL, asset_profile="body"
                )
            )
