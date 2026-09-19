from __future__ import annotations
import pytest
from tests.golden_corpus import (
    GoldenCorpusFixture,
    expected_summary_from_article,
    iter_golden_corpus_fixtures,
)
from tests.support.replay import build_article_from_fixture
from paper_fetch.provider_catalog import provider_names


GOLDEN_CORPUS_FIXTURES = iter_golden_corpus_fixtures()


def _fixture_id(fixture: GoldenCorpusFixture) -> str:
    return f"{fixture.provider}:{fixture.doi}"


def test_golden_corpus_uses_declared_providers() -> None:
    assert GOLDEN_CORPUS_FIXTURES
    assert {fixture.provider for fixture in GOLDEN_CORPUS_FIXTURES} <= set(
        provider_names()
    )


@pytest.mark.parametrize("fixture", GOLDEN_CORPUS_FIXTURES, ids=_fixture_id)
def test_golden_corpus_expected_summary_matches_current_extractor(
    fixture: GoldenCorpusFixture,
) -> None:
    article = build_article_from_fixture(fixture)
    actual = expected_summary_from_article(article)
    expected = fixture.load_expected()

    assert actual["expected_content_kind"] == "fulltext"
    assert expected["expected_content_kind"] == "fulltext"
    assert actual == {key: expected[key] for key in actual}


SOURCE_FIXTURES = [f for f in GOLDEN_CORPUS_FIXTURES if f.raw_path.suffix != ".pdf"]


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_complete_source_author_order(fixture):
    from tests.support.canonical_content import source_soup, source_authors, author_key

    soup = source_soup(fixture)
    names, selector = source_authors(fixture, soup)
    article = build_article_from_fixture(fixture)
    assert [author_key(a) for a in article.metadata.authors] == [
        author_key(a) for a in names
    ], (fixture.doi, selector, names, article.metadata.authors)


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_all_source_reference_text_and_doi(fixture, subtests):
    import re
    from tests.support.reviewed_publisher_content import _words
    from tests.support.canonical_content import (
        source_soup,
        source_references,
        source_reference_doi,
        source_reference_text,
        numeric_signature,
    )

    soup = source_soup(fixture)
    originals = source_references(fixture, soup)
    article = build_article_from_fixture(fixture)
    assert len(originals) == len(article.references), (
        fixture.doi,
        len(originals),
        len(article.references),
    )
    for index, (node, reference) in enumerate(
        zip(originals, article.references, strict=True), 1
    ):
        with subtests.test(reference=index, dimension="doi"):
            assert (reference.doi or "").lower() == (
                source_reference_doi(fixture, node) or ""
            )
        actual = re.sub(r"^(?:\d+\.|\[[^\]]+\])\s*", "", reference.raw)
        with subtests.test(reference=index, dimension="text"):
            if fixture.provider == "ieee":
                from bs4 import BeautifulSoup

                expected = BeautifulSoup(node["text"], "lxml").get_text(" ", strip=True)
            elif fixture.provider == "iop":
                for field in node["content"].split(";"):
                    key, sep, value = field.partition("=")
                    if sep and value.strip():
                        assert _words(value) in _words(actual), (key, value, actual)
                continue
            elif fixture.provider == "elsevier":
                structured = node.find("reference")
                if structured is None:
                    structured = node.find("textref") or node.find("source-text")
                assert structured is not None
                fields = structured.find_all(
                    [
                        "given-name",
                        "surname",
                        "maintitle",
                        "volume-nr",
                        "issue-nr",
                        "date",
                        "first-page",
                        "last-page",
                        "doi",
                        "edition",
                        "publisher-name",
                        "publisher-loc",
                        "name",
                        "location",
                        "article-number",
                        "comment",
                        "inter-ref",
                        "suffix",
                    ]
                )
                if fields:
                    for field in fields:
                        assert _words(field.get_text()) in _words(actual), (
                            field.name,
                            field.get_text(),
                            actual,
                        )
                    continue
                expected = structured.get_text(" ", strip=True)
                label = node.find("label")
                if label is not None:
                    suffix = "[" + label.get_text(" ", strip=True) + "]"
                    if actual.endswith(suffix):
                        actual = actual[: -len(suffix)].rstrip()
            else:
                expected = source_reference_text(fixture, node)
            assert _words(actual) == _words(expected), (
                fixture.doi,
                index,
                expected,
                actual,
            )
            assert numeric_signature(actual) == numeric_signature(expected), (
                fixture.doi,
                index,
                expected,
                actual,
            )


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_source_prose_blocks_in_order(fixture):
    from tests.support.canonical_content import source_soup, source_prose_blocks
    from tests.support.scientific_content import scientific_text_key as _words

    soup = source_soup(fixture)
    blocks = source_prose_blocks(fixture, soup)
    assert blocks
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="all"
    )
    import re

    def prose_key(text):
        return _words(re.sub(r"\bEq\.\s*\(", "Equation (", text))

    rendered = prose_key(markdown)
    cursor = 0
    for tag, runs in blocks:
        for run in runs:
            expected = prose_key(run)
            if not expected:
                continue
            position = rendered.find(expected, cursor)
            assert position >= 0, (
                fixture.doi,
                tag,
                run,
                markdown[max(0, cursor - 100) : cursor + 100],
            )
            cursor = position + len(expected)


