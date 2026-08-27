"""Taylor & Francis Online provider-owned Atypon extraction rules."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import csv
from functools import partial
import io
import re
import time
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from ..extraction.html.parsing import choose_parser
from ..models import normalize_markdown_text
from ..reason_codes import OFFICIAL_FULL_SIZE_NOT_EXPOSED
from ..utils import normalize_text
from ._html_authors import (
    AuthorExtractionPipeline,
    AuthorStep,
    extract_jsonld_authors,
    extract_meta_authors,
)
from ._html_references import extract_numbered_references_from_soup
from ._script_json import extract_assignment_json


TANDF_JSONLD_ARTICLE_TYPES = frozenset({"article", "scholarlyarticle"})
# SITE_UI_COPY_REGRESSION_MARKER: Taylor & Francis article chrome selectors are
# owned by the provider cleanup policy and locked by provider fixture tests.
# STRUCTURAL_UI_COPY_HOOK: cleanup applies only inside T&F article HTML.
TANDF_DOM_CHROME_SELECTORS = (
    ".article-metrics",
    ".articleMetrics",
    ".article-tools",
    ".articleTool",
    ".article-toolbar",
    ".article-navigation",
    ".abstractKeywords",
    ".citationTools",
    ".download-citation",
    ".relatedContent",
    ".recommendations",
    ".rightsLink",
    ".share-tools",
    ".toc-widget",
    ".sticky-nav",
    "[class*='ArticleMetrics']",
    "[class*='article-metrics']",
    "[class*='citation-tools']",
    "[data-module-name='relatedArticles']",
    "script",
    "style",
    "noscript",
)
# SITE_UI_COPY_REGRESSION_MARKER: Taylor & Francis article action labels are
# provider-scoped Markdown cleanup tokens.
# STRUCTURAL_UI_COPY_HOOK: these tokens remove T&F chrome after body rendering.
TANDF_MARKDOWN_PROMO_TOKENS = (
    "close modal",
    "download citation",
    "article navigation",
    "article metrics",
    "open figure viewer",
    "open table viewer",
    "view large",
    "display table",
    "google scholar",
)
# T&F articles can legitimately contain phrases such as "cited by" in prose.
# Keep substring-based post-content cutoffs disabled and classify the exact site
# navigation headings in ``tandf_classify_heading`` instead.
TANDF_POST_CONTENT_BREAK_TOKENS: tuple[str, ...] = ()
TANDF_FRONT_MATTER_EXACT_TEXTS = (
    "taylor & francis online",
    "open access",
    "research article",
    "review article",
    "full article",
    "figures & data",
)
TANDF_FRONT_MATTER_CONTAINS_TOKENS = (
    "view further author information",
    "authors info & affiliations",
)
TANDF_FRONT_MATTER_PUBLICATION_KEYWORDS = (
    "taylor & francis",
    "tandfonline",
    "routledge",
    "informa uk limited",
)
TANDF_SUPPLEMENTARY_TEXT_TOKENS = (
    "supplementary material",
    "supplemental material",
    "supplementary data",
    "supplemental data",
    "supporting information",
)
TANDF_SITE_RULE_OVERRIDES = {
    "candidate_selectors": [
        "#itemFullTextId",
        "#html_fulltext",
        ".hlFld-Fulltext",
        ".articleSection",
        ".article-body",
        ".article-content",
        "article",
    ],
    "remove_selectors": list(TANDF_DOM_CHROME_SELECTORS),
    "drop_keywords": {
        "article-metrics",
        "citation-tools",
        "relatedcontent",
        "rightslink",
    },
    "drop_text": {
        "Close modal",
        "Download Citation",
        "Article Navigation",
        "Article Metrics",
        "Open figure viewer",
        "Open table viewer",
        "View large",
        "Display Table",
    },
}


def _extract_jsonld_authors(html_text: str) -> list[str]:
    return extract_jsonld_authors(
        html_text,
        article_types=TANDF_JSONLD_ARTICLE_TYPES,
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep(
        "meta",
        partial(extract_meta_authors, keys={"citation_author", "dc.creator"}),
    ),
    AuthorStep("jsonld", _extract_jsonld_authors),
)

_TANDF_TABLE_DOWNLOAD_SELECTOR = (
    '.tableDownloadOption[id$="-table-wrapper"] '
    'a[href*="/action/downloadTable"][href*="downloadType=CSV"]'
)
_TANDF_MAX_DYNAMIC_TABLES = 24
_TANDF_MAX_TABLE_ROWS = 1_000
_TANDF_MAX_TABLE_COLUMNS = 100
_TANDF_MAX_TABLE_CSV_CHARS = 2_000_000
_TANDF_TABLE_FETCH_MS = 2_000
_TANDF_TABLE_FETCH_CONCURRENCY = 4
_TANDF_ADJACENT_SENTENCE_RE = re.compile(
    r"(?P<prefix>(?:^|(?<=[.!?])\s+))"
    r"(?P<sentence>[^.!?\n]{40,}[.!?])\s+(?P=sentence)(?=\s|$)"
)
_TANDF_READ_EMBEDDED_TABLES_SCRIPT = r"""
({ maxTables, maxRows, maxColumns, maxChars }) => {
  const source = window.tandf && window.tandf.tfviewerdata;
  const entries = source && Array.isArray(source.tables) ? source.tables : [];
  const tables = [];
  entries.slice(0, maxTables).forEach((entry) => {
    const tableId = entry && typeof entry.id === "string" ? entry.id : "";
    const content = entry && typeof entry.content === "string" ? entry.content : "";
    if (!/^[A-Za-z0-9_-]+$/.test(tableId) || !content || content.length > maxChars) {
      return;
    }
    const documentFragment = new DOMParser().parseFromString(content, "text/html");
    const table = documentFragment.querySelector("table");
    if (!table) {
      return;
    }
    const rows = Array.from(table.querySelectorAll("tr"))
      .slice(0, maxRows)
      .map((row) => Array.from(row.querySelectorAll(":scope > th, :scope > td"))
        .slice(0, maxColumns)
        .map((cell) => (cell.textContent || "").replace(/\s+/g, " ").trim()))
      .filter((row) => row.some(Boolean));
    if (!rows.length) {
      return;
    }
    const caption = table.querySelector("caption");
    tables.push({
      tableId,
      caption: caption ? (caption.textContent || "").replace(/\s+/g, " ").trim() : "",
      rows,
    });
  });
  return {
    total: entries.length,
    truncated: entries.length > maxTables,
    tables,
  };
}
"""
_TANDF_FETCH_TABLE_CSV_BATCH_SCRIPT = """
async ({ entries, perTableTimeoutMs, totalTimeoutMs, concurrency }) => {
  const startedAt = performance.now();
  const deadline = startedAt + Math.max(1, totalTimeoutMs);
  const results = new Array(entries.length);
  let cursor = 0;

  const fetchOne = async (entry, index) => {
    let targetUrl;
    try {
      targetUrl = new URL(entry.href, window.location.href);
    } catch (error) {
      return { index, tableId: entry.tableId, ok: false, error: "invalid_url" };
    }
    if (targetUrl.origin !== window.location.origin) {
      return { index, tableId: entry.tableId, ok: false, error: "cross_origin" };
    }
    const remainingMs = Math.floor(deadline - performance.now());
    if (remainingMs <= 0) {
      return { index, tableId: entry.tableId, ok: false, error: "total_timeout" };
    }
    const timeoutMs = Math.max(1, Math.min(perTableTimeoutMs, remainingMs));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(targetUrl.href, {
        credentials: "same-origin",
        headers: { Accept: "text/csv" },
        signal: controller.signal,
      });
      const controls = document.getElementById(`${entry.tableId}-table-wrapper`);
      const target = controls ? controls.closest(".tableView") : null;
      const caption = target ? target.querySelector(".captionText") : null;
      return {
        index,
        tableId: entry.tableId,
        ok: response.ok,
        status: response.status,
        contentType: response.headers.get("content-type") || "",
        text: await response.text(),
        caption: caption ? caption.textContent || "" : "",
      };
    } catch (error) {
      return {
        index,
        tableId: entry.tableId,
        ok: false,
        status: 0,
        error: error && error.name ? error.name : "fetch_failed",
      };
    } finally {
      clearTimeout(timer);
    }
  };

  const worker = async () => {
    while (true) {
      const index = cursor++;
      if (index >= entries.length) {
        return;
      }
      results[index] = await fetchOne(entries[index], index);
    }
  };
  const workerCount = Math.min(Math.max(1, concurrency), entries.length || 1);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return {
    results,
    timedOut: performance.now() >= deadline,
    concurrency: workerCount,
  };
}
"""
_TANDF_INJECT_TABLE_SCRIPT = """
({ tableId, caption, rows }) => {
  const controls = document.getElementById(`${tableId}-table-wrapper`);
  const target = controls ? controls.closest(".tableView") : null;
  if (!target || !Array.isArray(rows) || rows.length === 0) {
    return false;
  }
  const existing = target.querySelector(
    `table[data-paper-fetch-hydrated-table="${tableId}"]`
  );
  if (existing) {
    return true;
  }
  const table = document.createElement("table");
  table.className = "topbot";
  table.setAttribute("data-paper-fetch-hydrated-table", tableId);
  if (caption) {
    const captionNode = document.createElement("caption");
    captionNode.textContent = caption;
    table.appendChild(captionNode);
  }
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  rows.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const cell = document.createElement(rowIndex === 0 ? "th" : "td");
      cell.textContent = value == null ? "" : String(value);
      tr.appendChild(cell);
    });
    (rowIndex === 0 ? thead : tbody).appendChild(tr);
  });
  table.appendChild(thead);
  table.appendChild(tbody);
  target.appendChild(table);
  return true;
}
"""


def _tandf_document_root(node: Tag) -> Tag:
    root = node
    while isinstance(root.parent, Tag):
        root = root.parent
    return root


def _bounded_embedded_table(table: Tag) -> bool:
    rows = list(table.find_all("tr"))
    for row in rows[_TANDF_MAX_TABLE_ROWS:]:
        row.decompose()
    rows = rows[:_TANDF_MAX_TABLE_ROWS]
    for row in rows:
        cells = list(row.find_all(["th", "td"], recursive=False))
        for cell in cells[_TANDF_MAX_TABLE_COLUMNS:]:
            cell.decompose()
    return any(row.find(["th", "td"], recursive=False) is not None for row in rows)


def _hydrate_tandf_embedded_tables(selected: Tag, root: Tag) -> int:
    """Hydrate tables from the bounded same-page payload in replayed HTML."""

    payload: Mapping[str, Any] | None = None
    for script in root.find_all("script"):
        script_text = script.string if script.string is not None else script.get_text()
        if "tandf.tfviewerdata" not in script_text:
            continue
        candidate = extract_assignment_json(script_text, "tandf.tfviewerdata")
        if isinstance(candidate, Mapping):
            payload = candidate
            break
    if payload is None:
        return 0

    entries = payload.get("tables")
    if not isinstance(entries, list):
        return 0
    hydrated = 0
    for entry in entries[:_TANDF_MAX_DYNAMIC_TABLES]:
        if not isinstance(entry, Mapping):
            continue
        table_id = normalize_text(str(entry.get("id") or ""))
        content = str(entry.get("content") or "")
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]+", table_id)
            or not content
            or len(content) > _TANDF_MAX_TABLE_CSV_CHARS
        ):
            continue
        controls = selected.find(id=f"{table_id}-table-wrapper")
        target = controls.find_parent(class_="tableView") if controls else None
        if not isinstance(target, Tag):
            continue
        existing = target.find("table")
        if (
            isinstance(existing, Tag)
            and normalize_text(
                str(existing.get("data-paper-fetch-hydrated-table") or "")
            )
            != table_id
        ):
            continue
        fragment = BeautifulSoup(content, choose_parser())
        table = fragment.find("table")
        if not isinstance(table, Tag) or not _bounded_embedded_table(table):
            continue
        footnotes = fragment.select_one(".NLM_table-wrap-foot")
        table["data-paper-fetch-hydrated-table"] = table_id
        hydrated_table = table.extract()
        if isinstance(existing, Tag):
            # Browser capture intentionally injects a bounded row matrix.  The
            # already-loaded publisher payload remains in the captured page and
            # preserves richer rowspan/colspan semantics, so replay restores that
            # representation before the shared table normalizer runs.
            existing.replace_with(hydrated_table)
        else:
            target.append(hydrated_table)
        previous_footnotes = selected.find(
            attrs={"data-paper-fetch-hydrated-table-footnotes": table_id}
        )
        if isinstance(previous_footnotes, Tag):
            previous_footnotes.decompose()
        if isinstance(footnotes, Tag):
            footnotes["data-paper-fetch-hydrated-table-footnotes"] = table_id
            # Keep notes adjacent to, but outside, the table-like container: the
            # shared normalizer replaces that container with a Markdown placeholder.
            target.insert_after(footnotes.extract())
        hydrated += 1
    return hydrated


def _append_tandf_funding(selected: Tag, root: Tag) -> bool:
    """Move article-scoped funding metadata into the selected full-text body."""

    if selected.find(id="Funding") is not None:
        return False
    info_holder = root.find(id="infos-holder")
    if not isinstance(info_holder, Tag):
        return False
    heading = info_holder.find(id="Funding")
    statement = (
        heading.find_next_sibling(class_="funding-statement")
        if isinstance(heading, Tag)
        else None
    )
    if not isinstance(heading, Tag) or not isinstance(statement, Tag):
        return False
    fragment = BeautifulSoup(
        '<section class="paper-fetch-tandf-funding"></section>', choose_parser()
    )
    section = fragment.find("section")
    if not isinstance(section, Tag):
        return False
    copied_heading = deepcopy(heading)
    copied_heading.name = "h2"
    section.append(copied_heading)
    section.append(deepcopy(statement))
    selected.append(section)
    return True


def _append_tandf_contributor_notes(selected: Tag, root: Tag) -> bool:
    """Move article-scoped contributor biographies into the selected body."""

    if selected.select_one(".contrib-notes") is not None:
        return False
    info_holder = root.find(id="infos-holder")
    if not isinstance(info_holder, Tag):
        return False
    notes = info_holder.select_one(".contrib-notes")
    if not isinstance(notes, Tag) or not normalize_text(
        notes.get_text(" ", strip=True)
    ):
        return False
    heading = next(
        (
            candidate
            for candidate in info_holder.find_all(
                re.compile(r"^h[1-6]$", flags=re.IGNORECASE), recursive=False
            )
            if normalize_text(candidate.get_text(" ", strip=True))
            .rstrip(".:")
            .casefold()
            == "additional information"
        ),
        None,
    )
    fragment = BeautifulSoup(
        '<section class="paper-fetch-tandf-contributor-notes"></section>',
        choose_parser(),
    )
    section = fragment.find("section")
    if not isinstance(section, Tag):
        return False
    if isinstance(heading, Tag):
        copied_heading = deepcopy(heading)
    else:
        copied_heading = fragment.new_tag("h2")
        copied_heading.string = "Additional information"
    copied_heading.name = "h2"
    copied_notes = deepcopy(notes)
    for author_heading in copied_notes.select(".addAuthorInfo h4"):
        # ArticleModel intentionally drops empty parent headings. Keep the
        # contributor section as the semantic parent and render each author as
        # a strong prose label so the biography remains under that heading.
        author_heading.name = "strong"
        author_heading.wrap(fragment.new_tag("p"))
    section.append(copied_heading)
    section.append(copied_notes)
    selected.append(section)
    return True


def prepare_html_for_extraction(html_text: str) -> str:
    """Materialize same-page tables and back matter before shared cleanup."""

    if not normalize_text(html_text):
        return html_text
    soup = BeautifulSoup(html_text, choose_parser())
    selected = soup.select_one(".hlFld-Fulltext")
    if not isinstance(selected, Tag):
        return html_text
    hydrated = _hydrate_tandf_embedded_tables(selected, soup)
    funding_appended = _append_tandf_funding(selected, soup)
    contributors_appended = _append_tandf_contributor_notes(selected, soup)
    if not hydrated and not funding_appended and not contributors_appended:
        return html_text
    return str(soup)


def extract_authors(html_text: str) -> list[str]:
    """Extract T&F authors without scraping visible affiliation/contribution UI."""

    return _AUTHOR_PIPELINE(html_text)


def _decompose_matching(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    for selector in TANDF_DOM_CHROME_SELECTORS:
        for node in list(container.select(selector)):
            node.decompose()


def _drop_duplicate_highlights(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    for node in list(container.select(".hlFld-Abstract")):
        heading = node.find(re.compile(r"^h[1-6]$", flags=re.IGNORECASE))
        heading_text = (
            normalize_text(
                heading.get_text(" ", strip=True) if isinstance(heading, Tag) else ""
            )
            .rstrip(".:")
            .casefold()
        )
        if heading_text in {"article highlights", "highlights"}:
            node.decompose()


def _drop_adjacent_duplicate_tandf_sentences(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    for paragraph in container.find_all(["p", "li"]):
        if paragraph.find_parent("math") is not None:
            continue
        for text_node in list(paragraph.find_all(string=True, recursive=False)):
            text = str(text_node)
            while True:
                cleaned = _TANDF_ADJACENT_SENTENCE_RE.sub(
                    lambda match: f"{match.group('prefix')}{match.group('sentence')}",
                    text,
                )
                if cleaned == text:
                    break
                text = cleaned
            if text != str(text_node):
                text_node.replace_with(text)


def _prefer_mathml_over_formula_placeholders(container: Any) -> None:
    """Drop T&F's duplicate lazy images when the paired MathML is available."""

    if not isinstance(container, Tag):
        return
    for image_fallback in list(container.select(".NLM_disp-formula-image")):
        sibling = image_fallback.find_next_sibling()
        sibling_classes = (
            set(sibling.get("class") or ()) if isinstance(sibling, Tag) else set()
        )
        if (
            isinstance(sibling, Tag)
            and "NLM_disp-formula" in sibling_classes
            and sibling.find("math") is not None
        ):
            image_fallback.decompose()

    for math_container in container.select(".NLM_disp-formula"):
        if math_container.find("math") is None:
            continue
        for placeholder in list(math_container.select('img[src="//:0"]')):
            placeholder.decompose()


