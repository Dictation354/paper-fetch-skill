from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from filelock import Timeout as FileLockTimeout

from paper_fetch.providers.browser_runtime.paths import (
    commit_staged_storage_state,
    stage_storage_state,
)
from paper_fetch.providers.browser_runtime import paths as storage_paths
from paper_fetch.runtime import RuntimeContext
from paper_fetch.providers.browser_runtime.types import (
    BrowserRuntimeConfig,
    BrowserStagedStorageState,
)


class _StorageContext:
    def __init__(self, payload):
        self.payload = payload

    def storage_state(self):
        return self.payload


def _config(tmp_path: Path) -> BrowserRuntimeConfig:
    return BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1111/example",
        artifact_dir=tmp_path / "artifacts",
        headless=True,
        user_agent=None,
        storage_state_path=tmp_path / "wiley.json",
    )


def _cookie(name: str, value: str, domain: str) -> dict[str, str]:
    return {"name": name, "value": value, "domain": domain, "path": "/"}


def test_storage_state_stage_does_not_modify_existing_file(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert config.storage_state_path is not None
    old_bytes = b'{"cookies":[{"name":"old"}],"origins":[]}\n'
    config.storage_state_path.write_bytes(old_bytes)
    context = _StorageContext(
        {
            "cookies": [
                _cookie("sid", "new", ".wiley.com"),
                _cookie("idp", "drop", ".example.test"),
            ],
            "origins": [
                {"origin": "https://onlinelibrary.wiley.com"},
                {"origin": "https://login.example.test"},
            ],
        }
    )

    stage, result = stage_storage_state(
        context,
        config,
        filter_url="https://onlinelibrary.wiley.com/doi/full/10.1111/example",
    )

    assert stage is not None
    assert result["staged"] is True
    assert config.storage_state_path.read_bytes() == old_bytes
    assert [item["name"] for item in stage.payload["cookies"]] == ["sid"]
    assert [item["origin"] for item in stage.payload["origins"]] == [
        "https://onlinelibrary.wiley.com"
    ]


def test_out_of_provider_final_url_cannot_stage_or_overwrite_state(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    assert config.storage_state_path is not None
    config.storage_state_path.write_text('{"cookies":[],"origins":[]}\n')
    old_bytes = config.storage_state_path.read_bytes()

    stage, result = stage_storage_state(
        _StorageContext({"cookies": [], "origins": []}),
        config,
        filter_url="https://login.example.test/session",
    )

    assert stage is None
    assert result["reason"] == "final_url_outside_provider"
    assert config.storage_state_path.read_bytes() == old_bytes


def test_accepted_state_commit_merges_provider_state_and_drops_idp(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    assert config.storage_state_path is not None
    config.storage_state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    _cookie("old", "keep", ".wiley.com"),
                    _cookie("idp", "drop", ".example.test"),
                ],
                "origins": [
                    {"origin": "https://onlinelibrary.wiley.com"},
                    {"origin": "https://login.example.test"},
                ],
            }
        )
    )
    stage = BrowserStagedStorageState(
        path=config.storage_state_path,
        provider="wiley",
        filter_url="https://onlinelibrary.wiley.com/doi/full/10.1111/example",
        payload={
            "cookies": [_cookie("new", "value", ".wiley.com")],
            "origins": [{"origin": "https://www.wiley.com"}],
        },
    )

    result = commit_staged_storage_state(stage, config)

    assert result["saved"] is True
    payload = json.loads(config.storage_state_path.read_text())
    assert {item["name"] for item in payload["cookies"]} == {"old", "new"}
    assert {item["origin"] for item in payload["origins"]} == {
        "https://onlinelibrary.wiley.com",
        "https://www.wiley.com",
    }


def test_concurrent_storage_state_commits_remain_atomic(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert config.storage_state_path is not None

    def commit(index: int):
        return commit_staged_storage_state(
            BrowserStagedStorageState(
                path=config.storage_state_path,
                provider="wiley",
                filter_url="https://onlinelibrary.wiley.com/article",
                payload={
                    "cookies": [_cookie(f"cookie-{index}", str(index), ".wiley.com")],
                    "origins": [],
                },
            ),
            config,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(commit, range(8)))

    assert all(result["saved"] for result in results)
    payload = json.loads(config.storage_state_path.read_text())
    assert {item["name"] for item in payload["cookies"]} == {
        f"cookie-{index}" for index in range(8)
    }


def test_storage_state_lock_timeout_preserves_existing_file(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert config.storage_state_path is not None
    old_bytes = b'{"cookies":[],"origins":[]}\n'
    config.storage_state_path.write_bytes(old_bytes)
    stage = BrowserStagedStorageState(
        path=config.storage_state_path,
        provider="wiley",
        filter_url="https://onlinelibrary.wiley.com/article",
        payload={
            "cookies": [_cookie("new", "value", ".wiley.com")],
            "origins": [],
        },
    )
    runtime_context = RuntimeContext(env={})
    runtime_context.initialize_deadline(0.01)
    locked = mock.Mock()
    locked.acquire.side_effect = FileLockTimeout(str(config.storage_state_path))

    with mock.patch.object(storage_paths, "FileLock", return_value=locked):
        result = commit_staged_storage_state(
            stage,
            config,
            runtime_context=runtime_context,
        )

    assert result["saved"] is False
    assert result["reason"] == "lock_timeout"
    assert config.storage_state_path.read_bytes() == old_bytes
    assert locked.acquire.call_args.kwargs["timeout"] <= 0.01
