"""Bounded XML parsing for provider payloads and embedded MathML."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from defusedxml import ElementTree as DefusedElementTree
from defusedxml.common import DefusedXmlException

from .reason_codes import (
    XML_DEPTH_EXCEEDED,
    XML_ENTITIES_FORBIDDEN,
    XML_MALFORMED,
    XML_NODE_LIMIT_EXCEEDED,
    XML_SIZE_EXCEEDED,
)


@dataclass(frozen=True)
class XmlParseLimits:
    max_bytes: int
    max_nodes: int
    max_depth: int


EXTERNAL_XML_LIMITS = XmlParseLimits(
    max_bytes=32 * 1024 * 1024,
    max_nodes=250_000,
    max_depth=128,
)
MATHML_FRAGMENT_LIMITS = XmlParseLimits(
    max_bytes=1024 * 1024,
    max_nodes=10_000,
    max_depth=64,
)
TRUSTED_LOCAL_XML_LIMITS = EXTERNAL_XML_LIMITS


class XmlParseFailure(ValueError):
    """Stable XML rejection carrying a structured reason code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _payload_bytes(value: bytes | bytearray | memoryview | str) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return bytes(value)


def parse_xml(
    value: bytes | bytearray | memoryview | str,
    *,
    limits: XmlParseLimits = EXTERNAL_XML_LIMITS,
    source: str = "XML payload",
    allow_external_doctype: bool = False,
) -> ET.Element:
    """Parse XML with entity defenses and streaming node/depth budgets."""

    payload = _payload_bytes(value)
    if len(payload) > limits.max_bytes:
        raise XmlParseFailure(
            XML_SIZE_EXCEEDED,
            f"{source} exceeded the {limits.max_bytes}-byte XML limit.",
        )
    if allow_external_doctype:
        # JATS publishers commonly retain a standards-identifying external
        # DOCTYPE. ElementTree does not need it, so remove only declarations
        # without an internal subset before the defused parser sees them.
        payload = re.sub(
            rb"<!DOCTYPE\s+[^>\[]+>",
            b"",
            payload,
            count=1,
            flags=re.IGNORECASE,
        )

    depth = 0
    nodes = 0
    try:
        iterator = DefusedElementTree.iterparse(
            BytesIO(payload),
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
        for event, _element in iterator:
            if event == "start":
                depth += 1
                nodes += 1
                if depth > limits.max_depth:
                    raise XmlParseFailure(
                        XML_DEPTH_EXCEEDED,
                        f"{source} exceeded the XML depth limit of {limits.max_depth}.",
                    )
                if nodes > limits.max_nodes:
                    raise XmlParseFailure(
                        XML_NODE_LIMIT_EXCEEDED,
                        f"{source} exceeded the XML node limit of {limits.max_nodes}.",
                    )
            else:
                depth -= 1
        root = iterator.root
    except XmlParseFailure:
        raise
    except DefusedXmlException as exc:
        raise XmlParseFailure(
            XML_ENTITIES_FORBIDDEN,
            f"{source} contains a forbidden DTD, entity, or external reference.",
        ) from exc
    except (ET.ParseError, ValueError) as exc:
        raise XmlParseFailure(
            XML_MALFORMED,
            f"{source} is malformed XML: {exc}",
        ) from exc

    if root is None:
        raise XmlParseFailure(XML_MALFORMED, f"{source} has no document element.")
    return root


def parse_mathml_fragment(value: str, *, source: str = "MathML fragment") -> ET.Element:
    return parse_xml(value, limits=MATHML_FRAGMENT_LIMITS, source=source)


def parse_trusted_xml_file(path: Path) -> ET.Element:
    """Parse a controlled local sample while retaining the same resource budgets."""

    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise XmlParseFailure(
            XML_MALFORMED, f"Could not read local XML sample {path}: {exc}"
        ) from exc
    return parse_xml(
        payload,
        limits=TRUSTED_LOCAL_XML_LIMITS,
        source=f"Local XML sample {path}",
        allow_external_doctype=True,
    )


__all__ = [
    "EXTERNAL_XML_LIMITS",
    "MATHML_FRAGMENT_LIMITS",
    "TRUSTED_LOCAL_XML_LIMITS",
    "XmlParseFailure",
    "XmlParseLimits",
    "parse_mathml_fragment",
    "parse_trusted_xml_file",
    "parse_xml",
]
