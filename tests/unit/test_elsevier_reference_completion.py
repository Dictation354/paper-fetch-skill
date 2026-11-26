"""DOI matching and failure boundaries, with small bibliography fragments."""

import time
from contextvars import ContextVar
from dataclasses import replace
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from paper_fetch.http import HttpRequestPolicy, HttpTransport, RequestCancelledError
from paper_fetch.providers import _elsevier_reference_completion as completion
from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.elsevier import ElsevierClient
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from paper_fetch.workflow.session_cache import CROSSREF_METADATA_KEY
from tests.support.http_cache import FakeHTTPResponse
from tests.support.workflow_acceptance import _envelope

DOI = "10.1016/example"
REF_DOI = "10.1000/matched"
TITLE = "Measured vegetation responses across seasons"


def xml_payload(*, existing=False, journal=True):
    host_kind = "issue" if journal else "book"
    xml = f"""<full-text-retrieval-response><coredata><doi>{DOI}</doi><title>Example</title></coredata>
    <article><body><sections><section><section-title>Results</section-title><para>{"Scientific observations explain the measured vegetation response. " * 35}</para></section></sections></body>
    <tail><bibliography><bib-reference id="bib-changed"><label>7</label><reference id="publisher-key"><contribution><authors><author><given-name>A.</given-name><surname>Writer</surname></author></authors><title><maintitle>{TITLE}</maintitle></title></contribution><host><{host_kind}><volume-nr>12</volume-nr><date>2024</date></{host_kind}><pages><first-page>101</first-page></pages>{"<doi>10.1000/existing</doi>" if existing else ""}</host></reference></bib-reference></bibliography></tail></article></full-text-retrieval-response>"""
    return build_provider_payload(
        provider="elsevier",
        route_kind="official",
        route_name="xml_api",
        source_url="https://api.elsevier.com/content/article/doi/example",
        content_type="text/xml",
        body=xml.encode(),
    )


def setup(*, parent=None):
    crossref = SimpleNamespace(
        fetch_metadata=Mock(return_value={"doi": DOI, "references": []}),
        search_bibliographic_candidates=Mock(return_value=[]),
    )
    client = ElsevierClient(None, {"ELSEVIER_API_KEY": "key"})
    context = RuntimeContext(env={}, clients={"crossref": crossref})
    browser = Mock()
    client.deps = replace(client.deps, fetch_html_with_browser=browser)
    if parent is not None:
        context.set_session_cache(
            CROSSREF_METADATA_KEY.materialize(DOI),
            {"doi": DOI, "_reference_records": parent},
        )
    return client, context, crossref, browser


def parent_record(**changes):
    record = {
        "key": DOI + "_bib-changed",
        "DOI": REF_DOI,
        "article-title": TITLE,
        "author": "Writer",
        "year": "2024",
        "volume": "12",
        "first-page": "101",
    }
    return {**record, **changes}


def search_record(**changes):
    record = {
        "doi": REF_DOI,
        "title": TITLE,
        "authors": ["A. Writer"],
        "publication_dates": [
            {"kind": "unspecified", "value": "2024-02-01", "source": "test"}
        ],
        "_bibliography": {
            "first_author": "Writer",
            "volume": "12",
            "first_page": "101",
        },
    }
    return {**record, **changes}


def complete(client, context, *, journal=True):
    payload = completion.complete_reference_dois(
        DOI,
        xml_payload(journal=journal),
        context,
    )
    article = client.to_article_model(
        {"doi": DOI, "title": "Example"}, payload, context=context
    )
    return payload, article


@pytest.mark.parametrize("parent_match", [True, False])
def test_book_reference_uses_only_parent_reference_list(parent_match):
    client, context, crossref, browser = setup(
        parent=[parent_record()] if parent_match else []
    )
    _, article = complete(client, context, journal=False)
    assert article.references[0].doi == (REF_DOI if parent_match else None)
    crossref.fetch_metadata.assert_not_called()
    crossref.search_bibliographic_candidates.assert_not_called()
    browser.assert_not_called()


