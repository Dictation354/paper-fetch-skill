from __future__ import annotations
from __future__ import annotations
from __future__ import annotations
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from paper_fetch.providers import (
    _article_markdown_elsevier_document as elsevier_document,
)
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.models import article_from_structure
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset
from paper_fetch.models import article_from_markdown


def build_elsevier_markdown(
    xml_body: bytes,
    *,
    assets: list[dict[str, str]] | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    article_metadata = {
        "doi": "10.1016/test",
        "title": "Elsevier Markdown Example",
        "journal_title": "Example Journal",
        "published": "2026-01-01",
        "landing_page_url": "https://example.test/article",
        "abstract": "",
    }
    if metadata:
        article_metadata.update(metadata)

    with tempfile.TemporaryDirectory() as tmpdir:
        xml_path = Path(tmpdir) / "10.1016_test.xml"
        xml_path.write_bytes(xml_body)
        prepared_assets: list[dict[str, str]] = []
        for asset in assets or []:
            prepared = dict(asset)
            if prepared.get("path"):
                asset_path = Path(tmpdir) / Path(prepared["path"]).name
                asset_path.write_bytes(b"fake")
                prepared["path"] = str(asset_path)
            prepared_assets.append(prepared)
        markdown_path = elsevier_document.write_article_markdown(
            provider="elsevier",
            metadata=article_metadata,
            xml_body=xml_body,
            output_dir=Path(tmpdir),
            xml_path=str(xml_path),
            assets=prepared_assets,
        )

        assert markdown_path is not None
        return Path(markdown_path).read_text(encoding="utf-8")


def _load_elsevier_golden_xml(doi: str) -> bytes:
    return golden_criteria_asset(doi, "original.xml").read_bytes()


def _load_elsevier_scenario_xml(name: str) -> bytes:
    return golden_criteria_scenario_asset(name, "original.xml").read_bytes()


def _render_elsevier_golden_markdown(
    doi: str,
    *,
    assets: list[dict[str, str]] | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    article_metadata = {
        "doi": doi,
        "title": f"Elsevier Golden Fixture {doi}",
    }
    if metadata:
        article_metadata.update(metadata)
    return build_elsevier_markdown(
        _load_elsevier_golden_xml(doi),
        assets=assets,
        metadata=article_metadata,
    )


def _build_elsevier_golden_structure(doi: str):
    xml_body = _load_elsevier_golden_xml(doi)
    slug = doi.replace("/", "_")
    return elsevier_document.build_article_structure(
        provider="elsevier",
        metadata={"doi": doi, "title": f"Elsevier Golden Fixture {doi}"},
        xml_body=xml_body,
        xml_path=Path(f"{slug}.xml"),
        assets=elsevier_provider.extract_elsevier_asset_references(xml_body),
    )


def _assert_markdown_table_row(
    test_case: unittest.TestCase,
    markdown: str,
    cells: list[str],
    *,
    allow_more_cells: bool = False,
) -> None:
    cell_pattern = r"\s*\|\s*".join(re.escape(cell) for cell in cells)
    suffix = r"(?:\s*\|.*)?$" if allow_more_cells else r"\s*\|$"
    test_case.assertRegex(markdown, rf"(?m)^\|\s*{cell_pattern}{suffix}")


class ElsevierMarkdownTests(unittest.TestCase):
    def test_apgeog_xml_preserves_author_abstract_and_textual_highlights(self) -> None:
        from bs4 import BeautifulSoup
        from tests.golden_corpus import golden_corpus_fixture_for_doi
        from tests.support.replay import build_article_from_fixture
        from tests.support.reviewed_publisher_content import _words

        # The source-origin audit marks this input unverified. This test checks
        # its supplied XML content, not authenticity of a publisher capture.
        doi = "10.1016/j.apgeog.2012.04.006"
        source = BeautifulSoup(_load_elsevier_golden_xml(doi), "xml")
        abstracts = source.find_all("abstract")
        self.assertEqual(
            [node.get("class") for node in abstracts], ["author", "graphical"]
        )
        self.assertEqual(abstracts[0].get("xml:lang"), "en")
        self.assertEqual(
            abstracts[1].find("section-title").get_text(strip=True), "Highlights"
        )
        self.assertIsNone(abstracts[1].find("figure"))
        self.assertEqual(
            [len(node.find_all("simple-para")) for node in abstracts], [1, 1]
        )
        expected = [
            _words(node.find("simple-para").get_text(" ", strip=True))
            for node in abstracts
        ]
        self.assertNotEqual(expected[0], expected[1])

        fixture = golden_corpus_fixture_for_doi(doi)
        article = build_article_from_fixture(fixture)
        rendered = [
            section for section in article.sections if section.kind == "abstract"
        ]
        self.assertEqual(
            [section.heading for section in rendered], ["Abstract", "Highlights"]
        )
        self.assertEqual([_words(section.text) for section in rendered], expected)
        self.assertEqual(_words(article.metadata.abstract), expected[0])
        markdown = _words(article.to_ai_markdown(max_tokens="full_text"))
        self.assertLess(markdown.index(expected[0]), markdown.index(expected[1]))

    def test_build_article_structure_extracts_numbered_xml_references(self) -> None:
        doi = "10.1016/j.agrformet.2024.109975"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.agrformet.2024.109975.xml"),
            assets=[],
        )

        assert structure is not None
        self.assertGreater(len(structure.references), 20)
        first_reference = structure.references[0]
        self.assertTrue(first_reference.raw.startswith("1. A. Anav, P. Friedlingstein"))
        self.assertIn(
            "Spatiotemporal patterns of terrestrial gross primary production: a review",
            first_reference.raw,
        )
        self.assertIn("Reviews of Geophysics, 53(3): 785-818", first_reference.raw)
        self.assertIn("10.1002/2015rg000483", first_reference.raw)
        self.assertIn("[Anav et al., 2015]", first_reference.raw)

        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            doi=doi,
            abstract_lines=[],
            body_lines=["A short body paragraph keeps the article renderable."],
            figure_entries=[],
            table_entries=[],
            supplement_entries=[],
            conversion_notes=[],
            references=structure.references,
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertIn("1. A. Anav, P. Friedlingstein", rendered)
        self.assertNotIn(
            "- Spatiotemporal patterns of terrestrial gross primary production: a review",
            rendered,
        )

    def _assert_real_elsevier_display_formula_renders_as_formula_block(self) -> None:
        markdown = _render_elsevier_golden_markdown("10.1016/j.agrformet.2024.109975")

        self.assertIn("(26)", markdown)
        self.assertRegex(
            markdown,
            r"\$\$\nF_\{crit\} = \\sum(?:\\limits)?_\{t_\{p\}\}\^\{SOS_\{y0\}\}\s*R_\{f\}\n\$\$",
        )
        self.assertLess(markdown.index("(26)"), markdown.index("$$"))

    def _assert_inline_math_symbols_in_paragraph_do_not_repeat_as_display_blocks(
        self,
    ) -> None:
        xml_body = _load_elsevier_scenario_xml("elsevier_formula_inline_display")

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn(
            "Air temperature ($T$) and dewpoint temperature ($T_{d}$) were used:",
            markdown,
        )
        self.assertIn("where $c_{1}$ is constant.", markdown)
        self.assertRegex(markdown, r"\$\$\n\{?VPD\}? = T\n\$\$")
        self.assertNotIn("$$\nT\n$$", markdown)
        self.assertNotIn("$$\nT_{d}\n$$", markdown)
        self.assertNotIn("$$\nc_{1}\n$$", markdown)

    def _assert_formula_placeholder_is_visible_and_counted_when_conversion_fails(
        self,
    ) -> None:
        xml_body = _load_elsevier_scenario_xml("elsevier_formula_missing")

        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={
                "doi": "10.1016/formula-missing",
                "title": "Formula Missing Example",
                "landing_page_url": "https://example.test/article",
            },
            xml_body=xml_body,
            xml_path=Path("10.1016_formula-missing.xml"),
            assets=[],
        )

        assert structure is not None
        self.assertIn("[Formula unavailable: (1)]", "\n".join(structure.body_lines))
        self.assertEqual(structure.semantic_losses.formula_missing_count, 1)
        self.assertIn(
            "- (1): Formula could not be converted; an explicit placeholder was inserted.",
            structure.conversion_notes,
        )

    def test_elsevier_regression_32_preserves_independent_table_groups(self) -> None:
        doi = "10.1016/j.apgeog.2012.04.006"
        structure = _build_elsevier_golden_structure(doi)

        assert structure is not None
        table = next(
            entry for entry in structure.table_entries if entry["heading"] == "Table 1"
        )
        groups = table["_table_groups"]
        rendered = "\n".join(elsevier_document.render_table_block(table))

        self.assertEqual([len(group["headers"]) for group in groups], [3, 5])
        self.assertEqual([len(group["rows"]) for group in groups], [5, 19])
        self.assertEqual(len(re.findall(r"(?m)^\| -+(?:\s+\|.*)$", rendered)), 2)
        self.assertEqual(rendered.count("Table 1"), 1)
        self.assertEqual(
            structure.semantic_losses.table_fallback_count,
            0,
        )
        self.assertEqual(
            structure.semantic_losses.table_layout_degraded_count,
            0,
        )

        root = ET.fromstring(_load_elsevier_golden_xml(doi))
        source_table = next(
            node
            for node in root.iter()
            if isinstance(node.tag, str)
            and elsevier_document.xml_local_name(node.tag) == "table"
            and any(
                elsevier_document.xml_local_name(child.tag) == "label"
                and elsevier_document.normalize_text("".join(child.itertext()))
                == "Table 1"
                for child in list(node)
                if isinstance(child.tag, str)
            )
        )
        self.assertEqual(
            [
                sum(
                    1
                    for row in group.iter()
                    if isinstance(row.tag, str)
                    and elsevier_document.xml_local_name(row.tag) in {"row", "tr"}
                )
                for group in source_table.iter()
                if isinstance(group.tag, str)
                and elsevier_document.xml_local_name(group.tag) == "tgroup"
            ],
            [6, 21],
        )

    def test_elsevier_regression_97_renders_wbgt_t_at_groups_in_order(self) -> None:
        doi = "10.1016/j.envres.2018.12.059"
        structure = _build_elsevier_golden_structure(doi)

        assert structure is not None
        table = next(
            entry for entry in structure.table_entries if entry["heading"] == "Table 2"
        )
        groups = table["_table_groups"]
        rendered = "\n".join(elsevier_document.render_table_block(table))

        self.assertEqual(
            [group.get("_table_prefix_rows") for group in groups],
            [["(a) WBGT"], ["(b) T"], ["(c) AT"]],
        )
        self.assertEqual([len(group["rows"]) for group in groups], [18, 18, 18])
        self.assertEqual(len(re.findall(r"(?m)^\| -+(?:\s+\|.*)$", rendered)), 3)
        self.assertLess(rendered.index("(a) WBGT"), rendered.index("(b) T"))
        self.assertLess(rendered.index("(b) T"), rendered.index("(c) AT"))
        self.assertEqual(structure.semantic_losses.table_fallback_count, 0)
        self.assertEqual(structure.semantic_losses.table_layout_degraded_count, 0)

        root = ET.fromstring(_load_elsevier_golden_xml(doi))
        source_table = next(
            node
            for node in root.iter()
            if isinstance(node.tag, str)
            and elsevier_document.xml_local_name(node.tag) == "table"
            and any(
                elsevier_document.xml_local_name(child.tag) == "label"
                and elsevier_document.normalize_text("".join(child.itertext()))
                == "Table 2"
                for child in list(node)
                if isinstance(child.tag, str)
            )
        )
        self.assertEqual(
            [
                sum(
                    1
                    for row in group.iter()
                    if isinstance(row.tag, str)
                    and elsevier_document.xml_local_name(row.tag) in {"row", "tr"}
                )
                for group in source_table.iter()
                if isinstance(group.tag, str)
                and elsevier_document.xml_local_name(group.tag) == "tgroup"
            ],
            [21, 21, 21],
        )

    def test_elsevier_regression_42_uses_two_official_formula_images(self) -> None:
        doi = "10.1016/j.uclim.2019.100528"
        structure = _build_elsevier_golden_structure(doi)

        assert structure is not None
        formula_lines = [
            line for line in structure.body_lines if line.startswith("![Formula](")
        ]
        self.assertEqual(len(formula_lines), 2)
        self.assertTrue(any("fx1_lrg.jpg" in line for line in formula_lines))
        self.assertTrue(any("fx2_lrg.jpg" in line for line in formula_lines))
        self.assertEqual(structure.semantic_losses.formula_fallback_count, 2)
        self.assertEqual(structure.semantic_losses.formula_missing_count, 0)
        self.assertFalse(
            any("[Formula unavailable" in line for line in structure.body_lines)
        )

        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Formula image regression"},
            doi=doi,
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            semantic_losses=structure.semantic_losses,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        self.assertEqual(article.quality.confidence, "medium")
        self.assertIn("formula_fallback_present", article.quality.flags)

    def test_elsevier_real_multilevel_header_is_flattened_without_body_header_row(
        self,
    ) -> None:
        markdown = _render_elsevier_golden_markdown("10.1016/j.rse.2024.114346")

        _assert_markdown_table_row(
            self,
            markdown,
            [
                "Region",
                "Freeze-up date / Mean value (DOY)",
                "Freeze-up date / Trend (days per decade)",
                "Break-up date / Mean value (DOY)",
                "Break-up date / Trend (days per decade)",
                "Ice duration / Mean value (days)",
                "Ice duration / Trend (days per decade)",
            ],
        )
        self.assertNotRegex(
            markdown,
            r"(?m)^\|\s*Region\s*\|\s*Mean value \(DOY\)\s*\|\s*Trend",
        )

    def test_elsevier_real_complex_table_records_successful_normalization(
        self,
    ) -> None:
        doi = "10.1016/j.jhydrol.2021.126210"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.jhydrol.2021.126210.xml"),
            assets=[],
        )

        assert structure is not None
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            doi=doi,
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            semantic_losses=structure.semantic_losses,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        self.assertEqual(article.quality.semantic_losses.table_layout_degraded_count, 0)
        self.assertNotIn("table_layout_degraded", article.quality.flags)
        self.assertFalse(
            any(note.startswith("- Table 1:") for note in structure.conversion_notes)
        )

    def _render_real_elsevier_appendix_markdown(self) -> str:
        return _render_elsevier_golden_markdown(
            "10.1016/j.rse.2026.115369",
            assets=[
                {
                    "asset_type": "appendix_image",
                    "source_ref": "fx1",
                    "path": "figure-a1.jpg",
                }
            ],
        )

    def _assert_real_elsevier_appendix_figure_renders_as_figure_block(self) -> None:
        markdown = self._render_real_elsevier_appendix_markdown()
        appendix_section = markdown[markdown.index("### Appendix") :]

        self.assertIn("![Figure A.1](figure-a1.jpg)", appendix_section)
        self.assertIn(
            "Map of the locations of the offshore wind farms Vindeby, Horns Rev. 1, and Alpha Ventus, and three FINO meteorological masts.",
            appendix_section,
        )

    def _assert_real_elsevier_appendix_figure_stays_in_appendix_when_referenced_from_body(
        self,
    ) -> None:
        markdown = self._render_real_elsevier_appendix_markdown()
        body_reference_idx = markdown.index("Fig. A.1 indicates locations.")
        appendix_idx = markdown.index("### Appendix")
        figure_idx = markdown.index("![Figure A.1](figure-a1.jpg)")

        self.assertLess(body_reference_idx, appendix_idx)
        self.assertLess(appendix_idx, figure_idx)

    def _assert_real_elsevier_appendix_table_renders_as_markdown_table(self) -> None:
        markdown = self._render_real_elsevier_appendix_markdown()
        appendix_section = markdown[markdown.index("### Appendix") :]

        self.assertIn("Table A.1", appendix_section)
        self.assertIn(
            "List of publications on SAR-based wind resources using Envisat ASAR, ERS, and R-1.",
            appendix_section,
        )
        _assert_markdown_table_row(
            self,
            appendix_section,
            ["Reference", "SAR", "Location"],
            allow_more_cells=True,
        )

    def test_elsevier_appendix_figure_renders_as_figure_block(self) -> None:
        self._assert_real_elsevier_appendix_figure_renders_as_figure_block()

    def test_elsevier_appendix_reference_keeps_asset_in_appendix(self) -> None:
        self._assert_real_elsevier_appendix_figure_stays_in_appendix_when_referenced_from_body()

    def test_elsevier_appendix_table_renders_as_markdown_table(self) -> None:
        self._assert_real_elsevier_appendix_table_renders_as_markdown_table()

    def test_real_supplementary_e_component_from_golden_xml_is_listed(self) -> None:
        markdown = _render_elsevier_golden_markdown(
            "10.1016/j.ecolind.2024.112140",
            assets=[
                {
                    "asset_type": "supplementary",
                    "source_ref": "mmc1",
                    "path": "mmc1.docx",
                }
            ],
        )

        self.assertNotIn("### Supplementary data", markdown)
        self.assertIn("## Supplementary Materials", markdown)
        self.assertIn("[Supplementary Data 1](mmc1.docx)", markdown)

    def test_real_author_manuscript_alias_is_registered_and_rendered_once(self) -> None:
        doi = "10.1016/j.ecolind.2024.112140"
        xml_body = _load_elsevier_golden_xml(doi)
        assets = [
            asset
            for asset in elsevier_provider.extract_elsevier_asset_references(xml_body)
            if asset["asset_type"] == "supplementary"
        ]
        self.assertEqual([asset["source_ref"] for asset in assets], ["mmc1", "am"])
        self.assertEqual(
            [asset["source_kind"] for asset in assets], ["object", "object"]
        )
        self.assertEqual(
            [asset["filename_hint"] for asset in assets],
            ["1-s2.0-S1470160X24005971-mmc1.docx", "1-s2.0-S1470160X24005971-am.pdf"],
        )
        for asset in assets:
            asset["path"] = asset["filename_hint"]
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=xml_body,
            xml_path=Path("article.xml"),
            assets=assets,
        )
        assert structure is not None
        self.assertEqual(len(structure.supplement_entries), 2)
        self.assertEqual(
            structure.supplement_entries[0]["heading"], "Supplementary Data 1"
        )
        self.assertEqual(
            [entry["path"] for entry in structure.supplement_entries],
            [asset["path"] for asset in assets],
        )
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": structure.title},
            doi=doi,
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
        )
        supplements = [
            asset for asset in article.assets if asset.kind == "supplementary"
        ]
        self.assertEqual(
            [asset.path for asset in supplements], [asset["path"] for asset in assets]
        )
        markdown = article.to_ai_markdown(max_tokens="full_text", asset_profile="all")
        self.assertEqual(markdown.count(f"]({assets[1]['path']})"), 1)
        self.assertEqual(
            markdown.count(f"[Supplementary Data 1]({assets[0]['path']})"), 1
        )

    def test_real_graphical_abstract_from_golden_xml_is_excluded_from_figures(
        self,
    ) -> None:
        doi = "10.1016/j.scitotenv.2022.158499"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.scitotenv.2022.158499.xml"),
            assets=[
                {
                    "asset_type": "image",
                    "source_ref": "gr1",
                    "path": "gr1.jpg",
                },
                {
                    "asset_type": "graphical_abstract",
                    "source_ref": "ga1",
                    "path": "ga1.jpg",
                },
            ],
        )

        assert structure is not None
        self.assertTrue(
            any(entry["path"] == "gr1.jpg" for entry in structure.figure_entries)
        )
        self.assertFalse(
            any(entry["path"] == "ga1.jpg" for entry in structure.figure_entries)
        )

    def _render_real_elsevier_body_table_markdown(self) -> str:
        return _render_elsevier_golden_markdown("10.1016/j.jhydrol.2021.126210")

    def _assert_real_elsevier_body_table_is_inserted_near_reference(self) -> None:
        markdown = self._render_real_elsevier_body_table_markdown()
        reference_idx = markdown.index(
            "The detailed information on the hydro-meteorological data is given in Table 1"
        )
        caption_idx = markdown.index("Study area and data used in this study.")
        header_match = re.search(
            r"(?m)^\|\s*Type\s*\|\s*Location\s*\|\s*Station\s*\|", markdown
        )
        self.assertIsNotNone(header_match)
        assert header_match is not None
        header_idx = header_match.start()

        self.assertLess(reference_idx, caption_idx)
        self.assertLess(caption_idx, header_idx)
        self.assertLess(header_idx - reference_idx, 500)

    def _assert_real_elsevier_complex_body_table_prefers_normalized_markdown_over_image_fallback(
        self,
    ) -> None:
        markdown = self._render_real_elsevier_body_table_markdown()

        _assert_markdown_table_row(
            self,
            markdown,
            [
                "Hydrometric",
                "China",
                "Jiuzhou",
                "385",
                "1960–2006",
                "23°04′12″N",
                "114°35′24″E",
                "Water Conservancy and Electric Power Bureau, Guangdong Province, China",
            ],
            allow_more_cells=True,
        )
        self.assertNotIn("Merged table spans were semantically expanded", markdown)
        self.assertNotIn("- Table 1: None", markdown)
        self.assertNotIn("![Table 1]", markdown)

    def _assert_real_elsevier_consumed_table_is_not_appended_by_article_model(
        self,
    ) -> None:
        doi = "10.1016/j.jhydrol.2021.126210"
        structure = elsevier_document.build_article_structure(
            provider="elsevier",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            xml_body=_load_elsevier_golden_xml(doi),
            xml_path=Path("10.1016_j.jhydrol.2021.126210.xml"),
            assets=[],
        )

        assert structure is not None
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"doi": doi, "title": "Elsevier Golden Fixture"},
            doi=doi,
            abstract_lines=structure.abstract_lines,
            body_lines=structure.body_lines,
            figure_entries=structure.figure_entries,
            table_entries=structure.table_entries,
            supplement_entries=structure.supplement_entries,
            conversion_notes=structure.conversion_notes,
            semantic_losses=structure.semantic_losses,
            inline_figure_keys=sorted(structure.used_figure_keys),
            inline_table_keys=sorted(structure.used_table_keys),
        )
        rendered = article.to_ai_markdown(asset_profile="body")

        self.assertTrue(
            any(
                asset.kind == "table" and asset.render_state == "inline"
                for asset in article.assets
            )
        )
        self.assertEqual(article.quality.semantic_losses.table_layout_degraded_count, 0)
        self.assertNotIn("table_layout_degraded", article.quality.flags)
        self.assertNotIn("table_semantic_loss", article.quality.flags)
        self.assertNotIn("## Additional Tables", rendered)
        self.assertEqual(rendered.count("Study area and data used in this study."), 1)

    def _assert_unreferenced_body_table_is_listed_in_additional_tables(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <body>
    <ce:sections>
      <ce:section>
        <ce:section-title>Results</ce:section-title>
        <ce:para>Main text only.</ce:para>
      </ce:section>
    </ce:sections>
    <ce:floats>
      <ce:table id="t0005">
        <ce:label>Table 1</ce:label>
        <ce:caption>
          <ce:simple-para>Floating table.</ce:simple-para>
        </ce:caption>
        <tgroup cols="2">
          <thead>
            <row>
              <entry>A</entry>
              <entry>B</entry>
            </row>
          </thead>
          <tbody>
            <row>
              <entry>1</entry>
              <entry>2</entry>
            </row>
          </tbody>
        </tgroup>
      </ce:table>
    </ce:floats>
  </body>
</full-text-retrieval-response>
"""

        markdown = build_elsevier_markdown(xml_body)

        self.assertIn("Main text only.", markdown)
        self.assertIn("## Additional Tables", markdown)
        self.assertIn("Floating table.", markdown)
        _assert_markdown_table_row(self, markdown, ["A", "B"])

    def test_elsevier_golden_fixture_classifies_data_and_code_availability_sections(
        self,
    ) -> None:
        doi = "10.1016/j.rse.2025.114648"
        markdown = _render_elsevier_golden_markdown(doi)
        article = article_from_markdown(
            source="elsevier_xml",
            metadata={"title": f"Elsevier Golden Fixture {doi}"},
            doi=doi,
            markdown_text=markdown,
        )

        section_pairs = [
            (section.heading, section.kind) for section in article.sections
        ]
        self.assertIn(("Data availability", "data_availability"), section_pairs)
        self.assertIn(("Code availability", "code_availability"), section_pairs)

    def test_elsevier_table_placement_contracts(self) -> None:
        cases = [
            (
                "real_body_table_inserted_near_reference",
                self._assert_real_elsevier_body_table_is_inserted_near_reference,
            ),
            (
                "real_complex_body_table_prefers_normalized_markdown",
                self._assert_real_elsevier_complex_body_table_prefers_normalized_markdown_over_image_fallback,
            ),
            (
                "real_consumed_table_not_appended_by_article_model",
                self._assert_real_elsevier_consumed_table_is_not_appended_by_article_model,
            ),
            (
                "synthetic_unreferenced_float_table",
                self._assert_unreferenced_body_table_is_listed_in_additional_tables,
            ),
        ]

        for label, assertion in cases:
            with self.subTest(label=label):
                assertion()

    def test_elsevier_real_display_formula_renders_as_formula_block(self) -> None:
        self._assert_real_elsevier_display_formula_renders_as_formula_block()


if __name__ == "__main__":
    unittest.main()


def test_elsevier_original_mathml_sample_has_no_independent_formula_supplements() -> (
    None
):
    xml = golden_criteria_asset(
        "10.1016/j.rse.2025.114648", "original.xml"
    ).read_bytes()
    refs = elsevier_provider.extract_elsevier_asset_references(xml)
    assert refs
    assert not [a for a in refs if a["asset_type"] == "supplementary"]
    assert not [a for a in refs if a.get("object_type") == "ALTIMG"]


if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
