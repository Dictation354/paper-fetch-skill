"""ScienceDirect article DOM extraction; shared renderers own math and tables."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import re
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from ..elsevier_identifiers import extract_elsevier_pii_from_url
from ..extraction.html._metadata import parse_html_metadata
from ..extraction.html.parsing import choose_parser
from ..extraction.html.semantics import collect_html_section_hints
from ..extraction.html.signals import HtmlExtractionFailure
from ..formula.validation import formula_document, capture_formula_diagnostics
from ..models import SemanticLosses
from ..publisher_identity import normalize_doi
from ..quality.access_boundary import raise_for_paywall
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..utils import dedupe_authors, normalize_text
from ._html_references import _reference_doi, _reference_year
from ._reference_doi import reference_doi
from ._elsevier_xml_rules import (
    combine_elsevier_section_title,
    format_elsevier_reference,
)
from ._html_section_markdown import (
    render_container_markdown,
    render_clean_text_from_html,
)
from ..extraction.html.tables import render_table_inline_text
from ..markdown.images import render_markdown_image
from ._elsevier_navigation import anchor_id, anchor_markup, finalize_markdown

BODY_SELECTOR = "#body"
SUPPLEMENT_SELECTOR = ".Appendices .e-component, .appendices .e-component, .e-component, .supplementary-material, #supplementary-material"
CONTENT_SELECTOR = "#abstracts, .abstracts, .Highlights, .highlights, .Keywords, .keywords-section, #body, .Tail, .tail, #references"
NOISE_SELECTOR = "nav, aside, .RecommendedArticles, .recommended-articles, .related-content, .reading-assistant, .ReaderAssistant, .PdfEmbed, .u-screen-reader-only, .sr-only, button, style, noscript"

_MATHJAX_ORIGINALS_SCRIPT = r"""() => {
  let recovered = 0;
  const bind = (node, original) => {
    if (!node || typeof original !== 'string' || !/^\s*<(?:[\w-]+:)?math[\s>]/.test(original)) return;
    node.setAttribute('data-paper-fetch-mathml', original);
    recovered++;
  };
  if (window.MathJax && MathJax.Hub && MathJax.Hub.getAllJax) {
    for (const jax of MathJax.Hub.getAllJax()) {
      const source = jax.SourceElement && jax.SourceElement();
      const node = document.getElementById(jax.inputID + '-Frame')
        || (source && source.previousElementSibling);
      bind(node, jax.originalText);
    }
  }
  const doc = window.MathJax && MathJax.startup && MathJax.startup.document;
  if (doc && doc.getMathItemsWithin) {
    for (const item of doc.getMathItemsWithin(document.body)) bind(item.typesetRoot, item.math);
  }
  return { mathjax_original_mathml: recovered };
}"""


def prepare_browser_page(page: Any, *, timeout_ms: int, cancel_check=None):
    del timeout_ms
    if cancel_check is not None:
        cancel_check()
    from .browser_runtime.navigation import evaluate_main_world

    return evaluate_main_world(page, _MATHJAX_ORIGINALS_SCRIPT)


def main_document_matches(
    response_url: str, final_url: str, html: str, doi: str
) -> bool:
    if urldefrag(response_url)[0] != urldefrag(final_url)[0]:
        return False
    pii = extract_elsevier_pii_from_url(final_url)
    if not pii or extract_elsevier_pii_from_url(response_url) != pii:
        return False
    observed = normalize_doi(parse_html_metadata(html, final_url).get("doi"))
    return bool(observed and observed == normalize_doi(doi))


def extract_authors(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    authors = []
    for node in soup.select(
        ".author-group .react-xocs-alternative-link, #author-group .author, .author-group .author"
    ):
        given, surname = node.select_one(".given-name"), node.select_one(".surname")
        if surname is not None:
            authors.append(
                normalize_text(
                    " ".join(
                        n.get_text(" ", strip=True)
                        for n in (given, surname)
                        if n is not None
                    )
                )
            )
        else:
            name = node.select_one(".author-name")
            if name is not None:
                authors.append(normalize_text(name.get_text(" ", strip=True)))
    return dedupe_authors(
        authors or parse_html_metadata(html_text, "").get("authors") or []
    )


def extract_pdf_candidate_urls_from_html(
    html_text: str, source_url: str, *, expected_doi: str | None = None
) -> list[str]:
    """Only the current PII's download controls, never cited/recommended papers."""
    soup = BeautifulSoup(html_text, choose_parser())
    observed_doi = normalize_doi(parse_html_metadata(html_text, source_url).get("doi"))
    if expected_doi and observed_doi and observed_doi != normalize_doi(expected_doi):
        return []
    pii = extract_elsevier_pii_from_url(source_url)
    if not pii:
        return []
    result = []
    for node in soup.select('meta[name="citation_pdf_url"], a[href]'):
        if any(
            isinstance(parent, Tag)
            and (
                parent.get("id") in {"bibliography", "references", "recommendations"}
                or set(parent.get("class", []))
                & {
                    "References",
                    "references",
                    "RecommendedArticles",
                    "recommended-articles",
                    "related-content",
                }
            )
            for parent in node.parents
        ):
            continue
        url = urljoin(source_url, str(node.get("href") or node.get("content") or ""))
        if (
            urlsplit(url).hostname in {"www.sciencedirect.com", "sciencedirect.com"}
            and extract_elsevier_pii_from_url(url) == pii
            and any(token in urlsplit(url).path.lower() for token in ("/pdfft", "/pdf"))
            and url not in result
        ):
            result.append(url)
    return result


