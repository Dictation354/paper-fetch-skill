from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.mcp.fetch_cache import quality_from_payload
from paper_fetch.models import (
    ArticleModel,
    Asset,
    AssetQualitySummary,
    FetchEnvelope,
    Metadata,
    Quality,
    Section,
)
from paper_fetch.providers import _ams_html
from paper_fetch.quality.assets import (
    build_asset_quality_summary,
    logical_asset_kind,
)
from paper_fetch.tracing import trace_event
from paper_fetch.workflow.acceptance import (
    AssetAcceptanceStatus,
    ContentAcceptanceStatus,
    OverallAcceptanceStatus,
    evaluate_fetch_acceptance,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "golden_criteria"
VALID_PNG = (
    FIXTURES / "10.1371_journal.pone.0015338" / "body_assets" / "pone.0015338.e003.png"
)
VALID_JPEG = FIXTURES / "10.1063_5.0129134" / "body_assets" / "m_125205_1_f4.jpeg"


def _svg(width: int, height: int) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}"><rect width="100%" height="100%"/></svg>'
    ).encode()


def _fulltext_envelope(article: ArticleModel) -> FetchEnvelope:
    event = trace_event("fulltext", "ams", "ok")
    return FetchEnvelope(
        doi=article.doi,
        source=article.source,
        has_fulltext=True,
        content_kind="fulltext",
        has_abstract=True,
        trace=[event],
        quality=article.quality,
        article=article,
        markdown="# Asset audit\n\nFull text.\n",
    )


def test_valid_png_jpeg_svg_and_pseudo_extension_record_real_facts(
    tmp_path: Path,
) -> None:
    svg_path = tmp_path / "figure.svg"
    svg_path.write_bytes(_svg(640, 480))
    pseudo_jpeg = tmp_path / "actually-png.jpg"
    pseudo_jpeg.write_bytes(VALID_PNG.read_bytes() + b"\n")
    assets = [
        Asset(kind="figure", heading="Figure 1", path=str(VALID_PNG)),
        Asset(kind="table", heading="Table 1", path=str(VALID_JPEG)),
        Asset(kind="formula", heading="Equation 1", path=str(svg_path)),
        Asset(kind="figure", heading="Figure 2", path=str(pseudo_jpeg)),
    ]

    summary = build_asset_quality_summary(
        assets,
        asset_profile="body",
        archive_enabled=True,
    )

    assert [item.real_mime for item in summary.diagnostics] == [
        "image/png",
        "image/jpeg",
        "image/svg+xml",
        "image/png",
    ]
    assert [(item.width, item.height) for item in summary.diagnostics[:3]] == [
        (129, 36),
        (520, 287),
        (640, 480),
    ]
    assert summary.diagnostics[0].byte_count == VALID_PNG.stat().st_size
    assert (
        summary.diagnostics[0].sha256
        == hashlib.sha256(VALID_PNG.read_bytes()).hexdigest()
    )
    assert summary.diagnostics[3].status == "placeholder_suspected"
    assert summary.diagnostics[3].suspected_reasons == ["mime_extension_mismatch"]
    assert summary.failed == 0
    assert summary.by_kind["figure"].total == 2
    assert summary.by_kind["formula"].total == 1
    assert summary.by_kind["table"].total == 1


def test_placeholder_signals_are_suspected_and_never_delete_files(
    tmp_path: Path,
) -> None:
    zero = tmp_path / "zero.png"
    zero.write_bytes(b"")
    blank = tmp_path / "Blank.svg"
    blank.write_bytes(_svg(120, 80))
    tiny = tmp_path / "tiny.svg"
    tiny.write_bytes(_svg(1, 1))
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"<html>not an image</html>")
    duplicate_one = tmp_path / "figure-one.png"
    duplicate_two = tmp_path / "figure-two.png"
    duplicate_one.write_bytes(VALID_PNG.read_bytes())
    duplicate_two.write_bytes(VALID_PNG.read_bytes())
    paths = [zero, blank, tiny, invalid, duplicate_one, duplicate_two]
    before = {path: path.read_bytes() for path in paths}

    summary = build_asset_quality_summary(
        [
            Asset(kind="figure", heading="Figure 0", path=str(zero)),
            Asset(
                kind="formula",
                heading="Equation 1",
                url="https://example.test/assets/Blank.svg",
                path=str(blank),
            ),
            Asset(kind="decoration", heading="Rule", path=str(tiny)),
            Asset(kind="table", heading="Table 1", path=str(invalid)),
            Asset(kind="figure", heading="Figure 1", path=str(duplicate_one)),
            Asset(kind="figure", heading="Figure 2", path=str(duplicate_two)),
        ],
        asset_profile="all",
        archive_enabled=True,
    )

    assert summary.placeholder_suspected == 6
    assert summary.failed == 0
    assert "zero_byte" in summary.diagnostics[0].suspected_reasons
    assert "invalid_mime" in summary.diagnostics[0].suspected_reasons
    assert "blank_url" in summary.diagnostics[1].suspected_reasons
    assert "tiny_dimensions" in summary.diagnostics[2].suspected_reasons
    assert "invalid_mime" in summary.diagnostics[3].suspected_reasons
    assert all(
        "duplicate_sha256" in diagnostic.suspected_reasons
        for diagnostic in summary.diagnostics[4:]
    )
    assert summary.full_size == 6
    assert summary.diagnostics[0].sha256 == hashlib.sha256(b"").hexdigest()
    assert {path: path.read_bytes() for path in paths} == before


