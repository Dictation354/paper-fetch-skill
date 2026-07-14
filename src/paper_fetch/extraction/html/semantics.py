"""Canonical HTML section semantics shared by HTML extraction helpers."""

from __future__ import annotations

import re
from typing import Any
from collections.abc import Callable

from ...common_patterns import HEADING_LEVEL_PATTERN, REFERENCE_TOKEN_VOCABULARY
from ...section_vocab import MARKDOWN_ABSTRACT_HEADINGS
from ...utils import normalize_text
from ..citation_anchors import looks_like_reference_href
from ..section_hints import (
    SECTION_HINT_KINDS as HTML_SECTION_HINT_KINDS,
    coerce_section_hint_dicts,
    match_next_section_hint,
)
from .signals import contains_access_gate_text
from .ui_tokens import (
    CITATION_TOOL_CHROME_TOKENS,
    COMMON_NOISE_TOKENS,
    RELATED_CONTENT_CHROME_TOKENS,
)

from bs4 import Tag

HTML_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "form",
        "header",
        "li",
        "main",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)


def coerce_html_section_hints(section_hints: Any) -> list[dict[str, Any]]:
    return coerce_section_hint_dicts(
        section_hints, allowed_kinds=HTML_SECTION_HINT_KINDS
    )


def match_next_html_section_hint(
    section_hints: list[dict[str, Any]],
    hint_index: int,
    heading: str,
) -> tuple[dict[str, Any] | None, int]:
    matched, next_index = match_next_section_hint(section_hints, hint_index, heading)
    return (dict(matched), next_index) if matched is not None else (None, next_index)


