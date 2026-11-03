"""Inspect Markdown list ownership using the existing CommonMark parser."""

import re

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode


def markdown_tree(markdown):
    return SyntaxTreeNode(MarkdownIt().parse(markdown))


def ancestor(node, kind):
    parent = node.parent
    while parent is not None:
        if parent.type == kind:
            return parent
        parent = parent.parent
    return None


def inline_text(node):
    return " ".join(
        re.sub(
            r'<a id="elsevier-[^"]+"></a>',
            "",
            "".join(
                child.content
                for child in inline.walk()
                if child.type in {"text", "code_inline", "html_inline", "image"}
            ),
        )
        for inline in node.walk()
        if inline.type == "inline"
    )
