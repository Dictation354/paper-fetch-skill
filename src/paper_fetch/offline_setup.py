"""Post-install browser preparation and opt-in configuration (never a fetch hook)."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import ctypes.util
import getpass
import io
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import warnings

from dotenv import dotenv_values
from dotenv.parser import parse_stream

from .image_tools.convert import _probe_working_binary, convert_source_image_path_to_png
from .image_tools.paths import ghostscript_binary_candidates, vips_binary_candidates

CREDENTIAL_KEYS = ("ELSEVIER_API_KEY", "WILEY_TDM_CLIENT_TOKEN")
TOOL_KEYS = {
    "ghostscript": "PAPER_FETCH_GHOSTSCRIPT_BIN",
    "libvips": "PAPER_FETCH_VIPS_BIN",
}
# SONAMEs are the evidence; package names are only suggestions resolved against APT.
BROWSER_LIBRARIES = {
    "libgtk-3.so.0": ("libgtk-3-0t64", "libgtk-3-0"),
    "libgdk-3.so.0": ("libgtk-3-0t64", "libgtk-3-0"),
    "libgobject-2.0.so.0": ("libglib2.0-0t64", "libglib2.0-0"),
    "libdbus-1.so.3": ("libdbus-1-3",),
    "libdbus-glib-1.so.2": ("libdbus-glib-1-2",),
    "libX11.so.6": ("libx11-6",),
    "libX11-xcb.so.1": ("libx11-xcb1",),
    "libxcb.so.1": ("libxcb1",),
    "libXcomposite.so.1": ("libxcomposite1",),
    "libXdamage.so.1": ("libxdamage1",),
    "libXfixes.so.3": ("libxfixes3",),
    "libXrandr.so.2": ("libxrandr2",),
    "libXrender.so.1": ("libxrender1",),
    "libXext.so.6": ("libxext6",),
    "libXcursor.so.1": ("libxcursor1",),
    "libXi.so.6": ("libxi6",),
    "libXtst.so.6": ("libxtst6",),
    "libXt.so.6": ("libxt6t64", "libxt6"),
    "libasound.so.2": ("libasound2t64", "libasound2"),
    "libpangocairo-1.0.so.0": ("libpangocairo-1.0-0",),
    "libcairo.so.2": ("libcairo2",),
    "libgdk_pixbuf-2.0.so.0": ("libgdk-pixbuf-2.0-0",),
    "libfontconfig.so.1": ("libfontconfig1",),
    "libfreetype.so.6": ("libfreetype6",),
    "libstdc++.so.6": ("libstdc++6",),
}


def protect(path: Path) -> None:
    """Protect before writing secrets, including replacement files on Windows."""
    if os.name == "nt":
        system = Path(os.environ["SystemRoot"]) / "System32"
        identity = subprocess.check_output(
            [str(system / "whoami.exe"), "/user", "/fo", "csv", "/nh"]
        )
        # The SID is ASCII regardless of the username or console code page.
        match = re.search(rb'"(S-1-[0-9-]+)"', identity)
        if match is None:
            raise RuntimeError("Cannot determine the current Windows user SID")
        sid = match.group(1).decode("ascii")
        rights = "(OI)(CI)F" if path.is_dir() else "F"
        subprocess.run(
            [
                str(system / "icacls.exe"),
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"*{sid}:{rights}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def atomic_write(path: Path, text: str) -> None:
    if path.is_symlink():
        raise ValueError("Refusing to replace a symbolic-link configuration file")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".optional-", dir=path.parent)
    temporary = Path(name)
    try:
        os.close(fd)
        protect(temporary)
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def update_env(path: Path, updates: dict[str, str], *, readonly: bool = False) -> None:
    updates = {key: value for key, value in updates.items() if value}
    if not updates:
        return
    if readonly:
        raise PermissionError(
            "External env is read-only; configure the named keys manually"
        )
    if not set(updates) <= set(CREDENTIAL_KEYS) | set(TOOL_KEYS.values()):
        raise ValueError("Unsupported optional configuration key")
    original = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    # Parse complete bindings, including multiline values; remove every duplicate.
    kept = "".join(
        b.original.string
        for b in parse_stream(io.StringIO(original))
        if b.key not in updates
    )
    for key, value in updates.items():
        # dotenv's double-quoted decoder supports these escapes. Interpolation is
        # disabled by paper-fetch's config reader and the offline activate script.
        value = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        kept = kept.rstrip("\n") + f'\n{key}="{value}"\n'
    atomic_write(path, kept)


@contextmanager
def tool_environment(env: dict[str, str]):
    previous = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(env)
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def verify_image(tool: str, binary: Path, env: dict[str, str]) -> None:
    """Use the application's converter, then decode the actual PNG output."""
    import pymupdf

    if _probe_working_binary([binary], ["--version"], env=env).binary is None:
        raise RuntimeError("Selected image tool cannot run")
    with tempfile.TemporaryDirectory(prefix="paper-fetch-image-check-") as directory:
        root = Path(directory)
        source = root / ("sample.eps" if tool == "ghostscript" else "sample.tiff")
        if tool == "ghostscript":
            source.write_bytes(
                b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 8 8\n1 0 0 setrgbcolor\n0 0 8 8 rectfill\nshowpage\n%%EOF\n"
            )
        else:
            # Minimal baseline uncompressed RGB TIFF, no extra image dependency.
            tags = [
                (256, 4, 1, 8),
                (257, 4, 1, 8),
                (258, 3, 3, 134),
                (259, 3, 1, 1),
                (262, 3, 1, 2),
                (273, 4, 1, 140),
                (277, 3, 1, 3),
                (278, 4, 1, 8),
                (279, 4, 1, 192),
                (284, 3, 1, 1),
            ]
            source.write_bytes(
                b"II"
                + struct.pack("<HIH", 42, 8, 10)
                + b"".join(struct.pack("<HHII", *tag) for tag in tags)
                + struct.pack("<IHHH", 0, 8, 8, 8)
                + b"\xff\0\0" * 64
            )
        with tool_environment(
            {**env, TOOL_KEYS[tool]: str(binary), "PAPER_FETCH_EPS_DPI": "72"}
        ):
            result = convert_source_image_path_to_png(source, root / "result.png")
        if result is None:
            raise RuntimeError("Image conversion returned no result")
        if not (root / "result.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Image conversion did not produce a PNG")
        output = pymupdf.Pixmap(str(root / "result.png"))
        if (output.width, output.height) != (8, 8) or output.pixel(4, 4)[:3] != (
            255,
            0,
            0,
        ):
            raise RuntimeError("EPS/TIFF conversion produced an invalid PNG")