ABSTRACT_HEADINGS = frozenset(
    {
        "abstract",
        "structured abstract",
        "editor's summary",
        "editor’s summary",
        "editors summary",
        "summary",
        "significance",
        "significance statement",
        "resumo",
        "resumen",
        "resume",
        "résumé",
        "zusammenfassung",
    }
)
FRONT_MATTER_HEADINGS = frozenset(
    {
        "keywords",
        "key points",
        "about this article",
        "author notes",
        "authors",
        "article information",
        "highlights",
        "graphical abstract",
    }
)
DATA_AVAILABILITY_HEADINGS = frozenset(
    {
        "data availability",
        "data availability statement",
        "data, materials, and software availability",
        "data, code, and materials availability",
        "availability of data and materials",
    }
)
CODE_AVAILABILITY_HEADINGS = frozenset(
    {
        "code availability",
        "code availability statement",
        "software availability",
        "software availability statement",
    }
)
BACK_MATTER_HEADINGS = frozenset(
    {
        "references",
        "references and notes",
        "bibliography",
        "electronic supplementary material",
        "supplementary material",
        "supplementary materials",
        "supplementary information",
        "supporting information",
        "notes",
        "acknowledgements",
        "acknowledgments",
        "author contributions",
        "funding",
        "research funding",
        "ethics",
        "conflict of interest",
        "conflicts of interest",
        "competing interests",
        "statement of competing interests",
        "disclosures",
    }
)
SUPPLEMENTARY_BACK_MATTER_HEADINGS = (
    frozenset(
        {
            "electronic supplementary material",
            "supplementary material",
            "supplementary materials",
            "supplementary information",
            "supporting information",
        }
    )
    & BACK_MATTER_HEADINGS
)
# HTML ancillary headings classify DOM headings before rendering. Some labels
# overlap with markdown cleanup, but this set decides whether a source heading
# should be treated as article body while section hints are still available.
ANCILLARY_HEADINGS = frozenset(
    {
        "recommended",
        "recommendations",
        "related content",
        *RELATED_CONTENT_CHROME_TOKENS,
        "most read",
        "most read this month",
        "most cited",
        "metrics",
        "metrics & citations",
        "view options",
        "authors",
        "affiliations",
        "author information",
        "information & authors",
        "information and authors",
        "citations",
        "submission history",
        "license information",
        "cite as",
        *CITATION_TOOL_CHROME_TOKENS,
        "cited by",
        "citing literature",
        "figures",
        "tables",
        "media",
        "share",
        "permissions",
        "eletters",
        "corresponding author",
        "additional information",
        "rights and permissions",
        "profiles",
        "subscribe and save",
        "publisher's note",
        "publisher’s note",
        "open access",
    }
)
# Markdown auxiliary headings run after HTML/XML has already been rendered to
# text. Keep this separate from ANCILLARY_HEADINGS so renderer cleanup can drop
# chrome without changing DOM section classification.
MARKDOWN_AUXILIARY_HEADINGS = frozenset(
    {
        "abbreviations",
        "open access",
        "permissions",
        "rights and permissions",
        "reprints and permissions",
    }
)
MARKDOWN_FRONT_MATTER_HEADINGS = frozenset(
    {
        "editor's summary",
        "editor’s summary",
        "summary",
        "keywords",
        "key points",
        "about this article",
        "author notes",
        "authors",
        "article information",
        "highlights",
        "graphical abstract",
    }
)
MARKDOWN_BACK_MATTER_HEADINGS = BACK_MATTER_HEADINGS
BODY_CONTAINER_TOKENS = (
    "articlebody",
    "article-body",
    "article_body",
    "bodymatter",
    "fulltext",
    "full-text",
)
ABSTRACT_ATTR_TOKENS = (
    "abstract",
    "structured-abstract",
    "structured_abstract",
    "editor-abstract",
    "summary",
    "key-points",
    "highlights",
)
DATA_AVAILABILITY_TOKENS = (
    "data-availability",
    "data_availability",
    "data-code-availability",
    "data_code_availability",
    "data-code-materials-availability",
    "data_code_materials_availability",
    "data-and-code-availability",
    "data_and_code_availability",
    "data-software-availability",
    "data_software_availability",
    "data-and-software-availability",
    "data_and_software_availability",
    "data-materials-software-availability",
    "data_materials_software_availability",
)
CODE_AVAILABILITY_TOKENS = (
    "code-availability",
    "code_availability",
    "software-availability",
    "software_availability",
)
BACK_MATTER_TOKENS = (
    "reference",
    "bibliograph",
    "supplement",
    "supplementary",
    "supporting-information",
    "supporting_information",
    "acknowledg",
    "funding",
    "author-contribution",
    "conflict",
    "disclosure",
    "ethics",
)
ANCILLARY_TOKENS = (
    *COMMON_NOISE_TOKENS,
    "access",
    "viewer",
    "citation",
    "permissions",
    "eletter",
    "signup",
    "comment",
    "author-information",
    "additional-information",
    "profiles",
    "subscribe",
    "mostread",
    "most-read",
    "mostcited",
    "most-cited",
)
IDENTITY_ATTR_KEYS = (
    "id",
    "class",
    "property",
    "itemprop",
    "data-type",
    "data-title",
    "data-track-action",
    "data-track-label",
    "role",
    "aria-label",
    "aria-labelledby",
)
SECTION_HEADING_PATTERN = HEADING_LEVEL_PATTERN
SECTION_TITLE_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_REFERENCE_MARKER_TOKENS = tuple(
    token
    for token in (*REFERENCE_TOKEN_VOCABULARY, "r")
    if token not in {"refs", "reference", "bibliography"}
)
REFERENCE_MARKER_VALUE_PATTERN = re.compile(
    rf"(?:{'|'.join(re.escape(token) for token in _REFERENCE_MARKER_TOKENS)})\d+[a-z]?",
    flags=re.IGNORECASE,
)
REFERENCE_ANCHOR_CLASS_TOKENS = frozenset({"biblink", "to-citation"})


def normalize_heading(text: str) -> str:
    return normalize_text(text).lower().rstrip(".: ")


