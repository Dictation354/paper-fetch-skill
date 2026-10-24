"""A representative real conversion, with opaque output across model/rendering."""

from pathlib import Path
from unittest import mock

import pymupdf
import pytest
from paper_fetch.models import article_from_markdown
from paper_fetch.providers import _pdf_common
from tests.support._paper_fetch_support import fulltext_pdf_bytes


def test_converter_result_is_passed_through_to_model_and_render(tmp_path):
    original = _pdf_common._render_default_pdf_markdown
    with mock.patch.object(
        _pdf_common, "_render_default_pdf_markdown", wraps=original
    ) as converter:
        result = _pdf_common.pdf_fetch_result_from_bytes(
            artifact_dir=tmp_path,
            source_url="https://example.org/article.pdf",
            final_url="https://example.org/article.pdf",
            pdf_bytes=fulltext_pdf_bytes(),
        )
    converter.assert_called_once()
    article = article_from_markdown(
        source="plos_pdf",
        metadata={"title": "Conversion contract"},
        doi=None,
        markdown_text=result.markdown_text,
    )
    assert article.sections[0].text == result.markdown_text
    assert result.markdown_text in article.to_ai_markdown(max_tokens="full_text")
    assert article.to_dict()["sections"][0]["text"] == result.markdown_text
    assert article.references == []


def test_transparent_text_uses_helpers_output_verbatim(tmp_path):
    from pymupdf4llm.helpers import pymupdf_rag

    path = tmp_path / "transparent.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        for line in range(45):
            page.insert_text(
                (30, 30 + line * 15),
                "Transparent satellite observations across multiple seasons.",
                fontsize=9,
                fill_opacity=0,
            )
        document.save(path)
    expected = pymupdf_rag.to_markdown(str(path), ignore_alpha=True, hdr_info=False)
    with mock.patch.object(
        pymupdf_rag, "to_markdown", wraps=pymupdf_rag.to_markdown
    ) as converter:
        actual = _pdf_common._render_transparent_pdf_markdown(path)
    converter.assert_called_once_with(str(path), ignore_alpha=True, hdr_info=False)
    assert actual == expected
    assert "Transparent satellite observations" in actual
    assert _pdf_common._pdf_text_layer_stats(path).transparent_words > 0


@pytest.fixture
def pdf_with_body_image():
    with pymupdf.open(stream=fulltext_pdf_bytes(), filetype="pdf") as document:
        samples = bytes(
            value
            for y in range(160)
            for x in range(160)
            for value in (x, y, (x + y) % 256)
        )
        image = pymupdf.Pixmap(pymupdf.csRGB, 160, 160, samples, False)
        page = document.new_page()
        page.insert_text((72, 72), "Figure 1. Satellite observations")
        page.insert_image(pymupdf.Rect(72, 120, 450, 498), pixmap=image)
        return document.tobytes()


@pytest.mark.parametrize("persist", [True, False], ids=["body-assets", "no-artifacts"])
def test_pdf_body_image_respects_artifact_mode(tmp_path, pdf_with_body_image, persist):
    source_url = "https://example.org/image-contract.pdf"
    assets_dir = tmp_path / "paper_assets" if persist else None
    original = _pdf_common._render_default_pdf_markdown
    rendered = []

    def capture(*args, **kwargs):
        text = original(*args, **kwargs)
        rendered.append(text)
        return text

    with mock.patch.object(_pdf_common, "_render_default_pdf_markdown", capture):
        result = _pdf_common.pdf_fetch_result_from_bytes(
            artifact_dir=tmp_path / "raw" if persist else None,
            asset_profile="body",
            asset_output_dir=assets_dir,
            source_url=source_url,
            final_url=source_url,
            pdf_bytes=pdf_with_body_image,
        )
    assert len(rendered) == 1
    if persist:
        assert result.assets
        assert list((tmp_path / "raw").glob("*.pdf"))
        expected = rendered[0]
        for asset in result.assets:
            path = Path(asset["path"])
            assert path.parent == assets_dir
            assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
            assert asset["source_url"] == source_url
            assert asset["section"] == "body"
            assert asset["url"] in result.markdown_text
            expected = expected.replace(str(path), asset["url"])
        assert result.markdown_text == expected
    else:
        assert result.markdown_text == rendered[0]
        assert result.assets == []
        assert list(tmp_path.iterdir()) == []
