from __future__ import annotations

from pathlib import Path

from paper_fetch.mcp._instructions import fetch_tool_description, server_instructions
from paper_fetch.mcp.provider_catalog import PROVIDER_CATALOG_RESOURCE_URI
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
PLAYWRIGHT_PROVIDER_PATH = (
    REPO_ROOT / "src" / "paper_fetch" / "providers" / "_playwright_browser.py"
)
SKILL_ENTRYPOINT_PATH = REPO_ROOT / "skills" / "paper-fetch-skill" / "SKILL.md"
CLI_DOC_PATH = REPO_ROOT / "docs" / "cli.md"
DEPLOYMENT_DOC_PATH = REPO_ROOT / "docs" / "deployment.md"
ENVIRONMENT_REFERENCE_PATH = (
    REPO_ROOT / "skills" / "paper-fetch-skill" / "references" / "environment.md"
)
BROWSER_FACT_DOC_PATHS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "docs" / "deployment.md",
    REPO_ROOT / "docs" / "providers.md",
    REPO_ROOT / "docs" / "architecture" / "overview.md",
)
SOURCE_FACT_DOC_PATHS = (REPO_ROOT / "docs" / "providers.md",)


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


def test_camoufox_helper_does_not_keep_second_browser_provider_table() -> None:
    source = _read(PLAYWRIGHT_PROVIDER_PATH)

    assert "_BROWSER_WORKFLOW_PROVIDERS" not in source


def test_mcp_instructions_delegate_runtime_facts_to_dynamic_catalog() -> None:
    instructions = server_instructions()
    fetch_description = fetch_tool_description()
    rendered = instructions + "\n" + fetch_description

    assert PROVIDER_CATALOG_RESOURCE_URI in instructions
    assert PROVIDER_CATALOG_RESOURCE_URI in fetch_description
    assert "ProviderSpec.requires_browser_runtime=True" not in rendered
    assert all(source not in rendered for source in SOURCE_PROVIDER_MAP)
    assert all(f"`{name}`" not in rendered for name in provider_names())


def test_tool_contract_uses_dynamic_catalog_without_static_route_table() -> None:
    tool_contract = _read(
        REPO_ROOT / "skills/paper-fetch-skill/references/tool-contract.md"
    )

    assert "## Dynamic Provider Catalog" in tool_contract
    assert PROVIDER_CATALOG_RESOURCE_URI in tool_contract
    assert "## Provider Notes" not in tool_contract
    assert all(source not in tool_contract for source in SOURCE_PROVIDER_MAP)


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


def test_skill_failure_policy_uses_dynamic_catalog_without_provider_list() -> None:
    text = _read(
        REPO_ROOT
        / "skills"
        / "paper-fetch-skill"
        / "references"
        / "failure-handling.md"
    )

    assert PROVIDER_CATALOG_RESOURCE_URI in text
    listed = [
        spec.name
        for spec in _browser_provider_specs()
        if _provider_is_mentioned(text, spec.name)
    ]
    assert not listed, (
        "Skill failure policy must read the dynamic catalog instead of copying "
        "browser providers: " + ", ".join(listed)
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


def test_diagnostics_docs_define_static_live_auth_layers_and_secret_safe_sources() -> (
    None
):
    providers = _read(DOCS_PROVIDER_PATH)
    cli = _read(CLI_DOC_PATH)
    deployment = _read(DEPLOYMENT_DOC_PATH)
    environment = _read(ENVIRONMENT_REFERENCE_PATH)

    assert 'provider_status(provider=None, group=None, detail="full")' in providers
    assert 'detail="compact"' in providers
    assert "live_network_checked=false" in providers
    assert "process env > 显式 `env_file`" in providers
    assert "不包含变量值或配置文件路径" in providers
    assert "`provider_status` / `doctor`" in providers
    assert "→ `browser-preflight`" in providers
    assert "→ `auth`" in providers

    assert "paper-fetch doctor --group browser --json" in cli
    assert "退出码为 `0=ready`、`1=degraded`、`2=error`" in cli
    assert "不回显 token、cookie、endpoint" in cli
    assert "paper-fetch doctor --json" in deployment
    assert "不启动浏览器、不请求出版社页面" in deployment

    assert "process environment > an explicit `env_file`" in environment
    assert (
        "token, cookie, endpoint, path, and other values are never echoed"
        in environment
    )
    for variable in (
        "PAPER_FETCH_IMAGE_TOOLS_DIR",
        "PAPER_FETCH_GHOSTSCRIPT_BIN",
        "PAPER_FETCH_VIPS_BIN",
        "PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS",
    ):
        assert variable in environment


def test_browser_preflight_docs_define_shared_core_statuses_and_side_effects() -> None:
    providers = _read(DOCS_PROVIDER_PATH)
    cli = _read(CLI_DOC_PATH)
    deployment = _read(DEPLOYMENT_DOC_PATH)
    environment = _read(ENVIRONMENT_REFERENCE_PATH)
    tool_contract = _read(
        REPO_ROOT / "skills/paper-fetch-skill/references/tool-contract.md"
    )
    architecture = _read(REPO_ROOT / "docs/architecture/overview.md")

    assert "MCP `browser_preflight(provider=None" in providers
    assert "ready/challenge/auth_required/runtime_error/cancelled" in providers
    assert "save_storage_state=false" in providers
    assert "open-world、非只读和非 idempotent" in providers
    assert "MCP 的 `browser_preflight` 直接调用同一个 preflight 核心" in cli
    assert "不运行 PDF fallback 或自动 auth" in deployment
    assert "MCP preflight is open-world" in environment
    assert "## Browser Preflight Contract" in tool_contract
    assert "`pdf_fallback_attempted=false`" in tool_contract
    assert "`auth_attempted=false`" in tool_contract
    assert (
        "run_browser_provider_preflight()` 为唯一 orchestration owner" in architecture
    )


def test_cache_query_docs_distinguish_entries_from_current_request() -> None:
    providers = _read(DOCS_PROVIDER_PATH)
    tool_contract = _read(
        REPO_ROOT / "skills/paper-fetch-skill/references/tool-contract.md"
    )
    architecture = _read(REPO_ROOT / "docs/architecture/overview.md")

    assert '`detail="compact"`' in providers
    assert "`request_satisfied=true`" in providers
    assert "它只总结当前快照，不证明任意未来请求" in providers
    assert "## Cache Query Contract" in tool_contract
    assert '`status="hit"` 只表示' in tool_contract
    assert "cached_request_matches()" in tool_contract
    assert "当前索引/sidecar 快照的摘要" in tool_contract
    assert '`get_cached(detail="compact")`' in architecture
    assert "manifest canonical hash" in architecture


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
