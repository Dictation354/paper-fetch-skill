"""Source-derived numbering and list assertions for paired Elsevier replays."""

from copy import deepcopy
import re

from tests.support.reviewed_publisher_content import _words
from tests.support.markdown_lists import ancestor, inline_text, markdown_tree


def assert_numbering_and_list_structure(source, xml, markdown, *, route):
    """Source-derived checks shared with the saved comparison report."""
    assert_section_numbering(source, xml, markdown, route=route)
    assert_front_highlights_removed(source, markdown, route=route)
    assert_list_structure(source, markdown, route=route)


def assert_section_numbering(source, xml, markdown, *, route):
    if route == "html":
        headings = [
            n.get_text(" ", strip=True)
            for n in source.select("#body h2, #body h3, #body h4, #body h5, #body h6")
        ]
    else:
        headings = []
        for section in xml.find("body").find_all("section"):
            title = section.find("section-title", recursive=False)
            label = section.find("label", recursive=False)
            if title:
                headings.append(
                    (label.get_text(" ", strip=True) + " " if label else "")
                    + title.get_text(" ", strip=True)
                )
    actual = [_words(m[1]) for m in re.finditer(r"(?m)^#{2,6} (.+)$", markdown)]
    for heading in headings:
        if not re.match(r"^\d+(?:\.\d+)*\.?\s", heading):
            continue
        assert _words(heading) in actual, heading


def assert_front_highlights_removed(source, markdown, *, route):
    if route == "html":
        retained = " ".join(
            n.get_text("", strip=False)
            for n in source.select("#body, #abstracts > .abstract.author")
        )
        retained, actual = _words(retained), _words(markdown)
        for node in source.select(".author-highlights, .Highlights, .highlights"):
            if node.find_parent(id="body") is None:
                for paragraph in node.select("p, .list-content"):
                    key = _words(paragraph.get_text("", strip=False))
                    assert actual.count(key) <= retained.count(key), key


def assert_list_structure(source, markdown, *, route):
    tree = markdown_tree(markdown)
    paragraphs = [
        (n, _words(inline_text(n))) for n in tree.walk() if n.type == "paragraph"
    ]
    images = [n for n in tree.walk() if n.type == "image"]
    cursor = 0
    # Match source first paragraphs and captions independently of node ids.
    for item in source.select("#body li"):
        label = item.select_one(":scope > .list-label")
        content = item.select_one(":scope > .list-content")
        if label is None or content is None:
            continue
        first = next(
            (
                n
                for n in content.select("p, div")
                if n.find(["p", "div", "table", "figure"]) is None
                and n.get_text(strip=True)
            ),
            None,
        )
        if first is None:
            continue
        key = _words(first.get_text("", strip=False))
        if len(key) < 20 or first.select_one("math, mjx-container") is not None:
            continue
        matches = [
            (i, n)
            for i, (n, text) in enumerate(paragraphs)
            if i >= cursor and key in text and ancestor(n, "list_item") is not None
        ]
        assert matches, key
        position, match = matches[0]
        cursor = position + 1
        parent = ancestor(match, "list_item")
        assert parent is not None, key
        if (
            route == "html"
            and label.get_text(strip=True)
            and not re.fullmatch(r"[•◦▪▫‣⁃∙●○◾◽◼□■–—-]", label.get_text(strip=True))
        ):
            assert inline_text(match).startswith(label.get_text(strip=True) + " "), (
                key,
                inline_text(match)[:120],
                label.get_text(strip=True),
            )
        # Direct sibling source items must remain in the same Markdown list.
        sibling = item.find_next_sibling("li")
        if sibling:
            next_content = sibling.select_one(":scope > .list-content")
            if next_content:
                next_first = next(
                    (
                        n
                        for n in next_content.select("p, div")
                        if n.find(["p", "div", "table", "figure"]) is None
                        and n.get_text(strip=True)
                    ),
                    None,
                )
                if next_first is not None and not next_first.select_one(
                    "math, mjx-container"
                ):
                    next_key = _words(next_first.get_text("", strip=False))
                    if len(next_key) < 20:
                        continue
                    next_match = next(
                        (
                            n
                            for n, text in paragraphs[cursor:]
                            if next_key in text and ancestor(n, "list_item") is not None
                        ),
                        None,
                    )
                    assert next_match is not None
                    next_parent = ancestor(next_match, "list_item")
                    assert (
                        next_parent is not None and parent.parent is next_parent.parent
                    ), (
                        route,
                        key,
                        next_key,
                        parent.map,
                        next_parent.map if next_parent else None,
                    )
        for figure in content.select("figure"):
            # Nested list figures are checked against their own source item.
            if figure.find_parent("li") is not item:
                continue
            caption = figure.select_one(".captions")
            if caption is None:
                continue
            clone = deepcopy(caption)
            for node in clone.select(".label"):
                node.decompose()
            caption_key = _words(clone.get_text("", strip=False))
            caption_match = next(
                (n for n, text in paragraphs if caption_key in text), None
            )
            assert caption_match is not None
            assert ancestor(caption_match, "list_item") is parent
            assert len(
                [n for n in images if ancestor(n, "list_item") is parent]
            ) == len(content.select("figure"))
