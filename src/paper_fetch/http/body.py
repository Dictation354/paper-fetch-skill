"""HTTP response body and textual content helpers."""

from __future__ import annotations

import gzip
import io
import re
from typing import Any

from .cache import redact_url_for_cache
from .errors import RequestFailure

DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER = 8
TEXTUAL_CONTENT_TYPES = (
    "text/",
    "application/xml",
    "text/xml",
    "application/json",
    "application/jats+xml",
)


class BodyMixin:
    """Private body reading methods mixed into ``HttpTransport``."""

    def _read_response_body(
        self,
        response: Any,
        *,
        status_code: int | None,
        url: str,
        content_encoding: str | None = None,
    ) -> bytes:
        normalized_content_encoding = normalize_content_encoding(content_encoding)
        if normalized_content_encoding == "gzip":
            max_compressed_body_bytes = max(
                self.max_response_bytes,
                self.max_response_bytes * DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER,
            )
            payload = self._read_raw_bytes(response, max_compressed_body_bytes + 1)
        else:
            payload = self._read_raw_bytes(response, self.max_response_bytes + 1)
        if not isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload or b"")
        body = bytes(payload)
        if normalized_content_encoding == "gzip":
            if len(body) > max_compressed_body_bytes:
                raise RequestFailure(
                    status_code,
                    (
                        f"Compressed response body exceeded {max_compressed_body_bytes} bytes "
                        f"for {redact_url_for_cache(url)}"
                    ),
                    body=body[:max_compressed_body_bytes],
                    url=redact_url_for_cache(url),
                )
            return decompress_gzip_body(
                body,
                status_code=status_code,
                url=url,
                max_response_bytes=self.max_response_bytes,
            )
        if len(body) > self.max_response_bytes:
            raise RequestFailure(
                status_code,
                f"Response body exceeded {self.max_response_bytes} bytes for {redact_url_for_cache(url)}",
                body=body[: self.max_response_bytes],
                url=redact_url_for_cache(url),
            )
        return body

    def _read_raw_bytes(self, response: Any, max_bytes: int) -> bytes:
        try:
            return response.read(max_bytes, decode_content=False, cache_content=False)
        except TypeError:
            return response.read(max_bytes)


def is_xml_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    return normalized in {"application/xml", "text/xml", "application/jats+xml"} or normalized.endswith("+xml")


def is_textual_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    if not normalized:
        return False
    return (
        any(normalized.startswith(prefix) or normalized == prefix for prefix in TEXTUAL_CONTENT_TYPES)
        or normalized.endswith("+xml")
        or normalized.endswith("+json")
    )


def build_text_preview(body: bytes, content_type: str | None) -> str | None:
    normalized = (content_type or "").split(";", 1)[0].lower()
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
        token.strip().lower()
        for token in str(value).split(",")
        if token.strip()
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
        )
    return decompressed
