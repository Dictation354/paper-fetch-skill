#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
PMC_IDCONV_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
PMC_OAI_URL = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
CROSSREF_WORK_URL = "https://api.crossref.org/works/{doi}"
DEFAULT_FLARESOLVERR_URL = "http://127.0.0.1:8191/v1"
DEFAULT_FLARESOLVERR_WAIT_SECONDS = 8
DEFAULT_FLARESOLVERR_MAX_TIMEOUT_MS = 120000
SUCCESS_STATUSES = {
    "success_pmc",
    "success_html",
    "success_pdf_fallback",
}
PMC_DELAY_RANGE = (1.0, 2.0)
CROSSREF_DELAY_RANGE = (1.0, 2.0)
CLOUDFLARE_COOKIE_NAMES = {
    "_cfuvid",
    "__cf_bm",
    "cf_clearance",
}

CHALLENGE_PATTERNS = (
    "just a moment",
    "verify you are human",
    "checking your browser",
    "challenge-error-text",
    "attention required",
    "cloudflare",
)
PAYWALL_PATTERNS = (
    "purchase access",
    "institutional access",
    "log in to your account",
    "login to your account",
    "subscribe to continue",
    "access through your institution",
    "rent or buy",
    "purchase this article",
)
NOT_FOUND_PATTERNS = (
    "doi not found",
    "page not found",
    "article not found",
    "content not found",
)
COLLATERAL_HEADING_TITLES = {
    "continue reading",
    "information & authors",
    "metrics & citations",
    "view options",
    "figures",
    "tables",
    "media",
}

SITE_RULES: dict[str, dict[str, Any]] = {
    "science": {
        "domains": {"science.org", "www.science.org"},
        "candidate_selectors": [
            "article",
            "main article",
            "[role='main'] article",
            ".article",
            ".article__body",
            ".article__fulltext",
            ".article-view",
            "main",
            "[role='main']",
            "#main-content",
            ".main-content",
        ],
        "remove_selectors": [
            "script",
            "style",
            "noscript",
            "iframe",
            "svg",
            "header .social-share",
            ".social-share",
            ".metrics-widget",
            ".article-tools",
            ".related-content",
            ".recommended-articles",
            ".jump-to-nav",
            ".article-access-info",
            ".article-metrics",
            ".tab__nav",
            ".references-tab",
            ".permissions",
            ".toc",
            ".breadcrumbs",
            ".issue-item__citation",
            ".article-header__access",
        ],
        "drop_keywords": {
            "metrics",
            "metric",
            "share",
            "social",
            "recommend",
            "related",
            "citation-tool",
            "toolbar",
            "breadcrumb",
            "download",
            "access-widget",
            "advert",
            "cookie",
            "promo",
            "banner",
            "tab-nav",
            "jump-to",
        },
        "drop_text": {
            "Check for updates",
            "View Metrics",
            "Share",
            "Cite",
            "Permissions",
        },
    },
    "pnas": {
        "domains": {"pnas.org", "www.pnas.org"},
        "candidate_selectors": [
            "article",
            "main article",
            "[role='main'] article",
            ".article",
            ".article__body",
            ".article__fulltext",
            ".core-container",
            ".article-content",
            "main",
            "[role='main']",
            "#main-content",
            ".main-content",
        ],
        "remove_selectors": [
            "script",
            "style",
            "noscript",
            "iframe",
            "svg",
            ".social-share",
            ".article-tools",
            ".metrics-widget",
            ".related-content",
            ".recommended-articles",
            ".tab__nav",
            ".toc",
            ".breadcrumbs",
            ".accessIndicators",
            ".articleHeader__supplemental",
            ".article-header__access",
        ],
        "drop_keywords": {
            "metrics",
            "metric",
            "share",
            "social",
            "recommend",
            "related",
            "citation-tool",
            "toolbar",
            "breadcrumb",
            "download",
            "access-widget",
            "advert",
            "cookie",
            "promo",
            "banner",
            "tab-nav",
            "jump-to",
        },
        "drop_text": {
            "Check for updates",
            "View Metrics",
            "Share",
            "Cite",
            "Permissions",
        },
    },
}


@dataclass
class ArticleInput:
    doi: str
    label: Optional[str]
    publisher_override: Optional[str]
    row_number: int


@dataclass
class OutputPaths:
    root: Path
    raw_xml: Path
    raw_html: Path
    raw_pdf: Path
    markdown: Path
    logs: Path
    manifest: Path


@dataclass
class FetchFailure(Exception):
    status: str
    error_kind: str
    message: str
    details: Optional[dict[str, Any]] = None
    transient: Optional[dict[str, Any]] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "error_kind": self.error_kind,
            "message": self.message,
            "details": self.details or {},
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_doi(raw: str) -> str:
    value = (raw or "").strip()
    value = re.sub(r"^(doi:\s*)", "", value, flags=re.I)
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = value.strip().strip("/")
    return value.lower()


def safe_slug(value: str) -> str:
    normalized = normalize_doi(value)
    normalized = normalized.replace("/", "_")
    normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "unknown-doi"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_output_dirs(root: Path) -> OutputPaths:
    paths = OutputPaths(
        root=root,
        raw_xml=root / "raw" / "xml",
        raw_html=root / "raw" / "html",
        raw_pdf=root / "raw" / "pdf",
        markdown=root / "markdown",
        logs=root / "logs",
        manifest=root / "manifest.jsonl",
    )
    for path in [
        paths.root,
        paths.raw_xml,
        paths.raw_html,
        paths.raw_pdf,
        paths.markdown,
        paths.logs,
    ]:
        path.mkdir(parents=True, exist_ok=True)
    return paths


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def build_local_service_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    return session


