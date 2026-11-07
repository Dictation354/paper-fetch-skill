"""PNAS backend policy, isolated preparation and static probe boundary contracts."""

import hashlib
import io
import json
from types import SimpleNamespace
import zipfile

import pytest

from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime import platforms, selection
from paper_fetch.providers.browser_runtime import byparr_preparation as prep
from paper_fetch.providers.browser_runtime.api import load_runtime_config
from paper_fetch.providers.browser_runtime.types import (
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)


@pytest.mark.parametrize(
    "system,machine,backend",
    [
        ("linux", "x86_64", "byparr"),
        ("win32", "AMD64", "byparr"),
        ("darwin", "arm64", "byparr"),
        ("darwin", "x86_64", "byparr"),
        ("linux", "aarch64", "byparr"),
    ],
)
def test_auto_backend_is_pnas_only(monkeypatch, system, machine, backend):
    monkeypatch.setattr(platforms.sys, "platform", system)
    monkeypatch.setattr(platforms.platform, "machine", lambda: machine)
    assert selection.selected_backend({}, provider="pnas") == backend
    assert (
        selection.selected_backend(
            {selection.PNAS_BACKEND_ENV: "byparr"}, provider="wiley"
        )
        == "byparr"
    )
    assert (
        selection.selected_backend(
            {selection.PNAS_BACKEND_ENV: "camoufox"}, provider="pnas"
        )
        == "byparr"
    )


def test_invalid_and_unsupported_backend_are_configuration_errors(monkeypatch):
    for value in ("chrome", "binary"):
        with pytest.raises(ProviderFailure, match="must be"):
            selection.selected_backend(
                {selection.PNAS_BACKEND_ENV: value}, provider="pnas"
            )


def test_byparr_reuses_executable_but_isolates_native_state(monkeypatch, tmp_path):
    binary = tmp_path / "camoufox"
    binary.touch()
    binary.chmod(0o755)
    config = load_runtime_config(
        {
            "XDG_DATA_HOME": str(tmp_path),
            "PAPER_FETCH_BROWSER_BINARY_PATH": str(binary),
            "PAPER_FETCH_BROWSER_PROFILE_DIR": "/firefox/profile",
        },
        provider="pnas",
        doi="10.1073/test",
    )
    assert config.backend == "byparr" and config.headless
    assert config.binary_path == str(binary) and config.profile_dir is None
    assert config.user_data_dir.name == "pnas-byparr"


def test_removed_configuration_reports_migration():
    for env in [
        {selection.PNAS_BACKEND_ENV: "flaresolverr"},
        {"PAPER_FETCH_CHROME_BINARY_PATH": "/chrome"},
    ]:
        with pytest.raises(ProviderFailure, match="removed.*(use|remove)"):
            load_runtime_config(env, provider="pnas", doi="10.1073/test")


def _archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return data.getvalue()


def test_source_reuse_and_failed_replacement_preserve_ready_cache(
    monkeypatch, tmp_path
):
    source = _archive({"upstream/src/utils.py": "value=1"})
    manifest = {
        "source": {
            "root": "upstream",
            "url": "https://source",
            "sha256": hashlib.sha256(source).hexdigest(),
        },
        "packages": [],
    }
    file = tmp_path / "manifest.json"
    file.write_text(json.dumps(manifest))
    monkeypatch.setattr(prep, "MANIFEST_PATH", file)
    calls = []

    def fetch(url, path, budget, sha256=None):
        calls.append(url)
        path.write_bytes(source)

    monkeypatch.setattr(prep, "download", fetch)
    root = prep.prepare_source(tmp_path / "cache", prep.PreparationBudget(5))
    assert (root / "upstream/src/utils.py").read_text() == "value=1"
    assert prep.prepare_source(tmp_path / "cache", prep.PreparationBudget(5)) == root
    assert len(calls) == 1
    manifest["source"]["url"] = "https://broken"
    file.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        prep, "download", lambda *a, **kw: (_ for _ in ()).throw(OSError("interrupted"))
    )
    with pytest.raises(OSError, match="interrupted"):
        prep.prepare_source(tmp_path / "cache", prep.PreparationBudget(5))
    assert (root / "upstream/src/utils.py").read_text() == "value=1"
    assert not list(root.parent.glob(".prepare-*"))


