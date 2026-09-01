from __future__ import annotations

import json
from pathlib import Path

from tests.paths import SKILL_DIR


PRESETS_PATH = SKILL_DIR / "references" / "presets.md"


def _json_examples(path: Path) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    active: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if active is None:
            if line.strip() == "```json":
                active = []
            continue
        if line.strip() == "```":
            examples.append(json.loads("\n".join(active)))
            active = None
            continue
        active.append(line)
    return examples


def _preset_behavior(payload: dict[str, object]) -> tuple[object, ...]:
    if payload.get("mode") == "metadata":
        return ("batch_triage", False, False, "none", "none")

    strategy = payload.get("strategy")
    assert isinstance(strategy, dict)
    asset_profile = strategy.get("asset_profile")
    if "queries" in payload:
        return (
            "batch_archive",
            payload.get("save_markdown"),
            payload.get("no_download"),
            payload.get("artifact_mode"),
            asset_profile,
        )

    save_markdown = payload.get("save_markdown")
    prefer_cache = payload.get("prefer_cache")
    if save_markdown:
        name = "single_archive"
    elif prefer_cache:
        name = "cacheable_read"
    else:
        name = "temporary_read"
    return (
        name,
        save_markdown,
        payload.get("no_download"),
        payload.get("artifact_mode"),
        asset_profile,
    )


def test_five_presets_keep_their_public_save_cache_and_asset_behavior() -> None:
    behaviors = {_preset_behavior(payload) for payload in _json_examples(PRESETS_PATH)}

    assert behaviors == {
        ("temporary_read", False, True, "none", "none"),
        ("cacheable_read", False, False, "none", "none"),
        ("single_archive", True, True, "none", "none"),
        ("batch_triage", False, False, "none", "none"),
        ("batch_archive", True, True, "none", "none"),
    }