@pytest.mark.parametrize(
    "fixture",
    [f for f in GOLDEN_CORPUS_FIXTURES if f.raw_path.suffix == ".pdf"],
    ids=_fixture_id,
)
def test_canonical_pdf_identity_and_converter_passthrough(fixture):
    from unittest import mock
    import pymupdf
    from tests import golden_corpus

    body = fixture.raw_path.read_bytes()
    with pymupdf.open(stream=body, filetype="pdf") as document:
        assert not document.needs_pass
        assert not document.is_repaired
        assert document.page_count > 0
        assert all(
            document.load_page(i).rect.width > 0 for i in range(document.page_count)
        )
    converted = []
    original = golden_corpus.pdf_fetch_result_from_bytes

    def verified(**kwargs):
        kwargs["expected_identity"] = {"doi": fixture.doi, "title": fixture.title}
        result = original(**kwargs)
        assert result.diagnostics["identity"]["status"] == "match"
        converted.append(result.markdown_text)
        return result

    with mock.patch.object(
        golden_corpus, "pdf_fetch_result_from_bytes", side_effect=verified
    ):
        article = golden_corpus.build_article_from_fixture(fixture)
    assert len(converted) == 1
    assert converted[0]
    assert article.sections[0].text == converted[0]
    assert article.references == []
    assert article.to_dict()["sections"][0]["text"] == converted[0]
    assert converted[0] in article.to_ai_markdown(
        include_refs="all", max_tokens="full_text"
    )


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_source_table_cells(fixture, subtests):
    from tests.support.canonical_content import (
        source_soup,
        source_tables,
        source_prose_blocks,
    )
    from tests.support.object_content import assert_source_tables

    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    soup = source_soup(fixture)
    prose_runs = [run for _, runs in source_prose_blocks(fixture, soup) for run in runs]
    assert_source_tables(
        source_tables(fixture, soup),
        markdown,
        subtests,
        prose_runs=prose_runs,
        provider=fixture.provider,
    )


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_all_source_figure_captions(fixture, subtests):
    from tests.support.canonical_content import (
        source_soup,
        source_figures,
        source_caption_runs,
    )
    from tests.support.scientific_content import scientific_text_key as _words

    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    rendered = _words(markdown)
    for index, (figure, caption) in enumerate(
        source_figures(fixture, source_soup(fixture)), 1
    ):
        with subtests.test(figure=figure.get("id", index)):
            cursor = 0
            for run in source_caption_runs(caption):
                expected = _words(run)
                if not expected:
                    continue
                position = rendered.find(expected, cursor)
                assert position >= 0, (fixture.doi, index, run)
                cursor = position + len(expected)

    from tests.support.object_content import assert_figure_bindings

    assert_figure_bindings(fixture, source_soup(fixture), article, markdown)


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_source_table_notes_and_retained_statements(fixture, subtests):
    from tests.support.canonical_content import (
        source_soup,
        source_table_notes,
        source_statements,
        source_caption_runs,
    )
    from tests.support.scientific_content import scientific_text_key as _words

    soup = source_soup(fixture)
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    rendered = _words(markdown)
    for kind, nodes in [
        ("table_note", source_table_notes(fixture, soup)),
        ("statement", source_statements(fixture, soup)),
    ]:
        for index, node in enumerate(nodes, 1):
            with subtests.test(kind=kind, index=index):
                cursor = 0
                for run in source_caption_runs(node):
                    expected = _words(run)
                    if not expected:
                        continue
                    position = rendered.find(expected, cursor)
                    assert position >= 0, (fixture.doi, kind, index, run)
                    cursor = position + len(expected)


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_source_tex_formulas_preserve_structure(fixture, subtests):
    from tests.support.canonical_content import (
        source_soup,
        source_formulas,
        source_tex,
        tex_key,
    )

    article = build_article_from_fixture(fixture)
    rendered = tex_key(
        article.to_ai_markdown(
            include_refs="all", asset_profile="all", max_tokens="full_text"
        )
    )
    for index, node in enumerate(source_formulas(fixture, source_soup(fixture)), 1):
        tex = source_tex(node)
        if not tex:
            continue
        with subtests.test(formula=index):
            assert tex_key(tex) in rendered, (fixture.doi, index, tex)


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_mathml_numeric_and_structural_facts(fixture, subtests):
    from tests.support.canonical_content import (
        source_soup,
        source_formulas,
        formula_route,
    )
    from tests.support.scientific_content import assert_mathml_formulas

    nodes = source_formulas(fixture, source_soup(fixture))
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    checked = assert_mathml_formulas(nodes, markdown, subtests)
    assert checked == sum(formula_route(n) == "mathml" for n in nodes)


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_rendered_images_have_original_source_identity(fixture, subtests):
    import html
    import re
    from urllib.parse import unquote, urlsplit
    from tests.support.canonical_content import (
        source_soup,
        source_figures,
        source_figure_markup,
    )

    raw = unquote(html.unescape(fixture.raw_path.read_text())).lower()
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    image_origins = []
    for index, (label, url) in enumerate(
        re.findall(r"!\[([^\]]*)\]\(([^\s)]+)\)", markdown), 1
    ):
        with subtests.test(image=index, label=label):
            url = unquote(html.unescape(url)).lower()
            asset = next(
                (
                    a
                    for a in article.assets
                    if unquote(str(a.path or a.url or "")).lower() == url
                ),
                None,
            )
            origins = [url]
            if asset is not None:
                origins += [
                    str(asset.original_url or ""),
                    str(asset.source_href or ""),
                    str(asset.download_url or ""),
                ]

            image_origins.extend(origins)

            def bound(origin, raw_scope=raw):
                if fixture.provider == "plos":
                    from tests.support.object_content import image_matches_source

                    if image_matches_source(origin, None, raw_scope, "plos"):
                        return True
                origin = unquote(html.unescape(origin)).lower()
                filename = urlsplit(origin).path.rsplit("/", 1)[-1]
                if origin and (
                    origin in raw_scope
                    or (
                        re.search(r"\.(?:png|jpe?g|gif|webp|svg|tiff?)$", filename)
                        and filename in raw_scope
                    )
                ):
                    return True
                # Frontiers XML graphics name the same image without its
                # negotiated raster extension; the exact stem is authoritative.
                if fixture.provider == "frontiers" and filename:
                    return filename.rsplit(".", 1)[0] in raw_scope
                return False

            assert any(bound(origin) for origin in origins), (
                fixture.doi,
                label,
                origins,
            )

    for index, (figure, _caption) in enumerate(
        source_figures(fixture, source_soup(fixture)), 1
    ):
        if figure.find(["img", "graphic"]) is None:
            continue
        with subtests.test(source_figure=figure.get("id", index)):
            original = unquote(
                html.unescape(
                    source_figure_markup(fixture, figure, source_soup(fixture))
                )
            ).lower()
            assert image_origins and any(
                bound(origin, original) for origin in image_origins
            ), (fixture.doi, index, "no image link for captured figure")


