"""Independent source selections for the canonical article review.

Only original publisher DOM/XML and captured metadata are read here. This
module does not call provider parsers to construct expected content.
"""

from copy import deepcopy
import html
import hashlib
import json
import re
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup, Tag
from markdown_it import MarkdownIt

from tests.support.test_evidence import evidence_cache
from tests.support.scientific_content import preserve_dom_scripts

_INLINE_MARKDOWN = MarkdownIt()

REFERENCE_SELECTORS = {
    "acs": ".ref-list .ref",
    "aip": ".ref-list .ref",
    "ams": "#contentRoot .reference > p.citationText",
    "annualreviews": "#itemFullTextId li.refbody",
    "arxiv": ".ltx_bibitem",
    "copernicus": "ref-list ref",
    "elsevier": "bib-reference",
    "frontiers": "ref-list ref",
    "mdpi": "#html-references_list li",
    "oxfordacademic": ".ref-list .ref",
    "plos": "ref-list ref",
    "pnas": '#bibliography [role="listitem"]',
    "royalsocietypublishing": ".ref-list .ref",
    "science": '#bibliography [role="listitem"]',
    "springer": ".c-article-references__item",
    "tandf": "ul.references.numeric-ordered-list > li",
    "wiley": ".article-section__references li",
}

# These two compact author blocks include affiliation markers and institutions;
# the names below were read from their original .ltx_personname blocks.
COMPACT_AUTHORS = {
    "10.48550/arxiv.2605.06663v1": ["Ryan Wang", "Akshita Bhagia", "Sewon Min"],
    "10.48550/arxiv.2605.06665v1": [
        "Minbin Huang",
        "Han Shi",
        "Chuanyang Zheng",
        "Yimeng Wu",
        "Guoxuan Chen",
        "Xingtong Yu",
        "Yichun Yin",
        "Hong Cheng",
    ],
}


def text_key(value):
    """Ignore layout whitespace, retaining punctuation, digits and operators."""
    return re.sub(r"\s+", "", html.unescape(str(value))).replace("\u200b", "")


def author_key(value):
    value = html.unescape(value)
    if "," in value:
        family, given = value.split(",", 1)
        value = given + " " + family
    return text_key(value)


def source_soup(fixture):
    return _source_soup(fixture.raw_path)


@evidence_cache
def _source_soup(path):
    return BeautifulSoup(path.read_text(), "xml" if path.suffix == ".xml" else "lxml")


def source_authors(fixture, soup):
    if fixture.provider == "ieee":
        landing = (fixture.raw_path.parent / "landing.html").read_text()
        match = re.search(r'"authors"\s*:\s*', landing)
        assert match, fixture.doi
        authors, _ = json.JSONDecoder().raw_decode(landing[match.end() :])
        return [a["name"] for a in authors], "landing.html:embedded authors"
    if fixture.provider == "arxiv":
        nodes = soup.select("article .ltx_personname")
        if fixture.doi in COMPACT_AUTHORS:
            visible = text_key(" ".join(n.get_text(" ", strip=True) for n in nodes))
            names = COMPACT_AUTHORS[fixture.doi]
            for name in names:
                assert text_key(name) in visible
            return names, "article .ltx_personname:reviewed compact block"
        return [
            name.strip()
            for n in nodes
            for name in n.get_text(" ", strip=True).split(" and ")
        ], "article .ltx_personname"
    if fixture.provider == "science":
        nodes = soup.select('.contributors [property="author"]')
        names = [
            " ".join(
                n.get_text(" ", strip=True)
                for n in author.select(
                    '[property="givenName"], [property="familyName"]'
                )
            )
            for author in nodes
        ]
        return list(dict.fromkeys(names)), '.contributors [property="author"]'
    if fixture.raw_path.suffix == ".xml":
        selector = (
            "author-group author"
            if fixture.provider == "elsevier"
            else 'article-meta contrib-group contrib[contrib-type="author"]'
        )
        names = []
        for n in soup.select(selector):
            given = n.find(["given-names", "given-name"])
            family = n.find("surname")
            if given is not None and family is not None:
                names.append(
                    given.get_text(" ", strip=True)
                    + " "
                    + family.get_text(" ", strip=True)
                )
            elif (collab := n.find("collab")) is not None:
                names.append(collab.get_text(" ", strip=True))
        return names, selector
    selector = (
        'meta[name="dc.Creator"]'
        if fixture.provider == "tandf"
        else 'meta[name="citation_author"]'
    )
    return [n["content"] for n in soup.select(selector)], selector


