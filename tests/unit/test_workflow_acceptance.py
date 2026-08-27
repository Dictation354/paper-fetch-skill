from __future__ import annotations

from dataclasses import replace
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
    AcquisitionProvenance,
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    ArticleModel,
    Asset,
    AssetDiagnostic,
    AssetQualitySummary,
    FetchEnvelope,
    Metadata,
    Quality,
    Section,
    SemanticLosses,
    apply_quality_assessment,
)
from paper_fetch.reason_codes import METADATA_ONLY, NO_ACCESS, RATE_LIMITED
import paper_fetch.provider_catalog as provider_catalog_module
from paper_fetch.tracing import (
    acquisition_fallback_used,
    source_trail_from_trace,
    trace_event,
)
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
    _route_acceptance_satisfied,
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
        acquisition=AcquisitionProvenance(
            provider="elsevier",
            route="xml_api",
            representation="xml",
            transport="api",
        ),
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
    article.acquisition = AcquisitionProvenance(
        provider="elsevier",
        route="xml_api",
        representation="xml",
        transport="api",
        fallback_used=acquisition_fallback_used(events),
    )
    article.quality.asset_failures = list(asset_failures or [])
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
        trace=events,
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
    assert report.provenance.acceptance_policy == "structured_xml_body"
    assert report.provenance.acceptance_policy_satisfied is True


def test_catalog_acceptance_policy_mutation_changes_runtime_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_catalog = dict(provider_catalog_module.PROVIDER_CATALOG)
    elsevier = original_catalog["elsevier"]
    mutated_routes = tuple(
        replace(route, acceptance_policy="validated_pdf")
        if route.name == "xml_api"
        else route
        for route in elsevier.routes
    )
    monkeypatch.setattr(
        provider_catalog_module,
        "PROVIDER_CATALOG",
        {**original_catalog, "elsevier": replace(elsevier, routes=mutated_routes)},
    )

    report = evaluate_fetch_acceptance(_envelope(), asset_profile="none")

    assert report.provenance.acceptance_policy == "validated_pdf"
    assert report.provenance.acceptance_policy_satisfied is False


def test_route_acceptance_policies_use_their_matching_public_facet() -> None:
    asset_summary = AssetAcceptanceSummary(
        requested=True,
        profile="body",
        audited=True,
        expected=1,
        discovered=1,
        attempted=1,
        total=1,
        local=1,
        full_size=1,
    )
    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="body",
        asset_summary=asset_summary,
    )
    common = {
        "identity": report.identity,
        "content": report.content,
        "asset": report.asset,
    }

    assert _route_acceptance_satisfied(
        "metadata_identity",
        acquisition=AcquisitionProvenance(
            provider="crossref",
            route="metadata",
            representation="metadata",
            transport="api",
        ),
        **common,
    )
    assert _route_acceptance_satisfied(
        "provider_html_body",
        acquisition=AcquisitionProvenance(
            provider="example",
            route="html",
            representation="html",
            transport="http",
        ),
        **common,
    )
    assert _route_acceptance_satisfied(
        "structured_xml_body",
        acquisition=AcquisitionProvenance(
            provider="example",
            route="xml",
            representation="xml",
            transport="http",
        ),
        **common,
    )
    assert _route_acceptance_satisfied(
        "validated_pdf",
        acquisition=AcquisitionProvenance(
            provider="example",
            route="pdf",
            representation="pdf",
            transport="http",
        ),
        **common,
    )
    assert _route_acceptance_satisfied(
        "validated_asset",
        acquisition=AcquisitionProvenance(
            provider="example",
            route="asset",
            representation="xml",
            transport="http",
        ),
        **common,
    )
    assert not _route_acceptance_satisfied(
        "future_unrecognized_policy",
        acquisition=AcquisitionProvenance(
            provider="example",
            route="future",
            representation="xml",
            transport="http",
        ),
        **common,
    )