def browser_pdf_candidates(html_text, source_url, *, expected_doi):
    observed = normalize_doi(parse_html_metadata(html_text, source_url).get("doi"))
    if observed and observed != normalize_doi(expected_doi):
        return []
    candidates = extract_pdf_candidate_urls_from_html(
        html_text, source_url, expected_doi=expected_doi
    )
    pii = extract_elsevier_pii_from_url(source_url)
    if pii:
        fallback = f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
        if fallback not in candidates:
            candidates.append(fallback)
    return candidates


def _top_nodes(root, selector):
    nodes = root.select(selector)
    ids = {id(node) for node in nodes}
    return [
        node for node in nodes if not any(id(parent) in ids for parent in node.parents)
    ]


def prepare_source_images(container, source_url):
    for figure in container.select("figure, .figure"):
        preferred = None
        for link in figure.select("a[href]"):
            label = normalize_text(link.get_text(" ", strip=True)).lower()
            if (
                "high-res" in label
                or "high resolution" in label
                or "high-res" in str(link.get("class", []))
            ):
                preferred = urljoin(source_url, str(link["href"]))
                break
        for image in figure.select("img"):
            value = image.get("data-src") or image.get("src")
            if preferred or value:
                image["src"] = preferred or urljoin(source_url, str(value))
                if preferred:
                    image["data-full-size-src"] = preferred


