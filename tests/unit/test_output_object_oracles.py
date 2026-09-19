"""P09 minimal corruption tests for independent source-object assertions."""

from bs4 import BeautifulSoup
import pytest

from tests.support.object_content import (
    assert_image_occurrences,
    assert_source_object_link,
    assert_svg_content,
    svg_content_signature,
)


def test_source_target_oracle_rejects_deleted_wrong_and_unregistered_targets():
    source = BeautifulSoup(
        '<article><p id="ref1">First</p><p id="ref2">Second</p></article>', "lxml"
    )
    kwargs = dict(
        source_url="https://publisher.example/article", target_id="ref1", label="1"
    )
    valid = "See [1](https://publisher.example/article#ref1)."
    assert_source_object_link(source, valid, **kwargs)
    for broken in (
        "See 1.",
        valid.replace("#ref1", "#missing"),
        valid.replace("#ref1", "#ref2"),
        valid.replace("publisher.example/article", "publisher.example/other"),
    ):
        with pytest.raises(AssertionError):
            assert_source_object_link(source, broken, **kwargs)
    source.find(id="ref1").decompose()
    with pytest.raises(AssertionError):
        assert_source_object_link(source, valid, **kwargs)


def test_occurrence_oracle_keeps_source_reuse_but_rejects_missing_duplicate_or_moved_graphs():
    expected = ["a.svg", "b.svg", "a.svg"]
    valid = "![Figure 1](a.svg) ![Figure 2](b.svg) ![Figure 3](a.svg)"
    assert_image_occurrences(valid, expected)
    for broken in (
        valid.replace("![Figure 2](b.svg)", ""),
        valid + " ![Figure 1](a.svg)",
        valid.replace("b.svg", "a.svg"),
    ):
        with pytest.raises(AssertionError):
            assert_image_occurrences(broken, expected)


@pytest.mark.parametrize(
    "old,new",
    [
        ("M 1 2 L 3 4", "M 1 2 L 30 40"),
        ("translate(2 3)", "translate(8 9)"),
        ("Meaning", "Other"),
        ("<mi>x</mi>", "<mi>y</mi>"),
        ("<msup>", "<mrow>"),
        ('<path d="M 1 2 L 3 4"/>', ""),
    ],
)
def test_svg_oracle_rejects_geometry_transform_foreign_text_and_math_changes(old, new):
    source = """<svg id="diagram" viewBox="0 0 40 30"><g transform="translate(2 3)"><path d="M 1 2 L 3 4"/></g><foreignObject><span>Meaning <math><msup><mi>x</mi><mn>2</mn></msup></math></span></foreignObject></svg>"""
    expected = svg_content_signature(BeautifulSoup(source, "lxml").svg)
    vector = (
        source.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ')
        .replace("<span>", '<span xmlns="http://www.w3.org/1999/xhtml">')
        .replace("<math>", '<math xmlns="http://www.w3.org/1998/Math/MathML">')
    )
    assert_svg_content(expected, vector.encode())
    broken = (
        vector.replace(old, new).replace("</msup>", "</mrow>")
        if old == "<msup>"
        else vector.replace(old, new)
    )
    with pytest.raises(AssertionError):
        assert_svg_content(expected, broken.encode())