def test_validated_asset_requires_local_or_audited_not_applicable_evidence() -> None:
    no_local = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="body",
        asset_summary=AssetAcceptanceSummary(
            requested=True,
            profile="body",
            audited=True,
            expected=1,
            discovered=1,
            attempted=1,
            total=1,
            remote_link_count=1,
            remote_only_count=1,
        ),
    )
    not_applicable = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="body",
        asset_summary=AssetAcceptanceSummary(
            requested=True,
            profile="body",
            audited=True,
            expected=0,
        ),
    )
    acquisition = AcquisitionProvenance(
        provider="example",
        route="assets",
        representation="xml",
        transport="http",
    )

    assert not _route_acceptance_satisfied(
        "validated_asset",
        acquisition=acquisition,
        identity=no_local.identity,
        content=no_local.content,
        asset=no_local.asset,
    )
    assert _route_acceptance_satisfied(
        "validated_asset",
        acquisition=acquisition,
        identity=not_applicable.identity,
        content=not_applicable.content,
        asset=not_applicable.asset,
    )


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


def test_doi_less_title_alone_does_not_resolve_identity() -> None:
    envelope = _envelope()
    envelope.doi = None
    assert envelope.article is not None
    envelope.article.doi = None

    report = evaluate_fetch_acceptance(envelope, asset_profile="none")

    assert report.identity.status == IdentityAcceptanceStatus.UNAVAILABLE
    assert report.identity.codes == ("canonical_landing_identity_unverified",)
    assert report.overall == OverallAcceptanceStatus.ACTION_REQUIRED


def test_doi_less_verified_unique_canonical_landing_resolves_identity() -> None:
    envelope = _envelope()
    envelope.doi = None
    assert envelope.article is not None
    envelope.article.doi = None

    report = evaluate_fetch_acceptance(
        envelope,
        asset_profile="none",
        canonical_landing_url="https://publisher.example/article/unique-id",
        canonical_landing_verified=True,
        canonical_landing_unique=True,
    )

    assert report.identity.status == IdentityAcceptanceStatus.RESOLVED
    assert report.identity.canonical_landing_verified is True
    assert report.identity.canonical_landing_unique is True


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
        "asset_fidelity_degraded",
        "asset_placeholder_suspected",
        "asset_remote_only",
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


def test_audited_body_assets_ignore_remote_only_unrequested_supplements() -> None:
    summary = AssetAcceptanceSummary(
        requested=True,
        profile="body",
        audited=True,
        discovered=1,
        total=1,
        remote_link_count=1,
        remote_only_count=1,
        issue_codes=(),
    )

    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="body",
        asset_summary=summary,
    )

    assert report.asset.status == AssetAcceptanceStatus.COMPLETE
    assert report.asset.issue_codes == ()
    assert report.overall == OverallAcceptanceStatus.COMPLETE


def test_default_asset_acceptance_remains_compatible_with_audited_remote_only_rows() -> (
    None
):
    summary = AssetAcceptanceSummary(
        requested=True,
        profile="body",
        audited=True,
        discovered=1,
        attempted=1,
        total=1,
        not_archived=1,
        remote_link_count=1,
        remote_only_count=1,
        body_discovered=1,
        body_attempted=1,
        body_not_archived=1,
        body_remote_only_count=1,
        issue_codes=(),
    )

    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="body",
        asset_summary=summary,
    )

    assert report.asset.status == AssetAcceptanceStatus.COMPLETE
    assert report.asset.require_local_body_assets is False
    assert report.asset.local_body_assets_satisfied is True
    assert report.asset.has_local_body_assets is False
    assert report.asset.all_body_assets_local is False
    assert report.fetch.status == FetchAcceptanceStatus.OK
    assert report.overall == OverallAcceptanceStatus.COMPLETE