def _prepare_dom(soup, source_url, losses=None):
    body = soup.select_one(BODY_SELECTOR)
    front_nodes = {id(node) for node in body.find_all_previous()} if body else set()
    for node in list(soup.select(".author-highlights, .Highlights, .highlights")):
        if (
            node.parent is not None
            and id(node) in front_nodes
            and node.select_one(BODY_SELECTOR) is None
        ):
            node.decompose()
    for heading in soup.select("h1, h2, h3, h4, h5, h6"):
        label = heading.select_one(":scope > .label, :scope > .section-label")
        if label is None:
            sibling = heading.find_previous_sibling()
            if sibling is not None and set(sibling.get("class", [])) & {
                "label",
                "section-label",
            }:
                label = sibling
        if label is not None:
            counter = label.get_text(" ", strip=True)
            if re.fullmatch(r"\d+(?:\.\d+)*\.?", counter):
                label.extract()
                title = heading.get_text(" ", strip=True)
                if combine_elsevier_section_title(counter, title) != title:
                    heading.insert(0, counter + " ")
    for node in soup.select("[data-paper-fetch-mathml]"):
        math = BeautifulSoup(
            str(node["data-paper-fetch-mathml"]), choose_parser()
        ).find("math")
        if math is not None:
            node.clear()
            node.append(math)
            node.attrs.pop("aria-hidden", None)
            node["class"] = [
                "display-formula"
                if math.get("display") == "block"
                else "inline-formula"
            ]
    for script in list(soup.select("script")):
        if str(script.get("type") or "").lower() not in {
            "math/tex",
            "math/tex; mode=display",
            "math/mml",
            "application/mathml+xml",
        }:
            script.decompose()
    prepare_source_images(soup, source_url)
    for node in list(soup.select("figure .download-link, .figure .download-link")):
        node.decompose()
    for node in list(soup.select(NOISE_SELECTOR)):
        node.decompose()
    for node in list(soup.select("td .screen-reader-only, th .screen-reader-only")):
        node.decompose()
    for node in list(soup.select(".MathJax_Preview")):
        node.decompose()
    for link in list(soup.select("a[href]")):
        if "/topics/" in str(link["href"]):
            link.unwrap()
            continue
        if not str(link["href"]).startswith("#"):
            link["href"] = urljoin(source_url, str(link["href"]))
    # Source .para wrappers are paragraphs. Do not flatten their inline children.
    for node in soup.select("u"):
        node.unwrap()
    for label in soup.select(".list-label"):
        text = label.get_text("", strip=True)
        if re.fullmatch(r"\d+[.)]", text):
            # A source label inside a bullet must remain visible text, rather
            # than opening a second CommonMark ordered list.
            label.clear()
            label.append(text[:-1] + "\\" + text[-1])
    for node in soup.select("div.para, div[id^=para], div[id^=spara], div[id]"):
        if not (
            set(node.get("class", [])) & {"para"}
            or re.fullmatch(r"(?:p|para|spara|spar)\d+", str(node.get("id") or ""))
        ):
            continue
        if node.find(["p", "div", "table", "figure", "section"]) is None:
            node.name = "p"
    # Table captions/footnotes stay adjacent to the source table; the shared
    # renderer handles rowspan/colspan without converting tables into figures.
    for node in soup.select("figure .captions"):
        node.name = "figcaption"
    for node in soup.select(".tables, .table"):
        if node.find("table") is not None:
            node.name = "div"
    from .atypon_browser_workflow.formulas import _display_formula_replacement

    for node in _top_nodes(soup, ".display, .equation"):
        # .display wraps figures/tables/attachments as well as equations.
        if (
            node.name in {"figure", "table"}
            or set(node.get("class", [])) & {"figure", "tables", "e-component"}
            or node.select_one("figure, .figure, table, .e-component") is not None
        ):
            continue
        if (
            node.select_one(".formula, math, tex-math, script[type^='math/'], img")
            is None
        ):
            continue
        formula = node.select_one(".formula") or node
        label = formula.select_one(".label") or node.select_one(":scope > .label")
        if label is not None:
            formula["data-equation-label"] = normalize_text(
                label.get_text(" ", strip=True)
            )
        else:
            formula["data-no-equation-label"] = "true"
        replacement = _display_formula_replacement(formula, soup, losses)
        if replacement is None:
            continue
        for target in node.select("[id]") + [node]:
            if target.get("id"):
                replacement.insert(0, anchor_markup(target["id"]))
        node.replace_with(replacement)


def _render_table_cell(node):
    clone = deepcopy(node)
    literals: dict[str, str] = {}
    for raw in clone.select("[data-paper-fetch-markdown]"):
        token = f"ELSEVIERTABLELITERAL{len(literals)}TOKEN"
        while token in clone.get_text():
            token += "X"
        literals[token] = raw.get_text("\n\n", strip=False)
        raw.replace_with(token)
    text = render_table_inline_text(clone)
    for token, value in literals.items():
        text = text.replace(token, value)
    return text


def _raw_node(soup, markdown, *, inline=False):
    node = soup.new_tag(
        "span" if inline else "div", attrs={"data-paper-fetch-markdown": "1"}
    )
    node.string = markdown
    return node


def _prepare_navigation(container, soup, refs):
    aliases = {}
    for ref in refs:
        keys = ref["_bibliography"]["keys"]
        if keys:
            for key in keys:
                aliases[key] = keys[0]
                aliases["ref-id-" + key] = keys[0]
    # Only IDs in selected article content get targets; omitted front matter
    # and reference controls cannot accidentally produce dangling navigation.
    linked_keys = {str(link["href"])[1:] for link in container.select('a[href^="#"]')}
    for node in list(container.select("[id]")):
        key = str(node["id"])
        semantic_target = (
            node.name in {"section", "figure", "table"}
            or re.fullmatch(r"h[1-6]", node.name)
            or bool(set(node.get("class", [])) & {"tables", "figure"})
            or node.find(re.compile(r"^h[1-6]$"), recursive=False) is not None
        )
        if key not in linked_keys and not semantic_target:
            continue
        marker = _raw_node(soup, anchor_markup(key), inline=True)
        heading = (
            node
            if re.fullmatch(r"h[1-6]", node.name)
            else node.find(re.compile(r"^h[1-6]$"), recursive=False)
        )
        if heading is not None:
            heading.insert_after(marker)
        elif node.name == "table":
            node.insert_before(marker)
        elif node.name not in {"img", "br", "math"}:
            node.insert(0, marker)
        else:
            node.insert_before(marker)
    for link in list(container.select('a[href^="#"]')):
        key = str(link["href"])[1:]
        target = aliases.get(key, key)
        # Render the link directly to keep source superscripts and citation
        # text from being converted into positional numeric citation guesses.
        content = deepcopy(link)
        content.name = "span"
        content.attrs.pop("href", None)
        for generated in content.select("[data-paper-fetch-markdown]"):
            if generated.get_text().startswith('<a id="elsevier-'):
                generated.decompose()
        label = render_clean_text_from_html(content)
        own_target = anchor_markup(str(link["id"])) if link.get("id") else ""
        link.replace_with(
            _raw_node(
                soup, own_target + f"[{label}](#{anchor_id(target)})", inline=True
            )
        )


