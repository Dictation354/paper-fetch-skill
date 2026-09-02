from __future__ import annotations

import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from paper_fetch.extraction.html.tables import table_headers_and_data
from paper_fetch.extraction.table_grid import (
    TableCell,
    TableConversionReason,
    TableConversionStatus,
    TableRow,
    normalize_table,
)
from paper_fetch.extraction.xml_tables import parse_xml_table, parse_xml_table_groups
from paper_fetch.utils import normalize_text


def _xml_cell_text(cell: ET.Element) -> str:
    return normalize_text(" ".join(cell.itertext()))


def _normalized_xml_table(xml_text: str):
    root = ET.fromstring(xml_text)
    parsed = parse_xml_table(root, render_cell_text=_xml_cell_text)
    return normalize_table(
        parsed.rows,
        declared_width=parsed.declared_width,
        header_row_indices=tuple(
            index for index, row in enumerate(parsed.rows) if row.role == "header"
        ),
        reasons=parsed.reasons,
    )


def test_xml_table_tag_matching_preserves_supported_name_forms() -> None:
    for style, prefix in (
        ("plain", ""),
        ("clark", "{urn:paper-fetch:test}"),
        ("colon", "ce:"),
    ):
        root = ET.Element(f"{prefix}table")
        root.append(ET.Comment("non-element nodes must remain ignored"))
        tgroup = ET.SubElement(
            root,
            f"{prefix}tgroup",
            {"cols": "1"},
        )
        ET.SubElement(
            tgroup,
            f"{prefix}colspec",
            {"colname": "c1"},
        )
        row = ET.SubElement(tgroup, f"{prefix}row")
        entry = ET.SubElement(
            row,
            f"{prefix}entry",
            {"colname": "c1"},
        )
        entry.text = style

        parsed = parse_xml_table(root, render_cell_text=_xml_cell_text)

        assert parsed.declared_width == 1
        assert parsed.rows == (
            TableRow(
                cells=(TableCell(style, column_start=0),),
                role="body",
            ),
        )


def test_html_jats_and_cals_share_multilevel_header_contract() -> None:
    html = BeautifulSoup(
        """
<table>
  <thead>
    <tr><th rowspan="2">Region</th><th colspan="2">Period</th></tr>
    <tr><th>Mean</th><th>Trend</th></tr>
  </thead>
  <tbody><tr><td>Asia</td><td>10</td><td>+1</td></tr></tbody>
</table>
""",
        "html.parser",
    )
    assert html.table is not None
    html_headers, html_data, html_rectangular = table_headers_and_data(html.table)
    html_rows = tuple(
        tuple(normalize_text(str(cell.get("text") or "")) for cell in row)
        for row in html_data
    )

    jats = _normalized_xml_table(
        """
<table>
  <thead>
    <tr><th rowspan="2">Region</th><th colspan="2">Period</th></tr>
    <tr><th>Mean</th><th>Trend</th></tr>
  </thead>
  <tbody><tr><td>Asia</td><td>10</td><td>+1</td></tr></tbody>
</table>
"""
    )
    cals = _normalized_xml_table(
        """
<table>
  <tgroup cols="3">
    <colspec colname="c1"/><colspec colname="c2"/><colspec colname="c3"/>
    <thead>
      <row>
        <entry colname="c1" morerows="1">Region</entry>
        <entry namest="c2" nameend="c3">Period</entry>
      </row>
      <row><entry colname="c2">Mean</entry><entry colname="c3">Trend</entry></row>
    </thead>
    <tbody>
      <row>
        <entry colname="c1">Asia</entry>
        <entry colname="c2">10</entry>
        <entry colname="c3">+1</entry>
      </row>
    </tbody>
  </tgroup>
</table>
"""
    )

    expected_headers = ("Region", "Period / Mean", "Period / Trend")
    expected_rows = (("Asia", "10", "+1"),)
    assert html_rectangular
    assert tuple(html_headers) == expected_headers
    assert html_rows == expected_rows
    assert jats.headers == expected_headers
    assert jats.rows == expected_rows
    assert cals.headers == expected_headers
    assert cals.rows == expected_rows
    assert jats.status == TableConversionStatus.NORMALIZED
    assert cals.status == TableConversionStatus.NORMALIZED
    assert TableConversionReason.MERGED_SPAN_EXPANDED in jats.reasons
    assert TableConversionReason.MERGED_SPAN_EXPANDED in cals.reasons
    assert not jats.layout_degraded
    assert not cals.layout_degraded


def test_full_width_groups_are_normalized_without_layout_degradation() -> None:
    rows = (
        TableRow(
            cells=(TableCell("Group A", colspan=3, is_header=True),),
            role="header",
        ),
        TableRow(
            cells=tuple(
                TableCell(value, is_header=True) for value in ("Name", "Low", "High")
            ),
        ),
        TableRow(cells=tuple(TableCell(value) for value in ("Item 1", "1", "2"))),
        TableRow(cells=(TableCell("Group B", colspan=3, is_header=True),)),
        TableRow(cells=tuple(TableCell(value) for value in ("Item 2", "3", "4"))),
    )

    normalized = normalize_table(rows, header_row_indices=(0,))

    assert normalized.prefix_rows == ("Group A",)
    assert normalized.headers == ("Name", "Low", "High")
    assert normalized.rows == (
        ("Item 1", "1", "2"),
        ("Group B", "", ""),
        ("Item 2", "3", "4"),
    )
    assert normalized.status == TableConversionStatus.NORMALIZED
    assert TableConversionReason.FULL_WIDTH_GROUP_NORMALIZED in normalized.reasons
    assert not normalized.layout_degraded