def test_strict_local_assets_degrade_acceptance_without_failing_fulltext() -> None:
    summary = AssetAcceptanceSummary(
        requested=True,
        profile="body",
        audited=True,
        discovered=1,
        attempted=1,
        total=1,
        not_archived=1,
        remote_link_count=1,
        remote_only_count=1,
        body_discovered=1,
        body_attempted=1,
        body_not_archived=1,
        body_remote_only_count=1,
        issue_codes=(),
    )

    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="body",
        asset_summary=summary,
        require_local_body_assets=True,
    )

    assert report.asset.status == AssetAcceptanceStatus.DEGRADED
    assert report.asset.require_local_body_assets is True
    assert report.asset.local_body_assets_satisfied is False
    assert "local_body_assets_required" in report.asset.issue_codes
    assert report.fetch.status == FetchAcceptanceStatus.OK
    assert report.content.status == ContentAcceptanceStatus.FULLTEXT
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_strict_full_size_implies_local_and_rejects_accepted_preview() -> None:
    summary = AssetAcceptanceSummary(
        requested=True,
        profile="body",
        audited=True,
        discovered=1,
        attempted=1,
        total=1,
        local=1,
        preview=1,
        accepted_preview=1,
        body_discovered=1,
        body_attempted=1,
        body_local=1,
        body_preview=1,
        issue_codes=(),
    )

    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="body",
        asset_summary=summary,
        require_full_size_body_assets=True,
    )

    assert report.asset.require_local_body_assets is True
    assert report.asset.require_full_size_body_assets is True
    assert report.asset.local_body_assets_satisfied is True
    assert report.asset.full_size_body_assets_satisfied is False
    assert report.asset.all_body_assets_full_size is False
    assert "full_size_body_assets_required" in report.asset.issue_codes
    assert report.asset.status == AssetAcceptanceStatus.DEGRADED
    assert report.fetch.status == FetchAcceptanceStatus.OK


def test_strict_full_size_accepts_all_local_full_size_body_assets() -> None:
    summary = AssetAcceptanceSummary(
        requested=True,
        profile="all",
        audited=True,
        discovered=2,
        attempted=2,
        total=2,
        local=2,
        full_size=2,
        body_discovered=2,
        body_attempted=2,
        body_local=2,
        body_full_size=2,
        issue_codes=(),
    )

    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="all",
        asset_summary=summary,
        require_full_size_body_assets=True,
    )

    assert report.asset.status == AssetAcceptanceStatus.COMPLETE
    assert report.asset.has_local_body_assets is True
    assert report.asset.all_body_assets_local is True
    assert report.asset.all_body_assets_full_size is True
    assert report.asset.local_body_assets_satisfied is True
    assert report.asset.full_size_body_assets_satisfied is True
    assert report.overall == OverallAcceptanceStatus.COMPLETE


def test_strict_local_ignores_inline_semantics_without_binary_payloads() -> None:
    envelope = _envelope()
    envelope.quality.asset_summary = AssetQualitySummary(
        audited=True,
        requested=True,
        profile="body",
        discovered=3,
        attempted=3,
        total=3,
        local=1,
        full_size=1,
        diagnostics=[
            AssetDiagnostic(
                request_profile="body",
                kind="table",
                status="available",
            ),
            AssetDiagnostic(
                request_profile="body",
                kind="figure",
                status="available",
            ),
            AssetDiagnostic(
                request_profile="body",
                kind="figure",
                status="available",
                path="body_assets/figure.png",
                download_tier="full_size",
            ),
        ],
    )

    report = evaluate_fetch_acceptance(
        envelope,
        asset_profile="body",
        require_local_body_assets=True,
    )

    assert report.asset.body_discovered == 1
    assert report.asset.body_local == 1
    assert report.asset.all_body_assets_local is True
    assert report.asset.local_body_assets_satisfied is True
    assert report.asset.status == AssetAcceptanceStatus.COMPLETE


def test_strict_local_keeps_body_remote_only_failure_in_file_denominator() -> None:
    envelope = _envelope()
    envelope.quality.asset_summary = AssetQualitySummary(
        audited=True,
        requested=True,
        profile="body",
        discovered=2,
        attempted=2,
        total=2,
        remote_link_count=1,
        remote_only_count=1,
        diagnostics=[
            AssetDiagnostic(
                request_profile="body",
                kind="table",
                status="available",
            ),
            AssetDiagnostic(
                request_profile="body",
                kind="figure",
                status="failed",
                failure_code="missing_path",
            ),
        ],
    )

    report = evaluate_fetch_acceptance(
        envelope,
        asset_profile="body",
        require_local_body_assets=True,
    )

    assert report.asset.body_discovered == 1
    assert report.asset.body_failed == 1
    assert report.asset.body_remote_only_count == 1
    assert report.asset.all_body_assets_local is False
    assert report.asset.status == AssetAcceptanceStatus.DEGRADED


