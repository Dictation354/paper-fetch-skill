"""HTML availability signal helpers and typed provider signal sets."""

from __future__ import annotations
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from re import Pattern
from collections.abc import Mapping
from ..extraction.html.provider_keys import normalize_provider_key
from ..extraction.html.signals import ACCESS_GATE_PATTERNS
from ..utils import normalize_text


def _attr_markers(name: str, value: str) -> tuple[str, str]:
    return (f'{name}="{value}"', f"{name}='{value}'")


def provider_datalayer_assignment_pattern(name: str) -> Pattern[str]:
    return re.compile(rf"\b{re.escape(name)}\s*=", flags=re.DOTALL)


HTML_STRONG_FULLTEXT_MARKERS = (
    *_attr_markers("property", "articleBody"),
    *_attr_markers("itemprop", "articleBody"),
)
HTML_STRUCTURE_MARKERS = (
    *_attr_markers("data-article-access", "full"),
    *_attr_markers("data-article-access-type", "full"),
    *_attr_markers("id", "bodymatter"),
)
# SITE_UI_COPY_REGRESSION_MARKER: site-owned UI copy; rerun extraction rules
# when publisher text changes.
NATURE_RESEARCH_BRIEFING_HEADING_SIGNATURE = (
    "the question",
    "the discovery",
    "the implications",
    "expert opinion",
    "behind the paper",
    "from the editor",
)
PROVIDER_AUTHORLESS_HEADING_SIGNATURES: Mapping[str, tuple[tuple[str, ...], ...]] = (
    MappingProxyType(
        {
            "springer": (NATURE_RESEARCH_BRIEFING_HEADING_SIGNATURE,),
            "springer_nature": (NATURE_RESEARCH_BRIEFING_HEADING_SIGNATURE,),
            "nature": (NATURE_RESEARCH_BRIEFING_HEADING_SIGNATURE,),
        }
    )
)
AAAS_DATALAYER_PATTERN = provider_datalayer_assignment_pattern("AAASdataLayer")
PNAS_DATALAYER_PATTERN = provider_datalayer_assignment_pattern("PNASdataLayer")
WILEY_DATALAYER_PATTERN = re.compile(
    r"\bwindow\.adobeDataLayer\.push\s*\(", flags=re.DOTALL
)

FieldPaths = tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class DatalayerSchema:
    provider: str
    pattern: Pattern[str]
    fields: Mapping[str, FieldPaths]
    required_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatalayerFieldMatch:
    field: str
    expected: str
    negate: bool = False


@dataclass(frozen=True)
class DatalayerSignalRule:
    match: DatalayerFieldMatch
    token: str


@dataclass(frozen=True)
class DatalayerSignalCombo:
    matches: tuple[DatalayerFieldMatch, ...]
    token: str


@dataclass(frozen=True)
class DatalayerContainsRule:
    field: str
    substring: str
    token: str


DatalayerRule = DatalayerSignalRule | DatalayerSignalCombo | DatalayerContainsRule
DF = DatalayerFieldMatch
DR = DatalayerSignalRule
DC = DatalayerSignalCombo
DCR = DatalayerContainsRule


@dataclass(frozen=True)
class DatalayerSignalSet:
    schema: DatalayerSchema
    blocking_rules: tuple[DatalayerRule, ...] = ()
    strong_rules: tuple[DatalayerRule, ...] = ()
    soft_rules: tuple[DatalayerRule, ...] = ()
    abstract_only_rules: tuple[DatalayerRule, ...] = ()
    presence_rules: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TextMarkerRule:
    substring: str
    token: str
    negate: bool = False
    contains: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()
    access_gate_context: bool = False


@dataclass(frozen=True)
class TextMarkerSignalSet:
    blocking_rules: tuple[TextMarkerRule, ...] = ()
    strong_rules: tuple[TextMarkerRule, ...] = ()
    soft_rules: tuple[TextMarkerRule, ...] = ()
    abstract_only_rules: tuple[TextMarkerRule, ...] = ()


@dataclass(frozen=True)
class SelectorFlagRule:
    selector: str
    field: str
    value: bool = True


@dataclass(frozen=True)
class CanonicalUrlRule:
    substring: str
    token: str


@dataclass(frozen=True)
class SelectorBlockingRule:
    selector: str
    token: str
    require_structure_field_false: str | None = None


@dataclass(frozen=True)
class TextBlockingRule:
    substring: str
    token: str
    require_structure_field_false: str | None = None


@dataclass(frozen=True)
class EmptyShellRule:
    selector: str
    body_selectors: tuple[str, ...]
    token: str


