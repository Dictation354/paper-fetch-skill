"""Install optional external formula-conversion backends."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from .paths import (
    FORMULA_NODE_SCRIPT_NAME,
    FORMULA_NODE_WORKER_SCRIPT_NAME,
    bundled_formula_resources,
    default_user_formula_tools_dir,
    TEXMATH_EXECUTABLE_NAMES,
)


def log(message: str) -> None:
    print(f"\033[1;34m==>\033[0m {message}")


def warn(message: str) -> None:
    print(f"\033[1;33m!!\033[0m {message}", file=os.sys.stderr)


def _temporary_log_path(log_prefix: str) -> Path:
    fd, log_path = tempfile.mkstemp(prefix=log_prefix, suffix=".log")
    os.close(fd)
    return Path(log_path)


def _remove_log_file(log_file: Path) -> None:
    try:
        log_file.unlink(missing_ok=True)
    except OSError as exc:
        warn(f"Could not remove build log {log_file}: {exc}")


def _run_with_log(log_prefix: str, args: list[str], *, cwd: Path | None = None) -> bool:
    log_file = _temporary_log_path(log_prefix)
    try:
        with log_file.open("w", encoding="utf-8") as handle:
            process = subprocess.run(
                args,
                cwd=str(cwd) if cwd else None,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if process.returncode == 0:
            _remove_log_file(log_file)
            return True
        warn(f"{' '.join(args[:2])} failed. Build log: {log_file}")
        return False
    except OSError as exc:
        warn(f"Could not run {' '.join(args)}: {exc}")
        _remove_log_file(log_file)
        return False


def have_working_texmath(path: Path) -> bool:
    if not path.exists() or not os.access(path, os.X_OK):
        return False
    process = subprocess.run(
        [str(path), "--help"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return process.returncode == 0


def texmath_target_path(target_dir: Path) -> Path:
    name = "texmath.exe" if os.name == "nt" else "texmath"
    return target_dir / "bin" / name


def stage_bundled_node_workspace(target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    resource_root = bundled_formula_resources()
    for name in (FORMULA_NODE_SCRIPT_NAME, FORMULA_NODE_WORKER_SCRIPT_NAME, "package.json", "package-lock.json"):
        resource = resource_root.joinpath(name)
        payload = resource.read_bytes()
        destination = target_dir / name
        if destination.exists() and destination.read_bytes() == payload:
            continue
        destination.write_bytes(payload)
    return target_dir


def reuse_texmath_from_path(target_dir: Path) -> bool:
    system_texmath = next(
        (candidate for name in TEXMATH_EXECUTABLE_NAMES if (candidate := shutil.which(name))),
        None,
    )
    if not system_texmath:
        return False
    source = Path(system_texmath)
    if not have_working_texmath(source):
        return False
    target = texmath_target_path(target_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target != source:
        target.unlink(missing_ok=True)
        if os.name == "nt":
            shutil.copy2(source, target)
        else:
            target.symlink_to(source)
    log(f"Using existing texmath at {source}")
    return True


def install_texmath_with_cabal(target_dir: Path) -> bool:
    cabal = shutil.which("cabal")
    if not cabal:
        return False
    log("Attempting to install texmath with cabal")
    subprocess.run([cabal, "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return _run_with_log(
        "texmath-cabal-",
        [
            cabal,
            "install",
            "texmath",
            "-fexecutable",
            f"--installdir={target_dir / 'bin'}",
            "--install-method=copy",
            "--overwrite-policy=always",
            "--package-env=none",
        ],
    )


def install_texmath_with_stack(target_dir: Path) -> bool:
    stack = shutil.which("stack")
    if not stack:
        return False
    log("Attempting to install texmath with stack")
    return _run_with_log(
        "texmath-stack-",
        [
            stack,
            "install",
            "texmath",
            "--flag",
            "texmath:executable",
            "--local-bin-path",
            str(target_dir / "bin"),
        ],
    )


def ensure_texmath(target_dir: Path) -> bool:
    target = texmath_target_path(target_dir)
    if have_working_texmath(target):
        log(f"Formula backend ready: texmath ({target})")
        return True
    if reuse_texmath_from_path(target_dir):
        return True
    if install_texmath_with_cabal(target_dir) or install_texmath_with_stack(target_dir):
        if have_working_texmath(target):
            log(f"Formula backend ready: texmath ({target})")
            return True
        warn("texmath build reported success but the installed binary could not be executed.")
    return False


def ensure_mathml_to_latex(target_dir: Path, *, install_node: bool) -> bool:
    if not install_node:
        warn("Skipping mathml-to-latex fallback because --no-node was set.")
        return False
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node:
        warn("node not found; mathml-to-latex fallback is unavailable.")
        return False
    if not npm:
        warn("npm not found; mathml-to-latex fallback is unavailable.")
        return False

    workspace = stage_bundled_node_workspace(target_dir)
    if (workspace / "node_modules" / "mathml-to-latex").exists() and (workspace / "node_modules" / "katex").exists():
        log(f"Using existing mathml-to-latex Node dependencies in {workspace}")
        return True

    log(f"Installing Node dependencies for mathml-to-latex fallback in {workspace}")
    if _run_with_log("mathml-to-latex-", [npm, "install", "--omit=dev", "--silent"], cwd=workspace):
        log("Formula backend ready: mathml-to-latex")
        return True
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install optional external formula backends for paper-fetch.")
    parser.add_argument(
        "--target-dir",
        help="Directory that should store formula backend assets. Defaults to the paper-fetch user data directory.",
    )
    parser.add_argument("--no-node", action="store_true", help="Skip the Node mathml-to-latex fallback install.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target_dir = Path(args.target_dir).expanduser() if args.target_dir else default_user_formula_tools_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    if ensure_texmath(target_dir):
        return 0

    warn("texmath is unavailable; falling back to mathml-to-latex.")
    if ensure_mathml_to_latex(target_dir, install_node=not args.no_node):
        return 0

    warn("No external MathML-to-LaTeX backend is available. The built-in Python renderer will be used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
