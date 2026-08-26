"""Artifact writing and download diagnostics policies."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Literal
from collections.abc import Callable, Iterator, Mapping, Sequence

from filelock import FileLock
from platformdirs import user_runtime_path

from .config import APP_NAME
from .extraction.html.assets.dom import preview_dimensions_are_acceptable
from .models import ArticleModel, AssetProfile, AssetQualitySummary
from .provider_catalog import provider_persists_provider_html
from .reason_codes import PDF_FALLBACK
from .tracing import download_marker
from .utils import (
    _extract_year,
    build_output_path,
    extension_from_content_type,
    extend_unique,
    format_paper_stem,
    normalize_text,
    provider_display_name,
    safe_text,
)

ArtifactMode = Literal["markdown-assets", "all", "none"]
DEFAULT_ARTIFACT_MODE: ArtifactMode = "all"
ARTIFACT_LOCK_DIRNAME = "locks"


def artifact_file_lock_path(
    path: Path,
    *,
    scope: Literal["artifact", "run"] = "artifact",
) -> Path:
    """Return a stable path-scoped lock outside the user's output namespace."""

    digest = hashlib.sha256(
        str(path.expanduser().resolve(strict=False)).encode(
            "utf-8", errors="surrogatepass"
        )
    ).hexdigest()[:24]
    return (
        user_runtime_path(APP_NAME, appauthor=False)
        / ARTIFACT_LOCK_DIRNAME
        / f"{scope}-{digest}.lock"
    )


@dataclass(frozen=True)
class DownloadPolicy:
    """Controls whether provider artifacts are materialized locally."""

    download_dir: Path | None = None
    artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE

    def __post_init__(self) -> None:
        if self.artifact_mode not in {"markdown-assets", "all", "none"}:
            raise ValueError(
                "artifact_mode must be one of: markdown-assets, all, none."
            )

    @property
    def asset_download_dir(self) -> Path | None:
        if self.artifact_mode in {"markdown-assets", "all"}:
            return self.download_dir
        return None

    @property
    def allows_auxiliary_artifacts(self) -> bool:
        return self.artifact_mode == "all" and self.download_dir is not None

    @property
    def allows_http_disk_cache(self) -> bool:
        return self.artifact_mode == "all"

    @property
    def allows_structured_sidecars(self) -> bool:
        return self.artifact_mode == "all"

    @property
    def allows_provider_html(self) -> bool:
        return self.artifact_mode == "all" and self.download_dir is not None

    def allows_provider_payload(self, content: Any) -> bool:
        if self.download_dir is None or self.artifact_mode == "none":
            return False
        if self.artifact_mode == "all":
            return True
        return _is_pdf_fallback_content(content)


