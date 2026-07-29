from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from paper_fetch.mcp.fetch_cache import (
    envelope_from_payload,
    payload_from_envelope,
)
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.models import (
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    ArticleModel,
    Asset,
    AssetQualitySummary,
    FetchEnvelope,
    Metadata,
    Quality,
    Section,
    SemanticLosses,
    apply_quality_assessment,
)
from paper_fetch.reason_codes import METADATA_ONLY, NO_ACCESS, RATE_LIMITED
from paper_fetch.tracing import source_trail_from_trace, trace_event
from paper_fetch.workflow.acceptance import (
    AssetAcceptanceStatus,
    AssetAcceptanceSummary,
    ContentAcceptanceStatus,
    FetchAcceptanceStatus,
    IdentityAcceptanceStatus,
    OutputAcceptanceStatus,
    OverallAcceptanceStatus,
    ProvenanceAcceptanceStatus,
    evaluate_fetch_acceptance,
    fetch_acceptance_json_schema,
    parse_fetch_acceptance_report,
)


def _envelope(
    content_kind: str = "fulltext",
    *,
    assets: list[Asset] | None = None,
    asset_failures: list[dict[str, object]] | None = None,
    losses: SemanticLosses | None = None,
    flags: list[str] | None = None,
    warnings: list[str] | None = None,
    trace: list | None = None,
    include_article: bool = True,
    include_markdown: bool = True,
    include_metadata: bool = False,
) -> FetchEnvelope:
    abstract = None if content_kind == "metadata_only" else "Accepted abstract."
    sections = (
        [
            Section(
                heading="Introduction",
                level=2,
                kind="body",
                text="Accepted body text. " * 20,
            ),
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="Accepted result text. " * 20,
            ),
        ]
        if content_kind == "fulltext"
        else []
    )
    article = ArticleModel(
        doi="10.1000/acceptance",
        source="elsevier_xml",
        metadata=Metadata(title="Acceptance Article", abstract=abstract),
        sections=sections,
        assets=list(assets or []),
        quality=Quality(),
    )
    events = list(
        [
            trace_event("resolve", "doi_selected", "ok"),
            trace_event(
                "fulltext",
                "elsevier",
                "ok",
                provider="elsevier",
                route="xml",
            ),
        ]
        if trace is None
        else trace
    )
    article.quality.asset_failures = list(asset_failures or [])
    article.quality.trace = events
    article.quality.source_trail = source_trail_from_trace(events)
    apply_quality_assessment(
        article,
        semantic_losses=losses or SemanticLosses(),
        extra_flags=flags,
        recompute_tokens=False,
    )
    article.quality.warnings.extend(warnings or [])
    markdown = (
        "# Acceptance Article\n\nAccepted body text.\n" if include_markdown else None
    )
    return FetchEnvelope(
        doi=article.doi,
        source=article.source,
        has_fulltext=article.quality.has_fulltext,
        content_kind=article.quality.content_kind,
        has_abstract=article.quality.has_abstract,
        warnings=article.quality.warnings,
        source_trail=article.quality.source_trail,
        trace=article.quality.trace,
        token_estimate=article.quality.token_estimate,
        quality=article.quality,
        article=article if include_article else None,
        markdown=markdown,
        metadata=article.metadata if include_metadata else None,
    )


def test_complete_fulltext_has_separate_fetch_content_and_overall_statuses() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="none",
        requested_outputs={"article", "markdown"},
    )

    assert report.overall == OverallAcceptanceStatus.COMPLETE
    assert report.fetch.status == FetchAcceptanceStatus.OK
    assert report.fetch.completed is True
    assert report.content.status == ContentAcceptanceStatus.FULLTEXT
    assert report.content.has_fulltext is True
    assert report.output.status == OutputAcceptanceStatus.COMPLETE


@pytest.mark.parametrize(
    ("content_kind", "expected_status"),
    [
        ("abstract_only", ContentAcceptanceStatus.ABSTRACT_ONLY),
        ("metadata_only", ContentAcceptanceStatus.METADATA_ONLY),
    ],
)
def test_limited_content_can_still_have_fetch_ok(
    content_kind: str, expected_status: ContentAcceptanceStatus
) -> None:
    report = evaluate_fetch_acceptance(
        _envelope(content_kind),
        asset_profile="none",
        requested_outputs={"article"},
    )

    assert report.fetch.status == FetchAcceptanceStatus.OK
    assert report.content.status == expected_status
    assert report.overall == OverallAcceptanceStatus.LIMITED


