from __future__ import annotations
import json
from tests.paths import SKILL_DIR
from paper_fetch.mcp.schemas import (
    FetchPaperRequest,
    FetchStrategyInput,
    BatchFetchRequest,
    BatchCheckRequest,
)
from paper_fetch.mcp.fetch_cache import request_cache_payload


def test_five_documented_tasks_use_native_presets():
    text = (SKILL_DIR / "references/presets.md").read_text()
    examples = [
        json.loads(block.split("```", 1)[0]) for block in text.split("```json\n")[1:]
    ]
    assert len(examples) == 5
    for value in examples:
        model = (
            BatchCheckRequest
            if "mode" in value
            else BatchFetchRequest
            if "queries" in value
            else FetchPaperRequest
        )
        # tool-only path is used for execution, not acquisition semantics
        model.model_validate({k: v for k, v in value.items() if k != "download_dir"})


def test_presets_expand_before_explicit_false_and_nested_strategy_overrides():
    temporary = FetchPaperRequest(query="paper")
    assert temporary.modes == ["markdown"] and temporary.no_download
    assert temporary.include_refs == "all" and temporary.max_tokens == "full_text"
    assert temporary.artifact_mode == "none" and not temporary.prefer_cache
    cache = FetchPaperRequest(query="paper", preset="cacheable_read")
    assert cache.prefer_cache and not cache.no_download and not cache.save_markdown
    archive = FetchPaperRequest(
        query="paper",
        preset="archive",
        save_markdown=False,
        prefer_cache=False,
        strategy=FetchStrategyInput(
            asset_profile="body", allow_metadata_only_fallback=False
        ),
    )
    assert not archive.save_markdown and not archive.prefer_cache
    assert not archive.no_download and archive.artifact_mode == "markdown-assets"
    assert not archive.strategy.allow_metadata_only_fallback
    explicit = FetchPaperRequest(
        query="paper",
        strategy={"asset_profile": "all"},
        no_download=True,
        artifact_mode="none",
    )
    assert explicit.no_download and explicit.artifact_mode == "none"


def test_batch_and_single_share_expansion_and_fingerprints_ignore_preset_name():
    values = {
        "preset": "archive",
        "strategy": {"asset_profile": "body"},
        "save_markdown": False,
    }
    batch = BatchFetchRequest(queries=["paper"], **values).to_fetch_request("paper")
    assert batch == FetchPaperRequest(query="paper", **values)
    first = FetchPaperRequest(query="paper")
    second = FetchPaperRequest(
        query="paper", preset="cacheable_read", prefer_cache=False, no_download=True
    )
    assert request_cache_payload(first) == request_cache_payload(second)


def test_fetch_scope_requires_request_or_explicit_configuration(tmp_path):
    import pytest
    from paper_fetch.mcp.fetch_tool import resolve_fetch_scope
    from paper_fetch.mcp.cache_payloads import _MCP_DEFAULT_DOWNLOAD_DIR

    request = FetchPaperRequest(query="10.1000/scope", preset="cacheable_read")
    with pytest.raises(ValueError, match="requires download_dir"):
        resolve_fetch_scope(
            request, runtime_env={}, download_dir=_MCP_DEFAULT_DOWNLOAD_DIR
        )
    assert (
        resolve_fetch_scope(
            request,
            runtime_env={"PAPER_FETCH_DOWNLOAD_DIR": str(tmp_path)},
            download_dir=_MCP_DEFAULT_DOWNLOAD_DIR,
        )
        == tmp_path.resolve()
    )
    archive = FetchPaperRequest(
        query="10.1000/scope",
        preset="archive",
        markdown_output_dir=str(tmp_path / "papers"),
    )
    assert (
        resolve_fetch_scope(
            archive, runtime_env={}, download_dir=_MCP_DEFAULT_DOWNLOAD_DIR
        )
        == (tmp_path / "papers").resolve()
    )
