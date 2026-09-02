"""Provider-neutral HTML cleanup and Markdown extraction helpers."""

from __future__ import annotations

import codecs
import functools
import importlib
import logging
import re
from dataclasses import dataclass
from email.message import Message
from html.parser import HTMLParser
from typing import Any
from collections.abc import Mapping

from ...extraction.html.language import (
    collect_html_abstract_blocks,
    html_node_language_hint,
)
from ...extraction.html.front_matter import (
    ARTICLE_TYPE_FRONT_MATTER_PREFIXES,
    COMMON_FRONT_MATTER_LINE_PATTERNS,
)
from ...extraction.html.cleanup_policy import (
    HTML_DROP_SELECTORS as HTML_DROP_SELECTORS,
    HTML_EXACT_NOISE_TEXTS as HTML_EXACT_NOISE_TEXTS,
    HTML_NOISE_ATTR_TOKENS as HTML_NOISE_ATTR_TOKENS,
    HTML_PREFIX_NOISE_TEXTS as HTML_PREFIX_NOISE_TEXTS,
    MARKDOWN_CHROME_SECTION_HEADINGS,
    MARKDOWN_EXACT_NOISE_TEXTS as MARKDOWN_EXACT_NOISE_TEXTS,
    MARKDOWN_PREFIX_NOISE_TEXTS as MARKDOWN_PREFIX_NOISE_TEXTS,
    MARKDOWN_SHORT_NOISE_TOKENS as MARKDOWN_SHORT_NOISE_TOKENS,
    CleanupPolicy,
    classify_dom_cleanup_node,
    classify_markdown_cleanup_line,
    count_words,
    looks_like_markdown_promo_line,
)
from ...extraction.html.html_tags import HTML_DROP_TAGS
from ...extraction.html.parsing import choose_parser
from ...extraction.html.semantics import (
    HTML_BLOCK_TAGS,
    collect_html_section_hints,
    coerce_html_section_hints,
    markdown_heading_category,
    match_next_html_section_hint,
    parse_markdown_heading,
)
from ...extraction.html.section_scan import SectionScanState
from ...extraction.html.signals import (
    contains_access_gate_text,
)
from ...models import normalize_markdown_text, normalize_text
from ...publisher_identity import normalize_doi
from ...publisher_identity import extract_doi as extract_doi_from_text
from .provider_rules import (
    cleanup_policy_for_profile,
    front_matter_exact_texts_for_profile,
    front_matter_footer_prefixes,
    front_matter_publication_keywords_for_profile,
    normalize_noise_profile,
)
from bs4 import BeautifulSoup

_TRAFILATURA_UNSET = object()
trafilatura: Any = _TRAFILATURA_UNSET


@functools.lru_cache(maxsize=1)
def _import_trafilatura() -> Any:
    try:
        return importlib.import_module("trafilatura")
    except ImportError:  # pragma: no cover - exercised by degraded installs
        return None


def _module_trafilatura_backend() -> Any:
    if trafilatura is _TRAFILATURA_UNSET:
        return _import_trafilatura()
    return trafilatura


_charset_normalizer_from_bytes: Any
try:
    from charset_normalizer import (
        from_bytes as _imported_charset_normalizer_from_bytes,
    )
except ImportError:  # pragma: no cover - dependency is optional for degraded installs
    _charset_normalizer_from_bytes = None
else:
    _charset_normalizer_from_bytes = _imported_charset_normalizer_from_bytes

