"""Seven captured LaTeXML articles: node identity, in-place figures and title."""

import base64
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
import pytest

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers._arxiv_graphics import INLINE_SVG_PREFIX
from tests.support.canonical_content import source_prose_blocks
from tests.support.object_content import (
    assert_object_position,
    assert_image_occurrences,
    svg_content_signature,
    assert_svg_content,
)
from tests.support.arxiv_graphic_replay import (
    GRAPHIC_IDS,
    graphic_source,
    graphic_payload,
    graphic_article,
    graphic_acceptance,
)


def _assert_graphic_output(markdown, objects, source_url, runs):
    images = list(iter_markdown_images(markdown))
    inline = {}
    for image in images:
        if image.url.startswith("data:image/svg+xml;base64,"):
            body = base64.b64decode(image.url.split(",", 1)[1])
            node_id = ET.fromstring(body).get("id")
            inline.setdefault(node_id, []).append((image, body))
    retained = []
    for node, signature in objects:
        if node.name == "object":
            expected = urljoin(source_url, node["data"])
            matched = [image for image in images if image.url == expected]
            assert len(matched) == 1, (
                node["id"],
                "remote SVG occurrence lost/duplicated",
            )
            image = matched[0]
            assert expected.split("?", 1)[0].endswith(".svg")
        else:
            matched = inline.get(node["id"], [])
            assert len(matched) == 1, (
                node["id"],
                "inline SVG occurrence lost/duplicated",
            )
            image, body = matched[0]
            assert_svg_content(signature, body)
        assert assert_object_position(node, markdown, image.start, image.end, runs), (
            node["id"]
        )
        retained.append(image)
    assert [image.start for image in retained] == sorted(
        image.start for image in retained
    )
    return retained


@pytest.mark.parametrize("arxiv_id", GRAPHIC_IDS)
def test_captured_graphic_nodes_keep_source_identity_and_original_position(arxiv_id):
    # Register original type, node identity and complete vector tree before rendering.
    source = BeautifulSoup(graphic_source(arxiv_id).read_bytes(), "lxml")
    objects = []
    for node_id in GRAPHIC_IDS[arxiv_id]:
        node = source.find(id=node_id)
        assert node is not None and node.name in {"object", "svg"}
        objects.append(
            (node, svg_content_signature(node) if node.name == "svg" else None)
        )
    runs = [
        run
        for _, group in source_prose_blocks(
            SimpleNamespace(provider="arxiv", doi="10.48550/arxiv." + arxiv_id), source
        )
        for run in group
    ]
    client, extracted, payload = graphic_payload(arxiv_id)
    article, markdown = graphic_article(client, extracted, payload)
    images = _assert_graphic_output(markdown, objects, payload.content.source_url, runs)
    for (node, _), image in zip(objects, images, strict=True):
        assets = [
            a for a in extracted.extracted_assets if a.get("image_id") == node["id"]
        ]
        assert len(assets) == 1 and assets[0]["url"] == image.url
        expected_kind = (
            "arxiv_html_object" if node.name == "object" else "arxiv_inline_svg"
        )
        assert assets[0]["source_kind"] == expected_kind
        for damaged in (
            markdown[: image.start] + markdown[image.end :],
            markdown + "\n" + image.text,
        ):
            with pytest.raises(AssertionError):
                _assert_graphic_output(
                    damaged, objects, payload.content.source_url, runs
                )
        if node.name == "svg":
            vector = ET.fromstring(base64.b64decode(image.url.split(",", 1)[1]))
            path = vector.find(".//{http://www.w3.org/2000/svg}path")
            assert path is not None
            path.set("d", "M 0 0 L 1 1")
            bad_url = (
                "data:image/svg+xml;base64,"
                + base64.b64encode(ET.tostring(vector)).decode()
            )
            with pytest.raises(AssertionError):
                _assert_graphic_output(
                    markdown.replace(image.url, bad_url),
                    objects,
                    payload.content.source_url,
                    runs,
                )
    assert article.quality.has_fulltext
    assert (
        graphic_acceptance(article, markdown, require_local=True).asset.body_local == 0
    )
    assert (
        graphic_acceptance(article, markdown, require_local=True).asset.status
        == "degraded"
    )


