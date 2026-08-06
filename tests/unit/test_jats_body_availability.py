from __future__ import annotations

import pytest

from paper_fetch.providers._article_markdown_jats import (
    assess_jats_body_availability,
    parse_jats_xml,
)
from paper_fetch.quality.reason_codes import (
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
)


def _jats(*, article_type: str = "research-article", body: str = "") -> bytes:
    return f"""
<article article-type="{article_type}">
  <front>
    <journal-meta><journal-title>Example Journal</journal-title></journal-meta>
    <article-meta>
      <article-id pub-id-type="doi">10.1234/example</article-id>
      <title-group><article-title>Example article</article-title></title-group>
      <abstract><p>This abstract must not count as body prose.</p></abstract>
    </article-meta>
  </front>
  {body}
  <back>
    <ref-list>
      <ref><mixed-citation>A reference that must not count as body prose.</mixed-citation></ref>
    </ref-list>
  </back>
</article>
""".encode()


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("", STRUCTURED_MISSING_BODY_SECTIONS),
        ("<body/>", STRUCTURED_MISSING_BODY_SECTIONS),
        (
            "<body><sec><title>References</title></sec></body>",
            STRUCTURED_MISSING_BODY_SECTIONS,
        ),
        (
            "<body><sec><p>Too short for a research article.</p></sec></body>",
            STRUCTURED_ARTICLE_NOT_FULLTEXT,
        ),
    ],
)
def test_jats_abstract_references_and_empty_body_do_not_satisfy_fulltext(
    body: str,
    reason: str,
) -> None:
    extraction = parse_jats_xml(_jats(body=body))
    assert extraction is not None

    availability = assess_jats_body_availability(
        extraction,
        min_body_chars=1200,
    )

    assert availability.accepted is False
    assert availability.reason == reason
    assert availability.body_char_count < 1200


def test_jats_normal_body_meets_provider_threshold() -> None:
    body_text = " ".join(["Substantive methods results and discussion prose."] * 35)
    extraction = parse_jats_xml(
        _jats(body=f"<body><sec><title>Results</title><p>{body_text}</p></sec></body>")
    )
    assert extraction is not None

    availability = assess_jats_body_availability(
        extraction,
        min_body_chars=1200,
    )

    assert availability.accepted is True
    assert availability.short_article_policy is False
    assert availability.reason == "structured_body_sections"


def test_jats_explicit_editorial_uses_short_body_policy() -> None:
    body_text = " ".join(["Editorial body prose."] * 10)
    extraction = parse_jats_xml(
        _jats(
            article_type="editorial",
            body=f"<body><p>{body_text}</p></body>",
        )
    )
    assert extraction is not None

    availability = assess_jats_body_availability(
        extraction,
        min_body_chars=1200,
    )

    assert availability.accepted is True
    assert availability.short_article_policy is True
    assert availability.min_body_chars == 120
    assert availability.reason == "structured_short_article_body"


def test_jats_cals_tgroups_render_as_independent_ordered_grids() -> None:
    extraction = parse_jats_xml(
        _jats(
            body="""
<body><sec><title>Results</title>
  <table-wrap id="t1">
    <label>Table 1</label>
    <caption><p>Grouped measurements.</p></caption>
    <table>
      <tgroup cols="2">
        <colspec colname="a1"/><colspec colname="a2"/>
        <thead>
          <row><entry namest="a1" nameend="a2">(a) WBGT</entry></row>
          <row><entry colname="a1">Day</entry><entry colname="a2">Risk</entry></row>
        </thead>
        <tbody><row><entry colname="a1">1</entry><entry colname="a2">Low</entry></row></tbody>
      </tgroup>
      <tgroup cols="3">
        <colspec colname="b1"/><colspec colname="b2"/><colspec colname="b3"/>
        <thead>
          <row><entry namest="b1" nameend="b3">(b) T</entry></row>
          <row><entry colname="b1">Day</entry><entry colname="b2">Min</entry><entry colname="b3">Max</entry></row>
        </thead>
        <tbody><row><entry colname="b1">2</entry><entry colname="b2">10</entry><entry colname="b3">20</entry></row></tbody>
      </tgroup>
    </table>
    <table-wrap-foot><p>Source note.</p></table-wrap-foot>
  </table-wrap>
</sec></body>
"""
        )
    )

    assert extraction is not None
    markdown = extraction.markdown_text
    assert markdown.count("Table 1") == 1
    assert markdown.count("Grouped measurements.") == 1
    assert markdown.count("Source note.") == 1
    assert markdown.index("(a) WBGT") < markdown.index("| Day")
    assert markdown.index("(b) T") < markdown.rindex("| Day")
    assert "| 1" in markdown
    assert "| 2" in markdown
    assert extraction.semantic_losses.table_fallback_count == 0
    assert extraction.semantic_losses.table_layout_degraded_count == 0
