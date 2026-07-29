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