def test_captured_gan_title_yaml_h1_and_meaningful_body():
    client, extracted, payload = graphic_payload("1406.2661v1")
    article, markdown = graphic_article(client, extracted, payload)
    assert (
        extracted.merged_metadata["title"]
        == article.metadata.title
        == "Generative Adversarial Nets"
    )
    assert 'title: "Generative Adversarial Nets"' in markdown
    assert "# Generative Adversarial Nets\n" in markdown
    assert "Thanks" not in markdown.split("## Abstract", 1)[0]
    between = markdown.split("## Abstract", 1)[1].split("## 1 Introduction", 1)[0]
    assert "|" not in between
    assert "We propose a new framework for estimating generative models" in between
    assert "The promise of deep learning" in markdown
    assert "## 6 Advantages and disadvantages" in markdown
    assert "## 7 Conclusions and future work" in markdown


def test_captured_ddpm_source_figures_13_14_are_legitimate_separate_occurrences():
    client, extracted, payload = graphic_payload("2006.11239v2")
    _, markdown = graphic_article(client, extracted, payload)
    source = BeautifulSoup(payload.content.body, "lxml")
    images = list(iter_markdown_images(markdown))
    source_urls = []
    for node_id, number in (("S0.F1", 1), ("S4.F6", 6), ("A4.F13", 13), ("A4.F14", 14)):
        figure = source.find(id=node_id)
        assert figure is not None
        assert markdown.count(f"**Figure {number}.") == 1
        for image in figure.select("img[src]"):
            url = urljoin(payload.content.source_url, image["src"])
            source_urls.append(url)
            assert (
                sum(
                    item.url == url and item.alt == f"Figure {number}"
                    for item in images
                )
                == 1
            )
    assert_image_occurrences(markdown, source_urls)
    for node_id in ("A4.F13", "A4.F14"):
        assert source.select(f'a[href="#{node_id}"]')
    assert "Figure 11, 13, 16, 17, 18, and 19 show uncurated samples" in markdown
    assert "(Figs. 14 and 10)" in markdown
    assert "Unconditional CIFAR10 generated samples" in markdown
    assert "Unconditional CIFAR10 progressive generation" in markdown
    for suffix in (
        "cifar10_eps-fixedlarge-mse_20x20.png",
        "cifar10_eps-fixedlarge-mse_20_progressive.jpg",
    ):
        assert sum(image.url.endswith(suffix) for image in images) == 2
    assert "## Figures" not in markdown


def test_captured_ddpm_all_five_inline_vectors_publish_and_assemble(tmp_path):
    original = BeautifulSoup(graphic_source("2006.11239v2").read_bytes(), "lxml")
    signatures = {
        node_id: svg_content_signature(original.find(id=node_id))
        for node_id in GRAPHIC_IDS["2006.11239v2"]
    }
    client, extracted, payload = graphic_payload("2006.11239v2")
    inline = [
        asset
        for asset in extracted.extracted_assets
        if asset.get("source_kind") == "arxiv_inline_svg"
    ]
    # Download only the five acquired vectors; the remaining body assets must
    # stay in the denominator and prevent strict whole-paper acceptance.
    selected = replace(
        payload, content=replace(payload.content, extracted_assets=inline)
    )
    result = client.download_related_assets(
        "", {}, selected, tmp_path, asset_profile="body"
    )
    assert result["asset_failures"] == []
    assert len(result["assets"]) == 5
    article, markdown = graphic_article(client, extracted, payload, result["assets"])
    for asset in result["assets"]:
        path = Path(asset["path"])
        assert ET.fromstring(path.read_bytes()).attrib["id"] == asset["image_id"]
        assert_svg_content(signatures[asset["image_id"]], path.read_bytes())
        assert path.read_bytes() == base64.b64decode(
            asset["url"][len(INLINE_SVG_PREFIX) :]
        )
        assert markdown.count(f"]({path})") == 1
        assert asset["url"] not in markdown
    ArtifactStore.from_download_dir(tmp_path).audit_article_assets(
        article, asset_profile="body", archive_enabled=True
    )
    acceptance = graphic_acceptance(article, markdown, require_local=True)
    assert acceptance.asset.audited
    assert acceptance.asset.body_local == 5
    assert not acceptance.asset.local_body_assets_satisfied
    assert acceptance.asset.body_discovered > 5
    assert acceptance.asset.status == "degraded"
    assert (
        graphic_acceptance(article, markdown, require_local=False).asset.body_local == 5
    )
