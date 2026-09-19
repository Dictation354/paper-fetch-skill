"""Article entitlement stops requests, with local degradation and evidence."""

from types import SimpleNamespace
from unittest import mock
import pytest
from paper_fetch.models import RenderOptions, article_from_markdown
from paper_fetch.providers._pdf_fallback import PdfRequestContext, fetch_pdf_over_http
from paper_fetch.providers._waterfall import WaterfallStep, run_provider_waterfall
from paper_fetch.providers.base import (
    ProviderFailure,
    ProviderContent,
    RawFulltextPayload,
)
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.quality.access_boundary import (
    CONFIRMED_PAYWALL,
    confirmed_paywall,
    html_paywall_diagnostics,
    raise_for_api_entitlement,
    raise_for_paywall,
)
from paper_fetch.service import build_fetch_envelope
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._paper_fetch_support import RecordingTransport, http_response
from tests.support.reviewed_block_provider_paths import _fetch_through_service


DOI = "10.1111/example"
URL = "https://onlinelibrary.wiley.com/doi/" + DOI
ABSTRACT = "Received abstract about the measured properties."
PAGE = f'<meta name="citation_doi" content="{DOI}"><meta name="citation_title" content="Target article"><article><div class="abstract">{ABSTRACT}</div><div id="no-access-message">You do not currently have access to this article.</div></article>'
BODY = (
    "<div class='article-body'><h2>Results</h2>"
    + "<p>"
    + "The measured properties establish reproducible findings. " * 35
    + "</p></div>"
)


@pytest.mark.parametrize(
    "fragment",
    [
        "<header>You do not currently have access to this article.</header>",
        "<aside>You do not currently have access to this article.</aside>",
        "<template>You do not currently have access to this article.</template>",
        "<div hidden>You do not currently have access to this article.</div>",
        "<div style='display:none'>You do not currently have access to this article.</div>",
        "<div class='references'>You do not currently have access to this article.</div>",
        "<figure>You do not currently have access to this article.</figure>",
        "<div class='related-articles'>Purchase this article</div>",
        "<p>Login | Buy now | Not open access | HTTP 403 Forbidden</p>",
    ],
)
def test_peripheral_hidden_other_article_and_asset_signals_do_not_stop(fragment):
    html = PAGE.split("<article>")[0] + "<article>" + BODY + fragment + "</article>"
    assert not html_paywall_diagnostics(html, metadata={"doi": DOI}, source_url=URL)
    # Hidden/asset/chrome fragments cannot turn an empty shell into a paywall.
    assert not html_paywall_diagnostics(
        html.replace(BODY, ""), metadata={"doi": DOI}, source_url=URL
    )


def test_readable_body_outweighs_peripheral_purchase_prompt():
    assert not html_paywall_diagnostics(
        PAGE.replace("</article>", BODY + "</article>"),
        metadata={"doi": DOI},
        source_url=URL,
    )
    assert not html_paywall_diagnostics(
        PAGE, metadata={"doi": "10.1111/other"}, source_url=URL
    )


@pytest.mark.parametrize(
    "body",
    [
        f"<div hidden>{BODY}</div>",
        "<figure><figcaption>" + "caption " * 500 + "</figcaption></figure>",
        "<div class='references'>" + BODY + "</div>",
    ],
)
def test_hidden_body_captions_and_references_do_not_override_gate(body):
    diagnostics = html_paywall_diagnostics(
        PAGE.replace("</article>", body + "</article>"),
        metadata={"doi": DOI},
        source_url=URL,
    )
    assert confirmed_paywall(diagnostics)
    assert diagnostics["received_metadata"]["abstract"] == ABSTRACT


def test_overlay_blocking_visible_dom_is_terminal():
    html = PAGE.replace(
        'id="no-access-message"', 'id="no-access-message" aria-modal="true"'
    ).replace("</article>", BODY + "</article>")
    assert confirmed_paywall(
        html_paywall_diagnostics(html, metadata={"doi": DOI}, source_url=URL)
    )