def test_search_fanout_propagates_context_and_applies_matches_in_reference_order(
    monkeypatch,
):
    client, context, crossref, browser = setup(parent=[])
    titles = [f"{TITLE} {index}" for index in range(3)]
    citations = [
        completion.Citation(title=title, first_author="Writer", year="2024")
        for title in titles
    ]
    monkeypatch.setattr(completion, "xml_citations", lambda root: citations)
    request_marker = ContextVar("test_reference_search_marker")
    barrier = Barrier(3, timeout=3)

    def search(title, *, rows):
        assert rows == 5 and request_marker.get() == DOI
        barrier.wait()
        return [search_record(title=title, doi=f"10.1000/{titles.index(title)}")]

    crossref.search_bibliographic_candidates.side_effect = search
    token = request_marker.set(DOI)
    try:
        payload, _ = complete(client, context)
    finally:
        request_marker.reset(token)
    diagnostics = payload.content.diagnostics["reference_doi_completion"]
    assert [match["doi"] for match in diagnostics["matches"]] == [
        "10.1000/0",
        "10.1000/1",
        "10.1000/2",
    ]
    assert [attempt["source"] for attempt in diagnostics["attempts"]].count(
        "crossref_search"
    ) == 3
    assert all(
        event.duration_ms is not None and event.duration_ms >= 0
        for event in payload.trace
    )
    browser.assert_not_called()


def test_reference_http_individual_timeout_respects_remaining_budget():
    transport = Mock()
    context = RuntimeContext(env={})
    bounded = completion._RequestTransport(transport, context)
    bounded.request("GET", "https://example.test/reference")
    assert transport.request.call_args.kwargs["timeout"] == 5.0
    context.deadline_monotonic = time.monotonic() + 0.8
    bounded.request("GET", "https://example.test/reference")
    assert 0 < transport.request.call_args.kwargs["timeout"] <= 0.8


def test_reference_retry_wait_stops_at_outer_deadline(monkeypatch):
    url = "https://example.test/reference"
    now = 100.0

    def advance(seconds):
        nonlocal now
        now += seconds

    monkeypatch.setattr(completion.time, "monotonic", lambda: now)
    monkeypatch.setattr(completion.time, "sleep", advance)
    with RuntimeContext(env={}) as context:
        context.deadline_monotonic = now + 1.2
        transport = HttpTransport()
        try:
            send = Mock(
                return_value=FakeHTTPResponse(
                    b"{}",
                    url,
                    status=429,
                    headers={"Retry-After": "5"},
                )
            )
            monkeypatch.setattr(transport, "_perform_request", send)
            bounded = completion._RequestTransport(transport, context)
            with pytest.raises(completion._ReferenceDeadlineExceeded):
                bounded.request(
                    "GET",
                    url,
                    request_policy=HttpRequestPolicy(
                        retry_on_rate_limit=True,
                        rate_limit_retries=2,
                    ),
                )
            send.assert_called_once()
            assert now == pytest.approx(101.2, abs=0.1)
        finally:
            transport.close()


def test_reuse_parent_key_after_reordering_and_conversion_has_no_network():
    client, context, crossref, browser = setup(
        parent=[
            parent_record(
                key="unrelated", DOI="10.1000/wrong", **{"article-title": "Other title"}
            ),
            parent_record(),
        ]
    )
    payload, article = complete(client, context)
    assert article.source == "elsevier_xml"
    assert [r.doi for r in article.references] == [REF_DOI]
    assert article.references[0].raw.startswith("1. ")
    assert REF_DOI in article.to_ai_markdown(max_tokens="full_text", include_refs="all")
    matches = payload.content.diagnostics["reference_doi_completion"]["matches"]
    assert matches[0]["source"] == "crossref_parent"
    assert matches[0]["basis"] == "reference_key"
    client.to_article_model({"doi": DOI}, payload, context=context)
    crossref.fetch_metadata.assert_not_called()
    crossref.search_bibliographic_candidates.assert_not_called()
    browser.assert_not_called()