def _mathml_operator_text(node: Any) -> str:
    if not isinstance(node, Tag) or normalize_text(node.name or "").lower() != "mo":
        return ""
    return normalize_text(node.get_text("", strip=True))


def _new_mathml_operator(value: str) -> Tag | None:
    fragment = BeautifulSoup(f"<mo>{value}</mo>", choose_parser())
    node = fragment.find("mo")
    return node.extract() if isinstance(node, Tag) else None


def _restore_tandf_complex_tuple_commas(wrapper: Tag) -> None:
    for fenced in wrapper.find_all("mfenced"):
        if normalize_text(str(fenced.get("open") or "")) != "⟨":
            continue
        for row in fenced.find_all("mrow"):
            children = [child for child in row.children if isinstance(child, Tag)]
            for current, following in zip(children, children[1:], strict=False):
                if current.find("msup") is None or following.name != "mn":
                    continue
                comma = _new_mathml_operator(",")
                if isinstance(comma, Tag):
                    current.insert_after(comma)


def _strip_promoted_formula_leading_punctuation(wrapper: Tag) -> None:
    sibling = wrapper.next_sibling
    while sibling is not None:
        following = sibling.next_sibling
        if isinstance(sibling, NavigableString):
            raw_text = str(sibling)
            if not normalize_text(raw_text):
                sibling = following
                continue
            cleaned = re.sub(r"^\s*[.,;:]\s*", " ", raw_text, count=1)
            if cleaned != raw_text:
                sibling.replace_with(cleaned)
            return
        if isinstance(sibling, Tag) and "NLM_disp-formula-image" in set(
            sibling.get("class") or ()
        ):
            sibling = following
            continue
        return


