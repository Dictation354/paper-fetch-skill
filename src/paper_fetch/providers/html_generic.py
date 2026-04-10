"""Generic HTML fallback provider for AI-friendly article extraction."""

from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Mapping

from ..config import build_user_agent
from ..http import HttpTransport, RequestFailure
from ..models import article_from_markdown, normalize_markdown_text, normalize_text
from ..publisher_identity import normalize_doi
from ..utils import dedupe_authors
from .base import ProviderFailure, map_request_failure

try:
    import trafilatura
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    trafilatura = None

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None
    NavigableString = None
    Tag = None

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", flags=re.IGNORECASE)
HTML_ROOT_SELECTORS = ("article", "main", '[role="main"]')
HTML_DROP_TAGS = ("script", "style", "svg", "noscript", "template")
HTML_BLOCK_TAGS = {
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
HTML_DROP_SELECTORS = (
    "nav",
    "aside",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "dialog",
    '[aria-hidden="true"]',
    "[hidden]",
)
HTML_EXACT_NOISE_TEXTS = {
    "advertisement",
    "download pdf",
    "view all journals",
    "view author publications",
    "search author on:",
    "search author on: pubmed google scholar",
    "get shareable link",
    "copy shareable link to clipboard",
}
HTML_PREFIX_NOISE_TEXTS = (
    "skip to main content",
    "thank you for visiting nature.com",
    "you are using a browser version with limited support for css",
    "to obtain the best experience, we recommend you use a more up to date browser",
    "in the meantime, to ensure continued support, we are displaying the site without styles and javascript",
    "anyone you share the following link with will be able to read this content",
    "sorry, a shareable link is not currently available for this article",
)
HTML_NOISE_ATTR_TOKENS = (
    "advert",
    "cookie",
    "newsletter",
    "share",
    "toolbar",
    "related",
    "recommend",
    "metrics",
    "banner",
    "promo",
)
MARKDOWN_EXACT_NOISE_TEXTS = HTML_EXACT_NOISE_TEXTS | {
    "menu",
    "home",
    "similar content being viewed by others",
}
MARKDOWN_PREFIX_NOISE_TEXTS = HTML_PREFIX_NOISE_TEXTS + (
    "subscribe",
    "access provided by",
    "buy article",
    "view access options",
)
MARKDOWN_SHORT_NOISE_TOKENS = (
    "sign in",
    "sign-in",
    "log in",
    "login",
    "view access options",
)
HTML_LOOKUP_TITLE_DENYLIST = (
    "redirecting",
    "sign in",
    "just a moment",
    "cookie",
    "subscribe",
    "access denied",
)
HEADING_TAG_PATTERN = re.compile(r"^h[1-6]$")
HTML_TIGHT_INLINE_TAGS = {"sub", "sup"}
HTML_NO_SPACE_AFTER_CHARS = set("([{/+-–—−")
HTML_NO_SPACE_BEFORE_CHARS = set(")]},.;:!?%/+-–—−")
NATURE_FIGURE_LINE_PATTERN = re.compile(r"(?im)^(?:extended data\s+)?fig\.\s*[a-z0-9.-]+:.*$")
NATURE_REFERENCE_RANGE_PATTERN = re.compile(r"(?<=[A-Za-z)])\^?\s*\d+\s*[–-]\s*\d+(?=[.,;:]?(?:\s|$))")
NATURE_REFERENCE_LIST_PATTERN = re.compile(r"(?<=[A-Za-z)])\^?\s*\d+(?:\s*,\s*\d+){1,}(?=[.,;:]?(?:\s|$))")
INPUT_TAG_PATTERN = re.compile(r"<input\b[^>]*>", flags=re.IGNORECASE)
HTML_ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*("([^"]*)"|\'([^\']*)\')')
HTML_REFRESH_URL_PATTERN = re.compile(r"url\s*=\s*(?P<quote>['\"]?)(?P<url>[^'\";>]+)(?P=quote)", flags=re.IGNORECASE)
HTML_SCRIPT_ARTICLE_NAME_PATTERN = re.compile(r"\barticleName\s*:\s*(['\"])(?P<value>.*?)(?<!\\)\1", flags=re.IGNORECASE | re.DOTALL)
HTML_SCRIPT_IDENTIFIER_PATTERN = re.compile(r"\bidentifierValue\s*:\s*(['\"])(?P<value>.*?)(?<!\\)\1", flags=re.IGNORECASE | re.DOTALL)
HTML_BODY_MIN_CHARS = 800
HTML_SHORT_BODY_MIN_CHARS = 300
HTML_SHORT_BODY_MIN_WORDS = 60
HTML_CJK_MIN_CHARS = 120
HTML_CJK_MIN_RATIO = 0.20


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.title: list[str] = []
        self.canonical_url: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        lowered_tag = tag.lower()
        if lowered_tag == "meta":
            key = attributes.get("name") or attributes.get("property") or attributes.get("http-equiv")
            content = attributes.get("content", "").strip()
            if key and content:
                self.meta.setdefault(key.lower(), []).append(content)
        elif lowered_tag == "link":
            rel = attributes.get("rel", "").lower()
            href = attributes.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonical_url = href
        elif lowered_tag == "title":
            self.title = []

    def handle_data(self, data: str) -> None:
        if data and self.lasttag == "title":
            self.title.append(data)


