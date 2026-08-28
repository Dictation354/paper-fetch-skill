from __future__ import annotations

import argparse
import ast
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
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

CANONICAL_FIXTURE_PREFIXES = (
    "tests/fixtures/golden_criteria/",
    "tests/fixtures/block/",
)
PROVIDER_SECTIONS = (
    "Springer",
    "Elsevier",
    "Wiley",
    "Science",
    "PNAS",
    "AMS",
    "MDPI",
    "IEEE",
    "Copernicus",
)
SHARED_RULE_SECTIONS = ("Generic", "Models", "Service", "CLI")
PROVIDER_RULE_REQUIREMENTS = {
    "science": {
        "availability.site_rule_overrides",
    },
    "pnas": {
        "availability.site_rule_overrides",
        "cleanup.markdown_promo_tokens",
    },
    "springer_nature": {
        "cleanup.chrome_attr_tokens",
        "cleanup.chrome_section_headings",
        "cleanup.license_link_hosts",
        "cleanup.license_link_path_prefixes",
        "cleanup.license_word_limit",
        "cleanup.markdown_promo_tokens",
    },
    "wiley": {
        "availability.site_rule_overrides",
    },
    "ieee": {
        "availability.site_rule_overrides",
        "cleanup.access_block_text_tokens",
        "cleanup.extraction_cleanup_selectors",
        "cleanup.markdown_promo_tokens",
    },
    "ams": {
        "cleanup.dom_postprocess_cleanup_selectors",
    },
    "mdpi": {
        "availability.site_rule_overrides",
        "cleanup.extraction_cleanup_selectors",
        "cleanup.markdown_promo_tokens",
        "cleanup.post_content_break_tokens",
        "assets.supplementary_text_tokens",
    },
}

