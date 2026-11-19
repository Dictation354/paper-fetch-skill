"""HTTP retry policy builders and attempt decision state."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Literal, TypeAlias

from urllib3.util import Retry

from ..logging_utils import emit_structured_log
from .cache import redact_url_for_cache
from .errors import (
    RequestFailure,
    build_http_error_message,
    build_network_error_detail,
    classify_network_error,
    is_retryable_network_error,
)

DEFAULT_TRANSIENT_RETRIES = 2
DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS = 0.5
TRANSIENT_HTTP_STATUS_CODES = frozenset(range(500, 600))
logger = logging.getLogger("paper_fetch.http")

RetryDecisionKind: TypeAlias = Literal[
    "rate_limit",
    "transient_http",
    "transient_network",
]


@dataclass(frozen=True)
class RetryDecision:
    """Action returned when a failed attempt should be retried."""

    kind: RetryDecisionKind
    wait_seconds: float


def build_rate_limit_retry_policy(*, enabled: bool, retries: int) -> Retry:
    total = max(0, int(retries)) if enabled else 0
    return Retry(
        total=total,
        status=total,
        allowed_methods=frozenset({"GET", "HEAD"}),
        status_forcelist={429},
        respect_retry_after_header=True,
        raise_on_status=False,
    )


def build_transient_retry_policy(
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
        allowed_methods=frozenset({"GET", "HEAD"}),
        status_forcelist=TRANSIENT_HTTP_STATUS_CODES,
        backoff_factor=max(0.0, float(backoff_base_seconds)),
        respect_retry_after_header=False,
        raise_on_status=False,
    )


def _retry_remaining(policy: Retry) -> int:
    return max(0, int(policy.total or 0))


def _consume_retry(policy: Retry) -> Retry:
    return policy.new(total=max(0, _retry_remaining(policy) - 1))


def _transient_backoff_seconds(policy: Retry, attempts_made: int) -> float:
    return max(0.0, float(policy.backoff_factor)) * (2**attempts_made)


@dataclass
class RetryState:
    """Mutable per-request retry budget decoupled from transport locks."""

    rate_limit_policy: Retry
    transient_policy: Retry
    max_rate_limit_wait_seconds: int
    body_access_provider: str | None = None
    transient_attempts_made: int = 0

    def decide_network_error(
        self,
        *,
        method: str,
        request_url: str,
        exc: Exception,
        started_at: float,
        attempt: int,
        is_timeout: bool = False,
        emit_logs: bool = True,
    ) -> RetryDecision:
        redacted_url = redact_url_for_cache(request_url)
        retryable = method.upper() in {"GET", "HEAD"} and (
            _retry_remaining(self.transient_policy) > 0
            and (is_timeout or is_retryable_network_error(exc))
        )
        if retryable:
            if emit_logs:
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "http_request_retry",
                    method=method.upper(),
                    url=redacted_url,
                    status=None,
                    elapsed_ms=round((time.monotonic() - started_at) * 1000, 3),
                    retry_after_seconds=None,
                    attempt=attempt,
                    reason="timeout" if is_timeout else "pool_timeout",
                )
            self.transient_policy = _consume_retry(self.transient_policy)
            wait_seconds = _transient_backoff_seconds(
                self.transient_policy,
                self.transient_attempts_made,
            )
            self.transient_attempts_made += 1
            return RetryDecision(kind="transient_network", wait_seconds=wait_seconds)

        if emit_logs:
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_failure",
                method=method.upper(),
                url=redacted_url,
                status=None,
                elapsed_ms=round((time.monotonic() - started_at) * 1000, 3),
                retry_after_seconds=None,
                attempt=attempt,
            )
        detail = str(exc) if is_timeout else build_network_error_detail(exc)
        raise RequestFailure(
            None,
            f"Network error for {redacted_url}: {detail}",
            url=redacted_url,
            error_category=classify_network_error(exc),
        ) from exc

    def decide_http_failure(
        self,
        *,
        method: str,
        request_url: str,
        error_url: str,
        status_code: int,
        body: bytes,
        headers_map: Mapping[str, str],
        started_at: float,
        attempt: int,
    ) -> RetryDecision:
        # Only article retrieval routes participate in the access boundary.
        # Asset/metadata failures and unscoped requests retain their retry policy.
        if self.body_access_provider is not None:
            from ..quality.access_boundary import (
                raise_for_api_entitlement,
                raise_for_paywall,
            )

            raise_for_api_entitlement(
                body,
                source_url=request_url,
                provider=self.body_access_provider,
                headers=headers_map,
            )
            raise_for_paywall(
                body,
                source_url=error_url or request_url,
                provider=self.body_access_provider,
            )

        retry_after_seconds = parse_retry_after_seconds(headers_map.get("retry-after"))
        rate_limit_wait_seconds: float | None = retry_after_seconds
        if rate_limit_wait_seconds is None:
            fallback_wait_seconds = max(
                0.0, float(self.transient_policy.backoff_factor)
            )
            if fallback_wait_seconds <= self.max_rate_limit_wait_seconds:
                rate_limit_wait_seconds = fallback_wait_seconds

        redacted_error_url = redact_url_for_cache(error_url)
        if (
            status_code == 429
            and _retry_remaining(self.rate_limit_policy) > 0
            and self.rate_limit_policy.is_retry(
                method.upper(), status_code, retry_after_seconds is not None
            )
            and rate_limit_wait_seconds is not None
            and rate_limit_wait_seconds <= self.max_rate_limit_wait_seconds
        ):
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_retry",
                method=method.upper(),
                url=redacted_error_url,
                status=status_code,
                elapsed_ms=round((time.monotonic() - started_at) * 1000, 3),
                retry_after_seconds=retry_after_seconds,
                attempt=attempt,
                reason="rate_limit",
            )
            self.rate_limit_policy = _consume_retry(self.rate_limit_policy)
            return RetryDecision(
                kind="rate_limit",
                wait_seconds=max(0.0, rate_limit_wait_seconds),
            )

        if _retry_remaining(
            self.transient_policy
        ) > 0 and self.transient_policy.is_retry(
            method.upper(), status_code, retry_after_seconds is not None
        ):
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_retry",
                method=method.upper(),
                url=redacted_error_url,
                status=status_code,
                elapsed_ms=round((time.monotonic() - started_at) * 1000, 3),
                retry_after_seconds=retry_after_seconds,
                attempt=attempt,
                reason="transient_http",
            )
            self.transient_policy = _consume_retry(self.transient_policy)
            wait_seconds = _transient_backoff_seconds(
                self.transient_policy,
                self.transient_attempts_made,
            )
            self.transient_attempts_made += 1
            return RetryDecision(kind="transient_http", wait_seconds=wait_seconds)

        emit_structured_log(
            logger,
            logging.DEBUG,
            "http_request_failure",
            method=method.upper(),
            url=redacted_error_url,
            status=status_code,
            elapsed_ms=round((time.monotonic() - started_at) * 1000, 3),
            retry_after_seconds=retry_after_seconds,
            attempt=attempt,
        )
        raise RequestFailure(
            status_code,
            build_http_error_message(
                status_code, request_url, retry_after_seconds=retry_after_seconds
            ),
            body=body,
            headers=headers_map,
            url=redacted_error_url,
            retry_after_seconds=retry_after_seconds,
        )


def parse_retry_after_seconds(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return max(0, int(float(normalized)))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    delta = (parsed - datetime.now(UTC)).total_seconds()
    return max(0, int(delta))


def is_transient_http_status(status_code: int | None) -> bool:
    return status_code is not None and 500 <= status_code < 600


__all__ = [
    "DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS",
    "DEFAULT_TRANSIENT_RETRIES",
    "TRANSIENT_HTTP_STATUS_CODES",
    "RetryDecision",
    "RetryState",
    "build_rate_limit_retry_policy",
    "build_transient_retry_policy",
    "is_transient_http_status",
    "parse_retry_after_seconds",
]
