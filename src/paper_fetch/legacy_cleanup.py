"""Remove only positively identified paper-fetch legacy registrations and wrappers.

Kept dependency-free so online/offline installers can run this before importing the package.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib

LEGACY_MODULE = "paper_fetch.mcp.server"
MANAGED_MARKERS = (
    "# BEGIN paper-fetch installer managed",
    "# BEGIN paper-fetch offline managed",
)


def owned_wrapper(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return (
        LEGACY_MODULE in content or "from paper_fetch.mcp.server import main" in content
    )


def owned_entry(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    command = str(entry.get("command", ""))
    args = entry.get("args") or []
    basename = command.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if basename in {"paper-fetch-mcp", "paper-fetch-mcp.cmd", "paper-fetch-mcp.exe"}:
        return True
    if isinstance(args, list) and any(
        arg == "-m" and args[i + 1 : i + 2] == [LEGACY_MODULE]
        for i, arg in enumerate(args)
    ):
        return True
    return bool(command and owned_wrapper(Path(command).expanduser()))


def _write(path: Path, text: str):
    path = path.resolve()
    mode = path.stat().st_mode
    fd, temporary = tempfile.mkstemp(prefix=".paper-fetch-migrate-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def clean_json(path: Path, wrappers: set[Path]) -> bool:
    try:
        original = path.read_text(encoding="utf-8")
        data = json.loads(original)
    except (OSError, ValueError):
        return False
    changed = False

    def visit(node):
        nonlocal changed
        if not isinstance(node, dict):
            return
        for key, value in list(node.items()):
            if key in {"mcpServers", "mcp_servers"} and isinstance(value, dict):
                for name, entry in list(value.items()):
                    if owned_entry(entry):
                        command = entry.get("command")
                        if command:
                            wrappers.add(Path(command).expanduser())
                        del value[name]
                        changed = True
            elif isinstance(value, dict):
                visit(value)

    visit(data)
    if changed:
        _write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return changed


def clean_toml(path: Path, wrappers: set[Path]) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text)
    except (OSError, ValueError):
        return False
    servers = data.get("mcp_servers", {})
    if not isinstance(servers, dict):
        return False
    owned = {name for name, entry in servers.items() if owned_entry(entry)}
    for marker in MANAGED_MARKERS:
        end = marker.replace("BEGIN", "END")
        for match in re.finditer(
            re.escape(marker) + r"\n(.*?)" + re.escape(end), text, re.S
        ):
            try:
                marked = tomllib.loads(match.group(1)).get("mcp_servers", {})
            except ValueError:
                continue
            owned.update(marked)

    for name in owned:
        command = servers[name].get("command")
        if command:
            wrappers.add(Path(command).expanduser())
    if not owned:
        return False
    # Parse headers with tomllib too: quoted custom service names may contain dots.
    chunks = re.split(r"(?m)(?=^[ \t]*\[)", text)
    kept = []
    for chunk in chunks:
        header = chunk.splitlines()[0] if chunk else ""
        if re.match(r"^\s*\[", header):
            try:
                table = tomllib.loads(header + "\n").get("mcp_servers", {})
            except ValueError:
                table = {}
            if set(table) & owned:
                continue
        kept.append(chunk)
    result = "".join(kept)
    for marker in MANAGED_MARKERS:
        # Only empty migration markers are removed; unrelated contents stay intact.
        end = marker.replace("BEGIN", "END")
        result = re.sub(
            re.escape(marker) + r"\s*" + re.escape(end) + r"\n?", "", result
        )
    _write(path, result)
    return True


def cleanup(
    *,
    home: Path | None = None,
    project: Path | None = None,
    install_root: Path | None = None,
    codex_home: Path | None = None,
    antigravity_home: Path | None = None,
) -> list[str]:
    home = home or Path.home()
    codex_home = codex_home or Path(os.environ.get("CODEX_HOME") or home / ".codex")
    antigravity_home = antigravity_home or Path(
        os.environ.get("ANTIGRAVITY_HOME") or home / ".gemini/antigravity-cli"
    )
    configs = {
        codex_home / "config.toml",
        home / ".claude.json",
        home / ".claude/settings.json",
        home / ".claude/.mcp.json",
        antigravity_home / "mcp_config.json",
    }
    if project:
        configs.update(
            {
                project / ".mcp.json",
                project / ".agents/mcp_config.json",
                project / ".codex/config.toml",
                project / ".claude/settings.local.json",
            }
        )
    wrappers: set[Path] = set()
    changed = []
    for path in sorted(configs):
        if path.suffix == ".toml":
            did_change = clean_toml(path, wrappers)
        else:
            did_change = clean_json(path, wrappers)
        if did_change:
            changed.append(str(path))
    if install_root:
        for directory in (
            install_root / "bin",
            install_root / "Scripts",
            install_root / ".venv/bin",
        ):
            wrappers.update(
                directory / name
                for name in (
                    "paper-fetch-mcp",
                    "paper-fetch-mcp.cmd",
                    "paper-fetch-mcp-script.py",
                )
            )
    for path in sorted(wrappers):
        if owned_wrapper(path):
            path.unlink()
            changed.append(str(path))
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--install-root", type=Path)
    args = parser.parse_args(argv)
    for path in cleanup(
        home=args.home, project=args.project, install_root=args.install_root
    ):
        print("Removed legacy paper-fetch integration: " + path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
