"""Source-bound closure contracts for every confirmed third-round record."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin
import re
from collections import Counter

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pytest

from tests.paths import REPO_ROOT
from tests.golden_corpus import GoldenCorpusFixture
from tests.golden_criteria import iter_manifest_samples
from tests.support.replay import build_article_from_fixture
from tests.support.full_read_assertions import assert_source_list_items
from tests.support.reviewed_publisher_content import _words
from tests.support.canonical_content import BODY_SELECTORS, source_references

CASES = json.loads(
    (
        REPO_ROOT
        / "tests/fixtures/golden_criteria/_scenarios/review_contracts/expected.json"
    ).read_text()
)["cases"]
SAMPLES = {
    sample["sample_id"]: sample
    for sample in iter_manifest_samples(fixture_family="golden")
}


def fixture_for_case(case):
    assert (
        hashlib.sha256((REPO_ROOT / case["source"]).read_bytes()).hexdigest()
        == case["source_sha256"]
    )
    sample_id = Path(case["artifact"]).parent.name
    return GoldenCorpusFixture(sample_id, SAMPLES[sample_id])


def assert_record(case, fixture, source, article, markdown):
    """Expectations come from source structures or explicitly reviewed source literals."""
    rendered = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(markdown), "lxml"
    )
    visible = rendered.get_text(" ", strip=True)
    kind = case["contract"]
    body = source.select_one(BODY_SELECTORS[fixture.provider]) or source
    if kind == "xml_scripts":
        nodes = body.find_all("inf")
        assert nodes
        actual = {_words(n.get_text()) for n in rendered.select("sub")}
        for value in {_words(n.get_text()) for n in nodes} - {""}:
            assert value in actual, value
    elif kind == "inline":
        nodes = body.select("em, i, .jp-italic")
        if case["id"] == "FR-0-extra-1-7cc8da09-01":
            nodes = [
                n
                for n in body.select("b, strong")
                if n.get_text() in {"x", "L", "A", "if", "then", "return"}
            ]
        nodes = [
            n
            for n in nodes
            if not n.find_parent(["math", "a"])
            and not any(
                set(p.get("class", []))
                & {"inline-formula", "disp-formula", "math", "formula-wrap"}
                for p in n.parents
                if getattr(p, "attrs", None)
            )
            and not n.find("math")
            and n.get_text(strip=True)
            and len(n.get_text()) < 100
        ]
        assert nodes
        actual = {_words(n.get_text()) for n in rendered.select("em, strong")}
        expected = {_words(n.get_text()) for n in nodes} - {""}
        for text in expected:
            assert text in actual, text
    elif kind == "references":
        refs = source_references(fixture, source)
        assert refs and article.references
        parts = re.split(r"(?m)^## References[^\n]*\n", markdown, maxsplit=1)
        assert len(parts) == 2, "missing rendered bibliography"
        output = BeautifulSoup(
            MarkdownIt("commonmark", {"html": True}).render(parts[1]), "lxml"
        )
        for tag in ["sub", "sup", "em", "i"]:
            originals = [n for ref in refs for n in ref.find_all(tag)]
            if tag in {"sub", "sup"}:
                for text in {_words(n.get_text()) for n in originals} - {""}:
                    assert any(
                        _words(n.get_text()) == text for n in output.select(tag)
                    ), (tag, text)
            else:
                for text in {
                    _words(n.get_text())
                    for n in originals
                    if not n.find_parent(["math", "tex-math"])
                } - {""}:
                    assert any(
                        _words(n.get_text()) == text for n in output.select("em")
                    ), (tag, text)
        if fixture.provider == "frontiers":
            assert len(source.select("ref etal")) == 10
            assert output.get_text().count("et al.") >= 10
        if fixture.provider == "arxiv":
            for key in ["bib.bib34", "bib.bib35"]:
                original = source.find(id=key)
                urls = [
                    a["href"]
                    for a in original.select(
                        ".ltx_bib_external[href], .ltx_bib_external a[href]"
                    )
                ]
                assert urls and all(url in markdown for url in urls)
    elif kind == "lists":
        if fixture.provider == "ieee" and "TCOMM" in fixture.sample_id:
            for original in source.select(".alg-item.label"):
                label = original.select_one(".label").get_text(strip=True)
                assert re.search(r"(?m)^" + re.escape(label) + r" .+", markdown)
        else:
            if body.find("list") is not None:
                assert not re.search(r"(?m)^- • ", markdown)
                return
            assert_source_list_items(body, rendered)
            assert not re.search(r"(?m)^- • ", markdown)
    elif kind == "numbering":
        assert source.find("list") is not None
        assert re.search(r"(?m)^5\. ", markdown)
    elif kind == "glossary":
        original = source.select_one("#html-glossary table")
        assert original is not None
        rows = [n for n in original.select("tr") if n.find_all("td")]
        assert rows
        for row in rows:
            cells = [_words(c.get_text()) for c in row.find_all("td", recursive=False)]
            assert any(
                all(cell in _words(line) for cell in cells)
                for line in markdown.splitlines()
                if line.startswith("|")
            )
    elif kind == "table_notes":
        originals = source.select(".article-section__table-footnotes li")
        assert originals
        for original in originals:
            assert _words(original.get_text()) in _words(markdown)
    elif kind == "headings":
        heading = (
            "TIPPING POINTS IN EARTH'S PAST"
            if "environ" in fixture.doi
            else "BIOPHYSICAL MECHANISMS OF NMDA SPIKES"
        )
        assert heading in source.get_text() and heading in markdown
    elif kind == "subheadings":
        for original in source.select(".tl-third-level-section"):
            assert any(
                _words(original.get_text()) == _words(n.get_text())
                for n in rendered.select("h2,h3,h4,h5,h6")
            )
    elif kind == "decimal":
        assert "was .23." in source.get_text() and "was .23." in visible
    elif kind == "decimal_cell":
        assert source.select('td span[style*="float"]')
        assert "2.76f" in visible and "2. 76f" not in visible
    elif kind == "table_break":
        assert "xmltex" in fixture.raw_path.read_text()
        assert (
            "Water management<br>sensitivity" in markdown
            or "Water management sensitivity" in visible
        )
    elif kind == "table_label":
        assert source.select_one("#label-t1").get_text() == "TABLE I."
        assert "TABLE I." in markdown
    elif kind == "fences":
        assert source.select('mfenced[separators=""]')
        compact = re.sub(r"\s+|\\(?:left|right)", "", markdown)
        if "2322622121" in fixture.doi:
            assert re.search(r"\\sin\{?\(\{?2(?:\\,)?\\pi(?:\\,)?t\}?\)", compact)
            assert not re.search(r"\\(?:sin|cos).*?\(2,", compact)
        else:
            assert "E-P_m" in re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", compact).replace(
                "−", "-"
            ).replace("{", "").replace("}", "")
            assert "E,-,Pm" not in compact
    elif kind == "math_style":
        if "su12072826" in fixture.doi:
            assert source.select("mtd mn")
            assert "0.150.20.30.250.1" not in markdown
            assert r"\ " in markdown
        else:
            operators = {
                n.get_text(strip=True) for n in source.select("math mi, math mo")
            }
            for name in operators & {"ln", "log", "exp", "cos", "tanh"}:
                assert "\\" + name in markdown
            if "~" in operators:
                assert r"\sim" in markdown
            if source.select('mi[mathvariant="script"]'):
                assert r"\mathcal" in markdown
            if source.select('mi[mathvariant="normal"]'):
                assert r"\mathrm" in markdown
    elif kind in {"adjacent_emphasis", "literals"}:
        if kind == "adjacent_emphasis":
            assert body.select("i + i")
            assert re.search(r"<em>A[–-]</em><em>[DE]</em>", markdown)
            assert "A–**" not in visible
        elif "adm9732" in fixture.doi:
            assert "Herb*MAP*YSD" in body.get_text() and "Herb*MAP*YSD" in visible
        elif "gmd-" in fixture.doi:
            assert "_to_" in source.get_text() and "_to_" in visible
        elif "foods" in fixture.doi:
            assert re.search(r"(?m)^\\\* ", markdown)
        elif "rsos" in fixture.doi:
            assert all(
                r"\$" + price in markdown
                for price in re.findall(r"\$(\d+)", body.get_text())
            )
        else:
            assert body.select("strong, b")
            assert rendered.select("strong em, em strong")
            assert not re.search(r"\*<sub>[^<]+</sub>\*", visible)
    elif kind == "word":
        assert body.find("bold") is not None
        assert "paraformaldehyde" in visible and "saponin" in visible
        assert "para form aldehyde" not in visible
    elif kind in {"inline_image_spacing", "inline_formula_images"}:
        images = rendered.select("p img")
        assert images
        if kind == "inline_formula_images":
            matching = [
                n
                for n in images
                if "_IEq14_" in n.get("src", "") or "_IEq15_" in n.get("src", "")
            ]
            assert matching and all(
                len(n.find_parent("p").get_text(strip=True)) > 10 for n in matching
            )
        else:
            assert not re.search(
                r"\b(?:where|and|with|negative|Specifically)!\[", markdown
            )
    elif kind == "image":
        image = source.select_one('img[alt="epsilon"]') or source.select_one(
            ".c-article-section__content img"
        )
        assert image
        url = urljoin(fixture.source_url, image["src"])
        assert any(n.get("src") == url for n in rendered.select("img"))
    elif kind == "renditions":
        for index in [1, 2, 3]:
            assert (
                len(
                    [
                        n
                        for n in rendered.select("img")
                        if f"_Fig{index}_HTML" in n.get("src", "")
                    ]
                )
                == 1
            )
        assert (
            len(
                [n for n in rendered.select("img") if "_IEq71_HTML" in n.get("src", "")]
            )
            == 1
        )
    elif kind == "figure_refs":
        assert re.search(r"(?:Fig|Figs|Eq|Eqs)\.", body.get_text())
        assert re.search(r"(?:Fig|Figs|Eq|Eqs)\. [0-9]", visible)
        assert not re.search(r"\b(?:Fig|Figs|Eq|Eqs)[0-9]", visible)
    elif kind == "formula_labels":
        assert source.select("div.formula-wrap:has(mtable)")
        assert markdown.count("**Equation 1.**") == 1
    elif kind == "listing":
        for number in [1, 2, 3, 4]:
            assert not re.search(
                r"Listing " + str(number) + r"\.\*\* Listing", markdown
            )
            assert re.search(r"Listing " + str(number) + r"\.", markdown)
    elif kind == "ownership":
        if fixture.provider == "arxiv":
            assert "PAPER_FETCH" not in markdown and r"PAPER\_FETCH" not in markdown
            assert markdown.index("Table 2:") < markdown.index("x2.png")
            assert (
                re.search(r"Table 4[.:]", markdown).start()
                < re.search(r"Table 5[.:]", markdown).start()
            )
        else:
            assert "## Figures" not in markdown
    elif kind == "reference_count":
        assert len(source.select("#bibliography .citation-content")) == 71
        assert len(article.references) == 71
        tail = re.split(r"(?m)^## References[^\n]*\n", markdown, maxsplit=1)
        assert len(tail) == 2
        assert len(re.findall(r"(?m)^\d+\. ", tail[1])) == 71
    elif kind == "reference_boundaries":
        assert len(source.select(".ltx_bibitem")) == 50
        tail = markdown.split("## References (", 1)[1].split("\n\n", 1)[1]
        assert len([n for n in tail.split("\n\n") if n.strip()]) >= 50
    elif kind == "supplements":
        assert rendered.select("a[href]")
        assert "](info:doi/" not in markdown
        if fixture.provider == "royalsocietypublishing":
            original = source.select_one('a[href*="article-supplement"]')
            assert original
            assert urljoin(fixture.source_url, original["href"]) in markdown
        elif fixture.provider == "oxfordacademic":
            names = [n.get_text(strip=True) for n in source.select(".dataSuppLink a")]
            for name in set(names):
                assert visible.count(name) == 1
        else:
            originals = source.find_all("supplementary-material")
            assert originals
            for original in originals:
                url = original.get("href") or original.get("xlink:href") or ""
                if url.startswith("info:doi/"):
                    assert (
                        "https://doi.org/" + url.removeprefix("info:doi/")
                    ) in markdown
    elif kind == "availability":
        assert len(source.select("#data-availability-1, #data-availability-2")) == 2
        assert markdown.count("## Data Availability") == 1
        assert "Data deposition" in markdown
    elif kind == "frontiers":
        capture = (
            fixture.raw_path.parent
            / "acquisition/regression-2026-09-16/landing-response.bin"
        )
        assert "files/Articles/569407/" in capture.read_text()
        assert "/files/Articles/01216/" not in markdown
        assert "/files/Articles/569407/" in markdown
    elif kind == "significance":
        original = next(
            n
            for n in source.select("h3.abstractTitle")
            if n.get_text(strip=True) == "Significance Statement"
        )
        assert original
        assert "## Significance Statement" in markdown
    elif kind == "code":
        assert source.select("monospace")
        assert rendered.select("code")
        if case["id"].endswith("-02"):
            assert (
                len([n for n in rendered.select("code") if n.get_text() == "<NA>"]) >= 5
            )
        else:
            assert any(
                n.get_text().startswith(">") for n in rendered.select("pre code")
            )
    else:
        raise AssertionError(("unhandled source contract", kind, case["id"]))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_confirmed_full_read_source_contract(case):
    fixture = fixture_for_case(case)
    source = BeautifulSoup(
        fixture.raw_path.read_text(),
        "xml" if fixture.raw_path.suffix == ".xml" else "lxml",
    )
    assert (REPO_ROOT / case["source"]).is_file()
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(asset_profile="all", include_refs="all")
    assert_record(case, fixture, source, article, markdown)
    # The ledger closes against the persisted reader artifact as well as replay.
    final_markdown = (REPO_ROOT / case["artifact"]).read_text()
    assert_record(case, fixture, source, article, final_markdown)


@pytest.mark.parametrize("doi", ["10.1098/rsos.201188", "10.1126/sciadv.adl6155"])
def test_original_numeric_and_text_mathvariant_is_preserved(doi):
    sample = next(s for s in SAMPLES.values() if s["doi"] == doi)
    fixture = GoldenCorpusFixture(sample["sample_id"], sample)
    source = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
    counts = Counter(
        (n.name, n.get("mathvariant"), n.get_text())
        for n in source.select('mn[mathvariant="bold"], mtext[mathvariant="italic"]')
    )
    assert counts
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        asset_profile="all", include_refs="all", max_tokens="full_text"
    )
    for (tag, variant, text), count in counts.items():
        command = "mathbf" if tag == "mn" and variant == "bold" else "textit"
        assert markdown.count("\\" + command + "{" + text + "}") >= count
