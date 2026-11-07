#!/usr/bin/env python3
"""Assemble pinned private browser sources/dependencies on the native build host."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def build(destination: Path, *, frozen: Path | None = None) -> None:
    from paper_fetch.providers.browser_runtime.platforms import supported_platform
    from paper_fetch.providers.browser_runtime.byparr_preparation import (
        PreparationBudget,
        prepare_source,
        runtime_location,
        valid_cache,
    )

    if not supported_platform():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="paper-fetch-component-") as directory:
        cache = Path(directory)
        _, _, identity = runtime_location(cache)
        if frozen is not None:
            source = frozen / "browser-components" / "byparr"
            if not valid_cache(source, identity):
                raise ValueError("Frozen Byparr component is missing or corrupt")
        else:
            source = prepare_source(cache, PreparationBudget(600))
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            source, destination, ignore=shutil.ignore_patterns("__pycache__")
        )


def inventory(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument(
        "--frozen", type=Path, default=os.environ.get("PAPER_FETCH_DEPENDENCY_SNAPSHOT")
    )
    args = parser.parse_args()
    build(args.destination, frozen=args.frozen)
    if args.destination.exists():
        print(json.dumps(inventory(args.destination), sort_keys=True))


if __name__ == "__main__":
    main()
