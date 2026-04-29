"""Browser-workflow HTML heuristics built on top of the generic markdown pipeline."""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping

from ..metadata_types import ProviderMetadata
from ..extraction.html.figure_links import inject_inline_figure_links
from ..extraction.html.formula_rules import (
    display_formula_nodes,
    formula_image_url_from_node,
    is_display_formula_node,
    looks_like_formula_image,
    mathml_element_from_html_node,
)
from ..extraction.html.inline import normalize_html_inline_text
from ..extraction.html.language import (
    collect_html_abstract_blocks,
    html_node_language_hint,
)
from ..extraction.html.parsing import choose_parser
from ..extraction.html.semantics import (
    ABSTRACT_ATTR_TOKENS as ABSTRACT_TOKENS,
    ANCILLARY_TOKENS,
    BACK_MATTER_TOKENS,
    BODY_CONTAINER_TOKENS,
    CODE_AVAILABILITY_TOKENS,
    DATA_AVAILABILITY_TOKENS,
    ancestor_identity_text,
    collect_html_section_hints,
    heading_category,
    node_identity_text,
    node_source_selector,
    normalize_heading,
    parse_markdown_heading,
)
from ..extraction.html.signals import (
    PAYWALL_PATTERNS,
    SciencePnasHtmlFailure,
)
from ..extraction.html.shared import (
    append_text_block as _append_text_block,
    class_tokens as _class_tokens,
    direct_child_tags as _direct_child_tags,
    short_text as _short_text,
    soup_root as _soup_root,
)
from ..extraction.html.tables import (
    escape_markdown_table_cell,
    expanded_table_matrix,
    flatten_table_header_rows,
    inject_inline_table_blocks,
    normalize_table_inline_text,
    render_aligned_markdown_table,
    render_table_inline_node,
    render_table_inline_text,
    render_table_markdown,
    table_cell_data,
    table_header_row_count,
    table_headers_and_data,
    table_placeholder,
    table_rows,
    wrap_table_text_fragment,
)
from ..markdown.citations import is_citation_link, make_numeric_citation_sentinel, numeric_citation_payload
from ..models import normalize_markdown_text
from ..quality.html_availability import (
    HTML_CONTAINER_BROWSER_WORKFLOW_FALLBACK_TAGS,
    HTML_CONTAINER_DROP_BROWSER_WORKFLOW,
    HTML_CONTAINER_SCORE_BROWSER_WORKFLOW,
    HtmlContainerSelectionPolicy,
    assess_html_fulltext_availability,
    availability_failure_message,
    clean_container,
    select_best_container,
)
from ..utils import normalize_text
from ._article_markdown_math import render_external_mathml_expression
from . import _science_pnas_postprocess
from ._science_pnas_postprocess import (
    normalize_browser_workflow_markdown,
)
from ._science_pnas_profiles import (
    noise_profile_for_publisher as _profile_noise_profile_for_publisher,
    publisher_profile as _publisher_profile,
)
from . import html_noise as _html_noise

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    NavigableString = None
    Tag = None

