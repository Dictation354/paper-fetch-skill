from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest
from filelock import FileLock

from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime import preparation
from paper_fetch.providers.browser_runtime.preparation import (
    CamoufoxRuntimeProbe,
)
from paper_fetch.reason_codes import (
    BROWSER_RUNTIME_PREPARE_CANCELLED,
    BROWSER_RUNTIME_PREPARE_TIMEOUT,
)


def _missing() -> CamoufoxRuntimeProbe:
    return CamoufoxRuntimeProbe(
        state="missing",
        installed=False,
        valid=False,
        message="missing",
    )


def _ready(tmp_path: Path, version: str = "152.0.4-beta.28") -> CamoufoxRuntimeProbe:
    runtime_path = tmp_path / "browsers" / "official" / version
    return CamoufoxRuntimeProbe(
        state="ready",
        installed=True,
        valid=True,
        runtime_path=runtime_path,
        executable_path=runtime_path / "camoufox",
        version=version,
        active_spec=f"browsers/official/{version}",
        managed_path_safe=True,
    )


def _corrupt(tmp_path: Path) -> CamoufoxRuntimeProbe:
    version = "152.0.4-beta.28"
    return CamoufoxRuntimeProbe(
        state="corrupt",
        installed=True,
        valid=False,
        runtime_path=tmp_path / "browsers" / "official" / version,
        version=version,
        active_spec=f"browsers/official/{version}",
        managed_path_safe=True,
        message="incomplete",
    )


def _patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    lock_path = tmp_path / "runtime.lock"
    state_path = tmp_path / "runtime.json"
    monkeypatch.setattr(
        preparation,
        "_coordinator_paths",
        lambda: (lock_path, state_path),
    )
    return lock_path, state_path


def test_probe_validates_official_managed_executable_without_fetching(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    active_spec = "browsers/official/152.0.4-beta.28"
    runtime_path = tmp_path / active_spec
    executable = runtime_path / "camoufox"
    executable.parent.mkdir(parents=True)
    executable.touch()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"active_version": active_spec}),
        encoding="utf-8",
    )
    version = SimpleNamespace(
        full_string="152.0.4-beta.28",
        is_supported=lambda: True,
    )
    version_type = SimpleNamespace(from_path=mock.Mock(return_value=version))
    pkgman = SimpleNamespace(
        INSTALL_DIR=tmp_path,
        Version=version_type,
        launch_path=mock.Mock(return_value=str(executable)),
    )
    multiversion = SimpleNamespace(CONFIG_FILE=config_path)
    monkeypatch.setattr(
        preparation,
        "import_module",
        lambda name: pkgman if name == "camoufox.pkgman" else multiversion,
    )

    probe = preparation.probe_camoufox_managed_runtime()

    assert probe.valid is True
    assert probe.runtime_path == runtime_path
    assert probe.executable_path == executable
    version_type.from_path.assert_called_once_with(runtime_path)
    pkgman.launch_path.assert_called_once_with(runtime_path)


def test_probe_rejects_a_link_in_the_managed_runtime_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real-official"
    real_parent.mkdir()
    browsers = tmp_path / "browsers"
    browsers.mkdir()
    try:
        (browsers / "official").symlink_to(real_parent, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")
    runtime_path = real_parent / "152.0.4-beta.28"
    runtime_path.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"active_version":"browsers/official/152.0.4-beta.28"}',
        encoding="utf-8",
    )
    pkgman = SimpleNamespace(INSTALL_DIR=tmp_path)
    multiversion = SimpleNamespace(CONFIG_FILE=config_path)
    monkeypatch.setattr(
        preparation,
        "import_module",
        lambda name: pkgman if name == "camoufox.pkgman" else multiversion,
    )

    probe = preparation.probe_camoufox_managed_runtime()

    assert probe.valid is False
    assert probe.managed_path_safe is False
    assert probe.state == "corrupt"


def test_reparse_attribute_is_rejected_when_isjunction_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = mock.Mock()
    path.is_symlink.return_value = False
    path.lstat.return_value = SimpleNamespace(st_file_attributes=0x400)
    monkeypatch.setattr(preparation.os.path, "isjunction", None, raising=False)

    assert preparation._is_link_or_reparse(path) is True


def test_managed_candidate_rejects_parent_traversal_even_within_cache(
    tmp_path: Path,
) -> None:
    candidate, safe = preparation._managed_candidate(
        tmp_path,
        "browsers/../unexpected-runtime",
    )

    assert candidate == tmp_path / "browsers" / ".." / "unexpected-runtime"
    assert safe is False


def test_missing_runtime_is_installed_once_with_official_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _lock_path, state_path = _patch_paths(monkeypatch, tmp_path)
    ready = _ready(tmp_path)
    probes = iter((_missing(), _missing(), ready))
    monkeypatch.setattr(
        preparation, "probe_camoufox_managed_runtime", lambda: next(probes)
    )
    run = mock.Mock(return_value=(0, ["Installed Camoufox"]))
    monkeypatch.setattr(preparation, "_run_camoufox_command", run)

    outcome = preparation.ensure_camoufox_managed_runtime(wall_clock=lambda: 1_000.0)

    assert outcome.action == "install"
    assert outcome.ready is True
    run.assert_called_once()
    assert run.call_args.args[0] == ["fetch"]
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_successful_check_at"] == 1_000.0
    assert state["version"] == ready.version


