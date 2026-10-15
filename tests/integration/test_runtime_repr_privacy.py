"""An actual failed pytest run must not print runtime credentials in its reports."""

import os
from pathlib import Path
import subprocess
import sys


def test_failed_assertion_traceback_junit_and_diagnostics_hide_runtime_env(tmp_path):
    sentinel = "paper-fetch-private-runtime-28137"
    test_file = tmp_path / "test_runtime_failure.py"
    test_file.write_text("""import json
import os
from pathlib import Path
from paper_fetch.runtime import RuntimeContext

def test_failure():
    with RuntimeContext(env={"API_KEY": os.environ["REPR_TEST_SECRET"]}) as context:
        Path("diagnostic.json").write_text(json.dumps({"runtime": repr(context)}))
        assert context is None
""")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-q",
            "--showlocals",
            "--junitxml=report.xml",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
            "REPR_TEST_SECRET": sentinel,
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1
    assert "RuntimeContext(" in result.stdout
    for content in (
        result.stdout,
        result.stderr,
        (tmp_path / "report.xml").read_text(),
        (tmp_path / "diagnostic.json").read_text(),
    ):
        assert sentinel not in content
