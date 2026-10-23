"""Independent comparison keys; never repair production or PDF output."""

import html
import re
import unicodedata

from markdown_it import MarkdownIt

_INLINE = MarkdownIt()
_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ"
_SUB = "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"


def without_latex_spacing(value):
    """Exclude explicit layout dimensions from scientific content comparisons."""
    value = re.sub(r"(?<!\\)\\(?:[,;:!]|[ \t])", "", value)
    return re.sub(
        r"\\hspace\*?\s*\{\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*(?:em|ex|pt|bp|pc|in|cm|mm)\s*\}",
        "",
        value,
    )


def script_markup(value):
    """Preserve script roles before compatibility normalization."""
    value = html.unescape(value)
    for chars, operator in ((_SUP, "^"), (_SUB, "_")):
        value = re.sub(
            f"[{chars}]+",
            lambda m, operator=operator: (
                operator + "{" + unicodedata.normalize("NFKC", m[0]) + "}"
            ),
            value,
        )
    value = re.sub(
        r"<(sup|sub)(?:\s[^>]*)?>(.*?)</\1>",
        lambda m: ("^" if m[1] == "sup" else "_") + "{" + m[2] + "}",
        value,
        flags=re.S,
    )
    return value


def scientific_text_key(value):
    """Ignore editorial punctuation, never decimal points, signs or script roles."""
    value = without_latex_spacing(script_markup(value.replace(r"\_", "_")))
    # Protect TeX scripts from Markdown emphasis parsing.
    value = value.replace("_", "SCRIPTSUBTOKEN")
    tokens = _INLINE.parseInline(value)[0].children or []
    value = "".join(
        t.content for t in tokens if t.type in {"text", "code_inline", "html_inline"}
    )
    value = value.replace("SCRIPTSUBTOKEN", "_")
    value = re.sub(r"</?(?:br|em|strong|i|b|span)(?:\s[^<>]*?)?\s*/?>", "", value)
    value = unicodedata.normalize("NFKC", value).replace("−", "-").replace("–", "-")
    value = re.sub(r"(?<![\\_])([\^_])([A-Za-z0-9+-])", r"\1{\2}", value)
    value = value.replace(r"\%", "%").replace("π", "pi")
    return "".join(
        c
        for i, c in enumerate(value)
        if c.isalnum()
        or c in "^_{}+-=<>±×÷%/≤≥≠"
        or (
            c == "."
            and i > 0
            and i + 1 < len(value)
            and value[i - 1].isdigit()
            and value[i + 1].isdigit()
        )
    )


def preserve_dom_scripts(node, *, include_citations=False):
    """Retain visible scientific scripts; leave citation roles to citation tests."""
    for script in list(node.find_all(["sup", "sub", "inf"])):
        if script.find_parent(["math", "tex-math"]) or "ltx_note_mark" in script.get(
            "class", []
        ):
            continue
        if not include_citations and (
            script.find(["a", "xref"]) or script.find_parent(["a", "xref"])
        ):
            continue
        value = script.get_text()
        if not include_citations and not any(
            c.isalnum() or c in "+−-•*" for c in value
        ):
            continue
        script.replace_with(("^" if script.name == "sup" else "_") + "{" + value + "}")