def test_pdf_subscription_response_stops_candidates():
    second = URL + "/second.pdf"
    transport = RecordingTransport(
        {("GET", URL): http_response(URL, PAGE.encode(), "text/html")}
    )
    with pytest.raises(ProviderFailure) as failure:
        fetch_pdf_over_http(
            transport,
            [URL, second],
            request=PdfRequestContext(expected_identity={"doi": DOI}),
        )
    assert confirmed_paywall(failure.value)
    assert [call["url"] for call in transport.calls] == [URL]


def test_waterfall_never_runs_next_step_after_entitlement_denial():
    later = mock.Mock(side_effect=AssertionError("Further full-text request"))
    with pytest.raises(ProviderFailure) as failure:
        run_provider_waterfall(
            [
                WaterfallStep(
                    label="xml",
                    run=lambda _: raise_for_api_entitlement(
                        b"<error><status>NOT_ENTITLED</status></error>",
                        source_url="https://api.elsevier.com/content/article/doi/10.1016/example",
                        provider="elsevier",
                    ),
                ),
                WaterfallStep(label="pdf", run=later),
            ]
        )
    assert confirmed_paywall(failure.value)
    later.assert_not_called()


@pytest.mark.parametrize("assembled", [False, True])
@pytest.mark.parametrize("has_abstract", [False, True])
def test_result_stops_recovery_and_assets_and_keeps_received_metadata(
    tmp_path, assembled, has_abstract
):
    html = (
        PAGE
        if has_abstract
        else PAGE.replace(f'<div class="abstract">{ABSTRACT}</div>', "")
    )
    client = WileyClient(RecordingTransport({}), {})
    payload = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=URL,
            body=html.encode() if not assembled else b"",
            content_type="text/html",
            markdown_text="provisional",
        ),
    )
    client.fetch_raw_fulltext = mock.Mock(return_value=payload)
    client.download_related_assets = mock.Mock(
        side_effect=AssertionError("Asset request after gate")
    )
    if assembled:
        diagnostics = html_paywall_diagnostics(
            html, metadata={"doi": DOI}, source_url=URL, provider="wiley"
        )
        client.to_article_model = mock.Mock(
            side_effect=lambda *a, **k: article_from_markdown(
                source="wiley_browser",
                metadata=diagnostics["received_metadata"],
                doi=DOI,
                markdown_text="",
                availability_diagnostics=diagnostics,
            )
        )
    else:
        client.maybe_recover_fetch_result_payload = mock.Mock(
            side_effect=AssertionError("PDF/TDM recovery after gate")
        )
    result = client.fetch_result(DOI, {"doi": DOI}, tmp_path, asset_profile="all")
    client.download_related_assets.assert_not_called()
    article = result.article
    assert article.quality.content_kind == (
        "abstract_only" if has_abstract else "metadata_only"
    )
    assert not article.sections
    assert CONFIRMED_PAYWALL in article.quality.source_trail
    assert "access_gate_detected" in article.quality.flags
    if has_abstract:
        assert article.metadata.abstract == ABSTRACT
    envelope = build_fetch_envelope(
        article,
        modes={"article", "markdown"},
        render=RenderOptions(asset_profile="none"),
    )
    assert (
        evaluate_fetch_acceptance(
            envelope, doi=DOI, expected_doi=DOI, asset_profile="none"
        ).overall
        == "limited"
    )


def test_service_stops_after_provider_boundary():
    client = WileyClient(RecordingTransport({}), {})
    client.fetch_raw_fulltext = mock.Mock(
        side_effect=lambda *a, **k: raise_for_paywall(
            PAGE, metadata={"doi": DOI}, source_url=URL, provider="wiley"
        )
    )
    client._recover_pdf_payload_from_abstract_only_html = mock.Mock(
        side_effect=AssertionError("PDF requested")
    )
    fixture = SimpleNamespace(doi=DOI, provider="wiley", source_url=URL)
    envelope = _fetch_through_service(
        client,
        fixture,
        {
            "doi": DOI,
            "title": "Target article",
            "provider": "wiley",
            "official_provider": True,
        },
    )
    assert envelope.article.quality.content_kind == "abstract_only"
    assert envelope.article.metadata.abstract == ABSTRACT
    assert client.fetch_raw_fulltext.call_count == 1
    client._recover_pdf_payload_from_abstract_only_html.assert_not_called()


