"""EPS/TIFF conversion helpers backed by Ghostscript and libvips."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse
from collections.abc import Mapping

from ..http.headers import header_value
from ..utils import normalize_text
from .paths import (
    ghostscript_binary_candidates,
    image_tool_timeout_seconds,
    vips_binary_candidates,
)

_DOS_EPS_MAGIC = b"\xc5\xd0\xd3\xc6"
_POSTSCRIPT_PREFIX_RE = re.compile(rb"^\s*%!")
_TIFF_MAGICS = (b"II*\x00", b"MM\x00*")


class ImageConversionFailure(RuntimeError):
    """Raised when an external source image cannot be converted."""


@dataclass(frozen=True)
class SourceImageConversion:
    body: bytes
    content_type: str
    source_format: str
    tool: str


def source_image_format_from_payload(
    body: bytes | bytearray | None,
    *,
    content_type: str | None = None,
    source_url: str | None = None,
) -> str:
    payload = bytes(body or b"")
    normalized_content_type = normalize_text(content_type).split(";", 1)[0].lower()
    parsed_source = urllib.parse.urlparse(source_url or "")
    suffix = Path(parsed_source.path or source_url or "").suffix.lower()

    if payload.startswith(_DOS_EPS_MAGIC) or _POSTSCRIPT_PREFIX_RE.match(payload[:256]):
        return "eps"
    if normalized_content_type in {
        "application/postscript",
        "application/eps",
        "image/x-eps",
        "image/eps",
    }:
        return "eps"
    if suffix == ".eps":
        return "eps"

    if payload.startswith(_TIFF_MAGICS):
        return "tiff"
    if normalized_content_type in {"image/tiff", "image/tif"}:
        return "tiff"
    if suffix in {".tif", ".tiff"}:
        return "tiff"

    return ""


def _working_binary(candidates: list[Path], probe_args: list[str]) -> Path | None:
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            process = subprocess.run(
                [str(candidate), *probe_args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                env=_tool_env(candidate),
                timeout=image_tool_timeout_seconds(),
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if process.returncode == 0:
            return candidate
    return None


def _tool_env(binary: Path) -> dict[str, str]:
    env = os.environ.copy()
    parts = list(binary.resolve().parents)
    root = next(
        (
            parent
            for parent in parts
            if (parent / "share" / "ghostscript").exists()
            or (parent / "usr" / "share" / "ghostscript").exists()
            or (parent / "lib").exists()
            or (parent / "usr" / "lib").exists()
        ),
        None,
    )
    if root is None:
        return env

    usr_root = (
        root / "usr" if (root / "usr" / "share" / "ghostscript").exists() else root
    )
    lib_dirs = [
        usr_root / "lib" / "x86_64-linux-gnu",
        root / "lib" / "x86_64-linux-gnu",
        usr_root / "lib",
        root / "lib",
    ]
    existing_ld = env.get("LD_LIBRARY_PATH", "")
    ld_values = [str(path) for path in lib_dirs if path.exists()]
    if ld_values:
        env["LD_LIBRARY_PATH"] = ":".join(
            [*ld_values, *([existing_ld] if existing_ld else [])]
        )

    gs_share = usr_root / "share" / "ghostscript"
    versions = (
        sorted(path for path in gs_share.glob("*") if path.is_dir())
        if gs_share.exists()
        else []
    )
    if versions:
        version_root = versions[-1]
        gs_lib_values = [
            version_root / "Resource" / "Init",
            version_root / "lib",
            version_root / "Resource",
        ]
        env["GS_LIB"] = ":".join(str(path) for path in gs_lib_values if path.exists())
    return env


def _ghostscript_binary() -> Path:
    binary = _working_binary(ghostscript_binary_candidates(), ["--version"])
    if binary is None:
        raise ImageConversionFailure("Ghostscript is unavailable for EPS conversion.")
    return binary


def _vips_binary() -> Path:
    binary = _working_binary(vips_binary_candidates(), ["--version"])
    if binary is None:
        raise ImageConversionFailure("libvips is unavailable for TIFF conversion.")
    return binary


def _run(args: list[str], *, env: Mapping[str, str] | None = None) -> None:
    timeout = image_tool_timeout_seconds()
    try:
        process = subprocess.run(
            args,
            capture_output=True,
            check=False,
            env=dict(env) if env is not None else None,
            timeout=timeout,
        )
    except OSError as exc:
        raise ImageConversionFailure(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise ImageConversionFailure(
            f"{Path(args[0]).name} timed out after {timeout} seconds."
        ) from exc
    if process.returncode != 0:
        message = process.stderr.decode("utf-8", errors="replace").strip()
        raise ImageConversionFailure(
            message or f"{Path(args[0]).name} exited with {process.returncode}."
        )


def _convert_eps_to_png(input_path: Path, output_path: Path) -> str:
    binary = _ghostscript_binary()
    dpi = normalize_text(os.environ.get("PAPER_FETCH_EPS_DPI")) or "600"
    _run(
        [
            str(binary),
            "-q",
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-dEPSCrop",
            "-sDEVICE=pngalpha",
            f"-r{dpi}",
            f"-sOutputFile={output_path}",
            str(input_path),
        ],
        env=_tool_env(binary),
    )
    return "ghostscript"


def _convert_tiff_to_png(input_path: Path, output_path: Path) -> str:
    binary = _vips_binary()
    _run(
        [str(binary), "copy", str(input_path), str(output_path)], env=_tool_env(binary)
    )
    return "libvips"


def convert_source_image_response_to_png(
    response: Mapping[str, object],
    *,
    source_url: str,
) -> SourceImageConversion | None:
    body = response.get("body", b"")
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    headers = response.get("headers")
    content_type = header_value(
        headers if isinstance(headers, Mapping) else None, "content-type"
    )
    source_format = source_image_format_from_payload(
        body,
        content_type=content_type,
        source_url=source_url,
    )
    if source_format not in {"eps", "tiff"}:
        return None

    suffix = ".eps" if source_format == "eps" else ".tif"
    with tempfile.TemporaryDirectory(prefix="paper_fetch_image_convert_") as tmpdir:
        input_path = Path(tmpdir) / f"source{suffix}"
        output_path = Path(tmpdir) / "converted.png"
        input_path.write_bytes(bytes(body))
        tool = (
            _convert_eps_to_png(input_path, output_path)
            if source_format == "eps"
            else _convert_tiff_to_png(input_path, output_path)
        )
        converted = output_path.read_bytes()
    if not converted:
        raise ImageConversionFailure("Image conversion produced an empty PNG.")
    return SourceImageConversion(
        body=converted,
        content_type="image/png",
        source_format=source_format,
        tool=tool,
    )


__all__ = [
    "ImageConversionFailure",
    "SourceImageConversion",
    "convert_source_image_response_to_png",
    "source_image_format_from_payload",
]
