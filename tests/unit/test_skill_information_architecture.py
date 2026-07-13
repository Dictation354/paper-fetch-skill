from __future__ import annotations

from tests.paths import REPO_ROOT, SKILL_DIR
from tests.skill_bundle_links import REQUIRED_REFERENCE_FILES, skill_bundle_link_issues


REFERENCES = SKILL_DIR / "references"


def _read(relative_path: str) -> str:
    return (SKILL_DIR / relative_path).read_text(encoding="utf-8")


def _bundle_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SKILL_DIR.rglob("*.md"))
        if path.is_file()
    )


def test_source_skill_links_are_self_contained_complete_and_reachable() -> None:
    assert skill_bundle_link_issues(SKILL_DIR) == []
    assert {path.name for path in REFERENCES.glob("*.md")} == set(
        REQUIRED_REFERENCE_FILES
    )


def test_cli_workflow_is_a_normal_surface_with_only_a_narrow_fallback() -> None:
    workflow = _read("references/cli-workflow.md")
    bundle = _bundle_text()

    assert not (REFERENCES / "cli-fallback.md").exists()
    assert "CLI 是单篇/批量本地归档、shell 自动化" in workflow
    assert "不是 MCP 失败后的专用 fallback" in workflow
    assert "## 窄 fallback" in workflow
    assert "paper-fetch fetch --query-file" in workflow
    assert "paper-fetch manifest audit" in workflow
    assert "--resume ./papers/run-manifest.json" in workflow
    assert "python3 - ./papers/batch-results.jsonl" in workflow
    assert "python3 -m paper_fetch.cli" in workflow
    assert "jq " not in bundle
    assert "../../../docs" not in bundle


def test_skill_entrypoint_directly_navigates_every_critical_reference() -> None:
    skill = _read("SKILL.md")

    for filename in REQUIRED_REFERENCE_FILES:
        assert f"references/{filename}" in skill
    assert len(skill.splitlines()) <= 80
    assert "## BLOCKING 白名单" not in skill
    assert "### 失败决策表" not in skill


def test_prompt_templates_are_not_described_as_tools_and_have_equivalent_flows() -> (
    None
):
    contract = _read("references/tool-contract.md")
    tools_section, prompts_and_after = contract.split("## MCP Prompts（不是 Tools）", 1)
    prompts_section = prompts_and_after.split("\n## ", 1)[0]

    assert "summarize_paper" not in tools_section
    assert "verify_citation_list" not in tools_section
    assert "不是普通 tool" in prompts_section
    assert "不得把它们放进 `tools/call`" in prompts_section
    assert "不支持 MCP prompts 的宿主使用等价工具流程" in prompts_section
    for tool_name in (
        "resolve_paper",
        "get_cached",
        "fetch_paper",
        "batch_resolve",
        "batch_check",
        "batch_fetch",
    ):
        assert tool_name in prompts_section


def test_environment_documents_precedence_offline_wrapper_and_local_tooling() -> None:
    environment = _read("references/environment.md")

    assert (
        "进程环境 > 调用方显式 `env_file` > `PAPER_FETCH_ENV_FILE` 指向的文件 "
        "> platformdirs 用户配置 > 内置默认值"
    ) in environment
    assert "<install-root>/offline.env" in environment
    assert "--reuse-env-file <path>" in environment
    assert "resource://paper-fetch/provider-catalog" in environment
    for variable in (
        "PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT",
        "CLOAKBROWSER_CDP_ENDPOINT",
        "CLOAKBROWSER_BINARY_PATH",
        "CLOAKBROWSER_PROFILE_DIR",
        "CLOAKBROWSER_USER_DATA_DIR",
        "CLOAKBROWSER_HEADLESS",
        "CLOAKBROWSER_TIMEOUT_MS",
        "PAPER_FETCH_IMAGE_TOOLS_DIR",
        "PAPER_FETCH_GHOSTSCRIPT_BIN",
        "PAPER_FETCH_VIPS_BIN",
        "PAPER_FETCH_EPS_DPI",
        "PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS",
        "PAPER_FETCH_FORMULA_TOOLS_DIR",
        "MATHML_CONVERTER_BACKEND",
        "TEXMATH_BIN",
        "MATHML_TO_LATEX_NODE_BIN",
        "MATHML_CONVERSION_CACHE_SIZE",
    ):
        assert f"`{variable}" in environment
    for diagnostic in (
        "paper-fetch doctor --json",
        'provider_status(detail="full")',
        "paper-fetch browser-preflight",
        "browser_preflight(provider=...)",
        "paper-fetch-install-image-tools",
        "paper-fetch-install-formula-tools",
    ):
        assert diagnostic in environment
    assert 'ELSEVIER_API_KEY="' not in environment
    assert 'WILEY_TDM_CLIENT_TOKEN="' not in environment


def test_acceptance_reference_requires_real_path_hash_and_gitignored_checks() -> None:
    acceptance = _read("references/acceptance.md")

    for facet in (
        "`overall`",
        "`identity`",
        "`fetch`",
        "`content`",
        "`asset`",
        "`output`",
        "`provenance`",
    ):
        assert facet in acceptance
    assert "`.gitignore`" in acceptance
    assert "当前文件 size/SHA-256" in acceptance
    assert "python3 - ./papers/example.md" in acceptance
    assert "paper-fetch manifest audit" in acceptance
    assert "完整 1-based index 集合" in acceptance


def test_main_docs_cross_link_to_self_contained_skill_references() -> None:
    expected_links = {
        "docs/cli.md": ("cli-workflow.md", "presets.md", "acceptance.md"),
        "docs/providers.md": ("environment.md",),
        "docs/deployment.md": ("environment.md", "cli-workflow.md"),
    }
    for relative_path, filenames in expected_links.items():
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for filename in filenames:
            assert f"../skills/paper-fetch-skill/references/{filename}" in text