@dataclass
class ArtifactStore:
    """Centralizes provider payload saves and artifact diagnostics."""

    policy: DownloadPolicy = field(default_factory=DownloadPolicy)
    default_commit_guard: Callable[[], None] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @classmethod
    def from_download_dir(
        cls,
        download_dir: Path | None,
        *,
        artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE,
        commit_guard: Callable[[], None] | None = None,
    ) -> ArtifactStore:
        return cls(
            DownloadPolicy(download_dir=download_dir, artifact_mode=artifact_mode),
            default_commit_guard=commit_guard,
        )

    def _effective_commit_guard(
        self, commit_guard: Callable[[], None] | None
    ) -> Callable[[], None] | None:
        return commit_guard or self.default_commit_guard

    @staticmethod
    @contextlib.contextmanager
    def _commit_critical_section(
        guard: Callable[[], None] | None,
    ) -> Iterator[None]:
        critical_section = getattr(guard, "critical_section", None)
        if callable(critical_section):
            with critical_section():
                yield
            return
        if guard is not None:
            guard()
        yield

    @staticmethod
    def _fsync_parent(path: Path) -> None:
        """Best-effort directory durability after an atomic replace."""

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            directory_fd = os.open(path.parent, flags)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        except OSError:
            pass
        finally:
            os.close(directory_fd)

    @staticmethod
    def _matches_existing(path: Path, body: bytes) -> bool:
        try:
            if path.stat().st_size != len(body):
                return False
            existing_digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    existing_digest.update(block)
        except OSError:
            return False
        return existing_digest.digest() == hashlib.sha256(body).digest()

    @staticmethod
    def _files_match(left: Path, right: Path) -> bool:
        try:
            if left.stat().st_size != right.stat().st_size:
                return False
            digests = []
            for path in (left, right):
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                digests.append(digest.digest())
        except OSError:
            return False
        return digests[0] == digests[1]

    def _write_bytes_atomic(
        self,
        path: Path,
        body: bytes,
        *,
        overwrite: bool,
        commit_guard: Callable[[], None] | None,
    ) -> Path:
        """Durably replace one path using a unique same-directory staging file."""

        guard = self._effective_commit_guard(commit_guard)
        if guard is not None:
            guard()
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = artifact_file_lock_path(path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path)):
            if guard is not None:
                guard()
            if path.exists() and not overwrite:
                if self._matches_existing(path, body):
                    return path
                raise FileExistsError(
                    "refusing to overwrite existing artifact without explicit "
                    f"permission because content differs: {path}"
                )
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".part",
                dir=path.parent,
            )
            temporary_path = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                with self._commit_critical_section(guard):
                    os.replace(temporary_path, path)
                    self._fsync_parent(path)
            except BaseException:
                with contextlib.suppress(OSError):
                    temporary_path.unlink(missing_ok=True)
                raise
        return path

    @property
    def download_dir(self) -> Path | None:
        return self.policy.download_dir

    @property
    def artifact_mode(self) -> ArtifactMode:
        return self.policy.artifact_mode

    @property
    def asset_download_dir(self) -> Path | None:
        return self.policy.asset_download_dir

    @property
    def allows_auxiliary_artifacts(self) -> bool:
        return self.policy.allows_auxiliary_artifacts

    @property
    def allows_http_disk_cache(self) -> bool:
        return self.policy.allows_http_disk_cache

    @property
    def allows_structured_sidecars(self) -> bool:
        return self.policy.allows_structured_sidecars

    def write_text_file(
        self,
        path: Path,
        text: str,
        *,
        encoding: str = "utf-8",
        overwrite: bool = True,
        use_lock: bool = False,
        commit_guard: Callable[[], None] | None = None,
    ) -> Path:
        # ``use_lock`` is retained as a source-compatible argument. Every write is
        # now path-locked because callers cannot safely predict who else owns the
        # same DOI-derived output path.
        del use_lock
        return self._write_bytes_atomic(
            path,
            text.encode(encoding),
            overwrite=overwrite,
            commit_guard=commit_guard,
        )

    def write_bytes_file(
        self,
        path: Path,
        body: bytes,
        *,
        overwrite: bool = True,
        commit_guard: Callable[[], None] | None = None,
    ) -> Path:
        return self._write_bytes_atomic(
            path,
            body,
            overwrite=overwrite,
            commit_guard=commit_guard,
        )

    def publish_staged_file(
        self,
        staging_path: Path,
        path: Path,
        *,
        overwrite: bool = True,
        commit_guard: Callable[[], None] | None = None,
    ) -> Path:
        """Atomically publish an already flushed same-directory staging file."""

        staging_path = Path(staging_path)
        path = Path(path)
        if staging_path.parent.resolve(strict=False) != path.parent.resolve(
            strict=False
        ):
            raise ValueError("staging file must be in the destination directory")
        guard = self._effective_commit_guard(commit_guard)
        if guard is not None:
            guard()
        lock_path = artifact_file_lock_path(path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path)):
            if guard is not None:
                guard()
            if path.exists() and not overwrite:
                if self._files_match(path, staging_path):
                    staging_path.unlink(missing_ok=True)
                    return path
                raise FileExistsError(
                    "refusing to overwrite existing artifact without explicit "
                    f"permission because content differs: {path}"
                )
            with self._commit_critical_section(guard):
                os.replace(staging_path, path)
                self._fsync_parent(path)
        return path

    def write_json_file(
        self,
        path: Path,
        payload: Mapping[str, Any],
        *,
        overwrite: bool = True,
        use_lock: bool = False,
        commit_guard: Callable[[], None] | None = None,
    ) -> Path:
        return self.write_text_file(
            path,
            json.dumps(dict(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
            overwrite=overwrite,
            use_lock=use_lock,
            commit_guard=commit_guard,
        )

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
        provider_slug = (
            safe_text(provider_name or "provider").lower().replace(" ", "_")
            or "provider"
        )
        provider_label = provider_display_name(provider_slug)
        if self.download_dir is None:
            return [
                f"{provider_label} official PDF/binary was not written to disk because --no-download was set."
            ], [download_marker(provider_slug, "skipped")]
        if not self.policy.allows_provider_payload(content):
            return [], []
        naming_metadata = _payload_naming_metadata(content, metadata)
        output_path = build_output_path(
            self.download_dir,
            doi,
            safe_text(naming_metadata.get("title")),
            content.content_type,
            content.source_url,
            authors=naming_metadata.get("authors") or None,
            year=_extract_year(safe_text(naming_metadata.get("published")) or None),
        )
        if output_path is not None:
            saved_path = self.write_bytes_file(output_path, content.body)
            return [
                f"{provider_label} official full text was downloaded as PDF/binary to {saved_path}."
            ], [download_marker(provider_slug, "saved")]
        return [
            f"{provider_label} official full text was available only as PDF/binary and could not be written to disk."
        ], [download_marker(f"{provider_slug}_save_failed")]

    def provider_html_output_path(
        self,
        provider_name: str,
        *,
        content: Any,
        doi: str | None,
        metadata: Mapping[str, Any],
    ) -> Path | None:
        if (
            content is None
            or self.download_dir is None
            or not self.policy.allows_provider_html
        ):
            return None
        if not provider_persists_provider_html(provider_name):
            return None
        if normalize_text(content.route_kind).lower() != "html":
            return None

        extension = extension_from_content_type(
            content.content_type, content.source_url
        ).lower()
        if extension not in {".html", ".htm"}:
            return None

        article_slug = format_paper_stem(
            metadata.get("authors") or None,
            _extract_year(safe_text(metadata.get("published")) or None),
            safe_text(metadata.get("title")) or None,
            doi=doi,
        )
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
        self.write_bytes_file(output_path, content.body)
        return [], [
            download_marker(f"{normalize_text(provider_name).lower()}_html", "saved")
        ]

    def apply_provider_artifacts(
        self,
        *,
        provider_name: str,
        artifacts: Any,
        asset_profile: AssetProfile,
        warnings: list[str],
        source_trail: list[str],
    ) -> None:
        if self.asset_download_dir is None:
            return
        if asset_profile == "none":
            extend_unique(
                source_trail,
                [download_marker(f"{provider_name}_assets_skipped_profile_none")],
            )
            return
        skip_trace_markers = [
            event.marker() for event in artifacts.skip_trace if event.marker()
        ]
        if artifacts.skip_warning:
            extend_unique(warnings, [artifacts.skip_warning])
        if skip_trace_markers:
            extend_unique(source_trail, skip_trace_markers)
        if artifacts.skip_warning or artifacts.text_only:
            return
        if artifacts.assets:
            extend_unique(
                source_trail,
                [
                    download_marker(
                        f"{provider_name}_assets_saved_profile_{asset_profile}"
                    )
                ],
            )
            preview_assets = [
                asset
                for asset in artifacts.assets
                if normalize_text(asset.get("download_tier")).lower() == "preview"
            ]
            preview_accepted_count = sum(
                1 for asset in preview_assets if _preview_asset_accepted(asset)
            )
            preview_fallback_count = len(preview_assets) - preview_accepted_count
            if preview_accepted_count:
                extend_unique(
                    source_trail,
                    [download_marker(f"{provider_name}_assets_preview", "accepted")],
                )
            if preview_fallback_count:
                extend_unique(
                    warnings,
                    [
                        (
                            f"{provider_display_name(provider_name)} asset downloads fell back to preview images for "
                            f"{preview_fallback_count} asset(s) because full-size/original downloads were unavailable."
                        )
                    ],
                )
                extend_unique(
                    source_trail,
                    [download_marker(f"{provider_name}_assets_preview_fallback")],
                )
        if artifacts.asset_failures:
            asset_failure_message = (
                f"{provider_display_name(provider_name)} related assets were only partially downloaded "
                if artifacts.assets
                else f"{provider_display_name(provider_name)} related assets could not be downloaded "
            )
            extend_unique(
                warnings,
                [f"{asset_failure_message}({len(artifacts.asset_failures)} failed)."],
            )
            extend_unique(
                source_trail, [download_marker(f"{provider_name}_asset_failures")]
            )

    def audit_article_assets(
        self,
        article: ArticleModel,
        *,
        asset_profile: AssetProfile,
        asset_failures: Sequence[Mapping[str, Any]] | None = None,
        archive_enabled: bool | None = None,
    ) -> AssetQualitySummary:
        """Attach a pure, read-only asset audit without changing text quality."""

        from .quality.assets import build_asset_quality_summary

        summary = build_asset_quality_summary(
            article.assets,
            asset_failures=(
                asset_failures
                if asset_failures is not None
                else article.quality.asset_failures
            ),
            asset_profile=asset_profile,
            archive_enabled=(
                self.asset_download_dir is not None
                if archive_enabled is None
                else archive_enabled
            ),
            base_dir=self.download_dir,
        )
        article.quality.asset_summary = summary
        return summary


def _preview_asset_accepted(asset: Mapping[str, Any]) -> bool:
    if bool(asset.get("preview_accepted")):
        return True
    try:
        width = int(asset.get("width") or 0)
        height = int(asset.get("height") or 0)
    except (TypeError, ValueError):
        return False
    return preview_dimensions_are_acceptable(width, height)


def _payload_naming_metadata(
    content: Any, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    naming_metadata = dict(metadata)
    content_metadata = getattr(content, "merged_metadata", None)
    if not isinstance(content_metadata, Mapping):
        return naming_metadata
    for key, value in content_metadata.items():
        if value not in (None, "", [], {}):
            naming_metadata[str(key)] = value
    return naming_metadata


def _is_pdf_fallback_content(content: Any) -> bool:
    return normalize_text(getattr(content, "route_kind", "")).lower() == PDF_FALLBACK


__all__ = [
    "DEFAULT_ARTIFACT_MODE",
    "ArtifactMode",
    "ArtifactStore",
    "DownloadPolicy",
]
