from __future__ import annotations

import contextlib
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from paper_fetch.mcp import cache_index
from paper_fetch.utils import sanitize_filename


def _write_markdown(path: Path, doi: str) -> None:
    metadata = {
        "doi": doi,
        "source": "unit_test",
        "has_fulltext": True,
        "content_kind": "fulltext",
    }
    path.write_text(
        "---\n"
        + yaml.safe_dump(metadata, sort_keys=False)
        + "---\n\n# Paper\n"
        + ("body " * 100),
        encoding="utf-8",
    )


def test_fifty_doi_refresh_opens_each_changed_markdown_once(
    tmp_path: Path, monkeypatch
) -> None:
    dois = [f"10.1000/batch-{index}" for index in range(50)]
    paths = []
    for index, doi in enumerate(dois):
        path = tmp_path / f"paper-{index}.md"
        _write_markdown(path, doi)
        paths.append(path.resolve())

    real_reader = cache_index.read_markdown_front_matter_file
    reads: list[Path] = []

    def counted(path: Path):
        reads.append(path.resolve())
        return real_reader(path)

    monkeypatch.setattr(cache_index, "read_markdown_front_matter_file", counted)
    first = cache_index.refresh_cache_index_for_dois(tmp_path, dois)
    first_counts = {path: reads.count(path) for path in paths}
    reads.clear()
    second = cache_index.refresh_cache_index_for_dois(tmp_path, dois)

    assert all(len(first[doi]) == 1 for doi in dois)
    assert all(len(second[doi]) == 1 for doi in dois)
    assert set(first_counts.values()) == {1}
    assert reads == []


def test_fifty_sequential_doi_refreshes_read_each_markdown_at_most_once(
    tmp_path: Path, monkeypatch
) -> None:
    dois = [f"10.1000/sequential-{index}" for index in range(50)]
    paths = []
    for index, doi in enumerate(dois):
        path = tmp_path / f"sequential-paper-{index}.md"
        _write_markdown(path, doi)
        paths.append(path.resolve())

    real_reader = cache_index.read_markdown_front_matter_file
    reads: list[Path] = []

    def counted(path: Path):
        reads.append(path.resolve())
        return real_reader(path)

    monkeypatch.setattr(cache_index, "read_markdown_front_matter_file", counted)
    for doi in dois:
        result = cache_index.refresh_cache_index_for_doi(tmp_path, doi)
        assert any(entry["doi"] == doi for entry in result)

    assert {path: reads.count(path) for path in paths} == {path: 1 for path in paths}


def test_markdown_scan_and_hash_are_outside_global_index_lock(
    tmp_path: Path, monkeypatch
) -> None:
    doi = "10.1000/outside-lock"
    _write_markdown(tmp_path / "paper.md", doi)
    real_lock = cache_index.cache_file_lock
    real_reader = cache_index.read_markdown_front_matter_file
    local = threading.local()

    @contextlib.contextmanager
    def tracked_lock(path: Path):
        with real_lock(path):
            local.held = True
            try:
                yield
            finally:
                local.held = False

    def asserted_reader(path: Path):
        assert not getattr(local, "held", False)
        return real_reader(path)

    monkeypatch.setattr(cache_index, "cache_file_lock", tracked_lock)
    monkeypatch.setattr(cache_index, "read_markdown_front_matter_file", asserted_reader)

    result = cache_index.refresh_cache_index_for_dois(tmp_path, [doi])

    assert len(result[doi]) == 1


def test_concurrent_refresh_merges_different_dois_without_lost_update(
    tmp_path: Path, monkeypatch
) -> None:
    dois = ["10.1000/concurrent-a", "10.1000/concurrent-b"]
    for index, doi in enumerate(dois):
        _write_markdown(tmp_path / f"paper-{index}.md", doi)
    barrier = threading.Barrier(2)
    real_scan = cache_index.scan_cached_files_for_dois

    def synchronized_scan(*args, **kwargs):
        barrier.wait(timeout=5)
        return real_scan(*args, **kwargs)

    monkeypatch.setattr(cache_index, "scan_cached_files_for_dois", synchronized_scan)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(cache_index.refresh_cache_index_for_dois, tmp_path, [doi])
            for doi in dois
        ]
        for future in futures:
            future.result(timeout=10)

    entries = cache_index.read_cache_index(tmp_path).entries
    assert {entry["doi"] for entry in entries} == set(dois)


def test_refresh_preserves_same_doi_incremental_update_committed_during_scan(
    tmp_path: Path, monkeypatch
) -> None:
    doi = "10.1000/concurrent-same-doi"
    payload_path = tmp_path / f"{sanitize_filename(doi)}.xml"
    payload_path.write_text("old", encoding="utf-8")
    cache_index.refresh_cache_index_for_doi(tmp_path, doi)

    scan_finished = threading.Event()
    allow_merge = threading.Event()
    real_scan = cache_index.scan_cached_files_for_dois

    def paused_scan(*args, **kwargs):
        result = real_scan(*args, **kwargs)
        scan_finished.set()
        assert allow_merge.wait(timeout=5)
        return result

    monkeypatch.setattr(cache_index, "scan_cached_files_for_dois", paused_scan)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(cache_index.refresh_cache_index_for_doi, tmp_path, doi)
        assert scan_finished.wait(timeout=5)
        payload_path.write_text("new payload with different size", encoding="utf-8")
        cache_index.register_cache_files_for_doi(tmp_path, doi)
        allow_merge.set()
        future.result(timeout=10)

    entry = next(
        entry
        for entry in cache_index.read_cache_index(tmp_path).entries
        if Path(str(entry["path"])) == payload_path.resolve()
    )
    assert entry["size"] == payload_path.stat().st_size


def test_rescan_preserves_same_doi_registration_committed_during_scan(
    tmp_path: Path, monkeypatch
) -> None:
    doi = "10.1000/concurrent-rescan"
    original = tmp_path / "original.md"
    concurrent = tmp_path / "concurrent.md"
    _write_markdown(original, doi)
    assert (
        cache_index.register_markdown_entry(
            tmp_path,
            doi,
            original,
            source="unit_test",
            has_fulltext=True,
            content_kind="fulltext",
        )
        is not None
    )

    scan_finished = threading.Event()
    allow_merge = threading.Event()
    real_scan = cache_index.scan_cached_files_for_dois

    def paused_scan(*args, **kwargs):
        result = real_scan(*args, **kwargs)
        scan_finished.set()
        assert allow_merge.wait(timeout=5)
        return result

    monkeypatch.setattr(cache_index, "scan_cached_files_for_dois", paused_scan)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(cache_index.rescan_cache_index, tmp_path)
        assert scan_finished.wait(timeout=5)
        _write_markdown(concurrent, doi)
        assert (
            cache_index.register_markdown_entry(
                tmp_path,
                doi,
                concurrent,
                source="unit_test",
                has_fulltext=True,
                content_kind="fulltext",
            )
            is not None
        )
        allow_merge.set()
        future.result(timeout=10)

    entries = cache_index.read_cache_index(tmp_path).entries
    assert {
        Path(str(entry["path"])).name
        for entry in entries
        if entry["doi"] == doi and entry["kind"] == "markdown"
    } == {"original.md", "concurrent.md"}
