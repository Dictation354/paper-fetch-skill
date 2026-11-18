"""Versioned CLI receipts and durable, per-input reading artifacts."""

from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
from typing import Any

from ..artifacts import ArtifactStore
from ..manifest import ManifestOutputArtifactSpec, ManifestRecord
from ..models import TRUNCATION_WARNING
from ..redaction import is_sensitive_configuration_name, redact_text_for_diagnostics
from .acceptance_payloads import compact_acceptance_payload

CLI_RECEIPT_SCHEMA_VERSION = 1


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


def save_reading_artifacts(directory: Path, *, envelope=None, error=None):
    from ..targeted_assets import context_from_envelope

    store = ArtifactStore.from_download_dir(directory)
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = []
    if envelope is not None and envelope.markdown is not None:
        from ..workflow.rendering import rewrite_markdown_asset_links
        from ..models import RenderOptions

        body = directory / "body.md"
        store.write_text_file(
            body,
            rewrite_markdown_asset_links(
                envelope.markdown, envelope, target_path=body, render=RenderOptions()
            ),
        )
        artifacts.append(
            ManifestOutputArtifactSpec(
                path=str(body.resolve()), kind="reading_markdown"
            )
        )
    if envelope is not None:
        state = context_from_envelope(envelope)
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
                "assets": state.assets,
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


def receipt_from_record(record: ManifestRecord, manifest: Path) -> dict[str, Any]:
    def paths(*kinds):
        return [
            str(Path(a.path).expanduser().resolve())
            for a in record.output_artifacts
            if a.kind in kinds
        ]

    body_paths = paths("reading_markdown") or paths(
        "saved_markdown", "primary_markdown"
    )
    truncated = TRUNCATION_WARNING in record.warnings
    error = record.error.model_dump(mode="json") if record.error is not None else None
    return {
        "schema_version": CLI_RECEIPT_SCHEMA_VERSION,
        "contract": "paper-fetch/receipt",
        "index": record.index,
        "query": record.query,
        "status": record.record_status.value,
        "target_satisfied": target_satisfied(record),
        "error": public_diagnostics(
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
        else None,
        "identity": record.identity.model_dump(mode="json"),
        "doi": record.doi,
        "acceptance": compact_acceptance_payload(record.acceptance),
        "content_kind": record.acceptance.content.status.value,
        "source": record.source,
        "acquisition": asdict(record.acquisition) if record.acquisition else None,
        "body_path": body_paths[0] if body_paths else None,
        "manifest_path": str(manifest.resolve()),
        "diagnostic_paths": paths("diagnostic"),
        "image_index_path": next(iter(paths("image_index")), None),
        "output_paths": paths(
            "primary_markdown", "primary_json", "primary_both", "saved_markdown"
        ),
        "truncated": truncated,
        "truncation_reason": "max_tokens" if truncated else None,
        "fallback_codes": list(record.fallback_codes),
        "warning_codes": list(record.warning_codes),
        "failure_codes": list(record.failure_codes),
    }


def target_satisfied(record: ManifestRecord) -> bool:
    if record.error is not None:
        return False
    if record.acceptance.target == "supplementary":
        return record.acceptance.fetch.status.value == "ok"
    return record.acceptance.content.has_fulltext