def normalize_section_title(title: str) -> str:
    return SECTION_TITLE_NON_ALNUM_PATTERN.sub(
        " ", normalize_text(title).lower()
    ).strip()


def node_identity_text(node: Any) -> str:
    if node is None:
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(getattr(node, "name", "") or "")]
    for key in IDENTITY_ATTR_KEYS:
        value = attrs.get(key)
        if isinstance(value, (list, tuple, set)):
            parts.extend(normalize_text(str(item)) for item in value)
        else:
            parts.append(normalize_text(str(value or "")))
    return " ".join(part.lower() for part in parts if part)


def ancestor_identity_text(node: Any) -> str:
    identities: list[str] = []
    current = node
    while isinstance(current, Tag):
        identity = node_identity_text(current)
        if identity:
            identities.append(identity)
        current = (
            current.parent
            if isinstance(getattr(current, "parent", None), Tag)
            else None
        )
    return " ".join(identities)


def identity_category(identity_text: str) -> str:
    normalized = normalize_text(identity_text).lower()
    if not normalized:
        return ""
    if any(token in normalized for token in DATA_AVAILABILITY_TOKENS):
        return "data_availability"
    if any(token in normalized for token in CODE_AVAILABILITY_TOKENS):
        return "code_availability"
    if any(token in normalized for token in BACK_MATTER_TOKENS):
        return "references_or_back_matter"
    if any(token in normalized for token in ABSTRACT_ATTR_TOKENS):
        return "abstract"
    if any(token in normalized for token in BODY_CONTAINER_TOKENS):
        return "body"
    if any(token in normalized for token in ANCILLARY_TOKENS):
        return "ancillary"
    return ""


def looks_like_explicit_body_container(node: Any) -> bool:
    return identity_category(node_identity_text(node)) == "body"


def heading_category(node_name: str, text: str, *, title: str | None = None) -> str:
    if normalize_text(node_name or "").lower() == "h1":
        return "front_matter"
    normalized = normalize_heading(text)
    if not normalized:
        return "body_heading"
    if title and normalized == normalize_heading(title):
        return "front_matter"
    if contains_access_gate_text(normalized):
        return "ancillary"
    if normalized in ABSTRACT_HEADINGS or normalized.startswith("abstract"):
        return "abstract"
    if any(normalized.startswith(token) for token in DATA_AVAILABILITY_HEADINGS):
        return "data_availability"
    if any(normalized.startswith(token) for token in CODE_AVAILABILITY_HEADINGS):
        return "code_availability"
    if any(normalized.startswith(token) for token in BACK_MATTER_HEADINGS):
        return "references_or_back_matter"
    if any(normalized.startswith(token) for token in ANCILLARY_HEADINGS):
        return "ancillary"
    if normalized in FRONT_MATTER_HEADINGS:
        return "front_matter"
    return "body_heading"


