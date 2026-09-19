from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from scripts.scan_artifacts_for_secrets import scan_artifacts


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_controlled_pytest_failure_junit_cannot_render_live_secret(
    tmp_path: Path,
) -> None:
    sentinel = "paper-fetch-junit/+?=sentinel"
    junit_path = tmp_path / "pytest-junit.xml"
    test_path = tmp_path / "test_controlled_failure.py"
    test_path.write_text(
        """
import os
from tests.live._runtime_env import SecretSafeEnvironment

def test_controlled_failure():
    env = SecretSafeEnvironment({"ELSEVIER_API_KEY": os.environ["ELSEVIER_API_KEY"]})
    raise AssertionError(f"controlled failure env={env!r}")
""".lstrip(),
        encoding="utf-8",
    )
    process_env = dict(os.environ)
    process_env["ELSEVIER_API_KEY"] = sentinel
    process_env["PYTHONPATH"] = os.pathsep.join(
        (str(REPO_ROOT / "src"), str(REPO_ROOT))
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_path),
            "-q",
            "--confcutdir",
            str(tmp_path),
            f"--junitxml={junit_path}",
        ],
        cwd=tmp_path,
        env=process_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    persisted = junit_path.read_text(encoding="utf-8")
    combined = completed.stdout + completed.stderr + persisted
    assert sentinel not in combined
    assert quote(sentinel, safe="") not in combined
    report = scan_artifacts(
        [junit_path],
        env={"ELSEVIER_API_KEY": sentinel},
        env_names=["ELSEVIER_API_KEY"],
    )
    assert report["status"] == "clean"
