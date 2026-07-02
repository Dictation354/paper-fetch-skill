"""Elsevier XML element semantics and asset classification rules.

These rules are grounded in Elsevier's Journal Article / CEP DTD family and
the Tag-by-Tag documentation. The goal is to keep Markdown rendering driven by
element semantics instead of ad-hoc paper-specific checks.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..extraction.html.semantics import FRONT_MATTER_HEADINGS
from ..reason_codes import METADATA_ONLY


@dataclass(frozen=True)
class ElsevierElementRule:
    category: str
    handler: str
    markdown_behavior: str
    notes: str = ""


@dataclass(frozen=True)
class ElsevierXmlRules:
    ignored_section_titles: frozenset[str]


ELSEVIER_ELEMENT_RULES: dict[str, ElsevierElementRule] = {
    "sections": ElsevierElementRule(
        category="structure",
        handler="container",
        markdown_behavior="recurse into child sections",
    ),
    "section": ElsevierElementRule(
        category="structure",
        handler="section",
        markdown_behavior="render heading from section-title/title and recurse",
    ),
    "appendices": ElsevierElementRule(
        category="structure",
        handler="container",
        markdown_behavior="recurse with appendix context",
    ),
    "appendix": ElsevierElementRule(
        category="structure",
        handler="container",
        markdown_behavior="recurse with appendix context",
    ),
    "abstract-sec": ElsevierElementRule(
        category="structure",
        handler="section",
        markdown_behavior="render abstract subsection heading and recurse",
    ),
    "data-availability": ElsevierElementRule(
        category="structure",
        handler="section",
        markdown_behavior="render heading from section-title/title and recurse",
    ),
    "para": ElsevierElementRule(
        category="text",
        handler="paragraph",
        markdown_behavior="render inline text and nested display children",
    ),
    "simple-para": ElsevierElementRule(
        category="text",
        handler="paragraph",
        markdown_behavior="render inline text and nested display children",
    ),
    "display": ElsevierElementRule(
        category="compound",
        handler="display",
        markdown_behavior="dispatch to figure/table/supplement/formula handlers",
        notes="display is a container, not a formula by default",
    ),
    "figure": ElsevierElementRule(
        category="figure",
        handler="figure",
        markdown_behavior="render via registered image asset",
    ),
    "table": ElsevierElementRule(
        category="table",
        handler="table",
        markdown_behavior="render as markdown table",
    ),
    "e-component": ElsevierElementRule(
        category="supplementary",
        handler="supplementary",
        markdown_behavior="collect into Supplementary Materials, omit from body",
    ),
    "formula": ElsevierElementRule(
        category="formula",
        handler="formula",
        markdown_behavior="render display math",
    ),
    "inline-formula": ElsevierElementRule(
        category="formula",
        handler="inline_formula",
        markdown_behavior="render inline math",
    ),
    "math": ElsevierElementRule(
        category="formula",
        handler="math",
        markdown_behavior="render MathML to LaTeX",
    ),
    "tex-math": ElsevierElementRule(
        category="formula",
        handler="tex_math",
        markdown_behavior="render TeX directly",
    ),
    "cross-ref": ElsevierElementRule(
        category="reference",
        handler="inline_reference",
        markdown_behavior="keep inline text; figures handled separately",
    ),
    "cross-refs": ElsevierElementRule(
        category="reference",
        handler="inline_reference",
        markdown_behavior="keep inline text; figures handled separately",
    ),
    "section-title": ElsevierElementRule(
        category="text",
        handler="inline_text",
        markdown_behavior="used as heading source",
    ),
    "caption": ElsevierElementRule(
        category="text",
        handler="inline_text",
        markdown_behavior="render as caption text",
    ),
    "label": ElsevierElementRule(
        category="text",
        handler="inline_text",
        markdown_behavior="render as figure/table/e-component label",
    ),
    "link": ElsevierElementRule(
        category="linkage",
        handler=METADATA_ONLY,
        markdown_behavior="used to resolve assets; not rendered inline",
    ),
    "alt-text": ElsevierElementRule(
        category="metadata",
        handler=METADATA_ONLY,
        markdown_behavior="descriptive metadata only",
    ),
}


ELSEVIER_XML_RULES = ElsevierXmlRules(
    # Elsevier XML renders graphical abstracts as section-like metadata blocks.
    # Derive the shared front-matter heading while keeping supplementary data
    # provider-specific because it is an Elsevier XML section title.
    ignored_section_titles=(FRONT_MATTER_HEADINGS & {"graphical abstract"})
    | {"supplementary data"}
)

ELSEVIER_IMAGE_ASSET_TYPES = frozenset(
    {
        "image",
        "appendix_image",
        "graphical_abstract",
    }
)

ELSEVIER_ASSET_PREFIX_BY_KIND = {
    "body_image": ("gr",),
    "appendix_image": ("fx",),
    "graphical_abstract": ("ga",),
    "table_asset": ("tbl",),
    "supplementary": ("mmc", "si", "sup", "am"),
}


def _elsevier_asset_prefix_pattern(
    prefixes: tuple[str, ...], *, fullmatch: bool
) -> re.Pattern[str]:
    body = "|".join(f"{re.escape(prefix)}\\d+" for prefix in prefixes)
    suffix = r"\Z" if fullmatch else ""
    return re.compile(rf"({body}){suffix}", flags=re.IGNORECASE)


_ALL_ELSEVIER_ASSET_PREFIXES = tuple(
    prefix for prefixes in ELSEVIER_ASSET_PREFIX_BY_KIND.values() for prefix in prefixes
)
_ASSET_GROUP_PATTERN = _elsevier_asset_prefix_pattern(
    _ALL_ELSEVIER_ASSET_PREFIXES, fullmatch=False
)
_BODY_IMAGE_PATTERN = _elsevier_asset_prefix_pattern(
    ELSEVIER_ASSET_PREFIX_BY_KIND["body_image"], fullmatch=True
)
_APPENDIX_IMAGE_PATTERN = _elsevier_asset_prefix_pattern(
    ELSEVIER_ASSET_PREFIX_BY_KIND["appendix_image"],
    fullmatch=True,
)
_GRAPHICAL_ABSTRACT_PATTERN = _elsevier_asset_prefix_pattern(
    ELSEVIER_ASSET_PREFIX_BY_KIND["graphical_abstract"],
    fullmatch=True,
)
_TABLE_ASSET_PATTERN = _elsevier_asset_prefix_pattern(
    ELSEVIER_ASSET_PREFIX_BY_KIND["table_asset"], fullmatch=True
)
_SUPPLEMENTARY_ASSET_PATTERN = _elsevier_asset_prefix_pattern(
    ELSEVIER_ASSET_PREFIX_BY_KIND["supplementary"],
    fullmatch=True,
)


def get_elsevier_element_rule(local_name: str) -> ElsevierElementRule:
    return ELSEVIER_ELEMENT_RULES.get(
        local_name,
        ElsevierElementRule(
            category="unknown",
            handler="unknown",
            markdown_behavior="ignore unless explicitly handled",
        ),
    )


def normalize_elsevier_section_title(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def should_ignore_elsevier_section_title(value: str | None) -> bool:
    return (
        normalize_elsevier_section_title(value)
        in ELSEVIER_XML_RULES.ignored_section_titles
    )


def infer_elsevier_asset_group_key(value: str) -> str:
    normalized = value.strip().lower()
    filename = (
        re.split(r"[?#]", normalized, maxsplit=1)[0].rsplit("/", 1)[-1] or normalized
    )
    match = _ASSET_GROUP_PATTERN.search(filename)
    if match:
        return match.group(1).lower()
    return filename


def classify_elsevier_asset_kind(
    ref: str,
    asset_type: str | None = None,
    category: str | None = None,
) -> str:
    group_key = infer_elsevier_asset_group_key(ref)
    normalized_type = (asset_type or "").strip().upper()
    normalized_category = (category or "").strip().lower()

    if _GRAPHICAL_ABSTRACT_PATTERN.fullmatch(group_key):
        return "graphical_abstract"
    if _APPENDIX_IMAGE_PATTERN.fullmatch(group_key):
        return "appendix_image"
    if _TABLE_ASSET_PATTERN.fullmatch(group_key):
        return "table_asset"
    if _BODY_IMAGE_PATTERN.fullmatch(group_key):
        return "image"
    if _SUPPLEMENTARY_ASSET_PATTERN.fullmatch(group_key):
        return "supplementary"
    if normalized_type.startswith("IMAGE-") or normalized_category == "thumbnail":
        return "image"
    return "supplementary"