def node_source_selector(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    attrs = getattr(node, "attrs", None) or {}
    parts = [normalize_text(node.name or "").lower() or "node"]
    node_id = normalize_text(str(attrs.get("id") or "")).strip()
    if node_id:
        parts.append(f"#{node_id}")
    class_values = attrs.get("class")
    if isinstance(class_values, (list, tuple, set)):
        classes = [
            normalize_text(str(item)).strip()
            for item in class_values
            if normalize_text(str(item)).strip()
        ]
    else:
        classes = (
            [normalize_text(str(class_values)).strip()]
            if normalize_text(str(class_values or "")).strip()
            else []
        )
    if classes:
        parts.append("." + ".".join(classes[:3]))
    return "".join(parts)


def _node_class_tokens(node: Any) -> set[str]:
    if not isinstance(node, Tag):
        return set()
    attrs = getattr(node, "attrs", None) or {}
    class_values = attrs.get("class")
    if isinstance(class_values, (list, tuple, set)):
        return {
            normalize_text(str(item)).lower()
            for item in class_values
            if normalize_text(str(item))
        }
    token = normalize_text(str(class_values or "")).lower()
    return {token} if token else set()


def has_explicit_reference_marker(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    attrs = getattr(node, "attrs", None) or {}
    if "citation-ref" in attrs:
        return True
    if normalize_text(str(attrs.get("data-test") or "")).lower() == "citation-ref":
        return True
    if normalize_text(str(attrs.get("role") or "")).lower() == "doc-biblioref":
        return True
    if normalize_text(str(attrs.get("data-xml-rid") or "")):
        return True
    if normalize_text(str(attrs.get("ref-type") or "")).lower() == "bibr":
        return True
    if REFERENCE_ANCHOR_CLASS_TOKENS & _node_class_tokens(node):
        return True
    for key in ("anchor", "data-range", "rid"):
        value = normalize_text(str(attrs.get(key) or ""))
        if value and REFERENCE_MARKER_VALUE_PATTERN.fullmatch(value):
            return True
    return False


def looks_like_reference_anchor(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    if normalize_text(getattr(node, "name", "")).lower() != "a":
        return False
    return has_explicit_reference_marker(node) or looks_like_reference_href(
        str(node.get("href") or "")
    )


def section_hint_kind_for_category(category: str) -> str | None:
    if category == "body_heading":
        return "body"
    if category == "data_availability":
        return "data_availability"
    if category == "code_availability":
        return "code_availability"
    if category == "references_or_back_matter":
        return "references"
    return None


def category_for_section_hint_kind(kind: str) -> str:
    if kind == "data_availability":
        return "data_availability"
    if kind == "code_availability":
        return "code_availability"
    if kind == "references":
        return "references_or_back_matter"
    return "body_heading"


def parse_markdown_heading(block: str) -> tuple[int, str] | None:
    stripped = block.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s*(.*)$", stripped)
    if not match:
        return None
    return len(match.group(1)), normalize_text(match.group(2))


def markdown_heading_category(
    heading: str,
    *,
    title: str | None = None,
    section_hint_kind: str | None = None,
) -> str:
    if section_hint_kind:
        return category_for_section_hint_kind(section_hint_kind)

    normalized = normalize_heading(heading)
    if not normalized:
        return "body_heading"
    if title and normalized == normalize_heading(title):
        return "front_matter"
    if normalized in MARKDOWN_ABSTRACT_HEADINGS or normalized.startswith("abstract"):
        return "abstract"
    if normalized in MARKDOWN_AUXILIARY_HEADINGS:
        return "auxiliary"
    if normalized in MARKDOWN_FRONT_MATTER_HEADINGS:
        return "front_matter"
    if any(normalized.startswith(token) for token in DATA_AVAILABILITY_HEADINGS):
        return "data_availability"
    if any(normalized.startswith(token) for token in CODE_AVAILABILITY_HEADINGS):
        return "code_availability"
    if any(normalized.startswith(token) for token in MARKDOWN_BACK_MATTER_HEADINGS):
        return "references_or_back_matter"

    dom_category = heading_category("h2", heading, title=title)
    if dom_category == "ancillary":
        return "auxiliary"
    return dom_category


def container_has_explicit_body_container(container: Any) -> bool:
    if not isinstance(container, Tag):
        return False
    if looks_like_explicit_body_container(container):
        return True
    return any(
        looks_like_explicit_body_container(node) for node in container.find_all(True)
    )


def iter_html_blocks(container: Any) -> list[dict[str, Any]]:
    if not isinstance(container, Tag):
        return []
    blocks: list[dict[str, Any]] = []
    seen_markers: set[int] = set()
    if looks_like_explicit_body_container(container):
        blocks.append({"kind": "marker", "node": container, "text": ""})
        seen_markers.add(id(container))

    for node in container.find_all(True):
        if id(node) in seen_markers:
            continue
        if looks_like_explicit_body_container(node):
            blocks.append({"kind": "marker", "node": node, "text": ""})
            seen_markers.add(id(node))
            continue

        name = normalize_text(getattr(node, "name", "")).lower()
        if not name:
            continue
        if SECTION_HEADING_PATTERN.fullmatch(name):
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "heading", "node": node, "text": text})
            continue
        if name in {"figure", "table", "figcaption"}:
            blocks.append(
                {
                    "kind": "figure_or_table",
                    "node": node,
                    "text": normalize_text(node.get_text(" ", strip=True)),
                }
            )
            continue
        if name == "p":
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "paragraph", "node": node, "text": text})
            continue
        if (
            name == "div"
            and normalize_text(
                str((getattr(node, "attrs", None) or {}).get("role") or "")
            ).lower()
            == "paragraph"
        ):
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "paragraph", "node": node, "text": text})
            continue
        if name == "li":
            text = normalize_text(node.get_text(" ", strip=True))
            if text:
                blocks.append({"kind": "paragraph", "node": node, "text": text})
    return blocks