def test_formula_dimensions_and_duplicate_hashes_are_not_placeholder_signals(
    tmp_path: Path,
) -> None:
    tiny_formula = tmp_path / "tiny-formula.svg"
    duplicate_one = tmp_path / "formula-one.png"
    duplicate_two = tmp_path / "formula-two.png"
    tiny_formula.write_bytes(_svg(1, 1))
    duplicate_one.write_bytes(VALID_PNG.read_bytes())
    duplicate_two.write_bytes(VALID_PNG.read_bytes())

    summary = build_asset_quality_summary(
        [
            Asset(
                kind="formula",
                heading="Formula 1",
                path=str(tiny_formula),
                download_tier="preview",
                preview_accepted=True,
            ),
            Asset(
                kind="formula",
                heading="Formula 2",
                path=str(duplicate_one),
                download_tier="preview",
                preview_accepted=True,
            ),
            Asset(
                kind="formula",
                heading="Formula 3",
                path=str(duplicate_two),
                download_tier="preview",
                preview_accepted=True,
            ),
        ],
        asset_profile="body",
        archive_enabled=True,
    )

    assert summary.preview == 3
    assert summary.accepted_preview == 3
    assert summary.fallback_preview == 0
    assert summary.placeholder_suspected == 0
    assert summary.issue_codes == []
    assert all(item.status == "available" for item in summary.diagnostics)
    assert all(
        "tiny_dimensions" not in item.suspected_reasons
        and "duplicate_sha256" not in item.suspected_reasons
        for item in summary.diagnostics
    )


def test_formula_payload_and_path_failures_remain_diagnostic(
    tmp_path: Path,
) -> None:
    zero = tmp_path / "zero-formula.png"
    blank = tmp_path / "Blank.svg"
    invalid = tmp_path / "invalid-formula.png"
    missing = tmp_path / "missing-formula.png"
    zero.write_bytes(b"")
    blank.write_bytes(_svg(120, 80))
    invalid.write_bytes(b"<html>not an image</html>" * 2)

    summary = build_asset_quality_summary(
        [
            Asset(kind="formula", heading="Formula 1", path=str(zero)),
            Asset(
                kind="formula",
                heading="Formula 2",
                url="https://example.test/assets/Blank.svg",
                path=str(blank),
            ),
            Asset(kind="formula", heading="Formula 3", path=str(invalid)),
            Asset(kind="formula", heading="Formula 4", path=str(missing)),
        ],
        asset_profile="body",
        archive_enabled=True,
    )

    assert [item.status for item in summary.diagnostics] == [
        "placeholder_suspected",
        "placeholder_suspected",
        "placeholder_suspected",
        "failed",
    ]
    assert {"zero_byte", "invalid_mime"} <= set(
        summary.diagnostics[0].suspected_reasons
    )
    assert summary.diagnostics[1].suspected_reasons == ["blank_url"]
    assert "invalid_mime" in summary.diagnostics[2].suspected_reasons
    assert summary.diagnostics[3].failure_code == "missing_path"
    assert summary.placeholder_suspected == 3
    assert summary.failed == 1


def test_none_and_no_archive_policy_are_distinct_from_failures() -> None:
    assets = [
        Asset(
            kind="figure",
            heading="Figure 1",
            url="https://example.test/figure.png",
            path="/definitely/missing/paper-fetch/figure.png",
            download_tier="preview",
        ),
        Asset(
            kind="supplementary",
            heading="Supplement 1",
            url="https://example.test/supplement.pdf",
            section="supplementary",
        ),
    ]

    none_summary = build_asset_quality_summary(
        assets,
        asset_profile="none",
        archive_enabled=False,
    )
    body_summary = build_asset_quality_summary(
        assets,
        asset_profile="body",
        archive_enabled=False,
    )
    all_summary = build_asset_quality_summary(
        assets,
        asset_profile="all",
        archive_enabled=False,
    )

    assert none_summary.requested is False
    assert none_summary.not_requested == 2
    assert none_summary.not_archived == none_summary.failed == 0
    assert none_summary.preview == 0
    assert body_summary.not_archived == 1
    assert body_summary.not_requested == 1
    assert body_summary.failed == 0
    assert body_summary.preview == 0
    assert all_summary.not_archived == 2
    assert all_summary.not_requested == all_summary.failed == 0


