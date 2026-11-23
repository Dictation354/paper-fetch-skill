"""Versioned CLI receipts and durable, per-input reading artifacts."""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import UUID

from ..acquisition import is_pdf_article
from ..artifacts import ArtifactStore
from ..manifest import (
    ManifestOutputArtifact,
    ManifestOutputArtifactSpec,
    ManifestRecord,
)
from ..models import TRUNCATION_WARNING, RenderOptions
from ..models.markdown import iter_markdown_images
from ..redaction import is_sensitive_configuration_name, redact_text_for_diagnostics
from ..targeted_assets import asset_urls, context_from_envelope
from ..workflow.rendering import relative_asset_link, rewrite_markdown_asset_links
from .acceptance_payloads import compact_acceptance_payload

CLI_RECEIPT_SCHEMA_VERSION = 2
_ATX_HEADING = re.compile(r" {0,3}(#{1,6})(?:[ \t]+(.*)|$)")
_CLOSING_HASHES = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
_CODE_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)")
_SETEXT_UNDERLINE = re.compile(r" {0,3}(=+|-+)[ \t]*")
_NON_PARAGRAPH = re.compile(r" {0,3}(?:[>#<]|(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]|$))")


def run_receipt_directory(output_dir: Path, run_id: UUID) -> Path:
    return output_dir / ".paper-fetch-results" / str(run_id)


def section_index(markdown: str) -> dict[str, Any]:
    lines = markdown.removesuffix("\n").split("\n") if markdown else []
    body_start = 0
    if lines and lines[0].rstrip() == "---":
        body_start = next(
            (
                index + 1
                for index, line in enumerate(lines[1:], 1)
                if line.rstrip() in {"---", "..."}
            ),
            0,
        )
    sections: list[dict[str, Any]] = []
    fence = ""
    paragraph: list[str] = []
    for line_number, raw_line in enumerate(lines[body_start:], body_start + 1):
        line = raw_line.removesuffix("\r")
        marker = _CODE_FENCE.fullmatch(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
            continue
        if marker and (marker[1][0] == "~" or "`" not in marker[2]):
            fence = marker[1]
            paragraph.clear()
            continue
        heading = _ATX_HEADING.fullmatch(line)
        underline = _SETEXT_UNDERLINE.fullmatch(line)
        start_line = line_number
        if heading:
            level = len(heading[1])
            title = _CLOSING_HASHES.sub("", heading[2] or "").strip()
        elif underline and paragraph:
            start_line -= len(paragraph)
            level = 1 if underline[1].startswith("=") else 2
            title = " ".join(paragraph)
        else:
            if (
                line.strip()
                and not line.startswith(("    ", "\t"))
                and not _NON_PARAGRAPH.match(line)
            ):
                paragraph.append(line.strip())
            else:
                paragraph.clear()
            continue
        paragraph.clear()
        if sections:
            sections[-1]["end_line"] = start_line - 1
        sections.append(
            {
                "title": title,
                "level": level,
                "start_line": start_line,
                "end_line": len(lines),
            }
        )
    return {"schema_version": 1, "sections": sections}


def public_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): public_diagnostics(v)
            for k, v in value.items()
            if not is_sensitive_configuration_name(str(k))
            and str(k).lower()
            not in {
                "authorization",
                "proxy-authorization",
                "browser_context_seed",
                "storage_state",
                "headers",
                "body",
            }
        }
    if isinstance(value, (list, tuple)):
        return [public_diagnostics(item) for item in value]
    if isinstance(value, str):
        return redact_text_for_diagnostics(value)
    return value


def _formula_body_positions(
    assets: list[dict[str, Any]], markdown: str, *, body: Path
) -> list[dict[str, Any]]:
    by_reference: dict[str, set[int]] = defaultdict(set)
    for index, asset in enumerate(assets):
        if asset["kind"] != "formula":
            continue
        references = asset_urls(asset)
        if local_link := relative_asset_link(asset.get("path"), target_path=body):
            references.add(local_link)
        for reference in references:
            by_reference[reference].add(index)

    if not by_reference:
        return assets
    line_starts = [0, *(match.end() for match in re.finditer("\n", markdown))]
    positions: dict[int, list[dict[str, int]]] = defaultdict(list)
    for image in iter_markdown_images(markdown):
        matches = by_reference.get(image.url)
        if not matches or len(matches) != 1:
            continue
        line = bisect_right(line_starts, image.start)
        positions[next(iter(matches))].append(
            {"line": line, "column": image.start - line_starts[line - 1] + 1}
        )
    return [
        {**asset, "body_positions": positions[index]} if index in positions else asset
        for index, asset in enumerate(assets)
    ]


