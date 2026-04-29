"""HTTP retry policy helpers."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Mapping

from urllib3.util import Retry

from ..logging_utils import emit_structured_log
from .cache import redact_url_for_cache
from .errors import RequestFailure, build_http_error_message

DEFAULT_TRANSIENT_RETRIES = 2
DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS = 0.5
TRANSIENT_HTTP_STATUS_CODES = frozenset(range(500, 600))
logger = logging.getLogger("paper_fetch.http")


class RetryMixin:
    """Private retry methods mixed into ``HttpTransport``."""

    def _build_rate_limit_retry_policy(
        self,
        *,
        enabled: bool,
        retries: int,
    ) -> Retry:
        total = max(0, int(retries)) if enabled else 0
        return Retry(
            total=total,
            status=total,
            allowed_methods=None,
            status_forcelist={429},
            respect_retry_after_header=True,
            raise_on_status=False,
        )

    def _build_transient_retry_policy(
        self,
        *,
        enabled: bool,
        retries: int,
        backoff_base_seconds: float,
    ) -> Retry:
        total = max(0, int(retries)) if enabled else 0
        return Retry(
            total=total,
            connect=total,
            read=total,
            status=total,
            other=total,
            allowed_methods=None,
            status_forcelist=TRANSIENT_HTTP_STATUS_CODES,
            backoff_factor=max(0.0, float(backoff_base_seconds)),
            respect_retry_after_header=False,
            raise_on_status=False,
        )

    def _retry_remaining(self, policy: Retry) -> int:
        return max(0, int(policy.total or 0))

    def _consume_retry(self, policy: Retry) -> Retry:
        return policy.new(total=max(0, self._retry_remaining(policy) - 1))

    def _transient_backoff_seconds(self, policy: Retry, attempts_made: int) -> float:
        return max(0.0, float(policy.backoff_factor)) * (2**attempts_made)

    def _handle_http_failure(
        self,
        *,
        method: str,
        request_url: str,
        error_url: str,
        status_code: int,
        body: bytes,
        headers_map: Mapping[str, str],
        request_started_at: float,
        attempt: int,
        rate_limit_policy: Retry,
        max_rate_limit_wait_seconds: int,
        transient_policy: Retry,
        transient_attempts_made: int,
    ) -> tuple[bool, Retry, Retry, int]:
        retry_after_seconds = parse_retry_after_seconds(headers_map.get("retry-after"))
        rate_limit_wait_seconds = retry_after_seconds
        if rate_limit_wait_seconds is None:
            fallback_wait_seconds = max(0.0, float(transient_policy.backoff_factor))
            if fallback_wait_seconds <= max_rate_limit_wait_seconds:
                rate_limit_wait_seconds = fallback_wait_seconds
        if (
            status_code == 429
            and self._retry_remaining(rate_limit_policy) > 0
            and rate_limit_policy.is_retry(method.upper(), status_code, retry_after_seconds is not None)
            and rate_limit_wait_seconds is not None
            and rate_limit_wait_seconds <= max_rate_limit_wait_seconds
        ):
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_retry",
                method=method.upper(),
                url=redact_url_for_cache(error_url),
                status=status_code,
                elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                retry_after_seconds=retry_after_seconds,
                attempt=attempt,
                reason="rate_limit",
            )
            rate_limit_policy = self._consume_retry(rate_limit_policy)
            time.sleep(max(0.0, rate_limit_wait_seconds))
            return True, rate_limit_policy, transient_policy, transient_attempts_made
        if (
            self._retry_remaining(transient_policy) > 0
            and transient_policy.is_retry(method.upper(), status_code, retry_after_seconds is not None)
        ):
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_retry",
                method=method.upper(),
                url=redact_url_for_cache(error_url),
                status=status_code,
                elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                retry_after_seconds=retry_after_seconds,
                attempt=attempt,
                reason="transient_http",
            )
            transient_policy = self._consume_retry(transient_policy)
            time.sleep(self._transient_backoff_seconds(transient_policy, transient_attempts_made))
            transient_attempts_made += 1
            return True, rate_limit_policy, transient_policy, transient_attempts_made
        emit_structured_log(
            logger,
            logging.DEBUG,
            "http_request_failure",
            method=method.upper(),
            url=redact_url_for_cache(error_url),
            status=status_code,
            elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
            retry_after_seconds=retry_after_seconds,
            attempt=attempt,
        )
        raise RequestFailure(
            status_code,
            build_http_error_message(status_code, request_url, retry_after_seconds=retry_after_seconds),
            body=body,
            headers=headers_map,
            url=redact_url_for_cache(error_url),
            retry_after_seconds=retry_after_seconds,
        )


def parse_retry_after_seconds(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return max(0, int(normalized))
    try:
        parsed = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = (parsed - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(delta))


def is_transient_http_status(status_code: int | None) -> bool:
    return status_code is not None and 500 <= status_code < 600
