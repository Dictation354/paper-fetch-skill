from __future__ import annotations

from pathlib import Path

import pytest

from paper_fetch.reason_codes import (
    XML_DEPTH_EXCEEDED,
    XML_ENTITIES_FORBIDDEN,
    XML_MALFORMED,
    XML_NODE_LIMIT_EXCEEDED,
    XML_SIZE_EXCEEDED,
)
from paper_fetch.xml_security import (
    XmlParseFailure,
    XmlParseLimits,
    parse_mathml_fragment,
    parse_trusted_xml_file,
    parse_xml,
)


def _failure_code(payload: bytes | str, limits: XmlParseLimits) -> str:
    with pytest.raises(XmlParseFailure) as exc_info:
        parse_xml(payload, limits=limits, source="test XML")
    return exc_info.value.code


def test_parse_xml_rejects_payload_over_byte_limit_before_parsing() -> None:
    limits = XmlParseLimits(max_bytes=7, max_nodes=10, max_depth=10)
    assert _failure_code(b"<root />", limits) == XML_SIZE_EXCEEDED


def test_parse_xml_rejects_excessive_depth() -> None:
    limits = XmlParseLimits(max_bytes=100, max_nodes=10, max_depth=2)
    assert _failure_code("<a><b><c /></b></a>", limits) == XML_DEPTH_EXCEEDED


def test_parse_xml_rejects_excessive_node_count() -> None:
    limits = XmlParseLimits(max_bytes=100, max_nodes=2, max_depth=10)
    assert _failure_code("<a><b /><c /></a>", limits) == XML_NODE_LIMIT_EXCEEDED


@pytest.mark.parametrize(
    "payload",
    [
        '<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>',
        '<!DOCTYPE root SYSTEM "https://example.invalid/external.dtd"><root />',
    ],
)
def test_parse_xml_rejects_dtd_entities_and_external_references(payload: str) -> None:
    limits = XmlParseLimits(max_bytes=1000, max_nodes=10, max_depth=10)
    assert _failure_code(payload, limits) == XML_ENTITIES_FORBIDDEN


def test_parse_xml_reports_malformed_payload() -> None:
    limits = XmlParseLimits(max_bytes=100, max_nodes=10, max_depth=10)
    assert _failure_code("<root>", limits) == XML_MALFORMED


def test_mathml_fragment_uses_bounded_parser() -> None:
    root = parse_mathml_fragment(
        '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
    )
    assert root.tag.endswith("math")


def test_trusted_local_xml_uses_same_safe_parser(tmp_path: Path) -> None:
    path = tmp_path / "sample.xml"
    path.write_text("<article><body /></article>", encoding="utf-8")
    assert parse_trusted_xml_file(path).tag == "article"
