"""Conservative multilingual block filtering helpers for HTML and XML extraction."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any, Mapping

from ..utils import normalize_text
from ._html_semantics import ABSTRACT_ATTR_TOKENS, ABSTRACT_HEADINGS, node_source_selector

EXPLICIT_LANGUAGE_ATTRS = (
    "lang",
    "xml:lang",
    "data-lang",
    "data-lang-of",
    "hreflang",
    "lang-name",
)
SOFT_LANGUAGE_ATTRS = (
    "id",
    "class",
)
LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(?:[-_][a-z0-9]{2,8})*$")
SOFT_LANGUAGE_TOKENS = {
    "de": "de",
    "deutsch": "de",
    "en": "en",
    "eng": "en",
    "english": "en",
    "es": "es",
    "espanol": "es",
    "español": "es",
    "fr": "fr",
    "francais": "fr",
    "français": "fr",
    "it": "it",
    "italiano": "it",
    "ja": "ja",
    "jp": "ja",
    "japanese": "ja",
    "ko": "ko",
    "korean": "ko",
    "pt": "pt",
    "portugues": "pt",
    "portuguese": "pt",
    "português": "pt",
    "ru": "ru",
    "russian": "ru",
    "zh": "zh",
    "chinese": "zh",
}
XML_NAMESPACE_LANGUAGE_KEY = "{http://www.w3.org/XML/1998/namespace}lang"
ABSTRACT_LABELS = ABSTRACT_HEADINGS


def _fold_language_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def normalize_language_hint(
    value: Any,
    *,
    allow_token_scan: bool = False,
    allow_code_pattern: bool = True,
) -> str | None:
    normalized = normalize_text(str(value or "")).strip()
    if not normalized:
        return None

    folded = _fold_language_text(normalized).replace("_", "-")
    direct_hint = SOFT_LANGUAGE_TOKENS.get(folded)
    if direct_hint:
        return direct_hint
    if allow_code_pattern and LANGUAGE_CODE_PATTERN.fullmatch(folded):
        return folded.split("-", 1)[0]
    if not allow_token_scan:
        return None

    for token, hint in SOFT_LANGUAGE_TOKENS.items():
        if re.search(rf"(?:^|[-_]){re.escape(token)}$", folded):
            return hint
    return None


def html_node_language_hint(node: Any, *, allow_soft_hints: bool = False) -> str | None:
    attrs = getattr(node, "attrs", None) or {}
    for key in EXPLICIT_LANGUAGE_ATTRS:
        hint = _mapping_language_hint(attrs, key, allow_token_scan=False)
        if hint:
            return hint
    if not allow_soft_hints:
        return None
    for key in SOFT_LANGUAGE_ATTRS:
        hint = _mapping_language_hint(attrs, key, allow_token_scan=True)
        if hint:
            return hint
    return None


def collect_html_abstract_blocks(root: Any) -> list[dict[str, Any]]:
    structural_nodes = _top_level_html_abstract_nodes(root, structural_only=True)
    candidate_nodes = _expand_parallel_html_abstract_variants(structural_nodes) if structural_nodes else _top_level_html_abstract_nodes(root)
    blocks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for order, node in enumerate(candidate_nodes):
        attrs = getattr(node, "attrs", None) or {}
        heading = _first_html_heading_text(node) or normalize_text(_html_attribute_text(attrs.get("data-title"))) or "Abstract"
        text = normalize_text("\n\n".join(_html_text_blocks(node)))
        if not text:
            continue
        key = (_normalize_semantic_text(heading), _normalize_semantic_text(text))
        if key in seen:
            continue
        seen.add(key)
        blocks.append(
            {
                "heading": normalize_text(heading) or "Abstract",
                "text": text,
                "language": html_node_language_hint(node, allow_soft_hints=True),
                "kind": "abstract",
                "order": order,
                "source_selector": node_source_selector(node) or None,
            }
        )
    return blocks


def strip_non_english_html_nodes(root: Any, *, allow_soft_hints: bool = False) -> int:
    removed = 0
    for parent in [root, *list(root.find_all(True))]:
        if getattr(parent, "parent", None) is None and parent is not root:
            continue
        if _is_abstract_like_html_node(parent):
            removed += _remove_non_primary_html_variants(
                [
                    child
                    for child in _element_children(parent)
                    if html_node_language_hint(child, allow_soft_hints=allow_soft_hints)
                ],
                allow_soft_hints=allow_soft_hints,
            )
        removed += _remove_non_primary_html_variants(
            [
                child
                for child in _element_children(parent)
                if _is_abstract_like_html_node(child)
                and html_node_language_hint(child, allow_soft_hints=allow_soft_hints)
            ],
            allow_soft_hints=allow_soft_hints,
        )
    return removed


def xml_node_language_hint(node: ET.Element) -> str | None:
    for key, value in node.attrib.items():
        lowered_key = key.lower()
        local_key = lowered_key.rsplit("}", 1)[-1]
        if lowered_key in EXPLICIT_LANGUAGE_ATTRS or key == XML_NAMESPACE_LANGUAGE_KEY or local_key in {"lang", "hreflang"}:
            hint = normalize_language_hint(value, allow_token_scan=False)
            if hint:
                return hint
    return None


def collect_xml_abstract_blocks(root: ET.Element) -> list[dict[str, Any]]:
    candidate_nodes = _abstract_container_xml_variants(root) or _top_level_xml_abstract_nodes(root, structural_only=True) or _top_level_xml_abstract_nodes(root)
    blocks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for order, node in enumerate(candidate_nodes):
        heading = _first_xml_heading_text(node) or "Abstract"
        text = normalize_text("\n\n".join(_xml_text_blocks(node)))
        if not text:
            continue
        key = (_normalize_semantic_text(heading), _normalize_semantic_text(text))
        if key in seen:
            continue
        seen.add(key)
        blocks.append(
            {
                "heading": normalize_text(heading) or "Abstract",
                "text": text,
                "language": xml_node_language_hint(node),
                "kind": "abstract",
                "order": order,
                "source_selector": _xml_source_selector(node),
            }
        )
    return blocks


def strip_non_english_xml_subtrees(root: ET.Element) -> int:
    removed = 0
    for parent in root.iter():
        if _is_abstract_like_xml_node(parent):
            removed += _remove_non_primary_xml_variants(
                parent,
                [child for child in list(parent) if isinstance(child.tag, str) and xml_node_language_hint(child)],
            )
        removed += _remove_non_primary_xml_variants(
            parent,
            [
                child
                for child in list(parent)
                if isinstance(child.tag, str) and _is_abstract_like_xml_node(child) and xml_node_language_hint(child)
            ],
        )
    return removed


def _mapping_language_hint(
    attrs: Mapping[str, Any],
    key: str,
    *,
    allow_token_scan: bool,
) -> str | None:
    value = attrs.get(key)
    if isinstance(value, (list, tuple, set)):
        for item in value:
            hint = normalize_language_hint(
                item,
                allow_token_scan=allow_token_scan,
                allow_code_pattern=not allow_token_scan,
            )
            if hint:
                return hint
        return None
    return normalize_language_hint(
        value,
        allow_token_scan=allow_token_scan,
        allow_code_pattern=not allow_token_scan,
    )


def _normalize_semantic_text(value: Any) -> str:
    return _fold_language_text(normalize_text(str(value or "")))


def _element_children(parent: Any) -> list[Any]:
    children = getattr(parent, "children", None)
    if children is None:
        return []
    return [child for child in children if isinstance(getattr(child, "name", None), str)]


def _html_attribute_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item or "") for item in value)
    return str(value or "")


def _top_level_html_abstract_nodes(root: Any, *, structural_only: bool = False) -> list[Any]:
    nodes: list[Any] = []
    structural_match = _is_structural_html_abstract_node if structural_only else _is_abstract_like_html_node
    for node in [root, *_element_children(root), *list(getattr(root, "find_all", lambda *_args, **_kwargs: [])(True))]:
        if not isinstance(getattr(node, "name", None), str):
            continue
        if not structural_match(node):
            continue
        parent = getattr(node, "parent", None)
        while parent is not None and isinstance(getattr(parent, "name", None), str):
            if structural_match(parent):
                break
            parent = getattr(parent, "parent", None)
        else:
            nodes.append(node)
    return _dedupe_top_level_html_nodes(nodes)


def _dedupe_top_level_html_nodes(nodes: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    for node in nodes:
        if any(existing is node or node in getattr(existing, "find_all", lambda *_args, **_kwargs: [])(True) for existing in deduped):
            continue
        deduped.append(node)
    return deduped


def _expand_parallel_html_abstract_variants(nodes: list[Any]) -> list[Any]:
    expanded: list[Any] = []
    seen: set[int] = set()
    for node in nodes:
        nested_candidates = _parallel_child_html_abstract_variants(node)
        parent = getattr(node, "parent", None)
        siblings = _element_children(parent) if parent is not None else []
        sibling_candidates = [
            sibling
            for sibling in siblings
            if sibling.name == getattr(node, "name", None)
            and _html_has_meaningful_abstract_text(sibling)
            and (
                _is_structural_html_abstract_node(sibling)
                or _is_abstract_heading_text(_first_html_heading_text(sibling))
                or html_node_language_hint(sibling, allow_soft_hints=True)
            )
        ]
        for candidate in nested_candidates or sibling_candidates or [node]:
            candidate_id = id(candidate)
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            expanded.append(candidate)
    return expanded


def _parallel_child_html_abstract_variants(node: Any) -> list[Any]:
    child_candidates = [
        child
        for child in _element_children(node)
        if _html_has_meaningful_abstract_text(child)
        and (
            _is_structural_html_abstract_node(child)
            or _is_abstract_heading_text(_first_html_heading_text(child))
            or html_node_language_hint(child, allow_soft_hints=True)
        )
    ]
    if len(child_candidates) < 2:
        return []

    distinct_languages = {
        hint
        for hint in (html_node_language_hint(child, allow_soft_hints=True) for child in child_candidates)
        if hint
    }
    if len(distinct_languages) >= 2:
        return _dedupe_top_level_html_nodes(child_candidates)

    structural_children = [
        child
        for child in child_candidates
        if _is_structural_html_abstract_node(child) or _is_abstract_heading_text(_first_html_heading_text(child))
    ]
    if len(structural_children) >= 2:
        return _dedupe_top_level_html_nodes(structural_children)
    return []


def _first_html_heading_text(node: Any) -> str:
    finder = getattr(node, "find", None)
    if not callable(finder):
        return ""
    heading = finder(re.compile(r"^h[1-6]$"))
    if heading is None:
        return ""
    text = getattr(heading, "get_text", None)
    return normalize_text(text(" ", strip=True)) if callable(text) else ""


def _html_text_blocks(node: Any) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    finder = getattr(node, "find_all", None)
    if callable(finder):
        for candidate in finder(True):
            if candidate is node:
                continue
            if normalize_text(getattr(candidate, "name", "")).lower() not in {"p", "li"} and normalize_text(candidate.get("role") or "").lower() != "paragraph":
                continue
            text = normalize_text(candidate.get_text(" ", strip=True))
            if not text:
                continue
            canonical = _normalize_semantic_text(text)
            if canonical in seen:
                continue
            seen.add(canonical)
            texts.append(text)
    if texts:
        return texts
    fallback_text = normalize_text(getattr(node, "get_text", lambda *_args, **_kwargs: "")(" ", strip=True))
    heading_text = _first_html_heading_text(node)
    if heading_text and fallback_text:
        pattern = re.compile(rf"^{re.escape(heading_text)}[:\s-]*", flags=re.IGNORECASE)
        fallback_text = normalize_text(pattern.sub("", fallback_text, count=1))
    return [fallback_text] if fallback_text else []


def _is_abstract_heading_text(value: str) -> bool:
    normalized = _normalize_semantic_text(value)
    return normalized in ABSTRACT_LABELS


def _is_structural_html_abstract_node(node: Any) -> bool:
    attrs = getattr(node, "attrs", None) or {}
    for key in ("id", "class", "role", "itemprop", "property", "typeof", "data-title", "aria-label"):
        text = _normalize_semantic_text(_html_attribute_text(attrs.get(key)))
        if any(token in text for token in ABSTRACT_ATTR_TOKENS):
            return True
    return False


def _is_abstract_like_html_node(node: Any) -> bool:
    return _is_structural_html_abstract_node(node) or _is_abstract_heading_text(_first_html_heading_text(node))


def _html_has_meaningful_abstract_text(node: Any) -> bool:
    return any(_normalize_semantic_text(text) for text in _html_text_blocks(node))


def _candidate_priority(node: Any, language_hint: str) -> tuple[int, int]:
    attrs = getattr(node, "attrs", None) or {}
    class_text = _normalize_semantic_text(_html_attribute_text(attrs.get("class")))
    style_text = _normalize_semantic_text(_html_attribute_text(attrs.get("style")))
    aria_hidden = _normalize_semantic_text(_html_attribute_text(attrs.get("aria-hidden")))
    hidden = attrs.get("hidden")
    is_active = any(token in class_text for token in ("active", "current", "selected")) or attrs.get("aria-current") not in {None, "", "false"}
    is_hidden = hidden is not None or aria_hidden == "true" or "display:none" in style_text or "visibility:hidden" in style_text
    return (
        1 if language_hint == "en" else 0,
        1 if is_active else 0,
        0 if is_hidden else 1,
    )


def _remove_non_primary_html_variants(
    candidates: list[Any],
    *,
    allow_soft_hints: bool,
) -> int:
    if len(candidates) < 2:
        return 0

    hinted: list[tuple[Any, str]] = []
    for candidate in candidates:
        if getattr(candidate, "parent", None) is None:
            continue
        hint = html_node_language_hint(candidate, allow_soft_hints=allow_soft_hints)
        if hint:
            hinted.append((candidate, hint))
    if len(hinted) < 2:
        return 0

    distinct_languages = {hint for _, hint in hinted}
    if len(distinct_languages) < 2:
        return 0

    primary_node, primary_hint = max(hinted, key=lambda item: _candidate_priority(item[0], item[1]))
    removed = 0
    for candidate, hint in hinted:
        if candidate is primary_node or hint == primary_hint or getattr(candidate, "parent", None) is None:
            continue
        candidate.decompose()
        removed += 1
    return removed


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_source_selector(node: ET.Element) -> str | None:
    tag = _xml_local_name(node.tag) if isinstance(node.tag, str) else ""
    if not tag:
        return None
    node_id = normalize_text(str(node.attrib.get("id") or ""))
    if node_id:
        return f"{tag}#{node_id}"
    return tag


def _first_xml_heading_text(node: ET.Element) -> str:
    for child in node.iter():
        if not isinstance(child.tag, str):
            continue
        if _xml_local_name(child.tag) in {"section-title", "title", "label"}:
            return normalize_text("".join(child.itertext()))
    return ""


def _abstract_container_xml_variants(root: ET.Element) -> list[ET.Element]:
    variants: list[ET.Element] = []
    for node in root.iter():
        if not isinstance(node.tag, str) or _xml_local_name(node.tag) != "abstract":
            continue
        children = [
            child
            for child in list(node)
            if isinstance(child.tag, str) and _xml_has_meaningful_abstract_text(child)
        ]
        if children:
            variants.extend(children)
            continue
        if _xml_has_meaningful_abstract_text(node):
            variants.append(node)
    return variants


def _top_level_xml_abstract_nodes(root: ET.Element, *, structural_only: bool = False) -> list[ET.Element]:
    nodes: list[ET.Element] = []
    matcher = _is_structural_xml_abstract_node if structural_only else _is_abstract_like_xml_node
    for node in root.iter():
        if not isinstance(node.tag, str) or not matcher(node):
            continue
        nodes.append(node)
    return nodes


def _xml_text_blocks(node: ET.Element) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for child in node.iter():
        if not isinstance(child.tag, str):
            continue
        if _xml_local_name(child.tag) not in {"para", "p", "simple-para", "simple_para"}:
            continue
        text = normalize_text("".join(child.itertext()))
        if not text:
            continue
        canonical = _normalize_semantic_text(text)
        if canonical in seen:
            continue
        seen.add(canonical)
        texts.append(text)
    if texts:
        return texts
    fallback_text = normalize_text("".join(node.itertext()))
    heading_text = _first_xml_heading_text(node)
    if heading_text and fallback_text:
        pattern = re.compile(rf"^{re.escape(heading_text)}[:\s-]*", flags=re.IGNORECASE)
        fallback_text = normalize_text(pattern.sub("", fallback_text, count=1))
    return [fallback_text] if fallback_text else []


def _is_abstract_like_xml_node(node: ET.Element) -> bool:
    if _is_structural_xml_abstract_node(node):
        return True
    local_name = _xml_local_name(node.tag)
    if local_name in {"section", "sec", "abstract-sec"}:
        return _is_abstract_heading_text(_first_xml_heading_text(node))
    return False


def _is_structural_xml_abstract_node(node: ET.Element) -> bool:
    local_name = _xml_local_name(node.tag)
    if local_name == "abstract":
        return True
    for value in node.attrib.values():
        text = _normalize_semantic_text(value)
        if any(token in text for token in ABSTRACT_ATTR_TOKENS):
            return True
    return False


def _xml_has_meaningful_abstract_text(node: ET.Element) -> bool:
    return any(_normalize_semantic_text(text) for text in _xml_text_blocks(node))


def _remove_non_primary_xml_variants(parent: ET.Element, candidates: list[ET.Element]) -> int:
    if len(candidates) < 2:
        return 0

    hinted = [(candidate, xml_node_language_hint(candidate)) for candidate in candidates]
    hinted = [(candidate, hint) for candidate, hint in hinted if hint]
    if len(hinted) < 2:
        return 0

    distinct_languages = {hint for _, hint in hinted}
    if len(distinct_languages) < 2:
        return 0

    primary_node, primary_hint = max(
        hinted,
        key=lambda item: (
            1 if item[1] == "en" else 0,
            1 if normalize_text(item[0].attrib.get("active") or "").lower() == "true" else 0,
        ),
    )
    removed = 0
    for candidate, hint in hinted:
        if candidate is primary_node or hint == primary_hint:
            continue
        parent.remove(candidate)
        removed += 1
    return removed
