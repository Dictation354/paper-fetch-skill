from __future__ import annotations

import io
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import Mock
import zipfile

from dotenv import dotenv_values
import pytest

from paper_fetch import offline_setup as wizard
from paper_fetch import offline_windows_tools as windows
from paper_fetch.providers.browser_runtime import preparation


@pytest.fixture
def setup(tmp_path):
    return wizard.Setup(tmp_path, tmp_path / "offline.env")


def test_credentials_escape_remove_duplicates_preserve_other_keys(tmp_path, capsys):
    path = tmp_path / "offline.env"
    path.write_text(
        '# keep\nELSEVIER_API_KEY="old\nmultiline"\nexport ELSEVIER_API_KEY=duplicate\nWILEY_TDM_CLIENT_TOKEN=keep\n'
    )
    value = "a\"b\\c\nnew\rline' ${HOME} `echo private` #="
    wizard.update_env(path, {"ELSEVIER_API_KEY": value, "WILEY_TDM_CLIENT_TOKEN": ""})
    values = dotenv_values(path, interpolate=False)
    assert values["ELSEVIER_API_KEY"] == value
    assert values["WILEY_TDM_CLIENT_TOKEN"] == "keep"
    assert path.read_text().count("ELSEVIER_API_KEY=") == 1
    assert path.read_text().startswith("# keep")
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".optional-*"))
    assert not capsys.readouterr().out


def test_atomic_failure_preserves_credentials_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "offline.env"
    path.write_text("ELSEVIER_API_KEY=old\n")
    monkeypatch.setattr(wizard.os, "replace", Mock(side_effect=OSError("failure")))
    with pytest.raises(OSError):
        wizard.update_env(path, {"ELSEVIER_API_KEY": "new"})
    assert path.read_text() == "ELSEVIER_API_KEY=old\n"
    assert list(tmp_path.iterdir()) == [path]


def test_windows_private_acl_uses_sid_and_disables_inheritance(tmp_path, monkeypatch):
    target = tmp_path / "private.env"
    target.touch()
    monkeypatch.setattr(
        wizard, "os", SimpleNamespace(name="nt", environ={"SystemRoot": "/Windows"})
    )
    monkeypatch.setattr(
        wizard.subprocess,
        "check_output",
        lambda *_a, **_k: b'"domain\\\x81user","S-1-5-21-123-456-789-1001"\r\n',
    )
    run = Mock()
    monkeypatch.setattr(wizard.subprocess, "run", run)
    wizard.protect(target)
    command = run.call_args.args[0]
    assert command[-3:] == [
        "/inheritance:r",
        "/grant:r",
        "*S-1-5-21-123-456-789-1001:F",
    ]


def test_external_env_readonly_and_blank_preserved(setup):
    setup.env_file.write_text("ELSEVIER_API_KEY=old\n")
    before = setup.env_file.stat().st_mtime_ns
    setup.readonly = True
    setup.save_credentials({"ELSEVIER_API_KEY": "new-secret"})
    setup.save_tool("ghostscript", Path("/tools/gs"))
    assert setup.env_file.read_text() == "ELSEVIER_API_KEY=old\n"
    assert setup.env_file.stat().st_mtime_ns == before
    assert "new-secret" not in setup.summary()


@pytest.mark.parametrize("noninteractive", [False, True])
def test_noninteractive_exits_before_detection_or_network(
    tmp_path, monkeypatch, noninteractive
):
    monkeypatch.setattr(wizard.sys.stdin, "isatty", lambda: False)
    constructor = Mock(side_effect=AssertionError("must not initialize"))
    monkeypatch.setattr(wizard, "Setup", constructor)
    args = ["--install-root", str(tmp_path)]
    if noninteractive:
        args.append("--non-interactive")
    assert wizard.main(args) == 0
    constructor.assert_not_called()