def _prepare_figures(container, soup):
    for figure in _top_nodes(container, "figure, .figure"):
        lines: list[str] = []
        anchors = []
        for node in figure.select("[data-paper-fetch-markdown]"):
            value = node.get_text("", strip=False)
            if value.startswith('<a id="elsevier-'):
                anchors.append(value)
        for image in figure.select("img[src]"):
            alt = str(image.get("alt") or "Figure")
            if alt == "Unlabelled Image":
                alt = "Figure"
            lines.extend([render_markdown_image("figure", alt, str(image["src"])), ""])
        caption = figure.select_one("figcaption, .captions")
        if caption is not None:
            caption = deepcopy(caption)
            for node in caption.select("[data-paper-fetch-markdown]"):
                if node.get_text().startswith('<a id="elsevier-'):
                    node.decompose()
            # Source block boundaries matter for caption attribution (Fuente).
            for node in caption.find_all(["div", "p"]):
                node.name = "p"
            if caption.get_text(" ", strip=True) != "Unlabelled Image":
                render_container_markdown(
                    caption,
                    lines,
                    level=3,
                    render_table_cell=_render_table_cell,
                )
        if lines:
            image_lines = 2 * len(figure.select("img[src]"))
            if len(lines) > image_lines:
                lines[image_lines] = "".join(anchors) + lines[image_lines]
            elif anchors:
                lines = ["".join(anchors), "", *lines]
            figure.replace_with(_raw_node(soup, "\n".join(lines)))
    for link in container.select(".e-component a[href]"):
        # Keep the attachment's source type/size and actual URL once.
        label = normalize_text(link.get_text(" ", strip=True))
        label = re.sub(r"^(?:Download\s*)+", "", label, flags=re.I)
        label = re.sub(r"^(?:\s*:?\s*Download\b\s*)+", "", label, flags=re.I).lstrip(
            ": "
        )
        if label:
            link.clear()
            link.append(label)


def _article_notes(soup):
    lines: list[str] = []
    for note in _article_scope(soup).select(
        "#footnotes > .footnote, .footnotes > dl.footnote"
    ):
        if note.find_parent(class_="tables") is not None:
            continue
        label = note.select_one(".footnote-label")
        detail = note.select_one(".footnote-detail")
        if detail is None:
            continue
        content: list[str] = []
        render_container_markdown(
            detail, content, level=3, render_table_cell=_render_table_cell
        )
        text = "\n".join(content).strip()
        if text:
            lines.extend(
                [
                    (
                        normalize_text(label.get_text(" ", strip=True)) + " "
                        if label
                        else ""
                    )
                    + text,
                    "",
                ]
            )
    return lines


def _article_scope(soup):
    body = soup.select_one(BODY_SELECTOR)
    if body is None:
        return soup
    return (
        body.find_parent("article")
        or body.find_parent(class_="body-area")
        or body.parent
    )


def _content_nodes(soup):
    scope = _article_scope(soup)
    selected = list(scope.select(CONTENT_SELECTOR))
    # Declarations may have no semantic class or id. Their relationship to the
    # article body and their heading/paragraph structure identify them.
    for node in scope.select("div, section"):
        if node.select_one(BODY_SELECTOR) is not None:
            continue
        if (
            node.find(re.compile(r"^h[2-6]$"), recursive=False) is not None
            and node.select_one("p, .para, div") is not None
        ):
            selected.append(node)
    ids = {id(node) for node in selected}
    return [
        node
        for node in scope.descendants
        if isinstance(node, Tag)
        and id(node) in ids
        and not any(id(parent) in ids for parent in node.parents)
    ]


