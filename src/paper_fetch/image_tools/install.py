"""Install or stage optional image conversion tools."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from collections.abc import Sequence

from .paths import (
    GHOSTSCRIPT_EXECUTABLE_NAMES,
    VIPS_EXECUTABLE_NAMES,
    default_user_image_tools_dir,
    image_tool_timeout_seconds,
    repo_root,
)


def log(message: str) -> None:
    print(f"\033[1;34m==>\033[0m {message}")


def warn(message: str) -> None:
    print(f"\033[1;33m!!\033[0m {message}", file=sys.stderr)


def _have_working_binary(path: Path, *args: str) -> bool:
    if not path.exists():
        return False
    try:
        process = subprocess.run(
            [str(path), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=image_tool_timeout_seconds(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return process.returncode == 0


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    if os.name == "nt":
        shutil.copy2(source, target)
    else:
        target.symlink_to(source)


def _stage_from_path(names: tuple[str, ...], target_dir: Path, probe_arg: str) -> bool:
    for name in names:
        system = shutil.which(name)
        if not system:
            continue
        source = Path(system)
        if not _have_working_binary(source, probe_arg):
            continue
        _link_or_copy(source, target_dir / "bin" / source.name)
        log(f"Using existing image tool at {source}")
        return True
    return False


def _copy_repo_runtime(
    name: str,
    target_dir: Path,
    *,
    repo_root_path: Path | None = None,
) -> bool:
    root = repo_root_path or repo_root()
    if root is None:
        return False
    source = root / ".venv" / name
    if not source.exists():
        return False
    target = target_dir / name
    target_dir.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=True)
    log(f"Staged repo-local {name} into {target}")
    return True


def ensure_ghostscript(
    target_dir: Path,
    *,
    offline_bundle: bool = False,
    repo_root_path: Path | None = None,
) -> bool:
    if not offline_bundle and _stage_from_path(
        GHOSTSCRIPT_EXECUTABLE_NAMES,
        target_dir,
        "--version",
    ):
        return True
    if _copy_repo_runtime(
        "ghostscript-runtime",
        target_dir,
        repo_root_path=repo_root_path,
    ):
        return True
    warn(
        "Ghostscript is unavailable; EPS Download Figure conversion will fall back "
        "to webpage JPGs."
    )
    return False


def ensure_vips(
    target_dir: Path,
    *,
    offline_bundle: bool = False,
    repo_root_path: Path | None = None,
) -> bool:
    if not offline_bundle and _stage_from_path(
        VIPS_EXECUTABLE_NAMES,
        target_dir,
        "--version",
    ):
        return True
    if _copy_repo_runtime(
        "libvips-runtime",
        target_dir,
        repo_root_path=repo_root_path,
    ):
        return True
    warn(
        "libvips is unavailable; TIFF Download Figure conversion will fall back "
        "to webpage JPGs."
    )
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install optional image conversion tools for paper-fetch."
    )
    parser.add_argument(
        "--target-dir",
        help="Directory that should store image conversion assets. Defaults to the paper-fetch user data directory.",
    )
    parser.add_argument(
        "--offline-bundle",
        action="store_true",
        help="Stage only repo-local relocatable runtimes; never link tools from the build host PATH.",
    )
    parser.add_argument(
        "--repo-root",
        help="Repository root to search for .venv image tool runtimes when --offline-bundle is set.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target_dir = (
        Path(args.target_dir).expanduser()
        if args.target_dir
        else default_user_image_tools_dir()
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    repo_root_path = Path(args.repo_root).expanduser() if args.repo_root else None

    ghostscript_ok = ensure_ghostscript(
        target_dir,
        offline_bundle=bool(args.offline_bundle),
        repo_root_path=repo_root_path,
    )
    vips_ok = ensure_vips(
        target_dir,
        offline_bundle=bool(args.offline_bundle),
        repo_root_path=repo_root_path,
    )
    if ghostscript_ok or vips_ok:
        log(f"Image conversion tools staged in {target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