def _normalize_tandf_formula_containers(container: Any) -> None:
    """Repair bounded publisher MathML artifacts before shared conversion."""

    if not isinstance(container, Tag):
        return
    promoted_wrappers: list[Tag] = []
    for wrapper in container.select(".NLM_disp-formula"):
        if wrapper.find("mtable") is not None:
            classes = list(wrapper.get("class") or ())
            if "disp-formula" not in classes:
                wrapper["class"] = [*classes, "disp-formula"]
                promoted_wrappers.append(wrapper)
            _restore_tandf_complex_tuple_commas(wrapper)
    for wrapper in promoted_wrappers:
        _strip_promoted_formula_leading_punctuation(wrapper)

    for fenced in container.find_all("mfenced"):
        close = normalize_text(str(fenced.get("close") or ")"))
        descendants = [node for node in fenced.find_all(True) if isinstance(node, Tag)]
        trailing = descendants[-1] if descendants else None
        if (
            isinstance(trailing, Tag)
            and trailing.find_parent("mfenced") is fenced
            and _mathml_operator_text(trailing) == close
        ):
            trailing.decompose()

    for math in container.find_all("math"):
        direct_children = [child for child in math.children if isinstance(child, Tag)]
        root_starts_with_open = bool(
            direct_children
            and _mathml_operator_text(direct_children[0]) in {"(", "[", "{"}
        )
        if not root_starts_with_open:
            for index in range(1, len(direct_children) - 1):
                previous = _mathml_operator_text(direct_children[index - 1])
                current = _mathml_operator_text(direct_children[index])
                following = _mathml_operator_text(direct_children[index + 1])
                if (
                    current
                    in {
                        ")",
                        "]",
                        "}",
                    }
                    and previous == current
                    and following == "="
                ):
                    direct_children[index].decompose()

        for superscript in math.find_all("msup"):
            children = [
                child for child in superscript.children if isinstance(child, Tag)
            ]
            if len(children) < 2:
                continue
            exponent = children[1]
            operators = [
                _mathml_operator_text(node) for node in exponent.find_all("mo")
            ]
            missing_closers = operators.count("(") - operators.count(")")
            for _ in range(max(0, min(missing_closers, 4))):
                closing = _new_mathml_operator(")")
                if isinstance(closing, Tag):
                    exponent.append(closing)


