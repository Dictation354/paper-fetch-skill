"""Instance-owned, byte-bounded snapshots for paged MCP reading."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import re
import threading
import time
from typing import Any
from uuid import uuid4

from cachetools import TLRUCache

from .results import _tool_result, error_payload_from_exception, with_schema_version
from .schemas import ReadContentRequest, NavigateContentRequest

CONTENT_IDLE_TTL_SECONDS = 24 * 60 * 60
CONTENT_STORE_MAX_BYTES = 256 * 1024 * 1024
CONTENT_STORE_CAPACITY_EXCEEDED = "content_store_capacity_exceeded"


@dataclass(frozen=True)
class ContentSnapshot:
    views: Mapping[str, str]
    render_truncated: bool = False

    @property
    def size(self) -> int:
        return sum(len(value.encode("utf-8")) for value in self.views.values())


class ContentStore:
    """Serialize access, refresh idle expiry on reads, and evict old LRU entries."""

    def __init__(
        self,
        *,
        max_bytes: int = CONTENT_STORE_MAX_BYTES,
        idle_ttl: float = CONTENT_IDLE_TTL_SECONDS,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        self.idle_ttl = idle_ttl
        self._lock = threading.RLock()
        self._cache: TLRUCache[str, ContentSnapshot] = TLRUCache(
            maxsize=max_bytes,
            ttu=lambda _key, _value, now: now + idle_ttl,
            timer=timer,
            getsizeof=lambda value: value.size,
        )

    def register_many(
        self, snapshots: Sequence[ContentSnapshot]
    ) -> list[dict[str, Any] | None]:
        """Admit a request atomically; never evict a snapshot from this request."""
        refs: list[dict[str, Any] | None] = []
        with self._lock:
            remaining = self._cache.maxsize
            admitted: list[tuple[str, ContentSnapshot]] = []
            for snapshot in snapshots:
                # Take an immutable-in-practice copy of the caller's mapping.
                snapshot = ContentSnapshot(
                    dict(snapshot.views), snapshot.render_truncated
                )
                if snapshot.size > remaining:
                    refs.append(None)
                    continue
                remaining -= snapshot.size
                content_id = uuid4().hex
                admitted.append((content_id, snapshot))
                refs.append(
                    {
                        "content_id": content_id,
                        "views": {
                            view: {"total_chars": len(value)}
                            for view, value in snapshot.views.items()
                        },
                        "idle_ttl_seconds": self.idle_ttl,
                        "render_truncated": snapshot.render_truncated,
                    }
                )
            # Total admitted size is <= maxsize, so only older requests can be evicted.
            for content_id, snapshot in admitted:
                self._cache[content_id] = snapshot
        return refs

    def read(self, request: ReadContentRequest) -> dict[str, Any]:
        with self._lock:
            snapshot = self._cache.get(request.content_id)
            if snapshot is None:
                return self._error(
                    "content_handle_expired",
                    "Content handle is expired, evicted, or unknown.",
                )
            # Any access to a valid handle refreshes its idle lifetime.
            del self._cache[request.content_id]
            self._cache[request.content_id] = snapshot
            value = snapshot.views.get(request.view)
            if value is None:
                return self._error(
                    "content_view_unavailable",
                    "This representation was not retained for the handle.",
                )
            if request.offset > len(value):
                return self._error(
                    "content_range_out_of_bounds", "offset exceeds total_chars."
                )
            text = value[request.offset : request.offset + request.max_chars]
            end = request.offset + len(text)
            return with_schema_version(
                {
                    "status": "ok",
                    "content_id": request.content_id,
                    "view": request.view,
                    "text": text,
                    "offset": request.offset,
                    "returned_chars": len(text),
                    "total_chars": len(value),
                    "next_offset": end,
                    "eof": end == len(value),
                    "render_truncated": snapshot.render_truncated,
                }
            )

    def navigate(self, request: NavigateContentRequest) -> dict[str, Any]:
        # Read through the same owner to preserve TTL, capacity and error semantics.
        page = self.read(
            ReadContentRequest(
                content_id=request.content_id,
                offset=request.offset,
                max_chars=1,
            )
        )
        if page["status"] != "ok":
            return page
        with self._lock:
            snapshot = self._cache.get(request.content_id)
            if snapshot is None:
                return self._error(
                    "content_handle_expired",
                    "Content handle is expired, evicted, or unknown.",
                )
            markdown = snapshot.views["markdown"]
        if request.mode == "headings":
            from ..markdown.math import markdown_code_spans

            code = list(markdown_code_spans(markdown))
            headings = [
                m
                for m in re.finditer(
                    r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$",
                    markdown,
                    re.M,
                )
                if not any(start <= m.start() < end for start, end in code)
            ]
            entries = []
            for index, match in enumerate(headings):
                if match.start() < request.offset:
                    continue
                section_end = next(
                    (
                        other.start()
                        for other in headings[index + 1 :]
                        if len(other[1]) <= len(match[1])
                    ),
                    len(markdown),
                )
                entries.append(
                    {
                        "title": match[2],
                        "level": len(match[1]),
                        "start": match.start(),
                        "end": match.end(),
                        "section_start": match.start(),
                        "section_end": section_end,
                    }
                )
                if len(entries) > request.max_results:
                    break
        else:
            # Regex IGNORECASE retains original offsets even for Unicode case pairs.
            entries = []
            for match in re.finditer(
                re.escape(request.query or ""), markdown[request.offset :], re.I
            ):
                start, end = (
                    request.offset + match.start(),
                    request.offset + match.end(),
                )
                context_start = max(0, start - request.context_chars)
                context_end = min(len(markdown), end + request.context_chars)
                entries.append(
                    {
                        "start": start,
                        "end": end,
                        "context_start": context_start,
                        "context_end": context_end,
                        "context": markdown[context_start:context_end],
                    }
                )
                if len(entries) > request.max_results:
                    break
        more = len(entries) > request.max_results
        returned = entries[: request.max_results]
        next_offset = entries[-1]["start"] if more else len(markdown)
        return with_schema_version(
            {
                "status": "ok",
                "content_id": request.content_id,
                "mode": request.mode,
                "results": returned,
                "offset": request.offset,
                "total_chars": len(markdown),
                "next_offset": next_offset,
                "eof": not more,
                "render_truncated": snapshot.render_truncated,
            }
        )

    @staticmethod
    def _error(code: str, reason: str) -> dict[str, Any]:
        return with_schema_version(
            {"status": "error", "code": code, "reason": reason, "retryable": False}
        )


DEFAULT_CONTENT_STORE = ContentStore()


def read_content_tool(store: ContentStore, **arguments: Any):
    try:
        payload = store.read(ReadContentRequest.model_validate(arguments))
    except Exception as error:
        payload = error_payload_from_exception(error)
    return _tool_result(payload, is_error=payload["status"] != "ok")


def json_view(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def navigate_content_tool(store: ContentStore, **arguments: Any):
    try:
        payload = store.navigate(NavigateContentRequest.model_validate(arguments))
    except Exception as error:
        payload = error_payload_from_exception(error)
    return _tool_result(payload, is_error=payload["status"] != "ok")
