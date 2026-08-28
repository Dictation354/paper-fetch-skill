"""EPS/TIFF conversion helpers backed by Ghostscript and libvips."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import urllib.parse
from collections.abc import Mapping

from ..http.headers import header_value
from ..reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    IMAGE_CONVERSION_BACKEND_ERROR,
    IMAGE_CONVERSION_BACKEND_MISSING,
    IMAGE_CONVERSION_BACKEND_READY,
    IMAGE_CONVERSION_BACKEND_TIMEOUT,
    IMAGE_CONVERSION_FAILED,
)
from ..utils import normalize_text
from .paths import (
    _clear_image_tool_path_caches,
    ghostscript_binary_candidates,
    image_tool_timeout_seconds,
    vips_binary_candidates,
)

_DOS_EPS_MAGIC = b"\xc5\xd0\xd3\xc6"
_POSTSCRIPT_PREFIX_RE = re.compile(rb"^\s*%!")
_TIFF_MAGICS = (b"II*\x00", b"MM\x00*")
_WORKING_BINARY_CACHE: dict[tuple[object, ...], _WorkingBinaryProbe] = {}
_WORKING_BINARY_CACHE_LOCK = threading.RLock()
_TOOL_ENV_OVERLAY_CACHE: dict[tuple[object, ...], dict[str, str]] = {}
_TOOL_ENV_OVERLAY_CACHE_LOCK = threading.RLock()


class ImageConversionFailure(RuntimeError):
    """Raised when an external source image cannot be converted."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str = IMAGE_CONVERSION_FAILED,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class SourceImageConversion:
    body: bytes
    content_type: str
    source_format: str
    tool: str


@dataclass(frozen=True)
class SourceImagePathConversion:
    path: Path
    content_type: str
    source_format: str
    tool: str
    output_bytes: int


@dataclass(frozen=True)
class ImageConversionBackendProbe:
    backend: str
    source_formats: tuple[str, ...]
    status: str
    available: bool
    reason_code: str
    message: str
    candidate_count: int
    timeout_seconds: int

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "source_formats": list(self.source_formats),
            "status": self.status,
            "available": self.available,
            "reason_code": self.reason_code,
            "message": self.message,
            "candidate_count": self.candidate_count,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class _WorkingBinaryProbe:
    binary: Path | None
    status: str
    reason_code: str
    message: str
    candidate_count: int
    timeout_seconds: int


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


def _path_fingerprint(path: Path) -> tuple[str, bool, int, int]:
    try:
        stat_result = path.stat()
    except OSError:
        return (str(path), False, 0, 0)
    return (
        str(path),
        True,
        int(stat_result.st_mtime_ns),
        int(stat_result.st_size),
    )


