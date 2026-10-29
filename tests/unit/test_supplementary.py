from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

import pytest

from paper_fetch import service
from paper_fetch.mcp.fetch_cache import (
    FetchCache,
    cache_request_fingerprint,
    cached_payload_satisfies_request,
    cached_request_matches,
    envelope_from_payload,
    request_cache_payload,
)
from paper_fetch.mcp.schemas import BatchFetchRequest, FetchPaperRequest
from paper_fetch.providers.base import ProviderClient, ProviderFailure
from paper_fetch.providers.supplementary import _xml_index
from paper_fetch.providers.plos import PlosClient
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.providers.science import ScienceClient
from paper_fetch.providers.browser_runtime import BrowserFetchedHtml
from paper_fetch.providers.browser_workflow.shared import default_browser_workflow_deps
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from paper_fetch.workflow.rendering import save_markdown_to_disk
from paper_fetch.models import RenderOptions
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.supplementary import DOI, META, URL, XML_URL, envelope, html_page


def response(url, body, content_type="text/html"):
    return {
        "url": url,
        "status_code": 200,
        "headers": {"content-type": content_type},
        "body": body.encode(),
    }


def test_targets_validate_and_batch_propagates():
    assert FetchPaperRequest(query=DOI).target == "paper"
    batch = BatchFetchRequest(queries=[DOI], target="supplementary", save_markdown=True)
    assert batch.to_fetch_request(DOI).target == "supplementary"
    assert batch.to_fetch_request(DOI).requested_modes() == {"markdown"}
    with pytest.raises(ValueError):
        FetchPaperRequest(query=DOI, target="data")
    with pytest.raises(ValueError):
        service.fetch_paper(DOI, target="data")


def test_unsupported_provider_does_not_call_body():
    client = ProviderClient()
    with RuntimeContext(env={}) as context:
        with pytest.raises(ProviderFailure, match="does not support") as caught:
            client.fetch_supplementary(DOI, META, None, context=context)
    assert caught.value.code == "not_supported"


def test_jats_abstract_only_index_uses_supplement_nodes_only():
    xml = f'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><article-id pub-id-type="doi">{DOI}</article-id></article-meta></front><back><supplementary-material xlink:href="{DOI}.s001"><label>S1 Dataset</label></supplementary-material></back></article>'''
    transport = RecordingTransport(
        {("GET", XML_URL): response(XML_URL, xml, "application/xml")}
    )
    client = PlosClient(transport, {})
    with RuntimeContext(env={}, transport=transport) as context:
        raw = _xml_index(client, DOI, META, context)
    assert len(raw.content.extracted_assets) == 1
    assert raw.content.extracted_assets[0]["download_url"].endswith(
        f"type=supplementary&id={DOI}.s001"
    )


def test_identity_mismatch_stops_before_attachment_download():
    transport = RecordingTransport(
        {("GET", URL): response(URL, html_page("10.1371/other"))}
    )
    client = SpringerClient(transport, {})
    with RuntimeContext(env={}, transport=transport) as context:
        with pytest.raises(ProviderFailure) as caught:
            client.fetch_supplementary(DOI, META, None, context=context)
    assert caught.value.code == "identity_mismatch"
    assert len(transport.calls) == 1


def test_browser_index_ignores_body_and_requests_supplementary_mode():
    deps = default_browser_workflow_deps()
    fetched = BrowserFetchedHtml(
        source_url=URL,
        final_url=URL,
        html=html_page(),
        response_status=200,
        response_headers={},
        title="Attachment contract",
        summary="",
        browser_context_seed={},
    )
    fetcher = mock.Mock(return_value=fetched)
    deps = replace(
        deps,
        load_runtime_config=mock.Mock(return_value=SimpleNamespace()),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=fetcher,
    )
    client = ScienceClient(RecordingTransport({}), {}, deps=deps)
    with RuntimeContext(env={}) as context:
        result, acquisition = client.fetch_supplementary(
            DOI, META, None, context=context
        )
    assert len(result.assets) == 1
    assert result.assets[0]["url"].endswith("support.csv")
    assert result.status == "degraded"
    assert fetcher.call_args.kwargs["options"].supplementary_index
    assert not fetcher.call_args.kwargs["readiness"].wait_for_article_body
    assert acquisition.transport == "browser"


@pytest.mark.parametrize("profile", ["none", "body", "all"])
def test_supplementary_scope_is_independent_of_body_profile(profile):
    transport = RecordingTransport({("GET", URL): response(URL, html_page())})
    client = SpringerClient(transport, {})
    with RuntimeContext(
        env={}, transport=transport, artifact_mode="none", asset_profile=profile
    ) as context:
        result, _ = client.fetch_supplementary(
            DOI, META, context.artifact_store.asset_download_dir, context=context
        )
    assert result.discovery_complete
    assert len(result.assets) == 1
    assert result.assets[0]["archive_state"] == "not_archived"
    assert not result.assets[0].get("path")


