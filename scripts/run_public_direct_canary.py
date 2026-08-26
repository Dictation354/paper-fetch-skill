#!/usr/bin/env python3
"""Run the explicitly enabled, public direct-route provider canary."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paper_fetch.logging_utils import redact_log_value  # noqa: E402
from paper_fetch.models import FetchEnvelope  # noqa: E402
from paper_fetch.provider_catalog import provider_route  # noqa: E402
from paper_fetch.runtime import RuntimeContext  # noqa: E402
from paper_fetch.service import FetchStrategy, fetch_paper  # noqa: E402
from paper_fetch.utils import normalize_text  # noqa: E402


RUN_CANARY_ENV_VAR = "PAPER_FETCH_RUN_PUBLIC_CANARY"
DEFAULT_CONFIG = REPO_ROOT / "quality" / "public-direct-canary.json"
CanaryRunner = Callable[[Mapping[str, str]], Mapping[str, Any]]


def _required_text(item: Mapping[str, Any], key: str, *, index: int) -> str:
    value = normalize_text(item.get(key))
    if not value:
        raise ValueError(f"routes[{index}].{key} must be a non-empty string")
    return value


def load_canary_routes(path: Path = DEFAULT_CONFIG) -> tuple[dict[str, str], ...]:
    """Load and catalog-validate public routes without making network requests."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("public direct canary schema_version must be 1")
    raw_routes = payload.get("routes")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise ValueError("public direct canary routes must be a non-empty list")

    routes: list[dict[str, str]] = []
    seen: set[str] = set()
    required = {
        "provider",
        "route",
        "doi",
        "expected_source",
        "expected_trail_marker",
    }
    for index, raw_item in enumerate(raw_routes):
        if not isinstance(raw_item, dict) or set(raw_item) != required:
            raise ValueError(f"routes[{index}] must contain exactly {sorted(required)}")
        item = {key: _required_text(raw_item, key, index=index) for key in required}
        item["provider"] = item["provider"].lower()
        item["route"] = item["route"].lower()
        key = f"{item['provider']}:{item['route']}"
        if key in seen:
            raise ValueError(f"duplicate public direct canary route: {key}")
        seen.add(key)

        route = provider_route(item["provider"], item["route"])
        if route is None:
            raise ValueError(f"unknown provider route: {key}")
        if (
            route.implementation_status != "available"
            or route.transport != "http"
            or route.browser_required
            or route.browser_optional
            or route.browser_preflight
            or route.auth_supported
        ):
            raise ValueError(f"canary route is not public/direct/available: {key}")
        if route.source != item["expected_source"]:
            raise ValueError(
                f"{key} expected_source must match catalog source {route.source!r}"
            )
        routes.append(item)
    return tuple(routes)


def live_canary_runner(item: Mapping[str, str]) -> Mapping[str, Any]:
    """Fetch one public sample with an empty capability environment."""

    with RuntimeContext(env={}, artifact_mode="none") as context:
        envelope = fetch_paper(
            item["doi"],
            modes={"article"},
            strategy=FetchStrategy(
                allow_metadata_only_fallback=False,
                preferred_providers=[item["provider"]],
                asset_profile="none",
            ),
            context=context,
        )
    return classify_canary_envelope(item, envelope)


def classify_canary_envelope(
    item: Mapping[str, str], envelope: FetchEnvelope
) -> dict[str, Any]:
    acquisition = envelope.acquisition
    route_matches = bool(
        acquisition is not None
        and acquisition.provider == item["provider"]
        and acquisition.route == item["route"]
        and acquisition.transport == "http"
    )
    source_matches = envelope.source == item["expected_source"]
    marker_matches = item["expected_trail_marker"] in envelope.source_trail
    passed = bool(
        envelope.has_fulltext and route_matches and source_matches and marker_matches
    )
    failed_checks = [
        label
        for label, matched in (
            ("fulltext", envelope.has_fulltext),
            ("route", route_matches),
            ("source", source_matches),
            ("trail_marker", marker_matches),
        )
        if not matched
    ]
    return {
        "passed": passed,
        "reason": "ok" if passed else "contract_mismatch:" + ",".join(failed_checks),
        "source": envelope.source,
        "content_kind": envelope.content_kind,
        "acquisition": (
            {
                "provider": acquisition.provider,
                "route": acquisition.route,
                "representation": acquisition.representation,
                "transport": acquisition.transport,
            }
            if acquisition is not None
            else None
        ),
    }


def run_canary(
    routes: Sequence[Mapping[str, str]],
    *,
    runner: CanaryRunner = live_canary_runner,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for item in routes:
        key = f"{item['provider']}:{item['route']}"
        try:
            outcome = dict(runner(item))
            passed = outcome.get("passed") is True
            result = {
                "key": key,
                "provider": item["provider"],
                "route": item["route"],
                "doi": item["doi"],
                **outcome,
                "passed": passed,
            }
        except Exception as exc:
            result = {
                "key": key,
                "provider": item["provider"],
                "route": item["route"],
                "doi": item["doi"],
                "passed": False,
                "reason": type(exc).__name__,
                "error": redact_log_value(str(exc), key="error"),
            }
        results.append(result)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "results": results,
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if os.environ.get(RUN_CANARY_ENV_VAR) != "1":
        raise SystemExit(
            f"live public canary is disabled; set {RUN_CANARY_ENV_VAR}=1 explicitly"
        )
    routes = load_canary_routes(args.config)
    write_report(args.output, run_canary(routes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
