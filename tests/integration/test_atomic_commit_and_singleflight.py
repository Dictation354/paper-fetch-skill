from __future__ import annotations
import multiprocessing
from pathlib import Path
from paper_fetch.artifacts import ArtifactStore


def _process_artifact_write(path: str, body: bytes) -> None:
    ArtifactStore.from_download_dir(Path(path).parent).write_bytes_file(
        Path(path), body
    )


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
