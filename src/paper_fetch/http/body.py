"""HTTP response body reading, streaming, decompression, and preview helpers."""

from __future__ import annotations

import contextlib
import gzip
import io
import os
import re
import time
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    ASSET_CONTENT_ENCODING_UNSUPPORTED,
)
from .cache import redact_url_for_cache
from .content_types import (
    STRUCTURED_TEXT_MIME_TYPES,
    TEXTUAL_CONTENT_TYPES,
    content_type_base,
    is_textual_content_type,
    is_xml_content_type,
)
from .errors import RequestErrorCategory, RequestFailure

DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER = 8
STREAM_CHUNK_BYTES = 64 * 1024
STREAM_PREVIEW_BYTES = 8192


@dataclass(frozen=True)
class StreamedBodyStats:
    downloaded_bytes: int
    compressed_bytes: int
    body_preview: bytes
    elapsed_seconds: float


def _parsed_content_length(headers: Mapping[str, Any]) -> int | None:
    raw = next(
        (
            value
            for key, value in headers.items()
            if str(key).lower() == "content-length"
        ),
        None,
    )
    try:
        parsed = int(str(raw))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def read_raw_response_bytes(response: Any, max_bytes: int) -> bytes:
    """Read up to ``max_bytes`` from a pooled HTTP response without decoding."""

    try:
        raw = response.read(max_bytes, decode_content=False, cache_content=False)
    except TypeError:
        raw = response.read(max_bytes)
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    return bytes(raw or b"")


def read_bounded_response_body(
    response: Any,
    *,
    status_code: int | None,
    url: str,
    content_encoding: str | None = None,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_compressed_response_bytes: int | None = None,
    read_body: Callable[[int], bytes] | None = None,
) -> bytes:
    """Read and optionally gzip-decompress a response body within byte ceilings."""

    if read_body is None:

        def read_body(limit: int) -> bytes:
            return read_raw_response_bytes(response, limit)

    body_limit = max(0, int(max_response_bytes))
    normalized_encoding = normalize_content_encoding(content_encoding)
    if normalized_encoding == "gzip":
        compressed_limit = (
            max(body_limit, body_limit * DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER)
            if max_compressed_response_bytes is None
            else max(0, int(max_compressed_response_bytes))
        )
        body = read_body(compressed_limit + 1)
        if len(body) > compressed_limit:
            raise RequestFailure(
                status_code,
                (
                    f"Compressed response body exceeded {compressed_limit} bytes "
                    f"for {redact_url_for_cache(url)}"
                ),
                body=body[:compressed_limit],
                url=redact_url_for_cache(url),
                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
            )
        return decompress_gzip_body(
            body,
            status_code=status_code,
            url=url,
            max_response_bytes=body_limit,
        )

    body = read_body(body_limit + 1)
    if len(body) > body_limit:
        raise RequestFailure(
            status_code,
            f"Response body exceeded {body_limit} bytes for {redact_url_for_cache(url)}",
            body=body[:body_limit],
            url=redact_url_for_cache(url),
            error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
        )
    return body


def validate_stream_response_headers(
    headers: Mapping[str, str],
    *,
    status_code: int,
    response_url: str,
    response_limit: int,
    compressed_limit: int,
    on_content_length: Callable[[int | None], None] | None = None,
) -> str:
    declared_length = _parsed_content_length(headers)
    content_encoding = str(headers.get("content-encoding") or "").strip().lower()
    if content_encoding in {"", "identity"}:
        declared_limit = response_limit
    elif content_encoding == "gzip":
        declared_limit = compressed_limit
    else:
        raise RequestFailure(
            status_code,
            f"asset_content_encoding_unsupported: {content_encoding}",
            headers=headers,
            url=redact_url_for_cache(response_url),
            error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
            reason_code=ASSET_CONTENT_ENCODING_UNSUPPORTED,
        )
    if on_content_length is not None:
        on_content_length(
            declared_length if content_encoding in {"", "identity"} else None
        )
    if declared_length is not None and declared_length > declared_limit:
        raise RequestFailure(
            status_code,
            (
                f"Response Content-Length exceeded {declared_limit} bytes "
                f"for {redact_url_for_cache(response_url)}"
            ),
            headers=headers,
            url=redact_url_for_cache(response_url),
            error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
            reason_code=ASSET_BYTES_PER_ASSET_EXCEEDED,
        )
    return content_encoding