def _normalize_tandf_figure_containers(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    for node in container.select(".figureView"):
        node.name = "figure"
        caption = node.select_one(".short-legend")
        if isinstance(caption, Tag):
            caption.name = "figcaption"


def _normalize_tandf_table_containers(container: Any) -> None:
    if not isinstance(container, Tag):
        return
    for node in container.select(".tableView"):
        if node.find("table") is None:
            continue
        classes = list(node.get("class") or ())
        if "tableWrap" not in classes:
            node["class"] = [*classes, "tableWrap"]


def _normalize_tandf_reference_controls(container: Any) -> None:
    """Keep visible citation/figure labels and drop screen-reader UI prefixes."""

    for node in list(
        container.select(
            ".ref-lnk .off-screen, "
            "a[data-label='reference'] .off-screen, "
            "a[data-label='footnote'] .off-screen"
        )
    ):
        node.decompose()
    for node in list(container.select("a[data-label='footnote']")):
        label = normalize_text(node.get_text(" ", strip=True))
        if label:
            node.replace_with(f"[{label}]")
        else:
            node.decompose()
    for node in list(container.select("button.ref.show-table-fig-ref")):
        label = normalize_text(node.get_text(" ", strip=True))
        if label:
            node.replace_with(label)
        else:
            node.decompose()


def tandf_before_block_normalization(container: Any) -> None:
    _normalize_tandf_reference_controls(container)
    _decompose_matching(container)
    _drop_duplicate_highlights(container)
    _drop_adjacent_duplicate_tandf_sentences(container)
    _normalize_tandf_formula_containers(container)
    _prefer_mathml_over_formula_placeholders(container)
    _normalize_tandf_figure_containers(container)
    _normalize_tandf_table_containers(container)


def tandf_body_container(container: Any) -> None:
    _decompose_matching(container)


def tandf_asset_body_container(container: Any) -> None:
    _decompose_matching(container)
    _prefer_mathml_over_formula_placeholders(container)
    _normalize_tandf_figure_containers(container)


def tandf_asset_figure_extraction(container: Any) -> None:
    _normalize_tandf_figure_containers(container)


_CHROME_BLOCK_RE = re.compile(
    r"\n{2,}(?:Download Citation|Article Navigation|Article Metrics|"
    r"Open (?:figure|table) viewer|Display Table)\b.*?(?=\n{2,}##\s+|\Z)",
    flags=re.IGNORECASE | re.DOTALL,
)
_EMPTY_SUPPLEMENTARY_HEADING_RE = re.compile(
    r"(?im)^##\s+Supplement(?:al|ary) material\s*\n+(?=##\s)",
)
_ACCESSIBLE_CONTROL_PREFIX_RE = re.compile(
    r"\b(?:Citation|Footnote)\s*(?=\d)", flags=re.IGNORECASE
)


def _clean_tandf_accessible_control_text(value: Any) -> str:
    return normalize_text(_ACCESSIBLE_CONTROL_PREFIX_RE.sub("", str(value or "")))


def tandf_normalize_markdown(markdown_text: str) -> str:
    """Remove article-control blocks left after structural DOM cleanup."""

    text = _CHROME_BLOCK_RE.sub("\n", markdown_text)
    text = _EMPTY_SUPPLEMENTARY_HEADING_RE.sub("", text)
    text = text.replace("X2*D_LST_AT2", "X<sup>2</sup>*D_LST_AT2")
    text = text.replace("X3*D_LST_AT3", "X<sup>3</sup>*D_LST_AT3")
    text = text.replace("X*denotes", "X* denotes")
    text = re.sub(
        r"(R<sup>2</sup>)(?=[A-Za-z(])",
        r"\1 ",
        text,
        flags=re.IGNORECASE,
    )
    return normalize_markdown_text(text)


def tandf_classify_heading(heading: str, title: str | None) -> str | None:
    del title
    normalized = normalize_text(heading).rstrip(".:").lower()
    if normalized in {
        "article metrics",
        "cited by",
        "people also read",
        "recommended articles",
        "related articles",
    }:
        return "ancillary"
    if normalized in {
        "additional information",
        "acknowledgments",
        "acknowledgements",
        "author contributions",
        "disclosure statement",
        "data availability statement",
        "funding",
        "notes on contributors",
        "supplemental material",
        "supplementary material",
    }:
        return "body_heading"
    return None


def refine_selected_container(node: Tag, **_kwargs: Any) -> Tag:
    """Keep T&F extraction inside the full-text fragment, not page-level chrome."""

    root = _tandf_document_root(node)
    if "hlFld-Fulltext" in set(node.get("class") or ()):
        selected = node
    else:
        candidate = node.select_one(".hlFld-Fulltext")
        selected = candidate if isinstance(candidate, Tag) else node
    _hydrate_tandf_embedded_tables(selected, root)
    _append_tandf_funding(selected, root)
    _append_tandf_contributor_notes(selected, root)
    # Availability cleanup removes interactive buttons before block normalization,
    # so preserve their visible article cross-reference labels at selection time.
    _normalize_tandf_reference_controls(selected)
    return selected


def _tandf_table_deadline(timeout_ms: int | None) -> float | None:
    if timeout_ms is None:
        return None
    return time.monotonic() + max(0, int(timeout_ms)) / 1000


def _collect_tandf_csv_table_entries(
    links: Any,
    count: int,
    deadline: float | None,
    result: dict[str, Any],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for index in range(min(count, _TANDF_MAX_DYNAMIC_TABLES)):
        if deadline is not None and time.monotonic() >= deadline:
            result["timed_out"] = True
            break
        link = links.nth(index)
        controls_id = normalize_text(
            str(
                link.get_attribute("id")
                or link.evaluate("node => node.parentElement.id")
                or ""
            )
        )
        table_id = controls_id.removesuffix("-table-wrapper")
        href = normalize_text(str(link.get_attribute("href") or ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]+", table_id):
            result["table_failures"] += 1
            continue
        if "/action/downloadTable" not in href:
            result["table_failures"] += 1
            continue
        entries.append({"href": href, "tableId": table_id})
    return entries


def _tandf_csv_batch_budget_ms(
    deadline: float | None,
    entry_count: int,
) -> int:
    if deadline is not None:
        return int((deadline - time.monotonic()) * 1000)
    worker_rounds = (
        entry_count + _TANDF_TABLE_FETCH_CONCURRENCY - 1
    ) // _TANDF_TABLE_FETCH_CONCURRENCY
    return worker_rounds * _TANDF_TABLE_FETCH_MS


def _fetch_tandf_csv_table_batch(
    page: Any,
    entries: list[dict[str, str]],
    deadline: float | None,
    result: dict[str, Any],
) -> list[Any]:
    if not entries:
        return []
    remaining_ms = _tandf_csv_batch_budget_ms(deadline, len(entries))
    if remaining_ms <= 0:
        result["timed_out"] = True
        return []
    try:
        batch = page.evaluate(
            _TANDF_FETCH_TABLE_CSV_BATCH_SCRIPT,
            {
                "entries": entries,
                "perTableTimeoutMs": _TANDF_TABLE_FETCH_MS,
                "totalTimeoutMs": remaining_ms,
                "concurrency": _TANDF_TABLE_FETCH_CONCURRENCY,
            },
        )
    except Exception:
        return []
    if isinstance(batch, list):
        return batch
    if not isinstance(batch, Mapping):
        return []
    if batch.get("timedOut"):
        result["timed_out"] = True
    result["table_fetch_concurrency"] = max(0, int(batch.get("concurrency") or 0))
    raw_results = batch.get("results")
    return raw_results if isinstance(raw_results, list) else []


def _tandf_csv_rows(response: Mapping[str, Any]) -> list[list[str]]:
    if not response.get("ok"):
        raise ValueError("T&F table CSV request was not successful")
    content_type = normalize_text(str(response.get("contentType") or ""))
    csv_text = str(response.get("text") or "")
    if "csv" not in content_type.lower() or not csv_text.strip():
        raise ValueError("T&F table endpoint did not return CSV")
    if len(csv_text) > _TANDF_MAX_TABLE_CSV_CHARS:
        raise ValueError("T&F table CSV exceeded the bounded payload size")
    rows = [
        [
            _clean_tandf_accessible_control_text(cell)
            for cell in row[:_TANDF_MAX_TABLE_COLUMNS]
        ]
        for row in list(csv.reader(io.StringIO(csv_text)))[:_TANDF_MAX_TABLE_ROWS]
    ]
    rows = [row for row in rows if any(row)]
    if not rows:
        raise ValueError("T&F table CSV did not contain rows")
    return rows


def _hydrate_tandf_csv_table_batch(
    page: Any,
    entries: list[dict[str, str]],
    batch_results: list[Any],
    deadline: float | None,
    result: dict[str, Any],
) -> set[str]:
    hydrated_table_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if deadline is not None and time.monotonic() >= deadline:
            result["timed_out"] = True
            result["table_failures"] += len(entries) - index
            break
        response = batch_results[index] if index < len(batch_results) else None
        table_id = entry["tableId"]
        try:
            if not isinstance(response, Mapping):
                raise ValueError("T&F table CSV request was not successful")
            rows = _tandf_csv_rows(response)
            hydrated = bool(
                page.evaluate(
                    _TANDF_INJECT_TABLE_SCRIPT,
                    {
                        "tableId": table_id,
                        "caption": _clean_tandf_accessible_control_text(
                            response.get("caption")
                        ),
                        "rows": rows,
                    },
                )
            )
        except Exception:
            result["table_failures"] += 1
            continue
        if not hydrated:
            result["table_failures"] += 1
            continue
        result["tables_hydrated"] += 1
        result["csv_tables_hydrated"] += 1
        hydrated_table_ids.add(table_id)
    return hydrated_table_ids


def _tandf_embedded_rows(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    rows = [
        [
            _clean_tandf_accessible_control_text(cell)
            for cell in row[:_TANDF_MAX_TABLE_COLUMNS]
        ]
        for row in value[:_TANDF_MAX_TABLE_ROWS]
        if isinstance(row, list)
    ]
    return [row for row in rows if any(row)]


def _hydrate_tandf_embedded_tables_from_page(
    page: Any,
    hydrated_table_ids: set[str],
    deadline: float | None,
    result: dict[str, Any],
) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        result["timed_out"] = True
        return
    try:
        embedded = page.evaluate(
            _TANDF_READ_EMBEDDED_TABLES_SCRIPT,
            {
                "maxTables": _TANDF_MAX_DYNAMIC_TABLES,
                "maxRows": _TANDF_MAX_TABLE_ROWS,
                "maxColumns": _TANDF_MAX_TABLE_COLUMNS,
                "maxChars": _TANDF_MAX_TABLE_CSV_CHARS,
            },
        )
    except Exception:
        result["embedded_table_error"] = True
        return
    if not isinstance(embedded, Mapping):
        return
    result["embedded_tables"] = max(0, int(embedded.get("total") or 0))
    result["truncated"] = bool(result["truncated"] or embedded.get("truncated"))
    entries = embedded.get("tables")
    if not isinstance(entries, list):
        return
    for entry in entries[:_TANDF_MAX_DYNAMIC_TABLES]:
        if not isinstance(entry, Mapping):
            result["table_failures"] += 1
            continue
        table_id = normalize_text(str(entry.get("tableId") or ""))
        if table_id in hydrated_table_ids:
            continue
        rows = _tandf_embedded_rows(entry.get("rows"))
        if not re.fullmatch(r"[A-Za-z0-9_-]+", table_id) or not rows:
            result["table_failures"] += 1
            continue
        try:
            hydrated = bool(
                page.evaluate(
                    _TANDF_INJECT_TABLE_SCRIPT,
                    {
                        "tableId": table_id,
                        "caption": _clean_tandf_accessible_control_text(
                            entry.get("caption")
                        ),
                        "rows": rows,
                    },
                )
            )
        except Exception:
            hydrated = False
        if hydrated:
            result["tables_hydrated"] += 1
            result["embedded_tables_hydrated"] += 1
            hydrated_table_ids.add(table_id)
        else:
            result["table_failures"] += 1


def prepare_browser_page(
    page: Any,
    *,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    """Hydrate bounded T&F CSV or already-loaded same-page table payloads."""

    result: dict[str, Any] = {
        "attempted": True,
        "table_controls": 0,
        "tables_hydrated": 0,
        "csv_tables_hydrated": 0,
        "embedded_tables": 0,
        "embedded_tables_hydrated": 0,
        "table_failures": 0,
        "truncated": False,
    }
    locator = getattr(page, "locator", None)
    if not callable(locator):
        result["attempted"] = False
        return result
    links = locator(_TANDF_TABLE_DOWNLOAD_SELECTOR)
    count = max(0, int(links.count()))
    result["table_controls"] = count
    result["truncated"] = count > _TANDF_MAX_DYNAMIC_TABLES
    deadline = _tandf_table_deadline(timeout_ms)
    entries = _collect_tandf_csv_table_entries(links, count, deadline, result)
    batch_results = _fetch_tandf_csv_table_batch(page, entries, deadline, result)
    hydrated_table_ids = _hydrate_tandf_csv_table_batch(
        page,
        entries,
        batch_results,
        deadline,
        result,
    )
    _hydrate_tandf_embedded_tables_from_page(
        page,
        hydrated_table_ids,
        deadline,
        result,
    )
    return result


def extract_references(html_text: str) -> list[dict[str, str | None]]:
    """Extract the numbered T&F list through the shared HTML reference parser."""

    if not normalize_text(html_text):
        return []
    soup = BeautifulSoup(html_text, choose_parser())
    reference_nodes = soup.select("ul.references.numeric-ordered-list > li")
    for index, node in enumerate(reference_nodes, start=1):
        if not normalize_text(str(node.get("data-bib-id") or "")):
            node["data-bib-id"] = normalize_text(str(node.get("id") or index))
    if not reference_nodes:
        for index, node in enumerate(
            soup.select(".summation-section > div[id^='FN']"), start=1
        ):
            node.name = "li"
            node["data-bib-id"] = normalize_text(str(node.get("id") or index))
            first_text = next(
                (
                    child
                    for child in node.descendants
                    if isinstance(child, NavigableString) and normalize_text(str(child))
                ),
                None,
            )
            if first_text is not None:
                cleaned = re.sub(rf"^\s*{index}\s+", "", str(first_text), count=1)
                first_text.replace_with(cleaned)
    return extract_numbered_references_from_soup(soup)


def _normalize_tandf_section_hints(section_hints: Any) -> list[dict[str, Any]]:
    normalized_hints: list[dict[str, Any]] = []
    for hint in section_hints or []:
        if not isinstance(hint, Mapping):
            continue
        normalized_hint = dict(hint)
        heading = normalize_text(str(normalized_hint.get("heading") or "")).rstrip(
            ".: "
        )
        if heading:
            normalized_hint["heading"] = heading
        if heading.lower() in {
            "additional information",
            "acknowledgment",
            "acknowledgments",
            "acknowledgement",
            "acknowledgements",
            "funding",
            "notes on contributors",
        }:
            normalized_hint["kind"] = "body"
        normalized_hints.append(normalized_hint)
    return normalized_hints


def finalize_extraction(
    html_text: str,
    source_url: str,
    markdown_text: str,
    extraction: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    del source_url, metadata
    finalized = dict(extraction)
    finalized["section_hints"] = _normalize_tandf_section_hints(
        finalized.get("section_hints")
    )
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    extracted_references = extract_references(html_text)
    if extracted_references:
        finalized["references"] = extracted_references
    return tandf_normalize_markdown(markdown_text), finalized


def extract_asset_html_scopes(
    body_container: Tag,
    supplementary_container: Tag,
    *,
    publisher: str,
    content_fragment_html,
    **_kwargs: Any,
) -> tuple[str, str]:
    selector = ".supplemental-material-container"
    for node in list(body_container.select(selector)):
        node.decompose()
    supplementary_html = "\n".join(
        str(node) for node in supplementary_container.select(selector)
    )
    return content_fragment_html(
        body_container, publisher=publisher
    ), supplementary_html


def _extract_tandf_supplementary_assets(
    html_text: str, source_url: str
) -> list[dict[str, str]]:
    from ..extraction.html import assets as html_assets

    return [
        asset
        for asset in html_assets.extract_supplementary_assets(html_text, source_url)
        if "/action/downloadsupplement" in normalize_text(asset.get("url")).lower()
    ]


def _mark_tandf_accepted_figure_previews(
    assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    marked: list[dict[str, Any]] = []
    for asset in assets:
        item: dict[str, Any] = dict(asset)
        preview_url = normalize_text(item.get("preview_url"))
        parsed = urlparse(preview_url)
        host = normalize_text(parsed.hostname).lower()
        if (
            normalize_text(item.get("kind")).lower() == "figure"
            and (host == "tandfonline.com" or host.endswith(".tandfonline.com"))
            and parsed.path.lower().startswith("/cms/asset/")
        ):
            item["preview_accepted"] = "true"
            if not normalize_text(
                str(item.get("full_size_url") or item.get("download_url") or "")
            ):
                item["provenance"] = [OFFICIAL_FULL_SIZE_NOT_EXPOSED]
        marked.append(item)
    return marked


def scoped_asset_extractor(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile,
    supplementary_html_text: str | None = None,
) -> list[dict[str, Any]]:
    from ._html_asset_engine import (
        HtmlAssetExtractionPolicy,
        extract_scoped_assets_with_policy,
    )

    return extract_scoped_assets_with_policy(
        body_html_text,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=supplementary_html_text,
        policy=HtmlAssetExtractionPolicy(
            supplementary_extractor=_extract_tandf_supplementary_assets,
            finalizer=_mark_tandf_accepted_figure_previews,
        ),
    )


__all__ = [
    "TANDF_DOM_CHROME_SELECTORS",
    "TANDF_FRONT_MATTER_CONTAINS_TOKENS",
    "TANDF_FRONT_MATTER_EXACT_TEXTS",
    "TANDF_FRONT_MATTER_PUBLICATION_KEYWORDS",
    "TANDF_MARKDOWN_PROMO_TOKENS",
    "TANDF_POST_CONTENT_BREAK_TOKENS",
    "TANDF_SITE_RULE_OVERRIDES",
    "TANDF_SUPPLEMENTARY_TEXT_TOKENS",
    "extract_asset_html_scopes",
    "extract_authors",
    "extract_references",
    "finalize_extraction",
    "prepare_browser_page",
    "refine_selected_container",
    "scoped_asset_extractor",
    "tandf_asset_body_container",
    "tandf_asset_figure_extraction",
    "tandf_before_block_normalization",
    "tandf_body_container",
    "tandf_classify_heading",
    "tandf_normalize_markdown",
]