@pytest.mark.parametrize("failure_code", ["ambiguous", NO_ACCESS])
def test_ambiguity_and_no_access_require_action(failure_code: str) -> None:
    report = evaluate_fetch_acceptance(
        None,
        asset_profile="none",
        failure_code=failure_code,
        candidate_count=2 if failure_code == "ambiguous" else 0,
    )

    assert report.overall == OverallAcceptanceStatus.ACTION_REQUIRED
    assert report.fetch.status == FetchAcceptanceStatus.ACTION_REQUIRED
    assert report.fetch.completed is False
    assert report.content.status == ContentAcceptanceStatus.UNAVAILABLE
    if failure_code == "ambiguous":
        assert report.identity.status == IdentityAcceptanceStatus.AMBIGUOUS


def test_unhandled_fetch_error_is_failed() -> None:
    report = evaluate_fetch_acceptance(
        None, asset_profile="none", failure_code="provider_error"
    )

    assert report.overall == OverallAcceptanceStatus.FAILED
    assert report.fetch.status == FetchAcceptanceStatus.FAILED
    assert report.provenance.failure_codes == ("provider_error",)


def test_requested_assets_are_unavailable_when_fetch_did_not_complete() -> None:
    report = evaluate_fetch_acceptance(
        None,
        asset_profile="body",
        failure_code=NO_ACCESS,
        doi="https://doi.org/10.1000/acceptance",
    )

    assert report.identity.status == IdentityAcceptanceStatus.RESOLVED
    assert report.fetch.completed is False
    assert report.asset.requested is True
    assert report.asset.status == AssetAcceptanceStatus.UNAVAILABLE
    assert report.provenance.failure_codes == (NO_ACCESS,)
    assert report.overall == OverallAcceptanceStatus.ACTION_REQUIRED


def test_expected_doi_is_normalized_and_mismatch_requires_action() -> None:
    matching = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="none",
        expected_doi="https://doi.org/10.1000/ACCEPTANCE",
    )
    mismatch = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="none",
        expected_doi="10.1000/different",
    )

    assert matching.identity.status == IdentityAcceptanceStatus.RESOLVED
    assert matching.identity.doi == "10.1000/acceptance"
    assert matching.identity.expected_doi == "10.1000/acceptance"
    assert mismatch.identity.status == IdentityAcceptanceStatus.MISMATCH
    assert mismatch.identity.codes == ("identity_mismatch",)
    assert mismatch.overall == OverallAcceptanceStatus.ACTION_REQUIRED


def test_asset_profile_none_is_not_requested_and_preserves_remote_links() -> None:
    envelope = _envelope(
        assets=[
            Asset(
                kind="figure",
                heading="Figure 1",
                url="https://example.test/figure-1.png",
            )
        ],
        asset_failures=[
            {
                "kind": "figure",
                "reason": "must_not_count_for_unrequested_assets",
            }
        ],
    )

    report = evaluate_fetch_acceptance(envelope, asset_profile="none")

    assert report.asset.requested is False
    assert report.asset.status == AssetAcceptanceStatus.NOT_REQUESTED
    assert report.asset.remote_link_count == 1
    assert report.asset.remote_only_count == 1
    assert report.asset.remote_links_preserved is True
    assert report.asset.failed == 0
    assert report.asset.failure_codes == ()
    assert report.provenance.failure_codes == ()
    assert report.overall == OverallAcceptanceStatus.COMPLETE


def test_requested_asset_failure_degrades_assets_without_failing_text() -> None:
    envelope = _envelope(
        asset_failures=[
            {
                "kind": "figure",
                "reason": "cloudflare_challenge",
                "source_url": "https://example.test/figure-1.png",
            }
        ]
    )

    report = evaluate_fetch_acceptance(envelope, asset_profile="body")

    assert report.asset.requested is True
    assert report.asset.status == AssetAcceptanceStatus.FAILED
    assert report.asset.failure_codes == ("cloudflare_challenge",)
    assert report.content.status == ContentAcceptanceStatus.FULLTEXT
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_requested_assets_with_no_discovery_are_unknown_not_complete() -> None:
    report = evaluate_fetch_acceptance(_envelope(), asset_profile="body")

    assert report.asset.requested is True
    assert report.asset.discovered == 0
    assert report.asset.status == AssetAcceptanceStatus.UNKNOWN
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_audited_zero_expected_assets_are_not_applicable() -> None:
    envelope = _envelope()
    envelope.quality.asset_summary = AssetQualitySummary(
        audited=True,
        requested=True,
        profile="body",
        expected=0,
    )

    report = evaluate_fetch_acceptance(envelope, asset_profile="body")

    assert report.asset.status == AssetAcceptanceStatus.NOT_APPLICABLE
    assert report.asset.expected == 0


