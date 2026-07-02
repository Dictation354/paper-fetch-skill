#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _structured_errors import ToolError, emit_error, error_payload  # noqa: E402


NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
DOI_RE = re.compile(r"^10\.[^/\s]+/.+")
PROVIDERS_MATRIX_MARKER = "<!-- SCAFFOLD: providers-capability-matrix -->"
PROVIDERS_DETAILS_MARKER = "<!-- SCAFFOLD: provider-docs -->"
EXTRACTION_RULES_MARKER = "<!-- SCAFFOLD: extraction-rules-unstable-doi -->"
CHANGELOG_UNRELEASED_MARKER = "<!-- SCAFFOLD: changelog-unreleased -->"
MANIFEST_SCHEMA_INVALID = "MANIFEST_SCHEMA_INVALID"


class ScaffoldArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_error(
            error_payload(
                "SCAFFOLD_FORBIDDEN_FLAG_COMBINATION",
                message,
                provider=None,
                manifest=None,
                task_id="scaffold-parse-args",
                retryable=False,
                details={"reason": message},
            )
        )
        raise SystemExit(2)


@dataclass(frozen=True)
class FixtureSample:
    purpose: str
    doi: str


@dataclass(frozen=True)
class MarkdownContract:
    purpose: str
    doi: str
    must_include: tuple[str, ...]
    must_not_include: tuple[str, ...]
    must_match: tuple[str, ...] = ()
    count_equals: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class ScaffoldInput:
    name: str
    doi: str
    source: str
    fulltext_client: bool
    html_capable: bool
    display_name: str | None = None
    domains: tuple[str, ...] = ()
    doi_prefixes: tuple[str, ...] = ()
    domain_suffixes: tuple[str, ...] = ()
    publisher_aliases: tuple[str, ...] = ()
    asset_default: str = "none"
    asset_profile_none: tuple[str, ...] = ()
    asset_profile_body: tuple[str, ...] = ()
    asset_profile_all: tuple[str, ...] = ()
    env_requirements: tuple[str, ...] = ()
    requires_playwright: bool = False
    requires_browser_runtime: bool = False
    provider_managed_abstract_only: bool = False
    waterfall_steps: tuple[str, ...] = ("landing", "html", "xml", "pdf")
    fixture_samples: tuple[FixtureSample, ...] = ()
    skipped_fixture_purposes: tuple[str, ...] = ()
    markdown_contracts: tuple[MarkdownContract, ...] = ()
    docs_providers_md_capability_row: str | None = None
    docs_changelog_summary: str | None = None
    docs_extraction_rules_summary: str | None = None
    manifest_path: Path | None = None


