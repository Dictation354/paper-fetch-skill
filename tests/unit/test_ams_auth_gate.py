"""AMS authentication requirements at acquisition and CLI boundaries."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import threading

import pytest

from paper_fetch import auth, cli, targeted_assets
from paper_fetch.config import BROWSER_PROFILE_DIR_ENV_VAR
from paper_fetch.delivery.fetch_cache import FetchCache
from paper_fetch.failure import FailureDiagnostics
from paper_fetch.http import RequestCancelledError
from paper_fetch.providers.ams import AmsClient
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime.profile import METADATA_FILENAME
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from paper_fetch.workflow.fulltext import (
    _try_official_provider,
    _ProviderAttemptOutputs,
)
from paper_fetch.workflow.types import FetchStrategy, PaperFetchFailure
from tests.support.fetch_fixtures import sample_envelope
from tests.support.publisher_profiles import write_verified_ams_profile


DOI = "10.1175/jcli-d-23-0738.1"
URL = auth.AUTH_TARGETS["ams"].url


@pytest.fixture
def environment(tmp_path):
    return {BROWSER_PROFILE_DIR_ENV_VAR: str(tmp_path / "profile")}


@pytest.mark.parametrize(
    "state", ["missing", "cookies", "ordinary", "wrong_owner", "no_reopen", "verified"]
)
def test_requires_auth_marker_and_native_summary(environment, state):
    path = auth.ams_profile_path(environment)
    if state != "missing":
        path.mkdir(parents=True)
        (path / "cookies.sqlite").write_bytes(b"cookies")
    if state not in {"missing", "cookies"}:
        write_verified_ams_profile(path)
        file = path / METADATA_FILENAME
        data = json.loads(file.read_text())
        if state == "ordinary":
            data.pop("auth")
        elif state == "wrong_owner":
            data["provider"] = "wiley"
        elif state == "no_reopen":
            data["auth"]["native_profile_verified"] = False
        file.write_text(json.dumps(data))
    assert auth.has_verified_ams_profile(environment) == (state == "verified")
    # The current and original auth digests deliberately differ in this fixture.
    if state != "verified":
        with pytest.raises(ProviderFailure) as error:
            auth.require_ams_auth(environment, provider="ams")
        assert error.value.code == "auth_required"
    else:
        auth.require_ams_auth(environment, provider="ams")


@pytest.mark.parametrize(
    "entry", ["body", "supplementary", "image_discovery", "image_download"]
)
def test_python_network_entries_stop_before_transport(environment, entry):
    transport = Mock()
    client = AmsClient(transport, environment)
    state = targeted_assets.AssetContext(DOI, "ams", URL)
    with RuntimeContext(env=environment, transport=transport) as runtime:
        with pytest.raises(ProviderFailure) as error:
            if entry == "body":
                client.fetch_raw_fulltext(DOI, {"doi": DOI}, context=runtime)
            elif entry == "supplementary":
                client.fetch_supplementary(DOI, {"doi": DOI}, None, context=runtime)
            elif entry == "image_discovery":
                targeted_assets._load_source(state, runtime)
            else:
                targeted_assets._download_selected(state, [], Path("unused"), runtime)
        assert error.value.code == "auth_required"
        assert error.value.diagnostics.stage == "auth_preflight"
    assert transport.mock_calls == []


def test_auth_failure_cannot_become_metadata_success(environment, tmp_path):
    with RuntimeContext(env=environment, download_dir=tmp_path) as runtime:
        with pytest.raises(PaperFetchFailure) as error:
            _try_official_provider(
                doi=DOI,
                metadata={"doi": DOI},
                provider_name="ams",
                strategy=FetchStrategy(allow_metadata_only_fallback=True),
                artifact_store=runtime.artifact_store,
                context=runtime,
                clients={"ams": AmsClient(Mock(), environment)},
                outputs=_ProviderAttemptOutputs(),
            )
    assert error.value.status == "auth_required"


def test_local_images_need_no_authentication(environment, tmp_path):
    local = tmp_path / "formula.png"
    local.write_bytes(b"existing local asset")
    state = targeted_assets.AssetContext(
        DOI,
        "ams",
        URL,
        assets=[{"asset_id": "formula1", "kind": "formula", "path": str(local)}],
        discovery_complete=True,
    )
    assert not targeted_assets.selected_assets_need_network(state, kind="formula")
    with RuntimeContext(env=environment) as runtime:
        result = targeted_assets.fetch_selected_assets(
            state, kind="formula", runtime=runtime
        )
    assert result["status"] == "ok"
    assert result["results"][0]["path"] == str(local)


@pytest.fixture
def cli_boundary(monkeypatch, environment):
    monkeypatch.setattr(cli, "build_runtime_env", lambda: environment)
    monkeypatch.setattr(
        cli,
        "resolve_paper",
        lambda q, **kw: ResolvedQuery(
            query=q,
            query_kind="doi",
            doi=q,
            provider_hint="ams" if q.startswith("10.1175/") else "elsevier",
        ),
    )
    fetch = Mock(side_effect=lambda q, **kw: sample_envelope(modes=kw["modes"], doi=q))
    monkeypatch.setattr(cli, "fetch_paper", fetch)
    return fetch


def test_noninteractive_cli_receipt_reports_auth_required(
    cli_boundary, monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main(["fetch", "--query", DOI, "--output-dir", str(tmp_path)]) == 1
    receipt = json.loads(capsys.readouterr().out)
    assert not receipt["target_satisfied"]
    assert receipt["error"]["status"] == "auth_required"
    assert receipt["error"]["stage"] == "auth_preflight"
    assert receipt["acceptance"]["fetch"] == "action_required"
    cli_boundary.assert_not_called()


@pytest.mark.parametrize("controlled", [False, True])
def test_control_stdin_never_prompts(environment, monkeypatch, controlled):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: controlled)
    authenticate = Mock()
    monkeypatch.setattr(cli, "authenticate_provider_profile", authenticate)
    with RuntimeContext(env=environment) as runtime:
        with pytest.raises(ProviderFailure, match="paper-fetch auth ams"):
            cli._ensure_cli_ams_auth(SimpleNamespace(control_stdin=controlled), runtime)
    authenticate.assert_not_called()


def test_interactive_auth_continues_and_keeps_stdout_json(
    cli_boundary, environment, monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    def authenticate(**kwargs):
        write_verified_ams_profile(auth.ams_profile_path(kwargs["env"]))

    authenticate = Mock(side_effect=authenticate)
    monkeypatch.setattr(cli, "authenticate_provider_profile", authenticate)
    assert cli.main(["fetch", "--query", DOI, "--output-dir", str(tmp_path)]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["target_satisfied"] is True
    assert "requires authentication" in output.err
    authenticate.assert_called_once()
    cli_boundary.assert_called_once()


@pytest.mark.parametrize("cancelled", [False, True])
def test_failed_or_cancelled_auth_stops_acquisition(
    cli_boundary, monkeypatch, capsys, tmp_path, cancelled
):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    failure = (
        RequestCancelledError("Cancelled")
        if cancelled
        else ProviderFailure(
            "auth_replay_failed",
            "Reopen failed",
            diagnostics=FailureDiagnostics(provider="ams", stage="auth_profile_reopen"),
        )
    )
    monkeypatch.setattr(cli, "authenticate_provider_profile", Mock(side_effect=failure))
    assert cli.main(["fetch", "--query", DOI, "--output-dir", str(tmp_path)]) == 1
    receipt = json.loads(capsys.readouterr().out)
    assert not receipt["target_satisfied"]
    assert receipt["error"]["status"] == (
        "aborted" if cancelled else "auth_replay_failed"
    )
    if cancelled:
        assert receipt["error"]["stage"] == "auth_manual_check"
    if not cancelled:
        assert receipt["error"]["stage"] == "auth_profile_reopen"
        assert receipt["error"]["reason"] == "Reopen failed"
    cli_boundary.assert_not_called()


def test_cache_hit_bypasses_resolution_and_auth(
    cli_boundary, monkeypatch, capsys, tmp_path
):
    cached = sample_envelope(modes={"article", "markdown"}, doi=DOI)
    monkeypatch.setattr(FetchCache, "load_fetch_envelope", lambda *a, **kw: cached)
    monkeypatch.setattr(
        cli, "resolve_paper", Mock(side_effect=AssertionError("must reuse cache"))
    )
    monkeypatch.setattr(
        cli,
        "authenticate_provider_profile",
        Mock(side_effect=AssertionError("must reuse cache")),
    )
    assert (
        cli.main(
            ["fetch", "--query", DOI, "--prefer-cache", "--output-dir", str(tmp_path)]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["target_satisfied"]
    cli_boundary.assert_not_called()


def test_batch_cache_hits_need_no_auth(cli_boundary, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        FetchCache,
        "load_fetch_envelope",
        lambda self, request, **kw: sample_envelope(
            modes=request.requested_modes(),
            doi=request.query,
        ),
    )
    authenticate = Mock(
        side_effect=AssertionError("cached batch must not authenticate")
    )
    monkeypatch.setattr(cli, "authenticate_provider_profile", authenticate)
    queries = tmp_path / "queries.txt"
    queries.write_text(f"{DOI}\n10.1175/second\n")
    assert (
        cli.main(
            [
                "fetch",
                "--query-file",
                str(queries),
                "--prefer-cache",
                "--output-dir",
                str(tmp_path / "papers"),
            ]
        )
        == 0
    )
    assert all(
        json.loads(line)["target_satisfied"]
        for line in capsys.readouterr().out.splitlines()
    )
    authenticate.assert_not_called()
    cli_boundary.assert_not_called()


@pytest.mark.parametrize("auth_success", [True, False, "cancel"])
def test_batch_authenticates_once_on_scheduler_and_keeps_other_entries(
    cli_boundary, environment, monkeypatch, capsys, tmp_path, auth_success
):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    threads = []

    def authenticate(**kwargs):
        threads.append(threading.get_ident())
        assert cli_boundary.call_count == 0
        if auth_success == "cancel":
            raise auth.AuthCancelledError(
                "Authentication cancelled", provider="ams", stage="auth_manual_check"
            )
        if not auth_success:
            raise ProviderFailure(
                "auth_replay_failed",
                "Reopen failed",
                diagnostics=FailureDiagnostics(
                    provider="ams", stage="auth_profile_reopen"
                ),
            )
        write_verified_ams_profile(auth.ams_profile_path(kwargs["env"]))

    monkeypatch.setattr(cli, "authenticate_provider_profile", authenticate)
    queries = tmp_path / "queries.txt"
    queries.write_text(f"{DOI}\n10.1175/second\n10.1016/other\n")
    assert cli.main(
        [
            "fetch",
            "--query-file",
            str(queries),
            "--batch-concurrency",
            "3",
            "--output-dir",
            str(tmp_path / "papers"),
        ]
    ) == int(auth_success is not True)
    receipts = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert threads == [threading.get_ident()]
    assert len(receipts) == 3
    assert cli_boundary.call_count == (3 if auth_success is True else 1)
    if auth_success is not True:
        failed = [r for r in receipts if r["error"]]
        assert len(failed) == 2
        assert {r["error"]["stage"] for r in failed} == {
            "auth_manual_check" if auth_success == "cancel" else "auth_profile_reopen"
        }


def test_auth_required_maps_to_action_required():
    report = evaluate_fetch_acceptance(
        None, asset_profile="none", failure_code="auth_required"
    )
    assert report.fetch.status == report.overall == "action_required"