def test_strict_asset_requirements_are_not_applicable_to_profile_none() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(),
        asset_profile="none",
        require_local_body_assets=True,
        require_full_size_body_assets=True,
    )

    assert report.asset.status == AssetAcceptanceStatus.NOT_REQUESTED
    assert report.asset.local_body_assets_satisfied is True
    assert report.asset.full_size_body_assets_satisfied is True
    assert report.fetch.status == FetchAcceptanceStatus.OK
    assert report.overall == OverallAcceptanceStatus.COMPLETE


def test_warning_message_text_is_never_used_as_a_classifier() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(
            warnings=[
                "HTML route was unavailable.",
                "PDF fallback succeeded.",
                "PDF artifact was saved.",
                "formula missing table failed no_access",
            ]
        ),
        asset_profile="none",
    )

    assert report.provenance.unstructured_warning_count == 4
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


def test_missing_acquisition_is_partial_without_guessing_from_source() -> None:
    envelope = _envelope()
    envelope.acquisition = None
    assert envelope.article is not None
    envelope.article.acquisition = None

    report = evaluate_fetch_acceptance(envelope, asset_profile="none")

    assert report.provenance.source == "elsevier_xml"
    assert report.provenance.acquisition is None
    assert report.provenance.status == ProvenanceAcceptanceStatus.PARTIAL
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_catalog_inconsistent_acquisition_is_partial() -> None:
    envelope = _envelope()
    inconsistent = AcquisitionProvenance(
        provider="elsevier",
        route="xml_api",
        representation="pdf",
        transport="api",
    )
    envelope.acquisition = inconsistent
    assert envelope.article is not None
    envelope.article.acquisition = inconsistent

    report = evaluate_fetch_acceptance(envelope, asset_profile="none")

    assert report.provenance.acquisition == inconsistent
    assert report.provenance.status == ProvenanceAcceptanceStatus.PARTIAL


def test_fallback_flag_must_match_structured_trace() -> None:
    events = [
        trace_event("resolve", "doi_selected", "ok"),
        trace_event(
            "fulltext",
            "elsevier_xml",
            "fail",
            provider="elsevier",
            route="xml_api",
        ),
        trace_event(
            "fulltext",
            "elsevier_pdf",
            "ok",
            provider="elsevier",
            route="pdf_api",
        ),
    ]
    envelope = _envelope(trace=events)
    mismatched = AcquisitionProvenance(
        provider="elsevier",
        route="pdf_api",
        representation="pdf",
        transport="api",
        fallback_used=False,
    )
    envelope.acquisition = mismatched
    assert envelope.article is not None
    envelope.article.acquisition = mismatched

    report = evaluate_fetch_acceptance(envelope, asset_profile="none")

    assert report.provenance.status == ProvenanceAcceptanceStatus.PARTIAL


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


def test_recovered_metadata_lookup_failure_does_not_degrade_fulltext() -> None:
    report = evaluate_fetch_acceptance(
        _envelope(
            trace=[
                trace_event("resolve", "doi_selected", "ok"),
                trace_event(
                    "metadata",
                    "crossref",
                    "fail",
                    code="crossref_not_found",
                    provider="crossref",
                    route="api",
                ),
                trace_event(
                    "fulltext",
                    "arxiv_html",
                    "ok",
                    provider="arxiv",
                    route="html",
                ),
            ]
        ),
        asset_profile="none",
    )

    assert report.provenance.failure_codes == ()
    assert report.overall == OverallAcceptanceStatus.COMPLETE


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


def test_report_round_trip_schema_and_additive_v2_compatibility() -> None:
    report = evaluate_fetch_acceptance(_envelope(), asset_profile="none")
    payload = json.loads(report.to_json())
    schema = fetch_acceptance_json_schema()

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert payload["schema_version"] == 2
    assert payload["minimum_reader_schema_version"] == 2
    assert parse_fetch_acceptance_report(payload) == report

    payload["future_additive_field"] = {"accepted_by_v2_reader": True}
    assert parse_fetch_acceptance_report(payload) == report


@pytest.mark.parametrize("schema_version", [None, 1, 3])
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
