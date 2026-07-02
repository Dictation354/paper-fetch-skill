from __future__ import annotations

import re
import shlex
import subprocess
import warnings
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
AI_ONBOARDING_DIR = REPO_ROOT / "onboarding"
HARD_CONSTRAINTS_PATH = AI_ONBOARDING_DIR / "hard-constraints.md"
PROVIDER_DEVELOPMENT_PATH = REPO_ROOT / "docs" / "provider-development.md"
ADDING_PROVIDER_PATH = REPO_ROOT / "docs" / "adding-a-provider.md"
HUMAN_DOC_PATHS = (PROVIDER_DEVELOPMENT_PATH, ADDING_PROVIDER_PATH)
AI_ONBOARDING_INDEX_LINK = "../onboarding/README.md"
AI_AUTHORITY_REQUIRED_LINKS = (
    "../onboarding/coordinator-spec.md",
    "../onboarding/provider-manifest.md",
    "../onboarding/provider-manifest.schema.json",
    "../onboarding/agent-task-brief.md",
    "../onboarding/hard-constraints.md",
    "../onboarding/acceptance.md",
)
HUMAN_ONLY_API_ALLOWLIST = frozenset(
    {
        "ACCESS_GATE_LABELS",
        "ACCESS_GATE_PATTERNS",
        "ArticleModel",
        "ArticleModel.source",
        "ArtifactStore",
        "AssetRetryPolicy",
        "DEFAULT_FULLTEXT_TIMEOUT_SECONDS",
        "FetchEnvelope",
        "Figures",
        "HttpTransport",
        "MARKDOWN_ACCESS_NOISE_LABELS",
        "MdpiClient",
        "NewpubClient",
        "NotImplementedError",
        "PROVIDER_CATALOG",
        "ProviderArtifacts",
        "ProviderBundle",
        "ProviderContent",
        "ProviderContent.diagnostics",
        "ProviderFailure",
        "ProviderFailure.code",
        "ProviderFetchResult",
        "ProviderHtmlRules",
        "ProviderHtmlRules.availability",
        "ProviderSpec",
        "PdfFallbackStrategy",
        "RawFulltextPayload",
        "RuntimeContext",
        "RuntimeContext.transport",
        "Tables",
        "WaterfallStep",
        "_X_author_",
        "_doi_",
        "_doi_pdf_candidate",
        "_header_value",
        "_render_",
        "_render_table_markdown",
        "register_provider_bundle",
    }
)
HUMAN_DOC_NON_API_TOKENS = frozenset({"Formula", "Image"})

FENCE_PATTERN = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<body>.*?)```", re.DOTALL)
PROVIDER_API_CALL_PATTERN = re.compile(
    r"\b(?P<name>register_provider_bundle|ProviderBundle|ProviderSpec)\s*\("
)
PROHIBITION_PATTERN = re.compile(r"禁止使用|不要使用|do not use", re.IGNORECASE)
AI_AUTHORITY_TOPIC_PATTERN = re.compile(
    r"\bAI/coordinator\b"
    r"|\bAI worker\b"
    r"|worker 输入"
    r"|worker input"
    r"|子 agent"
    r"|\bDAG\b"
    r"|\bProviderManifest\b"
    r"|\bmerge-ready\b"
    r"|\bhard constraints\b"
    r"|\bacceptance\b"
    r"|provider-manifest\.schema\.json"
    r"|fixtures\.doi_samples",
    re.IGNORECASE,
)
AI_AUTHORITY_LINK_PATTERN = re.compile(
    r"(?:^|[\s(`])(?:\.\./)?onboarding/"
    r"(?:coordinator-spec|provider-manifest|provider-manifest\.schema|agent-task-brief|hard-constraints|acceptance)\."
)
API_TOKEN_PATTERN = re.compile(
    r"`(?P<backtick>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)`"
    r"|\b(?P<call>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fenced_code_blocks(markdown: str) -> list[str]:
    return [match.group("body") for match in FENCE_PATTERN.finditer(markdown)]


def _src_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(SRC_DIR.rglob("*.py"))
    )


