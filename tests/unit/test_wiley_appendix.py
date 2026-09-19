"""Minimal Wiley DOM boundary scenarios; complete papers live in golden."""

import pytest
from bs4 import BeautifulSoup

from paper_fetch.providers._wiley_html import wiley_body_container


def appendix(letter, attrs=""):
    return (
        f'<div class="article-section__sub-content" id="paper-app-000{letter}" {attrs}>'
        f'<h2>Appendix {letter}</h2><section class="article-section__content">'
        f'<p>Scientific appendix {letter} <a href="#ref">citation</a>.</p>'
        "</section></div>"
    )


def document(tail):
    return BeautifulSoup(
        '<section class="article-section__full">'
        '<section class="article-section__content"><h2>Conclusions</h2><p>Body.</p></section>'
        '<div class="article-section__content"><h2>Acknowledgments</h2><p>Thanks.</p></div>'
        + tail
        + '<section class="article-section__references"><h2>References</h2></section>'
        "</section>",
        "html.parser",
    )


@pytest.mark.parametrize("letters", ["", "1", "12"])
def test_only_real_appendices_move_before_back_matter_in_source_order(letters):
    soup = document("".join(appendix(letter) for letter in letters))
    wiley_body_container(soup)
    assert [h.get_text() for h in soup.select("h2")] == [
        "Conclusions",
        *[f"Appendix {letter}" for letter in letters],
        "Acknowledgments",
        "References",
    ]
    for letter in letters:
        content = soup.select_one(f"#paper-app-000{letter} > section")
        assert content.find("h2").get_text() == f"Appendix {letter}"
        assert content.select_one("a")["href"] == "#ref"
    once = str(soup)
    wiley_body_container(soup)
    assert str(soup) == once


@pytest.mark.parametrize(
    "tail",
    [
        appendix("1", "hidden"),
        appendix("1", 'aria-hidden="true"'),
        appendix("1", 'style="display: none"'),
        appendix("1", 'style="visibility: hidden"'),
        "<aside>" + appendix("1") + "</aside>",
        '<section class="article-section__supporting">' + appendix("1") + "</section>",
        '<div class="article-section__sub-content"><h2>Appendix 1</h2><p>Sidebar.</p></div>',
    ],
)
def test_hidden_sidebar_and_unlabelled_appendix_headings_are_not_promoted(tail):
    soup = document(tail)
    before = str(soup)
    wiley_body_container(soup)
    assert str(soup) == before
