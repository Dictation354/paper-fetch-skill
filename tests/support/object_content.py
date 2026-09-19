"""Object-scoped assertions against original publisher content."""

from contextlib import nullcontext
from dataclasses import dataclass
import re

from tests.support.canonical_content import (
    comparable_cell,
    source_cell_text,
    source_table_grid,
)


@dataclass
class RenderedTable:
    start: int
    end: int
    rows: list[list[str]]


def rendered_tables(markdown):
    result = []
    for match in re.finditer(r"^\|[^\n]*(?:\n\|[^\n]*)*", markdown, re.M):
        rows = [
            [
                comparable_cell(c)
                for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))
            ]
            for line in match[0].splitlines()
        ]
        result.append(RenderedTable(match.start(), match.end(), rows))
    return result


def row_matches(actual, expected, cells):
    if len(actual) < len(expected) or any(actual[len(expected) :]):
        return False
    for column, text in enumerate(expected):
        full_width = cells[column] is not None and all(
            c is cells[column] for c in cells
        )
        if full_width and column and actual[column] == "":
            continue
        if actual[column] != text:
            return False
    return True


def assert_source_tables(
    tables, markdown, subtests=None, *, prose_runs=None, provider=None
):
    groups = rendered_tables(markdown)
    # MDPI captures main tables in a trailing gallery, after appendix tables.
    # The public renderer restores main tables before the appendix.
    if provider == "mdpi":
        tables = sorted(
            tables,
            key=lambda t: (
                0 if t.find_parent(id=re.compile(r"^FiguresandTables?$")) else 1
            ),
        )

    def cell_text(cell):
        return source_cell_text(
            cell,
            citation_superscript=provider == "science",
            title_case_headings=provider == "annualreviews",
            empty_bibr=provider == "copernicus",
        )

    next_group = 0
    checked = 0
    for table_index, table in enumerate(tables, 1):
        grid = source_table_grid(table)
        is_list = (
            table.select_one(".list-td") is not None
            or table.find_parent(class_="list-paired") is not None
            or table.find_parent(id="html-glossary") is not None
        )
        anchors = [
            (cells, [comparable_cell(cell_text(c)) if c else "" for c in cells])
            for row, cells in grid
            if len(cells) > 1
            and not row.find_parent("thead")
            and not all(c is not None and c.name == "th" for c in cells)
            and not all(c is cells[0] for c in cells)
        ]
        if not anchors and not is_list:
            anchors = [
                (cells, [comparable_cell(cell_text(c)) if c else "" for c in cells])
                for row, cells in grid
                if len(cells) > 1 and not row.find_parent("thead")
            ]
            if not anchors:
                anchors = [
                    (cells, [comparable_cell(cell_text(c)) if c else "" for c in cells])
                    for _, cells in grid
                    if len(cells) > 1
                ]
        if not is_list and anchors:
            cells, expected = anchors[0]
            group_index = next(
                (
                    i
                    for i in range(next_group, len(groups))
                    if any(row_matches(r, expected, cells) for r in groups[i].rows)
                ),
                None,
            )
            assert group_index is not None, (
                table_index,
                "missing or reused table",
                expected,
            )
            count = max(1, len(table.find_all("tgroup", recursive=False)))
            owned = groups[group_index : group_index + count]
            assert len(owned) == count, (table_index, "missing split table")
            rows = [r for group in owned for r in group.rows]
            start = groups[group_index - 1].end if group_index else 0
            end = (
                groups[group_index + count].start
                if group_index + count < len(groups)
                else len(markdown)
            )
            scope = markdown[start:end]
            assert_table_notes(table, markdown[owned[-1].end : end])
            next_group = group_index + count
            if prose_runs is not None:
                if provider == "elsevier" and table.find_parent("floats"):
                    root = table
                    while root.parent is not None:
                        root = root.parent
                    anchor = root.find("float-anchor", refid=table.get("id"))
                    callout = (
                        anchor
                        if anchor is not None
                        else root.find("cross-ref", refid=table.get("id"))
                    )
                    if callout is not None:
                        list_node = callout.find_parent("list")
                        position_node = (
                            list_node
                            if list_node is not None
                            else callout.find_parent("para")
                        )
                        if position_node is not None:
                            assert_object_position(
                                position_node,
                                markdown,
                                owned[0].start,
                                owned[-1].end,
                                prose_runs,
                            )
                elif not table.find_parent(id=re.compile(r"^FiguresandTables?$")):
                    assert_object_position(
                        table, markdown, owned[0].start, owned[-1].end, prose_runs
                    )
        else:
            # Semantic lists and one-column tables have no pipe-table contract.
            # They retain source-order text checks rather than claiming a grid.
            scope = markdown
            rows = []
        comparable_markdown = "".join(
            comparable_cell(line) for line in scope.splitlines()
        )
        cursor = 0
        for row_index, (row, cells) in enumerate(grid, 1):
            expected = [comparable_cell(cell_text(c)) if c else "" for c in cells]
            with (
                subtests.test(table=table_index, row=row_index)
                if subtests
                else nullcontext()
            ):
                if is_list:
                    for cell in row.find_all(["td", "th"], recursive=False):
                        if "list-td" not in cell.get("class", []):
                            assert (
                                comparable_cell(cell_text(cell)) in comparable_markdown
                            )
                elif row.find_parent("thead") or all(
                    c is not None and c.name == "th" for c in cells
                ):
                    for text in expected:
                        assert text in comparable_markdown, (
                            table_index,
                            row_index,
                            text,
                        )
                    if len(cells) > 1 and not all(c is cells[0] for c in cells):
                        assert any(
                            len(actual) >= len(expected)
                            and all(
                                text in actual[col] for col, text in enumerate(expected)
                            )
                            for actual in rows
                        ), (table_index, "header columns", expected)
                elif len(cells) == 1:
                    assert expected[0] in comparable_markdown, (
                        table_index,
                        row_index,
                        expected,
                    )
                else:
                    matched = next(
                        (
                            i
                            for i in range(cursor, len(rows))
                            if row_matches(rows[i], expected, cells)
                        ),
                        None,
                    )
                    assert matched is not None, (
                        table_index,
                        row_index,
                        expected,
                        rows[cursor : cursor + 2],
                    )
                    cursor = matched + 1
                checked += 1
    return checked