def source_references(fixture, soup):
    if fixture.provider == "ieee":
        path = fixture.raw_path.parent / "references.json"
        if path.exists():
            return json.loads(path.read_text())["references"]
        # RITA's captured full-text fragment contains a loaded bibliography.
        return soup.select(".reference-container")
    if fixture.provider == "iop":
        return [
            n
            for n in soup.select('meta[name="citation_reference"]')
            if n.get("content", "").strip()
        ]
    nodes = soup.select(REFERENCE_SELECTORS[fixture.provider])
    if fixture.provider == "tandf" and not nodes:
        nodes = soup.select(".summation-section > div[id^='FN']")
    return nodes


def source_reference_doi(fixture, node):
    """Read DOI-bearing original fields, never the current paper's linkout DOI."""
    if fixture.provider == "ieee" and isinstance(node, dict):
        links = node.get("links") or {}
        values = [
            links.get("crossRefLink"),
            links.get("doiLink"),
            node.get("doi"),
            node.get("googleScholarStructredQuery"),
            node.get("googleScholarStructuredQuery"),
            node.get("text"),
        ]
        for value in values:
            if match := re.search(r"10\.\d{4,9}/[^\s\"'<>]+", str(value or ""), re.I):
                return match.group().lower().rstrip(").,;")
        return None
    if fixture.provider == "iop":
        m = re.search(r"citation_doi=([^;]+)", node["content"])
        return m.group(1).strip().lower() if m else None
    if fixture.raw_path.suffix == ".xml":
        doi = node.select_one(
            'pub-id[pub-id-type="doi"], ext-link[ext-link-type="doi"], doi, inter-ref[inter-ref-type="doi"]'
        )
        if doi:
            return (
                re.sub(r"\s+", "", doi.get_text("", strip=True))
                .lower()
                .removeprefix("https://doi.org/")
            )
    candidates = []
    if fixture.provider == "arxiv":
        for anchor in node.select("a[href]"):
            if match := re.search(r"10\.\d{4,9}/[^\s\"'<>]+", anchor["href"], re.I):
                candidates.append(match.group().rstrip(").,;"))
    for anchor in node.select("a[href], ext-link"):
        href = unquote(str(anchor.get("href") or anchor.get("xlink:href") or ""))
        if re.match(r"https?://(?:dx\.)?doi\.org/", href, re.I):
            candidates.append(
                re.sub(r"^https?://(?:dx\.)?doi\.org/", "", href, flags=re.I)
            )
    if fixture.provider == "tandf":
        candidates += [n["data-target"] for n in node.select(".getFTR[data-target]")]
        for anchor in node.select("a[href]"):
            query = parse_qs(urlsplit(anchor["href"]).query)
            candidates += query.get("refDoi", []) + query.get("doiOfLink", [])
    if fixture.provider == "annualreviews":
        candidates.append(node.get("data-doi", ""))
    for value in candidates:
        value = html.unescape(unquote(value)).lower().strip().rstrip(".,")
        if re.fullmatch(r"10\.\d{4,9}/\S+", value):
            if fixture.provider == "oxfordacademic" and "(issn)" in value:
                continue
            return value
    # Several originals print a DOI as text without a DOI link (including
    # repository citations); no unrelated article-level URL is considered.
    text = node.get_text(" ", strip=True)
    if match := re.search(
        r"10\.\d{4,9}/[^\s\"'<>]+<[^>\s]+>\d+\.\d+\.co;[^\s\"'<>]+|10\.\d{4,9}/[^\s\"'<>]+",
        text,
        re.I,
    ):
        return match.group().lower().rstrip(").,;")
    return None