def test_overlapping_named_columns_fall_back_without_dropping_cell_text() -> None:
    normalized = _normalized_xml_table(
        """
<table>
  <tgroup cols="2">
    <colspec colname="c1"/><colspec colname="c2"/>
    <thead>
      <row><entry colname="c1">A</entry><entry colname="c1">B</entry></row>
    </thead>
    <tbody>
      <row><entry colname="c1">1</entry><entry colname="c2">2</entry></row>
    </tbody>
  </tgroup>
</table>
"""
    )

    assert normalized.status == TableConversionStatus.FALLBACK
    assert not normalized.is_rectangular
    assert normalized.headers == ("A", "B")
    assert normalized.rows == (("1", "2"),)
    assert TableConversionReason.OVERLAPPING_SPAN in normalized.reasons


def test_invalid_cals_dimensions_degrade_safely_without_crashing() -> None:
    normalized = _normalized_xml_table(
        """
<table>
  <tgroup cols="invalid">
    <colspec colname="c1"/><colspec colname="c2"/>
    <thead><row><entry colname="c1">A</entry><entry colname="c2">B</entry></row></thead>
    <tbody>
      <row>
        <entry colname="c1" morerows="invalid">1</entry>
        <entry colname="c2">2</entry>
      </row>
    </tbody>
  </tgroup>
</table>
"""
    )

    assert normalized.is_rectangular
    assert normalized.headers == ("A", "B")
    assert normalized.rows == (("1", "2"),)
    assert normalized.status == TableConversionStatus.LAYOUT_DEGRADED
    assert TableConversionReason.INVALID_DECLARED_WIDTH in normalized.reasons
    assert TableConversionReason.INVALID_SPAN in normalized.reasons


def test_ragged_grid_fallback_preserves_headerless_first_row() -> None:
    rows = (
        TableRow(cells=(TableCell("first"), TableCell("1"))),
        TableRow(cells=(TableCell("second"),)),
    )

    normalized = normalize_table(rows)

    assert normalized.status == TableConversionStatus.FALLBACK
    assert normalized.headers == ()
    assert normalized.rows == (("first", "1"), ("second",))
    assert TableConversionReason.RAGGED_GRID in normalized.reasons


def test_table_dimension_limit_uses_readable_fallback() -> None:
    rows = (
        TableRow(
            cells=tuple(TableCell(f"c{index}", is_header=True) for index in range(257)),
            role="header",
        ),
        TableRow(cells=tuple(TableCell(str(index)) for index in range(257))),
    )

    normalized = normalize_table(rows, header_row_indices=(0,))

    assert normalized.status == TableConversionStatus.FALLBACK
    assert len(normalized.headers) == 257
    assert len(normalized.rows[0]) == 257
    assert TableConversionReason.DIMENSION_LIMIT in normalized.reasons


def test_cals_tgroups_are_parsed_with_independent_column_definitions() -> None:
    root = ET.fromstring(
        """
<table>
  <tgroup cols="2">
    <colspec colname="a1"/><colspec colname="a2"/>
    <thead>
      <row><entry namest="a1" nameend="a2">(a) WBGT</entry></row>
      <row><entry colname="a1">Day</entry><entry colname="a2">Risk</entry></row>
    </thead>
    <tbody><row><entry colname="a1">1</entry><entry colname="a2">Low</entry></row></tbody>
  </tgroup>
  <tgroup cols="3">
    <colspec colname="b1"/><colspec colname="b2"/><colspec colname="b3"/>
    <thead>
      <row><entry namest="b1" nameend="b3">(b) T</entry></row>
      <row>
        <entry colname="b1">Day</entry><entry colname="b2">Min</entry><entry colname="b3">Max</entry>
      </row>
    </thead>
    <tbody>
      <row><entry colname="b1">2</entry><entry colname="b2">10</entry><entry colname="b3">20</entry></row>
    </tbody>
  </tgroup>
</table>
"""
    )

    parsed_groups = parse_xml_table_groups(root, render_cell_text=_xml_cell_text)
    normalized_groups = [
        normalize_table(
            parsed.rows,
            declared_width=parsed.declared_width,
            header_row_indices=tuple(
                index for index, row in enumerate(parsed.rows) if row.role == "header"
            ),
            reasons=parsed.reasons,
        )
        for parsed in parsed_groups
    ]

    assert [parsed.declared_width for parsed in parsed_groups] == [2, 3]
    assert [group.prefix_rows for group in normalized_groups] == [
        ("(a) WBGT",),
        ("(b) T",),
    ]
    assert [group.headers for group in normalized_groups] == [
        ("Day", "Risk"),
        ("Day", "Min", "Max"),
    ]
    assert [group.rows for group in normalized_groups] == [
        (("1", "Low"),),
        (("2", "10", "20"),),
    ]
    assert all(not group.layout_degraded for group in normalized_groups)


def test_table_without_tgroup_remains_one_compatible_group() -> None:
    root = ET.fromstring(
        """
<table>
  <thead><tr><th>Name</th><th>Value</th></tr></thead>
  <tbody><tr><td>A</td><td>1</td></tr></tbody>
</table>
"""
    )

    legacy = parse_xml_table(root, render_cell_text=_xml_cell_text)
    groups = parse_xml_table_groups(root, render_cell_text=_xml_cell_text)

    assert groups == (legacy,)
