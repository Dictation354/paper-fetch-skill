from __future__ import annotations
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from paper_fetch import artifacts as paper_fetch_artifacts
from paper_fetch import service as paper_fetch
from paper_fetch.arxiv_id import canonical_arxiv_html_url, canonical_arxiv_pdf_url
from paper_fetch.extraction.html.assets.dom import preview_dimensions_are_acceptable
from paper_fetch.providers import (
    _arxiv_assets,
    _arxiv_atom,
    _arxiv_authors,
    _arxiv_html,
    _arxiv_references,
)
from paper_fetch.providers.arxiv import ArxivClient
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.resolve.query import resolve_query
from tests.golden_criteria import (
    golden_criteria_asset,
)
from tests.support._paper_fetch_support import (
    RecordingTransport,
    http_response,
)


PDF_FALLBACK_IDS = ("2006.11239v2", "1406.2661v1")
HTML_ROUTE_IDS = (
    "2605.06556v1",
    "2605.06598v1",
    "2605.06653v1",
    "2605.06659v1",
    "2605.06663v1",
    "2605.06665v1",
    "2605.06666v1",
    "2605.06667v1",
)
MARKDOWN_REVIEWED_FIXTURES = {
    "structure": "10.48550_arxiv.2605.06663v1",
    "table": "10.48550_arxiv.2605.06663v1",
    "formula": "10.48550_arxiv.2605.06653v1",
    "figure": "10.48550_arxiv.2605.06667v1",
    "references": "10.48550_arxiv.2605.06663v1",
    "pdf_fallback": "10.48550_arxiv.1406.2661v1",
}
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?"
    b"\x00\x05\xfe\x02\xfeA\xe2%\xb8\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _doi(arxiv_id: str) -> str:
    return f"10.48550/arxiv.{arxiv_id}"