@pytest.mark.parametrize(
    "conflict",
    [
        {"year": "2023"},
        {"author": "Different"},
        {"volume": "13"},
        {"first-page": "102"},
        {"article-title": "A different full title"},
    ],
)
def test_key_does_not_override_bibliographic_conflicts(conflict):
    client, context, _, _ = setup(parent=[parent_record(**conflict)])
    _, article = complete(client, context)
    assert article.references[0].doi is None


def test_without_key_requires_full_title_author_year_and_available_volume_pages():
    target = completion.Citation(
        title=TITLE, first_author="Writer", year="2024", volume="12", first_page="101"
    )
    candidate = completion.metadata_citation(parent_record(key="different"))
    assert (
        completion.match_citation(target, [candidate], parent_doi=DOI)[1]
        == "title_author_year_volume_pages"
    )
    for field in ("title", "first_author", "year"):
        assert (
            completion.match_citation(
                target, [replace(candidate, **{field: ""})], parent_doi=DOI
            )
            is None
        )


def test_search_checks_candidates_instead_of_accepting_first_result_and_caches():
    client, context, crossref, browser = setup(parent=[])
    crossref.search_bibliographic_candidates.return_value = [
        search_record(doi="10.1000/wrong", title="A different title"),
        search_record(),
    ]
    payload, article = complete(client, context)
    assert article.references[0].doi == REF_DOI
    assert (
        payload.content.diagnostics["reference_doi_completion"]["matches"][0]["source"]
        == "crossref_search"
    )
    _, again = complete(client, context)
    assert again.references[0].doi == REF_DOI
    assert crossref.search_bibliographic_candidates.call_count == 1
    browser.assert_not_called()


@pytest.mark.parametrize(
    "records",
    [
        [search_record(), search_record(doi="10.1000/second")],
        [
            search_record(
                publication_dates=[
                    {"kind": "unspecified", "value": "2023", "source": "test"}
                ]
            )
        ],
        [search_record(title="Measured vegetation")],
    ],
)
def test_search_ambiguity_year_conflict_and_partial_title_leave_doi_empty(records):
    client, context, crossref, browser = setup(parent=[])
    crossref.search_bibliographic_candidates.return_value = records
    payload, article = complete(client, context)
    assert article.references[0].doi is None
    assert payload.trace[-1].outcome == "info"
    browser.assert_not_called()


@pytest.mark.parametrize("source_tag", ["doi", "comment"])
def test_existing_doi_is_never_replaced_or_queried(source_tag):
    client, context, crossref, browser = setup()
    payload = xml_payload(existing=True)
    payload.content = replace(
        payload.content,
        body=payload.content.body.replace(
            b"<doi>10.1000/existing</doi>",
            f"<{source_tag}>10.1000/existing</{source_tag}>".encode(),
        ),
    )
    payload = completion.complete_reference_dois(DOI, payload, context)
    article = client.to_article_model({"doi": DOI}, payload, context=context)
    assert article.references[0].doi == "10.1000/existing"
    assert "reference_doi_completion" not in payload.content.diagnostics
    crossref.search_bibliographic_candidates.assert_not_called()
    crossref.fetch_metadata.assert_not_called()
    browser.assert_not_called()


