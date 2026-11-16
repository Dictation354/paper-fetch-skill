"""Shared single/batch output-file snapshot presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..manifest import (
    DEFAULT_MANIFEST_BUILDER_DEPENDENCIES,
    ManifestOutputArtifact,
    ManifestOutputArtifactSpec,
    snapshot_output_artifact,
)


def artifact_payload(artifact: ManifestOutputArtifact) -> dict[str, Any]:
    return {
        "path": artifact.path,
        "kind": artifact.kind,
        "route": artifact.route,
        "failure_code": artifact.failure_code,
        "size": artifact.size,
        "sha256": artifact.sha256,
        "completed_at": artifact.completed_at.isoformat(),
        "verification_status": artifact.verification_status.value,
    }


def fetch_output_artifacts(
    saved_path: Path | None,
    diagnostic_artifacts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    specs = []
    if saved_path is not None:
        specs.append(
            ManifestOutputArtifactSpec(
                path=str(saved_path.resolve()), kind="saved_markdown"
            )
        )
    for item in diagnostic_artifacts:
        path = item.get("path")
        if path:
            specs.append(
                ManifestOutputArtifactSpec(
                    path=str(Path(path).expanduser().resolve()),
                    kind="diagnostic",
                    route=item.get("route") or None,
                    failure_code=item.get("failure_code") or None,
                )
            )
    deps = DEFAULT_MANIFEST_BUILDER_DEPENDENCIES
    completed_at = deps.clock()
    return [
        artifact_payload(
            snapshot_output_artifact(spec, completed_at=completed_at, deps=deps)
        )
        for spec in specs
    ]