def image_matches_source(url, asset, original, provider):
    import html
    from urllib.parse import parse_qs, unquote, urlsplit

    scope = unquote(html.unescape(original)).lower()
    origins = [url]
    if asset is not None:
        origins += [
            asset.original_url or "",
            asset.source_href or "",
            asset.download_url or "",
        ]
    for origin in origins:
        origin = unquote(html.unescape(str(origin))).lower()
        filename = urlsplit(origin).path.rsplit("/", 1)[-1]
        if origin and (
            origin in scope
            or (
                re.search(r"\.(?:png|jpe?g|gif|webp|svg|tiff?)$", filename)
                and filename in scope
            )
        ):
            return True
        if provider == "frontiers" and filename and filename.rsplit(".", 1)[0] in scope:
            return True
        if provider == "plos":
            from bs4 import BeautifulSoup

            parts = urlsplit(origin)
            query = parse_qs(parts.query)
            source = BeautifulSoup(scope, "lxml")
            formula_ids = {
                str(node.get("xlink:href") or node.get("href") or "").removeprefix(
                    "info:doi/"
                )
                for node in source.find_all("inline-graphic")
                if node.find_parent("inline-formula") is not None
            }
            graphic_ids = {
                str(node.get("xlink:href") or node.get("href") or "").removeprefix(
                    "info:doi/"
                )
                for node in source.find_all("graphic")
            }
            asset_id = (query.get("id") or [""])[0]
            journal = asset_id.split("journal.", 1)[-1].split(".", 1)[0]
            route = {
                "pcbi": "ploscompbiol",
                "pbio": "plosbiology",
                "pone": "plosone",
                "pgen": "plosgenetics",
                "ppat": "plospathogens",
                "pntd": "plosntds",
                "pmed": "plosmedicine",
            }.get(journal)
            if (
                parts.scheme != "https"
                or parts.hostname != "journals.plos.org"
                or not route
            ):
                continue
            if (
                parts.path == f"/{route}/article/file"
                and query.get("type") == ["thumbnail"]
                and asset_id in formula_ids
            ) or (
                parts.path == f"/{route}/article/figure/image"
                and query.get("size") == ["large"]
                and asset_id in graphic_ids
            ):
                return True
    return False