def test_all_skipped_never_installs_or_prepares(setup, monkeypatch):
    monkeypatch.setattr(wizard.getpass, "getpass", lambda _: "")
    monkeypatch.setattr(wizard, "confirm", lambda _: False)
    monkeypatch.setattr(wizard, "detect_image", lambda *_: (None, "missing"))
    monkeypatch.setattr(wizard, "library_status", lambda _: "missing")
    monkeypatch.setattr(wizard, "apt_supported", lambda: True)
    monkeypatch.setattr(wizard, "apt_package", lambda names: names[0])
    monkeypatch.setattr(
        preparation,
        "probe_camoufox_managed_runtime",
        lambda: SimpleNamespace(state="missing", runtime_path=None, valid=False),
    )
    install = Mock(side_effect=AssertionError("unselected install"))
    prepare = Mock(side_effect=AssertionError("unselected browser"))
    monkeypatch.setattr(setup, "install_packages", install)
    monkeypatch.setattr(preparation, "prepare_camoufox_managed_runtime", prepare)
    setup.terminal()
    install.assert_not_called()
    prepare.assert_not_called()
    assert not setup.env_file.exists()
    assert "Publisher access: not tested" in setup.summary()


@pytest.mark.parametrize(
    "selected", [("1", "0", "0"), ("0", "1", "0"), ("0", "0", "1"), ("0", "0", "0")]
)
def test_windows_request_choices_are_independent_and_secrets_deleted(
    setup, monkeypatch, selected
):
    request = setup.root / "request.txt"
    request.write_text(
        "\ufeffsecret\n\n" + "\n".join(selected) + "\n", encoding="utf-8"
    )
    calls = []
    monkeypatch.setattr(wizard, "Setup", lambda *a, **kw: setup)

    def image(tool, *, selected):
        assert not request.exists()
        calls.append((tool, selected))

    monkeypatch.setattr(setup, "image", image)
    monkeypatch.setattr(
        setup, "browser", lambda **kw: calls.append(("browser", kw["selected"]))
    )
    assert (
        wizard.main(["--install-root", str(setup.root), "--request", str(request)]) == 0
    )
    assert calls == [
        ("ghostscript", selected[1] == "1"),
        ("libvips", selected[2] == "1"),
        ("browser", selected[0] == "1"),
    ]
    assert "secret" not in setup.summary()
    assert dotenv_values(setup.env_file)["ELSEVIER_API_KEY"] == "secret"


def test_invalid_request_cleans_secrets_and_reports_no_exception_text(setup):
    request = setup.root / "request.txt"
    request.write_text("sensitive-secret\ninvalid")
    result = setup.root / "result.txt"
    assert (
        wizard.main(
            [
                "--install-root",
                str(setup.root),
                "--request",
                str(request),
                "--result",
                str(result),
            ]
        )
        == 0
    )
    assert not request.exists()
    assert "sensitive-secret" not in result.read_text()
    assert "failed" in result.read_text()


def test_unreadable_env_still_cleans_credential_request(tmp_path, monkeypatch):
    request = tmp_path / "request.txt"
    request.write_text("secret\n\n0\n0\n0\n")
    monkeypatch.setattr(wizard, "Setup", Mock(side_effect=PermissionError("sensitive")))
    assert (
        wizard.main(["--install-root", str(tmp_path), "--request", str(request)]) == 0
    )
    assert not request.exists()


def test_tool_detection_falls_back_after_conversion_failure(monkeypatch, tmp_path):
    first, second = tmp_path / "broken/gs", tmp_path / "working/gs"
    monkeypatch.setattr(wizard.sys, "platform", "linux")
    monkeypatch.setattr(
        wizard, "ghostscript_binary_candidates", lambda _: [first, second]
    )
    monkeypatch.setattr(
        wizard,
        "_probe_working_binary",
        lambda paths, *_a, **_k: SimpleNamespace(binary=paths[0], status="ready"),
    )
    verify = Mock(side_effect=[RuntimeError("EPS conversion failed"), None])
    monkeypatch.setattr(wizard, "verify_image", verify)
    assert wizard.detect_image("ghostscript", {}) == (second, "ready")
    assert verify.call_count == 2