def detect_image(tool: str, env: dict[str, str]) -> tuple[Path | None, str]:
    candidates = (
        ghostscript_binary_candidates
        if tool == "ghostscript"
        else vips_binary_candidates
    )(env)
    if sys.platform == "darwin":
        name = "gs" if tool == "ghostscript" else "vips"
        candidates += [
            Path(prefix) / "bin" / name for prefix in ("/opt/homebrew", "/usr/local")
        ]
        brew = brew_binary()
        if brew:
            prefix = subprocess.run(
                [brew, "--prefix", "ghostscript" if tool == "ghostscript" else "vips"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if prefix.returncode == 0 and Path(prefix.stdout.strip()).is_absolute():
                candidates.append(Path(prefix.stdout.strip()) / "bin" / name)
    elif sys.platform == "win32" and tool == "ghostscript":
        from .offline_windows_tools import registered_ghostscript

        candidates += [
            Path(item["directory"]) / "bin/gswin64c.exe"
            for item in registered_ghostscript()
            if item.get("directory")
        ]
    state = "missing"
    for candidate in dict.fromkeys(candidates):
        probe = _probe_working_binary([candidate], ["--version"], env=env)
        if probe.binary is None:
            if probe.status != "missing":
                state = probe.status
            continue
        try:
            verify_image(tool, probe.binary, env)
        except Exception:
            state = "conversion_failed"
            continue
        return probe.binary.absolute(), "ready"
    return None, state


def brew_binary() -> str | None:
    return shutil.which("brew") or next(
        (
            str(p)
            for p in (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew"))
            if p.is_file()
        ),
        None,
    )


def library_status(soname: str) -> str:
    try:
        ctypes.CDLL(soname)
        return "ready"
    except OSError as exc:
        # A missing transitive dependency or loader problem is not proof that
        # this SONAME is absent. Non-glibc/unknown messages remain unverified.
        if str(exc).startswith(
            soname + ": cannot open shared object file: No such file"
        ):
            if (
                ctypes.util.find_library(soname.removeprefix("lib").split(".so")[0])
                is None
            ):
                return "missing"
        return "unverified"


def apt_package(names: tuple[str, ...]) -> str | None:
    if not shutil.which("apt-cache"):
        return None
    for name in names:
        result = subprocess.run(
            ["apt-cache", "policy", name],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "LC_ALL": "C"},
        )
        if result.returncode == 0 and any(
            line.strip().startswith("Candidate:")
            and line.strip() != "Candidate: (none)"
            for line in result.stdout.splitlines()
        ):
            return name
    return None


def apt_supported() -> bool:
    try:
        release = __import__("platform").freedesktop_os_release()
    except OSError:
        return False
    ids = {release.get("ID", ""), *release.get("ID_LIKE", "").split()}
    return bool(ids & {"debian", "ubuntu"}) and bool(shutil.which("apt-get"))


@contextmanager
def preparation_warnings():
    """Shorten only the known Canvas warning during installer launch checks."""
    from camoufox._warnings import LeakWarning, WARNINGS_DATA

    with warnings.catch_warnings():
        original = warnings.showwarning

        def showwarning(message, category, filename, lineno, file=None, line=None):
            if issubclass(category, LeakWarning) and str(message).startswith(
                WARNINGS_DATA["canvas_noise"]
            ):
                print(
                    "Camoufox: Canvas/WebGL readback returns random data (privacy fingerprint protection).",
                    file=file or sys.stderr,
                )
            else:
                original(message, category, filename, lineno, file=file, line=line)

        warnings.showwarning = showwarning
        yield


class Setup:
    def __init__(self, root: Path, env_file: Path, *, readonly: bool = False):
        self.root, self.env_file, self.readonly = root, env_file, readonly
        self.env = {
            **os.environ,
            **{
                k: v
                for k, v in dotenv_values(env_file, interpolate=False).items()
                if v is not None
            },
        }
        self.env["PAPER_FETCH_IMAGE_TOOLS_DIR"] = str(root / "image-tools")
        self.results: dict[str, tuple[str, str]] = {}

    def report(self, name: str, state: str, detail: str = "") -> None:
        line = f"{name}: {state}" + (f" — {detail}" if detail else "")
        if state not in {"checking", "preparing", "installing"}:
            self.results[name] = (state, detail)
        print(line, flush=True)

    def result_lines(self) -> str:
        return "\n".join(
            f"{name}: {state}" + (f" — {detail}" if detail else "")
            for name, (state, detail) in self.results.items()
        )

    def step(self, name: str, action) -> None:
        try:
            action()
        except (KeyboardInterrupt, EOFError):
            self.report(name, "cancelled", "Core installation is preserved")
        except Exception as exc:
            # Do not serialize exceptions: env parser/process errors can carry secrets.
            self.report(
                name, "failed", f"{type(exc).__name__}; core installation is preserved"
            )

    def save_credentials(self, values: dict[str, str]) -> None:
        for key in CREDENTIAL_KEYS:
            value = values.get(key, "")
            if self.readonly:
                self.report(
                    key,
                    "skipped",
                    f"External env is read-only: configure {key} in {self.env_file}",
                )
            elif value:
                update_env(self.env_file, {key: value})
                self.report(
                    key, "completed", "Saved privately; restart running hosts/MCP"
                )
            else:
                self.report(key, "skipped", "Existing value preserved")

    def save_tool(self, tool: str, binary: Path) -> None:
        if self.readonly:
            self.report(
                tool,
                "ready",
                f"Conversion verified: {binary}; external env is read-only; set {TOOL_KEYS[tool]}={binary}",
            )
        else:
            update_env(self.env_file, {TOOL_KEYS[tool]: str(binary)})
            self.env[TOOL_KEYS[tool]] = str(binary)
            self.report(tool, "ready", f"Conversion verified: {binary}")

    def image(self, tool: str, *, selected: bool | None = None) -> None:
        binary, state = detect_image(tool, self.env)
        if binary:
            self.save_tool(tool, binary)
            if sys.platform == "win32":
                from .offline_windows_tools import record_reused

                record_reused(self, tool, binary)
            return
        self.report(tool, state)
        if sys.platform == "win32":
            if not selected:
                self.report(tool, "skipped")
                return
            from .offline_windows_tools import install_tool

            install_tool(self, tool)
            return
        package = "ghostscript" if tool == "ghostscript" else "libvips-tools"
        if sys.platform == "darwin":
            package = "ghostscript" if tool == "ghostscript" else "vips"
            brew = brew_binary()
            if not brew:
                self.report(
                    tool,
                    "skipped",
                    "Install Homebrew yourself: https://brew.sh/ ; then brew install "
                    + package,
                )
                return
            command = [brew, "install", package]
            detail = "Homebrew prefix; network; normal user, no sudo"
        elif apt_supported():
            candidate = apt_package((package,))
            if not candidate:
                self.report(
                    tool,
                    "unverified",
                    f"APT package unavailable; refresh sources yourself, then sudo apt-get install {package}",
                )
                return
            command = ["sudo", "apt-get", "install", "--", candidate]
            detail = "system package directories; network; sudo prompts for password"
        else:
            self.report(
                tool,
                "skipped",
                f"Install {package} with your distribution's package manager",
            )
            return
        if selected is None:
            selected = confirm(f"Install {tool}? {detail}\n{shlex.join(command)}")
        if not selected:
            self.report(tool, "skipped")
            return
        self.install_packages(tool, command)
        binary, state = detect_image(tool, self.env)
        if binary:
            self.save_tool(tool, binary)
        elif self.results.get(tool, (None, ""))[0] != "failed":
            self.report(
                tool, state, f"Not ready; retry manually: {shlex.join(command)}"
            )

    def install_packages(self, label: str, command: list[str]) -> None:
        self.report(label, "installing", shlex.join(command))
        try:
            status = subprocess.run(command, check=False).returncode
        except OSError:
            status = -1
        if status:
            self.report(
                label,
                "failed",
                f"Exit {status}; packages already installed are preserved. Retry: {shlex.join(command)}",
            )

    def browser_libraries(self) -> None:
        if sys.platform != "linux":
            self.report(
                "Browser system libraries",
                "unverified",
                "Use local launch validation; no Linux packages or quarantine changes",
            )
            return
        missing = []
        for soname in BROWSER_LIBRARIES:
            state = library_status(soname)
            if state != "ready":
                self.report(soname, state)
            if state == "missing":
                missing.append(soname)
        if not missing:
            self.report(
                "Browser library detection",
                "completed",
                "Local launch remains the functional check",
            )
            return
        if not apt_supported():
            self.report(
                "Browser libraries",
                "unverified",
                "Ask your distribution's package manager to provide: "
                + ", ".join(missing),
            )
            return
        packages = []
        for soname in missing:
            package = apt_package(BROWSER_LIBRARIES[soname])
            if package:
                packages.append(package)
            else:
                self.report(
                    soname,
                    "unverified",
                    "APT candidate unavailable: "
                    + " / ".join(BROWSER_LIBRARIES[soname]),
                )
        if not packages:
            return
        command = ["sudo", "apt-get", "install", "--", *sorted(set(packages))]
        if not confirm(
            "Install browser system libraries? Network, system directories; sudo alone receives your password.\n"
            + shlex.join(command)
        ):
            self.report("Browser libraries", "skipped")
            return
        self.install_packages("Browser libraries", command)
        for soname in missing:
            self.report(
                soname,
                library_status(soname),
                "Rechecked after APT; local launch still required",
            )

    def browser(self, *, selected: bool | None = None) -> None:
        """Prepare and validate through the real backend with temporary state."""
        if selected is None:
            selected = confirm(
                "Prepare and locally test Camoufox + Byparr in the user cache?"
            )
        if not selected:
            self.report(
                "Camoufox", "skipped", "Runtime automatic preparation remains enabled"
            )
            return
        from .offline_browsers import prepare

        prepare(self, selection="all", interactive=True)

    def terminal(self) -> None:
        print(
            f"Optional configuration. Core installation is complete. Credentials: {self.env_file}\nBlank credentials preserve existing values; all installs default to No."
        )

        def credentials():
            if self.readonly:
                self.save_credentials({})
                return
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                for key in CREDENTIAL_KEYS:
                    value = getpass.getpass(
                        f"{key} (hidden, blank preserves existing): "
                    )
                    if value:
                        update_env(self.env_file, {key: value})
                        self.report(key, "completed", "Saved privately")
                    else:
                        self.report(key, "skipped", "Existing value preserved")

        self.step("Credentials", credentials)
        for tool in TOOL_KEYS:
            self.step(tool, lambda tool=tool: self.image(tool))

    def summary(self) -> str:
        return (
            "Core installation preserved. Optional configuration results:\n"
            + self.result_lines()
            + "\nRestart running hosts/MCP to reload configuration.\n"
        )


def confirm(prompt: str) -> bool:
    return input(prompt + " [y/N]: ").strip().lower() in {"y", "yes"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--reuse-env-file", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument(
        "--prepare-byparr",
        action="store_true",
        help="Prepare managed Byparr and Camoufox components",
    )
    parser.add_argument(
        "--prepare-flaresolverr", action="store_true", help=argparse.SUPPRESS
    )

    def browser_selection(value):
        if value == "flaresolverr":
            raise argparse.ArgumentTypeError(
                "FlareSolverr was removed; use --prepare-byparr or --prepare-browsers byparr. See docs/browser-backends.md#migration."
            )
        return value

    parser.add_argument(
        "--prepare-browsers",
        choices=("all", "camoufox", "byparr"),
        type=browser_selection,
    )
    parser.add_argument("--initialize-request", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--cleanup-tools", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_flaresolverr:
        parser.error(
            "FlareSolverr was removed; use --prepare-byparr or --prepare-browsers byparr. See docs/browser-backends.md#migration."
        )
    if args.initialize_request:
        args.initialize_request.mkdir(exist_ok=False)
        protect(args.initialize_request)
        return 0
    if args.prepare_byparr:
        args.prepare_browsers = "byparr"
    if not args.prepare_browsers and (
        args.non_interactive
        or (
            not args.request
            and not args.cleanup_tools
            and not (sys.stdin.isatty() and sys.stdout.isatty())
        )
    ):
        print(
            "Optional configuration skipped (non-interactive). No downloads or elevation. Runtime automatic browser preparation remains enabled."
        )
        return 0
    try:
        setup = Setup(
            args.install_root.absolute(),
            args.env_file or args.install_root / "offline.env",
            readonly=args.reuse_env_file,
        )
    except Exception:
        if args.request:
            args.request.unlink(missing_ok=True)
        message = "Optional configuration failed to read configuration; core installation is preserved.\n"
        if args.prepare_browsers:
            message = (
                "Browser preparation: not ready\n"
                "Failed to read configuration; core installation is preserved.\n"
                f"Retry: {browser_command(args.install_root.absolute(), args.env_file or args.install_root / 'offline.env', args.prepare_browsers)}\n"
            )
        print(message)
        if args.result:
            atomic_write(args.result, message)
        return 0
    try:
        if args.prepare_browsers:
            from .config import resolve_runtime_env
            from .offline_browsers import prepare

            setup.env = resolve_runtime_env(env_file=setup.env_file).values
            interactive = (
                not args.non_interactive and sys.stdin.isatty() and sys.stdout.isatty()
            )
            with tool_environment(setup.env):
                setup.step(
                    "Browsers",
                    lambda: prepare(
                        setup, selection=args.prepare_browsers, interactive=interactive
                    ),
                )
        elif args.cleanup_tools:
            from .offline_windows_tools import cleanup_tools

            setup.step("Optional tools cleanup", lambda: cleanup_tools(setup))
        elif args.request:
            try:
                lines = args.request.read_text(encoding="utf-8-sig").splitlines()
                if len(lines) != 5 or any(
                    value not in {"0", "1"} for value in lines[2:]
                ):
                    raise ValueError("Invalid request")
            finally:
                args.request.unlink(missing_ok=True)
            setup.step(
                "Credentials",
                lambda: setup.save_credentials(
                    dict(zip(CREDENTIAL_KEYS, lines[:2], strict=True))
                ),
            )
            lines[0] = lines[1] = ""
            for tool, selected in zip(TOOL_KEYS, lines[3:], strict=True):
                setup.step(
                    tool,
                    lambda tool=tool, selected=selected: setup.image(
                        tool, selected=selected == "1"
                    ),
                )
            if lines[2] == "1":
                setup.step("Byparr", lambda: setup.browser(selected=True))
        else:
            setup.terminal()
    except (KeyboardInterrupt, EOFError):
        setup.report("Optional configuration", "cancelled")
    except Exception as exc:
        setup.report("Optional configuration", "failed", type(exc).__name__)
    finally:
        if args.request:
            args.request.unlink(missing_ok=True)
    if args.prepare_browsers:
        from .offline_browsers import selected_backends

        backends = selected_backends(args.prepare_browsers)
        if any(
            name in setup.results for name in ("Browsers", "Optional configuration")
        ):
            state = "not ready"
        elif not backends:
            state = "skipped"
        elif all(
            setup.results.get(name, (None, ""))[0] == "ready" for name in backends
        ):
            state = "ready"
        else:
            state = "not ready"
        summary = (
            f"Browser preparation: {state}\n"
            "Core installation preserved. Browser preparation results:\n"
            + setup.result_lines()
            + "\n"
        )
        if state == "not ready":
            summary += (
                "Retry: "
                + browser_command(setup.root, setup.env_file, args.prepare_browsers)
                + "\nRuntime on-demand repair remains enabled.\n"
            )
    else:
        summary = setup.summary()
    print(summary)
    if args.result:
        atomic_write(args.result, summary)
    return 0


def browser_command(root: Path, env_file: Path, selection: str) -> str:
    installed_python = root / (
        "runtime/python.exe" if os.name == "nt" else "runtime/paper-fetch-python"
    )
    command = [
        str(installed_python) if installed_python.is_file() else sys.executable,
        "-m",
        "paper_fetch.offline_setup",
        "--install-root",
        str(root),
        "--env-file",
        str(env_file),
        "--prepare-browsers",
        selection,
    ]
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


if __name__ == "__main__":
    raise SystemExit(main())
