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


def prepare_retained_object_links(root, source_url: str) -> None:
    """Resolve HTML cross references using source IDs and explicit popup aliases.

    Run before publisher cleanup removes dialogs, bibliography or formula owners.
    Source-page links remain usable when the output omits an object by budget.
    """
    from bs4 import Tag

    if not isinstance(root, Tag):
        return
    targets: dict[str, str] = {}
    nodes = [root, *root.find_all(True)]
    for node in nodes:
        identity = str(
            node.get("id") or node.get("name") or node.get("data-content-id") or ""
        )
        if not identity:
            continue
        for attr in (
            "id",
            "name",
            "data-legacyid",
            "data-legacy-id",
            "content-id",
            "data-content-id",
            "data-bib-id",
        ):
            alias = str(node.get(attr) or "")
            if alias:
                targets[alias] = identity
        # The image/viewer and its visible owner share an explicit data-target.
        for viewer in node.select("[data-target]"):
            if viewer.find_parent(["figure", "table"]) is node:
                targets[str(viewer["data-target"]).lstrip("#")] = identity
    for viewer in root.select("[data-target]"):
        if viewer.name == "a":
            continue
        owner = viewer.find_parent(attrs={"id": True})
        if owner is not None:
            targets.setdefault(str(viewer["data-target"]).lstrip("#"), str(owner["id"]))
    folded = {key.casefold(): value for key, value in targets.items()}
    for anchor in root.find_all("a"):
        href = str(anchor.get("href") or "")
        candidates = [
            str(anchor.get(attr) or "").lstrip("#")
            for attr in (
                "data-rid",
                "data-modal-source-id",
                "reveal-id",
                "data-open",
                "data-target",
            )
        ]
        if href.startswith("#"):
            candidates.append(unquote(href[1:]))
        target = next(
            (
                targets.get(key) or folded.get(key.casefold())
                for key in candidates
                if key in targets or key.casefold() in folded
            ),
            None,
        )
        if target:
            anchor["href"] = (
                urljoin(source_url, "#" + quote(target))
                if source_url
                else "#" + quote(target)
            )
