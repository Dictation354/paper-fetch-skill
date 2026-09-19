"""Exercise unit policy in child pytest sessions with the project configuration."""

import os
import subprocess
import sys
import pytest
from tests.paths import REPO_ROOT


def _run_unit(tmp_path, source, *args):
    unit = tmp_path / "unit"
    unit.mkdir()
    (tmp_path / "conftest.py").write_text('pytest_plugins = ["tests.conftest"]\n')
    (unit / "test_probe.py").write_text(source)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT), str(REPO_ROOT / "src")))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(REPO_ROOT / "pyproject.toml"),
            str(unit),
            "-q",
            *args,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_unit_real_boundaries_fail_before_external_work(tmp_path):
    result = _run_unit(
        tmp_path,
        """
import os
import subprocess
import sys
from tests.golden_corpus import build_article_from_fixture
from tests.golden_criteria import golden_criteria_asset

def test_backend_is_not_loaded():
    assert "pymupdf4llm" not in sys.modules

def test_process():
    subprocess.run([sys.executable, "-c", "raise SystemExit(99)"])

def test_shell():
    os.system("exit 99")

def test_conversion():
    import pymupdf4llm

def test_replay():
    build_article_from_fixture(None)

def test_html_source():
    golden_criteria_asset("10.1038/nature12915", "original.html").read_text()
""",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "5 failed, 1 passed" in output
    for operation in (
        "external process",
        "real PDF conversion backend",
        "full-paper replay builder",
        "canonical full-paper source read",
    ):
        assert operation in output


@pytest.mark.parametrize("marker", ["browser", "live", "allow_subprocess"])
def test_unit_cannot_bypass_boundaries_with_markers(tmp_path, marker):
    result = _run_unit(
        tmp_path,
        f"import pytest\n@pytest.mark.{marker}\ndef test_bad(): pass\n",
        "--collect-only",
    )
    assert result.returncode == 4
    assert f"forbidden marker {marker}" in result.stdout + result.stderr


def test_default_collection_excludes_golden_and_explicit_golden_is_complete():
    import ast
    import tomllib

    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert config["tool"]["pytest"]["ini_options"]["testpaths"] == [
        "tests/unit",
        "tests/integration",
    ]
    module = ast.parse((REPO_ROOT / "tests/golden/test_golden_corpus.py").read_text())
    inventory = next(
        n
        for n in module.body
        if isinstance(n, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "GOLDEN_CORPUS_FIXTURES"
            for t in n.targets
        )
    )
    assert ast.unparse(inventory.value) == "iter_golden_corpus_fixtures()"
    assert not any(
        isinstance(n, ast.Attribute) and n.attr == "skipif" for n in ast.walk(module)
    )


@pytest.mark.parametrize(
    "args", [("--fast", "--with-golden"), ("--with-golden", "--skip-integration")]
)
def test_preflight_rejects_partial_golden_run(args):
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/dev-preflight.sh"), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "conflicts" in result.stderr