def test_asset_summary_extension_preserves_preview_placeholder_and_archive_facts() -> (
    None
):
    summary = AssetAcceptanceSummary(
        requested=True,
        profile="body",
        total=3,
        local=2,
        full_size=1,
        preview=1,
        placeholder_suspected=1,
        not_archived=1,
        remote_link_count=2,
        remote_only_count=1,
    )

    report = evaluate_fetch_acceptance(
        _envelope(), asset_profile="body", asset_summary=summary
    )

    assert report.asset.status == AssetAcceptanceStatus.DEGRADED
    assert report.asset.preview == 1
    assert report.asset.placeholder_suspected == 1
    assert report.asset.not_archived == 1
    assert set(report.provenance.warning_codes) >= {
        "asset_preview",
        "asset_placeholder_suspected",
        "asset_not_archived",
    }


def test_audited_quality_asset_summary_matches_explicit_acceptance_adapter() -> None:
    envelope = _envelope()
    envelope.quality.asset_summary = AssetQualitySummary(
        audited=True,
        requested=True,
        profile="body",
        total=4,
        local=2,
        full_size=1,
        preview=1,
        failed=1,
        placeholder_suspected=1,
        not_archived=1,
        remote_link_count=2,
        remote_only_count=1,
        failure_codes=["image_fetch_error"],
    )
    explicit = AssetAcceptanceSummary(
        requested=True,
        profile="body",
        audited=True,
        total=4,
        local=2,
        full_size=1,
        preview=1,
        failed=1,
        placeholder_suspected=1,
        not_archived=1,
        remote_link_count=2,
        remote_only_count=1,
        failure_codes=("image_fetch_error",),
    )

    automatic_report = evaluate_fetch_acceptance(envelope, asset_profile="body")
    explicit_report = evaluate_fetch_acceptance(
        _envelope(), asset_profile="body", asset_summary=explicit
    )

    assert automatic_report.asset == explicit_report.asset
    assert automatic_report.provenance.warning_codes == (
        explicit_report.provenance.warning_codes
    )
    assert automatic_report.provenance.failure_codes == (
        explicit_report.provenance.failure_codes
    )


@pytest.mark.parametrize(
    ("losses", "field", "code"),
    [
        (
            SemanticLosses(table_layout_degraded_count=2),
            "layout_degraded_count",
            "table_layout_degraded",
        ),
        (
            SemanticLosses(table_semantic_loss_count=1),
            "semantic_loss_count",
            "table_semantic_loss",
        ),
    ],
)
def test_table_layout_and_semantic_loss_remain_separate(
    losses: SemanticLosses, field: str, code: str
) -> None:
    report = evaluate_fetch_acceptance(_envelope(losses=losses), asset_profile="none")

    assert getattr(report.content.tables, field) > 0
    other = (
        "semantic_loss_count"
        if field == "layout_degraded_count"
        else "layout_degraded_count"
    )
    assert getattr(report.content.tables, other) == 0
    assert code in report.provenance.warning_codes
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_formula_fallback_and_missing_are_separate_structured_counts() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(
            losses=SemanticLosses(
                formula_fallback_count=2,
                formula_missing_count=1,
            )
        ),
        asset_profile="none",
    )

    assert report.content.formulas.fallback_count == 2
    assert report.content.formulas.missing_count == 1
    assert set(report.provenance.warning_codes) >= {
        "formula_fallback",
        "formula_missing",
    }
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_trace_fallback_is_classified_from_structured_event_not_message() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(
            trace=[
                trace_event(
                    "fallback",
                    "metadata",
                    "ok",
                    code=METADATA_ONLY,
                    message="arbitrary human text",
                )
            ]
        ),
        asset_profile="none",
    )

    assert report.provenance.fallback_codes == (METADATA_ONLY,)
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_asset_trace_failure_is_not_misclassified_as_fetch_fallback() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(
            trace=[
                trace_event(
                    "download",
                    "figure",
                    "fail",
                    code="asset_download_failed",
                )
            ]
        ),
        asset_profile="body",
    )

    assert report.provenance.fallback_codes == ()
    assert report.provenance.failure_codes == ("asset_download_failed",)
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_warning_message_text_is_never_used_as_a_classifier() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(warnings=["formula missing table failed no_access"]),
        asset_profile="none",
    )

    assert report.provenance.unstructured_warning_count == 1
    assert report.provenance.warning_codes == ()
    assert report.provenance.failure_codes == ()
    assert report.overall == OverallAcceptanceStatus.COMPLETE


