"""November audit: final persisted output and immutable source identities."""

import hashlib
import json
import os
import re
import subprocess
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pytest

from paper_fetch.models.markdown import iter_markdown_images
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample
from tests.support.replay import build_article_from_fixture, persisted_fixture_markdown
from tests.paths import REPO_ROOT

CURRENT = [
    "10.1016_j.edumed.2018.09.002",
    "10.1021_acsomega.3c06992",
    "10.1021_acsomega.4c03987",
    "10.1029_2004gb002273",
    "10.1038_nature12915",
    "10.1038_nature13376",
    "10.1038_s41612-021-00218-2",
    "10.1063_1.39658",
    "10.1063_5.0188905",
    "10.1073_pnas.2317456120",
    "10.1088_1681-7575_ae1dfc",
    "10.1088_1748-9326_ab7d02",
    "10.1088_2058-9565_ac3460",
    "10.1093_bioinformatics_btaa823",
    "10.1109_CICTN64563.2025.10932570",
    "10.1109_RITA.2026.3668995",
    "10.1109_TBME.2024.3434477",
    "10.1109_TCOMM.2024.3395332",
    "10.1109_TDEI.2024.3373549",
    "10.1109_TIM.2024.3509573",
    "10.1111_cas.16395",
    "10.1111_gcb.15322",
    "10.1111_gcb.16011",
    "10.1111_gcb.16386",
    "10.1111_gcb.16414",
    "10.1111_gcb.16455",
    "10.1111_gcb.16561",
    "10.1111_gcb.16745",
    "10.1111_gcb.16758",
    "10.1111_gcb.16998",
    "10.1111_gcb.17141",
    "10.1126_science.adz3492",
    "10.1371_journal.pcbi.1003118",
    "10.3389_fmars.2023.1101972",
    "10.3389_fpls.2020.01216",
    "10.3390_ijerph18094484",
    "10.3390_s23010001",
]


@pytest.mark.parametrize("sample_id", CURRENT)
def test_audited_current_output_is_persisted_and_links_are_portable(
    sample_id, tmp_path
):
    fixture = golden_corpus_fixture_for_doi(golden_criteria_sample(sample_id)["doi"])
    article = build_article_from_fixture(fixture)
    markdown = persisted_fixture_markdown(fixture, article)
    baseline = golden_criteria_asset(fixture.doi, "extracted.md")
    output = tmp_path / "article.md"
    output.write_text(markdown)
    assert output.read_bytes() == baseline.read_bytes()
    if fixture.route_kind != "pdf_fallback":
        assert "javascript:" not in markdown
    html = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(markdown), "lxml"
    )
    local_ids = {n["id"] for n in html.select("[id]")}
    for anchor in (
        [] if fixture.route_kind == "pdf_fallback" else html.select("a[href]")
    ):
        href = anchor["href"]
        assert not href.startswith("/"), href
        if href.startswith("#"):
            assert href[1:] in local_ids, href
    if fixture.provider == "ieee":
        soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
        originals = soup.select("div.figure.figure-full.table")
        expected = [
            re.search(r"TABLE\s+([IVXLCDM]+|\d+)", n.get_text(" "), re.I)[1]
            for n in originals
        ]
        actual = [
            i.alt.removeprefix("Table ")
            for i in iter_markdown_images(markdown)
            if i.alt.startswith("Table ")
        ]
        assert actual == expected
    if sample_id == "10.1093_bioinformatics_btaa823":
        soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
        calls = [
            a
            for a in soup.select("table a[data-open]")
            if str(a.get("href", "")).startswith("javascript:")
        ]
        assert len(calls) == 20
        for call in calls:
            note = soup.find(class_="footnote", attrs={"content-id": call["data-open"]})
            target = note.find_previous_sibling()["id"]
            assert f"{fixture.source_url}#{target}" in markdown
    if sample_id == "10.1126_science.adz3492":
        soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
        for anchor in soup.select('a[data-xml-rid][href^="#core-collateral-"]'):
            assert f"{fixture.source_url}#{anchor['data-xml-rid']}" in markdown
    if sample_id == "10.1073_pnas.2317456120":
        assert "> The study quantifies" in markdown
        assert "&gt; The study quantifies" not in markdown
    if sample_id == "10.1016_j.edumed.2018.09.002":
        for number in range(1, 4):
            assert f"![Figura {number}]" in markdown
            assert f"**Figura {number}.**" in markdown
    if fixture.provider == "frontiers":
        count = 6 if "fpls" in sample_id else 1
        assert markdown.count("## Supplementary") == 1
        for number in range(1, count + 1):
            assert markdown.count(f"[Table_{number}.docx]") == 1
        if count == 1:
            assert "public-pages-files-2025.frontiersin.org" in markdown
    if sample_id == "10.1063_1.39658":
        assert article.metadata.title == "High throughput x-ray astronomy"
        assert 'title: "High throughput x-ray astronomy"' in markdown
        assert "# High throughput x-ray astronomy\n" in markdown
        # The converter's complete body is retained byte for byte.
        expected = json.loads(
            golden_criteria_asset(fixture.doi, "expected.json").read_text()
        )
        body = markdown.split("# High throughput x-ray astronomy\n", 1)[1]
        assert hashlib.sha256(body.encode()).hexdigest() == expected["pdf_body_sha256"]