def assert_figure_bindings(fixture, soup, article, markdown):
    from tests.support.canonical_content import (
        source_figures,
        source_figure_markup,
        source_caption_runs,
        source_prose_blocks,
    )
    from tests.support.scientific_content import scientific_text_key

    figures = source_figures(fixture, soup)
    prose_runs = [r for _, runs in source_prose_blocks(fixture, soup) for r in runs]
    images = list(re.finditer(r"!\[([^\]]*)\]\(([^\s)]+)\)", markdown))
    blocks = list(re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", markdown))
    owners = {}
    for index, (figure, _) in enumerate(figures):
        original = source_figure_markup(fixture, figure, soup)
        owned = []
        for image_index, image in enumerate(images):
            asset = next(
                (a for a in article.assets if str(a.path or a.url or "") == image[2]),
                None,
            )
            if image_matches_source(image[2], asset, original, fixture.provider):
                owned.append(image_index)
        if owned:
            owners[index] = owned
    checked = 0
    for index, (figure, caption) in enumerate(figures):
        runs = [scientific_text_key(r) for r in source_caption_runs(caption)]
        runs = [r for r in runs if r]
        if not runs:
            continue
        own = owners.get(index, [])
        # LaTeXML panel figures share an outer figure's image/caption group.
        parent = figure.find_parent("figure")
        if parent is not None:
            parent_index = next(
                (i for i, (f, _) in enumerate(figures) if f is parent), None
            )
            if parent_index is not None:
                own = sorted(set(own) | set(owners.get(parent_index, [])))
        if figure.find(["img", "graphic"]) is not None:
            assert own, (fixture.doi, index + 1, "no own image")
        if not own:
            # Text-only figure objects retain the separate caption assertion.
            continue
        foreign = {
            i for owner, indices in owners.items() if owner != index for i in indices
        } - set(own)
        own_blocks = [
            i
            for i, b in enumerate(blocks)
            if any(b.start() <= images[j].start() < b.end() for j in own)
        ]
        foreign_blocks = {
            i
            for i, b in enumerate(blocks)
            if any(b.start() <= images[j].start() < b.end() for j in foreign)
        }
        assert own_blocks, (fixture.doi, index + 1, "unparsed image block")
        windows = []
        for block_index in own_blocks:
            # A caption may precede or follow a panel group, but cannot cross
            # an image belonging exclusively to another source figure.
            lower = max((i for i in foreign_blocks if i < block_index), default=-1) + 1
            upper = min(
                (i for i in foreign_blocks if i > block_index), default=len(blocks)
            )
            windows.append((lower, upper))
        matches = []
        for lower, upper in windows:
            rendered = scientific_text_key(
                "\n\n".join(b[0] for b in blocks[lower:upper])
            )
            cursor = 0
            for run in runs:
                pos = rendered.find(run, cursor)
                if pos < 0:
                    break
                cursor = pos + len(run)
            else:
                matches.append((lower, upper))
        assert matches, (
            fixture.doi,
            index + 1,
            "caption separated from its own asset",
            runs[:2],
        )
        source_label = figure.select_one(
            ".fig-label, label, .ltx_tag_figure, .html-fig_label"
        )
        label_text = (
            source_label.get_text(" ", strip=True)
            if source_label is not None
            else (caption.get_text(" ", strip=True) if caption is not None else "")
        )
        number_pattern = (
            r"(?:fig(?:ure)?\.?)[\s\u00a0]*([A-Z]?\d+[A-Za-z]?(?:\.\d+)?)(?!\w)"
        )
        label = re.match(number_pattern, label_text, re.I)
        if label:
            labels = [images[j][1] for j in own]
            longest = max(runs, key=len)
            labels += [
                b[0]
                for lower, upper in matches
                for b in blocks[lower:upper]
                if longest in scientific_text_key(b[0])
            ]
            assert any(
                m[1].casefold() == label[1].casefold()
                for text in labels
                for m in re.finditer(number_pattern, text, re.I)
            ), (fixture.doi, index + 1, "figure number lost or reassigned", label[1])
        inline_assets = [
            a
            for a in article.assets
            if a.render_state == "inline"
            and any(str(a.path or a.url or "") == images[j][2] for j in own)
        ]
        if inline_assets and not figure.find_parent("floats"):
            position_node = parent if parent is not None else figure
            assert_object_position(
                position_node,
                markdown,
                images[min(own)].start(),
                images[max(own)].end(),
                prose_runs,
            )
        checked += 1
    return checked


def source_object_neighbors(node, prose_runs):
    """Nearest retained paragraph text on either side of a DOM object."""
    from bs4 import Tag
    from tests.support.scientific_content import scientific_text_key

    retained = set(prose_runs)
    result = []
    for direction in ("previous_siblings", "next_siblings"):
        current = node
        found = None
        if direction == "previous_siblings" and node.name in {"para", "list"}:
            found = next(
                (
                    str(t).strip()
                    for t in reversed(list(node.strings))
                    if str(t).strip() in retained
                    and len(scientific_text_key(str(t))) >= 60
                ),
                None,
            )
        while isinstance(current, Tag) and found is None:
            for sibling in getattr(current, direction):
                strings = (
                    list(sibling.strings) if isinstance(sibling, Tag) else [sibling]
                )
                if direction == "previous_siblings":
                    strings.reverse()
                for text in strings:
                    value = str(text).strip()
                    if value in retained and len(scientific_text_key(value)) >= 60:
                        found = value
                        break
                if found is not None:
                    break
            current = current.parent
        result.append(found)
    return tuple(result)


def assert_object_position(node, markdown, start, end, prose_runs):
    from tests.support.scientific_content import scientific_text_key

    before, after = source_object_neighbors(node, prose_runs)
    if before:
        assert scientific_text_key(before) in scientific_text_key(markdown[:start]), (
            "object moved before preceding paragraph",
            node.get("id"),
            before,
        )
    if after:
        assert scientific_text_key(after) in scientific_text_key(markdown[end:]), (
            "object moved after following paragraph",
            node.get("id"),
            after,
        )
    return int(before is not None) + int(after is not None)


def assert_table_notes(table, markdown):
    from tests.support.canonical_content import source_caption_runs
    from tests.support.scientific_content import scientific_text_key

    scope = table
    notes = []
    while scope is not None:
        if len(scope.find_all("table")) > 1:
            break
        notes = scope.select(
            "table-wrap-foot, table-footnote, .table-wrap-foot, .NLM_table-wrap-foot, .tabFoot, .html-table_foot"
        )
        if notes:
            break
        scope = scope.parent
    rendered = scientific_text_key(markdown)
    cursor = 0
    for note in notes:
        for run in source_caption_runs(note):
            expected = scientific_text_key(run)
            if not expected:
                continue
            pos = rendered.find(expected, cursor)
            assert pos >= 0, ("note separated from its own table", table.get("id"), run)
            cursor = pos + len(expected)


def assert_source_object_link(source, markdown, *, source_url, target_id, label):
    """Require a source-registered target and every matching callout to reach it."""
    from urllib.parse import quote, urljoin

    assert source.find(id=target_id) is not None, ("unknown source target", target_id)
    urls = re.findall(r"(?<!!)\[" + re.escape(label) + r"\]\(([^\s)]+)\)", markdown)
    assert urls, ("missing object callout", target_id)
    expected = urljoin(source_url, "#" + quote(target_id))
    assert all(url == expected for url in urls), (
        "incorrect object target",
        urls,
        expected,
    )


def assert_image_occurrences(markdown, source_urls):
    """Compare source occurrences, preserving legal reuse of the same image URL."""
    from paper_fetch.models.markdown import iter_markdown_images

    urls = set(source_urls)
    actual = [image for image in iter_markdown_images(markdown) if image.url in urls]
    assert [image.url for image in actual] == list(source_urls), (
        "source image occurrences differ"
    )
    return actual


def svg_content_signature(node):
    """Independent source tree: tolerate XML name casing/namespaces, not content loss."""
    from bs4 import Comment, Tag

    attrs = tuple(
        sorted(
            (
                str(key).lower(),
                " ".join(value) if isinstance(value, list) else str(value),
            )
            for key, value in node.attrs.items()
            if not str(key).startswith("xmlns")
        )
    )
    children = tuple(
        svg_content_signature(child) if isinstance(child, Tag) else str(child)
        for child in node.contents
        if not isinstance(child, Comment)
    )
    return node.name.lower(), attrs, children


def assert_svg_content(expected_signature, body):
    """Require complete vector geometry and foreignObject/MathML source contents."""
    from bs4 import BeautifulSoup
    from xml.etree import ElementTree as ET

    root = ET.fromstring(body)
    assert root.tag == "{http://www.w3.org/2000/svg}svg", "wrong vector representation"
    actual = BeautifulSoup(body.decode("utf-8"), "xml").find("svg")
    assert actual is not None
    assert svg_content_signature(actual) == expected_signature, (
        "SVG source content changed"
    )
    for foreign in root.iter("{http://www.w3.org/2000/svg}foreignObject"):
        for child in foreign:
            assert child.tag.startswith("{http://www.w3.org/1999/xhtml}"), (
                "foreignObject HTML namespace lost"
            )
    for math in actual.find_all("math"):
        assert math.namespace == "http://www.w3.org/1998/Math/MathML", (
            "MathML namespace lost"
        )
