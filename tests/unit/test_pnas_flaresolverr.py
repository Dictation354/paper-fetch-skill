"""PNAS backend policy, isolated preparation and static probe boundary contracts."""

import hashlib
import io
import json
from types import SimpleNamespace
import zipfile

import pytest

from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime import chrome, selection
from paper_fetch.providers.browser_runtime import flaresolverr_preparation as prep
from paper_fetch.providers.browser_runtime.api import load_runtime_config
from paper_fetch.providers.browser_runtime.types import (
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)


@pytest.mark.parametrize(
    "system,machine,backend",
    [
        ("linux", "x86_64", "flaresolverr"),
        ("win32", "AMD64", "flaresolverr"),
        ("darwin", "arm64", "camoufox"),
        ("darwin", "x86_64", "camoufox"),
        ("linux", "aarch64", "camoufox"),
    ],
)
def test_auto_backend_is_pnas_only(monkeypatch, system, machine, backend):
    monkeypatch.setattr(chrome.sys, "platform", system)
    monkeypatch.setattr(chrome.platform, "machine", lambda: machine)
    assert selection.selected_backend({}, provider="pnas") == backend
    assert (
        selection.selected_backend(
            {selection.PNAS_BACKEND_ENV: "flaresolverr"}, provider="wiley"
        )
        == "camoufox"
    )
    assert (
        selection.selected_backend(
            {selection.PNAS_BACKEND_ENV: "camoufox"}, provider="pnas"
        )
        == "camoufox"
    )


def test_invalid_and_unsupported_backend_are_configuration_errors(monkeypatch):
    for value in ("chrome", "binary"):
        with pytest.raises(ProviderFailure, match="must be"):
            selection.selected_backend(
                {selection.PNAS_BACKEND_ENV: value}, provider="pnas"
            )
    monkeypatch.setattr(selection, "supported_platform", lambda: False)
    with pytest.raises(ProviderFailure, match="Windows/Linux x64"):
        selection.selected_backend(
            {selection.PNAS_BACKEND_ENV: "flaresolverr"}, provider="pnas"
        )


def test_camoufox_settings_do_not_leak_into_chrome_state(monkeypatch, tmp_path):
    monkeypatch.setattr(selection, "supported_platform", lambda: True)
    config = load_runtime_config(
        {
            "XDG_DATA_HOME": str(tmp_path),
            "PAPER_FETCH_BROWSER_BINARY_PATH": "/missing/firefox",
            "PAPER_FETCH_BROWSER_PROFILE_DIR": "/firefox/profile",
            chrome.CHROME_ENV: "/custom/chrome",
        },
        provider="pnas",
        doi="10.1073/test",
    )
    assert config.backend == "flaresolverr" and config.headless
    assert config.chrome_binary_path == "/custom/chrome"
    assert config.binary_path is None and config.profile_dir is None
    assert config.user_data_dir.name == "pnas-flaresolverr"
    assert (
        BrowserRuntimeConfig("science", "doi", tmp_path, True, None).backend
        == "camoufox"
    )


def test_explicit_chrome_is_validated_without_falling_back(monkeypatch, tmp_path):
    executable = tmp_path / "google-chrome"
    executable.touch()
    executable.chmod(0o755)
    monkeypatch.setattr(chrome.sys, "platform", "linux")
    calls = []
    monkeypatch.setattr(
        chrome.subprocess,
        "run",
        lambda args, **kw: (
            calls.append(args)
            or SimpleNamespace(stdout="Google Chrome 156.0.8078.79\n")
        ),
    )
    result = chrome.discover_chrome({chrome.CHROME_ENV: str(executable)})
    assert result.path == str(executable) and result.version == "156.0.8078.79"
    assert calls == [[str(executable), "--version"]]
    with pytest.raises(ValueError, match="google.com/chrome"):
        chrome.discover_chrome({chrome.CHROME_ENV: str(tmp_path / "missing")})
    assert len(calls) == 1