@pytest.mark.parametrize(
    "failure", [KeyboardInterrupt(), EOFError(), PermissionError("SECRET")]
)
def test_optional_failure_isolated_and_redacted(setup, failure):
    setup.step("first", Mock(side_effect=failure))
    second = Mock()
    setup.step("second", second)
    second.assert_called_once()
    assert "SECRET" not in setup.summary()
    assert "Core installation" in setup.summary()


def test_existing_tool_reused_without_package_install(setup, monkeypatch):
    monkeypatch.setattr(wizard.sys, "platform", "linux")
    monkeypatch.setattr(wizard, "detect_image", lambda *_: (Path("/known/gs"), "ready"))
    install = Mock(side_effect=AssertionError)
    monkeypatch.setattr(setup, "install_packages", install)
    setup.image("ghostscript", selected=True)
    install.assert_not_called()
    assert dotenv_values(setup.env_file)["PAPER_FETCH_GHOSTSCRIPT_BIN"] == str(
        Path("/known/gs")
    )


def test_linux_apt_failure_rechecks_and_supplies_actual_command(setup, monkeypatch):
    monkeypatch.setattr(wizard.sys, "platform", "linux")
    monkeypatch.setattr(wizard, "apt_supported", lambda: True)
    monkeypatch.setattr(wizard, "apt_package", lambda names: names[0])
    monkeypatch.setattr(wizard, "confirm", lambda _: True)
    detect = Mock(return_value=(None, "missing"))
    monkeypatch.setattr(wizard, "detect_image", detect)
    run = Mock(return_value=SimpleNamespace(returncode=100))
    monkeypatch.setattr(wizard.subprocess, "run", run)
    setup.image("libvips")
    assert detect.call_count == 2
    assert run.call_args.args[0] == [
        "sudo",
        "apt-get",
        "install",
        "--",
        "libvips-tools",
    ]
    assert "Exit 100" in setup.summary()
    assert "sudo apt-get install -- libvips-tools" in setup.summary()


@pytest.mark.parametrize(
    "status",
    [
        "libgtk-3.so.0: cannot open shared object file: No such file or directory",
        "wrong ELF class",
        "libdependency.so.0: cannot open shared object file: No such file or directory",
    ],
)
def test_library_detection_does_not_mislabel_loader_errors(monkeypatch, status):
    monkeypatch.setattr(wizard.ctypes, "CDLL", Mock(side_effect=OSError(status)))
    monkeypatch.setattr(wizard.ctypes.util, "find_library", lambda _: None)
    assert wizard.library_status("libgtk-3.so.0") == (
        "missing" if status.startswith("libgtk") else "unverified"
    )


def test_apt_resolves_t64_from_actual_candidate(monkeypatch):
    monkeypatch.setattr(wizard.shutil, "which", lambda _: "/usr/bin/apt-cache")
    run = Mock(
        side_effect=[
            SimpleNamespace(returncode=0, stdout="  Candidate: (none)\n"),
            SimpleNamespace(returncode=0, stdout="  Candidate: 1.2.3\n"),
        ]
    )
    monkeypatch.setattr(wizard.subprocess, "run", run)
    assert wizard.apt_package(("libasound2t64", "libasound2")) == "libasound2"
    assert run.call_args_list[0].args[0][-1] == "libasound2t64"


def test_macos_no_homebrew_does_not_install_anything(setup, monkeypatch):
    monkeypatch.setattr(wizard.sys, "platform", "darwin")
    monkeypatch.setattr(wizard, "detect_image", lambda *_: (None, "missing"))
    monkeypatch.setattr(wizard, "brew_binary", lambda: None)
    install = Mock(side_effect=AssertionError)
    monkeypatch.setattr(setup, "install_packages", install)
    setup.image("libvips", selected=True)
    install.assert_not_called()
    assert "https://brew.sh/" in setup.summary()


