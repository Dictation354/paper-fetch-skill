from dataclasses import asdict

import pytest

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.metadata.crossref import CrossrefLookupClient
from paper_fetch.metadata.types import merge_primary_secondary_metadata
from paper_fetch.models.builders import build_metadata
from paper_fetch.models.codec import metadata_from_payload
from paper_fetch.publication_dates import citation_date, publication_years
from paper_fetch.resolve.query import (
    StructuredResolveRequest,
    _author_match_score,
    score_candidates,
)


@pytest.mark.parametrize(
    "requested,candidate,score",
    [
        (["Yong Hu"], ["Yong Hu"], 1.0),
        (["Hu, Yong"], ["Yong Hu"], 1.0),
        (["Y. Hu"], ["Yong Hu"], 0.8),
        (["Hu"], ["Yong Hu"], 0.5),
        (["Yong Hu"], ["Yang Hu"], 0.0),
        (["Y. Hu", "Yong Hu"], ["Yong Hu"], 0.5),
        (["Y. Hu", "Yong Hu"], ["Yong Hu", "Yang Hu"], 0.9),
    ],
)
def test_author_evidence_is_weighted_and_one_to_one(requested, candidate, score):
    assert _author_match_score(tuple(requested), {"authors": candidate}) == score


def test_multiple_upstream_dates_and_relations_survive_merge_codec_and_scoring():
    metadata = CrossrefLookupClient(None, {}).normalize_message(
        {
            "DOI": "10.1000/correction",
            "title": ["Satellite response"],
            "type": "correction",
            "published-online": {"date-parts": [[2024, 12, 1]]},
            "published-print": {"date-parts": [[2025, 1]]},
            "issued": {"date-parts": [[2025]]},
            "created": {"date-parts": [[2023, 9, 1]]},
            "relation": {
                "is-correction-of": [{"id-type": "doi", "id": "10.1000/ORIGINAL"}]
            },
            "update-to": [
                {
                    "DOI": "10.1000/ORIGINAL",
                    "type": "correction",
                    "updated": {"date-parts": [[2025]]},
                }
            ],
        },
        source_url="https://api.crossref.org/works/10.1000/correction",
    )
    html = parse_html_metadata(
        '<meta name="citation_online_date" content="2024-12-02">',
        "https://example.org/paper",
    )
    merged = merge_primary_secondary_metadata(html, metadata)
    assert len(merged["publication_dates"]) == 5
    assert citation_date(merged["publication_dates"]) == "2025-1"
    assert publication_years(merged["publication_dates"]) == {2024, 2025}
    model = build_metadata(merged)
    assert metadata_from_payload(asdict(model)) == model
    assert "published" not in asdict(model)
    assert model.relations[0]["kind"] == "is-correction-of"
    candidates = score_candidates(
        StructuredResolveRequest(title="Satellite response", year=2025), [metadata]
    )
    assert candidates[0]["article_type"] == "correction"
    assert candidates[0]["relations"] == metadata["relations"]
    assert candidates[0]["update_to"] == metadata["update_to"]
    assert candidates[0]["year_score"] == 1.0
    assert (
        score_candidates(
            StructuredResolveRequest(title="Satellite response", year=2023), [metadata]
        )[0]["year_score"]
        == 0.5
    )


def test_created_alone_is_not_a_publication_year_and_unknown_dates_stay_empty():
    assert (
        publication_years(
            [{"kind": "created", "value": "2025", "source": "crossref:created"}]
        )
        == set()
    )
    assert build_metadata({}).publication_dates == []


def test_html_keeps_multiple_actual_dates_without_guessing_print_kind():
    from paper_fetch.extraction.html._metadata import merge_html_metadata

    metadata = parse_html_metadata(
        """
        <meta name="citation_publication_date" content="2025-01-01">
        <meta name="citation_online_date" content="2024-12-01">
        <meta name="citation_online_date" content="2024-12-02">
        <meta name="dc.date.created" content="2023-11-01">
    """,
        "https://example.org/paper",
    )
    assert {item["value"] for item in metadata["publication_dates"]} == {
        "2025-01-01",
        "2024-12-01",
        "2024-12-02",
        "2023-11-01",
    }
    assert all(item["kind"] != "print" for item in metadata["publication_dates"])
    merged = merge_html_metadata(metadata, metadata)
    assert merged["publication_dates"] == metadata["publication_dates"]


def test_same_title_original_and_correction_still_require_the_existing_margin():
    from paper_fetch.resolve.query import CONFIDENT_MARGIN_MIN

    title = "Reconciling the optimal and empirical approaches to modelling stomatal conductance"
    candidates = [
        {
            "doi": "10.1111/j.1365-2486.2010.02375.x",
            "title": title,
            "authors": ["BELINDA E. MEDLYN"],
            "publication_dates": [
                {"kind": "online", "value": "2011", "source": "test"}
            ],
        },
        {
            "doi": "10.1111/j.1365-2486.2012.02790.x",
            "title": title,
            "authors": ["BELINDA E. MEDLYN"],
            "publication_dates": [
                {"kind": "online", "value": "2012", "source": "test"}
            ],
            "article_type": "correction",
        },
    ]
    scored = score_candidates(
        StructuredResolveRequest(title=title, authors=("Medlyn",), year=2011),
        candidates,
    )
    assert scored[0]["author_score"] == scored[1]["author_score"] == 0.5
    assert scored[0]["score"] - scored[1]["score"] < CONFIDENT_MARGIN_MIN
    assert [item["doi"] for item in scored] == [item["doi"] for item in candidates]
