"""Pinned optional Windows tools, separate from the release payload inventory."""

from __future__ import annotations

import ctypes
from contextlib import suppress
import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile

from .offline_setup import atomic_write, protect, verify_image
from .image_tools.convert import _tool_env
from .providers.browser_runtime.preparation import _path_chain_has_link

INVENTORY = "optional-tools.json"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(asset: dict, target: Path) -> None:
    if not asset["url"].startswith("https://"):
        raise ValueError("Only HTTPS tool assets are supported")
    checksum = asset["sha256"]
    if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
        raise ValueError("Missing pinned SHA-256")
    try:
        with (
            urllib.request.urlopen(asset["url"], timeout=60) as response,
            target.open("xb") as output,
        ):
            if not response.url.startswith("https://"):
                raise ValueError("Insecure asset redirect")
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if digest(target) != checksum:
            raise ValueError("Asset SHA-256 mismatch")
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def safe_relative(value: str) -> Path:
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if (
        not posix.parts
        or posix.is_absolute()
        or windows.drive
        or "\\" in value
        or any(
            part in {".", ".."}
            or ":" in part
            or part.rstrip(" .") != part
            or part.split(".")[0].upper()
            in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "CONIN$",
                "CONOUT$",
                *[f"{prefix}{n}" for prefix in ("COM", "LPT") for n in "123456789¹²³"],
            }
            for part in posix.parts
        )
    ):
        raise ValueError("Unsafe optional tool path")
    if any(ord(c) < 32 for c in value):
        raise ValueError("Invalid path character")
    return Path(*posix.parts)


def extract_zip(archive: Path, destination: Path) -> None:
    """Validate the complete archive before extracting; never follow links."""
    with zipfile.ZipFile(archive) as bundle:
        names: set[str] = set()
        entries = []
        total = 0
        for member in bundle.infolist():
            relative = safe_relative(member.filename.rstrip("/"))
            mode = member.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError("ZIP links and special files are forbidden")
            # DOS reparse points and case-insensitive collisions are unsafe too.
            if (
                member.external_attr & 0x400
                or member.filename.casefold().rstrip("/") in names
            ):
                raise ValueError("ZIP reparse point or duplicate path")
            names.add(member.filename.casefold().rstrip("/"))
            total += member.file_size
            if total > 2 * 1024**3 or len(names) > 50000:
                raise ValueError("ZIP exceeds optional tool extraction limits")
            entries.append((member, relative))
        for member, relative in entries:
            target = destination / relative
            if _path_chain_has_link(destination, target):
                raise ValueError("ZIP destination contains a link")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)


def registered_ghostscript() -> list[dict[str, str]]:
    import winreg

    result = {}
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        for product in (
            "GPL Ghostscript",
            "Aladdin Ghostscript",
            "AFPL Ghostscript",
            "Artifex Ghostscript",
        ):
            for prefix in ("SOFTWARE\\", "SOFTWARE\\Artifex\\"):
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        prefix + product,
                        0,
                        winreg.KEY_READ | view,
                    )
                except FileNotFoundError:
                    continue
                with key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        version = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, version) as entry:
                            try:
                                dll = winreg.QueryValueEx(entry, "GS_DLL")[0]
                                directory = str(Path(dll).parent.parent)
                            except FileNotFoundError:
                                try:
                                    directory = winreg.QueryValueEx(entry, "")[0]
                                except FileNotFoundError:
                                    directory = ""
                        result[(version, directory)] = {
                            "version": version,
                            "directory": directory,
                        }
        # Keep a registration even when its DLL key is broken/missing: do not
        # overwrite that version's official system-wide uninstall registration.
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                0,
                winreg.KEY_READ | view,
            )
        except FileNotFoundError:
            continue
        with key:
            for index in range(winreg.QueryInfoKey(key)[0]):
                name = winreg.EnumKey(key, index)
                if not name.startswith("GPL Ghostscript "):
                    continue
                version = name.removeprefix("GPL Ghostscript ")
                if not any(v == version for v, _ in result):
                    result[(version, "")] = {"version": version, "directory": ""}
    return list(result.values())


def run_official(executable: Path, parameters: str = "") -> int:
    """Run the visible official installer/uninstaller, allowing its required UAC."""
    from ctypes import wintypes

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    info = ShellExecuteInfo()
    info.cbSize, info.fMask = (
        ctypes.sizeof(info),
        0x40 | 0x100,
    )  # NOCLOSEPROCESS | NOASYNC
    info.lpVerb, info.lpFile, info.lpParameters, info.nShow = (
        "runas",
        str(executable),
        parameters,
        1,
    )
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value
    finally:
        kernel.CloseHandle(info.hProcess)


def load_inventory(root: Path) -> dict:
    path = root / INVENTORY
    if not path.exists():
        return {"schema_version": 1, "tools": {}}
    if _path_chain_has_link(root, path):
        raise ValueError("Unsafe optional inventory path")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("tools"), dict):
        raise ValueError("Invalid optional tool inventory")
    return data