class _FigureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.assets: list[dict[str, str]] = []
        self._in_figure = False
        self._in_figcaption = False
        self._current_src = ""
        self._caption_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        lowered_tag = tag.lower()
        if lowered_tag == "figure":
            self._in_figure = True
            self._current_src = ""
            self._caption_parts = []
        elif self._in_figure and lowered_tag == "img" and not self._current_src:
            self._current_src = attributes.get("src", "").strip()
        elif self._in_figure and lowered_tag == "figcaption":
            self._in_figcaption = True

    def handle_endtag(self, tag: str) -> None:
        lowered_tag = tag.lower()
        if lowered_tag == "figcaption":
            self._in_figcaption = False
        elif lowered_tag == "figure":
            caption = normalize_text(" ".join(self._caption_parts))
            if self._current_src or caption:
                self.assets.append(
                    {
                        "kind": "figure",
                        "heading": caption[:80] or "Figure",
                        "caption": caption,
                        "url": self._current_src,
                    }
                )
            self._in_figure = False
            self._in_figcaption = False
            self._current_src = ""
            self._caption_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_figcaption and data.strip():
            self._caption_parts.append(data)


class _FallbackMarkdownParser(HTMLParser):
    BLOCK_TAGS = {"p", "div", "section", "article", "li", "ul", "ol", "table", "tr"}
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
        if any(token in f"{class_attr} {id_attr}" for token in ("cookie", "nav", "footer", "header", "share", "signin")):
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
        if lowered_tag in {"script", "style", "nav", "footer", "header"} and self._skip_depth:
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


