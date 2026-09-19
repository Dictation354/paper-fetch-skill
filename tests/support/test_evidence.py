"""Test-only evidence accounting. Reads establish provenance, not assertion truth.

Manifest/catalog owns origins; this ledger owns assertion scope and evidence roles.
The audit hook observes collection, fixtures and calls. Cached values carry the
same read set, including the cross-worker canonical build envelope.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from contextlib import contextmanager
from functools import cache as _cache, wraps
import json
import os
from pathlib import Path
import sys

import pytest

from tests.paths import REPO_ROOT

LEDGER = REPO_ROOT / "tests/test-evidence.json"
ACTIVE: set[str] | None = None
CAPTURES: list[set[str]] = []
COLLECTED: dict[str, set[str]] = defaultdict(set)
CATALOG = {}
ASSET_ROLES: dict[str, str] = {}
ENABLED = False


def observe(paths):
    for capture in CAPTURES:
        capture.update(paths)


@contextmanager
def capture_reads():
    reads: set[str] = set()
    CAPTURES.append(reads)
    try:
        yield reads
    finally:
        assert CAPTURES.pop() is reads


def evidence_cache(function):
    @_cache
    def cached(*args, **kwargs):
        with capture_reads() as reads:
            value = function(*args, **kwargs)
        return value, frozenset(reads)

    @wraps(function)
    def wrapped(*args, **kwargs):
        value, reads = cached(*args, **kwargs)
        observe(reads)
        return value

    wrapped.cache_clear = cached.cache_clear
    return wrapped


def audit(event, args):
    if not ENABLED or event != "open" or not isinstance(args[0], (str, bytes)):
        return
    mode = args[1]
    if isinstance(mode, str) and any(flag in mode for flag in "wax+"):
        return
    path = os.path.abspath(os.fsdecode(args[0]))
    prefix = str(REPO_ROOT / "tests/fixtures") + os.sep
    if not path.startswith(prefix):
        return
    relative = Path(path).relative_to(REPO_ROOT).as_posix()
    # Descriptive metadata is infrastructure, not paper input. Cataloged JSON
    # responses remain tracked; provenance is independently hash-checked.
    if relative not in CATALOG and (
        path.endswith("/manifest.json")
        or Path(path).name in {"README.md", "provenance.json"}
    ):
        return
    observe({relative})
    if ACTIVE is None:
        frame = sys._getframe(1)
        while frame:
            filename = os.path.abspath(frame.f_code.co_filename)
            if filename.endswith(".py"):
                COLLECTED[filename].add(relative)
            frame = frame.f_back


def definitions(path):
    tree = ast.parse(path.read_text())
    found = set()
    for node in tree.body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test_"):
            found.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(
                    method, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and method.name.startswith("test_"):
                    found.add(node.name + "::" + method.name)
    return found


def validate_ledger(ledger, root):
    if ledger.get("version") != 2:
        raise ValueError("unsupported test evidence ledger version")
    modules = ledger["modules"]
    actual = {
        p.relative_to(root).as_posix(): definitions(p)
        for layer in ("unit", "integration", "golden", "live")
        for p in (root / "tests" / layer).glob("test_*.py")
    }
    for name in set(modules) | set(actual):
        if name not in actual:
            raise ValueError(f"stale evidence module: {name}")
        if name not in modules:
            raise ValueError(f"unclassified test module: {name}")
        module = modules[name]
        if set(module.get("overrides", {})) - actual[name]:
            raise ValueError(f"stale evidence override: {name}")
        for entry in [module["default"], *module.get("overrides", {}).values()]:
            validate_entry(entry, name)
    validate_template_reviews(modules, actual)


def validate_entry(entry, name):
    kind = entry.get("kind")
    if kind not in {"content", "mechanism", "infrastructure"}:
        raise ValueError(f"unclassified test: {name}")
    if not entry.get("scope"):
        raise ValueError(f"missing assertion scope: {name}")
    if "live_response" in entry.get("primary", []) and "/live/" not in name:
        raise ValueError(f"live evidence outside live layer: {name}")
    if set(entry.get("primary", [])) - {"source", "asset", "live_response"}:
        raise ValueError(f"unknown primary evidence role: {name}")
    if kind == "content" and not entry.get("primary"):
        raise ValueError(f"missing primary evidence: {name}")
    if set(entry.get("primary", [])) & set(entry.get("auxiliary", [])):
        raise ValueError(f"conflicting evidence roles: {name}")
    if kind == "mechanism" and not entry.get("reason"):
        raise ValueError(f"missing mechanism reason: {name}")


def validate_template_reviews(modules, actual):
    """Review links prove their target exists, not semantic equivalence."""
    for path, module in modules.items():
        entries = [module["default"], *module.get("overrides", {}).values()]
        for entry in entries:
            if "template_gap" not in entry and "template_review" not in entry:
                continue
            review = entry.get("template_review", {})
            status = review.get("status")
            if status not in {"mechanism", "covered", "partial"} or not review.get(
                "scope"
            ):
                raise ValueError(f"missing or invalid template review: {path}")
            evidence = review.get("evidence_tests")
            remaining = review.get("remaining")
            if not isinstance(evidence, list) or not isinstance(remaining, list):
                raise ValueError(f"invalid template review lists: {path}")
            if any(not isinstance(gap, str) or not gap.strip() for gap in remaining):
                raise ValueError(f"empty template review gap: {path}")
            if (status == "partial") != bool(remaining):
                raise ValueError(
                    f"template review status contradicts remaining gaps: {path}"
                )
            if status == "covered" and not evidence:
                raise ValueError(f"covered template review lacks evidence: {path}")
            if status == "mechanism" and (evidence or entry["kind"] != "mechanism"):
                raise ValueError(f"invalid mechanism template review: {path}")
            for target in evidence:
                target_path, separator, definition = str(target).partition("::")
                target_module = modules.get(target_path)
                if (
                    not separator
                    or target_module is None
                    or definition not in actual.get(target_path, set())
                ):
                    raise ValueError(f"stale template review evidence: {target}")
                target_entry = target_module.get("overrides", {}).get(
                    definition, target_module["default"]
                )
                if target_entry[
                    "kind"
                ] != "content" or "live_response" in target_entry.get("primary", []):
                    raise ValueError(
                        f"template review evidence is not offline content: {target}"
                    )


def asset_role(path):
    if path in ASSET_ROLES:
        return ASSET_ROLES[path]
    name = Path(path).name
    if name in {
        "expected.json",
        "article.json",
        "fetch.manifest.json",
        "provenance.json",
        "capture.json",
        "collection.json",
        "identity.json",
    } or path.endswith(".md"):
        return "snapshot"
    if Path(path).suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".tif",
        ".tiff",
        ".eps",
        ".zip",
        ".gz",
    }:
        return "asset"
    return "source"


def verify_reads(entry, reads):
    unknown = sorted(path for path in reads if path not in CATALOG)
    if unknown:
        raise ValueError(f"unregistered fixture input: {unknown}")
    if entry["kind"] != "content":
        return
    if entry["primary"] == ["live_response"]:
        return  # Network responses are outside the offline file provenance audit.
    declared = set(entry["primary"]) | set(entry.get("auxiliary", []))
    undeclared = sorted(path for path in reads if asset_role(path) not in declared)
    if undeclared:
        raise ValueError(f"undeclared auxiliary evidence: {undeclared}")
    for role in entry["primary"]:
        if not any(asset_role(path) == role for path in reads):
            raise ValueError(
                f"content test did not read its declared primary evidence: {role}"
            )
    primary = [path for path in reads if asset_role(path) in entry["primary"]]
    if not primary:
        raise ValueError("content test did not read its declared primary evidence")
    for path in primary:
        origin = CATALOG[path].origin_kind
        if origin not in {"real_replay", "real_excerpt"}:
            raise ValueError(f"content primary evidence is {origin}: {path}")


def pytest_addoption(parser):
    parser.addoption(
        "--test-evidence-manifest",
        help="Test-only evidence ledger for isolated policy probes",
    )


def pytest_configure(config):
    global CATALOG, ENABLED
    from tests.fixture_catalog import fixture_catalog

    try:
        CATALOG = fixture_catalog()
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
    # Captured entities deliberately use .bin; use the provenance's media
    # type/asset kind rather than pretending extensions establish their role.
    for path in CATALOG:
        if not path.endswith("/acquisition/provenance.json"):
            continue
        provenance = REPO_ROOT / path
        for record in json.loads(provenance.read_text()).get("records", []):
            body_path = (
                (provenance.parent.parent / record["body_file"])
                .relative_to(REPO_ROOT)
                .as_posix()
            )
            headers = record.get("response_headers") or {}
            media_type = str(
                headers.get("content-type") or record.get("content_type") or ""
            )
            if media_type.startswith("image/") or record.get("asset_kind") in {
                "figure",
                "table",
                "formula",
                "supplementary",
            }:
                ASSET_ROLES[body_path] = "asset"
    ledger_path = Path(config.getoption("--test-evidence-manifest") or LEDGER)
    ledger = json.loads(ledger_path.read_text())
    root = ledger_path.parent.parent
    if ledger.get("version") != 2:
        raise pytest.UsageError("unsupported test evidence ledger version")
    config._test_evidence_ledger = ledger
    config._test_evidence_root = root
    if not ENABLED:
        sys.addaudithook(audit)
        ENABLED = True


def pytest_collection_modifyitems(config, items):
    root = config._test_evidence_root
    modules = config._test_evidence_ledger["modules"]
    for item in items:
        path = Path(str(item.path))
        if not path.is_relative_to(root / "tests"):
            continue  # Existing external boundary probes have their own contract.
        module = modules.get(path.relative_to(root).as_posix())
        name = item.nodeid.split("::", 1)[1].split("[", 1)[0]
        if module is None:
            raise pytest.UsageError(f"unclassified collected test: {item.nodeid}")
        entry = module.get("overrides", {}).get(name, module["default"])
        try:
            validate_entry(entry, item.nodeid)
        except ValueError as exc:
            raise pytest.UsageError(str(exc)) from exc
        item._test_evidence_entry = entry


@pytest.hookimpl(wrapper=True)
def pytest_fixture_setup(fixturedef, request):
    with capture_reads() as reads:
        result = yield
    fixturedef._test_evidence_reads = reads
    return result


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    global ACTIVE
    previous = ACTIVE
    with capture_reads() as reads:
        reads.update(COLLECTED.get(str(item.path), set()))
        ACTIVE = reads
        item._test_evidence_reads = reads
        try:
            return (yield)
        finally:
            ACTIVE = previous


@pytest.hookimpl(trylast=True)
def pytest_runtest_call(item):
    entry = getattr(item, "_test_evidence_entry", None)
    if entry is None:
        return
    for fixture in item._request._fixture_defs.values():
        observe(getattr(fixture, "_test_evidence_reads", set()))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    entry = getattr(item, "_test_evidence_entry", None)
    if call.when == "call" and entry and not report.skipped:
        try:
            verify_reads(entry, item._test_evidence_reads)
        except ValueError as exc:
            report.outcome = "failed"
            report.longrepr = (
                str(report.longrepr or "") + "\ntest evidence: " + str(exc)
            )
    return report