@pytest.mark.parametrize("fixture", SOURCE_FIXTURES, ids=_fixture_id)
def test_canonical_source_citations_resolve_to_ordered_references(fixture, subtests):
    from tests.support.canonical_content import (
        source_soup,
        source_citation_targets,
        source_references,
        source_reference_doi,
    )

    soup = source_soup(fixture)
    originals = source_references(fixture, soup)
    article = build_article_from_fixture(fixture)
    for link, index, target in source_citation_targets(fixture, soup):
        with subtests.test(target=target, callout=link.get_text(" ", strip=True)):
            assert index < len(article.references)
            assert (article.references[index].doi or "").lower() == (
                source_reference_doi(fixture, originals[index]) or ""
            )
            assert article.references[index].raw


def test_canonical_review_register_covers_exact_corpus():
    from tests.paths import REPO_ROOT

    rows = [
        fixture.load_expected()["source_review"] for fixture in GOLDEN_CORPUS_FIXTURES
    ]
    assert len(rows) == len(GOLDEN_CORPUS_FIXTURES)
    by_id = {row["sample_id"]: row for row in rows}
    assert len(by_id) == len(rows)
    assert set(by_id) == {fixture.sample_id for fixture in GOLDEN_CORPUS_FIXTURES}
    for fixture in GOLDEN_CORPUS_FIXTURES:
        row = by_id[fixture.sample_id]
        assert row["doi"] == fixture.doi
        assert REPO_ROOT / row["original"] == fixture.raw_path
        assert row["limitations"]
        assert row["dimensions"]
        for dimension in row["dimensions"].values():
            assert dimension["test"].split("::")[1] in globals()