def _references(soup):
    refs: list[dict[str, Any]] = []
    noise_ids = {id(node) for node in soup.select(NOISE_SELECTOR)}
    for node in _top_nodes(
        _article_scope(soup),
        "#references .references > li, .References .bib-reference, .references .bib-reference, #bibliography .bib-reference",
    ):
        if any(id(parent) in noise_ids for parent in node.parents):
            continue
        label_node = node.select_one(".label")
        label = (
            normalize_text(label_node.get_text(" ", strip=True)) if label_node else None
        )
        clone = deepcopy(node)
        for label_copy in clone.select(".label"):
            label_copy.decompose()
        doi = _reference_doi(node, include_text=False)
        for noise in clone.select(".ReferenceLinks, a.link, .reference-link, svg"):
            noise.decompose()
        for block in clone.select("div, p, li"):
            block.insert_before(" ")
            block.insert_after(" ")
        raw = " ".join(clone.get_text("", strip=False).split())
        if raw:
            title = clone.select_one(".title")
            authors = clone.select_one(".authors")
            host = clone.select_one(".host")
            host_text = host.get_text(" ", strip=True) if host else ""
            volume = re.search(
                r",\s*(\d+)\s*(?:\([^()]*\)\s*)?\((?:18|19|20)\d{2}\)", host_text
            )
            page = re.search(r"\bpp?\.\s*([\w]+)", host_text)
            keys = [
                str(n.get("id"))
                for n in [node, *node.select(".reference[id]")]
                if n.get("id")
            ]
            keys.extend(
                str(n["id"])[len("ref-id-") :]
                for n in node.select('.label a[id^="ref-id-"]')
            )
            refs.append(
                {
                    "label": label,
                    "raw": format_elsevier_reference(
                        len(refs) + 1,
                        raw,
                        label or "",
                        doi=doi or reference_doi(raw) or "",
                        keys=keys[:1],
                    ),
                    "doi": doi or reference_doi(raw),
                    "year": _reference_year(node, raw),
                    "title": title.get_text(" ", strip=True) if title else None,
                    "_bibliography": {
                        "keys": keys,
                        "first_author": authors.get_text(" ", strip=True).split(",", 1)[
                            0
                        ]
                        if authors
                        else "",
                        "volume": volume.group(1) if volume else "",
                        "first_page": page.group(1) if page else "",
                    },
                }
            )
    return refs


def extract_title(soup, *, page_metadata=None, metadata=None):
    if isinstance(soup, str):
        soup = BeautifulSoup(soup, choose_parser())
    page_metadata = page_metadata or {}
    metadata = metadata or {}
    title_node = next(
        (
            node
            for selector in ("h1 .title-text", "h1.title-text", "h1")
            if (node := soup.select_one(selector)) is not None
        ),
        None,
    )
    return normalize_text(
        title_node.get_text(" ", strip=True)
        if title_node
        else page_metadata.get("title") or metadata.get("title")
    )


