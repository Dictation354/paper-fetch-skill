#!/usr/bin/env python3
"""Generate provider onboarding task DAGs and worker briefs."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from fnmatch import fnmatchcase
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, NamedTuple
from collections.abc import Mapping

from bs4 import BeautifulSoup
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from _structured_errors import ToolError, emit_error, error_payload  # noqa: E402
from paper_fetch.config import build_browser_user_agent  # noqa: E402
from paper_fetch.errors import ProviderFailure  # noqa: E402
from paper_fetch.extraction.html.signals import (  # noqa: E402
    CHALLENGE_PATTERNS,
    HtmlExtractionFailure,
    contains_access_gate_text,
)
from paper_fetch.http import HttpTransport, RequestFailure  # noqa: E402
from paper_fetch.markdown_quality import (  # noqa: E402
    PENDING_STATUS,
    blocking_markdown_quality_issues,
    build_fresh_markdown_quality_prompt,
    validate_markdown_quality_report,
)
from paper_fetch.metadata.crossref import CrossrefLookupClient  # noqa: E402
from paper_fetch.publisher_identity import normalize_doi  # noqa: E402
from paper_fetch.utils import normalize_text  # noqa: E402


PROVIDER_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
SCHEMA_PATH = "onboarding/provider-manifest.schema.json"
ACCESS_REVIEW_SCHEMA_PATH = "onboarding/access-review.schema.json"
HARD_CONSTRAINTS_PATH = "onboarding/hard-constraints.md"
FAILURE_RECOVERY_PATH = "onboarding/failure-recovery.md"
STATE_SCHEMA_PATH = "onboarding/onboarding-state.schema.json"
DEFAULT_STATE_PATH = "onboarding/onboarding-state.json"
AGENT_CLI_ENV = "PROVIDER_ONBOARDING_AGENT_CLI"
DEFAULT_CODEX_AGENT_CLI = (
    'codex exec --cd <repo-root> --sandbox workspace-write -c approval_policy="never" -'
)
ACCESS_PREFLIGHT_STEP = "operator-access-preflight"
HUMAN_PREFLIGHT_REVIEW_GATE = "waterfall-preflight-review"
DISCOVER_STEP = "discover-manifest"
IMPLEMENT_STEP = "implement-provider"
PROPOSE_CLEANING_STEP = "propose-cleaning-chain"
SHARED_INTEGRATION_STEP = "shared-integration"
SNAPSHOT_EXPECTED_STEP = "snapshot-expected"
FINAL_MARKDOWN_QUALITY_REVIEW_GATE = "final-markdown-quality-review"
REPAIR_MARKDOWN_QUALITY_STEP = "repair-markdown-quality"
CLEANING_PROPOSAL_DIR = "onboarding/cleaning-chain-proposals"
MAX_WORKER_RETRIES = 3
ROUTING_REQUIREMENTS = [
    "doi_prefixes",
    "domains",
    "domain_suffixes",
    "crossref_publisher",
]
DOI_SAMPLE_PURPOSES = [
    "structure",
    "table",
    "formula",
    "figure",
    "supplementary",
    "references",
    "pdf_fallback",
    "abstract_only",
    "access_gate",
    "empty_shell",
]
MANDATORY_DISCOVERY_PROOF_PURPOSES = [
    "table",
    "formula",
    "supplementary",
]
DISCOVERY_EVIDENCE_RELATIVE_PATH = "discovery/evidence-pack.json"
DISCOVERY_MAX_QUERIES_PER_PURPOSE = 3
DISCOVERY_MAX_METADATA_CANDIDATES_PER_PURPOSE = 6
DISCOVERY_MAX_PAGE_PROBES_PER_PURPOSE = 3
DISCOVERY_PROBE_TIMEOUT_SECONDS = 8
DISCOVERY_HIGH_CONFIDENCE_SCORE = 0.72
DISCOVERY_MEDIUM_CONFIDENCE_SCORE = 0.45
DISCOVERY_NO_NETWORK_ENV = "PAPER_FETCH_DISCOVERY_NO_NETWORK"
DISCOVERY_BROWSER_FALLBACK_MODES = ("auto", "off")
DISCOVERY_FULLTEXT_SAMPLE_PURPOSES = frozenset(
    {
        "structure",
        "table",
        "formula",
        "figure",
        "supplementary",
        "references",
        "pdf_fallback",
    }
)
PURPOSE_KEYWORDS = {
    "structure": ["structure", "abstract", "sections"],
    "table": ["table"],
    "formula": ["formula", "equation", "math"],
    "figure": ["figure", "image"],
    "supplementary": ["supplementary", "supporting information"],
    "references": ["references", "bibliography"],
    "pdf_fallback": ["pdf", "full text"],
    "abstract_only": ["abstract only", "metadata"],
    "access_gate": ["access gate", "paywall"],
    "empty_shell": ["empty shell", "article shell"],
}
PURPOSE_SIGNAL_MAP = {
    "structure": {"article_html", "html_body", "abstract", "sections"},
    "table": {"body_tables", "table"},
    "formula": {"formula", "equation", "mathjax", "mathml", "latex"},
    "figure": {"figures", "body_figures", "body_images"},
    "supplementary": {"supplementary", "supporting_information"},
    "references": {"references", "bibliography"},
    "pdf_fallback": {"pdf_fallback", "pdf_link", "pdf_content"},
    "abstract_only": {"abstract_only", "abstract", "metadata_only"},
    "access_gate": {"access_gate", "challenge", "paywall"},
    "empty_shell": {"empty_shell"},
}
DOI_SCHEMA_RE = re.compile(r"^10\.[^\s/]+/.+")
FILES_MUST_NOT_MODIFY = [
    "src/",
    "tests/",
    "docs/providers.md",
    "CHANGELOG.md",
]
SHARED_FILES_MUST_NOT_MODIFY = [
    "onboarding/known-providers.yml",
    "docs/providers.md",
    "docs/extraction-rules.md",
    "CHANGELOG.md",
]
CENTRAL_PROVIDER_LOGIC_PATHS = [
    "src/paper_fetch/extraction/html/provider_rules.py",
    "src/paper_fetch/quality/html_signals.py",
    "src/paper_fetch/quality/html_availability.py",
]
LEGACY_LIVE_REVIEW_EXEMPT_PROVIDERS = frozenset(
    {
        "arxiv",
        "copernicus",
        "crossref",
        "elsevier",
        "ieee",
        "royalsocietypublishing",
        "springer",
    }
)
SHARED_MARKDOWN_REPAIR_SCOPES = {
    "table": [
        "src/paper_fetch/extraction/markdown_render.py",
        "tests/unit/test_markdown_render.py",
    ],
    "formula": [
        "src/paper_fetch/extraction/markdown_render.py",
        "src/paper_fetch/extraction/html/formula_rules.py",
        "src/paper_fetch/providers/_article_markdown_math.py",
        "tests/unit/test_markdown_render.py",
        "tests/unit/test_article_markdown_math.py",
        "tests/unit/test_formula_rules.py",
    ],
    "figure/asset": [
        "src/paper_fetch/extraction/markdown_render.py",
        "src/paper_fetch/markdown/images.py",
        "tests/unit/test_markdown_render.py",
        "tests/unit/test_markdown_images.py",
    ],
    "references": [
        "src/paper_fetch/markdown/citations.py",
        "src/paper_fetch/extraction/html/citation_anchors.py",
        "tests/unit/test_markdown_citations.py",
        "tests/unit/test_citation_anchors.py",
    ],
}


class CoordinatorArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_error(
            error_payload(
                "TASK_BRIEF_INVALID",
                message,
                provider=None,
                manifest=None,
                task_id="coordinator-parse-args",
                retryable=False,
                details={"reason": message},
            )
        )
        raise SystemExit(2)


class DagStep(NamedTuple):
    id: str
    type: str
    owner: str
    brief: str | None = None
    command: tuple[str, ...] = ()


TASK_DAG: tuple[DagStep, ...] = (
    DagStep(
        id=ACCESS_PREFLIGHT_STEP,
        type="operator-gate",
        owner="operator",
    ),
    DagStep(
        id=DISCOVER_STEP,
        type="worker-brief",
        owner="coordinator-subagent",
        brief="briefs/discover-manifest.yml",
    ),
    DagStep(id="validate-manifest", type="coordinator-check", owner="coordinator"),
    DagStep(id="capture-fixtures", type="coordinator-action", owner="coordinator"),
    DagStep(id=PROPOSE_CLEANING_STEP, type="coordinator-action", owner="coordinator"),
    DagStep(id="scaffold", type="coordinator-action", owner="coordinator"),
    DagStep(
        id=IMPLEMENT_STEP,
        type="worker-brief",
        owner="coordinator-subagent",
        brief="briefs/implement-provider.yml",
    ),
    DagStep(id=SHARED_INTEGRATION_STEP, type="coordinator-action", owner="coordinator"),
    DagStep(id=SNAPSHOT_EXPECTED_STEP, type="coordinator-action", owner="coordinator"),
    DagStep(id="manifest-sync-back", type="coordinator-action", owner="coordinator"),
    DagStep(
        id="provider-local-acceptance", type="coordinator-check", owner="coordinator"
    ),
    DagStep(id="global-lint", type="coordinator-check", owner="coordinator"),
    DagStep(id="merge-ready", type="coordinator-action", owner="coordinator"),
)


class OnboardingSource(NamedTuple):
    provider: str
    manifest: str
    include_discovery: bool
    manifest_yaml: str | None


class MarkdownQualityRepairContext(NamedTuple):
    provider: str
    doi: str
    sample_id: str
    fixture_root: Path
    expected_path: Path
    markdown_path: Path
    prompt_path: Path
    quality_path: Path
    manifest_path: Path
    review_path: Path
    manifest: dict[str, Any]
    golden_sample: dict[str, Any]
    purpose: str | None
    markdown_contract: dict[str, Any]
    quality_report: dict[str, Any]
    persistent_quality_report: dict[str, Any]
    fresh_quality_path: Path | None


class WorkerDispatcher(NamedTuple):
    argv: list[str]
    agent_cli: str
    source: str


def _provider_slug(provider: str) -> str:
    slug = provider.strip().lower()
    if not slug:
        raise ValueError("provider must not be empty")
    if not PROVIDER_RE.fullmatch(slug):
        raise ValueError("provider must be snake_case starting with a lowercase letter")
    return slug


def default_manifest_path(provider: str) -> str:
    return f"onboarding/manifests/{_provider_slug(provider)}.yml"


def default_access_review_path(provider: str) -> str:
    return f"onboarding/access-reviews/{_provider_slug(provider)}.yml"


def default_cleaning_proposal_path(provider: str) -> str:
    return f"{CLEANING_PROPOSAL_DIR}/{_provider_slug(provider)}.yml"


def default_cleaning_evidence_path(provider: str) -> str:
    return f"{CLEANING_PROPOSAL_DIR}/{_provider_slug(provider)}.evidence.yml"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_codex_agent_argv() -> list[str]:
    return [
        "codex",
        "exec",
        "--cd",
        str(_repo_root()),
        "--sandbox",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "-",
    ]


def _worker_dispatcher_label() -> str | None:
    agent_cli = os.environ.get(AGENT_CLI_ENV)
    if agent_cli is not None and agent_cli.strip():
        return agent_cli
    if shutil.which("codex"):
        return shlex.join(_default_codex_agent_argv())
    return None


def _worker_dispatcher(
    *,
    provider: str,
    task: str,
    manifest: str | None = None,
) -> WorkerDispatcher:
    agent_cli = os.environ.get(AGENT_CLI_ENV)
    if agent_cli is not None and agent_cli.strip():
        argv = shlex.split(agent_cli)
        if not argv or not argv[0]:
            raise ToolError(
                "WORKER_AGENT_CLI_MISSING",
                f"{AGENT_CLI_ENV} did not contain an executable command.",
                retryable=False,
                provider=provider,
                manifest=manifest,
                task_id=f"{provider}-{task}",
                details={"env": AGENT_CLI_ENV, "source": "env_override"},
            )
        return WorkerDispatcher(argv=argv, agent_cli=agent_cli, source="env_override")

    if shutil.which("codex"):
        argv = _default_codex_agent_argv()
        return WorkerDispatcher(
            argv=argv,
            agent_cli=shlex.join(argv),
            source="default_codex_cli",
        )

    raise ToolError(
        "WORKER_AGENT_CLI_MISSING",
        (
            "Codex CLI was not found on PATH and "
            f"{AGENT_CLI_ENV} is not set; install codex or set "
            f"{AGENT_CLI_ENV} to a compatible worker CLI."
        ),
        retryable=False,
        provider=provider,
        manifest=manifest,
        task_id=f"{provider}-{task}",
        details={
            "env": AGENT_CLI_ENV,
            "default_dispatcher": DEFAULT_CODEX_AGENT_CLI,
            "codex_on_path": False,
        },
    )


def _load_json_schema(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"schema cannot be loaded: {path}",
            retryable=False,
            task_id="coordinator-load-schema",
            details={"path": path.as_posix(), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"schema root must be an object: {path}",
            retryable=False,
            task_id="coordinator-load-schema",
            details={"path": path.as_posix()},
        )
    return data


def _load_access_review(provider: str) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    path = _repo_root() / default_access_review_path(provider_name)
    if not path.exists():
        raise ToolError(
            "ACCESS_REVIEW_NOT_FOUND",
            "Operator access review is required before discovery.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{ACCESS_PREFLIGHT_STEP}",
            details={
                "path": path.relative_to(_repo_root()).as_posix(),
                "required_before": DISCOVER_STEP,
            },
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolError(
            "ACCESS_REVIEW_SCHEMA_INVALID",
            "Access review YAML is invalid.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{ACCESS_PREFLIGHT_STEP}",
            details={
                "path": path.relative_to(_repo_root()).as_posix(),
                "reason": str(exc),
            },
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "ACCESS_REVIEW_SCHEMA_INVALID",
            "Access review root must be an object.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{ACCESS_PREFLIGHT_STEP}",
            details={"path": path.relative_to(_repo_root()).as_posix()},
        )
    return data


def validate_access_review(provider: str) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    review = _load_access_review(provider_name)
    schema_path = _repo_root() / ACCESS_REVIEW_SCHEMA_PATH
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ToolError(
            "ACCESS_REVIEW_SCHEMA_INVALID",
            "Access review schema validation dependency is missing.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{ACCESS_PREFLIGHT_STEP}",
            details={"reason": str(exc)},
        ) from exc
    schema = _load_json_schema(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(review), key=lambda error: error.json_path)
    if errors:
        error = errors[0]
        raise ToolError(
            "ACCESS_REVIEW_SCHEMA_INVALID",
            "Access review failed schema validation.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{ACCESS_PREFLIGHT_STEP}",
            details={
                "path": default_access_review_path(provider_name),
                "field": error.json_path,
                "reason": error.message,
            },
        )
    if review.get("provider") != provider_name:
        raise ToolError(
            "ACCESS_REVIEW_SCHEMA_INVALID",
            "Access review provider must match the onboarding provider.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{ACCESS_PREFLIGHT_STEP}",
            details={
                "path": default_access_review_path(provider_name),
                "field": "$.provider",
                "expected": provider_name,
                "actual": review.get("provider"),
            },
        )
    if review.get("status") == "blocked" or review.get("may_continue") is not True:
        raise ToolError(
            "ACCESS_REVIEW_NOT_APPROVED",
            "Operator access review does not allow provider onboarding to continue.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{ACCESS_PREFLIGHT_STEP}",
            details={
                "path": default_access_review_path(provider_name),
                "status": review.get("status"),
                "may_continue": review.get("may_continue"),
            },
        )
    return review


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ToolError(
            "MANIFEST_NOT_FOUND",
            "Provider manifest was not found.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="start-validate-manifest",
            details={"path": path.as_posix()},
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest YAML is invalid.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="start-validate-manifest",
            details={"reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest root must be a mapping.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="start-validate-manifest",
            details={"path": path.as_posix()},
        )
    return data


def _manifest_source(path_value: str) -> OnboardingSource:
    manifest_path = Path(path_value)
    if not manifest_path.is_absolute():
        manifest_path = _repo_root() / manifest_path
    manifest = _read_manifest(manifest_path)
    provider_value = manifest.get("name")
    if not isinstance(provider_value, str):
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest must contain string name.",
            retryable=False,
            manifest=path_value,
            task_id="start-validate-manifest",
            details={"field": "name", "expected": "string"},
        )
    provider = _provider_slug(provider_value)
    manifest_yaml = manifest_path.read_text(encoding="utf-8")
    return OnboardingSource(
        provider=provider,
        manifest=path_value,
        include_discovery=False,
        manifest_yaml=manifest_yaml,
    )


def _provider_source(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> OnboardingSource:
    del domain, doi_prefix
    provider_name = _provider_slug(provider)
    return OnboardingSource(
        provider=provider_name,
        manifest=default_manifest_path(provider_name),
        include_discovery=True,
        manifest_yaml=None,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_doi_or_none(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = normalize_doi(value)
    return doi if DOI_SCHEMA_RE.fullmatch(doi) else None


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url
    return None


def _doi_url(doi: str | None) -> str:
    return f"https://doi.org/{doi}" if doi else "https://doi.org/"


def _seed_base_url(domain: str | None) -> str:
    if domain and domain.strip():
        value = domain.strip().rstrip("/")
        if value.startswith(("http://", "https://")):
            return value + "/"
        return f"https://{value}/"
    return "https://doi.org/"


def default_evidence_pack_path(
    provider: str, output_dir: Path | str | None = None
) -> str:
    provider_name = _provider_slug(provider)
    if output_dir is None:
        return f".paper-fetch-runs/{provider_name}-onboarding/{DISCOVERY_EVIDENCE_RELATIVE_PATH}"
    base = Path(output_dir)
    return (base / DISCOVERY_EVIDENCE_RELATIVE_PATH).as_posix()


def _query_identity_terms(
    provider: str, domain: str | None, doi_prefix: str | None
) -> list[str]:
    terms = [provider]
    if domain:
        terms.append(domain)
    if doi_prefix:
        terms.append(doi_prefix.rstrip("/"))
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        normalized = str(term).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def build_discovery_query_plan(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> dict[str, list[str]]:
    provider_name = _provider_slug(provider)
    identity = _query_identity_terms(provider_name, domain, doi_prefix)
    prefix_or_provider = doi_prefix.rstrip("/") if doi_prefix else provider_name
    site_query = f"site:{domain}" if domain else provider_name
    query_plan: dict[str, list[str]] = {}
    for purpose in DOI_SAMPLE_PURPOSES:
        keywords = PURPOSE_KEYWORDS[purpose]
        keyword_phrase = " ".join(keywords[:2])
        queries = [
            f"{provider_name} {prefix_or_provider} {keyword_phrase} DOI candidates",
            f"{site_query} {provider_name} {keyword_phrase} article DOI",
            f"{prefix_or_provider} {keyword_phrase} fixture discovery {identity[0]}",
        ]
        query_plan[purpose] = queries[:DISCOVERY_MAX_QUERIES_PER_PURPOSE]
    return query_plan


def _route_contract_template(step: str) -> dict[str, Any]:
    if step == "article_html":
        return {
            "success_requires": [
                "provider article container is present",
                "title or DOI metadata is present",
                "body text or body sections are present",
            ],
            "reject_if_any": [
                "challenge page",
                "access gate only",
                "site navigation only",
                "empty article shell",
            ],
            "min_body_chars": 1200,
            "min_body_sections": 1,
        }
    if step == "landing_html":
        return {
            "success_requires": [
                "landing page resolves for the DOI",
                "title or DOI metadata is present",
                "route can discover a full text or fallback candidate",
            ],
            "reject_if_any": [
                "challenge page",
                "access gate only",
                "unrelated search page",
                "empty article shell",
            ],
            "min_body_chars": 400,
        }
    if step == "xml":
        return {
            "success_requires": [
                "XML response parses as article metadata or body content",
                "title or DOI metadata is present",
                "article body, references, or abstract nodes are present",
            ],
            "reject_if_any": [
                "HTML wrapper",
                "challenge page",
                "access gate page",
                "error XML",
            ],
        }
    if step == "pdf_fallback":
        return {
            "success_requires": [
                "PDF response has application/pdf content type or PDF magic bytes",
                "PDF text extraction produces body text",
            ],
            "reject_if_any": [
                "HTML wrapper",
                "challenge page",
                "access gate page",
                "error page",
            ],
            "require_pdf_magic": True,
            "reject_html_wrapper": True,
        }
    if step == "abstract_only":
        return {
            "success_requires": [
                "metadata contains DOI or title",
                "abstract text is present",
                "result is marked as abstract-only",
            ],
            "reject_if_any": [
                "fabricated body text",
                "provider fulltext source without fulltext",
            ],
        }
    return {
        "success_requires": [
            "metadata contains DOI or title",
            "source trail marks metadata-only fallback",
        ],
        "reject_if_any": [
            "fabricated body text",
            "provider-specific fulltext source without fulltext",
        ],
    }


def _markdown_contract_template(
    *,
    purpose: str,
    doi: str,
    observed_signals: list[str] | None = None,
) -> dict[str, Any]:
    signals = set(observed_signals or [])
    include_by_purpose = {
        "structure": "## Abstract",
        "table": "Table",
        "formula": "Equation",
        "figure": "Figure",
        "supplementary": "Supplementary",
        "references": "Reference",
        "pdf_fallback": "#",
        "abstract_only": "## Abstract",
        "access_gate": "access",
        "empty_shell": "metadata",
    }
    exclude_by_purpose = {
        "structure": "Download PDF",
        "table": "Google Scholar",
        "formula": "[Formula unavailable]",
        "figure": "Article Metrics",
        "supplementary": "Download Citation",
        "references": "Google Scholar",
        "pdf_fallback": "Access Denied",
        "abstract_only": "References",
        "access_gate": "full text body",
        "empty_shell": "site navigation",
    }
    contract: dict[str, Any] = {
        "doi": doi,
        "must_include": [include_by_purpose.get(purpose, "## Abstract")],
        "must_not_include": [exclude_by_purpose.get(purpose, "Download PDF")],
    }
    if purpose == "table" or "body_tables" in signals:
        contract["must_match"] = [r"(?m)^\|.+\|$"]
    elif purpose == "formula" or {"formula", "mathjax", "mathml"} & signals:
        contract["must_match"] = [r"(?:\$\$|!\[Formula\]|Equation)"]
    elif purpose == "figure" or {"figures", "body_figures"} & signals:
        contract["must_match"] = [r"(?:!\[Figure|\*\*Figure)"]
    return contract


def _contract_templates_for_discovery() -> dict[str, Any]:
    return {
        "route_contract": {
            step: _route_contract_template(step)
            for step in [
                "landing_html",
                "article_html",
                "xml",
                "pdf_fallback",
                "abstract_only",
                "metadata_only",
            ]
        },
        "markdown_contract": {
            purpose: {
                "must_include_hint": _markdown_contract_template(
                    purpose=purpose,
                    doi="10.0000/example",
                )["must_include"],
                "must_not_include_hint": _markdown_contract_template(
                    purpose=purpose,
                    doi="10.0000/example",
                )["must_not_include"],
            }
            for purpose in DOI_SAMPLE_PURPOSES
        },
        "asset_contract": {
            "figures": {
                "with_body_figure_signal": {
                    "inline": "body",
                    "download": "required",
                    "purposes": ["figure"],
                    "exception_reason": None,
                },
                "without_body_figure_signal": {
                    "inline": "not_applicable",
                    "download": "not_applicable",
                    "purposes": ["figure"],
                    "exception_reason": (
                        "Discovery evidence did not show stable body figure assets."
                    ),
                },
            }
        },
    }


def _decode_response_body(response: Mapping[str, Any]) -> str:
    body = response.get("body", b"")
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return str(body)


def _load_optional_access_review(provider: str) -> dict[str, Any] | None:
    try:
        return _load_access_review(provider)
    except ToolError:
        return None


def _access_review_allowed_runtimes(review: Mapping[str, Any] | None) -> set[str]:
    runtimes = review.get("allowed_runtimes") if isinstance(review, Mapping) else None
    if isinstance(runtimes, list):
        return {
            str(runtime).strip().lower() for runtime in runtimes if str(runtime).strip()
        }
    return set()


def _access_review_allows_browser(review: Mapping[str, Any] | None) -> bool:
    return bool(_access_review_allowed_runtimes(review) & {"browser", "playwright"})


def _manifest_probe_for_provider(provider: str) -> dict[str, Any]:
    manifest_path = _repo_root() / default_manifest_path(provider)
    if not manifest_path.exists():
        return {}
    try:
        manifest = _read_manifest(manifest_path)
    except ToolError:
        return {}
    probe = manifest.get("probe") if isinstance(manifest.get("probe"), dict) else {}
    return dict(probe)


def _provider_requires_browser_runtime(provider: str) -> bool:
    probe = _manifest_probe_for_provider(provider)
    if bool(probe.get("requires_browser_runtime") or probe.get("requires_playwright")):
        return True
    try:
        from paper_fetch.provider_catalog import PROVIDER_CATALOG

        spec = PROVIDER_CATALOG.get(provider)
    except Exception:
        return False
    return bool(
        spec
        and (
            getattr(spec, "requires_browser_runtime", False)
            or getattr(spec, "requires_playwright", False)
        )
    )


def _discovery_browser_fallback_policy(
    *,
    provider: str,
    mode: str,
    no_network: bool,
) -> dict[str, Any]:
    review = _load_optional_access_review(provider)
    allowed_runtimes = sorted(_access_review_allowed_runtimes(review))
    provider_requires_browser = _provider_requires_browser_runtime(provider)
    enabled = (
        mode == "auto" and not no_network and _access_review_allows_browser(review)
    )
    disabled_reason = None
    if mode == "off":
        disabled_reason = "cli_disabled"
    elif no_network:
        disabled_reason = "no_network"
    elif not _access_review_allows_browser(review):
        disabled_reason = "access_review_disallows_browser"
    return {
        "mode": mode,
        "enabled": enabled,
        "access_review": default_access_review_path(provider),
        "access_review_present": review is not None,
        "allowed_runtimes": allowed_runtimes,
        "provider_requires_browser_runtime": provider_requires_browser,
        "disabled_reason": disabled_reason,
    }


def _candidate_rejection_hint(purpose: str) -> str:
    keywords = ", ".join(PURPOSE_KEYWORDS.get(purpose, [purpose]))
    return (
        f"Reject if the page does not expose stable {keywords} evidence "
        "or belongs to a different provider route."
    )


def _candidate_confidence(score: float) -> str:
    if score >= DISCOVERY_HIGH_CONFIDENCE_SCORE:
        return "high"
    if score >= DISCOVERY_MEDIUM_CONFIDENCE_SCORE:
        return "medium"
    return "low"


def _merge_candidate(
    candidates: dict[str, dict[str, Any]],
    candidate: dict[str, Any],
) -> None:
    doi = _normalize_doi_or_none(candidate.get("doi"))
    if doi is None:
        return
    candidate["doi"] = doi
    existing = candidates.get(doi)
    if existing is None:
        candidates[doi] = candidate
        return
    for key in [
        "title",
        "journal_title",
        "publisher",
        "landing_page_url",
        "evidence_url",
    ]:
        if not existing.get(key) and candidate.get(key):
            existing[key] = candidate[key]
    existing_queries = existing.setdefault("source_queries", [])
    for query in candidate.get("source_queries") or []:
        if query not in existing_queries:
            existing_queries.append(query)
    existing_sources = existing.setdefault("metadata_sources", [])
    for source in candidate.get("metadata_sources") or []:
        if source not in existing_sources:
            existing_sources.append(source)
    existing_signals = existing.setdefault("observed_signals", [])
    for signal in candidate.get("observed_signals") or []:
        if signal not in existing_signals:
            existing_signals.append(signal)


def _crossref_candidate(
    metadata: Mapping[str, Any],
    *,
    purpose: str,
    query: str,
    domain: str | None = None,
) -> dict[str, Any] | None:
    doi = _normalize_doi_or_none(metadata.get("doi"))
    if doi is None:
        return None
    landing_url = _preferred_crossref_evidence_url(
        metadata,
        purpose=purpose,
        doi=doi,
        domain=domain,
    )
    signals = ["crossref_metadata"]
    if metadata.get("abstract"):
        signals.append("abstract")
    if metadata.get("references"):
        signals.append("references")
    for link in metadata.get("fulltext_links") or []:
        if isinstance(link, Mapping):
            content_type = str(link.get("content_type") or "").lower()
            url = str(link.get("url") or "").lower()
            if "pdf" in content_type or url.endswith(".pdf") or "/pdf" in url:
                signals.append("pdf_link")
    return {
        "doi": doi,
        "purpose": purpose,
        "title": metadata.get("title"),
        "journal_title": metadata.get("journal_title"),
        "publisher": metadata.get("publisher"),
        "landing_page_url": landing_url,
        "evidence_url": landing_url,
        "source_queries": [query],
        "metadata_sources": [{"source": "crossref", "url": metadata.get("source_url")}],
        "observed_signals": sorted(set(signals)),
        "rejection_hint": _candidate_rejection_hint(purpose),
    }


def _preferred_crossref_evidence_url(
    metadata: Mapping[str, Any],
    *,
    purpose: str,
    doi: str,
    domain: str | None = None,
) -> str:
    domain_token = normalize_text(domain).lower()
    pdf_urls: list[str] = []
    html_urls: list[str] = []
    other_urls: list[str] = []
    for link in metadata.get("fulltext_links") or []:
        if not isinstance(link, Mapping):
            continue
        url = _safe_url(link.get("url"))
        if url is None:
            continue
        normalized_url = url.lower()
        if domain_token and domain_token not in normalized_url:
            continue
        content_type = normalize_text(str(link.get("content_type") or "")).lower()
        if "pdf" in content_type or normalized_url.rstrip("/").endswith("/pdf"):
            pdf_urls.append(url)
        elif "html" in content_type or "/article/" in normalized_url:
            html_urls.append(url)
        else:
            other_urls.append(url)
    if purpose == "pdf_fallback" and pdf_urls:
        return pdf_urls[0]
    if html_urls:
        return html_urls[0]
    if pdf_urls:
        return pdf_urls[0]
    if other_urls:
        return other_urls[0]
    return _safe_url(metadata.get("landing_page_url")) or _doi_url(doi)


def _normalized_doi_prefix(value: str | None) -> str | None:
    normalized = normalize_text(value).lower().rstrip("/")
    return normalized or None


def _candidate_matches_provider_seed(
    candidate: Mapping[str, Any],
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> bool:
    normalized_prefix = _normalized_doi_prefix(doi_prefix)
    doi = normalize_text(str(candidate.get("doi") or "")).lower()
    if normalized_prefix and not doi.startswith(f"{normalized_prefix}/"):
        return False
    domain_token = normalize_text(domain).lower().strip("/")
    if not domain_token:
        return True
    url_text = " ".join(
        normalize_text(str(candidate.get(key) or "")).lower()
        for key in ["evidence_url", "landing_page_url"]
    )
    if domain_token in url_text:
        return True
    identity_text = " ".join(
        normalize_text(str(candidate.get(key) or "")).lower()
        for key in ["publisher", "journal_title", "title"]
    )
    provider_terms = {provider.replace("_", " "), provider}
    return any(term and term in identity_text for term in provider_terms)


def _search_crossref_discovery_candidates(
    crossref: Any,
    query: str,
    *,
    doi_prefix: str | None,
    rows: int,
) -> list[Mapping[str, Any]]:
    if doi_prefix:
        try:
            return list(
                crossref.search_bibliographic_candidates(
                    query,
                    rows=rows,
                    doi_prefix=_normalized_doi_prefix(doi_prefix),
                )
            )
        except TypeError as exc:
            if "doi_prefix" not in str(exc):
                raise
    return list(crossref.search_bibliographic_candidates(query, rows=rows))


def _openalex_candidates(
    *,
    transport: Any,
    query: str,
    purpose: str,
) -> list[dict[str, Any]]:
    try:
        response = transport.request(
            "GET",
            "https://api.openalex.org/works",
            headers={"Accept": "application/json"},
            query={"search": query, "per-page": "3"},
            timeout=DISCOVERY_PROBE_TIMEOUT_SECONDS,
            retry_on_rate_limit=True,
            retry_on_transient=True,
        )
    except Exception:
        return []
    try:
        payload = json.loads(_decode_response_body(response))
    except json.JSONDecodeError:
        return []
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    candidates: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, Mapping):
            continue
        doi = _normalize_doi_or_none(item.get("doi"))
        if doi is None:
            continue
        primary_location = item.get("primary_location")
        source = (
            primary_location.get("source")
            if isinstance(primary_location, Mapping)
            else {}
        )
        landing_url = _safe_url(item.get("landing_page_url"))
        if landing_url is None and isinstance(primary_location, Mapping):
            landing_url = _safe_url(primary_location.get("landing_page_url"))
        signals = ["openalex_metadata"]
        abstract = item.get("abstract_inverted_index")
        if isinstance(abstract, dict) and abstract:
            signals.append("abstract")
        if item.get("referenced_works_count"):
            signals.append("references")
        candidates.append(
            {
                "doi": doi,
                "purpose": purpose,
                "title": item.get("display_name"),
                "journal_title": (
                    source.get("display_name") if isinstance(source, Mapping) else None
                ),
                "publisher": item.get("publisher"),
                "landing_page_url": landing_url or _doi_url(doi),
                "evidence_url": landing_url or _doi_url(doi),
                "source_queries": [query],
                "metadata_sources": [
                    {"source": "openalex", "url": item.get("id") or response.get("url")}
                ],
                "observed_signals": signals,
                "rejection_hint": _candidate_rejection_hint(purpose),
            }
        )
    return candidates


def _probe_landing_page(
    *,
    transport: Any,
    url: str,
    purpose: str,
    provider: str | None = None,
    browser_fallback_enabled: bool = False,
    browser_required: bool = False,
    browser_probe_func: Any | None = None,
) -> dict[str, Any]:
    http_probe = _http_probe_landing_page(transport=transport, url=url, purpose=purpose)
    fallback_reason = _browser_fallback_reason(
        http_probe,
        purpose=purpose,
        browser_required=browser_required,
    )
    if not browser_fallback_enabled or fallback_reason is None:
        return _decorate_probe_result(
            http_probe,
            route="http",
            browser_attempted=False,
            fallback_from=None,
            http_probe=http_probe,
            browser_probe=None,
        )

    probe_func = browser_probe_func or _browser_probe_landing_page
    browser_probe = probe_func(url=url, purpose=purpose, provider=provider)
    browser_failure_code = _probe_failure_code(browser_probe)
    if browser_probe.get("status") == "ok":
        return _decorate_probe_result(
            browser_probe,
            route="browser",
            browser_attempted=True,
            fallback_from=fallback_reason,
            http_probe=http_probe,
            browser_probe=browser_probe,
        )

    result = _decorate_probe_result(
        http_probe,
        route="http",
        browser_attempted=True,
        fallback_from=fallback_reason,
        http_probe=http_probe,
        browser_probe=browser_probe,
    )
    result["browser_failure_code"] = browser_failure_code
    return result


def _decorate_probe_result(
    probe: Mapping[str, Any],
    *,
    route: str,
    browser_attempted: bool,
    fallback_from: str | None,
    http_probe: Mapping[str, Any],
    browser_probe: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result = dict(probe)
    result["route"] = route
    result["browser_attempted"] = browser_attempted
    result["fallback_from"] = fallback_from
    result["http_probe"] = dict(http_probe)
    if browser_probe is not None:
        result["browser_probe"] = dict(browser_probe)
    return result


def _http_probe_landing_page(
    *,
    transport: Any,
    url: str,
    purpose: str,
) -> dict[str, Any]:
    try:
        response = transport.request(
            "GET",
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1",
            },
            timeout=DISCOVERY_PROBE_TIMEOUT_SECONDS,
            retry_on_rate_limit=False,
            retry_on_transient=True,
        )
    except (ProviderFailure, RequestFailure, Exception) as exc:
        return {
            "url": url,
            "status": "request_failed",
            "route": "http",
            "observed_signals": [],
            "reason": str(exc),
        }
    return _html_probe_from_response(response, url=url, purpose=purpose, route="http")


def _browser_probe_landing_page(
    *,
    url: str,
    purpose: str,
    provider: str | None = None,
) -> dict[str, Any]:
    try:
        from paper_fetch.providers.browser_workflow.html_extraction import (
            fetch_html_with_fast_browser,
        )

        result = fetch_html_with_fast_browser(
            [url],
            publisher=provider or "unknown",
            user_agent=build_browser_user_agent(os.environ),
            timeout_ms=DISCOVERY_PROBE_TIMEOUT_SECONDS * 1000,
        )
    except HtmlExtractionFailure as exc:
        return _browser_failure_probe(url=url, exc=exc)
    except Exception as exc:
        return _browser_failure_probe(url=url, exc=exc)

    headers = {
        str(key).lower(): str(value)
        for key, value in (result.response_headers or {}).items()
    }
    headers.setdefault("content-type", "text/html")
    return _html_probe_from_response(
        {
            "headers": headers,
            "body": result.html,
            "url": result.final_url or url,
            "status_code": result.response_status or 200,
        },
        url=url,
        purpose=purpose,
        route="browser",
    )


def _browser_failure_probe(*, url: str, exc: Exception) -> dict[str, Any]:
    failure_code = (
        getattr(exc, "reason", None)
        or getattr(exc, "kind", None)
        or getattr(exc, "code", None)
        or exc.__class__.__name__
    )
    message = getattr(exc, "message", None) or str(exc)
    signals = _signals_from_failure_code(str(failure_code))
    return {
        "url": url,
        "status": "request_failed",
        "route": "browser",
        "observed_signals": signals,
        "reason": str(message),
        "browser_failure_code": str(failure_code),
    }


def _signals_from_failure_code(failure_code: str) -> list[str]:
    normalized = failure_code.strip().lower()
    signals: list[str] = []
    if any(token in normalized for token in ["challenge", "captcha", "cloudflare"]):
        signals.append("challenge")
    if any(
        token in normalized for token in ["access", "paywall", "forbidden", "denied"]
    ):
        signals.append("access_gate")
    if "empty" in normalized:
        signals.append("empty_shell")
    return signals


def _html_probe_from_response(
    response: Mapping[str, Any],
    *,
    url: str,
    purpose: str,
    route: str,
) -> dict[str, Any]:
    content_type = str(
        (response.get("headers") or {}).get("content-type") or ""
    ).lower()
    body = _decode_response_body(response)
    signals: list[str] = []
    if "pdf" in content_type or body.startswith("%PDF"):
        signals.extend(["pdf_fallback", "pdf_content"])
        return {
            "url": response.get("url") or url,
            "status": "ok",
            "route": route,
            "status_code": response.get("status_code"),
            "content_type": content_type,
            "observed_signals": sorted(set(signals)),
        }
    body_fragment = body[:250_000]
    body_lower = body_fragment.lower()
    soup = BeautifulSoup(body_fragment, "html.parser")
    text = " ".join(soup.get_text(" ", strip=True).split())
    text_lower = text.lower()
    if soup.find(["article", "main"]) or len(text) >= 1200:
        signals.extend(["article_html", "html_body"])
    if soup.find("abstract") or "abstract" in text_lower:
        signals.append("abstract")
    if soup.find("table") or re.search(r"\btable\s+\d+\b", text_lower):
        signals.extend(["body_tables", "table"])
    if soup.find("math") or any(
        token in body.lower() for token in ["mathjax", "mathml", "<mml:math"]
    ):
        signals.extend(["formula", "mathml"])
    if re.search(r"\b(equation|formula)\s+\d+\b", text_lower):
        signals.extend(["formula", "equation"])
    if soup.find("figure") or soup.select("img[src]"):
        signals.extend(["figures", "body_figures"])
    if "supplementary" in text_lower or "supporting information" in text_lower:
        signals.extend(["supplementary", "supporting_information"])
    if "references" in text_lower or "bibliography" in text_lower:
        signals.extend(["references", "bibliography"])
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href") or "").lower()
        label = anchor.get_text(" ", strip=True).lower()
        if href.endswith(".pdf") or "/pdf" in href or label == "pdf":
            signals.append("pdf_link")
        if (
            "supplement" in href
            or "supplement" in label
            or "supporting information" in label
        ):
            signals.append("supplementary")
    status_code = _response_status_code(response)
    if any(token in body_lower or token in text_lower for token in CHALLENGE_PATTERNS):
        signals.append("challenge")
    if status_code in {401, 402, 403}:
        signals.extend(["access_gate", f"http_{status_code}"])
    if status_code == 429:
        signals.extend(["rate_limited", "http_429"])
    if contains_access_gate_text(text_lower) or any(
        token in text_lower
        for token in ["access denied", "sign in", "subscribe", "purchase access"]
    ):
        signals.append("access_gate")
    if len(text) < 500 and not (set(signals) & {"html_body", "pdf_content"}):
        signals.append("empty_shell")
    if purpose in PURPOSE_SIGNAL_MAP and PURPOSE_SIGNAL_MAP[purpose] & set(signals):
        signals.append(f"{purpose}_evidence")
    status = "ok"
    if route == "browser":
        if "challenge" in signals:
            status = "challenge"
        elif "access_gate" in signals:
            status = "access_gate"
        elif "empty_shell" in signals:
            status = "empty_shell"
    return {
        "url": response.get("url") or url,
        "status": status,
        "route": route,
        "status_code": status_code,
        "content_type": content_type,
        "title": soup.title.get_text(" ", strip=True) if soup.title else None,
        "body_chars": len(text),
        "observed_signals": sorted(set(signals)),
    }


def _response_status_code(response: Mapping[str, Any]) -> int | None:
    status_code = response.get("status_code")
    try:
        return int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        return None


def _probe_failure_code(probe: Mapping[str, Any]) -> str | None:
    explicit = probe.get("browser_failure_code")
    if explicit:
        return str(explicit)
    status = str(probe.get("status") or "").strip()
    if status and status != "ok":
        return status
    status_code = _response_status_code(probe)
    if status_code in {401, 402, 403, 429}:
        return f"http_{status_code}"
    signals = {str(signal) for signal in probe.get("observed_signals") or []}
    for signal in ("challenge", "access_gate", "empty_shell"):
        if signal in signals:
            return signal
    return None


def _browser_fallback_reason(
    probe: Mapping[str, Any],
    *,
    purpose: str,
    browser_required: bool,
) -> str | None:
    status = str(probe.get("status") or "")
    if status == "request_failed":
        return "http_request_failed"
    status_code = _response_status_code(probe)
    if status_code in {401, 402, 403, 429}:
        return "http_access_or_rate_limit"
    signals = {str(signal) for signal in probe.get("observed_signals") or []}
    if "challenge" in signals:
        return "http_challenge"
    if "empty_shell" in signals:
        return "http_empty_shell"
    expected = PURPOSE_SIGNAL_MAP.get(purpose)
    if expected and not (expected & signals):
        return (
            "browser_required_missing_purpose_signal"
            if browser_required
            else "http_missing_purpose_signal"
        )
    return None


def _score_discovery_candidate(
    candidate: Mapping[str, Any],
    *,
    purpose: str,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> float:
    score = 0.1 if _normalize_doi_or_none(candidate.get("doi")) else 0.0
    doi = str(candidate.get("doi") or "").lower()
    if doi_prefix and doi.startswith(doi_prefix.rstrip("/").lower()):
        score += 0.25
    evidence_url = str(
        candidate.get("evidence_url") or candidate.get("landing_page_url") or ""
    ).lower()
    if domain and domain.lower().strip("/") in evidence_url:
        score += 0.18
    identity_text = " ".join(
        str(candidate.get(key) or "")
        for key in ["publisher", "journal_title", "title", "landing_page_url"]
    ).lower()
    provider_terms = {provider.replace("_", " "), provider}
    if domain:
        provider_terms.add(domain.lower())
    if any(term and term in identity_text for term in provider_terms):
        score += 0.16
    signals = set(str(signal) for signal in candidate.get("observed_signals") or [])
    if PURPOSE_SIGNAL_MAP.get(purpose, set()) & signals:
        score += 0.3
    if f"{purpose}_evidence" in signals:
        score += 0.12
    if {"article_html", "html_body"} & signals and purpose in {
        "structure",
        "table",
        "formula",
        "figure",
        "supplementary",
        "references",
    }:
        score += 0.08
    if "crossref_metadata" in signals or "openalex_metadata" in signals:
        score += 0.06
    probe = candidate.get("probe")
    if isinstance(probe, Mapping):
        score += 0.04
        failure_code = normalize_text(_probe_failure_code(probe)).lower()
        if purpose in DISCOVERY_FULLTEXT_SAMPLE_PURPOSES and any(
            token in failure_code
            for token in [
                "access",
                "captcha",
                "challenge",
                "cloudflare",
                "denied",
                "empty",
                "forbidden",
            ]
        ):
            score = min(score, DISCOVERY_MEDIUM_CONFIDENCE_SCORE)
    elif purpose in DISCOVERY_FULLTEXT_SAMPLE_PURPOSES:
        score = min(score, DISCOVERY_MEDIUM_CONFIDENCE_SCORE)
    return min(score, 1.0)


def _finalize_discovery_candidate(
    candidate: dict[str, Any],
    *,
    purpose: str,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
) -> dict[str, Any]:
    signals = list(
        dict.fromkeys(str(signal) for signal in candidate.get("observed_signals") or [])
    )
    candidate["observed_signals"] = signals
    score = _score_discovery_candidate(
        candidate,
        purpose=purpose,
        provider=provider,
        domain=domain,
        doi_prefix=doi_prefix,
    )
    candidate["score"] = round(score, 3)
    candidate["confidence"] = _candidate_confidence(score)
    candidate.setdefault(
        "evidence_url",
        candidate.get("landing_page_url") or _doi_url(candidate.get("doi")),
    )
    candidate.setdefault("rejection_hint", _candidate_rejection_hint(purpose))
    return candidate


def _prepare_discovery_candidates(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    query_plan: dict[str, list[str]],
    transport: Any,
    browser_fallback_enabled: bool = False,
    browser_required: bool = False,
    browser_probe_func: Any | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    crossref = CrossrefLookupClient(transport, os.environ)
    candidates_by_purpose: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []
    for purpose, queries in query_plan.items():
        merged: dict[str, dict[str, Any]] = {}
        for query in queries:
            try:
                for metadata in _search_crossref_discovery_candidates(
                    crossref,
                    query,
                    doi_prefix=doi_prefix,
                    rows=3,
                ):
                    candidate = _crossref_candidate(
                        metadata,
                        purpose=purpose,
                        query=query,
                        domain=domain,
                    )
                    if candidate is not None:
                        _merge_candidate(merged, candidate)
            except Exception as exc:
                errors.append(
                    {
                        "source": "crossref",
                        "purpose": purpose,
                        "query": query,
                        "reason": str(exc),
                    }
                )
            for candidate in _openalex_candidates(
                transport=transport,
                query=query,
                purpose=purpose,
            ):
                _merge_candidate(merged, candidate)
        candidates = [
            candidate
            for candidate in merged.values()
            if _candidate_matches_provider_seed(
                candidate,
                provider=provider,
                domain=domain,
                doi_prefix=doi_prefix,
            )
        ]
        candidates.sort(
            key=lambda candidate: (
                -_score_discovery_candidate(
                    candidate,
                    purpose=purpose,
                    provider=provider,
                    domain=domain,
                    doi_prefix=doi_prefix,
                ),
                str(candidate.get("doi") or ""),
            )
        )
        candidates = candidates[:DISCOVERY_MAX_METADATA_CANDIDATES_PER_PURPOSE]
        for candidate in candidates[:DISCOVERY_MAX_PAGE_PROBES_PER_PURPOSE]:
            url = _safe_url(candidate.get("landing_page_url")) or _doi_url(
                candidate.get("doi")
            )
            probe = _probe_landing_page(
                transport=transport,
                url=url,
                purpose=purpose,
                provider=provider,
                browser_fallback_enabled=browser_fallback_enabled,
                browser_required=browser_required,
                browser_probe_func=browser_probe_func,
            )
            candidate["probe"] = probe
            candidate["evidence_url"] = _safe_url(probe.get("url")) or url
            for signal in probe.get("observed_signals") or []:
                signals = candidate.setdefault("observed_signals", [])
                if signal not in signals:
                    signals.append(signal)
        finalized = [
            _finalize_discovery_candidate(
                candidate,
                purpose=purpose,
                provider=provider,
                domain=domain,
                doi_prefix=doi_prefix,
            )
            for candidate in candidates
        ]
        finalized.sort(
            key=lambda item: (
                -float(item.get("score") or 0),
                str(item.get("doi") or ""),
            )
        )
        candidates_by_purpose[purpose] = finalized
    return candidates_by_purpose, errors


def prepare_manifest_discovery(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    output_dir: Path | str,
    no_network: bool = False,
    browser_fallback: str = "auto",
    transport: Any | None = None,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    fallback_mode = str(browser_fallback or "auto").strip().lower()
    if fallback_mode not in DISCOVERY_BROWSER_FALLBACK_MODES:
        raise ValueError(
            "--browser-fallback must be one of: "
            + ", ".join(DISCOVERY_BROWSER_FALLBACK_MODES)
        )
    output_path = Path(default_evidence_pack_path(provider_name, output_dir))
    if not output_path.is_absolute():
        output_path = _repo_root() / output_path
    query_plan = build_discovery_query_plan(
        provider=provider_name,
        domain=domain,
        doi_prefix=doi_prefix,
    )
    fallback_policy = _discovery_browser_fallback_policy(
        provider=provider_name,
        mode=fallback_mode,
        no_network=no_network,
    )
    pack: dict[str, Any] = {
        "schema_version": 1,
        "provider": provider_name,
        "generated_at": _utc_now_iso(),
        "network": {"enabled": not no_network},
        "browser_fallback": fallback_policy,
        "provider_seed": {
            "name": provider_name,
            "domain": domain,
            "doi_prefix_hint": doi_prefix,
        },
        "routing_evidence": {
            "seed_domain": domain,
            "seed_doi_prefix": doi_prefix,
            "identity_terms": _query_identity_terms(provider_name, domain, doi_prefix),
            "candidate_primary": "doi_prefix" if doi_prefix else "domain",
        },
        "query_plan": query_plan,
        "doi_candidates": {purpose: [] for purpose in DOI_SAMPLE_PURPOSES},
        "network_errors": [],
    }
    if not no_network:
        active_transport = transport or HttpTransport(
            cache_ttl=300,
            max_response_bytes=250_000,
            pool_num_pools=4,
            pool_maxsize=2,
            per_host_concurrency=2,
        )
        candidates, errors = _prepare_discovery_candidates(
            provider=provider_name,
            domain=domain,
            doi_prefix=doi_prefix,
            query_plan=query_plan,
            transport=active_transport,
            browser_fallback_enabled=bool(fallback_policy.get("enabled")),
            browser_required=bool(
                fallback_policy.get("provider_requires_browser_runtime")
            ),
        )
        pack["doi_candidates"] = candidates
        pack["network_errors"] = errors
    write_text(output_path, json.dumps(pack, indent=2, sort_keys=True) + "\n")
    return pack


def _compact_evidence_pack_summary(pack: Mapping[str, Any]) -> dict[str, Any]:
    query_plan = (
        pack.get("query_plan") if isinstance(pack.get("query_plan"), Mapping) else {}
    )
    candidates = (
        pack.get("doi_candidates")
        if isinstance(pack.get("doi_candidates"), Mapping)
        else {}
    )
    summary: dict[str, Any] = {
        "provider": pack.get("provider"),
        "network_enabled": bool((pack.get("network") or {}).get("enabled"))
        if isinstance(pack.get("network"), Mapping)
        else None,
        "query_count_by_purpose": {
            str(purpose): len(queries) if isinstance(queries, list) else 0
            for purpose, queries in query_plan.items()
        },
        "top_candidates": {},
    }
    top_candidates: dict[str, Any] = {}
    for purpose, items in candidates.items():
        if not isinstance(items, list) or not items:
            continue
        top = items[0]
        if not isinstance(top, Mapping):
            continue
        top_candidates[str(purpose)] = {
            "doi": top.get("doi"),
            "score": top.get("score"),
            "confidence": top.get("confidence"),
            "observed_signals": top.get("observed_signals"),
            "evidence_url": top.get("evidence_url"),
            "probe_route": (top.get("probe") or {}).get("route")
            if isinstance(top.get("probe"), Mapping)
            else None,
            "browser_attempted": (top.get("probe") or {}).get("browser_attempted")
            if isinstance(top.get("probe"), Mapping)
            else None,
        }
    summary["top_candidates"] = top_candidates
    return summary


def _load_evidence_pack(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "DISCOVERY_EVIDENCE_INVALID",
            "Discovery evidence pack cannot be loaded.",
            retryable=False,
            task_id="prepare-discovery",
            details={"path": path.as_posix(), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "DISCOVERY_EVIDENCE_INVALID",
            "Discovery evidence pack root must be an object.",
            retryable=False,
            task_id="prepare-discovery",
            details={"path": path.as_posix()},
        )
    return data


def _candidate_list(
    evidence_pack: Mapping[str, Any], purpose: str
) -> list[dict[str, Any]]:
    raw_candidates = evidence_pack.get("doi_candidates")
    if not isinstance(raw_candidates, Mapping):
        return []
    items = raw_candidates.get(purpose)
    if not isinstance(items, list):
        return []
    candidates = [item for item in items if isinstance(item, dict)]
    candidates.sort(
        key=lambda item: (-float(item.get("score") or 0), str(item.get("doi") or ""))
    )
    return candidates


def _best_high_confidence_candidate(
    evidence_pack: Mapping[str, Any],
    purpose: str,
) -> dict[str, Any] | None:
    for candidate in _candidate_list(evidence_pack, purpose):
        doi = _normalize_doi_or_none(candidate.get("doi"))
        score = float(candidate.get("score") or 0)
        if doi and (
            candidate.get("confidence") == "high"
            or score >= DISCOVERY_HIGH_CONFIDENCE_SCORE
        ):
            return candidate
    return None


def _autofix_default_routing(evidence_pack: Mapping[str, Any]) -> dict[str, Any]:
    seed = (
        evidence_pack.get("provider_seed")
        if isinstance(evidence_pack.get("provider_seed"), Mapping)
        else {}
    )
    provider = str(seed.get("name") or evidence_pack.get("provider") or "provider")
    domain = str(seed.get("domain") or "").strip()
    doi_prefix = str(seed.get("doi_prefix_hint") or "").strip()
    return {
        "primary": "doi_prefix" if doi_prefix else "domain",
        "doi_prefixes": [doi_prefix if doi_prefix.endswith("/") else f"{doi_prefix}/"]
        if doi_prefix
        else [],
        "domains": [domain] if domain else [],
        "domain_suffixes": [],
        "publisher_aliases": [provider.replace("_", " ")],
        "crossref_publisher": None,
    }


def _sample_from_candidate(
    candidate: Mapping[str, Any] | None,
    *,
    purpose: str,
    domain: str | None,
) -> dict[str, Any]:
    if candidate is None:
        return {
            "doi": None,
            "evidence_url": _seed_base_url(domain),
            "evidence_reason": (
                f"Discovery evidence did not produce a high-confidence {purpose} DOI sample."
            ),
            "observed_signals": [],
            "confidence": "low",
        }
    doi = _normalize_doi_or_none(candidate.get("doi"))
    return {
        "doi": doi,
        "evidence_url": _safe_url(candidate.get("evidence_url")) or _doi_url(doi),
        "evidence_reason": (
            f"Discovery evidence selected {doi} for {purpose} with "
            f"{candidate.get('confidence', 'low')} confidence."
        ),
        "observed_signals": [
            str(signal)
            for signal in candidate.get("observed_signals") or ["crossref_metadata"]
        ],
        "confidence": str(candidate.get("confidence") or "low"),
    }


def _ensure_manifest_containers(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    provider = str(manifest.get("name") or evidence_pack.get("provider") or "provider")
    seed = (
        evidence_pack.get("provider_seed")
        if isinstance(evidence_pack.get("provider_seed"), Mapping)
        else {}
    )
    domain = seed.get("domain") if isinstance(seed.get("domain"), str) else None
    if not manifest.get("schema_version"):
        manifest["schema_version"] = 1
        changes.append("schema_version")
    if not isinstance(manifest.get("name"), str):
        manifest["name"] = provider
        changes.append("name")
    if not isinstance(manifest.get("display_source"), str):
        manifest["display_source"] = f"{_provider_slug(str(manifest['name']))}_html"
        changes.append("display_source")
    generation = manifest.get("generation")
    if not isinstance(generation, dict):
        generation = {}
        manifest["generation"] = generation
        changes.append("generation")
    for key, value in {
        "generated_by": "ai_discovery",
        "generated_at": _utc_now_iso(),
        "source_queries": [],
        "confidence": "low",
    }.items():
        if key not in generation or generation.get(key) in (None, "", []):
            generation[key] = value
            changes.append(f"generation.{key}")
    if not isinstance(manifest.get("routing"), dict):
        manifest["routing"] = _autofix_default_routing(evidence_pack)
        changes.append("routing")
    if not isinstance(manifest.get("main_path"), list) or not manifest.get("main_path"):
        manifest["main_path"] = ["article_html", "pdf_fallback", "metadata_only"]
        changes.append("main_path")
    if not isinstance(manifest.get("success_criteria"), dict):
        manifest["success_criteria"] = {}
        changes.append("success_criteria")
    for step in manifest.get("main_path") or []:
        if step not in manifest["success_criteria"]:
            manifest["success_criteria"][step] = {}
            changes.append(f"success_criteria.{step}")
    if not isinstance(manifest.get("route_contract"), dict):
        manifest["route_contract"] = {}
        changes.append("route_contract")
    if not isinstance(manifest.get("markdown_contract"), dict):
        manifest["markdown_contract"] = {}
        changes.append("markdown_contract")
    if not isinstance(manifest.get("asset_profile"), dict):
        manifest["asset_profile"] = {
            "none": [],
            "body": ["figures", "body_tables", "formula_images"],
            "all": ["figures", "body_tables", "formula_images", "supplementary"],
        }
        changes.append("asset_profile")
    if not isinstance(manifest.get("asset_contract"), dict):
        manifest["asset_contract"] = {}
        changes.append("asset_contract")
    if not isinstance(manifest.get("supplementary_scope"), dict):
        manifest["supplementary_scope"] = {"selector": None, "url_pattern": None}
        changes.append("supplementary_scope")
    if not manifest.get("abstract_only_strategy"):
        manifest["abstract_only_strategy"] = "metadata_only"
        changes.append("abstract_only_strategy")
    if not isinstance(manifest.get("probe"), dict):
        manifest["probe"] = {
            "env_requirements": [],
            "requires_playwright": False,
            "requires_browser_runtime": False,
            "ping_url": _seed_base_url(domain) if domain else None,
        }
        changes.append("probe")
    else:
        probe = manifest["probe"]
        for key, value in {
            "env_requirements": [],
            "requires_playwright": False,
            "requires_browser_runtime": False,
        }.items():
            if key not in probe:
                probe[key] = value
                changes.append(f"probe.{key}")
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, dict):
        fixtures = {}
        manifest["fixtures"] = fixtures
        changes.append("fixtures")
    if not isinstance(fixtures.get("doi_samples"), dict):
        fixtures["doi_samples"] = {}
        changes.append("fixtures.doi_samples")
    if not isinstance(fixtures.get("discovery_proof"), dict):
        fixtures["discovery_proof"] = {}
        changes.append("fixtures.discovery_proof")
    if not isinstance(manifest.get("extraction_hints"), dict):
        manifest["extraction_hints"] = {}
        changes.append("extraction_hints")
    for key, value in {
        "datalayer_signal_set": None,
        "text_marker_signal_set": None,
        "front_matter": None,
        "asset_retry": None,
        "metadata_merge": [],
    }.items():
        if key not in manifest["extraction_hints"]:
            manifest["extraction_hints"][key] = value
            changes.append(f"extraction_hints.{key}")
    if not isinstance(manifest.get("owner_reuse_exceptions"), list):
        manifest["owner_reuse_exceptions"] = []
        changes.append("owner_reuse_exceptions")
    if not isinstance(manifest.get("docs"), dict):
        manifest["docs"] = {
            "providers_md_capability_row": (
                f"{manifest['name']} | discovery-generated routing | pending implementation"
            ),
            "changelog_summary": (
                f"Add discovery-generated onboarding manifest for {manifest['name']}."
            ),
        }
        changes.append("docs")
    else:
        docs = manifest["docs"]
        if not docs.get("providers_md_capability_row"):
            docs["providers_md_capability_row"] = (
                f"{manifest['name']} | discovery-generated routing | pending implementation"
            )
            changes.append("docs.providers_md_capability_row")
        if not docs.get("changelog_summary"):
            docs["changelog_summary"] = (
                f"Add discovery-generated onboarding manifest for {manifest['name']}."
            )
            changes.append("docs.changelog_summary")


def _autofix_doi_samples(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    seed = (
        evidence_pack.get("provider_seed")
        if isinstance(evidence_pack.get("provider_seed"), Mapping)
        else {}
    )
    domain = seed.get("domain") if isinstance(seed.get("domain"), str) else None
    doi_samples = manifest["fixtures"]["doi_samples"]
    for purpose in DOI_SAMPLE_PURPOSES:
        sample = doi_samples.get(purpose)
        if not isinstance(sample, dict):
            candidate = _best_high_confidence_candidate(evidence_pack, purpose)
            doi_samples[purpose] = _sample_from_candidate(
                candidate, purpose=purpose, domain=domain
            )
            changes.append(f"fixtures.doi_samples.{purpose}")
            continue
        sample_doi = _normalize_doi_or_none(sample.get("doi"))
        raw_doi = sample.get("doi")
        invalid_doi = raw_doi not in (None, "") and sample_doi is None
        if (sample_doi is None or invalid_doi) and (
            candidate := _best_high_confidence_candidate(evidence_pack, purpose)
        ):
            doi_samples[purpose] = _sample_from_candidate(
                candidate, purpose=purpose, domain=domain
            )
            changes.append(f"fixtures.doi_samples.{purpose}.doi")
            continue
        if invalid_doi and purpose not in REQUIRED_DISCOVERY_SAMPLE_PURPOSES:
            sample["doi"] = None
            changes.append(f"fixtures.doi_samples.{purpose}.doi")
        for key, value in {
            "evidence_url": _seed_base_url(domain),
            "evidence_reason": (
                f"Discovery evidence records {purpose} as unavailable or pending confirmation."
            ),
            "observed_signals": [],
            "confidence": "low",
        }.items():
            if key not in sample or sample.get(key) in (None, ""):
                sample[key] = value
                changes.append(f"fixtures.doi_samples.{purpose}.{key}")


REQUIRED_DISCOVERY_SAMPLE_PURPOSES = {"structure", "figure", "references"}


def _autofix_discovery_proof(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    query_plan = (
        evidence_pack.get("query_plan")
        if isinstance(evidence_pack.get("query_plan"), Mapping)
        else {}
    )
    proof = manifest["fixtures"]["discovery_proof"]
    doi_samples = manifest["fixtures"]["doi_samples"]
    source_queries = manifest["generation"].setdefault("source_queries", [])
    if not isinstance(source_queries, list):
        manifest["generation"]["source_queries"] = []
        source_queries = manifest["generation"]["source_queries"]
        changes.append("generation.source_queries")
    for purpose in MANDATORY_DISCOVERY_PROOF_PURPOSES:
        entry = proof.get(purpose)
        if not isinstance(entry, dict):
            entry = {}
            proof[purpose] = entry
            changes.append(f"fixtures.discovery_proof.{purpose}")
        queries = [
            str(query)
            for query in (
                query_plan.get(purpose)
                if isinstance(query_plan.get(purpose), list)
                else []
            )
            if str(query).strip()
        ][:DISCOVERY_MAX_QUERIES_PER_PURPOSE]
        if len(queries) < 3:
            provider = str(
                manifest.get("name") or evidence_pack.get("provider") or "provider"
            )
            fallback_plan = build_discovery_query_plan(
                provider=provider,
                domain=None,
                doi_prefix=None,
            )
            queries = fallback_plan[purpose]
        existing_queries = entry.get("queries")
        if not isinstance(existing_queries, list) or len(existing_queries) < 3:
            entry["queries"] = queries
            changes.append(f"fixtures.discovery_proof.{purpose}.queries")
            active_queries = queries
        else:
            active_queries = [
                str(query) for query in existing_queries if str(query).strip()
            ]
        for query in active_queries:
            if query not in source_queries:
                source_queries.append(query)
                changes.append("generation.source_queries")
        sample = (
            doi_samples.get(purpose)
            if isinstance(doi_samples.get(purpose), dict)
            else {}
        )
        sample_doi = _normalize_doi_or_none(sample.get("doi"))
        candidate_dois = [
            doi
            for doi in (
                _normalize_doi_or_none(candidate.get("doi"))
                for candidate in _candidate_list(evidence_pack, purpose)
            )
            if doi
        ]
        if sample_doi and sample_doi not in candidate_dois:
            candidate_dois.insert(0, sample_doi)
        seen: set[str] = set()
        deduped = [doi for doi in candidate_dois if not (doi in seen or seen.add(doi))]
        existing_candidates = [
            doi
            for doi in (
                _normalize_doi_or_none(candidate)
                for candidate in (entry.get("candidates") or [])
            )
            if doi
        ]
        merged_candidates = list(existing_candidates)
        for doi in deduped:
            if doi not in merged_candidates:
                merged_candidates.append(doi)
        if entry.get("candidates") != merged_candidates:
            entry["candidates"] = merged_candidates
            changes.append(f"fixtures.discovery_proof.{purpose}.candidates")
        selected_value = sample.get("doi") if sample_doi else None
        if "selected_doi" not in entry or entry.get("selected_doi") != selected_value:
            entry["selected_doi"] = selected_value
            changes.append(f"fixtures.discovery_proof.{purpose}.selected_doi")
        exhausted = sample_doi is None
        if entry.get("exhausted") is not exhausted:
            entry["exhausted"] = exhausted
            changes.append(f"fixtures.discovery_proof.{purpose}.exhausted")
        rejections = entry.get("rejections")
        if not isinstance(rejections, dict):
            rejections = {}
            entry["rejections"] = rejections
            changes.append(f"fixtures.discovery_proof.{purpose}.rejections")
        for candidate in _candidate_list(evidence_pack, purpose):
            doi = _normalize_doi_or_none(candidate.get("doi"))
            if not doi or doi == sample_doi:
                continue
            if doi not in rejections:
                rejections[doi] = str(
                    candidate.get("rejection_hint")
                    or _candidate_rejection_hint(purpose)
                )
                changes.append(f"fixtures.discovery_proof.{purpose}.rejections.{doi}")
        summary = (
            f"Selected {sample_doi} from discovery evidence for {purpose}."
            if sample_doi
            else (
                f"Discovery evidence for {purpose} was exhausted without a "
                "high-confidence replacement; candidates are recorded with rejection reasons."
            )
        )
        if not entry.get("evidence_summary"):
            entry["evidence_summary"] = summary
            changes.append(f"fixtures.discovery_proof.{purpose}.evidence_summary")


def _autofix_contracts(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    changes: list[str],
) -> None:
    route_contract = manifest["route_contract"]
    for step in manifest.get("main_path") or []:
        if step not in route_contract or not isinstance(route_contract.get(step), dict):
            route_contract[step] = _route_contract_template(str(step))
            changes.append(f"route_contract.{step}")
        elif not route_contract[step].get("success_requires"):
            route_contract[step].update(_route_contract_template(str(step)))
            changes.append(f"route_contract.{step}.success_requires")
    doi_samples = manifest["fixtures"]["doi_samples"]
    markdown_contract = manifest["markdown_contract"]
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict):
            continue
        doi = _normalize_doi_or_none(sample.get("doi"))
        if doi is None:
            continue
        contract = markdown_contract.get(purpose)
        observed_signals = [
            str(signal) for signal in sample.get("observed_signals") or []
        ]
        if not isinstance(contract, dict):
            markdown_contract[purpose] = _markdown_contract_template(
                purpose=str(purpose),
                doi=doi,
                observed_signals=observed_signals,
            )
            changes.append(f"markdown_contract.{purpose}")
            continue
        if contract.get("doi") != sample.get("doi"):
            contract["doi"] = sample.get("doi")
            changes.append(f"markdown_contract.{purpose}.doi")
        template = _markdown_contract_template(
            purpose=str(purpose),
            doi=doi,
            observed_signals=observed_signals,
        )
        for key in ["must_include", "must_not_include"]:
            if not contract.get(key):
                contract[key] = template[key]
                changes.append(f"markdown_contract.{purpose}.{key}")
    asset_contract = manifest["asset_contract"]
    figures = asset_contract.get("figures")
    figure_sample = (
        doi_samples.get("figure") if isinstance(doi_samples.get("figure"), dict) else {}
    )
    figure_signals = set(
        str(signal) for signal in figure_sample.get("observed_signals") or []
    )
    if not figure_signals:
        for candidate in _candidate_list(evidence_pack, "figure")[:1]:
            figure_signals.update(
                str(signal) for signal in candidate.get("observed_signals") or []
            )
    if {"figures", "body_figures", "body_images"} & figure_signals:
        template = {
            "inline": "body",
            "download": "required",
            "purposes": ["figure"],
            "exception_reason": None,
        }
    else:
        template = {
            "inline": "not_applicable",
            "download": "not_applicable",
            "purposes": ["figure"],
            "exception_reason": (
                "Discovery evidence did not show stable downloadable body figure assets."
            ),
        }
    if not isinstance(figures, dict):
        asset_contract["figures"] = template
        changes.append("asset_contract.figures")
    else:
        for key, value in template.items():
            current = figures.get(key)
            if (
                key not in figures
                or current in ([], "")
                or (current is None and value is not None)
            ):
                figures[key] = value
                changes.append(f"asset_contract.figures.{key}")


def autofix_manifest_data(
    manifest: dict[str, Any],
    evidence_pack: Mapping[str, Any],
    *,
    targeted: bool = False,
) -> dict[str, Any]:
    changes: list[str] = []
    _ensure_manifest_containers(manifest, evidence_pack, changes)
    _autofix_doi_samples(manifest, evidence_pack, changes)
    _autofix_discovery_proof(manifest, evidence_pack, changes)
    _autofix_contracts(manifest, evidence_pack, changes)
    return {
        "changed": bool(changes),
        "changed_paths": sorted(set(changes)),
        "targeted": targeted,
    }


def _read_manifest_for_autofix(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest cannot be loaded for autofix.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="autofix-manifest",
            details={"path": path.as_posix(), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            "MANIFEST_SCHEMA_INVALID",
            "Manifest root must be a mapping for autofix.",
            retryable=False,
            manifest=path.as_posix(),
            task_id="autofix-manifest",
            details={"path": path.as_posix()},
        )
    return data


def autofix_manifest_file(
    *,
    manifest_path: Path,
    evidence_pack_path: Path,
    write: bool,
    targeted: bool = False,
) -> dict[str, Any]:
    manifest = _read_manifest_for_autofix(manifest_path)
    evidence_pack = _load_evidence_pack(evidence_pack_path)
    result = autofix_manifest_data(manifest, evidence_pack, targeted=targeted)
    if write and result["changed"]:
        write_text(
            manifest_path,
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        )
    return {
        **result,
        "manifest": manifest_path.as_posix(),
        "evidence_pack": evidence_pack_path.as_posix(),
        "write": write,
    }


def inspect_manifest_discovery(
    *,
    manifest: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
) -> dict[str, Any]:
    fixtures = (
        manifest.get("fixtures")
        if isinstance(manifest.get("fixtures"), Mapping)
        else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), Mapping)
        else {}
    )
    proof = (
        fixtures.get("discovery_proof")
        if isinstance(fixtures.get("discovery_proof"), Mapping)
        else {}
    )
    purposes: dict[str, Any] = {}
    low_confidence: list[str] = []
    proof_gaps: list[dict[str, Any]] = []
    for purpose in DOI_SAMPLE_PURPOSES:
        candidates = _candidate_list(evidence_pack, purpose)
        top = candidates[0] if candidates else None
        sample = (
            doi_samples.get(purpose)
            if isinstance(doi_samples.get(purpose), Mapping)
            else {}
        )
        sample_confidence = (
            sample.get("confidence") if isinstance(sample, Mapping) else None
        )
        purposes[purpose] = {
            "sample_doi": sample.get("doi") if isinstance(sample, Mapping) else None,
            "sample_confidence": sample_confidence,
            "candidate_count": len(candidates),
            "top_candidates": [
                {
                    "doi": candidate.get("doi"),
                    "score": candidate.get("score"),
                    "confidence": candidate.get("confidence"),
                    "observed_signals": candidate.get("observed_signals"),
                    "evidence_url": candidate.get("evidence_url"),
                }
                for candidate in candidates[:3]
            ],
        }
        if top is None or top.get("confidence") == "low" or sample_confidence == "low":
            low_confidence.append(purpose)
    for purpose in MANDATORY_DISCOVERY_PROOF_PURPOSES:
        entry = proof.get(purpose) if isinstance(proof.get(purpose), Mapping) else None
        sample = (
            doi_samples.get(purpose)
            if isinstance(doi_samples.get(purpose), Mapping)
            else {}
        )
        if entry is None:
            proof_gaps.append({"purpose": purpose, "gap": "missing_discovery_proof"})
            continue
        if len(entry.get("queries") or []) < 3:
            proof_gaps.append({"purpose": purpose, "gap": "fewer_than_three_queries"})
        if entry.get("selected_doi") != sample.get("doi"):
            proof_gaps.append({"purpose": purpose, "gap": "selected_doi_mismatch"})
        candidates = entry.get("candidates") or []
        rejections = (
            entry.get("rejections")
            if isinstance(entry.get("rejections"), Mapping)
            else {}
        )
        for candidate in candidates:
            if candidate != entry.get("selected_doi") and candidate not in rejections:
                proof_gaps.append(
                    {
                        "purpose": purpose,
                        "gap": "missing_rejection",
                        "doi": candidate,
                    }
                )
    return {
        "provider": manifest.get("name") or evidence_pack.get("provider"),
        "purposes": purposes,
        "low_confidence_purposes": low_confidence,
        "proof_gaps": proof_gaps,
    }


def build_discover_brief(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    output_manifest: str,
    evidence_pack: str | None = None,
) -> dict[str, Any]:
    """Build the worker input for the manifest discovery task."""
    provider_name = _provider_slug(provider)
    access_review = default_access_review_path(provider_name)
    evidence_pack_path = evidence_pack or default_evidence_pack_path(provider_name)
    return {
        "task_id": f"{provider_name}-{DISCOVER_STEP}",
        "current_step": DISCOVER_STEP,
        "runtime": "coding-agent-subagent",
        "provider_seed": {
            "name": provider_name,
            "domain": domain,
            "doi_prefix_hint": doi_prefix,
        },
        "output_manifest": output_manifest,
        "evidence_pack": {
            "path": evidence_pack_path,
            "producer": "prepare-discovery",
            "required_before_worker": True,
            "worker_should_use_as_evidence_not_manifest_source": True,
        },
        "contract_templates": _contract_templates_for_discovery(),
        "autofix_policy": {
            "coordinator_runs_before_validate": True,
            "allowed_fixes": [
                "missing structural containers",
                "empty success_criteria and extraction_hints defaults",
                "generation.source_queries coverage for discovery_proof queries",
                "discovery_proof selected_doi synchronization",
                "missing route, markdown, and figure asset contracts",
                "high-confidence DOI sample replacement from evidence pack",
            ],
            "will_not_set_access_approval": True,
            "will_not_mark_markdown_semantic_reviewed": True,
            "low_confidence_candidates": "record proof and rejection reasons only",
        },
        "access_review": access_review,
        "access_policy_constraints": {
            "source": access_review,
            "operator_gate": ACCESS_PREFLIGHT_STEP,
            "worker_must_not_infer_access_policy": True,
            "discovery_may_only_use_review_as_constraints": True,
        },
        "schema": SCHEMA_PATH,
        "hard_constraints": HARD_CONSTRAINTS_PATH,
        "search_requirements": {
            "routing": ROUTING_REQUIREMENTS,
            "doi_sample_purposes": DOI_SAMPLE_PURPOSES,
            "mandatory_discovery_proof": {
                "purposes": MANDATORY_DISCOVERY_PROOF_PURPOSES,
                "minimum_queries_per_purpose": 3,
                "query_must_include": [
                    "provider name, provider domain, or DOI prefix",
                    "purpose keyword",
                ],
                "candidate_pool_required": True,
                "worker_must_search_beyond_seed_doi": True,
                "record_rejections_by_doi": True,
                "selected_doi_must_match_doi_samples": True,
            },
        },
        "output_requirements": {
            "generation_generated_by": "ai_discovery",
            "doi_sample_evidence_keys": [
                "doi",
                "evidence_url",
                "evidence_reason",
                "observed_signals",
                "confidence",
            ],
            "required_non_null_sample_purposes": [
                "structure",
                "figure",
                "references",
            ],
            "optional_null_sample_purposes_require_discovery_proof": (
                MANDATORY_DISCOVERY_PROOF_PURPOSES
            ),
            "null_discovery_proof_requires": [
                "exhausted: true",
                "at least three recorded queries",
                "rejected candidate DOI reasons",
                "evidence_reason more specific than no sample found",
            ],
            "retry_error_code": "UNSUITABLE_DOI_SAMPLE",
        },
        "files_allowed_to_modify": [output_manifest],
        "files_must_not_modify": FILES_MUST_NOT_MODIFY,
        "no_commit": True,
    }


def _implementation_allowed_files(provider: str, manifest: str) -> list[str]:
    provider_name = _provider_slug(provider)
    return [
        manifest,
        f"src/paper_fetch/providers/{provider_name}.py",
        f"src/paper_fetch/providers/_{provider_name}_html.py",
        f"src/paper_fetch/providers/_{provider_name}_*.py",
        f"src/paper_fetch/providers/{provider_name}/**",
        f"tests/unit/test_{provider_name}_provider.py",
        f"tests/unit/test_{provider_name}_*.py",
        f"onboarding/reviews/{provider_name}.yml",
    ]


def _implementation_forbidden_files() -> list[str]:
    return [
        *SHARED_FILES_MUST_NOT_MODIFY,
        "src/paper_fetch/provider_catalog.py",
        *CENTRAL_PROVIDER_LOGIC_PATHS,
    ]


def _compact_cleaning_proposal_for_brief(provider: str) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    proposal_ref = default_cleaning_proposal_path(provider_name)
    evidence_ref = default_cleaning_evidence_path(provider_name)
    path = _repo_root() / proposal_ref
    base = {
        "artifact": proposal_ref,
        "evidence_artifact": evidence_ref,
        "producer_task": PROPOSE_CLEANING_STEP,
    }
    if not path.exists():
        return {
            **base,
            "status": "missing",
            "action": f"run python3 scripts/propose_cleaning_chain.py --provider {provider_name} --write",
        }
    try:
        proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {**base, "status": "invalid_yaml", "error": str(exc)}
    if not isinstance(proposal, dict):
        return {
            **base,
            "status": "invalid_shape",
            "error": "proposal root is not a mapping",
        }
    if proposal.get("schema_version") != 2:
        return {
            **base,
            "status": "legacy_schema",
            "schema_version": proposal.get("schema_version"),
            "action": f"rerun {PROPOSE_CLEANING_STEP} before implementation",
        }
    return {"status": "ready", "producer_task": PROPOSE_CLEANING_STEP, **proposal}


def build_implementation_brief(
    *,
    provider: str,
    manifest: str,
    manifest_yaml: str | None = None,
) -> dict[str, Any]:
    """Build the worker input for provider implementation."""
    provider_name = _provider_slug(provider)
    access_review = default_access_review_path(provider_name)
    brief: dict[str, Any] = {
        "task_id": f"{provider_name}-{IMPLEMENT_STEP}",
        "provider_manifest": manifest,
        "current_step": IMPLEMENT_STEP,
        "runtime": "coding-agent-subagent",
        "access_review": access_review,
        "access_policy_constraints": {
            "source": access_review,
            "must_follow_operator_review": True,
            "do_not_auto_login": True,
            "do_not_solve_captcha": True,
            "do_not_bypass_paywall_or_challenge": True,
            "challenge_or_permission_uncertainty": "stop_and_report",
        },
        "upstream_artifacts": {
            "task_dag": "task-dag.json",
            "capture_commands": f"onboarding/capture-commands/{provider_name}.txt",
            "cleaning_proposal": default_cleaning_proposal_path(provider_name),
            "cleaning_proposal_evidence": default_cleaning_evidence_path(provider_name),
            "scaffold_summary": f"onboarding/scaffold/{provider_name}.json",
        },
        "cleaning_proposal": _compact_cleaning_proposal_for_brief(provider_name),
        "hard_constraints": HARD_CONSTRAINTS_PATH,
        "human_review_policy": {
            "required_gates": [
                HUMAN_PREFLIGHT_REVIEW_GATE,
                FINAL_MARKDOWN_QUALITY_REVIEW_GATE,
            ],
            "fixture_level_operator_review": False,
            "operator_reviews_final_markdown_batch": True,
            "finalize_command": (
                "python3 scripts/onboard_from_manifests.py "
                f"finalize-review-artifact --provider {provider_name} "
                "--confirmed-final-quality"
            ),
        },
        "markdown_review_loop": {
            "required": True,
            "fixture_source": (
                "provider_manifest.fixtures.doi_samples + "
                "provider_manifest.extra_fixtures"
            ),
            "route_contract_source": "provider_manifest.route_contract",
            "markdown_contract_source": "provider_manifest.markdown_contract",
            "operator_review_granularity": "final_batch_only",
            "worker_prepares_review_artifact": True,
            "require_each_non_null_purpose_asserted": True,
            "require_positive_and_negative_markdown_assertions": True,
            "forbid_skipped_scaffold_placeholder": True,
        },
        "coordinator_integration_scope": {
            "route_sources": (
                "provider_manifest.route_sources maps main_path steps to "
                "runtime sources."
            ),
            "extra_fixtures": (
                "provider_manifest.extra_fixtures extends capture and Markdown "
                "review beyond fixed purpose slots."
            ),
            "post_worker_integrations": [
                "golden corpus adapter wiring",
                "runtime source/schema registration",
                "manifest/bundle sync-back",
            ],
        },
        "output_requirements": {
            "review_artifact": f"onboarding/reviews/{provider_name}.yml",
            "reviewed_fixtures": (
                "one entry per non-null provider_manifest.fixtures.doi_samples "
                "purpose and per provider_manifest.extra_fixtures item"
            ),
            "human_signoff": (
                "final batch signoff is written only by finalize-review-artifact "
                "after --confirmed-final-quality"
            ),
            "reviewed_fixture_fields": [
                "fixture",
                "purpose",
                "current_quality_status",
                "assertion",
                "final_signoff_state",
            ],
        },
        "acceptance": {
            "pytest": [
                f"PYTHONPATH=src python3 -m pytest tests/unit/test_{provider_name}_provider.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_markdown_review_contract.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_asset_contract.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_route_contract.py -q",
                "PYTHONPATH=src python3 -m pytest "
                "tests/unit/test_provider_bundle_completeness.py "
                "tests/unit/test_provider_owner_reuse.py -q",
            ],
            "grep_must_be_empty": [
                {
                    "pattern": provider_name,
                    "paths": CENTRAL_PROVIDER_LOGIC_PATHS,
                }
            ],
            "cleaning_contract_gate": [
                f"python3 scripts/onboard_from_manifests.py check-cleaning-proposal --provider {provider_name}",
                f"python3 scripts/propose_cleaning_chain.py --provider {provider_name} --check-contract",
            ],
            "live_review": {
                "required_for_provider_acceptance": _provider_requires_live_review(
                    provider_name
                ),
                "policy": (
                    "Future providers default to one provider subset live assets review; "
                    "legacy non-risk providers are exempt."
                ),
                "command": (
                    "PAPER_FETCH_RUN_LIVE=1 python3 "
                    f"scripts/run_golden_criteria_live_review.py --providers {provider_name}"
                ),
                "source_contract": "provider_manifest.route_sources",
                "markdown_contract": "provider_manifest.markdown_contract",
            },
        },
        "files_allowed_to_modify": _implementation_allowed_files(
            provider_name, manifest
        ),
        "files_must_not_modify": _implementation_forbidden_files(),
        "failure_recovery": {
            "policy": FAILURE_RECOVERY_PATH,
            "max_retries": MAX_WORKER_RETRIES,
            "forbidden_write_code": "WORKER_MODIFIED_FORBIDDEN_FILE",
            "acceptance_failure_retry_task": IMPLEMENT_STEP,
            "blocked_after_retry_exhaustion": True,
        },
        "manifest_adjustment_policy": {
            "allowed_only_for_failure_code": "MARKDOWN_CONTRACT_DRIFT",
            "allowed_path": manifest,
            "allowed_fields": ["markdown_contract.<purpose>"],
            "forbidden_fields": [
                "routing",
                "main_path",
                "route_contract",
                "fixtures",
                "extra_fixtures",
                "probe",
                "access_policy",
            ],
            "must_match_current_provider": provider_name,
        },
        "no_commit": True,
    }
    if manifest_yaml is not None:
        brief["manifest_yaml"] = manifest_yaml
    return brief


def build_dag(
    *,
    provider: str | None,
    manifest: str | None,
    include_discovery: bool,
    dry_run: bool,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider) if provider else None
    steps: list[dict[str, Any]] = []
    previous_step: str | None = None
    for step in TASK_DAG:
        if step.id == DISCOVER_STEP and not include_discovery:
            continue
        item: dict[str, Any] = {
            "id": step.id,
            "type": step.type,
            "owner": step.owner,
            "depends_on": [previous_step] if previous_step else [],
            "retry_limit": MAX_WORKER_RETRIES if step.type == "worker-brief" else 0,
        }
        if step.brief is not None:
            item["brief"] = step.brief
        if step.command:
            item["command"] = list(step.command)
        if step.id == ACCESS_PREFLIGHT_STEP and provider_name is not None:
            item["produces"] = [default_access_review_path(provider_name)]
        if step.id == DISCOVER_STEP and manifest is not None:
            item["produces"] = [manifest]
        if step.id == PROPOSE_CLEANING_STEP and provider_name is not None:
            item["produces"] = [
                default_cleaning_proposal_path(provider_name),
                default_cleaning_evidence_path(provider_name),
            ]
        steps.append(item)
        previous_step = step.id
    return {
        "provider": provider_name,
        "manifest": manifest,
        "dry_run": dry_run,
        "runtime": "coding-agent-subagent",
        "human_gates": [
            {
                "id": HUMAN_PREFLIGHT_REVIEW_GATE,
                "purpose": "operator reviews access policy, route waterfall, runtime constraints, and purpose coverage plan before automated fixture work",
                "command": (
                    "python3 scripts/onboard_from_manifests.py "
                    f"prepare-human-preflight --provider {provider_name}"
                    if provider_name is not None
                    else None
                ),
                "blocks": DISCOVER_STEP,
                "operator_must_edit": default_access_review_path(provider_name)
                if provider_name is not None
                else None,
            },
            {
                "id": FINAL_MARKDOWN_QUALITY_REVIEW_GATE,
                "purpose": "operator reviews final extracted.md quality summary once automated quality checks pass",
                "command": (
                    "python3 scripts/onboard_from_manifests.py "
                    f"finalize-review-artifact --provider {provider_name} "
                    "--confirmed-final-quality"
                    if provider_name is not None
                    else None
                ),
                "blocks": "merge-ready",
                "operator_must_review": [
                    "tests/fixtures/**/extracted.md",
                    "tests/fixtures/**/markdown-quality.json",
                    f"onboarding/reviews/{provider_name}.yml"
                    if provider_name is not None
                    else "onboarding/reviews/<provider>.yml",
                ],
            },
        ],
        "agent_cli_env": AGENT_CLI_ENV,
        "worker_dispatch": {
            "default": DEFAULT_CODEX_AGENT_CLI,
            "override_env": AGENT_CLI_ENV,
            "prompt_transport": "stdin",
        },
        "state_schema": STATE_SCHEMA_PATH,
        "serial": {
            "single_provider": True,
            "single_task": True,
            "no_matrix": True,
        },
        "steps": steps,
    }


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if "\n" in text or "\r" in text:
        return json.dumps(text)
    if text in {"-", "?", ":"} or text.startswith(("- ", "? ", ": ")):
        return json.dumps(text)
    if any(
        char in text
        for char in [
            ":",
            "#",
            "{",
            "}",
            "[",
            "]",
            ",",
            "&",
            "*",
            "!",
            "|",
            ">",
            "'",
            '"',
        ]
    ):
        return json.dumps(text)
    if text.lower() in {"null", "true", "false", "yes", "no"}:
        return json.dumps(text)
    return text


def to_yaml(data: Any, *, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(to_yaml(value, indent=indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    elif isinstance(data, list):
        if not data:
            lines.append(f"{prefix}[]")
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(to_yaml(item, indent=indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(data)}")
    return "\n".join(lines)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def _state_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return _repo_root() / path


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "agent_cli": _worker_dispatcher_label(),
        "active_provider": None,
        "providers": {},
    }


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"state root must be an object: {path}")
    data.setdefault("schema_version", 1)
    data["agent_cli"] = _worker_dispatcher_label() or data.get("agent_cli")
    data.setdefault("active_provider", None)
    providers = data.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise ValueError(f"state providers must be an object: {path}")
    return data


def _dag_step_ids(include_discovery: bool) -> tuple[str, ...]:
    return tuple(
        step.id for step in TASK_DAG if include_discovery or step.id != DISCOVER_STEP
    )


def _task_statuses(step_ids: tuple[str, ...]) -> dict[str, str]:
    return {
        step_id: "in_progress" if index == 0 else "pending"
        for index, step_id in enumerate(step_ids)
    }


def _ensure_single_active_provider(state: dict[str, Any], provider: str) -> None:
    active_provider = state.get("active_provider")
    if active_provider not in {None, provider}:
        providers = state.get("providers", {})
        active_state = providers.get(active_provider, {})
        if active_state.get("status") == "in_progress":
            raise ToolError(
                "TASK_BRIEF_INVALID",
                "another provider is already in_progress: "
                f"{active_provider}; finish or block it before starting {provider}",
                retryable=False,
                provider=provider,
                task_id=f"{provider}-coordinator-state-conflict",
                details={"active_provider": active_provider},
            )


def _ensure_provider_state(
    state: dict[str, Any],
    *,
    provider: str,
    manifest: str | None = None,
    include_discovery: bool = True,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    _ensure_single_active_provider(state, provider_name)
    providers = state["providers"]
    current = providers.get(provider_name)
    if isinstance(current, dict):
        return current
    step_ids = _dag_step_ids(include_discovery)
    provider_state = {
        "provider": provider_name,
        "manifest": manifest or default_manifest_path(provider_name),
        "status": "in_progress",
        "current_step": step_ids[0],
        "steps": list(step_ids),
        "completed_steps": [],
        "task_statuses": _task_statuses(step_ids),
        "retry_counts": {step_id: 0 for step_id in step_ids},
        "verifications": {},
    }
    providers[provider_name] = provider_state
    state["active_provider"] = provider_name
    return provider_state


def _next_pending_step(provider_state: dict[str, Any]) -> str | None:
    task_statuses = provider_state["task_statuses"]
    for step_id in provider_state["steps"]:
        if task_statuses.get(step_id) == "in_progress":
            return str(step_id)
    for step_id in provider_state["steps"]:
        if task_statuses.get(step_id) == "pending":
            task_statuses[step_id] = "in_progress"
            provider_state["current_step"] = step_id
            return str(step_id)
    provider_state["current_step"] = None
    return None


def _failed_steps(provider_state: dict[str, Any]) -> list[str]:
    task_statuses = provider_state.get("task_statuses")
    steps = provider_state.get("steps")
    if not isinstance(task_statuses, dict) or not isinstance(steps, list):
        return []
    return [
        str(step_id)
        for step_id in steps
        if task_statuses.get(step_id) in {"failed", "blocked"}
    ]


def _provider_requires_live_review(provider: str) -> bool:
    provider_name = _provider_slug(provider)
    manifest_path = _repo_root() / default_manifest_path(provider)
    if not manifest_path.exists():
        return provider_name not in LEGACY_LIVE_REVIEW_EXEMPT_PROVIDERS
    try:
        manifest = _read_manifest(manifest_path)
    except ToolError:
        return provider_name not in LEGACY_LIVE_REVIEW_EXEMPT_PROVIDERS
    probe = manifest.get("probe") if isinstance(manifest.get("probe"), dict) else {}
    if bool(probe.get("requires_browser_runtime")) or bool(
        probe.get("requires_playwright")
    ):
        return True
    return provider_name not in LEGACY_LIVE_REVIEW_EXEMPT_PROVIDERS


def _manifest_path_for_provider(provider: str) -> Path:
    return _repo_root() / default_manifest_path(provider)


def _normalized_doi(value: str) -> str:
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


def _doi_slug(value: str) -> str:
    return _normalized_doi(value).replace("/", "_")


def _manifest_dois(manifest: dict[str, Any]) -> list[str]:
    dois: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        doi = _normalized_doi(value)
        if doi and doi not in seen:
            seen.add(doi)
            dois.append(doi)

    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for sample in doi_samples.values():
        if isinstance(sample, dict):
            add(sample.get("doi"))

    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for sample in extra_fixtures:
            if isinstance(sample, dict):
                add(sample.get("doi"))
    return dois


def _snapshot_expected_commands(
    provider: str, manifest_path: str | None = None
) -> list[list[str]]:
    if manifest_path is None:
        path = _manifest_path_for_provider(provider)
    else:
        path = Path(manifest_path)
        if not path.is_absolute():
            path = _repo_root() / path
    manifest = _read_manifest(path)
    commands: list[list[str]] = []
    for doi in _manifest_dois(manifest):
        commands.append(
            [
                "PYTHONPATH=src",
                "python3",
                "scripts/snapshot_expected.py",
                "--doi",
                doi,
                "--review",
            ]
        )
        commands.append(
            [
                "PYTHONPATH=src",
                "python3",
                "scripts/snapshot_expected.py",
                "--doi",
                doi,
            ]
        )
        commands.append(
            [
                "PYTHONPATH=src",
                "python3",
                "scripts/onboard_from_manifests.py",
                "check-snapshot",
                "--provider",
                provider,
                "--doi",
                doi,
            ]
        )
    return commands


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _manifest_review_samples(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    contracts = (
        manifest.get("markdown_contract")
        if isinstance(manifest.get("markdown_contract"), dict)
        else {}
    )
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict) or not sample.get("doi"):
            continue
        contract = contracts.get(purpose)
        samples.append(
            {
                "purpose": str(purpose),
                "doi": _normalized_doi(str(sample["doi"])),
                "contract": contract if isinstance(contract, dict) else {},
                "fixture_family": "golden",
            }
        )
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict) or not sample.get("doi"):
                continue
            contract = sample.get("markdown_contract")
            samples.append(
                {
                    "purpose": str(sample.get("purpose") or f"extra_fixtures[{index}]"),
                    "doi": _normalized_doi(str(sample["doi"])),
                    "contract": contract if isinstance(contract, dict) else {},
                    "fixture_family": "golden",
                }
            )
    return samples


def _assertions_from_markdown_contract(contract: dict[str, Any]) -> list[str]:
    assertions: list[str] = []
    for value in contract.get("must_include") or ():
        assertions.append(f"must include {value}")
    for value in contract.get("must_not_include") or ():
        assertions.append(f"must not include {value}")
    for value in contract.get("must_match") or ():
        assertions.append(f"must match {value}")
    count_equals = contract.get("count_equals")
    if isinstance(count_equals, dict):
        for key, value in sorted(count_equals.items()):
            assertions.append(f"count {key} equals {value}")
    return assertions or ["baseline Markdown passed final batch review"]


def _contract_issues_for_markdown(
    contract: dict[str, Any], markdown_text: str
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, value in enumerate(contract.get("must_include") or (), start=1):
        if str(value) not in markdown_text:
            issues.append(
                {
                    "id": f"missing-include-{index}",
                    "severity": "high",
                    "summary": f"extracted Markdown is missing required text: {value}",
                }
            )
    for index, value in enumerate(contract.get("must_not_include") or (), start=1):
        if str(value) in markdown_text:
            issues.append(
                {
                    "id": f"forbidden-text-{index}",
                    "severity": "high",
                    "summary": f"extracted Markdown contains forbidden text: {value}",
                }
            )
    for index, pattern in enumerate(contract.get("must_match") or (), start=1):
        try:
            matched = re.search(str(pattern), markdown_text) is not None
        except re.error:
            matched = False
        if not matched:
            issues.append(
                {
                    "id": f"missing-pattern-{index}",
                    "severity": "high",
                    "summary": f"extracted Markdown does not match required pattern: {pattern}",
                }
            )
    count_equals = contract.get("count_equals")
    if isinstance(count_equals, dict):
        for index, (text, expected) in enumerate(sorted(count_equals.items()), start=1):
            try:
                expected_count = int(expected)
            except (TypeError, ValueError):
                expected_count = -1
            actual_count = markdown_text.count(str(text))
            if actual_count != expected_count:
                issues.append(
                    {
                        "id": f"count-mismatch-{index}",
                        "severity": "high",
                        "summary": (
                            f"extracted Markdown count for {text} is {actual_count}, "
                            f"expected {expected_count}"
                        ),
                    }
                )
    return issues


def _review_fixture_assets(
    *,
    provider: str,
    doi: str,
    task_id: str,
) -> dict[str, Any]:
    golden_manifest = _load_golden_manifest()
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is missing from golden criteria manifest.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=task_id,
            details={"doi": doi, "sample_id": _doi_slug(doi)},
        )
    sample_id, sample = sample_entry
    fixture_root = _fixture_root_for_sample(sample_id, sample)
    paths = {
        "expected": fixture_root / "expected.json",
        "markdown": fixture_root / "extracted.md",
        "prompt": fixture_root / "markdown-quality-prompt.md",
        "quality": fixture_root / "markdown-quality.json",
    }
    for key, path in paths.items():
        if not path.is_file():
            code = (
                "MARKDOWN_QUALITY_FAILED"
                if key in {"prompt", "quality"}
                else "EXPECTED_SNAPSHOT_FAILED"
            )
            raise ToolError(
                code,
                f"final review requires fixture artifact {path.name}.",
                retryable=True,
                provider=provider,
                manifest=default_manifest_path(provider),
                task_id=task_id,
                details={"doi": doi, "path": _rel(path)},
            )
    return {
        "sample_id": sample_id,
        "sample": sample,
        "fixture_root": fixture_root,
        **paths,
    }


def _quality_report_for_final_review(
    *,
    provider: str,
    doi: str,
    quality_path: Path,
    markdown_path: Path,
    prompt_path: Path,
    task_id: str,
) -> dict[str, Any]:
    quality = _read_json_object(
        quality_path,
        code="MARKDOWN_QUALITY_FAILED",
        task_id=task_id,
        provider=provider,
    )
    validation_errors = _markdown_quality_report_errors(
        quality,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
    )
    if validation_errors:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report must use the agent_prompt schema v2 contract.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=task_id,
            details={
                "doi": doi,
                "markdown_quality_path": _rel(quality_path),
                "validation_errors": validation_errors,
            },
        )
    blocking = blocking_markdown_quality_issues(quality)
    if quality.get("status") != "pass" or blocking:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Final review cannot be signed while markdown-quality.json is not pass.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=task_id,
            details={
                "doi": doi,
                "markdown_quality_path": _rel(quality_path),
                "status": quality.get("status"),
                "issues": blocking,
            },
        )
    return quality


def build_human_preflight_digest(
    *,
    provider: str,
    domain: str | None = None,
    doi_prefix: str | None = None,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    manifest_path = _manifest_path_for_provider(provider_name)
    manifest: dict[str, Any] = {}
    manifest_status = "missing"
    if manifest_path.exists():
        manifest = _read_manifest(manifest_path)
        manifest_status = "present"
    access = _access_review_summary(provider_name)
    fixtures = _manifest_fixture_summary(manifest) if manifest else []
    purpose_status = {
        str(item.get("purpose")): {
            "doi": item.get("doi"),
            "proof_status": item.get("proof_status"),
            "confidence": item.get("confidence"),
            "null_reason": item.get("null_reason"),
            "discovery_proof": item.get("discovery_proof"),
        }
        for item in fixtures
        if isinstance(item, dict)
    }
    missing_purposes = [
        purpose for purpose in DOI_SAMPLE_PURPOSES if purpose not in purpose_status
    ]
    route_contract = (
        manifest.get("route_contract")
        if isinstance(manifest.get("route_contract"), dict)
        else {}
    )
    route_sources = (
        manifest.get("route_sources")
        if isinstance(manifest.get("route_sources"), dict)
        else {}
    )
    main_path = (
        manifest.get("main_path") if isinstance(manifest.get("main_path"), list) else []
    )
    waterfall = [
        {
            "step": step,
            "source": route_sources.get(step) or manifest.get("display_source"),
            "success_requires": (
                route_contract.get(step, {}).get("success_requires")
                if isinstance(route_contract.get(step), dict)
                else []
            ),
            "reject_if_any": (
                route_contract.get(step, {}).get("reject_if_any")
                if isinstance(route_contract.get(step), dict)
                else []
            ),
        }
        for step in main_path
    ]
    return {
        "provider": provider_name,
        "gate": HUMAN_PREFLIGHT_REVIEW_GATE,
        "manifest": {
            "path": default_manifest_path(provider_name),
            "status": manifest_status,
            "display_source": manifest.get("display_source"),
            "routing": manifest.get("routing"),
            "main_path": main_path,
            "route_sources": route_sources,
        },
        "seed": {
            "domain": domain,
            "doi_prefix": doi_prefix,
        },
        "access_review": access,
        "waterfall": waterfall,
        "purpose_coverage": {
            "purposes": purpose_status,
            "missing_purposes": missing_purposes,
            "mandatory_discovery_proof_purposes": MANDATORY_DISCOVERY_PROOF_PURPOSES,
        },
        "asset_contract": manifest.get("asset_contract"),
        "operator_checklist": [
            "access review reflects legal access and allowed runtime",
            "waterfall order and route success/rejection rules are plausible",
            "table/formula/supplementary are either selected or have exhausted discovery proof",
            "strong local fixture signals are promoted or rejected with concrete reasons",
            "figure asset contract is body/download unless a concrete exception applies",
        ],
        "next_prompt": f"确认预检后对 agent 说：继续 {provider_name} provider",
    }


def finalize_review_artifact(
    *,
    provider: str,
    reviewed_by: str,
    confirmed_final_quality: bool,
    run_fresh_review: bool = True,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    task_id = f"{provider_name}-{FINAL_MARKDOWN_QUALITY_REVIEW_GATE}"
    if not confirmed_final_quality:
        raise ToolError(
            "FINAL_MARKDOWN_REVIEW_NOT_CONFIRMED",
            "Final Markdown review requires explicit --confirmed-final-quality.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"required_flag": "--confirmed-final-quality"},
        )
    manifest_path = _manifest_path_for_provider(provider_name)
    manifest = _read_manifest(manifest_path)
    samples = _manifest_review_samples(manifest)
    if not samples:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "Manifest does not contain non-null DOI fixtures for final review.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"manifest": default_manifest_path(provider_name)},
        )
    review_path = _repo_root() / "onboarding" / "reviews" / f"{provider_name}.yml"
    if review_path.exists():
        review = yaml.safe_load(review_path.read_text(encoding="utf-8"))
        if not isinstance(review, dict):
            raise ToolError(
                "REVIEW_ARTIFACT_INVALID",
                "Review artifact root must be a mapping.",
                retryable=True,
                provider=provider_name,
                manifest=default_manifest_path(provider_name),
                task_id=task_id,
                details={"path": _rel(review_path)},
            )
    else:
        review = {
            "schema_version": 2,
            "provider": provider_name,
            "fixtures": [],
        }
    existing_items = (
        review.get("fixtures") if isinstance(review.get("fixtures"), list) else []
    )
    existing = {
        (str(item.get("purpose")), _normalized_doi(str(item.get("doi") or ""))): item
        for item in existing_items
        if isinstance(item, dict)
    }
    finalized: list[dict[str, Any]] = []
    fresh_reports: list[str] = []
    for sample in samples:
        purpose = str(sample["purpose"])
        doi = str(sample["doi"])
        assets = _review_fixture_assets(
            provider=provider_name, doi=doi, task_id=task_id
        )
        quality = _quality_report_for_final_review(
            provider=provider_name,
            doi=doi,
            quality_path=assets["quality"],
            markdown_path=assets["markdown"],
            prompt_path=assets["prompt"],
            task_id=task_id,
        )
        if run_fresh_review:
            fresh = _run_fresh_markdown_quality_review(
                provider=provider_name,
                doi=doi,
                sample_id=str(assets["sample_id"]),
                purpose=purpose,
                markdown_path=assets["markdown"],
                prompt_path=assets["prompt"],
                task_id=task_id,
            )
            fresh_blocking = _fresh_markdown_quality_blocking_issues(fresh.report)
            if fresh.report.get("status") != "pass" or fresh_blocking:
                raise ToolError(
                    "MARKDOWN_QUALITY_FAILED",
                    "Fresh Markdown quality review found blocking issues before final signoff.",
                    retryable=True,
                    provider=provider_name,
                    manifest=default_manifest_path(provider_name),
                    task_id=task_id,
                    details={
                        "doi": doi,
                        "fresh_markdown_quality_path": _rel(fresh.report_path),
                        "fresh_markdown_quality_status": fresh.report.get("status"),
                        "issues": fresh_blocking,
                    },
                )
            fresh_reports.append(_rel(fresh.report_path))
        markdown_text = assets["markdown"].read_text(encoding="utf-8", errors="replace")
        contract_issues = _contract_issues_for_markdown(
            sample["contract"], markdown_text
        )
        if contract_issues:
            raise ToolError(
                "MARKDOWN_CONTRACT_DRIFT",
                "Final review cannot be signed while markdown_contract does not match extracted.md.",
                retryable=True,
                provider=provider_name,
                manifest=default_manifest_path(provider_name),
                task_id=task_id,
                details={
                    "doi": doi,
                    "purpose": purpose,
                    "baseline_markdown_path": _rel(assets["markdown"]),
                    "issues": contract_issues,
                },
            )
        current = existing.get((purpose, doi), {})
        finalized.append(
            {
                "fixture": _rel(assets["fixture_root"]),
                "purpose": purpose,
                "doi": doi,
                "baseline_markdown_path": _rel(assets["markdown"]),
                "baseline_markdown_sha256": _sha256_file(assets["markdown"]),
                "markdown_quality_path": _rel(assets["quality"]),
                "markdown_quality_sha256": _sha256_file(assets["quality"]),
                "review_notes": (
                    f"Final batch Markdown quality review confirmed by {reviewed_by}; "
                    f"persistent quality status={quality.get('status')}."
                ),
                "sample_representative": True,
                "markdown_semantic_reviewed": True,
                "issues": [],
                "assertions": current.get("assertions")
                if isinstance(current.get("assertions"), list)
                and current.get("assertions")
                else _assertions_from_markdown_contract(sample["contract"]),
                "fixes": [],
            }
        )
    now = _utc_now_iso()
    review["schema_version"] = 2
    review["provider"] = provider_name
    review["reviewed_at"] = now
    review["reviewed_by"] = reviewed_by
    review["final_markdown_quality_review"] = {
        "confirmed": True,
        "confirmed_by": reviewed_by,
        "confirmed_at": now,
        "method": FINAL_MARKDOWN_QUALITY_REVIEW_GATE,
        "fixture_count": len(finalized),
        "fresh_markdown_quality_reports": fresh_reports,
    }
    review["fixtures"] = finalized
    write_text(review_path, yaml.safe_dump(review, allow_unicode=True, sort_keys=False))
    return {
        "provider": provider_name,
        "review_path": _rel(review_path),
        "fixture_count": len(finalized),
        "fresh_markdown_quality_reports": fresh_reports,
        "result": "finalized",
    }


def _verify_commands(
    provider: str, task: str, *, include_live: bool = True
) -> list[list[str]]:
    provider_name = _provider_slug(provider)
    command_map: dict[str, list[list[str]]] = {
        ACCESS_PREFLIGHT_STEP: [
            [
                "test",
                "-f",
                default_access_review_path(provider_name),
            ],
        ],
        "validate-manifest": [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_manifest_schema.py",
                "tests/unit/test_known_providers_sync.py",
                "-q",
            ]
        ],
        "capture-fixtures": [
            [
                "python3",
                "scripts/capture_fixture.py",
                "--from-manifest",
                default_manifest_path(provider_name),
                "--all",
                "--auto-via",
                "--fail-fast",
                "--dry-run",
            ]
        ],
        PROPOSE_CLEANING_STEP: [
            [
                "python3",
                "scripts/propose_cleaning_chain.py",
                "--provider",
                provider_name,
                "--write",
            ]
        ],
        "scaffold": [
            [
                "python3",
                "scripts/scaffold_provider.py",
                "--from-manifest",
                default_manifest_path(provider_name),
                "--merge-existing=safe",
            ]
        ],
        IMPLEMENT_STEP: [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                f"tests/unit/test_{provider_name}_provider.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_markdown_review_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_asset_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_route_contract.py",
                "-q",
            ],
            [
                "git",
                "grep",
                "-n",
                provider_name,
                "--",
                *CENTRAL_PROVIDER_LOGIC_PATHS,
            ],
        ],
        SHARED_INTEGRATION_STEP: [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_manifest_bundle_sync.py",
                "tests/unit/test_golden_corpus_adapters.py",
                "tests/unit/test_provider_benchmark_samples.py",
                "tests/devtools/test_golden_criteria_live.py",
                "-q",
            ]
        ],
        "manifest-sync-back": [
            [
                "python3",
                "scripts/manifest_sync_back.py",
                "--provider",
                provider_name,
                "--manifest",
                default_manifest_path(provider_name),
                "--sync-docs",
            ]
        ],
        "provider-local-acceptance": [
            [
                "python3",
                "scripts/onboard_from_manifests.py",
                "check-cleaning-proposal",
                "--provider",
                provider_name,
            ],
            [
                "python3",
                "scripts/propose_cleaning_chain.py",
                "--provider",
                provider_name,
                "--check-contract",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                f"tests/unit/test_{provider_name}_provider.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_markdown_review_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_asset_contract.py",
                "-q",
            ],
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_route_contract.py",
                "-q",
            ],
            [
                "git",
                "grep",
                "-n",
                provider_name,
                "--",
                *CENTRAL_PROVIDER_LOGIC_PATHS,
            ],
        ],
        "global-lint": [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_manifest_bundle_sync.py",
                "tests/unit/test_provider_owner_reuse.py",
                "tests/unit/test_provider_bundle_completeness.py",
                "tests/unit/test_import_boundaries.py",
                "tests/unit/test_extraction_rules_validator.py",
                "-q",
            ]
        ],
        "merge-ready": [
            [
                "git",
                "diff",
                "--",
                default_manifest_path(provider_name),
                "onboarding/known-providers.yml",
                "docs/providers.md",
                "CHANGELOG.md",
            ]
        ],
    }
    if task == SNAPSHOT_EXPECTED_STEP:
        return _snapshot_expected_commands(provider_name)
    if (
        include_live
        and task == "provider-local-acceptance"
        and _provider_requires_live_review(provider_name)
    ):
        command_map["provider-local-acceptance"].append(
            [
                "PAPER_FETCH_RUN_LIVE=1",
                "python3",
                "scripts/run_golden_criteria_live_review.py",
                "--providers",
                provider_name,
            ]
        )
    return command_map.get(task, [])


def _load_golden_manifest() -> dict[str, Any]:
    path = _repo_root() / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "golden criteria manifest cannot be loaded.",
            retryable=True,
            task_id=SNAPSHOT_EXPECTED_STEP,
            details={
                "path": path.relative_to(_repo_root()).as_posix(),
                "reason": str(exc),
            },
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("samples"), dict):
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "golden criteria manifest must contain samples.",
            retryable=True,
            task_id=SNAPSHOT_EXPECTED_STEP,
            details={"path": path.relative_to(_repo_root()).as_posix()},
        )
    return data


def _golden_sample_for_doi(
    doi: str, manifest: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    slug = _doi_slug(doi)
    samples = manifest.get("samples", {})
    sample = samples.get(slug)
    if isinstance(sample, dict):
        return slug, sample
    normalized = _normalized_doi(doi)
    for sample_id, item in samples.items():
        if (
            isinstance(item, dict)
            and _normalized_doi(str(item.get("doi") or "")) == normalized
        ):
            return str(sample_id), item
    return None


def _fixture_root_for_sample(sample_id: str, sample: dict[str, Any]) -> Path:
    family = str(sample.get("fixture_family") or "golden")
    if family == "block":
        assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
        for value in assets.values():
            path = _repo_root() / str(value)
            if "tests/fixtures/block/" in path.as_posix():
                return path.parent
        return (
            _repo_root()
            / "tests"
            / "fixtures"
            / "block"
            / sample_id.removesuffix("__block")
        )
    return _repo_root() / "tests" / "fixtures" / "golden_criteria" / sample_id


def _rel(path: Path) -> str:
    try:
        return path.relative_to(_repo_root()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json_object(
    path: Path, *, code: str, task_id: str, provider: str | None = None
) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            code,
            f"JSON file cannot be loaded: {_rel(path)}",
            retryable=True,
            provider=provider,
            task_id=task_id,
            details={"path": _rel(path), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ToolError(
            code,
            f"JSON file root must be an object: {_rel(path)}",
            retryable=True,
            provider=provider,
            task_id=task_id,
            details={"path": _rel(path)},
        )
    return data


def _markdown_quality_report_errors(
    report: Any,
    *,
    markdown_path: Path,
    prompt_path: Path,
) -> list[str]:
    errors = validate_markdown_quality_report(report)
    if isinstance(report, dict):
        if report.get("markdown_path") != _rel(markdown_path):
            errors.append("markdown_path must point to extracted.md")
        if report.get("prompt_path") != _rel(prompt_path):
            errors.append("prompt_path must point to markdown-quality-prompt.md")
    else:
        errors.append("markdown quality report root must be an object")
    return errors


class FreshMarkdownQualityReview(NamedTuple):
    report: dict[str, Any]
    report_path: Path
    attempt_dir: Path


def _fresh_markdown_quality_attempt_dir(
    *,
    provider: str,
    doi: str,
    output_dir: Path | None,
) -> Path:
    base_dir = output_dir or (
        _repo_root() / f".paper-fetch-runs/{provider}-markdown-quality-audit"
    )
    if not base_dir.is_absolute():
        base_dir = _repo_root() / base_dir
    review_root = base_dir / _doi_slug(doi)
    existing: list[int] = []
    if review_root.is_dir():
        for child in review_root.iterdir():
            match = re.fullmatch(r"attempt-(\d+)", child.name)
            if match and child.is_dir():
                existing.append(int(match.group(1)))
    return review_root / f"attempt-{max(existing, default=0) + 1}"


def _parse_json_object_from_stdout(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _run_fresh_markdown_quality_review(
    *,
    provider: str,
    doi: str,
    sample_id: str,
    markdown_path: Path,
    prompt_path: Path,
    purpose: str | None = None,
    output_dir: Path | None = None,
    task_id: str | None = None,
) -> FreshMarkdownQualityReview:
    provider_name = _provider_slug(provider)
    normalized_doi = _normalized_doi(doi)
    argv = _agent_argv(
        provider=provider_name,
        task="fresh-markdown-quality-review",
        manifest=default_manifest_path(provider_name),
    )
    attempt_dir = _fresh_markdown_quality_attempt_dir(
        provider=provider_name,
        doi=normalized_doi,
        output_dir=output_dir,
    )
    attempt_dir.mkdir(parents=True, exist_ok=True)
    report_path = attempt_dir / "fresh-markdown-quality.json"
    prompt = build_fresh_markdown_quality_prompt(
        provider=provider_name,
        doi=normalized_doi,
        sample_id=sample_id,
        purpose=purpose,
        markdown_path=_rel(markdown_path),
        prompt_path=_rel(prompt_path),
        report_path=_rel(report_path),
        markdown_sha256=_sha256_file(markdown_path),
    )
    completed, before, after = _run_agent_with_scope(
        argv=argv,
        prompt=prompt,
        attempt_dir=attempt_dir,
        prefix="fresh-quality-agent",
        allowed_scope=[_rel(report_path)],
    )
    disallowed = _disallowed_changes(before, after, [_rel(report_path)])
    if disallowed:
        raise ToolError(
            "WORKER_MODIFIED_FORBIDDEN_FILE",
            "fresh markdown quality worker modified files outside its report path.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "forbidden_paths": disallowed,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    if completed.returncode != 0:
        raise ToolError(
            "WORKER_AGENT_FAILED",
            "fresh markdown quality worker failed.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    if not report_path.is_file():
        stdout_report = _parse_json_object_from_stdout(completed.stdout)
        if stdout_report is not None:
            write_text(
                report_path, json.dumps(stdout_report, indent=2, sort_keys=True) + "\n"
            )
    if not report_path.is_file():
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "fresh markdown quality worker did not write its report.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "fresh markdown quality report cannot be loaded.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "reason": str(exc),
            },
        ) from exc
    validation_errors = _markdown_quality_report_errors(
        report,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
    )
    if validation_errors:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "fresh markdown quality report must use the agent_prompt schema v2 contract.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id or f"{provider_name}-fresh-markdown-quality-review",
            details={
                "doi": normalized_doi,
                "fresh_markdown_quality_path": _rel(report_path),
                "validation_errors": validation_errors,
            },
        )
    return FreshMarkdownQualityReview(
        report=report,
        report_path=report_path,
        attempt_dir=attempt_dir,
    )


def _fresh_markdown_quality_blocking_issues(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    blocking = blocking_markdown_quality_issues(report)
    if blocking:
        return blocking
    if report.get("status") == "fail":
        issues = report.get("issues")
        return (
            [issue for issue in issues if isinstance(issue, dict)]
            if isinstance(issues, list)
            else []
        )
    return []


def _synthetic_persistent_quality_issue(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "markdown-quality-report-not-pass",
        "severity": "high",
        "blocking": True,
        "summary": "Persistent markdown-quality.json is not pass for the current fixture.",
        "evidence": f"status={report.get('status')!r}",
    }


def _effective_markdown_repair_report(
    *,
    persistent_report: dict[str, Any],
    fresh_report: dict[str, Any],
) -> dict[str, Any]:
    fresh_issues = _fresh_markdown_quality_blocking_issues(fresh_report)
    if fresh_report.get("status") != "pass" or fresh_issues:
        return fresh_report
    persistent_issues = _markdown_repair_issues(persistent_report)
    if persistent_report.get("status") != "pass" or persistent_issues:
        if persistent_issues:
            return persistent_report
        report = dict(persistent_report)
        report["status"] = "fail"
        report["issues"] = [_synthetic_persistent_quality_issue(persistent_report)]
        report["blocking_issue_count"] = 1
        return report
    return persistent_report


def _manifest_fixture_for_doi(
    manifest: dict[str, Any],
    doi: str,
) -> tuple[str | None, dict[str, Any]]:
    normalized = _normalized_doi(doi)
    manifest_contract = manifest.get("markdown_contract")
    manifest_contract = manifest_contract if isinstance(manifest_contract, dict) else {}
    fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        fixtures.get("doi_samples")
        if isinstance(fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict):
            continue
        if _normalized_doi(str(sample.get("doi") or "")) != normalized:
            continue
        contract = manifest_contract.get(purpose)
        return str(purpose), contract if isinstance(contract, dict) else {}
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict):
                continue
            if _normalized_doi(str(sample.get("doi") or "")) != normalized:
                continue
            contract = sample.get("markdown_contract")
            purpose = sample.get("purpose") or f"extra_fixtures[{index}]"
            return str(purpose), contract if isinstance(contract, dict) else {}
    return None, {}


def _load_markdown_repair_context(
    provider: str,
    doi: str,
    *,
    quality_report_override: dict[str, Any] | None = None,
    fresh_quality_path: Path | None = None,
    allow_passing_report: bool = False,
    allow_pending_report: bool = False,
) -> MarkdownQualityRepairContext:
    provider_name = _provider_slug(provider)
    normalized_doi = _normalized_doi(doi)
    task_id = f"{provider_name}-{REPAIR_MARKDOWN_QUALITY_STEP}"
    manifest_path = _manifest_path_for_provider(provider_name)
    manifest = _read_manifest(manifest_path)
    if normalized_doi not in _manifest_dois(manifest):
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is not registered in provider manifest fixtures.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"doi": normalized_doi},
        )

    golden_manifest = _load_golden_manifest()
    sample_entry = _golden_sample_for_doi(normalized_doi, golden_manifest)
    if sample_entry is None:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is missing from golden criteria manifest.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={"doi": normalized_doi, "sample_id": _doi_slug(normalized_doi)},
        )
    sample_id, sample = sample_entry
    fixture_root = _fixture_root_for_sample(sample_id, sample)
    expected_path = fixture_root / "expected.json"
    markdown_path = fixture_root / "extracted.md"
    prompt_path = fixture_root / "markdown-quality-prompt.md"
    quality_path = fixture_root / "markdown-quality.json"
    for path, error_code, message in (
        (
            expected_path,
            "EXPECTED_SNAPSHOT_FAILED",
            "expected snapshot file is missing.",
        ),
        (
            markdown_path,
            "EXPECTED_SNAPSHOT_FAILED",
            "extracted Markdown baseline is missing.",
        ),
        (
            prompt_path,
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality agent prompt is missing.",
        ),
        (
            quality_path,
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report is missing.",
        ),
    ):
        if not path.is_file():
            raise ToolError(
                error_code,
                message,
                retryable=True,
                provider=provider_name,
                manifest=default_manifest_path(provider_name),
                task_id=task_id,
                details={"doi": normalized_doi, "path": _rel(path)},
            )

    quality = _read_json_object(
        quality_path,
        code="MARKDOWN_QUALITY_FAILED",
        task_id=task_id,
        provider=provider_name,
    )
    validation_errors = _markdown_quality_report_errors(
        quality,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
    )
    if validation_errors:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report must use the agent_prompt schema v2 contract.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_path": _rel(quality_path),
                "validation_errors": validation_errors,
            },
        )
    if quality.get("status") == PENDING_STATUS and not allow_pending_report:
        raise ToolError(
            "MARKDOWN_QUALITY_REVIEW_PENDING",
            "Markdown quality report is pending agent review; complete the quality review before repair.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_prompt_path": _rel(prompt_path),
                "markdown_quality_path": _rel(quality_path),
                "status": quality.get("status"),
            },
        )
    effective_quality = quality_report_override or quality
    blocking_issues = blocking_markdown_quality_issues(effective_quality)
    if (
        effective_quality.get("status") == "pass"
        and not blocking_issues
        and not allow_passing_report
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_REPAIR_NOT_REQUIRED",
            "Markdown quality report is already passing.",
            retryable=False,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_path": _rel(quality_path),
            },
        )
    if (
        effective_quality.get("status") != "fail"
        and not blocking_issues
        and not (
            allow_pending_report and effective_quality.get("status") == PENDING_STATUS
        )
        and not allow_passing_report
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report must be fail or contain blocking issues before repair.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=task_id,
            details={
                "doi": normalized_doi,
                "markdown_quality_path": _rel(quality_path),
                "status": effective_quality.get("status"),
            },
        )

    purpose, contract = _manifest_fixture_for_doi(manifest, normalized_doi)
    return MarkdownQualityRepairContext(
        provider=provider_name,
        doi=normalized_doi,
        sample_id=sample_id,
        fixture_root=fixture_root,
        expected_path=expected_path,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
        quality_path=quality_path,
        manifest_path=manifest_path,
        review_path=_repo_root() / "onboarding" / "reviews" / f"{provider_name}.yml",
        manifest=manifest,
        golden_sample=sample,
        purpose=purpose,
        markdown_contract=contract,
        quality_report=effective_quality,
        persistent_quality_report=quality,
        fresh_quality_path=fresh_quality_path,
    )


def _markdown_repair_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    blocking = blocking_markdown_quality_issues(report)
    if blocking:
        return blocking
    issues = report.get("issues")
    return (
        [issue for issue in issues if isinstance(issue, dict)]
        if isinstance(issues, list)
        else []
    )


def _infer_markdown_repair_domains(issues: list[dict[str, Any]]) -> list[str]:
    matches: list[str] = []

    def add(domain: str) -> None:
        if domain not in matches:
            matches.append(domain)

    for issue in issues:
        text = " ".join(
            str(issue.get(field) or "") for field in ("id", "summary", "evidence")
        ).lower()
        if re.search(r"\b(table|row|column|cell|header)\b|\|", text):
            add("table")
        if re.search(r"\b(formula|equation|math|latex|tex)\b", text):
            add("formula")
        if re.search(
            r"\b(figure|fig\.|image|caption|asset|media|supplementary)\b", text
        ):
            add("figure/asset")
        if re.search(
            r"\b(reference|references|citation|bibliography|doi-only|scholar)\b", text
        ):
            add("references")
        if re.search(
            r"\b(chrome|boilerplate|navigation|cookie|license|download|toolbar|metrics)\b",
            text,
        ):
            add("chrome/boilerplate")
        if re.search(
            r"javascript|template|placeholder|unresolved|\{\{|ocr|noise", text
        ):
            add("javascript/unresolved text")
        if re.search(
            r"\b(duplicate|duplicated|missing|section|abstract|title|body|empty)\b",
            text,
        ):
            add("duplicate/missing section")
    if not matches:
        matches.append("generic markdown corruption")
    return matches


def _provider_owned_repair_scope(ctx: MarkdownQualityRepairContext) -> list[str]:
    provider = ctx.provider
    return [
        f"src/paper_fetch/providers/{provider}.py",
        f"src/paper_fetch/providers/_{provider}_*.py",
        f"tests/unit/test_{provider}_provider.py",
        f"{_rel(ctx.fixture_root)}/**",
        f"onboarding/reviews/{provider}.yml",
    ]


def _markdown_repair_allowed_scope(
    ctx: MarkdownQualityRepairContext, domains: list[str]
) -> list[str]:
    allowed = _provider_owned_repair_scope(ctx)
    for domain in domains:
        for path in SHARED_MARKDOWN_REPAIR_SCOPES.get(domain, []):
            if path not in allowed:
                allowed.append(path)
    return allowed


def _markdown_repair_forbidden_scope(ctx: MarkdownQualityRepairContext) -> list[str]:
    return [
        "onboarding/access-reviews/",
        "onboarding/known-providers.yml",
        "docs/providers.md",
        "docs/extraction-rules.md",
        "CHANGELOG.md",
        _rel(ctx.manifest_path),
    ]


def _markdown_repair_commands(ctx: MarkdownQualityRepairContext) -> list[list[str]]:
    return [
        [
            "PYTHONPATH=src",
            "python3",
            "-m",
            "pytest",
            f"tests/unit/test_{ctx.provider}_provider.py",
            "tests/unit/test_provider_markdown_review_contract.py",
            "tests/unit/test_provider_asset_contract.py",
            "-q",
        ],
        [
            "PYTHONPATH=src",
            "python3",
            "scripts/snapshot_expected.py",
            "--doi",
            ctx.doi,
        ],
        [
            "PYTHONPATH=src",
            "python3",
            "scripts/onboard_from_manifests.py",
            "check-snapshot",
            "--provider",
            ctx.provider,
            "--doi",
            ctx.doi,
        ],
    ]


def _markdown_repair_brief(
    ctx: MarkdownQualityRepairContext,
    *,
    attempt: int,
    max_attempts: int,
    domains: list[str],
    allowed_scope: list[str],
) -> dict[str, Any]:
    assets = (
        ctx.golden_sample.get("assets")
        if isinstance(ctx.golden_sample.get("assets"), dict)
        else {}
    )
    issues = _markdown_repair_issues(ctx.quality_report)
    issue_payload = [
        {
            "id": issue.get("id"),
            "severity": issue.get("severity"),
            "blocking": issue.get("blocking"),
            "summary": issue.get("summary"),
            "evidence": issue.get("evidence"),
            "domain": domain,
        }
        for issue, domain in zip(
            issues,
            domains + [domains[-1]] * max(0, len(issues) - len(domains)),
            strict=False,
        )
    ]
    return {
        "task_id": f"{ctx.provider}-{REPAIR_MARKDOWN_QUALITY_STEP}-{ctx.sample_id}",
        "current_step": REPAIR_MARKDOWN_QUALITY_STEP,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "runtime": "coding-agent-subagent",
        "provider": ctx.provider,
        "provider_manifest": _rel(ctx.manifest_path),
        "review_artifact": _rel(ctx.review_path),
        "doi": ctx.doi,
        "sample_id": ctx.sample_id,
        "purpose": ctx.purpose,
        "fixture": {
            "root": _rel(ctx.fixture_root),
            "expected": _rel(ctx.expected_path),
            "markdown": _rel(ctx.markdown_path),
            "markdown_sha256": _sha256_file(ctx.markdown_path),
            "quality_prompt": _rel(ctx.prompt_path),
            "quality_report": _rel(ctx.quality_path),
            "fresh_quality_report": _rel(ctx.fresh_quality_path)
            if ctx.fresh_quality_path
            else None,
            "assets": assets,
        },
        "markdown_contract": ctx.markdown_contract,
        "repair_domains": domains,
        "quality_issues": issue_payload,
        "required_order": [
            "Add or update a provider-local regression test for each issue before changing implementation.",
            "Prefer provider-owned implementation files; use shared renderer paths only when the inferred domain explicitly allows them.",
            "Regenerate the DOI snapshot with scripts/snapshot_expected.py --doi after the implementation fix.",
            "Do not mark markdown_semantic_reviewed true; semantic signoff remains operator controlled.",
        ],
        "files_allowed_to_modify": allowed_scope,
        "files_must_not_modify": _markdown_repair_forbidden_scope(ctx),
        "verification_commands": _markdown_repair_commands(ctx),
        "no_commit": True,
    }


def _markdown_excerpt(path: Path, *, limit: int = 6000) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    head = text[: limit // 2].rstrip()
    tail = text[-limit // 2 :].lstrip()
    return f"{head}\n\n[... markdown excerpt truncated ...]\n\n{tail}"


def _markdown_repair_worker_prompt(
    ctx: MarkdownQualityRepairContext,
    brief: dict[str, Any],
) -> str:
    return (
        f"# Markdown quality repair worker: {ctx.provider} / {ctx.doi}\n"
        "\n"
        "Fix the failing Markdown baseline by changing implementation and tests, not by editing the quality report.\n"
        "Do not commit changes.\n"
        "\n"
        "## Repair Brief\n"
        "```yaml\n"
        f"{to_yaml(brief)}\n"
        "```\n"
        "\n"
        "## Current Markdown Quality Report\n"
        "```json\n"
        f"{json.dumps(ctx.quality_report, indent=2, sort_keys=True)}\n"
        "```\n"
        "\n"
        "## Extracted Markdown Excerpt\n"
        "```markdown\n"
        f"{_markdown_excerpt(ctx.markdown_path)}\n"
        "```\n"
    )


def _markdown_quality_review_prompt(ctx: MarkdownQualityRepairContext) -> str:
    prompt_text = ctx.prompt_path.read_text(encoding="utf-8", errors="replace")
    return (
        f"# Markdown quality repair review: {ctx.provider} / {ctx.doi}\n"
        "\n"
        "Read the current extracted Markdown and write the pass/fail report requested below.\n"
        f"You may modify only `{_rel(ctx.quality_path)}`. Do not modify code, tests, expected snapshots, or extracted Markdown.\n"
        "\n"
        "## Existing Review Prompt\n"
        "```markdown\n"
        f"{prompt_text}\n"
        "```\n"
    )


def _run_env_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    argv = list(command)
    while argv and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", argv[0]):
        key, value = argv.pop(0).split("=", 1)
        env[key] = value
    if not argv:
        raise ValueError("command must contain an executable")
    return subprocess.run(
        argv,
        cwd=_repo_root(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else _repo_root() / path


def check_cleaning_proposal_freshness(
    provider: str,
    *,
    proposal_path: Path | None = None,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    proposal_ref = default_cleaning_proposal_path(provider_name)
    path = proposal_path or (_repo_root() / proposal_ref)
    if not path.exists():
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal is missing; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": "missing_proposal",
            },
        )
    try:
        proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal YAML is invalid; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": str(exc),
            },
        ) from exc
    if not isinstance(proposal, dict) or proposal.get("schema_version") != 2:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal is stale or legacy; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "schema_version": proposal.get("schema_version")
                if isinstance(proposal, dict)
                else None,
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": "proposal_schema_not_compact",
            },
        )
    digest_items = proposal.get("fixtures_digest")
    if not isinstance(digest_items, list) or not digest_items:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal has no fixture digest; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "reason": "missing_fixtures_digest",
            },
        )

    stale: list[dict[str, Any]] = []
    checked = 0
    for item in digest_items:
        if not isinstance(item, dict):
            stale.append({"reason": "invalid_digest_item", "item": item})
            continue
        raw_path = item.get("raw_path")
        expected_sha = item.get("sha256")
        if not raw_path or not expected_sha:
            stale.append(
                {
                    "purpose": item.get("purpose"),
                    "doi": item.get("doi"),
                    "raw_path": raw_path,
                    "reason": "missing_digest_path_or_sha256",
                }
            )
            continue
        fixture_path = _resolve_repo_path(str(raw_path))
        if not fixture_path.exists():
            stale.append(
                {
                    "purpose": item.get("purpose"),
                    "doi": item.get("doi"),
                    "raw_path": raw_path,
                    "reason": "fixture_missing",
                }
            )
            continue
        actual_sha = _sha256_file(fixture_path)
        checked += 1
        if actual_sha != str(expected_sha):
            stale.append(
                {
                    "purpose": item.get("purpose"),
                    "doi": item.get("doi"),
                    "raw_path": raw_path,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "reason": "sha256_mismatch",
                }
            )
    if stale:
        raise ToolError(
            "MARKDOWN_CONTRACT_DRIFT",
            "Cleaning proposal fixture digest is stale; rerun propose-cleaning-chain.",
            retryable=True,
            provider=provider_name,
            manifest=default_manifest_path(provider_name),
            task_id=f"{provider_name}-{PROPOSE_CLEANING_STEP}",
            details={
                "proposal": path.as_posix(),
                "recovery_task": PROPOSE_CLEANING_STEP,
                "stale_fixtures_digest": stale,
            },
        )
    return {
        "provider": provider_name,
        "proposal": path.as_posix(),
        "fixtures_checked": checked,
        "result": "passed",
    }


def _command_failed(
    command: list[str], completed: subprocess.CompletedProcess[str]
) -> bool:
    argv = _command_argv(command)
    if len(argv) >= 2 and argv[0] == "git" and argv[1] == "grep":
        return completed.returncode != 1
    return completed.returncode != 0


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _command_argv(command: list[str]) -> list[str]:
    return [
        part for part in command if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", part)
    ]


def _is_cleaning_contract_command(command: list[str]) -> bool:
    argv = _command_argv(command)
    return (
        len(argv) >= 3
        and argv[0] == "python3"
        and argv[1] == "scripts/propose_cleaning_chain.py"
        and "--check-contract" in argv
    )


def _failure_code_for_task(task: str, command: list[str] | None = None) -> str:
    if command is not None and _is_cleaning_contract_command(command):
        return "MARKDOWN_CONTRACT_DRIFT"
    if task == SNAPSHOT_EXPECTED_STEP:
        return "EXPECTED_SNAPSHOT_FAILED"
    if task == "global-lint":
        return "GLOBAL_LINT_FAILED"
    if task == SHARED_INTEGRATION_STEP:
        return "SHARED_INTEGRATION_FAILED"
    if task == "provider-local-acceptance":
        return "PROVIDER_LOCAL_ACCEPTANCE_FAILED"
    if task == "validate-manifest":
        return "MANIFEST_SCHEMA_INVALID"
    if task == ACCESS_PREFLIGHT_STEP:
        return "ACCESS_REVIEW_NOT_FOUND"
    return "LOCAL_CHECK_FAILED"


def _load_failure_recovery_entries() -> dict[str, dict[str, Any]]:
    path = _repo_root() / FAILURE_RECOVERY_PATH
    entries: dict[str, dict[str, Any]] = {}
    current_code: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## Signal: "):
            current_code = line.removeprefix("## Signal: ").strip()
            entries[current_code] = {}
            continue
        if current_code is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in {"diagnosis", "action", "retryable"}:
            entries[current_code][key] = value
    for entry in entries.values():
        retryable = entry.get("retryable")
        if isinstance(retryable, str):
            entry["retryable"] = retryable.lower() == "true"
    return entries


def _latest_failure(provider_state: dict[str, Any]) -> dict[str, Any] | None:
    runs = provider_state.get("runs")
    if not isinstance(runs, dict):
        return None
    ordered_tasks: list[str] = []
    task_statuses = provider_state.get("task_statuses")
    task_statuses = task_statuses if isinstance(task_statuses, dict) else {}
    current_step = provider_state.get("current_step")
    if isinstance(current_step, str) and task_statuses.get(current_step) != "completed":
        ordered_tasks.append(current_step)
    steps = provider_state.get("steps")
    if isinstance(steps, list):
        ordered_tasks.extend(
            str(step)
            for step in reversed(steps)
            if task_statuses.get(step) in {"failed", "blocked"}
        )
    ordered_tasks.extend(
        str(task)
        for task, status in task_statuses.items()
        if status in {"failed", "blocked"}
        and (not isinstance(steps, list) or task not in steps)
    )
    seen: set[str] = set()
    for task in ordered_tasks:
        if task in seen:
            continue
        seen.add(task)
        run = runs.get(task)
        if not isinstance(run, dict):
            continue
        failure = run.get("failure")
        if isinstance(failure, dict):
            return {"task": task, **failure}
    return None


def _access_review_summary(provider: str) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    path = _repo_root() / default_access_review_path(provider_name)
    if not path.exists():
        return {
            "status": "missing",
            "path": default_access_review_path(provider_name),
            "may_continue": False,
            "approved": False,
        }
    try:
        review = _load_access_review(provider_name)
    except ToolError as exc:
        return {
            "status": "schema_invalid",
            "path": default_access_review_path(provider_name),
            "may_continue": False,
            "approved": False,
            "error_code": exc.code,
        }
    status = str(review.get("status") or "unknown")
    may_continue = review.get("may_continue") is True
    approved = status == "approved" and may_continue
    if not approved and review.get("reviewed_by") == "operator-required":
        status_label = "draft"
    else:
        status_label = "approved" if approved else status
    return {
        "status": status_label,
        "path": default_access_review_path(provider_name),
        "may_continue": may_continue,
        "approved": approved,
        "reviewed_by": review.get("reviewed_by"),
        "legal_access_mode": (
            review.get("legal_access", {}).get("mode")
            if isinstance(review.get("legal_access"), dict)
            else None
        ),
        "allowed_runtimes": review.get("allowed_runtimes"),
    }


OPERATOR_REQUIRED_FAILURE_CODES = {
    "ACCESS_REVIEW_NOT_FOUND",
    "ACCESS_REVIEW_SCHEMA_INVALID",
    "ACCESS_REVIEW_NOT_APPROVED",
    "BROWSER_RUNTIME_REQUIRED",
    "CHALLENGE_DETECTED",
    "WORKER_MODIFIED_FORBIDDEN_FILE",
    "MANIFEST_PROVIDER_CONFLICT",
    "DISCOVERY_RETRY_EXHAUSTED",
    "TASK_RETRY_EXHAUSTED",
}

AGENT_TARGET_STEPS = {
    "local-ready": "provider-local-acceptance",
    "merge-ready": "merge-ready",
}

AGENT_FAILURE_USER_ACTIONS = {
    "ACCESS_REVIEW_NOT_FOUND": (
        "我需要生成或定位 access review 草稿；你稍后只需确认访问策略。"
    ),
    "ACCESS_REVIEW_NOT_APPROVED": (
        "我停在访问批准点；请人工确认 access review 后告诉我继续。"
    ),
    "ACCESS_REVIEW_SCHEMA_INVALID": (
        "access review 文件结构不合法；我会指出字段，用户只需确认真实访问策略。"
    ),
    "BROWSER_RUNTIME_REQUIRED": (
        "当前路线需要 browser runtime；请决定是否允许，不能默认绕过。"
    ),
    "HTTP_FORBIDDEN": (
        "当前样本被拒绝；若 access review 允许 browser 我会重试，否则我会换 DOI 或停下说明。"
    ),
    "HTTP_RATE_LIMITED": (
        "这是暂态或限流；我会按 retry budget 重试，耗尽后给出等待或换样本建议。"
    ),
    "NETWORK_TRANSIENT": (
        "这是暂态网络失败；我会按 retry budget 重试，耗尽后给出等待或换样本建议。"
    ),
    "CHALLENGE_DETECTED": (
        "遇到 challenge/CAPTCHA；我不会绕过，只能按 access review 重试或换样本。"
    ),
    "UNSUITABLE_DOI_SAMPLE": (
        "这个 DOI 不适合当前 purpose；我会只替换这个 purpose 的样本。"
    ),
    "NON_PDF_FALLBACK_CONTENT": (
        "PDF fallback 样本不是 PDF；我会重新找 pdf_fallback 样本。"
    ),
    "ACCESS_GATE_CAPTURED": ("样本捕获到 access gate；我会替换失败 purpose 的 DOI。"),
    "EMPTY_ARTICLE_SHELL": ("样本捕获到空文章壳；我会替换失败 purpose 的 DOI。"),
    "MARKDOWN_CONTRACT_DRIFT": (
        "Markdown contract 与当前 fixture 不一致；我会先刷新 cleaning proposal 或回到实现修复。"
    ),
    "MARKDOWN_QUALITY_FAILED": (
        "当前 Markdown 还有 blocking issue；我会运行 repair loop，失败后给出具体 artifact。"
    ),
    "MARKDOWN_QUALITY_REPAIR_FAILED": (
        "自动修复预算耗尽；需要人工看最后一轮 quality report 和 repair logs。"
    ),
    "PROVIDER_LOCAL_ACCEPTANCE_FAILED": (
        "provider-local 验证失败；我会修 provider-owned 实现或测试，并汇报失败命令。"
    ),
    "SHARED_INTEGRATION_FAILED": (
        "shared integration 验证失败；我会只修有 manifest/fixture/test 证据支持的 shared surface。"
    ),
    "GLOBAL_LINT_FAILED": ("全局本地检查失败；我只修当前 provider 引入的问题。"),
    "WORKER_MODIFIED_FORBIDDEN_FILE": (
        "worker 修改了不该改的文件；我会停下保护工作区并说明越界路径。"
    ),
    "DISCOVERY_RETRY_EXHAUSTED": (
        "自动 discovery 重试耗尽；我会列出失败 task、最近命令、artifact 路径和需要的新事实。"
    ),
    "TASK_RETRY_EXHAUSTED": (
        "自动重试耗尽；我会列出失败 task、最近命令、artifact 路径和需要的新事实。"
    ),
}


def _latest_markdown_quality_repair(
    provider_state: dict[str, Any],
) -> dict[str, Any] | None:
    repairs = provider_state.get("repairs")
    if not isinstance(repairs, dict):
        return None
    markdown_repairs = repairs.get("markdown_quality")
    if not isinstance(markdown_repairs, list) or not markdown_repairs:
        return None
    latest = markdown_repairs[-1]
    return latest if isinstance(latest, dict) else None


def diagnose_provider_state(provider_state: dict[str, Any]) -> dict[str, Any]:
    provider = _provider_slug(str(provider_state.get("provider") or "unknown"))
    recovery_entries = _load_failure_recovery_entries()
    failure = _latest_failure(provider_state)
    failure_code = str(failure.get("code")) if failure and failure.get("code") else None
    recovery = recovery_entries.get(failure_code or "", {})
    retryable = (
        bool(recovery.get("retryable")) if failure_code in recovery_entries else None
    )
    operator_required = (
        failure_code in OPERATOR_REQUIRED_FAILURE_CODES
        if failure_code is not None
        else False
    )
    access = _access_review_summary(provider)
    if not access["approved"] and provider_state.get("status") == "blocked":
        operator_required = True
    return {
        "provider": provider,
        "status": provider_state.get("status"),
        "current_step": provider_state.get("current_step"),
        "failure": {
            "task": failure.get("task") if failure else None,
            "code": failure_code,
            "retryable": retryable,
            "diagnosis": recovery.get("diagnosis"),
            "action": recovery.get("action"),
        },
        "access_review": access,
        "recent_markdown_quality_repair": _latest_markdown_quality_repair(
            provider_state
        ),
        "operator_required": operator_required,
    }


def plan_resume_blocked(provider_state: dict[str, Any]) -> dict[str, Any]:
    diagnosis = diagnose_provider_state(provider_state)
    provider = diagnosis["provider"]
    failure = diagnosis["failure"]
    code = failure.get("code")
    task = failure.get("task") or provider_state.get("current_step")
    blockers: list[str] = []
    if provider_state.get("status") != "blocked":
        blockers.append("provider status is not blocked")
    if not isinstance(task, str) or not task:
        blockers.append("no failed or current task is recorded")
    if failure.get("retryable") is not True:
        blockers.append(f"failure code is not retryable: {code}")
    access = diagnosis["access_review"]
    if not access.get("approved"):
        blockers.append(f"access review is not approved: {access.get('status')}")
    if code in OPERATOR_REQUIRED_FAILURE_CODES:
        blockers.append(f"operator action required for failure code: {code}")
    if code == "UNSUITABLE_DOI_SAMPLE":
        blockers.append(
            "failed DOI purpose must be replaced or explicitly approved before retry"
        )
    if code == "NON_PDF_FALLBACK_CONTENT":
        blockers.append("failed pdf_fallback DOI sample must be replaced before retry")
    if code == "BROWSER_RUNTIME_REQUIRED":
        blockers.append("browser runtime must be configured and approved before retry")
    resumable = not blockers
    next_task = IMPLEMENT_STEP if code == "MARKDOWN_CONTRACT_DRIFT" else task
    return {
        "provider": provider,
        "resumable": resumable,
        "next_task": next_task if isinstance(next_task, str) else None,
        "operator_required": bool(blockers),
        "blockers": blockers,
        "diagnosis": diagnosis,
    }


def _source_from_provider_state(provider_state: dict[str, Any]) -> OnboardingSource:
    provider = _provider_slug(str(provider_state["provider"]))
    manifest = str(provider_state.get("manifest") or default_manifest_path(provider))
    include_discovery = DISCOVER_STEP in set(provider_state.get("steps") or [])
    manifest_yaml: str | None = None
    if not include_discovery:
        manifest_path = _repo_root() / manifest
        if manifest_path.exists():
            manifest_yaml = manifest_path.read_text(encoding="utf-8")
    return OnboardingSource(
        provider=provider,
        manifest=manifest,
        include_discovery=include_discovery,
        manifest_yaml=manifest_yaml,
    )


def _execute_run_loop(
    *,
    source: OnboardingSource,
    output_dir: Path,
    state_path: Path,
    state: dict[str, Any],
    provider_state: dict[str, Any],
    until: str,
    domain: str | None,
    doi_prefix: str | None,
) -> dict[str, Any]:
    _run_artifacts(
        source=source,
        output_dir=output_dir,
        domain=domain,
        doi_prefix=doi_prefix,
    )
    state["agent_cli"] = _worker_dispatcher_label() or state.get("agent_cli")
    executed: list[str] = []
    try:
        while True:
            task = _next_pending_step(provider_state)
            if task is None:
                failed_steps = _failed_steps(provider_state)
                if failed_steps:
                    failed_task = failed_steps[0]
                    provider_state["current_step"] = failed_task
                    provider_state["status"] = "blocked"
                    state["active_provider"] = source.provider
                    _write_json(state_path, state)
                    failure = (
                        provider_state.get("runs", {})
                        .get(failed_task, {})
                        .get("failure", {})
                    )
                    raise ToolError(
                        str(failure.get("code") or "TASK_PREVIOUSLY_FAILED"),
                        f"onboarding run cannot continue while task {failed_task} is failed.",
                        retryable=bool(failure.get("retryable", True)),
                        provider=source.provider,
                        manifest=source.manifest,
                        task_id=f"{source.provider}-run-{failed_task}",
                        details={
                            "failed_task": failed_task,
                            "failed_steps": failed_steps,
                            "failure": failure if isinstance(failure, dict) else {},
                        },
                    )
                break
            if task in {DISCOVER_STEP, IMPLEMENT_STEP}:
                brief_name = (
                    "discover-manifest.yml"
                    if task == DISCOVER_STEP
                    else "implement-provider.yml"
                )
                if task == DISCOVER_STEP:
                    _prepare_discovery_for_runner(
                        provider=source.provider,
                        domain=domain,
                        doi_prefix=doi_prefix,
                        output_dir=output_dir,
                    )
                _dispatch_worker(
                    provider=source.provider,
                    task=task,
                    brief_path=output_dir / "briefs" / brief_name,
                    output_dir=output_dir,
                    provider_state=provider_state,
                )
                if task == DISCOVER_STEP:
                    _autofix_manifest_for_runner(
                        provider=source.provider,
                        manifest=source.manifest,
                        output_dir=output_dir,
                        targeted=False,
                    )
            else:
                _execute_local_task(
                    provider=source.provider,
                    task=task,
                    provider_state=provider_state,
                    state=state,
                    state_path=state_path,
                    output_dir=output_dir,
                )
                if task == PROPOSE_CLEANING_STEP:
                    _write_implementation_brief(output_dir=output_dir, source=source)
            executed.append(task)
            _mark_step_completed(
                state,
                provider_state,
                provider=source.provider,
                task=task,
            )
            _write_json(state_path, state)
            if task == until:
                break
    except ToolError:
        failed_task = provider_state.get("current_step")
        if isinstance(failed_task, str):
            _mark_step_failed(
                state,
                provider_state,
                provider=source.provider,
                task=failed_task,
            )
            _write_json(state_path, state)
        raise

    _write_json(state_path, state)
    return {
        "provider": source.provider,
        "manifest": source.manifest,
        "executed": executed,
        "until": until,
        "status": provider_state["status"],
        "current_step": provider_state.get("current_step"),
        "state": str(state_path),
        "output_dir": str(output_dir),
    }


def _record_run(
    provider_state: dict[str, Any],
    *,
    task: str,
    commands: list[list[str]],
    result: str,
    failure: dict[str, Any] | None = None,
) -> None:
    runs = provider_state.setdefault("runs", {})
    entry: dict[str, Any] = {
        "dry_run": False,
        "commands": commands,
        "result": result,
    }
    if failure is not None:
        entry["failure"] = failure
    runs[task] = entry


def _failure_from_tool_error(
    exc: ToolError,
    *,
    commands: list[list[str]],
) -> dict[str, Any]:
    structured = error_payload(
        exc.code,
        exc.message,
        provider=exc.provider,
        manifest=exc.manifest,
        task_id=exc.task_id,
        retryable=exc.retryable,
        details=exc.details,
        extras=exc.extras,
    )
    return {
        "code": exc.code,
        "command": commands[0] if commands else [],
        "returncode": 1,
        "stdout_tail": "",
        "stderr_tail": json.dumps(structured, ensure_ascii=False, sort_keys=True),
        "structured_error": structured,
    }


def _mark_step_failed(
    state: dict[str, Any],
    provider_state: dict[str, Any],
    *,
    provider: str,
    task: str,
) -> None:
    provider_state["task_statuses"][task] = "failed"
    provider_state["current_step"] = task
    provider_state["status"] = "blocked"
    state["active_provider"] = provider


def _mark_step_completed(
    state: dict[str, Any],
    provider_state: dict[str, Any],
    *,
    provider: str,
    task: str,
) -> str | None:
    task_statuses = provider_state["task_statuses"]
    task_statuses[task] = "completed"
    completed_steps = provider_state["completed_steps"]
    if task not in completed_steps:
        completed_steps.append(task)
    provider_state["current_step"] = None
    next_step = _next_pending_step(provider_state)
    if next_step is None:
        failed_steps = _failed_steps(provider_state)
        if failed_steps:
            provider_state["current_step"] = failed_steps[0]
            provider_state["status"] = "blocked"
            state["active_provider"] = provider
        else:
            provider_state["status"] = "merge_ready"
            state["active_provider"] = None
    else:
        provider_state["status"] = "in_progress"
        state["active_provider"] = provider
    return next_step


def _write_implementation_brief(*, output_dir: Path, source: OnboardingSource) -> None:
    manifest_yaml = source.manifest_yaml
    manifest_path = _repo_root() / source.manifest
    if manifest_yaml is None and manifest_path.exists():
        manifest_yaml = manifest_path.read_text(encoding="utf-8")
    implementation_brief = build_implementation_brief(
        provider=source.provider,
        manifest=source.manifest,
        manifest_yaml=manifest_yaml,
    )
    write_text(
        output_dir / "briefs" / "implement-provider.yml",
        to_yaml(implementation_brief) + "\n",
    )


def _discovery_no_network_requested() -> bool:
    value = os.environ.get(DISCOVERY_NO_NETWORK_ENV)
    if value is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _runner_evidence_pack_path(*, provider: str, output_dir: Path) -> Path:
    path = Path(default_evidence_pack_path(provider, output_dir))
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _prepare_discovery_for_runner(
    *,
    provider: str,
    domain: str | None,
    doi_prefix: str | None,
    output_dir: Path,
) -> dict[str, Any]:
    return prepare_manifest_discovery(
        provider=provider,
        domain=domain,
        doi_prefix=doi_prefix,
        output_dir=output_dir,
        no_network=_discovery_no_network_requested(),
    )


def _autofix_manifest_for_runner(
    *,
    provider: str,
    manifest: str,
    output_dir: Path | None,
    targeted: bool = False,
) -> dict[str, Any]:
    manifest_path = Path(manifest)
    if not manifest_path.is_absolute():
        manifest_path = _repo_root() / manifest_path
    if not manifest_path.exists():
        return {
            "changed": False,
            "changed_paths": [],
            "targeted": targeted,
            "skipped": "manifest_missing",
            "manifest": manifest_path.as_posix(),
        }
    evidence_path = (
        _runner_evidence_pack_path(
            provider=provider,
            output_dir=output_dir,
        )
        if output_dir is not None
        else None
    )
    if evidence_path is None or not evidence_path.exists():
        return {
            "changed": False,
            "changed_paths": [],
            "targeted": targeted,
            "skipped": "evidence_pack_missing",
            "manifest": manifest_path.as_posix(),
            "evidence_pack": evidence_path.as_posix() if evidence_path else None,
        }
    return autofix_manifest_file(
        manifest_path=manifest_path,
        evidence_pack_path=evidence_path,
        write=True,
        targeted=targeted,
    )


def _run_artifacts(
    *,
    source: OnboardingSource,
    output_dir: Path,
    domain: str | None,
    doi_prefix: str | None,
) -> None:
    dag = build_dag(
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
        dry_run=False,
    )
    write_text(
        output_dir / "task-dag.json",
        json.dumps(dag, indent=2, sort_keys=True) + "\n",
    )
    if source.include_discovery:
        evidence_pack = default_evidence_pack_path(source.provider, output_dir)
        discover_brief = build_discover_brief(
            provider=source.provider,
            domain=domain,
            doi_prefix=doi_prefix,
            output_manifest=source.manifest,
            evidence_pack=evidence_pack,
        )
        write_text(
            output_dir / "briefs" / "discover-manifest.yml",
            to_yaml(discover_brief) + "\n",
        )
    _write_implementation_brief(output_dir=output_dir, source=source)


def _workspace_changed_paths() -> set[str]:
    root = _repo_root()
    paths: set[str] = set()
    diff = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if diff.returncode == 0:
        paths.update(line.strip() for line in diff.stdout.splitlines() if line.strip())
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip() if len(line) > 3 else line.strip()
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[-1]
            if path:
                paths.add(path)
    return paths


def _matches_forbidden(path: str, forbidden: list[str]) -> bool:
    normalized = path.strip("/")
    for item in forbidden:
        pattern = item.strip()
        if not pattern:
            continue
        if pattern.endswith("/"):
            base = pattern.strip("/")
            if normalized == base or normalized.startswith(base + "/"):
                return True
            continue
        if normalized == pattern.strip("/") or normalized.startswith(
            pattern.strip("/") + "/"
        ):
            return True
    return False


def _forbidden_changes(
    before: set[str], after: set[str], forbidden: list[str]
) -> list[str]:
    return sorted(
        path for path in after - before if _matches_forbidden(path, forbidden)
    )


def _matches_scope(path: str, scope: list[str]) -> bool:
    normalized = path.strip("/")
    for item in scope:
        pattern = item.strip().strip("/")
        if not pattern:
            continue
        if fnmatchcase(normalized, pattern):
            return True
        if pattern.endswith("/**"):
            base = pattern[:-3].strip("/")
            if normalized == base or normalized.startswith(base + "/"):
                return True
        if pattern.endswith("/"):
            base = pattern.strip("/")
            if normalized == base or normalized.startswith(base + "/"):
                return True
        elif normalized == pattern or normalized.startswith(pattern + "/"):
            return True
    return False


def _disallowed_changes(
    before: set[str], after: set[str], allowed: list[str]
) -> list[str]:
    return sorted(path for path in after - before if not _matches_scope(path, allowed))


def _agent_argv(
    *,
    provider: str,
    task: str,
    manifest: str | None = None,
) -> list[str]:
    return _worker_dispatcher(provider=provider, task=task, manifest=manifest).argv


def _load_brief(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"worker brief must load as a mapping: {path}")
    return data


def _worker_prompt(
    *,
    provider: str,
    task: str,
    brief: dict[str, Any],
) -> str:
    root = _repo_root()
    parts = [
        f"# Provider onboarding worker task: {provider} / {task}",
        "",
        "Follow the YAML task brief exactly. Do not commit changes.",
        "",
        "## Task Brief",
        "```yaml",
        to_yaml(brief),
        "```",
    ]
    access_path = root / default_access_review_path(provider)
    if access_path.exists():
        parts.extend(
            [
                "",
                "## Access Review",
                "```yaml",
                access_path.read_text(encoding="utf-8"),
                "```",
            ]
        )
    hard_constraints = root / HARD_CONSTRAINTS_PATH
    if hard_constraints.exists():
        parts.extend(
            [
                "",
                "## Hard Constraints",
                "```markdown",
                hard_constraints.read_text(encoding="utf-8"),
                "```",
            ]
        )
    if task == DISCOVER_STEP:
        evidence_ref = brief.get("evidence_pack")
        evidence_path_value = (
            evidence_ref.get("path") if isinstance(evidence_ref, dict) else evidence_ref
        )
        if isinstance(evidence_path_value, str):
            evidence_path = Path(evidence_path_value)
            if not evidence_path.is_absolute():
                evidence_path = root / evidence_path
            if evidence_path.exists():
                try:
                    evidence_pack = _load_evidence_pack(evidence_path)
                    parts.extend(
                        [
                            "",
                            "## Discovery Evidence Pack Summary",
                            "```json",
                            json.dumps(
                                _compact_evidence_pack_summary(evidence_pack),
                                indent=2,
                                sort_keys=True,
                            ),
                            "```",
                            "",
                            f"Full evidence pack: `{evidence_path_value}`",
                        ]
                    )
                except ToolError:
                    parts.extend(
                        [
                            "",
                            "## Discovery Evidence Pack Summary",
                            f"Evidence pack was declared but could not be loaded: `{evidence_path_value}`",
                        ]
                    )
        schema = root / SCHEMA_PATH
        if schema.exists():
            parts.extend(
                [
                    "",
                    "## Provider Manifest Schema",
                    "```json",
                    schema.read_text(encoding="utf-8"),
                    "```",
                ]
            )
    if task == IMPLEMENT_STEP:
        manifest_path = root / str(
            brief.get("provider_manifest") or default_manifest_path(provider)
        )
        if manifest_path.exists():
            parts.extend(
                [
                    "",
                    "## Provider Manifest",
                    "```yaml",
                    manifest_path.read_text(encoding="utf-8"),
                    "```",
                ]
            )
        proposal_path = root / default_cleaning_proposal_path(provider)
        if proposal_path.exists():
            parts.extend(
                [
                    "",
                    "## Compact Cleaning Proposal",
                    "```yaml",
                    proposal_path.read_text(encoding="utf-8"),
                    "```",
                ]
            )
    return "\n".join(parts) + "\n"


def _dispatch_worker(
    *,
    provider: str,
    task: str,
    brief_path: Path,
    output_dir: Path,
    provider_state: dict[str, Any],
) -> None:
    dispatcher = _worker_dispatcher(
        provider=provider,
        task=task,
        manifest=provider_state.get("manifest"),
    )
    brief = _load_brief(brief_path)
    prompt = _worker_prompt(provider=provider, task=task, brief=brief)
    allowed = [str(value) for value in brief.get("files_allowed_to_modify") or ()]
    forbidden = [str(value) for value in brief.get("files_must_not_modify") or ()]
    worker_dir = output_dir / "workers"
    worker_dir.mkdir(parents=True, exist_ok=True)
    argv = dispatcher.argv

    retry_counts = provider_state.setdefault("retry_counts", {})
    attempt_start = int(retry_counts.get(task, 0)) + 1
    commands = [argv]
    last_failure: dict[str, Any] | None = None
    for attempt in range(attempt_start, MAX_WORKER_RETRIES + 1):
        before = _workspace_changed_paths()
        completed = subprocess.run(
            argv,
            cwd=_repo_root(),
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
        )
        prefix = worker_dir / f"{task}-attempt-{attempt}"
        write_text(prefix.with_suffix(".prompt.md"), prompt)
        write_text(prefix.with_suffix(".stdout.log"), completed.stdout)
        write_text(prefix.with_suffix(".stderr.log"), completed.stderr)
        after = _workspace_changed_paths()
        forbidden_paths = _forbidden_changes(before, after, forbidden)
        if forbidden_paths:
            retry_counts[task] = attempt
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "forbidden_paths": forbidden_paths,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            _record_run(
                provider_state,
                task=task,
                commands=commands,
                result="failed",
                failure=last_failure,
            )
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "worker modified files outside its allowed scope.",
                retryable=True,
                provider=provider,
                manifest=provider_state.get("manifest"),
                task_id=f"{provider}-{task}",
                details=last_failure,
            )
        disallowed_paths = (
            _disallowed_changes(before, after, allowed) if allowed else []
        )
        if disallowed_paths:
            retry_counts[task] = attempt
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "disallowed_paths": disallowed_paths,
                "allowed_scope": allowed,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            _record_run(
                provider_state,
                task=task,
                commands=commands,
                result="failed",
                failure=last_failure,
            )
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "worker modified files outside its allowed scope.",
                retryable=True,
                provider=provider,
                manifest=provider_state.get("manifest"),
                task_id=f"{provider}-{task}",
                details=last_failure,
            )
        if completed.returncode == 0:
            _record_run(provider_state, task=task, commands=commands, result="passed")
            return
        retry_counts[task] = attempt
        last_failure = {
            "code": "WORKER_AGENT_FAILED",
            "attempt": attempt,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    _record_run(
        provider_state,
        task=task,
        commands=commands,
        result="failed",
        failure=last_failure,
    )
    raise ToolError(
        "TASK_RETRY_EXHAUSTED",
        f"worker task {task} failed after {MAX_WORKER_RETRIES} attempts.",
        retryable=False,
        provider=provider,
        manifest=provider_state.get("manifest"),
        task_id=f"{provider}-{task}",
        details=last_failure or {"task": task},
    )


def _run_task_commands(
    provider: str,
    task: str,
    *,
    manifest: str | None = None,
) -> list[list[str]]:
    provider_name = _provider_slug(provider)
    manifest_path = manifest or default_manifest_path(provider_name)
    if task == "validate-manifest":
        return [
            [
                "PYTHONPATH=src",
                "python3",
                "-m",
                "pytest",
                "tests/unit/test_provider_manifest_schema.py",
                "-q",
            ]
        ]
    if task == "capture-fixtures":
        return [
            [
                "python3",
                "scripts/capture_fixture.py",
                "--from-manifest",
                manifest_path,
                "--all",
                "--auto-via",
                "--fail-fast",
            ]
        ]
    if task == PROPOSE_CLEANING_STEP:
        return [
            [
                "python3",
                "scripts/propose_cleaning_chain.py",
                "--provider",
                provider_name,
                "--write",
            ]
        ]
    if task == "scaffold":
        return [
            [
                "python3",
                "scripts/scaffold_provider.py",
                "--from-manifest",
                manifest_path,
                "--merge-existing=safe",
            ]
        ]
    if task == "manifest-sync-back":
        return [
            [
                "python3",
                "scripts/manifest_sync_back.py",
                "--provider",
                provider_name,
                "--manifest",
                manifest_path,
                "--sync-docs",
            ]
        ]
    if task == SNAPSHOT_EXPECTED_STEP:
        commands = _snapshot_expected_commands(provider_name, manifest_path)
        commands.append(
            [
                "python3",
                "scripts/bootstrap_review_artifact.py",
                "--provider",
                provider_name,
                "--manifest",
                manifest_path,
            ]
        )
        return commands
    return _verify_commands(provider_name, task)


def _payload_from_stderr(stderr: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stderr)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _payload_from_stdout_yaml(stdout: str) -> dict[str, Any] | None:
    try:
        payload = yaml.safe_load(stdout)
    except yaml.YAMLError:
        return None
    return payload if isinstance(payload, dict) else None


def _execute_local_task(
    *,
    provider: str,
    task: str,
    provider_state: dict[str, Any],
    state: dict[str, Any] | None = None,
    state_path: Path | None = None,
    output_dir: Path | None = None,
) -> None:
    manifest_path = str(
        provider_state.get("manifest") or default_manifest_path(provider)
    )
    commands = _run_task_commands(provider, task, manifest=manifest_path)
    if task in {ACCESS_PREFLIGHT_STEP, DISCOVER_STEP}:
        try:
            validate_access_review(provider)
        except ToolError as exc:
            _record_run(
                provider_state,
                task=task,
                commands=commands,
                result="failed",
                failure=_failure_from_tool_error(exc, commands=commands),
            )
            raise
    validate_autofix: dict[str, Any] | None = None
    if task == "validate-manifest":
        validate_autofix = _autofix_manifest_for_runner(
            provider=provider,
            manifest=manifest_path,
            output_dir=output_dir,
            targeted=False,
        )
    for command in commands:
        targeted_autofix: dict[str, Any] | None = None
        completed = _run_env_command(command)
        if _command_failed(command, completed):
            failure_code = _failure_code_for_task(task, command)
            structured = _payload_from_stderr(completed.stderr)
            if structured and isinstance(structured.get("code"), str):
                failure_code = str(structured["code"])
            if (
                task == SNAPSHOT_EXPECTED_STEP
                and failure_code == "MARKDOWN_QUALITY_FAILED"
                and state_path is not None
                and "check-snapshot" in command
            ):
                try:
                    doi_index = command.index("--doi") + 1
                    repair_doi = command[doi_index]
                except (ValueError, IndexError):
                    repair_doi = None
                if repair_doi:
                    try:
                        run_repair_markdown_quality(
                            argparse.Namespace(
                                provider=provider,
                                doi=repair_doi,
                                state=str(state_path),
                                output_dir=f".paper-fetch-runs/{provider}-markdown-repair",
                                max_attempts=MAX_WORKER_RETRIES,
                            )
                        )
                    except ToolError as exc:
                        failure = {
                            "code": exc.code,
                            "command": command,
                            "returncode": completed.returncode,
                            "stdout_tail": _tail(completed.stdout),
                            "stderr_tail": _tail(completed.stderr),
                            "auto_repair_failure": {
                                "code": exc.code,
                                "message": exc.message,
                                "details": exc.details,
                            },
                        }
                        if structured:
                            failure["structured_error"] = structured
                        _record_run(
                            provider_state,
                            task=task,
                            commands=commands,
                            result="failed",
                            failure=failure,
                        )
                        raise ToolError(
                            exc.code,
                            "snapshot Markdown quality auto-repair failed.",
                            retryable=exc.retryable,
                            provider=provider,
                            manifest=manifest_path,
                            task_id=f"{provider}-run-{task}",
                            details=failure,
                        ) from exc
                    if state is not None:
                        fresh_state = _load_state(state_path)
                        fresh_provider_state = fresh_state.get("providers", {}).get(
                            provider
                        )
                        if isinstance(fresh_provider_state, dict):
                            provider_state.clear()
                            provider_state.update(fresh_provider_state)
                            state["agent_cli"] = fresh_state.get("agent_cli")
                            state["active_provider"] = fresh_state.get(
                                "active_provider"
                            )
                            state.setdefault("providers", {})[provider] = provider_state
                    completed = _run_env_command(command)
                    if not _command_failed(command, completed):
                        continue
                    failure_code = _failure_code_for_task(task, command)
                    structured = _payload_from_stderr(completed.stderr)
                    if structured and isinstance(structured.get("code"), str):
                        failure_code = str(structured["code"])
            if (
                task == "validate-manifest"
                and failure_code == "MANIFEST_SCHEMA_INVALID"
            ):
                targeted_autofix = _autofix_manifest_for_runner(
                    provider=provider,
                    manifest=manifest_path,
                    output_dir=output_dir,
                    targeted=True,
                )
                rerun = _run_env_command(command)
                if not _command_failed(command, rerun):
                    continue
                completed = rerun
                structured = _payload_from_stderr(completed.stderr)
                if structured and isinstance(structured.get("code"), str):
                    failure_code = str(structured["code"])
            failure = {
                "code": failure_code,
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            if validate_autofix is not None:
                failure["pre_validate_autofix"] = validate_autofix
            if targeted_autofix is not None:
                failure["targeted_autofix"] = targeted_autofix
            if structured:
                failure["structured_error"] = structured
            if _is_cleaning_contract_command(command):
                contract_payload = _payload_from_stdout_yaml(completed.stdout)
                if contract_payload is not None:
                    failure["contract_check"] = contract_payload
            _record_run(
                provider_state,
                task=task,
                commands=commands,
                result="failed",
                failure=failure,
            )
            raise ToolError(
                failure_code,
                f"onboarding run failed for task {task}.",
                retryable=bool(structured.get("retryable")) if structured else True,
                provider=provider,
                manifest=manifest_path,
                task_id=f"{provider}-run-{task}",
                details=failure,
            )
    _record_run(provider_state, task=task, commands=commands, result="passed")


def run_run(args: argparse.Namespace) -> int:
    if args.manifest:
        source = _manifest_source(args.manifest)
    else:
        source = _provider_source(
            provider=args.provider,
            domain=args.domain,
            doi_prefix=args.doi_prefix,
        )
    output_dir = Path(
        args.output_dir or f".paper-fetch-runs/{source.provider}-onboarding"
    )
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    step_ids = _dag_step_ids(source.include_discovery)
    if args.until not in step_ids:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"--until must name a task in the active DAG: {args.until}",
            retryable=False,
            provider=source.provider,
            manifest=source.manifest,
            task_id=f"{source.provider}-run",
            details={"until": args.until, "steps": list(step_ids)},
        )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(
        state,
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
    )
    print(
        json.dumps(
            _execute_run_loop(
                source=source,
                output_dir=output_dir,
                state_path=state_path,
                state=state,
                provider_state=provider_state,
                until=args.until,
                domain=args.domain,
                doi_prefix=args.doi_prefix,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_discover(args: argparse.Namespace) -> int:
    brief = build_discover_brief(
        provider=args.provider,
        domain=args.domain,
        doi_prefix=args.doi_prefix,
        output_manifest=args.output,
        evidence_pack=getattr(args, "evidence_pack", None),
    )
    print(to_yaml(brief))
    return 0


def run_prepare_discovery(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    pack = prepare_manifest_discovery(
        provider=args.provider,
        domain=args.domain,
        doi_prefix=args.doi_prefix,
        output_dir=output_dir,
        no_network=args.no_network,
        browser_fallback=args.browser_fallback,
    )
    payload = {
        "provider": _provider_slug(args.provider),
        "evidence_pack": default_evidence_pack_path(args.provider, output_dir),
        "network_enabled": bool(pack.get("network", {}).get("enabled"))
        if isinstance(pack.get("network"), dict)
        else None,
        "browser_fallback": pack.get("browser_fallback"),
        "query_plan_purposes": sorted((pack.get("query_plan") or {}).keys()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def run_autofix_manifest(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = _repo_root() / manifest_path
    evidence_pack_path = Path(args.evidence_pack)
    if not evidence_pack_path.is_absolute():
        evidence_pack_path = _repo_root() / evidence_pack_path
    result = autofix_manifest_file(
        manifest_path=manifest_path,
        evidence_pack_path=evidence_pack_path,
        write=args.write,
        targeted=bool(getattr(args, "targeted", False)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def run_inspect_discovery(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = _repo_root() / manifest_path
    evidence_pack_path = Path(args.evidence_pack)
    if not evidence_pack_path.is_absolute():
        evidence_pack_path = _repo_root() / evidence_pack_path
    manifest = _read_manifest_for_autofix(manifest_path)
    evidence_pack = _load_evidence_pack(evidence_pack_path)
    result = inspect_manifest_discovery(manifest=manifest, evidence_pack=evidence_pack)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def run_start(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    if args.manifest:
        source = _manifest_source(args.manifest)
    else:
        source = _provider_source(
            provider=args.provider,
            domain=args.domain,
            doi_prefix=args.doi_prefix,
        )

    dag = build_dag(
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
        dry_run=args.dry_run,
    )
    implementation_brief = build_implementation_brief(
        provider=source.provider,
        manifest=source.manifest,
        manifest_yaml=source.manifest_yaml,
    )
    write_text(
        output_dir / "task-dag.json",
        json.dumps(dag, indent=2, sort_keys=True) + "\n",
    )
    write_text(
        output_dir / "briefs" / "implement-provider.yml",
        to_yaml(implementation_brief) + "\n",
    )

    if source.include_discovery:
        evidence_pack = default_evidence_pack_path(source.provider, output_dir)
        discover_brief = build_discover_brief(
            provider=source.provider,
            domain=args.domain,
            doi_prefix=args.doi_prefix,
            output_manifest=source.manifest,
            evidence_pack=evidence_pack,
        )
        write_text(
            output_dir / "briefs" / "discover-manifest.yml",
            to_yaml(discover_brief) + "\n",
        )
    if args.dry_run:
        return 0

    state_path = _state_path(args.state)
    state = _load_state(state_path)
    _ensure_provider_state(
        state,
        provider=source.provider,
        manifest=source.manifest,
        include_discovery=source.include_discovery,
    )
    _write_json(state_path, state)
    return 0


def run_next(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    step_id = _next_pending_step(provider_state)
    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "status": provider_state["status"],
                "current_step": step_id,
                "state": str(state_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_verify(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    if args.task not in _dag_step_ids(include_discovery=True):
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"unknown task for provider {provider}: {args.task}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-verify-{args.task}",
            details={"task": args.task},
        )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    if args.task in {ACCESS_PREFLIGHT_STEP, DISCOVER_STEP}:
        validate_access_review(provider)
    commands = _verify_commands(provider, args.task)
    verifications = provider_state.setdefault("verifications", {})
    verifications[args.task] = {
        "dry_run": True,
        "commands": commands,
        "result": "planned",
    }
    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "task": args.task,
                "dry_run": True,
                "commands": commands,
                "result": "planned",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_check_snapshot(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    doi = _normalized_doi(args.doi)
    provider_manifest = _read_manifest(_manifest_path_for_provider(provider))
    if doi not in _manifest_dois(provider_manifest):
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is not registered in provider manifest fixtures.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi},
        )
    golden_manifest = _load_golden_manifest()
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "DOI is missing from golden criteria manifest.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi, "sample_id": _doi_slug(doi)},
        )
    sample_id, sample = sample_entry
    fixture_root = _fixture_root_for_sample(sample_id, sample)
    expected_path = fixture_root / "expected.json"
    markdown_path = fixture_root / "extracted.md"
    prompt_path = fixture_root / "markdown-quality-prompt.md"
    quality_path = fixture_root / "markdown-quality.json"
    if not fixture_root.is_dir():
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "fixture directory is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "fixture_dir": fixture_root.relative_to(_repo_root()).as_posix(),
            },
        )
    if not expected_path.is_file():
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "expected snapshot file is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "expected_path": expected_path.relative_to(_repo_root()).as_posix(),
            },
        )
    if not markdown_path.is_file():
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "extracted Markdown baseline is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "baseline_markdown_path": markdown_path.relative_to(
                    _repo_root()
                ).as_posix(),
            },
        )
    if not prompt_path.is_file():
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality agent prompt is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_prompt_path": prompt_path.relative_to(
                    _repo_root()
                ).as_posix(),
            },
        )
    if not quality_path.is_file():
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report is missing.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
            },
        )
    try:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report cannot be loaded.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "reason": str(exc),
            },
        ) from exc
    validation_errors = _markdown_quality_report_errors(
        quality,
        markdown_path=markdown_path,
        prompt_path=prompt_path,
    )
    if validation_errors:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report must use the agent_prompt schema v2 contract.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "validation_errors": validation_errors,
            },
        )
    fresh = _run_fresh_markdown_quality_review(
        provider=provider,
        doi=doi,
        sample_id=sample_id,
        purpose=str(sample.get("purpose") or ""),
        markdown_path=markdown_path,
        prompt_path=prompt_path,
        task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
    )
    fresh_blocking_issues = _fresh_markdown_quality_blocking_issues(fresh.report)
    if fresh.report.get("status") != "pass" or fresh_blocking_issues:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Fresh Markdown quality review found blocking issues in extracted.md.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "baseline_markdown_path": markdown_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_status": quality.get("status")
                if isinstance(quality, dict)
                else None,
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "issues": fresh_blocking_issues,
            },
        )
    if isinstance(quality, dict) and quality.get("status") == PENDING_STATUS:
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report is pending agent review; run the prompt and write a pass/fail report.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_prompt_path": prompt_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "status": quality.get("status"),
            },
        )
    blocking_issues = blocking_markdown_quality_issues(quality)
    if (
        not isinstance(quality, dict)
        or quality.get("status") != "pass"
        or blocking_issues
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_FAILED",
            "Markdown quality report contains blocking issues.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={
                "doi": doi,
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "status": quality.get("status") if isinstance(quality, dict) else None,
                "issues": blocking_issues,
            },
        )
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    expected_assets = {
        "expected.json": expected_path,
        "extracted.md": markdown_path,
        "markdown-quality-prompt.md": prompt_path,
        "markdown-quality.json": quality_path,
    }
    missing_asset_entries = [
        name
        for name, path in expected_assets.items()
        if assets.get(name) != path.relative_to(_repo_root()).as_posix()
    ]
    if missing_asset_entries:
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            "fixture manifest assets do not register all snapshot artifacts.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi, "missing_assets": missing_asset_entries},
        )
    if sample.get("expected_outcome") == "pending":
        raise ToolError(
            "EXPECTED_OUTCOME_PENDING",
            "fixture manifest expected_outcome is still pending.",
            retryable=True,
            provider=provider,
            manifest=default_manifest_path(provider),
            task_id=f"{provider}-{SNAPSHOT_EXPECTED_STEP}",
            details={"doi": doi, "sample_id": sample_id},
        )
    print(
        json.dumps(
            {
                "provider": provider,
                "doi": doi,
                "sample_id": sample_id,
                "expected_path": expected_path.relative_to(_repo_root()).as_posix(),
                "baseline_markdown_path": markdown_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_prompt_path": prompt_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "markdown_quality_path": quality_path.relative_to(
                    _repo_root()
                ).as_posix(),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
                "fresh_markdown_quality_status": fresh.report.get("status"),
                "markdown_quality_status": quality.get("status"),
                "expected_outcome": sample.get("expected_outcome"),
                "result": "passed",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_check_cleaning_proposal(args: argparse.Namespace) -> int:
    proposal_path = Path(args.proposal) if args.proposal else None
    if proposal_path is not None and not proposal_path.is_absolute():
        proposal_path = _repo_root() / proposal_path
    print(
        json.dumps(
            check_cleaning_proposal_freshness(
                args.provider, proposal_path=proposal_path
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_run_checks(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    if bool(args.task) == bool(args.all_local):
        raise ToolError(
            "TASK_BRIEF_INVALID",
            "run-checks requires exactly one of --task or --all-local.",
            retryable=True,
            provider=provider,
            task_id=f"{provider}-run-checks",
            details={"task": args.task, "all_local": args.all_local},
        )
    all_step_ids = _dag_step_ids(include_discovery=True)
    if args.task and args.task not in all_step_ids:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"unknown task for provider {provider}: {args.task}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-run-checks-{args.task}",
            details={"task": args.task},
        )

    tasks = (
        [
            ACCESS_PREFLIGHT_STEP,
            "validate-manifest",
            "provider-local-acceptance",
            SHARED_INTEGRATION_STEP,
            "global-lint",
        ]
        if args.all_local
        else [args.task]
    )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    completed_tasks: list[str] = []

    for task in tasks:
        commands = _verify_commands(provider, task, include_live=not args.all_local)
        if task in {ACCESS_PREFLIGHT_STEP, DISCOVER_STEP}:
            try:
                validate_access_review(provider)
            except ToolError as exc:
                _record_run(
                    provider_state,
                    task=task,
                    commands=commands,
                    result="failed",
                    failure=_failure_from_tool_error(exc, commands=commands),
                )
                _write_json(state_path, state)
                raise
        for command in commands:
            completed = _run_env_command(command)
            if _command_failed(command, completed):
                failure_code = _failure_code_for_task(task, command)
                structured = _payload_from_stderr(completed.stderr)
                if structured and isinstance(structured.get("code"), str):
                    failure_code = str(structured["code"])
                failure = {
                    "code": failure_code,
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                }
                if structured:
                    failure["structured_error"] = structured
                if _is_cleaning_contract_command(command):
                    contract_payload = _payload_from_stdout_yaml(completed.stdout)
                    if contract_payload is not None:
                        failure["contract_check"] = contract_payload
                _record_run(
                    provider_state,
                    task=task,
                    commands=commands,
                    result="failed",
                    failure=failure,
                )
                _write_json(state_path, state)
                raise ToolError(
                    failure_code,
                    f"onboarding local check failed for task {task}.",
                    retryable=bool(structured.get("retryable")) if structured else True,
                    provider=provider,
                    manifest=default_manifest_path(provider),
                    task_id=f"{provider}-run-checks-{task}",
                    details=failure,
                )
        _record_run(provider_state, task=task, commands=commands, result="passed")
        completed_tasks.append(task)

    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "tasks": completed_tasks,
                "result": "passed",
                "state": str(state_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _record_markdown_quality_repair(
    provider_state: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    repairs = provider_state.setdefault("repairs", {})
    if not isinstance(repairs, dict):
        repairs = {}
        provider_state["repairs"] = repairs
    markdown_repairs = repairs.setdefault("markdown_quality", [])
    if not isinstance(markdown_repairs, list):
        markdown_repairs = []
        repairs["markdown_quality"] = markdown_repairs
    markdown_repairs.append(entry)


def _run_agent_with_scope(
    *,
    argv: list[str],
    prompt: str,
    attempt_dir: Path,
    prefix: str,
    allowed_scope: list[str],
) -> tuple[subprocess.CompletedProcess[str], set[str], set[str]]:
    write_text(attempt_dir / f"{prefix}.prompt.md", prompt)
    before = _workspace_changed_paths()
    completed = subprocess.run(
        argv,
        cwd=_repo_root(),
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    after = _workspace_changed_paths()
    write_text(attempt_dir / f"{prefix}.stdout.log", completed.stdout)
    write_text(attempt_dir / f"{prefix}.stderr.log", completed.stderr)
    write_text(
        attempt_dir / f"{prefix}.changed-before.json",
        json.dumps(sorted(before), indent=2, sort_keys=True) + "\n",
    )
    write_text(
        attempt_dir / f"{prefix}.changed-after.json",
        json.dumps(sorted(after), indent=2, sort_keys=True) + "\n",
    )
    disallowed = _disallowed_changes(before, after, allowed_scope)
    if disallowed:
        write_text(
            attempt_dir / f"{prefix}.forbidden-paths.json",
            json.dumps(disallowed, indent=2, sort_keys=True) + "\n",
        )
    return completed, before, after


def _run_repair_command(
    command: list[str],
    *,
    attempt_dir: Path,
    index: int,
) -> tuple[bool, dict[str, Any]]:
    completed = _run_env_command(command)
    command_dir = attempt_dir / "commands"
    command_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{index:02d}"
    write_text(command_dir / f"{stem}.command.txt", _markdown_command(command) + "\n")
    write_text(command_dir / f"{stem}.stdout.log", completed.stdout)
    write_text(command_dir / f"{stem}.stderr.log", completed.stderr)
    failed = _command_failed(command, completed)
    details = {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }
    structured = _payload_from_stderr(completed.stderr)
    if structured:
        details["structured_error"] = structured
    return not failed, details


def _load_quality_after_review(
    ctx: MarkdownQualityRepairContext,
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        quality = json.loads(ctx.quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"Markdown quality report cannot be loaded: {exc}"]
    errors = validate_markdown_quality_report(quality)
    if isinstance(quality, dict):
        if quality.get("markdown_path") != _rel(ctx.markdown_path):
            errors.append("markdown_path must point to extracted.md")
        if quality.get("prompt_path") != _rel(ctx.prompt_path):
            errors.append("prompt_path must point to markdown-quality-prompt.md")
    else:
        errors.append("markdown quality report root must be an object")
        quality = None
    return quality, errors


def _load_fresh_markdown_repair_context(
    provider: str,
    doi: str,
    *,
    output_dir: Path,
) -> MarkdownQualityRepairContext:
    base_ctx = _load_markdown_repair_context(
        provider,
        doi,
        allow_passing_report=True,
        allow_pending_report=True,
    )
    fresh = _run_fresh_markdown_quality_review(
        provider=base_ctx.provider,
        doi=base_ctx.doi,
        sample_id=base_ctx.sample_id,
        purpose=base_ctx.purpose,
        markdown_path=base_ctx.markdown_path,
        prompt_path=base_ctx.prompt_path,
        output_dir=output_dir / "fresh-review",
        task_id=f"{base_ctx.provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
    )
    effective = _effective_markdown_repair_report(
        persistent_report=base_ctx.persistent_quality_report,
        fresh_report=fresh.report,
    )
    if effective.get("status") == "pass" and not blocking_markdown_quality_issues(
        effective
    ):
        raise ToolError(
            "MARKDOWN_QUALITY_REPAIR_NOT_REQUIRED",
            "Fresh Markdown quality review and persistent report are already passing.",
            retryable=False,
            provider=base_ctx.provider,
            manifest=default_manifest_path(base_ctx.provider),
            task_id=f"{base_ctx.provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
            details={
                "doi": base_ctx.doi,
                "markdown_quality_path": _rel(base_ctx.quality_path),
                "fresh_markdown_quality_path": _rel(fresh.report_path),
            },
        )
    return base_ctx._replace(
        quality_report=effective,
        fresh_quality_path=fresh.report_path,
    )


def _update_review_artifact_hashes(ctx: MarkdownQualityRepairContext) -> bool:
    if not ctx.review_path.is_file():
        return False
    try:
        review = yaml.safe_load(ctx.review_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return False
    if not isinstance(review, dict):
        return False
    fixtures = review.get("fixtures")
    if not isinstance(fixtures, list):
        return False
    quality_rel = _rel(ctx.quality_path)
    markdown_rel = _rel(ctx.markdown_path)
    changed = False
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        fixture_doi = _normalized_doi(str(fixture.get("doi") or ""))
        matches_doi = fixture_doi == ctx.doi
        matches_quality = fixture.get("markdown_quality_path") == quality_rel
        matches_markdown = fixture.get("baseline_markdown_path") == markdown_rel
        if not (matches_doi or matches_quality or matches_markdown):
            continue
        fixture["markdown_quality_sha256"] = _sha256_file(ctx.quality_path)
        if ctx.markdown_path.is_file():
            fixture["baseline_markdown_sha256"] = _sha256_file(ctx.markdown_path)
        changed = True
    if changed:
        write_text(
            ctx.review_path,
            yaml.safe_dump(review, sort_keys=False, allow_unicode=True),
        )
    return changed


def run_repair_markdown_quality(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    doi = _normalized_doi(args.doi)
    max_attempts = int(args.max_attempts)
    if max_attempts < 1:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            "--max-attempts must be at least 1.",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
            details={"max_attempts": max_attempts},
        )
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    output_dir = Path(
        args.output_dir or f".paper-fetch-runs/{provider}-markdown-repair"
    )
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    repair_dir = output_dir / "markdown-quality" / _doi_slug(doi)
    ctx = _load_markdown_repair_context(
        provider,
        doi,
        allow_passing_report=True,
        allow_pending_report=True,
    )
    dispatcher = _worker_dispatcher(
        provider=provider,
        task=REPAIR_MARKDOWN_QUALITY_STEP,
        manifest=_rel(ctx.manifest_path),
    )
    state["agent_cli"] = dispatcher.agent_cli
    argv = dispatcher.argv
    initial_issue_ids: list[str] = []
    changed_paths: set[str] = set()
    executed_commands: list[list[str]] = []
    command_details: list[dict[str, Any]] = []
    last_failure: dict[str, Any] | None = None
    attempts_run = 0
    quality_status = ctx.quality_report.get("status")

    for attempt in range(1, max_attempts + 1):
        attempts_run = attempt
        ctx = _load_fresh_markdown_repair_context(provider, doi, output_dir=repair_dir)
        issues = _markdown_repair_issues(ctx.quality_report)
        if not initial_issue_ids:
            initial_issue_ids = [
                str(issue.get("id"))
                for issue in issues
                if isinstance(issue.get("id"), str) and issue.get("id")
            ]
        domains = _infer_markdown_repair_domains(issues)
        allowed_scope = _markdown_repair_allowed_scope(ctx, domains)
        attempt_dir = repair_dir / f"attempt-{attempt}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        brief = _markdown_repair_brief(
            ctx,
            attempt=attempt,
            max_attempts=max_attempts,
            domains=domains,
            allowed_scope=allowed_scope,
        )
        write_text(attempt_dir / "repair-brief.yml", to_yaml(brief) + "\n")
        worker_prompt = _markdown_repair_worker_prompt(ctx, brief)
        completed, before, after = _run_agent_with_scope(
            argv=argv,
            prompt=worker_prompt,
            attempt_dir=attempt_dir,
            prefix="repair-agent",
            allowed_scope=allowed_scope,
        )
        changed_paths.update(after - before)
        disallowed = _disallowed_changes(before, after, allowed_scope)
        if disallowed:
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "forbidden_paths": disallowed,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            entry = {
                "provider": provider,
                "doi": doi,
                "sample_id": ctx.sample_id,
                "attempts": attempts_run,
                "status": "failed",
                "issue_ids": initial_issue_ids,
                "changed_paths": sorted(changed_paths),
                "commands": executed_commands,
                "command_results": command_details,
                "quality_status": quality_status,
                "run_dir": _rel(repair_dir),
                "failure": last_failure,
            }
            _record_markdown_quality_repair(provider_state, entry)
            _write_json(state_path, state)
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "repair worker modified files outside the inferred allowed scope.",
                retryable=True,
                provider=provider,
                manifest=_rel(ctx.manifest_path),
                task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
                details=last_failure,
            )
        if completed.returncode != 0:
            last_failure = {
                "code": "WORKER_AGENT_FAILED",
                "attempt": attempt,
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
            continue

        commands = _markdown_repair_commands(ctx)
        pre_review_commands = commands[:2]
        post_review_command = commands[2]
        command_failed = False
        for index, command in enumerate(pre_review_commands, start=1):
            ok, details = _run_repair_command(
                command, attempt_dir=attempt_dir, index=index
            )
            executed_commands.append(command)
            command_details.append(details)
            if not ok:
                command_failed = True
                last_failure = {
                    "code": "LOCAL_CHECK_FAILED",
                    "attempt": attempt,
                    **details,
                }
                break
        if command_failed:
            continue

        review_prompt = _markdown_quality_review_prompt(ctx)
        review_completed, review_before, review_after = _run_agent_with_scope(
            argv=argv,
            prompt=review_prompt,
            attempt_dir=attempt_dir,
            prefix="quality-review-agent",
            allowed_scope=[_rel(ctx.quality_path)],
        )
        changed_paths.update(review_after - review_before)
        review_disallowed = _disallowed_changes(
            review_before, review_after, [_rel(ctx.quality_path)]
        )
        if review_disallowed:
            last_failure = {
                "code": "WORKER_MODIFIED_FORBIDDEN_FILE",
                "attempt": attempt,
                "forbidden_paths": review_disallowed,
                "stdout_tail": _tail(review_completed.stdout),
                "stderr_tail": _tail(review_completed.stderr),
            }
            entry = {
                "provider": provider,
                "doi": doi,
                "sample_id": ctx.sample_id,
                "attempts": attempts_run,
                "status": "failed",
                "issue_ids": initial_issue_ids,
                "changed_paths": sorted(changed_paths),
                "commands": executed_commands,
                "command_results": command_details,
                "quality_status": quality_status,
                "run_dir": _rel(repair_dir),
                "failure": last_failure,
            }
            _record_markdown_quality_repair(provider_state, entry)
            _write_json(state_path, state)
            raise ToolError(
                "WORKER_MODIFIED_FORBIDDEN_FILE",
                "quality review worker modified files outside markdown-quality.json.",
                retryable=True,
                provider=provider,
                manifest=_rel(ctx.manifest_path),
                task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
                details=last_failure,
            )
        if review_completed.returncode != 0:
            last_failure = {
                "code": "WORKER_AGENT_FAILED",
                "attempt": attempt,
                "returncode": review_completed.returncode,
                "stdout_tail": _tail(review_completed.stdout),
                "stderr_tail": _tail(review_completed.stderr),
            }
            continue

        ok, details = _run_repair_command(
            post_review_command, attempt_dir=attempt_dir, index=3
        )
        executed_commands.append(post_review_command)
        command_details.append(details)
        quality, quality_errors = _load_quality_after_review(ctx)
        quality_status = (
            quality.get("status") if isinstance(quality, dict) else "invalid"
        )
        write_text(
            attempt_dir / "quality-status.json",
            json.dumps(
                {
                    "status": quality_status,
                    "errors": quality_errors,
                    "blocking_issues": blocking_markdown_quality_issues(quality)
                    if isinstance(quality, dict)
                    else [],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        if (
            ok
            and isinstance(quality, dict)
            and not quality_errors
            and quality.get("status") == "pass"
            and not blocking_markdown_quality_issues(quality)
        ):
            review_updated = _update_review_artifact_hashes(ctx)
            if review_updated:
                changed_paths.add(_rel(ctx.review_path))
            entry = {
                "provider": provider,
                "doi": doi,
                "sample_id": ctx.sample_id,
                "attempts": attempts_run,
                "status": "passed",
                "issue_ids": initial_issue_ids,
                "changed_paths": sorted(changed_paths),
                "commands": executed_commands,
                "command_results": command_details,
                "quality_status": quality_status,
                "run_dir": _rel(repair_dir),
                "review_artifact_updated": review_updated,
            }
            _record_markdown_quality_repair(provider_state, entry)
            _write_json(state_path, state)
            print(
                json.dumps(
                    {**entry, "state": str(state_path)}, indent=2, sort_keys=True
                )
            )
            return 0
        last_failure = {
            "code": "MARKDOWN_QUALITY_FAILED",
            "attempt": attempt,
            "quality_status": quality_status,
            "quality_errors": quality_errors,
            "check_snapshot": details,
        }

    entry = {
        "provider": provider,
        "doi": doi,
        "sample_id": ctx.sample_id,
        "attempts": attempts_run,
        "status": "failed",
        "issue_ids": initial_issue_ids,
        "changed_paths": sorted(changed_paths),
        "commands": executed_commands,
        "command_results": command_details,
        "quality_status": quality_status,
        "run_dir": _rel(repair_dir),
        "failure": last_failure or {"code": "MARKDOWN_QUALITY_REPAIR_FAILED"},
    }
    _record_markdown_quality_repair(provider_state, entry)
    _write_json(state_path, state)
    raise ToolError(
        "MARKDOWN_QUALITY_REPAIR_FAILED",
        f"Markdown quality repair did not pass after {max_attempts} attempts.",
        retryable=False,
        provider=provider,
        manifest=_rel(ctx.manifest_path),
        task_id=f"{provider}-{REPAIR_MARKDOWN_QUALITY_STEP}",
        details=entry,
    )


def _fixture_path_for_doi(doi: str) -> str | None:
    try:
        golden_manifest = _load_golden_manifest()
    except ToolError:
        return None
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        return None
    sample_id, sample = sample_entry
    return (
        _fixture_root_for_sample(sample_id, sample).relative_to(_repo_root()).as_posix()
    )


def _fixture_asset_paths_for_doi(doi: str) -> dict[str, Any]:
    try:
        golden_manifest = _load_golden_manifest()
    except ToolError:
        return {}
    sample_entry = _golden_sample_for_doi(doi, golden_manifest)
    if sample_entry is None:
        return {}
    _sample_id, sample = sample_entry
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    raw_path = None
    for name in (
        "original.xml",
        "original.pdf",
        "original.html",
        "raw.html",
        "article.html",
    ):
        value = assets.get(name)
        if isinstance(value, str) and value:
            raw_path = value
            break
    quality_path_value = assets.get("markdown-quality.json")
    quality_status = None
    if isinstance(quality_path_value, str) and quality_path_value:
        quality_path = _repo_root() / quality_path_value
        if quality_path.is_file():
            try:
                quality = json.loads(quality_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                quality_status = "invalid"
            else:
                quality_status = (
                    quality.get("status") if isinstance(quality, dict) else "invalid"
                )
        else:
            quality_status = "missing"
    return {
        "raw_path": raw_path,
        "extracted_markdown_path": assets.get("extracted.md"),
        "markdown_quality_path": quality_path_value,
        "markdown_quality_status": quality_status,
        "expected_json_path": assets.get("expected.json"),
        "expected_outcome": sample.get("expected_outcome"),
        "route_kind": sample.get("route_kind"),
        "content_type": sample.get("content_type"),
    }


def _discovery_proof_summary(
    manifest_fixtures: dict[str, Any],
    purpose: str,
    doi: str | None,
) -> dict[str, Any] | None:
    proof_map = (
        manifest_fixtures.get("discovery_proof")
        if isinstance(manifest_fixtures.get("discovery_proof"), dict)
        else {}
    )
    proof = proof_map.get(purpose)
    if not isinstance(proof, dict):
        return None
    queries = proof.get("queries") if isinstance(proof.get("queries"), list) else []
    candidates = (
        proof.get("candidates") if isinstance(proof.get("candidates"), list) else []
    )
    rejections = (
        proof.get("rejections") if isinstance(proof.get("rejections"), dict) else {}
    )
    selected_doi = proof.get("selected_doi")
    evidence_summary = normalize_text(str(proof.get("evidence_summary") or ""))
    exhausted = proof.get("exhausted")
    complete = (
        bool(evidence_summary)
        and len(queries) >= 3
        and len(candidates) >= 3
        and (selected_doi == doi if doi else exhausted is True)
        and (not doi or selected_doi in candidates)
        and bool(rejections)
    )
    return {
        "status": "complete" if complete else "needs_review",
        "queries_count": len(queries),
        "candidates": candidates,
        "selected_doi": selected_doi,
        "rejection_count": len(rejections),
        "exhausted": exhausted,
        "evidence_summary": evidence_summary or None,
    }


def _manifest_fixture_summary(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    manifest_fixtures = (
        manifest.get("fixtures") if isinstance(manifest.get("fixtures"), dict) else {}
    )
    doi_samples = (
        manifest_fixtures.get("doi_samples")
        if isinstance(manifest_fixtures.get("doi_samples"), dict)
        else {}
    )
    for purpose, sample in doi_samples.items():
        if not isinstance(sample, dict):
            continue
        doi = sample.get("doi")
        asset_paths = _fixture_asset_paths_for_doi(str(doi)) if doi else {}
        proof_summary = _discovery_proof_summary(
            manifest_fixtures,
            str(purpose),
            str(doi) if doi else None,
        )
        item = {
            "purpose": purpose,
            "doi": doi,
            "confidence": sample.get("confidence"),
            "observed_signals": sample.get("observed_signals") or [],
            "evidence_url": sample.get("evidence_url"),
            "evidence_reason": sample.get("evidence_reason"),
            "fixture_path": _fixture_path_for_doi(str(doi)) if doi else None,
            "raw_path": asset_paths.get("raw_path"),
            "extracted_markdown_path": asset_paths.get("extracted_markdown_path"),
            "markdown_quality_path": asset_paths.get("markdown_quality_path"),
            "markdown_quality_status": asset_paths.get("markdown_quality_status"),
            "expected_json_path": asset_paths.get("expected_json_path"),
            "expected_outcome": asset_paths.get("expected_outcome"),
            "route_kind": asset_paths.get("route_kind"),
            "content_type": asset_paths.get("content_type"),
            "proof_status": (
                proof_summary["status"]
                if proof_summary is not None
                else "fixture_captured"
                if doi and asset_paths.get("raw_path")
                else "human_review_required"
            ),
            "discovery_proof": proof_summary,
            "null_reason": None if doi else sample.get("evidence_reason"),
        }
        fixtures.append(item)
    extra_fixtures = manifest.get("extra_fixtures")
    if isinstance(extra_fixtures, list):
        for index, sample in enumerate(extra_fixtures):
            if not isinstance(sample, dict):
                continue
            doi = sample.get("doi")
            asset_paths = _fixture_asset_paths_for_doi(str(doi)) if doi else {}
            fixtures.append(
                {
                    "purpose": sample.get("purpose") or f"extra_fixtures[{index}]",
                    "doi": doi,
                    "confidence": sample.get("confidence"),
                    "observed_signals": sample.get("observed_signals") or [],
                    "evidence_url": sample.get("evidence_url"),
                    "evidence_reason": sample.get("evidence_reason"),
                    "fixture_path": _fixture_path_for_doi(str(doi)) if doi else None,
                    "raw_path": asset_paths.get("raw_path"),
                    "extracted_markdown_path": asset_paths.get(
                        "extracted_markdown_path"
                    ),
                    "markdown_quality_path": asset_paths.get("markdown_quality_path"),
                    "markdown_quality_status": asset_paths.get(
                        "markdown_quality_status"
                    ),
                    "expected_json_path": asset_paths.get("expected_json_path"),
                    "expected_outcome": asset_paths.get("expected_outcome"),
                    "route_kind": asset_paths.get("route_kind"),
                    "content_type": asset_paths.get("content_type"),
                    "proof_status": (
                        "extra_fixture_captured"
                        if doi and asset_paths.get("raw_path")
                        else "human_review_required"
                    ),
                    "discovery_proof": None,
                    "null_reason": None if doi else sample.get("evidence_reason"),
                }
            )
    return fixtures


def _review_artifact_summary(provider: str) -> dict[str, Any]:
    path = _repo_root() / "onboarding" / "reviews" / f"{provider}.yml"
    if not path.exists():
        return {
            "status": "missing",
            "path": path.relative_to(_repo_root()).as_posix(),
            "fixtures": [],
        }
    try:
        review = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {
            "status": "invalid_yaml",
            "path": path.relative_to(_repo_root()).as_posix(),
            "error": str(exc),
            "fixtures": [],
        }
    fixtures = review.get("fixtures") if isinstance(review, dict) else None
    summaries: list[dict[str, Any]] = []
    if isinstance(fixtures, list):
        for fixture in fixtures:
            if not isinstance(fixture, dict):
                continue
            fixes = (
                fixture.get("fixes") if isinstance(fixture.get("fixes"), list) else []
            )
            issues = (
                fixture.get("issues") if isinstance(fixture.get("issues"), list) else []
            )
            quality_status = None
            quality_path_value = fixture.get("markdown_quality_path")
            if isinstance(quality_path_value, str) and quality_path_value:
                quality_path = _repo_root() / quality_path_value
                if quality_path.is_file():
                    try:
                        quality = json.loads(quality_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        quality_status = "invalid"
                    else:
                        quality_status = (
                            quality.get("status")
                            if isinstance(quality, dict)
                            else "invalid"
                        )
                else:
                    quality_status = "missing"
            summaries.append(
                {
                    "fixture": fixture.get("fixture"),
                    "purpose": fixture.get("purpose"),
                    "doi": fixture.get("doi"),
                    "issue_ids": [
                        issue.get("id")
                        for issue in issues
                        if isinstance(issue, dict) and issue.get("id")
                    ],
                    "fix_ids": [
                        fix.get("id")
                        for fix in fixes
                        if isinstance(fix, dict) and fix.get("id")
                    ],
                    "test_names": sorted(
                        {
                            str(test_name)
                            for fix in fixes
                            if isinstance(fix, dict)
                            for test_name in (fix.get("test_names") or [])
                        }
                    ),
                    "markdown_semantic_reviewed": fixture.get(
                        "markdown_semantic_reviewed"
                    ),
                    "markdown_quality_status": quality_status,
                }
            )
    reviewed_values = [
        item.get("markdown_semantic_reviewed")
        for item in summaries
        if "markdown_semantic_reviewed" in item
    ]
    quality_values = [
        item.get("markdown_quality_status")
        for item in summaries
        if item.get("markdown_quality_status") is not None
    ]
    return {
        "status": "present",
        "path": path.relative_to(_repo_root()).as_posix(),
        "semantic_review_status": (
            "complete"
            if reviewed_values and all(value is True for value in reviewed_values)
            else "pending"
        ),
        "markdown_quality_status": (
            "pass"
            if quality_values and all(value == "pass" for value in quality_values)
            else "pending"
            if not quality_values
            or any(value == PENDING_STATUS for value in quality_values)
            else "fail"
        ),
        "fixtures": summaries,
    }


def build_provider_summary(
    *,
    provider: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    provider_state = (
        providers.get(provider_name) if isinstance(providers, dict) else None
    )
    if not isinstance(provider_state, dict):
        provider_state = {
            "provider": provider_name,
            "manifest": default_manifest_path(provider_name),
            "status": "not_started",
            "current_step": None,
        }
    manifest_path = _repo_root() / str(
        provider_state.get("manifest") or default_manifest_path(provider_name)
    )
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = _read_manifest(manifest_path)
    runs = (
        provider_state.get("runs")
        if isinstance(provider_state.get("runs"), dict)
        else {}
    )
    verifications = (
        provider_state.get("verifications")
        if isinstance(provider_state.get("verifications"), dict)
        else {}
    )
    repairs = (
        provider_state.get("repairs")
        if isinstance(provider_state.get("repairs"), dict)
        else {}
    )
    markdown_quality_repairs = (
        repairs.get("markdown_quality")
        if isinstance(repairs.get("markdown_quality"), list)
        else []
    )
    diagnosis = diagnose_provider_state(provider_state)
    summary: dict[str, Any] = {
        "provider": provider_name,
        "status": provider_state.get("status"),
        "current_step": provider_state.get("current_step"),
        "failed_task": diagnosis["failure"].get("task"),
        "failure_code": diagnosis["failure"].get("code"),
        "failure_recovery_action": diagnosis["failure"].get("action"),
        "access_review": diagnosis["access_review"],
        "manifest": {
            "path": manifest_path.relative_to(_repo_root()).as_posix(),
            "main_path": manifest.get("main_path"),
            "route_sources": manifest.get("route_sources"),
            "display_source": manifest.get("display_source"),
        },
        "fixture_coverage": _manifest_fixture_summary(manifest) if manifest else [],
        "review_artifact": _review_artifact_summary(provider_name),
        "markdown_quality_repairs": [
            repair for repair in markdown_quality_repairs if isinstance(repair, dict)
        ][-5:],
        "run_checks": [
            {
                "task": task,
                "result": run.get("result"),
                "commands": run.get("commands"),
                "failure_code": (
                    run.get("failure", {}).get("code")
                    if isinstance(run.get("failure"), dict)
                    else None
                ),
            }
            for task, run in runs.items()
            if isinstance(run, dict)
        ],
        "verification_plans": [
            {
                "task": task,
                "result": plan.get("result"),
                "commands": plan.get("commands"),
            }
            for task, plan in verifications.items()
            if isinstance(plan, dict)
        ],
        "operator_action": None,
        "merge_ready_pr_draft": None,
    }
    if provider_state.get("status") == "blocked":
        plan = plan_resume_blocked(provider_state)
        summary["operator_action"] = (
            diagnosis["failure"].get("action")
            or "; ".join(plan["blockers"])
            or "inspect blocked provider state"
        )
    if provider_state.get("status") == "merge_ready":
        summary["merge_ready_pr_draft"] = (
            f"Add {provider_name} provider onboarding artifacts and local verification summary."
        )
    return summary


def normalize_agent_target(target: str | None) -> str:
    normalized = str(target or "local-ready").strip().lower().replace("_", "-")
    if normalized not in AGENT_TARGET_STEPS:
        raise ValueError(
            "target must be one of: " + ", ".join(sorted(AGENT_TARGET_STEPS))
        )
    return normalized


def agent_target_step(target: str | None) -> str:
    return AGENT_TARGET_STEPS[normalize_agent_target(target)]


def _provider_state_for_agent_summary(
    provider: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    provider_state = (
        providers.get(provider_name) if isinstance(providers, dict) else None
    )
    if isinstance(provider_state, dict):
        return provider_state
    return {
        "provider": provider_name,
        "manifest": default_manifest_path(provider_name),
        "status": "not_started",
        "current_step": None,
        "steps": list(_dag_step_ids(include_discovery=True)),
        "completed_steps": [],
        "task_statuses": {},
        "retry_counts": {},
        "verifications": {},
    }


def _step_completed(provider_state: dict[str, Any], step: str) -> bool:
    task_statuses = (
        provider_state.get("task_statuses")
        if isinstance(provider_state.get("task_statuses"), dict)
        else {}
    )
    completed_steps = (
        provider_state.get("completed_steps")
        if isinstance(provider_state.get("completed_steps"), list)
        else []
    )
    return task_statuses.get(step) == "completed" or step in completed_steps


def _agent_target_complete(provider_state: dict[str, Any], target: str) -> bool:
    target_name = normalize_agent_target(target)
    if target_name == "local-ready":
        return provider_state.get("status") != "blocked" and _step_completed(
            provider_state, AGENT_TARGET_STEPS[target_name]
        )
    return provider_state.get("status") == "merge_ready" or _step_completed(
        provider_state,
        AGENT_TARGET_STEPS[target_name],
    )


def _semantic_review_gate_pending(
    summary: dict[str, Any],
    provider_state: dict[str, Any],
    target: str,
) -> bool:
    if normalize_agent_target(target) != "merge-ready":
        return False
    review = summary.get("review_artifact")
    if not isinstance(review, dict) or review.get("status") != "present":
        return False
    if review.get("semantic_review_status") == "complete":
        return False
    return any(
        _step_completed(provider_state, step)
        for step in (
            SNAPSHOT_EXPECTED_STEP,
            "manifest-sync-back",
            "provider-local-acceptance",
            "global-lint",
        )
    )


def _agent_failure_action(summary: dict[str, Any]) -> str | None:
    code = summary.get("failure_code")
    if isinstance(code, str) and code in AGENT_FAILURE_USER_ACTIONS:
        return AGENT_FAILURE_USER_ACTIONS[code]
    action = summary.get("failure_recovery_action")
    return str(action) if action else None


def _agent_phase(
    summary: dict[str, Any],
    provider_state: dict[str, Any],
    target: str,
) -> str:
    status = summary.get("status")
    failure_code = summary.get("failure_code")
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    if status == "merge_ready":
        return "merge-ready"
    if _agent_target_complete(provider_state, target):
        return normalize_agent_target(target)
    if _semantic_review_gate_pending(summary, provider_state, target):
        return "user-gate"
    if status == "not_started":
        return (
            "user-gate" if access.get("status") not in {None, "missing"} else "intake"
        )
    if status == "blocked":
        if failure_code in OPERATOR_REQUIRED_FAILURE_CODES or not access.get(
            "approved"
        ):
            return "user-gate"
        return "blocked"
    if not access.get("approved") and access.get("status") not in {None, "missing"}:
        return "user-gate"
    if summary.get("current_step") == ACCESS_PREFLIGHT_STEP:
        return "preflight"
    return "running"


def _agent_completed_items(
    summary: dict[str, Any],
    provider_state: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    if access.get("approved"):
        items.append("access review 已批准")
    manifest = (
        summary.get("manifest") if isinstance(summary.get("manifest"), dict) else {}
    )
    manifest_path = manifest.get("path")
    if isinstance(manifest_path, str) and (_repo_root() / manifest_path).exists():
        items.append("manifest 已生成")
    if any(
        item.get("raw_path")
        for item in summary.get("fixture_coverage", [])
        if isinstance(item, dict)
    ):
        items.append("至少一个 fixture 已捕获")
    if _step_completed(provider_state, "scaffold"):
        items.append("provider-owned skeleton 已生成")
    if _step_completed(provider_state, "provider-local-acceptance"):
        items.append("最小 provider-local 验证通过")
    if provider_state.get("status") == "merge_ready":
        items.append("merge-ready 本地 gate 已完成")
    return items


def _compact_agent_samples(summary: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for item in summary.get("fixture_coverage", []):
        if not isinstance(item, dict):
            continue
        samples.append(
            {
                "purpose": item.get("purpose"),
                "doi": item.get("doi"),
                "confidence": item.get("confidence"),
                "proof_status": item.get("proof_status"),
                "evidence": item.get("evidence_reason") or item.get("null_reason"),
                "fixture_path": item.get("fixture_path"),
                "extracted_markdown_path": item.get("extracted_markdown_path"),
                "markdown_quality_status": item.get("markdown_quality_status"),
            }
        )
    return samples


def _markdown_review_user_summary(summary: dict[str, Any]) -> dict[str, Any]:
    review = summary.get("review_artifact")
    if not isinstance(review, dict):
        return {"status": "missing", "fixtures": []}
    return {
        "status": review.get("status"),
        "path": review.get("path"),
        "semantic_review_status": review.get("semantic_review_status"),
        "markdown_quality_status": review.get("markdown_quality_status"),
        "fixtures": review.get("fixtures")
        if isinstance(review.get("fixtures"), list)
        else [],
    }


def _agent_related_files(
    provider: str,
    summary: dict[str, Any],
    state_path: Path,
) -> list[str]:
    provider_name = _provider_slug(provider)
    files: list[str] = []
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    for value in (
        access.get("path"),
        summary.get("manifest", {}).get("path")
        if isinstance(summary.get("manifest"), dict)
        else None,
        summary.get("review_artifact", {}).get("path")
        if isinstance(summary.get("review_artifact"), dict)
        else None,
        str(state_path),
        f".paper-fetch-runs/{provider_name}-onboarding/",
    ):
        if isinstance(value, str) and value and value not in files:
            files.append(value)
    for sample in _compact_agent_samples(summary):
        for key in ("extracted_markdown_path", "fixture_path"):
            value = sample.get(key)
            if isinstance(value, str) and value and value not in files:
                files.append(value)
                break
        if len(files) >= 8:
            break
    return files


def build_agent_user_summary(
    *,
    provider: str,
    state: dict[str, Any],
    target: str | None = None,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    provider_name = _provider_slug(provider)
    target_name = normalize_agent_target(target)
    state_ref = _state_path(str(state_path))
    provider_state = _provider_state_for_agent_summary(provider_name, state)
    summary = build_provider_summary(provider=provider_name, state=state)
    phase = _agent_phase(summary, provider_state, target_name)
    access = (
        summary.get("access_review")
        if isinstance(summary.get("access_review"), dict)
        else {}
    )
    failure_action = _agent_failure_action(summary)
    review = _markdown_review_user_summary(summary)
    if phase == "local-ready":
        why_stopped = (
            "已达到默认目标 local-ready：主路径本地可用，最小 provider-local 验证通过。"
        )
        next_action = (
            f"如需完整合入标准，请告诉我：继续 {provider_name} provider 到 merge-ready"
        )
    elif phase == "merge-ready":
        why_stopped = "已达到 merge-ready：完整本地 acceptance 和人工语义签字均已完成。"
        next_action = "未发现必需的下一步。"
    elif phase == "user-gate" and not access.get("approved"):
        why_stopped = "access review 还没有人工批准，agent 不能替你批准合法访问策略。"
        next_action = (
            f"打开 {access.get('path') or default_access_review_path(provider_name)}，"
            f"确认 allowed_runtimes、challenge_policy、status、may_continue；确认后对我说：继续 {provider_name} provider"
        )
    elif phase == "user-gate" and review.get("semantic_review_status") != "complete":
        why_stopped = (
            "Markdown semantic review 需要人工基于当前 extracted.md 和质量报告签字。"
        )
        next_action = (
            "阅读 extracted.md、markdown-quality.json 和 "
            f"{review.get('path') or f'onboarding/reviews/{provider_name}.yml'}；"
            f"确认后对我说：继续 {provider_name} provider 到 merge-ready"
        )
    elif phase in {"blocked", "user-gate"}:
        why_stopped = failure_action or "runner 停在需要诊断的 blocked state。"
        next_action = (
            failure_action
            or f"查看相关 artifact 后对我说：诊断 {provider_name} provider 为什么卡住"
        )
    elif phase == "intake":
        why_stopped = "还没有足够的 provider 启动信息。"
        next_action = (
            f"请提供 domain，例如：添加 {provider_name} provider，domain 是 example.org"
        )
    else:
        why_stopped = "没有停在人工 gate；项目 runner 可以继续推进。"
        next_action = f"继续运行项目 runner 到下一个人工 gate 或 {target_name}"
    return {
        "provider": provider_name,
        "target": target_name,
        "target_step": agent_target_step(target_name),
        "phase": phase,
        "status": summary.get("status"),
        "current_step": summary.get("current_step"),
        "failed_task": summary.get("failed_task"),
        "failure_code": summary.get("failure_code"),
        "why_stopped": why_stopped,
        "completed": _agent_completed_items(summary, provider_state),
        "next_user_action": next_action,
        "related_files": _agent_related_files(provider_name, summary, state_ref),
        "samples": _compact_agent_samples(summary),
        "markdown_review": review,
        "operator_action": summary.get("operator_action"),
    }


def render_agent_user_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "当前状态:",
        f"- provider: {payload.get('provider')}",
        f"- 目标: {payload.get('target')}",
        f"- 阶段: {payload.get('phase')}",
    ]
    if payload.get("current_step"):
        lines.append(f"- 当前 task: {payload.get('current_step')}")
    if payload.get("failure_code"):
        lines.append(f"- failure code: {payload.get('failure_code')}")
    lines.extend(["", "为什么停:", f"- {payload.get('why_stopped')}"])
    completed = (
        payload.get("completed") if isinstance(payload.get("completed"), list) else []
    )
    lines.extend(["", "已完成:"])
    if completed:
        lines.extend(f"- {item}" for item in completed)
    else:
        lines.append("- 暂无可确认的完成项")
    if payload.get("phase") == "local-ready":
        lines.extend(
            [
                "",
                "尚未承诺:",
                "- 完整 fixture coverage",
                "- Markdown semantic review",
                "- expected snapshots",
                "- shared docs / changelog",
                "- global lint / merge-ready acceptance",
            ]
        )
    samples = payload.get("samples") if isinstance(payload.get("samples"), list) else []
    if samples:
        lines.extend(["", "样本候选:"])
        for sample in samples[:8]:
            if not isinstance(sample, dict):
                continue
            evidence = sample.get("evidence")
            evidence_suffix = f"，证据: {evidence}" if evidence else ""
            lines.append(
                "- "
                f"{sample.get('purpose')}: {sample.get('doi') or 'null'} "
                f"confidence={sample.get('confidence')} "
                f"proof={sample.get('proof_status')}"
                f"{evidence_suffix}"
            )
    markdown_review = payload.get("markdown_review")
    if isinstance(markdown_review, dict) and markdown_review.get("status") != "missing":
        lines.extend(
            [
                "",
                "Markdown review:",
                f"- artifact: {markdown_review.get('path')}",
                f"- semantic: {markdown_review.get('semantic_review_status')}",
                f"- quality: {markdown_review.get('markdown_quality_status')}",
            ]
        )
    lines.extend(["", "下一步:", f"- {payload.get('next_user_action')}"])
    related = (
        payload.get("related_files")
        if isinstance(payload.get("related_files"), list)
        else []
    )
    if related:
        lines.extend(["", "相关文件:"])
        lines.extend(f"- {path}" for path in related)
    return "\n".join(lines) + "\n"


def _markdown_scalar(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _markdown_command(command: Any) -> str:
    if isinstance(command, list):
        return shlex.join(str(part) for part in command)
    if isinstance(command, str):
        return command
    return _markdown_scalar(command)


def _append_markdown_commands(lines: list[str], commands: Any) -> None:
    if not isinstance(commands, list) or not commands:
        lines.append("  - commands: []")
        return
    for command in commands:
        lines.append(f"  - command: `{_markdown_command(command)}`")


def render_provider_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# {summary['provider']} onboarding summary",
        "",
        f"- status: {summary.get('status')}",
        f"- current_step: {summary.get('current_step')}",
        f"- failed_task: {summary.get('failed_task')}",
        f"- failure_code: {summary.get('failure_code')}",
        f"- failure_recovery_action: {summary.get('failure_recovery_action')}",
        f"- access_review: {summary['access_review'].get('status')}",
        "",
        "## Manifest",
        "",
        f"- path: {summary['manifest'].get('path')}",
        f"- display_source: {summary['manifest'].get('display_source')}",
        f"- main_path: {summary['manifest'].get('main_path')}",
        f"- route_sources: {summary['manifest'].get('route_sources')}",
        "",
        "## Fixture Coverage",
        "",
    ]
    for fixture in summary.get("fixture_coverage", []):
        lines.append(
            "- "
            f"{fixture.get('purpose')}: doi={fixture.get('doi')} "
            f"fixture={fixture.get('fixture_path')} "
            f"expected={fixture.get('expected_outcome')}"
        )

    review = summary.get("review_artifact")
    lines.extend(["", "## Review Artifact", ""])
    if not isinstance(review, dict):
        lines.append("- missing review artifact summary")
    else:
        lines.append(f"- status: {review.get('status')}")
        lines.append(f"- path: {review.get('path')}")
        lines.append(
            f"- semantic_review_status: {review.get('semantic_review_status')}"
        )
        lines.append(
            f"- markdown_quality_status: {review.get('markdown_quality_status')}"
        )
        fixtures = (
            review.get("fixtures") if isinstance(review.get("fixtures"), list) else []
        )
        if not fixtures:
            lines.append("- no review fixture summaries")
        for fixture in fixtures:
            if not isinstance(fixture, dict):
                continue
            lines.append(
                "- "
                f"{fixture.get('fixture')}/{fixture.get('purpose')}: "
                f"doi={fixture.get('doi')} "
                f"reviewed={fixture.get('markdown_semantic_reviewed')} "
                f"quality={fixture.get('markdown_quality_status')} "
                f"issue_ids={_markdown_scalar(fixture.get('issue_ids') or [])} "
                f"fix_ids={_markdown_scalar(fixture.get('fix_ids') or [])} "
                f"tests={_markdown_scalar(fixture.get('test_names') or [])}"
            )

    lines.extend(["", "## Markdown Quality Repairs", ""])
    repairs = summary.get("markdown_quality_repairs") or []
    if not repairs:
        lines.append("- no recorded markdown quality repairs")
    for repair in repairs:
        if not isinstance(repair, dict):
            continue
        failure = (
            repair.get("failure") if isinstance(repair.get("failure"), dict) else {}
        )
        lines.append(
            "- "
            f"doi={repair.get('doi')} "
            f"status={repair.get('status')} "
            f"attempts={repair.get('attempts')} "
            f"quality={repair.get('quality_status')} "
            f"failure={failure.get('code')} "
            f"run_dir={repair.get('run_dir')}"
        )

    lines.extend(["", "## Run Checks", ""])
    run_checks = summary.get("run_checks") or []
    if not run_checks:
        lines.append("- no recorded run-check results")
    for run in run_checks:
        lines.append(
            f"- {run.get('task')}: result={run.get('result')} failure_code={run.get('failure_code')}"
        )
        _append_markdown_commands(lines, run.get("commands"))

    lines.extend(["", "## Verification Plans", ""])
    verification_plans = summary.get("verification_plans") or []
    if not verification_plans:
        lines.append("- no recorded verification plans")
    for plan in verification_plans:
        lines.append(f"- {plan.get('task')}: result={plan.get('result')}")
        _append_markdown_commands(lines, plan.get("commands"))

    lines.extend(["", "## Operator Action", ""])
    lines.append(f"- {summary.get('operator_action') or 'none recorded'}")
    if summary.get("merge_ready_pr_draft"):
        lines.extend(["", "## PR Draft", "", str(summary["merge_ready_pr_draft"])])
    return "\n".join(lines) + "\n"


def run_diagnose(args: argparse.Namespace) -> int:
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    if args.provider:
        provider_name = _provider_slug(args.provider)
        provider_state = providers.get(provider_name)
        if not isinstance(provider_state, dict):
            raise ToolError(
                "TASK_BRIEF_INVALID",
                f"provider is missing from state: {provider_name}",
                retryable=False,
                provider=provider_name,
                task_id=f"{provider_name}-diagnose",
            )
        diagnoses = [diagnose_provider_state(provider_state)]
    else:
        diagnoses = [
            diagnose_provider_state(provider_state)
            for provider_state in providers.values()
            if isinstance(provider_state, dict)
        ]
    print(
        json.dumps(
            {
                "state": str(state_path),
                "providers": diagnoses,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_resume_blocked(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    providers = (
        state.get("providers") if isinstance(state.get("providers"), dict) else {}
    )
    provider_state = providers.get(provider)
    if not isinstance(provider_state, dict):
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"provider is missing from state: {provider}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-resume-blocked",
        )
    plan = plan_resume_blocked(provider_state)
    payload = {"resume_plan": {**plan, "until": args.until}, "state": str(state_path)}
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if not plan["resumable"]:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            "blocked provider is not resumable without operator action.",
            retryable=False,
            provider=provider,
            manifest=provider_state.get("manifest"),
            task_id=f"{provider}-resume-blocked",
            details=payload,
        )
    steps = (
        provider_state.get("steps")
        if isinstance(provider_state.get("steps"), list)
        else []
    )
    if args.until not in steps:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"--until must name a task in the provider state DAG: {args.until}",
            retryable=False,
            provider=provider,
            manifest=provider_state.get("manifest"),
            task_id=f"{provider}-resume-blocked",
            details={"until": args.until, "steps": steps},
        )
    next_task = str(plan["next_task"])
    task_statuses = provider_state.setdefault("task_statuses", {})
    task_statuses[next_task] = "in_progress"
    provider_state["current_step"] = next_task
    provider_state["status"] = "in_progress"
    state["active_provider"] = provider
    _write_json(state_path, state)
    source = _source_from_provider_state(provider_state)
    output_dir = Path(args.output_dir or f".paper-fetch-runs/{provider}-onboarding")
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    run_payload = _execute_run_loop(
        source=source,
        output_dir=output_dir,
        state_path=state_path,
        state=state,
        provider_state=provider_state,
        until=args.until,
        domain=None,
        doi_prefix=None,
    )
    print(json.dumps({**payload, "run": run_payload}, indent=2, sort_keys=True))
    return 0


def run_summarize(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    if args.format in {"agent-json", "agent-markdown"}:
        summary = build_agent_user_summary(
            provider=provider,
            state=state,
            target=args.target,
            state_path=state_path,
        )
    else:
        summary = build_provider_summary(provider=provider, state=state)
    if args.format in {"json", "agent-json"}:
        content = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    elif args.format == "agent-markdown":
        content = render_agent_user_summary_markdown(summary)
    else:
        content = render_provider_summary_markdown(summary)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = _repo_root() / output_path
        write_text(output_path, content)
    else:
        print(content, end="")
    return 0


def run_prepare_human_preflight(args: argparse.Namespace) -> int:
    payload = build_human_preflight_digest(
        provider=args.provider,
        domain=args.domain,
        doi_prefix=args.doi_prefix,
    )
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = _repo_root() / output_path
        write_text(output_path, content)
    else:
        print(content, end="")
    return 0


def run_finalize_review_artifact(args: argparse.Namespace) -> int:
    reviewed_by = args.reviewed_by or os.environ.get("USER") or "operator"
    payload = finalize_review_artifact(
        provider=args.provider,
        reviewed_by=reviewed_by,
        confirmed_final_quality=args.confirmed_final_quality,
        run_fresh_review=True,
    )
    print(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end=""
    )
    return 0


def run_advance(args: argparse.Namespace) -> int:
    provider = _provider_slug(args.provider)
    state_path = _state_path(args.state)
    state = _load_state(state_path)
    provider_state = _ensure_provider_state(state, provider=provider)
    task_statuses = provider_state["task_statuses"]
    if args.task not in task_statuses:
        raise ToolError(
            "TASK_BRIEF_INVALID",
            f"unknown task for provider {provider}: {args.task}",
            retryable=False,
            provider=provider,
            task_id=f"{provider}-advance-{args.task}",
            details={"task": args.task},
        )
    if args.task == ACCESS_PREFLIGHT_STEP:
        validate_access_review(provider)
    elif (
        args.task == DISCOVER_STEP
        and ACCESS_PREFLIGHT_STEP not in provider_state["completed_steps"]
    ):
        validate_access_review(provider)
        raise ToolError(
            "ACCESS_REVIEW_NOT_APPROVED",
            "operator-access-preflight must be completed before discover-manifest.",
            retryable=False,
            provider=provider,
            manifest=provider_state.get("manifest"),
            task_id=f"{provider}-advance-{args.task}",
            details={
                "required_completed_step": ACCESS_PREFLIGHT_STEP,
                "task": args.task,
            },
        )
    task_statuses[args.task] = "completed"
    completed_steps = provider_state["completed_steps"]
    if args.task not in completed_steps:
        completed_steps.append(args.task)
    provider_state["current_step"] = None
    next_step = _next_pending_step(provider_state)
    if next_step is None:
        provider_state["status"] = "merge_ready"
        state["active_provider"] = None
    else:
        provider_state["status"] = "in_progress"
        state["active_provider"] = provider
    _write_json(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider,
                "advanced": args.task,
                "status": provider_state["status"],
                "next_step": next_step,
                "state": str(state_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = CoordinatorArgumentParser(
        description="Generate manifest-driven provider onboarding dry-run artifacts."
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=CoordinatorArgumentParser
    )

    discover = subparsers.add_parser(
        "discover",
        help="print a manifest discovery worker brief",
    )
    discover.add_argument("--provider", required=True, help="provider name seed")
    discover.add_argument("--domain", help="provider domain seed")
    discover.add_argument("--doi-prefix", help="DOI prefix seed")
    discover.add_argument(
        "--output",
        required=True,
        help="manifest path the discovery worker is allowed to write",
    )
    discover.add_argument(
        "--evidence-pack",
        help="prepared discovery evidence pack path to include in the brief",
    )
    discover.set_defaults(func=run_discover)

    prepare_discovery = subparsers.add_parser(
        "prepare-discovery",
        help="write the manifest discovery evidence pack",
    )
    prepare_discovery.add_argument(
        "--provider", required=True, help="provider name seed"
    )
    prepare_discovery.add_argument(
        "--domain", required=True, help="provider domain seed"
    )
    prepare_discovery.add_argument(
        "--doi-prefix", required=True, help="DOI prefix seed"
    )
    prepare_discovery.add_argument(
        "--output-dir",
        required=True,
        help="directory for discovery/evidence-pack.json",
    )
    prepare_discovery.add_argument(
        "--no-network",
        action="store_true",
        help="only write query plans and routing seed evidence",
    )
    prepare_discovery.add_argument(
        "--browser-fallback",
        choices=DISCOVERY_BROWSER_FALLBACK_MODES,
        default="auto",
        help="whether discovery may fall back from HTTP landing probes to browser probes",
    )
    prepare_discovery.set_defaults(func=run_prepare_discovery)

    autofix_manifest = subparsers.add_parser(
        "autofix-manifest",
        help="repair schema-level manifest discovery gaps from an evidence pack",
    )
    autofix_manifest.add_argument(
        "--manifest", required=True, help="ProviderManifest YAML path"
    )
    autofix_manifest.add_argument(
        "--evidence-pack", required=True, help="discovery evidence pack JSON"
    )
    write_group = autofix_manifest.add_mutually_exclusive_group(required=True)
    write_group.add_argument(
        "--write", action="store_true", help="write changes back to manifest"
    )
    write_group.add_argument(
        "--dry-run", action="store_true", help="print proposed changes only"
    )
    autofix_manifest.add_argument(
        "--targeted",
        action="store_true",
        help="mark this as a validate-manifest retry autofix",
    )
    autofix_manifest.set_defaults(func=run_autofix_manifest)

    inspect_discovery = subparsers.add_parser(
        "inspect-discovery",
        help="summarize candidates, low-confidence purposes, and proof gaps",
    )
    inspect_discovery.add_argument(
        "--manifest", required=True, help="ProviderManifest YAML path"
    )
    inspect_discovery.add_argument(
        "--evidence-pack", required=True, help="discovery evidence pack JSON"
    )
    inspect_discovery.set_defaults(func=run_inspect_discovery)

    start = subparsers.add_parser(
        "start",
        help="write a dry-run onboarding DAG and worker briefs",
    )
    source = start.add_mutually_exclusive_group(required=True)
    source.add_argument("--provider", help="provider name seed")
    source.add_argument("--manifest", help="existing manifest path for replay mode")
    start.add_argument("--domain", help="provider domain seed")
    start.add_argument("--doi-prefix", help="DOI prefix seed")
    start.add_argument(
        "--dry-run", action="store_true", help="write planned artifacts only"
    )
    start.add_argument(
        "--output-dir", required=True, help="directory for dry-run artifacts"
    )
    start.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    start.set_defaults(func=run_start)

    run = subparsers.add_parser(
        "run",
        help="execute the serial onboarding DAG for one provider",
    )
    run_source = run.add_mutually_exclusive_group(required=True)
    run_source.add_argument("--provider", help="provider name seed")
    run_source.add_argument("--manifest", help="existing manifest path for replay mode")
    run.add_argument("--domain", help="provider domain seed")
    run.add_argument("--doi-prefix", help="DOI prefix seed")
    run.add_argument(
        "--until",
        default="merge-ready",
        help="inclusive task id to stop after; defaults to merge-ready",
    )
    run.add_argument(
        "--output-dir",
        help="directory for DAG, briefs, and worker logs",
    )
    run.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    run.set_defaults(func=run_run)

    diagnose = subparsers.add_parser(
        "diagnose",
        help="summarize blocked provider failures from coordinator state",
    )
    diagnose.add_argument("--provider", help="optional provider name")
    diagnose.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    diagnose.set_defaults(func=run_diagnose)

    resume_blocked = subparsers.add_parser(
        "resume-blocked",
        help="resume one retryable blocked provider after preconditions are satisfied",
    )
    resume_blocked.add_argument("--provider", required=True, help="provider name")
    resume_blocked.add_argument(
        "--dry-run", action="store_true", help="print resume plan only"
    )
    resume_blocked.add_argument(
        "--until",
        default="provider-local-acceptance",
        help="inclusive task id to stop after; defaults to provider-local-acceptance",
    )
    resume_blocked.add_argument(
        "--output-dir",
        help="directory for DAG, briefs, and worker logs",
    )
    resume_blocked.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    resume_blocked.set_defaults(func=run_resume_blocked)

    summarize = subparsers.add_parser(
        "summarize",
        help="render an operator-facing provider onboarding summary",
    )
    summarize.add_argument("--provider", required=True, help="provider name")
    summarize.add_argument(
        "--format",
        choices=("json", "markdown", "agent-json", "agent-markdown"),
        default="json",
        help="summary output format",
    )
    summarize.add_argument(
        "--target",
        choices=tuple(AGENT_TARGET_STEPS),
        default="local-ready",
        help="agent summary target tier",
    )
    summarize.add_argument("--output", help="optional output path")
    summarize.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    summarize.set_defaults(func=run_summarize)

    prepare_human_preflight = subparsers.add_parser(
        "prepare-human-preflight",
        help="render the compact human review digest for access, waterfall, and purpose coverage",
    )
    prepare_human_preflight.add_argument(
        "--provider", required=True, help="provider name"
    )
    prepare_human_preflight.add_argument("--domain", help="provider domain seed")
    prepare_human_preflight.add_argument("--doi-prefix", help="DOI prefix seed")
    prepare_human_preflight.add_argument("--output", help="optional output path")
    prepare_human_preflight.set_defaults(func=run_prepare_human_preflight)

    finalize_review = subparsers.add_parser(
        "finalize-review-artifact",
        help="write final batch Markdown semantic signoff after human confirmation",
    )
    finalize_review.add_argument("--provider", required=True, help="provider name")
    finalize_review.add_argument(
        "--confirmed-final-quality",
        action="store_true",
        help="required: operator confirmed current extracted.md quality summary",
    )
    finalize_review.add_argument(
        "--reviewed-by",
        help="operator name to record in onboarding/reviews/<provider>.yml",
    )
    finalize_review.set_defaults(func=run_finalize_review_artifact)

    next_task = subparsers.add_parser(
        "next",
        help="print and persist the next serial task for one provider",
    )
    next_task.add_argument("--provider", required=True, help="provider name")
    next_task.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    next_task.set_defaults(func=run_next)

    verify = subparsers.add_parser(
        "verify",
        help="write dry-run verification plan for a provider task",
    )
    verify.add_argument("--provider", required=True, help="provider name")
    verify.add_argument("--task", required=True, help="task id to verify")
    verify.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    verify.set_defaults(func=run_verify)

    run_checks = subparsers.add_parser(
        "run-checks",
        help="execute local verification commands for a provider task",
    )
    run_checks.add_argument("--provider", required=True, help="provider name")
    task_group = run_checks.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--task", help="single task id to execute")
    task_group.add_argument(
        "--all-local",
        action="store_true",
        help="run access, manifest, review, shared integration, and global lint gates",
    )
    run_checks.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    run_checks.set_defaults(func=run_run_checks)

    repair_markdown_quality = subparsers.add_parser(
        REPAIR_MARKDOWN_QUALITY_STEP,
        help="repair a failing markdown-quality.json report through the onboarding agent CLI",
    )
    repair_markdown_quality.add_argument(
        "--provider", required=True, help="provider name"
    )
    repair_markdown_quality.add_argument("--doi", required=True, help="DOI to repair")
    repair_markdown_quality.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    repair_markdown_quality.add_argument(
        "--output-dir",
        help="directory for repair briefs, prompts, and logs",
    )
    repair_markdown_quality.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_WORKER_RETRIES,
        help="maximum repair attempts; defaults to 3",
    )
    repair_markdown_quality.set_defaults(func=run_repair_markdown_quality)

    check_snapshot = subparsers.add_parser(
        "check-snapshot",
        help="check that a DOI fixture has an expected snapshot",
    )
    check_snapshot.add_argument("--provider", required=True, help="provider name")
    check_snapshot.add_argument("--doi", required=True, help="DOI to check")
    check_snapshot.set_defaults(func=run_check_snapshot)

    check_cleaning = subparsers.add_parser(
        "check-cleaning-proposal",
        help="check cleaning proposal fixture digest freshness",
    )
    check_cleaning.add_argument("--provider", required=True, help="provider name")
    check_cleaning.add_argument("--proposal", help="optional compact proposal path")
    check_cleaning.set_defaults(func=run_check_cleaning_proposal)

    advance = subparsers.add_parser(
        "advance",
        help="mark a task complete and persist the next serial task",
    )
    advance.add_argument("--provider", required=True, help="provider name")
    advance.add_argument("--task", required=True, help="task id to mark complete")
    advance.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    advance.set_defaults(func=run_advance)

    return parser


def _provider_from_args(args: argparse.Namespace) -> str | None:
    provider = getattr(args, "provider", None)
    if isinstance(provider, str):
        try:
            return _provider_slug(provider)
        except ValueError:
            return provider
    return None


def _manifest_from_args(args: argparse.Namespace) -> str | None:
    manifest = getattr(args, "manifest", None)
    return manifest if isinstance(manifest, str) else None


def _task_id_from_args(args: argparse.Namespace) -> str:
    provider = _provider_from_args(args)
    command = getattr(args, "command", None) or "coordinator"
    task = getattr(args, "task", None)
    if provider and task:
        return f"{provider}-{command}-{task}"
    if provider:
        return f"{provider}-{command}"
    return str(command)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ToolError as exc:
        emit_error(
            error_payload(
                exc.code,
                exc.message,
                provider=exc.provider or _provider_from_args(args),
                manifest=exc.manifest or _manifest_from_args(args),
                task_id=exc.task_id or _task_id_from_args(args),
                retryable=exc.retryable,
                details=exc.details,
            )
        )
        return 1
    except ValueError as exc:
        emit_error(
            error_payload(
                "TASK_BRIEF_INVALID",
                str(exc),
                provider=_provider_from_args(args),
                manifest=_manifest_from_args(args),
                task_id=_task_id_from_args(args),
                retryable=False,
                details={"reason": str(exc)},
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