@pytest.mark.parametrize(
    "doi,count",
    [
        ("10.1021/acsomega.3c06992", 8),
        ("10.1021/acsomega.4c03987", 10),
        ("10.1063/5.0188905", 6),
    ],
)
def test_all_24_signed_images_match_saved_source_objects(doi, count):
    from tests.support.acquired_publisher_inputs import capture_url_identity

    fixture = golden_corpus_fixture_for_doi(doi)
    article = build_article_from_fixture(fixture)
    markdown = persisted_fixture_markdown(fixture, article)
    baseline = golden_criteria_asset(doi, "extracted.md")
    images = list(iter_markdown_images(markdown))
    assert len(images) == count
    provenance = json.loads(
        golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
    )

    def identity(url):
        return capture_url_identity(url, provider=fixture.provider)

    records = provenance["records"]
    for image in images:
        assert not urlsplit(image.url).scheme
        path = (baseline.parent / image.url).resolve()
        assert path.is_file()
        asset = next(
            a
            for a in article.assets
            if a.path and (REPO_ROOT / a.path).resolve() == path
        )
        record = next(
            r
            for r in records
            if golden_criteria_asset(doi, r["body_file"]).resolve() == path
            and identity(asset.download_url)
            in {identity(r.get(k, "")) for k in ("requested_url", "final_url")}
        )
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]


def test_acs_wide_table_keeps_all_source_rows_under_one_number():
    fixture = golden_corpus_fixture_for_doi("10.1021/acsomega.3c06992")
    source = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
    wrapper = source.find(id="tbl2").find_parent(class_="table-wrap")
    from paper_fetch.providers._acs_html import render_acs_table
    from paper_fetch.extraction.html.tables import render_table_inline_text

    markdown = render_acs_table(wrapper, label="Table 2.", caption="Source caption")
    tokens = MarkdownIt().enable("table").parse(markdown)
    cells = [
        tokens[i + 1].content
        for i, token in enumerate(tokens[:-1])
        if token.type == "td_open"
    ]
    expected = []
    visible = [t for t in wrapper.select("table") if not t.get("aria-hidden")]
    for table in visible:
        for cell in table.select("tbody td"):
            expected.append(render_table_inline_text(cell))
    assert cells == expected
    assert markdown.count("**Table 2.**") == 1
    for table in visible:
        for span in table.select("thead th[colspan]"):
            expression = render_table_inline_text(span)
            if expression:
                assert markdown.count(expression) == 1


def _historical_html(doi):
    fixture = golden_corpus_fixture_for_doi(doi)
    paths = {
        "10.1021/jacs.6c10062": "acquisition/current-19-2026-09-18/001-browser_rendered_dom.html",
        "10.1088/1681-7575/ae1dfc": "acquisition/fulltext-baselines-2026-10-21/service-001-browser_rendered_dom.html",
    }
    key = paths.get(doi)
    if key is None:
        key = next(
            k
            for k in fixture.sample["assets"]
            if "official-reacquisition-2026-09-19/raw_sources/" in k
            and k.endswith(".html")
        )
    return fixture, golden_criteria_asset(doi, key).read_text()