def decode_html(body: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def clean_html_for_extraction(html_text: str) -> str:
    if BeautifulSoup is None:
        return html_text

    soup = BeautifulSoup(html_text, "html.parser")
    root = select_html_content_root(soup)
    if root is None:
        root = soup.body or soup

    candidate_soup = BeautifulSoup(str(root), "html.parser")
    active_root = candidate_soup.body or candidate_soup
    prune_html_tree(active_root)
    return str(active_root)


def select_html_content_root(root: Any):
    if BeautifulSoup is None:
        return None

    nature_root = select_nature_article_root(root)
    if nature_root is not None:
        return nature_root

    best_candidate = None
    best_words = 0
    for selector in HTML_ROOT_SELECTORS:
        for candidate in root.select(selector):
            words = count_words(normalize_text(candidate.get_text(" ", strip=True)))
            if words > best_words:
                best_candidate = candidate
                best_words = words
    return best_candidate


def select_nature_article_root(root: Any):
    if BeautifulSoup is None:
        return None

    best_article = None
    best_words = 0
    candidates = []
    if isinstance(root, Tag) and getattr(root, "name", None) == "article":
        candidates.append(root)
    candidates.extend(root.select("article"))
    for article in candidates:
        main = article.select_one("div.c-article-body div.main-content")
        if main is None:
            continue
        words = count_words(normalize_text(main.get_text(" ", strip=True)))
        if words > best_words:
            best_article = article
            best_words = words
    return best_article


def is_nature_like_url(url: str) -> bool:
    hostname = urllib.parse.urlparse(url).netloc.lower()
    return hostname.endswith("nature.com") or hostname.endswith(".nature.com")


def select_nature_abstract_section(body: Any):
    if BeautifulSoup is None or body is None:
        return None
    for section in body.find_all("section", recursive=False):
        if normalize_section_title(extract_section_title(section)) == "abstract":
            return section
    return None


def extract_section_title(section: Any) -> str:
    if BeautifulSoup is None or section is None:
        return ""
    heading = section.find(HEADING_TAG_PATTERN)
    if heading is None:
        return ""
    return normalize_text(heading.get_text(" ", strip=True))


def normalize_section_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def clean_nature_text_fragment(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return ""
    cleaned = NATURE_REFERENCE_RANGE_PATTERN.sub("", cleaned)
    cleaned = NATURE_REFERENCE_LIST_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\((?:ref|refs)\.\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    return normalize_text(cleaned)


def extract_nature_markdown(html_text: str, source_url: str) -> str:
    if BeautifulSoup is None:
        return ""

    soup = BeautifulSoup(html_text, "html.parser")
    article = select_nature_article_root(soup) or soup.select_one("article")
    if article is None:
        return ""

    body = article.select_one("div.c-article-body") or article
    main = body.select_one("div.main-content") or body
    lines: list[str] = []

    title_node = article.select_one("h1")
    title_text = render_clean_text_from_html(title_node)
    if title_text:
        lines.extend([f"# {title_text}", ""])

    abstract_section = select_nature_abstract_section(body)
    if abstract_section is not None:
        render_nature_section_markdown(
            abstract_section,
            lines,
            level=2,
            force_heading="Abstract",
        )

    sections = main.find_all("section", recursive=False) if main is not None else []
    if sections:
        for section in sections:
            render_nature_section_markdown(section, lines, level=2)
    elif main is not None:
        render_nature_container_markdown(main, lines, level=2)

    rendered = clean_markdown("\n".join(lines))
    return postprocess_nature_markdown(rendered, source_url)


def render_nature_section_markdown(
    section: Any,
    lines: list[str],
    *,
    level: int,
    force_heading: str | None = None,
) -> None:
    heading = force_heading or extract_section_title(section)
    if heading:
        lines.extend([f"{'#' * max(2, min(level, 6))} {heading}", ""])
    content_root = section.select_one("div.c-article-section__content") or section
    render_nature_container_markdown(content_root, lines, level=level + 1, skip_first_heading=heading or None)


def render_nature_container_markdown(
    node: Any,
    lines: list[str],
    *,
    level: int,
    skip_first_heading: str | None = None,
) -> None:
    if BeautifulSoup is None or node is None:
        return

    skipped_heading = False
    for child in node.children:
        if isinstance(child, NavigableString):
            text = normalize_text(str(child))
            if text:
                lines.extend([text, ""])
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in HTML_DROP_TAGS or should_drop_html_element(child):
            continue
        if child.name == "section":
            render_nature_section_markdown(child, lines, level=level)
            continue
        if child.name and HEADING_TAG_PATTERN.match(child.name):
            heading_text = render_clean_text_from_html(child)
            if skip_first_heading and not skipped_heading and normalize_section_title(heading_text) == normalize_section_title(skip_first_heading):
                skipped_heading = True
                continue
            skipped_heading = True
            if heading_text:
                lines.extend([f"{'#' * max(2, min(level, 6))} {heading_text}", ""])
            continue
        if child.name in {"p", "blockquote", "pre"}:
            text = render_clean_text_from_html(child)
            if text:
                lines.extend([text, ""])
            continue
        if child.name in {"ul", "ol"}:
            for item in child.find_all("li", recursive=False):
                text = render_clean_text_from_html(item)
                if text:
                    lines.append(f"- {text}")
            if lines and lines[-1]:
                lines.append("")
            continue
        if child.name == "figure":
            continue
        if child.name == "table":
            text = render_clean_text_from_html(child)
            if text:
                lines.extend([text, ""])
            continue
        if child.name in {"div", "article", "main"}:
            render_nature_container_markdown(child, lines, level=level, skip_first_heading=skip_first_heading if not skipped_heading else None)
            continue
        text = render_clean_text_from_html(child)
        if text:
            lines.extend([text, ""])


def render_clean_text_from_html(node: Any) -> str:
    rendered = render_clean_html_node(node)
    rendered = re.sub(r"[ \t\r\f\v]+", " ", rendered)
    rendered = re.sub(r" *\n *", "\n", rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return normalize_text(rendered)


def render_clean_html_node(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name in HTML_DROP_TAGS:
        return ""
    if node.name == "br":
        return "\n"
    if node.name == "a":
        text = render_clean_children(node)
        href = str(node.get("href") or "")
        if is_citation_link(href, text):
            return ""
        return text
    if node.name == "sup":
        text = render_clean_children(node)
        if is_citation_text(text):
            return ""
        return text
    if node.name == "sub":
        return render_clean_children(node)
    if node.name == "figure":
        caption = node.find("figcaption")
        return render_clean_html_node(caption)

    rendered = render_clean_children(node)
    if not rendered.strip():
        return ""
    if node.name in {"li"}:
        return f"\n\n{rendered}\n\n"
    if node.name in HTML_BLOCK_TAGS:
        return f"\n\n{rendered}\n\n"
    return rendered


def render_clean_children(node: Any) -> str:
    text = ""
    previous_child: Any = None
    for child in node.children:
        rendered = render_clean_html_node(child)
        if not rendered:
            continue
        if needs_space_between(text, rendered, previous_child, child):
            text += " "
        text += rendered
        previous_child = child
    return text


def needs_space_between(left: str, right: str, previous_child: Any, child: Any) -> bool:
    if not left or not right:
        return False
    if left[-1].isspace() or right[0].isspace():
        return False
    if is_tight_inline_node(previous_child) or is_tight_inline_node(child):
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


def is_tight_inline_node(node: Any) -> bool:
    return isinstance(node, Tag) and node.name in HTML_TIGHT_INLINE_TAGS


def last_significant_char(text: str) -> str:
    for char in reversed(text):
        if not char.isspace():
            return char
    return ""


def first_significant_char(text: str) -> str:
    for char in text:
        if not char.isspace():
            return char
    return ""


def is_citation_text(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return bool(re.fullmatch(r"[\d,\-\u2013\u2014\s]+", normalized))


def is_citation_link(href: str, text: str) -> bool:
    normalized_href = href.strip().lower()
    normalized_text = normalize_text(text)
    if "#ref-" in normalized_href or "#bib" in normalized_href or "#cite" in normalized_href:
        return True
    if is_citation_text(normalized_text) and normalized_href.startswith("#"):
        return True
    return False


def postprocess_nature_markdown(markdown_text: str, source_url: str) -> str:
    if not markdown_text:
        return ""
    cleaned = markdown_text
    cleaned = NATURE_FIGURE_LINE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"(?im)^\s*source data\s*$", "", cleaned)
    cleaned = re.sub(r"\((?:ref|refs)\.\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[([^\]]+)\]\((?:/articles/[^)]+|#[^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\b([A-Z]{1,4})\s+(\d+)\b", r"\1\2", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*]\s*$", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return clean_markdown(cleaned)


def prune_html_tree(root: Any) -> None:
    if BeautifulSoup is None:
        return

    for tag in root(HTML_DROP_TAGS):
        tag.decompose()
    for selector in HTML_DROP_SELECTORS:
        for element in root.select(selector):
            element.decompose()
    for element in list(root.find_all(href=re.compile(r"orcid\.org", re.IGNORECASE))):
        element.decompose()
    for element in list(root.find_all(True)):
        if should_drop_html_element(element):
            element.decompose()


def should_drop_html_element(element: Any) -> bool:
    if BeautifulSoup is None:
        return False
    if element.name and HEADING_TAG_PATTERN.match(element.name):
        return False

    text = normalize_text(element.get_text(separator=" ", strip=True))
    if not text:
        return False

    lowered = text.lower()
    if lowered in HTML_EXACT_NOISE_TEXTS:
        return True
    if any(lowered.startswith(prefix) for prefix in HTML_PREFIX_NOISE_TEXTS):
        return count_words(text) <= 40

    attr_tokens: list[str] = []
    for value in element.attrs.values():
        if isinstance(value, str):
            attr_tokens.append(value.lower())
        elif isinstance(value, list):
            attr_tokens.extend(str(item).lower() for item in value)
    if attr_tokens:
        joined = " ".join(attr_tokens)
        if any(token in joined for token in HTML_NOISE_ATTR_TOKENS):
            return count_words(text) <= 80
    return False


def parse_html_metadata(html_text: str, source_url: str) -> dict[str, Any]:
    parser = _MetaParser()
    parser.feed(html_text)
    parser.close()
    lookup_hints = extract_html_lookup_hints(html_text, source_url, meta=parser.meta)

    def first(*keys: str) -> str | None:
        for key in keys:
            values = parser.meta.get(key.lower())
            if values:
                value = normalize_text(values[0])
                if value:
                    return html.unescape(value)
        return None

    authors = dedupe_authors([normalize_text(value) for value in parser.meta.get("citation_author", []) if normalize_text(value)])
    doi = extract_doi_from_meta(parser.meta) or extract_doi_from_text(parser.canonical_url or "")
    html_title = normalize_text("".join(parser.title)) or None
    if not is_usable_lookup_title(html_title):
        html_title = lookup_hints.get("lookup_title")
    title = first("citation_title", "dc.title", "og:title") or html_title or None
    abstract = first("citation_abstract", "description", "dc.description", "og:description")
    if abstract and is_nature_like_url(source_url):
        abstract = clean_nature_text_fragment(abstract)
    journal_title = first("citation_journal_title", "prism.publicationname", "dc.source")
    published = first("citation_publication_date", "citation_online_date", "dc.date", "prism.publicationdate")
    keywords = [
        normalize_text(item)
        for item in parser.meta.get("citation_keywords", []) + parser.meta.get("keywords", [])
        if normalize_text(item)
    ]

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "journal_title": journal_title,
        "published": published,
        "landing_page_url": parser.canonical_url or source_url,
        "doi": doi,
        "keywords": list(dict.fromkeys(keywords)),
        "raw_meta": parser.meta,
        "lookup_title": lookup_hints.get("lookup_title"),
        "lookup_redirect_url": lookup_hints.get("redirect_url"),
        "identifier_value": lookup_hints.get("identifier_value"),
    }


def extract_html_lookup_hints(
    html_text: str,
    source_url: str,
    *,
    meta: Mapping[str, list[str]] | None = None,
) -> dict[str, str | None]:
    input_values = extract_html_input_values(html_text)
    hidden_redirect = normalize_lookup_url(input_values.get("redirecturl"), source_url)
    refresh_redirect = None
    for refresh_value in (meta or {}).get("refresh", []):
        refresh_redirect = extract_refresh_redirect_url(refresh_value, source_url)
        if refresh_redirect:
            break

    lookup_title = (
        extract_script_value(HTML_SCRIPT_ARTICLE_NAME_PATTERN, html_text)
        or normalize_text(input_values.get("articletitle") or "")
        or None
    )
    identifier_value = (
        extract_script_value(HTML_SCRIPT_IDENTIFIER_PATTERN, html_text)
        or normalize_text(input_values.get("id") or "")
        or None
    )

    return {
        "lookup_title": lookup_title if is_usable_lookup_title(lookup_title) else None,
        "redirect_url": hidden_redirect or refresh_redirect,
        "identifier_value": identifier_value,
    }


def extract_html_input_values(html_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in INPUT_TAG_PATTERN.finditer(html_text):
        attributes: dict[str, str] = {}
        for name, _, double_quoted, single_quoted in HTML_ATTRIBUTE_PATTERN.findall(match.group(0)):
            attributes[name.lower()] = html.unescape(double_quoted or single_quoted or "")
        key = normalize_text(attributes.get("name") or "").lower()
        if key:
            values[key] = attributes.get("value", "")
    return values


def extract_script_value(pattern: re.Pattern[str], html_text: str) -> str | None:
    match = pattern.search(html_text)
    if not match:
        return None
    return normalize_text(html.unescape(match.group("value")))


def extract_refresh_redirect_url(refresh_value: str, source_url: str) -> str | None:
    match = HTML_REFRESH_URL_PATTERN.search(refresh_value or "")
    if not match:
        return None
    return normalize_lookup_url(match.group("url"), source_url)


def normalize_lookup_url(value: str | None, source_url: str) -> str | None:
    raw = html.unescape((value or "").strip())
    if not raw:
        return None
    unquoted = urllib.parse.unquote(raw)
    return urllib.parse.urljoin(source_url, unquoted)


def is_usable_lookup_title(value: str | None) -> bool:
    normalized = normalize_text(value).lower()
    if not normalized:
        return False
    return not any(token in normalized for token in HTML_LOOKUP_TITLE_DENYLIST)


def extract_doi_from_meta(meta: Mapping[str, list[str]]) -> str | None:
    for key in ("citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi"):
        for value in meta.get(key, []):
            doi = extract_doi_from_text(value)
            if doi:
                return doi
    return None


def extract_doi_from_text(value: str | None) -> str | None:
    if not value:
        return None
    match = DOI_PATTERN.search(value)
    if not match:
        return None
    return normalize_doi(match.group(0).rstrip(").,;"))


def extract_article_markdown(html_text: str, source_url: str) -> str:
    cleaned_html = clean_html_for_extraction(html_text)
    if is_nature_like_url(source_url):
        custom_markdown = extract_nature_markdown(cleaned_html, source_url)
        if custom_markdown:
            return custom_markdown
    if trafilatura is not None:
        for candidate_html in [cleaned_html, html_text]:
            extracted = trafilatura.extract(
                candidate_html,
                output_format="markdown",
                include_links=True,
                include_tables=True,
                favor_precision=True,
            )
            if extracted:
                cleaned = clean_markdown(extracted)
                if cleaned:
                    return cleaned

    parser = _FallbackMarkdownParser()
    parser.feed(cleaned_html)
    parser.close()
    return clean_markdown("\n".join(parser.lines))


def clean_markdown(markdown_text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = re.sub(r"\(\s*refs?\.\s*\)", "", raw_line, flags=re.IGNORECASE).rstrip()
        normalized = normalize_text(re.sub(r"^#+\s*", "", line)).lower()
        if normalized in MARKDOWN_EXACT_NOISE_TEXTS:
            continue
        if any(normalized.startswith(prefix) for prefix in MARKDOWN_PREFIX_NOISE_TEXTS):
            continue
        if any(token in normalized for token in MARKDOWN_SHORT_NOISE_TOKENS) and count_words(normalized) <= 16:
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    return normalize_markdown_text(cleaned)


def body_character_count(markdown_text: str, metadata: Mapping[str, Any]) -> int:
    return body_metrics(markdown_text, metadata)["char_count"]


def body_metrics(markdown_text: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    candidate = normalize_markdown_text(markdown_text)
    title = normalize_text(str(metadata.get("title") or ""))
    if title:
        candidate = re.sub(rf"^#\s*{re.escape(title)}\s*", "", candidate, count=1, flags=re.IGNORECASE)
    abstract = normalize_text(str(metadata.get("abstract") or ""))
    if abstract:
        candidate = candidate.replace(abstract, "", 1)
    candidate = normalize_markdown_text(candidate)
    char_count = len(candidate)
    word_count = count_words(candidate)
    cjk_chars = sum(1 for char in candidate if "\u4e00" <= char <= "\u9fff")
    cjk_ratio = (cjk_chars / char_count) if char_count else 0.0
    has_doi = bool(normalize_doi(str(metadata.get("doi") or "")) or extract_doi_from_text(candidate))
    return {
        "text": candidate,
        "char_count": char_count,
        "word_count": word_count,
        "cjk_chars": cjk_chars,
        "cjk_ratio": cjk_ratio,
        "has_doi": has_doi,
    }


def has_sufficient_article_body(markdown_text: str, metadata: Mapping[str, Any]) -> bool:
    metrics = body_metrics(markdown_text, metadata)
    if metrics["char_count"] >= HTML_BODY_MIN_CHARS:
        return True
    if metrics["char_count"] < HTML_SHORT_BODY_MIN_CHARS:
        return False
    if metrics["cjk_chars"] >= HTML_CJK_MIN_CHARS and metrics["cjk_ratio"] >= HTML_CJK_MIN_RATIO:
        return True
    return metrics["has_doi"] and metrics["word_count"] >= HTML_SHORT_BODY_MIN_WORDS


def extract_figure_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    parser = _FigureParser()
    parser.feed(html_text)
    parser.close()
    assets: list[dict[str, str]] = []
    for item in parser.assets:
        url = item.get("url", "").strip()
        assets.append(
            {
                "kind": "figure",
                "heading": item.get("heading", "Figure"),
                "caption": item.get("caption", ""),
                "url": urllib.parse.urljoin(source_url, url) if url else "",
            }
        )
    return assets


def merge_metadata(base_metadata: Mapping[str, Any] | None, html_metadata: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(base_metadata or {})
    merged = dict(base)
    for key in ("title", "journal_title", "published", "landing_page_url", "doi"):
        merged[key] = normalize_text(str(base.get(key) or html_metadata.get(key) or "")) or None
    merged["abstract"] = normalize_text(str(html_metadata.get("abstract") or base.get("abstract") or "")) or None
    base_authors = [normalize_text(str(item)) for item in (base.get("authors") or []) if normalize_text(str(item))]
    html_authors = [normalize_text(str(item)) for item in (html_metadata.get("authors") or []) if normalize_text(str(item))]
    merged["authors"] = dedupe_authors(base_authors + html_authors)
    merged["keywords"] = list(
        dict.fromkeys(
            normalize_text(str(item))
            for item in (base.get("keywords") or []) + (html_metadata.get("keywords") or [])
            if normalize_text(str(item))
        )
    )
    merged["license_urls"] = list(base.get("license_urls") or [])
    merged["fulltext_links"] = list(base.get("fulltext_links") or [])
    merged["raw_meta"] = html_metadata.get("raw_meta", {})
    return merged


def infer_provider_from_url(url: str) -> str | None:
    hostname = urllib.parse.urlparse(url).netloc.lower()
    if any(token in hostname for token in ("sciencedirect.com", "elsevier.com")):
        return "elsevier"
    if any(token in hostname for token in ("springer.com", "springernature.com", "nature.com", "biomedcentral.com")):
        return "springer"
    if any(token in hostname for token in ("wiley.com", "onlinelibrary.wiley.com")):
        return "wiley"
    return None


class HtmlGenericClient:
    name = "html_generic"

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.user_agent = build_user_agent(env)

    def fetch_article_model(
        self,
        landing_url: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        expected_doi: str | None = None,
    ):
        try:
            response = self.transport.request(
                "GET",
                landing_url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        html_text = decode_html(response["body"])
        html_metadata = parse_html_metadata(html_text, response["url"])
        merged_metadata = merge_metadata(metadata, html_metadata)
        if expected_doi and not merged_metadata.get("doi"):
            merged_metadata["doi"] = normalize_doi(expected_doi)

        markdown_text = clean_markdown(extract_article_markdown(html_text, response["url"]))
        if not has_sufficient_article_body(markdown_text, merged_metadata):
            raise ProviderFailure("no_result", "HTML extraction did not produce enough article body text.")

        assets = extract_figure_assets(html_text, response["url"])
        return article_from_markdown(
            source="html_generic",
            metadata=merged_metadata,
            doi=normalize_doi(str(merged_metadata.get("doi") or expected_doi or "")) or None,
            markdown_text=markdown_text,
            assets=assets,
        )
