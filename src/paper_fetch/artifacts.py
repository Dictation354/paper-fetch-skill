"""Artifact writing and download diagnostics policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .models import AssetProfile
from .utils import (
    build_output_path,
    extension_from_content_type,
    extend_unique,
    normalize_text,
    safe_text,
    sanitize_filename,
    save_payload,
)

ACCEPTABLE_PREVIEW_MIN_WIDTH = 300
ACCEPTABLE_PREVIEW_MIN_HEIGHT = 200


@dataclass(frozen=True)
class DownloadPolicy:
    """Controls whether provider artifacts are materialized locally."""

    download_dir: Path | None = None


@dataclass
class ArtifactStore:
    """Centralizes provider payload saves and artifact diagnostics."""

    policy: DownloadPolicy = field(default_factory=DownloadPolicy)

    @classmethod
    def from_download_dir(cls, download_dir: Path | None) -> "ArtifactStore":
        return cls(DownloadPolicy(download_dir=download_dir))

    @property
    def download_dir(self) -> Path | None:
        return self.policy.download_dir

    def save_provider_payload(
        self,
        provider_name: str,
        *,
        content: Any,
        doi: str | None,
        metadata: Mapping[str, Any],
    ) -> tuple[list[str], list[str]]:
        if content is None or not content.needs_local_copy:
            return [], []
        provider_slug = safe_text(provider_name or "provider").lower().replace(" ", "_") or "provider"
        provider_label = provider_slug.replace("_", " ").title()
        if self.download_dir is None:
            return [f"{provider_label} official PDF/binary was not written to disk because --no-download was set."], [
                f"download:{provider_slug}_skipped"
            ]
        saved_path = save_payload(
            build_output_path(
                self.download_dir,
                doi,
                safe_text(metadata.get("title")),
                content.content_type,
                content.source_url,
            ),
            content.body,
        )
        if saved_path:
            return [f"{provider_label} official full text was downloaded as PDF/binary to {saved_path}."], [
                f"download:{provider_slug}_saved"
            ]
        return [f"{provider_label} official full text was available only as PDF/binary and could not be written to disk."], [
            f"download:{provider_slug}_save_failed"
        ]

    def provider_html_output_path(
        self,
        provider_name: str,
        *,
        content: Any,
        doi: str | None,
        metadata: Mapping[str, Any],
    ) -> Path | None:
        if content is None or self.download_dir is None:
            return None
        if normalize_text(provider_name).lower() != "springer":
            return None
        if normalize_text(content.route_kind).lower() != "html":
            return None

        extension = extension_from_content_type(content.content_type, content.source_url).lower()
        if extension not in {".html", ".htm"}:
            return None

        article_slug = sanitize_filename(doi or safe_text(metadata.get("title")) or "article")
        if self.download_dir.name == article_slug:
            return self.download_dir / f"original{extension}"
        return self.download_dir / f"{article_slug}_original{extension}"

    def save_provider_html_payload(
        self,
        provider_name: str,
        *,
        content: Any,
        doi: str | None,
        metadata: Mapping[str, Any],
    ) -> tuple[list[str], list[str]]:
        output_path = self.provider_html_output_path(
            provider_name,
            content=content,
            doi=doi,
            metadata=metadata,
        )
        if output_path is None or content is None:
            return [], []
        save_payload(output_path, content.body)
        return [], [f"download:{normalize_text(provider_name).lower()}_html_saved"]

    def apply_provider_artifacts(
        self,
        *,
        provider_name: str,
        artifacts: Any,
        asset_profile: AssetProfile,
        warnings: list[str],
        source_trail: list[str],
    ) -> None:
        if self.download_dir is None:
            return
        if asset_profile == "none":
            extend_unique(source_trail, [f"download:{provider_name}_assets_skipped_profile_none"])
            return
        if artifacts.skip_warning:
            extend_unique(warnings, [artifacts.skip_warning])
            extend_unique(source_trail, [event.marker() for event in artifacts.skip_trace if event.marker()])
            return
        if artifacts.assets:
            extend_unique(source_trail, [f"download:{provider_name}_assets_saved_profile_{asset_profile}"])
            preview_assets = [
                asset
                for asset in artifacts.assets
                if normalize_text(asset.get("download_tier")).lower() == "preview"
            ]
            preview_accepted_count = sum(1 for asset in preview_assets if _preview_asset_accepted(asset))
            preview_fallback_count = len(preview_assets) - preview_accepted_count
            if preview_accepted_count:
                extend_unique(
                    warnings,
                    [
                        (
                            f"{provider_name.replace('_', ' ').title()} figure downloads used preview images for "
                            f"{preview_accepted_count} asset(s), but their saved dimensions met the acceptance threshold."
                        )
                    ],
                )
                extend_unique(source_trail, [f"download:{provider_name}_assets_preview_accepted"])
            if preview_fallback_count:
                extend_unique(
                    warnings,
                    [
                        (
                            f"{provider_name.replace('_', ' ').title()} figure downloads fell back to preview images for "
                            f"{preview_fallback_count} asset(s) because full-size/original downloads were unavailable."
                        )
                    ],
                )
                extend_unique(source_trail, [f"download:{provider_name}_assets_preview_fallback"])
        if artifacts.asset_failures:
            extend_unique(
                warnings,
                [
                    (
                        f"{provider_name.replace('_', ' ').title()} related assets were only partially downloaded "
                        f"({len(artifacts.asset_failures)} failed)."
                    )
                ],
            )
            extend_unique(source_trail, [f"download:{provider_name}_asset_failures"])


def _preview_asset_accepted(asset: Mapping[str, Any]) -> bool:
    if bool(asset.get("preview_accepted")):
        return True
    try:
        width = int(asset.get("width") or 0)
        height = int(asset.get("height") or 0)
    except (TypeError, ValueError):
        return False
    return width >= ACCEPTABLE_PREVIEW_MIN_WIDTH and height >= ACCEPTABLE_PREVIEW_MIN_HEIGHT