def source_reference_text(fixture, node):
    original = deepcopy(node)
    if fixture.provider == "wiley":
        for label in original.select(":scope > .bullet"):
            label.decompose()
    for noise in original.select(
        "label, .label, .citation-label, .citation-links, .extra-links, .ref-links, "
        ".external-links, .crossref-doi, .adsDoiReference, .xslopenurl, a.google-scholar, "
        "a.cross-ref, .js-references, a.externallink, a.js-externallink, .getFTR, "
        ".refLink-parent, .ltx_bib_links"
    ):
        noise.decompose()
    for tag in original.select(".ltx_tag"):
        if re.fullmatch(r"\[?\d+\]?\.?", tag.get_text(strip=True)):
            tag.decompose()
    # LaTeXML stores both MathML and TeX; use its explicit source TeX rather
    # than concatenating the alternative encodings into duplicate content.
    for math in original.select("math[alttext]"):
        math.replace_with(math["alttext"])
    for block in list(original.select(".ltx_bibblock")):
        if (
            block.get_text(" ", strip=True)
            .lower()
            .startswith(("cited by", "external links"))
        ):
            block.decompose()
    for anchor in list(original.select("a")):
        if anchor.get_text(" ", strip=True) == "Green Version":
            anchor.decompose()
    if fixture.provider == "springer":
        original = original.select_one(".c-article-references__text") or original
    if fixture.provider in {"pnas", "science"}:
        original = original.select_one(".citation-content") or original
    text = original.get_text(" ", strip=True)
    if fixture.provider == "tandf" and str(original.get("id", "")).startswith("FN"):
        text = re.sub(r"^\d+\s+", "", text)
    return text


def numeric_signature(value):
    """Bibliographic numeric values and signs, independently of word matching."""
    from tests.support.scientific_content import without_latex_spacing

    value = without_latex_spacing(html.unescape(value))
    value = re.sub(
        r"</?(?:sub|sup|br|em|strong|i|b|span)(?:\s[^<>]*?)?\s*/?>", "", value
    )
    value = value.translate(str.maketrans({"−": "-", "–": "-", "—": "-"}))
    value = re.sub(r"\s+", "", value)
    return re.findall(r"\d+(?:\.\d+)?|[<>≤≥≠±+-]", value)


BODY_SELECTORS = {
    "acs": ".article-body",
    "aip": '[data-widgetname="ArticleFulltext"]',
    "ams": "#articleBody",
    "annualreviews": "#itemFullTextId",
    "arxiv": "article",
    "copernicus": "body",
    "elsevier": "sections",
    "frontiers": "body",
    "ieee": "body",
    "iop": ".wd-jnl-art-full-text",
    "mdpi": ".html-body, #html-body, article",
    "oxfordacademic": '[data-widgetname="ArticleFulltext"]',
    "plos": "body",
    "pnas": "#bodymatter",
    "royalsocietypublishing": ".article-body",
    "science": "#bodymatter",
    "springer": ".main-content",
    "tandf": ".hlFld-Fulltext",
    "wiley": ".article-section__full",
}