ANCHOR_RE = re.compile(r'<a\s+id="(rule-[A-Za-z0-9_-]+)"></a>')
RULE_HEADING_RE = re.compile(r'<a\s+id="(rule-[A-Za-z0-9_-]+)"></a>\s*\n### ([^\n]+)')
RULE_LINK_RE = re.compile(r"(?<![A-Za-z0-9_-])#(rule-[A-Za-z0-9_-]+)")
ANGLE_FIXTURE_LINK_RE = re.compile(r"\]\(<(\.\./tests/fixtures/[^>]+)>\)")
PLAIN_FIXTURE_LINK_RE = re.compile(r"\]\((\.\./tests/fixtures/[^)\s]+)\)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
CONTROLLED_STAGE_RE = re.compile(r"^- `([^`]+)`：", flags=re.MULTILINE)
PHASE_FIELD_RE = re.compile(r"^- 它对应的阶段是：(.+)$", flags=re.MULTILINE)
OWNER_FIELD_RE = re.compile(r"^- Owner：(.+)$", flags=re.MULTILINE)
SITE_UI_COPY_MARKER = "SITE_UI_COPY_REGRESSION_MARKER"
SITE_UI_COPY_STRUCTURAL_HOOK_MARKER = "STRUCTURAL_UI_COPY_HOOK"
SITE_UI_COPY_CONSTANT_RE = re.compile(
    r"^(?P<name>[A-Z][A-Z0-9_]*(?:PROMO_TOKENS|POST_CONTENT_BREAK_TOKENS|CHROME_[A-Z0-9_]+|FATAL_ERROR_TEXTS|ERROR_TEXTS))\s*=",
    flags=re.MULTILINE,
)
SITE_UI_COPY_EXEMPT_PREFIXES = ("COMMON_", "MARKDOWN_")
SITE_UI_COPY_POLICY_OWNED_FILES = {
    Path("src/paper_fetch/extraction/html/cleanup_policy.py"),
    Path("src/paper_fetch/extraction/html/provider_rules.py"),
}

PROVIDER_INFERENCE_PATTERNS = {
    # Nature HTML is intentionally maintained through the Springer/Springer Nature
    # provider path, so nature-named tests are checked against Springer shared rules.
    "Springer": re.compile(
        r"(?<![A-Za-z])(?:springer|nature)(?![A-Za-z])", flags=re.IGNORECASE
    ),
    "Elsevier": re.compile(r"(?<![A-Za-z])elsevier(?![A-Za-z])", flags=re.IGNORECASE),
    "Wiley": re.compile(r"(?<![A-Za-z])wiley(?![A-Za-z])", flags=re.IGNORECASE),
    "Science": re.compile(
        r"(?<![A-Za-z])(?:science|sciadv)(?![A-Za-z])", flags=re.IGNORECASE
    ),
    "PNAS": re.compile(r"(?<![A-Za-z])pnas(?![A-Za-z])", flags=re.IGNORECASE),
    "IEEE": re.compile(r"(?<![A-Za-z])ieee(?![A-Za-z])", flags=re.IGNORECASE),
    "MDPI": re.compile(r"(?<![A-Za-z])mdpi(?![A-Za-z])", flags=re.IGNORECASE),
    "Copernicus": re.compile(
        r"(?<![A-Za-z])copernicus(?![A-Za-z])", flags=re.IGNORECASE
    ),
}


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


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
    start_match = re.search(
        rf"^### {re.escape(name)}\s*$", markdown, flags=re.MULTILINE
    )
    if start_match is None:
        return None
    next_match = re.search(
        r"^###\s+", markdown[start_match.end() :], flags=re.MULTILINE
    )
    if next_match is None:
        return markdown[start_match.end() :]
    return markdown[start_match.end() : start_match.end() + next_match.start()]


def _low_stability_summary_rule_ids(markdown: str) -> set[str]:
    section = _subsection_body(markdown, "无稳定 DOI 样本规则汇总表")
    if section is None:
        return set()
    return set(RULE_LINK_RE.findall(section))


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
    stripped = block.lstrip()
    return (
        title.startswith("已")
        or title.startswith("兼容锚点")
        or stripped.startswith("> 已")
        or stripped.startswith("> 参见")
    )


def _manifest_samples() -> dict[str, dict[str, object]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("samples", {})


def validate_anchors(markdown: str) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {}
    for match in ANCHOR_RE.finditer(markdown):
        anchor = match.group(1)
        line = _line_number(markdown, match.start(1))
        if anchor in seen:
            errors.append(
                f"duplicate anchor #{anchor} at line {line}; first seen at line {seen[anchor]}"
            )
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
            errors.append(
                f"rule #{anchor} at line {line} is missing required Owner： field"
            )
            continue
        owner_paths = _owner_path_tokens(match.group(1))
        if not owner_paths:
            errors.append(f"rule #{anchor} at line {line} has no backticked owner path")
            continue
        for owner_path in owner_paths:
            error = _validate_owner_path(owner_path)
            if error:
                errors.append(
                    f"rule #{anchor} at line {line} has invalid Owner `{owner_path}`: {error}"
                )
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
    if not re.match(
        r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$", owner_path
    ):
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
            errors.append(
                f"rule #{anchor} at line {line} is missing required phase field"
            )
            continue
        field = match.group(1)
        stages = BACKTICK_RE.findall(field)
        if not stages:
            errors.append(
                f"rule #{anchor} at line {line} must use backticked controlled stage tokens"
            )
            continue
        for stage in stages:
            if stage not in controlled_stages:
                errors.append(
                    f"rule #{anchor} at line {line} uses unknown stage token `{stage}`"
                )
        unbackticked = BACKTICK_RE.sub("", field)
        unbackticked = re.sub(r"[、,，。\s]+", "", unbackticked)
        if unbackticked:
            errors.append(
                f"rule #{anchor} at line {line} has non-token phase text: {match.group(1)}"
            )
    return errors


def validate_unstable_sample_summary(markdown: str) -> list[str]:
    errors: list[str] = []
    summary_rule_ids = _low_stability_summary_rule_ids(markdown)
    for anchor, title, block, line in _iter_rule_blocks(markdown):
        if _is_redirect_rule(title, block):
            continue
        if "当前无稳定 DOI 样本" in block and anchor not in summary_rule_ids:
            errors.append(
                f"rule #{anchor} at line {line} declares no stable DOI sample but is missing "
                "from the low-stability summary table"
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


def validate_canonical_fixture_manifest() -> list[str]:
    errors: list[str] = []
    manifest_dirs: dict[str, set[str]] = {"golden": set(), "block": set()}
    for sample in _manifest_samples().values():
        if not isinstance(sample, dict) or not isinstance(sample.get("assets"), dict):
            continue
        for asset_path in sample["assets"].values():
            parts = Path(str(asset_path)).parts
            if len(parts) >= 4 and parts[:3] == (
                "tests",
                "fixtures",
                "golden_criteria",
            ):
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
            errors.append(
                f"golden fixture directory is missing from manifest assets: {path.name}"
            )

    block_root = REPO_ROOT / "tests" / "fixtures" / "block"
    for path in sorted(item for item in block_root.iterdir() if item.is_dir()):
        if path.name not in manifest_dirs["block"]:
            errors.append(
                f"block fixture directory is missing from manifest assets: {path.name}"
            )
    return errors


def validate_manifest_test_mapping(anchors: set[str]) -> list[str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    samples = manifest.get("samples")
    entries = manifest.get("tests")
    if not isinstance(samples, dict):
        return ["golden fixture manifest must define a samples object"]
    if not isinstance(entries, list):
        return ["golden fixture manifest must define a tests array"]
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"manifest tests[{index}] must be an object")
            continue
        missing = [key for key in ("test", "anchors", "samples") if key not in entry]
        if missing:
            errors.append(
                f"manifest tests[{index}] is missing required field(s): {', '.join(missing)}"
            )
            continue
        test_id = entry["test"]
        test_anchors = entry["anchors"]
        test_samples = entry["samples"]
        if not isinstance(test_id, str) or test_id.count("::") != 1:
            errors.append(f"manifest tests[{index}].test must be module.py::test_name")
            continue
        module_name, test_name = test_id.split("::", 1)
        module_path = REPO_ROOT / module_name
        if not module_path.is_file():
            errors.append(f"manifest test {test_id} references missing module")
        else:
            tree = ast.parse(
                module_path.read_text(encoding="utf-8"), filename=str(module_path)
            )
            names = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if test_name not in names:
                errors.append(f"manifest test {test_id} does not exist")
        if not isinstance(test_anchors, list) or not test_anchors or not all(
            isinstance(value, str) and value for value in test_anchors
        ):
            errors.append(f"manifest test {test_id} must define non-empty anchors")
            continue
        if not isinstance(test_samples, list) or not all(
            isinstance(value, str) and value for value in test_samples
        ):
            errors.append(f"manifest test {test_id} must define a samples list")
            continue
        for anchor in test_anchors:
            if anchor not in anchors:
                errors.append(
                    f"manifest test {test_id} references missing anchor #{anchor}"
                )
        for sample_id in test_samples:
            if sample_id not in samples:
                errors.append(
                    f"manifest test {test_id} references missing sample {sample_id}"
                )
    return errors


def validate_provider_rule_registry() -> list[str]:
    from paper_fetch.extraction.html.provider_rules import (
        DEFAULT_NOISE_PROFILE,
        PROVIDER_HTML_RULES,
        REGISTERED_NOISE_PROFILES,
        require_provider_html_rules,
    )

    errors: list[str] = []
    expected_profiles = frozenset(
        {
            DEFAULT_NOISE_PROFILE,
            *(
                rules.noise_profile
                for rules in PROVIDER_HTML_RULES.values()
                if rules.noise_profile
            ),
        }
    )
    registered_profiles = frozenset(REGISTERED_NOISE_PROFILES)
    missing_profiles = expected_profiles - registered_profiles
    extra_profiles = registered_profiles - expected_profiles
    if missing_profiles:
        errors.append(
            "REGISTERED_NOISE_PROFILES stale/missing profile(s): "
            + ", ".join(sorted(missing_profiles))
        )
    if extra_profiles:
        errors.append(
            "REGISTERED_NOISE_PROFILES stale/extra profile(s): "
            + ", ".join(sorted(extra_profiles))
        )

    for provider, required_fields in PROVIDER_RULE_REQUIREMENTS.items():
        rules = PROVIDER_HTML_RULES.get(provider)
        if rules is None:
            errors.append(
                f"provider HTML rules registry is missing provider: {provider}"
            )
            continue
        try:
            resolved = require_provider_html_rules(provider)
        except KeyError:
            errors.append(
                f"provider HTML rules registry does not resolve canonical provider: {provider}"
            )
        else:
            if resolved.name != provider:
                errors.append(
                    f"provider HTML rules registry does not resolve canonical provider: {provider}"
                )
        if rules.noise_profile and rules.noise_profile not in expected_profiles:
            errors.append(
                f"provider HTML rules registry provider `{provider}` has unregistered "
                f"noise profile `{rules.noise_profile}`"
            )
        if not rules.noise_profile:
            errors.append(
                f"provider HTML rules registry has empty noise profile for provider: {provider}"
            )
        for alias in rules.aliases:
            try:
                alias_rules = require_provider_html_rules(alias)
            except KeyError:
                errors.append(
                    f"provider HTML rules registry alias `{alias}` does not resolve to provider: {provider}"
                )
                continue
            if alias_rules.name != provider:
                errors.append(
                    f"provider HTML rules registry alias `{alias}` does not resolve to provider: {provider}"
                )
        for field_name in sorted(required_fields):
            value: object = rules
            for field_part in field_name.split("."):
                value = getattr(value, field_part)
            if not value:
                errors.append(
                    f"provider HTML rules registry provider `{provider}` is missing required `{field_name}`"
                )
    return errors


def validate_site_ui_copy_markers() -> list[str]:
    errors: list[str] = []
    for path in sorted((SRC_ROOT / "paper_fetch").rglob("*.py")):
        relative_path = path.relative_to(REPO_ROOT)
        if not _site_ui_copy_marker_scope(relative_path):
            continue
        text = path.read_text(encoding="utf-8")
        for match in SITE_UI_COPY_CONSTANT_RE.finditer(text):
            name = match.group("name")
            if name.startswith(SITE_UI_COPY_EXEMPT_PREFIXES):
                continue
            preceding_lines = text[: match.start()].splitlines()[-5:]
            if SITE_UI_COPY_MARKER not in "\n".join(preceding_lines):
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}:{_line_number(text, match.start())} "
                    f"`{name}` is missing {SITE_UI_COPY_MARKER}"
                )
                continue
            if not _site_ui_copy_has_cleanup_owner(path, text, match):
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}:{_line_number(text, match.start())} "
                    f"`{name}` is missing CleanupPolicy or {SITE_UI_COPY_STRUCTURAL_HOOK_MARKER} ownership"
                )
    return errors