@dataclass(frozen=True)
class AvailabilityOverrides:
    selector_flags: tuple[SelectorFlagRule, ...] = ()
    canonical_url_rules: tuple[CanonicalUrlRule, ...] = ()
    selector_blocking_rules: tuple[SelectorBlockingRule, ...] = ()
    text_blocking_rules: tuple[TextBlockingRule, ...] = ()
    empty_shell_rules: tuple[EmptyShellRule, ...] = ()


class AvailabilityOverrideState:
    def __init__(
        self,
        *,
        soup: Any,
        structure: Any,
        final_url: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        hard_negative_signals: list[str] | None = None,
        abstract_only_hints: list[str] | None = None,
        blocking_fallback_signals: list[str] | None = None,
    ) -> None:
        self.soup = soup
        self.structure = structure
        self.final_url = final_url
        self.metadata = metadata
        self.hard_negative_signals = (
            [] if hard_negative_signals is None else hard_negative_signals
        )
        self.abstract_only_hints = (
            [] if abstract_only_hints is None else abstract_only_hints
        )
        self.blocking_fallback_signals = (
            [] if blocking_fallback_signals is None else blocking_fallback_signals
        )


@dataclass(frozen=True)
class ProviderDatalayer:
    schema: DatalayerSchema
    payload: Mapping[str, Any]

    def value(self, field_name: str) -> Any:
        for path in self.schema.fields.get(field_name, ()):
            value: Any = self.payload
            for key in path:
                if not isinstance(value, Mapping):
                    value = None
                    break
                value = value.get(key)
            if value is not None:
                return value
        return None

    def text(self, field_name: str) -> str:
        return normalize_text(self.value(field_name))

    def lowered(self, field_name: str) -> str:
        return self.text(field_name).lower()


