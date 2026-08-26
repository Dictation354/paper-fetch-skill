from __future__ import annotations

from io import BytesIO
from pathlib import Path
import gzip
import sys
import threading
import types
import zlib
import zipfile

import pytest
import urllib3

from paper_fetch.extraction.html.assets import download as asset_download_module
from paper_fetch.asset_budget import (
    AssetBudget,
    AssetBudgetExceeded,
    DEFAULT_ASSET_MAX_BYTES_PER_ASSET,
    DEFAULT_ASSET_MAX_BYTES_TOTAL,
    DEFAULT_ASSET_MAX_CONCURRENCY,
    DEFAULT_ASSET_MAX_FILES,
    DEFAULT_ASSET_MAX_PIXELS,
)
from paper_fetch.http import HttpRequestPolicy, HttpTransport
from paper_fetch.http.errors import RequestFailure
from paper_fetch.image_tools import SourceImagePathConversion
from paper_fetch.extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
)
from paper_fetch.extraction.html.assets.state import (
    AssetDownloadResolution,
    resolve_and_collect_downloads_as_completed,
)
from paper_fetch.reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    ASSET_BYTES_TOTAL_EXCEEDED,
    ASSET_CANCELLED,
    ASSET_CONTENT_ENCODING_UNSUPPORTED,
    ASSET_FILE_LIMIT_EXCEEDED,
    ASSET_PIXEL_LIMIT_EXCEEDED,
)
from paper_fetch.providers import _arxiv_assets
from paper_fetch.runtime import RuntimeContext