def assert_mathml_formulas(nodes, markdown, subtests=None):
    from contextlib import nullcontext

    import re
    from collections import defaultdict
    from tests.support.canonical_content import (
        math_identifier_text,
        source_tex,
    )

    block_pattern = re.compile(
        r"^[ \t]*\$\$[^\S\n]*\n(.*?)^[ \t]*\$\$[^\S\n]*$", re.M | re.S
    )
    expressions = block_pattern.findall(markdown)
    inline_markdown = block_pattern.sub("", markdown)
    expressions += re.findall(r"\$([^$\n]+)\$", inline_markdown)

    def numbers(text):
        text = without_latex_spacing(text)
        text = re.sub(
            r"\\(?:mkern|kern|hskip|vskip)\s*-?[\d.]+\s*(?:mu|pt|em)", "", text
        )
        text = re.sub(r"\\\\\[[\d.]+pt\]", "", text)
        return "".join(re.findall(r"\d|(?<=\d)\.(?=\d)", text))

    by_numbers = defaultdict(list)
    for expression in expressions:
        by_numbers[numbers(expression)].append(
            (expression, math_identifier_text(expression))
        )

    # A labeled MathML table has one displayed expression per source row.
    # Check its aggregate source facts, including every label in source order.
    for node in nodes:
        labeled = node.find_all("mlabeledtr")
        if not labeled:
            continue
        labels = [
            row.find("mtd", recursive=False).get_text(strip=True) for row in labeled
        ]
        pattern = r"\s*".join(
            re.escape(label) + r"\s*\n[ \t]*\$\$\n(.*?)^[ \t]*\$\$" for label in labels
        )
        for match in re.finditer(pattern, markdown, re.M | re.S):
            expression = "".join(
                label + part for label, part in zip(labels, match.groups(), strict=True)
            )
            by_numbers[numbers(expression)].append(
                (expression, math_identifier_text(expression))
            )

    checked = 0
    for index, node in enumerate(nodes, 1):
        if (
            node.name != "math"
            or source_tex(node)
            or node.find_parent("annotation-xml")
        ):
            continue
        if not node.get_text(strip=True):
            continue
        checked += 1
        facts = node.__dict__.get("_source_mathml")
        if facts is None:
            # Literal unit fragments have no complex math equivalence contract.
            assert not node.find_all(["mfrac", "msqrt", "msub", "msup", "msubsup"])
            facts = {
                "numbers": numbers(node.get_text(" ")),
                "minimum": {},
                "identifiers": [
                    math_identifier_text(n.get_text()) for n in node.find_all("mi")
                ],
                "operators": [],
            }
        expected_numbers = facts["numbers"]
        minimum = facts["minimum"]
        with subtests.test(formula=index) if subtests else nullcontext():
            candidates = by_numbers[expected_numbers]
            identifiers = facts["identifiers"]
            operators = facts["operators"]
            candidates = [
                e
                for e, text in candidates
                if all(identifier in text for identifier in identifiers)
                and mathml_control_words_preserved(node, e)
                and all(
                    text.count(token) >= operators.count(token)
                    for token in set(operators)
                )
            ]

            assert any(
                all(
                    e.count(token) + (e.count("'") if token == "^" else 0) >= count
                    for token, count in minimum.items()
                )
                for e in candidates
            ), (index, expected_numbers, minimum, str(node)[:500])

    return checked


def mathml_control_words_preserved(node, expression):
    """Require whole control words, so matching substrings cannot hide glue."""
    from collections import Counter

    operators = {
        "∫": "int",
        "∬": "iint",
        "∭": "iiint",
        "∑": "sum",
        "∏": "prod",
        "∞": "infty",
    }
    source = Counter(n.get_text(strip=True) for n in node.find_all("mo"))
    commands = Counter(re.findall(r"\\([A-Za-z]+)", expression))
    return all(
        commands[command] + expression.count(symbol) >= source[symbol]
        for symbol, command in operators.items()
    )


def math_semantic_key(value):
    """Retain argument boundaries while ignoring optional TeX grouping braces."""

    def group(pos):
        while pos < len(value) and value[pos].isspace():
            pos += 1
        if pos == len(value):
            return "", pos
        if value[pos] != "{":
            match = re.match(r"\\[A-Za-z]+|.", value[pos:])
            return match[0], pos + len(match[0])
        depth, start = 1, pos + 1
        pos += 1
        while pos < len(value) and depth:
            if value[pos] == "{" and value[pos - 1] != "\\":
                depth += 1
            elif value[pos] == "}" and value[pos - 1] != "\\":
                depth -= 1
            pos += 1
        # A captured source may itself contain an unclosed TeX group. Keep
        # its literal remainder comparable; parser diagnostics cover validity.
        return value[start : pos - 1] if depth == 0 else value[start:], pos

    result = []
    pos = 0
    while pos < len(value):
        match = re.match(
            r"(?<!\\)[_^](?=\s*\{)|\\(?:frac|dfrac|tfrac|sqrt)(?![A-Za-z])", value[pos:]
        )
        if match and (pos == 0 or value[pos - 1] != "\\"):
            command = match[0]
            first, pos = group(pos + len(command))
            kind = {"^": "sup", "_": "sub", r"\sqrt": "root"}.get(command, "frac")
            args = [math_semantic_key(first)]
            if kind == "frac":
                second, pos = group(pos)
                args.append(math_semantic_key(second))
            marker = "⟦" + kind + ":" + "¦".join(args) + "⟧"
            if kind == "sub" and result and result[-1].startswith("⟦sup:"):
                result.insert(len(result) - 1, marker)
            else:
                result.append(marker)
        else:
            if value.startswith((r"\{", r"\}"), pos):
                # Visible fence versus optional grouping is covered separately;
                # ignore either representation only in the cell comparison key.
                pos += 2
                continue
            if value[pos] not in "{}$":
                result.append(value[pos])
            pos += 1
    return "".join(result)