def source_prose_blocks(fixture, soup):
    """Locate prose independently; separate figures, tables and bibliography."""
    body = soup.select_one(BODY_SELECTORS[fixture.provider])
    if fixture.provider == "ieee" and body is None:
        body = soup
    assert body is not None, (fixture.doi, BODY_SELECTORS[fixture.provider])
    body = deepcopy(body)
    for node in list(
        body.select(
            "figure, fig, table, table-wrap, ref-list, bib-reference, .ref-list, "
            ".ltx_bibliography, .ltx_abstract, .ltx_authors, .ltx_title_document, "
            ".figure, .fig, .figureView, .tableView, .table-wrap, .reference, "
            ".c-article-references__item, #bibliography, #html-references_list, "
            ".article-section__references, .references, .summation-section, "
            'script, style, nav, aside, [hidden], [aria-hidden="true"], '
            ".c-article-author-affiliation, .c-article-author-list, .c-article-metrics-bar, "
            ".hlFld-Abstract, .abstractSection, .abstract, .abstractInFull, .abstractInHTML, "
            ".keywords, .hlFld-Keyword, .NLM_kwd-group, .abstractKeywords, .author-notes, "
            ".contrib-group, .author-affiliations, .sectionInfo, .articleTools, .author-footnote, "
            ".article-title-and-authors, .off-screen, .table-wrap-foot, .html-table_footer, .html-table_foot, "
            ".dropDownMenu, .menuButton, .clearer, .hidden, .NLM_supplementary-material, "
            ".NLM_disp-formula, .disp-formula, .inline-formula"
        )
    ):
        if node.parent is not None:
            node.decompose()
    preserve_dom_scripts(body)
    # These back-matter categories are intentionally excluded by the public
    # rendering contract. Explicit data/code statements remain in their scope.
    for section in list(body.select("section, sec, ack, acknowledgment")):
        if section.parent is None:
            continue
        heading = section.find(["title", "section-title", "h2", "h3"], recursive=False)
        label = (
            heading.get_text(" ", strip=True).casefold().strip(" :.") if heading else ""
        )
        if section.name in {"ack", "acknowledgment"} or label in {
            "acknowledgments",
            "acknowledgements",
            "author contributions",
            "funding",
            "competing interests",
            "conflict of interest",
            "conflicts of interest",
            "author information",
            "additional information",
            "rights and permissions",
            "ethics declarations",
            "change history",
            "supplementary materials",
            "supporting information",
            "supplementary information",
            "supplementary material",
            "data availability statement",
            "code availability statement",
        }:
            section.decompose()
    result = []
    block_names = ["title", "section-title", "h2", "h3", "h4", "h5", "p", "para"]
    # Wiley's existing public contract moves the front-matter glossary after
    # the research body. It is checked separately, not treated as body order.
    if fixture.provider == "wiley":
        for heading in list(body.find_all(["h2", "h3"])):
            if heading.get_text(strip=True).casefold() == "abbreviations":
                parent = heading.parent
                if parent is not body:
                    parent.decompose()
                else:
                    heading.decompose()
    excluded_level = None
    for node in body.find_all(block_names + ["div"]):
        is_heading = (
            node.name in {"title", "section-title", "h2", "h3", "h4", "h5"}
            or "section-title" in node.get("class", [])
            or {"tl-main-part", "title"} <= set(node.get("class", []))
        )
        if is_heading:
            level = int(node.name[1]) if re.fullmatch(r"h[2-5]", node.name) else 2
            title = (
                re.sub(r"^[\d.\s]+", "", node.get_text(" ", strip=True))
                .casefold()
                .strip(" .:")
            )
            if excluded_level is not None and level <= excluded_level:
                excluded_level = None
            if title in {
                "acknowledgments",
                "acknowledgements",
                "author contributions",
                "authors’ roles",
                "funding",
                "funding information",
                "ethics statement",
                "supplementary data",
                "supplementary materials",
                "supplementary material",
                "supporting information",
                "conflict of interest statement",
                "reporting summary",
                "conflict of interest",
                "conflicts of interest",
                "disclosure statement",
                "competing interests",
                "notes on contributors",
                "institutional review board statement",
                "informed consent statement",
                "share and cite",
                "article metrics",
                "literature cited",
                "references",
                "references and notes",
                "supplemental material",
            } or title.startswith("sign up for"):
                excluded_level = level
        if excluded_level is not None:
            continue
        if (
            node.name == "div"
            and not is_heading
            and node.get("role") != "paragraph"
            and "html-p" not in node.get("class", [])
        ):
            continue
        if (
            node.find(block_names) is not None
            or node.select_one("div.html-p, div[role=paragraph]") is not None
        ):
            continue
        if node.name == "title" and node.parent.name != "sec":
            continue
        runs = []
        for string in node.strings:
            if string.find_parent(
                [
                    "math",
                    "tex-math",
                    "inline-formula",
                    "disp-formula",
                    "equation",
                    "xref",
                    "sup",
                ]
            ) or any(
                "ltx_ref" in p.get("class", [])
                or "ref" in p.get("data-track-action", "")
                for p in string.parents
            ):
                continue
            if any(
                set(p.get("class", []))
                & {"ltx_tag", "inline-equation", "display-formula", "equation"}
                for p in string.parents
            ):
                continue
            value = re.sub(r"\b[Rr]efs?\.\s*$", "", str(string)).strip()
            if is_heading:
                value = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", value)
                if (
                    fixture.provider == "annualreviews"
                    and value.isupper()
                    and len(value) > 3
                ):
                    value = value.title()
                if value.casefold() == "online methods":
                    value = "Methods"
            if (
                value
                and value
                not in {
                    "Keywords:",
                    "KEYWORDS:",
                    "Citation",
                    "Footnote",
                    "Visual Abstract",
                }
                and not re.fullmatch(r"\\\(.*\\\)", value, re.S)
            ):
                runs.append(value)
        if runs:
            result.append((node.name, runs))
    return result


