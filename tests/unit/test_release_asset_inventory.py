from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.prepare_release_assets import (
    offline_asset_names,
    prepare_stable_release,
    stable_asset_names,
    stable_input_mapping,
    write_checksums,
)


VERSION = "5.5.0"


def _write_stable_inputs(root: Path) -> None:
    for relative in stable_input_mapping(VERSION):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"payload:{relative.as_posix()}\n".encode())


def _read_checksum_manifest(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        assert separator
        assert name not in checksums
        checksums[name] = digest
    return checksums


def test_stable_assets_are_exactly_flattened_and_checksums_use_basenames(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "release-assets"
    _write_stable_inputs(input_root)

    expected = prepare_stable_release(
        input_root=input_root,
        output_dir=output_dir,
        version=VERSION,
    )

    assert expected == stable_asset_names(VERSION)
    assert len(expected) == 31
    assert {path.name for path in output_dir.iterdir()} == {
        *expected,
        "SHA256SUMS",
    }
    assert all(path.is_file() for path in output_dir.iterdir())
    checksums = _read_checksum_manifest(output_dir / "SHA256SUMS")
    assert set(checksums) == set(expected)
    assert all("/" not in name and "\\" not in name for name in checksums)
    for name, digest in checksums.items():
        assert digest == hashlib.sha256((output_dir / name).read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "mutation, expected_fragment",
    [
        ("missing", "missing="),
        ("extra", "extra="),
        ("collision", "basename collision"),
    ],
)
def test_stable_asset_input_rejects_missing_extra_and_basename_collision(
    tmp_path: Path,
    mutation: str,
    expected_fragment: str,
) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "release-assets"
    _write_stable_inputs(input_root)
    if mutation == "missing":
        next(iter(input_root.glob("python/*.whl"))).unlink()
    elif mutation == "extra":
        extra = input_root / "offline/unexpected.bin"
        extra.write_bytes(b"extra")
    else:
        collision = input_root / "unexpected/dependency-manifest.json"
        collision.parent.mkdir()
        collision.write_bytes(b"collision")

    with pytest.raises(ValueError, match=expected_fragment):
        prepare_stable_release(
            input_root=input_root,
            output_dir=output_dir,
            version=VERSION,
        )

    assert not output_dir.exists()


def test_flat_offline_inventory_rejects_nested_or_unknown_assets(
    tmp_path: Path,
) -> None:
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    for name in offline_asset_names():
        (asset_dir / name).write_bytes(name.encode())
    nested = asset_dir / "nested/unexpected.bin"
    nested.parent.mkdir()
    nested.write_bytes(b"extra")

    with pytest.raises(ValueError, match="extra="):
        write_checksums(asset_dir, offline_asset_names())

    assert not (asset_dir / "SHA256SUMS").exists()


def test_flat_offline_inventory_writes_exact_checksum_set(tmp_path: Path) -> None:
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    for name in offline_asset_names():
        (asset_dir / name).write_bytes(name.encode())

    checksum_path = write_checksums(asset_dir, offline_asset_names())

    assert set(_read_checksum_manifest(checksum_path)) == set(offline_asset_names())