AAAS_DATALAYER_SCHEMA = DatalayerSchema(
    "science",
    AAAS_DATALAYER_PATTERN,
    {
        "page_type": (("page", "pageInfo", "pageType"),),
        "view_type": (("page", "pageInfo", "viewType"),),
        "article_type": (("page", "pageInfo", "articleType"),),
        "user_entitled": (("user", "entitled"),),
        "user_access": (("user", "access"),),
    },
    ("page_type", "view_type", "user_entitled", "user_access"),
)
PNAS_DATALAYER_SCHEMA = DatalayerSchema(
    "pnas",
    PNAS_DATALAYER_PATTERN,
    {
        "access_type": (("page", "attributes", "accessType"),),
        "free_access": (("page", "attributes", "freeAccess"),),
        "user_access": (("user", "access"),),
    },
    ("access_type", "free_access", "user_access"),
)
WILEY_DATALAYER_SCHEMA = DatalayerSchema(
    "wiley",
    WILEY_DATALAYER_PATTERN,
    {
        "item_access": (("content", "item", "access"),),
        "format_viewed": (
            ("content", "item", "format-viewed"),
            ("content", "item", "format_viewed"),
        ),
        "page_tertiary_section": (
            ("page", "tertiary-section"),
            ("page", "tertiary_section"),
        ),
    },
    ("item_access", "format_viewed", "page_tertiary_section"),
)
DATALAYER_SCHEMAS: Mapping[str, DatalayerSchema] = {
    schema.provider: schema
    for schema in (AAAS_DATALAYER_SCHEMA, PNAS_DATALAYER_SCHEMA, WILEY_DATALAYER_SCHEMA)
}
SCIENCE_SIGNAL_SET = DatalayerSignalSet(
    AAAS_DATALAYER_SCHEMA,
    blocking_rules=(
        DR(DF("page_type", "journal-article-denial"), "aaas_page_type_denial"),
        DR(DF("page_type", "journal-article-abstract"), "aaas_page_type_abstract"),
        DR(DF("view_type", "abs"), "aaas_view_abs"),
        DC(
            (DF("user_entitled", "false"), DF("user_access", "yes", negate=True)),
            "aaas_entitlement_denied",
        ),
    ),
    strong_rules=(
        DR(DF("user_entitled", "true"), "aaas_user_entitled"),
        DR(DF("user_access", "yes"), "aaas_user_access_yes"),
    ),
    soft_rules=(
        DR(DF("page_type", "journal-article-full-text"), "aaas_page_type_full_text"),
        DR(DF("view_type", "full"), "aaas_view_full"),
    ),
    abstract_only_rules=(
        DCR("page_type", "abstract", "aaas_page_type_abstract"),
        DCR("view_type", "abstract", "aaas_view_abstract"),
    ),
    presence_rules=(("article_type", "aaas_article_type_present"),),
)
PNAS_SIGNAL_SET = DatalayerSignalSet(
    PNAS_DATALAYER_SCHEMA,
    blocking_rules=(
        DC(
            (
                DF("access_type", "paywall"),
                DF("free_access", "no"),
                DF("user_access", "no"),
            ),
            "pnas_paywall_no_access",
        ),
    ),
)
WILEY_SIGNAL_SET = DatalayerSignalSet(
    WILEY_DATALAYER_SCHEMA,
    blocking_rules=(
        DR(DF("item_access", "no"), "wiley_access_no"),
        DR(DF("format_viewed", "abstract"), "wiley_format_viewed_abstract"),
        DR(DF("page_tertiary_section", "abs"), "wiley_page_tertiary_abs"),
    ),
)
AMS_TEXT_MARKER_SIGNAL_SET = TextMarkerSignalSet(
    blocking_rules=(
        TextMarkerRule(
            "check access",
            "ams_check_access_without_body",
            absent=(
                'id="bodymatter"',
                "id='bodymatter'",
                "articlebody",
                "nlm_body",
                "articlefulltext",
            ),
            access_gate_context=True,
        ),
        TextMarkerRule(
            "purchase this article",
            "ams_purchase_without_body",
            absent=(
                'id="bodymatter"',
                "id='bodymatter'",
                "articlebody",
                "nlm_body",
                "articlefulltext",
            ),
            access_gate_context=True,
        ),
    ),
    strong_rules=(
        TextMarkerRule('id="bodymatter"', "ams_bodymatter"),
        TextMarkerRule("id='bodymatter'", "ams_bodymatter"),
    ),
    soft_rules=(
        TextMarkerRule("nlm_body", "ams_body_container"),
        TextMarkerRule("articlefulltext", "ams_body_container"),
        TextMarkerRule("citation_fulltext_html_url", "ams_fulltext_meta"),
        TextMarkerRule("citation_pdf_url", "ams_pdf_meta"),
    ),
)
IEEE_TEXT_MARKER_SIGNAL_SET = TextMarkerSignalSet(
    blocking_rules=(
        TextMarkerRule("institutional sign in", "ieee_access_or_challenge_page"),
        TextMarkerRule("purchase access", "ieee_access_or_challenge_page"),
    ),
    strong_rules=(
        TextMarkerRule('div class="section', "ieee_section_nodes"),
        TextMarkerRule("div class='section", "ieee_section_nodes"),
    ),
    soft_rules=(
        TextMarkerRule('id="article"', "ieee_article_container"),
        TextMarkerRule("id='article'", "ieee_article_container"),
        TextMarkerRule("<tex-math", "ieee_formula_marker"),
        TextMarkerRule("tex-math", "ieee_formula_marker"),
        TextMarkerRule("<figure", "ieee_figure_marker"),
        TextMarkerRule('class="figure', "ieee_figure_marker"),
        TextMarkerRule("class='figure", "ieee_figure_marker"),
        TextMarkerRule("<table", "ieee_table_marker"),
    ),
)
SCIENCE_AVAILABILITY_OVERRIDES = AvailabilityOverrides(
    selector_flags=(
        SelectorFlagRule(
            ".perspective, .article-type-perspective", "narrative_article_type"
        ),
    )
)
ELSEVIER_AVAILABILITY_OVERRIDES = AvailabilityOverrides(
    canonical_url_rules=(
        CanonicalUrlRule("/science/article/abs/", "canonical_abstract_url"),
    )
)
SPRINGER_ARTICLE_IN_PRESS_NOTICE = (
    "we are providing an unedited version of this manuscript"
)
SPRINGER_AVAILABILITY_OVERRIDES = AvailabilityOverrides(
    selector_blocking_rules=(
        SelectorBlockingRule(
            ".app-article-access__heading, .c-preview-message__link, [data-test='access-via-institution']",
            "springer_access_preview_wall",
            require_structure_field_false="post_abstract_body_run",
        ),
    ),
    text_blocking_rules=(
        TextBlockingRule(
            SPRINGER_ARTICLE_IN_PRESS_NOTICE,
            "springer_article_in_press_notice",
            require_structure_field_false="post_abstract_body_run",
        ),
    ),
)
IEEE_AVAILABILITY_OVERRIDES = AvailabilityOverrides(
    empty_shell_rules=(
        EmptyShellRule(
            "#article",
            (
                "p",
                "h2",
                "h3",
                "div.section",
                "div.section_2",
                "figure",
                "table",
                "tex-math",
            ),
            "ieee_empty_article_shell",
        ),
    )
)