def test_historical_acs_multiline_title_and_sections_are_complete():
    from paper_fetch.providers.acs import AcsClient
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    fixture, source = _historical_html("10.1021/jacs.6c10062")
    soup = BeautifulSoup(source, "lxml")
    client = AcsClient(FixtureHtmlTransport({}), {})
    metadata = {"doi": fixture.doi}
    markdown, extraction = client.extract_markdown(
        source, fixture.source_url, metadata=metadata
    )
    article = client.to_article_model(
        metadata,
        RawFulltextPayload(
            provider="acs",
            content=ProviderContent(
                route_kind="html",
                source_url=fixture.source_url,
                content_type="text/html",
                body=source.encode(),
                markdown_text=markdown,
                merged_metadata=metadata,
                diagnostics={"extraction": extraction},
            ),
        ),
    )
    rendered = article.to_ai_markdown(max_tokens="full_text")
    assert "# " + " ".join(soup.h1.get_text(" ", strip=True).split()) + "\n" in rendered
    for heading in soup.select("h2, h3, h4"):
        text = " ".join(heading.get_text(" ", strip=True).split())
        if text.startswith(("Preparation", "Cation-Dependent")):
            assert any(
                line.startswith("#") and text in line for line in rendered.splitlines()
            )


@pytest.mark.parametrize(
    "doi",
    [
        "10.48550/arxiv.1406.2661v1",
        "10.48550/arxiv.2605.06659v1",
        "10.48550/arxiv.2605.06667v1",
        "10.1088/1681-7575/ae1dfc",
    ],
)
def test_historical_math_replays_from_html_in_current_reader(doi, tmp_path):
    reader = os.environ.get("PAPER_FETCH_REVIEW_READER_ROOT")
    if not reader:
        pytest.skip("requires explicitly selected installed LitRoot")
    fixture, source = _historical_html(doi)
    if fixture.provider == "arxiv":
        from paper_fetch.providers._arxiv_html import _extract_arxiv_html_markdown

        extracted = _extract_arxiv_html_markdown(
            source,
            "https://arxiv.org/html/" + doi.split("arxiv.")[1],
            metadata={"doi": doi},
        )
        markdown = extracted.markdown_text
    else:
        from paper_fetch.providers.iop import IopClient
        from tests.support._paper_fetch_support import FixtureHtmlTransport

        markdown, _ = IopClient(FixtureHtmlTransport({}), {}).extract_markdown(
            source, fixture.source_url, metadata={"doi": doi}
        )
    presentation = BeautifulSoup(
        MarkdownIt("commonmark", {"html": True}).render(markdown), "lxml"
    )
    assert not any("$" in code.get_text() for code in presentation.select("pre code"))
    output = tmp_path / "replayed.md"
    output.write_text(markdown)
    result = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "scripts/review_markdown_math.mjs"),
            "--modules-root",
            reader,
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr or result.stdout[-2000:]
    report = json.loads(result.stdout)["files"][0]
    assert report["formulas"] > 0 and not report["errors"]


def test_historical_emo_decorative_icons_do_not_split_the_resource_table():
    from paper_fetch.providers._arxiv_html import _extract_arxiv_html_markdown

    fixture, source = _historical_html("10.48550/arxiv.2605.06663v1")
    soup = BeautifulSoup(source, "lxml")
    icons = [
        image
        for image in soup.select("img")
        if image.get("src", "").endswith(("blog.png", "search.png"))
    ]
    assert len(icons) == 2
    extracted = _extract_arxiv_html_markdown(
        source, "https://arxiv.org/html/2605.06663v1", metadata={"doi": fixture.doi}
    )
    markdown = extracted.markdown_text
    images = list(iter_markdown_images(markdown))
    assert not any(image.url.endswith(("blog.png", "search.png")) for image in images)
    for icon in icons:
        links = icon.find_parent("tr").select("a[href]")
        assert links
        for link in links:
            assert link["href"] in markdown
    assert not any(line.strip() == "|" for line in markdown.splitlines())


def test_saved_plos_xml_tables_appear_once_and_reference_names_keep_spacing():
    from paper_fetch.providers.plos import parse_plos_xml

    for doi in ["10.1371/journal.pcbi.1003118", "10.1371/journal.pbio.0040298"]:
        source = golden_criteria_asset(
            doi, "acquisition/source-completion-2026-09-18/001-http_response_entity.xml"
        ).read_bytes()
        soup = BeautifulSoup(source, "xml")
        extracted = parse_plos_xml(
            source, source_url="https://journals.plos.org/article/file?id=" + doi
        )
        assert extracted is not None
        for table in soup.select("table-wrap"):
            label = table.find("label").get_text(" ", strip=True)
            assert extracted.markdown_text.splitlines().count(label) == 1
        for original, reference in zip(
            soup.select("ref-list > ref"), extracted.references, strict=True
        ):
            for name in original.select("name"):
                expected = " ".join(
                    " ".join(n.get_text(strip=True).split())
                    for n in name.find_all(recursive=False)
                )
                assert expected in reference["raw"]