def source_tables(fixture, soup):
    if fixture.provider == "copernicus":
        # Empty table xrefs derive their text from the article's bibliography.
        source_copy = deepcopy(soup)
        body = source_copy.select_one(BODY_SELECTORS[fixture.provider]) or source_copy
    else:
        body = deepcopy(soup.select_one(BODY_SELECTORS[fixture.provider]) or soup)
    if fixture.provider == "tandf":
        # The captured DOM row matrix loses spans. The publisher's original
        # same-page viewer JSON preserves the authoritative table markup.
        for script in soup.find_all("script"):
            raw = script.string or script.get_text()
            match = re.search(r"tandf\.tfviewerdata\s*=\s*", raw)
            if not match:
                continue
            payload, _ = json.JSONDecoder().raw_decode(raw[match.end() :])
            for entry in payload.get("tables", []):
                old = body.find(
                    "table", attrs={"data-paper-fetch-hydrated-table": entry["id"]}
                )
                original = BeautifulSoup(entry["content"], "lxml").find("table")
                if old is not None and original is not None:
                    old.replace_with(original)
    tables = (soup if fixture.provider == "elsevier" else body).select("table")
    if fixture.provider == "arxiv":
        tables = body.select("figure.ltx_table table.ltx_tabular")
    result = []
    seen = set()
    for table in tables:
        if table.find_parent("table") or table.find_parent("math"):
            continue
        if any(p.get("aria-hidden") == "true" for p in [table, *table.parents]):
            continue
        # Supporting-file indexes and publisher disclaimers are not data tables.
        text = table.get_text(" ", strip=True)
        if (
            "Publisher’s Note:" in text
            or "Publisher's Note:" in text
            or text.startswith("Filename Description")
        ):
            continue
        if any(
            "supporting" in str(p.get("class", ""))
            or "supplement" in str(p.get("class", ""))
            for p in table.parents
        ):
            continue
        rows = table.select("tr") or table.select("row")
        if not rows:
            continue
        key = tuple(
            tuple(
                c.get_text(" ", strip=True)
                for c in row.find_all(["td", "th", "entry"], recursive=False)
            )
            for row in rows
        )
        if not any(key) or key in seen:
            continue
        seen.add(key)
        result.append(table)
    expected = source_object_expectations(fixture.doi, fixture.raw_path)
    bind_table_expectations(result, expected["tables"])
    return result


def source_object_expectations(doi, path):
    from tests.golden_criteria import golden_criteria_sample_for_doi
    from tests.paths import REPO_ROOT

    sample = golden_criteria_sample_for_doi(doi)
    if "expected.json" in sample["assets"]:
        data = json.loads((REPO_ROOT / sample["assets"]["expected.json"]).read_text())
    else:
        data = sample
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return next(
        record for record in data["source_objects"] if record["sha256"] == digest
    )


def bind_table_expectations(tables, expected):
    by_hash = {entry["node_sha256"]: entry for entry in expected}
    for table in tables:
        entry = by_hash[hashlib.sha256(str(table).encode()).hexdigest()]
        table.__dict__["_source_grid"] = entry["grid"]
        cells = table.find_all(["th", "td", "entry"])
        assert len(cells) == len(entry["cells"])
        for cell, text in zip(cells, entry["cells"], strict=True):
            cell.__dict__["_source_text"] = text


def source_cell_text(cell, **_options):
    if "_source_text" in cell.__dict__:
        return cell.__dict__["_source_text"]
    # Minimal contract snippets need only literal node text. Scientific/table
    # transformations in whole-paper replays must have fixed source expectations.
    assert not cell.select("math, xref, sup, sub")
    return cell.get_text(" ", strip=True)