LOGGER = logging.getLogger(__name__)
HTML_ROOT_SELECTORS = ("article", "main", '[role="main"]')
HTML_META_CHARSET_PATTERN = re.compile(
    rb"<meta\b[^>]*\bcharset\s*=\s*['\"]?\s*([A-Za-z0-9._:-]+)",
    flags=re.IGNORECASE,
)
HTML_META_HTTP_EQUIV_CONTENT_TYPE_PATTERN = re.compile(
    rb"<meta\b(?=[^>]*http-equiv\s*=\s*['\"]?content-type['\"]?)"
    rb"(?=[^>]*content\s*=\s*['\"][^'\"]*charset\s*=\s*([A-Za-z0-9._:-]+))",
    flags=re.IGNORECASE,
)
ORCID_HREF_PATTERN = re.compile(r"orcid\.org", re.IGNORECASE)
RAW_TRAFILATURA_FALLBACK_CHAR_LIMIT = 1_000_000
# Publication-watermark heuristic only: these English masthead nouns are used
# after short/title-like guards and are not a general language or NER list.
FRONT_MATTER_PUBLICATION_KEYWORDS = {
    "advances",
    "bulletin",
    "communications",
    "journal",
    "journals",
    "letters",
    "proceedings",
    "reports",
    "review",
    "reviews",
    "sciences",
    "transactions",
}
PUBLICATION_WATERMARK_PUNCTUATION = ".:;!?。！？"
PUBLICATION_WATERMARK_CONNECTORS = {"and", "of", "the", "&"}
PUBLICATION_WATERMARK_MAX_LENGTH = 64
PUBLICATION_WATERMARK_MAX_TOKENS = 5
FRONT_MATTER_BYLINE_CONNECTORS = {
    "and",
    "&",
    "et",
    "al",
    "the",
    "de",
    "del",
    "van",
    "von",
}
FRONT_MATTER_BYLINE_MAX_LENGTH = 96
FRONT_MATTER_BYLINE_MAX_WORDS = 10
TEXT_EXTRACTION_BLOCK_TAGS = frozenset(
    tag
    for tag in ("p", "div", "section", "article", "li", "ul", "ol", "table", "tr")
    if tag in HTML_BLOCK_TAGS
)
_USE_MODULE_TRAFILATURA = object()


@dataclass(frozen=True)
class HtmlCleanupRules:
    policy: CleanupPolicy
    drop_selectors: tuple[str, ...]
    exact_texts: frozenset[str]
    extraction_cleanup_selectors: tuple[str, ...]
    markdown_exact_texts: frozenset[str]
    markdown_prefix_texts: tuple[str, ...]
    markdown_short_tokens: tuple[str, ...]
    markdown_promo_tokens: tuple[str, ...]


@functools.lru_cache(maxsize=32)
def html_cleanup_rules(noise_profile: str | None = None) -> HtmlCleanupRules:
    active_noise_profile = _normalize_noise_profile(noise_profile)
    policy = cleanup_policy_for_profile(active_noise_profile)
    return HtmlCleanupRules(
        policy=policy,
        drop_selectors=policy.dom_drop_selectors,
        exact_texts=policy.dom_exact_texts,
        extraction_cleanup_selectors=policy.extraction_cleanup_selectors,
        markdown_exact_texts=policy.markdown_exact_texts,
        markdown_prefix_texts=policy.markdown_prefix_texts,
        markdown_short_tokens=policy.markdown_short_tokens,
        markdown_promo_tokens=policy.markdown_contains_tokens,
    )