class _FakeStreamResponse:
    def __init__(
        self,
        body: bytes,
        *,
        headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self._body = BytesIO(body)
        self._paper_fetch_final_url = "https://assets.example/file.bin"
        self.closed = False
        self.released = False
        self.bytes_read = 0

    def read(self, amount: int, **_kwargs: object) -> bytes:
        payload = self._body.read(amount)
        self.bytes_read += len(payload)
        return payload

    def geturl(self) -> str:
        return self._paper_fetch_final_url

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


def _transport_with_response(
    monkeypatch: pytest.MonkeyPatch,
    response: _FakeStreamResponse,
    *,
    max_response_bytes: int = 1024,
) -> HttpTransport:
    transport = HttpTransport(max_response_bytes=max_response_bytes)
    monkeypatch.setattr(
        transport,
        "_perform_request",
        lambda _request, *, timeout: response,
    )
    return transport


def test_asset_budget_defaults_and_route_concurrency_cap() -> None:
    budget = AssetBudget(route_concurrency_cap=2)

    assert budget.max_files == DEFAULT_ASSET_MAX_FILES == 128
    assert (
        budget.max_bytes_per_asset
        == DEFAULT_ASSET_MAX_BYTES_PER_ASSET
        == 32 * 1024 * 1024
    )
    assert budget.max_bytes_total == DEFAULT_ASSET_MAX_BYTES_TOTAL == 256 * 1024 * 1024
    assert budget.max_pixels == DEFAULT_ASSET_MAX_PIXELS == 64_000_000
    assert DEFAULT_ASSET_MAX_CONCURRENCY == 4
    assert budget.max_concurrency == 2
    assert budget.effective_concurrency(8) == 2


def test_failed_candidate_rollback_releases_reserved_bytes() -> None:
    budget = AssetBudget(max_files=2, max_bytes_per_asset=10, max_bytes_total=10)
    reservation = budget.reserve(declared_bytes=8)
    reservation.consume(3)
    reservation.rollback()

    replacement = budget.reserve(declared_bytes=10)
    replacement.consume(10)
    replacement.commit()

    assert budget.snapshot()["retained_bytes"] == 10
    assert budget.snapshot()["retained_files"] == 1


def test_transient_reservation_can_promote_to_retained_file() -> None:
    budget = AssetBudget(max_files=1, max_bytes_per_asset=8, max_bytes_total=8)
    reservation = budget.reserve_transient(declared_bytes=5)
    reservation.consume(3)
    reservation.reconcile_actual()

    assert budget.snapshot()["reserved_bytes"] == 3
    reservation.promote_file()
    reservation.commit()

    assert budget.snapshot()["retained_files"] == 1
    assert budget.snapshot()["retained_bytes"] == 3


def test_asset_reservation_noops_and_stale_tokens_fail_closed() -> None:
    budget = AssetBudget(max_files=4, max_bytes_per_asset=8, max_bytes_total=16)
    reservation = budget.reserve()

    reservation.declare_content_length(-1)
    reservation.consume(0)
    reservation.promote_file()
    reservation.commit()
    reservation.commit()

    stale = budget.reserve()
    stale.rollback()
    with pytest.raises(RuntimeError, match="no longer active"):
        stale.consume(1)


def test_rollback_active_removes_every_registered_staging_path(tmp_path: Path) -> None:
    budget = AssetBudget(max_files=2)
    with_staging = budget.reserve()
    without_staging = budget.reserve()
    staging = tmp_path / "pending.part"
    staging.write_bytes(b"pending")
    with_staging.register_staging(staging)

    budget.rollback_active()

    assert not staging.exists()
    assert budget.snapshot()["reserved_files"] == 0
    with pytest.raises(RuntimeError, match="no longer active"):
        without_staging.consume(1)


def test_admission_counts_129_duplicate_urls_as_129_possible_files() -> None:
    budget = AssetBudget(max_files=128)

    admitted = budget.admit_work(["same-url"] * 129)

    assert sum(admitted) == 128
    assert admitted[-1] is False
    # A later retry subset reuses its first admitted occurrence.
    assert budget.admit_work(["same-url"]) == [True]


def test_total_budget_overrun_cancels_and_removes_all_registered_staging(
    tmp_path: Path,
) -> None:
    budget = AssetBudget(max_files=3, max_bytes_per_asset=10, max_bytes_total=5)
    first_path = tmp_path / "first.part"
    second_path = tmp_path / "second.part"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    first = budget.reserve()
    second = budget.reserve()
    first.register_staging(first_path)
    second.register_staging(second_path)
    first.consume(4)

    with pytest.raises(AssetBudgetExceeded) as raised:
        second.consume(2)

    assert raised.value.reason_code == ASSET_BYTES_TOTAL_EXCEEDED
    assert raised.value.fatal is True
    assert budget.cancelled is True
    assert not first_path.exists()
    assert not second_path.exists()


def test_pixel_limit_is_fail_closed() -> None:
    budget = AssetBudget(max_pixels=12)
    reservation = budget.reserve()

    with pytest.raises(AssetBudgetExceeded) as raised:
        reservation.validate_pixels(4, 4)

    assert raised.value.reason_code == ASSET_PIXEL_LIMIT_EXCEEDED
    reservation.rollback()


def test_worker_slots_enforce_route_cap() -> None:
    budget = AssetBudget(max_concurrency=4, route_concurrency_cap=2)
    barrier = threading.Barrier(4)
    release = threading.Event()
    two_entered = threading.Event()
    all_three_entered = threading.Event()
    active = 0
    entered = 0
    peak = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal active, entered, peak
        barrier.wait()
        with budget.worker_slot():
            with lock:
                active += 1
                entered += 1
                peak = max(peak, active)
                if entered >= 2:
                    two_entered.set()
                if entered >= 3:
                    all_three_entered.set()
            release.wait(1)
            with lock:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for thread in threads:
        thread.start()
    barrier.wait()
    assert two_entered.wait(1)
    assert not all_three_entered.wait(0.1)
    assert peak == 2
    release.set()
    for thread in threads:
        thread.join(1)
        assert not thread.is_alive()
    assert entered == 3
    assert peak == 2


def test_external_cancellation_propagates_from_as_completed_workers() -> None:
    external_cancel = threading.Event()
    release = threading.Event()
    barrier = threading.Barrier(3)
    budget = AssetBudget(
        max_files=4,
        max_concurrency=2,
        cancel_check=external_cancel.is_set,
    )
    captured: list[BaseException] = []

    def resolver(item: int) -> AssetDownloadResolution:
        barrier.wait()
        assert release.wait(2)
        budget.raise_if_cancelled()
        return AssetDownloadResolution(asset={"index": item})

    def coordinate() -> None:
        try:
            resolve_and_collect_downloads_as_completed(
                [1, 2],
                resolver=resolver,
                saver=lambda _resolved: None,
                asset_download_concurrency=2,
                asset_budget=budget,
                force_worker_thread=True,
            )
        except BaseException as exc:
            captured.append(exc)

    thread = threading.Thread(target=coordinate)
    thread.start()
    barrier.wait(timeout=2)
    external_cancel.set()
    release.set()
    thread.join(3)

    assert not thread.is_alive()
    assert len(captured) == 1
    captured_error = captured[0]
    assert isinstance(captured_error, AssetBudgetExceeded)
    assert captured_error.reason_code == ASSET_CANCELLED


def test_stream_unknown_length_counts_actual_bytes_and_cleans_partial_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    response = _FakeStreamResponse(b"123456")
    transport = _transport_with_response(monkeypatch, response)
    destination = tmp_path / "asset.part"
    budget = AssetBudget(max_bytes_per_asset=5, max_bytes_total=20)

    with budget.reserve() as reservation:
        reservation.register_staging(destination)
        with pytest.raises(AssetBudgetExceeded) as raised:
            transport.stream_to_file(
                "GET",
                "https://assets.example/file.bin",
                destination,
                on_content_length=reservation.declare_content_length,
                on_chunk=reservation.consume,
            )

    assert raised.value.reason_code == ASSET_BYTES_PER_ASSET_EXCEEDED
    assert not destination.exists()


def test_stream_content_length_rejected_before_destination_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    response = _FakeStreamResponse(b"payload", headers={"content-length": "7"})
    transport = _transport_with_response(monkeypatch, response)
    destination = tmp_path / "asset.part"
    budget = AssetBudget(max_bytes_per_asset=6, max_bytes_total=20)

    with budget.reserve() as reservation:
        with pytest.raises(AssetBudgetExceeded) as raised:
            transport.stream_to_file(
                "GET",
                "https://assets.example/file.bin",
                destination,
                on_content_length=reservation.declare_content_length,
                on_chunk=reservation.consume,
            )

    assert raised.value.reason_code == ASSET_BYTES_PER_ASSET_EXCEEDED
    assert not destination.exists()


def test_stream_gzip_expansion_is_bounded_by_decoded_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    compressor = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
    compressed = compressor.compress(b"a" * 64) + compressor.flush()
    response = _FakeStreamResponse(
        compressed,
        headers={
            "content-encoding": "gzip",
            "content-length": str(len(compressed)),
        },
    )
    transport = _transport_with_response(monkeypatch, response, max_response_bytes=8)
    destination = tmp_path / "asset.part"

    with pytest.raises(RequestFailure):
        transport.stream_to_file(
            "GET",
            "https://assets.example/file.bin",
            destination,
            request_policy=HttpRequestPolicy(
                max_response_bytes=8,
                max_compressed_response_bytes=128,
            ),
        )

    assert not destination.exists()


def _download_one_streamed_supplementary(
    transport: HttpTransport,
    *,
    output_dir: Path,
    budget: AssetBudget,
) -> dict[str, list[dict[str, object]]]:
    return download_assets(
        SUPPLEMENTARY_KIND,
        transport,
        article_id="10.1234/reason",
        assets=[
            {
                "kind": "supplementary",
                "source_url": "https://assets.example/file.bin",
            }
        ],
        output_dir=output_dir,
        user_agent="test",
        asset_profile="all",
        asset_budget=budget,
        allowed_hosts=("assets.example",),
    )


@pytest.mark.parametrize(
    ("headers", "payload", "reason"),
    [
        (
            {"content-length": "9"},
            b"123456789",
            ASSET_BYTES_PER_ASSET_EXCEEDED,
        ),
        (
            {"content-encoding": "br"},
            b"compressed",
            ASSET_CONTENT_ENCODING_UNSUPPORTED,
        ),
    ],
)
def test_download_assets_preserves_transport_asset_reason_codes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    headers: dict[str, str],
    payload: bytes,
    reason: str,
) -> None:
    response = _FakeStreamResponse(payload, headers=headers)
    transport = _transport_with_response(monkeypatch, response, max_response_bytes=8)
    budget = AssetBudget(max_files=2, max_bytes_per_asset=8, max_bytes_total=16)

    result = _download_one_streamed_supplementary(
        transport,
        output_dir=tmp_path,
        budget=budget,
    )

    assert result["assets"] == []
    assert result["asset_failures"][0]["reason"] == reason
    if reason == ASSET_BYTES_PER_ASSET_EXCEEDED:
        assert budget.cancelled is True
    assert not list(tmp_path.rglob("*.part"))