@pytest.mark.parametrize(
    "fragment",
    [
        "<p>We studied messages such as “You do not currently have access to this article” in publishing interfaces.</p>",
        '<section data-doi="10.1111/other"><p>You do not currently have access to this article.</p></section>',
    ],
)
def test_research_discussion_and_explicit_other_article_are_not_entitlement(fragment):
    assert not html_paywall_diagnostics(
        PAGE.split("<article>")[0] + fragment, metadata={"doi": DOI}, source_url=URL
    )


@pytest.mark.parametrize(
    "body",
    [
        b"<article><p>Subjects are not entitled to access this article in the simulation.</p></article>",
        b'{"full-text": "not entitled"}',
        b"Forbidden",
    ],
)
def test_official_api_requires_entitlement_error_not_prose_or_status(body):
    raise_for_api_entitlement(
        body,
        source_url="https://api.elsevier.com/content/article/doi/10.1016/example",
        provider="elsevier",
    )


@pytest.mark.parametrize(
    "route,body,terminal",
    [
        ("browser_html", PAGE.encode(), True),
        ("assets", PAGE.encode(), False),
        ("browser_html", b"Temporary failure", False),
    ],
)
def test_confirmed_http_error_prevents_retry_only_for_article_routes(
    route, body, terminal
):
    from paper_fetch.http import (
        HttpTransport,
        HttpRequestPolicy,
        provider_request_policy,
    )
    from tests.support.http_cache import FakeHTTPResponse, build_http_error

    transport = HttpTransport(cache_ttl=0, cache_capacity=0)
    perform = mock.Mock(
        side_effect=[
            build_http_error(URL, status=503, body=body),
            FakeHTTPResponse(b"ok", URL),
        ]
    )
    with (
        mock.patch.object(transport, "_perform_request", perform),
        mock.patch("paper_fetch.http.retry.time.sleep"),
    ):

        def request():
            return transport.request(
                "GET",
                URL,
                retry_on_transient=True,
                request_policy=HttpRequestPolicy(
                    cooldown_scope="independent-cooldown-key",
                    body_access_provider=provider_request_policy(
                        "wiley", route
                    ).body_access_provider,
                    retry_on_transient=True,
                    transient_backoff_base_seconds=0,
                ),
            )

        if terminal:
            with pytest.raises(ProviderFailure) as exc:
                request()
            assert confirmed_paywall(exc.value)
        else:
            assert request()["body"] == b"ok"
    assert perform.call_count == (1 if terminal else 2)


@pytest.mark.parametrize("allow_fallback", [True, False])
def test_weak_provider_candidate_stops_cross_provider_dispatch(allow_fallback):
    from paper_fetch import service
    from paper_fetch.workflow import fulltext
    from tests.support._paper_fetch_support import FixtureProvider

    metadata = {
        "doi": DOI,
        "title": "Target article",
        "provider": "wiley",
        "official_provider": True,
    }
    client = WileyClient(RecordingTransport({}), {})
    client.fetch_raw_fulltext = mock.Mock(
        side_effect=lambda *a, **k: raise_for_paywall(
            PAGE, metadata=metadata, source_url=URL, provider="wiley"
        )
    )
    client.fetch_metadata = mock.Mock(return_value=metadata)
    later = FixtureProvider(
        article_factory=mock.Mock(side_effect=AssertionError("Next provider requested"))
    )
    resolved = service.ResolvedQuery(
        query=DOI,
        query_kind="doi",
        doi=DOI,
        landing_url=URL,
        provider_hint="wiley",
        confidence=1.0,
    )
    with (
        mock.patch.object(service, "resolve_paper", return_value=resolved),
        mock.patch.object(
            fulltext,
            "_ranked_fulltext_provider_candidates",
            return_value=[("wiley", "test", "weak"), ("elsevier", "test", "strong")],
        ),
    ):

        def fetch():
            return service.fetch_paper(
                DOI,
                modes={"article"},
                strategy=service.FetchStrategy(
                    allow_metadata_only_fallback=allow_fallback, asset_profile="none"
                ),
                context=service.RuntimeContext(
                    env={},
                    clients={
                        "wiley": client,
                        "elsevier": later,
                        "crossref": FixtureProvider(metadata=metadata),
                    },
                ),
            )

        if allow_fallback:
            assert fetch().content_kind == "abstract_only"
        else:
            with pytest.raises(service.PaperFetchFailure) as exc:
                fetch()
            assert exc.value.status == "no_access"
    assert client.fetch_raw_fulltext.call_count == 1


