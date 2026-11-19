"""Modern AMS URL identity through the shared parser and public entry points."""

import json
from unittest.mock import Mock

import pytest

from paper_fetch import auth, cli, publisher_identity, service
from paper_fetch.config import BROWSER_PROFILE_DIR_ENV_VAR
from paper_fetch.delivery.fetch_cache import FetchCache
from paper_fetch.delivery.requests import FetchPaperRequest
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.models import FetchEnvelope, SupplementaryResult
from paper_fetch.providers import supplementary as provider_supplementary
from paper_fetch.providers.ams import AmsClient
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_workflow import BrowserWorkflowClient
from paper_fetch.resolve.query import resolve_query
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow import fulltext, supplementary
from paper_fetch.workflow.batch_routing import expected_doi_from_query
from paper_fetch.workflow.types import FetchStrategy, PaperFetchFailure
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.fetch_fixtures import sample_envelope
from tests.support.publisher_profiles import write_verified_ams_profile

DOI = "10.1175/jcli-d-21-0790.1"
URL = "https://journals.ametsoc.org/view/journals/clim/35/18/JCLI-D-21-0790.1.xml"


@pytest.mark.parametrize("route", ["view", "downloadpdf", "downloadpdf/view"])
@pytest.mark.parametrize("extension", ["xml", "pdf"])
@pytest.mark.parametrize(
    "journal,article_id,issue",
    [
        ("clim", "JCLI-D-21-0790.1", "35/18"),
        ("hydr", "JHM-D-18-0159.2", "20/1"),
        ("apme", "JAMC-D-24-0048.1", "aop/JAMC-D-24-0048.1"),
        ("bams", "BAMS-D-25-12345.10", "aop/BAMS-D-25-12345.10"),
    ],
)
def test_modern_article_paths(route, extension, journal, article_id, issue):
    url = f"https://journals.ametsoc.org/{route}/journals/{journal}/{issue}/{article_id}.{extension}"
    doi = "10.1175/" + article_id.lower()
    assert publisher_identity.extract_doi_from_url(url) == doi
    assert expected_doi_from_query(url) == doi


@pytest.mark.parametrize(
    "url",
    [
        URL,
        URL + "?download=true#abstract",
        URL.replace("journals.ametsoc.org", "archive.journals.ametsoc.org"),
        URL.upper(),
        URL.replace("JCLI-D-21-0790.1", "JCLI%2dD%2d21%2d0790%2e1"),
        URL.replace("/view/journals/", "/%76iew%2Fjournals/") + "?x=1#fig1",
    ],
)
def test_resolver_preserves_input_and_never_requests_405_landing(url):
    transport = RecordingTransport(
        {("GET", url): {"status_code": 405, "headers": {}, "body": b""}}
    )
    resolved = resolve_query(url, transport=transport, env={})
    assert resolved.query_kind == "url"
    assert resolved.query == resolved.landing_url == url
    assert resolved.doi == DOI
    assert resolved.provider_hint == "ams"
    assert resolved.confidence == 1.0
    assert transport.calls == []


@pytest.mark.parametrize(
    "url",
    [
        URL.replace("journals.ametsoc.org", "ametsoc.org"),
        URL.replace("journals.ametsoc.org", "journals.ametsoc.org.example.com"),
        URL.replace("journals.ametsoc.org", "fakejournals.ametsoc.org"),
        URL.replace("/view/", "/doc/"),
        URL.replace("/35/18/", "/"),
        URL.replace("/35/18/", "/aop/JCLI-D-21-0791.1/"),
        URL.replace("/35/18/", "/aop/"),
        URL.replace(".xml", ".jpg"),
        URL + "/extra",
        URL + ";extra",
        URL.replace("JCLI-D-21-0790.1", "full-JCLI-D-21-0790.1"),
        URL.replace("JCLI-D-21-0790.1", "JCLI-D-2021-0790.1"),
        URL.replace("JCLI-D-21-0790.1", "JCLI-D-21-0790"),
        URL.replace("JCLI-D-21-0790.1", "JCLI-D-21-0790_1"),
        URL.replace("JCLI-D-21-0790.1", "JCLI-D-21-0790.1-f1"),
        URL.replace("JCLI-D-21-0790.1", "JCLI-D-21-xyz.1"),
        URL.replace("JCLI-D-21-0790.1", "JCLI-D-21-0790.x"),
    ],
)
def test_unrelated_urls_do_not_derive_doi(url):
    assert publisher_identity.extract_doi_from_url(url) is None


