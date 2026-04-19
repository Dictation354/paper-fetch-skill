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
)
PROFILE_HTML_PREFIX_NOISE_TEXTS = {
    "springer_nature": (
    "thank you for visiting nature.com",
    "you are using a browser version with limited support for css",
    "to obtain the best experience, we recommend you use a more up to date browser",
    "in the meantime, to ensure continued support, we are displaying the site without styles and javascript",
    "anyone you share the following link with will be able to read this content",
    "sorry, a shareable link is not currently available for this article",
    )
}
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
PROFILE_MARKDOWN_PREFIX_NOISE_TEXTS = {
    "springer_nature": PROFILE_HTML_PREFIX_NOISE_TEXTS["springer_nature"],
}
MARKDOWN_SHORT_NOISE_TOKENS = (
    "sign in",
    "sign-in",
    "log in",
    "login",
    "view access options",
)
MARKDOWN_PROMO_TOKENS: tuple[str, ...] = ()
PROFILE_MARKDOWN_PROMO_TOKENS = {
    "pnas": (
        "sign up for pnas alerts",
        "get alerts for new articles, or get an alert when an article is cited",
    )
}
DEFAULT_NOISE_PROFILE = "generic"
HTML_BODY_MIN_CHARS = 800
HTML_SHORT_BODY_MIN_CHARS = 300
HTML_SHORT_BODY_MIN_WORDS = 60
HTML_SINGLE_BLOCK_MIN_WORDS = 90
HTML_CJK_MIN_CHARS = 120
HTML_SINGLE_BLOCK_MIN_CJK_CHARS = 180
HTML_CJK_MIN_RATIO = 0.20
MARKDOWN_ABSTRACT_HEADINGS = {"abstract", "structured abstract"}
MARKDOWN_AUXILIARY_HEADINGS = {"abbreviations"}
MARKDOWN_FRONT_MATTER_HEADINGS = {
    "editor's summary",
    "editor’s summary",
    "summary",
    "key points",
    "highlights",
    "graphical abstract",
}
MARKDOWN_BACK_MATTER_HEADINGS = (
    "references",
    "references and notes",
    "bibliography",
    "acknowledgments",
    "supplementary materials",
    "supplementary material",
    "supplementary information",
    "supporting information",
    "notes",
    "data availability",
    "author contributions",
    "funding",
    "ethics",
    "competing interests",
    "disclosures",
)
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


def _normalize_noise_profile(noise_profile: str | None) -> str:
    normalized = normalize_text(noise_profile or DEFAULT_NOISE_PROFILE).lower().replace("-", "_")
    if normalized in {DEFAULT_NOISE_PROFILE, *PROFILE_HTML_PREFIX_NOISE_TEXTS, *PROFILE_MARKDOWN_PROMO_TOKENS}:
        return normalized
    return DEFAULT_NOISE_PROFILE


def _html_prefix_noise_texts(noise_profile: str | None) -> tuple[str, ...]:
    active_noise_profile = _normalize_noise_profile(noise_profile)
    return HTML_PREFIX_NOISE_TEXTS + PROFILE_HTML_PREFIX_NOISE_TEXTS.get(active_noise_profile, ())


def _markdown_prefix_noise_texts(noise_profile: str | None) -> tuple[str, ...]:
    active_noise_profile = _normalize_noise_profile(noise_profile)
    return MARKDOWN_PREFIX_NOISE_TEXTS + PROFILE_MARKDOWN_PREFIX_NOISE_TEXTS.get(active_noise_profile, ())


def _markdown_promo_tokens(noise_profile: str | None) -> tuple[str, ...]:
    active_noise_profile = _normalize_noise_profile(noise_profile)
    return MARKDOWN_PROMO_TOKENS + PROFILE_MARKDOWN_PROMO_TOKENS.get(active_noise_profile, ())


def clean_html_for_extraction(html_text: str, *, noise_profile: str | None = None) -> str:
    if BeautifulSoup is None:
        return html_text

    soup = BeautifulSoup(html_text, "html.parser")
    root = select_html_content_root(soup)
    if root is None:
        root = soup.body or soup

    candidate_soup = BeautifulSoup(str(root), "html.parser")
    active_root = candidate_soup.body or candidate_soup
    prune_html_tree(active_root, noise_profile=noise_profile)
    return str(active_root)


