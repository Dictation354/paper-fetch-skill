"""A representative real conversion, with opaque output across model/rendering."""

from unittest import mock
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
