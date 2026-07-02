from __future__ import annotations

from pathlib import Path

from paper_fetch.mcp._instructions import fetch_tool_description, server_instructions
from paper_fetch.provider_catalog import (
    PROVIDER_CATALOG,
    SOURCE_PROVIDER_MAP,
    ordered_provider_specs,
    provider_names,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_PROVIDER_PATH = REPO_ROOT / "docs" / "providers.md"
ONBOARDING_README_PATH = REPO_ROOT / "onboarding" / "README.md"
MCP_INSTRUCTIONS_PATH = REPO_ROOT / "src" / "paper_fetch" / "mcp" / "_instructions.py"
PROVIDER_CATALOG_PATH = REPO_ROOT / "src" / "paper_fetch" / "provider_catalog.py"
CLOAKBROWSER_PROVIDER_PATH = (
    REPO_ROOT / "src" / "paper_fetch" / "providers" / "_cloakbrowser.py"
)
SKILL_ENTRYPOINT_PATH = REPO_ROOT / "skills" / "paper-fetch-skill" / "SKILL.md"
BROWSER_FACT_DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "docs" / "deployment.md",
    REPO_ROOT / "docs" / "providers.md",
    REPO_ROOT / "docs" / "architecture" / "overview.md",
    REPO_ROOT / "skills" / "paper-fetch-skill" / "references" / "failure-handling.md",
    REPO_ROOT / "skills" / "paper-fetch-skill" / "references" / "tool-contract.md",
)
SOURCE_FACT_DOC_PATHS = (
    REPO_ROOT / "docs" / "providers.md",
    REPO_ROOT / "skills" / "paper-fetch-skill" / "references" / "tool-contract.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _browser_provider_specs():
    return tuple(
        spec for spec in ordered_provider_specs() if spec.requires_browser_runtime
    )


def _official_provider_specs():
    return tuple(spec for spec in ordered_provider_specs() if spec.official)


def _provider_is_mentioned(text: str, provider_name: str) -> bool:
    spec = PROVIDER_CATALOG[provider_name]
    lowered = text.lower()
    return provider_name.lower() in lowered or spec.display_name.lower() in lowered


def _section_after_anchor(text: str, anchor: str) -> str:
    marker = f'<a id="{anchor}"></a>'
    assert marker in text
    section = text.split(marker, 1)[1]
    endings = [
        index
        for index in (section.find("\n<a id="), section.find("\n## "))
        if index != -1
    ]
    return section[: min(endings)] if endings else section


def _manifest_provider_names() -> frozenset[str]:
    manifest_dir = REPO_ROOT / "onboarding" / "manifests"
    return frozenset(path.stem for path in manifest_dir.glob("*.yml"))


def test_browser_runtime_providers_are_declared_on_provider_specs() -> None:
    source = _read(PROVIDER_CATALOG_PATH)

    assert "_BROWSER_RUNTIME_PROVIDER_NAMES" not in source
    for spec in _browser_provider_specs():
        assert spec.requires_browser_runtime is True


def test_cloakbrowser_helper_does_not_keep_second_browser_provider_table() -> None:
    source = _read(CLOAKBROWSER_PROVIDER_PATH)

    assert "_BROWSER_WORKFLOW_PROVIDERS" not in source


def test_mcp_instructions_cover_runtime_provider_and_source_catalog() -> None:
    rendered = server_instructions() + "\n" + fetch_tool_description()

    missing_providers = [
        name for name in provider_names() if not _provider_is_mentioned(rendered, name)
    ]
    assert not missing_providers, (
        "MCP instructions must mention every runtime provider accepted by "
        "provider_hint/preferred_providers: " + ", ".join(missing_providers)
    )

    missing_browser = [
        spec.name
        for spec in _browser_provider_specs()
        if not _provider_is_mentioned(rendered, spec.name)
    ]
    assert not missing_browser, (
        "MCP instructions must mention every catalog browser runtime provider: "
        + ", ".join(missing_browser)
    )
    assert "ProviderSpec.requires_browser_runtime=True" in rendered

    missing_sources = [
        source for source in SOURCE_PROVIDER_MAP if source not in rendered
    ]
    assert not missing_sources, (
        "MCP instructions must cover public sources from SOURCE_PROVIDER_MAP: "
        + ", ".join(missing_sources)
    )


def test_human_docs_cover_catalog_browser_runtime_providers() -> None:
    for path in BROWSER_FACT_DOC_PATHS:
        text = _read(path)
        missing = [
            spec.name
            for spec in _browser_provider_specs()
            if not _provider_is_mentioned(text, spec.name)
        ]
        assert not missing, (
            f"{path.relative_to(REPO_ROOT)} must mention all catalog browser "
            "runtime providers: " + ", ".join(missing)
        )


def test_skill_entrypoint_uses_catalog_browser_runtime_boundary() -> None:
    text = _read(SKILL_ENTRYPOINT_PATH)

    assert "ProviderSpec.requires_browser_runtime=True" in text
    assert "provider_status()" in text
    listed = [
        spec.name
        for spec in _browser_provider_specs()
        if _provider_is_mentioned(text, spec.name)
    ]
    assert not listed, (
        "Thin SKILL.md should point at catalog-derived browser runtime policy "
        "instead of keeping a static provider table: " + ", ".join(listed)
    )


def test_human_docs_cover_public_source_provider_map() -> None:
    for path in SOURCE_FACT_DOC_PATHS:
        text = _read(path)
        missing = [source for source in SOURCE_PROVIDER_MAP if source not in text]
        assert not missing, (
            f"{path.relative_to(REPO_ROOT)} must mention every public source in "
            "SOURCE_PROVIDER_MAP: " + ", ".join(missing)
        )


def test_docs_provider_status_section_covers_official_provider_catalog() -> None:
    text = _read(DOCS_PROVIDER_PATH)
    section = _section_after_anchor(text, "provider-status-local-boundary")
    missing = [
        spec.name
        for spec in _official_provider_specs()
        if not _provider_is_mentioned(section, spec.name)
    ]

    assert not missing, (
        "docs/providers.md provider_status() section must mention every "
        "official provider from the runtime catalog: " + ", ".join(missing)
    )


def test_docs_providers_mentions_catalog_as_provider_fact_source() -> None:
    text = _read(DOCS_PROVIDER_PATH)

    assert "paper_fetch.provider_catalog.ProviderSpec" in text
    assert "SOURCE_PROVIDER_MAP" in text
    assert "official_provider_names()" in text


def test_onboarding_readme_manifest_entry_uses_manifest_directory_as_authority() -> (
    None
):
    text = _read(ONBOARDING_README_PATH)
    manifest_line = next(line for line in text.splitlines() if "[`manifests/`]" in line)

    assert "known-providers.yml" in manifest_line
    assert "例如" not in manifest_line
    explicitly_listed = [
        name
        for name in sorted(_manifest_provider_names())
        if _provider_is_mentioned(manifest_line, name)
    ]
    assert not explicitly_listed, (
        "onboarding/README.md manifests entry should point at the manifest "
        "directory/known-providers index instead of keeping a partial provider "
        "example list: " + ", ".join(explicitly_listed)
    )
