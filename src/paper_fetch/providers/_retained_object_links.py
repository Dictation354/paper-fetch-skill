"""Source-object links for publisher text whose IDs are not rendered locally."""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import quote, unquote, urljoin, urlsplit


def resolve_retained_object_links(
    markdown: str, source_url: str, targets: Mapping[str, str]
) -> str:
    """Resolve only publisher-verified IDs, leaving ordinary Markdown alone.

    Bibliography entries and popup tables lose their HTML IDs when rendered.
    Their source-page addresses remain valid when references/sections are omitted
    by the final render budget as well as when all content is requested.
    """
    source = urlsplit(source_url)
    has_source = source.scheme in {"http", "https"} and bool(source.netloc)

    def replace(match: re.Match[str]) -> str:
        target = targets.get(unquote(match["target"]))
        if target is None:
            return match[0]
        if not has_source:
            return match["label"]
        return f"[{match['label']}]({urljoin(source_url, '#' + quote(target))})"

    return re.sub(
        r"(?<!!)\[(?P<label>[^\[\]\n]+)\]\(#(?P<target>[^\s)]+)\)",
        replace,
        markdown,
    )