def test_macos_brew_uses_absolute_path_without_sudo(setup, monkeypatch):
    monkeypatch.setattr(wizard.sys, "platform", "darwin")
    monkeypatch.setattr(wizard, "brew_binary", lambda: "/custom/homebrew/bin/brew")
    monkeypatch.setattr(
        wizard,
        "detect_image",
        Mock(
            side_effect=[
                (None, "missing"),
                (Path("/custom/homebrew/bin/vips"), "ready"),
            ]
        ),
    )
    install = Mock()
    monkeypatch.setattr(setup, "install_packages", install)
    setup.image("libvips", selected=True)
    install.assert_called_once_with(
        "libvips", ["/custom/homebrew/bin/brew", "install", "vips"]
    )
    assert dotenv_values(setup.env_file)["PAPER_FETCH_VIPS_BIN"] == str(
        Path("/custom/homebrew/bin/vips")
    )


def test_browser_reuses_cache_and_opens_only_blank_page(setup, monkeypatch):
    import playwright.sync_api

    monkeypatch.setattr(wizard.os, "geteuid", lambda: 1000, raising=False)
    probe = SimpleNamespace(
        state="ready",
        runtime_path=Path("/cache"),
        valid=True,
        version="pinned",
        executable_path=Path("/cache/camoufox"),
    )
    monkeypatch.setattr(preparation, "probe_camoufox_managed_runtime", lambda: probe)
    prepare = Mock(side_effect=AssertionError("no update on valid cache"))
    monkeypatch.setattr(preparation, "prepare_camoufox_managed_runtime", prepare)
    browser = Mock()
    page = browser.new_context.return_value.new_page.return_value
    page.evaluate.return_value = 2
    api = Mock()
    api.firefox.launch.return_value = browser
    from contextlib import nullcontext

    monkeypatch.setattr(
        playwright.sync_api, "sync_playwright", lambda: nullcontext(api)
    )
    setup.browser(selected=True)
    prepare.assert_not_called()
    page.goto.assert_called_once_with("about:blank", timeout=10000)
    browser.new_context.return_value.storage_state.assert_not_called()
    browser.close.assert_called_once()
    assert "Camoufox local launch: ready" in setup.summary()
    assert "Publisher access: not tested" in setup.summary()


