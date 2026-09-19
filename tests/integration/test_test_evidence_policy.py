"""Child pytest probes demonstrate that evidence policy fails closed."""

import json
import os
import subprocess
import sys

import pytest
from tests.paths import REPO_ROOT
from tests.golden_criteria import golden_criteria_manifest
from tests.fixture_catalog import fixture_catalog


def _probe(
    tmp_path, source, entry, *, overrides=None, flags=(), conftest="", integrity=False
):
    root = tmp_path / "probe"
    tests = root / "tests"
    layer = tests / "golden"
    layer.mkdir(parents=True)
    if integrity:
        conftest += """
def pytest_sessionstart(session):
    import json
    from pathlib import Path
    from tests.support.test_evidence import validate_ledger
    ledger_path = Path(session.config.getoption("--test-evidence-manifest"))
    validate_ledger(json.loads(ledger_path.read_text()), ledger_path.parent.parent)
"""
    (root / "conftest.py").write_text(
        'pytest_plugins = ["tests.support.test_evidence"]\n' + conftest
    )
    (layer / "test_probe.py").write_text(source)
    ledger = {
        "version": 2,
        "modules": {
            "tests/golden/test_probe.py": {
                "default": entry,
                "overrides": overrides or {},
            }
        },
    }
    path = tests / "test-evidence.json"
    path.write_text(json.dumps(ledger))
    env = dict(
        os.environ, PYTHONPATH=os.pathsep.join([str(REPO_ROOT), str(REPO_ROOT / "src")])
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(REPO_ROOT / "pyproject.toml"),
            str(layer),
            "--test-evidence-manifest",
            str(path),
            "-q",
            *flags,
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return result.returncode, result.stdout + result.stderr


def _source_path(origin):
    return next(
        r.absolute_path
        for r in fixture_catalog().values()
        if r.origin_kind == origin and r.absolute_path.suffix == ".html"
    )


CONTENT = {"kind": "content", "scope": "original paragraph", "primary": ["source"]}


@pytest.mark.parametrize(
    "case",
    ["synthetic", "contract_scenario", "missing", "no_input"],
)
def test_invalid_evidence_fails_in_child_pytest(tmp_path, case):
    path = (
        _source_path(case)
        if case in {"synthetic", "contract_scenario"}
        else REPO_ROOT / "tests/fixtures/unregistered.html"
    )
    source = f"from pathlib import Path\ndef test_probe():\n    Path({str(path)!r}).read_text()\n"
    if case == "no_input":
        source = 'def test_probe(): assert "fabricated"\n'
    if case == "missing":
        # Opening an absent, undeclared input still records the attempted read.
        source = f"from pathlib import Path\ndef test_probe():\n    try: Path({str(path)!r}).read_text()\n    except FileNotFoundError: pass\n"
    status, output = _probe(tmp_path, source, CONTENT)
    assert status != 0, output
    assert any(
        token in output
        for token in (
            "content primary evidence",
            "unclassified or stale",
            "unregistered fixture input",
            "did not read",
        )
    ), output


@pytest.mark.parametrize(
    "input_kind", ["synthetic_source", "synthetic_asset", "inline_asset"]
)
def test_real_html_does_not_promote_synthetic_primary_asset(tmp_path, input_kind):
    real = _source_path("real_replay")
    fake = _source_path("synthetic")
    if input_kind == "synthetic_source":
        statement = f"Path({str(fake)!r}).read_text()"
        entry = CONTENT
        message = "synthetic"
    elif input_kind == "synthetic_asset":
        fake = next(
            r.absolute_path
            for r in fixture_catalog().values()
            if r.origin_kind == "synthetic" and r.absolute_path.suffix == ".png"
        )
        statement = f"Path({str(fake)!r}).read_bytes()"
        entry = dict(CONTENT, primary=["source", "asset"])
        message = "synthetic"
    else:
        statement = "image = b'placeholder image'; assert image"
        entry = dict(CONTENT, primary=["source", "asset"])
        message = "primary evidence: asset"
    status, output = _probe(
        tmp_path,
        f"from pathlib import Path\ndef test_probe():\n    Path({str(real)!r}).read_text()\n    {statement}\n",
        entry,
    )
    assert status == 1 and message in output, output


@pytest.mark.parametrize("origin", ["real_replay", "synthetic"])
def test_parametrized_cached_original_propagates_across_workers(tmp_path, origin):
    real = _source_path(origin)
    source = f"""
from pathlib import Path
import pytest
from tests.support import replay
from tests.golden_corpus import GoldenCorpusFixture

def build(fixture):
    marker = replay.ROOT / "builder-was-called"
    assert not marker.exists(), "canonical builder ran twice across workers"
    marker.write_text("called")
    return Path({str(real)!r}).read_text()

@pytest.fixture(scope="session", autouse=True)
def setup(tmp_path_factory):
    import tests.golden_corpus
    tests.golden_corpus.build_article_from_fixture = build
    base = tmp_path_factory.getbasetemp().parent
    replay.ROOT = base / 'evidence-build'
    replay.ROOT.mkdir(exist_ok=True)

@pytest.mark.parametrize('value', range(48))
def test_probe(value):
    assert replay.build_article_from_fixture(GoldenCorpusFixture('probe', {{'sample_id':'probe'}}))
"""
    status, output = _probe(tmp_path, source, CONTENT)
    assert status == (0 if origin == "real_replay" else 1), output
    assert ("48 passed" if origin == "real_replay" else "synthetic") in output


def test_module_loading_and_shared_fixture_cache_keep_evidence(tmp_path):
    real = _source_path("real_replay")
    source = f"""
from pathlib import Path
import pytest
RAW = Path({str(real)!r}).read_text()
@pytest.fixture(scope='session')
def shared(): return RAW
@pytest.mark.parametrize('value', range(4))
def test_probe(value, shared): assert shared
"""
    status, output = _probe(tmp_path, source, CONTENT)
    assert status == 0, output


@pytest.mark.parametrize(
    "change,message",
    [
        ("unknown", "Unknown asset_origins"),
        ("conflict", "Conflicting asset origins"),
        ("spoof", "Unproven synthetic origin override"),
    ],
)
def test_bad_asset_override_rejected_by_child_pytest(tmp_path, change, message):
    manifest = json.loads(json.dumps(golden_criteria_manifest()))
    sample = next(iter(manifest["samples"].values()))
    if change == "unknown":
        sample["asset_origins"] = {"not-an-asset": "real_replay"}
    elif change == "spoof":
        sample = next(
            s
            for s in manifest["samples"].values()
            if s["origin_kind"] == "synthetic"
            and any(
                k.endswith(".html") and not k.startswith("acquisition/")
                for k in s["assets"]
            )
        )
        sample["asset_origins"] = {
            next(
                k
                for k in sample["assets"]
                if k.endswith(".html") and not k.startswith("acquisition/")
            ): "real_replay"
        }
    else:
        duplicate = dict(sample, origin_kind="synthetic", asset_origins={})
        manifest["samples"]["conflicting-alias"] = duplicate
    custom = tmp_path / "manifest.json"
    custom.write_text(json.dumps(manifest))
    conftest = f"""
import json
from pathlib import Path
import tests.fixture_catalog as catalog
catalog.golden_criteria_manifest = lambda: json.loads(Path({str(custom)!r}).read_text())
catalog.fixture_catalog.cache_clear()
"""
    status, output = _probe(
        tmp_path, "def test_probe(): pass\n", CONTENT, conftest=conftest
    )
    assert status != 0 and message in output, output


@pytest.mark.parametrize(
    "case",
    [
        "unreviewed",
        "no_evidence",
        "stale",
        "mechanism_target",
        "empty_partial",
        "synthetic",
        "real",
    ],
)
def test_template_gap_review_cannot_invent_content_coverage(tmp_path, case):
    target = "tests/golden/test_probe.py::test_probe"
    entry = dict(CONTENT, template_gap="Historical source gap")
    review = {
        "status": "covered",
        "scope": "Same captured paragraph",
        "evidence_tests": [target],
        "remaining": [],
    }
    entry["template_review"] = review
    if case == "unreviewed":
        del entry["template_review"]
    elif case == "no_evidence":
        review["evidence_tests"] = []
    elif case == "stale":
        review["evidence_tests"] = ["tests/golden/test_probe.py::test_deleted"]
    elif case == "mechanism_target":
        entry.update(kind="mechanism", reason="Injected control")
    elif case == "empty_partial":
        review["status"] = "partial"
    path = _source_path("synthetic" if case == "synthetic" else "real_replay")
    status, output = _probe(
        tmp_path,
        f"from pathlib import Path\ndef test_probe():\n    assert Path({str(path)!r}).read_text()\n",
        entry,
        integrity=True,
    )
    if case == "real":
        assert status == 0, output
    else:
        assert status != 0, output
        assert (
            "template review" in output
            or "content primary evidence is synthetic" in output
        ), output


def test_evidence_ledger_integrity():
    from tests.support.test_evidence import LEDGER, validate_ledger

    validate_ledger(json.loads(LEDGER.read_text()), REPO_ROOT)


def test_new_test_uses_module_default_without_registration(tmp_path):
    real = _source_path("real_replay")
    source = f"from pathlib import Path\ndef test_new(): assert Path({str(real)!r}).read_text()\n"
    status, output = _probe(tmp_path, source, CONTENT)
    assert status == 0, output


@pytest.mark.parametrize("case", ["override", "module", "reference"])
def test_stale_ledger_entries_are_rejected(tmp_path, case):
    from tests.support.test_evidence import validate_ledger

    layer = tmp_path / "tests/golden"
    layer.mkdir(parents=True)
    (layer / "test_probe.py").write_text("def test_probe(): pass\n")
    entry = dict(CONTENT)
    module = {"default": entry}
    ledger = {"version": 2, "modules": {"tests/golden/test_probe.py": module}}
    if case == "override":
        module["overrides"] = {"test_deleted": CONTENT}
    elif case == "module":
        ledger["modules"]["tests/golden/test_deleted.py"] = module
    else:
        entry["template_review"] = {
            "status": "covered",
            "scope": "paragraph",
            "remaining": [],
            "evidence_tests": ["tests/golden/test_probe.py::test_deleted"],
        }
    with pytest.raises(ValueError, match="stale"):
        validate_ledger(ledger, tmp_path)