def test_valid_runtime_skips_network_for_twenty_four_hours(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _lock_path, state_path = _patch_paths(monkeypatch, tmp_path)
    preparation._write_state(
        state_path,
        {"last_successful_check_at": 1_000.0, "version": "152.0.4-beta.28"},
    )
    monkeypatch.setattr(
        preparation,
        "probe_camoufox_managed_runtime",
        lambda: _ready(tmp_path),
    )
    forbidden = mock.Mock(side_effect=AssertionError("must not access the network"))
    monkeypatch.setattr(preparation, "_run_camoufox_command", forbidden)

    outcome = preparation.ensure_camoufox_managed_runtime(wall_clock=lambda: 1_001.0)

    assert outcome.attempted is False
    assert outcome.action == "none"
    forbidden.assert_not_called()


def test_failed_update_keeps_existing_valid_runtime_and_backs_off(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _lock_path, state_path = _patch_paths(monkeypatch, tmp_path)
    ready = _ready(tmp_path)
    monkeypatch.setattr(preparation, "probe_camoufox_managed_runtime", lambda: ready)
    run = mock.Mock(return_value=(0, ["official... Error: network unavailable"]))
    monkeypatch.setattr(
        preparation,
        "_run_camoufox_command",
        run,
    )

    outcome = preparation.ensure_camoufox_managed_runtime(wall_clock=lambda: 2_000.0)
    retry = preparation.ensure_camoufox_managed_runtime(wall_clock=lambda: 2_001.0)

    assert outcome.ready is True
    assert outcome.warning is not None
    assert retry.attempted is False
    run.assert_called_once()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_update_failure_at"] == 2_000.0
    assert "last_successful_check_at" not in state


def test_child_process_timeout_terminates_noninteractive_official_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.StringIO("")
            self.returncode: int | None = None
            self.terminated = False

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15

        def wait(self, timeout: float) -> int:
            del timeout
            assert self.returncode is not None
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    process = FakeProcess()
    popen = mock.Mock(return_value=process)
    monkeypatch.setattr(preparation.subprocess, "Popen", popen)
    monkeypatch.setattr(preparation, "probe_camoufox_managed_runtime", _missing)

    with pytest.raises(ProviderFailure) as raised:
        preparation._run_camoufox_command(
            ["fetch"],
            action="install",
            deadline=1.0,
            clock=lambda: 2.0,
        )

    assert raised.value.code == BROWSER_RUNTIME_PREPARE_TIMEOUT
    assert process.terminated is True
    assert popen.call_args.kwargs["stdin"] is preparation.subprocess.DEVNULL


def test_corrupt_exact_managed_version_is_removed_and_reinstalled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_paths(monkeypatch, tmp_path)
    corrupt = _corrupt(tmp_path)
    ready = _ready(tmp_path)
    monkeypatch.setattr(
        preparation,
        "probe_camoufox_managed_runtime",
        mock.Mock(side_effect=(corrupt, corrupt, corrupt, ready)),
    )
    run = mock.Mock(return_value=(0, []))
    monkeypatch.setattr(preparation, "_run_camoufox_command", run)

    outcome = preparation.ensure_camoufox_managed_runtime(wall_clock=lambda: 3_000.0)

    assert outcome.action == "repair"
    assert [call.args[0] for call in run.call_args_list] == [
        ["fetch"],
        ["remove", corrupt.active_spec, "--yes"],
        ["fetch"],
    ]


def test_concurrent_preparations_share_one_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_paths(monkeypatch, tmp_path)
    runtime_ready = threading.Event()
    command_started = threading.Event()
    release_command = threading.Event()
    command_calls = 0
    calls_lock = threading.Lock()

    def probe() -> CamoufoxRuntimeProbe:
        return _ready(tmp_path) if runtime_ready.is_set() else _missing()

    def run_command(*_args: object, **_kwargs: object) -> tuple[int, list[str]]:
        nonlocal command_calls
        with calls_lock:
            command_calls += 1
        command_started.set()
        assert release_command.wait(timeout=5)
        runtime_ready.set()
        return 0, []

    monkeypatch.setattr(preparation, "probe_camoufox_managed_runtime", probe)
    monkeypatch.setattr(preparation, "_run_camoufox_command", run_command)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            preparation.ensure_camoufox_managed_runtime,
            wall_clock=lambda: 4_000.0,
        )
        assert command_started.wait(timeout=5)
        second = executor.submit(
            preparation.ensure_camoufox_managed_runtime,
            wall_clock=lambda: 4_000.0,
        )
        time.sleep(0.1)
        release_command.set()
        first_outcome = first.result(timeout=5)
        second_outcome = second.result(timeout=5)

    assert first_outcome.ready is True
    assert second_outcome.ready is True
    assert command_calls == 1
    assert second_outcome.waited_for_lock is True


def test_lock_wait_honors_cooperative_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock_path, _state_path = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        preparation, "probe_camoufox_managed_runtime", lambda: _missing()
    )
    forbidden = mock.Mock(side_effect=AssertionError("must not run"))
    monkeypatch.setattr(preparation, "_run_camoufox_command", forbidden)
    held_lock = FileLock(str(lock_path))
    held_lock.acquire()
    try:
        with preparation.browser_runtime_preparation_scope(cancel_check=lambda: True):
            with pytest.raises(ProviderFailure) as raised:
                preparation.ensure_camoufox_managed_runtime()
    finally:
        held_lock.release()

    assert raised.value.code == BROWSER_RUNTIME_PREPARE_CANCELLED
    forbidden.assert_not_called()
