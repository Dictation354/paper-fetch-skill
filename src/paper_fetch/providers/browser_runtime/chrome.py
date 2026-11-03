"""System Google Chrome discovery shared verbatim with the installers (stdlib only)."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

CHROME_ENV = "PAPER_FETCH_CHROME_BINARY_PATH"
CHROME_DOWNLOAD_URL = "https://www.google.com/chrome/"


@dataclass(frozen=True)
class SystemChrome:
    path: str
    version: str


def supported_platform() -> bool:
    return sys.platform in {"win32", "linux"} and platform.machine().lower() in {
        "amd64",
        "x86_64",
    }


def _windows_version(path: str) -> str:
    # chrome.exe --version can open the user's normal browser on Windows.
    from ctypes import wintypes

    version = cast(Any, ctypes).WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    version.GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    version.VerQueryValueW.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        raise ValueError("Chrome has no file version resource")
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, buffer):
        raise ValueError("Cannot read Chrome file version")
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(
        buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)
    ):
        raise ValueError("Cannot read Chrome file version")
    # Match the installer's product check without launching chrome.exe.
    translation = ctypes.c_void_p()
    if not version.VerQueryValueW(
        buffer,
        r"\VarFileInfo\Translation",
        ctypes.byref(translation),
        ctypes.byref(length),
    ):
        raise ValueError("Chrome has no product metadata")
    pair = ctypes.cast(translation, ctypes.POINTER(wintypes.WORD))
    key = f"\\StringFileInfo\\{pair[0]:04x}{pair[1]:04x}\\ProductName"
    product = ctypes.c_void_p()
    if (
        not version.VerQueryValueW(
            buffer, key, ctypes.byref(product), ctypes.byref(length)
        )
        or ctypes.wstring_at(product) != "Google Chrome"
    ):
        raise ValueError("not Google Chrome")
    words = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
    return f"{words[2] >> 16}.{words[2] & 65535}.{words[3] >> 16}.{words[3] & 65535}"


def _candidates(env: Mapping[str, str]):
    explicit = env.get(CHROME_ENV, "").strip()
    if explicit:
        yield explicit
        return
    if sys.platform == "win32":
        import winreg

        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(
                        hive,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                        0,
                        winreg.KEY_READ | view,
                    ) as key:
                        yield winreg.QueryValue(key, None)
                except OSError:
                    pass
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = env.get(variable)
            if root:
                yield str(Path(root) / "Google/Chrome/Application/chrome.exe")
        names = ("chrome.exe",)
    else:
        names = ("google-chrome", "google-chrome-stable")
    for name in names:
        path = shutil.which(name, path=env.get("PATH", os.defpath))
        if path:
            yield path
    if sys.platform != "win32":
        yield "/opt/google/chrome/chrome"
        yield "/usr/bin/google-chrome"
        yield "/usr/bin/google-chrome-stable"


def discover_chrome(
    env: Mapping[str, str] | None = None, *, timeout: float = 10
) -> SystemChrome:
    env = os.environ if env is None else env
    errors = []
    for value in dict.fromkeys(_candidates(env)):
        path = Path(value).expanduser()
        try:
            if not path.is_file() or (os.name != "nt" and not os.access(path, os.X_OK)):
                raise ValueError("not an executable file")
            if sys.platform == "win32":
                # Require Google Chrome product metadata as well as a version.
                version = _windows_version(str(path))
            else:
                result = subprocess.run(
                    [str(path), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=True,
                )
                if not result.stdout.startswith("Google Chrome "):
                    raise ValueError("not Google Chrome")
                match = re.search(r"\b\d+\.\d+\.\d+\.\d+\b", result.stdout)
                if match is None:
                    raise ValueError("Chrome version is unavailable")
                version = match.group()
            if int(version.split(".")[0]) < 115:
                raise ValueError("Chrome 115 or newer is required")
            return SystemChrome(str(path.absolute()), version)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            errors.append(f"{path}: {exc}")
    detail = "; ".join(errors)
    raise ValueError(
        f"System Google Chrome is required. {CHROME_ENV}: {detail or 'Chrome not found'}. Install Chrome from {CHROME_DOWNLOAD_URL} and rerun the installer/request."
    )


if __name__ == "__main__":
    if supported_platform():
        try:
            chrome = discover_chrome()
            print(f"Google Chrome {chrome.version}: {chrome.path}")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