@pytest.mark.parametrize(
    "assets,failures,complete,overall,asset_status,code",
    [
        (
            [{"url": "https://x/s", "path": "/a"}],
            [],
            True,
            "complete",
            "complete",
            None,
        ),
        (
            [{"url": "https://x/s", "path": "/a"}, {"url": "https://x/t"}],
            [{"reason": "no_access"}],
            True,
            "degraded",
            "degraded",
            None,
        ),
        (
            [{"url": "https://x/s"}],
            [{"reason": "no_access"}],
            True,
            "failed",
            "failed",
            "no_access",
        ),
        ([], [], True, "failed", "not_applicable", "no_result"),
        ([{"url": "https://x/s"}], [], True, "degraded", "degraded", None),
        ([], [{"reason": "index_failed"}], False, "failed", "failed", "index_failed"),
    ],
)
def test_supplementary_acceptance(
    assets, failures, complete, overall, asset_status, code
):
    report = evaluate_fetch_acceptance(
        envelope(assets, failures=failures, complete=complete),
        asset_profile="none",
        requested_outputs={"article", "markdown"},
    )
    assert report.target == "supplementary"
    assert not report.content.requested
    assert report.content.status == "unavailable"
    assert report.overall == overall
    assert report.asset.status == asset_status
    assert report.fetch.code == code


def test_index_save_and_cache_round_trip(tmp_path):
    asset = tmp_path / "support.csv"
    asset.write_text("a,b\n1,2\n")
    result = envelope(
        [
            {
                "heading": "S1",
                "url": "https://x/s",
                "path": str(asset),
                "downloaded_bytes": asset.stat().st_size,
            }
        ]
    )
    from paper_fetch.workflow.supplementary import render_supplementary_index

    result.markdown = render_supplementary_index(result.supplementary)
    saved = save_markdown_to_disk(result, output_dir=tmp_path, render=RenderOptions())
    assert saved.name.endswith("_supplementary.md")
    assert "S1" in saved.read_text()
    loaded = envelope_from_payload(result.to_dict())
    assert loaded.supplementary == result.supplementary
    cache = FetchCache(tmp_path)
    request = FetchPaperRequest(query=DOI, target="supplementary", prefer_cache=True)
    cache.write_fetch_envelope(result, request)
    with RuntimeContext(env={}) as context:
        assert cache.load_fetch_envelope(
            request,
            resolve_paper_fn=mock.Mock(side_effect=AssertionError),
            context=context,
        ).supplementary.assets[0]["path"] == str(asset)
        assert (
            cache.load_fetch_envelope(
                FetchPaperRequest(query=DOI, prefer_cache=True),
                resolve_paper_fn=mock.Mock(side_effect=AssertionError),
                context=context,
            )
            is None
        )
        asset.unlink()
        assert (
            cache.load_fetch_envelope(
                request,
                resolve_paper_fn=mock.Mock(side_effect=AssertionError),
                context=context,
            )
            is None
        )


def test_target_cache_isolation_and_default_fingerprint_compatibility():
    paper = FetchPaperRequest(query=DOI)
    supplementary = FetchPaperRequest(query=DOI, target="supplementary")
    payload = request_cache_payload(paper)
    assert "target" not in payload
    assert cache_request_fingerprint(DOI, payload) != cache_request_fingerprint(
        DOI, request_cache_payload(supplementary)
    )
    assert not cached_request_matches(payload, supplementary)
    assert not cached_request_matches(request_cache_payload(supplementary), paper)
    assert not cached_payload_satisfies_request(envelope().to_dict(), paper)
    assert not cached_payload_satisfies_request(
        envelope(complete=False).to_dict(), supplementary
    )


def test_arxiv_ancillary_is_independent_of_html_pdf_and_source_archive():
    from paper_fetch.providers.arxiv import ArxivClient

    arxiv_id = "2606.00587v2"
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    detail_url = f"https://arxiv.org/src/{arxiv_id}/anc"
    abstract = f'<meta name="citation_arxiv_id" content="{arxiv_id}"><div id="abs"><h1 class="title">Title</h1><div class="arxividv"><a href="{abs_url}">v2</a></div><div class="ancillary"><a href="{detail_url}">Ancillary files</a></div></div>'
    details = f'<div id="content"><h2>Ancillary files for <a href="{abs_url}">{arxiv_id}</a></h2><p>There are 1 ancillary files</p><a class="anc-file-name" href="{detail_url}/data.csv">data.csv</a></div>'
    transport = RecordingTransport(
        {
            ("GET", abs_url): response(abs_url, abstract),
            ("GET", detail_url): response(detail_url, details),
        }
    )
    client = ArxivClient(transport, {})
    with RuntimeContext(env={}, transport=transport) as context:
        result, _ = client.fetch_supplementary(
            f"10.48550/arxiv.{arxiv_id}", {"arxiv_id": arxiv_id}, None, context=context
        )
    assert result.discovery_complete and result.identity_verified
    assert [asset["url"] for asset in result.assets] == [detail_url + "/data.csv"]
    assert len(transport.calls) == 2


