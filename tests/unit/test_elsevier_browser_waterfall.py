"""Minimal Elsevier route contracts; publisher content replays live in golden."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from paper_fetch.http import RequestFailure
from paper_fetch.providers import elsevier
from paper_fetch.providers.base import (
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.providers.browser_runtime import selection
from paper_fetch.providers.browser_workflow.profile import (
    BrowserWorkflowBootstrapResult,
)
from paper_fetch.quality.access_boundary import confirmed_paywall, paywall_failure

DOI = "10.1016/example"
META = {"doi": DOI, "pii": "S016819232400090X", "title": "Example"}


def payload(route):
    kind = (
        "html"
        if route == "browser_html"
        else "official"
        if route == "xml_api"
        else "pdf_fallback"
    )
    return RawFulltextPayload(
        provider="elsevier",
        content=ProviderContent(
            route_kind=kind,
            route_name=route,
            source_url="https://example.test/article",
            content_type="text/html"
            if kind == "html"
            else "text/xml"
            if kind == "official"
            else "application/pdf",
            body=b"minimal contract payload",
        ),
    )


@pytest.mark.parametrize(
    "success,expected",
    [
        ("xml_api", ["xml_api"]),
        ("browser_html", ["xml_api", "browser_html"]),
        ("pdf_api", ["xml_api", "browser_html", "pdf_api"]),
        ("browser_pdf", ["xml_api", "browser_html", "pdf_api", "browser_pdf"]),
    ],
)
def test_four_stage_order_and_short_circuit(monkeypatch, success, expected):
    client = elsevier.ElsevierClient(Mock(), {"ELSEVIER_API_KEY": "key"})
    calls = []

    def run(route):
        calls.append(route)
        if route == success:
            return payload(route)
        raise ProviderFailure("no_result", route + " failed")

    def bootstrap(*args, **kwargs):
        try:
            html = run("browser_html")
        except ProviderFailure:
            html = None
        return BrowserWorkflowBootstrapResult(
            DOI,
            SimpleNamespace(),
            None,
            [],
            [],
            html_payload=html,
            html_failure_reason="insufficient_body",
        )

    monkeypatch.setattr(
        client, "_fetch_official_xml_payload", lambda doi: run("xml_api")
    )
    monkeypatch.setattr(client, "_official_payload_is_usable", lambda *a, **k: True)
    monkeypatch.setattr(
        client, "_fetch_official_pdf_payload", lambda *a, **k: run("pdf_api")
    )
    monkeypatch.setattr(
        client, "validate_raw_payload_identity", lambda doi, meta, raw: raw
    )
    client.deps = replace(
        client.deps,
        bootstrap_browser_workflow=bootstrap,
        fetch_seeded_browser_pdf_payload=lambda **kw: run("browser_pdf"),
    )
    result = client.fetch_raw_fulltext(DOI, META)
    assert calls == expected
    assert result.content.route_name == success
    if len(expected) > 1:
        assert result.warnings
        assert any(event.outcome == "fail" for event in result.trace)


def test_missing_key_skips_both_api_stages(monkeypatch):
    client = elsevier.ElsevierClient(Mock(), {})
    xml, pdf = Mock(), Mock()
    monkeypatch.setattr(client, "_fetch_official_xml_payload", xml)
    monkeypatch.setattr(client, "_fetch_official_pdf_payload", pdf)
    monkeypatch.setattr(
        client, "validate_raw_payload_identity", lambda doi, meta, raw: raw
    )
    html = payload("browser_html")
    client.deps = replace(
        client.deps,
        bootstrap_browser_workflow=lambda *a, **k: BrowserWorkflowBootstrapResult(
            DOI, None, None, [], [], html_payload=html
        ),
    )
    assert client.fetch_raw_fulltext(DOI, META) is html
    xml.assert_not_called()
    pdf.assert_not_called()


@pytest.mark.parametrize("status", [200, 403])
def test_api_not_entitled_continues_to_html(monkeypatch, status):
    transport = Mock()
    body = b'{"service-error":{"status":{"statusCode":"NOT_ENTITLED"}}}'
    if status == 403:
        transport.request.side_effect = RequestFailure(403, "denied", body=body)
    else:
        transport.request.return_value = {"status": status, "body": body, "headers": {}}
    client = elsevier.ElsevierClient(transport, {"ELSEVIER_API_KEY": "key"})
    monkeypatch.setattr(
        client, "validate_raw_payload_identity", lambda doi, meta, raw: raw
    )
    client.deps = replace(
        client.deps,
        bootstrap_browser_workflow=lambda *a, **k: BrowserWorkflowBootstrapResult(
            DOI, None, None, [], [], html_payload=payload("browser_html")
        ),
    )
    raw = client.fetch_raw_fulltext(DOI, META)
    assert raw.content.route_name == "browser_html"
    assert any(event.http_status == status for event in raw.trace)
    assert transport.request.call_count == 1


def test_html_confirmed_paywall_is_terminal(monkeypatch):
    client = elsevier.ElsevierClient(Mock(), {"ELSEVIER_API_KEY": "key"})
    monkeypatch.setattr(
        client,
        "_fetch_official_xml_payload",
        Mock(side_effect=ProviderFailure("no_result", "no XML")),
    )
    pdf = Mock()
    monkeypatch.setattr(client, "_fetch_official_pdf_payload", pdf)
    failure = paywall_failure(
        {"confirmed_article_paywall": {"confirmed": True, "provider": "elsevier"}}
    )
    client.deps = replace(
        client.deps, bootstrap_browser_workflow=Mock(side_effect=failure)
    )
    with pytest.raises(ProviderFailure) as caught:
        client.fetch_raw_fulltext(DOI, META)
    assert confirmed_paywall(caught.value)
    pdf.assert_not_called()


def test_macos_keeps_elsevier_browser_stages(monkeypatch, tmp_path):
    import platform
    import sys
    from paper_fetch.providers.browser_runtime.api import load_runtime_config

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    config = load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="elsevier", doi=DOI
    )
    assert selection.selected_backend({}, provider="elsevier") == "byparr"
    assert config.state_mode == "native"
    assert config.user_data_dir.name == "elsevier-camoufox"


def test_first_page_api_pdf_is_rejected_before_conversion(monkeypatch):
    client = elsevier.ElsevierClient(Mock(), {"ELSEVIER_API_KEY": "key"})
    client.transport.request.return_value = {
        "body": b"%PDF",
        "headers": {"X-ELS-Status": "limited to first page"},
    }
    converter = Mock()
    monkeypatch.setattr(elsevier, "pdf_fetch_result_from_response", converter)
    with pytest.raises(ProviderFailure, match="first page") as caught:
        client._fetch_official_pdf_payload(DOI)
    assert not confirmed_paywall(caught.value)
    converter.assert_not_called()


def test_html_identity_mismatch_continues_to_api_pdf(monkeypatch):
    client = elsevier.ElsevierClient(Mock(), {"ELSEVIER_API_KEY": "key"})
    monkeypatch.setattr(
        client,
        "_fetch_official_xml_payload",
        Mock(side_effect=ProviderFailure("no_result", "no XML")),
    )
    monkeypatch.setattr(
        client, "_fetch_official_pdf_payload", lambda *a, **k: payload("pdf_api")
    )

    def validate(doi, metadata, raw):
        if raw.content.route_kind == "html":
            raise ProviderFailure("identity_mismatch", "different DOI")
        return raw

    monkeypatch.setattr(client, "validate_raw_payload_identity", validate)
    client.deps = replace(
        client.deps,
        bootstrap_browser_workflow=lambda *a, **k: BrowserWorkflowBootstrapResult(
            DOI, None, None, [], [], html_payload=payload("browser_html")
        ),
    )
    raw = client.fetch_raw_fulltext(DOI, META)
    assert raw.content.route_name == "pdf_api"
    assert any(event.code == "identity_mismatch" for event in raw.trace)


def test_real_html_paywall_signal_stops_before_both_pdf_routes(monkeypatch):
    from paper_fetch.providers.browser_runtime.types import BrowserFetchedHtml

    url = "https://www.sciencedirect.com/science/article/pii/S016819232400090X"
    gate = f'<meta name="citation_doi" content="{DOI}"><div class="preview">Purchase PDF</div>'
    client = elsevier.ElsevierClient(Mock(), {})
    api_pdf, browser_pdf = Mock(), Mock()
    monkeypatch.setattr(client, "_fetch_official_pdf_payload", api_pdf)
    client.deps = replace(
        client.deps,
        load_runtime_config=lambda *a, **k: SimpleNamespace(
            timeout_ms=120000, backend="byparr"
        ),
        ensure_runtime_ready=lambda config: None,
        fetch_html_with_browser=lambda *a, **k: BrowserFetchedHtml(
            url, url, gate, 200, {}, "Example", "Purchase PDF", {}
        ),
        fetch_seeded_browser_pdf_payload=browser_pdf,
    )
    with pytest.raises(ProviderFailure) as caught:
        client.fetch_raw_fulltext(DOI, META)
    assert confirmed_paywall(caught.value)
    api_pdf.assert_not_called()
    browser_pdf.assert_not_called()