@pytest.mark.parametrize(
    ("parent_error", "search_error", "outcome", "overall"),
    [
        (None, None, "info", "complete"),
        ("no_result", None, "info", "complete"),
        ("error", None, "unavailable", "degraded"),
        (None, "rate_limited", "unavailable", "degraded"),
    ],
)
def test_zero_matches_preserve_xml_and_report_crossref_availability(
    monkeypatch, parent_error, search_error, outcome, overall
):
    client, context, crossref, browser = setup()
    if parent_error:
        crossref.fetch_metadata.side_effect = ProviderFailure(
            parent_error, "Parent lookup"
        )
    if search_error:
        crossref.search_bibliographic_candidates.side_effect = ProviderFailure(
            search_error, "Title lookup"
        )
    monkeypatch.setattr(
        client, "_fetch_official_xml_payload", lambda doi: xml_payload()
    )
    pdf = Mock()
    monkeypatch.setattr(client, "_fetch_official_pdf_payload", pdf)
    payload = client.fetch_raw_fulltext(
        DOI, {"doi": DOI, "title": "Example"}, context=context
    )
    article = client.to_article_model({"doi": DOI}, payload, context=context)
    assert article.source == "elsevier_xml"
    assert article.references[0].doi is None
    assert payload.content.diagnostics["availability_diagnostics"]["accepted"]
    assert payload.content.diagnostics["identity"]
    assert payload.trace[-1].outcome == outcome
    envelope = _envelope()
    envelope.trace.extend(payload.trace)
    report = evaluate_fetch_acceptance(envelope, asset_profile="none")
    assert report.content.has_fulltext
    assert report.overall == overall
    browser.assert_not_called()
    pdf.assert_not_called()

    # Only successful lookups, including ordinary empty results, are reusable.
    crossref.fetch_metadata.side_effect = None
    crossref.search_bibliographic_candidates.side_effect = None
    crossref.search_bibliographic_candidates.return_value = [search_record()]
    again, article = complete(client, context)
    assert crossref.fetch_metadata.call_count == (2 if parent_error else 1)
    assert crossref.search_bibliographic_candidates.call_count == (
        2 if search_error else 1
    )
    assert article.references[0].doi == (REF_DOI if search_error else None)
    assert again.trace[-1].outcome == ("ok" if search_error else "info")


@pytest.mark.parametrize("stage", ["parent", "search"])
def test_explicit_cancellation_propagates(stage):
    client, context, crossref, _ = setup(parent=[] if stage != "parent" else None)
    call = (
        crossref.fetch_metadata
        if stage == "parent"
        else crossref.search_bibliographic_candidates
    )
    call.side_effect = RequestCancelledError("cancelled")
    with pytest.raises(RequestCancelledError):
        complete(client, context)


def test_expired_deadline_does_not_start_network_or_browser():
    client, context, crossref, browser = setup(parent=[])
    context.deadline_monotonic = time.monotonic() - 1
    payload, article = complete(client, context)
    assert article.references[0].doi is None
    assert payload.trace[-1].outcome == "unavailable"
    crossref.search_bibliographic_candidates.assert_not_called()
    browser.assert_not_called()


def test_parent_identity_and_duplicate_key_candidates_are_not_trusted():
    client, context, _, _ = setup(
        parent=[parent_record(), parent_record(DOI="10.1000/ambiguous")]
    )
    assert complete(client, context)[1].references[0].doi is None
    context.set_session_cache(
        CROSSREF_METADATA_KEY.materialize(DOI),
        {"doi": "10.1016/wrong", "_reference_records": [parent_record()]},
    )
    assert complete(client, context)[1].references[0].doi is None


def test_xml_citations_prefer_journal_host_and_exclude_conference_and_books():
    import xml.etree.ElementTree as ET

    root = ET.fromstring("""
      <bibliography xmlns:sb="urn:elsevier:sb">
        <bib-reference id="multi"><sb:reference>
          <sb:host><sb:e-host><sb:date>1900</sb:date></sb:e-host></sb:host>
          <sb:host><sb:issue><sb:date>2024</sb:date><sb:volume-nr>7</sb:volume-nr></sb:issue>
            <sb:first-page>18</sb:first-page></sb:host>
        </sb:reference></bib-reference>
        <bib-reference id="in-press"><sb:reference><sb:host>
          <sb:issue><sb:series><sb:title><sb:maintitle>Journal</sb:maintitle></sb:title></sb:series></sb:issue>
        </sb:host></sb:reference></bib-reference>
        <bib-reference id="conference"><sb:reference><sb:host>
          <sb:issue><sb:conference/><sb:volume-nr>3</sb:volume-nr></sb:issue>
        </sb:host></sb:reference></bib-reference>
        <bib-reference id="edited"><sb:reference><sb:host>
          <sb:edited-book/><sb:issue/>
        </sb:host></sb:reference></bib-reference>
        <bib-reference id="bare-journal"><sb:reference><sb:host>
          <sb:title><sb:maintitle>Journal</sb:maintitle></sb:title>
        </sb:host></sb:reference></bib-reference>
      </bibliography>""")
    multi, in_press, conference, edited, bare_journal = completion.xml_citations(root)
    assert (multi.is_journal_host, multi.year, multi.volume, multi.first_page) == (
        True,
        "2024",
        "7",
        "18",
    )
    assert in_press.is_journal_host and not in_press.volume and not in_press.first_page
    assert not conference.is_journal_host and not edited.is_journal_host
    assert bare_journal.is_journal_host