def test_explicit_doi_keeps_priority():
    assert publisher_identity.extract_doi_from_url(URL + "?doi=10.1175/EXPLICIT") == (
        "10.1175/explicit"
    )
    assert (
        publisher_identity.extract_doi_from_url(
            URL.replace("JCLI-D-21-0790.1.xml", "10.1175/EXPLICIT")
        )
        == "10.1175/explicit"
    )


@pytest.fixture
def boundaries(monkeypatch, tmp_path):
    env = {BROWSER_PROFILE_DIR_ENV_VAR: str(tmp_path / "profile")}
    monkeypatch.setattr(cli, "build_runtime_env", lambda: env)
    request = Mock(side_effect=AssertionError("identity must not request HTTP"))
    monkeypatch.setattr(HttpTransport, "request", request)
    authenticate = Mock()
    monkeypatch.setattr(cli, "authenticate_provider_profile", authenticate)
    return env, request, authenticate


@pytest.mark.parametrize("target", ["paper", "supplementary"])
def test_cli_url_reports_auth_required(
    boundaries, monkeypatch, capsys, tmp_path, target
):
    _, request, authenticate = boundaries
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    fetch = Mock(side_effect=AssertionError("must stop before acquisition"))
    monkeypatch.setattr(cli, "fetch_paper", fetch)
    assert (
        cli.main(
            ["fetch", "--query", URL, "--target", target, "--output-dir", str(tmp_path)]
        )
        == 1
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["error"]["status"] == "auth_required"
    assert receipt["error"]["stage"] == "auth_preflight"
    request.assert_not_called()
    authenticate.assert_not_called()
    fetch.assert_not_called()


def test_interactive_url_authentication_and_batch_deduplication(
    boundaries, monkeypatch, capsys, tmp_path
):
    env, request, authenticate = boundaries
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    authenticate.side_effect = lambda **kw: write_verified_ams_profile(
        auth.ams_profile_path(kw["env"])
    )

    def acquire(query, *, context, **kwargs):
        resolved = service.resolve_paper(query, context=context)
        assert resolved.doi == DOI
        assert resolved.landing_url == URL
        assert auth.has_verified_ams_profile(env)
        return sample_envelope(modes=kwargs["modes"], doi=resolved.doi)

    fetch = Mock(side_effect=acquire)
    monkeypatch.setattr(cli, "fetch_paper", fetch)
    queries = tmp_path / "queries.txt"
    queries.write_text(f"{URL}\n{DOI}\n")
    assert (
        cli.main(
            [
                "fetch",
                "--query-file",
                str(queries),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    receipts = [json.loads(line) for line in output.out.splitlines()]
    assert len(receipts) == 2
    assert all(receipt["target_satisfied"] for receipt in receipts)
    assert [receipt["query"] for receipt in receipts] == [URL, DOI]
    authenticate.assert_called_once()
    fetch.assert_called_once()
    request.assert_not_called()


@pytest.mark.parametrize("target", ["paper", "supplementary"])
@pytest.mark.parametrize("verified", [False, True])
def test_python_url_uses_real_resolver_and_ams_gate(
    boundaries, monkeypatch, tmp_path, target, verified
):
    env, request, _ = boundaries
    if verified:
        write_verified_ams_profile(auth.ams_profile_path(env))

    def metadata(resolved, **kwargs):
        assert resolved.doi == DOI
        assert resolved.landing_url == URL
        return {"doi": DOI, "landing_page_url": URL}, "ams", []

    monkeypatch.setattr(fulltext, "fetch_metadata_for_resolved_query", metadata)
    monkeypatch.setattr(supplementary, "fetch_metadata_for_resolved_query", metadata)
    acquisition = Mock(side_effect=ProviderFailure("no_access", "provider boundary"))
    if target == "paper":
        monkeypatch.setattr(BrowserWorkflowClient, "fetch_raw_fulltext", acquisition)
    else:
        monkeypatch.setattr(provider_supplementary, "_browser_index", acquisition)
    with RuntimeContext(env=env, download_dir=tmp_path) as runtime:
        monkeypatch.setattr(
            runtime, "get_clients", lambda: {"ams": AmsClient(runtime.transport, env)}
        )
        with pytest.raises(PaperFetchFailure) as error:
            service.fetch_paper(
                URL,
                target=target,
                context=runtime,
                strategy=FetchStrategy(allow_metadata_only_fallback=False),
            )
    assert error.value.status == ("no_access" if verified else "auth_required")
    if verified:
        acquisition.assert_called_once()
        offset = 0 if target == "paper" else 1
        assert acquisition.call_args.args[offset] == DOI
        assert acquisition.call_args.args[offset + 1]["landing_page_url"] == URL
    else:
        acquisition.assert_not_called()
    request.assert_not_called()


def test_url_cache_reuses_doi_entry_without_auth(boundaries, tmp_path):
    env, request, authenticate = boundaries
    cache = FetchCache(tmp_path)
    cached_request = FetchPaperRequest(query=DOI, prefer_cache=True)
    cache.write_fetch_envelope(
        sample_envelope(modes={"markdown"}, doi=DOI), cached_request
    )
    with RuntimeContext(env=env, download_dir=tmp_path) as runtime:
        loaded = cache.load_fetch_envelope(
            cached_request.model_copy(update={"query": URL}),
            resolve_paper_fn=service.resolve_paper,
            context=runtime,
        )
    assert loaded is not None and loaded.doi == DOI
    assert loaded.markdown == "# Example Article\n\nExample body.\n"
    assert not auth.has_verified_ams_profile(env)
    authenticate.assert_not_called()
    request.assert_not_called()


def test_cli_resolve_does_not_authenticate(boundaries, capsys):
    _, request, authenticate = boundaries
    assert cli.main(["resolve", "--query", URL]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["doi"] == DOI
    assert result["landing_url"] == URL
    authenticate.assert_not_called()
    request.assert_not_called()


def test_cli_check_does_not_authenticate(boundaries, monkeypatch, capsys):
    _, request, authenticate = boundaries
    monkeypatch.setattr(RuntimeContext, "get_clients", lambda self: {})
    request.side_effect = RequestFailure(405, "landing unavailable", url=URL)
    assert cli.main(["check", "--query", URL]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["doi"] == DOI
    assert result["state"] == "unknown"
    authenticate.assert_not_called()
    # check may probe availability after the no-I/O identity resolution.
    request.assert_called_once()


def test_interactive_url_supplementary_continues_after_auth(
    boundaries, monkeypatch, capsys, tmp_path
):
    env, request, authenticate = boundaries
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    authenticate.side_effect = lambda **kw: write_verified_ams_profile(
        auth.ams_profile_path(kw["env"])
    )
    local = tmp_path / "supplement.txt"
    local.write_text("supplementary boundary asset")

    def acquire(query, *, context, target, **kwargs):
        resolved = service.resolve_paper(query, context=context)
        assert resolved.doi == DOI and resolved.landing_url == URL
        assert target == "supplementary"
        assert auth.has_verified_ams_profile(env)
        return FetchEnvelope(
            doi=DOI,
            source="ams",
            target=target,
            supplementary=SupplementaryResult(
                assets=[{"path": str(local), "url": URL + "?supplement=1"}],
                discovery_complete=True,
                identity_verified=True,
                source_urls=[URL],
            ),
            markdown="Supplementary index\n",
        )

    fetch = Mock(side_effect=acquire)
    monkeypatch.setattr(cli, "fetch_paper", fetch)
    assert (
        cli.main(
            [
                "fetch",
                "--query",
                URL,
                "--target",
                "supplementary",
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["target_satisfied"]
    authenticate.assert_called_once()
    fetch.assert_called_once()
    request.assert_not_called()
