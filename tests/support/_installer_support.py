from __future__ import annotations
from pathlib import Path
import stat
import subprocess
import textwrap


def write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_posix_command_wrappers(staging: Path) -> None:
    """Generate the actual release launchers for installer process contracts."""
    builder = Path(__file__).resolve().parents[2] / "scripts/build-offline-package.sh"
    script = builder.read_text(encoding="utf-8")
    function = script.split("write_cmd_wrappers() {", 1)[1].split(
        "write_offline_readme()", 1
    )[0]
    subprocess.run(
        [
            "bash",
            "-c",
            "set -eu\nlog() { :; }\nwrite_cmd_wrappers() {"
            + function
            + '\nwrite_cmd_wrappers "$1"',
            "test-launchers",
            str(staging),
        ],
        check=True,
    )
