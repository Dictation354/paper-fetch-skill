"""On-demand, verified FlareSolverr source/dependencies and ChromeDriver caches."""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import time
from typing import Any
import urllib.request
import zipfile

from filelock import FileLock, Timeout

from .types import BrowserRuntimeFailure

MANIFEST_PATH = Path(__file__).with_name("flaresolverr-manifest.json")
DRIVER_INDEX = "https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json"


class PreparationBudget:
    def __init__(self, seconds: float, runtime_context: Any = None):
        self.deadline = time.monotonic() + seconds
        self.context = runtime_context

    def remaining(self) -> float:
        if self.context is not None:
            self.context.raise_if_cancelled()
        remaining = self.deadline - time.monotonic()
        if self.context is not None:
            remaining = min(remaining, self.context.remaining_seconds(remaining))
        if remaining <= 0:
            raise BrowserRuntimeFailure(
                "flaresolverr_timeout",
                "FlareSolverr browser preparation/access deadline exhausted.",
            )
        return remaining

    def check(self):
        self.remaining()


@contextlib.contextmanager
def cache_lock(path: Path, budget: PreparationBudget):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path), thread_local=False)
    while True:
        budget.check()
        try:
            lock.acquire(timeout=0)
            break
        except Timeout:
            time.sleep(min(0.05, budget.remaining()))
    try:
        yield
    finally:
        lock.release()


def download(
    url: str, path: Path, budget: PreparationBudget, sha256: str | None = None
) -> str:
    print(f"FlareSolverr browser: downloading {url}", file=sys.stderr)
    digest = hashlib.sha256()
    with (
        urllib.request.urlopen(url, timeout=min(10, budget.remaining())) as response,
        path.open("wb") as output,
    ):
        while True:
            budget.check()
            block = response.read(256 * 1024)
            if not block:
                break
            output.write(block)
            digest.update(block)
    result = digest.hexdigest()
    if sha256 is not None and result != sha256:
        raise BrowserRuntimeFailure(
            "flaresolverr_checksum_mismatch", f"SHA-256 mismatch: {url}"
        )
    return result


def _destination(root: Path, name: str) -> Path:
    target = root / name
    if "\\" in name or target.is_absolute() and not target.is_relative_to(root):
        raise ValueError(f"Unsafe archive member: {name}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Unsafe archive member: {name}")
    return target


def extract_zip(archive: Path, root: Path, budget: PreparationBudget):
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            budget.check()
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Archive symlink: {info.filename}")
            target = _destination(root, info.filename)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)


def _inventory(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "ready.json" and "__pycache__" not in p.parts
    }


def valid_cache(root: Path, identity: str) -> bool:
    try:
        marker = json.loads((root / "ready.json").read_text())
        return (
            marker["identity"] == identity
            and bool(marker["files"])
            and all(
                hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
                for name, digest in marker["files"].items()
            )
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _publish(staged: Path, target: Path, identity: str):
    (staged / "ready.json").write_text(
        json.dumps({"identity": identity, "files": _inventory(staged)})
    )
    backup = target.with_name(target.name + ".previous")
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        target.rename(backup)
    try:
        staged.rename(target)
    except BaseException:
        if backup.exists():
            backup.rename(target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def runtime_location(cache: Path) -> tuple[Path, dict[str, Any], str]:
    raw = MANIFEST_PATH.read_bytes()
    manifest = json.loads(raw)
    identity = hashlib.sha256(
        raw
        + f"{sys.platform}-cp{sys.version_info.major}{sys.version_info.minor}".encode()
    ).hexdigest()
    return cache / "source" / identity, manifest, identity


def prepare_source(cache: Path, budget: PreparationBudget) -> Path:
    target, manifest, identity = runtime_location(cache)
    with cache_lock(target.with_suffix(".lock"), budget):
        if valid_cache(target, identity):
            return target
        stage = Path(tempfile.mkdtemp(prefix=".prepare-", dir=target.parent))
        try:
            archive = stage / "source.zip"
            download(
                manifest["source"]["url"], archive, budget, manifest["source"]["sha256"]
            )
            extract_zip(archive, stage, budget)
            archive.unlink()
            (stage / manifest["source"]["root"]).rename(stage / "upstream")
            libraries = stage / "lib"
            libraries.mkdir()
            for package in manifest["packages"]:
                if sys.platform not in package["platforms"]:
                    continue
                artifacts = [
                    a
                    for a in package["artifacts"]
                    if "python" not in a
                    or a["python"]
                    == f"{sys.version_info.major}{sys.version_info.minor}"
                ]
                if len(artifacts) != 1:
                    raise BrowserRuntimeFailure(
                        "flaresolverr_unsupported_python",
                        f"No locked artifact for {package['name']} on {sys.version}.",
                    )
                artifact = artifacts[0]
                archive = stage / artifact["filename"]
                download(artifact["url"], archive, budget, artifact["sha256"])
                if archive.suffix == ".whl":
                    extract_zip(archive, libraries, budget)
                else:
                    # func-timeout is pure Python but PyPI publishes only an sdist.
                    prefix = package["source_root"]
                    with tarfile.open(archive) as source:
                        for member in source.getmembers():
                            budget.check()
                            if member.name.startswith(prefix + "/") and member.isfile():
                                name = "func_timeout/" + member.name[len(prefix) + 1 :]
                                dest = _destination(libraries, name)
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                handle = source.extractfile(member)
                                if handle is None:
                                    raise ValueError(
                                        f"Archive member has no file: {member.name}"
                                    )
                                with (
                                    handle as src,
                                    dest.open("wb") as dst,
                                ):
                                    shutil.copyfileobj(src, dst)
                archive.unlink()
            budget.check()
            _publish(stage, target, identity)
            return target
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def prepare_driver(
    cache: Path, chrome_version: str, budget: PreparationBudget
) -> tuple[Path, str]:
    target = cache / "drivers" / sys.platform / chrome_version
    executable = "chromedriver.exe" if sys.platform == "win32" else "chromedriver"
    with cache_lock(target.with_suffix(".lock"), budget):
        if valid_cache(target, chrome_version):
            return target / executable, (target / "version").read_text()
        stage = Path(tempfile.mkdtemp(prefix=".driver-", dir=target.parent))
        try:
            index = stage / "index.json"
            download(DRIVER_INDEX, index, budget)
            build = ".".join(chrome_version.split(".")[:3])
            entry = json.loads(index.read_text())["builds"].get(build)
            if entry is None:
                raise BrowserRuntimeFailure(
                    "chromedriver_unavailable",
                    f"No official ChromeDriver for Chrome build {build}.",
                )
            platform_key = "win64" if sys.platform == "win32" else "linux64"
            asset = next(
                a
                for a in entry["downloads"]["chromedriver"]
                if a["platform"] == platform_key
            )
            archive = stage / "driver.zip"
            digest = download(asset["url"], archive, budget)
            extract_zip(archive, stage / "unpacked", budget)
            path = next((stage / "unpacked").rglob(executable))
            path.rename(stage / executable)
            (stage / executable).chmod(0o755)
            shutil.rmtree(stage / "unpacked")
            archive.unlink()
            index.unlink()
            (stage / "version").write_text(entry["version"])
            (stage / "download.json").write_text(
                json.dumps(
                    {
                        "url": asset["url"],
                        "sha256": digest,
                        "chrome_version": chrome_version,
                    }
                )
            )
            budget.check()
            _publish(stage, target, chrome_version)
            return target / executable, entry["version"]
        finally:
            if stage.exists():
                shutil.rmtree(stage)
