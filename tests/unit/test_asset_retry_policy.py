from __future__ import annotations

import pytest

from paper_fetch.providers import _arxiv_assets, _ieee_html, elsevier, springer
from paper_fetch.providers._asset_retry import (
    assets_for_network_retry,
    merge_asset_failures,
    merge_asset_retry_results,
)
from paper_fetch.providers.browser_workflow import assets as browser_assets


@pytest.mark.parametrize(
    ("policy", "asset", "retry_asset", "failure", "retry_failure"),
    [
        (
            _arxiv_assets.ARXIV_ASSET_RETRY_POLICY,
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "Caption",
                "url": "https://arxiv.test/fig1.png",
            },
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "Caption",
                "download_url": "https://arxiv.test/fig1.png",
                "path": "/tmp/arxiv-fig1.png",
            },
            {
                "heading": "Figure 1",
                "caption": "Caption",
                "source_url": "https://arxiv.test/fig1.png",
                "reason": "Network error: timed out",
            },
            {
                "heading": "Figure 1",
                "caption": "Caption",
                "source_url": "https://arxiv.test/fig1.png",
                "reason": "connection reset",
            },
        ),
        (
            elsevier.ELSEVIER_ASSET_RETRY_POLICY,
            {
                "asset_type": "image",
                "source_ref": "fig0",
                "source_url": "https://api.elsevier.com/content/object/eid/fig0",
            },
            {
                "asset_type": "image",
                "source_ref": "fig0",
                "download_url": "https://api.elsevier.com/content/object/eid/fig0",
                "path": "/tmp/elsevier-fig0.png",
            },
            {
                "asset_type": "image",
                "section": "body",
                "source_ref": "fig0",
                "source_url": "https://api.elsevier.com/content/object/eid/fig0",
                "error_category": "timeout",
                "reason": "Network error: timed out",
            },
            {
                "asset_type": "image",
                "section": "body",
                "source_ref": "fig0",
                "source_url": "https://api.elsevier.com/content/object/eid/fig0",
                "error_category": "connection_reset",
                "reason": "connection reset",
            },
        ),
        (
            springer.SPRINGER_ASSET_RETRY_POLICY,
            {
                "kind": "figure",
                "heading": "Figure 1",
                "url": "https://media.springernature.com/full/fig1.png",
            },
            {
                "kind": "figure",
                "heading": "Figure 1",
                "url": "https://media.springernature.com/full/fig1.png",
                "path": "/tmp/springer-fig1.png",
            },
            {
                "source_url": "https://media.springernature.com/full/fig1.png",
                "reason": "Network error: timed out",
            },
            {
                "source_url": "https://media.springernature.com/full/fig1.png",
                "reason": "connection reset",
            },
        ),
        (
            _ieee_html.IEEE_ASSET_RETRY_POLICY,
            {
                "kind": "table",
                "heading": "Table I.",
                "full_size_url": "https://ieee.test/table-large.gif",
                "preview_url": "https://ieee.test/table-small.gif",
            },
            {
                "kind": "table",
                "heading": "Table I.",
                "download_url": "https://ieee.test/table-large.gif",
                "path": "/tmp/ieee-table.gif",
            },
            {
                "source_url": "https://ieee.test/table-large.gif",
                "reason": "Network error: timed out",
            },
            {
                "source_url": "https://ieee.test/table-large.gif",
                "reason": "connection reset",
            },
        ),
        (
            browser_assets.BROWSER_WORKFLOW_ASSET_RETRY_POLICY,
            {
                "kind": "figure",
                "heading": "Figure 1",
                "url": "https://browser.test/fig1.png",
                "section": "body",
            },
            {
                "kind": "figure",
                "heading": "Figure 1",
                "download_url": "https://browser.test/fig1.png",
                "section": "body",
                "path": "/tmp/browser-fig1.png",
            },
            {
                "kind": "figure",
                "heading": "Figure 1",
                "source_url": "https://browser.test/fig1.png",
                "section": "body",
                "reason": "cloudflare_challenge",
            },
            {
                "kind": "figure",
                "heading": "Figure 1",
                "source_url": "https://browser.test/fig1.png",
                "section": "body",
                "reason": "browser_context_refreshed_but_failed",
            },
        ),
    ],
)
def test_provider_asset_retry_policies_round_trip_merge_and_retry(
    policy,
    asset,
    retry_asset,
    failure,
    retry_failure,
) -> None:
    assert assets_for_network_retry([asset], [failure], policy=policy) == [asset]

    merged_assets = merge_asset_retry_results([asset], [retry_asset], policy=policy)
    assert merged_assets == [{**asset, **retry_asset}]

    merged_failures = merge_asset_failures(
        [failure],
        [retry_failure],
        policy=policy,
    )
    assert merged_failures == [retry_failure]


def test_merge_asset_failures_drops_retried_previous_failure() -> None:
    asset = {
        "kind": "figure",
        "heading": "Figure 1",
        "caption": "Caption",
        "url": "https://arxiv.test/fig1.png",
    }
    retryable_failure = {
        "kind": "figure",
        "heading": "Figure 1",
        "caption": "Caption",
        "source_url": "https://arxiv.test/fig1.png",
        "error_category": "timeout",
        "reason": "Network error: timed out",
    }
    retained_failure = {
        "kind": "figure",
        "heading": "Figure 2",
        "caption": "Caption",
        "source_url": "https://arxiv.test/fig2.png",
        "status": 404,
        "reason": "HTTP 404",
    }

    assert merge_asset_failures(
        [retryable_failure, retained_failure],
        [],
        policy=_arxiv_assets.ARXIV_ASSET_RETRY_POLICY,
        retried_assets=[asset],
    ) == [retained_failure]


def test_merge_asset_retry_results_dedupes_previous_by_policy_key() -> None:
    first = {
        "kind": "figure",
        "heading": "Figure 1",
        "caption": "Caption",
        "url": "https://arxiv.test/fig1.png",
    }
    second = {
        "kind": "figure",
        "heading": "Figure 1",
        "caption": "Caption",
        "url": "https://arxiv.test/fig1.png",
        "path": "/tmp/fig1.png",
    }

    assert merge_asset_retry_results(
        [first, second],
        [],
        policy=_arxiv_assets.ARXIV_ASSET_RETRY_POLICY,
    ) == [{**first, **second}]