def test_browser_candidate_loop_closes_page_before_preparation_or_next_url(tmp_path):
    from dataclasses import replace
    from paper_fetch.providers import _playwright_browser
    from tests.support.browser_preflight import _runtime_config

    page = mock.Mock(url=URL)
    page.content.return_value = PAGE
    page.title.return_value = "Target article"
    page.goto.return_value = SimpleNamespace(
        status=200, headers={"content-type": "text/html"}
    )
    context = mock.Mock()
    context.new_page.return_value = page
    context.cookies.return_value = []
    config = replace(
        _runtime_config(tmp_path, provider="wiley", doi=DOI),
        persist_storage_state=False,
    )
    with (
        mock.patch.object(
            _playwright_browser, "open_browser_context", return_value=(None, context)
        ),
        mock.patch.object(_playwright_browser, "_wait_for_browser_html_readiness"),
        mock.patch.object(
            _playwright_browser,
            "_prepare_provider_browser_page",
            side_effect=AssertionError("Page expansion after gate"),
        ) as prepare,
    ):
        with pytest.raises(ProviderFailure) as exc:
            _playwright_browser.fetch_html_with_playwright(
                [URL, URL + "/second"], publisher="wiley", config=config, wait_seconds=0
            )
    assert confirmed_paywall(exc.value)
    assert page.goto.call_count == 1
    prepare.assert_not_called()
    page.close.assert_called_once()
    context.close.assert_called_once()


def test_independent_asset_access_failure_keeps_readable_body(tmp_path):
    client = WileyClient(RecordingTransport({}), {})
    raw = "## Results\n\n" + "Measured findings establish the article body. " * 100
    payload = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=URL,
            body=BODY.encode(),
            content_type="text/html",
            markdown_text=raw,
        ),
    )
    client.fetch_raw_fulltext = mock.Mock(return_value=payload)
    client.download_related_assets = mock.Mock(
        side_effect=ProviderFailure(
            "no_access", "This figure requires a separate subscription."
        )
    )
    result = client.fetch_result(
        DOI, {"doi": DOI, "title": "Target article"}, tmp_path, asset_profile="all"
    )
    client.download_related_assets.assert_called_once()
    assert result.article.quality.content_kind == "fulltext"
    assert CONFIRMED_PAYWALL not in result.article.quality.source_trail
    assert "Measured findings" in result.article.to_ai_markdown()


def test_assembly_boundary_keeps_abstract_from_extracted_blocks():
    from paper_fetch.models import article_from_structure

    diagnostics = html_paywall_diagnostics(PAGE, metadata={"doi": DOI}, source_url=URL)
    diagnostics.pop("received_metadata")
    with pytest.raises(ProviderFailure) as exc:
        article_from_structure(
            source="wiley_browser",
            metadata={"doi": DOI},
            doi=DOI,
            abstract_lines=[ABSTRACT],
            body_lines=[],
            figure_entries=[],
            table_entries=[],
            supplement_entries=[],
            conversion_notes=[],
            availability_diagnostics=diagnostics,
        )
    assert exc.value.details["received_metadata"]["abstract"] == ABSTRACT


@pytest.mark.parametrize("css_class", ["hidden", "d-none", "is-hidden"])
def test_hidden_css_body_does_not_outweigh_gate(css_class):
    html = PAGE.replace(
        "</article>", f'<div class="{css_class}">{BODY}</div></article>'
    )
    assert confirmed_paywall(
        html_paywall_diagnostics(html, metadata={"doi": DOI}, source_url=URL)
    )
    hidden_notice = PAGE.replace(
        'id="no-access-message"', f'id="no-access-message" class="{css_class}"'
    )
    assert not html_paywall_diagnostics(
        hidden_notice, metadata={"doi": DOI}, source_url=URL
    )