def test_download_hash_and_cancel_are_enforced(monkeypatch, tmp_path):
    class Response(io.BytesIO):
        pass

    monkeypatch.setattr(
        prep.urllib.request, "urlopen", lambda *a, **kw: Response(b"bad")
    )
    with pytest.raises(BrowserRuntimeFailure, match="SHA-256"):
        prep.download(
            "https://source", tmp_path / "part", prep.PreparationBudget(5), "0" * 64
        )
    context = SimpleNamespace(
        raise_if_cancelled=lambda: (_ for _ in ()).throw(InterruptedError("cancelled"))
    )
    with pytest.raises(InterruptedError, match="cancelled"):
        prep.prepare_source(tmp_path / "cache", prep.PreparationBudget(5, context))


def test_static_status_does_not_prepare_source_or_browser(monkeypatch, tmp_path):
    from paper_fetch.browser_preflight import static_browser_capabilities

    monkeypatch.setattr(
        prep,
        "download",
        lambda *a, **kw: pytest.fail("static diagnostics downloaded runtime"),
    )
    result = static_browser_capabilities(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas"
    )
    assert result["selected_backend"] == "byparr"
    assert result["browser_runtime"]["details"]["download_required"] is True
    assert not (tmp_path / "paper-fetch/byparr").exists()


def test_backend_cache_states_are_isolated(monkeypatch, tmp_path):
    from paper_fetch.capability_scope import capability_scopes_for_query
    from paper_fetch.providers.browser_runtime.paths import (
        default_provider_user_data_dir,
    )

    env = {"XDG_DATA_HOME": str(tmp_path)}
    path = (
        default_provider_user_data_dir(env, provider="pnas", backend="byparr")
        / "storage-state.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text('{"cookies":[],"origins":[]}')
    assert capability_scopes_for_query(env, "10.1073/pnas.2406303121")[0].startswith(
        "credential:"
    )
    assert capability_scopes_for_query(
        {**env, selection.PNAS_BACKEND_ENV: "camoufox"}, "10.1073/pnas.2406303121"
    ) == ("public",)


def test_solver_error_survives_candidate_deadline():
    from paper_fetch.providers._playwright_browser import _candidate_deadline_failure

    failure = BrowserRuntimeFailure(
        "byparr_navigation_failed", "Cloudflare denied the request"
    )
    assert _candidate_deadline_failure(failure, trace={"backend": "byparr"}) is failure
    assert failure.message == "Cloudflare denied the request"


@pytest.mark.parametrize(
    "backend,mode", [("byparr", "context_request"), ("camoufox", "page_click")]
)
def test_pnas_attachment_mode_uses_its_actual_backend(tmp_path, backend, mode):
    from dataclasses import replace
    from paper_fetch.providers.pnas import PnasClient

    client = PnasClient(object(), {})
    captured = []
    client.deps = replace(
        client.deps,
        _build_shared_browser_file_fetcher=lambda **kwargs: captured.append(kwargs),
    )
    config = BrowserRuntimeConfig(
        "pnas",
        "10.1073/test",
        tmp_path,
        True,
        None,
        backend="byparr",
        state_mode="json" if backend == "byparr" else "native",
    )
    client._browser_asset_file_fetcher(
        object(),
        attempt_supplementary_assets=True,
        browser_config=config,
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
        browser_user_agent=None,
        headless=True,
    )
    assert captured[0]["browser_options"].file_fetch_mode == mode
    assert captured[0]["browser_options"].runtime_config is config
    assert captured[0]["use_runtime_shared_browser"] is True


@pytest.mark.parametrize("version", ["1.57.0", "1.64.0"])
def test_shared_playwright_version_boundary(monkeypatch, tmp_path, version):
    from paper_fetch.providers.browser_runtime.backends import byparr
    import importlib.metadata

    monkeypatch.setattr(
        byparr,
        "_dependency_details",
        lambda: {"packages": {"playwright": True, "camoufox": True}},
    )
    monkeypatch.setattr(importlib.metadata, "version", lambda _: version)
    with pytest.raises(ProviderFailure, match="Playwright >=1.58,<1.64"):
        byparr.DEFAULT_BYPARR_BACKEND.ensure_runtime_ready(
            BrowserRuntimeConfig("pnas", "doi", tmp_path, True, None, backend="byparr")
        )
