"""Original rejection pages through real extraction/candidate selection/degradation.

Only transport/browser setup and PDF failure are injected; no historical markdown
or unrelated successful PDF supplies a recoverability claim.
"""

from tests.support.reviewed_block_provider_paths import _fetch_through_service
from unittest import mock
import json
from urllib.parse import unquote
from paper_fetch.extraction.html._metadata import parse_html_metadata
import pytest
from paper_fetch.providers import (
    browser_runtime,
    springer,
    annualreviews,
    pnas,
    science,
    wiley,
    ams,
    iop,
    mdpi,
    tandf,
    aip,
    oxfordacademic,
)
from paper_fetch.providers._pdf_common import PdfFetchFailure
from tests.block_fixtures import iter_block_samples
from tests.support._browser_workflow_deps import install_browser_workflow_deps


CLIENTS = {
    "aip": aip.AipClient,
    "ams": ams.AmsClient,
    "iop": iop.IopClient,
    "mdpi": mdpi.MdpiClient,
    "tandf": tandf.TandfClient,
    "annualreviews": annualreviews.AnnualreviewsClient,
    "pnas": pnas.PnasClient,
    "science": science.ScienceClient,
    "wiley": wiley.WileyClient,
}


@pytest.mark.parametrize(
    "fixture",
    [
        f
        for f in iter_block_samples()
        if f.raw_path.suffix == ".html" and f.provider != "oxfordacademic"
    ],
    ids=lambda f: f"{f.provider}:{f.doi}",
)
def test_original_rejection_page_obeys_fixed_stop_or_fallback_expectation(
    fixture, tmp_path
):
    raw = fixture.raw_path.read_text()
    capture_path = fixture.root / "acquisition/provenance.json"
    capture = (
        next(
            (
                r
                for r in json.loads(capture_path.read_text())["records"]
                if r["body_file"] == str(fixture.raw_path.relative_to(fixture.root))
            ),
            {},
        )
        if capture_path.exists()
        else {}
    )
    metadata = {
        **parse_html_metadata(raw, fixture.source_url),
        "provider": fixture.provider,
        "official_provider": True,
        "doi": fixture.doi,
        "title": fixture.title,
        "landing_page_url": fixture.source_url,
    }
    pdf = mock.Mock(
        side_effect=PdfFetchFailure(
            "pdf_download_failed", "Injected same-article PDF transport failure."
        )
    )
    if fixture.provider == "springer":
        client = springer.SpringerClient(mock.Mock(), {})
        response = {
            "status_code": 200,
            "headers": {"content-type": "text/html"},
            "body": raw.encode(),
            "url": fixture.source_url,
        }
        with (
            mock.patch.object(
                client,
                "_fetch_html_response",
                return_value=(response, fixture.source_url),
            ),
            mock.patch.object(springer, "fetch_pdf_over_http", pdf),
        ):
            envelope = _fetch_through_service(client, fixture, metadata)
    else:
        client = CLIENTS[fixture.provider](None, {})
        runtime = browser_runtime.BrowserRuntimeConfig(
            provider=fixture.provider,
            doi=fixture.doi,
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
        )
        fetched = browser_runtime.BrowserFetchedHtml(
            source_url=fixture.source_url,
            final_url=fixture.source_url,
            html=raw,
            response_status=capture.get("status_code"),
            response_headers=capture.get(
                "response_headers", {"content-type": "text/html"}
            ),
            title=fixture.title,
            summary="",
            browser_context_seed={},
        )
        install_browser_workflow_deps(
            client,
            load_runtime_config=mock.Mock(return_value=runtime),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=mock.Mock(return_value=fetched),
            warm_browser_context=mock.Mock(return_value={}),
            fetch_pdf_with_browser=pdf,
        )
        envelope = _fetch_through_service(client, fixture, metadata)
    article = envelope.article
    assert article is not None
    from paper_fetch.quality.access_boundary import (
        html_paywall_diagnostics,
        CONFIRMED_PAYWALL,
    )

    from tests.support.subscription_scenarios import BLOCK_PAYWALLS, BLOCK_NOT_PAYWALLS

    assert fixture.doi in BLOCK_PAYWALLS | BLOCK_NOT_PAYWALLS
    expected_gate = fixture.doi in BLOCK_PAYWALLS
    assert (
        bool(
            html_paywall_diagnostics(
                raw,
                metadata=metadata,
                source_url=fixture.source_url,
                provider=fixture.provider,
            )
        )
        is expected_gate
    )
    assert not article.quality.has_fulltext
    from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance

    assert (
        evaluate_fetch_acceptance(
            envelope, doi=fixture.doi, expected_doi=fixture.doi, asset_profile="none"
        ).overall
        == "limited"
    )
    if expected_gate:
        pdf.assert_not_called()
        assert f"trace:{CONFIRMED_PAYWALL}" in article.quality.source_trail
        assert article.quality.content_kind in {"abstract_only", "metadata_only"}
        return
    assert pdf.called
    assert any(e.code == "pdf_download_failed" for e in envelope.trace), envelope.trace
    assert article.quality.content_kind in {"abstract_only", "metadata_only"}
    trail = article.quality.source_trail
    assert f"fulltext:{fixture.provider}_html_fail" in trail
    assert f"fulltext:{fixture.provider}_pdf_fallback_ok" not in trail
    assert any(
        "Injected same-article PDF transport failure." in w
        for w in article.quality.warnings
    )
    candidates = [
        unquote(str(u)).lower()
        for call in pdf.call_args_list
        for u in call.args[1 if fixture.provider == "springer" else 0]
    ]
    assert candidates
    if fixture.provider == "mdpi":
        # MDPI's canonical volume/issue/article path contains no DOI string.
        assert candidates == [fixture.source_url.rstrip("/") + "/pdf"]
        return
    assert any(
        fixture.doi.lower() in u or fixture.doi.rsplit("/", 1)[1].lower() in u
        for u in candidates
    ), candidates
    assert any("pdf" in u.lower() for u in candidates), candidates