def _api_tokens(markdown: str) -> set[str]:
    tokens: set[str] = set()
    for match in API_TOKEN_PATTERN.finditer(markdown):
        token = match.group("backtick") or match.group("call")
        if token is None:
            continue
        if "." in token and token.endswith(".py"):
            continue
        if "/" in token or "-" in token:
            continue
        if token in {"None", "True", "False", "TODO", "TBD", "JSON", "YAML"}:
            continue
        if token[0].islower() and not token.endswith("_bundle"):
            continue
        tokens.add(token)
    return tokens


def _human_docs_text() -> str:
    return "\n".join(_read(path) for path in HUMAN_DOC_PATHS)


def _ai_docs_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(AI_ONBOARDING_DIR.glob("*.md"))
    )


def _prohibited_api_tokens(markdown: str) -> set[str]:
    tokens: set[str] = set()
    for line in markdown.splitlines():
        if PROHIBITION_PATTERN.search(line):
            tokens.update(_api_tokens(line))
    return tokens


def _markdown_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def test_provider_development_code_block_api_names_still_exist_in_src() -> None:
    code_blocks = _fenced_code_blocks(_read(PROVIDER_DEVELOPMENT_PATH))
    api_names = {
        match.group("name")
        for block in code_blocks
        for match in PROVIDER_API_CALL_PATTERN.finditer(block)
    }

    assert api_names == {"register_provider_bundle", "ProviderBundle", "ProviderSpec"}

    src_text = _src_text()
    for api_name in sorted(api_names):
        assert re.search(rf"\b{re.escape(api_name)}\b", src_text), (
            f"{api_name} appears in {PROVIDER_DEVELOPMENT_PATH.relative_to(REPO_ROOT)} "
            "code blocks but no longer exists under src/"
        )


def test_human_docs_declare_ai_onboarding_authority() -> None:
    for path in HUMAN_DOC_PATHS:
        text = _read(path)
        assert "Human reference only" in text, path.relative_to(REPO_ROOT)
        assert AI_ONBOARDING_INDEX_LINK in text, (
            f"{path.relative_to(REPO_ROOT)} must link onboarding README as the "
            "human entry/index"
        )
        for required_link in AI_AUTHORITY_REQUIRED_LINKS:
            assert required_link in text, (
                f"{path.relative_to(REPO_ROOT)} must link AI/coordinator authority "
                f"{required_link}"
            )


def test_adding_provider_uses_stable_provider_development_anchors() -> None:
    provider_development = _read(PROVIDER_DEVELOPMENT_PATH)
    stable_anchors = set(re.findall(r'<a id="([^"]+)"></a>', provider_development))
    fragments = set(
        re.findall(
            r"\(provider-development\.md#([^)]+)\)",
            _read(ADDING_PROVIDER_PATH),
        )
    )

    assert fragments, (
        "docs/adding-a-provider.md must link provider-development.md anchors"
    )
    assert fragments <= stable_anchors, (
        "docs/adding-a-provider.md must link explicit stable anchors in "
        "docs/provider-development.md: " + ", ".join(sorted(fragments - stable_anchors))
    )


def test_human_docs_ai_topics_link_ai_authority_in_same_block() -> None:
    violations: list[str] = []
    for path in HUMAN_DOC_PATHS:
        for block in _markdown_blocks(_read(path)):
            if not AI_AUTHORITY_TOPIC_PATTERN.search(block):
                continue
            if AI_AUTHORITY_LINK_PATTERN.search(block):
                continue
            snippet = " ".join(line.strip() for line in block.splitlines())[:160]
            violations.append(f"{path.relative_to(REPO_ROOT)}: {snippet}")

    assert not violations, (
        "Human docs may explain onboarding, but AI worker input, DAG, manifest "
        "fields, hard constraints, acceptance, and merge-ready gates must link "
        "onboarding/ authority in the same block:\n" + "\n".join(violations)
    )