def test_abstract_discussion_and_hidden_entitlement_template_are_not_a_gate():
    head = PAGE.split("<article>")[0]
    script = '<script>window.adobeDataLayer = [{"content":{"item":{"access":"no"}}}];</script>'
    for content in [
        f"<template>{script}</template>",
        f"<div hidden>{script}</div>",
        '<div class="abstract">You do not currently have access to this article is a message examined in our study.</div>',
    ]:
        assert not html_paywall_diagnostics(
            head + content, metadata={"doi": DOI}, source_url=URL, provider="wiley"
        )


@pytest.mark.parametrize("preconfirmed", [False, True])
def test_response_metadata_cannot_retarget_paywall_identity(preconfirmed):
    from paper_fetch.quality.access_boundary import check_payload_paywall

    other = "10.1111/other"
    html = PAGE.replace(DOI, other)
    diagnostics = (
        html_paywall_diagnostics(
            html, metadata={"doi": other}, source_url=URL.replace(DOI, other)
        )
        if preconfirmed
        else {}
    )
    payload = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=URL.replace(DOI, other),
            content_type="text/html",
            body=html.encode(),
            merged_metadata={"doi": other},
            diagnostics=diagnostics,
        ),
    )
    if preconfirmed:
        with pytest.raises(ProviderFailure) as exc:
            check_payload_paywall(payload, {"doi": DOI})
        assert exc.value.code == "identity_mismatch"
        assert not confirmed_paywall(exc.value)
    else:
        check_payload_paywall(payload, {"doi": DOI})


@pytest.mark.parametrize("provider", ["science", "pnas"])
@pytest.mark.parametrize("location", ["body", "aside", "template", "other"])
def test_publisher_denial_block_requires_visible_same_article_body(provider, location):
    gate = (
        '<section id="bodymatter"><div class="core-container">'
        '<section class="denial-block"><p>View all access options to continue reading this article.</p>'
        "</section></div></section>"
    )
    if location in {"aside", "template"}:
        gate = f"<{location}>{gate}</{location}>"
    elif location == "other":
        gate = f'<section data-doi="10.1111/other">{gate}</section>'
    html = PAGE.split("<article>")[0] + gate
    assert bool(
        html_paywall_diagnostics(
            html, metadata={"doi": DOI}, source_url=URL, provider=provider
        )
    ) is (location == "body")


@pytest.mark.parametrize("has_body", [False, True])
def test_iop_only_research_body_can_outweigh_turnaway_panel(has_body):
    html = PAGE + '<div class="overlay-text">' + BODY + "</div>"
    html += '<div class="author-affiliations">' + BODY + "</div>"
    if has_body:
        html += '<div class="wd-jnl-art-full-text">' + BODY + "</div>"
    assert (
        bool(
            html_paywall_diagnostics(
                html, metadata={"doi": DOI}, source_url=URL, provider="iop"
            )
        )
        is not has_body
    )


@pytest.mark.parametrize("provider", ["pnas", "science"])
def test_publisher_role_paragraph_body_outweighs_purchase_notice(provider):
    html = (
        PAGE
        + '<section id="bodymatter"><div role="paragraph">'
        + ("The measured properties establish reproducible findings. " * 35)
        + "</div></section>"
    )
    assert not html_paywall_diagnostics(
        html, metadata={"doi": DOI}, source_url=URL, provider=provider
    )


@pytest.mark.parametrize(
    "key",
    [
        "DC.Identifier",
        "dc.identifier.doi",
        "prism.doi",
        "publication_doi",
        "CITATION_DOI",
    ],
)
def test_gate_uses_validated_shared_metadata_identity(key):
    html = f'<meta name="{key}" content="doi:{DOI}"><div class="paywall">Purchase this article</div>'
    assert confirmed_paywall(
        html_paywall_diagnostics(
            html, metadata={"doi": DOI}, source_url="https://example.org/article"
        )
    )
    assert not html_paywall_diagnostics(
        html,
        metadata={"doi": "10.1111/other"},
        source_url="https://example.org/article",
    )
    invalid = html.replace(f"doi:{DOI}", "12345")
    assert not html_paywall_diagnostics(
        invalid, source_url="https://example.org/article"
    )


