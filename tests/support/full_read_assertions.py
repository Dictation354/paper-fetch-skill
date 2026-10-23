"""Source-driven list contracts shared by full-paper review regressions."""

import re
from collections import Counter
from bs4 import BeautifulSoup
from tests.support.reviewed_publisher_content import _words
from tests.support.canonical_content import BODY_SELECTORS


def assert_source_list_items(body, rendered):
    """Locate source items in actual body lists, including their nested level."""
    sources = body.select(
        'ol.label-provided, ol.NLM_list, ul.NLM_list, ol.content-list, ul.content-list, ul.unordered-list, dl.html-simple, dl.html-order, table.listgroup, [role="list"]'
    )
    if not sources:
        sources = body.select("ol, ul")
    sources = [
        node
        for node in sources
        if not any(
            re.search(
                r"referenc|bibliograph|ref-list",
                " ".join(parent.get("class", [])) + " " + str(parent.get("id", "")),
                re.I,
            )
            for parent in [node, *node.parents]
            if getattr(parent, "attrs", None)
        )
    ]
    assert sources
    main = BeautifulSoup(str(rendered), "lxml")
    references = next(
        (h for h in main.select("h2") if h.get_text().startswith("References")), None
    )
    if references:
        for sibling in list(references.next_siblings):
            sibling.extract()
    actual = main.select("li")
    used = set()
    checked = 0
    for source in sources:
        ordered = source.name == "ol" or "html-order" in source.get("class", [])
        supplied = "label-provided" in source.get("class", []) or any(
            n.get("data-list-item-label")
            for n in source.find_all("li", recursive=False)
        )
        if supplied:
            ordered = False
        if source.name == "table":
            items = [
                row for row in source.select("tr") if row.find_parent("table") is source
            ]
            labels = [item.find(["td", "th"]).get_text(strip=True) for item in items]
            # Single letter-and-bold tables are scientific subsection headings.
            if (
                len(items) == 1
                and re.fullmatch(r"[a-z]\)", labels[0])
                and items[0].find(["b", "strong"])
            ):
                continue
            ordered = all(re.fullmatch(r"\(?\d+[.)]?", label) for label in labels)
        elif source.name == "dl":
            items = source.find_all("dd", recursive=False)
        elif source.get("role") == "list":
            items = source.find_all(attrs={"role": "listitem"}, recursive=False)
            labels = [item.find(class_="label", recursive=False) for item in items]
            ordered = bool(items) and all(
                label and re.fullmatch(r"\(?\d+[.)]?", label.get_text(strip=True))
                for label in labels
            )
        else:
            items = source.find_all("li", recursive=False)
        for item in items:
            text = next(
                (
                    str(s)
                    for s in item.strings
                    if len(_words(str(s))) >= 8
                    and not s.find_parent(["math", "annotation", "tex-math"])
                ),
                None,
            )
            if text is None:
                text = next(
                    (
                        str(s)
                        for s in item.strings
                        if _words(str(s))
                        and not s.find_parent(["math", "annotation", "tex-math"])
                    ),
                    item.get_text(" ", strip=True),
                )
            anchor = _words(text)
            nested = any(parent in sources for parent in source.parents)
            matches = [
                n
                for n in actual
                if id(n) not in used
                and n.parent.name == ("ol" if ordered else "ul")
                and bool(n.find_parent("li")) == nested
                and anchor in _words(n.get_text())
            ]
            assert matches, (
                source.name,
                "ordered" if ordered else "unordered",
                text[:180],
            )
            explicit_label = item.get("data-list-item-label")
            if explicit_label and not re.fullmatch(r"\(?\d+[.)]?", explicit_label):
                assert matches[0].get_text(strip=True).startswith(explicit_label)
            cursor = 0
            actual_item = _words(matches[0].get_text())
            for run in item.strings:
                if run.find_parent(["math", "annotation", "tex-math"]) or (
                    item.name in {"li", "dd"} and run.find_parent(item.name) is not item
                ):
                    continue
                if run.find_parent(class_="link") and run.find_parent(class_="formula"):
                    continue
                expected = _words(str(run))
                if len(expected) < 8:
                    continue
                found = actual_item.find(expected, cursor)
                assert found >= 0, str(run)
                cursor = found + len(expected)
            used.add(id(matches[0]))
            checked += 1
    assert checked


def assert_article_lists(fixture, source, rendered):
    body = source.select_one(BODY_SELECTORS[fixture.provider]) or source
    assert_source_list_items(body, rendered)