def polite_sleep(min_seconds: float, max_seconds: float) -> float:
    if max_seconds <= 0:
        return 0.0
    actual_max = max(max_seconds, min_seconds)
    duration = random.uniform(min_seconds, actual_max)
    time.sleep(duration)
    return duration


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_completed_successes(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    completed: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            doi = normalize_doi(item.get("doi", ""))
            status = item.get("status")
            markdown_path = Path(item["markdown_path"]) if item.get("markdown_path") else None
            if doi and status in SUCCESS_STATUSES and markdown_path and markdown_path.exists():
                completed[doi] = item
    return completed


def load_inputs(csv_path: Path) -> list[ArticleInput]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "doi" not in (reader.fieldnames or []):
            raise ValueError("Input CSV must contain a 'doi' column")

        items: list[ArticleInput] = []
        seen: set[str] = set()
        for index, row in enumerate(reader, start=2):
            doi = normalize_doi(row.get("doi", ""))
            if not doi or doi in seen:
                continue
            seen.add(doi)
            publisher = normalize_whitespace(row.get("publisher", "")).lower() or None
            label = normalize_whitespace(row.get("label", "")) or None
            items.append(
                ArticleInput(
                    doi=doi,
                    label=label,
                    publisher_override=publisher,
                    row_number=index,
                )
            )
        return items


def infer_publisher(
    doi: str,
    override: Optional[str] = None,
    crossref_publisher: Optional[str] = None,
    crossref_url: Optional[str] = None,
) -> Optional[str]:
    if override:
        lowered = override.strip().lower()
        if lowered in {"science", "pnas"}:
            return lowered
        return None

    if doi.startswith("10.1126/"):
        return "science"
    if doi.startswith("10.1073/"):
        return "pnas"

    blob = " ".join(filter(None, [crossref_publisher, crossref_url])).lower()
    if "science.org" in blob or "american association for the advancement of science" in blob or "aaas" in blob:
        return "science"
    if "pnas.org" in blob or "proceedings of the national academy of sciences" in blob:
        return "pnas"
    return None


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def first_descendant_text(node: ET.Element, target_name: str) -> Optional[str]:
    for elem in node.iter():
        if local_name(elem.tag) == target_name:
            text = jats_inline_text(elem)
            if text:
                return text
    return None


def normalize_path(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    return str(path.resolve())


def read_crossref_metadata(session: requests.Session, doi: str) -> Optional[dict[str, Any]]:
    url = CROSSREF_WORK_URL.format(doi=quote(doi, safe=""))
    response = session.get(url, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    return payload.get("message")


def extract_pdf_url_from_crossref(message: Optional[dict[str, Any]]) -> Optional[str]:
    if not message:
        return None
    for item in message.get("link", []) or []:
        url = item.get("URL") or ""
        if "/doi/pdf/" in url:
            return url
        if item.get("content-type") == "application/pdf":
            return url
    return None


def build_html_candidates(publisher: str, doi: str) -> list[str]:
    if publisher == "science":
        base_urls = ["https://www.science.org", "https://science.org"]
        path_templates = ["/doi/full/{doi}", "/doi/{doi}"]
    else:
        base_urls = ["https://www.pnas.org", "https://pnas.org"]
        path_templates = ["/doi/{doi}", "/doi/full/{doi}"]

    candidates: list[str] = []
    for base in base_urls:
        for template in path_templates:
            candidates.append(f"{base}{template.format(doi=doi)}")
    return candidates


def build_pdf_candidates(publisher: str, doi: str, crossref_pdf_url: Optional[str]) -> list[str]:
    candidates: list[str] = []
    if crossref_pdf_url:
        candidates.append(crossref_pdf_url)
    if publisher == "science":
        base_urls = ["https://www.science.org", "https://science.org"]
        path_templates = ["/doi/pdf/{doi}"]
    else:
        base_urls = ["https://www.pnas.org", "https://pnas.org"]
        path_templates = ["/doi/pdf/{doi}?download=true", "/doi/pdf/{doi}"]
    for base in base_urls:
        for template in path_templates:
            url = f"{base}{template.format(doi=doi)}"
            if url not in candidates:
                candidates.append(url)
    return candidates


def resolve_pmcid(session: requests.Session, doi: str, tool_email: str) -> Optional[str]:
    response = session.get(
        PMC_IDCONV_URL,
        params={
            "ids": doi,
            "format": "json",
            "idtype": "doi",
            "tool": "fetch_fulltext",
            "email": tool_email,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    for record in payload.get("records", []):
        pmcid = record.get("pmcid")
        if pmcid:
            return pmcid
    return None


def extract_article_xml_from_oai(oai_xml: str) -> Optional[str]:
    root = ET.fromstring(oai_xml)
    for elem in root.iter():
        if local_name(elem.tag) == "error":
            return None
        if local_name(elem.tag) == "article":
            return ET.tostring(elem, encoding="unicode")
    return None


def fetch_pmc_article_xml(session: requests.Session, pmcid: str) -> Optional[str]:
    pmcid_numeric = pmcid.replace("PMC", "")
    response = session.get(
        PMC_OAI_URL,
        params={
            "verb": "GetRecord",
            "identifier": f"oai:pubmedcentral.nih.gov:{pmcid_numeric}",
            "metadataPrefix": "pmc",
        },
        timeout=30,
    )
    response.raise_for_status()
    return extract_article_xml_from_oai(response.text)


def strip_xml_namespaces(elem: ET.Element) -> ET.Element:
    clone = ET.fromstring(ET.tostring(elem, encoding="unicode"))
    for node in clone.iter():
        node.tag = local_name(node.tag)
        cleaned_attrib: dict[str, str] = {}
        for key, value in node.attrib.items():
            cleaned_attrib[local_name(key)] = value
        node.attrib.clear()
        node.attrib.update(cleaned_attrib)
    return clone


def jats_inline_text(elem: ET.Element) -> str:
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)

    for child in list(elem):
        name = local_name(child.tag)
        if name == "ext-link":
            label = normalize_whitespace("".join(child.itertext()))
            href = child.attrib.get("{http://www.w3.org/1999/xlink}href") or child.attrib.get("href")
            if href and label and label != href:
                parts.append(f"[{label}]({href})")
            else:
                parts.append(href or label)
        else:
            parts.append(jats_inline_text(child))
        if child.tail:
            parts.append(child.tail)

    return normalize_whitespace("".join(parts))


def render_jats_list(list_elem: ET.Element) -> list[str]:
    ordered = (list_elem.attrib.get("list-type") or "").lower() in {"order", "ordered", "number"}
    lines: list[str] = []
    for index, item in enumerate([child for child in list(list_elem) if local_name(child.tag) == "list-item"], start=1):
        bullet = f"{index}." if ordered else "-"
        content_parts: list[str] = []
        for child in list(item):
            if local_name(child.tag) == "p":
                paragraph = jats_inline_text(child)
                if paragraph:
                    content_parts.append(paragraph)
        if not content_parts:
            fallback = jats_inline_text(item)
            if fallback:
                content_parts.append(fallback)
        if content_parts:
            lines.append(f"{bullet} {' '.join(content_parts)}")
    return lines


def extract_jats_caption(node: ET.Element) -> Optional[str]:
    for child in node.iter():
        if local_name(child.tag) == "caption":
            text = normalize_whitespace(" ".join(jats_inline_text(sub) for sub in child if jats_inline_text(sub)))
            if not text:
                text = jats_inline_text(child)
            if text:
                return text
    return None


def render_jats_node(node: ET.Element, level: int = 2) -> list[str]:
    name = local_name(node.tag)
    blocks: list[str] = []

    if name == "title":
        title_text = jats_inline_text(node)
        if title_text:
            blocks.append(f"{'#' * min(level, 6)} {title_text}")
        return blocks

    if name == "p":
        paragraph = jats_inline_text(node)
        if paragraph:
            blocks.append(paragraph)
        return blocks

    if name == "sec":
        title = first_descendant_text(node, "title")
        if title:
            blocks.append(f"{'#' * min(level, 6)} {title}")
        for child in list(node):
            if local_name(child.tag) == "title":
                continue
            blocks.extend(render_jats_node(child, level + 1))
        return blocks

    if name == "list":
        return render_jats_list(node)

    if name == "fig":
        caption = extract_jats_caption(node)
        return [f"Figure: {caption}"] if caption else []

    if name == "table-wrap":
        caption = extract_jats_caption(node)
        if caption:
            blocks.append(f"Table: {caption}")
        table_elem = next((elem for elem in node.iter() if local_name(elem.tag) == "table"), None)
        if table_elem is not None:
            blocks.append(ET.tostring(strip_xml_namespaces(table_elem), encoding="unicode", method="html"))
        return blocks

    for child in list(node):
        blocks.extend(render_jats_node(child, level))
    return blocks


def render_jats_blocks(node: ET.Element, level: int = 2) -> list[str]:
    blocks: list[str] = []
    for child in list(node):
        blocks.extend(render_jats_node(child, level))
    return blocks


def jats_xml_to_markdown(article_xml: str) -> str:
    root = ET.fromstring(article_xml)
    title = None
    abstract_nodes: list[ET.Element] = []
    body = None
    ref_list = None

    for elem in root.iter():
        name = local_name(elem.tag)
        if name == "article-title" and not title:
            title = jats_inline_text(elem)
        elif name == "abstract":
            abstract_nodes.append(elem)
        elif name == "body" and body is None:
            body = elem
        elif name == "ref-list" and ref_list is None:
            ref_list = elem

    lines: list[str] = []
    if title:
        lines.append(f"# {title}")

    if abstract_nodes:
        lines.append("## Abstract")
        for abstract_node in abstract_nodes:
            lines.extend(render_jats_blocks(abstract_node, level=3))

    if body is not None:
        lines.extend(render_jats_blocks(body, level=2))

    if ref_list is not None:
        references: list[str] = []
        for index, ref in enumerate([elem for elem in list(ref_list) if local_name(elem.tag) == "ref"], start=1):
            text = jats_inline_text(ref)
            if text:
                references.append(f"{index}. {text}")
        if references:
            lines.append("## References")
            lines.extend(references)

    markdown = "\n\n".join(line for line in lines if normalize_whitespace(line))
    return markdown.strip() + ("\n" if markdown else "")


def detect_html_block(title: str, text: str, response_status: Optional[int]) -> Optional[FetchFailure]:
    combined = normalize_whitespace(" ".join([title, text])).lower()
    if any(pattern in combined for pattern in CHALLENGE_PATTERNS):
        return FetchFailure(
            status="blocked_captcha",
            error_kind="cloudflare_challenge",
            message="Encountered a challenge or CAPTCHA page while loading publisher HTML",
        )
    if response_status == 404 or any(pattern in combined for pattern in NOT_FOUND_PATTERNS):
        return FetchFailure(
            status="not_found",
            error_kind="publisher_not_found",
            message="Publisher page was not found for this DOI",
        )
    if response_status in {401, 402, 403} and not any(pattern in combined for pattern in CHALLENGE_PATTERNS):
        return FetchFailure(
            status="blocked_paywall",
            error_kind="publisher_access_denied",
            message="Publisher denied access to the full-text page",
        )
    if any(pattern in combined for pattern in PAYWALL_PATTERNS):
        return FetchFailure(
            status="blocked_paywall",
            error_kind="publisher_paywall",
            message="Publisher paywall or access gate detected on the page",
        )
    return None


def choose_parser() -> str:
    return "lxml" if has_module("lxml") else "html.parser"


def summarize_html(html: str, limit: int = 1000) -> str:
    soup = BeautifulSoup(html, choose_parser())
    text = " ".join(soup.stripped_strings)
    return text[:limit]


def sanitize_storage_state(path: Path) -> Path:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cookies = payload.get("cookies", []) or []
    filtered_cookies = [
        cookie
        for cookie in cookies
        if cookie.get("name") not in CLOUDFLARE_COOKIE_NAMES
        and not str(cookie.get("name", "")).startswith("cf_chl_")
    ]
    payload["cookies"] = filtered_cookies

    fd, temp_path = tempfile.mkstemp(prefix="playwright_state_", suffix=".json")
    temp_file = Path(temp_path)
    os.close(fd)
    temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return temp_file


def heading_title(line: str) -> str:
    title = re.sub(r"^#+\s*", "", line).strip()
    title = title.replace("*", "")
    return normalize_whitespace(title).lower()


def looks_like_abstract_redirect(requested_url: str, final_url: Optional[str]) -> bool:
    if not final_url:
        return False
    requested = requested_url.lower()
    final = final_url.lower()
    return "/doi/full/" in requested and "/doi/abs/" in final and requested != final


def score_container(node: Tag) -> float:
    text = " ".join(node.stripped_strings)
    text_length = len(text)
    paragraph_count = len(node.find_all("p"))
    heading_count = len(node.find_all(re.compile(r"^h[1-6]$")))
    link_count = len(node.find_all("a"))
    score = text_length / 120.0
    score += paragraph_count * 6.0
    score += heading_count * 12.0
    score -= max(0, link_count - paragraph_count * 2) * 1.5
    lowered = text.lower()
    if any(pattern in lowered for pattern in CHALLENGE_PATTERNS):
        score -= 500
    if "abstract" in lowered:
        score += 20
    if "references" in lowered:
        score += 20
    return score


def select_best_container(soup: BeautifulSoup, publisher: str) -> Optional[Tag]:
    selectors = SITE_RULES[publisher]["candidate_selectors"]
    candidates: list[tuple[float, Tag]] = []
    seen: set[int] = set()
    for selector in selectors:
        try:
            nodes = soup.select(selector)
        except Exception:
            continue
        for node in nodes:
            if id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append((score_container(node), node))
    if not candidates:
        for node in soup.find_all(["article", "main", "body"]):
            if id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append((score_container(node), node))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def node_identity_text(node: Tag) -> str:
    attrs = getattr(node, "attrs", None) or {}
    values = []
    node_id = attrs.get("id")
    if node_id:
        values.append(str(node_id))
    for class_name in attrs.get("class", []):
        values.append(str(class_name))
    return " ".join(values).lower()


def should_drop_node(node: Tag, publisher: str) -> bool:
    if node.name in {"script", "style", "noscript", "svg", "iframe", "button", "input", "form"}:
        return True

    identity = node_identity_text(node)
    text = normalize_whitespace(node.get_text(" ", strip=True))
    short_text = len(text) <= 200
    for keyword in SITE_RULES[publisher]["drop_keywords"]:
        if keyword in identity and short_text:
            return True
    if short_text and text in SITE_RULES[publisher]["drop_text"]:
        return True
    if short_text and any(pattern in text.lower() for pattern in {"share this", "view metrics", "article metrics"}):
        return True
    return False


def clean_container(container: Tag, publisher: str) -> Tag:
    for selector in SITE_RULES[publisher]["remove_selectors"]:
        for node in list(container.select(selector)):
            node.decompose()

    for node in list(container.find_all(True)):
        if should_drop_node(node, publisher):
            node.decompose()
    return container


def render_inline_html(node: Tag) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
            continue

        if not isinstance(child, Tag):
            continue

        if child.name == "br":
            parts.append("\n")
            continue

        content = render_inline_html(child)
        if child.name == "a":
            href = (getattr(child, "attrs", None) or {}).get("href")
            label = normalize_whitespace(content)
            if href and label:
                parts.append(f"[{label}]({href})")
            else:
                parts.append(label or href or "")
        elif child.name in {"strong", "b"}:
            parts.append(f"**{normalize_whitespace(content)}**")
        elif child.name in {"em", "i"}:
            parts.append(f"*{normalize_whitespace(content)}*")
        elif child.name == "sup":
            parts.append(f"^{normalize_whitespace(content)}^")
        elif child.name == "sub":
            parts.append(f"~{normalize_whitespace(content)}~")
        else:
            parts.append(content)

    text = "".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def render_html_list(node: Tag) -> list[str]:
    ordered = node.name == "ol"
    lines: list[str] = []
    for index, item in enumerate(node.find_all("li", recursive=False), start=1):
        bullet = f"{index}." if ordered else "-"
        text = render_inline_html(item)
        if text:
            lines.append(f"{bullet} {text}")
    return lines


def extract_caption_text(node: Tag) -> Optional[str]:
    caption = node.find(["figcaption", "caption"])
    if caption is None:
        return None
    text = render_inline_html(caption)
    return text or None


def render_html_blocks(node: Tag) -> list[str]:
    blocks: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            text = normalize_whitespace(str(child))
            if text:
                blocks.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        if child.name in {"section", "div", "article", "main", "body"}:
            blocks.extend(render_html_blocks(child))
        elif re.fullmatch(r"h[1-6]", child.name or ""):
            text = render_inline_html(child)
            if text:
                level = int(child.name[1])
                blocks.append(f"{'#' * level} {text}")
        elif child.name == "p":
            text = render_inline_html(child)
            if text:
                blocks.append(text)
        elif child.name in {"ul", "ol"}:
            blocks.extend(render_html_list(child))
        elif child.name == "figure":
            caption = extract_caption_text(child)
            if caption:
                blocks.append(f"Figure: {caption}")
        elif child.name == "table":
            blocks.append(str(child))
        elif child.name == "blockquote":
            quote_text = render_inline_html(child)
            if quote_text:
                blocks.append(f"> {quote_text}")
        else:
            blocks.extend(render_html_blocks(child))
    return blocks


def normalize_markdown_blocks(blocks: Iterable[str]) -> str:
    cleaned = [normalize_whitespace(block) if not block.lstrip().startswith("<table") else block for block in blocks]
    cleaned = [block for block in cleaned if block]
    text = "\n\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + ("\n" if text else "")


def extract_page_title(soup: BeautifulSoup) -> Optional[str]:
    for selector in ["h1", "meta[property='og:title']", "title"]:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_whitespace((getattr(node, "attrs", None) or {}).get("content", ""))
        else:
            title = normalize_whitespace(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def markdown_looks_like_fulltext(markdown: str) -> tuple[bool, str]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    heading_lines = [line for line in lines if line.startswith("## ")]
    paragraph_lines = [line for line in lines if not line.startswith("#") and not line.startswith("- ") and not re.match(r"^\d+\.\s", line)]
    has_title = any(line.startswith("# ") for line in lines)
    if not has_title:
        return False, "missing_title"
    if len(paragraph_lines) < 5:
        return False, "insufficient_paragraphs"
    if len(heading_lines) < 1:
        return False, "missing_section_heading"
    substantive_headings = [
        line
        for line in heading_lines
        if heading_title(line) not in {"abstract", "references", *COLLATERAL_HEADING_TITLES}
    ]
    if not substantive_headings:
        return False, "looks_like_abstract_only"
    if len(markdown) < 1200:
        return False, "content_too_short"
    return True, "ok"


def html_to_markdown(html: str, publisher: str) -> tuple[str, dict[str, Any]]:
    soup = BeautifulSoup(html, choose_parser())
    title = extract_page_title(soup)
    container = select_best_container(soup, publisher)
    if container is None:
        raise FetchFailure(
            status="parse_error",
            error_kind="article_container_not_found",
            message="Could not identify the main article container in publisher HTML",
        )

    clean_container(container, publisher)
    blocks = render_html_blocks(container)
    markdown = normalize_markdown_blocks(blocks)
    if title and f"# {title}" not in markdown:
        markdown = f"# {title}\n\n{markdown}".strip() + "\n"

    looks_ok, reason = markdown_looks_like_fulltext(markdown)
    if not looks_ok:
        raise FetchFailure(
            status="blocked_paywall",
            error_kind=reason,
            message="HTML content does not look like a complete full-text article",
        )

    return markdown, {
        "title": title,
        "container_tag": container.name,
        "container_text_length": len(" ".join(container.stripped_strings)),
    }


def save_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def save_bytes(path: Path, content: bytes) -> None:
    path.write_bytes(content)


def decode_base64_blob(data: str) -> bytes:
    payload = data or ""
    if "," in payload and payload.lower().startswith("data:"):
        payload = payload.split(",", 1)[1]
    return base64.b64decode(payload)


def parse_optional_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalize_browser_cookie_for_playwright(
    cookie: dict[str, Any],
    fallback_url: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    name = normalize_whitespace(str(cookie.get("name") or ""))
    if not name:
        return None

    normalized: dict[str, Any] = {
        "name": name,
        "value": str(cookie.get("value") or ""),
    }

    domain = normalize_whitespace(str(cookie.get("domain") or ""))
    path = normalize_whitespace(str(cookie.get("path") or "")) or "/"
    if domain:
        normalized["domain"] = domain
        normalized["path"] = path
    elif fallback_url:
        normalized["url"] = fallback_url
    else:
        return None

    if cookie.get("secure") is not None:
        normalized["secure"] = bool(cookie.get("secure"))
    if cookie.get("httpOnly") is not None:
        normalized["httpOnly"] = bool(cookie.get("httpOnly"))

    expires_value = cookie.get("expiry")
    if expires_value is None:
        expires_value = cookie.get("expires")
    if expires_value is not None:
        try:
            normalized["expires"] = float(expires_value)
        except (TypeError, ValueError):
            pass

    same_site = normalize_whitespace(str(cookie.get("sameSite") or ""))
    if same_site:
        canonical_same_site = {
            "lax": "Lax",
            "strict": "Strict",
            "none": "None",
        }.get(same_site.lower())
        if canonical_same_site:
            normalized["sameSite"] = canonical_same_site

    return normalized


def normalize_browser_cookies_for_playwright(
    cookies: Optional[list[dict[str, Any]]],
    fallback_url: Optional[str] = None,
) -> list[dict[str, Any]]:
    normalized_cookies: list[dict[str, Any]] = []
    for cookie in cookies or []:
        if not isinstance(cookie, dict):
            continue
        normalized_cookie = normalize_browser_cookie_for_playwright(cookie, fallback_url=fallback_url)
        if normalized_cookie is not None:
            normalized_cookies.append(normalized_cookie)
    return normalized_cookies


def extract_flaresolverr_browser_context_seed(solution: dict[str, Any]) -> dict[str, Any]:
    final_url = solution.get("url") if isinstance(solution.get("url"), str) else None
    return {
        "browser_cookies": normalize_browser_cookies_for_playwright(
            solution.get("cookies") if isinstance(solution.get("cookies"), list) else None,
            fallback_url=final_url,
        ),
        "browser_user_agent": normalize_whitespace(str(solution.get("userAgent") or "")) or None,
        "browser_final_url": final_url,
    }


def redact_flaresolverr_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    solution = redacted_payload.get("solution")
    if not isinstance(solution, dict):
        return redacted_payload

    cookies = solution.get("cookies")
    if not isinstance(cookies, list):
        return redacted_payload

    redacted_cookies: list[dict[str, Any]] = []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        redacted_cookie = dict(cookie)
        if "value" in redacted_cookie:
            redacted_cookie["value"] = "[redacted]"
        redacted_cookies.append(redacted_cookie)
    solution["cookies"] = redacted_cookies
    return redacted_payload


def post_to_flaresolverr(
    session: requests.Session,
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        response = session.post(base_url.rstrip("/"), json=payload, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise FetchFailure(
            status="network_error",
            error_kind="flaresolverr_timeout",
            message=f"Timed out while calling FlareSolverr: {exc}",
        ) from exc
    except requests.RequestException as exc:
        raise FetchFailure(
            status="network_error",
            error_kind="flaresolverr_transport_error",
            message=f"Failed to call FlareSolverr: {exc}",
        ) from exc

    try:
        payload_json = response.json()
    except ValueError as exc:
        raise FetchFailure(
            status="parse_error",
            error_kind="invalid_flaresolverr_response",
            message=f"FlareSolverr returned non-JSON content: {exc}",
        ) from exc

    if not isinstance(payload_json, dict):
        raise FetchFailure(
            status="parse_error",
            error_kind="invalid_flaresolverr_response",
            message="FlareSolverr returned a non-object JSON payload",
        )

    return payload_json


def save_flaresolverr_failure_artifacts(
    slug: str,
    paths: OutputPaths,
    html: Optional[str] = None,
    screenshot_b64: Optional[str] = None,
    response_payload: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    artifact_paths: dict[str, str] = {}

    if html:
        html_path = paths.logs / f"{slug}.failure.html"
        save_text(html_path, html)
        artifact_paths["html_path"] = str(html_path.resolve())

    if screenshot_b64:
        screenshot_path = paths.logs / f"{slug}.failure.png"
        try:
            save_bytes(screenshot_path, decode_base64_blob(screenshot_b64))
            artifact_paths["screenshot_path"] = str(screenshot_path.resolve())
        except Exception:
            pass

    if response_payload is not None:
        response_path = paths.logs / f"{slug}.failure.response.json"
        save_text(
            response_path,
            json.dumps(redact_flaresolverr_response_payload(response_payload), ensure_ascii=False, indent=2) + "\n",
        )
        artifact_paths["response_path"] = str(response_path.resolve())

    return artifact_paths


def fetch_html_with_flaresolverr(
    candidate_urls: list[str],
    publisher: str,
    slug: str,
    paths: OutputPaths,
    flaresolverr_url: str,
    wait_seconds: int = DEFAULT_FLARESOLVERR_WAIT_SECONDS,
    max_timeout_ms: int = DEFAULT_FLARESOLVERR_MAX_TIMEOUT_MS,
) -> dict[str, Any]:
    if not candidate_urls:
        raise FetchFailure(
            status="parse_error",
            error_kind="empty_html_attempts",
            message="No publisher HTML candidates were attempted",
        )

    last_failure: Optional[FetchFailure] = None
    last_page_info: dict[str, Any] = {}
    latest_browser_context_seed: Optional[dict[str, Any]] = None
    flaresolverr_session = build_local_service_session()
    session_id = f"fetch-{slug[:32]}-{uuid.uuid4().hex[:8]}"

    try:
        try:
            create_response = post_to_flaresolverr(
                flaresolverr_session,
                flaresolverr_url,
                {"cmd": "sessions.create", "session": session_id},
                timeout_seconds=30,
            )
            if create_response.get("status") != "ok":
                raise FetchFailure(
                    status="network_error",
                    error_kind="flaresolverr_session_create_failed",
                    message=create_response.get("message") or "FlareSolverr refused to create a session",
                    details={"response": create_response},
                )

            for url in candidate_urls:
                request_payload = {
                    "cmd": "request.get",
                    "url": url,
                    "session": session_id,
                    "returnScreenshot": True,
                    "waitInSeconds": wait_seconds,
                    "maxTimeout": max_timeout_ms,
                }
                try:
                    request_response = post_to_flaresolverr(
                        flaresolverr_session,
                        flaresolverr_url,
                        request_payload,
                        timeout_seconds=(max_timeout_ms / 1000.0) + 45.0,
                    )
                except FetchFailure as exc:
                    last_failure = exc
                    last_page_info = {"source_url": url}
                    continue

                top_level_status = normalize_whitespace(str(request_response.get("status", ""))).lower()
                if top_level_status and top_level_status != "ok":
                    message = normalize_whitespace(str(request_response.get("message", "")))
                    error_kind = "flaresolverr_timeout" if "timeout" in message.lower() else "flaresolverr_request_failed"
                    last_failure = FetchFailure(
                        status="network_error",
                        error_kind=error_kind,
                        message=message or "FlareSolverr request.get failed",
                        details={"response": request_response},
                    )
                    last_page_info = {
                        "source_url": url,
                        "flaresolverr_status": request_response.get("status"),
                        "flaresolverr_message": request_response.get("message"),
                        **save_flaresolverr_failure_artifacts(
                            slug=slug,
                            paths=paths,
                            response_payload=request_response,
                        ),
                    }
                    continue

                solution = request_response.get("solution") or {}
                html = solution.get("response") or ""
                final_url = solution.get("url") or url
                response_status = parse_optional_int(solution.get("status"))
                response_headers = solution.get("headers") if isinstance(solution.get("headers"), dict) else {}
                title = extract_page_title(BeautifulSoup(html, choose_parser())) or ""
                summary = summarize_html(html)
                browser_context_seed = extract_flaresolverr_browser_context_seed(solution)
                if browser_context_seed.get("browser_cookies") or browser_context_seed.get("browser_user_agent"):
                    latest_browser_context_seed = browser_context_seed

                if looks_like_abstract_redirect(url, final_url):
                    detected_failure = FetchFailure(
                        status="blocked_paywall",
                        error_kind="redirected_to_abstract",
                        message="Publisher redirected the full-text URL to an abstract page",
                        transient=browser_context_seed,
                    )
                else:
                    detected_failure = detect_html_block(title=title, text=summary, response_status=response_status)
                    if detected_failure is not None:
                        detected_failure.transient = browser_context_seed

                if detected_failure is not None:
                    last_failure = detected_failure
                    last_page_info = {
                        "source_url": url,
                        "final_url": final_url,
                        "title": title,
                        "response_status": response_status,
                        "response_headers": response_headers,
                        "summary": summary,
                        **save_flaresolverr_failure_artifacts(
                            slug=slug,
                            paths=paths,
                            html=html,
                            screenshot_b64=solution.get("screenshot"),
                            response_payload=request_response,
                        ),
                    }
                    continue

                try:
                    markdown, extraction_info = html_to_markdown(html, publisher=publisher)
                except FetchFailure as exc:
                    exc.transient = browser_context_seed
                    last_failure = exc
                    last_page_info = {
                        "source_url": url,
                        "final_url": final_url,
                        "title": title,
                        "response_status": response_status,
                        "response_headers": response_headers,
                        "summary": summary,
                        **save_flaresolverr_failure_artifacts(
                            slug=slug,
                            paths=paths,
                            html=html,
                            screenshot_b64=solution.get("screenshot"),
                            response_payload=request_response,
                        ),
                    }
                    continue
                except Exception as exc:
                    last_failure = FetchFailure(
                        status="parse_error",
                        error_kind="html_parse_exception",
                        message=f"Unexpected error while converting publisher HTML: {exc}",
                        transient=browser_context_seed,
                    )
                    last_page_info = {
                        "source_url": url,
                        "final_url": final_url,
                        "title": title,
                        "response_status": response_status,
                        "response_headers": response_headers,
                        "summary": summary,
                        **save_flaresolverr_failure_artifacts(
                            slug=slug,
                            paths=paths,
                            html=html,
                            screenshot_b64=solution.get("screenshot"),
                            response_payload=request_response,
                        ),
                    }
                    continue

                raw_html_path = paths.raw_html / f"{slug}.html"
                markdown_path = paths.markdown / f"{slug}.md"
                save_text(raw_html_path, html)
                save_text(markdown_path, markdown)
                return {
                    "status": "success_html",
                    "selected_source": "publisher_html",
                    "source_url": url,
                    "final_url": final_url,
                    "raw_path": raw_html_path,
                    "markdown_path": markdown_path,
                    "title": title,
                    "response_status": response_status,
                    "response_headers": response_headers,
                    "summary": summary,
                    "extraction": extraction_info,
                    "html_fetcher": "flaresolverr",
                }
        except FetchFailure as exc:
            last_failure = exc
            if last_failure.transient is None and latest_browser_context_seed is not None:
                last_failure.transient = latest_browser_context_seed
            if not last_page_info:
                last_page_info = {"source_url": candidate_urls[0]}
    finally:
        try:
            post_to_flaresolverr(
                flaresolverr_session,
                flaresolverr_url,
                {"cmd": "sessions.destroy", "session": session_id},
                timeout_seconds=30,
            )
        except FetchFailure:
            pass
        flaresolverr_session.close()

    if last_failure is None:
        last_failure = FetchFailure(
            status="parse_error",
            error_kind="empty_html_attempts",
            message="No publisher HTML candidates were attempted",
        )
    elif last_failure.transient is None and latest_browser_context_seed is not None:
        last_failure.transient = latest_browser_context_seed

    log_payload = {
        **last_failure.as_dict(),
        **last_page_info,
        "html_fetcher": "flaresolverr",
        "flaresolverr_url": flaresolverr_url,
        "session_id": session_id,
    }
    save_text(paths.logs / f"{slug}.html-failure.json", json.dumps(log_payload, ensure_ascii=False, indent=2) + "\n")
    raise last_failure


def fetch_html_with_playwright(
    candidate_urls: list[str],
    publisher: str,
    slug: str,
    paths: OutputPaths,
    headless: bool,
    storage_state_path: Optional[Path] = None,
) -> dict[str, Any]:
    if not has_module("playwright"):
        raise FetchFailure(
            status="parse_error",
            error_kind="missing_playwright",
            message="playwright is not installed; cannot fetch publisher HTML",
        )

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    last_failure: Optional[FetchFailure] = None
    last_page_info: dict[str, Any] = {}
    sanitized_storage_state_path: Optional[Path] = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context_kwargs: dict[str, Any] = {
            "user_agent": USER_AGENT,
            "locale": "en-US",
            "viewport": {"width": 1440, "height": 1600},
        }
        if storage_state_path is not None:
            sanitized_storage_state_path = sanitize_storage_state(storage_state_path)
            context_kwargs["storage_state"] = str(sanitized_storage_state_path)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        try:
            for url in candidate_urls:
                response_status: Optional[int] = None
                response_headers: dict[str, str] = {}
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    response_status = response.status if response is not None else None
                    response_headers = response.all_headers() if response is not None else {}
                    try:
                        page.wait_for_load_state("networkidle", timeout=30000)
                    except PlaywrightTimeoutError:
                        pass
                except Exception as exc:
                    last_failure = FetchFailure(
                        status="network_error",
                        error_kind="playwright_navigation_error",
                        message=f"Failed to load publisher HTML: {exc}",
                    )
                    last_page_info = {
                        "source_url": url,
                        "title": None,
                        "response_status": response_status,
                        "response_headers": response_headers,
                    }
                    continue

                title = normalize_whitespace(page.title())
                html = page.content()
                summary = summarize_html(html)
                if looks_like_abstract_redirect(url, page.url):
                    detected_failure = FetchFailure(
                        status="blocked_paywall",
                        error_kind="redirected_to_abstract",
                        message="Publisher redirected the full-text URL to an abstract page",
                    )
                else:
                    detected_failure = detect_html_block(title=title, text=summary, response_status=response_status)
                if detected_failure is not None:
                    screenshot_path = paths.logs / f"{slug}.failure.png"
                    last_failure = detected_failure
                    last_page_info = {
                        "source_url": url,
                        "final_url": page.url,
                        "title": title,
                        "response_status": response_status,
                        "response_headers": response_headers,
                        "summary": summary,
                        "html_path": str((paths.logs / f"{slug}.failure.html").resolve()),
                        "screenshot_path": str(screenshot_path.resolve()),
                    }
                    save_text(paths.logs / f"{slug}.failure.html", html)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    continue

                try:
                    markdown, extraction_info = html_to_markdown(html, publisher=publisher)
                except FetchFailure as exc:
                    screenshot_path = paths.logs / f"{slug}.failure.png"
                    last_failure = exc
                    last_page_info = {
                        "source_url": url,
                        "final_url": page.url,
                        "title": title,
                        "response_status": response_status,
                        "response_headers": response_headers,
                        "summary": summary,
                        "html_path": str((paths.logs / f"{slug}.failure.html").resolve()),
                        "screenshot_path": str(screenshot_path.resolve()),
                    }
                    save_text(paths.logs / f"{slug}.failure.html", html)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    continue
                except Exception as exc:
                    screenshot_path = paths.logs / f"{slug}.failure.png"
                    last_failure = FetchFailure(
                        status="parse_error",
                        error_kind="html_parse_exception",
                        message=f"Unexpected error while converting publisher HTML: {exc}",
                    )
                    last_page_info = {
                        "source_url": url,
                        "final_url": page.url,
                        "title": title,
                        "response_status": response_status,
                        "response_headers": response_headers,
                        "summary": summary,
                        "html_path": str((paths.logs / f"{slug}.failure.html").resolve()),
                        "screenshot_path": str(screenshot_path.resolve()),
                    }
                    save_text(paths.logs / f"{slug}.failure.html", html)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    continue

                raw_html_path = paths.raw_html / f"{slug}.html"
                markdown_path = paths.markdown / f"{slug}.md"
                save_text(raw_html_path, html)
                save_text(markdown_path, markdown)
                return {
                    "status": "success_html",
                    "selected_source": "publisher_html",
                    "source_url": url,
                    "final_url": page.url,
                    "raw_path": raw_html_path,
                    "markdown_path": markdown_path,
                    "title": title,
                    "response_status": response_status,
                    "response_headers": response_headers,
                    "summary": summary,
                    "extraction": extraction_info,
                }
        finally:
            context.close()
            browser.close()
            if sanitized_storage_state_path is not None:
                sanitized_storage_state_path.unlink(missing_ok=True)

    if last_failure is None:
        last_failure = FetchFailure(
            status="parse_error",
            error_kind="empty_html_attempts",
            message="No publisher HTML candidates were attempted",
        )

    log_payload = {
        **last_failure.as_dict(),
        **last_page_info,
    }
    save_text(paths.logs / f"{slug}.html-failure.json", json.dumps(log_payload, ensure_ascii=False, indent=2) + "\n")
    raise last_failure


def fetch_pdf_and_convert(
    candidate_urls: list[str],
    slug: str,
    paths: OutputPaths,
    headless: bool,
    storage_state_path: Optional[Path] = None,
    browser_cookies: Optional[list[dict[str, Any]]] = None,
    browser_user_agent: Optional[str] = None,
) -> dict[str, Any]:
    if not has_module("playwright"):
        raise FetchFailure(
            status="parse_error",
            error_kind="missing_playwright",
            message="playwright is not installed; cannot use browser-context PDF fallback",
        )
    if not has_module("pymupdf4llm"):
        raise FetchFailure(
            status="parse_error",
            error_kind="missing_pymupdf4llm",
            message="pymupdf4llm is not installed; cannot use PDF fallback",
        )

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
    import pymupdf4llm

    last_failure: Optional[FetchFailure] = None
    last_page_info: dict[str, Any] = {}
    sanitized_storage_state_path: Optional[Path] = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context_kwargs: dict[str, Any] = {
            "user_agent": browser_user_agent or USER_AGENT,
            "locale": "en-US",
            "viewport": {"width": 1440, "height": 1600},
            "accept_downloads": True,
        }
        if storage_state_path is not None:
            sanitized_storage_state_path = sanitize_storage_state(storage_state_path)
            context_kwargs["storage_state"] = str(sanitized_storage_state_path)
        context = browser.new_context(**context_kwargs)

        try:
            if browser_cookies:
                try:
                    context.add_cookies(browser_cookies)
                except Exception as exc:
                    raise FetchFailure(
                        status="parse_error",
                        error_kind="invalid_browser_context_seed",
                        message=f"Failed to seed browser-context PDF fallback with cookies: {exc}",
                    ) from exc

            page = context.new_page()
            for url in candidate_urls:
                try:
                    with page.expect_download(timeout=30000) as download_info:
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        except PlaywrightError as exc:
                            if "Download is starting" not in str(exc):
                                raise
                    download = download_info.value
                except PlaywrightTimeoutError:
                    title = normalize_whitespace(page.title())
                    html = page.content()
                    summary = summarize_html(html)
                    detected_failure = detect_html_block(title=title, text=summary, response_status=None)
                    screenshot_path = paths.logs / f"{slug}.pdf-failure.png"
                    last_failure = detected_failure or FetchFailure(
                        status="blocked_paywall",
                        error_kind="pdf_download_not_triggered",
                        message="Browser context did not trigger a PDF download",
                    )
                    last_page_info = {
                        "source_url": url,
                        "final_url": page.url,
                        "title": title,
                        "summary": summary,
                        "html_path": str((paths.logs / f"{slug}.pdf-failure.html").resolve()),
                        "screenshot_path": str(screenshot_path.resolve()),
                    }
                    save_text(paths.logs / f"{slug}.pdf-failure.html", html)
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    continue
                except Exception as exc:
                    last_failure = FetchFailure(
                        status="network_error",
                        error_kind="pdf_download_failed",
                        message=f"Failed to trigger PDF fallback download: {exc}",
                    )
                    last_page_info = {
                        "source_url": url,
                        "final_url": page.url,
                        "title": normalize_whitespace(page.title()),
                    }
                    continue

                pdf_path = paths.raw_pdf / f"{slug}.pdf"
                markdown_path = paths.markdown / f"{slug}.md"
                download.save_as(str(pdf_path))
                content = pdf_path.read_bytes()
                if not content.startswith(b"%PDF-"):
                    pdf_path.unlink(missing_ok=True)
                    last_failure = FetchFailure(
                        status="blocked_paywall",
                        error_kind="downloaded_file_not_pdf",
                        message="Browser-context PDF fallback did not produce a PDF file",
                    )
                    last_page_info = {
                        "source_url": url,
                        "suggested_filename": download.suggested_filename,
                    }
                    continue

                markdown = pymupdf4llm.to_markdown(str(pdf_path))
                if not normalize_whitespace(markdown):
                    raise FetchFailure(
                        status="parse_error",
                        error_kind="empty_pdf_markdown",
                        message="PDF fallback produced empty Markdown",
                    )
                save_text(markdown_path, markdown)
                return {
                    "status": "success_pdf_fallback",
                    "selected_source": "pdf_fallback",
                    "source_url": url,
                    "raw_path": pdf_path,
                    "markdown_path": markdown_path,
                    "sha256": sha256_file(pdf_path),
                    "suggested_filename": download.suggested_filename,
                }
        finally:
            context.close()
            browser.close()
            if sanitized_storage_state_path is not None:
                sanitized_storage_state_path.unlink(missing_ok=True)

    if last_failure is None:
        last_failure = FetchFailure(
            status="parse_error",
            error_kind="empty_pdf_attempts",
            message="No PDF fallback candidates were attempted",
        )
    save_text(paths.logs / f"{slug}.pdf-failure.json", json.dumps({**last_failure.as_dict(), **last_page_info}, ensure_ascii=False, indent=2) + "\n")
    raise last_failure


def choose_tool_email() -> str:
    return os.environ.get("NCBI_EMAIL") or os.environ.get("EMAIL") or "unknown@example.com"


def process_article(
    item: ArticleInput,
    session: requests.Session,
    args: argparse.Namespace,
    paths: OutputPaths,
) -> dict[str, Any]:
    slug = safe_slug(item.doi)
    started_at = utc_now()
    crossref_message: Optional[dict[str, Any]] = None
    crossref_error: Optional[dict[str, Any]] = None
    attempts: list[dict[str, Any]] = []
    publisher = infer_publisher(item.doi, override=item.publisher_override)
    source_url: Optional[str] = None
    selected_source: Optional[str] = None
    raw_path: Optional[Path] = None
    markdown_path: Optional[Path] = None
    error_kind: Optional[str] = None
    status = "not_found"
    notes: list[str] = []

    try:
        pmcid = resolve_pmcid(session, item.doi, choose_tool_email())
        attempts.append({"source": "pmc_lookup", "pmcid": pmcid})
        polite_sleep(*PMC_DELAY_RANGE)
        if pmcid:
            article_xml = fetch_pmc_article_xml(session, pmcid)
            polite_sleep(*PMC_DELAY_RANGE)
            attempts.append({"source": "pmc_oai", "pmcid": pmcid, "available": bool(article_xml)})
            if article_xml:
                markdown = jats_xml_to_markdown(article_xml)
                if not normalize_whitespace(markdown):
                    raise FetchFailure(
                        status="parse_error",
                        error_kind="empty_pmc_markdown",
                        message="PMC XML converted to empty Markdown",
                    )
                raw_path = paths.raw_xml / f"{slug}.xml"
                markdown_path = paths.markdown / f"{slug}.md"
                save_text(raw_path, article_xml)
                save_text(markdown_path, markdown)
                status = "success_pmc"
                selected_source = "pmc_xml"
                source_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
                return {
                    "doi": item.doi,
                    "label": item.label,
                    "publisher": publisher,
                    "html_fetcher": args.html_fetcher,
                    "selected_source": selected_source,
                    "source_url": source_url,
                    "status": status,
                    "raw_path": normalize_path(raw_path),
                    "markdown_path": normalize_path(markdown_path),
                    "error_kind": None,
                    "attempted_at": started_at,
                    "pmcid": pmcid,
                    "attempts": attempts,
                }
    except requests.RequestException as exc:
        attempts.append(
            {
                "source": "pmc",
                "status": "network_error",
                "error_kind": "pmc_request_failed",
                "message": str(exc),
            }
        )
        notes.append("PMC lookup failed; continuing to Crossref and publisher HTML")
    except FetchFailure as exc:
        attempts.append({"source": "pmc", **exc.as_dict()})
        notes.append("PMC XML path failed; continuing to Crossref and publisher HTML")

    try:
        crossref_message = read_crossref_metadata(session, item.doi)
        polite_sleep(*CROSSREF_DELAY_RANGE)
        attempts.append(
            {
                "source": "crossref",
                "status": "ok" if crossref_message else "not_found",
                "publisher": crossref_message.get("publisher") if crossref_message else None,
                "url": crossref_message.get("URL") if crossref_message else None,
            }
        )
    except requests.RequestException as exc:
        crossref_error = {
            "source": "crossref",
            "status": "network_error",
            "error_kind": "crossref_request_failed",
            "message": str(exc),
        }
        attempts.append(crossref_error)

    publisher = infer_publisher(
        item.doi,
        override=item.publisher_override,
        crossref_publisher=crossref_message.get("publisher") if crossref_message else None,
        crossref_url=crossref_message.get("URL") if crossref_message else None,
    )

    if publisher not in {"science", "pnas"}:
        return {
            "doi": item.doi,
            "label": item.label,
            "publisher": publisher,
            "html_fetcher": args.html_fetcher,
            "selected_source": None,
            "source_url": None,
            "status": "not_found",
            "raw_path": None,
            "markdown_path": None,
            "error_kind": "unsupported_publisher",
            "attempted_at": started_at,
            "attempts": attempts,
        }

    html_candidates = build_html_candidates(publisher, item.doi)
    pdf_candidates = build_pdf_candidates(publisher, item.doi, extract_pdf_url_from_crossref(crossref_message))

    html_failure: Optional[FetchFailure] = None
    try:
        if args.html_fetcher == "flaresolverr":
            html_result = fetch_html_with_flaresolverr(
                candidate_urls=html_candidates,
                publisher=publisher,
                slug=slug,
                paths=paths,
                flaresolverr_url=args.flaresolverr_url,
                wait_seconds=args.flaresolverr_wait_seconds,
                max_timeout_ms=args.flaresolverr_max_timeout_ms,
            )
        else:
            html_result = fetch_html_with_playwright(
                candidate_urls=html_candidates,
                publisher=publisher,
                slug=slug,
                paths=paths,
                headless=args.headless,
                storage_state_path=args.playwright_storage_state,
            )
        attempts.append(
            {
                "source": "publisher_html",
                "fetcher": args.html_fetcher,
                "status": html_result["status"],
                "source_url": html_result["source_url"],
                "final_url": html_result.get("final_url"),
                "response_status": html_result.get("response_status"),
            }
        )
        polite_sleep(args.delay_min, args.delay_max)
        status = html_result["status"]
        selected_source = html_result["selected_source"]
        source_url = html_result["source_url"]
        raw_path = html_result["raw_path"]
        markdown_path = html_result["markdown_path"]
        return {
            "doi": item.doi,
            "label": item.label,
            "publisher": publisher,
            "html_fetcher": args.html_fetcher,
            "selected_source": selected_source,
            "source_url": source_url,
            "status": status,
            "raw_path": normalize_path(raw_path),
            "markdown_path": normalize_path(markdown_path),
            "error_kind": None,
            "attempted_at": started_at,
            "attempts": attempts,
        }
    except FetchFailure as exc:
        html_failure = exc
        error_kind = exc.error_kind
        status = exc.status
        attempts.append({"source": "publisher_html", "fetcher": args.html_fetcher, **exc.as_dict()})
        polite_sleep(args.delay_min, args.delay_max)

    if args.enable_pdf_fallback:
        pdf_browser_cookies: Optional[list[dict[str, Any]]] = None
        pdf_browser_user_agent: Optional[str] = None
        if html_failure is not None and html_failure.transient:
            pdf_browser_cookies = html_failure.transient.get("browser_cookies")
            pdf_browser_user_agent = html_failure.transient.get("browser_user_agent")

        try:
            pdf_result = fetch_pdf_and_convert(
                pdf_candidates,
                slug=slug,
                paths=paths,
                headless=args.headless,
                storage_state_path=args.playwright_storage_state,
                browser_cookies=pdf_browser_cookies,
                browser_user_agent=pdf_browser_user_agent,
            )
            attempts.append(
                {
                    "source": "pdf_fallback",
                    "fetcher": args.html_fetcher,
                    "seeded_browser_context": bool(pdf_browser_cookies),
                    "status": pdf_result["status"],
                    "source_url": pdf_result["source_url"],
                    "sha256": pdf_result["sha256"],
                }
            )
            polite_sleep(args.delay_min, args.delay_max)
            status = pdf_result["status"]
            selected_source = pdf_result["selected_source"]
            source_url = pdf_result["source_url"]
            raw_path = pdf_result["raw_path"]
            markdown_path = pdf_result["markdown_path"]
            return {
                "doi": item.doi,
                "label": item.label,
                "publisher": publisher,
                "html_fetcher": args.html_fetcher,
                "selected_source": selected_source,
                "source_url": source_url,
                "status": status,
                "raw_path": normalize_path(raw_path),
                "markdown_path": normalize_path(markdown_path),
                "error_kind": None,
                "attempted_at": started_at,
                "attempts": attempts,
            }
        except FetchFailure as exc:
            attempts.append(
                {
                    "source": "pdf_fallback",
                    "fetcher": args.html_fetcher,
                    "seeded_browser_context": bool(pdf_browser_cookies),
                    **exc.as_dict(),
                }
            )
            polite_sleep(args.delay_min, args.delay_max)
            status = exc.status
            error_kind = exc.error_kind

    return {
        "doi": item.doi,
        "label": item.label,
        "publisher": publisher,
        "html_fetcher": args.html_fetcher,
        "selected_source": selected_source,
        "source_url": source_url or (html_candidates[0] if html_candidates else None),
        "status": status,
        "raw_path": normalize_path(raw_path),
        "markdown_path": normalize_path(markdown_path),
        "error_kind": error_kind or (html_failure.error_kind if html_failure else None),
        "attempted_at": started_at,
        "attempts": attempts,
        "notes": notes,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Science/PNAS full text to Markdown")
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 CSV with a required 'doi' column")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory root")
    parser.add_argument("--format", default="markdown", choices=["markdown"], help="Output format")
    parser.add_argument("--resume", action="store_true", help="Skip DOIs that already succeeded in manifest.jsonl")
    parser.add_argument("--enable-pdf-fallback", action="store_true", help="Allow explicit PDF fallback after PMC/HTML failure")
    parser.add_argument(
        "--html-fetcher",
        default="playwright",
        choices=["playwright", "flaresolverr"],
        help="Publisher HTML backend; default keeps the current Playwright workflow",
    )
    parser.add_argument(
        "--flaresolverr-url",
        default=DEFAULT_FLARESOLVERR_URL,
        help="FlareSolverr v1 endpoint used when --html-fetcher flaresolverr is selected",
    )
    parser.add_argument(
        "--flaresolverr-wait-seconds",
        type=int,
        default=DEFAULT_FLARESOLVERR_WAIT_SECONDS,
        help="Seconds FlareSolverr waits after navigation before returning HTML",
    )
    parser.add_argument(
        "--flaresolverr-max-timeout-ms",
        type=int,
        default=DEFAULT_FLARESOLVERR_MAX_TIMEOUT_MS,
        help="FlareSolverr request timeout in milliseconds",
    )
    parser.add_argument(
        "--playwright-storage-state",
        type=Path,
        default=None,
        help="Optional Playwright storage state JSON to reuse browser cookies/session",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Playwright in headless mode",
    )
    parser.add_argument("--max-items", type=int, default=None, help="Limit the number of DOIs processed")
    parser.add_argument("--delay-min", type=float, default=15.0, help="Minimum delay between publisher requests")
    parser.add_argument("--delay-max", type=float, default=30.0, help="Maximum delay between publisher requests")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.delay_min < 0 or args.delay_max < 0:
        parser.error("--delay-min and --delay-max must be non-negative")
    if args.delay_max < args.delay_min:
        parser.error("--delay-max must be greater than or equal to --delay-min")
    if args.flaresolverr_wait_seconds < 0:
        parser.error("--flaresolverr-wait-seconds must be non-negative")
    if args.flaresolverr_max_timeout_ms <= 0:
        parser.error("--flaresolverr-max-timeout-ms must be greater than zero")
    if args.playwright_storage_state is not None and not args.playwright_storage_state.exists():
        parser.error("--playwright-storage-state must point to an existing JSON file")

    items = load_inputs(args.input)
    if args.max_items is not None:
        items = items[: args.max_items]

    paths = ensure_output_dirs(args.output_dir)
    completed_successes = load_completed_successes(paths.manifest) if args.resume else {}
    session = build_session()

    summary = {
        "total": len(items),
        "processed": 0,
        "skipped": 0,
        "success_pmc": 0,
        "success_html": 0,
        "success_pdf_fallback": 0,
        "blocked_paywall": 0,
        "blocked_captcha": 0,
        "not_found": 0,
        "parse_error": 0,
        "network_error": 0,
    }

    for item in items:
        if args.resume and item.doi in completed_successes:
            summary["skipped"] += 1
            print(f"[skip] {item.doi} already succeeded in {paths.manifest}")
            continue

        print(f"[start] {item.doi}")
        result = process_article(item=item, session=session, args=args, paths=paths)
        append_jsonl(paths.manifest, result)

        summary["processed"] += 1
        summary[result["status"]] = summary.get(result["status"], 0) + 1

        if result["status"] in SUCCESS_STATUSES:
            print(f"[ok] {item.doi} -> {result['status']} ({result['selected_source']})")
        else:
            print(f"[fail] {item.doi} -> {result['status']} ({result.get('error_kind')})")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