def record(
    setup, tool: str, asset: dict, directory: Path, *, owned: bool, status: str
) -> None:
    inventory = load_inventory(setup.root)
    files = {}
    directories = []
    if owned and directory.exists():
        for path in directory.rglob("*"):
            if _path_chain_has_link(directory, path):
                raise ValueError("Optional tool contains links")
            if path.is_file():
                files[path.relative_to(directory).as_posix()] = digest(path)
            elif path.is_dir():
                directories.append(path.relative_to(directory).as_posix())
    inventory["tools"][tool] = {
        "version": asset["version"],
        "url": asset["url"],
        "sha256": asset["sha256"],
        "directory": str(directory),
        "owned": owned,
        "status": status,
        "files": files,
        "directories": directories,
    }
    atomic_write(setup.root / INVENTORY, json.dumps(inventory, indent=2) + "\n")


def record_reused(setup, tool: str, binary: Path) -> None:
    inventory = load_inventory(setup.root)
    existing = inventory["tools"].get(tool)
    if existing and binary.resolve().is_relative_to(
        Path(existing["directory"]).resolve()
    ):
        existing["status"] = "ready"
    elif existing:
        # Keep ownership of any previously installed tree when a user switches
        # configuration to an external binary. Do not claim the external tool.
        existing["reused_binary"] = str(binary)
    else:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            env=_tool_env(binary, env=setup.env),
            timeout=30,
        )
        version = re.search(r"\d+\.\d+(?:\.\d+)?", result.stdout)
        inventory["tools"][tool] = {
            "version": version.group(0) if version else "unknown",
            "url": "existing PATH/configuration/official registration",
            "sha256": None,
            "directory": str(binary.parent.parent),
            "owned": False,
            "status": "ready",
            "files": {},
            "reused_binary": str(binary),
        }
    atomic_write(setup.root / INVENTORY, json.dumps(inventory, indent=2) + "\n")


def install_tool(setup, tool: str) -> None:
    manifest = json.loads(
        (setup.root / "installer/manifest.json").read_text(encoding="utf-8")
    )
    asset = manifest["optional_windows_tools"][tool]
    parent = setup.root / "image-tools" / tool
    version = safe_relative(asset["version"])
    if len(version.parts) != 1:
        raise ValueError("Invalid optional tool version")
    target = parent / version
    if _path_chain_has_link(setup.root, target):
        raise ValueError("Unsafe optional tool target")
    # Validate the ledger before any download/mutation; a malformed ledger must
    # not cause a later install to lose ownership of an existing tool.
    load_inventory(setup.root)
    if tool == "ghostscript":
        registered = [
            item
            for item in registered_ghostscript()
            if item["version"] == asset["version"]
        ]
        if registered:
            setup.report(
                tool,
                "skipped",
                "Target version is already registered; repair it with the official installer. Locations: "
                + ", ".join(item["directory"] or "unknown" for item in registered),
            )
            return
    if target.exists():
        # A failed/aborted previous install is never silently replaced.
        candidates = (
            list(target.rglob("vips.exe"))
            if tool == "libvips"
            else [target / "bin/gswin64c.exe"]
        )
        for candidate in candidates:
            if _path_chain_has_link(target, candidate):
                continue
            try:
                verify_image(tool, candidate, setup.env)
            except Exception:
                continue
            setup.save_tool(tool, candidate)
            return
        setup.report(
            tool,
            "skipped",
            f"Existing directory was preserved; repair manually: {target}",
        )
        return
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".download-", dir=parent) as temporary:
        staging = Path(temporary)
        protect(staging)
        archive = staging / ("installer.exe" if tool == "ghostscript" else "tool.zip")
        setup.report(
            tool, "downloading", f"{asset['version']} from {asset['url']} to {target}"
        )
        try:
            download(asset, archive)
        except Exception:
            setup.report(
                tool,
                "failed",
                "Download or SHA-256 verification failed; retry optional setup. Existing tools preserved",
            )
            return
        if tool == "libvips":
            extracted = staging / "extracted"
            extract_zip(archive, extracted)
            candidates = list(extracted.rglob("bin/vips.exe"))
            if len(candidates) != 1:
                raise ValueError("ZIP must contain exactly one bin/vips.exe")
            binary_relative = candidates[0].relative_to(extracted)
            verify_image(tool, candidates[0], setup.env)
            extracted.rename(target)
            record(setup, tool, asset, target, owned=True, status="ready")
            setup.save_tool(tool, target / binary_relative)
        else:
            setup.report(
                tool,
                "installing",
                "Official visible wizard requests administrator rights and writes system registry. /D target: "
                + str(target),
            )
            # NSIS requires /D last and unquoted, including paths with spaces.
            try:
                status = run_official(archive, "/D=" + str(target))
            except OSError:
                setup.report(
                    tool,
                    "failed",
                    f"Official installer/UAC was cancelled or could not start. Retry optional setup; inspect {target}",
                )
                return
            registered = [
                item
                for item in registered_ghostscript()
                if item["version"] == asset["version"] and item["directory"]
            ]
            directories = {Path(item["directory"]).resolve() for item in registered}
            if len(directories) != 1:
                if target.exists():
                    record(setup, tool, asset, target, owned=True, status="unverified")
                setup.report(
                    tool,
                    "failed",
                    f"Official installer exit {status}; installation location not verified. Inspect {target} and Windows Installed Apps",
                )
                return
            actual = directories.pop()
            owned = actual == target.absolute() and not _path_chain_has_link(
                setup.root, target
            )
            record(setup, tool, asset, actual, owned=owned, status="unverified")
            if status:
                setup.report(
                    tool,
                    "failed",
                    f"Official installer exit {status}; preserved at {actual}; repair with official installer",
                )
                return
            binary = actual / "bin/gswin64c.exe"
            verify_image(tool, binary, setup.env)
            record(setup, tool, asset, actual, owned=owned, status="ready")
            setup.save_tool(tool, binary)


