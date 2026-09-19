"""OUP and PNAS full captured articles replay through real MathML backends."""

import re

from bs4 import BeautifulSoup
import pytest

from paper_fetch.formula.convert import formula_runtime_env
from tests.paths import REPO_ROOT
from tests.support.mathml_backends import installed_formula_env
from tests.support.verified_source_inputs import (
    build_verified_source_article,
    inspect_original,
)


@pytest.mark.parametrize("backend", ["texmath", "mathml-to-latex"])
@pytest.mark.parametrize(
    "doi, provider, filename",
    [
        (
            "10.1093/bioinformatics/btaa153",
            "oxfordacademic",
            "001-http_response_entity.html",
        ),
        ("10.1073/pnas.2310157121", "pnas", "002-camoufox-selector-dom.html"),
    ],
)
def test_real_article_mathml_preserves_error_content_and_spacing(
    backend, doi, provider, filename
):
    sample_id = doi.replace("/", "_")
    path = (
        REPO_ROOT
        / "tests/fixtures/golden_criteria"
        / sample_id
        / "acquisition/source-completion-2026-09-18"
        / filename
    )
    body = path.read_bytes()
    source_url = "https://doi.org/" + doi
    identity = inspect_original(body, provider, doi, source_url)
    assert identity and identity["identity"] == "matched"
    source = BeautifulSoup(body.decode(), "lxml")
    with formula_runtime_env(installed_formula_env(backend)):
        article = build_verified_source_article(
            dict(
                sample_id=sample_id,
                doi=doi,
                provider=provider,
                format="html",
                source=str(path.relative_to(REPO_ROOT)),
                source_url=source_url,
                identity=identity,
            )
        )
        markdown = article.to_ai_markdown(
            include_refs="all", max_tokens="full_text", asset_profile="all"
        )
    if provider == "oxfordacademic":
        assert len(source.select("math merror")) == 1
        formula = next(
            part
            for part in markdown.split("$")
            if re.search(r"C,\s*w\^\{\(t\)\}", part) and r"\frac{k - 1}{K})" in part
        )
        assert r"\Theta^{(t +" in formula
        assert re.search(r"C,\s*w\^\{\(t\)\}", formula)
        assert any("1 merror" in warning for warning in article.quality.warnings)
    else:
        assert source.select_one("math#me3 mspace")["width"] == "40pt"
        equation = next(
            block
            for block in re.findall(r"\$\$\s*(.*?)\$\$", markdown, re.S)
            if r"\hspace{40pt}" in block
        )
        assert r"\mkern7200mu" not in markdown
        for term in (
            "annual",
            "Clearing",
            "Fire",
            "Logging",
            "Windthrow",
            "Other",
            "Growth",
        ):
            assert term in equation
        assert "No\\ change" in equation or "No change" in equation
    assert article.quality.has_fulltext
    assert "PAPERFETCHMATHSPACE" not in markdown
