#!/usr/bin/env python3
"""Render the shared SKILL.md template with absolute paths."""

from __future__ import annotations

import argparse
from pathlib import Path
from string import Template


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_TEMPLATE = ROOT_DIR / "templates" / "skill_template.md"


def build_context(repo_dir: Path, skill_dir: Path, venv_dir: Path) -> dict[str, str]:
    return {
        "REPO_DIR": str(repo_dir),
        "SKILL_DIR": str(skill_dir),
        "VENV_DIR": str(venv_dir),
        "PY_BIN": str(venv_dir / "bin" / "python"),
        "SCRIPT": str(repo_dir / "scripts" / "paper_fetch.py"),
        "RESOLVE_SCRIPT": str(repo_dir / "scripts" / "resolve_query.py"),
        "MODEL_SCRIPT": str(repo_dir / "scripts" / "article_model.py"),
        "HTML_PROVIDER": str(repo_dir / "scripts" / "providers" / "html_generic.py"),
        "IDENTITY_SCRIPT": str(repo_dir / "scripts" / "publisher_identity.py"),
        "CLIENT_REGISTRY_SCRIPT": str(repo_dir / "scripts" / "provider_clients.py"),
    }


def render_skill_template(template_text: str, context: dict[str, str]) -> str:
    return Template(template_text).substitute(context)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the shared paper-fetch SKILL.md template.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--venv-dir", required=True)
    args = parser.parse_args()

    template_path = Path(args.template).resolve()
    repo_dir = Path(args.repo_dir).resolve()
    skill_dir = Path(args.skill_dir).resolve()
    venv_dir = Path(args.venv_dir).resolve()
    rendered = render_skill_template(
        template_path.read_text(encoding="utf-8"),
        build_context(repo_dir, skill_dir, venv_dir),
    )
    print(rendered, end="")


if __name__ == "__main__":
    main()