def cleanup_tools(setup) -> None:
    inventory = load_inventory(setup.root)
    for tool, entry in list(inventory["tools"].items()):

        def cleanup(tool=tool, entry=entry):
            directory = Path(entry["directory"])
            version = safe_relative(entry["version"])
            expected = setup.root / "image-tools" / tool / version
            if (
                tool not in {"ghostscript", "libvips"}
                or not entry.get("owned")
                or directory != expected
                or _path_chain_has_link(setup.root, directory)
            ):
                setup.report(
                    tool, "preserved", f"Not an owned safe tool directory: {directory}"
                )
                return
            if tool == "ghostscript":
                if any(
                    _path_chain_has_link(directory, path)
                    for path in directory.rglob("*")
                ):
                    setup.report(
                        tool,
                        "preserved",
                        f"Tool tree contains a link; inspect before official uninstall: {directory}",
                    )
                    return
                registered = [
                    item
                    for item in registered_ghostscript()
                    if item["version"] == entry["version"]
                ]
                uninstaller = directory / "uninstgs.exe"
                if (
                    not registered
                    or any(
                        not item["directory"]
                        or Path(item["directory"]).resolve() != directory.resolve()
                        for item in registered
                    )
                    or _path_chain_has_link(directory, uninstaller)
                    or not uninstaller.is_file()
                    or entry["files"].get("uninstgs.exe") != digest(uninstaller)
                ):
                    setup.report(
                        tool,
                        "preserved",
                        f"Official registration/uninstaller mismatch; repair or uninstall via Windows Installed Apps: {directory}",
                    )
                    return
                # Official visible uninstaller: user may cancel UAC or its wizard.
                # _?= makes NSIS uninstall in place instead of spawning a TEMP
                # second stage whose parent exits before the work completes.
                status = run_official(uninstaller, "_?=" + str(directory))
                if status or any(
                    item["version"] == entry["version"]
                    for item in registered_ghostscript()
                ):
                    setup.report(
                        tool,
                        "preserved",
                        f"Official uninstall cancelled/failed (exit {status}): {directory}",
                    )
                    return
                if uninstaller.is_file() and digest(uninstaller) == entry["files"].get(
                    "uninstgs.exe"
                ):
                    uninstaller.unlink()
            else:
                # Validate all paths before deleting any; keep added/changed files.
                paths = [
                    (directory / safe_relative(name), checksum)
                    for name, checksum in entry["files"].items()
                ]
                # Only remove directories present when the tool was recorded,
                # plus ancestors of recorded files for older inventories. An
                # empty directory added by the user is still user-owned.
                directories = {
                    directory / safe_relative(name)
                    for name in entry.get("directories", [])
                }
                for path, _checksum in paths:
                    parent = path.parent
                    while parent != directory:
                        directories.add(parent)
                        parent = parent.parent
                for path in [*(path for path, _ in paths), *directories]:
                    if _path_chain_has_link(directory, path):
                        raise ValueError("Managed file path contains a link")
                for path, checksum in paths:
                    if path.is_file() and digest(path) == checksum:
                        path.unlink()
                for path in sorted(
                    directories, key=lambda p: len(p.parts), reverse=True
                ):
                    if path.is_dir() and not _path_chain_has_link(directory, path):
                        with suppress(OSError):
                            path.rmdir()
                with suppress(OSError):
                    directory.rmdir()
            del inventory["tools"][tool]
            atomic_write(setup.root / INVENTORY, json.dumps(inventory, indent=2) + "\n")
            setup.report(
                tool,
                "completed",
                f"Managed tool cleanup finished; any remaining user files are preserved at {directory}",
            )

        setup.step(tool, cleanup)
