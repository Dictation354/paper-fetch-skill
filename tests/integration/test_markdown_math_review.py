"""Exercise the review script with the explicitly selected reader's real parser."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.paths import REPO_ROOT


def test_reader_keeps_iop_nested_math_and_arxiv_currency_inline(tmp_path):
    reader = os.environ.get("PAPER_FETCH_REVIEW_READER_ROOT")
    if not reader or not shutil.which("node"):
        pytest.skip("requires the explicitly selected installed LitRoot reader")
    from bs4 import BeautifulSoup
    from paper_fetch.extraction.markdown_render.formulas import (
        render_html_formula_container,
        render_inline_latex_markdown,
    )
    from paper_fetch.providers._arxiv_authors import _arxiv_math_markdown

    nested = (
        r"m\overset{\lower0.2em\hbox{$\smash{\scriptscriptstyle\rightharpoonup}$}} {g}"
    )
    iop = BeautifulSoup(
        '<span class="inline-eqn"><script type="math/tex">'
        + nested
        + "</script></span>",
        "html.parser",
    )
    arxiv = BeautifulSoup(
        r'<math alttext="\$75"><annotation encoding="application/x-tex">\$75</annotation></math>',
        "html.parser",
    )
    expressions = [nested, r"\$75", r"\text{for $x>1$}", r"\$"]
    rendered = [
        render_html_formula_container(iop.span),
        _arxiv_math_markdown(arxiv.math),
        render_inline_latex_markdown(expressions[2]),
        render_inline_latex_markdown(expressions[3]),
    ]
    path = tmp_path / "dollars.md"
    path.write_text("\n\n".join("Before " + value + " after." for value in rendered))
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "scripts/review_markdown_math.mjs"),
            "--modules-root",
            reader,
            "--output",
            str(report),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(report.read_text())
    assert data["mathjax"] == "4.1.3"
    assert "katex" not in data
    assert "mhchem" in data["extensions"]
    row = data["files"][0]
    assert (row["formulas"], row["inline"], row["display"]) == (3, 3, 0)
    assert row["errors"] == []
    assert row["warnings"] == []
    assert row["delimiterCandidates"] == [
        {"line": 3, "column": 1, "text": "Before $75 after."}
    ]
    assert rendered[1] == expressions[1]  # Currency remains ordinary escaped prose.
    assert [rendered[0], rendered[2]] == [
        "$$" + tex + "$$" for tex in [expressions[0], expressions[2]]
    ]
    assert rendered[3] == r"$$ \$ $$"


def test_reader_parses_tex_norms_in_gfm_table_cells(tmp_path):
    reader = os.environ.get("PAPER_FETCH_REVIEW_READER_ROOT")
    if not reader or not shutil.which("node"):
        pytest.skip("requires the explicitly selected installed LitRoot reader")
    from paper_fetch.extraction.markdown_render.table_format import (
        render_aligned_markdown_table,
    )

    path = tmp_path / "table.md"
    path.write_text(
        "\n".join(
            render_aligned_markdown_table(
                [
                    ["Objective", "Value"],
                    [r"$\|x-y\|^2$", "1"],
                ]
            )
        )
    )
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "scripts/review_markdown_math.mjs"),
            "--modules-root",
            reader,
            "--output",
            str(report),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    row = json.loads(report.read_text())["files"][0]
    assert row["formulas"] == 1
    assert row["delimiterCandidates"] == []


def test_reader_parser_covers_inline_display_lists_tables_and_rejects_glue(tmp_path):
    reader = os.environ.get("PAPER_FETCH_REVIEW_READER_ROOT")
    if not reader or not shutil.which("node"):
        pytest.skip(
            "requires an explicit existing Markdown reader installation and Node"
        )
    path = tmp_path / "article.md"
    report = tmp_path / "report.json"
    path.write_text(
        "Inline $\\int SMBdt$.\n\n"
        "$$\n\\begin{split}x&=1\\end{split}\n$$\n\n"
        "1. item\n\n   $$\n   \\sum x\n   $$\n\n"
        "| Formula |\n| --- |\n| $\\iint x$ |\n\n"
        "$\\infty x$\n\n"
        "Bad $\\intSMBdt$, $\\intDdt$, $\\sumx$, $\\iintx$, $\\inftyx$.\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "scripts/review_markdown_math.mjs"),
            "--modules-root",
            reader,
            "--output",
            str(report),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stderr
    data = json.loads(report.read_text())
    assert data["totals"] == {"files": 1, "formulas": 10, "errors": 5, "warnings": 0}
    row = data["files"][0]
    assert row["display"] == 3
    assert [e["expression"] for e in row["errors"]] == [
        r"\intSMBdt",
        r"\intDdt",
        r"\sumx",
        r"\iintx",
        r"\inftyx",
    ]
    assert all(e["line"] == 19 for e in row["errors"])
    assert all("Undefined control sequence" in e["message"] for e in row["errors"])
    assert Path(row["path"]) == path


def test_mathjax_review_locates_errors_and_isolates_document_macros(tmp_path):
    reader = os.environ.get("PAPER_FETCH_REVIEW_READER_ROOT")
    if not reader or not shutil.which("node"):
        pytest.skip("requires the explicitly selected installed LitRoot reader")
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    asset = tmp_path / "figure.svg"
    asset.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    bad_line = r"Bad $\unknownFormula$, $\frac{1}{$."
    first.write_text(
        r"Define $\newcommand{\reviewmacro}{x}$."
        + "\n\n"
        + r"Use $\reviewmacro$, $\ce{H2O}$ and $\cancel{x}$."
        + "\n\n"
        + bad_line
        + "\n\nAfter $x^2$.\n\n"
        + "![Figure](figure.svg)\n\nCash $75\n"
    )
    second.write_text(r"Other $\reviewmacro$ and $y^2$." + "\n")
    result = subprocess.run(
        [
            "node",
            str(REPO_ROOT / "scripts/review_markdown_math.mjs"),
            "--modules-root",
            reader,
            str(first),
            str(second),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stderr
    data = json.loads(result.stdout)
    assert data["mathjax"] == "4.1.3"
    assert data["totals"] == {"files": 2, "formulas": 9, "errors": 3, "warnings": 0}
    one, two = data["files"]
    assert len(one["sha256"]) == 64
    for error, expression in zip(
        one["errors"], [r"\unknownFormula", r"\frac{1}{"], strict=True
    ):
        assert error["expression"] == expression
        assert error["line"] == error["endLine"] == 5
        assert error["column"] == bad_line.index("$" + expression) + 1
        assert error["displayMode"] is False
        assert error["context"] == ["root", "paragraph"]
    assert "Undefined control sequence" in one["errors"][0]["message"]
    assert "brace" in one["errors"][1]["message"].lower()
    assert one["warnings"] == two["warnings"] == []
    assert one["assets"] == [{"line": 9, "url": "figure.svg", "exists": True}]
    assert one["delimiterCandidates"] == [{"line": 11, "column": 1, "text": "Cash $75"}]
    assert [error["expression"] for error in two["errors"]] == [r"\reviewmacro"]
    assert two["errors"][0]["line"] == 1
    assert two["errors"][0]["column"] == 7


def test_reader_renders_preserved_styles_code_symbols_and_links(tmp_path):
    """Use LitRoot's installed plugins and its actual sanitizer schema."""
    reader = os.environ.get("PAPER_FETCH_REVIEW_READER_ROOT")
    if not reader or not shutil.which("node"):
        pytest.skip("requires the explicitly selected installed LitRoot reader")
    from xml.etree import ElementTree as ET
    from paper_fetch.providers._article_markdown_common import render_inline_text
    from paper_fetch.providers._article_markdown_math import render_mathml_expression

    prose = render_inline_text(
        ET.fromstring(
            '<p>para<bold>form</bold>aldehyde; <italic>A</italic><italic>B</italic>; Herb*MAP*YSD; CO<inf>2</inf>; <monospace>&lt;NA&gt;</monospace>; <ext-link href="https://example.org/data_file">data</ext-link>.</p>'
        )
    )
    formula = render_mathml_expression(
        ET.fromstring(
            '<math><mi mathvariant="script">N</mi><mo>~</mo><mi>ln</mi><mfenced separators=""><mn>2</mn><mi>π</mi><mi>t</mi></mfenced></math>'
        )
    )
    markdown = tmp_path / "source.md"
    markdown.write_text(
        prose + "\n\n$$\n" + formula + "\n$$\n\n```\n> x <- NA\n+ y\n```\n"
    )
    script = tmp_path / "reader.mjs"
    script.write_text(r"""
import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
const [reader,path] = process.argv.slice(2);
const require = createRequire(resolve(reader,'package.json'));
const paths = [dirname(require.resolve('react-markdown'))];
const dep = async name => (await import(pathToFileURL(require.resolve(name,{paths})).href));
const {unified} = await dep('unified');
const [parse,gfm,math,rehype,raw,sanitize] = await Promise.all(['remark-parse','remark-gfm','remark-math','remark-rehype','rehype-raw','rehype-sanitize'].map(async name => (await dep(name)).default));
const {defaultSchema} = await dep('rehype-sanitize');
const {rehypeMathjax} = await import(pathToFileURL(resolve(reader,'src/shared/markdown-math.mjs')).href);
const source = await readFile(resolve(reader,'src/renderer/src/MarkdownReader.tsx'),'utf8');
if (!source.includes('rehypeRaw, [rehypeSanitize, sanitizeSchema], rehypeMathjax')) throw new Error('reader plugin order changed');
const expression = source.match(/const sanitizeSchema = ([\s\S]*?)\nconst urlTransform/);
if (!expression) throw new Error('reader sanitizer not found');
const schema = new Function('defaultSchema','return ('+expression[1].trim()+')')(defaultSchema);
const processor = unified().use(parse).use(gfm).use(math).use(rehype,{allowDangerousHtml:true}).use(raw).use(sanitize,schema).use(rehypeMathjax);
const tree = await processor.run(processor.parse(await readFile(path,'utf8')));
const nodes = [];
const content = node => node.type === 'text' ? node.value : (node.children??[]).map(content).join('');
function visit(node) {
 if (node.type==='element') nodes.push({tag:node.tagName,properties:node.properties,text:content(node)});
 for(const child of node.children??[])visit(child);
}
visit(tree);
process.stdout.write(JSON.stringify(nodes));
""")
    completed = subprocess.run(
        ["node", str(script), reader, str(markdown)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    nodes = json.loads(completed.stdout)
    assert any(n["tag"] == "strong" and n["text"] == "form" for n in nodes)
    assert [n["text"] for n in nodes if n["tag"] == "em"] == ["A", "B"]
    assert any(
        n["tag"] == "p" and "paraformaldehyde; AB; Herb*MAP*YSD;" in n["text"]
        for n in nodes
    )
    assert any(n["tag"] == "sub" and n["text"] == "2" for n in nodes)
    assert any(
        n["tag"] == "a" and n["properties"]["href"] == "https://example.org/data_file"
        for n in nodes
    )
    assert any(n["tag"] == "code" and n["text"] == "<NA>" for n in nodes)
    assert any(n["tag"] == "code" and n["text"] == "> x <- NA\n+ y\n" for n in nodes)
    assert any(n["tag"] == "svg" for n in nodes)
    assert any(n["tag"] == "path" for n in nodes)
    assistive_math = [n["text"] for n in nodes if n["tag"] == "mjx-assistive-mml"]
    assert assistive_math and all(
        "∼" in text and "ln" in text and "," not in text for text in assistive_math
    )