def _working_binary_cache_key(
    candidates: list[Path],
    probe_args: list[str],
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[object, ...]:
    active_env = os.environ if env is None else env
    return (
        tuple(str(candidate) for candidate in candidates),
        tuple(_path_fingerprint(candidate) for candidate in candidates),
        tuple(probe_args),
        image_tool_timeout_seconds(active_env),
        active_env.get("LD_LIBRARY_PATH", ""),
        active_env.get("GS_LIB", ""),
    )


def _probe_working_binary(
    candidates: list[Path],
    probe_args: list[str],
    *,
    env: Mapping[str, str] | None = None,
) -> _WorkingBinaryProbe:
    active_env = os.environ if env is None else env
    timeout = image_tool_timeout_seconds(active_env)
    existing_candidates = [candidate for candidate in candidates if candidate.exists()]
    timed_out = False
    failed = False
    for candidate in existing_candidates:
        try:
            process = subprocess.run(
                [str(candidate), *probe_args],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                env=_tool_env(candidate, env=active_env),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            continue
        except OSError:
            failed = True
            continue
        if process.returncode == 0:
            return _WorkingBinaryProbe(
                binary=candidate,
                status="ready",
                reason_code=IMAGE_CONVERSION_BACKEND_READY,
                message="Local image conversion backend is executable.",
                candidate_count=len(existing_candidates),
                timeout_seconds=timeout,
            )
        failed = True

    if timed_out:
        return _WorkingBinaryProbe(
            binary=None,
            status="error",
            reason_code=IMAGE_CONVERSION_BACKEND_TIMEOUT,
            message="Local image conversion backend probe timed out.",
            candidate_count=len(existing_candidates),
            timeout_seconds=timeout,
        )
    if failed:
        return _WorkingBinaryProbe(
            binary=None,
            status="error",
            reason_code=IMAGE_CONVERSION_BACKEND_ERROR,
            message="Local image conversion backend candidates failed their version probe.",
            candidate_count=len(existing_candidates),
            timeout_seconds=timeout,
        )
    return _WorkingBinaryProbe(
        binary=None,
        status="not_configured",
        reason_code=IMAGE_CONVERSION_BACKEND_MISSING,
        message="No local image conversion backend executable was found.",
        candidate_count=0,
        timeout_seconds=timeout,
    )


def _working_binary_probe(
    candidates: list[Path],
    probe_args: list[str],
    *,
    env: Mapping[str, str] | None = None,
) -> _WorkingBinaryProbe:
    cache_key = _working_binary_cache_key(candidates, probe_args, env=env)
    with _WORKING_BINARY_CACHE_LOCK:
        cached = _WORKING_BINARY_CACHE.get(cache_key)
        if cached is not None:
            return cached
        probe = _probe_working_binary(candidates, probe_args, env=env)
        _WORKING_BINARY_CACHE[cache_key] = probe
        return probe


def _tool_env_root(binary: Path) -> Path | None:
    parts = list(binary.resolve().parents)
    return next(
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


def _tool_env_overlay_cache_key(
    binary: Path, env: Mapping[str, str] | None = None
) -> tuple[object, ...]:
    active_env = os.environ if env is None else env
    resolved = binary.resolve()
    parents = tuple(
        (
            str(parent),
            _path_fingerprint(parent / "share" / "ghostscript"),
            _path_fingerprint(parent / "usr" / "share" / "ghostscript"),
            _path_fingerprint(parent / "lib"),
            _path_fingerprint(parent / "usr" / "lib"),
        )
        for parent in resolved.parents
    )
    return (
        str(resolved),
        _path_fingerprint(resolved),
        active_env.get("LD_LIBRARY_PATH", ""),
        active_env.get("GS_LIB", ""),
        parents,
    )


def _tool_env_overlay(
    binary: Path, env: Mapping[str, str] | None = None
) -> dict[str, str]:
    active_env = os.environ if env is None else env
    cache_key = _tool_env_overlay_cache_key(binary, active_env)
    with _TOOL_ENV_OVERLAY_CACHE_LOCK:
        cached = _TOOL_ENV_OVERLAY_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

    overlay: dict[str, str] = {}
    root = _tool_env_root(binary)
    if root is None:
        with _TOOL_ENV_OVERLAY_CACHE_LOCK:
            _TOOL_ENV_OVERLAY_CACHE[cache_key] = {}
        return {}
    usr_root = (
        root / "usr" if (root / "usr" / "share" / "ghostscript").exists() else root
    )
    lib_dirs = [
        usr_root / "lib" / "x86_64-linux-gnu",
        root / "lib" / "x86_64-linux-gnu",
        usr_root / "lib",
        root / "lib",
    ]
    existing_ld = active_env.get("LD_LIBRARY_PATH", "")
    ld_values = [str(path) for path in lib_dirs if path.exists()]
    if ld_values:
        overlay["LD_LIBRARY_PATH"] = ":".join(
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
        overlay["GS_LIB"] = ":".join(
            str(path) for path in gs_lib_values if path.exists()
        )
    with _TOOL_ENV_OVERLAY_CACHE_LOCK:
        _TOOL_ENV_OVERLAY_CACHE[cache_key] = dict(overlay)
    return overlay


def _tool_env(binary: Path, *, env: Mapping[str, str] | None = None) -> dict[str, str]:
    active_env = dict(os.environ if env is None else env)
    active_env.update(_tool_env_overlay(binary, active_env))
    return active_env


def _clear_image_tool_caches() -> None:
    _clear_image_tool_path_caches()
    with _WORKING_BINARY_CACHE_LOCK:
        _WORKING_BINARY_CACHE.clear()
    with _TOOL_ENV_OVERLAY_CACHE_LOCK:
        _TOOL_ENV_OVERLAY_CACHE.clear()


def _ghostscript_binary() -> Path:
    probe = _working_binary_probe(ghostscript_binary_candidates(), ["--version"])
    if probe.binary is None:
        raise ImageConversionFailure(
            "Ghostscript is unavailable for EPS conversion.",
            reason_code=probe.reason_code,
        )
    return probe.binary


def _vips_binary() -> Path:
    probe = _working_binary_probe(vips_binary_candidates(), ["--version"])
    if probe.binary is None:
        raise ImageConversionFailure(
            "libvips is unavailable for TIFF conversion.",
            reason_code=probe.reason_code,
        )
    return probe.binary


def probe_image_conversion_backends(
    env: Mapping[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Probe EPS/TIFF conversion executables without converting user assets."""

    probes = (
        (
            "ghostscript",
            ("eps",),
            _working_binary_probe(
                ghostscript_binary_candidates(env), ["--version"], env=env
            ),
        ),
        (
            "libvips",
            ("tiff",),
            _working_binary_probe(vips_binary_candidates(env), ["--version"], env=env),
        ),
    )
    return {
        backend: ImageConversionBackendProbe(
            backend=backend,
            source_formats=source_formats,
            status=probe.status,
            available=probe.binary is not None,
            reason_code=probe.reason_code,
            message=probe.message,
            candidate_count=probe.candidate_count,
            timeout_seconds=probe.timeout_seconds,
        ).to_dict()
        for backend, source_formats, probe in probes
    }


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
        raise ImageConversionFailure(
            str(exc), reason_code=IMAGE_CONVERSION_BACKEND_ERROR
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ImageConversionFailure(
            f"{Path(args[0]).name} timed out after {timeout} seconds.",
            reason_code=IMAGE_CONVERSION_BACKEND_TIMEOUT,
        ) from exc
    if process.returncode != 0:
        message = process.stderr.decode("utf-8", errors="replace").strip()
        raise ImageConversionFailure(
            message or f"{Path(args[0]).name} exited with {process.returncode}.",
            reason_code=IMAGE_CONVERSION_FAILED,
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


def convert_source_image_path_to_png(
    input_path: Path,
    output_path: Path,
    *,
    content_type: str | None = None,
    source_url: str = "",
    max_output_bytes: int | None = None,
) -> SourceImagePathConversion | None:
    """Convert an existing source file without materializing it in Python."""

    input_path = Path(input_path)
    output_path = Path(output_path)
    try:
        with input_path.open("rb") as source:
            prefix = source.read(8192)
    except OSError as exc:
        raise ImageConversionFailure(str(exc)) from exc
    source_format = source_image_format_from_payload(
        prefix,
        content_type=content_type,
        source_url=source_url,
    )
    if source_format not in {"eps", "tiff"}:
        return None
    if output_path.exists():
        raise ImageConversionFailure(
            f"Image conversion output already exists: {output_path}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tool = (
            _convert_eps_to_png(input_path, output_path)
            if source_format == "eps"
            else _convert_tiff_to_png(input_path, output_path)
        )
        output_bytes = output_path.stat().st_size
        if output_bytes <= 0:
            raise ImageConversionFailure("Image conversion produced an empty PNG.")
        if max_output_bytes is not None and output_bytes > max(0, max_output_bytes):
            raise ImageConversionFailure(
                "Converted PNG exceeded the configured per-asset byte limit.",
                reason_code=ASSET_BYTES_PER_ASSET_EXCEEDED,
            )
        with output_path.open("rb+") as converted:
            os.fsync(converted.fileno())
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise
    return SourceImagePathConversion(
        path=output_path,
        content_type="image/png",
        source_format=source_format,
        tool=tool,
        output_bytes=output_bytes,
    )


__all__ = [
    "ImageConversionBackendProbe",
    "ImageConversionFailure",
    "SourceImageConversion",
    "SourceImagePathConversion",
    "convert_source_image_path_to_png",
    "convert_source_image_response_to_png",
    "probe_image_conversion_backends",
    "source_image_format_from_payload",
]
