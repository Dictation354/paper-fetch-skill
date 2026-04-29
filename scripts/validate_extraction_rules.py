from __future__ import annotations

import ast
from dataclasses import dataclass
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
DOC_PATH = REPO_ROOT / "docs" / "extraction-rules.md"
MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
TESTS_ROOT = REPO_ROOT / "tests"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

CANONICAL_FIXTURE_PREFIXES = (
    "tests/fixtures/golden_criteria/",
    "tests/fixtures/block/",
)
PROVIDER_SECTIONS = ("Springer", "Elsevier", "Wiley", "Science", "PNAS")
SHARED_RULE_SECTIONS = ("Generic", "Models", "Service", "CLI")
UNLINKED_FIXTURES_START = "<!-- extraction-rules-unlinked-fixtures:start -->"
UNLINKED_FIXTURES_END = "<!-- extraction-rules-unlinked-fixtures:end -->"
LOW_COVERAGE_MARKERS = ("测试覆盖度低", "单测试规则")

ANCHOR_RE = re.compile(r'<a\s+id="(rule-[A-Za-z0-9_-]+)"></a>')
RULE_HEADING_RE = re.compile(r'<a\s+id="(rule-[A-Za-z0-9_-]+)"></a>\s*\n### ([^\n]+)')
RULE_LINK_RE = re.compile(r"(?<![A-Za-z0-9_-])#(rule-[A-Za-z0-9_-]+)")
TEST_NAME_RE = re.compile(r"`(test_[A-Za-z0-9_]+)`")
ANGLE_FIXTURE_LINK_RE = re.compile(r"\]\(<(\.\./tests/fixtures/[^>]+)>\)")
PLAIN_FIXTURE_LINK_RE = re.compile(r"\]\((\.\./tests/fixtures/[^)\s]+)\)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
CONTROLLED_STAGE_RE = re.compile(r"^- `([^`]+)`：", flags=re.MULTILINE)
PHASE_FIELD_RE = re.compile(r"^- 它对应的阶段是：(.+)$", flags=re.MULTILINE)
OWNER_FIELD_RE = re.compile(r"^- Owner：(.+)$", flags=re.MULTILINE)
RULE_MARKER_RE = re.compile(r"^\s*rule:\s*(rule-[A-Za-z0-9_-]+)\s*$", flags=re.MULTILINE)

PROVIDER_INFERENCE_PATTERNS = {
    # Nature HTML is intentionally maintained through the Springer/Springer Nature
    # provider path, so nature-named tests are checked against Springer shared rules.
    "Springer": re.compile(r"(?<![A-Za-z])(?:springer|nature)(?![A-Za-z])", flags=re.IGNORECASE),
    "Elsevier": re.compile(r"(?<![A-Za-z])elsevier(?![A-Za-z])", flags=re.IGNORECASE),
    "Wiley": re.compile(r"(?<![A-Za-z])wiley(?![A-Za-z])", flags=re.IGNORECASE),
    "Science": re.compile(r"(?<![A-Za-z])(?:science|sciadv)(?![A-Za-z])", flags=re.IGNORECASE),
    "PNAS": re.compile(r"(?<![A-Za-z])pnas(?![A-Za-z])", flags=re.IGNORECASE),
}


@dataclass(frozen=True)
class TestDefinition:
    path: Path
    rule_markers: frozenset[str]


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _iter_python_tests() -> dict[str, list[TestDefinition]]:
    test_defs: dict[str, list[TestDefinition]] = {}
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        if "fixtures" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    docstring = ast.get_docstring(node, clean=False) or ""
                    markers = frozenset(RULE_MARKER_RE.findall(docstring))
                    test_defs.setdefault(node.name, []).append(
                        TestDefinition(path=path, rule_markers=markers)
                    )
    return test_defs


def _extract_fixture_links(markdown: str) -> list[tuple[str, int]]:
    links: list[tuple[str, int]] = []
    for pattern in (ANGLE_FIXTURE_LINK_RE, PLAIN_FIXTURE_LINK_RE):
        for match in pattern.finditer(markdown):
            links.append((match.group(1), _line_number(markdown, match.start(1))))
    return sorted(set(links), key=lambda item: (item[1], item[0]))


def _normalize_fixture_link(link: str) -> str:
    if not link.startswith("../"):
        return link
    return link.removeprefix("../")


def _iter_rule_blocks(markdown: str) -> list[tuple[str, str, str, int]]:
    matches = list(RULE_HEADING_RE.finditer(markdown))
    blocks: list[tuple[str, str, str, int]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        blocks.append(
            (
                match.group(1),
                match.group(2),
                markdown[start:end],
                _line_number(markdown, match.start(1)),
            )
        )
    return blocks


def _subsection_body(markdown: str, name: str) -> str | None:
    start_match = re.search(rf"^### {re.escape(name)}\s*$", markdown, flags=re.MULTILINE)
    if start_match is None:
        return None
    next_match = re.search(r"^###\s+", markdown[start_match.end() :], flags=re.MULTILINE)
    if next_match is None:
        return markdown[start_match.end() :]
    return markdown[start_match.end() : start_match.end() + next_match.start()]


def _rule_top_level_sections(markdown: str) -> dict[str, str]:
    headings = list(re.finditer(r"^## ([^\n]+)\s*$", markdown, flags=re.MULTILINE))
    rule_sections: dict[str, str] = {}
    for match in RULE_HEADING_RE.finditer(markdown):
        section = ""
        for heading in headings:
            if heading.start() > match.start():
                break
            section = heading.group(1)
        rule_sections[match.group(1)] = section
    return rule_sections


def _is_redirect_rule(title: str, block: str) -> bool:
    return title.startswith("已") or block.lstrip().startswith("> 已")


def _manifest_samples() -> dict[str, dict[str, object]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("samples", {})


def validate_anchors(markdown: str) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {}
    for match in ANCHOR_RE.finditer(markdown):
        anchor = match.group(1)
        line = _line_number(markdown, match.start(1))
        if anchor in seen:
            errors.append(f"duplicate anchor #{anchor} at line {line}; first seen at line {seen[anchor]}")
        else:
            seen[anchor] = line

    anchors = set(seen)
    for match in RULE_LINK_RE.finditer(markdown):
        anchor = match.group(1)
        if anchor not in anchors:
            line = _line_number(markdown, match.start(1))
            errors.append(f"unresolved rule link #{anchor} at line {line}")
    return errors


def validate_rule_owners(markdown: str) -> list[str]:
    errors: list[str] = []
    for anchor, title, block, line in _iter_rule_blocks(markdown):
        if _is_redirect_rule(title, block):
            continue
        match = OWNER_FIELD_RE.search(block)
        if match is None:
            errors.append(f"rule #{anchor} at line {line} is missing required Owner： field")
            continue
        owner_paths = _owner_path_tokens(match.group(1))
        if not owner_paths:
            errors.append(f"rule #{anchor} at line {line} has no backticked owner path")
            continue
        for owner_path in owner_paths:
            error = _validate_owner_path(owner_path)
            if error:
                errors.append(f"rule #{anchor} at line {line} has invalid Owner `{owner_path}`: {error}")
    return errors


def _owner_path_tokens(owner_field: str) -> list[str]:
    paths: list[str] = []
    for token in BACKTICK_RE.findall(owner_field):
        for part in re.split(r"\s*(?:\+|与)\s*", token):
            owner_path = part.strip()
            if owner_path:
                paths.append(owner_path)
    return paths


def _find_spec(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _validate_owner_path(owner_path: str) -> str | None:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$", owner_path):
        return "not a dotted import path"
    if _find_spec(owner_path):
        return None
    parent, _separator, attr = owner_path.rpartition(".")
    if not _find_spec(parent):
        return f"parent module `{parent}` cannot be imported"
    try:
        module = importlib.import_module(parent)
    except Exception as exc:  # pragma: no cover - surfaced as validation detail
        return f"parent module `{parent}` failed to import: {exc}"
    if not hasattr(module, attr):
        return f"parent module `{parent}` has no attribute `{attr}`"
    return None


def validate_rule_phases(markdown: str) -> list[str]:
    errors: list[str] = []
    section = _subsection_body(markdown, "受控阶段清单")
    if section is None:
        return ["missing controlled stage list"]
    controlled_stages = set(CONTROLLED_STAGE_RE.findall(section))
    if not controlled_stages:
        return ["controlled stage list contains no backticked stage tokens"]

    for anchor, title, block, line in _iter_rule_blocks(markdown):
        if _is_redirect_rule(title, block):
            continue
        match = PHASE_FIELD_RE.search(block)
        if match is None:
            errors.append(f"rule #{anchor} at line {line} is missing required phase field")
            continue
        field = match.group(1)
        stages = BACKTICK_RE.findall(field)
        if not stages:
            errors.append(f"rule #{anchor} at line {line} must use backticked controlled stage tokens")
            continue
        for stage in stages:
            if stage not in controlled_stages:
                errors.append(f"rule #{anchor} at line {line} uses unknown stage token `{stage}`")
        unbackticked = BACKTICK_RE.sub("", field)
        unbackticked = re.sub(r"[、,，。\s]+", "", unbackticked)
        if unbackticked:
            errors.append(
                f"rule #{anchor} at line {line} has non-token phase text: {match.group(1)}"
            )
    return errors


def validate_single_test_rule_risk_markers(markdown: str) -> list[str]:
    errors: list[str] = []
    for anchor, title, block, line in _iter_rule_blocks(markdown):
        if _is_redirect_rule(title, block):
            continue
        test_names = set(TEST_NAME_RE.findall(block))
        if len(test_names) == 1 and not any(marker in block for marker in LOW_COVERAGE_MARKERS):
            errors.append(
                f"single-test rule #{anchor} at line {line} must mark low coverage risk"
            )
    return errors


def validate_fixtures(markdown: str) -> list[str]:
    errors: list[str] = []
    for link, line in _extract_fixture_links(markdown):
        normalized = _normalize_fixture_link(link)
        if not normalized.startswith(CANONICAL_FIXTURE_PREFIXES):
            errors.append(f"non-canonical fixture link at line {line}: {link}")
            continue
        path = (DOC_PATH.parent / link).resolve()
        if not str(path).startswith(str(REPO_ROOT.resolve())):
            errors.append(f"fixture link escapes repo at line {line}: {link}")
            continue
        if not path.is_file():
            errors.append(f"missing fixture linked at line {line}: {link}")
    return errors


def _documented_unlinked_fixture_sample_ids(markdown: str) -> set[str]:
    start = markdown.find(UNLINKED_FIXTURES_START)
    end = markdown.find(UNLINKED_FIXTURES_END)
    if start == -1 or end == -1 or end < start:
        return set()
    section = markdown[start:end]
    return set(re.findall(r"`([^`]+)`", section))


def _covered_manifest_sample_ids(markdown: str) -> set[str]:
    fixture_links = {
        _normalize_fixture_link(link)
        for link, _line in _extract_fixture_links(markdown)
    }
    covered: set[str] = set()
    for sample_id, sample in _manifest_samples().items():
        assets = sample.get("assets") if isinstance(sample, dict) else None
        if not isinstance(assets, dict):
            continue
        if any(str(asset_path) in fixture_links for asset_path in assets.values()):
            covered.add(sample_id)
    return covered


def validate_manifest_fixture_reverse_index(markdown: str) -> list[str]:
    errors: list[str] = []
    if UNLINKED_FIXTURES_START not in markdown or UNLINKED_FIXTURES_END not in markdown:
        return ["missing unlinked fixture allowlist markers"]

    samples = _manifest_samples()
    sample_ids = set(samples)
    covered = _covered_manifest_sample_ids(markdown)
    documented_unlinked = _documented_unlinked_fixture_sample_ids(markdown)

    unknown = documented_unlinked - sample_ids
    for sample_id in sorted(unknown):
        errors.append(f"unlinked fixture list references unknown manifest sample: {sample_id}")

    stale = documented_unlinked & covered
    for sample_id in sorted(stale):
        errors.append(f"manifest sample is both reverse-indexed and listed as unlinked: {sample_id}")

    sample_ids_with_assets = {
        sample_id
        for sample_id, sample in samples.items()
        if isinstance(sample, dict) and isinstance(sample.get("assets"), dict) and sample["assets"]
    }
    undocumented = sample_ids_with_assets - covered - documented_unlinked
    for sample_id in sorted(undocumented):
        errors.append(
            f"manifest sample is not covered by fixture reverse index or unlinked list: {sample_id}"
        )
    return errors


def validate_canonical_fixture_manifest() -> list[str]:
    errors: list[str] = []
    manifest_dirs: dict[str, set[str]] = {"golden": set(), "block": set()}
    for sample in _manifest_samples().values():
        if not isinstance(sample, dict) or not isinstance(sample.get("assets"), dict):
            continue
        for asset_path in sample["assets"].values():
            parts = Path(str(asset_path)).parts
            if len(parts) >= 4 and parts[:3] == ("tests", "fixtures", "golden_criteria"):
                manifest_dirs["golden"].add(parts[3])
            elif len(parts) >= 4 and parts[:3] == ("tests", "fixtures", "block"):
                manifest_dirs["block"].add(parts[3])
            path = REPO_ROOT / str(asset_path)
            if not path.is_file():
                errors.append(f"manifest asset path is missing: {asset_path}")

    golden_root = REPO_ROOT / "tests" / "fixtures" / "golden_criteria"
    for path in sorted(item for item in golden_root.iterdir() if item.is_dir()):
        if path.name == "_scenarios":
            continue
        if path.name not in manifest_dirs["golden"]:
            errors.append(f"golden fixture directory is missing from manifest assets: {path.name}")

    block_root = REPO_ROOT / "tests" / "fixtures" / "block"
    for path in sorted(item for item in block_root.iterdir() if item.is_dir()):
        if path.name not in manifest_dirs["block"]:
            errors.append(f"block fixture directory is missing from manifest assets: {path.name}")
    return errors


def validate_test_names(markdown: str) -> list[str]:
    test_defs = _iter_python_tests()
    errors: list[str] = []
    for test_name in sorted(set(TEST_NAME_RE.findall(markdown))):
        if test_name not in test_defs:
            errors.append(f"documented test does not exist under tests/: {test_name}")
    return errors


def validate_test_docstring_markers(markdown: str) -> list[str]:
    test_defs = _iter_python_tests()
    errors: list[str] = []
    for anchor, title, block, line in _iter_rule_blocks(markdown):
        if _is_redirect_rule(title, block):
            continue
        has_matching_marker = False
        for test_name in sorted(set(TEST_NAME_RE.findall(block))):
            for definition in test_defs.get(test_name, []):
                if anchor in definition.rule_markers:
                    has_matching_marker = True
                elif definition.rule_markers:
                    errors.append(
                        f"documented test `{test_name}` for #{anchor} at line {line} "
                        f"has rule markers {sorted(definition.rule_markers)}"
                    )
        if TEST_NAME_RE.findall(block) and not has_matching_marker:
            errors.append(
                f"rule #{anchor} at line {line} has no documented test with matching docstring marker"
            )
    return errors


def validate_manifest_anchors(anchors: set[str]) -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in manifest.get("tests", []):
        test_id = entry.get("test", "<unknown>")
        for anchor in entry.get("anchors", []):
            if anchor not in anchors:
                errors.append(f"manifest test {test_id} references missing anchor #{anchor}")
    return errors


def _section_body(markdown: str, name: str) -> str | None:
    start_match = re.search(rf"^## {re.escape(name)}\s*$", markdown, flags=re.MULTILINE)
    if start_match is None:
        return None
    next_match = re.search(r"^##\s+", markdown[start_match.end() :], flags=re.MULTILINE)
    if next_match is None:
        return markdown[start_match.end() :]
    return markdown[start_match.end() : start_match.end() + next_match.start()]


def validate_provider_shared_lists(markdown: str, anchors: set[str]) -> list[str]:
    errors: list[str] = []
    for provider in PROVIDER_SECTIONS:
        body = _section_body(markdown, provider)
        if body is None:
            errors.append(f"missing provider section: {provider}")
            continue
        marker = "- 共享规则另见："
        if marker not in body:
            errors.append(f"provider section {provider} is missing shared-rule list")
            continue
        shared = body.split(marker, 1)[1]
        shared = re.split(
            r"\n- 不适用 / 部分适用说明：|\n<a id=|\n### |\n## ",
            shared,
            maxsplit=1,
        )[0]
        bullet_lines = [line for line in shared.splitlines() if line.strip().startswith("- ")]
        if not bullet_lines:
            errors.append(f"provider section {provider} has an empty shared-rule list")
            continue
        for line in bullet_lines:
            links = RULE_LINK_RE.findall(line)
            if not links:
                errors.append(f"provider section {provider} shared item lacks rule link: {line.strip()}")
                continue
            for anchor in links:
                if anchor not in anchors:
                    errors.append(
                        f"provider section {provider} shared item references missing #{anchor}"
                    )
    return errors


def validate_provider_shared_applicability(markdown: str) -> list[str]:
    errors: list[str] = []
    rule_sections = _rule_top_level_sections(markdown)
    test_defs = _iter_python_tests()
    shared_by_provider: dict[str, set[str]] = {}
    for provider in PROVIDER_SECTIONS:
        body = _section_body(markdown, provider)
        if body is None:
            continue
        marker = "- 共享规则另见："
        if marker not in body:
            continue
        shared = body.split(marker, 1)[1]
        shared = re.split(
            r"\n- 不适用 / 部分适用说明：|\n<a id=|\n### |\n## ",
            shared,
            maxsplit=1,
        )[0]
        shared_by_provider[provider] = set(RULE_LINK_RE.findall(shared))

    for anchor, title, block, line in _iter_rule_blocks(markdown):
        if _is_redirect_rule(title, block) or rule_sections.get(anchor) not in SHARED_RULE_SECTIONS:
            continue
        owner_match = OWNER_FIELD_RE.search(block)
        inferred = _infer_providers(owner_match.group(1) if owner_match else "")
        for test_name in TEST_NAME_RE.findall(block):
            name_providers = _infer_providers(test_name)
            for definition in test_defs.get(test_name, []):
                inferred.update(name_providers or _infer_providers(str(definition.path.relative_to(REPO_ROOT))))
        for provider in sorted(inferred):
            if anchor not in shared_by_provider.get(provider, set()):
                errors.append(
                    f"shared rule #{anchor} at line {line} has {provider} owner/tests "
                    f"but {provider} shared-rule list does not include it"
                )
    return errors


def _infer_providers(text: str) -> set[str]:
    return {
        provider
        for provider, pattern in PROVIDER_INFERENCE_PATTERNS.items()
        if pattern.search(text)
    }


def main() -> int:
    markdown = DOC_PATH.read_text(encoding="utf-8")
    anchors = set(ANCHOR_RE.findall(markdown))
    errors: list[str] = []
    errors.extend(validate_anchors(markdown))
    errors.extend(validate_rule_phases(markdown))
    errors.extend(validate_rule_owners(markdown))
    errors.extend(validate_single_test_rule_risk_markers(markdown))
    errors.extend(validate_fixtures(markdown))
    errors.extend(validate_canonical_fixture_manifest())
    errors.extend(validate_manifest_fixture_reverse_index(markdown))
    errors.extend(validate_test_names(markdown))
    errors.extend(validate_test_docstring_markers(markdown))
    errors.extend(validate_manifest_anchors(anchors))
    errors.extend(validate_provider_shared_lists(markdown, anchors))
    errors.extend(validate_provider_shared_applicability(markdown))

    if errors:
        print("docs/extraction-rules.md validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("docs/extraction-rules.md validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
