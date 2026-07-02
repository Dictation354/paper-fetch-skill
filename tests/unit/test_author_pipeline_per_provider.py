from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from paper_fetch.providers import (
    _arxiv_authors,
    _arxiv_html,
    _ams_html,
    _ieee_metadata,
    _pnas_html,
    _science_html,
    _springer_html,
    _wiley_html,
)


def _jsonld(payload: object) -> str:
    return f'<script type="application/ld+json">{json.dumps(payload)}</script>'


@pytest.mark.parametrize(
    ("pipeline", "expected_names"),
    (
        (_science_html._AUTHOR_PIPELINE, ["datalayer", "dom"]),
        (_pnas_html._AUTHOR_PIPELINE, ["dom", "meta"]),
        (_wiley_html._AUTHOR_PIPELINE, ["meta", "jsonld", "dom"]),
        (_ams_html._AUTHOR_PIPELINE, ["meta", "property", "selector"]),
        (_springer_html._AUTHOR_PIPELINE, ["meta", "jsonld", "dom"]),
        (_arxiv_authors._AUTHOR_PIPELINE, ["creators", "person-names"]),
        (_ieee_metadata._AUTHOR_PIPELINE, ["authors", "authorsList"]),
        (
            _ieee_metadata._AUTHOR_NAME_PIPELINE,
            ["name-field", "first-last", "scalar"],
        ),
    ),
)
def test_provider_author_pipelines_use_named_steps(
    pipeline: object, expected_names: list[str]
) -> None:
    assert [step.name for step in pipeline.steps] == expected_names


@pytest.mark.parametrize(
    ("extract_authors", "html", "expected"),
    (
        (
            _science_html.extract_authors,
            """
            <html>
              <script>
                AAASdataLayer={"page":{"pageInfo":{"author":"Science Primary|Science Second"}}};
              </script>
              <div class="contributors">
                <div property="author"><span property="name">Science DOM</span></div>
              </div>
            </html>
            """,
            ["Science Primary", "Science Second"],
        ),
        (
            _pnas_html.extract_authors,
            """
            <html>
              <head><meta name="citation_author" content="PNAS Meta"></head>
              <body>
                <div class="contributors">
                  <div property="author"><span property="name">PNAS DOM</span></div>
                </div>
              </body>
            </html>
            """,
            ["PNAS DOM"],
        ),
        (
            _wiley_html.extract_authors,
            """
            <html>
              <head><meta name="citation_author" content="Wiley Meta"></head>
              <body>
            """
            + _jsonld(
                {
                    "@type": "ScholarlyArticle",
                    "author": [{"name": "Wiley JSON-LD"}],
                }
            )
            + """
                <div class="loa-authors-trunc">
                  <a class="author-name">Wiley DOM</a>
                </div>
              </body>
            </html>
            """,
            ["Wiley Meta"],
        ),
        (
            _ams_html.extract_authors,
            """
            <html>
              <head><meta name="citation_author" content="AMS Meta"></head>
              <body><div class="authors"><a>AMS Selector</a></div></body>
            </html>
            """,
            ["AMS Meta"],
        ),
        (
            _springer_html.extract_authors,
            """
            <html>
              <head><meta name="citation_author" content="Springer Meta"></head>
              <body>
            """
            + _jsonld(
                {
                    "@type": "WebPage",
                    "mainEntity": {"author": [{"name": "Springer JSON-LD"}]},
                }
            )
            + """
                <ol class="c-article-author-list">
                  <li><span itemprop="name">Springer DOM</span></li>
                </ol>
              </body>
            </html>
            """,
            ["Springer Meta"],
        ),
    ),
)
def test_provider_author_pipelines_stop_on_first_non_empty_step(
    extract_authors: Callable[[str], list[str]], html: str, expected: list[str]
) -> None:
    assert extract_authors(html) == expected


