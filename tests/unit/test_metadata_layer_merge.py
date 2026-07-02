from __future__ import annotations

from paper_fetch.metadata.types import MetadataMergeRule, merge_metadata_layers
from paper_fetch.providers import _arxiv_metadata, _ieee_metadata, _springer_html


def test_merge_metadata_layers_respects_field_precedence_and_default_fill_empty() -> (
    None
):
    rule = MetadataMergeRule(
        fill_empty=("title",),
        overwrite=("abstract",),
        concat_unique=("keywords",),
        take_first_non_empty=("journal_title",),
    )

    merged = merge_metadata_layers(
        [
            {
                "title": "",
                "abstract": "Base abstract",
                "journal_title": "Base Journal",
                "keywords": ["AI", "Robotics"],
                "publisher": "Base Publisher",
            },
            {
                "title": "HTML title",
                "abstract": "HTML abstract",
                "journal_title": "HTML Journal",
                "keywords": ["ai", "Vision"],
                "publisher": "HTML Publisher",
                "landing_page_url": "https://example.test/html",
            },
        ],
        rule=rule,
    )

    assert merged["title"] == "HTML title"
    assert merged["abstract"] == "HTML abstract"
    assert merged["journal_title"] == "Base Journal"
    assert merged["keywords"] == ["AI", "Robotics", "Vision"]
    assert merged["publisher"] == "Base Publisher"
    assert merged["landing_page_url"] == "https://example.test/html"


def test_merge_metadata_layers_merges_lists_by_field_rule() -> None:
    rule = MetadataMergeRule(
        overwrite=("fulltext_links",),
        concat_unique=("authors", "keywords"),
        take_first_non_empty=("license_urls",),
    )

    merged = merge_metadata_layers(
        [
            {
                "authors": ["First Author"],
                "keywords": ["AI", "Robotics"],
                "license_urls": ["https://example.test/base-license"],
                "fulltext_links": [{"url": "https://example.test/base.pdf"}],
            },
            {
                "authors": ["first author", "Second Author"],
                "keywords": ["ai", "Vision"],
                "license_urls": ["https://example.test/html-license"],
                "fulltext_links": [{"url": "https://example.test/html.pdf"}],
            },
        ],
        rule=rule,
    )

    assert merged["authors"] == ["First Author", "Second Author"]
    assert merged["keywords"] == ["AI", "Robotics", "Vision"]
    assert merged["license_urls"] == ["https://example.test/base-license"]
    assert merged["fulltext_links"] == [{"url": "https://example.test/html.pdf"}]


def test_ieee_merge_uses_landing_scalars_and_keeps_base_fallbacks() -> None:
    merged = _ieee_metadata._merge_ieee_metadata(
        {
            "doi": "10.1109/BASE.2024.1",
            "title": "Base title",
            "abstract": "Base abstract",
            "journal": "Base Journal",
            "published": "2023",
            "authors": ["Base Author"],
            "keywords": ["Random access memory", "near-data processing"],
        },
        {
            "doi": "10.1109/LANDING.2024.2",
            "formulaStrippedArticleTitle": "<span>Landing title</span>",
            "abstract": "<p>Landing abstract</p>",
            "publicationTitle": "IEEE Access",
            "publicationDate": "2024",
            "articleNumber": "10388355",
            "articleId": "10388355",
            "authors": [{"name": "Landing Author"}],
            "keywords": [
                {"kwd": ["random access memory", "edge inference"]},
            ],
            "isDynamicHtml": "true",
            "ml_html_flag": "true",
        },
        "https://ieeexplore.ieee.org/document/10388355/",
    )

    assert merged["doi"] == "10.1109/landing.2024.2"
    assert merged["title"] == "Landing title"
    assert merged["abstract"] == "Landing abstract"
    assert merged["journal_title"] == "IEEE Access"
    assert merged["published"] == "2024"
    assert merged["authors"] == ["Landing Author", "Base Author"]
    assert merged["keywords"] == [
        "Random access memory",
        "near-data processing",
        "edge inference",
    ]
    assert merged["article_number"] == "10388355"
    assert (
        merged["landing_page_url"] == "https://ieeexplore.ieee.org/document/10388355/"
    )
    assert merged["publisher"] == "IEEE"


def test_arxiv_merge_appends_html_but_api_layer_replaces_lists() -> None:
    merged = _arxiv_metadata._merge_arxiv_metadata_layers(
        {
            "source_url": "https://example.test/source",
            "arxiv_id": "2605.06663v1",
            "title": "Derived title",
            "authors": ["Derived Author"],
            "keywords": ["cs.CL"],
            "license_urls": ["https://example.test/derived-license"],
        },
        html_metadata={
            "source_url": "https://example.test/html",
            "title": "HTML title",
            "authors": ["HTML Author"],
            "keywords": ["cs.AI"],
        },
        api_metadata={
            "title": "API title",
            "authors": ["API Author"],
            "keywords": ["cs.LG"],
            "license_urls": ["https://example.test/api-license"],
        },
        references=[{"raw": "1. API reference"}],
    )

    assert merged["title"] == "API title"
    assert merged["authors"] == ["API Author"]
    assert merged["keywords"] == ["cs.LG"]
    assert merged["license_urls"] == ["https://example.test/api-license"]
    assert merged["references"] == [{"raw": "1. API reference"}]
    assert merged["doi"] == "10.48550/arxiv.2605.06663v1"
    assert "source_url" not in merged


def test_springer_merge_preserves_base_first_and_html_abstract_behavior() -> None:
    merged = _springer_html.merge_html_metadata(
        {
            "title": "Base title",
            "abstract": "Base abstract",
            "doi": "10.1007/base",
            "journal_title": "Base Journal",
            "authors": ["Li, Yang"],
            "keywords": ["AI"],
            "license_urls": ["https://example.test/base-license"],
            "fulltext_links": [{"url": "https://example.test/base.pdf"}],
            "references": [{"raw": "Base reference"}],
        },
        {
            "title": "HTML title",
            "abstract": "HTML abstract",
            "doi": "10.1007/html",
            "authors": ["Yang Li", "HTML Author"],
            "keywords": ["AI", "ML"],
            "license_urls": ["https://example.test/html-license"],
            "fulltext_links": [{"url": "https://example.test/html.pdf"}],
            "references": [{"raw": "HTML reference"}],
            "raw_meta": {"citation_title": ["HTML title"]},
            "lookup_title": "Lookup title",
        },
    )

    assert merged["title"] == "Base title"
    assert merged["abstract"] == "HTML abstract"
    assert merged["doi"] == "10.1007/base"
    assert merged["journal_title"] == "Base Journal"
    assert merged["authors"] == ["Li, Yang", "HTML Author"]
    assert merged["keywords"] == ["AI", "ML"]
    assert merged["license_urls"] == ["https://example.test/base-license"]
    assert merged["fulltext_links"] == [{"url": "https://example.test/base.pdf"}]
    assert merged["references"] == [{"raw": "Base reference"}]
    assert merged["raw_meta"] == {"citation_title": ["HTML title"]}
    assert merged["lookup_title"] == "Lookup title"