clean_markdown = _html_noise.clean_markdown
extract_article_markdown = _html_noise.extract_article_markdown
body_metrics = _html_noise.body_metrics
has_sufficient_article_body = _html_noise.has_sufficient_article_body
BODY_PARAGRAPH_MIN_CHARS = 80
HEADING_TAG_PATTERN = re.compile(r"^h[1-6]$")
SENTENCE_PATTERN = re.compile(r"[.!?。！？]+")
FRONT_MATTER_LINE_PATTERNS = (
    re.compile(r"^doi:\s*", flags=re.IGNORECASE),
    re.compile(r"^(vol\.?|volume)\b", flags=re.IGNORECASE),
    re.compile(r"^issue\b", flags=re.IGNORECASE),
    re.compile(r"^[A-Z][a-z]{2,9}\s+\d{4}$"),
    re.compile(r"^[0-3]?\d\s+[A-Z][a-z]{2,9}\s+\d{4}$"),
)
FRONT_MATTER_EXACT_TEXTS = {
    "full access",
    "open access",
    "free access",
    "research article",
    "perspective",
    "review",
    "editorial",
    "commentary",
}
POST_CONTENT_BREAK_PREFIXES = (
    "copyright",
    "license information",
    "submission history",
)
POST_CONTENT_BREAK_TEXTS = {
    "these authors contributed equally to this work.",
}
POST_CONTENT_BREAK_TOKENS = (
    "view all articles by this author",
    "purchase digital access to this article",
    "purchase access to other journals in the science family",
    "select the format you want to export the citation of this publication",
    "loading institution options",
    "become a aaas member",
    "activate your aaas id",
    "account help",
)
PROMO_BLOCK_TOKENS = (
    "sign up for pnas alerts",
    "get alerts for new articles, or get an alert when an article is cited",
)
FIGURE_LABEL_PATTERN = re.compile(r"\bfig(?:ure)?\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
TABLE_LABEL_PATTERN = re.compile(r"\btable\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
EQUATION_NUMBER_PATTERN = re.compile(r"(\d+[A-Za-z]?)")
CONTENT_ABSTRACT_SELECTORS = (
    "#abstracts",
    "section[role='doc-abstract']",
    "[property='abstract'][typeof='Text']",
    "[itemprop='description']",
    ".abstract",
    ".article-section__abstract",
)
CONTENT_BODY_SELECTORS = (
    "#bodymatter",
    "[data-extent='bodymatter']",
    "[property='articleBody']",
    "[itemprop='articleBody']",
    ".article__body",
    ".article-body",
    ".article__content",
    ".article-section__content",
    ".article__fulltext",
    ".epub-section",
)
CONTENT_AVAILABILITY_SELECTORS = (
    "#data-availability",
    "#code-availability",
    "#software-availability",
    "section[id*='data-availability']",
    "section[id*='code-availability']",
    "section[id*='software-availability']",
    "section[class*='data-availability']",
    "section[class*='code-availability']",
    "section[class*='software-availability']",
    "div[id*='data-availability']",
    "div[id*='code-availability']",
    "div[id*='software-availability']",
    "div[class*='data-availability']",
    "div[class*='code-availability']",
    "div[class*='software-availability']",
)


def _noise_profile_for_publisher(publisher: str | None) -> str:
    return _profile_noise_profile_for_publisher(publisher)


def _container_selection_policy(publisher: str) -> HtmlContainerSelectionPolicy:
    profile = _publisher_profile(publisher)
    return HtmlContainerSelectionPolicy(
        score_profile=HTML_CONTAINER_SCORE_BROWSER_WORKFLOW,
        drop_profile=HTML_CONTAINER_DROP_BROWSER_WORKFLOW,
        fallback_tags=HTML_CONTAINER_BROWSER_WORKFLOW_FALLBACK_TAGS,
        prefer_complete_ancestor=True,
        avoid_page_level_container=True,
        body_selectors=CONTENT_BODY_SELECTORS,
        abstract_node_finder=_abstract_nodes,
        refine_selected_container=profile.refine_selected_container,
    )


def _sentence_count(text: str) -> int:
    normalized = normalize_text(text)
    if not normalized:
        return 0
    matches = SENTENCE_PATTERN.findall(normalized)
    if matches:
        return len(matches)
    return 1 if len(normalized) >= BODY_PARAGRAPH_MIN_CHARS else 0


def _is_substantial_prose(text: str) -> bool:
    normalized = normalize_text(text)
    return len(normalized) >= BODY_PARAGRAPH_MIN_CHARS or _sentence_count(normalized) >= 2


def _heading_category(node_name: str, text: str, *, title: str | None = None) -> str:
    return heading_category(node_name, text, title=title)


def _normalize_table_inline_text(value: str) -> str:
    return normalize_table_inline_text(value)


def _has_explicit_bibliography_marker(node: Tag) -> bool:
    attrs = getattr(node, "attrs", None) or {}
    if "citation-ref" in attrs:
        return True
    if normalize_text(str(attrs.get("data-test") or "")).lower() == "citation-ref":
        return True
    if normalize_text(str(attrs.get("role") or "")).lower() == "doc-biblioref":
        return True
    if normalize_text(str(attrs.get("data-xml-rid") or "")):
        return True
    class_tokens = _class_tokens(node)
    return bool({"biblink", "to-citation"} & class_tokens)


def _numeric_citation_payload_from_inline_node(node: Any) -> str | None:
    if not isinstance(node, Tag):
        return None
    text = normalize_text(node.get_text(" ", strip=True))
    payload = numeric_citation_payload(text)
    if payload is None:
        return None
    href = normalize_text(str(node.get("href") or ""))
    if node.name == "a" and (_has_explicit_bibliography_marker(node) or is_citation_link(href, text)):
        return payload
    if node.name in {"sup", "i", "em"}:
        anchors = [match for match in node.find_all("a") if isinstance(match, Tag)]
        if anchors and all(_numeric_citation_payload_from_inline_node(anchor) for anchor in anchors):
            return payload
    return None


def _wrap_table_text_fragment(text: str, marker: str | None) -> str:
    return wrap_table_text_fragment(text, marker)


def _render_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    return render_table_inline_node(node, text_style=text_style)


def _render_table_inline_text(node: Any) -> str:
    return render_table_inline_text(node)


def _normalize_non_table_inline_text(value: str) -> str:
    return normalize_html_inline_text(value, policy="body")


def _render_non_table_inline_fragment(node: Any, *, text_style: str | None = None) -> str:
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    name = normalize_text(node.name or "").lower()
    payload = _numeric_citation_payload_from_inline_node(node)
    if payload is not None:
        return make_numeric_citation_sentinel(payload) or ""
    if name == "img" and _looks_like_formula_image_node(node):
        return _formula_image_markdown(node)
    if name == "a":
        return _render_non_table_inline_node(node, text_style=text_style)
    if name in {"i", "em"}:
        return _render_non_table_inline_node(node, text_style="*")
    if name in {"b", "strong"}:
        return _render_non_table_inline_node(node, text_style="**")
    if name == "sub":
        text = _render_non_table_inline_node(node)
        return f"<sub>{text}</sub>" if text else ""
    if name == "sup":
        text = _render_non_table_inline_node(node)
        return f"<sup>{text}</sup>" if text else ""
    if name == "br":
        return "<br>"
    return _render_non_table_inline_node(node, text_style=text_style)


def _render_non_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    if node is None:
        return ""
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    parts: list[str] = []
    for child in node.children:
        rendered_child = _render_non_table_inline_fragment(child, text_style=text_style)
        if rendered_child:
            parts.append(rendered_child)

    return _normalize_non_table_inline_text("".join(parts))


def _render_non_table_inline_text(node: Any) -> str:
    return _render_non_table_inline_node(node)


def _join_non_table_text_fragments(fragments: list[str]) -> str:
    joined = ""
    for fragment in fragments:
        normalized_fragment = normalize_text(fragment)
        if not normalized_fragment:
            continue
        if (
            joined
            and not joined.endswith((" ", "\n", "<br>", "(", "[", "{", "/"))
            and not normalized_fragment.startswith((".", ",", ";", ":", ")", "]", "}", "%", "<br>"))
        ):
            joined += " "
        joined += normalized_fragment
    return _normalize_non_table_inline_text(joined)


def _render_caption_text(node: Tag) -> str:
    fragments: list[str] = []
    direct_tag_children = 0
    for child in node.children:
        if NavigableString is not None and isinstance(child, NavigableString):
            text = _wrap_table_text_fragment(str(child), None)
        elif isinstance(child, Tag):
            direct_tag_children += 1
            text = _render_non_table_inline_fragment(child)
        else:
            text = ""
        if text:
            fragments.append(text)
    if direct_tag_children > 1:
        return _join_non_table_text_fragments(fragments)
    return _render_non_table_inline_text(node)


def _is_non_table_paragraph_node(node: Tag) -> bool:
    name = normalize_text(node.name or "").lower()
    if name in {"p", "li"}:
        return True
    if name == "div" and normalize_text(str((getattr(node, "attrs", None) or {}).get("role") or "")).lower() == "paragraph":
        return True
    return False


def _normalize_non_table_inline_blocks(container: Tag) -> None:
    candidates = [
        node
        for node in container.find_all(["p", "li", "div"])
        if isinstance(node, Tag) and node.parent is not None and _is_non_table_paragraph_node(node)
    ]
    for node in _dedupe_top_level_nodes(candidates):
        if node.find_parent("table") is not None:
            continue
        rendered = _render_non_table_inline_text(node)
        if not rendered:
            continue
        node.clear()
        node.append(rendered)


def _promotional_parent(node: Tag) -> Tag:
    current = node
    while isinstance(current.parent, Tag):
        parent = current.parent
        parent_text = _short_text(parent).lower()
        if not parent_text or len(parent_text) > 320:
            break
        if any(token in parent_text for token in PROMO_BLOCK_TOKENS) or parent_text == "learn more":
            current = parent
            continue
        break
    return current


def _drop_promotional_blocks(container: Tag, publisher: str) -> None:
    if publisher != "pnas":
        return
    for node in list(container.find_all(True)):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        text = _short_text(node).lower()
        if not text or len(text) > 220:
            continue
        if any(token in text for token in PROMO_BLOCK_TOKENS) or text == "learn more":
            _promotional_parent(node).decompose()


def _structural_abstract_nodes(container: Tag) -> list[Tag]:
    abstract_roots: list[Tag] = []
    if normalize_text(((getattr(container, "attrs", None) or {}).get("id") or "")).lower() == "abstracts":
        abstract_roots.append(container)
    try:
        abstract_roots.extend([node for node in container.select("#abstracts") if isinstance(node, Tag)])
    except Exception:
        pass

    sections: list[Tag] = []
    seen: set[int] = set()
    for root in abstract_roots:
        search_parents = [child for child in _direct_child_tags(root) if "core-container" in _class_tokens(child)] or [root]
        for parent in search_parents:
            for child in _direct_child_tags(parent):
                if normalize_text(child.name or "").lower() != "section":
                    continue
                if normalize_text(child.get("role") or "").lower() != "doc-abstract":
                    continue
                if id(child) in seen:
                    continue
                seen.add(id(child))
                sections.append(child)
    return sections


def _abstract_nodes(container: Tag) -> list[Tag]:
    structural_nodes = _structural_abstract_nodes(container)
    if structural_nodes:
        return structural_nodes
    nodes: list[Tag] = []
    for selector in CONTENT_ABSTRACT_SELECTORS:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _node_language_hint(node: Tag) -> str | None:
    return html_node_language_hint(node, allow_soft_hints=True)


def _abstract_section_payloads(container: Tag) -> list[dict[str, Any]]:
    structural_nodes = _structural_abstract_nodes(container)
    if structural_nodes:
        payloads: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for order, node in enumerate(structural_nodes):
            heading = _short_text(node.find(HEADING_TAG_PATTERN)) or "Abstract"
            text = normalize_text("\n\n".join(_abstract_block_texts(node)))
            if not text:
                continue
            key = (normalize_heading(heading), normalize_text(text))
            if key in seen:
                continue
            seen.add(key)
            payloads.append(
                {
                    "heading": normalize_text(heading) or "Abstract",
                    "text": text,
                    "language": _node_language_hint(node),
                    "kind": "abstract",
                    "order": order,
                    "source_selector": node_source_selector(node) or None,
                }
            )
        return payloads
    return [
        payload
        for payload in collect_html_abstract_blocks(container)
        if normalize_text(payload.get("text"))
    ]


def _drop_abstract_sections_from_body_container(container: Tag, publisher: str) -> None:
    if publisher != "wiley":
        return
    for node in _abstract_nodes(container):
        node.decompose()


def _normalize_abstract_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    for node in _abstract_nodes(container):
        if node.name not in {"section", "div"}:
            node.name = "section"
        heading = node.find(HEADING_TAG_PATTERN)
        if isinstance(heading, Tag):
            heading.name = "h2"
            if not normalize_heading(_short_text(heading)):
                heading.string = "Abstract"
            continue
        heading = soup.new_tag("h2")
        heading.string = "Abstract"
        node.insert(0, heading)


def _markdown_has_abstract_heading(markdown_text: str) -> bool:
    for block in re.split(r"\n\s*\n", markdown_text):
        heading_info = _markdown_heading_info(block)
        if heading_info is None:
            continue
        level, heading_text = heading_info
        if _heading_category(f"h{min(level, 6)}", heading_text) == "abstract":
            return True
    return False


def _ensure_body_markdown_heading(markdown_text: str, *, title: str | None = None) -> str:
    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    if not blocks:
        return normalize_markdown_text(markdown_text)

    normalized_title = normalize_heading(title or "")
    first_heading = _markdown_heading_info(blocks[0])
    if first_heading is None:
        return clean_markdown(f"## Main Text\n\n{markdown_text}", noise_profile=None)

    _, heading_text = first_heading
    if normalized_title and normalize_heading(heading_text) == normalized_title:
        if len(blocks) < 2:
            return normalize_markdown_text(markdown_text)
        second_heading = _markdown_heading_info(blocks[1])
        if second_heading is None:
            return clean_markdown(
                "\n\n".join([blocks[0], "## Main Text", *blocks[1:]]),
                noise_profile=None,
            )
    return normalize_markdown_text(markdown_text)


def _abstract_block_texts(node: Tag) -> list[str]:
    heading = node.find(HEADING_TAG_PATTERN)
    texts: list[str] = []
    seen: set[str] = set()

    for candidate in node.find_all(True):
        if candidate is heading:
            continue
        if normalize_text(candidate.get("role") or "").lower() == "paragraph" or candidate.name in {"p", "li"}:
            text = _render_non_table_inline_text(candidate)
            if text and text not in seen:
                texts.append(text)
                seen.add(text)

    if texts:
        return texts

    fallback_text = _render_non_table_inline_text(node)
    heading_text = _short_text(heading)
    if heading_text:
        pattern = re.compile(rf"^{re.escape(heading_text)}[:\s-]*", flags=re.IGNORECASE)
        fallback_text = normalize_text(pattern.sub("", fallback_text, count=1))
    return [fallback_text] if fallback_text else []


def _missing_abstract_markdown(container: Tag, markdown_text: str, *, publisher: str) -> str:
    existing_normalized = normalize_text(markdown_text)
    leading_semantic_text = _leading_semantic_markdown_text(markdown_text)
    if publisher == "pnas" and _markdown_has_heading(markdown_text, "significance") and _markdown_has_heading(
        markdown_text,
        "abstract",
    ):
        return ""
    abstract_blocks: list[str] = []
    for payload in _abstract_section_payloads(container):
        heading_text = normalize_text(payload.get("heading")) or "Abstract"
        body_text = normalize_text(payload.get("text"))
        normalized_body_text = normalize_text(body_text)
        if normalized_body_text and normalized_body_text in existing_normalized:
            continue
        if _semantic_text_matches(body_text, leading_semantic_text):
            continue
        abstract_blocks.append(f"## {heading_text}\n\n{body_text}")

    if not abstract_blocks:
        return ""
    return clean_markdown(
        "\n\n".join(abstract_blocks),
        noise_profile=_noise_profile_for_publisher(publisher),
    )


def _mathml_element_from_node(node: Tag | None):
    return mathml_element_from_html_node(node)


def _latex_from_math_node(node: Tag, *, display_mode: bool) -> str:
    element = _mathml_element_from_node(node)
    if element is not None:
        expression = normalize_text(render_external_mathml_expression(element, display_mode=display_mode))
        if expression:
            return expression
    return _short_text(node)


def _formula_image_url_from_node(node: Tag) -> str:
    return formula_image_url_from_node(node, include_adjacent=True)


def _looks_like_formula_image_node(node: Tag) -> bool:
    return looks_like_formula_image(node, _formula_image_url_from_node(node))


def _formula_image_markdown(node: Tag) -> str:
    url = _formula_image_url_from_node(node)
    return f"![Formula]({url})" if url else ""


def _display_formula_nodes(container: Tag) -> list[Tag]:
    return _dedupe_top_level_nodes(
        [node for node in display_formula_nodes(container) if isinstance(node, Tag)]
    )


def _equation_label(node: Tag) -> str:
    candidates: list[str] = []
    for candidate in (
        node.select_one(".label"),
        node.find_previous_sibling(class_="label"),
    ):
        if isinstance(candidate, Tag):
            candidates.append(_short_text(candidate))
    node_id = normalize_text(str((getattr(node, "attrs", None) or {}).get("id") or ""))
    if node_id:
        id_match = re.search(r"(?:^|[-_])(?:disp|eq|equation)[-_]?0*([0-9]+[A-Za-z]?)$", node_id, flags=re.IGNORECASE)
        if id_match:
            return f"Equation {id_match.group(1)}."
        candidates.append(node_id)
    for text in candidates:
        match = EQUATION_NUMBER_PATTERN.search(text)
        if match:
            return f"Equation {match.group(1)}."
    return ""


def _display_formula_replacement(node: Tag, soup: BeautifulSoup) -> Tag | None:
    latex = _latex_from_math_node(node, display_mode=True)
    replacement = soup.new_tag("div")
    label = _equation_label(node)
    if label:
        _append_text_block(replacement, f"**{label}**", soup=soup)
    if latex:
        for line in ("$$", latex, "$$"):
            _append_text_block(replacement, line, soup=soup)
        return replacement
    image_markdown = _formula_image_markdown(node)
    if image_markdown:
        _append_text_block(replacement, image_markdown, soup=soup)
        return replacement
    _append_text_block(replacement, "[Formula unavailable]", soup=soup)
    return replacement


def _direct_child_with_parent(node: Tag, parent: Tag) -> Tag | None:
    current: Tag | None = node
    while isinstance(current, Tag) and current.parent is not None:
        if current.parent is parent:
            return current
        current = current.parent if isinstance(current.parent, Tag) else None
    return None


def _clone_shallow_tag(node: Tag, soup: BeautifulSoup) -> Tag:
    clone = soup.new_tag(node.name)
    clone.attrs = copy.deepcopy(getattr(node, "attrs", None) or {})
    return clone


def _insert_split_paragraph(parent: Tag, children: list[Any], soup: BeautifulSoup) -> None:
    segment = _clone_shallow_tag(parent, soup)
    for child in children:
        if (NavigableString is not None and isinstance(child, NavigableString)) or isinstance(child, Tag):
            segment.append(child.extract())
    if normalize_text(segment.get_text(" ", strip=True)):
        parent.insert_before(segment)
        return
    segment.decompose()


def _split_paragraph_display_formula_blocks(parent: Tag, soup: BeautifulSoup) -> bool:
    formula_nodes: dict[int, Tag] = {}
    for formula_node in _display_formula_nodes(parent):
        direct_child = _direct_child_with_parent(formula_node, parent)
        if isinstance(direct_child, Tag):
            formula_nodes[id(direct_child)] = formula_node
    if not formula_nodes:
        return False

    pending_children: list[Any] = []
    for child in list(parent.contents):
        formula_node = formula_nodes.get(id(child))
        if formula_node is None:
            pending_children.append(child)
            continue
        replacement = _display_formula_replacement(formula_node, soup)
        if pending_children:
            _insert_split_paragraph(parent, pending_children, soup)
            pending_children = []
        if replacement is not None:
            parent.insert_before(replacement)
    if pending_children:
        _insert_split_paragraph(parent, pending_children, soup)
    parent.decompose()
    return True


def _normalize_display_formula_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    handled_parents: set[int] = set()
    nodes = _display_formula_nodes(container)
    for node in nodes:
        if not isinstance(node, Tag) or not isinstance(node.parent, Tag):
            continue
        parent = node.parent
        if not _is_non_table_paragraph_node(parent) or id(parent) in handled_parents:
            continue
        if _split_paragraph_display_formula_blocks(parent, soup):
            handled_parents.add(id(parent))

    for node in nodes:
        if not isinstance(node, Tag) or node.parent is None:
            continue
        replacement = _display_formula_replacement(node, soup)
        if replacement is None:
            continue
        node.replace_with(replacement)


def _is_display_formula_math(node: Tag) -> bool:
    return is_display_formula_node(node)


def _inline_math_replacement_target(node: Tag) -> Tag:
    for current in (
        node.find_parent("mjx-container"),
        node.find_parent("mjx-assistive-mml"),
    ):
        if isinstance(current, Tag):
            return current
    return node


def _normalize_inline_math_nodes(container: Tag) -> None:
    for math_node in list(container.find_all("math")):
        if not isinstance(math_node, Tag) or math_node.parent is None:
            continue
        if _is_display_formula_math(math_node):
            continue
        latex = _latex_from_math_node(math_node, display_mode=False)
        if not latex:
            continue
        _inline_math_replacement_target(math_node).replace_with(f"${latex}$")


def _normalize_inline_formula_image_nodes(container: Tag) -> None:
    for image in list(container.find_all("img")):
        if not isinstance(image, Tag) or image.parent is None:
            continue
        if not _looks_like_formula_image_node(image):
            continue
        image.replace_with(_formula_image_markdown(image))


def _caption_label(node: Tag, *, kind: str) -> str:
    label_pattern = FIGURE_LABEL_PATTERN if kind == "Figure" else TABLE_LABEL_PATTERN
    for candidate in (
        node.select_one("header .label"),
        node.select_one(".label"),
    ):
        if isinstance(candidate, Tag):
            text = _short_text(candidate)
            match = label_pattern.search(text)
            if match:
                return f"{kind} {match.group(1)}."
    match = label_pattern.search(_short_text(node))
    if match:
        return f"{kind} {match.group(1)}."
    return kind


def _caption_text(node: Tag) -> str:
    for selector in (".figure__caption-text", "figcaption", ".figure__caption", "[role='doc-caption']", ".caption"):
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _render_caption_text(candidate)
            if text:
                return text
    return ""


def _strip_caption_label(text: str, label: str) -> str:
    label_text = normalize_text(label).rstrip(".")
    if not label_text:
        return text
    variants = [label_text]
    if label_text.lower().startswith("figure "):
        variants.append(f"Fig. {label_text.split(' ', 1)[1]}")
    for variant in variants:
        text = re.sub(rf"^{re.escape(variant)}\.?\s*", "", text, flags=re.IGNORECASE)
    return normalize_text(text).lstrip(".:;,-) ]")


def _table_caption_text(node: Tag, label: str) -> str:
    for selector in (".article-table-caption", ".caption", "figcaption", "caption", "header"):
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _strip_caption_label(_render_caption_text(candidate), label)
            if text:
                return text
    return ""


def _is_glossary_table(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        if "list-paired" in node_identity_text(current):
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _table_like_nodes(container: Tag) -> list[Tag]:
    nodes: list[Tag] = []
    for table in container.find_all("table"):
        if not isinstance(table, Tag):
            continue
        if _is_glossary_table(table):
            continue
        identity = _ancestor_identity_text(table)
        if any(token in identity for token in BACK_MATTER_TOKENS + ANCILLARY_TOKENS):
            continue
        best: Tag = table
        current = table.parent if isinstance(table.parent, Tag) else None
        depth = 0
        while isinstance(current, Tag) and current is not container and depth < 8:
            current_identity = node_identity_text(current)
            if (
                current.name == "figure"
                or "figure-wrap" in current_identity
                or "table-wrap" in current_identity
                or "article-table" in current_identity
                or current_identity.startswith("table ")
                or " table " in f" {current_identity} "
            ):
                best = current
            current = current.parent if isinstance(current.parent, Tag) else None
            depth += 1
        nodes.append(best)
    return _dedupe_top_level_nodes(nodes)


def _first_abstract_node(container: Tag) -> Tag | None:
    nodes = _abstract_nodes(container)
    return nodes[0] if nodes else None


def _is_front_matter_teaser_figure(node: Tag, *, publisher: str, abstract_anchor: Tag | None = None) -> bool:
    if publisher != "science":
        return False
    if _caption_label(node, kind="Figure") != "Figure":
        return False
    if any(token in _ancestor_identity_text(node) for token in ABSTRACT_TOKENS):
        return True
    if abstract_anchor is None:
        return False
    return abstract_anchor in node.find_all_next()


def _drop_front_matter_teaser_figures(container: Tag, publisher: str) -> None:
    abstract_anchor = _first_abstract_node(container)
    if abstract_anchor is None:
        return
    for node in list(container.find_all("figure")):
        if isinstance(node, Tag) and _is_front_matter_teaser_figure(node, publisher=publisher, abstract_anchor=abstract_anchor):
            node.decompose()


def _drop_table_blocks(container: Tag) -> None:
    for node in list(_table_like_nodes(container)):
        if isinstance(node, Tag):
            node.decompose()


def _figure_like_nodes(container: Tag) -> list[Tag]:
    table_nodes = _table_like_nodes(container)
    abstract_anchor = _first_abstract_node(container)
    nodes: list[Tag] = []
    for selector in (".figure-wrap", "figure"):
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag):
                continue
            if any(
                match is table_node or _is_descendant(match, table_node) or _is_descendant(table_node, match)
                for table_node in table_nodes
            ):
                continue
            if _is_front_matter_teaser_figure(match, publisher="science", abstract_anchor=abstract_anchor):
                continue
            if any(token in _ancestor_identity_text(match) for token in BACK_MATTER_TOKENS + ANCILLARY_TOKENS):
                continue
            if match.find("table") is not None:
                continue
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _table_cell_data(cell: Tag) -> dict[str, Any]:
    return table_cell_data(cell, render_inline_text=_render_table_inline_text)


def _table_rows(table: Tag) -> list[list[dict[str, Any]]]:
    return table_rows(table, render_inline_text=_render_table_inline_text)


def _table_header_row_count(table: Tag, rows: list[list[dict[str, Any]]]) -> int:
    return table_header_row_count(table, rows)


def _expanded_table_matrix(rows: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]] | None:
    return expanded_table_matrix(rows)


def _flatten_table_header_rows(rows: list[list[dict[str, Any]]]) -> list[str]:
    return flatten_table_header_rows(rows)


def _table_headers_and_data(table: Tag) -> tuple[list[str], list[list[dict[str, Any]]], bool]:
    return table_headers_and_data(table, render_inline_text=_render_table_inline_text)


def _escape_markdown_table_cell(text: str) -> str:
    return escape_markdown_table_cell(text)


def _render_aligned_markdown_table(matrix: list[list[str]]) -> list[str]:
    return render_aligned_markdown_table(matrix)


def _render_table_markdown(table_node: Tag, *, label: str, caption: str) -> str:
    return render_table_markdown(
        table_node,
        label=label,
        caption=caption,
        render_inline_text=_render_table_inline_text,
    )


def _table_placeholder(index: int) -> str:
    return table_placeholder(index)


def _normalize_table_blocks(container: Tag) -> list[dict[str, str]]:
    soup = _soup_root(container)
    if soup is None:
        return []

    entries: list[dict[str, str]] = []
    for node in _table_like_nodes(container):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        label = _caption_label(node, kind="Table")
        caption = _table_caption_text(node, label)
        rendered_markdown = _render_table_markdown(node, label=label, caption=caption)
        if not rendered_markdown:
            continue
        placeholder = _table_placeholder(len(entries) + 1)
        block = soup.new_tag("p")
        block.string = placeholder
        node.replace_with(block)
        entries.append({"placeholder": placeholder, "markdown": rendered_markdown})
    return entries


def _normalize_figure_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    for node in _figure_like_nodes(container):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        label = _caption_label(node, kind="Figure")
        caption = _strip_caption_label(_caption_text(node), label)
        if not caption and label == "Figure":
            continue
        block = soup.new_tag("p")
        block.string = f"**{label}** {caption}".strip()
        node.replace_with(block)


def _normalize_special_blocks(container: Tag, publisher: str) -> list[dict[str, str]]:
    _drop_promotional_blocks(container, publisher)
    _normalize_abstract_blocks(container)
    _drop_front_matter_teaser_figures(container, publisher)
    _normalize_display_formula_blocks(container)
    _normalize_inline_math_nodes(container)
    _normalize_inline_formula_image_nodes(container)
    table_entries = _normalize_table_blocks(container)
    _normalize_figure_blocks(container)
    _normalize_non_table_inline_blocks(container)
    profile = _publisher_profile(publisher)
    if profile.dom_postprocess is not None:
        profile.dom_postprocess(container)
    return table_entries


def extract_page_title(soup: BeautifulSoup) -> str | None:
    for selector in ["h1", "meta[property='og:title']", "title"]:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_text((getattr(node, "attrs", None) or {}).get("content", ""))
        elif node.name == "h1":
            title = _render_non_table_inline_text(node)
        else:
            title = normalize_text(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def _ancestor_identity_text(node: Tag | None) -> str:
    return ancestor_identity_text(node)


def _looks_like_front_matter_paragraph(text: str, *, title: str | None = None) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not normalized:
        return True
    if title and lowered == normalize_text(title).lower():
        return True
    if lowered in FRONT_MATTER_EXACT_TEXTS:
        return True
    if "authors info" in lowered or "affiliations" in lowered:
        return True
    if len(normalized) <= 80 and normalized.upper() == normalized and len(normalized.split()) <= 5:
        return True
    if lowered.startswith("by ") and _sentence_count(normalized) <= 1:
        return True
    if any(pattern.match(normalized) for pattern in FRONT_MATTER_LINE_PATTERNS):
        return True
    return lowered in {"science", "pnas", "wiley interdisciplinary reviews"}


def _looks_like_access_gate_text(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if any(pattern in lowered for pattern in PAYWALL_PATTERNS):
        return True
    return any(
        pattern in lowered
        for pattern in (
            "get access",
            "sign in to access",
            "view access options",
            "access provided by",
            "institutional login",
            "purchase article",
        )
    )


def _markdown_heading_info(block: str) -> tuple[int, str] | None:
    return parse_markdown_heading(block)


def _looks_like_post_content_noise_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if any(token in lowered for token in PROMO_BLOCK_TOKENS) or lowered == "learn more":
        return True
    if lowered in POST_CONTENT_BREAK_TEXTS:
        return True
    if any(lowered.startswith(prefix) for prefix in POST_CONTENT_BREAK_PREFIXES):
        return True
    return any(token in lowered for token in POST_CONTENT_BREAK_TOKENS)


def _looks_like_markdown_auxiliary_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if lowered == "$$":
        return True
    return lowered.startswith("**equation") or lowered.startswith("**figure") or lowered.startswith("**table")


def _is_descendant(node: Tag, candidate_ancestor: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        if current is candidate_ancestor:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _dedupe_top_level_nodes(nodes: list[Tag]) -> list[Tag]:
    deduped: list[Tag] = []
    seen: set[int] = set()
    for node in nodes:
        if id(node) in seen:
            continue
        if any(_is_descendant(node, existing) for existing in deduped):
            continue
        deduped = [existing for existing in deduped if not _is_descendant(existing, node)]
        deduped.append(node)
        seen.add(id(node))
    return deduped


def _nodes_from_selectors(container: Tag, selectors: tuple[str, ...]) -> list[Tag]:
    nodes: list[Tag] = []
    for selector in selectors:
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _availability_node_score(node: Tag) -> int:
    score = 0
    identity = _ancestor_identity_text(node)
    node_id = normalize_text(str((getattr(node, "attrs", None) or {}).get("id") or "")).lower()
    if node_id in {"data-availability", "code-availability", "software-availability"}:
        score += 120
    if normalize_text(node.name or "").lower() == "section":
        score += 10
    if any(token in identity for token in BODY_CONTAINER_TOKENS):
        score += 40
    if any(token in identity for token in DATA_AVAILABILITY_TOKENS + CODE_AVAILABILITY_TOKENS):
        score += 20
    heading = node.find(HEADING_TAG_PATTERN)
    if isinstance(heading, Tag):
        heading_kind = _heading_category(normalize_text(heading.name or "").lower(), heading.get_text(" ", strip=True))
        if heading_kind in {"data_availability", "code_availability"}:
            score += 40
    if any(token in identity for token in ANCILLARY_TOKENS):
        score -= 60
    if any(token in identity for token in ("collateral", "tabpanel", "tab-panel", "tab_panel", "info-panel", "info_panel")):
        score -= 120
    return score


def _select_availability_nodes(container: Tag, body_nodes: list[Tag]) -> list[Tag]:
    chosen_by_text: dict[str, tuple[int, int, Tag]] = {}
    for index, node in enumerate(_nodes_from_selectors(container, CONTENT_AVAILABILITY_SELECTORS)):
        if any(_is_descendant(node, body_node) for body_node in body_nodes):
            continue
        text_key = normalize_text(node.get_text(" ", strip=True)).lower()
        if not text_key:
            continue
        candidate = (_availability_node_score(node), index, node)
        current = chosen_by_text.get(text_key)
        if current is None or candidate[0] > current[0]:
            chosen_by_text[text_key] = candidate
    return _dedupe_top_level_nodes(
        [entry[2] for entry in sorted(chosen_by_text.values(), key=lambda entry: entry[1])]
    )


def _select_content_nodes(container: Tag, *, publisher: str | None = None) -> list[Tag]:
    profile = _publisher_profile(publisher)
    if profile.select_content_nodes is not None:
        provider_nodes = profile.select_content_nodes(
            container,
            structural_abstract_nodes=_structural_abstract_nodes,
            nodes_from_selectors=_nodes_from_selectors,
            content_abstract_selectors=CONTENT_ABSTRACT_SELECTORS,
            content_body_selectors=CONTENT_BODY_SELECTORS,
            select_availability_nodes=_select_availability_nodes,
            dedupe_top_level_nodes=_dedupe_top_level_nodes,
            is_tag=lambda node: isinstance(node, Tag),
        )
        if provider_nodes:
            return provider_nodes

    selected: list[Tag] = []
    abstract_nodes = _nodes_from_selectors(container, CONTENT_ABSTRACT_SELECTORS)
    body_nodes = _nodes_from_selectors(container, CONTENT_BODY_SELECTORS)
    availability_nodes = _select_availability_nodes(container, body_nodes)
    selected.extend(abstract_nodes)
    selected.extend(body_nodes)
    selected.extend(availability_nodes)

    return _dedupe_top_level_nodes(selected)


def _content_fragment_html(container: Tag, *, publisher: str | None = None) -> str:
    content_nodes = _select_content_nodes(container, publisher=publisher)
    if not content_nodes:
        return str(container)
    return "<div>" + "".join(str(node) for node in content_nodes) + "</div>"


def _strip_heading_terminal_punctuation(heading_text: str) -> str:
    normalized = normalize_text(heading_text)
    if normalized.endswith("."):
        return normalized[:-1].rstrip()
    return normalized


def _inject_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    publisher: str,
) -> str:
    return inject_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def rewrite_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    publisher: str,
) -> str:
    return _science_pnas_postprocess.rewrite_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def _inject_inline_table_blocks(
    markdown_text: str,
    *,
    table_entries: list[Mapping[str, str]] | None,
    publisher: str,
) -> str:
    return inject_inline_table_blocks(
        markdown_text,
        table_entries=table_entries,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile=_noise_profile_for_publisher(publisher),
        ),
    )


def _known_abstract_block_texts(container: Tag) -> list[str]:
    return _abstract_block_texts_from_payloads(_abstract_section_payloads(container))


def _abstract_block_texts_from_payloads(payloads: list[Mapping[str, Any]] | None) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for payload in payloads or []:
        normalized = normalize_text(normalize_markdown_text(str(payload.get("text") or "")))
        if normalized and normalized not in seen:
            texts.append(normalized)
            seen.add(normalized)
    return texts


def _semantic_match_text(value: str) -> str:
    normalized = normalize_text(normalize_markdown_text(str(value or ""))).lower()
    if not normalized:
        return ""
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _shared_prefix_word_count(left_words: list[str], right_words: list[str]) -> int:
    count = 0
    for left_word, right_word in zip(left_words, right_words):
        if left_word != right_word:
            break
        count += 1
    return count


def _semantic_text_matches(left: str, right: str) -> bool:
    left_text = _semantic_match_text(left)
    right_text = _semantic_match_text(right)
    if not left_text or not right_text:
        return False
    if left_text == right_text or left_text in right_text or right_text in left_text:
        return True

    left_words = left_text.split()
    right_words = right_text.split()
    shared_prefix_words = _shared_prefix_word_count(left_words, right_words)
    required_prefix_words = min(24, max(12, min(len(left_words), len(right_words)) // 3))
    return shared_prefix_words >= required_prefix_words


def _leading_semantic_markdown_text(markdown_text: str, *, limit: int = 6) -> str:
    leading_blocks: list[str] = []
    for block in re.split(r"\n\s*\n", markdown_text):
        normalized_block = normalize_text(block)
        if not normalized_block:
            continue
        heading_info = _markdown_heading_info(block)
        if heading_info is not None:
            continue
        if _looks_like_markdown_auxiliary_block(normalized_block):
            continue
        if not _is_substantial_prose(normalized_block):
            continue
        leading_blocks.append(block)
        if len(leading_blocks) >= limit:
            break
    return "\n\n".join(leading_blocks)


def _markdown_has_heading(markdown_text: str, heading_text: str) -> bool:
    normalized_target = normalize_heading(heading_text)
    if not normalized_target:
        return False
    for block in re.split(r"\n\s*\n", markdown_text):
        heading_info = _markdown_heading_info(block)
        if heading_info is None:
            continue
        _, current_heading = heading_info
        if normalize_heading(current_heading) == normalized_target:
            return True
    return False


def _block_matches_known_abstract_text(block: str, abstract_block_texts: list[str]) -> bool:
    normalized_block = normalize_text(normalize_markdown_text(block))
    if not normalized_block:
        return False
    for known in abstract_block_texts:
        if not known:
            continue
        if normalized_block == known or normalized_block in known or known in normalized_block:
            return True
        if _semantic_text_matches(block, known):
            return True
    return False


def _normalize_browser_workflow_markdown(markdown_text: str, *, publisher: str) -> str:
    return normalize_browser_workflow_markdown(
        markdown_text,
        markdown_postprocess=_publisher_profile(publisher).markdown_postprocess,
    )


def _postprocess_browser_workflow_markdown(
    markdown_text: str,
    *,
    title: str | None,
    publisher: str,
    figure_assets: list[Mapping[str, Any]] | None = None,
    table_entries: list[Mapping[str, str]] | None = None,
    abstract_block_texts: list[str] | None = None,
) -> str:
    markdown_text = _normalize_browser_workflow_markdown(markdown_text, publisher=publisher)
    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    kept: list[str] = []
    normalized_title = normalize_text(title or "")
    normalized_title_lower = normalized_title.lower()
    known_abstract_blocks = [normalize_text(text) for text in abstract_block_texts or [] if normalize_text(text)]
    title_kept = False
    started_content = False
    in_front_matter = False
    in_abstract = False
    in_back_matter = False
    in_data_availability = False
    abstract_prose_blocks_seen = 0

    for block in blocks:
        heading_info = _markdown_heading_info(block)
        if heading_info is not None:
            level, heading_text = heading_info
            normalized_heading = normalize_heading(heading_text)
            if normalized_title and normalized_heading == normalized_title_lower:
                if not title_kept:
                    kept.append(f"# {normalized_title}")
                    title_kept = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue

            category = _heading_category(f"h{min(level, 6)}", heading_text, title=normalized_title or None)
            if category == "front_matter":
                in_front_matter = True
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue
            if category in {"references_or_back_matter", "ancillary"}:
                if category == "ancillary" and started_content:
                    break
                in_front_matter = False
                in_abstract = False
                in_back_matter = category == "references_or_back_matter"
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue
            if category == "abstract":
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                kept.append(block)
                started_content = True
                in_front_matter = False
                in_abstract = True
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue
            if category in {"data_availability", "code_availability"}:
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                cleaned_heading = _strip_heading_terminal_punctuation(heading_text)
                kept.append(f"{'#' * level} {cleaned_heading}")
                started_content = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = True
                abstract_prose_blocks_seen = 0
                continue
            if category == "body_heading":
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                cleaned_heading = _strip_heading_terminal_punctuation(heading_text)
                kept.append(f"{'#' * level} {cleaned_heading}")
                started_content = True
                in_front_matter = False
                in_abstract = False
                in_back_matter = False
                in_data_availability = False
                abstract_prose_blocks_seen = 0
                continue

        normalized_block = normalize_text(block)
        if not normalized_block:
            continue
        is_auxiliary_block = _looks_like_markdown_auxiliary_block(normalized_block)
        if _looks_like_post_content_noise_block(normalized_block):
            if started_content:
                break
            continue
        if in_front_matter:
            continue
        if in_abstract:
            if (
                known_abstract_blocks
                and _is_substantial_prose(normalized_block)
                and not is_auxiliary_block
                and not _block_matches_known_abstract_text(block, known_abstract_blocks)
            ):
                if publisher == "science" and abstract_prose_blocks_seen == 0:
                    if not title_kept and normalized_title:
                        kept.insert(0, f"# {normalized_title}")
                        title_kept = True
                    kept.append(block)
                    started_content = True
                    abstract_prose_blocks_seen += 1
                    continue
                kept.append("## Main Text")
                in_abstract = False
                abstract_prose_blocks_seen = 0
            else:
                if not title_kept and normalized_title:
                    kept.insert(0, f"# {normalized_title}")
                    title_kept = True
                kept.append(block)
                started_content = True
                if _is_substantial_prose(normalized_block) and not is_auxiliary_block:
                    abstract_prose_blocks_seen += 1
                continue
        if in_back_matter:
            continue
        if in_data_availability:
            if not title_kept and normalized_title:
                kept.insert(0, f"# {normalized_title}")
                title_kept = True
            kept.append(block)
            started_content = True
            continue
        if _looks_like_access_gate_text(normalized_block):
            if started_content:
                break
            continue
        if not started_content and is_auxiliary_block:
            continue
        if not is_auxiliary_block and _looks_like_front_matter_paragraph(normalized_block, title=normalized_title or None):
            continue
        if not started_content and not is_auxiliary_block and not _is_substantial_prose(normalized_block):
            continue
        if not title_kept and normalized_title:
            kept.insert(0, f"# {normalized_title}")
            title_kept = True
        kept.append(block)
        started_content = True

    if not kept and normalized_title:
        kept.append(f"# {normalized_title}")
    elif normalized_title and not any(
        (_markdown_heading_info(block) or (0, ""))[1].lower() == normalized_title_lower for block in kept
    ):
        kept.insert(0, f"# {normalized_title}")
    cleaned = clean_markdown(
        "\n\n".join(kept),
        noise_profile=_noise_profile_for_publisher(publisher),
    )
    cleaned = _normalize_browser_workflow_markdown(cleaned, publisher=publisher)
    cleaned = _inject_inline_table_blocks(cleaned, table_entries=table_entries, publisher=publisher)
    cleaned = _normalize_browser_workflow_markdown(cleaned, publisher=publisher)
    return _inject_inline_figure_links(
        cleaned,
        figure_assets=figure_assets,
        publisher=publisher,
    )


def extract_browser_workflow_markdown(
    html_text: str,
    source_url: str,
    publisher: str,
    *,
    metadata: ProviderMetadata | Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    if BeautifulSoup is None:
        raise SciencePnasHtmlFailure("missing_bs4", "BeautifulSoup is required for browser-workflow HTML extraction.")

    soup = BeautifulSoup(html_text, choose_parser())
    title = extract_page_title(soup)
    container = select_best_container(soup, publisher, policy=_container_selection_policy(publisher))
    if container is None:
        raise SciencePnasHtmlFailure(
            "article_container_not_found",
            "Could not identify the main article container in publisher HTML.",
        )

    clean_container(container, publisher, drop_profile=HTML_CONTAINER_DROP_BROWSER_WORKFLOW)
    from .html_assets import extract_figure_assets

    asset_container = copy.deepcopy(container)
    _normalize_abstract_blocks(asset_container)
    _drop_front_matter_teaser_figures(asset_container, publisher)
    _drop_table_blocks(asset_container)
    figure_assets = extract_figure_assets(_content_fragment_html(asset_container, publisher=publisher), source_url)

    table_entries = _normalize_special_blocks(container, publisher)
    abstract_sections = _abstract_section_payloads(container)
    abstract_block_texts = _abstract_block_texts_from_payloads(abstract_sections)
    body_container = copy.deepcopy(container)
    _drop_abstract_sections_from_body_container(body_container, publisher)
    section_hints = collect_html_section_hints(
        body_container,
        title=title,
        language_hint_resolver=_node_language_hint,
    )
    container_html = _content_fragment_html(body_container, publisher=publisher)
    noise_profile = _noise_profile_for_publisher(publisher)
    markdown = clean_markdown(
        extract_article_markdown(
            container_html,
            source_url,
            trafilatura_backend=None,
            noise_profile=noise_profile,
        ),
        noise_profile=noise_profile,
    )
    if abstract_sections:
        markdown = _ensure_body_markdown_heading(markdown, title=title)
    abstract_markdown = _missing_abstract_markdown(container, markdown, publisher=publisher)
    if abstract_markdown:
        markdown = clean_markdown(f"{abstract_markdown}\n\n{markdown}", noise_profile=noise_profile)
    if title and f"# {title}" not in markdown:
        markdown = f"# {title}\n\n{markdown}".strip() + "\n"
    markdown = _inject_inline_table_blocks(markdown, table_entries=table_entries, publisher=publisher)
    markdown = _postprocess_browser_workflow_markdown(
        markdown,
        title=title,
        publisher=publisher,
        figure_assets=figure_assets,
        table_entries=table_entries,
        abstract_block_texts=abstract_block_texts,
    )

    quality_metadata = dict(metadata or {})
    if title and not quality_metadata.get("title"):
        quality_metadata["title"] = title
    diagnostics = assess_html_fulltext_availability(
        markdown,
        quality_metadata,
        provider=publisher,
        html_text=html_text,
        title=title,
        final_url=source_url,
        container_tag=container.name,
        container_text_length=len(" ".join(container.stripped_strings)),
        section_hints=section_hints,
    )
    if not diagnostics.accepted:
        raise SciencePnasHtmlFailure(diagnostics.reason, availability_failure_message(diagnostics))

    extraction_payload = {
        "title": title,
        "abstract_text": normalize_text(abstract_sections[0]["text"]) if abstract_sections else ("\n\n".join(abstract_block_texts) if abstract_block_texts else None),
        "abstract_sections": abstract_sections,
        "section_hints": section_hints,
        "container_tag": container.name,
        "container_text_length": len(" ".join(container.stripped_strings)),
        "availability_diagnostics": diagnostics.to_dict(),
    }
    profile = _publisher_profile(publisher)
    if profile.finalize_extraction is not None:
        markdown, extraction_payload = profile.finalize_extraction(
            html_text,
            source_url,
            markdown,
            extraction_payload,
            metadata=metadata,
        )
    return markdown, extraction_payload


def extract_browser_workflow_asset_html_scopes(
    html_text: str,
    source_url: str,
    publisher: str,
) -> tuple[str, str]:
    del source_url
    if BeautifulSoup is None:
        raise SciencePnasHtmlFailure("missing_bs4", "BeautifulSoup is required for browser-workflow HTML asset extraction.")

    soup = BeautifulSoup(html_text, choose_parser())
    container = select_best_container(soup, publisher, policy=_container_selection_policy(publisher))
    if container is None:
        raise SciencePnasHtmlFailure(
            "article_container_not_found",
            "Could not identify the main article container in publisher HTML.",
        )

    clean_container(container, publisher, drop_profile=HTML_CONTAINER_DROP_BROWSER_WORKFLOW)

    supplementary_container = copy.deepcopy(container)
    body_container = copy.deepcopy(container)
    _normalize_abstract_blocks(body_container)
    _drop_front_matter_teaser_figures(body_container, publisher)
    _drop_abstract_sections_from_body_container(body_container, publisher)

    return (
        _content_fragment_html(body_container, publisher=publisher),
        _content_fragment_html(supplementary_container, publisher=publisher),
    )


def extract_science_pnas_markdown(
    html_text: str,
    source_url: str,
    publisher: str,
    *,
    metadata: ProviderMetadata | Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    return extract_browser_workflow_markdown(
        html_text,
        source_url,
        publisher,
        metadata=metadata,
    )
