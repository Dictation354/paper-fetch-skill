"""DOI matching and failure boundaries, with small bibliography fragments."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import time

import pytest

from paper_fetch.http import RequestCancelledError
from paper_fetch.providers import _elsevier_reference_completion as completion
from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
)
from paper_fetch.providers.elsevier import ElsevierClient
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.session_cache import CROSSREF_METADATA_KEY

DOI = "10.1016/example"
REF_DOI = "10.1000/matched"
TITLE = "Measured vegetation responses across seasons"
URL = "https://www.sciencedirect.com/science/article/pii/S016819232400090X"


def xml_payload(*, existing=False):
    xml = f"""<full-text-retrieval-response><coredata><doi>{DOI}</doi><title>Example</title></coredata>
    <article><body><sections><section><section-title>Results</section-title><para>{"Scientific observations explain the measured vegetation response. " * 35}</para></section></sections></body>
    <tail><bibliography><bib-reference id="bib-changed"><label>7</label><reference id="publisher-key"><contribution><authors><author><given-name>A.</given-name><surname>Writer</surname></author></authors><title><maintitle>{TITLE}</maintitle></title></contribution><host><issue><volume-nr>12</volume-nr><date>2024</date></issue><pages><first-page>101</first-page></pages>{"<doi>10.1000/existing</doi>" if existing else ""}</host></reference></bib-reference></bibliography></tail></article></full-text-retrieval-response>"""
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
    browser = Mock(
        side_effect=ProviderFailure("not_supported", "No browser on this platform")
    )
    client.deps = replace(client.deps, load_runtime_config=browser)
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
        "published": "2024-02-01",
        "_bibliography": {
            "first_author": "Writer",
            "volume": "12",
            "first_page": "101",
        },
    }
    return {**record, **changes}


def complete(client, context, *, existing=False):
    payload = completion.complete_reference_dois(
        client,
        DOI,
        {"doi": DOI, "title": "Example", "landing_page_url": URL},
        xml_payload(existing=existing),
        context,
    )
    article = client.to_article_model(
        {"doi": DOI, "title": "Example"}, payload, context=context
    )
    return payload, article


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
        [search_record(published="2023")],
        [search_record(title="Measured vegetation")],
    ],
)
def test_search_ambiguity_year_conflict_and_partial_title_leave_doi_empty(records):
    client, context, crossref, _ = setup(parent=[])
    crossref.search_bibliographic_candidates.return_value = records
    _, article = complete(client, context)
    assert article.references[0].doi is None


def test_existing_doi_is_never_replaced_or_queried():
    client, context, crossref, browser = setup()
    payload, article = complete(client, context, existing=True)
    assert article.references[0].doi == "10.1000/existing"
    assert "reference_doi_completion" not in payload.content.diagnostics
    crossref.fetch_metadata.assert_not_called()
    browser.assert_not_called()


@pytest.mark.parametrize(
    "page_doi,expected", [(DOI, REF_DOI), ("10.1016/different", None)]
)
def test_web_fallback_checks_identity_and_excludes_recommended_references(
    page_doi, expected, tmp_path
):
    client, context, crossref, _ = setup(parent=[])
    source = f'''<meta name="citation_doi" content="{page_doi}"><article><div id="body"></div>
    <div id="references"><ol class="references"><li><span class="reference" id="publisher-key"><div class="authors">A. Writer</div><div class="title">{TITLE}</div><div class="host">Journal, 12 (2024), pp. 101-110 <a href="https://doi.org/{REF_DOI}">DOI</a></div></span></li></ol></div>
    <aside><div id="references"><ol class="references"><li><span class="reference" id="publisher-key"><a href="https://doi.org/10.1000/recommended">Recommended</a></span></li></ol></div></aside></article>'''
    fetch = Mock(
        return_value=BrowserFetchedHtml(URL, URL, source, 200, {}, "Example", "", {})
    )
    client.deps = replace(
        client.deps,
        load_runtime_config=lambda *a, **k: BrowserRuntimeConfig(
            provider="elsevier",
            doi=DOI,
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
            backend="byparr",
        ),
        ensure_runtime_ready=lambda config: None,
        fetch_html_with_browser=fetch,
    )
    payload, article = complete(client, context)
    assert article.references[0].doi == expected
    assert len(article.references) == 1
    assert fetch.call_args.kwargs["runtime_context"] is context
    assert fetch.call_args.kwargs["readiness"].selector == "#references"
    assert crossref.search_bibliographic_candidates.call_count == 1
    if expected:
        assert (
            payload.content.diagnostics["reference_doi_completion"]["matches"][0][
                "source"
            ]
            == "elsevier_html"
        )


def test_lookup_failures_and_platform_skip_keep_accepted_xml_without_pdf(monkeypatch):
    client, context, crossref, browser = setup()
    crossref.fetch_metadata.side_effect = ProviderFailure("error", "Unavailable")
    crossref.search_bibliographic_candidates.side_effect = ProviderFailure(
        "rate_limited", "Throttled"
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
    browser.assert_called_once()
    pdf.assert_not_called()


@pytest.mark.parametrize("stage", ["parent", "search", "browser"])
def test_explicit_cancellation_propagates(stage):
    client, context, crossref, browser = setup(parent=[] if stage != "parent" else None)
    call = (
        crossref.fetch_metadata
        if stage == "parent"
        else crossref.search_bibliographic_candidates
        if stage == "search"
        else browser
    )
    call.side_effect = RequestCancelledError("cancelled")
    with pytest.raises(RequestCancelledError):
        complete(client, context)


def test_expired_deadline_does_not_start_network_or_browser():
    client, context, crossref, browser = setup(parent=[])
    context.deadline_monotonic = time.monotonic() - 1
    _, article = complete(client, context)
    assert article.references[0].doi is None
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
