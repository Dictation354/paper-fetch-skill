"""PDF conversion output is opaque, including malformed bibliography/layout."""

import json
from unittest import mock

import pytest

from paper_fetch.models import article_from_markdown
from paper_fetch.providers import _pdf_common

RAW = "\n# A  title\n\n\n**Abstract**\nAn abstract.\n\n# Running header\n\nA hyphen-\nated line. [ 1 ]\n\n![](missing.png)\n\n## **REFERENCES**\n\n2M. A reference\ncontinued.\n\n1M. Another reference.\n  \n"


@pytest.mark.parametrize(
    "source",
    ["plos_pdf", "elsevier_pdf", "aip_pdf", "acs", "science", "pnas", "wiley_browser"],
)
def test_pdf_body_is_verbatim_across_assembly_serialization_and_render(source):
    article = article_from_markdown(
        source=source,
        pdf_representation=True,
        metadata={"title": "A title", "abstract": "An abstract."},
        doi=None,
        markdown_text=RAW,
    )
    assert len(article.sections) == 1
    assert article.sections[0].text == RAW
    assert json.loads(article.to_json())["sections"][0]["text"] == RAW
    assert article.references == []
    for mode in ("none", "top10", "all"):
        assert RAW in article.to_ai_markdown(include_refs=mode)


def test_include_refs_only_controls_independent_metadata_references():
    article = article_from_markdown(
        source="aip_pdf",
        metadata={
            "references": [
                {"raw": "Independent metadata reference", "doi": "10.1000/ref"}
            ]
        },
        doi=None,
        markdown_text=RAW,
    )
    for mode in ("none", "top10", "all"):
        rendered = article.to_ai_markdown(include_refs=mode)
        assert RAW in rendered
        assert ("Independent metadata reference" in rendered) == (mode != "none")
    assert article.references[0].doi == "10.1000/ref"
    assert RAW not in article.to_ai_markdown(max_tokens=40)


def test_converter_postprocessing_only_rewrites_existing_exported_asset_path(tmp_path):
    image_dir = tmp_path / "body_assets"
    image_dir.mkdir()
    image = image_dir / "original.png"
    image.write_bytes(b"image")
    raw = RAW + f'![  Original alt {image}  ]({image} "title")\n' + "raw word " * 300
    with mock.patch.object(
        _pdf_common, "_render_default_pdf_markdown", return_value=raw
    ):
        rendered = _pdf_common.render_pdf_markdown_result(
            tmp_path / "article.pdf", asset_profile="body", asset_output_dir=tmp_path
        )
    assert rendered.markdown_text == raw.replace(
        f"]({image}", "](body_assets/original.png"
    )
    assert len(rendered.assets) == 1


def test_budgeted_pdf_body_is_a_raw_prefix():
    raw = "\n\n##  Spacing\n" + "line-\nwrap  and   spacing\n\n" * 300
    article = article_from_markdown(
        source="aip_pdf", metadata={}, doi=None, markdown_text=raw
    )
    full = article.to_ai_markdown()
    limited = article.to_ai_markdown(max_tokens=180)
    # The surrounding header is unchanged and the payload prefix keeps linebreaks.
    header = full[: full.index(raw)]
    assert limited.startswith(header + raw[:100])
    assert raw.startswith(limited[len(header) :].rstrip("\n"))