class ManifestSchemaError(ValueError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ScaffoldMergePlan(Exception):
    def __init__(self, summary: dict[str, Any]) -> None:
        super().__init__("scaffold merge plan generated")
        self.summary = summary


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _doi_slug(doi: str) -> str:
    return doi.replace("/", "_")


def _class_name(provider_name: str) -> str:
    return "".join(part.capitalize() for part in provider_name.split("_")) + "Client"


def _parse_html_capable(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise argparse.ArgumentTypeError("--html-capable must be true or false")


def _format_py_string(value: str) -> str:
    return json.dumps(value)


def _format_py_tuple(values: tuple[str, ...] | list[str]) -> str:
    normalized = tuple(str(value) for value in values)
    if not normalized:
        return "()"
    rendered = ", ".join(_format_py_string(value) for value in normalized)
    if len(normalized) == 1:
        rendered += ","
    return f"({rendered})"


def _step_function_name(name: str, step: str) -> str:
    return f"{name}_fetch_{step}_step"


def _write_new(path: Path, content: str = "") -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ensure_scaffold_doc(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_providers_doc() -> str:
    return "\n".join(
        [
            "# Providers",
            "",
            "## Provider 能力矩阵",
            "",
            PROVIDERS_MATRIX_MARKER,
            "| Provider | 元数据 | 全文主路径 | 资产下载 | Markdown 能力 | 备注 |",
            "| --- | --- | --- | --- | --- | --- |",
            "",
            PROVIDERS_DETAILS_MARKER,
            "",
        ]
    )


def _minimal_extraction_rules_doc() -> str:
    return "\n".join(
        [
            "# Extraction Rules",
            "",
            "### 无稳定 DOI 样本规则汇总表",
            "",
            EXTRACTION_RULES_MARKER,
            "| 规则 | 当前证据状态 | 后续补样本触发 | 下一步候选 fixture |",
            "| --- | --- | --- | --- |",
            "",
        ]
    )


def _minimal_changelog_doc() -> str:
    return "\n".join(
        [
            "# Changelog",
            "",
            "## Unreleased",
            "",
            CHANGELOG_UNRELEASED_MARKER,
            "",
        ]
    )


def _insert_table_row_after_marker(
    text: str, marker: str, row: str
) -> tuple[str, bool]:
    if row in text:
        return text, False
    if marker not in text:
        raise ValueError(f"missing scaffold marker: {marker}")
    lines = text.splitlines()
    marker_index = next(index for index, line in enumerate(lines) if marker in line)
    table_start = None
    for index in range(marker_index + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            table_start = index
            break
        if stripped and not stripped.startswith("<!--"):
            break
    if table_start is None:
        raise ValueError(f"missing markdown table after scaffold marker: {marker}")
    insert_at = table_start
    for index in range(table_start, len(lines)):
        stripped = lines[index].strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            break
        insert_at = index + 1
    lines.insert(insert_at, row)
    return "\n".join(lines) + "\n", True


def _insert_before_marker(text: str, marker: str, block: str) -> tuple[str, bool]:
    if block in text:
        return text, False
    if marker not in text:
        raise ValueError(f"missing scaffold marker: {marker}")
    return text.replace(marker, f"{block.rstrip()}\n\n{marker}", 1), True


def _insert_after_marker(text: str, marker: str, block: str) -> tuple[str, bool]:
    if block in text:
        return text, False
    if marker not in text:
        raise ValueError(f"missing scaffold marker: {marker}")
    updated = text.replace(marker, f"{marker}\n\n{block.rstrip()}", 1)
    updated = updated.replace("\n_No unreleased changes._\n", "\n", 1)
    return updated if updated.endswith("\n") else updated + "\n", True


def _load_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"samples": {}}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest is not valid JSON: {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"manifest root must be an object: {path}")
    samples = manifest.setdefault("samples", {})
    if not isinstance(samples, dict):
        raise ValueError(f"manifest samples must be an object: {path}")
    return manifest


def _load_provider_manifest(path: Path) -> dict[str, Any]:
    try:
        import yaml
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ManifestSchemaError(
            f"manifest validation dependency is missing: {exc}"
        ) from exc

    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestSchemaError(str(exc)) from exc
    except yaml.YAMLError as exc:
        raise ManifestSchemaError(f"manifest YAML is invalid: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ManifestSchemaError("manifest root must be an object")

    schema_path = _repo_root() / "onboarding" / "provider-manifest.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestSchemaError(
            f"provider manifest schema cannot be loaded: {exc}"
        ) from exc

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        path_text = ".".join(str(part) for part in error.path)
        prefix = f"{path_text}: " if path_text else ""
        raise ManifestSchemaError(
            f"{prefix}{error.message}",
            details={
                "field": path_text or None,
                "expected": str(error.validator),
                "reason": error.message,
            },
        ) from None
    return manifest


def _asset_default_from_manifest(asset_profile: dict[str, Any]) -> str:
    if asset_profile.get("body"):
        return "body"
    if asset_profile.get("all"):
        return "all"
    return "none"


def _fixture_samples_from_manifest(
    fixtures: dict[str, Any],
    extra_fixtures: list[Any] | None = None,
) -> tuple[tuple[FixtureSample, ...], tuple[str, ...]]:
    samples: list[FixtureSample] = []
    skipped: list[str] = []
    doi_samples = fixtures.get("doi_samples", {})
    if not isinstance(doi_samples, dict):
        return (), ()
    for purpose, sample in doi_samples.items():
        doi = sample.get("doi") if isinstance(sample, dict) else None
        if doi:
            samples.append(FixtureSample(purpose=str(purpose), doi=str(doi)))
        else:
            skipped.append(str(purpose))
    for extra_fixture in extra_fixtures or ():
        if not isinstance(extra_fixture, dict):
            continue
        doi = extra_fixture.get("doi")
        purpose = extra_fixture.get("purpose")
        if doi and purpose:
            samples.append(FixtureSample(purpose=str(purpose), doi=str(doi)))
    return tuple(samples), tuple(skipped)


def _markdown_contracts_from_manifest(
    markdown_contract: dict[str, Any],
) -> tuple[MarkdownContract, ...]:
    contracts: list[MarkdownContract] = []
    for purpose, contract in markdown_contract.items():
        if not isinstance(contract, dict):
            continue
        count_equals = contract.get("count_equals")
        count_items: tuple[tuple[str, int], ...] = ()
        if isinstance(count_equals, dict):
            count_items = tuple(
                (str(key), int(value)) for key, value in sorted(count_equals.items())
            )
        contracts.append(
            MarkdownContract(
                purpose=str(purpose),
                doi=str(contract["doi"]),
                must_include=tuple(str(value) for value in contract["must_include"]),
                must_not_include=tuple(
                    str(value) for value in contract["must_not_include"]
                ),
                must_match=tuple(
                    str(value) for value in contract.get("must_match") or ()
                ),
                count_equals=count_items,
            )
        )
    return tuple(contracts)


def _scaffold_input_from_manifest(manifest_path: Path) -> ScaffoldInput:
    if not manifest_path.exists():
        raise ToolError(
            "MANIFEST_NOT_FOUND",
            "Provider manifest was not found.",
            retryable=False,
            manifest=manifest_path.as_posix(),
            task_id="scaffold-validate-manifest",
            details={"path": manifest_path.as_posix()},
        )
    manifest = _load_provider_manifest(manifest_path)
    name = str(manifest["name"])
    display_source = str(manifest["display_source"])
    routing = manifest["routing"]
    asset_profile = manifest["asset_profile"]
    probe = manifest["probe"]
    docs = manifest["docs"]
    main_path = tuple(str(step) for step in manifest["main_path"])
    fixture_samples, skipped_purposes = _fixture_samples_from_manifest(
        manifest["fixtures"],
        (
            manifest.get("extra_fixtures")
            if isinstance(manifest.get("extra_fixtures"), list)
            else None
        ),
    )
    placeholder_doi = next((sample.doi for sample in fixture_samples), None)
    if placeholder_doi is None:
        raise ManifestSchemaError("fixtures.doi_samples must contain at least one DOI")

    return ScaffoldInput(
        name=name,
        doi=placeholder_doi,
        source=display_source,
        fulltext_client=bool(main_path),
        html_capable=any(
            step in {"landing_html", "article_html"} for step in main_path
        ),
        display_name=name.replace("_", " ").title(),
        domains=tuple(str(value) for value in routing["domains"]),
        doi_prefixes=tuple(str(value) for value in routing["doi_prefixes"]),
        domain_suffixes=tuple(str(value) for value in routing["domain_suffixes"]),
        publisher_aliases=tuple(str(value) for value in routing["publisher_aliases"]),
        asset_default=_asset_default_from_manifest(asset_profile),
        asset_profile_none=tuple(str(value) for value in asset_profile["none"]),
        asset_profile_body=tuple(str(value) for value in asset_profile["body"]),
        asset_profile_all=tuple(str(value) for value in asset_profile["all"]),
        env_requirements=tuple(str(value) for value in probe["env_requirements"]),
        requires_playwright=bool(probe["requires_playwright"]),
        requires_browser_runtime=bool(probe["requires_browser_runtime"]),
        provider_managed_abstract_only=(
            manifest["abstract_only_strategy"] == "provider_managed"
        ),
        waterfall_steps=main_path,
        fixture_samples=fixture_samples,
        skipped_fixture_purposes=skipped_purposes,
        markdown_contracts=_markdown_contracts_from_manifest(
            manifest["markdown_contract"]
        ),
        docs_providers_md_capability_row=str(docs["providers_md_capability_row"]),
        docs_changelog_summary=str(docs["changelog_summary"]),
        docs_extraction_rules_summary=(
            str(docs["extraction_rules_summary"])
            if docs.get("extraction_rules_summary") is not None
            else None
        ),
        manifest_path=manifest_path,
    )


def _legacy_scaffold_input(args: argparse.Namespace) -> ScaffoldInput:
    source = args.source or args.name
    return ScaffoldInput(
        name=args.name,
        doi=args.doi,
        source=source,
        fulltext_client=args.fulltext_client,
        html_capable=True if args.html_capable is None else args.html_capable,
        doi_prefixes=(args.doi.split("/", 1)[0] + "/",),
        publisher_aliases=(source,),
        fixture_samples=(FixtureSample(purpose="content", doi=args.doi),),
    )


def _html_module_content(
    *,
    spec: ScaffoldInput,
) -> str:
    name = spec.name
    display_name = name.replace("_", " ").title()
    client_factory_path = (
        f"paper_fetch.providers.{name}:{_class_name(name)}"
        if spec.fulltext_client
        else ""
    )
    catalog_lines = [
        "        catalog=ProviderSpec(",
        f'            name="{name}",',
        f'            display_name="{spec.display_name or display_name}",',
        "            official=True,",
        f"            domains={_format_py_tuple(spec.domains)},",
        f"            doi_prefixes={_format_py_tuple(spec.doi_prefixes)},",
        f"            publisher_aliases={_format_py_tuple(spec.publisher_aliases)},",
        f'            asset_default="{spec.asset_default}",',
        '            probe_capability="routing_signal",',
        f"            provider_managed_abstract_only={spec.provider_managed_abstract_only},",
        f'            client_factory_path="{client_factory_path}",',
        "            status_order=999,",
    ]
    if spec.domain_suffixes or spec.manifest_path is not None:
        catalog_lines.append(
            f"            domain_suffixes={_format_py_tuple(spec.domain_suffixes)},"
        )
    if spec.env_requirements or spec.manifest_path is not None:
        catalog_lines.append(
            f"            env_requirements={_format_py_tuple(spec.env_requirements)},"
        )
    if spec.requires_playwright or spec.manifest_path is not None:
        catalog_lines.append(
            f"            requires_playwright={spec.requires_playwright},"
        )
    if spec.requires_browser_runtime or spec.manifest_path is not None:
        catalog_lines.append(
            f"            requires_browser_runtime={spec.requires_browser_runtime},"
        )
    if not spec.html_capable:
        catalog_lines.append("            html_capable=False,")
    catalog_lines.append("        ),")

    bundle_lines = [*catalog_lines]
    if spec.html_capable:
        bundle_lines.extend(
            [
                "        html_rules=ProviderHtmlRules(",
                f'            name="{name}",',
                "            availability=AvailabilityPolicy(",
                f'                name="{name}",',
                "                no_signals=True,",
                "            ),",
                "        ),",
            ]
        )
    bundle_lines.append(f"        sources={_format_py_tuple((spec.source,))},")

    imports = [
        '"""Provider scaffold for TODO: fill provider-specific HTML extraction rules."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
    ]
    if spec.html_capable:
        imports.extend(
            [
                "",
                "from ..extraction.html.availability_policy import AvailabilityPolicy",
                "from ..extraction.html.provider_rules import ProviderHtmlRules",
            ]
        )
    if spec.fulltext_client:
        imports.extend(
            [
                "from ..reason_codes import NOT_SUPPORTED",
                "from .base import ProviderFailure",
            ]
        )
    imports.extend(
        [
            "from ..provider_catalog import ProviderSpec",
            "from ._registry import ProviderBundle, register_provider_bundle",
            "",
            "",
            "register_provider_bundle(",
            "    ProviderBundle(",
            "        # asset_profile from manifest:",
            f"        # none={_format_py_tuple(spec.asset_profile_none)},",
            f"        # body={_format_py_tuple(spec.asset_profile_body)},",
            f"        # all={_format_py_tuple(spec.asset_profile_all)},",
            *bundle_lines,
            "    )",
            ")",
            "",
            "",
            f"def {name}_before_block_normalization(container: Any) -> Any:",
            "    return container",
            "",
            "",
            f"def {name}_normalize_markdown(text: str) -> str:",
            "    return text",
            "",
            "",
            "def extract_authors(html_text: str) -> list[str]:",
            "    return []",
            "",
        ]
    )
    if spec.fulltext_client:
        for step in spec.waterfall_steps:
            imports.extend(
                [
                    "",
                    "",
                    f"def {_step_function_name(name, step)}(client: object, doi: str, metadata: dict[str, object], *, context: object | None = None):",
                    "    del client, doi, metadata, context",
                    f'    raise ProviderFailure(NOT_SUPPORTED, "{display_name} {step} fallback is not implemented yet.")',
                    "",
                ]
            )
    return "\n".join(imports)


def _client_module_content(name: str, waterfall_steps: tuple[str, ...]) -> str:
    class_name = _class_name(name)
    step_lines: list[str] = []
    for step in waterfall_steps:
        step_lines.extend(
            [
                "        WaterfallStep(",
                f'            label="{step}",',
                f"            run=_provider_rules.{_step_function_name(name, step)},",
                f'            failure_marker="fulltext:{name}_{step}_failed",',
                f'            success_markers=("fulltext:{name}_{step}_ok",),',
                "            continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,",
                "        ),",
            ]
        )
    return "\n".join(
        [
            f'"""TODO: fill {name} full-text client implementation."""',
            "",
            "from __future__ import annotations",
            "",
            f"from . import _{name}_html as _provider_rules",
            "from ._waterfall import DEFAULT_WATERFALL_CONTINUE_CODES, WaterfallStep",
            "from .base import ProviderClient",
            "",
            "",
            f"class {class_name}(ProviderClient):",
            f'    name = "{name}"',
            "    waterfall_steps = (",
            *step_lines,
            "    )",
            "",
            "",
            f'__all__ = ["{class_name}"]',
            "",
        ]
    )


def _markdown_contract_test_content(
    name: str,
    contracts: tuple[MarkdownContract, ...],
) -> list[str]:
    if not contracts:
        slug = _doi_slug(contracts[0].doi) if contracts else ""
        return [
            "",
            "",
            "def test_markdown_review_loop_contract_placeholder() -> None:",
            "    assert False, (",
            '        "Replace this scaffold placeholder with real fixture Markdown review "',
            '        "assertions for every non-null manifest purpose, including positive "',
            '        "Markdown assertions and negative site chrome assertions. "',
            f'        "First fixture slug: {slug}"',
            "    )",
        ]

    lines = [
        "",
        "",
        "def _render_markdown_for_fixture(doi: str) -> str:",
        "    raise AssertionError(",
        f'        "Implement {name} fixture replay Markdown rendering before enabling "',
        '        f"provider acceptance for {doi}."',
        "    )",
    ]
    for contract in contracts:
        function_suffix = re.sub(r"[^a-z0-9_]+", "_", contract.purpose.lower())
        lines.extend(
            [
                "",
                "",
                f"def test_markdown_contract_{function_suffix}_fixture() -> None:",
                f"    # markdown-review: purpose={contract.purpose} doi={contract.doi}",
                f'    markdown = _render_markdown_for_fixture("{contract.doi}")',
            ]
        )
        for value in contract.must_include:
            lines.append(f"    assert {_format_py_string(value)} in markdown")
        for value in contract.must_not_include:
            lines.append(f"    assert {_format_py_string(value)} not in markdown")
        for pattern in contract.must_match:
            lines.append(
                f"    assert re.search({_format_py_string(pattern)}, markdown)"
            )
        for value, expected_count in contract.count_equals:
            lines.append(
                f"    assert markdown.count({_format_py_string(value)}) == {expected_count}"
            )
    return lines


def _test_module_content(
    name: str,
    doi: str,
    *,
    html_capable: bool,
    markdown_contracts: tuple[MarkdownContract, ...] = (),
) -> str:
    html_rule_assertions = [
        "    assert bundle.html_rules is not None",
        f'    assert bundle.html_rules.name == "{name}"',
    ]
    if not html_capable:
        html_rule_assertions = [
            "    assert bundle.html_rules is None",
            "    assert bundle.catalog.html_capable is False",
        ]
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import re",
            "",
            "from paper_fetch.provider_catalog import PROVIDER_CATALOG",
            "from paper_fetch.providers._registry import provider_bundle",
            f"import paper_fetch.providers._{name}_html  # noqa: F401",
            "",
            "",
            "def test_provider_bundle_round_trip() -> None:",
            f'    bundle = provider_bundle("{name}")',
            f'    assert bundle.catalog.name == "{name}"',
            *html_rule_assertions,
            "",
            "",
            "def test_provider_catalog_is_readable() -> None:",
            f'    assert PROVIDER_CATALOG["{name}"].name == "{name}"',
            "",
            *_markdown_contract_test_content(name, markdown_contracts),
            "",
        ]
    )


def _manifest_entry(*, name: str, doi: str, html_capable: bool) -> dict[str, object]:
    route_kind = "html" if html_capable else "official"
    content_type = "text/html" if html_capable else "application/octet-stream"
    return {
        "doi": doi,
        "publisher": name,
        "title": "TODO: fill golden criteria title",
        "source_url": "",
        "landing_url": "",
        "route_kind": route_kind,
        "content_type": content_type,
        "origin_kind": "placeholder",
        "usage_kind": "content",
        "fixture_family": "golden",
        "expected_outcome": "pending",
        "assets": {},
    }


def _capture_commands_content(spec: ScaffoldInput) -> str:
    name = spec.name
    if spec.manifest_path is not None:
        lines = [
            f"# Capture commands for {name}",
            "",
            "python3 scripts/capture_fixture.py "
            f"--from-manifest {spec.manifest_path.as_posix()} "
            "--all",
            "",
            "# Null DOI purposes are skipped automatically by --all.",
        ]
        return "\n".join(lines) + "\n"

    lines = [
        f"# Capture commands for {name}",
        "",
    ]
    for sample in spec.fixture_samples:
        lines.extend(
            [
                f"# purpose: {sample.purpose}",
                "python3 scripts/capture_fixture.py "
                f"--doi {sample.doi} "
                f"--provider {name} "
                f"--purpose {sample.purpose}",
            ]
        )
    for purpose in spec.skipped_fixture_purposes:
        lines.append(f"# skipped: {purpose} has null DOI in manifest")
    return "\n".join(lines) + "\n"


def _diff_preview(
    path: Path, planned_content: str, *, max_lines: int = 80
) -> list[str]:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    diff = list(
        difflib.unified_diff(
            existing.splitlines(),
            planned_content.splitlines(),
            fromfile=f"existing/{path.name}",
            tofile=f"planned/{path.name}",
            lineterm="",
        )
    )
    return diff[:max_lines]


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _merge_plan_summary(
    *,
    root: Path,
    spec: ScaffoldInput,
    planned_content: dict[Path, str],
    existing_paths: list[Path],
    manifest_sample_conflicts: list[str],
    reused_fixture_samples: list[str] | None = None,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for path in existing_paths:
        actions.append(
            {
                "path": _rel(path, root),
                "action": "manual_merge",
                "diff_preview": _diff_preview(path, planned_content.get(path, "")),
            }
        )
    for slug in manifest_sample_conflicts:
        actions.append(
            {
                "path": "tests/fixtures/golden_criteria/manifest.json",
                "sample_id": slug,
                "action": "merge_or_reuse_existing_fixture_sample",
            }
        )
    return {
        "status": "MERGE_PLAN",
        "provider": spec.name,
        "reason": "scaffold outputs already exist",
        "generated_files": [],
        "existing_files": [_rel(path, root) for path in existing_paths],
        "manifest_sample_conflicts": manifest_sample_conflicts,
        "reused_fixture_samples": sorted(set(reused_fixture_samples or ())),
        "merge_plan": actions,
    }


def _sync_docs_placeholders(root: Path, *, spec: ScaffoldInput) -> list[Path]:
    name = spec.name
    docs_paths = [
        root / "docs" / "providers.md",
        root / "docs" / "extraction-rules.md",
        root / "CHANGELOG.md",
    ]
    _ensure_scaffold_doc(docs_paths[0], _minimal_providers_doc())
    _ensure_scaffold_doc(docs_paths[1], _minimal_extraction_rules_doc())
    _ensure_scaffold_doc(docs_paths[2], _minimal_changelog_doc())

    todo = f"TODO(scaffold-{name}): fill"
    providers_path, extraction_path, changelog_path = docs_paths

    providers_text = providers_path.read_text(encoding="utf-8")
    provider_anchor = f'<a id="{name.replace("_", "-")}"></a>'
    providers_row = f"| `{name}` | TODO | TODO | TODO | TODO | <!-- {todo} --> |"
    if todo in providers_text or provider_anchor in providers_text:
        providers_changed = False
        provider_section_changed = False
    else:
        providers_row = (
            f"| {spec.docs_providers_md_capability_row} | <!-- {todo} --> |"
            if spec.docs_providers_md_capability_row
            else providers_row
        )
        providers_text, providers_changed = _insert_table_row_after_marker(
            providers_text,
            PROVIDERS_MATRIX_MARKER,
            providers_row,
        )
        provider_section = "\n".join(
            [
                provider_anchor,
                f"### {name.replace('_', ' ').title()}",
                "",
                f"<!-- {todo} routing / waterfall / asset_profile / status docs. -->",
                "",
                "- routing: TODO",
                "- waterfall: TODO",
                "- asset_profile: TODO",
                "- status: TODO",
            ]
        )
        providers_text, provider_section_changed = _insert_before_marker(
            providers_text,
            PROVIDERS_DETAILS_MARKER,
            provider_section,
        )
    if providers_changed or provider_section_changed:
        providers_path.write_text(providers_text, encoding="utf-8")

    extraction_text = extraction_path.read_text(encoding="utf-8")
    extraction_summary = (
        spec.docs_extraction_rules_summary
        or "skipped: manifest docs.extraction_rules_summary is null; fill after fixture replay."
    )
    extraction_row = f"| `{name}` | <!-- {todo} --> | {extraction_summary} | TODO |"
    if todo in extraction_text:
        extraction_changed = False
    else:
        extraction_text, extraction_changed = _insert_table_row_after_marker(
            extraction_text,
            EXTRACTION_RULES_MARKER,
            extraction_row,
        )
    if extraction_changed:
        extraction_path.write_text(extraction_text, encoding="utf-8")

    changelog_text = changelog_path.read_text(encoding="utf-8")
    changelog_summary = (
        spec.docs_changelog_summary
        or f"Add `{name}` provider scaffold docs before enabling the provider."
    )
    changelog_entry = f"- <!-- {todo} --> {changelog_summary}"
    if todo in changelog_text:
        changelog_changed = False
    else:
        changelog_text, changelog_changed = _insert_after_marker(
            changelog_text,
            CHANGELOG_UNRELEASED_MARKER,
            changelog_entry,
        )
    if changelog_changed:
        changelog_path.write_text(changelog_text, encoding="utf-8")

    return docs_paths


def scaffold(
    args: argparse.Namespace,
) -> tuple[list[Path], list[Path], ScaffoldInput, list[str], list[Path]]:
    root = Path(args.output_dir).resolve()
    spec = (
        _scaffold_input_from_manifest(Path(args.from_manifest))
        if args.from_manifest
        else _legacy_scaffold_input(args)
    )
    name = spec.name

    if not NAME_RE.fullmatch(name):
        raise ValueError("--name must be snake_case starting with a lowercase letter")
    if not NAME_RE.fullmatch(spec.source):
        raise ValueError("--source must be snake_case when provided")
    if not DOI_RE.fullmatch(spec.doi):
        raise ValueError("--doi must look like a DOI, for example 10.1234/sample")
    for sample in spec.fixture_samples:
        if not DOI_RE.fullmatch(sample.doi):
            raise ValueError(f"manifest DOI sample must look like a DOI: {sample.doi}")

    html_module = root / "src" / "paper_fetch" / "providers" / f"_{name}_html.py"
    client_module = root / "src" / "paper_fetch" / "providers" / f"{name}.py"
    test_module = root / "tests" / "unit" / f"test_{name}_provider.py"
    fixture_keeps = tuple(
        root
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / _doi_slug(sample.doi)
        / ".gitkeep"
        for sample in spec.fixture_samples
    )
    manifest_path = root / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    capture_commands_path = (
        root / "onboarding" / "capture-commands" / f"{name}.txt"
        if spec.manifest_path is not None
        else None
    )

    html_module_text = _html_module_content(spec=spec)
    client_module_text = _client_module_content(name, spec.waterfall_steps)
    test_module_text = _test_module_content(
        name,
        spec.doi,
        html_capable=spec.html_capable,
        markdown_contracts=spec.markdown_contracts,
    )
    planned_content: dict[Path, str] = {
        html_module: html_module_text,
        test_module: test_module_text,
        **{fixture_keep: "" for fixture_keep in fixture_keeps},
    }
    if capture_commands_path is not None:
        planned_content[capture_commands_path] = _capture_commands_content(spec)
    if spec.fulltext_client:
        planned_content[client_module] = client_module_text
    required_provider_paths = [html_module, test_module]
    provider_output_paths = [html_module, test_module]
    if spec.fulltext_client:
        required_provider_paths.append(client_module)
        provider_output_paths.append(client_module)
    if capture_commands_path is not None:
        provider_output_paths.append(capture_commands_path)

    manifest = _load_manifest(manifest_path)
    samples = manifest["samples"]
    manifest_sample_conflicts: list[str] = []
    for sample in spec.fixture_samples:
        slug = _doi_slug(sample.doi)
        if slug in samples:
            manifest_sample_conflicts.append(slug)
    existing_provider_paths = [path for path in provider_output_paths if path.exists()]
    identical_existing_paths = [
        path
        for path in existing_provider_paths
        if path.read_text(encoding="utf-8") == planned_content.get(path, "")
    ]
    divergent_existing_paths = [
        path for path in existing_provider_paths if path not in identical_existing_paths
    ]
    reused_fixture_samples = sorted(
        {
            _doi_slug(sample.doi)
            for sample in spec.fixture_samples
            if (
                (
                    root
                    / "tests"
                    / "fixtures"
                    / "golden_criteria"
                    / _doi_slug(sample.doi)
                ).exists()
                or _doi_slug(sample.doi) in manifest_sample_conflicts
            )
        }
    )
    if existing_provider_paths and spec.manifest_path is not None:
        merge_existing = getattr(args, "merge_existing", "plan")
        provider_required_outputs_exist = all(
            path.exists() for path in required_provider_paths
        )
        if merge_existing != "safe" or (
            divergent_existing_paths and not provider_required_outputs_exist
        ):
            raise ScaffoldMergePlan(
                _merge_plan_summary(
                    root=root,
                    spec=spec,
                    planned_content=planned_content,
                    existing_paths=existing_provider_paths,
                    manifest_sample_conflicts=manifest_sample_conflicts,
                    reused_fixture_samples=reused_fixture_samples,
                )
            )
    for path in existing_provider_paths:
        if spec.manifest_path is None:
            raise FileExistsError(f"refusing to overwrite existing path: {path}")
    if manifest_sample_conflicts and spec.manifest_path is None:
        raise FileExistsError(
            f"manifest sample already exists: {manifest_sample_conflicts[0]}"
        )

    written: list[Path] = []
    reused_existing_paths = sorted(existing_provider_paths)
    if not html_module.exists():
        _write_new(html_module, html_module_text)
        written.append(html_module)
    if spec.fulltext_client:
        if not client_module.exists():
            _write_new(client_module, client_module_text)
            written.append(client_module)
    seen_fixture_keeps: set[Path] = set()
    for fixture_keep in fixture_keeps:
        if fixture_keep in seen_fixture_keeps:
            continue
        seen_fixture_keeps.add(fixture_keep)
        if fixture_keep.exists():
            continue
        _write_new(fixture_keep)
        written.append(fixture_keep)
    if not test_module.exists():
        _write_new(
            test_module,
            test_module_text,
        )
        written.append(test_module)

    purposes_by_slug: dict[str, list[str]] = {}
    for sample in spec.fixture_samples:
        purposes_by_slug.setdefault(_doi_slug(sample.doi), []).append(sample.purpose)
    for sample in spec.fixture_samples:
        slug = _doi_slug(sample.doi)
        if slug in samples:
            continue
        entry = _manifest_entry(
            name=name,
            doi=sample.doi,
            html_capable=spec.html_capable,
        )
        if spec.manifest_path is not None:
            entry["fixture_purposes"] = purposes_by_slug[slug]
        samples[slug] = entry
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    written.append(manifest_path)
    if capture_commands_path is not None:
        if not capture_commands_path.exists():
            _write_new(capture_commands_path, planned_content[capture_commands_path])
            written.append(capture_commands_path)
    docs_paths = _sync_docs_placeholders(root, spec=spec) if args.sync_docs else []
    return written, docs_paths, spec, reused_fixture_samples, reused_existing_paths


def _json_summary(
    paths: list[Path],
    root: Path,
    *,
    docs_paths: list[Path],
    provider: str,
    reused_fixture_samples: list[str] | None = None,
    reused_existing_paths: list[Path] | None = None,
) -> dict[str, object]:
    def rel(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    return {
        "status": "OK",
        "provider": provider,
        "generated_files": [rel(path) for path in paths],
        "docs_files": [rel(path) for path in docs_paths],
        "reused_fixture_samples": sorted(set(reused_fixture_samples or ())),
        "reused_existing_files": [
            rel(path) for path in sorted(reused_existing_paths or [])
        ],
    }


def _write_scaffold_summary(
    root: Path, provider: str, summary: dict[str, object]
) -> None:
    path = root / "onboarding" / "scaffold" / f"{provider}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    summary["summary_path"] = _rel(path, root)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _print_checklist(paths: list[Path], root: Path, *, docs_paths: list[Path]) -> None:
    print("PR-checklist TODO:")
    print("- Fill ProviderSpec domains, aliases, routing templates, and status_order.")
    print(
        "- Replace placeholder HTML rules with provider-owned cleanup and availability signals."
    )
    print("- Generate baseline Markdown for every non-null manifest fixture purpose.")
    print(
        "- Replace the failing Markdown review-loop placeholder test with provider-local assertions."
    )
    print("- Add positive Markdown assertions for expected article content.")
    print(
        "- Add negative Markdown assertions for site chrome, access noise, and duplicate boilerplate."
    )
    print(
        "- Ensure each non-null fixture purpose is named or asserted in the provider test."
    )
    print("- Run python3 scripts/validate_extraction_rules.py and targeted pytest.")
    print("Generated files:")
    for path in paths:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        print(f"- {rel.as_posix()}")
    if docs_paths:
        print("Docs placeholders to fill:")
        for path in docs_paths:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"- {rel.as_posix()}")


def build_parser() -> argparse.ArgumentParser:
    parser = ScaffoldArgumentParser(
        description="Scaffold provider-owned bundle, tests, and golden fixture placeholders."
    )
    parser.add_argument("--from-manifest", help="provider manifest YAML input path")
    parser.add_argument("--name", help="provider name in snake_case")
    parser.add_argument("--doi", help="placeholder golden DOI")
    parser.add_argument(
        "--source",
        help="public source name to register; defaults to --name",
    )
    parser.add_argument(
        "--fulltext-client",
        action="store_true",
        help="also generate src/paper_fetch/providers/NAME.py client skeleton",
    )
    parser.add_argument(
        "--html-capable",
        type=_parse_html_capable,
        default=None,
        metavar="true|false",
        help="set to false to skip ProviderHtmlRules placeholder",
    )
    parser.add_argument(
        "--output-dir",
        default=_repo_root(),
        help="repo root to write into; defaults to this checkout",
    )
    docs_group = parser.add_mutually_exclusive_group()
    docs_group.add_argument(
        "--sync-docs",
        dest="sync_docs",
        action="store_true",
        help="write docs and changelog scaffold placeholders (default)",
    )
    docs_group.add_argument(
        "--no-sync-docs",
        dest="sync_docs",
        action="store_false",
        help="skip docs and changelog scaffold placeholders",
    )
    parser.add_argument(
        "--merge-existing",
        choices=("plan", "safe"),
        default="plan",
        help=(
            "for --from-manifest, return a merge plan for existing outputs by default; "
            "safe reuses identical files and keeps complete existing provider files"
        ),
    )
    parser.set_defaults(sync_docs=True)
    return parser


def _validate_input_mode(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    del parser
    legacy_values = {
        "--name": args.name,
        "--doi": args.doi,
        "--source": args.source,
    }
    if args.from_manifest:
        mixed = [flag for flag, value in legacy_values.items() if value is not None]
        if args.fulltext_client:
            mixed.append("--fulltext-client")
        if args.html_capable is not None:
            mixed.append("--html-capable")
        if mixed:
            raise ToolError(
                "SCAFFOLD_FORBIDDEN_FLAG_COMBINATION",
                "--from-manifest cannot be combined with " + ", ".join(mixed),
                retryable=False,
                manifest=args.from_manifest,
                task_id="scaffold-validate-input-mode",
                details={"forbidden_flags": mixed},
            )
        return
    missing = [flag for flag in ("--name", "--doi") if getattr(args, flag[2:]) is None]
    if missing:
        raise ToolError(
            "SCAFFOLD_FORBIDDEN_FLAG_COMBINATION",
            "the following arguments are required: " + ", ".join(missing),
            retryable=False,
            task_id="scaffold-validate-input-mode",
            details={"missing_flags": missing},
        )


def _provider_hint_from_manifest(path_value: str | None) -> str | None:
    if not path_value:
        return None
    try:
        import yaml

        data = yaml.safe_load(Path(path_value).read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict) and isinstance(data.get("name"), str):
        return str(data["name"])
    return None


def _task_id_for_scaffold(args: argparse.Namespace, default: str) -> str:
    provider = args.name or _provider_hint_from_manifest(args.from_manifest)
    if provider:
        return f"{provider}-step4-scaffold"
    return default


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_input_mode(parser, args)
        paths, docs_paths, spec, reused_fixture_samples, reused_existing_paths = (
            scaffold(args)
        )
    except ScaffoldMergePlan as exc:
        print(json.dumps(exc.summary, ensure_ascii=False, sort_keys=True))
        return 0
    except ToolError as exc:
        emit_error(
            error_payload(
                exc.code,
                exc.message,
                provider=exc.provider
                or args.name
                or _provider_hint_from_manifest(args.from_manifest),
                manifest=exc.manifest or args.from_manifest,
                task_id=exc.task_id or _task_id_for_scaffold(args, "scaffold"),
                retryable=exc.retryable,
                details=exc.details,
            )
        )
        return 2
    except ManifestSchemaError as exc:
        payload = error_payload(
            MANIFEST_SCHEMA_INVALID,
            "Manifest failed schema validation.",
            provider=_provider_hint_from_manifest(args.from_manifest),
            manifest=args.from_manifest,
            task_id=_task_id_for_scaffold(args, "scaffold-validate-manifest"),
            retryable=False,
            details=exc.details or {"reason": str(exc)},
            extras={"status": MANIFEST_SCHEMA_INVALID, "reason": str(exc)},
        )
        emit_error(payload)
        return 2
    except FileExistsError as exc:
        emit_error(
            error_payload(
                "SCAFFOLD_OUTPUT_EXISTS",
                str(exc),
                provider=args.name or _provider_hint_from_manifest(args.from_manifest),
                manifest=args.from_manifest,
                task_id=_task_id_for_scaffold(args, "scaffold"),
                retryable=False,
                details={
                    "path": str(exc).removeprefix(
                        "refusing to overwrite existing path: "
                    )
                },
            )
        )
        return 2
    except ValueError as exc:
        emit_error(
            error_payload(
                "SCAFFOLD_TEMPLATE_RENDER_FAILED",
                str(exc),
                provider=args.name or _provider_hint_from_manifest(args.from_manifest),
                manifest=args.from_manifest,
                task_id=_task_id_for_scaffold(args, "scaffold"),
                retryable=False,
                details={"reason": str(exc)},
            )
        )
        return 2
    root = Path(args.output_dir).resolve()
    if args.from_manifest:
        summary = _json_summary(
            paths,
            root,
            docs_paths=docs_paths,
            provider=spec.name,
            reused_fixture_samples=reused_fixture_samples,
            reused_existing_paths=reused_existing_paths,
        )
        _write_scaffold_summary(root, spec.name, summary)
        print(
            json.dumps(
                summary,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        _print_checklist(paths, root, docs_paths=docs_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
