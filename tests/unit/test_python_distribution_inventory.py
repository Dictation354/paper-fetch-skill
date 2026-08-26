from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
from pathlib import PurePosixPath
import tarfile
import zipfile

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "quality" / "python-distribution-inventory.json"
FIXTURE_INVENTORY = {
    "distribution": "paper-fetch-skill",
    "console_scripts": {},
    "package_data": [],
    "static_skill": [],
}
FIXTURE_PACKAGE_MEMBERS = {"paper_fetch/__init__.py"}


def _record_payload(contents: dict[str, bytes], record_path: str) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    for name, payload in sorted(contents.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
        writer.writerow(
            [name, f"sha256={digest.rstrip(b'=').decode('ascii')}", len(payload)]
        )
    writer.writerow([record_path, "", ""])
    return output.getvalue().encode("utf-8")


def _write_wheel(
    tmp_path: Path,
    *,
    extra: str | None = None,
    omit: str | None = None,
) -> Path:
    wheel = tmp_path / "paper_fetch_skill-1.0-py3-none-any.whl"
    dist_info = "paper_fetch_skill-1.0.dist-info"
    record_path = f"{dist_info}/RECORD"
    contents = {
        "paper_fetch/__init__.py": b"",
        f"{dist_info}/METADATA": (
            b"Metadata-Version: 2.1\nName: paper-fetch-skill\nVersion: 1.0\n"
        ),
        f"{dist_info}/WHEEL": (
            b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ),
        f"{dist_info}/entry_points.txt": b"[console_scripts]\n",
        f"{dist_info}/licenses/LICENSE": b"fixture license\n",
        f"{dist_info}/top_level.txt": b"paper_fetch\n",
    }
    if extra is not None:
        contents[extra] = b"malicious extra\n"
    if omit is not None and omit != record_path:
        contents.pop(omit)
    if omit != record_path:
        contents[record_path] = _record_payload(contents, record_path)
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, payload in sorted(contents.items()):
            archive.writestr(name, payload)
    return wheel


def _sdist_sources() -> set[str]:
    return {
        "LICENSE",
        "MANIFEST.in",
        "README.md",
        "pyproject.toml",
        "src/paper_fetch/__init__.py",
        "src/paper_fetch_skill.egg-info/PKG-INFO",
        "src/paper_fetch_skill.egg-info/SOURCES.txt",
        "src/paper_fetch_skill.egg-info/dependency_links.txt",
        "src/paper_fetch_skill.egg-info/entry_points.txt",
        "src/paper_fetch_skill.egg-info/requires.txt",
        "src/paper_fetch_skill.egg-info/top_level.txt",
    }


def _write_sdist(
    tmp_path: Path,
    *,
    extra: str | None = None,
    omit: str | None = None,
) -> Path:
    root = "paper_fetch_skill-1.0"
    metadata = b"Metadata-Version: 2.1\nName: paper-fetch-skill\nVersion: 1.0\n"
    sources = "".join(f"{name}\n" for name in sorted(_sdist_sources())).encode()
    files = {
        f"{root}/LICENSE": b"fixture license\n",
        f"{root}/MANIFEST.in": b"",
        f"{root}/PKG-INFO": metadata,
        f"{root}/README.md": b"fixture\n",
        f"{root}/pyproject.toml": b"",
        f"{root}/setup.cfg": b"",
        f"{root}/src/paper_fetch/__init__.py": b"",
        f"{root}/src/paper_fetch_skill.egg-info/PKG-INFO": metadata,
        f"{root}/src/paper_fetch_skill.egg-info/SOURCES.txt": sources,
        f"{root}/src/paper_fetch_skill.egg-info/dependency_links.txt": b"",
        f"{root}/src/paper_fetch_skill.egg-info/entry_points.txt": (
            b"[console_scripts]\n"
        ),
        f"{root}/src/paper_fetch_skill.egg-info/requires.txt": b"",
        f"{root}/src/paper_fetch_skill.egg-info/top_level.txt": b"paper_fetch\n",
    }
    if extra is not None:
        files[f"{root}/{extra}"] = b"malicious extra\n"
    if omit is not None:
        files.pop(f"{root}/{omit}")
    directories = {
        parent.as_posix()
        for name in files
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }
    sdist = tmp_path / f"{root}.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        for directory in sorted(directories):
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            archive.addfile(info)
        for name, content in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return sdist


def test_distribution_inventory_matches_source_tree() -> None:
    from scripts.verify_python_distribution import verify_source

    payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
    verify_source(REPO_ROOT, payload)


def test_distribution_inventory_rejects_unlisted_package_data() -> None:
    from scripts.verify_python_distribution import _assert_exact

    with pytest.raises(ValueError, match=r"extra=\['unexpected.json'\]"):
        _assert_exact(
            "fixture", {"expected.json", "unexpected.json"}, {"expected.json"}
        )


def test_minimal_complete_archives_match_exact_inventory(tmp_path: Path) -> None:
    from scripts.verify_python_distribution import verify_sdist, verify_wheel

    verify_wheel(
        _write_wheel(tmp_path),
        FIXTURE_INVENTORY,
        expected_package_members=FIXTURE_PACKAGE_MEMBERS,
    )
    verify_sdist(
        _write_sdist(tmp_path),
        FIXTURE_INVENTORY,
        expected_package_members=FIXTURE_PACKAGE_MEMBERS,
    )


@pytest.mark.parametrize(
    "extra",
    [
        "paper_fetch/unexpected.py",
        "unexpected-top-level.txt",
        "paper_fetch_skill-1.0.data/data/unexpected.txt",
        "paper_fetch_skill-1.0.dist-info/EXTRA",
        "evil-1.0.dist-info/METADATA",
    ],
)
def test_wheel_inventory_rejects_every_unknown_archive_member(
    tmp_path: Path,
    extra: str,
) -> None:
    from scripts.verify_python_distribution import verify_wheel

    with pytest.raises(ValueError, match=r"wheel archive inventory mismatch.*extra="):
        verify_wheel(
            _write_wheel(tmp_path, extra=extra),
            FIXTURE_INVENTORY,
            expected_package_members=FIXTURE_PACKAGE_MEMBERS,
        )


@pytest.mark.parametrize(
    "missing",
    [
        "paper_fetch_skill-1.0.dist-info/METADATA",
        "paper_fetch_skill-1.0.dist-info/RECORD",
    ],
)
def test_wheel_inventory_requires_core_dist_info_members(
    tmp_path: Path,
    missing: str,
) -> None:
    from scripts.verify_python_distribution import verify_wheel

    with pytest.raises(ValueError, match=r"wheel archive inventory mismatch.*missing="):
        verify_wheel(
            _write_wheel(tmp_path, omit=missing),
            FIXTURE_INVENTORY,
            expected_package_members=FIXTURE_PACKAGE_MEMBERS,
        )


@pytest.mark.parametrize(
    "extra",
    [
        "unexpected-top-level.txt",
        "docs/secret.md",
        "src/unexpected.py",
        "src/paper_fetch/unexpected.py",
        "src/paper_fetch_skill.egg-info/EXTRA",
    ],
)
def test_sdist_inventory_rejects_every_unknown_regular_member(
    tmp_path: Path,
    extra: str,
) -> None:
    from scripts.verify_python_distribution import verify_sdist

    with pytest.raises(
        ValueError, match=r"sdist archive files inventory mismatch.*extra="
    ):
        verify_sdist(
            _write_sdist(tmp_path, extra=extra),
            FIXTURE_INVENTORY,
            expected_package_members=FIXTURE_PACKAGE_MEMBERS,
        )


def test_sdist_inventory_requires_root_and_egg_info_metadata(tmp_path: Path) -> None:
    from scripts.verify_python_distribution import verify_sdist

    with pytest.raises(
        ValueError, match=r"sdist archive files inventory mismatch.*missing="
    ):
        verify_sdist(
            _write_sdist(tmp_path, omit="src/paper_fetch_skill.egg-info/PKG-INFO"),
            FIXTURE_INVENTORY,
            expected_package_members=FIXTURE_PACKAGE_MEMBERS,
        )