def comparable_cell(value):
    """Normalize only mathematical/Markdown presentation, retaining all symbols."""
    from tests.support.reviewed_html_publisher_content import _table_cell
    from tests.support.scientific_content import (
        script_markup,
        math_semantic_key,
        without_latex_spacing,
    )

    value = without_latex_spacing(script_markup(value))
    value = re.sub(
        r"\$([^$]+)\$",
        lambda m: "$" + re.sub(r"(?<!\\)([_^])([^{}\s\\])", r"\1{\2}", m[1]) + "$",
        value,
    )
    value = value.replace("⋅", "·")
    value = html.unescape(value).replace("\\|", "|")
    for command, accent in (("widetilde", "˜"), ("tilde", "˜"), ("breve", "⌣")):
        value = re.sub(
            r"\\" + command + r"\{([^{}]*)\}",
            lambda m, accent=accent: m[1] + accent,
            value,
        )
    value = value.replace(r"\smile", "⌣")
    value = re.sub(r"\\overset\{([^{}]*)\}\{([^{}]*)\}", r"\2\1", value)
    value = re.sub(r"\\(?:bar|overline)\{([^{}]*)\}", lambda m: m[1] + "̄", value)
    formulas = []

    def protect_math(match):
        formulas.append(match[0])
        return f"PAPERFETCHFORMULA{len(formulas) - 1}END"

    value = re.sub(r"\$([^$]+)\$", protect_math, value)
    value = value.replace("_", "SCRIPTSUBTOKEN")
    tokens = _INLINE_MARKDOWN.parseInline(value)[0].children or []
    value = "".join(
        token.content
        for token in tokens
        if token.type in {"text", "code_inline", "html_inline"}
    )
    value = value.replace("SCRIPTSUBTOKEN", "_")
    for index, formula in enumerate(formulas):
        value = value.replace(f"PAPERFETCHFORMULA{index}END", formula)
    value = value.replace("*", "LITERALASTERISK")
    for command, symbol in {
        "mu": "μ",
        "alpha": "α",
        "beta": "β",
        "gamma": "γ",
        "delta": "δ",
        "Delta": "Δ",
        "sigma": "σ",
        "rho": "ρ",
        "lambda": "λ",
        "pi": "π",
        "Omega": "Ω",
        "omega": "ω",
        "theta": "θ",
        "tau": "τ",
        "varepsilon": "ε",
        "times": "×",
        "cdot": "·",
        "sim": "∼",
        "sum": "∑",
        "int": "∫",
        "xi": "ξ",
        "pm": "±",
        "leq": "≤",
        "geq": "≥",
        "AA": "Å",
        "partial": "∂",
        "hslash": "ℏ",
        "ldots": "...",
        "phi": "φ",
        "chi": "χ",
        "ell": "l",
    }.items():
        value = re.sub(
            r"\\" + command + r"(?![A-Za-z])", lambda _, symbol=symbol: symbol, value
        )
    value = re.sub(
        r"\\(?:text|mathrm|mathbf|mathit|textrm|operatorname|mathcal)\s*\{([^{}]*)\}",
        r"\1",
        value,
    )
    value = re.sub(r"\\overset\{([^{}]*)\}\{([^{}]*)\}", r"\2\1", value)
    value = re.sub(r"\\(?:left|right|displaystyle|limits)(?![A-Za-z])", "", value)
    value = re.sub(r"\\(?:begin|end)\{[^{}]+\}", "", value)
    value = value.replace(r"\\", "").replace("&", "")
    value = re.sub(r"\\[,;! ]", "", value)
    value = value.replace("\\%", "%").replace("\\_", "_")
    return _table_cell(math_semantic_key(value))


def source_table_grid(table):
    rows = table.select("tr") or table.select("row")
    if "_source_grid" in table.__dict__:
        cells = table.find_all(["th", "td", "entry"])
        return [
            (
                rows[row],
                [cells[index] if index is not None else None for index in indexes],
            )
            for row, indexes in table.__dict__["_source_grid"]
        ]
    # The unit contract uses literal rectangular fragments, never span expansion.
    assert not table.select("[rowspan], [colspan], [namest], [morerows]")
    return [(row, row.find_all(["td", "th", "entry"], recursive=False)) for row in rows]


FIGURE_SELECTORS = {
    "acs": ".article-body .fig.fig-section",
    "aip": '[data-widgetname="ArticleFulltext"] .fig',
    "ams": "#articleBody .figure",
    "annualreviews": "#itemFullTextId .figure",
    "arxiv": "article figure.ltx_figure",
    "copernicus": "body fig",
    "elsevier": "figure",
    "frontiers": "body fig",
    "ieee": ".figure",
    "iop": 'figure[data-toolbar-type="figure"]',
    "mdpi": ".html-fig-wrap",
    "oxfordacademic": '[data-widgetname="ArticleFulltext"] .fig',
    "plos": "body fig",
    "pnas": "#bodymatter figure.graphic",
    "royalsocietypublishing": ".article-body .fig",
    "science": "#bodymatter figure.graphic",
    "springer": ".main-content figure",
    "tandf": ".hlFld-Fulltext .figureView",
    "wiley": ".article-section__full figure",
}