@pytest.mark.parametrize("fixture", GOLDEN_CORPUS_FIXTURES, ids=_fixture_id)
def test_canonical_registered_source_counts_and_hash(fixture):
    import hashlib
    from tests.support.canonical_content import (
        source_soup,
        source_authors,
        source_references,
        source_prose_blocks,
        source_tables,
        source_table_grid,
        source_figures,
        source_table_notes,
        source_statements,
        source_formulas,
        formula_route,
    )

    row = fixture.load_expected()["source_review"]
    assert hashlib.sha256(fixture.raw_path.read_bytes()).hexdigest() == row["sha256"]
    if fixture.raw_path.suffix == ".pdf":
        import pymupdf

        with pymupdf.open(fixture.raw_path) as doc:
            assert len(doc) == row["pdf"]["pages"]
        return
    soup = source_soup(fixture)
    counts = {
        "authors": len(source_authors(fixture, soup)[0]),
        "references": len(source_references(fixture, soup)),
        "prose": len(source_prose_blocks(fixture, soup)),
        "figures": len(source_figures(fixture, soup)),
        "tables": sum(
            len(cells)
            for table in source_tables(fixture, soup)
            for _, cells in source_table_grid(table)
        ),
        "notes_and_statements": len(source_table_notes(fixture, soup))
        + len(source_statements(fixture, soup)),
    }
    assert counts == {key: row["dimensions"][key]["source_count"] for key in counts}

    from collections import Counter

    formulas = source_formulas(fixture, soup)
    routes = Counter(formula_route(n) for n in formulas)
    assert row["formula_audit"] == {
        "selected": len(formulas),
        "tex_checked": routes["tex"],
        "mathml_checked": routes["mathml"],
        "empty_excluded": routes["empty"],
    }
    assert sum(routes.values()) == len(formulas)
    assert row["dimensions"]["tex"]["source_count"] == routes["tex"]
    assert row["dimensions"]["mathml"]["source_count"] == routes["mathml"]