def save_reading_artifacts(
    directory: Path,
    *,
    envelope: Any = None,
    error: Any = None,
) -> list[ManifestOutputArtifactSpec]:
    store = ArtifactStore.from_download_dir(directory)
    directory.mkdir(parents=True, exist_ok=True)
    artifacts: list[ManifestOutputArtifactSpec] = []
    body = directory / "body.md"
    markdown = None
    if envelope is not None and envelope.markdown is not None:
        markdown = rewrite_markdown_asset_links(
            envelope.markdown, envelope, target_path=body, render=RenderOptions()
        )
        store.write_text_file(body, markdown)
        sections = store.write_json_file(
            directory / "sections.json", section_index(markdown)
        )
        artifacts.extend(
            (
                ManifestOutputArtifactSpec(
                    path=str(body.resolve()), kind="reading_markdown"
                ),
                ManifestOutputArtifactSpec(
                    path=str(sections.resolve()), kind="section_index"
                ),
            )
        )
    if envelope is not None:
        state = context_from_envelope(envelope)
        assets = state.assets
        if (
            markdown
            and state.provider == "wiley"
            and state.route_kind == "html"
            and not is_pdf_article(envelope.article)
        ):
            assets = _formula_body_positions(assets, markdown, body=body)
        # These descriptors are sufficient for selective downloads; never persist browser seeds.
        index = store.write_json_file(
            directory / "images.json",
            {
                "schema_version": 1,
                "doi": state.doi,
                "provider": state.provider,
                "source_url": state.source_url,
                "metadata": state.metadata,
                "route_kind": state.route_kind,
                "discovery_complete": state.discovery_complete,
                "assets": assets,
            },
        )
        artifacts.append(
            ManifestOutputArtifactSpec(path=str(index.resolve()), kind="image_index")
        )
    diagnostics = store.write_json_file(
        directory / "diagnostics.json",
        public_diagnostics(
            {
                "diagnostics": envelope.diagnostics,
                "trace": envelope.to_dict().get("trace"),
                "warnings": envelope.quality.warnings,
            }
            if envelope is not None
            else error or {}
        ),
    )
    artifacts.append(
        ManifestOutputArtifactSpec(path=str(diagnostics.resolve()), kind="diagnostic")
    )
    return artifacts


def reading_body_artifact(record: ManifestRecord) -> ManifestOutputArtifact | None:
    return next(
        (
            artifact
            for artifact in record.output_artifacts
            if artifact.kind == "reading_markdown"
        ),
        None,
    )


def section_index_artifact(record: ManifestRecord) -> ManifestOutputArtifact | None:
    return next(
        (
            artifact
            for artifact in record.output_artifacts
            if artifact.kind == "section_index"
        ),
        None,
    )


def receipt_from_record(record: ManifestRecord, manifest: Path) -> dict[str, Any]:
    def paths(*kinds: str) -> list[str]:
        return [
            str(Path(a.path).expanduser().resolve())
            for a in record.output_artifacts
            if a.kind in kinds
        ]

    body = reading_body_artifact(record)
    sections = section_index_artifact(record)
    truncated = TRUNCATION_WARNING in record.warnings
    error = record.error.model_dump(mode="json") if record.error is not None else None
    provenance = record.acceptance.provenance
    return {
        "schema_version": CLI_RECEIPT_SCHEMA_VERSION,
        "contract": "paper-fetch/receipt",
        "index": record.index,
        "query": record.request.query,
        "status": record.record_status.value,
        "target_satisfied": target_satisfied(record),
        "error": (
            public_diagnostics(
                {
                    name: error.get(name)
                    for name in (
                        "status",
                        "reason",
                        "provider",
                        "route",
                        "stage",
                        "http_status",
                        "retryable",
                    )
                }
            )
            if error is not None
            else None
        ),
        "identity": record.acceptance.identity.model_dump(
            mode="json",
            include={
                "status",
                "doi",
                "expected_doi",
                "title",
                "candidate_count",
                "codes",
            },
        ),
        "doi": record.acceptance.identity.doi,
        "acceptance": compact_acceptance_payload(record.acceptance),
        "content_kind": record.acceptance.content.status.value,
        "source": provenance.source,
        "acquisition": (
            asdict(provenance.acquisition) if provenance.acquisition else None
        ),
        "body_path": str(Path(body.path).expanduser().resolve()) if body else None,
        "manifest_path": str(manifest.resolve()),
        "diagnostic_paths": paths("diagnostic"),
        "image_index_path": next(iter(paths("image_index")), None),
        "section_index_path": (
            str(Path(sections.path).expanduser().resolve()) if sections else None
        ),
        "output_paths": paths(
            "primary_markdown", "primary_json", "primary_both", "saved_markdown"
        ),
        "truncated": truncated,
        "truncation_reason": "max_tokens" if truncated else None,
        "fallback_codes": list(provenance.fallback_codes),
        "warning_codes": list(provenance.warning_codes),
        "failure_codes": list(provenance.failure_codes),
    }


def target_satisfied(record: ManifestRecord) -> bool:
    if record.error is not None:
        return False
    if record.acceptance.target == "supplementary":
        return record.acceptance.fetch.status.value == "ok"
    return record.acceptance.content.has_fulltext


__all__ = [
    "CLI_RECEIPT_SCHEMA_VERSION",
    "public_diagnostics",
    "reading_body_artifact",
    "receipt_from_record",
    "run_receipt_directory",
    "save_reading_artifacts",
    "section_index",
    "section_index_artifact",
    "target_satisfied",
]
