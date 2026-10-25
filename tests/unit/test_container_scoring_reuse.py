from collections import Counter
from dataclasses import replace
from unittest import mock

from bs4 import BeautifulSoup

from paper_fetch.quality import html_availability as availability


def _soup_and_policy(monkeypatch):
    soup = BeautifulSoup(
        "<html><body><article><p>Identical body.</p></article>"
        "<article><p>Identical body.</p></article></body></html>",
        "html.parser",
    )
    monkeypatch.setattr(
        availability,
        "site_rule_for_publisher",
        lambda _: {"candidate_selectors": ["body", "article", "article p"]},
    )
    soup.body.append("Page shell. " * 100)
    return soup, availability.HtmlContainerSelectionPolicy(
        prefer_complete_ancestor=True,
        avoid_page_level_container=True,
    )


def test_selection_scores_each_node_once_including_shared_ancestors(monkeypatch):
    soup, policy = _soup_and_policy(monkeypatch)
    with (
        mock.patch.object(
            availability, "score_container", wraps=availability.score_container
        ) as scores,
        mock.patch.object(
            availability,
            "container_completeness_score",
            wraps=availability.container_completeness_score,
        ) as completeness,
        mock.patch.object(
            availability,
            "_prefer_complete_ancestor",
            wraps=availability._prefer_complete_ancestor,
        ) as ancestors,
    ):
        assert (
            availability.select_best_container(soup, None, policy=policy)
            is soup.select("article")[0]
        )
        for operation in (scores, completeness, ancestors):
            identities = Counter(id(call.args[0]) for call in operation.call_args_list)
            assert identities and max(identities.values()) == 1
        assert len(scores.call_args_list) == 5
        # Equal BeautifulSoup Tags are still separate scoring identities.
        assert soup.select("article")[0] == soup.select("article")[1]
        availability.select_best_container(soup, None, policy=policy)
        assert scores.call_count == 10


def test_equal_candidate_scores_keep_first_node(monkeypatch):
    soup, policy = _soup_and_policy(monkeypatch)
    monkeypatch.setattr(
        availability,
        "site_rule_for_publisher",
        lambda _: {"candidate_selectors": ["article"]},
    )
    selected = availability.select_best_container(
        soup,
        None,
        policy=replace(policy, prefer_complete_ancestor=False),
    )
    assert selected is soup.select("article")[0]


def test_mutating_refiner_keeps_order_and_gets_uncached_callbacks(monkeypatch):
    soup, policy = _soup_and_policy(monkeypatch)
    articles = soup.select("article")
    order = []

    def refine(node, *, score_container, container_completeness_score, **_):
        order.append(node)
        before = score_container(node), container_completeness_score(node)
        node.append(soup.new_tag("h1"))
        node.h1.string = "Added title"
        after = score_container(node), container_completeness_score(node)
        assert after[0] > before[0]
        if before[1] < 40:
            assert after[1] == before[1] + 40
        return node

    monkeypatch.setattr(
        availability,
        "site_rule_for_publisher",
        lambda _: {"candidate_selectors": ["body", "article"]},
    )
    selected = availability.select_best_container(
        soup,
        None,
        policy=replace(
            policy, prefer_complete_ancestor=False, refine_selected_container=refine
        ),
    )
    assert [id(node) for node in order] == [
        id(soup.body),
        id(soup.body),
        *map(id, articles),
    ]
    assert selected is articles[0]
    # A new selection must score the modified DOM rather than reuse old values.
    articles[1].append("Much more body text. " * 100)
    assert (
        availability.select_best_container(
            soup,
            None,
            policy=replace(policy, prefer_complete_ancestor=False),
        )
        is articles[1]
    )