def test_missing_path_and_explicit_failure_are_definite_and_classified(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.png"
    summary = build_asset_quality_summary(
        [Asset(kind="figure", heading="Figure 1", path=str(missing))],
        asset_failures=[
            {
                "kind": "formula",
                "heading": "Equation 2",
                "source_url": "https://example.test/equation.png",
                "reason": "cloudflare_challenge",
            }
        ],
        asset_profile="body",
        archive_enabled=True,
    )

    assert summary.failed == 2
    assert summary.failure_codes == ["cloudflare_challenge", "missing_path"]
    assert summary.by_kind["figure"].failed == 1
    assert summary.by_kind["formula"].failed == 1
    assert summary.diagnostics[0].status == "failed"
    assert summary.diagnostics[0].failure_code == "missing_path"


def test_ams_body_figures_formulas_and_tables_keep_separate_kinds() -> None:
    source_url = "https://journals.ametsoc.org/view/journals/clim/37/24/article.xml"
    ams_assets = _ams_html.scoped_asset_extractor(
        """
        <article><section>
          <figure id="fig1">
            <img data-image-src="/images/figure-1.jpg"
                 src="/skin/site/img/Blank.svg" alt="Fig. 1." />
            <figcaption>Fig. 1. Circulation response.</figcaption>
          </figure>
          <div class="formula" id="e1">
            <img data-image-src="/images/formula-1.gif"
                 src="/skin/site/img/Blank.png" alt="e1" />
          </div>
          <figure class="tableWrap" id="tbl1">
            <span class="tableWrapLabel">Table 1.</span>
            <img data-image-src="/images/table-1.jpg"
                 src="/skin/site/img/Blank.svg" alt="Table 1." />
          </figure>
        </section></article>
        """,
        source_url,
        asset_profile="body",
    )

    summary = build_asset_quality_summary(
        ams_assets,
        asset_profile="body",
        archive_enabled=False,
    )

    assert [logical_asset_kind(item) for item in ams_assets] == [
        "figure",
        "formula",
        "table",
    ]
    assert summary.by_kind["figure"].total == 1
    assert summary.by_kind["formula"].total == 1
    assert summary.by_kind["table"].total == 1
    assert summary.not_archived == 3
    assert summary.failed == 0


def test_relative_archive_path_is_not_prefixed_twice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    archive = Path("papers")
    archive.mkdir()
    image_path = archive / "figure.png"
    image_path.write_bytes(VALID_PNG.read_bytes())

    summary = build_asset_quality_summary(
        [Asset(kind="figure", heading="Figure 1", path=str(image_path))],
        asset_profile="body",
        archive_enabled=True,
        base_dir=archive,
    )

    assert summary.local == 1
    assert summary.failed == 0
    assert summary.diagnostics[0].real_mime == "image/png"


def test_wiley_preview_is_asset_degradation_not_text_failure() -> None:
    asset = Asset(
        kind="figure",
        heading="Figure 1",
        path=str(VALID_JPEG),
        download_tier="preview",
        provenance=["wiley_preview_fallback"],
    )
    summary = build_asset_quality_summary(
        [asset],
        asset_profile="body",
        archive_enabled=True,
    )
    article = ArticleModel(
        doi="10.1000/wiley-preview",
        source="wiley_browser",
        metadata=Metadata(title="Preview", abstract="Abstract"),
        sections=[
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="Full text body. " * 50,
            )
        ],
        assets=[asset],
    )
    article.quality.asset_summary = summary

    report = evaluate_fetch_acceptance(
        _fulltext_envelope(article), asset_profile="body"
    )

    assert summary.preview == 1
    assert summary.failed == 0
    assert summary.diagnostics[0].provenance == ["wiley_preview_fallback"]
    assert report.asset.status == AssetAcceptanceStatus.DEGRADED
    assert report.asset.preview == 1
    assert report.content.status == ContentAcceptanceStatus.FULLTEXT
    assert report.overall == OverallAcceptanceStatus.DEGRADED


