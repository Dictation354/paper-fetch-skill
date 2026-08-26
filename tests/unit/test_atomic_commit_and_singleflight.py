from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextlib
import multiprocessing
from pathlib import Path
import threading

import pytest

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.http import RequestCancelledError
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.singleflight import (
    RequestSingleFlight,
    fetch_request_singleflight_key,
)


def _process_artifact_write(path: str, body: bytes) -> None:
    ArtifactStore.from_download_dir(Path(path).parent).write_bytes_file(
        Path(path), body
    )


def test_same_path_thread_writers_commit_only_complete_payloads(
    tmp_path: Path,
) -> None:
    target = tmp_path / "paper.pdf"
    bodies = (b"a" * 100_003, b"b" * 100_019)
    barrier = threading.Barrier(2)

    def write(body: bytes) -> Path:
        barrier.wait(timeout=2)
        return ArtifactStore.from_download_dir(tmp_path).write_bytes_file(target, body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, bodies))

    assert results == [target, target]
    assert target.read_bytes() in bodies
    assert list(tmp_path.glob(f".{target.name}.*.part")) == []


def test_overwrite_false_is_idempotent_only_for_identical_content(
    tmp_path: Path,
) -> None:
    target = tmp_path / "paper.pdf"
    target.write_bytes(b"stable")
    before = target.stat().st_mtime_ns
    store = ArtifactStore.from_download_dir(tmp_path)

    assert store.write_bytes_file(target, b"stable", overwrite=False) == target
    assert target.stat().st_mtime_ns == before
    with pytest.raises(FileExistsError, match="content differs"):
        store.write_bytes_file(target, b"different", overwrite=False)

    assert target.read_bytes() == b"stable"
    assert list(tmp_path.glob(f".{target.name}.*.part")) == []


def test_overwrite_true_allows_complete_atomic_replacement(tmp_path: Path) -> None:
    target = tmp_path / "paper.pdf"
    target.write_bytes(b"previous")

    ArtifactStore.from_download_dir(tmp_path).write_bytes_file(
        target,
        b"replacement",
        overwrite=True,
    )

    assert target.read_bytes() == b"replacement"
    assert list(tmp_path.glob(f".{target.name}.*.part")) == []


def test_same_path_process_writers_share_the_path_lock(tmp_path: Path) -> None:
    target = tmp_path / "paper.pdf"
    bodies = (b"first" * 20_003, b"second" * 20_003)
    process_context = multiprocessing.get_context("spawn")
    processes = [
        process_context.Process(
            target=_process_artifact_write,
            args=(str(target), body),
        )
        for body in bodies
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)

    assert [process.exitcode for process in processes] == [0, 0]
    assert target.read_bytes() in bodies
    assert list(tmp_path.glob(f".{target.name}.*.part")) == []


def test_commit_guard_rejects_staged_write_after_cancellation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "paper.pdf"
    target.write_bytes(b"previous")
    staged = threading.Event()
    release = threading.Event()
    cancelled = threading.Event()
    guard_calls = 0
    guard_lock = threading.Lock()

    def guard() -> None:
        nonlocal guard_calls
        with guard_lock:
            guard_calls += 1
            call = guard_calls
        if call == 3:
            staged.set()
            assert release.wait(timeout=2)
        if cancelled.is_set():
            raise RequestCancelledError("cancel fence")

    store = ArtifactStore.from_download_dir(tmp_path, commit_guard=guard)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(store.write_bytes_file, target, b"late")
        assert staged.wait(timeout=2)
        cancelled.set()
        release.set()
        with pytest.raises(RequestCancelledError, match="cancel fence"):
            future.result(timeout=2)

    assert target.read_bytes() == b"previous"
    assert list(tmp_path.glob(f".{target.name}.*.part")) == []


def test_runtime_fence_linearizes_before_final_replace(tmp_path: Path) -> None:
    target = tmp_path / "paper.pdf"
    target.write_bytes(b"previous")
    at_final_boundary = threading.Event()
    release_boundary = threading.Event()
    errors: list[Exception] = []
    context = RuntimeContext(env={}, download_dir=tmp_path)

    class BoundaryGuard:
        def __call__(self) -> None:
            context.commit_guard()

        @contextlib.contextmanager
        def critical_section(self):
            at_final_boundary.set()
            assert release_boundary.wait(timeout=2)
            with context.commit_guard.critical_section():
                yield

    assert context.artifact_store is not None
    context.artifact_store.default_commit_guard = BoundaryGuard()

    def write() -> None:
        try:
            context.artifact_store.write_bytes_file(target, b"late")
        except Exception as error:
            errors.append(error)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(write)
        assert at_final_boundary.wait(timeout=2)
        # This is the linearization point: once it returns, every later critical
        # section observes the permanent fence before os.replace.
        context.fence_commits()
        release_boundary.set()
        future.result(timeout=2)

    context.close()
    assert len(errors) == 1
    assert isinstance(errors[0], RequestCancelledError)
    assert target.read_bytes() == b"previous"
    assert list(tmp_path.glob(f".{target.name}.*.part")) == []