@pytest.mark.parametrize(
    ("extract_authors", "html", "expected"),
    (
        (
            _science_html.extract_authors,
            """
            <div class="contributors">
              <div property="author">
                <span property="givenName">Science</span>
                <span property="familyName">DOM</span>
              </div>
            </div>
            """,
            ["Science DOM"],
        ),
        (
            _pnas_html.extract_authors,
            '<meta name="dc.creator" content="PNAS Meta Fallback">',
            ["PNAS Meta Fallback"],
        ),
        (
            _wiley_html.extract_authors,
            _jsonld(
                {
                    "@type": "Article",
                    "author": [{"name": "Wiley JSON Fallback"}],
                }
            ),
            ["Wiley JSON Fallback"],
        ),
        (
            _wiley_html.extract_authors,
            """
            <div class="loa-authors-trunc">
              <a class="author-name">Wiley DOM Fallback</a>
            </div>
            """,
            ["Wiley DOM Fallback"],
        ),
        (
            _ams_html.extract_authors,
            '<div property="author"><span property="name">AMS Property</span></div>',
            ["AMS Property"],
        ),
        (
            _ams_html.extract_authors,
            '<div class="authors"><a>AMS Selector Fallback</a></div>',
            ["AMS Selector Fallback"],
        ),
        (
            _springer_html.extract_authors,
            _jsonld(
                {
                    "@type": "ScholarlyArticle",
                    "mainEntity": {"author": [{"name": "Springer JSON"}]},
                }
            ),
            ["Springer JSON"],
        ),
        (
            _springer_html.extract_authors,
            """
            <ol class="c-article-author-list">
              <li><span itemprop="name">Springer DOM Fallback</span></li>
            </ol>
            """,
            ["Springer DOM Fallback"],
        ),
    ),
)
def test_provider_author_pipelines_fall_back_by_step(
    extract_authors: Callable[[str], list[str]], html: str, expected: list[str]
) -> None:
    assert extract_authors(html) == expected


def test_arxiv_author_pipeline_prefers_multiple_creator_nodes() -> None:
    soup = _arxiv_html.BeautifulSoup(
        """
        <article>
          <div class="ltx_creator ltx_role_author">
            <span class="ltx_personname">Ada Lovelace</span>
          </div>
          <div class="ltx_creator ltx_role_author">
            <span class="ltx_personname">Grace Hopper</span>
          </div>
          <span class="ltx_personname">Ignored Person Node</span>
        </article>
        """,
        "html.parser",
    )

    assert _arxiv_authors._AUTHOR_PIPELINE(str(soup.article)) == [
        "Ada Lovelace",
        "Grace Hopper",
    ]


def test_arxiv_author_pipeline_falls_back_to_person_boundary_split() -> None:
    soup = _arxiv_html.BeautifulSoup(
        """
        <article>
          <span class="ltx_personname">
            Katherine Johnson<br>
            <span>Department of Mathematics, Example University, Russia</span>
          </span>
          <span class="ltx_personname">Alan Turing and Alonzo Church</span>
        </article>
        """,
        "html.parser",
    )

    assert _arxiv_authors._AUTHOR_PIPELINE(str(soup.article)) == [
        "Katherine Johnson",
        "Alan Turing",
        "Alonzo Church",
    ]


def test_ieee_author_pipeline_handles_metadata_author_shapes() -> None:
    metadata = {
        "authors": [
            {"preferredName": "Ada Preferred", "firstName": "Ignored"},
            {"firstName": "Grace", "lastName": "Hopper"},
            "Alan Turing",
            {"authorName": "Katherine Johnson"},
            {"name": "Ada Preferred"},
        ]
    }

    assert _ieee_metadata._AUTHOR_PIPELINE(json.dumps(metadata)) == [
        "Ada Preferred",
        "Grace Hopper",
        "Alan Turing",
        "Katherine Johnson",
    ]


def test_ieee_author_pipeline_uses_authors_before_authors_list() -> None:
    metadata = {
        "authors": [{"name": "Primary Author"}],
        "authorsList": [{"name": "Fallback Author"}],
    }

    assert _ieee_metadata._AUTHOR_PIPELINE(json.dumps(metadata)) == ["Primary Author"]


def test_ieee_author_pipeline_falls_back_to_authors_list_container() -> None:
    metadata = {
        "authorsList": {
            "authors": [
                {"fullName": "List Author"},
                {"firstName": "Second", "lastName": "Author"},
            ]
        }
    }

    assert _ieee_metadata._AUTHOR_PIPELINE(json.dumps(metadata)) == [
        "List Author",
        "Second Author",
    ]