def test_linux_chrome_discovery_order(monkeypatch, tmp_path):
    monkeypatch.setattr(chrome.sys, "platform", "linux")
    monkeypatch.setattr(chrome.shutil, "which", lambda name, **kw: str(tmp_path / name))
    assert list(chrome._candidates({}))[:2] == [
        str(tmp_path / "google-chrome"),
        str(tmp_path / "google-chrome-stable"),
    ]


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


def test_driver_is_cached_per_chrome_build_and_updated_on_version_change(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(prep.sys, "platform", "linux")
    calls = []
    archive = _archive({"chromedriver-linux64/chromedriver": b"driver"})

    def fetch(url, path, budget, sha256=None):
        calls.append(url)
        if url == prep.DRIVER_INDEX:
            path.write_text(
                json.dumps(
                    {
                        "builds": {
                            build: {
                                "version": build + ".99",
                                "downloads": {
                                    "chromedriver": [
                                        {
                                            "platform": "linux64",
                                            "url": "https://official/" + build,
                                        }
                                    ]
                                },
                            }
                            for build in ("156.0.1", "157.0.2")
                        }
                    }
                )
            )
        else:
            path.write_bytes(archive)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    monkeypatch.setattr(prep, "download", fetch)
    first, version = prep.prepare_driver(
        tmp_path, "156.0.1.1", prep.PreparationBudget(5)
    )
    assert version == "156.0.1.99"
    assert (
        prep.prepare_driver(tmp_path, "156.0.1.1", prep.PreparationBudget(5))[0]
        == first
    )
    assert len(calls) == 2
    second, _ = prep.prepare_driver(tmp_path, "157.0.2.1", prep.PreparationBudget(5))
    assert second != first and first.exists() and second.exists() and len(calls) == 4


def test_static_status_does_not_prepare_source_or_driver(monkeypatch, tmp_path):
    from paper_fetch.providers.browser_runtime.backends import flaresolverr as backend
    from paper_fetch.browser_preflight import static_browser_capabilities

    monkeypatch.setattr(selection, "supported_platform", lambda: True)
    monkeypatch.setattr(
        backend,
        "discover_chrome",
        lambda env: chrome.SystemChrome("/chrome", "156.0.1.2"),
    )
    monkeypatch.setattr(
        prep,
        "download",
        lambda *a, **kw: pytest.fail("static diagnostics downloaded runtime"),
    )
    result = static_browser_capabilities(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas"
    )
    assert result["selected_backend"] == "flaresolverr"
    assert result["browser_runtime"]["details"]["download_required"] is True
    assert not (tmp_path / "paper-fetch/flaresolverr").exists()


def test_backend_cache_states_are_isolated(monkeypatch, tmp_path):
    from paper_fetch.capability_scope import capability_scopes_for_query
    from paper_fetch.providers.browser_runtime.paths import (
        default_provider_user_data_dir,
    )

    monkeypatch.setattr(selection, "supported_platform", lambda: True)
    env = {"XDG_DATA_HOME": str(tmp_path)}
    path = (
        default_provider_user_data_dir(env, provider="pnas", backend="flaresolverr")
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
        "flaresolverr_navigation_failed", "Cloudflare denied the request"
    )
    assert (
        _candidate_deadline_failure(failure, trace={"backend": "flaresolverr"})
        is failure
    )
    assert failure.message == "Cloudflare denied the request"


def test_linux_missing_xvfb_is_preparation_error(monkeypatch, tmp_path):
    from paper_fetch.providers.browser_runtime import flaresolverr_manager as manager

    monkeypatch.setattr(manager.sys, "platform", "linux")
    monkeypatch.setattr(manager.shutil, "which", lambda name: None)
    with pytest.raises(BrowserRuntimeFailure, match="requires Xvfb"):
        manager.linux_launch_prefix(True, tmp_path, prep.PreparationBudget(5))


@pytest.mark.parametrize(
    "backend,mode", [("flaresolverr", "context_request"), ("camoufox", "page_click")]
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
        "pnas", "10.1073/test", tmp_path, True, None, backend=backend
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