def test_current_revision_cache_flag_is_provenance_not_degradation() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(flags=[QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION]),
        asset_profile="none",
    )

    assert QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION in report.content.flags
    assert QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION not in (
        report.provenance.warning_codes
    )
    assert report.overall == OverallAcceptanceStatus.COMPLETE


def test_missing_requested_output_fails_acceptance() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(include_markdown=False),
        asset_profile="none",
        requested_outputs={"markdown"},
    )

    assert report.output.status == OutputAcceptanceStatus.MISSING
    assert report.output.missing == ("markdown",)
    assert report.overall == OverallAcceptanceStatus.FAILED


def test_incomplete_provenance_is_reported_separately() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(trace=[]),
        asset_profile="none",
    )

    assert report.provenance.status == ProvenanceAcceptanceStatus.PARTIAL
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_recovered_rate_limit_remains_structured_degradation() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(
            trace=[
                trace_event("resolve", "doi_selected", "ok"),
                trace_event(
                    "fulltext",
                    "elsevier_api",
                    RATE_LIMITED,
                    code=RATE_LIMITED,
                    provider="elsevier",
                    route="api",
                    http_status=429,
                    retry_after_seconds=7,
                ),
                trace_event(
                    "fulltext",
                    "elsevier_pdf",
                    "ok",
                    provider="elsevier",
                    route="pdf",
                ),
            ]
        ),
        asset_profile="none",
    )

    assert report.fetch.status == FetchAcceptanceStatus.OK
    assert report.provenance.failure_codes == (RATE_LIMITED,)
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_same_envelope_has_identical_acceptance_after_existing_payload_adapters() -> (
    None
):
    envelope = _envelope(
        losses=SemanticLosses(table_layout_degraded_count=1),
        include_metadata=True,
    )
    audited_assets = AssetQualitySummary(
        audited=True,
        requested=True,
        profile="body",
        total=2,
        local=1,
        full_size=1,
        failed=1,
        placeholder_suspected=1,
        failure_codes=["image_fetch_error"],
    )
    envelope.quality.asset_summary = audited_assets
    assert envelope.article is not None
    envelope.article.quality.asset_summary = audited_assets
    request = FetchPaperRequest.model_validate(
        {
            "query": "10.1000/acceptance",
            "modes": ["article", "markdown", "metadata"],
            "strategy": {"asset_profile": "body"},
        }
    )
    payload = payload_from_envelope(envelope, request)
    round_tripped = envelope_from_payload(payload)

    direct = evaluate_fetch_acceptance(
        envelope,
        asset_profile="body",
        requested_outputs=request.requested_modes(),
    )
    adapted = evaluate_fetch_acceptance(
        round_tripped,
        asset_profile="body",
        requested_outputs=request.requested_modes(),
    )

    assert round_tripped.quality.asset_summary == audited_assets
    assert direct.asset.status == AssetAcceptanceStatus.DEGRADED
    assert adapted == direct


def test_report_round_trip_schema_and_additive_v1_compatibility() -> None:
    report = evaluate_fetch_acceptance(_envelope(), asset_profile="none")
    payload = json.loads(report.to_json())
    schema = fetch_acceptance_json_schema()

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert payload["schema_version"] == 1
    assert payload["minimum_reader_schema_version"] == 1
    assert parse_fetch_acceptance_report(payload) == report

    payload["future_additive_field"] = {"accepted_by_v1_reader": True}
    assert parse_fetch_acceptance_report(payload) == report


@pytest.mark.parametrize("schema_version", [None, 2])
def test_missing_or_incompatible_schema_version_is_rejected(
    schema_version: int | None,
) -> None:
    payload = evaluate_fetch_acceptance(_envelope(), asset_profile="none").to_dict()
    if schema_version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = schema_version

    with pytest.raises(ValidationError):
        parse_fetch_acceptance_report(payload)


def test_overall_enum_values_are_stable_contract() -> None:
    assert {item.value for item in OverallAcceptanceStatus} == {
        "complete",
        "degraded",
        "limited",
        "failed",
        "action_required",
    }