class _FallbackMarkdownParser(HTMLParser):
    BLOCK_TAGS = TEXT_EXTRACTION_BLOCK_TAGS
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._current: list[str] = []
        self._heading_level = 0
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered_tag = tag.lower()
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if lowered_tag in {"script", "style", "nav", "footer", "header"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        class_attr = attributes.get("class", "").lower()
        id_attr = attributes.get("id", "").lower()
        skip_attr_tokens: tuple[str, ...] = (
            "cookie",
            "nav",
            "footer",
            "share",
            "signin",
        )
        if lowered_tag not in self.HEADING_TAGS:
            skip_attr_tokens = (*skip_attr_tokens, "header")
        if any(token in f"{class_attr} {id_attr}" for token in skip_attr_tokens):
            self._skip_depth += 1
            return
        if lowered_tag in self.HEADING_TAGS:
            self._flush()
            self._heading_level = int(lowered_tag[1])
        elif lowered_tag == "br":
            self._current.append("\n")
        elif lowered_tag in self.BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.lower()
        if (
            lowered_tag in {"script", "style", "nav", "footer", "header"}
            and self._skip_depth
        ):
            self._skip_depth -= 1
            return
        if self._skip_depth:
            if lowered_tag in {"div", "section", "article"}:
                self._skip_depth = max(0, self._skip_depth - 1)
            return
        if lowered_tag in self.HEADING_TAGS:
            self._flush()
            self._heading_level = 0
        elif lowered_tag in self.BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data.strip():
            self._current.append(data)

    def _flush(self) -> None:
        text = normalize_text("".join(self._current))
        if not text:
            self._current = []
            return
        if self._heading_level:
            self.lines.append(f"{'#' * self._heading_level} {text}")
        else:
            self.lines.append(text)
        self.lines.append("")
        self._current = []


def _normalized_encoding(value: str | bytes | None) -> str | None:
    if isinstance(value, bytes):
        raw = value.decode("ascii", errors="ignore")
    else:
        raw = str(value or "")
    encoding = raw.strip().strip("\"'").lower()
    if not encoding:
        return None
    try:
        return codecs.lookup(encoding).name
    except LookupError:
        return None


def _content_type_charset(content_type: str | None) -> str | None:
    if not content_type:
        return None
    message = Message()
    message["content-type"] = content_type
    return _normalized_encoding(message.get_content_charset())


def _html_meta_charset(body: bytes) -> str | None:
    head = body[:8192]
    for pattern in (
        HTML_META_CHARSET_PATTERN,
        HTML_META_HTTP_EQUIV_CONTENT_TYPE_PATTERN,
    ):
        match = pattern.search(head)
        if match is None:
            continue
        encoding = _normalized_encoding(match.group(1))
        if encoding:
            return encoding
    return None


def _decode_with_encoding(body: bytes, encoding: str | None) -> str | None:
    normalized = _normalized_encoding(encoding)
    if not normalized:
        return None
    try:
        return body.decode(normalized)
    except UnicodeDecodeError:
        return None


def decode_html(body: bytes, *, content_type: str | None = None) -> str:
    if body.startswith(codecs.BOM_UTF8):
        decoded = _decode_with_encoding(body, "utf-8-sig")
        if decoded is not None:
            return decoded

    decoded = _decode_with_encoding(body, "utf-8")
    if decoded is not None:
        return decoded

    for encoding in (
        _content_type_charset(content_type),
        _html_meta_charset(body),
    ):
        decoded = _decode_with_encoding(body, encoding)
        if decoded is not None:
            return decoded

    if _charset_normalizer_from_bytes is not None:
        best = _charset_normalizer_from_bytes(body).best()
        if best is not None:
            decoded = str(best)
            if decoded:
                return decoded

    return body.decode("utf-8", errors="replace")


def _normalize_noise_profile(noise_profile: str | None) -> str:
    return normalize_noise_profile(noise_profile)


def select_html_content_root(root: Any):

    best_candidate = None
    best_words = 0
    scored_candidates: set[int] = set()
    for selector in HTML_ROOT_SELECTORS:
        for candidate in root.select(selector):
            candidate_id = id(candidate)
            if candidate_id in scored_candidates:
                continue
            scored_candidates.add(candidate_id)
            if best_candidate is not None and best_candidate in getattr(
                candidate, "parents", []
            ):
                continue
            if best_candidate is not None and candidate in getattr(
                best_candidate, "parents", []
            ):
                words = _html_root_candidate_word_count(candidate)
            else:
                words = _html_root_candidate_word_count(candidate)
            if words > best_words:
                best_candidate = candidate
                best_words = words
    return best_candidate


def _html_root_candidate_word_count(candidate: Any) -> int:
    words = 0
    for text in getattr(candidate, "stripped_strings", ()):
        words += count_words(normalize_text(text))
    return words


def prune_html_tree(
    root: Any,
    *,
    noise_profile: str | None = None,
    classify_elements: bool = True,
) -> None:

    rules = html_cleanup_rules(noise_profile)
    for tag in root(HTML_DROP_TAGS):
        tag.decompose()
    for selector in rules.drop_selectors:
        for element in root.select(selector):
            element.decompose()
    for selector in rules.extraction_cleanup_selectors:
        for element in root.select(selector):
            element.decompose()
    for element in list(root.find_all(href=ORCID_HREF_PATTERN)):
        element.decompose()
    if not classify_elements:
        return
    for element in list(root.find_all(True)):
        if should_drop_html_element(element, noise_profile=noise_profile, rules=rules):
            element.decompose()


def should_drop_html_element(
    element: Any,
    *,
    noise_profile: str | None = None,
    rules: HtmlCleanupRules | None = None,
) -> bool:
    cleanup_rules = rules or html_cleanup_rules(noise_profile)
    return (
        classify_dom_cleanup_node(
            element,
            policy=cleanup_rules.policy,
            stage="extraction",
        ).action
        == "drop"
    )


def prepare_html_extraction_tree(
    html_text: str, *, noise_profile: str | None = None
) -> tuple[str, Any]:

    soup = BeautifulSoup(html_text, choose_parser())
    root = select_html_content_root(soup)
    classify_elements = True
    if root is None:
        root = soup.body or soup
        classify_elements = False
    prune_html_tree(
        root,
        noise_profile=noise_profile,
        classify_elements=classify_elements,
    )
    return str(root), root


def extract_html_extraction_sidecars(
    html_text: str,
    *,
    noise_profile: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    cleaned_html, active_root = prepare_html_extraction_tree(
        html_text, noise_profile=noise_profile
    )
    if active_root is None:
        return {
            "cleaned_html": cleaned_html,
            "abstract_sections": [],
            "section_hints": [],
        }
    return {
        "cleaned_html": cleaned_html,
        "abstract_sections": collect_html_abstract_blocks(active_root),
        "section_hints": collect_html_section_hints(
            active_root,
            title=title,
            language_hint_resolver=lambda node: html_node_language_hint(
                node, allow_soft_hints=True
            ),
        ),
    }


def clean_html_for_extraction(
    html_text: str, *, noise_profile: str | None = None
) -> str:
    cleaned_html, _ = prepare_html_extraction_tree(
        html_text, noise_profile=noise_profile
    )
    return cleaned_html


def extract_html_abstract_blocks(
    html_text: str,
    *,
    noise_profile: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    return list(
        extract_html_extraction_sidecars(
            html_text, noise_profile=noise_profile, title=title
        )["abstract_sections"]
    )


def extract_html_section_hints(
    html_text: str,
    *,
    noise_profile: str | None = None,
    title: str | None = None,
) -> list[dict[str, Any]]:
    return list(
        extract_html_extraction_sidecars(
            html_text, noise_profile=noise_profile, title=title
        )["section_hints"]
    )


def extract_article_markdown(
    html_text: str,
    source_url: str,
    *,
    trafilatura_backend: Any = _USE_MODULE_TRAFILATURA,
    noise_profile: str | None = None,
) -> str:
    active_noise_profile = _normalize_noise_profile(noise_profile)
    cleaned_html, _ = prepare_html_extraction_tree(
        html_text, noise_profile=active_noise_profile
    )
    return extract_article_markdown_from_cleaned_html(
        cleaned_html,
        source_url,
        trafilatura_backend=trafilatura_backend,
        noise_profile=active_noise_profile,
        raw_html=html_text,
    )


def extract_article_markdown_from_cleaned_html(
    cleaned_html: str,
    source_url: str,
    *,
    trafilatura_backend: Any = _USE_MODULE_TRAFILATURA,
    noise_profile: str | None = None,
    raw_html: str | None = None,
) -> str:
    del source_url
    active_noise_profile = _normalize_noise_profile(noise_profile)
    active_trafilatura = (
        _module_trafilatura_backend()
        if trafilatura_backend is _USE_MODULE_TRAFILATURA
        else trafilatura_backend
    )
    if active_trafilatura is not None:
        candidates: list[tuple[str, str]] = [("cleaned", cleaned_html)]
        if raw_html and raw_html != cleaned_html:
            candidates.append(("raw", raw_html))
        for candidate_kind, candidate_html in candidates:
            if not candidate_html:
                continue
            if (
                candidate_kind == "raw"
                and len(candidate_html) > RAW_TRAFILATURA_FALLBACK_CHAR_LIMIT
            ):
                LOGGER.debug(
                    "Skipping raw trafilatura fallback for %s chars; limit is %s.",
                    len(candidate_html),
                    RAW_TRAFILATURA_FALLBACK_CHAR_LIMIT,
                )
                continue
            extracted = active_trafilatura.extract(
                candidate_html,
                output_format="markdown",
                include_links=True,
                include_tables=True,
                favor_precision=True,
            )
            if extracted:
                cleaned = clean_markdown(extracted, noise_profile=active_noise_profile)
                if cleaned:
                    return cleaned

    parser = _FallbackMarkdownParser()
    parser.feed(cleaned_html)
    parser.close()
    return clean_markdown("\n".join(parser.lines), noise_profile=active_noise_profile)


def _strip_markdown_chrome_sections(markdown_text: str) -> str:
    lines: list[str] = []
    skip_level: int | None = None
    for raw_line in markdown_text.splitlines():
        heading_info = parse_markdown_heading(raw_line)
        if heading_info is not None:
            level, heading = heading_info
            if skip_level is not None and level <= skip_level:
                skip_level = None
            normalized_heading = normalize_text(heading).lower().strip(" :")
            if normalized_heading in MARKDOWN_CHROME_SECTION_HEADINGS:
                skip_level = level
                continue
        if skip_level is not None:
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def clean_markdown(markdown_text: str, *, noise_profile: str | None = None) -> str:
    cleanup_rules = html_cleanup_rules(noise_profile)
    markdown_text = _strip_markdown_chrome_sections(markdown_text)
    cleaned_lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = re.sub(r"\(\s*refs?\.\s*\)", "", raw_line, flags=re.IGNORECASE).rstrip()
        decision = classify_markdown_cleanup_line(line, policy=cleanup_rules.policy)
        if decision.action == "drop":
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    return normalize_markdown_text(cleaned)


def _canonical_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", normalize_text(value).lower(), flags=re.UNICODE)


def _split_markdown_blocks(markdown_text: str) -> list[str]:
    return [
        normalize_markdown_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]


def _heading_text(block: str) -> str | None:
    heading_info = parse_markdown_heading(block)
    return heading_info[1] if heading_info is not None else None


def _strip_title_heading(markdown_text: str, title: str) -> str:
    normalized_title = normalize_text(title)
    if not normalized_title:
        return markdown_text
    return re.sub(
        rf"^#\s*{re.escape(normalized_title)}\s*(?:\n+|$)",
        "",
        markdown_text,
        count=1,
        flags=re.IGNORECASE,
    )


def _looks_like_access_block(
    text: str,
    *,
    rules: HtmlCleanupRules | None = None,
) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    cleanup_rules = rules or html_cleanup_rules()
    if contains_access_gate_text(lowered):
        return True
    if any(prefix in lowered for prefix in cleanup_rules.markdown_prefix_texts):
        return True
    return any(token in lowered for token in cleanup_rules.markdown_short_tokens)


def _looks_like_promo_block(
    text: str,
    *,
    rules: HtmlCleanupRules | None = None,
    noise_profile: str | None = None,
) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    cleanup_profile = rules or html_cleanup_rules(noise_profile)
    return looks_like_markdown_promo_line(lowered, policy=cleanup_profile.policy)


def _looks_like_caption_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    return lowered.startswith("**figure") or lowered.startswith("**table")


def _looks_like_markdown_image_block(text: str) -> bool:
    return bool(re.match(r"^!\[[^\]]*\]\([^)]+\)$", normalize_text(text)))


def _looks_like_equation_label_block(text: str) -> bool:
    return normalize_text(text).lower().startswith("**equation")


def _front_matter_publication_keywords(noise_profile: str | None) -> set[str]:
    return {
        *FRONT_MATTER_PUBLICATION_KEYWORDS,
        *front_matter_publication_keywords_for_profile(noise_profile),
    }


def _publication_watermark_label_tokens(text: str) -> tuple[str, ...]:
    """Return tokens only for short publication masthead labels, not prose."""
    normalized = normalize_text(text)
    if not normalized or len(normalized) > PUBLICATION_WATERMARK_MAX_LENGTH:
        return ()
    if any(character in normalized for character in PUBLICATION_WATERMARK_PUNCTUATION):
        return ()
    tokens = tuple(normalized.split())
    if not tokens or len(tokens) > PUBLICATION_WATERMARK_MAX_TOKENS:
        return ()
    if normalized.upper() == normalized:
        return tokens
    if all(
        token[:1].isupper() or token.lower() in PUBLICATION_WATERMARK_CONNECTORS
        for token in tokens
    ):
        return tokens
    return ()


def _looks_like_publication_watermark(
    text: str,
    *,
    noise_profile: str | None = None,
) -> bool:
    normalized = normalize_text(text)
    tokens = _publication_watermark_label_tokens(normalized)
    if not tokens:
        return False
    lowered_tokens = [token.lower().strip("&") for token in tokens]
    publication_keywords = _front_matter_publication_keywords(noise_profile)
    return any(token in publication_keywords for token in lowered_tokens)


def _is_author_name_token(token: str) -> bool:
    cleaned = token.strip(" ,;:()[]{}")
    if not cleaned:
        return True
    lowered = cleaned.rstrip(".").lower()
    if lowered in FRONT_MATTER_BYLINE_CONNECTORS:
        return True
    if re.fullmatch(r"(?:[A-Z]\.)+", cleaned):
        return True
    return cleaned[:1].isupper()


def _looks_like_front_matter_byline(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized.lower().startswith("by "):
        return False
    byline = normalized[3:].strip()
    if not byline or len(normalized) > FRONT_MATTER_BYLINE_MAX_LENGTH:
        return False
    if count_words(byline) > FRONT_MATTER_BYLINE_MAX_WORDS:
        return False
    sentence_text = re.sub(r"\b[A-Z]\.", "A", byline)
    if len(re.findall(r"[.!?。！？]", sentence_text)) > 1:
        return False
    if re.search(r"[.!?。！？]\s+\S", sentence_text):
        return False
    tokens = [part for token in byline.split() for part in token.split("-")]
    return any(_is_author_name_token(token) for token in tokens) and all(
        _is_author_name_token(token) for token in tokens
    )


def _looks_like_front_matter_block(
    text: str,
    *,
    title: str | None = None,
    noise_profile: str | None = None,
    allow_byline: bool = False,
) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not normalized:
        return True
    if title and lowered == normalize_text(title).lower():
        return True
    if title:
        compact_text = re.sub(r"\s+", "", lowered)
        compact_title = re.sub(r"\s+", "", normalize_text(title).lower())
        if compact_title and compact_text.endswith(compact_title):
            for prefix in ARTICLE_TYPE_FRONT_MATTER_PREFIXES:
                if compact_text.startswith(re.sub(r"\s+", "", prefix)):
                    return True
    if any(lowered.startswith(prefix) for prefix in front_matter_footer_prefixes()):
        return True
    if allow_byline and _looks_like_front_matter_byline(normalized):
        return True
    if any(pattern.match(normalized) for pattern in COMMON_FRONT_MATTER_LINE_PATTERNS):
        return True
    return lowered in front_matter_exact_texts_for_profile(
        noise_profile
    ) or _looks_like_publication_watermark(
        normalized,
        noise_profile=noise_profile,
    )


def _filtered_body_blocks(
    markdown_text: str,
    metadata: Mapping[str, Any],
    *,
    section_hints: Any = None,
    noise_profile: str | None = None,
) -> dict[str, Any]:
    candidate = normalize_markdown_text(markdown_text)
    title = normalize_text(str(metadata.get("title") or ""))
    if title:
        candidate = _strip_title_heading(candidate, title)
    abstract = normalize_text(str(metadata.get("abstract") or ""))
    abstract_canonical = _canonical_text(abstract)
    blocks = _split_markdown_blocks(candidate)
    coerced_section_hints = coerce_html_section_hints(section_hints)
    cleanup_rules = html_cleanup_rules(noise_profile)
    filtered_blocks: list[str] = []
    abstract_blocks: list[str] = []
    body_heading_count = 0
    body_block_count = 0
    state = SectionScanState(
        enabled_states=frozenset(
            {
                "body",
                "abstract",
                "back_matter",
                "front_matter",
                "data_availability",
                "auxiliary",
            }
        )
    )
    in_formula = False
    section_hint_index = 0

    for block in blocks:
        heading = _heading_text(block)
        if heading is not None:
            normalized_heading = normalize_text(heading).lower().strip(" :")
            if title and normalized_heading == normalize_text(title).lower():
                continue
            matched_hint, next_hint_index = match_next_html_section_hint(
                coerced_section_hints, section_hint_index, heading
            )
            if matched_hint is not None:
                section_hint_index = next_hint_index
            category = markdown_heading_category(
                heading,
                title=title or None,
                section_hint_kind=matched_hint["kind"]
                if matched_hint is not None
                else None,
            )
            if category in {
                "abstract",
                "auxiliary",
                "front_matter",
                "references_or_back_matter",
                "data_availability",
                "code_availability",
            }:
                state.transition(category, is_heading=True)
                continue
            state.transition("body_heading", is_heading=True)
            filtered_blocks.append(block)
            body_heading_count += 1
            continue

        normalized_block = normalize_text(block)
        block_canonical = _canonical_text(normalized_block)
        if normalized_block == "$$":
            in_formula = not in_formula
            continue
        if state.in_abstract:
            if normalized_block:
                abstract_blocks.append(normalized_block)
            continue
        if state.in_skipped_section() or in_formula:
            continue
        if (
            _looks_like_access_block(normalized_block, rules=cleanup_rules)
            or _looks_like_promo_block(normalized_block, rules=cleanup_rules)
            or _looks_like_markdown_image_block(normalized_block)
            or _looks_like_caption_block(normalized_block)
            or _looks_like_equation_label_block(normalized_block)
            or _looks_like_front_matter_block(
                normalized_block,
                title=title or None,
                noise_profile=noise_profile,
                allow_byline=(body_heading_count == 0 and body_block_count == 0),
            )
        ):
            continue
        if (
            abstract_canonical
            and block_canonical
            and block_canonical == abstract_canonical
        ):
            abstract_blocks.append(normalized_block)
            continue
        filtered_blocks.append(block)
        body_block_count += 1

    body_text = normalize_markdown_text("\n\n".join(filtered_blocks))
    abstract_text = normalize_markdown_text("\n\n".join(abstract_blocks)) or abstract
    return {
        "body_text": body_text,
        "abstract_text": abstract_text,
        "body_heading_count": body_heading_count,
        "body_block_count": body_block_count,
        "has_abstract": bool(state.abstract_seen or abstract_text),
    }


def body_metrics(
    markdown_text: str,
    metadata: Mapping[str, Any],
    *,
    section_hints: Any = None,
    noise_profile: str | None = None,
) -> dict[str, Any]:
    filtered = _filtered_body_blocks(
        markdown_text,
        metadata,
        section_hints=section_hints,
        noise_profile=noise_profile,
    )
    candidate = filtered["body_text"]
    char_count = len(candidate)
    word_count = count_words(candidate)
    cjk_chars = sum(1 for char in candidate if "\u4e00" <= char <= "\u9fff")
    cjk_ratio = (cjk_chars / char_count) if char_count else 0.0
    has_doi = bool(
        normalize_doi(str(metadata.get("doi") or ""))
        or extract_doi_from_text(candidate)
    )
    abstract_text = normalize_text(filtered["abstract_text"])
    abstract_word_count = count_words(abstract_text)
    abstract_char_count = len(abstract_text)
    body_to_abstract_ratio = (
        word_count / max(abstract_word_count, 1)
        if abstract_word_count
        else (float(word_count) if word_count else 0.0)
    )
    return {
        "text": candidate,
        "char_count": char_count,
        "word_count": word_count,
        "cjk_chars": cjk_chars,
        "cjk_ratio": cjk_ratio,
        "has_doi": has_doi,
        "body_block_count": int(filtered["body_block_count"]),
        "body_heading_count": int(filtered["body_heading_count"]),
        "abstract_text": abstract_text,
        "abstract_word_count": abstract_word_count,
        "abstract_char_count": abstract_char_count,
        "has_abstract": bool(filtered["has_abstract"]),
        "body_to_abstract_ratio": body_to_abstract_ratio,
    }


def has_sufficient_article_body(
    markdown_text: str,
    metadata: Mapping[str, Any],
    *,
    section_hints: Any = None,
    noise_profile: str | None = None,
    provider: str | None = None,
) -> bool:
    metrics = body_metrics(
        markdown_text,
        metadata,
        section_hints=section_hints,
        noise_profile=noise_profile,
    )
    from ...provider_catalog import provider_body_text_thresholds

    thresholds = provider_body_text_thresholds(provider or noise_profile)
    if metrics["char_count"] < thresholds.short_body_min_chars:
        return False
    has_body_structure = (
        metrics["body_block_count"] >= 2 or metrics["body_heading_count"] >= 1
    )
    if (
        metrics["cjk_chars"] >= thresholds.cjk_min_chars
        and metrics["cjk_ratio"] >= thresholds.cjk_min_ratio
    ):
        if has_body_structure:
            return True
        return (
            metrics["body_block_count"] == 1
            and (
                not metrics["has_abstract"]
                or float(metrics.get("body_to_abstract_ratio") or 0.0) >= 1.5
            )
            and metrics["cjk_chars"] >= thresholds.single_block_min_cjk_chars
        )
    if metrics["word_count"] < thresholds.short_body_min_words:
        return False
    if has_body_structure:
        return True
    return (
        metrics["body_block_count"] == 1
        and metrics["word_count"] >= thresholds.single_block_min_words
        and (
            not metrics["has_abstract"]
            or float(metrics.get("body_to_abstract_ratio") or 0.0) >= 1.5
        )
    )