def assert_equation_rows(source, markdown):
    """Check each source cell in its own aligned row, including continuation rows."""
    from tests.support.canonical_content import math_identifier_text

    groups = []
    for table in source.select("table.ltx_eqn_table"):
        for group in table.find_all("tbody", recursive=False) or [table]:
            rows = []
            for row in group.find_all("tr"):
                if row.find_parent("table") is not table:
                    continue
                cells = [
                    c
                    for c in row.find_all(["td", "th"], recursive=False)
                    if c.find("math") and "ltx_eqn_eqno" not in c.get("class", [])
                ]
                if cells:
                    rows.append(cells)
            if rows:
                groups.append((group, rows))
    blocks = [
        m["body"].strip()
        for m in re.finditer(
            r"(?ms)^(?P<indent>[ \t]*)\$\$[ \t]*\n(?P<body>.*?)\n(?P=indent)\$\$",
            markdown,
        )
        if m["body"].lstrip().startswith(r"\begin{aligned}")
    ]
    assert groups and len(groups) == len(blocks), (len(groups), len(blocks))
    for (group, rows), block in zip(groups, blocks, strict=True):
        for label in group.select(".ltx_eqn_eqno"):
            assert r"\tag{" + label.get_text(strip=True).strip("()") in block
        body = block[len(r"\begin{aligned}") : block.rfind(r"\end{aligned}")]
        actual = [[]]
        buffer = ""
        cursor = 0
        stack = []
        for token in re.finditer(
            r"\\begin\{([^}]+)\}|\\end\{([^}]+)\}|\\\\|(?<!\\)&", body
        ):
            buffer += body[cursor : token.start()]
            if token[1]:
                stack.append(token[1])
            elif token[2]:
                assert stack and stack.pop() == token[2]
            elif not stack:
                actual[-1].append(buffer)
                buffer = ""
                if token[0] == r"\\":
                    actual.append([])
                cursor = token.end()
                continue
            buffer += token[0]
            cursor = token.end()
        actual[-1].append(buffer + body[cursor:])
        assert len(rows) == len(actual), (len(rows), len(actual))
        for original, rendered in zip(rows, actual, strict=True):
            assert len(original) == len(rendered), (len(original), len(rendered))
            for cell, latex in zip(original, rendered, strict=True):
                normalized = math_identifier_text(latex)
                # MathML sub/sup child order and equivalent TeX script order
                # differ. Check multiplicity inside the corresponding cell;
                # row and column order are asserted above.
                expected = Counter(
                    "".join(
                        math_identifier_text(symbol.get_text())
                        for symbol in cell.select("math mi")
                    )
                )
                assert not (expected - Counter(normalized)), (expected, latex)


def assert_explicit_source_breaks(source, rendered, *, tables_only=False):
    """Match source processing instructions to visible breaks in the same block."""
    from bs4 import NavigableString, ProcessingInstruction, Tag
    from tests.support.reviewed_publisher_content import _words

    checked = 0
    for directive in source.find_all(
        string=lambda s: isinstance(s, ProcessingInstruction)
    ):
        if not re.search(r"newline|hfill.*break|\\\\", str(directive)):
            continue
        if tables_only and not directive.find_parent(["td", "th", "entry"]):
            continue
        if tables_only and (
            not re.search(r"hfill.*break", str(directive))
            or directive.find_parent("thead")
        ):
            continue
        left, right = directive.previous_sibling, directive.next_sibling
        while isinstance(left, ProcessingInstruction):
            left = left.previous_sibling
        while isinstance(right, ProcessingInstruction):
            right = right.next_sibling
        if left is None or right is None:
            continue
        before = left.get_text() if isinstance(left, Tag) else str(left)
        after = right.get_text() if isinstance(right, Tag) else str(right)
        before, after = _words(before[-45:]), _words(after[:45])
        if not before or not after:
            continue
        matches = []
        for br in rendered.select("td br, th br" if tables_only else "br"):
            block = br.find_parent(["p", "td", "th", "li"])
            if block is None:
                continue
            descendants = list(block.descendants)
            index = next(i for i, child in enumerate(descendants) if child is br)
            preceding = "".join(
                str(n) for n in descendants[:index] if isinstance(n, NavigableString)
            )
            following = "".join(
                str(n)
                for n in descendants[index + 1 :]
                if isinstance(n, NavigableString)
            )
            if before in _words(preceding) and after in _words(following):
                matches.append(br)
        # Header labels may be flattened by the existing grid normalization;
        # body cell paragraphs must retain their explicit break.
        if tables_only and any(
            before in _words(n.get_text()) and after in _words(n.get_text())
            for n in rendered.select("th")
        ):
            continue
        assert matches, (before, after)
        checked += 1
    assert checked


def assert_source_declarations(fixture, source, article):
    """Read retained scientific declaration headings/prose from original sources."""
    from tests.support.reviewed_publisher_content import _words
    from tests.support.markdown_presentation import visible_markdown

    roots = source.select(BODY_SELECTORS[fixture.provider]) + source.select(
        "back, ack, acknowledgment, .html-back, #acknowledgments, #acknowledgements"
    )
    names = {"h2", "h3", "h4", "h5", "h6", "title", "section-title"}
    for heading in source.find_all(list(names)):
        label = (
            " ".join(heading.get_text(" ", strip=True).split()).strip(" .:").casefold()
        )
        if not re.fullmatch(
            r"acknowledg(?:e)?ments?(?: and disclosure of funding)?|agradecimientos|author(?:s[’'])? contributions|authors[’'] roles|funding(?: information)?|financial support|competing interests|conflicts? of interests?(?: statement)?|disclosure statement",
            label,
        ):
            continue
        if not any(root is heading or root in heading.parents for root in roots):
            continue
        if heading.find_parent(
            ["ref", "ref-list", "bib-reference", "nav", "header", "footer"]
        ):
            continue
        matches = [s for s in article.sections if _words(s.heading) == _words(label)]
        assert matches and all(s.kind == "body" for s in matches), (fixture.doi, label)
        visible = " ".join(
            visible_markdown(s.text)
            for s in [
                *matches,
                *(
                    s
                    for s in article.sections
                    if s.kind in {"data_availability", "code_availability"}
                ),
            ]
        )
        for following in heading.next_elements:
            if getattr(following, "name", None) in names:
                break
            if not isinstance(following, str) or len(str(following).split()) < 6:
                continue
            if following.find_parent(["math", "annotation", "script", "style"]):
                continue
            assert _words(str(following)) in _words(visible), (
                fixture.doi,
                label,
                str(following),
            )
