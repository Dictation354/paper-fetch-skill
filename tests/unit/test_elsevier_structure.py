"""Small XML structural contracts, independent of article text or ids."""

from pathlib import Path
import pytest

from paper_fetch.providers._article_markdown_elsevier_document import (
    build_article_structure,
)
from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers.elsevier import ElsevierClient
from paper_fetch.providers._article_markdown_elsevier import render_elsevier_blocks
from paper_fetch.xml_security import parse_xml
from paper_fetch.models.markdown import normalize_markdown_text
from tests.support.markdown_lists import ancestor, inline_text, markdown_tree


def test_xml_section_labels_are_direct_and_never_inferred_or_repeated():
    root = parse_xml(b"""<sections><section><label>8.</label><section-title>Overview</section-title>
    <section><label>8.2.</label><section-title>Results</section-title><para>First.</para></section>
    <section><label>8.3.</label><section-title>8.3. Discussion</section-title><para>Second.</para></section>
    <section><section-title>Unnumbered</section-title><para>Third.</para></section>
    </section></sections>""")
    markdown = "\n".join(render_elsevier_blocks(root, heading_level=2))
    assert "## 8. Overview" in markdown
    assert "### 8.2. Results" in markdown
    assert "### 8.3. Discussion" in markdown
    assert "8.3. 8.3." not in markdown
    assert "### Unnumbered" in markdown


@pytest.mark.parametrize("label,marker", [("(1)", "- (1)"), ("99.", "99.")])
def test_xml_list_blocks_keep_parent_and_marker_width(label, marker):
    root = parse_xml(
        f"""<section><list><list-item><label>{label}</label><para>First step.</para>
    <para>Second paragraph.</para><formula><tex-math>x=1</tex-math></formula>
    <display><figure id="figure-new"/></display>
    <list><list-item><para>Nested step.</para></list-item></list>
    </list-item><list-item><label>{label}</label><para>Following step.</para></list-item></list></section>""".encode()
    )
    markdown = normalize_markdown_text(
        "\n".join(
            render_elsevier_blocks(
                root,
                heading_level=2,
                figure_lookup={
                    "figure-new": {
                        "key": "new",
                        "heading": "Figure 1",
                        "caption": "Original caption.",
                        "link": "figure.png",
                    }
                },
            )
        )
    )
    assert markdown.startswith(marker + " First step.")
    tree = markdown_tree(markdown)
    items = [n for n in tree.children[0].children if n.type == "list_item"]
    assert len(items) == 2
    assert "Following step." in inline_text(items[1])
    first = inline_text(items[0])
    assert "Second paragraph." in first and "x=1" in first
    assert "Original caption." in first and "Nested step." in first
    images = [n for n in tree.walk() if n.type == "image"]
    assert len(images) == 1 and ancestor(images[0], "list_item") is items[0]


def test_declarations_across_head_body_tail_preserve_order_without_duplicates():
    xml = b"""<article><head><data-availability id="changed"><section-title>Access statement</section-title><para>Head statement.</para></data-availability></head>
    <body><sections><section><section-title>Observations</section-title><para>Body observation.</para>
    <conflict-of-interest><section-title>Author disclosure</section-title><para>Body disclosure.</para></conflict-of-interest></section></sections></body>
    <tail><conflict-of-interest><section-title>Disclosure in tail</section-title><para>Tail disclosure.</para>
    <data-availability><section-title>Nested statement</section-title><para>Nested data.</para></data-availability></conflict-of-interest>
    <acknowledgment><section-title>Thanks</section-title><para>Final acknowledgment.</para></acknowledgment></tail></article>"""
    structure = build_article_structure(
        provider="elsevier",
        metadata={},
        xml_body=xml,
        xml_path=Path("article.xml"),
        assets=[],
    )
    markdown = "\n".join(structure.body_lines)
    paragraphs = [
        "Head statement.",
        "Body observation.",
        "Body disclosure.",
        "Tail disclosure.",
        "Nested data.",
        "Final acknowledgment.",
    ]
    assert [markdown.index(p) for p in paragraphs] == sorted(
        markdown.index(p) for p in paragraphs
    )
    assert all(markdown.count(p) == 1 for p in paragraphs)


def test_xml_keywords_and_graphical_abstract_reach_final_article():
    xml = b"""<article><head><keywords><section-title>Keywords</section-title><keyword><text>Canopy</text></keyword><keyword><text>Water flux</text></keyword></keywords>
    <abstract class="author"><abstract-sec><simple-para>Textual finding.</simple-para></abstract-sec></abstract>
    <abstract class="graphical"><section-title>Graphical abstract</section-title><abstract-sec><simple-para><display><figure id="changed-figure"><link locator="ga9"/></figure></display></simple-para></abstract-sec></abstract>
    </head><body><sections><section><section-title>Results</section-title><para>A measured result.</para></section></sections></body></article>"""
    raw = build_provider_payload(
        provider="elsevier",
        route_kind="official",
        source_url="https://api.elsevier.com/example",
        content_type="text/xml",
        body=xml,
    )
    client = ElsevierClient(None, {})
    article = client.to_article_model(
        {"doi": "10.1016/example", "keywords": ["Canopy", "Existing"]},
        raw,
        downloaded_assets=[
            {
                "source_ref": "ga9",
                "asset_type": "graphical_abstract",
                "url": "https://ars.els-cdn.com/ga9.jpg",
                "source_url": "https://ars.els-cdn.com/ga9.jpg",
            }
        ],
    )
    markdown = article.to_ai_markdown(max_tokens="full_text", asset_profile="all")
    assert article.metadata.keywords == ["Canopy", "Existing", "Water flux"]
    assert len(article.assets) == 1
    assert article.assets[0].section == "abstract"
    assert article.assets[0].render_state == "inline"
    assert markdown.count("https://ars.els-cdn.com/ga9.jpg") == 1
    assert markdown.index("ga9.jpg") < markdown.index("## Results")
    assert "Additional Figures" not in markdown
    assert all(
        "ga9.jpg" not in section.text
        for section in article.sections
        if section.kind == "body"
    )