def test_payload_html_cache_reuses_inputs_but_checks_new_diagnostics():
    from paper_fetch.quality import access_boundary
    from paper_fetch.runtime import RuntimeContext

    payload = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=URL,
            content_type="text/html",
            body=BODY.encode(),
        ),
    )
    context = RuntimeContext(env={})
    with mock.patch.object(
        access_boundary, "html_paywall_diagnostics", wraps=html_paywall_diagnostics
    ) as detect:
        for _ in range(3):
            access_boundary.check_payload_paywall(
                payload, {"doi": DOI}, context=context
            )
        assert detect.call_count == 1
        payload.content.diagnostics.update(
            html_paywall_diagnostics(PAGE, metadata={"doi": DOI}, source_url=URL)
        )
        with pytest.raises(ProviderFailure) as exc:
            access_boundary.check_payload_paywall(
                payload, {"doi": DOI}, context=context
            )
        assert confirmed_paywall(exc.value)
        assert detect.call_count == 1


@pytest.mark.parametrize(
    "changed",
    ["body", "provider", "source_url", "doi", "article_number", "abstract", "context"],
)
def test_payload_html_cache_invalidates_each_detection_input(changed):
    from paper_fetch.quality import access_boundary
    from paper_fetch.runtime import RuntimeContext
    from dataclasses import replace

    payload = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=URL,
            content_type="text/html",
            body=BODY.encode(),
        ),
    )
    context = RuntimeContext(env={})
    metadata = {"doi": DOI}
    with mock.patch.object(
        access_boundary, "html_paywall_diagnostics", wraps=html_paywall_diagnostics
    ) as detect:
        access_boundary.check_payload_paywall(payload, metadata, context=context)
        if changed == "body":
            payload.content = replace(
                payload.content, body=payload.content.body + b"<p>Changed</p>"
            )
        elif changed == "provider":
            payload.provider = "science"
        elif changed == "source_url":
            payload.content = replace(
                payload.content, source_url=payload.content.source_url + "?new=1"
            )
        elif changed == "context":
            context = RuntimeContext(env={})
        else:
            metadata[changed] = "changed"
        access_boundary.check_payload_paywall(payload, metadata, context=context)
        assert detect.call_count == 2


def test_response_article_number_cannot_confirm_an_explicit_target_doi():
    from paper_fetch.quality.access_boundary import check_payload_paywall

    payload = RawFulltextPayload(
        provider="ieee",
        content=ProviderContent(
            route_kind="html",
            source_url="https://ieeexplore.ieee.org/document/12345",
            body=b'<div class="paywall">Purchase this article</div>',
            content_type="text/html",
            merged_metadata={"article_number": "12345"},
        ),
    )
    check_payload_paywall(payload, {"doi": DOI})
    with pytest.raises(ProviderFailure) as exc:
        check_payload_paywall(payload, {"doi": DOI, "article_number": "12345"})
    assert confirmed_paywall(exc.value)


def test_assembly_reuses_body_check_but_observes_mutated_body_and_diagnostics():
    from dataclasses import replace
    from paper_fetch.quality import access_boundary
    from paper_fetch.runtime import RuntimeContext

    payload = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=URL,
            content_type="text/html",
            body=BODY.encode(),
        ),
    )
    with RuntimeContext(env={}) as context:
        checked = access_boundary.check_payload_paywall(
            payload, {"doi": DOI}, context=context
        )
        with mock.patch.object(
            context,
            "build_parse_cache_key",
            side_effect=AssertionError("unchanged assembly reparsed body"),
        ):
            access_boundary.check_payload_paywall(
                payload, {"doi": DOI}, context=context, checked_input=checked
            )
            payload.content.diagnostics.update(
                html_paywall_diagnostics(PAGE, metadata={"doi": DOI}, source_url=URL)
            )
            with pytest.raises(ProviderFailure) as failure:
                access_boundary.check_payload_paywall(
                    payload, {"doi": DOI}, context=context, checked_input=checked
                )
            assert confirmed_paywall(failure.value)
        payload.content = replace(payload.content, body=PAGE.encode(), diagnostics={})
        with pytest.raises(ProviderFailure) as failure:
            access_boundary.check_payload_paywall(
                payload, {"doi": DOI}, context=context, checked_input=checked
            )
        assert confirmed_paywall(failure.value)
