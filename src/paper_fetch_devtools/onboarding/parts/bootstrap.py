# ruff: noqa
#!/usr/bin/env python3
"""Generate provider onboarding task DAGs and worker briefs."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
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
from paper_fetch_devtools.onboarding import dispatch as onboarding_dispatch  # noqa: E402
from paper_fetch_devtools.onboarding import state as onboarding_state  # noqa: E402


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