def stream_bounded_response_to_file(
    destination: Path,
    *,
    request_url: str,
    response_url: str,
    status_code: int,
    headers_map: Mapping[str, str],
    response_limit: int,
    compressed_limit: int,
    read_chunk: Callable[[int], bytes],
    on_content_length: Callable[[int | None], None] | None = None,
    on_chunk: Callable[[int], None] | None = None,
) -> StreamedBodyStats:
    """Stream and optionally gunzip a pooled response into an exclusive file."""

    content_encoding = validate_stream_response_headers(
        headers_map,
        status_code=status_code,
        response_url=response_url,
        response_limit=response_limit,
        compressed_limit=compressed_limit,
        on_content_length=on_content_length,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    preview = bytearray()
    written = 0
    compressed_read = 0
    decompressor = (
        zlib.decompressobj(16 + zlib.MAX_WBITS) if content_encoding == "gzip" else None
    )

    def write_chunk(stream: Any, chunk: bytes) -> None:
        nonlocal written
        if not chunk:
            return
        if on_chunk is not None:
            on_chunk(len(chunk))
        if written + len(chunk) > response_limit:
            raise RequestFailure(
                status_code,
                (
                    f"Response body exceeded {response_limit} bytes for "
                    f"{redact_url_for_cache(response_url)}"
                ),
                headers=headers_map,
                url=redact_url_for_cache(response_url),
                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
                reason_code=ASSET_BYTES_PER_ASSET_EXCEEDED,
            )
        stream.write(chunk)
        written += len(chunk)
        if len(preview) < STREAM_PREVIEW_BYTES:
            preview.extend(chunk[: STREAM_PREVIEW_BYTES - len(preview)])

    destination_created = False
    completed = False
    started_at = time.monotonic()
    try:
        with destination.open("xb") as stream:
            destination_created = True
            while True:
                raw_bytes = read_chunk(STREAM_CHUNK_BYTES)
                if not raw_bytes:
                    break
                compressed_read += len(raw_bytes)
                if compressed_read > compressed_limit:
                    raise RequestFailure(
                        status_code,
                        (
                            "Compressed response body exceeded "
                            f"{compressed_limit} bytes for "
                            f"{redact_url_for_cache(response_url)}"
                        ),
                        headers=headers_map,
                        url=redact_url_for_cache(response_url),
                        error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
                        reason_code=ASSET_BYTES_PER_ASSET_EXCEEDED,
                    )
                if decompressor is None:
                    write_chunk(stream, raw_bytes)
                    continue
                pending = raw_bytes
                while pending:
                    expanded = decompressor.decompress(pending, STREAM_CHUNK_BYTES)
                    write_chunk(stream, expanded)
                    pending = decompressor.unconsumed_tail
            if decompressor is not None:
                write_chunk(stream, decompressor.flush(STREAM_CHUNK_BYTES))
                if not decompressor.eof:
                    raise RequestFailure(
                        status_code,
                        f"Truncated gzip response for {redact_url_for_cache(response_url)}",
                        headers=headers_map,
                        url=redact_url_for_cache(response_url),
                        error_category=RequestErrorCategory.NETWORK_ERROR,
                    )
                if decompressor.unused_data:
                    raise RequestFailure(
                        status_code,
                        f"Trailing gzip response data for {redact_url_for_cache(response_url)}",
                        headers=headers_map,
                        url=redact_url_for_cache(response_url),
                        error_category=RequestErrorCategory.NETWORK_ERROR,
                    )
            stream.flush()
            os.fsync(stream.fileno())
        completed = True
    except zlib.error as exc:
        raise RequestFailure(
            None,
            f"Invalid gzip response for {redact_url_for_cache(request_url)}: {exc}",
            url=redact_url_for_cache(request_url),
            error_category=RequestErrorCategory.NETWORK_ERROR,
        ) from exc
    finally:
        if destination_created and not completed:
            with contextlib.suppress(OSError):
                destination.unlink(missing_ok=True)

    return StreamedBodyStats(
        downloaded_bytes=written,
        compressed_bytes=compressed_read,
        body_preview=bytes(preview),
        elapsed_seconds=max(0.0, time.monotonic() - started_at),
    )


def build_text_preview(body: bytes, content_type: str | None) -> str | None:
    normalized = content_type_base(content_type)
    if normalized and not is_textual_content_type(normalized):
        return None
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500] or None


def normalize_content_encoding(value: str | None) -> str:
    if not value:
        return ""
    return ",".join(
        token.strip().lower() for token in str(value).split(",") if token.strip()
    )


def decompress_gzip_body(
    body: bytes,
    *,
    status_code: int | None,
    url: str,
    max_response_bytes: int,
) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as gzip_file:
            decompressed = gzip_file.read(max_response_bytes + 1)
    except OSError as exc:
        raise RequestFailure(
            status_code,
            f"Unable to decompress gzip response for {redact_url_for_cache(url)}: {exc}",
            body=body[:max_response_bytes],
            url=redact_url_for_cache(url),
        ) from exc
    if len(decompressed) > max_response_bytes:
        raise RequestFailure(
            status_code,
            f"Response body exceeded {max_response_bytes} bytes for {redact_url_for_cache(url)}",
            body=decompressed[:max_response_bytes],
            url=redact_url_for_cache(url),
            error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
        )
    return decompressed


__all__ = [
    "DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "STREAM_CHUNK_BYTES",
    "STREAM_PREVIEW_BYTES",
    "STRUCTURED_TEXT_MIME_TYPES",
    "TEXTUAL_CONTENT_TYPES",
    "StreamedBodyStats",
    "build_text_preview",
    "decompress_gzip_body",
    "is_textual_content_type",
    "is_xml_content_type",
    "normalize_content_encoding",
    "read_bounded_response_body",
    "read_raw_response_bytes",
    "stream_bounded_response_to_file",
    "validate_stream_response_headers",
]