@pytest.mark.parametrize("broken", [False, True])
def test_ieee_multimedia_discovery_failure_is_not_an_empty_result(broken):
    import json
    from paper_fetch.providers.ieee import IeeeClient

    doi = "10.1109/test.123"
    url = "https://ieeexplore.ieee.org/document/123/"
    api = "https://ieeexplore.ieee.org/rest/document/123/multimedia"
    landing = f"<script>xplGlobal.document.metadata = {json.dumps({'doi': doi, 'articleNumber': '123', 'sections': {'multimedia': 'true'}})};</script>"
    api_body = (
        "{}"
        if broken
        else json.dumps(
            {"multimedia": [{"filePath": "/data/file.mp4", "fileName": "Video.mp4"}]}
        )
    )
    transport = RecordingTransport(
        {
            ("GET", url): response(url, landing),
            ("GET", api): response(api, api_body, "application/json"),
        }
    )
    client = IeeeClient(transport, {})
    with RuntimeContext(env={}, transport=transport) as context:
        result, _ = client.fetch_supplementary(
            doi, {"doi": doi, "landing_page_url": url}, None, context=context
        )
    assert result.discovery_complete is not broken
    if broken:
        assert result.status == "ieee_multimedia_discovery_failed"
    else:
        assert result.assets[0]["url"].endswith("file.mp4")


def test_supplementary_provenance_requires_the_material_provider():
    result = envelope([{"url": "https://x/s", "path": "/a"}])
    result.acquisition = replace(result.acquisition, provider="crossref")
    report = evaluate_fetch_acceptance(result, asset_profile="all")
    assert report.provenance.status == "partial"
    assert report.overall == "degraded"


def test_unverified_index_is_not_reported_as_complete_empty_discovery():
    transport = RecordingTransport(
        {("GET", URL): response(URL, "<html><body>Index unavailable</body></html>")}
    )
    client = SpringerClient(transport, {})
    with RuntimeContext(env={}, transport=transport) as context:
        with pytest.raises(ProviderFailure) as caught:
            client.fetch_supplementary(DOI, META, None, context=context)
    assert caught.value.code == "error"


@pytest.mark.parametrize(
    "reason,has_attachment",
    [
        (None, False),
        ("parser_failed", False),
        ("parser_failed", True),
        ("insufficient_body", True),
        ("article_container_not_found", False),
        ("article_container_not_found", True),
    ],
)
@pytest.mark.parametrize("archive", [False, True])
def test_browser_discovery_preserves_failures_and_recovered_assets(
    monkeypatch, tmp_path, reason, has_attachment, archive
):
    from paper_fetch.extraction.html.signals import HtmlExtractionFailure
    from paper_fetch.providers.browser_workflow import assets as browser_assets

    failure = HtmlExtractionFailure(reason, "Original parser diagnostic")
    failure.details = {"selector": ".article-body", "phase": "scope"}
    scanner = mock.Mock(side_effect=failure) if reason else mock.Mock(return_value=[])
    monkeypatch.setattr(browser_assets, "_cached_browser_workflow_assets", scanner)
    page = html_page() if has_attachment else html_page(links="")
    fetched = BrowserFetchedHtml(
        source_url=URL,
        final_url=URL,
        html=page,
        response_status=200,
        response_headers={},
        title="Attachment contract",
        summary="",
        browser_context_seed={},
    )
    deps = replace(
        default_browser_workflow_deps(),
        load_runtime_config=mock.Mock(return_value=SimpleNamespace()),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=mock.Mock(return_value=fetched),
    )
    transport = RecordingTransport({})
    client = ScienceClient(transport, {}, deps=deps)
    downloader = mock.Mock(
        side_effect=lambda *a, **k: {
            "assets": [{**asset, "path": "support.csv"} for asset in k["assets"]],
            "asset_failures": [],
        }
    )
    monkeypatch.setattr(client, "_download_browser_backed_related_assets", downloader)
    monkeypatch.setattr(
        client,
        "fetch_raw_fulltext",
        mock.Mock(side_effect=AssertionError("body request")),
    )
    with RuntimeContext(env={}, transport=transport) as context:
        result, _ = client.fetch_supplementary(
            DOI, META, tmp_path if archive else None, context=context
        )
    failed = reason not in {None, "article_container_not_found"}
    assert result.discovery_complete is not failed
    assert len(result.assets) == int(has_attachment)
    assert result.asset_failures == (
        [
            {
                "kind": "supplementary",
                "source_url": URL,
                "reason": reason,
                "message": failure.message,
                "details": failure.details,
            }
        ]
        if failed
        else []
    )
    assert downloader.call_count == int(archive and has_attachment)
    if archive and has_attachment:
        assert result.assets[0]["path"] == "support.csv"
    assert transport.calls == []