def authorless_heading_signatures_for_provider(
    provider_name: str | None,
) -> tuple[tuple[str, ...], ...]:
    return PROVIDER_AUTHORLESS_HEADING_SIGNATURES.get(
        normalize_provider_key(provider_name), ()
    )


def dedupe_signals(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _datalayer_rule_value(value: str) -> str:
    return normalize_text(value).lower()


def _matches_datalayer_field(
    datalayer: ProviderDatalayer, match: DatalayerFieldMatch
) -> bool:
    matched = datalayer.lowered(match.field) == _datalayer_rule_value(match.expected)
    return not matched if match.negate else matched


def _matches_datalayer_rule(datalayer: ProviderDatalayer, rule: DatalayerRule) -> bool:
    if isinstance(rule, DatalayerSignalRule):
        return _matches_datalayer_field(datalayer, rule.match)
    if isinstance(rule, DatalayerSignalCombo):
        return all(_matches_datalayer_field(datalayer, match) for match in rule.matches)
    return _datalayer_rule_value(rule.substring) in datalayer.lowered(rule.field)


def _evaluate_datalayer_rules(
    datalayer: ProviderDatalayer, rules: tuple[DatalayerRule, ...]
) -> list[str]:
    return dedupe_signals(
        [rule.token for rule in rules if _matches_datalayer_rule(datalayer, rule)]
    )


def evaluate_datalayer_blocking_signals(
    html_text: str, signal_set: DatalayerSignalSet
) -> list[str]:
    datalayer = load_provider_datalayer(html_text, signal_set.schema)
    if datalayer is None:
        return []
    return _evaluate_datalayer_rules(datalayer, signal_set.blocking_rules)


def _evaluate_datalayer_positive_signal_set(
    html_text: str, signal_set: DatalayerSignalSet
) -> tuple[list[str], list[str], list[str]]:
    strong, soft, abstract_only = default_positive_signals(html_text)
    datalayer = load_provider_datalayer(html_text, signal_set.schema)
    if datalayer is None:
        return strong, soft, abstract_only
    strong.extend(_evaluate_datalayer_rules(datalayer, signal_set.strong_rules))
    soft.extend(_evaluate_datalayer_rules(datalayer, signal_set.soft_rules))
    abstract_only.extend(
        _evaluate_datalayer_rules(datalayer, signal_set.abstract_only_rules)
    )
    soft.extend(
        token
        for field_name, token in signal_set.presence_rules
        if datalayer.text(field_name)
    )
    return dedupe_signals(strong), dedupe_signals(soft), dedupe_signals(abstract_only)


def _matches_text_marker_rule(lowered: str, rule: TextMarkerRule) -> bool:
    matched = _datalayer_rule_value(rule.substring) in lowered
    if rule.contains:
        matched = matched and all(
            _datalayer_rule_value(token) in lowered for token in rule.contains
        )
    if rule.absent:
        matched = matched and not any(
            _datalayer_rule_value(token) in lowered for token in rule.absent
        )
    if rule.access_gate_context:
        matched = matched and rule.substring in ACCESS_GATE_PATTERNS
    return not matched if rule.negate else matched


def _evaluate_text_marker_rules(
    html_text: str, rules: tuple[TextMarkerRule, ...]
) -> list[str]:
    lowered = normalize_text(html_text).lower()
    return dedupe_signals(
        [rule.token for rule in rules if _matches_text_marker_rule(lowered, rule)]
    )


def evaluate_text_marker_blocking_signals(
    html_text: str, signal_set: TextMarkerSignalSet
) -> list[str]:
    return _evaluate_text_marker_rules(html_text, signal_set.blocking_rules)


def _evaluate_text_marker_positive_signal_set(
    html_text: str, signal_set: TextMarkerSignalSet
) -> tuple[list[str], list[str], list[str]]:
    strong, soft, abstract_only = default_positive_signals(html_text)
    strong.extend(_evaluate_text_marker_rules(html_text, signal_set.strong_rules))
    soft.extend(_evaluate_text_marker_rules(html_text, signal_set.soft_rules))
    abstract_only.extend(
        _evaluate_text_marker_rules(html_text, signal_set.abstract_only_rules)
    )
    return dedupe_signals(strong), dedupe_signals(soft), dedupe_signals(abstract_only)


def _apply_availability_override_rules(
    state: AvailabilityOverrideState, overrides: AvailabilityOverrides
) -> None:
    for selector_flag_rule in overrides.selector_flags:
        if state.soup.select_one(selector_flag_rule.selector):
            setattr(state.structure, selector_flag_rule.field, selector_flag_rule.value)
    for canonical_url_rule in overrides.canonical_url_rules:
        canonical_node = state.soup.select_one("link[rel='canonical']")
        canonical_url = normalize_text(
            str((getattr(canonical_node, "attrs", None) or {}).get("href") or "")
        )
        if (
            canonical_url_rule.substring in canonical_url
            and state.abstract_only_hints is not None
            and state.blocking_fallback_signals is not None
        ):
            state.abstract_only_hints.append(canonical_url_rule.token)
            state.blocking_fallback_signals.append(canonical_url_rule.token)
    for selector_blocking_rule in overrides.selector_blocking_rules:
        if selector_blocking_rule.require_structure_field_false and getattr(
            state.structure, selector_blocking_rule.require_structure_field_false, False
        ):
            continue
        if (
            state.soup.select_one(selector_blocking_rule.selector)
            and state.blocking_fallback_signals is not None
        ):
            state.blocking_fallback_signals.append(selector_blocking_rule.token)
    page_text = normalize_text(" ".join(state.soup.stripped_strings)).lower()
    for text_blocking_rule in overrides.text_blocking_rules:
        if text_blocking_rule.require_structure_field_false and getattr(
            state.structure, text_blocking_rule.require_structure_field_false, False
        ):
            continue
        if (
            normalize_text(text_blocking_rule.substring).lower() in page_text
            and state.blocking_fallback_signals is not None
        ):
            state.blocking_fallback_signals.append(text_blocking_rule.token)
    for empty_shell_rule in overrides.empty_shell_rules:
        node = state.soup.select_one(empty_shell_rule.selector)
        if node is None:
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        if (
            not text
            and not bool(node.select(", ".join(empty_shell_rule.body_selectors)))
            and state.blocking_fallback_signals is not None
        ):
            state.blocking_fallback_signals.append(empty_shell_rule.token)


def _default_positive_signal_values(
    html_text: str,
) -> tuple[list[str], list[str], list[str]]:
    strong: list[str] = []
    soft: list[str] = []
    lowered = html_text.lower()
    if any(marker in lowered for marker in HTML_STRONG_FULLTEXT_MARKERS):
        strong.append("article_body_marker")
    if any(marker in lowered for marker in HTML_STRUCTURE_MARKERS):
        soft.append("article_body_structure_marker")
    if "<article" in lowered:
        soft.append("article_tag_present")
    return dedupe_signals(strong), dedupe_signals(soft), []


evaluate_datalayer_positive_signals = _evaluate_datalayer_positive_signal_set
evaluate_text_marker_positive_signals = _evaluate_text_marker_positive_signal_set
apply_availability_overrides = _apply_availability_override_rules
default_positive_signals = _default_positive_signal_values


def looks_like_abstract_redirect(
    requested_url: str | None, final_url: str | None
) -> bool:
    if not requested_url or not final_url:
        return False
    requested = requested_url.lower()
    final = final_url.lower()
    return "/doi/full/" in requested and "/doi/abs/" in final and requested != final


def _schema_field_is_present(
    payload: Mapping[str, Any], schema: DatalayerSchema, field_name: str
) -> bool:
    return ProviderDatalayer(schema, payload).value(field_name) is not None


def _payload_matches_schema(
    payload: Mapping[str, Any], schema: DatalayerSchema
) -> bool:
    if not schema.required_fields:
        return True
    return any(
        _schema_field_is_present(payload, schema, field_name)
        for field_name in schema.required_fields
    )


def _json_payload_after_match(
    html_text: str, match: re.Match[str]
) -> Mapping[str, Any] | None:
    decoder = json.JSONDecoder()
    payload_text = html_text[match.end() :].lstrip()
    if not payload_text:
        return None
    try:
        payload, _end = decoder.raw_decode(payload_text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def load_provider_datalayer(
    html_text: str, schema: DatalayerSchema
) -> ProviderDatalayer | None:
    for match in schema.pattern.finditer(html_text):
        payload = _json_payload_after_match(html_text, match)
        if payload is None:
            continue
        if _payload_matches_schema(payload, schema):
            return ProviderDatalayer(schema, payload)
    return None


def load_aaas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    datalayer = load_provider_datalayer(html_text, AAAS_DATALAYER_SCHEMA)
    return datalayer.payload if datalayer is not None else None


def load_pnas_datalayer(html_text: str) -> Mapping[str, Any] | None:
    datalayer = load_provider_datalayer(html_text, PNAS_DATALAYER_SCHEMA)
    return datalayer.payload if datalayer is not None else None


def load_wiley_datalayer(html_text: str) -> Mapping[str, Any] | None:
    datalayer = load_provider_datalayer(html_text, WILEY_DATALAYER_SCHEMA)
    return datalayer.payload if datalayer is not None else None
