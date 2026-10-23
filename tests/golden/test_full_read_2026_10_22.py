"""Source-driven closure of every scoped finding in the 22 October review."""

import hashlib
import json
import re
from urllib.parse import quote, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pytest

from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.paths import REPO_ROOT
from tests.support.replay import build_article_from_fixture, persisted_fixture_markdown

CONTRACTS = json.loads(
    (
        REPO_ROOT
        / "tests/fixtures/golden_criteria/_scenarios/review_contracts/expected.json"
    ).read_text()
)
FILES = {f["path"]: f for f in CONTRACTS["files"]}
CASES = CONTRACTS["records"]


def key(value):
    return re.sub(r"[^\w]+", "", value).casefold()


def presentation(markdown):
    return BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown),
        "lxml",
    )


def source_targets(source):
    """Read IDs and explicit aliases independently of production link rewriting."""
    targets = {}
    for n in source.find_all(True):
        owner = n.get("id") or n.get("name") or n.get("data-content-id")
        if owner:
            for attr in [
                "id",
                "name",
                "data-legacyid",
                "data-legacy-id",
                "content-id",
                "data-content-id",
                "data-bib-id",
            ]:
                if n.get(attr):
                    targets[str(n[attr])] = str(owner)
            if n.name in {"figure", "table"}:
                for child in n.select("[data-target]"):
                    if child.find_parent(["figure", "table"]) is n:
                        targets[str(child["data-target"]).lstrip("#")] = str(owner)
    return targets


def assert_source_links(source, rendered, fixture):
    targets = source_targets(source)
    folded = {key.casefold(): value for key, value in targets.items()}
    actual = {unquote(a["href"]) for a in rendered.select("a[href]")}
    checked = 0
    missing = []
    from tests.support.canonical_content import BODY_SELECTORS

    roots = source.select(BODY_SELECTORS[fixture.provider]) + source.select(
        ".ltx_abstract, section.abstract"
    )
    assert roots
    for a in source.find_all("a"):
        if not any(root is a or root in a.parents for root in roots):
            continue
        if a.find_parent(
            class_=re.compile(
                r"bibliograph|ref-list|references|ltx_bib_cited|ltx_bib_links"
            )
        ):
            continue
        text = key(a.get_text())
        if not text:
            continue
        href = str(a.get("href") or "")
        candidates = [
            str(a.get(attr) or "").lstrip("#")
            for attr in [
                "data-rid",
                "data-modal-source-id",
                "reveal-id",
                "data-open",
                "data-target",
            ]
        ]
        if href.startswith("#"):
            candidates.append(unquote(href[1:]))
        target = next(
            (
                (targets.get(c) or folded.get(c.casefold()))
                for c in candidates
                if c in targets or c.casefold() in folded
            ),
            None,
        )
        if target is None:
            continue
        # Navigation, source widgets and bibliography discovery controls are not prose callouts.
        if a.find_parent(["nav", "header", "footer"]) or a.find_parent(
            class_=re.compile(r"toc|toolbar|navbar|menu|dropDownMenu")
        ):
            continue
        if re.search(
            r"^(?:view|download|open|show|hide|back|next|previous|top|article|abstract|references|figures|tables|supplement|browse)",
            a.get_text(" ", strip=True),
            re.I,
        ):
            continue
        expected = unquote(urljoin(fixture.source_url, "#" + quote(target)))
        checked += 1
        if expected not in actual and "#" + target not in actual:
            missing.append((a.get_text(" ", strip=True)[:55], expected))
    assert checked, "no positive source cross-reference assertions"
    assert not missing, missing[:20]
    assert not rendered.select('a[href="#"]')