def test_accepted_preview_is_complete_and_fallback_preview_is_fidelity_only() -> None:
    accepted_asset = Asset(
        kind="figure",
        heading="Figure 1",
        path=str(VALID_JPEG),
        download_tier="preview",
        preview_accepted=True,
    )
    accepted = build_asset_quality_summary(
        [accepted_asset],
        asset_profile="body",
        archive_enabled=True,
    )
    accepted_article = ArticleModel(
        doi="10.1000/accepted-preview",
        source="arxiv_html",
        metadata=Metadata(title="Accepted preview", abstract="Abstract"),
        sections=[
            Section(
                heading="Body",
                level=2,
                kind="body",
                text="Full text body. " * 50,
            )
        ],
        assets=[accepted_asset],
    )
    accepted_article.quality.asset_summary = accepted

    accepted_report = evaluate_fetch_acceptance(
        _fulltext_envelope(accepted_article),
        asset_profile="body",
    )

    assert accepted.preview == 1
    assert accepted.accepted_preview == 1
    assert accepted.fallback_preview == 0
    assert accepted.issue_codes == []
    assert accepted_report.asset.status == AssetAcceptanceStatus.COMPLETE

    fallback_asset = Asset(
        kind="figure",
        heading="Figure 2",
        path=str(VALID_PNG),
        download_tier="preview",
    )
    fallback = build_asset_quality_summary(
        [fallback_asset],
        asset_profile="body",
        archive_enabled=True,
    )

    assert fallback.preview == 1
    assert fallback.accepted_preview == 0
    assert fallback.fallback_preview == 1
    assert fallback.failed == 0
    assert fallback.issue_codes == ["asset_fidelity_degraded"]


def test_asset_issue_codes_distinguish_failure_placeholder_and_archive_policy(
    tmp_path: Path,
) -> None:
    missing = build_asset_quality_summary(
        [
            Asset(
                kind="figure",
                heading="Missing",
                path=str(tmp_path / "missing.png"),
            )
        ],
        asset_profile="body",
        archive_enabled=True,
    )
    placeholder_path = tmp_path / "placeholder.png"
    placeholder_path.write_bytes(b"")
    placeholder = build_asset_quality_summary(
        [
            Asset(
                kind="figure",
                heading="Placeholder",
                path=str(placeholder_path),
            )
        ],
        asset_profile="body",
        archive_enabled=True,
    )
    remote_asset = Asset(
        kind="figure",
        heading="Remote",
        url="https://example.test/remote.png",
    )
    remote_requested = build_asset_quality_summary(
        [remote_asset],
        asset_profile="body",
        archive_enabled=True,
    )
    remote_not_archived = build_asset_quality_summary(
        [remote_asset],
        asset_profile="body",
        archive_enabled=False,
    )

    assert missing.failure_codes == ["missing_path"]
    assert missing.issue_codes == ["asset_download_failure"]
    assert placeholder.issue_codes == ["asset_placeholder_suspected"]
    assert "asset_remote_only" in remote_requested.issue_codes
    assert "asset_fidelity_degraded" not in remote_requested.issue_codes
    assert remote_not_archived.issue_codes == []
    assert remote_not_archived.not_archived == 1


def test_artifact_store_audit_records_policy_without_mutating_text_quality(
    tmp_path: Path,
) -> None:
    article = ArticleModel(
        doi="10.1000/no-archive",
        source="ams_html",
        metadata=Metadata(title="No archive", abstract="Abstract"),
        sections=[Section(heading="Body", level=2, kind="body", text="Body text")],
        assets=[
            Asset(
                kind="figure",
                heading="Figure 1",
                url="https://example.test/figure.png",
            )
        ],
    )
    content_facts = (
        article.quality.content_kind,
        article.quality.has_fulltext,
        list(article.quality.warnings),
    )
    store = ArtifactStore.from_download_dir(tmp_path, artifact_mode="none")

    body_summary = store.audit_article_assets(article, asset_profile="body")
    none_summary = store.audit_article_assets(article, asset_profile="none")
    provider_policy_summary = ArtifactStore.from_download_dir(
        tmp_path
    ).audit_article_assets(
        article,
        asset_profile="body",
        archive_enabled=False,
    )

    assert body_summary.not_archived == 1
    assert body_summary.failed == 0
    assert none_summary.not_requested == 1
    assert none_summary.not_archived == 0
    assert provider_policy_summary.not_archived == 1
    assert (
        article.quality.content_kind,
        article.quality.has_fulltext,
        article.quality.warnings,
    ) == content_facts


def test_asset_summary_model_and_legacy_cache_payloads_are_compatible() -> None:
    summary = build_asset_quality_summary(
        [], asset_profile="none", archive_enabled=False
    )
    restored = Quality(asset_summary=asdict(summary))  # type: ignore[arg-type]
    legacy_model = Quality(asset_summary={})  # type: ignore[arg-type]
    legacy_cache = quality_from_payload(
        {
            "has_fulltext": True,
            "content_kind": "fulltext",
            "has_abstract": True,
        }
    )

    assert restored.asset_summary == summary
    assert legacy_model.asset_summary == AssetQualitySummary()
    assert legacy_cache.asset_summary == AssetQualitySummary()