def test_singleflight_waiter_cancel_does_not_cancel_owner() -> None:
    singleflight: RequestSingleFlight[dict[str, list[int]]] = RequestSingleFlight(
        poll_interval_seconds=0.005
    )
    owner_started = threading.Event()
    owner_release = threading.Event()
    waiter_cancelled = threading.Event()
    owner_calls = 0

    def owner() -> dict[str, list[int]]:
        nonlocal owner_calls
        owner_calls += 1
        owner_started.set()
        assert owner_release.wait(timeout=2)
        return {"values": [1]}

    with ThreadPoolExecutor(max_workers=1) as executor:
        owner_future = executor.submit(singleflight.run, "doi+fingerprint", owner)
        assert owner_started.wait(timeout=2)
        waiter_cancelled.set()
        with pytest.raises(RequestCancelledError, match="in-flight DOI"):
            singleflight.run(
                "doi+fingerprint",
                owner,
                cancel_check=waiter_cancelled.is_set,
            )
        assert owner_future.done() is False
        owner_release.set()
        assert owner_future.result(timeout=2) == {"values": [1]}

    assert owner_calls == 1


def test_retained_singleflight_results_are_copied_for_fanout() -> None:
    singleflight: RequestSingleFlight[dict[str, list[int]]] = RequestSingleFlight()
    calls = 0

    def owner() -> dict[str, list[int]]:
        nonlocal calls
        calls += 1
        return {"values": [1]}

    first = singleflight.run("doi", owner, retain_completed=True)
    second = singleflight.run("doi", owner, retain_completed=True)
    second["values"].append(2)

    assert calls == 1
    assert first == {"values": [1]}
    assert second == {"values": [1, 2]}


def test_singleflight_fails_closed_when_result_cannot_be_copied() -> None:
    class Uncopyable:
        def __deepcopy__(self, _memo):
            raise TypeError("cannot copy")

    singleflight: RequestSingleFlight[object] = RequestSingleFlight()
    value = Uncopyable()

    assert singleflight.run("doi", lambda: value, retain_completed=True) is value
    with pytest.raises(RuntimeError, match="could not be copied safely"):
        singleflight.run("doi", lambda: object(), retain_completed=True)


def test_singleflight_waiter_never_reuses_uncopyable_exception() -> None:
    class UncopyableError(Exception):
        def __deepcopy__(self, _memo):
            raise TypeError("cannot copy")

    singleflight: RequestSingleFlight[object] = RequestSingleFlight()
    error = UncopyableError("owner failed")

    with pytest.raises(UncopyableError) as owner_failure:
        singleflight.run(
            "doi",
            lambda: (_ for _ in ()).throw(error),
            retain_completed=True,
        )
    with pytest.raises(RuntimeError, match="UncopyableError: owner failed") as waiter:
        singleflight.run("doi", lambda: object(), retain_completed=True)

    assert owner_failure.value is error
    assert waiter.value is not error


def test_fetch_singleflight_key_canonicalizes_output_directories(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    markdown_dir = tmp_path / "markdown"
    first = FetchPaperRequest(
        query="10.1000/Example",
        save_markdown=True,
        markdown_output_dir=str(tmp_path / "nested" / ".." / "markdown"),
    )
    second = FetchPaperRequest(
        query="https://doi.org/10.1000/example",
        save_markdown=True,
        markdown_output_dir=str(markdown_dir.resolve(strict=False)),
    )

    first_key = fetch_request_singleflight_key(
        "10.1000/example",
        request=first,
        capability_scope={"kind": "public"},
        cache_dir=tmp_path / "nested" / ".." / "cache",
        markdown_dir=tmp_path / "nested" / ".." / "markdown",
    )
    second_key = fetch_request_singleflight_key(
        "10.1000/example",
        request=second,
        capability_scope={"kind": "public"},
        cache_dir=cache_dir.resolve(strict=False),
        markdown_dir=markdown_dir.resolve(strict=False),
    )

    assert first_key == second_key