def select_html_content_root(root: Any):
    if BeautifulSoup is None:
        return None

    from . import html_springer_nature

    springer_nature_root = html_springer_nature.select_springer_nature_article_root(root)
    if springer_nature_root is not None:
        return springer_nature_root

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
    noise_profile: str | None = None,
) -> str:
    active_noise_profile = _normalize_noise_profile(noise_profile)
    cleaned_html = clean_html_for_extraction(html_text, noise_profile=active_noise_profile)

    from . import html_springer_nature

    if html_springer_nature.is_springer_nature_url(source_url):
        custom_markdown = html_springer_nature.extract_springer_nature_markdown(cleaned_html, source_url)
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
                cleaned = clean_markdown(extracted, noise_profile=active_noise_profile)
                if cleaned:
                    return cleaned

    parser = _FallbackMarkdownParser()
    parser.feed(cleaned_html)
    parser.close()
    return clean_markdown("\n".join(parser.lines), noise_profile=active_noise_profile)


def clean_markdown(markdown_text: str, *, noise_profile: str | None = None) -> str:
    active_noise_profile = _normalize_noise_profile(noise_profile)
    markdown_prefix_noise_texts = _markdown_prefix_noise_texts(active_noise_profile)
    markdown_promo_tokens = _markdown_promo_tokens(active_noise_profile)
    cleaned_lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = re.sub(r"\(\s*refs?\.\s*\)", "", raw_line, flags=re.IGNORECASE).rstrip()
        normalized = normalize_text(re.sub(r"^#+\s*", "", line)).lower()
        if normalized in MARKDOWN_EXACT_NOISE_TEXTS:
            continue
        if any(normalized.startswith(prefix) for prefix in markdown_prefix_noise_texts):
            continue
        if any(token in normalized for token in markdown_promo_tokens):
            continue
        if any(token in normalized for token in MARKDOWN_SHORT_NOISE_TOKENS) and count_words(normalized) <= 16:
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    return normalize_markdown_text(cleaned)


def body_character_count(markdown_text: str, metadata: Mapping[str, Any]) -> int:
    return body_metrics(markdown_text, metadata)["char_count"]


def _canonical_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", normalize_text(value).lower(), flags=re.UNICODE)


def _split_markdown_blocks(markdown_text: str) -> list[str]:
    return [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]


def _heading_text(block: str) -> str | None:
    stripped = block.strip()
    if not stripped.startswith("#"):
        return None
    match = re.match(r"^(#+)\s*(.*)$", stripped)
    if not match:
        return None
    return normalize_text(match.group(2))


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


def _looks_like_access_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if any(prefix in lowered for prefix in MARKDOWN_PREFIX_NOISE_TEXTS):
        return True
    return any(token in lowered for token in MARKDOWN_SHORT_NOISE_TOKENS)


def _looks_like_promo_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if not lowered:
        return False
    if lowered == "learn more":
        return True
    return any(token in lowered for token in MARKDOWN_PROMO_TOKENS)


def _looks_like_caption_block(text: str) -> bool:
    lowered = normalize_text(text).lower()
    return lowered.startswith("**figure") or lowered.startswith("**table")


def _looks_like_markdown_image_block(text: str) -> bool:
    return bool(re.match(r"^!\[[^\]]*\]\([^)]+\)$", normalize_text(text)))


def _looks_like_equation_label_block(text: str) -> bool:
    return normalize_text(text).lower().startswith("**equation")


def _looks_like_front_matter_block(text: str, *, title: str | None = None) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not normalized:
        return True
    if title and lowered == normalize_text(title).lower():
        return True
    if lowered.startswith("by "):
        return True
    if any(pattern.match(normalized) for pattern in (re.compile(r"^doi:\s*", flags=re.IGNORECASE), re.compile(r"^(vol\.?|volume)\b", flags=re.IGNORECASE), re.compile(r"^issue\b", flags=re.IGNORECASE))):
        return True
    return lowered in {"authors", "author information", "affiliations"}


