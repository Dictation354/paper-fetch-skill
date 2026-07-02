from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS_DIR = REPO_ROOT / "onboarding" / "manifests"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "golden_criteria"
UNIT_TESTS_DIR = REPO_ROOT / "tests" / "unit"

MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
BODY_BOUNDARY_RE = re.compile(
    r"(?im)^##\s+(?:references|figures?|figure captions?|supplementary|supporting information)\b"
)


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} must load as a mapping"
    return data


def _manifest_paths() -> tuple[Path, ...]:
    paths = tuple(sorted(MANIFESTS_DIR.glob("*.yml")))
    assert paths
    return paths


def _doi_slug(doi: str) -> str:
    return doi.replace("/", "_")


def _body_markdown(markdown: str) -> str:
    match = BODY_BOUNDARY_RE.search(markdown)
    return markdown[: match.start()] if match else markdown


def _provider_test_text(provider: str) -> str:
    texts: list[str] = []
    for path in sorted(UNIT_TESTS_DIR.glob("test*.py")):
        text = path.read_text(encoding="utf-8")
        if provider in text or f"provider={provider}" in text:
            texts.append(text)
    return "\n".join(texts)


def _marker_block(text: str, marker: str, *, line_count: int = 160) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if marker in line:
            end = min(len(lines), index + line_count)
            for cursor in range(index + 1, end):
                if lines[cursor].startswith(("def test_", "    def test_")):
                    end = cursor
                    break
            return "\n".join(lines[index:end])
    return ""


def test_provider_manifests_define_figure_asset_contracts() -> None:
    for manifest_path in _manifest_paths():
        manifest = _load_yaml(manifest_path)
        contract = manifest.get("asset_contract")
        assert isinstance(contract, dict), (
            f"{manifest_path}: asset_contract is required"
        )
        figures = contract.get("figures")
        assert isinstance(figures, dict), (
            f"{manifest_path}: asset_contract.figures is required"
        )

        inline = figures.get("inline")
        download = figures.get("download")
        purposes = figures.get("purposes")
        exception_reason = figures.get("exception_reason")
        assert inline in {"body", "not_applicable"}, (
            f"{manifest_path}: invalid figures.inline"
        )
        assert download in {"required", "not_applicable"}, (
            f"{manifest_path}: invalid figures.download"
        )
        assert isinstance(purposes, list) and purposes, (
            f"{manifest_path}: asset_contract.figures.purposes must list fixture purposes"
        )
        if inline == "not_applicable" or download == "not_applicable":
            assert isinstance(exception_reason, str) and exception_reason.strip(), (
                f"{manifest_path}: not_applicable figure contract needs exception_reason"
            )
        else:
            assert exception_reason is None, (
                f"{manifest_path}: fully applicable figure contract should use exception_reason: null"
            )

        samples = manifest["fixtures"]["doi_samples"]
        for purpose in purposes:
            assert purpose in samples, (
                f"{manifest_path}: unknown figure contract purpose {purpose!r}"
            )
            assert samples[purpose].get("doi"), (
                f"{manifest_path}: figure contract purpose {purpose!r} must point to a DOI fixture"
            )


def test_body_inline_figure_contracts_have_markdown_images_before_tail_sections() -> (
    None
):
    for manifest_path in _manifest_paths():
        manifest = _load_yaml(manifest_path)
        figures = manifest["asset_contract"]["figures"]
        if figures["inline"] != "body":
            continue
        for purpose in figures["purposes"]:
            doi = str(manifest["fixtures"]["doi_samples"][purpose]["doi"])
            markdown_path = FIXTURES_DIR / _doi_slug(doi) / "extracted.md"
            assert markdown_path.is_file(), f"{manifest_path}: missing {markdown_path}"
            markdown = markdown_path.read_text(encoding="utf-8", errors="replace")
            body = _body_markdown(markdown)
            assert MARKDOWN_IMAGE_RE.search(body), (
                f"{manifest_path}: {purpose}:{doi} must contain a Markdown image "
                "in body text before References/Figures/Supplementary tail sections"
            )
            tail = markdown[len(body) :]
            if MARKDOWN_IMAGE_RE.search(tail):
                assert MARKDOWN_IMAGE_RE.search(body), (
                    f"{manifest_path}: {purpose}:{doi} cannot rely only on tail figure images"
                )


def test_required_figure_download_contracts_have_provider_local_markers() -> None:
    for manifest_path in _manifest_paths():
        manifest = _load_yaml(manifest_path)
        provider = str(manifest["name"])
        figures = manifest["asset_contract"]["figures"]
        if figures["download"] != "required":
            continue

        marker = f"asset-download-contract: provider={provider}"
        test_text = _provider_test_text(provider)
        block = _marker_block(test_text, marker)
        assert block, (
            f"{manifest_path}: provider-local tests must contain marker {marker!r}"
        )
        assert "download_related_assets(" in block or ".fetch_result(" in block, (
            f"{manifest_path}: marker {marker!r} must cover a fetch/download call"
        )
        assert "path" in block and (
            "read_bytes" in block or "is_file" in block or "downloaded_bytes" in block
        ), f"{manifest_path}: marker {marker!r} must assert downloaded asset path/bytes"
        assert "asset_failures" in block or "artifacts.assets" in block, (
            f"{manifest_path}: marker {marker!r} must assert asset download result state"
        )