def _source_tar(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def _atom_feed(arxiv_id: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}</id>
    <updated>2026-05-12T10:00:00Z</updated>
    <published>2026-05-11T09:00:00Z</published>
    <title>Internal Atom Title</title>
    <summary>Atom abstract with
      line breaks.</summary>
    <author><name>First Author</name></author>
    <author><name>Second Author</name></author>
    <arxiv:comment>12 pages</arxiv:comment>
    <arxiv:journal_ref>Example Journal 1</arxiv:journal_ref>
    <arxiv:doi>10.1234/example</arxiv:doi>
    <arxiv:primary_category term="cs.CL" />
    <category term="cs.CL" />
    <category term="cs.AI" />
    <link href="https://arxiv.org/abs/{arxiv_id}" rel="alternate" type="text/html" />
    <link title="pdf" href="https://arxiv.org/pdf/{arxiv_id}" rel="related" type="application/pdf" />
  </entry>
</feed>
""".encode()


# Official arXiv page fragments retrieved 2026-09-08; retained DOM and full
# ancillary lists (not the source archives or the 103 binary attachments).
ARXIV_ANCILLARY_PAGES = {
    arxiv_id: tuple(
        golden_criteria_asset(_doi(arxiv_id), name).read_text(encoding="utf-8")
        for name in ("abstract-excerpt.html", "ancillary-excerpt.html")
    )
    for arxiv_id in ("0811.2625v2",)
}


class ArxivProviderTests(unittest.TestCase):
    def test_fetch_metadata_uses_internal_atom_api_client(self) -> None:
        arxiv_id = "2605.06663v1"
        transport = RecordingTransport(
            {
                ("GET", _arxiv_atom.ARXIV_API_URL): http_response(
                    _arxiv_atom.ARXIV_API_URL,
                    _atom_feed(arxiv_id),
                    "application/atom+xml",
                )
            }
        )
        client = ArxivClient(transport, {})

        metadata = client.fetch_metadata({"arxiv_id": arxiv_id})

        self.assertEqual(metadata["provider"], "arxiv")
        self.assertEqual(metadata["doi"], _doi(arxiv_id))
        self.assertEqual(metadata["external_doi"], "10.1234/example")
        self.assertEqual(metadata["title"], "Internal Atom Title")
        self.assertEqual(metadata["authors"], ["First Author", "Second Author"])
        self.assertEqual(metadata["abstract"], "Atom abstract with line breaks.")
        self.assertEqual(metadata["published"], "2026-05-11")
        self.assertEqual(metadata["updated"], "2026-05-12")
        self.assertEqual(metadata["primary_category"], "cs.CL")
        self.assertEqual(metadata["categories"], ["cs.CL", "cs.AI"])
        self.assertEqual(metadata["pdf_url"], canonical_arxiv_pdf_url(arxiv_id))
        self.assertEqual(
            transport.calls[0]["query"],
            {"id_list": arxiv_id, "max_results": "1"},
        )
        self.assertEqual(
            transport.calls[0]["headers"]["Accept"], _arxiv_atom.ARXIV_API_ACCEPT
        )
        self.assertEqual(
            transport.calls[0]["timeout"], _arxiv_atom.ARXIV_API_TIMEOUT_SECONDS
        )
        self.assertTrue(transport.calls[0]["retry_on_transient"])
        self.assertEqual(
            transport.calls[0]["transient_retries"], _arxiv_atom.ARXIV_API_NUM_RETRIES
        )
        self.assertIn("User-Agent", transport.calls[0]["headers"])

    def test_probe_status_reports_atom_client_timeout_and_retries(self) -> None:
        client = ArxivClient(RecordingTransport({}), {})

        status = client.probe_status()
        metadata_check = next(
            check for check in status.checks if check.name == "metadata_api"
        )

        self.assertEqual(
            metadata_check.details["client_timeout_seconds"],
            _arxiv_atom.ARXIV_API_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            metadata_check.details["client_num_retries"],
            _arxiv_atom.ARXIV_API_NUM_RETRIES,
        )

    def test_fetch_metadata_reports_no_result_for_empty_atom_feed(self) -> None:
        arxiv_id = "2605.06663v1"
        transport = RecordingTransport(
            {
                ("GET", _arxiv_atom.ARXIV_API_URL): http_response(
                    _arxiv_atom.ARXIV_API_URL,
                    b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>',
                    "application/atom+xml",
                )
            }
        )
        client = ArxivClient(transport, {})

        with self.assertRaises(ProviderFailure) as caught:
            client.fetch_metadata({"arxiv_id": arxiv_id})

        self.assertEqual(caught.exception.code, "no_result")
        self.assertIn(arxiv_id, caught.exception.message)

    def test_resolve_query_recognizes_arxiv_urls_ids_and_dois_without_network(
        self,
    ) -> None:
        cases = {
            "https://arxiv.org/abs/2605.06663v1": ("url", "2605.06663v1"),
            "https://arxiv.org/html/2605.06663v1": ("url", "2605.06663v1"),
            "https://arxiv.org/pdf/2605.06663v1": ("url", "2605.06663v1"),
            "arXiv:2605.06663v1": ("arxiv_id", "2605.06663v1"),
            "2605.06663": ("arxiv_id", "2605.06663"),
            "10.48550/arXiv.2605.06663v1": ("doi", "2605.06663v1"),
        }

        for query, (kind, arxiv_id) in cases.items():
            with self.subTest(query=query):
                resolved = resolve_query(query, env={})
                self.assertEqual(resolved.query_kind, kind)
                self.assertEqual(resolved.doi, _doi(arxiv_id))
                self.assertEqual(
                    resolved.landing_url, f"https://arxiv.org/abs/{arxiv_id}"
                )
                self.assertEqual(resolved.provider_hint, "arxiv")
                self.assertEqual(resolved.confidence, 1.0)

    def test_arxiv_ar5iv_chrome_selectors_share_base_script_style_rules(self) -> None:
        self.assertEqual(_arxiv_html._ARXIV_BASE_CHROME_SELECTORS, ("script", "style"))
        for key in ("frontmatter_noise", "reference_noise", "article_chrome"):
            with self.subTest(key=key):
                selectors = _arxiv_html._ARXIV_AR5IV_SELECTORS[key]
                self.assertEqual(
                    selectors[:2], _arxiv_html._ARXIV_BASE_CHROME_SELECTORS
                )

    def test_author_boundary_splits_affiliations_without_rejecting_country_name_authors(
        self,
    ) -> None:
        soup = _arxiv_html.BeautifulSoup(
            """
            <article>
              <span class="ltx_personname">Anatole France</span>
              <span class="ltx_personname">Ada Lovelace<br><span>Department of Computing, Example University, Russia</span></span>
              <span class="ltx_personname">Grace Hopper<br><span>Centro de Matematica, Lisbon, Portugal</span></span>
            </article>
            """,
            "html.parser",
        )
        names = soup.select(".ltx_personname")

        self.assertTrue(_arxiv_authors._looks_like_arxiv_author_name("Anatole France"))
        candidate = _arxiv_authors._candidate_arxiv_author_text_from_person_node(
            names[1]
        )
        self.assertNotIn("Department", candidate)
        self.assertEqual(
            _arxiv_authors._split_arxiv_author_text(candidate), ["Ada Lovelace"]
        )
        data_file_candidate = (
            _arxiv_authors._candidate_arxiv_author_text_from_person_node(names[2])
        )
        self.assertNotIn("Portugal", data_file_candidate)
        self.assertEqual(
            _arxiv_authors._split_arxiv_author_text(data_file_candidate),
            ["Grace Hopper"],
        )
        self.assertEqual(
            _arxiv_authors._trim_arxiv_author_text_at_boundary(
                "Katherine Johnson, 10115 Berlin"
            ),
            "Katherine Johnson",
        )

    def test_author_boundary_resource_loading_fails_closed(self) -> None:
        self.assertIn(
            "Portugal",
            _arxiv_authors._load_arxiv_author_boundary_tokens(
                "country_boundary_patterns"
            ),
        )
        self.assertEqual(
            _arxiv_authors._load_arxiv_author_boundary_tokens(
                "country_boundary_patterns", resource_name="missing.json"
            ),
            (),
        )
        empty_country_pattern = (
            _arxiv_authors._compile_arxiv_author_country_boundary_pattern(())
        )
        self.assertIsNone(empty_country_pattern.search("Ada Lovelace, Portugal"))

    def test_html_route_sanitizes_nested_tex_dollars_in_latexml_annotations(
        self,
    ) -> None:
        soup = _arxiv_html.BeautifulSoup(
            r"""
<math class="ltx_Math" alttext="P(A(1,x,y)\text{ is a quota violation for $x&gt;x_{\tau}$})">
  <semantics>
    <mrow><mi>P</mi></mrow>
    <annotation encoding="application/x-tex">P(A(1,x,y)\text{ is a quota violation for $x&gt;x_{\tau}$})</annotation>
  </semantics>
</math>
""",
            "html.parser",
        )

        markdown = _arxiv_authors._arxiv_math_markdown(soup.math)

        self.assertEqual(markdown.count("$"), 2)
        self.assertNotIn(r"for $x>x_{\tau}$", markdown)
        self.assertIn(r"x>x_{\tau}", markdown)
        self.assertTrue(markdown.startswith("$P(A(1,x,y)"))

    def test_arxiv_complex_table_falls_back_to_key_value_without_semantic_loss(
        self,
    ) -> None:
        soup = _arxiv_html.BeautifulSoup(
            """
            <figure class="ltx_table" id="S1.T9">
              <figcaption><span class="ltx_tag ltx_tag_table">Table 9. </span>Grouped scores.</figcaption>
              <table class="ltx_tabular">
                <tr><th>Group</th><th>Metric</th><th>Score</th></tr>
                <tr><td>A</td><td>Loss</td><td>0.1</td></tr>
                <tr><td>B</td><td>Accuracy</td></tr>
              </table>
            </figure>
            """,
            "html.parser",
        )
        markdown, rendered, key_value_fallback = (
            _arxiv_references._render_arxiv_table_block(soup.figure)
        )

        self.assertTrue(rendered)
        self.assertTrue(key_value_fallback)
        self.assertIn("**Table 9.** Grouped scores.", markdown)
        self.assertIn("- Group: A; Metric: Loss; Score: 0.1", markdown)
        self.assertIn("- Group: B; Metric: Accuracy", markdown)

    def test_preview_dimension_threshold_accepts_wide_figures_but_rejects_small_icons(
        self,
    ) -> None:
        self.assertTrue(preview_dimensions_are_acceptable(997, 187))
        self.assertFalse(preview_dimensions_are_acceptable(40, 30))
        self.assertTrue(
            paper_fetch_artifacts._preview_asset_accepted({"width": 997, "height": 187})
        )
        self.assertFalse(
            paper_fetch_artifacts._preview_asset_accepted({"width": 40, "height": 30})
        )

    def test_source_archive_shared_member_is_published_once_and_fanned_out(
        self,
    ) -> None:
        arxiv_id = "2605.06556v1"
        source_url = f"https://arxiv.org/e-print/{arxiv_id}"
        article_url = canonical_arxiv_html_url(arxiv_id)
        article_html = b"""
        <article>
          <figure id="S1.F1" class="ltx_figure">
            <img src="" id="S1.F1.g1" class="ltx_graphics" />
            <figcaption>Figure 1. Shared first.</figcaption>
          </figure>
          <figure id="S1.F2" class="ltx_figure">
            <img src="" id="S1.F2.g1" class="ltx_graphics" />
            <figcaption>Figure 2. Shared second.</figcaption>
          </figure>
        </article>
        """
        archive = _source_tar(
            {
                "main.tex": rb"""
                \documentclass{article}
                \begin{document}
                \begin{figure}
                  \includegraphics{shared.png}
                  \caption{Shared first.}
                \end{figure}
                \begin{figure}
                  \includegraphics{shared.png}
                  \caption{Shared second.}
                \end{figure}
                \end{document}
                """,
                "shared.png": PNG_1X1,
            }
        )
        transport = RecordingTransport(
            {
                ("GET", source_url): http_response(
                    source_url, archive, "application/gzip"
                )
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _arxiv_assets.download_arxiv_source_figure_assets(
                transport,
                arxiv_id=arxiv_id,
                article_id=arxiv_id,
                article_html=article_html.decode(),
                source_url=article_url,
                output_dir=Path(tmpdir),
                user_agent="test",
            )

            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(len(result["assets"]), 2)
            paths = [Path(asset["path"]) for asset in result["assets"]]
            self.assertEqual(paths[0], paths[1])
            self.assertEqual(paths[0].read_bytes(), PNG_1X1)
            self.assertEqual(len(list(paths[0].parent.glob("shared*.png"))), 1)
            self.assertFalse(list(Path(tmpdir).rglob("*.part")))


class TestArxivAncillaryAssets(unittest.TestCase):
    def _responses(self, arxiv_id, *, fixture_id="0811.2625v2", requested_id=None):
        abstract, details = ARXIV_ANCILLARY_PAGES[fixture_id]
        abstract = abstract.replace(fixture_id, arxiv_id).replace(
            fixture_id.rsplit("v", 1)[0], arxiv_id.rsplit("v", 1)[0]
        )
        details = details.replace(fixture_id, arxiv_id)
        abs_url = f"https://arxiv.org/abs/{requested_id or arxiv_id}"
        details_url = f"https://arxiv.org/src/{arxiv_id}/anc"
        return {
            ("GET", abs_url): http_response(abs_url, abstract.encode(), "text/html"),
            ("GET", details_url): http_response(
                details_url, details.encode(), "text/html"
            ),
        }

    def _discover(self, arxiv_id, responses):
        transport = RecordingTransport(responses)
        with paper_fetch.RuntimeContext(env={}) as context:
            fixed_id, result = _arxiv_assets.discover_arxiv_ancillary_assets(
                transport, arxiv_id, user_agent="test", context=context
            )
        return fixed_id, result, transport

    def test_dedupe_and_reject_untrusted_listing_links(self):
        arxiv_id = "0811.2625v2"
        responses = self._responses(arxiv_id)
        url = f"https://arxiv.org/src/{arxiv_id}/anc"
        invalid = [
            "/src/0811.2625v3/anc/other.pdf",
            "/src/0811.9999v2/anc/other.pdf",
            "/src/0811.2625v2",
            "https://example.org/src/0811.2625v2/anc/x.pdf",
            "/src/0811.2625v2/anc/../x.pdf",
            "/src/0811.2625v2/anc/a/../x.pdf",
            "/src/0811.2625v2/anc/%2e%2e/x.pdf",
            "/src/0811.2625v2/anc/%252e%252e/x.pdf",
            "/src/0811.2625v2/anc/a%5cb.pdf",
            "/src/0811.2625v2/anc/a%00b.pdf",
        ]
        duplicate = "/src/0811.2625v2/anc/solve-sparse-opt-check-small%2Enb#download"
        extra = "".join(
            f'<a class="anc-file-name" href="{href}">bad</a>'
            for href in [*invalid, duplicate]
        )
        responses[("GET", url)]["body"] = responses[("GET", url)]["body"].replace(
            b"</ul>", (extra + "</ul>").encode()
        )
        _, result, _ = self._discover(arxiv_id, responses)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 2)

    def test_no_ancillary_section_is_empty_but_failed_discovery_is_not(self):
        arxiv_id = "0811.2625v2"
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        details_url = f"https://arxiv.org/src/{arxiv_id}/anc"
        for failure in (
            "abs_http",
            "abs_identity",
            "abs_redirect",
            "details_http",
            "details_identity",
            "details_incomplete",
            "missing_entry",
            None,
        ):
            with self.subTest(failure=failure):
                responses = self._responses(arxiv_id)
                if failure == "abs_http":
                    responses[("GET", abs_url)]["status"] = 503
                elif failure == "abs_identity":
                    responses[("GET", abs_url)]["body"] = b"<html>Blocked</html>"
                elif failure == "abs_redirect":
                    responses[("GET", abs_url)]["url"] = abs_url.replace("v2", "v3")
                elif failure == "details_http":
                    responses[("GET", details_url)]["status"] = 403
                elif failure == "details_identity":
                    responses[("GET", details_url)]["body"] = responses[
                        ("GET", details_url)
                    ]["body"].replace(b"/abs/0811.2625v2", b"/abs/0811.2625v3")
                elif failure == "details_incomplete":
                    responses[("GET", details_url)]["body"] = responses[
                        ("GET", details_url)
                    ]["body"].replace(b"There are 2", b"There are 3")
                elif failure == "missing_entry":
                    responses[("GET", abs_url)]["body"] = responses[("GET", abs_url)][
                        "body"
                    ].replace(b'/anc"', b'/other"')
                else:
                    soup = _arxiv_html.BeautifulSoup(
                        responses[("GET", abs_url)]["body"], "html.parser"
                    )
                    soup.select_one(".ancillary").decompose()
                    responses[("GET", abs_url)]["body"] = str(soup).encode()
                _, result, transport = self._discover(arxiv_id, responses)
                self.assertEqual(result["assets"], [])
                if failure:
                    self.assertEqual(
                        result["asset_failures"][0]["reason"],
                        "arxiv_ancillary_discovery_failed",
                    )
                else:
                    self.assertEqual(result["asset_failures"], [])
                    self.assertEqual(len(transport.calls), 1)

    def test_explicit_version_rejects_latest_abstract(self):
        responses = self._responses("0811.2625v3", requested_id="0811.2625v2")
        fixed, result, transport = self._discover("0811.2625v2", responses)
        self.assertEqual(fixed, "0811.2625v2")
        self.assertEqual(len(result["asset_failures"]), 1)
        self.assertEqual(len(transport.calls), 1)

    def test_discovery_transport_failure_preserves_fixed_version(self):
        from paper_fetch.http import RequestFailure

        responses = self._responses("0811.2625v2", requested_id="0811.2625")
        url = "https://arxiv.org/src/0811.2625v2/anc"
        responses[("GET", url)] = RequestFailure(
            None, "Timed out", url=url, error_category="timeout"
        )
        fixed_id, result, _ = self._discover("0811.2625", responses)
        self.assertEqual(fixed_id, "0811.2625v2")
        self.assertEqual(result["asset_failures"][0]["source_url"], url)
        self.assertEqual(
            result["asset_failures"][0]["reason"], "arxiv_ancillary_discovery_failed"
        )


if __name__ == "__main__":
    unittest.main()