def source_figures(fixture, soup):
    result = []
    seen = set()
    for figure in soup.select(FIGURE_SELECTORS[fixture.provider]):
        if any(
            p.get("aria-hidden") == "true" or "fig-modal" in p.get("class", [])
            for p in [figure, *figure.parents]
        ):
            continue
        if figure.find("table") is not None or "ltx_table" in figure.get("class", []):
            continue
        caption = figure.select_one(
            "figcaption, caption, .caption, .fig-caption, .figcaption, .html-fig_description, .captionText"
        )
        key = figure.get("id") or (
            caption.get_text(" ", strip=True) if caption else str(figure)
        )
        if key in seen:
            continue
        seen.add(key)
        result.append((figure, caption))
    return result


def source_caption_runs(caption):
    if caption is None:
        return []
    caption = deepcopy(caption)
    for noise in caption.select(
        "script, style, .off-screen, button, .figure-extra, .print-hide, .open-figure-link, .graphic-download-links"
    ):
        noise.decompose()
    for formula in caption.select(
        "[role=math], mjx-container, math, tex-math, .inline-formula, inline-formula, .InlineEquation, .inline-equation"
    ):
        if formula.parent is not None:
            formula.replace_with("\u241e")
    preserve_dom_scripts(caption)
    runs = []
    for string in caption.strings:
        text = re.sub(
            r"^\s*(?:Figure|Fig\.)\s*\d+[A-Za-z]?\s*[.:]?\s*",
            "",
            str(string),
            flags=re.I,
        )
        text = re.sub(r"\[Colou?r figure can be viewed at.*", "", text, flags=re.I)
        text = re.sub(r"\b[Rr]ef\.\s*$", "", text)
        if string.find_parent(
            "a", href=re.compile(r"^https?://(?:www\.)?wileyonlinelibrary\.com/?$")
        ):
            continue
        runs.extend(part.strip() for part in text.split("\u241e") if part.strip())
    return runs


def source_table_notes(fixture, soup):
    body = soup.select_one(BODY_SELECTORS[fixture.provider]) or soup
    scope = soup if fixture.provider == "elsevier" else body
    notes = scope.select(
        "table-wrap-foot, table-footnote, .table-wrap-foot, .NLM_table-wrap-foot, .tabFoot, .html-table_foot"
    )
    result = []
    seen = set()
    for note in notes:
        text = note.get_text(" ", strip=True)
        if text and text not in seen:
            seen.add(text)
            result.append(note)
    return result


def source_statements(fixture, soup):
    result = []
    seen = set()
    headings = soup.find_all(["h2", "h3", "title"])
    for heading in headings:
        label = heading.get_text(" ", strip=True).strip(" :").casefold()
        if not re.fullmatch(
            r"(?:data|code|software|data and (?:code|materials)|data, code, and materials) availability(?: statement)?",
            label,
        ):
            continue
        block = BeautifulSoup("<section></section>", "lxml").section
        block.append(deepcopy(heading))
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in {"h1", "h2", "h3", "title"}:
                break
            block.append(deepcopy(sibling))
        key = block.get_text(" ", strip=True)
        if key and key not in seen:
            seen.add(key)
            result.append(block)
    for paragraph in soup.select(
        "#acknowledgments p, #acknowledgments div[role=paragraph]"
    ):
        label = paragraph.find(["b", "strong"], recursive=False)
        if label and re.fullmatch(
            r"(?:Data|Code|Software|Data and (?:code|materials)) availability:",
            label.get_text(strip=True),
            re.I,
        ):
            key = paragraph.get_text(" ", strip=True)
            if key not in seen:
                seen.add(key)
                result.append(paragraph)
    return result


def source_formulas(fixture, soup):
    body = soup.select_one(BODY_SELECTORS[fixture.provider]) or soup
    result = []
    seen = set()
    for node in body.select("math, tex-math"):
        if node.find_parent(["math", "tex-math", "annotation-xml"]):
            continue
        if any(
            p.get("aria-hidden") == "true"
            or set(p.get("class", []))
            & {
                "ref-list",
                "ltx_bibliography",
                "ltx_authors",
                "fig-modal",
                "NLM_disp-formula-image",
            }
            for p in node.parents
        ):
            continue
        # MathJax exposes the accessible MathML once; duplicated modal/table
        # copies carry identical markup. Content facts are checked per unique
        # expression; prose/table tests separately constrain occurrence order.
        key = str(node)
        if key not in seen:
            seen.add(key)
            result.append(node)
    expected = source_object_expectations(fixture.doi, fixture.raw_path)
    by_hash = {entry["node_sha256"]: entry for entry in expected["mathml"]}
    for node in result:
        key = hashlib.sha256(str(node).encode()).hexdigest()
        if key in by_hash:
            node.__dict__["_source_mathml"] = by_hash[key]
    return result


