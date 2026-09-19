"""Captured HTML object identities, occurrence counts and algorithm positions.

Source download completion is injected; these assertions cover HTML assembly,
not archive acquisition or image byte fidelity.
"""

from collections import Counter
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import pytest

from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers._arxiv_assets import _arxiv_source_downloaded_asset
from tests.support.arxiv_graphic_replay import (
    graphic_source,
    graphic_payload,
    graphic_article,
    graphic_acceptance,
)

REVIEW_IDS = (
    "1406.2661v1",
    "2006.11239v2",
    "2605.06663v1",
    "2605.06665v1",
    "2605.06666v1",
    "2605.06667v1",
)


@pytest.mark.parametrize("arxiv_id", REVIEW_IDS)
def test_source_download_aliases_preserve_original_raster_occurrences(arxiv_id):
    soup = BeautifulSoup(graphic_source(arxiv_id).read_bytes(), "lxml")
    client, extracted, payload = graphic_payload(arxiv_id)
    originals = Counter(
        urljoin(payload.content.source_url, node["src"])
        for node in soup.select("article figure img[src]")
        if node["src"]
    )
    downloads = []
    paths = {}
    for asset in extracted.extracted_assets:
        if asset["url"] not in originals:
            continue
        path = paths.setdefault(asset["url"], f"body_assets/image_{len(paths)}.png")
        downloads.append(
            _arxiv_source_downloaded_asset(
                asset,
                arxiv_id=arxiv_id,
                source_archive_url=f"https://arxiv.org/e-print/{arxiv_id}",
                source_path=PurePosixPath(urlsplit(asset["url"]).path).name,
                content_type="image/png",
                saved_path=path,
                output_bytes=100,
                width=100,
                height=100,
            )
        )
    _, original_markdown = graphic_article(client, extracted, payload)
    _, markdown = graphic_article(client, extracted, payload, downloads)
    # Reused files retain the label of each source occurrence, not the first
    # asset's heading (DDPM Figure 13/14 reuse Figure 1/6 files).
    assert Counter(
        (image.alt, image.url) for image in iter_markdown_images(markdown)
    ) == Counter(
        (image.alt, paths.get(image.url, image.url))
        for image in iter_markdown_images(original_markdown)
    )
    actual = Counter(image.url for image in iter_markdown_images(markdown))
    assert paths
    for remote, count in originals.items():
        assert actual[paths.get(remote, remote)] == count, (
            arxiv_id,
            remote,
            count,
            actual,
        )
        if remote in paths:
            assert actual[remote] == 0


@pytest.mark.parametrize("arxiv_id", ["2006.11239v2", "2605.06667v1"])
def test_unlocalized_captured_body_figures_fail_strict_local_acceptance(arxiv_id):
    client, extracted, payload = graphic_payload(arxiv_id)
    article, markdown = graphic_article(client, extracted, payload)
    remote = {
        image.url
        for image in iter_markdown_images(markdown)
        if image.url.startswith("https://")
    }
    assert remote
    registered = {asset.original_url for asset in article.assets}
    assert remote <= registered
    assert not graphic_acceptance(
        article, markdown, require_local=True
    ).asset.local_body_assets_satisfied


def test_ddpm_algorithms_keep_their_source_sections_and_order():
    soup = BeautifulSoup(graphic_source("2006.11239v2").read_bytes(), "lxml")
    client, extracted, payload = graphic_payload("2006.11239v2")
    _, markdown = graphic_article(client, extracted, payload)
    positions = []
    for number, section in (
        (1, "S3.SS2"),
        (2, "S3.SS2"),
        (3, "S4.SS3.SSS0.Px1"),
        (4, "S4.SS3.SSS0.Px1"),
    ):
        node = soup.find(id=f"alg{number}")
        assert node.find_parent("section")["id"] == section
        label = node.find("figcaption").get_text(" ", strip=True)
        assert label.startswith(f"Algorithm {number}")
        position = markdown.index(f"**Algorithm {number}.")
        positions.append(position)
    assert positions == sorted(positions)
    assert (
        markdown.index("## 3.2 Reverse process")
        < positions[0]
        < positions[1]
        < markdown.index("## 3.3")
    )
    assert (
        markdown.index("Progressive lossy compression")
        < positions[2]
        < positions[3]
        < markdown.index("When applied to")
    )
    assert extracted.diagnostics["extraction"]["semantic_block_appended_count"] == 0


@pytest.mark.parametrize(
    "arxiv_id,node_ids",
    [
        ("2006.11239v2", ("S2.F2", "S4.F4.fig1", "S4.F4.fig2", "S4.F6", "S4.F7")),
        ("2605.06667v1", ("S0.F1", "S3.F2")),
    ],
)
def test_seven_reviewed_figures_match_source_members_by_identity(arxiv_id, node_ids):
    from paper_fetch.providers._arxiv_assets import (
        _match_source_figures_to_html_placeholders,
    )

    soup = BeautifulSoup(graphic_source(arxiv_id).read_bytes(), "lxml")
    _, extracted, payload = graphic_payload(arxiv_id)
    placeholders = []
    members = []
    expected = []
    for node_id in node_ids:
        image = soup.find(id=node_id).find("img")
        url = urljoin(payload.content.source_url, image["src"])
        path = url.split(f"/{arxiv_id}/", 1)[1]
        asset = next(a for a in extracted.extracted_assets if a["url"] == url)
        placeholders.append(asset)
        expected.append(path)
        members.append({"source_path": path, "caption": "Unrelated source order"})
    # Reordering and misleading captions must not change which object is bound.
    members.reverse()
    for member, placeholder in zip(members, placeholders, strict=True):
        member["caption"] = placeholder["caption"]
    matches = _match_source_figures_to_html_placeholders(placeholders, members)
    assert [member["source_path"] for _, member in matches] == expected
    for placeholder, path in zip(placeholders, expected, strict=True):
        without_target = [member for member in members if member["source_path"] != path]
        assert (
            _match_source_figures_to_html_placeholders([placeholder], without_target)[
                0
            ][1]
            is None
        )