def _site_ui_copy_marker_scope(relative_path: Path) -> bool:
    if relative_path in SITE_UI_COPY_POLICY_OWNED_FILES:
        return True
    return relative_path.parts[:3] == ("src", "paper_fetch", "providers")


def _site_ui_copy_has_cleanup_owner(
    path: Path, text: str, match: re.Match[str]
) -> bool:
    relative_path = path.relative_to(REPO_ROOT)
    if relative_path in SITE_UI_COPY_POLICY_OWNED_FILES:
        return True
    context = "\n".join(text[: match.start()].splitlines()[-8:])
    if SITE_UI_COPY_STRUCTURAL_HOOK_MARKER in context:
        return True
    if "CleanupPolicy" in context or "cleanup policy" in context.lower():
        return True
    if (
        match.group("name").endswith(("ERROR_TEXTS", "FATAL_ERROR_TEXTS"))
        and "structural" in context.lower()
    ):
        return True
    return False


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
        bullet_lines = [
            line for line in shared.splitlines() if line.strip().startswith("- ")
        ]
        if not bullet_lines:
            errors.append(f"provider section {provider} has an empty shared-rule list")
            continue
        for line in bullet_lines:
            links = RULE_LINK_RE.findall(line)
            if not links:
                errors.append(
                    f"provider section {provider} shared item lacks rule link: {line.strip()}"
                )
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
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    tests_by_anchor: dict[str, list[str]] = {}
    for entry in manifest.get("tests", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("test"), str):
            continue
        for anchor in entry.get("anchors", []):
            if isinstance(anchor, str):
                tests_by_anchor.setdefault(anchor, []).append(entry["test"])
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
        if (
            _is_redirect_rule(title, block)
            or rule_sections.get(anchor) not in SHARED_RULE_SECTIONS
        ):
            continue
        owner_match = OWNER_FIELD_RE.search(block)
        inferred = _infer_providers(owner_match.group(1) if owner_match else "")
        for test_id in tests_by_anchor.get(anchor, []):
            inferred.update(_infer_providers(test_id))
        for provider in sorted(inferred):
            if anchor not in shared_by_provider.get(provider, set()):
                errors.append(
                    f"shared rule #{anchor} at line {line} has {provider} owner/tests "
                    f"but {provider} shared-rule list does not include it"
                )
    return errors


