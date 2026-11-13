"""Response-only handle presentation; acquisition and persistent caches stay unchanged."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
import re
from typing import Any

from ..markdown.math import markdown_code_spans, markdown_math_spans
from ..models import FetchEnvelope, TRUNCATION_WARNING
from ..workflow.acceptance import evaluate_fetch_acceptance
from ..workflow.types import effective_asset_profile
from .acceptance_payloads import expected_doi_from_query
from .content_store import (
    CONTENT_STORE_CAPACITY_EXCEEDED,
    ContentSnapshot,
    ContentStore,
    json_view,
)
from .schemas import FetchPaperRequest


def formula_locations(
    markdown: str, diagnostics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Locate exact complete math payloads without interpreting or rewriting TeX."""
    spans = list(markdown_math_spans(markdown))
    code_spans = list(markdown_code_spans(markdown))
    headings = [
        heading
        for heading in re.finditer(r"^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", markdown, re.M)
        if not any(start <= heading.start() < end for start, end in code_spans)
    ]
    locations = []
    for index, diagnostic in enumerate(diagnostics):
        latex = diagnostic.get("final_latex")
        candidates = []
        if isinstance(latex, str) and latex.strip():
            for start, end, expression in spans:
                if expression.strip() != latex.strip():
                    continue
                section = next(
                    (
                        heading[1]
                        for heading in reversed(headings)
                        if heading.start() < start
                    ),
                    None,
                )
                candidates.append({"start": start, "end": end, "section": section})
        locations.append(
            {
                "diagnostic_index": index,
                "node_id": diagnostic.get("node_id"),
                "status": "located"
                if len(candidates) == 1
                else "ambiguous"
                if candidates
                else "unlocated",
                "candidates": candidates,
            }
        )
    return locations


def content_snapshot(
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    *,
    acceptance: Any = None,
    response_warnings: list[str] | None = None,
) -> ContentSnapshot:
    payload = envelope.to_dict()
    views: dict[str, str] = {}
    if "markdown" in request.requested_modes() and envelope.markdown is not None:
        views["markdown"] = envelope.markdown
    if "article" in request.requested_modes() and envelope.article is not None:
        views["article"] = json_view(envelope.article.to_dict())
    quality = (
        envelope.article.quality if envelope.article is not None else envelope.quality
    )
    diagnostics = {
        key: value
        for key, value in payload.items()
        if key not in {"article", "markdown"}
    }
    diagnostics["response_warnings"] = list(response_warnings or [])
    diagnostics["acceptance"] = acceptance or evaluate_fetch_acceptance(
        envelope,
        asset_profile=effective_asset_profile(
            request.strategy.asset_profile, source_name=envelope.source
        ),
        requested_outputs=request.requested_modes(),
        expected_doi=expected_doi_from_query(request.query),
        require_local_body_assets=request.strategy.require_local_body_assets,
        require_full_size_body_assets=request.strategy.require_full_size_body_assets,
    ).model_dump(mode="json")
    diagnostics["formula_locations"] = formula_locations(
        envelope.markdown or "", quality.semantic_losses.formula_diagnostics
    )
    warnings = [*envelope.quality.warnings, *quality.warnings]
    truncated = TRUNCATION_WARNING in warnings
    diagnostics["render_truncated"] = truncated
    views["diagnostics"] = json_view(diagnostics)
    return ContentSnapshot(views=views, render_truncated=truncated)


def attach_content_ref(
    payload: dict[str, Any], content_ref: dict[str, Any] | None
) -> None:
    payload["content_ref"] = content_ref
    if content_ref is None:
        warnings = list(payload.get("warnings") or [])
        warnings.append(CONTENT_STORE_CAPACITY_EXCEEDED)
        payload["warnings"] = warnings


def handle_payload(
    payload: Mapping[str, Any],
    envelope: FetchEnvelope,
    request: FetchPaperRequest,
    store: ContentStore | None,
) -> dict[str, Any]:
    snapshot = content_snapshot(
        envelope, request, response_warnings=list(payload.get("warnings") or [])
    )
    ref = store.register_many([snapshot])[0] if store is not None else None
    result = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "article",
            "markdown",
            "trace",
            "quality",
            "events",
            "diagnostic_artifacts",
            "token_estimate_breakdown",
        }
    }
    metadata = (
        envelope.article.metadata if envelope.article is not None else envelope.metadata
    )
    if metadata is not None:
        result["metadata"] = asdict(metadata)
    result["warnings"] = [
        str(warning)[:400]
        for warning in [*envelope.quality.warnings, *(payload.get("warnings") or [])][
            :8
        ]
    ]
    attach_content_ref(result, ref)
    return result
