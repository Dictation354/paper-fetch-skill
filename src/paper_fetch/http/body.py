"""HTTP response body and textual content helpers."""

from __future__ import annotations

import gzip
import io
import re
from typing import Any

from .cache import redact_url_for_cache
from .content_types import STRUCTURED_TEXT_MIME_TYPES, content_type_base
from .errors import RequestErrorCategory, RequestFailure

DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER = 8
TEXTUAL_CONTENT_TYPES = (
    "text/",
    *STRUCTURED_TEXT_MIME_TYPES,
    "text/xml",
)


class BodyMixin:
    """Private body reading methods mixed into ``HttpTransport``."""

    max_response_bytes: int

    def _read_response_body(
        self,
        response: Any,
        *,
        status_code: int | None,
        url: str,
        content_encoding: str | None = None,
        max_response_bytes: int | None = None,
        max_compressed_response_bytes: int | None = None,
    ) -> bytes:
        body_limit = (
            self.max_response_bytes
            if max_response_bytes is None
            else max(0, int(max_response_bytes))
        )
        normalized_content_encoding = normalize_content_encoding(content_encoding)
        if normalized_content_encoding == "gzip":
            compressed_limit = (
                max(
                    body_limit,
                    body_limit * DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER,
                )
                if max_compressed_response_bytes is None
                else max(0, int(max_compressed_response_bytes))
            )
            payload = self._read_raw_bytes(response, compressed_limit + 1)
        else:
            payload = self._read_raw_bytes(response, body_limit + 1)
        if not isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload or b"")
        body = bytes(payload)
        if normalized_content_encoding == "gzip":
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
        if len(body) > body_limit:
            raise RequestFailure(
                status_code,
                f"Response body exceeded {body_limit} bytes for {redact_url_for_cache(url)}",
                body=body[:body_limit],
                url=redact_url_for_cache(url),
                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
            )
        return body

    def _read_raw_bytes(self, response: Any, max_bytes: int) -> bytes:
        try:
            return response.read(max_bytes, decode_content=False, cache_content=False)
        except TypeError:
            return response.read(max_bytes)


def is_xml_content_type(content_type: str | None) -> bool:
    normalized = content_type_base(content_type)
    return normalized in {
        "application/xml",
        "text/xml",
        "application/jats+xml",
    } or normalized.endswith("+xml")


def is_textual_content_type(content_type: str | None) -> bool:
    normalized = content_type_base(content_type)
    if not normalized:
        return False
    return (
        any(
            normalized.startswith(prefix) or normalized == prefix
            for prefix in TEXTUAL_CONTENT_TYPES
        )
        or normalized.endswith("+xml")
        or normalized.endswith("+json")
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