def test_browser_download_failure_does_not_attempt_launch(setup, monkeypatch):
    monkeypatch.setattr(wizard.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(
        preparation,
        "probe_camoufox_managed_runtime",
        lambda: SimpleNamespace(state="missing", runtime_path=None, valid=False),
    )
    monkeypatch.setattr(
        preparation,
        "prepare_camoufox_managed_runtime",
        Mock(side_effect=OSError("offline")),
    )
    setup.browser(selected=True)
    assert "Camoufox download: failed" in setup.summary()
    assert "Camoufox local launch: skipped" in setup.summary()


@pytest.mark.parametrize(
    "name",
    ["../escape", "/escape", "C:/escape", "..\\escape", "x:stream", "CON", "x. /file"],
)
def test_malicious_zip_paths_rejected_before_extraction(tmp_path, name):
    archive = tmp_path / "asset.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("valid.txt", "ok")
        bundle.writestr(name, "bad")
    with pytest.raises(ValueError):
        windows.extract_zip(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_zip_links_and_case_collisions_rejected(tmp_path):
    for mode in ("symlink", "collision"):
        archive = tmp_path / f"{mode}.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            if mode == "symlink":
                entry = zipfile.ZipInfo("bin/link")
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                bundle.writestr(entry, "../../outside")
            else:
                bundle.writestr("bin/A.dll", "first")
                bundle.writestr("bin/a.dll", "second")
        with pytest.raises(ValueError):
            windows.extract_zip(archive, tmp_path / "out")


def test_download_hash_failure_removes_temporary_file(tmp_path, monkeypatch):
    response = io.BytesIO(b"wrong digest")
    response.url = "https://example.test/asset"
    monkeypatch.setattr(windows.urllib.request, "urlopen", lambda *a, **kw: response)
    target = tmp_path / "download"
    with pytest.raises(ValueError, match="SHA-256"):
        windows.download({"url": response.url, "sha256": "0" * 64}, target)
    assert not target.exists()


def test_download_cancel_removes_temporary_file(tmp_path, monkeypatch):
    response = io.BytesIO(b"data")
    response.url = "https://example.test/asset"
    monkeypatch.setattr(windows.urllib.request, "urlopen", lambda *a, **kw: response)
    monkeypatch.setattr(
        windows.shutil, "copyfileobj", Mock(side_effect=KeyboardInterrupt)
    )
    target = tmp_path / "download"
    with pytest.raises(KeyboardInterrupt):
        windows.download({"url": response.url, "sha256": "0" * 64}, target)
    assert not target.exists()


@pytest.fixture
def assets(setup):
    manifest = json.loads(
        (Path(__file__).parents[2] / "installer/manifest.json").read_text()
    )
    (setup.root / "installer").mkdir()
    (setup.root / "installer/manifest.json").write_text(json.dumps(manifest))
    return manifest["optional_windows_tools"]


def test_registered_ghostscript_never_overwritten(setup, assets, monkeypatch):
    monkeypatch.setattr(
        windows,
        "registered_ghostscript",
        lambda: [{"version": assets["ghostscript"]["version"], "directory": "/broken"}],
    )
    download = Mock(side_effect=AssertionError)
    monkeypatch.setattr(windows, "download", download)
    windows.install_tool(setup, "ghostscript")
    download.assert_not_called()
    assert "repair" in setup.summary()


def test_libvips_complete_tree_recorded_after_conversion(setup, assets, monkeypatch):
    def download(asset, target):
        with zipfile.ZipFile(target, "w") as bundle:
            bundle.writestr("vips/bin/vips.exe", b"binary")
            bundle.writestr("vips/bin/dependency.dll", b"dll")
            bundle.writestr("vips/share/resource.xml", b"resource")

    monkeypatch.setattr(windows, "download", download)
    verify = Mock()
    monkeypatch.setattr(windows, "verify_image", verify)
    windows.install_tool(setup, "libvips")
    entry = windows.load_inventory(setup.root)["tools"]["libvips"]
    assert entry["status"] == "ready" and entry["owned"]
    assert len(entry["files"]) == 3
    assert (Path(entry["directory"]) / "vips/bin/dependency.dll").read_bytes() == b"dll"
    verify.assert_called_once()
    assert not list((setup.root / "image-tools/libvips").glob(".download-*"))


def test_libvips_conversion_failure_not_published(setup, assets, monkeypatch):
    def download(asset, target):
        with zipfile.ZipFile(target, "w") as bundle:
            bundle.writestr("vips/bin/vips.exe", b"binary")

    monkeypatch.setattr(windows, "download", download)
    monkeypatch.setattr(
        windows, "verify_image", Mock(side_effect=RuntimeError("no conversion"))
    )
    setup.step("libvips", lambda: windows.install_tool(setup, "libvips"))
    assert not setup.env_file.exists()
    assert not (
        setup.root / "image-tools/libvips" / assets["libvips"]["version"]
    ).exists()
    assert not list((setup.root / "image-tools/libvips").glob(".download-*"))


def test_ghostscript_external_directory_is_never_owned(
    setup, assets, monkeypatch, tmp_path
):
    actual = tmp_path / "external-gs"
    monkeypatch.setattr(
        windows,
        "registered_ghostscript",
        Mock(
            side_effect=[
                [],
                [
                    {
                        "version": assets["ghostscript"]["version"],
                        "directory": str(actual),
                    }
                ],
            ]
        ),
    )
    monkeypatch.setattr(
        windows, "download", lambda asset, target: target.write_bytes(b"exe")
    )
    run = Mock(return_value=0)
    monkeypatch.setattr(windows, "run_official", run)
    monkeypatch.setattr(windows, "verify_image", Mock())
    windows.install_tool(setup, "ghostscript")
    entry = windows.load_inventory(setup.root)["tools"]["ghostscript"]
    assert not entry["owned"]
    assert entry["directory"] == str(actual)
    assert run.call_args.args[1].startswith("/D=")
    assert '"' not in run.call_args.args[1]


def test_ghostscript_uac_cancel_preserves_core_and_cleans_download(
    setup, assets, monkeypatch
):
    monkeypatch.setattr(windows, "registered_ghostscript", lambda: [])
    monkeypatch.setattr(
        windows, "download", lambda asset, target: target.write_bytes(b"exe")
    )
    monkeypatch.setattr(
        windows, "run_official", Mock(side_effect=OSError("UAC cancelled"))
    )
    setup.step("ghostscript", lambda: windows.install_tool(setup, "ghostscript"))
    assert not setup.env_file.exists()
    assert not list((setup.root / "image-tools/ghostscript").glob(".download-*"))
    assert "Core installation preserved" in setup.summary()


def test_libvips_cleanup_preserves_added_and_modified_user_files(setup, assets):
    directory = setup.root / "image-tools/libvips" / assets["libvips"]["version"]
    directory.mkdir(parents=True)
    (directory / "owned.dll").write_text("original")
    (directory / "modified.dll").write_text("original")
    windows.record(
        setup, "libvips", assets["libvips"], directory, owned=True, status="ready"
    )
    (directory / "modified.dll").write_text("user-changed")
    (directory / "user.txt").write_text("user-added")
    (directory / "user-empty-directory").mkdir()
    windows.cleanup_tools(setup)
    assert not (directory / "owned.dll").exists()
    assert (directory / "modified.dll").read_text() == "user-changed"
    assert (directory / "user.txt").read_text() == "user-added"
    assert (directory / "user-empty-directory").is_dir()


@pytest.mark.parametrize("mismatch", [False, True])
def test_ghostscript_cleanup_failure_preserves_inventory(
    setup, assets, monkeypatch, mismatch
):
    directory = (
        setup.root / "image-tools/ghostscript" / assets["ghostscript"]["version"]
    )
    directory.mkdir(parents=True)
    (directory / "uninstgs.exe").write_bytes(b"official")
    windows.record(
        setup,
        "ghostscript",
        assets["ghostscript"],
        directory,
        owned=True,
        status="ready",
    )
    monkeypatch.setattr(
        windows,
        "registered_ghostscript",
        lambda: [
            {
                "version": assets["ghostscript"]["version"],
                "directory": "/elsewhere" if mismatch else str(directory),
            }
        ],
    )
    run = Mock(side_effect=OSError("cancelled"))
    monkeypatch.setattr(windows, "run_official", run)
    windows.cleanup_tools(setup)
    assert "ghostscript" in windows.load_inventory(setup.root)["tools"]
    assert (directory / "uninstgs.exe").exists()
    assert run.call_count == (0 if mismatch else 1)


def test_inno_silent_guards_and_private_input_order():
    script = (Path(__file__).parents[2] / "installer/paper-fetch-skill.iss").read_text()
    assert "WizardSilent or not OptionalCoreReady" in script
    assert "if UninstallSilent then exit" in script
    assert "CleanupTools.Checked := False" in script
    for checkbox in ("OptionalBrowser", "OptionalGhostscript", "OptionalVips"):
        assert f"{checkbox}.Checked := False" in script
    body = script.split("procedure RunOptionalConfiguration;", 1)[1].split(
        "function NextButtonClick", 1
    )[0]
    assert body.index("--initialize-request") < body.index("SaveStringsToUTF8File")
    assert "finally" in body and "DeleteOptionalRequest" in body
    assert (
        "Params :=" in body
        and "Values[0]" not in body.split("Params :=", 1)[1].split(";", 1)[0]
    )
