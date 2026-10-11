"""Resolve actual local Markdown destinations independently of providers."""

from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


def local_markdown_paths(markdown: str, *, base_dir: Path) -> set[Path]:
    paths = set()
    for block in MarkdownIt().parse(markdown):
        for token in block.children or []:
            destination = token.attrGet("src") or token.attrGet("href")
            if destination:
                parsed = urlsplit(destination)
                if not parsed.scheme and not parsed.netloc and parsed.path:
                    paths.add((base_dir / unquote(parsed.path)).resolve())
    return paths
