"""Shared inline-token rendering for HTML-derived Markdown."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal
from collections.abc import Callable, Sequence

from ...markdown.citations import (
    NUMERIC_CITATION_SENTINEL_PREFIX,
)
from ...markdown.inline_spacing import normalize_inline_sup_sub_tag_bodies

InlineTextPolicy = Literal["body", "heading", "table_cell"]
SupSubTag = Literal["sub", "sup"]

HTML_NO_SPACE_AFTER_CHARS = set("([{/+-–—−")
HTML_NO_SPACE_BEFORE_CHARS = set(")]},.;:!?%/+-–—−")
INLINE_MARKDOWN_TOKEN_PATTERN = re.compile(
    rf"(?P<citation>{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}(?P<payload>[^@\n]+)@@)"
    r"|(?P<br><br\s*/?>)"
    r"|<(?P<tag>sub|sup)>(?P<body>[^<>]*)</(?P=tag)>",
    flags=re.IGNORECASE,
)
INLINE_EXPONENT_BODY_PATTERN = re.compile(r"[+\-−–]?\d+(?:\.\d+)?")
INLINE_UNSIGNED_INTEGER_BODY_PATTERN = re.compile(r"\d+")
INLINE_SUBSCRIPT_BODY_PATTERN = re.compile(r"\d+[A-Za-z]?|[A-Za-z]\d*")
INLINE_CHEMICAL_BASE_PATTERN = re.compile(r"[A-Z][A-Z0-9]{0,5}")
INLINE_COMPACT_UNIT_SYMBOL_PATTERN = re.compile(
    r"(?:[cdfhkmunpµμ][a-zµμ]{0,3}|[A-Z][A-Za-z]{0,3})"
)
INLINE_MARKED_SINGLE_LETTER_PATTERN = re.compile(r"[*_][A-Za-z][*_]")
INLINE_TOKEN_PATTERN = re.compile(r"[*_`]*[A-Za-z0-9µμ]+[*_`]*\Z")

CitationPayloadFn = Callable[[Any], str | None]
RawMarkdownFn = Callable[[Any], str | None]
DropNodeFn = Callable[[Any], bool]


@dataclass(frozen=True)
class TextToken:
    text: str


@dataclass(frozen=True)
class RawMarkdownToken:
    text: str


@dataclass(frozen=True)
class CitationToken:
    payload: str


@dataclass(frozen=True)
class SupSubToken:
    tag: SupSubTag
    body: str
    trailing_body_space: bool = False


@dataclass(frozen=True)
class BreakToken:
    pass


InlineToken = TextToken | RawMarkdownToken | CitationToken | SupSubToken | BreakToken


def _normalize_inline_text_fragment(
    text: str,
    *,
    collapse_newlines: bool,
    preserve_edge_space: bool = True,
) -> str:
    value = text.replace("\xa0", " ")
    has_leading_space = bool(value[:1].isspace())
    has_trailing_space = bool(value[-1:].isspace())
    if collapse_newlines:
        normalized = re.sub(r"\s+", " ", value).strip()
    else:
        normalized = re.sub(r"[ \t\r\f\v]+", " ", value).strip(" ")
    if not normalized:
        return (
            " "
            if preserve_edge_space and (has_leading_space or has_trailing_space)
            else ""
        )
    if preserve_edge_space and has_leading_space:
        normalized = f" {normalized}"
    if preserve_edge_space and has_trailing_space:
        normalized = f"{normalized} "
    return normalized


def wrap_html_inline_text_fragment(text: str, marker: str | None = None) -> str:
    value = _normalize_inline_text_fragment(text, collapse_newlines=True)
    if not value.strip():
        return value
    has_leading_space = value[:1].isspace()
    has_trailing_space = value[-1:].isspace()
    normalized = value.strip()
    if marker:
        normalized = f"{marker}{normalized}{marker}"
    if has_leading_space:
        normalized = f" {normalized}"
    if has_trailing_space:
        normalized = f"{normalized} "
    return normalized


def _sup_sub_token_from_body(tag: str, body: str) -> SupSubToken | None:
    normalized_tag = tag.lower()
    if normalized_tag not in {"sub", "sup"}:
        return None
    normalized_body = body.replace("\xa0", " ")
    body_text = re.sub(r"\s+", " ", normalized_body).strip()
    if not body_text:
        return None
    return SupSubToken(
        tag=normalized_tag,  # type: ignore[arg-type]
        body=body_text,
        trailing_body_space=bool(normalized_body and normalized_body[-1].isspace()),
    )


def inline_markdown_tokens(
    text: str, *, parse_citations: bool = True
) -> list[InlineToken]:
    """Tokenize a Markdown inline fragment containing existing sup/sub tags."""

    tokens: list[InlineToken] = []
    offset = 0
    for match in INLINE_MARKDOWN_TOKEN_PATTERN.finditer(text):
        if match.start() > offset:
            tokens.append(TextToken(text[offset : match.start()]))
        if match.group("citation"):
            if parse_citations:
                tokens.append(CitationToken(match.group("payload")))
            else:
                tokens.append(TextToken(match.group(0)))
        elif match.group("br"):
            tokens.append(BreakToken())
        else:
            token = _sup_sub_token_from_body(match.group("tag"), match.group("body"))
            if token is not None:
                tokens.append(token)
        offset = match.end()
    if offset < len(text):
        tokens.append(TextToken(text[offset:]))
    return tokens


def _node_name(node: Any) -> str:
    return re.sub(r"\s+", " ", str(getattr(node, "name", "") or "")).strip().lower()


def html_inline_tokens(
    node: Any,
    *,
    text_style: str | None = None,
    citation_payload_from_node: CitationPayloadFn | None = None,
    raw_markdown_from_node: RawMarkdownFn | None = None,
    drop_node: DropNodeFn | None = None,
    render_text_styles: bool = True,
) -> list[InlineToken]:
    """Render an HTML inline node to structured tokens."""

    if _is_navigable_string(node):
        fragment = wrap_html_inline_text_fragment(str(node), text_style)
        return [TextToken(fragment)] if fragment else []
    if node is None or not hasattr(node, "children"):
        return []
    if drop_node is not None and drop_node(node):
        return []

    if citation_payload_from_node is not None:
        payload = citation_payload_from_node(node)
        if payload is not None:
            return [CitationToken(payload)]

    if raw_markdown_from_node is not None:
        raw_markdown = raw_markdown_from_node(node)
        if raw_markdown:
            return [RawMarkdownToken(raw_markdown)]

    name = _node_name(node)
    if name == "br":
        return [BreakToken()]
    if render_text_styles and name in {"i", "em"}:
        return html_inline_child_tokens(
            node,
            text_style="*",
            citation_payload_from_node=citation_payload_from_node,
            raw_markdown_from_node=raw_markdown_from_node,
            drop_node=drop_node,
            render_text_styles=render_text_styles,
        )
    if render_text_styles and name in {"b", "strong"}:
        return html_inline_child_tokens(
            node,
            text_style="**",
            citation_payload_from_node=citation_payload_from_node,
            raw_markdown_from_node=raw_markdown_from_node,
            drop_node=drop_node,
            render_text_styles=render_text_styles,
        )
    if name in {"sub", "sup"}:
        body = render_inline_tokens(
            html_inline_child_tokens(
                node,
                citation_payload_from_node=citation_payload_from_node,
                raw_markdown_from_node=raw_markdown_from_node,
                drop_node=drop_node,
                render_text_styles=render_text_styles,
            ),
            policy="body",
            collapse_newlines=True,
            break_render="<br>",
            strip=False,
        )
        token = _sup_sub_token_from_body(name, body)
        return [token] if token is not None else []
    return html_inline_child_tokens(
        node,
        text_style=text_style,
        citation_payload_from_node=citation_payload_from_node,
        raw_markdown_from_node=raw_markdown_from_node,
        drop_node=drop_node,
        render_text_styles=render_text_styles,
    )


def html_inline_child_tokens(
    node: Any,
    *,
    text_style: str | None = None,
    citation_payload_from_node: CitationPayloadFn | None = None,
    raw_markdown_from_node: RawMarkdownFn | None = None,
    drop_node: DropNodeFn | None = None,
    render_text_styles: bool = True,
) -> list[InlineToken]:
    tokens: list[InlineToken] = []
    for child in getattr(node, "children", ()):
        tokens.extend(
            html_inline_tokens(
                child,
                text_style=text_style,
                citation_payload_from_node=citation_payload_from_node,
                raw_markdown_from_node=raw_markdown_from_node,
                drop_node=drop_node,
                render_text_styles=render_text_styles,
            )
        )
    return tokens


def render_html_inline_node(
    node: Any,
    *,
    policy: InlineTextPolicy = "body",
    text_style: str | None = None,
    citation_payload_from_node: CitationPayloadFn | None = None,
    raw_markdown_from_node: RawMarkdownFn | None = None,
    drop_node: DropNodeFn | None = None,
    render_text_styles: bool = True,
    break_render: str = "<br>",
) -> str:
    return render_inline_tokens(
        html_inline_tokens(
            node,
            text_style=text_style,
            citation_payload_from_node=citation_payload_from_node,
            raw_markdown_from_node=raw_markdown_from_node,
            drop_node=drop_node,
            render_text_styles=render_text_styles,
        ),
        policy=policy,
        collapse_newlines=True,
        break_render=break_render,
    )


def normalize_html_inline_text(value: str, *, policy: InlineTextPolicy = "body") -> str:
    """Normalize whitespace around inline HTML fragments rendered as Markdown."""

    return render_inline_tokens(
        inline_markdown_tokens(value, parse_citations=True),
        policy=policy,
        collapse_newlines=True,
        break_render="<br>",
    )


def render_inline_tokens(
    tokens: Sequence[InlineToken],
    *,
    policy: InlineTextPolicy = "body",
    collapse_newlines: bool = True,
    break_render: str = "<br>",
    strip: bool = True,
) -> str:
    if not tokens:
        return ""
    pieces = [
        _render_token(
            token, collapse_newlines=collapse_newlines, break_render=break_render
        )
        for token in tokens
    ]
    rendered = ""
    for index, (token, piece) in enumerate(zip(tokens, pieces, strict=True)):
        if not piece:
            continue
        if isinstance(token, (CitationToken, BreakToken)):
            rendered = rendered.rstrip(" \t")
        elif isinstance(token, SupSubToken) and _should_tighten_before_sup_sub(
            rendered, token, pieces[index + 1 :]
        ):
            rendered = rendered.rstrip(" \t")
        elif _needs_inserted_space(
            rendered,
            piece,
            previous_token=tokens[index - 1] if index else None,
            current_token=token,
        ):
            rendered += " "
        rendered += piece
    rendered = _cleanup_rendered_inline_text(
        rendered, policy=policy, collapse_newlines=collapse_newlines
    )
    return rendered.strip() if strip else rendered


def _render_token(
    token: InlineToken, *, collapse_newlines: bool, break_render: str
) -> str:
    if isinstance(token, TextToken):
        return _normalize_inline_text_fragment(
            token.text, collapse_newlines=collapse_newlines
        )
    if isinstance(token, RawMarkdownToken):
        return _normalize_inline_text_fragment(
            token.text, collapse_newlines=collapse_newlines
        )
    if isinstance(token, CitationToken):
        return f"{NUMERIC_CITATION_SENTINEL_PREFIX}{token.payload}@@"
    if isinstance(token, SupSubToken):
        trailing_space = " " if token.trailing_body_space else ""
        return f"<{token.tag}>{token.body}</{token.tag}>{trailing_space}"
    if isinstance(token, BreakToken):
        return break_render
    return ""


def _cleanup_rendered_inline_text(
    text: str, *, policy: InlineTextPolicy, collapse_newlines: bool
) -> str:
    normalized = text.replace("\xa0", " ")
    if collapse_newlines:
        normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
        normalized = re.sub(r"\s*\n\s*", " ", normalized)
    else:
        normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
    normalized = re.sub(r"\s*(<br>)\s*", r"\1", normalized)
    normalized = normalize_inline_sup_sub_tag_bodies(normalized)
    normalized = re.sub(r"\s+</(sub|sup)>", r"</\1>", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(</sub>)\s+\(", r"\1(", normalized, flags=re.IGNORECASE)
    punctuation = r"[,.;:%\]\}]" if policy == "table_cell" else r"[,.;:%\]\}\+\)]"
    normalized = re.sub(
        rf"(</(?:sub|sup)>)\s+({punctuation})", r"\1\2", normalized, flags=re.IGNORECASE
    )
    normalized = re.sub(
        r"([(\[])\s+(?=<(?:sub|sup)>)", r"\1", normalized, flags=re.IGNORECASE
    )
    return normalized


def _needs_inserted_space(
    left: str,
    right: str,
    *,
    previous_token: InlineToken | None,
    current_token: InlineToken,
) -> bool:
    if not left or not right:
        return False
    if left[-1:].isspace() or right[:1].isspace():
        return False
    if isinstance(current_token, (SupSubToken, CitationToken, BreakToken)):
        return False
    if isinstance(previous_token, (SupSubToken, BreakToken)):
        return False
    left_edge = _visible_inline_edge(left, last=True)
    right_edge = _visible_inline_edge(right, last=False)
    if not left_edge or not right_edge:
        return False
    if (
        left_edge in HTML_NO_SPACE_AFTER_CHARS
        or right_edge in HTML_NO_SPACE_BEFORE_CHARS
    ):
        return False
    return right_edge.isalnum() or right_edge in {"*", "_", "<"}


def _should_tighten_before_sup_sub(
    left: str, token: SupSubToken, future_pieces: Sequence[str]
) -> bool:
    if not left:
        return False
    if not left[-1:].isspace():
        return True
    stripped_left = left.rstrip(" \t")
    if not stripped_left:
        return False
    left_char = _visible_inline_edge(stripped_left, last=True)
    if left_char in "([{":
        return True
    body = token.body.strip()
    right = _first_visible_text(future_pieces)
    if _looks_like_isotope_superscript(token.tag, body, right):
        return False
    base = _last_inline_base(stripped_left)
    if not base:
        return False
    if token.tag == "sup":
        return _should_tighten_superscript(base, body, right)
    return _should_tighten_subscript(base, body)


def _should_tighten_superscript(base: str, body: str, right: str) -> bool:
    if not INLINE_EXPONENT_BODY_PATTERN.fullmatch(body):
        return False
    if _is_single_letter_math_symbol(base):
        return True
    if body[:1] in {"-", "+", "−", "–"}:
        return _looks_symbol_like(base)
    if right[:1].isupper() and INLINE_UNSIGNED_INTEGER_BODY_PATTERN.fullmatch(body):
        return False
    return INLINE_UNSIGNED_INTEGER_BODY_PATTERN.fullmatch(
        body
    ) is not None and _looks_compact_unit_symbol(base)


def _should_tighten_subscript(base: str, body: str) -> bool:
    if not INLINE_SUBSCRIPT_BODY_PATTERN.fullmatch(body):
        return False
    if _is_single_letter_math_symbol(base):
        return True
    return INLINE_CHEMICAL_BASE_PATTERN.fullmatch(_plain_inline_base(base)) is not None


def _looks_like_isotope_superscript(tag: str, body: str, right: str) -> bool:
    return (
        tag == "sup"
        and right[:1].isupper()
        and INLINE_UNSIGNED_INTEGER_BODY_PATTERN.fullmatch(body) is not None
    )


def _looks_symbol_like(base: str) -> bool:
    return _is_single_letter_math_symbol(base) or _looks_compact_unit_symbol(base)


def _looks_compact_unit_symbol(base: str) -> bool:
    plain = _plain_inline_base(base)
    if not plain or len(plain) > 4:
        return False
    return INLINE_COMPACT_UNIT_SYMBOL_PATTERN.fullmatch(plain) is not None


def _is_single_letter_math_symbol(base: str) -> bool:
    plain = _plain_inline_base(base)
    return bool(
        re.fullmatch(r"[A-Za-z]", plain)
        or INLINE_MARKED_SINGLE_LETTER_PATTERN.fullmatch(base)
    )


def _plain_inline_base(base: str) -> str:
    return re.sub(r"[*_`]+", "", base).strip()


def _last_inline_base(text: str) -> str:
    scrubbed = re.sub(r"</?(?:sub|sup)>", "", text, flags=re.IGNORECASE)
    match = INLINE_TOKEN_PATTERN.search(scrubbed)
    return match.group(0) if match else ""


def _first_visible_text(pieces: Sequence[str]) -> str:
    for piece in pieces:
        normalized = re.sub(r"</?(?:sub|sup)>", "", piece, flags=re.IGNORECASE)
        normalized = re.sub(r"[*_`]+", "", normalized)
        normalized = normalized.strip()
        if normalized:
            return normalized
    return ""


def _visible_inline_edge(text: str, *, last: bool) -> str:
    normalized = re.sub(r"</?(?:sub|sup)>", "", text, flags=re.IGNORECASE)
    normalized = re.sub(r"[*_`]+", "", normalized).strip()
    if not normalized:
        return ""
    return normalized[-1] if last else normalized[0]


def first_significant_char(text: str) -> str:
    for char in text:
        if not char.isspace():
            return char
    return ""


def last_significant_char(text: str) -> str:
    for char in reversed(text):
        if not char.isspace():
            return char
    return ""


def needs_space_between_inline_text(
    left: str,
    right: str,
    *,
    previous_is_tight: bool = False,
    current_is_tight: bool = False,
    right_is_markdown_image: bool = False,
) -> bool:
    if not left or not right:
        return False
    if left[-1].isspace() or right[0].isspace():
        return False
    if right_is_markdown_image:
        return True
    if previous_is_tight or current_is_tight:
        return False

    left_char = last_significant_char(left)
    right_char = first_significant_char(right)
    if not left_char or not right_char:
        return False
    if left_char in HTML_NO_SPACE_AFTER_CHARS:
        return False
    if right_char in HTML_NO_SPACE_BEFORE_CHARS:
        return False
    return left_char.isalnum() and right_char.isalnum()


def _is_navigable_string(node: Any) -> bool:
    return node.__class__.__name__ == "NavigableString"