def test_oxford_original_browser_dom_rejects_then_tries_current_pdf_candidates():
    fixture = next(f for f in iter_block_samples() if f.provider == "oxfordacademic")
    raw = fixture.raw_path.read_text()
    metadata = {
        "doi": fixture.doi,
        "title": fixture.title,
        "landing_page_url": fixture.source_url,
        "provider": "oxfordacademic",
        "official_provider": True,
    }
    # The historical capture is DOM, so inject the article attempt with unknown
    # HTTP metadata instead of manufacturing a direct HTTP response.
    attempt = oxfordacademic.OxfordAcademicArticleAttempt(
        doi=fixture.doi,
        requested_url=fixture.source_url,
        final_url=fixture.source_url,
        html_text=raw,
        response_status=None,
        response_headers={},
        metadata=metadata,
    )
    client = oxfordacademic.OxfordAcademicClient(None, {})
    with (
        mock.patch.object(client, "_fetch_article_attempt", return_value=attempt),
        mock.patch.object(
            client,
            "_request_pdf_candidate",
            side_effect=PdfFetchFailure(
                "pdf_download_failed", "Injected PDF transport failure."
            ),
        ) as pdf,
    ):
        envelope = _fetch_through_service(client, fixture, metadata)
    assert [call.args[0] for call in pdf.call_args_list] == [
        f"https://academic.oup.com/doi/pdf/{fixture.doi}",
        f"https://academic.oup.com/doi/epdf/{fixture.doi}",
    ]
    assert not envelope.article.quality.has_fulltext
    assert envelope.article.quality.content_kind == "metadata_only"
    assert "fulltext:oxfordacademic_html_fail" in envelope.article.quality.source_trail
    assert (
        "fulltext:oxfordacademic_pdf_fallback_fail"
        in envelope.article.quality.source_trail
    )
    assert any(
        "Encountered a challenge or CAPTCHA page" in warning
        for warning in envelope.article.quality.warnings
    )
