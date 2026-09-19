"""Shared test support; contains no collected tests."""

from __future__ import annotations
from collections.abc import Mapping
from types import SimpleNamespace
from unittest import mock
from tests.support._browser_workflow_deps import browser_workflow_deps


class _FakeIopSupplementaryIndexFetcher:
    def __init__(
        self,
        response: Mapping[str, object] | None,
        *,
        failure: Mapping[str, object] | None = None,
    ) -> None:
        self.response = response
        self.failure = dict(failure or {})
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    def __call__(
        self,
        url: str,
        asset: Mapping[str, object],
    ) -> Mapping[str, object] | None:
        self.calls.append((url, dict(asset)))
        return self.response

    def failure_for(self, _url: str) -> dict[str, object] | None:
        return dict(self.failure) if self.failure else None

    def close(self) -> None:
        self.closed = True


def _iop_supplementary_test_deps(index_fetcher):
    runtime = SimpleNamespace(
        user_agent="UnitTestAgent/1.0",
        headless=True,
        binary_path=None,
        profile_dir=None,
        user_data_dir=None,
    )
    return browser_workflow_deps(
        load_runtime_config=mock.Mock(return_value=runtime),
        ensure_runtime_ready=mock.Mock(),
        _build_shared_browser_file_fetcher=mock.Mock(return_value=index_fetcher),
    )
