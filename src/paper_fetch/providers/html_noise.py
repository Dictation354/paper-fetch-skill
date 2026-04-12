"""Generic HTML cleanup and Markdown extraction helpers."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Mapping

from ..models import normalize_markdown_text, normalize_text
from ..publisher_identity import normalize_doi

try:
    import trafilatura
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    trafilatura = None

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - exercised implicitly when dependency is absent
    BeautifulSoup = None
    Tag = None

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
HTML_BODY_MIN_CHARS = 800
HTML_SHORT_BODY_MIN_CHARS = 300
HTML_SHORT_BODY_MIN_WORDS = 60
HTML_CJK_MIN_CHARS = 120
HTML_CJK_MIN_RATIO = 0.20
_USE_MODULE_TRAFILATURA = object()


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

    from . import html_nature

    nature_root = html_nature.select_nature_article_root(root)
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


def extract_article_markdown(
    html_text: str,
    source_url: str,
    *,
    trafilatura_backend: Any = _USE_MODULE_TRAFILATURA,
) -> str:
    cleaned_html = clean_html_for_extraction(html_text)

    from . import html_nature

    if html_nature.is_nature_like_url(source_url):
        custom_markdown = html_nature.extract_nature_markdown(cleaned_html, source_url)
        if custom_markdown:
            return custom_markdown

    active_trafilatura = trafilatura if trafilatura_backend is _USE_MODULE_TRAFILATURA else trafilatura_backend
    if active_trafilatura is not None:
        for candidate_html in [cleaned_html, html_text]:
            extracted = active_trafilatura.extract(
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
    from .html_generic import extract_doi_from_text

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
    if element.name and re.compile(r"^h[1-6]$").match(element.name):
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