def test_unsearchable_journal_can_still_match_parent_reference_key(monkeypatch):
    client, context, crossref, browser = setup(parent=[parent_record()])
    original = completion.xml_citations
    monkeypatch.setattr(
        completion,
        "xml_citations",
        lambda root: [replace(ref, title="", year="") for ref in original(root)],
    )
    payload, article = complete(client, context)
    assert article.references[0].doi == REF_DOI
    (match,) = payload.content.diagnostics["reference_doi_completion"]["matches"]
    assert (match["source"], match["basis"]) == ("crossref_parent", "reference_key")
    browser.assert_not_called()
    crossref.search_bibliographic_candidates.assert_not_called()


def test_parallel_search_applies_finished_title_when_first_title_expires(monkeypatch):
    from threading import Event

    client, context, crossref, _ = setup(parent=[])
    citations = [
        completion.Citation(title=title, first_author="Writer", year="2024")
        for title in (TITLE, "Second study")
    ]
    monkeypatch.setattr(completion, "xml_citations", lambda root: citations)
    unblock = Event()

    def search(title, *, rows):
        if title == TITLE:
            assert unblock.wait(5)
            return []
        return [search_record(title=title)]

    def expire_after_first_completion(futures, **kwargs):
        done, unfinished = original_wait(futures, **kwargs)
        if done:
            context.deadline_monotonic = time.monotonic() - 1
        return done, unfinished

    original_wait = completion.wait
    monkeypatch.setattr(completion, "wait", expire_after_first_completion)
    crossref.search_bibliographic_candidates.side_effect = search
    try:
        payload, _ = complete(client, context)
    finally:
        unblock.set()
    diagnostics = payload.content.diagnostics["reference_doi_completion"]
    assert [(match["index"], match["doi"]) for match in diagnostics["matches"]] == [
        (1, REF_DOI)
    ]
    assert payload.trace[-1].outcome == "ok"
    assert diagnostics["attempts"][-1] == {
        "source": "crossref_search",
        "outcome": "unavailable",
        "reason": "_ReferenceDeadlineExceeded",
    }


@pytest.mark.parametrize("operation", ["xml_citations", "match_citation"])
@pytest.mark.parametrize(
    "error", [ValueError("unexpected"), RequestCancelledError("stop")]
)
def test_failure_in_enrichment_parsing_or_matching_keeps_accepted_xml(
    monkeypatch, operation, error
):
    client, context, _, _ = setup(parent=[parent_record()])
    original = xml_payload()
    monkeypatch.setattr(completion, operation, Mock(side_effect=error))
    if isinstance(error, RequestCancelledError):
        with pytest.raises(RequestCancelledError):
            completion.complete_reference_dois(DOI, original, context)
    else:
        body = original.content.body
        updated = completion.complete_reference_dois(DOI, original, context)
        assert updated is original and updated.content.body == body
        attempt = updated.content.diagnostics["reference_doi_completion"]["attempts"][
            -1
        ]
        assert (attempt["outcome"], attempt["reason"]) == ("unavailable", "ValueError")