def assert_evidence_text(case, rendered):
    """Assert positive source excerpts, never removal of the old faulty excerpt."""
    checked = 0
    visible = key(rendered.get_text())
    for evidence in case["source_evidence"]:
        text = BeautifulSoup(evidence.get("excerpt", ""), "html.parser").get_text(
            " ", strip=True
        )
        # A partial tag carries identity evidence, not a textual expectation.
        if len(re.findall(r"\w+", text)) < 4 or "<" in text:
            continue
        assert key(text) in visible, text
        checked += 1
    assert checked, "this rule requires a dedicated structural source assertion"


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_source_driven_fix(case):
    info = FILES[case["path"]]
    fixture = golden_corpus_fixture_for_doi(info["doi"])
    for path, digest in case["source_hashes"].items():
        assert hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest() == digest
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="all"
    )
    rendered = presentation(markdown)
    source = (
        BeautifulSoup(
            fixture.raw_path.read_bytes(),
            "xml" if info["source_type"] == "xml" else "lxml",
        )
        if info["source_type"] != "pdf"
        else None
    )
    kind = case["rule"]
    if kind == "source_links":
        assert_source_links(source, rendered, fixture)
    elif kind in {
        "equation_intro",
    }:
        assert_evidence_text(case, rendered)
    elif kind == "backmatter":
        assert_evidence_text(case, rendered)
        for evidence in case["source_evidence"]:
            text = BeautifulSoup(evidence.get("excerpt", ""), "html.parser").get_text(
                " ", strip=True
            )
            if len(text.split()) < 4:
                continue
            matches = [
                section
                for section in article.sections
                if key(text) in key(section.heading + " " + section.text)
            ]
            assert matches and all(section.kind == "body" for section in matches), text
    elif kind == "table_notes":
        assert_evidence_text(case, rendered)
        for evidence in case["source_evidence"]:
            fragment = BeautifulSoup(evidence["excerpt"], "html.parser")
            parts = fragment.select("li") or [fragment]
            for part in parts:
                text = key(part.get_text())
                matches = [
                    n for n in rendered.select("p,li") if text in key(n.get_text())
                ]
                assert matches and any(
                    n.find_previous("table") is not None for n in matches
                ), text
    elif kind == "caption_boundary":
        assert_evidence_text(case, rendered)
        for evidence in case["source_evidence"]:
            text = BeautifulSoup(evidence["excerpt"], "html.parser").get_text().strip()
            assert any(n.get_text().startswith(text) for n in rendered.select("p")), (
                text
            )
    elif kind == "spaces":
        visible = " ".join(rendered.get_text().split())
        for evidence in case["source_evidence"]:
            expected = BeautifulSoup(evidence["excerpt"], "html.parser").get_text()
            assert " ".join(expected.split()) in visible
    elif kind == "breaks" or (
        kind == "table_paragraphs" and info["source_type"] == "xml"
    ):
        from tests.support.full_read_assertions import assert_explicit_source_breaks

        assert_explicit_source_breaks(
            source, rendered, tables_only=kind == "table_paragraphs"
        )
    elif kind == "table_paragraphs":
        checked = 0
        evidence_sources = [
            BeautifulSoup((REPO_ROOT / path).read_bytes(), "lxml")
            for path in case["source_hashes"]
        ]
        for cell in [
            n for capture in evidence_sources for n in capture.select("td,th")
        ]:
            paragraphs = cell.find_all("p", recursive=False)
            if len(paragraphs) < 2:
                continue
            runs = [p.get_text() for p in paragraphs]
            matches = [
                c
                for c in rendered.select("td,th")
                if all(key(t) in key(c.get_text()) for t in runs)
            ]
            assert matches, runs
            assert any(
                c.find("br") is not None or len(c.find_all("p")) >= len(runs)
                for c in matches
            )
            checked += 1
        assert checked
    elif kind == "literal_comparison":
        originals = [
            str(t).strip()
            for t in source.strings
            if t.find_parent(["list-item", "li"]) and re.match(r"^\s*>\s*\d+", str(t))
        ]
        assert originals
        for text in originals:
            assert any(
                " ".join(text.split()) in " ".join(n.get_text().split())
                for n in rendered.select("li")
            ), text
    elif kind == "heading_labels":
        checked = 0
        for heading in source.select(".tl-third-level-section"):
            label = heading.find_previous_sibling(class_="label")
            if label is None:
                continue
            expected = key(label.get_text() + heading.get_text())
            assert any(
                key(h.get_text()) == expected for h in rendered.select("h2,h3,h4,h5,h6")
            )
            checked += 1
        assert checked
    elif kind == "supplement_link":
        originals = [
            a
            for a in source.select("a[href]")
            if urlsplit(a["href"]).path.endswith("/s1")
            and a.find_parent("section", id=True)
        ]
        assert originals
        for a in originals:
            assert any(
                n["href"] == urljoin(fixture.source_url, a["href"])
                for n in rendered.select("a[href]")
            )
    elif kind == "equation_rows":
        from tests.support.full_read_assertions import assert_equation_rows

        assert_equation_rows(source, markdown)
    elif kind in {"email"}:
        payloads = re.findall(
            r'data-cfemail="([0-9a-f]+)"',
            " ".join(e.get("excerpt", "") for e in case["source_evidence"]),
        )
        encoded = [
            n for n in source.select("[data-cfemail]") if n["data-cfemail"] in payloads
        ]
        assert encoded
        for n in encoded:
            data = bytes.fromhex(n["data-cfemail"])
            email = bytes(v ^ data[0] for v in data[1:]).decode()
            assert email in rendered.get_text(), email
    elif kind in {"source_data_links", "url_encoding"}:
        originals = [
            a
            for a in source.select("a[href]")
            if (
                a.get_text(" ", strip=True).casefold() == "source data"
                if kind == "source_data_links"
                else "/search?" in a["href"] and " " in a["href"]
            )
        ]
        assert originals
        actual = {unquote(a["href"]) for a in rendered.select("a[href]")}
        for a in originals:
            assert urljoin(fixture.source_url, a["href"]) in actual
    elif kind == "pdf_refresh":
        import pymupdf

        with pymupdf.open(fixture.raw_path) as pdf:
            source_text = "\n".join(page.get_text() for page in pdf)
        assert "References" in source_text or "REFERENCES" in source_text
        assert re.search(r"references", markdown, re.I)
        # Verify both ends of the formerly missing source bibliography.
        anchors = {
            "FR22-022": ["Charlevoix", "Varble"],
            "FR22-201": ["de Gennes", "Zannoni"],
            "FR22-359": ["Supporting Information", "Acknowledgments"],
        }[case["id"]]
        for anchor in anchors:
            assert key(anchor) in key(source_text)
            assert key(anchor) in key(markdown)
    elif kind == "pdf_abstract":
        assert "<p" not in (article.metadata.abstract or "")
        body = article.sections[0].text
        assert body in markdown
        assert "**Abstract.**" not in markdown[: markdown.index(body)]
    elif kind == "pdf_metadata":
        import pymupdf

        with pymupdf.open(fixture.raw_path) as pdf:
            metadata = pdf.metadata
        assert article.metadata.title == metadata["title"]
        assert article.metadata.authors
        assert all(name in metadata["author"] for name in article.metadata.authors)
    elif kind == "heading_markup":
        originals = [
            h for h in source.select("h2,h3,h4,h5,h6") if h.find(["sub", "sup"])
        ]
        assert originals
        actual = rendered.select("h2,h3,h4,h5,h6")
        for h in originals:
            if key(h.get_text()) not in key(rendered.get_text()):
                continue
            matches = [n for n in actual if key(n.get_text()) == key(h.get_text())]
            assert matches, str(h)[:200]
            for tag in ["sub", "sup"]:
                for child in h.select(tag):
                    assert any(
                        key(child.get_text()) == key(n.get_text())
                        for m in matches
                        for n in m.select(tag)
                    )
    elif kind == "script_styles":
        originals = source.select("sub em, sub i, sub b, sub strong")
        assert originals
        for n in originals:
            tag = "strong" if n.name in {"b", "strong"} else "em"
            assert any(
                key(m.get_text()) == key(n.get_text())
                for m in rendered.select("sub " + tag)
            ), str(n)
    elif kind == "cell_styles":
        originals = source.select("table .ltx_font_bold")
        assert originals
        actual = {key(n.get_text()) for n in rendered.select("td strong, th strong")}
        assert {key(n.get_text()) for n in originals} <= actual
    elif kind == "algorithm":
        originals = source.select(
            "figure.ltx_float .ltx_listing, figure.ltx_algorithm .ltx_listing"
        )
        assert originals
        assert rendered.select("p")
        for listing in originals:
            for line in listing.select(".ltx_listingline"):
                text = next(
                    (
                        str(s)
                        for s in line.strings
                        if len(str(s).strip()) > 12
                        and not s.find_parent(["math", "annotation"])
                    ),
                    "",
                )
                if text:
                    assert key(text) in key(rendered.get_text())
        assert not any(
            "\\" in n.get_text() and "$" in n.get_text()
            for n in rendered.select("pre code")
        )
    elif kind in {"lists"}:
        # The helper is shared below; source scopes exclude frontmatter/UI lists.
        from tests.support.full_read_assertions import assert_article_lists

        assert_article_lists(fixture, source, rendered)
    elif kind == "abstract_hierarchy":
        abstracts = source.find_all("abstract")
        assert len(abstracts) > 1
        headings = rendered.select("h2,h3,h4,h5,h6")
        for abstract in abstracts:
            title = abstract.find("section-title", recursive=False)
            container = next(
                (
                    h
                    for h in headings
                    if key(h.get_text())
                    == key(title.get_text() if title else "Abstract")
                ),
                None,
            )
            assert container is not None
            for section in abstract.find_all("abstract-sec"):
                title = section.find("section-title", recursive=False)
                if title is not None:
                    assert any(
                        key(h.get_text()) == key(title.get_text())
                        and int(h.name[1]) > int(container.name[1])
                        for h in headings
                    )
    elif kind == "degree":
        body = source.select_one("#bodymatter") or source
        degrees = [n for n in body.select("math msup > mo") if n.get_text() == "°"]
        assert degrees
        assert markdown.count(r"\circ") >= len(degrees)
        assert not re.search(r"\\circ\s*\^", markdown)
    elif kind == "inline_math":
        if case["id"] == "FR22-448":
            values = [
                n["alttext"]
                for n in source.select("math[alttext]")
                if re.fullmatch(r"\\\$[0-9.,]+", n["alttext"])
            ]
            assert values and all(value in markdown for value in values)
            assert not re.search(r"\$\$\\\$[0-9]", markdown)
        else:
            nodes = (source.select_one("#bodymatter") or source).select(
                'math[display="inline"]'
            )
            assert nodes
            assert "No alternative text available" not in markdown
            from tests.support.canonical_content import math_identifier_text

            actual = math_identifier_text(markdown)
            for node in nodes:
                for variable in node.select("mi"):
                    assert math_identifier_text(variable.get_text()) in actual
    elif kind == "heading_once":
        headings = [
            h
            for h in rendered.select("h2,h3")
            if h.get_text().casefold()
            in {"supplementary materials", "supplementary material"}
        ]
        assert len(headings) == 1
    elif kind == "asset_paths":
        output = persisted_fixture_markdown(fixture, article)
        images = presentation(output).select("img")
        local = [
            n
            for n in images
            if not urlsplit(n["src"]).scheme and not n["src"].startswith("//")
        ]
        assert local
        base = (REPO_ROOT / case["path"]).parent
        assert all((base / unquote(n["src"])).is_file() for n in local)
    elif kind == "equation_label":
        labels = [
            n.get_text(strip=True).strip("()")
            for n in source.select("div.formula > label")
        ]
        assert labels
        for label in labels:
            assert "**Equation " + label + ".**" in markdown
    elif kind == "pseudocode":
        original = [p for p in source.select("p") if p.get_text().startswith("\u2003")]
        assert original
        actual = rendered.select("p")
        for p in original:
            count = len(p.get_text()) - len(p.get_text().lstrip("\u2003"))
            assert any(n.get_text().startswith("\u2003" * count) for n in actual)
    elif kind == "notes":
        if case["id"] == "FR22-156":
            assert_source_links(source, rendered, fixture)
            assert any(h.get_text() == "Notes" for h in rendered.select("h2,h3"))
        else:
            notes = source.select(".ltx_note_content")
            assert notes
            for note in notes:
                runs = [
                    str(t)
                    for t in note.strings
                    if len(str(t).split()) > 8
                    and not t.find_parent(["math", "annotation"])
                ]
                if not runs:
                    continue
                assert all(key(t) in key(rendered.get_text()) for t in runs)
            assert "footnotetext:" not in rendered.get_text()
    elif kind == "supplement_once":
        supplements = source.find_all("supplementary-material")
        assert supplements
        actual = [unquote(n["href"]) for n in rendered.select("a[href]")]
        for node in supplements:
            link = node.get("xlink:href") or node.get("href")
            if link:
                target = (
                    "https://doi.org/" + link.removeprefix("info:doi/")
                    if link.startswith("info:doi/")
                    else urljoin(fixture.source_url, link)
                )
                assert actual.count(target) == 1, target
                label = node.find("label")
                if label:
                    assert key(label.get_text()) in key(rendered.get_text())
    elif kind == "citation_punctuation":
        assert_source_links(source, rendered, fixture)
        visible = " ".join(rendered.get_text().split())
        for evidence in case["source_evidence"]:
            fragment = BeautifulSoup(evidence["excerpt"], "html.parser")
            assert " ".join(fragment.get_text().split()) in visible
        assert re.search(r"\(\s*<a[^>]+>.*?</a>\s*\)", str(rendered), re.S)
    elif kind == "citation_groups":
        refs = {r["id"]: r for r in source.find_all("ref") if r.get("id")}
        groups = [
            n
            for n in source.find_all("xref")
            if str(n.get("id", "")).startswith("paren.")
        ]
        assert groups
        visible = " ".join(rendered.get_text().split())
        for group in groups:
            labels = []
            for rid in group["rid"].split():
                label = refs[rid].find("label").get_text()
                short = re.match(r"^(.*?)\s*\((\d{4}[a-z]?)\)", label)
                assert short, label
                labels.append(" ".join(short[1].split()) + ", " + short[2])
            prefix = " ".join(
                n.get_text()
                for n in group.find_all("named-content", attrs={"content-type": "pre"})
            ).strip()
            expected = "(" + (prefix + " " if prefix else "") + "; ".join(labels) + ")"
            assert expected in visible, expected
    elif kind == "caption_once":
        captions = source.select(".figure-caption")
        assert captions
        from tests.support.canonical_content import source_caption_runs

        visible = key(rendered.get_text())
        for caption in captions:
            runs = [t for t in source_caption_runs(caption) if len(t.split()) > 5]
            assert runs
            for text in runs:
                assert visible.count(key(text)) == 1, text
        assert rendered.select("img")
        assert not re.search(r"(?m)^Table$", markdown)
        if case["id"] == "FR22-164":
            assert not re.search(r"(?m)^\*\*Figure \d+ .*\*\*$", markdown)
    elif kind in {"figures", "figure_order"}:
        if kind == "figures" and case["id"] != "FR22-075":
            if case["id"] in {"FR22-289", "FR22-296"}:
                fig = source.find(id="Fa")
                assert fig is not None
                for t in fig.find("figcaption").strings:
                    if len(str(t).split()) > 4 and not t.find_parent(
                        ["math", "annotation"]
                    ):
                        assert key(str(t)) in key(rendered.get_text()), str(t)
                assert rendered.select("img")
            else:
                assert_evidence_text(case, rendered)
        if kind == "figure_order":
            figures = {n["id"]: n for n in source.find_all("figure") if n.get("id")}
            anchors = [
                n for n in source.find_all("float-anchor") if n.get("refid") in figures
            ]
            assert anchors
            labels = [
                figures[n["refid"]].find("label").get_text(strip=True) for n in anchors
            ]
            images = [n["alt"] for n in rendered.select("img[alt]")]
            positions = [
                next(
                    i
                    for i, alt in enumerate(images)
                    if key(re.sub(r"^Fig\.", "Figure", alt))
                    == key(re.sub(r"^Fig\.", "Figure", label))
                )
                for label in labels
            ]
            assert positions == sorted(positions) and len(set(positions)) == len(
                positions
            )
        if case["id"] == "FR22-075":
            originals = source.select("h3 img")
            assert originals
            for n in originals:
                assert any(
                    urlsplit(m["src"]).path.rsplit("/", 1)[-1]
                    == urlsplit(n["src"]).path.rsplit("/", 1)[-1]
                    for m in rendered.select("img")
                )
    elif kind == "title_math":
        title = source.select_one("h1.ltx_title_document")
        assert title and title.select_one("math")
        for annotation in title.select("annotation"):
            annotation.decompose()
        assert key(title.get_text(" ", strip=True)) in key(rendered.h1.get_text())
    else:
        assert_evidence_text(case, rendered)


@pytest.mark.parametrize(
    "info",
    [f for f in CONTRACTS["files"] if f["scope"] == "current"],
    ids=lambda f: f["sample_id"],
)
def test_every_reviewed_baseline_matches_persisted_captured_replay(info):
    fixture = golden_corpus_fixture_for_doi(info["doi"])
    for path, digest in info["source_hashes"].items():
        assert hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest() == digest
    article = build_article_from_fixture(fixture)
    assert (
        persisted_fixture_markdown(fixture, article)
        == (REPO_ROOT / info["path"]).read_text()
    )
