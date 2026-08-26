"""Process-local request singleflight with cancellation-isolated waiters."""

from __future__ import annotations

import copy
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from collections.abc import Callable, Hashable
import hashlib
import json
import threading
from pathlib import Path
from typing import Generic, TypeVar, cast

from ..http import RequestCancelledError

ResultT = TypeVar("ResultT")


class RequestSingleFlight(Generic[ResultT]):
    """Coalesce overlapping owners without coupling waiter cancellation.

    Completed calls are removed immediately; durable reuse remains the cache's
    responsibility. Values and failures handed to waiters are deep copies so a
    caller cannot mutate another request's result or traceback-bearing exception.
    """

    def __init__(self, *, poll_interval_seconds: float = 0.05) -> None:
        self._poll_interval_seconds = max(0.001, float(poll_interval_seconds))
        self._lock = threading.Lock()
        self._inflight: dict[Hashable, Future[tuple[bool, object]]] = {}

    @staticmethod
    def _copy(value: object) -> object:
        try:
            copied = copy.deepcopy(value)
        except Exception as error:
            if isinstance(value, BaseException):
                return RuntimeError(f"{type(value).__name__}: {value}")
            raise RuntimeError(
                "Singleflight result could not be copied safely for another request."
            ) from error
        if copied is value and not isinstance(
            value,
            (str, bytes, int, float, bool, complex, type(None), tuple, frozenset),
        ):
            if isinstance(value, BaseException):
                return RuntimeError(f"{type(value).__name__}: {value}")
            raise RuntimeError(
                "Singleflight result copy retained mutable object identity."
            )
        return copied

    def run(
        self,
        key: Hashable,
        owner: Callable[[], ResultT],
        *,
        cancel_check: Callable[[], bool] | None = None,
        retain_completed: bool = False,
    ) -> ResultT:
        with self._lock:
            future = self._inflight.get(key)
            is_owner = future is None
            if future is None:
                future = Future()
                self._inflight[key] = future

        if is_owner:
            try:
                result = owner()
            except BaseException as error:
                future.set_result((False, self._copy(error)))
                raise
            else:
                try:
                    snapshot = self._copy(result)
                except Exception as copy_error:
                    # The owner has an independent result and may return it.  A
                    # waiter must fail closed instead of receiving a shared
                    # mutable object when no safe snapshot can be produced.
                    future.set_result((False, copy_error))
                else:
                    future.set_result((True, snapshot))
                return result
            finally:
                if not retain_completed:
                    with self._lock:
                        if self._inflight.get(key) is future:
                            self._inflight.pop(key, None)

        while True:
            if cancel_check is not None and cancel_check():
                raise RequestCancelledError(
                    "Request cancelled while waiting for an in-flight DOI fetch."
                )
            try:
                succeeded, value = future.result(timeout=self._poll_interval_seconds)
                break
            except FutureTimeoutError:
                continue
        copied = self._copy(value)
        if succeeded:
            return cast(ResultT, copied)
        if isinstance(copied, BaseException):
            raise copied
        raise RuntimeError(str(copied))


def semantic_singleflight_fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_directory(value: Path | str | None) -> str | None:
    if value is None:
        return None
    return str(Path(value).expanduser().resolve(strict=False))


def fetch_request_singleflight_key(
    canonical_doi: str,
    *,
    request: object,
    capability_scope: object,
    cache_dir: Path | str | None,
    markdown_dir: Path | str | None,
) -> tuple[str, str]:
    """Build the one global fetch key shared by single and batch adapters."""

    model_dump = getattr(request, "model_dump", None)
    if not callable(model_dump):
        raise TypeError("singleflight request must provide model_dump()")
    request_semantics = dict(model_dump(mode="json"))
    # Identity and output-directory spellings are normalized separately. Other
    # FetchPaperRequest fields remain part of the complete fetch semantics.
    request_semantics.pop("query", None)
    request_semantics.pop("markdown_output_dir", None)
    fingerprint = semantic_singleflight_fingerprint(
        {
            "fetch": request_semantics,
            "capability_scope": capability_scope,
            "cache_dir": _canonical_directory(cache_dir),
            "markdown_dir": _canonical_directory(markdown_dir),
        }
    )
    return canonical_doi, fingerprint


FETCH_ENVELOPE_SINGLEFLIGHT: RequestSingleFlight[object] = RequestSingleFlight()


__all__ = [
    "FETCH_ENVELOPE_SINGLEFLIGHT",
    "RequestSingleFlight",
    "fetch_request_singleflight_key",
    "semantic_singleflight_fingerprint",
]