@formula_document(new_document=True)
def extract_markdown(html_text: str, source_url: str, *, metadata=None):
    metadata = dict(metadata or {})
    raise_for_paywall(
        html_text, metadata=metadata, source_url=source_url, provider="elsevier"
    )
    soup = BeautifulSoup(html_text, choose_parser())
    body = soup.select_one(BODY_SELECTOR)
    if body is None:
        raise HtmlExtractionFailure(
            "article_container_not_found", "ScienceDirect #body was not present."
        )
    page_metadata = parse_html_metadata(html_text, source_url)
    title = extract_title(soup, page_metadata=page_metadata, metadata=metadata)
    authors = extract_authors(html_text)
    refs = _references(soup)
    keywords = [
        normalize_text(node.get_text("", strip=False))
        for node in soup.select(".Keywords .keyword, .keywords-section .keyword")
    ]
    losses = SemanticLosses()
    _prepare_dom(soup, source_url, losses)
    container = BeautifulSoup("<article></article>", choose_parser()).article
    for node in _content_nodes(soup):
        container.append(deepcopy(node))
    for node in _top_nodes(container, ".Keywords, .keywords-section, #references"):
        node.decompose()
    _prepare_navigation(container, soup, refs)
    _prepare_figures(container, soup)
    for heading in container.select("h1, h2, h3, h4, h5, h6"):
        if heading.name == "h1":
            heading.name = "h2"
    abstract_nodes = [
        node
        for node in _top_nodes(container, ".abstract, .Abstracts")
        if not set(node.get("class", [])) & {"graphical", "author-highlights"}
    ]
    abstract_sections: list[dict[str, Any]] = []
    for node in abstract_nodes:
        head = node.find(re.compile(r"^h[1-6]$"), recursive=False)
        text_node = deepcopy(node)
        outer_heading = text_node.find(re.compile(r"^h[1-6]$"), recursive=False)
        if outer_heading is not None:
            outer_heading.decompose()
        abstract_lines: list[str] = []
        render_container_markdown(
            text_node,
            abstract_lines,
            level=3,
            preserve_heading_levels=True,
            render_table_cell=_render_table_cell,
        )
        text = "\n".join(abstract_lines).strip()
        language_node = (
            node if node.get("lang") else node.find_parent(attrs={"lang": True})
        )
        if text:
            abstract_sections.append(
                {
                    "heading": normalize_text(head.get_text(" ", strip=True))
                    if head
                    else "Abstract",
                    "text": text,
                    "language": language_node.get("lang") if language_node else None,
                    "order": len(abstract_sections),
                }
            )
        node.decompose()
    lines: list[str] = []
    render_container_markdown(
        container,
        lines,
        level=2,
        preserve_heading_levels=True,
        render_table_cell=_render_table_cell,
    )
    notes = _article_notes(soup)
    if notes:
        lines.extend(["## Article notes", "", *notes])
    body_markdown = (
        (f"# {title}\n\n" if title else "") + "\n".join(lines).strip() + "\n"
    )
    if refs:
        body_markdown += (
            "\n## References\n\n" + "\n\n".join(ref["raw"] for ref in refs) + "\n"
        )
    abstract_markdown = "\n\n".join(
        f"## {block['heading']}\n\n{block['text']}" for block in abstract_sections
    )
    title_prefix = f"# {title}\n\n" if title else ""
    markdown = (
        title_prefix
        + (abstract_markdown + "\n\n" if abstract_markdown else "")
        + body_markdown[len(title_prefix) :]
    )
    markdown = finalize_markdown(markdown)
    body_markdown = finalize_markdown(body_markdown)
    hints = collect_html_section_hints(container, title=title)
    diagnostics = HtmlQualityAssessor("elsevier").assess(
        markdown,
        metadata,
        html_text=html_text,
        structure_dom=BeautifulSoup(str(container), choose_parser()),
        title=title,
        final_url=source_url,
        section_hints=hints,
    )
    if not diagnostics.accepted:
        raise HtmlExtractionFailure(
            diagnostics.reason, availability_failure_message(diagnostics)
        )
    capture_formula_diagnostics(losses, count_fallbacks=True)
    return markdown, {
        "title": title,
        "extracted_authors": authors,
        "references": refs,
        "keywords": keywords,
        "abstract_sections": abstract_sections,
        "body_markdown": body_markdown,
        "abstract_text": abstract_sections[0]["text"] if abstract_sections else None,
        "section_hints": hints,
        "semantic_losses": asdict(losses),
        "availability_diagnostics": diagnostics.to_dict(),
    }


def extract_assets(html_text, source_url, *, asset_profile):
    from ..extraction.html.assets import extract_scoped_html_assets

    if asset_profile == "none":
        return []
    soup = BeautifulSoup(html_text, choose_parser())
    _prepare_dom(soup, source_url)
    supplementary = BeautifulSoup("<div></div>", choose_parser()).div
    for node in _top_nodes(soup, SUPPLEMENT_SELECTOR):
        supplementary.append(node.extract())
    body = BeautifulSoup("<article></article>", choose_parser()).article
    for node in _top_nodes(soup, "#body, .graphical, .graphical-abstract"):
        body.append(deepcopy(node))
    assets = extract_scoped_html_assets(
        str(body),
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=str(supplementary),
    )
    abstract_urls = {
        str(image.get("src"))
        for image in soup.select(".graphical img, .graphical-abstract img")
    }
    appendix_urls = {
        str(image.get("src"))
        for image in soup.select(".Appendices img, .appendices img")
    }
    for asset in assets:
        if asset.get("url") in abstract_urls:
            asset["section"] = "abstract"
        elif asset.get("url") in appendix_urls:
            asset["section"] = "appendix"
    return assets
