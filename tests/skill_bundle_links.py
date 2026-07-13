"""Markdown-aware link validation shared by source, staging, and install tests."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token


REQUIRED_REFERENCE_FILES = frozenset(
    {
        "acceptance.md",
        "cli-workflow.md",
        "environment.md",
        "failure-handling.md",
        "presets.md",
        "tool-contract.md",
        "workflow.md",
    }
)

_MARKDOWN = MarkdownIt("commonmark")


def _walk_tokens(tokens: Iterable[Token]) -> Iterable[Token]:
    for token in tokens:
        yield token
        if token.children:
            yield from _walk_tokens(token.children)


def _destinations(path: Path) -> list[str]:
    tokens = _MARKDOWN.parse(path.read_text(encoding="utf-8"))
    destinations: list[str] = []
    for token in _walk_tokens(tokens):
        attribute = "href" if token.type == "link_open" else "src"
        if token.type not in {"link_open", "image"}:
            continue
        value = token.attrGet(attribute)
        if value:
            destinations.append(value)
    return destinations


def skill_bundle_link_issues(root: Path) -> list[str]:
    """Return self-containment, reachability, and relative-link issues."""

    resolved_root = root.resolve()
    entrypoint = resolved_root / "SKILL.md"
    markdown_files = sorted(
        path for path in resolved_root.rglob("*.md") if path.is_file()
    )
    issues: list[str] = []
    if not entrypoint.is_file():
        return [f"missing skill entrypoint: {entrypoint}"]

    references = resolved_root / "references"
    actual_references = {
        path.name for path in references.glob("*.md") if path.is_file()
    }
    missing_references = REQUIRED_REFERENCE_FILES - actual_references
    if missing_references:
        issues.append(
            "missing required references: " + ", ".join(sorted(missing_references))
        )
    if "cli-fallback.md" in actual_references:
        issues.append("normal CLI workflow must not be named cli-fallback.md")

    graph: dict[Path, set[Path]] = {path.resolve(): set() for path in markdown_files}
    for source in markdown_files:
        source_resolved = source.resolve()
        for destination in _destinations(source):
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            raw_path = unquote(parsed.path)
            if raw_path.startswith("/"):
                issues.append(
                    f"{source.relative_to(resolved_root)}: absolute link {destination!r}"
                )
                continue
            target = (source.parent / raw_path).resolve(strict=False)
            try:
                target.relative_to(resolved_root)
            except ValueError:
                issues.append(
                    f"{source.relative_to(resolved_root)}: link escapes skill bundle "
                    f"{destination!r}"
                )
                continue
            if not target.is_file():
                issues.append(
                    f"{source.relative_to(resolved_root)}: missing link target "
                    f"{destination!r}"
                )
                continue
            if target.suffix.lower() == ".md":
                graph[source_resolved].add(target)

    direct_required = {
        (references / filename).resolve() for filename in REQUIRED_REFERENCE_FILES
    }
    missing_direct = direct_required - graph.get(entrypoint.resolve(), set())
    if missing_direct:
        issues.append(
            "SKILL.md must directly link required references: "
            + ", ".join(
                sorted(
                    path.relative_to(resolved_root).as_posix()
                    for path in missing_direct
                )
            )
        )

    reachable: set[Path] = set()
    pending = [entrypoint.resolve()]
    while pending:
        current = pending.pop()
        if current in reachable:
            continue
        reachable.add(current)
        pending.extend(graph.get(current, set()) - reachable)
    orphaned = set(graph) - reachable
    if orphaned:
        issues.append(
            "orphan Markdown references: "
            + ", ".join(
                sorted(path.relative_to(resolved_root).as_posix() for path in orphaned)
            )
        )
    return issues


__all__ = ["REQUIRED_REFERENCE_FILES", "skill_bundle_link_issues"]