def validate_markdown(markdown: str) -> list[str]:
    anchors = set(ANCHOR_RE.findall(markdown))
    errors: list[str] = []
    errors.extend(validate_anchors(markdown))
    errors.extend(validate_rule_phases(markdown))
    errors.extend(validate_rule_owners(markdown))
    errors.extend(validate_unstable_sample_summary(markdown))
    errors.extend(validate_fixtures(markdown))
    errors.extend(validate_canonical_fixture_manifest())
    errors.extend(validate_manifest_test_mapping(anchors))
    errors.extend(validate_provider_rule_registry())
    errors.extend(validate_site_ui_copy_markers())
    errors.extend(validate_provider_shared_lists(markdown, anchors))
    errors.extend(validate_provider_shared_applicability(markdown))
    return errors


def _infer_providers(text: str) -> set[str]:
    return {
        provider
        for provider, pattern in PROVIDER_INFERENCE_PATTERNS.items()
        if pattern.search(text)
    }


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Validate docs/extraction-rules.md and related rule registries."
    )


def main(argv: list[str] | None = None) -> int:
    _parser().parse_args(argv)
    markdown = DOC_PATH.read_text(encoding="utf-8")
    errors = validate_markdown(markdown)

    if errors:
        print("docs/extraction-rules.md validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("docs/extraction-rules.md validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