def _grep_commands_from_hard_constraints() -> list[list[str]]:
    commands: list[list[str]] = []
    for block in _fenced_code_blocks(_read(HARD_CONSTRAINTS_PATH)):
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = shlex.split(line)
            if tokens[:2] == ["git", "grep"]:
                commands.append(tokens)
    return commands


def _grep_pattern_and_paths(tokens: list[str]) -> tuple[str, list[str]]:
    assert "--" in tokens, (
        f"grep command must include explicit path separator: {' '.join(tokens)}"
    )
    separator = tokens.index("--")
    path_tokens = tokens[separator + 1 :]
    assert path_tokens, (
        f"grep command must include at least one path: {' '.join(tokens)}"
    )

    pattern: str | None = None
    index = 2
    while index < separator:
        token = tokens[index]
        if token in {"-e", "--regexp"}:
            index += 1
            assert index < separator, f"grep option {token} requires a pattern"
            pattern = tokens[index]
        elif token.startswith("-"):
            pass
        else:
            pattern = token
        index += 1

    assert pattern is not None, (
        f"grep command must include a pattern: {' '.join(tokens)}"
    )
    return pattern, path_tokens


def test_hard_constraints_grep_commands_are_parseable_and_paths_exist() -> None:
    commands = _grep_commands_from_hard_constraints()
    assert commands, (
        f"{HARD_CONSTRAINTS_PATH.relative_to(REPO_ROOT)} must list grep checks"
    )

    for tokens in commands:
        pattern, path_tokens = _grep_pattern_and_paths(tokens)
        re.compile(pattern)
        for path_token in path_tokens:
            path = REPO_ROOT / path_token
            assert path.exists(), (
                f"{HARD_CONSTRAINTS_PATH.relative_to(REPO_ROOT)} grep path does not exist: "
                f"{path_token}"
            )

        result = subprocess.run(
            tokens,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode in {0, 1}, (
            f"grep command is not executable: {' '.join(tokens)}\n{result.stderr}"
        )


def test_human_only_api_drift_warns_but_ai_prohibition_conflicts_fail() -> None:
    human_text = _human_docs_text()
    ai_text = _ai_docs_text()
    human_apis = _api_tokens(human_text)
    ai_apis = _api_tokens(ai_text)

    allowlist_missing_from_human = sorted(HUMAN_ONLY_API_ALLOWLIST - human_apis)
    assert not allowlist_missing_from_human, (
        "HUMAN_ONLY_API_ALLOWLIST entries must appear in human reference docs: "
        + ", ".join(allowlist_missing_from_human)
    )

    allowlist_prohibition_conflicts = sorted(
        HUMAN_ONLY_API_ALLOWLIST & _prohibited_api_tokens(ai_text)
    )
    assert not allowlist_prohibition_conflicts, (
        "HUMAN_ONLY_API_ALLOWLIST entries conflict with AI onboarding prohibitions: "
        + ", ".join(allowlist_prohibition_conflicts)
    )

    missing_from_ai = sorted(
        human_apis - ai_apis - HUMAN_ONLY_API_ALLOWLIST - HUMAN_DOC_NON_API_TOKENS
    )
    if missing_from_ai:
        warnings.warn(
            "Human reference docs mention APIs not present in onboarding/: "
            + ", ".join(missing_from_ai),
            UserWarning,
            stacklevel=1,
        )

    conflicts: list[str] = []
    for prohibited_api in _prohibited_api_tokens(human_text):
        if prohibited_api in ai_apis:
            conflicts.append(prohibited_api)

    assert not conflicts, (
        "AI onboarding docs mention APIs that human reference docs mark as prohibited: "
        + ", ".join(sorted(set(conflicts)))
    )