def source_tex(node):
    """An accessibility placeholder is not a TeX representation."""
    value = str(node.get("alttext") or "").strip()
    if value.casefold() == "no alternative text available":
        value = ""
    if not value and node.name == "tex-math":
        value = node.get_text().strip()
    return value


def formula_route(node):
    if source_tex(node):
        return "tex"
    if node.name == "math" and node.get_text(strip=True):
        return "mathml"
    return "empty"


def tex_key(value):
    value = html.unescape(value).replace(r"\|", "|")
    value = re.sub(
        r"\\(?:left|right|displaystyle|textstyle|limits)(?![A-Za-z])", "", value
    )
    value = re.sub(r"(?<!\\)\\[,;! ]", "", value)
    value = re.sub(r"\{(\\(?:times|cdot))\}", r"\1", value)
    value = value.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    return re.sub(r"\s+|(?<!\\)\$", "", value)


def source_citation_targets(fixture, soup):
    references = source_references(fixture, soup)
    identities = {}
    for index, reference in enumerate(references):
        if not isinstance(reference, Tag):
            continue
        for node in [reference, *reference.find_all(id=True)]:
            if node.get("id"):
                identities[node["id"]] = index
    body = soup.select_one(BODY_SELECTORS[fixture.provider]) or soup
    result = []
    for link in body.select("a[href], xref[rid], cross-ref[refid]"):
        target = (
            link.get("rid")
            or link.get("refid")
            or urlsplit(link.get("href", "")).fragment
        )
        for key in str(target).split():
            if key in identities:
                result.append((link, identities[key], key))
    return result


def math_identifier_text(value):
    """Typography equivalence for original MathML identifiers, not an oracle renderer."""
    import unicodedata

    aliases = {
        "alpha": "α",
        "beta": "β",
        "gamma": "γ",
        "delta": "δ",
        "epsilon": "ε",
        "varepsilon": "ε",
        "zeta": "ζ",
        "eta": "η",
        "theta": "θ",
        "vartheta": "θ",
        "iota": "ι",
        "kappa": "κ",
        "lambda": "λ",
        "mu": "μ",
        "nu": "ν",
        "xi": "ξ",
        "pi": "π",
        "rho": "ρ",
        "sigma": "σ",
        "tau": "τ",
        "upsilon": "υ",
        "phi": "φ",
        "varphi": "φ",
        "chi": "χ",
        "psi": "ψ",
        "omega": "ω",
        "Gamma": "Γ",
        "Delta": "Δ",
        "Theta": "Θ",
        "Lambda": "Λ",
        "Xi": "Ξ",
        "Pi": "Π",
        "Sigma": "Σ",
        "Phi": "Φ",
        "Psi": "Ψ",
        "Omega": "Ω",
        "partial": "∂",
        "ell": "l",
        "infty": "∞",
        "pm": "±",
        "times": "×",
        "ast": "*",
        "leq": "≤",
        "le": "≤",
        "geq": "≥",
        "ge": "≥",
        "lt": "<",
        "gt": ">",
        "neq": "≠",
        "ne": "≠",
    }
    value = re.sub(r"\\([A-Za-z]+)", lambda m: aliases.get(m[1], m[0]), value)
    value = unicodedata.normalize("NFKC", html.unescape(value)).replace("−", "-")
    return re.sub(r"[\s{}\u200b\u2061\u2062\u2063\u2064]", "", value)


def source_figure_markup(fixture, figure, soup):
    markup = str(figure)
    if fixture.provider == "tandf":
        ids = {node.get("data-id") for node in figure.select("[data-id]")}
        for script in soup.find_all("script"):
            raw = script.string or script.get_text()
            match = re.search(r"tandf\.tfviewerdata\s*=\s*", raw)
            if match:
                payload, _ = json.JSONDecoder().raw_decode(raw[match.end() :])
                markup += "".join(
                    entry["content"]
                    for entry in payload.get("figures", [])
                    if entry.get("id") in ids
                )
    return markup
