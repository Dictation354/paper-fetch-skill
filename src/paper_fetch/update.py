"""Update an official installation using one verified GitHub Release."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import BROWSER_HEADLESS_ENV_VAR, ENV_FILE_ENV_VAR, build_runtime_env
from .version import package_version

REPOSITORY = "Dictation354/paper-fetch-skill"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


@dataclass(frozen=True)
class Installation:
    root: Path
    manifest: dict[str, Any]
    packages: dict[str, str]


def version_key(value: str) -> tuple:
    """Compare project release tags, including development/prerelease builds."""
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?"
        r"(?:\.post(\d+))?(?:\.dev(\d+))?(?:\+[a-zA-Z0-9.-]+)?",
        value.strip(),
    )
    if not match:
        raise ValueError(f"无法识别版本：{value}")
    major, minor, patch, pre, pre_number, post, dev = match.groups()
    pre_order = {"a": 0, "b": 1, "rc": 2}
    # A bare dev build sorts before alpha; final/post builds sort after rc.
    phase = pre_order[pre] if pre else (-1 if dev and post is None else 3)
    return (
        int(major),
        int(minor),
        int(patch),
        phase,
        int(pre_number or 0),
        int(post) if post is not None else -1,
        int(dev) if dev is not None else float("inf"),
    )


def find_installation() -> Installation:
    module = Path(__file__).resolve()
    for root in module.parents:
        expected = (
            root / "runtime" / "site-packages" / "paper_fetch" / "update.py",
            root / "runtime" / "Lib" / "site-packages" / "paper_fetch" / "update.py",
        )
        if module not in expected:
            continue
        manifest = json.loads(
            (root / "offline-manifest.json").read_text(encoding="utf-8-sig")
        )
        installer = json.loads(
            (root / "installer/manifest.json").read_text(encoding="utf-8-sig")
        )
        if not isinstance(manifest, dict) or not isinstance(installer, dict):
            raise ValueError("安装 manifest 无效")
        target = manifest.get("target", {})
        packages = installer.get("packages", {})
        if not isinstance(target, dict) or not isinstance(packages, dict):
            raise ValueError("安装 manifest 无效")
        system = target.get("platform")
        if (
            manifest.get("schema_version") != 3
            or manifest.get("project") != "paper-fetch-skill"
            or installer.get("project") != "paper-fetch-skill"
            or system not in {"linux", "macos", "windows"}
            or manifest.get("name") != packages.get(f"{system}_manifest_name")
        ):
            raise ValueError("当前目录不是受支持的官方安装包")
        if system == "windows":
            if not (root / "runtime/python.exe").is_file():
                raise ValueError("缺少官方内嵌 Python")
        elif (
            manifest.get("entrypoint") != "install-offline.sh"
            or not (root / "runtime/python-bin").is_file()
        ):
            raise ValueError("缺少官方安装标记")
        return Installation(root, manifest, packages)
    source_root = module.parents[2]
    if (source_root / "pyproject.toml").is_file():
        raise ValueError(
            "当前为源码环境；请在原仓库运行 git pull，再在原 Python 环境运行 "
            "python -m pip install --upgrade .（保留原有 extras）。"
        )
    raise ValueError(
        "当前为 pip 或非官方安装环境；请在原 Python 环境运行 "
        "python -m pip install --upgrade paper-fetch-skill（保留原有 extras）。"
    )


def installer_asset_name(installation: Installation) -> str:
    system = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(
        platform.system()
    )
    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    target = installation.manifest.get("target", {})
    if (
        sys.implementation.name != "cpython"
        or bool(getattr(sys, "abiflags", None))
        or sysconfig.get_config_var("Py_GIL_DISABLED")
        or target.get("platform") != system
        or target.get("arch") != arch
        or target.get("python_tag") != tag
    ):
        raise ValueError("当前平台、架构或 CPython ABI 与安装包不匹配")
    packages = installation.packages
    if system == "windows" and arch == "x86_64" and tag == "cp313":
        return packages["windows_setup_base_name"] + ".exe"
    if tag not in {"cp311", "cp312", "cp313", "cp314"} or not str(
        sysconfig.get_config_var("SOABI") or ""
    ).startswith(f"cpython-{tag[2:]}-"):
        raise ValueError("更新需要标准 GIL CPython 3.11–3.14 ABI")
    if system == "linux" and arch == "x86_64":
        return f"{packages['linux_offline_name_prefix']}-{tag}.sh"
    if system == "macos" and arch == "arm64":
        return f"{packages['macos_offline_name_prefix']}-{arch}-{tag}.tar.gz"
    raise ValueError("当前平台或架构没有官方更新安装包")


def _request(url: str) -> Request:
    return Request(
        url,
        headers={
            "User-Agent": f"paper-fetch-skill/{package_version()}",
            "Accept": "application/vnd.github+json"
            if url == LATEST_RELEASE_URL
            else "application/octet-stream",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )


def latest_release() -> dict[str, Any]:
    with urlopen(_request(LATEST_RELEASE_URL), timeout=30) as response:
        release = json.load(response)
    if (
        not isinstance(release, dict)
        or release.get("draft")
        or release.get("prerelease")
    ):
        raise ValueError("GitHub 未返回正式 Release")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not re.fullmatch(
        r"v?\d+\.\d+\.\d+(?:\.post\d+)?", tag
    ):
        raise ValueError("Release 缺少有效的正式版本 tag")
    return release


def release_asset_url(release: dict[str, Any], name: str) -> str:
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("Release 资产列表无效")
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"Release 缺少唯一资产：{name}")
    expected = f"https://github.com/{REPOSITORY}/releases/download/{quote(release['tag_name'], safe='')}/{quote(name, safe='')}"
    if matches[0].get("browser_download_url") != expected:
        raise ValueError(f"Release 资产下载地址无效：{name}")
    return expected


def download(url: str, destination: Path) -> str:
    digest = hashlib.sha256()
    with (
        urlopen(_request(url), timeout=60) as response,
        destination.open("wb") as output,
    ):
        while block := response.read(1024 * 1024):
            output.write(block)
            digest.update(block)
    return digest.hexdigest()


def verify_checksum(sums: Path, name: str, digest: str) -> None:
    matches = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *](.+)", line)
        if match and match[2] == name:
            matches.append(match[1].lower())
    if matches != [digest]:
        raise ValueError(f"SHA256 校验失败：{name}")


def unpack_macos(archive_path: Path, destination: Path) -> Path:
    """Preflight the entire archive; only directories and regular files are allowed."""
    bundle_name = archive_path.name.removesuffix(".tar.gz")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        paths: dict[str, bool] = {}
        for member in members:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
                or not path.parts
                or path.parts[0] != bundle_name
                or not (member.isdir() or member.isfile())
                or member.issym()
                or member.islnk()
                or member.issparse()
            ):
                raise ValueError(f"macOS 安装包包含不允许的路径或文件：{member.name}")
            key = path.as_posix().casefold()
            if key in paths:
                raise ValueError(f"macOS 安装包包含重复路径：{member.name}")
            paths[key] = member.isdir()
        for key in paths:
            if any(
                paths.get(parent.as_posix()) is False
                for parent in PurePosixPath(key).parents
            ):
                raise ValueError(f"macOS 安装包文件与目录冲突：{key}")
        installer = f"{bundle_name}/install-offline.sh".casefold()
        if paths.get(installer) is not False:
            raise ValueError("macOS 安装包缺少 install-offline.sh")
        # Manual extraction avoids restoring archive ownership, links or special modes.
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"无法读取安装包文件：{member.name}")
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)
    return destination / bundle_name / "install-offline.sh"


def run_update() -> int:
    temporary: Path | None = None
    handed_off = False
    try:
        installation = find_installation()
        name = installer_asset_name(installation)
        release = latest_release()
        current = package_version()
        version = release["tag_name"]
        if version_key(current) >= version_key(version):
            print(f"当前版本 {current} 已是最新或更新版本（最新正式版：{version}）。")
            return 0
        asset_url = release_asset_url(release, name)
        sums_url = release_asset_url(release, "SHA256SUMS")
        temporary = Path(tempfile.mkdtemp(prefix="paper-fetch-update-"))
        package = temporary / name
        sums = temporary / "SHA256SUMS"
        print(f"正在更新 {current} → {version}：{name}", flush=True)
        download(sums_url, sums)
        digest = download(asset_url, package)
        verify_checksum(sums, name, digest)
        if name.endswith(".exe"):
            subprocess.Popen(
                [str(package), f"/DIR={installation.root}"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200),
            )
            handed_off = True
            print(f"已启动安装向导；由向导报告升级结果。安装包：{package}")
            return 0
        installer = (
            unpack_macos(package, temporary / "unpacked")
            if name.endswith(".tar.gz")
            else package
        )
        runtime_env = build_runtime_env()
        headless = runtime_env.get(
            BROWSER_HEADLESS_ENV_VAR, ""
        ).strip().lower() not in {"0", "false", "no", "off"}
        command = [
            "bash",
            str(installer),
            "--install-dir",
            str(installation.root),
            f"--preset={'headless' if headless else 'headful'}",
            "--non-interactive",
        ]
        env_file = runtime_env.get(ENV_FILE_ENV_VAR, "").strip()
        if env_file:
            path = Path(env_file).expanduser().resolve()
            if path != (installation.root / "offline.env").resolve():
                command.extend(["--reuse-env-file", str(path)])
        env = dict(os.environ, PAPER_FETCH_OFFLINE_PYTHON_BIN=sys.executable)
        result = subprocess.run(command, env=env, check=False)
        if result.returncode:
            raise ValueError(f"安装器失败（退出码 {result.returncode}）")
        print(f"已更新至 {version}。")
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        tarfile.TarError,
        http.client.HTTPException,
        subprocess.SubprocessError,
    ) as error:
        print(f"更新失败：{error}", file=sys.stderr)
        return 1
    finally:
        if temporary is not None and not handed_off:
            shutil.rmtree(temporary, ignore_errors=True)