def classify_html_paragraph(
    node: Any,
    text: str,
    *,
    title: str | None = None,
    in_back_matter: bool = False,
    in_front_matter: bool = False,
    in_abstract: bool = False,
    in_data_availability: bool = False,
    in_code_availability: bool = False,
    in_auxiliary: bool = False,
    looks_like_front_matter_paragraph: Callable[[str], bool] | None = None,
    is_substantial_prose: Callable[[str], bool] | None = None,
    looks_like_access_gate_text: Callable[[str], bool] | None = None,
) -> str:
    if in_back_matter:
        return "references_or_back_matter"
    if in_front_matter:
        return "front_matter"
    if in_abstract:
        return "abstract"
    if in_data_availability:
        return "data_availability"
    if in_code_availability:
        return "code_availability"
    if in_auxiliary:
        return "ancillary"

    identity_kind = identity_category(ancestor_identity_text(node))
    if identity_kind in {
        "references_or_back_matter",
        "data_availability",
        "code_availability",
        "abstract",
        "ancillary",
    }:
        return identity_kind
    lowered = normalize_text(text).lower()
    if looks_like_access_gate_text is not None and looks_like_access_gate_text(lowered):
        return "ancillary"
    if (
        looks_like_front_matter_paragraph is not None
        and looks_like_front_matter_paragraph(text)
    ):
        return "front_matter"
    if is_substantial_prose is not None and is_substantial_prose(text):
        return "body_paragraph"
    return "ancillary"


def collect_html_section_hints(
    root: Any,
    *,
    title: str | None = None,
    language_hint_resolver: Callable[[Any], str | None] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(root, Tag):
        return []
    hints: list[dict[str, Any]] = []
    for node in root.find_all(SECTION_HEADING_PATTERN):
        if not isinstance(node, Tag):
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        category = heading_category(
            normalize_text(node.name or "").lower(), text, title=title
        )
        if category in {"body_heading", "front_matter"}:
            container = (
                node.parent if isinstance(getattr(node, "parent", None), Tag) else node
            )
            container_kind = identity_category(ancestor_identity_text(container))
            if container_kind in {
                "abstract",
                "data_availability",
                "code_availability",
                "references_or_back_matter",
                "ancillary",
            }:
                category = container_kind
        kind = section_hint_kind_for_category(category)
        if kind is None:
            continue
        level_match = SECTION_HEADING_PATTERN.fullmatch(
            normalize_text(node.name or "").lower()
        )
        level = int(level_match.group(1)) if level_match else 2
        language = None
        if language_hint_resolver is not None:
            language = language_hint_resolver(node)
            if not language and isinstance(getattr(node, "parent", None), Tag):
                language = language_hint_resolver(node.parent)
        hints.append(
            {
                "heading": normalize_text(text),
                "level": level,
                "kind": kind,
                "order": len(hints),
                "language": normalize_text(language) or None,
                "source_selector": node_source_selector(
                    node.parent
                    if isinstance(getattr(node, "parent", None), Tag)
                    else node
                )
                or None,
            }
        )
    return hints