def _filtered_body_blocks(markdown_text: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    candidate = normalize_markdown_text(markdown_text)
    title = normalize_text(str(metadata.get("title") or ""))
    if title:
        candidate = _strip_title_heading(candidate, title)
    abstract = normalize_text(str(metadata.get("abstract") or ""))
    abstract_canonical = _canonical_text(abstract)
    blocks = _split_markdown_blocks(candidate)
    filtered_blocks: list[str] = []
    abstract_blocks: list[str] = []
    body_heading_count = 0
    body_block_count = 0
    in_abstract = False
    in_back_matter = False
    in_front_matter = False
    in_auxiliary = False
    in_formula = False
    saw_abstract_heading = False

    for block in blocks:
        heading = _heading_text(block)
        if heading is not None:
            normalized_heading = normalize_text(heading).lower().strip(" :")
            if title and normalized_heading == normalize_text(title).lower():
                continue
            if normalized_heading in MARKDOWN_ABSTRACT_HEADINGS or normalized_heading.startswith("abstract"):
                in_abstract = True
                in_back_matter = False
                in_front_matter = False
                in_auxiliary = False
                saw_abstract_heading = True
                continue
            if normalized_heading in MARKDOWN_AUXILIARY_HEADINGS:
                in_auxiliary = True
                in_abstract = False
                in_back_matter = False
                in_front_matter = False
                continue
            if normalized_heading in MARKDOWN_FRONT_MATTER_HEADINGS:
                in_front_matter = True
                in_abstract = False
                in_back_matter = False
                in_auxiliary = False
                continue
            if any(normalized_heading.startswith(token) for token in MARKDOWN_BACK_MATTER_HEADINGS):
                in_back_matter = True
                in_abstract = False
                in_front_matter = False
                in_auxiliary = False
                continue
            in_abstract = False
            in_back_matter = False
            in_front_matter = False
            in_auxiliary = False
            filtered_blocks.append(block)
            body_heading_count += 1
            continue

        normalized_block = normalize_text(block)
        block_canonical = _canonical_text(normalized_block)
        if normalized_block == "$$":
            in_formula = not in_formula
            continue
        if in_abstract:
            if normalized_block:
                abstract_blocks.append(normalized_block)
            continue
        if in_back_matter or in_front_matter or in_auxiliary or in_formula:
            continue
        if (
            _looks_like_access_block(normalized_block)
            or _looks_like_promo_block(normalized_block)
            or _looks_like_markdown_image_block(normalized_block)
            or _looks_like_caption_block(normalized_block)
            or _looks_like_equation_label_block(normalized_block)
            or _looks_like_front_matter_block(normalized_block, title=title or None)
        ):
            continue
        if abstract_canonical and block_canonical and block_canonical == abstract_canonical:
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
        "has_abstract": bool(saw_abstract_heading or abstract_text),
    }


def body_metrics(markdown_text: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    from .html_generic import extract_doi_from_text

    filtered = _filtered_body_blocks(markdown_text, metadata)
    candidate = filtered["body_text"]
    char_count = len(candidate)
    word_count = count_words(candidate)
    cjk_chars = sum(1 for char in candidate if "\u4e00" <= char <= "\u9fff")
    cjk_ratio = (cjk_chars / char_count) if char_count else 0.0
    has_doi = bool(normalize_doi(str(metadata.get("doi") or "")) or extract_doi_from_text(candidate))
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


def has_sufficient_article_body(markdown_text: str, metadata: Mapping[str, Any]) -> bool:
    metrics = body_metrics(markdown_text, metadata)
    if metrics["char_count"] < HTML_SHORT_BODY_MIN_CHARS:
        return False
    has_body_structure = metrics["body_block_count"] >= 2 or metrics["body_heading_count"] >= 1
    if metrics["cjk_chars"] >= HTML_CJK_MIN_CHARS and metrics["cjk_ratio"] >= HTML_CJK_MIN_RATIO:
        if has_body_structure:
            return True
        return (
            metrics["body_block_count"] == 1
            and (
                not metrics["has_abstract"]
                or float(metrics.get("body_to_abstract_ratio") or 0.0) >= 1.5
            )
            and metrics["cjk_chars"] >= HTML_SINGLE_BLOCK_MIN_CJK_CHARS
        )
    if metrics["word_count"] < HTML_SHORT_BODY_MIN_WORDS:
        return False
    if has_body_structure:
        return True
    return (
        metrics["body_block_count"] == 1
        and metrics["word_count"] >= HTML_SINGLE_BLOCK_MIN_WORDS
        and (
            not metrics["has_abstract"]
            or float(metrics.get("body_to_abstract_ratio") or 0.0) >= 1.5
        )
    )


def prune_html_tree(root: Any, *, noise_profile: str | None = None) -> None:
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
        if should_drop_html_element(element, noise_profile=noise_profile):
            element.decompose()


def should_drop_html_element(element: Any, *, noise_profile: str | None = None) -> bool:
    if BeautifulSoup is None:
        return False
    if element.name and re.compile(r"^h[1-6]$").match(element.name):
        return False

    text = normalize_text(element.get_text(separator=" ", strip=True))
    if not text:
        return False

    has_heading_descendant = bool(element.find(re.compile(r"^h[1-6]$")))
    lowered = text.lower()
    if lowered in HTML_EXACT_NOISE_TEXTS:
        return True
    if any(lowered.startswith(prefix) for prefix in _html_prefix_noise_texts(noise_profile)):
        if has_heading_descendant:
            return False
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
