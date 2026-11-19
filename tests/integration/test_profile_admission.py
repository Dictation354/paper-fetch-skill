"""Real locks, path aliases and batch execution admission using a fake native engine."""

import threading
import time
from dataclasses import replace

from paper_fetch.providers.browser_runtime import profile
from paper_fetch.providers.browser_runtime.backends.byparr import (
    DEFAULT_BYPARR_BACKEND,
)
from paper_fetch.providers.browser_runtime.context import open_browser_context
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.batch_runner import run_batch
from tests.support.publisher_profiles import NativeProfileDouble


def test_profile_wait_longer_than_page_budget_then_full_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "ByparrManager", NativeProfileDouble)
    config = DEFAULT_BYPARR_BACKEND.load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas", doi="10.1073/pnas.test"
    )
    first, _ = open_browser_context(config)
    actual = profile.profile_path(config)
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    alias_config = replace(config, profile_dir=alias, timeout_ms=120)
    entered = threading.Event()
    facts = []

    def waiter():
        with RuntimeContext(env={}) as context:
            open_browser_context(alias_config, runtime_context=context)
            facts.append(context.browser_remaining_seconds())
            entered.set()

    worker = threading.Thread(target=waiter)
    worker.start()
    try:
        assert not entered.wait(0.25)
        first.close()
        worker.join(2)
        assert entered.is_set() and 0.08 < facts[0] <= 0.12
    finally:
        first.close()
        worker.join(2)


def test_waiter_yields_batch_capacity_for_another_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "ByparrManager", NativeProfileDouble)
    config = DEFAULT_BYPARR_BACKEND.load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas", doi="10.1073/pnas.test"
    )
    first, _ = open_browser_context(config)
    other_done = threading.Event()
    failures = []

    def item(index):
        with RuntimeContext(env={}) as context:
            selected = (
                config
                if index == 0
                else replace(config, profile_dir=tmp_path / "other-profile")
            )
            open_browser_context(selected, runtime_context=context)
            if index == 1:
                other_done.set()
            return index

    def batch():
        try:
            result = run_batch([0, 1], item, max_workers=1)
            assert [r.value for r in result.results] == [0, 1]
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=batch)
    thread.start()
    try:
        assert other_done.wait(2), "a queued profile consumed the only execution slot"
    finally:
        first.close()
        thread.join(3)
    assert not thread.is_alive() and not failures


def test_reuse_and_profile_switch_share_budget_excluding_queue(tmp_path, monkeypatch):
    from filelock import FileLock

    monkeypatch.setattr(profile, "ByparrManager", NativeProfileDouble)
    config = DEFAULT_BYPARR_BACKEND.load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas", doi="10.1073/pnas.test"
    )
    config = replace(config, timeout_ms=1000)
    other = replace(config, profile_dir=tmp_path / "other-profile")
    other.profile_dir.mkdir()
    lease = FileLock(
        str(other.profile_dir / profile.PROFILE_LOCK_FILENAME), thread_local=False
    )
    lease.acquire()
    with RuntimeContext(env={}) as context:
        _, first = open_browser_context(config, runtime_context=context)
        deadline = context.browser_deadline_monotonic
        time.sleep(0.05)
        _, reused = open_browser_context(config, runtime_context=context)
        assert reused is first and context.browser_deadline_monotonic == deadline
        before = context.browser_remaining_seconds()
        timer = threading.Timer(0.15, lease.release)
        timer.start()
        try:
            open_browser_context(other, runtime_context=context)
            after = context.browser_remaining_seconds()
            assert before - 0.07 < after <= before
            assert first.closed
        finally:
            lease.release()
            timer.join(2)