def test_download_assets_reports_total_budget_for_unknown_length(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    response = _FakeStreamResponse(b"12")
    transport = _transport_with_response(monkeypatch, response, max_response_bytes=8)
    budget = AssetBudget(max_files=3, max_bytes_per_asset=8, max_bytes_total=5)
    retained = budget.reserve(declared_bytes=4)
    retained.consume(4)
    retained.commit()

    result = _download_one_streamed_supplementary(
        transport,
        output_dir=tmp_path,
        budget=budget,
    )

    assert result["assets"] == []
    assert result["asset_failures"][0]["reason"] == ASSET_BYTES_TOTAL_EXCEEDED
    assert budget.cancelled is True
    assert not list(tmp_path.rglob("*.part"))


def test_download_assets_reports_decoded_gzip_expansion_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    compressor = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
    compressed = compressor.compress(b"x" * 64) + compressor.flush()
    response = _FakeStreamResponse(
        compressed,
        headers={
            "content-encoding": "gzip",
            "content-length": str(len(compressed)),
        },
    )
    transport = _transport_with_response(monkeypatch, response, max_response_bytes=128)
    budget = AssetBudget(max_files=2, max_bytes_per_asset=32, max_bytes_total=96)

    result = _download_one_streamed_supplementary(
        transport,
        output_dir=tmp_path,
        budget=budget,
    )

    assert result["assets"] == []
    assert result["asset_failures"][0]["reason"] == ASSET_BYTES_PER_ASSET_EXCEEDED
    assert budget.cancelled is True
    assert not list(tmp_path.rglob("*.part"))


def test_compressed_length_budget_failure_cancels_pending_asset_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    transport = HttpTransport(max_response_bytes=8)
    request_count = 0
    request_lock = threading.Lock()

    def oversized_gzip(_request: object, *, timeout: int) -> _FakeStreamResponse:
        del timeout
        nonlocal request_count
        with request_lock:
            request_count += 1
        return _FakeStreamResponse(
            b"123456789",
            headers={
                "content-encoding": "gzip",
                "content-length": "9",
            },
        )

    monkeypatch.setattr(transport, "_perform_request", oversized_gzip)
    budget = AssetBudget(
        max_files=10,
        max_bytes_per_asset=8,
        max_bytes_total=80,
        max_concurrency=2,
    )
    assets = [
        {
            "kind": "supplementary",
            "source_url": f"https://assets.example/file-{index}.gz",
        }
        for index in range(10)
    ]

    result = download_assets(
        SUPPLEMENTARY_KIND,
        transport,
        article_id="10.1234/cancel-pending",
        assets=assets,
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="all",
        asset_budget=budget,
        asset_download_concurrency=2,
        allowed_hosts=("assets.example",),
    )

    assert result["assets"] == []
    assert result["asset_failures"]
    assert {failure["reason"] for failure in result["asset_failures"]} == {
        ASSET_BYTES_PER_ASSET_EXCEEDED
    }
    # At most the two already-running workers reach the transport. Queued work
    # observes the shared cancellation fence before it can issue a request.
    assert 1 <= request_count <= 2
    assert budget.cancelled is True
    assert budget.diagnostic["reason"] == ASSET_BYTES_PER_ASSET_EXCEEDED
    assert not list(tmp_path.rglob("*.part"))


def test_stream_retry_count_is_not_multiplied_by_transport_layer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    transport = HttpTransport(max_response_bytes=16)
    attempts = 0

    def fail(_request: object, *, timeout: int) -> _FakeStreamResponse:
        nonlocal attempts
        attempts += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr(transport, "_perform_request", fail)
    monkeypatch.setattr(transport, "_cancellable_sleep", lambda _seconds: None)

    result = _download_one_streamed_supplementary(
        transport,
        output_dir=tmp_path,
        budget=AssetBudget(max_files=4, max_bytes_per_asset=16),
    )

    assert result["assets"] == []
    assert attempts == 3
    assert not list(tmp_path.rglob("*.part"))


def test_partial_body_retry_uses_fresh_staging_and_rolls_back_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class PartialResponse(_FakeStreamResponse):
        def __init__(self) -> None:
            super().__init__(b"partial")
            self._reads = 0

        def read(self, amount: int, **kwargs: object) -> bytes:
            del amount, kwargs
            self._reads += 1
            if self._reads == 1:
                self.bytes_read += 4
                return b"part"
            raise TimeoutError("body stalled")

    transport = HttpTransport(max_response_bytes=16)
    responses: list[_FakeStreamResponse] = [
        PartialResponse(),
        _FakeStreamResponse(b"success"),
    ]
    request_count = 0
    staging_paths: list[Path] = []
    original_stream_to_file = transport.stream_to_file

    def perform(_request: object, *, timeout: int) -> _FakeStreamResponse:
        del timeout
        nonlocal request_count
        request_count += 1
        return responses.pop(0)

    def record_stream(
        method: str,
        url: str,
        destination: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        staging_paths.append(destination)
        return original_stream_to_file(method, url, destination, **kwargs)

    monkeypatch.setattr(transport, "_perform_request", perform)
    monkeypatch.setattr(transport, "stream_to_file", record_stream)
    monkeypatch.setattr(transport, "_cancellable_sleep", lambda _seconds: None)
    budget = AssetBudget(max_files=2, max_bytes_per_asset=16, max_bytes_total=16)

    result = _download_one_streamed_supplementary(
        transport,
        output_dir=tmp_path,
        budget=budget,
    )

    assert result["asset_failures"] == []
    assert len(result["assets"]) == 1
    assert request_count == 2
    assert len(staging_paths) == 2
    assert staging_paths[0] != staging_paths[1]
    assert all(not path.exists() for path in staging_paths)
    assert budget.snapshot()["retained_bytes"] == len(b"success")


def test_arxiv_gzip_expansion_uses_shared_budget_and_cleans_staging(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "source.gz"
    archive.write_bytes(gzip.compress(b"x" * 64))
    budget = AssetBudget(max_files=4, max_bytes_per_asset=16, max_bytes_total=64)

    with pytest.raises(AssetBudgetExceeded) as raised:
        _arxiv_assets._read_arxiv_source_files_from_path(
            archive,
            staging_dir=tmp_path,
            asset_budget=budget,
        )

    assert raised.value.reason_code == ASSET_BYTES_PER_ASSET_EXCEEDED
    assert budget.cancelled is True
    assert not list(tmp_path.glob(".paper-fetch-arxiv-member-*.part"))


def test_arxiv_member_actual_bytes_override_forged_declared_size(
    tmp_path: Path,
) -> None:
    files: dict[str, _arxiv_assets._ArxivSourceMember] = {}
    budget = AssetBudget(max_files=4, max_bytes_per_asset=8, max_bytes_total=32)

    with pytest.raises(AssetBudgetExceeded) as raised:
        _arxiv_assets._retain_arxiv_source_member(
            files,
            name="figure.bin",
            declared_size=1,
            handle=BytesIO(b"123456789"),
            staging_dir=tmp_path,
            asset_budget=budget,
        )

    assert raised.value.reason_code == ASSET_BYTES_PER_ASSET_EXCEEDED
    assert files == {}
    assert not list(tmp_path.glob(".paper-fetch-arxiv-member-*.part"))


def test_arxiv_member_cumulative_limit_stops_and_cleans_all_staging(
    tmp_path: Path,
) -> None:
    files: dict[str, _arxiv_assets._ArxivSourceMember] = {}
    budget = AssetBudget(max_files=4, max_bytes_per_asset=8, max_bytes_total=10)
    _arxiv_assets._retain_arxiv_source_member(
        files,
        name="one.bin",
        declared_size=None,
        handle=BytesIO(b"123456"),
        staging_dir=tmp_path,
        asset_budget=budget,
    )

    with pytest.raises(AssetBudgetExceeded) as raised:
        _arxiv_assets._retain_arxiv_source_member(
            files,
            name="two.bin",
            declared_size=None,
            handle=BytesIO(b"abcdef"),
            staging_dir=tmp_path,
            asset_budget=budget,
        )
    _arxiv_assets._cleanup_arxiv_source_members(files)

    assert raised.value.reason_code == ASSET_BYTES_TOTAL_EXCEEDED
    assert not list(tmp_path.glob(".paper-fetch-arxiv-member-*.part"))


def test_arxiv_archive_member_count_uses_shared_file_limit(
    tmp_path: Path,
) -> None:
    files: dict[str, _arxiv_assets._ArxivSourceMember] = {}
    budget = AssetBudget(max_files=2, max_bytes_per_asset=8, max_bytes_total=32)
    for name in ("one.bin", "two.bin"):
        _arxiv_assets._retain_arxiv_source_member(
            files,
            name=name,
            declared_size=1,
            handle=BytesIO(b"x"),
            staging_dir=tmp_path,
            asset_budget=budget,
        )

    with pytest.raises(AssetBudgetExceeded) as raised:
        _arxiv_assets._retain_arxiv_source_member(
            files,
            name="three.bin",
            declared_size=1,
            handle=BytesIO(b"x"),
            staging_dir=tmp_path,
            asset_budget=budget,
        )
    _arxiv_assets._cleanup_arxiv_source_members(files)

    assert raised.value.reason_code == ASSET_FILE_LIMIT_EXCEEDED
    assert budget.cancelled is True
    assert not list(tmp_path.glob(".paper-fetch-arxiv-member-*.part"))


def test_arxiv_archive_counts_duplicate_regular_members_before_deduplication(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "duplicates.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("duplicate.tex", b"\\documentclass{article}")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("duplicate.tex", b"second")
            archive.writestr("duplicate.tex", b"third")
    budget = AssetBudget(max_files=2, max_bytes_per_asset=64, max_bytes_total=128)

    with pytest.raises(AssetBudgetExceeded) as raised:
        _arxiv_assets._read_arxiv_source_files_from_path(
            archive_path,
            staging_dir=tmp_path,
            asset_budget=budget,
        )

    assert raised.value.reason_code == ASSET_FILE_LIMIT_EXCEEDED
    assert raised.value.diagnostic["encountered_regular_members"] == 3
    assert budget.diagnostic["boundary"] == "arxiv_archive_member_count"
    assert not list(tmp_path.glob(".paper-fetch-arxiv-member-*.part"))


def test_arxiv_pdf_render_prechecks_pixels_and_forces_png_encoder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    save_calls: list[tuple[str, str | None]] = []
    pixmap_calls = 0

    class FakePixmap:
        width = 20
        height = 20

        def save(self, path: str, *, output: str | None = None) -> None:
            save_calls.append((path, output))
            Path(path).write_bytes(_SMALL_PNG)

    class FakePage:
        rect = types.SimpleNamespace(width=10, height=10)

        def get_pixmap(self, **_kwargs: object) -> FakePixmap:
            nonlocal pixmap_calls
            pixmap_calls += 1
            return FakePixmap()

    class FakeDocument:
        def __enter__(self) -> FakeDocument:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def __len__(self) -> int:
            return 1

        def load_page(self, _index: int) -> FakePage:
            return FakePage()

    fake_module = types.SimpleNamespace(
        open=lambda _path: FakeDocument(),
        Matrix=lambda x, y: (x, y),
    )
    monkeypatch.setitem(sys.modules, "pymupdf", fake_module)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-fake")
    destination = tmp_path / "render.part"
    budget = AssetBudget(max_files=2, max_bytes_per_asset=128, max_pixels=1000)
    reservation = budget.reserve()

    width, height, output_bytes = _arxiv_assets._render_pdf_source_figure_path_to_png(
        source,
        destination,
        reservation=reservation,
    )

    assert (width, height) == (20, 20)
    assert output_bytes == len(_SMALL_PNG)
    assert pixmap_calls == 1
    assert save_calls == [(str(destination), "png")]
    reservation.rollback()
    assert not destination.exists()


def test_arxiv_pdf_render_rejects_pixels_before_pixmap_allocation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakePage:
        rect = types.SimpleNamespace(width=100, height=100)

        def get_pixmap(self, **_kwargs: object) -> object:
            raise AssertionError("pixel preflight must run before raster allocation")

    class FakeDocument:
        def __enter__(self) -> FakeDocument:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def __len__(self) -> int:
            return 1

        def load_page(self, _index: int) -> FakePage:
            return FakePage()

    monkeypatch.setitem(
        sys.modules,
        "pymupdf",
        types.SimpleNamespace(
            open=lambda _path: FakeDocument(),
            Matrix=lambda x, y: (x, y),
        ),
    )
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-fake")
    destination = tmp_path / "render.part"
    reservation = AssetBudget(max_files=2, max_pixels=100).reserve()

    with pytest.raises(AssetBudgetExceeded) as raised:
        _arxiv_assets._render_pdf_source_figure_path_to_png(
            source,
            destination,
            reservation=reservation,
        )

    assert raised.value.reason_code == ASSET_PIXEL_LIMIT_EXCEEDED
    assert not destination.exists()


def test_stream_rejects_truncated_gzip_and_preserves_existing_destination(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    compressor = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
    compressed = (compressor.compress(b"payload") + compressor.flush())[:-4]
    response = _FakeStreamResponse(
        compressed,
        headers={"content-encoding": "gzip"},
    )
    transport = _transport_with_response(monkeypatch, response)
    destination = tmp_path / "asset.part"

    with pytest.raises(RequestFailure, match="Truncated gzip"):
        transport.stream_to_file("GET", "https://assets.example/file.bin", destination)
    assert not destination.exists()

    destination.write_bytes(b"existing")
    fresh_response = _FakeStreamResponse(b"new")
    monkeypatch.setattr(
        transport,
        "_perform_request",
        lambda _request, *, timeout: fresh_response,
    )
    with pytest.raises(FileExistsError):
        transport.stream_to_file("GET", "https://assets.example/file.bin", destination)
    assert destination.read_bytes() == b"existing"


@pytest.mark.parametrize(
    ("first_result", "retry_kwargs"),
    [
        (
            _FakeStreamResponse(
                b"rate limited",
                headers={"retry-after": "0"},
                status=429,
            ),
            {"retry_on_rate_limit": True},
        ),
        (TimeoutError("first attempt timed out"), {"retry_on_transient": True}),
    ],
)
def test_stream_retries_before_body_with_one_final_budget_accounting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    first_result: _FakeStreamResponse | TimeoutError,
    retry_kwargs: dict[str, bool],
) -> None:
    transport = HttpTransport(max_response_bytes=64)
    successful = _FakeStreamResponse(b"payload", headers={"content-length": "7"})
    attempts: list[object] = [first_result, successful]

    def perform(_request: object, *, timeout: int) -> _FakeStreamResponse:
        result = attempts.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(transport, "_perform_request", perform)
    monkeypatch.setattr(transport, "_cancellable_sleep", lambda _seconds: None)
    budget = AssetBudget(max_bytes_per_asset=8, max_bytes_total=8)
    destination = tmp_path / "retry.part"

    with budget.reserve() as reservation:
        reservation.register_staging(destination)
        result = transport.stream_to_file(
            "GET",
            "https://assets.example/file.bin",
            destination,
            on_content_length=reservation.declare_content_length,
            on_chunk=reservation.consume,
            **retry_kwargs,
        )
        reservation.unregister_staging(destination)
        reservation.commit()

    assert not attempts
    assert result["downloaded_bytes"] == 7
    assert destination.read_bytes() == b"payload"
    assert budget.snapshot()["retained_bytes"] == 7


def test_cookie_seed_get_reads_only_preview_and_preserves_multiple_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = urllib3._collections.HTTPHeaderDict()
    headers.add("content-type", "text/html")
    headers.add("set-cookie", "one=first; Path=/")
    headers.add("set-cookie", "two=second; Path=/article")
    response = _FakeStreamResponse(b"x" * 20_000, headers=headers)  # type: ignore[arg-type]
    transport = _transport_with_response(
        monkeypatch, response, max_response_bytes=32_000
    )
    from paper_fetch.extraction.html.assets.requester import PinnedAssetSession

    session = PinnedAssetSession(
        transport,
        browser_cookies=None,
        seed_urls=["https://assets.example/article"],
        headers={},
        allowed_hosts=("assets.example",),
    )

    session.ensure_seeded()
    session.ensure_seeded()

    assert response.bytes_read == 8192
    assert session.seed_attempts == 1
    assert (
        session.request_headers_for("https://assets.example/article/1", {})["Cookie"]
        == "two=second; one=first"
    )


def test_download_assets_publishes_streamed_file_and_commits_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    png = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + (10).to_bytes(4, "big")
        + (10).to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
    )
    response = _FakeStreamResponse(
        png,
        headers={"content-type": "image/png", "content-length": str(len(png))},
    )
    transport = _transport_with_response(
        monkeypatch,
        response,
        max_response_bytes=1024,
    )
    budget = AssetBudget(max_files=2, max_bytes_per_asset=1024, max_bytes_total=1024)

    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id="10.1234/example",
        assets=[{"kind": "figure", "url": "https://assets.example/file.png"}],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="body",
        asset_budget=budget,
        candidate_builder=lambda *_args, **_kwargs: ["https://assets.example/file.png"],
    )

    assert result["asset_failures"] == []
    assert len(result["assets"]) == 1
    published = Path(result["assets"][0]["path"])
    assert published.read_bytes() == png
    assert not list(published.parent.glob("*.part"))
    assert budget.snapshot()["retained_files"] == 1
    assert budget.snapshot()["retained_bytes"] == len(png)


_SMALL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR"
    + (1).to_bytes(4, "big")
    + (1).to_bytes(4, "big")
    + b"\x08\x06\x00\x00\x00"
)


class _SessionReuseTransport:
    def __init__(self) -> None:
        self.cancelled = False
        self._pinned_streaming_ready = True
        self.seed_urls: list[str] = []

    def request(self, method: str, url: str, **_kwargs: object) -> dict[str, object]:
        assert method == "GET"
        self.seed_urls.append(url)
        return {
            "status_code": 200,
            "headers": {},
            "body": b"",
            "url": url,
        }

    def stream_to_file(
        self,
        _method: str,
        url: str,
        destination: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        payload = (
            _SMALL_PNG if url.endswith(".png") else url.rsplit("/", 1)[-1].encode()
        )
        content_length = kwargs["on_content_length"]
        on_chunk = kwargs["on_chunk"]
        assert callable(content_length)
        assert callable(on_chunk)
        content_length(len(payload))
        on_chunk(len(payload))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(payload)
        return {
            "status_code": 200,
            "headers": {
                "content-type": "image/png"
                if url.endswith(".png")
                else "application/octet-stream"
            },
            "url": url,
            "staging_path": str(destination),
            "downloaded_bytes": len(payload),
            "body_preview": payload,
        }


def test_one_worker_seeds_once_instead_of_once_per_candidate(tmp_path: Path) -> None:
    transport = _SessionReuseTransport()
    seed_urls = ["https://publisher.example/article", "https://publisher.example/auth"]
    assets = [
        {
            "kind": "supplementary",
            "source_url": f"https://publisher.example/file-{index}.bin",
            "heading": f"File {index}",
        }
        for index in range(3)
    ]

    result = download_assets(
        SUPPLEMENTARY_KIND,
        transport,  # type: ignore[arg-type]
        article_id="10.1234/seeded",
        assets=assets,
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="all",
        seed_urls=seed_urls,
        asset_download_concurrency=1,
        fetch_policy="browser_first",
        allowed_hosts=("publisher.example",),
    )

    assert len(result["assets"]) == 3
    assert transport.seed_urls == seed_urls


def test_one_runtime_worker_reuses_seed_session_across_figure_and_supplementary(
    tmp_path: Path,
) -> None:
    transport = _SessionReuseTransport()
    runtime_context = RuntimeContext(
        transport=transport,  # type: ignore[arg-type]
        download_dir=tmp_path,
    )
    common = {
        "article_id": "10.1234/cross-kind",
        "output_dir": tmp_path,
        "user_agent": "test",
        "seed_urls": ["https://publisher.example/article"],
        "allowed_hosts": ("publisher.example",),
        "runtime_context": runtime_context,
        "asset_budget": runtime_context.asset_budget,
        "asset_download_concurrency": 1,
        "fetch_policy": "browser_first",
    }

    figure = download_assets(
        FIGURE_KIND,
        transport,  # type: ignore[arg-type]
        assets=[{"kind": "figure", "url": "https://publisher.example/file.png"}],
        asset_profile="body",
        candidate_builder=lambda *_args, **_kwargs: [
            "https://publisher.example/file.png"
        ],
        **common,
    )
    supplementary = download_assets(
        SUPPLEMENTARY_KIND,
        transport,  # type: ignore[arg-type]
        assets=[
            {
                "kind": "supplementary",
                "source_url": "https://publisher.example/file.bin",
            }
        ],
        asset_profile="all",
        **common,
    )

    assert len(figure["assets"]) == 1
    assert len(supplementary["assets"]) == 1
    assert transport.seed_urls == ["https://publisher.example/article"]


def test_shared_budget_spans_figure_and_supplementary_calls(tmp_path: Path) -> None:
    transport = _SessionReuseTransport()
    budget = AssetBudget(
        max_files=3,
        max_bytes_per_asset=64,
        max_bytes_total=len(_SMALL_PNG) + 6,
    )
    first = download_assets(
        FIGURE_KIND,
        transport,  # type: ignore[arg-type]
        article_id="10.1234/shared",
        assets=[{"kind": "figure", "url": "https://assets.example/file.png"}],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="body",
        asset_budget=budget,
        candidate_builder=lambda *_args, **_kwargs: ["https://assets.example/file.png"],
    )
    second = download_assets(
        SUPPLEMENTARY_KIND,
        transport,  # type: ignore[arg-type]
        article_id="10.1234/shared",
        assets=[
            {
                "kind": "supplementary",
                "source_url": "https://assets.example/7654321",
            }
        ],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="all",
        asset_budget=budget,
    )

    assert len(first["assets"]) == 1
    assert second["assets"] == []
    assert second["asset_failures"][0]["reason"] == ASSET_BYTES_TOTAL_EXCEEDED


class _ConcurrentStreamTransport(_SessionReuseTransport):
    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self.saturated = threading.Event()
        self.fifth_entered = threading.Event()
        self._active = 0
        self.peak = 0
        self._lock = threading.Lock()

    def stream_to_file(
        self,
        _method: str,
        url: str,
        destination: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        with self._lock:
            self._active += 1
            self.peak = max(self.peak, self._active)
            if self._active >= 4:
                self.saturated.set()
            if self._active >= 5:
                self.fifth_entered.set()
        try:
            assert self.release.wait(2)
            return super().stream_to_file(_method, url, destination, **kwargs)
        finally:
            with self._lock:
                self._active -= 1


def test_parallel_figure_and_supplementary_calls_share_worker_slots(
    tmp_path: Path,
) -> None:
    transport = _ConcurrentStreamTransport()
    runtime = RuntimeContext(
        transport=transport,  # type: ignore[arg-type]
        download_dir=tmp_path,
        asset_budget=AssetBudget(max_files=16, max_concurrency=4),
    )
    assert runtime.asset_budget is not None
    barrier = threading.Barrier(3)
    results: dict[str, dict[str, list[dict[str, object]]]] = {}

    def body() -> None:
        barrier.wait()
        results["body"] = download_assets(
            FIGURE_KIND,
            transport,  # type: ignore[arg-type]
            article_id="10.1234/concurrency",
            assets=[
                {
                    "kind": "figure",
                    "url": f"https://assets.example/figure-{index}.png",
                }
                for index in range(4)
            ],
            output_dir=tmp_path,
            user_agent="test",
            asset_profile="body",
            candidate_builder=lambda _transport, *, asset, **_kwargs: [asset["url"]],
            asset_download_concurrency=4,
            fetch_policy="direct_then_browser",
            runtime_context=runtime,
            allowed_hosts=("assets.example",),
        )

    def supplementary() -> None:
        barrier.wait()
        results["supplementary"] = download_assets(
            SUPPLEMENTARY_KIND,
            transport,  # type: ignore[arg-type]
            article_id="10.1234/concurrency",
            assets=[
                {
                    "kind": "supplementary",
                    "source_url": f"https://assets.example/supp-{index}.bin",
                }
                for index in range(4)
            ],
            output_dir=tmp_path,
            user_agent="test",
            asset_profile="all",
            asset_download_concurrency=4,
            fetch_policy="direct_then_browser",
            runtime_context=runtime,
            allowed_hosts=("assets.example",),
        )

    threads = [threading.Thread(target=body), threading.Thread(target=supplementary)]
    for thread in threads:
        thread.start()
    barrier.wait()
    assert transport.saturated.wait(2)
    assert not transport.fifth_entered.wait(0.1)
    transport.release.set()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()

    assert transport.peak == 4
    assert len(results["body"]["assets"]) == 4
    assert len(results["supplementary"]["assets"]) == 4


class _EmptyStreamTransport(_SessionReuseTransport):
    def stream_to_file(
        self,
        _method: str,
        url: str,
        destination: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        content_length = kwargs["on_content_length"]
        assert callable(content_length)
        content_length(0)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.open("xb").close()
        return {
            "status_code": 200,
            "headers": {"content-type": "application/octet-stream"},
            "url": url,
            "staging_path": str(destination),
            "downloaded_bytes": 0,
            "body_preview": b"",
        }


def test_empty_streamed_staging_is_rolled_back(tmp_path: Path) -> None:
    budget = AssetBudget(max_files=2, max_bytes_total=64)
    result = download_assets(
        SUPPLEMENTARY_KIND,
        _EmptyStreamTransport(),  # type: ignore[arg-type]
        article_id="10.1234/empty",
        assets=[
            {
                "kind": "supplementary",
                "source_url": "https://assets.example/empty.bin",
            }
        ],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="all",
        asset_budget=budget,
        allowed_hosts=("assets.example",),
    )

    assert result["assets"] == []
    assert result["asset_failures"][0]["reason"] == "empty_response_body"
    assert budget.snapshot()["retained_files"] == 0
    assert budget.snapshot()["reserved_files"] == 0
    assert not list(tmp_path.rglob("*.part"))


class _TiffStreamTransport(_SessionReuseTransport):
    source_payload = b"II*\x00source-tiff-on-disk"

    def stream_to_file(
        self,
        _method: str,
        url: str,
        destination: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        content_length = kwargs["on_content_length"]
        on_chunk = kwargs["on_chunk"]
        assert callable(content_length)
        assert callable(on_chunk)
        content_length(len(self.source_payload))
        on_chunk(len(self.source_payload))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(self.source_payload)
        return {
            "status_code": 200,
            "headers": {"content-type": "image/tiff"},
            "url": url,
            "staging_path": str(destination),
            "downloaded_bytes": len(self.source_payload),
            "body_preview": self.source_payload,
        }


def test_streamed_tiff_conversion_publishes_source_and_png_with_one_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    converted_payload = _SMALL_PNG

    def convert(
        _source: Path,
        output: Path,
        **_kwargs: object,
    ) -> SourceImagePathConversion:
        with output.open("xb") as stream:
            stream.write(converted_payload)
        return SourceImagePathConversion(
            path=output,
            content_type="image/png",
            source_format="tiff",
            tool="fake-vips",
            output_bytes=len(converted_payload),
        )

    monkeypatch.setattr(
        asset_download_module,
        "convert_source_image_path_to_png",
        convert,
    )
    transport = _TiffStreamTransport()
    budget = AssetBudget(max_files=4, max_bytes_per_asset=128, max_bytes_total=256)
    result = download_assets(
        FIGURE_KIND,
        transport,  # type: ignore[arg-type]
        article_id="10.1234/converted",
        assets=[
            {
                "kind": "figure",
                "url": "https://assets.example/source.tif",
            }
        ],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="body",
        asset_budget=budget,
        allowed_hosts=("assets.example",),
        candidate_builder=lambda *_args, **_kwargs: [
            "https://assets.example/source.tif"
        ],
    )

    assert result["asset_failures"] == []
    assert len(result["assets"]) == 1
    downloaded = result["assets"][0]
    assert Path(downloaded["path"]).read_bytes() == converted_payload
    assert (
        Path(downloaded["original_source_path"]).read_bytes()
        == transport.source_payload
    )
    assert downloaded["conversion_source_format"] == "tiff"
    assert downloaded["conversion_tool"] == "fake-vips"
    assert budget.snapshot()["retained_files"] == 2
    assert budget.snapshot()["retained_bytes"] == len(converted_payload) + len(
        transport.source_payload
    )
