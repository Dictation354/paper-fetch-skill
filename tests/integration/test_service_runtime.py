from __future__ import annotations
from tests.support._service_support import *
# ruff: noqa: F403,F405


class ServiceRuntimeTests(unittest.TestCase):
    def test_artifact_store_preserves_provider_payload_and_springer_html_markers(
        self,
    ) -> None:
        pdf_content = ProviderContent(
            route_kind="pdf_fallback",
            source_url="https://example.test/article.pdf",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            needs_local_copy=True,
        )
        html_content = ProviderContent(
            route_kind="html",
            source_url="https://www.nature.com/articles/example",
            content_type="text/html; charset=utf-8",
            body=b"<html><body>Springer article</body></html>",
        )

        skipped_warnings, skipped_trail = ArtifactStore.from_download_dir(
            None
        ).save_provider_payload(
            "wiley",
            content=pdf_content,
            doi="10.1111/example",
            metadata={"title": "Example Article"},
        )
        self.assertEqual(
            skipped_warnings,
            [
                "Wiley official PDF/binary was not written to disk because artifact mode is none."
            ],
        )
        self.assertEqual(skipped_trail, ["download:wiley_skipped"])
        ieee_skipped_warnings, ieee_skipped_trail = ArtifactStore.from_download_dir(
            None
        ).save_provider_payload(
            "ieee",
            content=pdf_content,
            doi="10.1109/example",
            metadata={"title": "IEEE Example"},
        )
        self.assertEqual(
            ieee_skipped_warnings,
            [
                "IEEE official PDF/binary was not written to disk because artifact mode is none."
            ],
        )
        self.assertEqual(ieee_skipped_trail, ["download:ieee_skipped"])

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.from_download_dir(Path(tmpdir))
            saved_warnings, saved_trail = store.save_provider_payload(
                "wiley",
                content=pdf_content,
                doi="10.1111/example",
                metadata={"title": "Example Article"},
            )
            html_warnings, html_trail = store.save_provider_html_payload(
                "springer",
                content=html_content,
                doi="10.1007/example",
                metadata={"title": "Springer Example"},
            )
            wiley_html_warnings, wiley_html_trail = store.save_provider_html_payload(
                "wiley",
                content=html_content,
                doi="10.1111/example",
                metadata={"title": "Wiley Example"},
            )

            saved_paths = list(Path(tmpdir).glob("*"))

        self.assertEqual(saved_trail, ["download:wiley_saved"])
        self.assertTrue(
            any(
                "Wiley official full text was downloaded as PDF/binary to" in item
                for item in saved_warnings
            )
        )
        self.assertEqual(html_warnings, [])
        self.assertEqual(html_trail, ["download:springer_html_saved"])
        self.assertEqual(wiley_html_warnings, [])
        self.assertEqual(wiley_html_trail, [])
        self.assertTrue(any(path.name.endswith(".pdf") for path in saved_paths))
        self.assertTrue(
            any(path.name.endswith("_original.html") for path in saved_paths)
        )

    def test_artifact_store_markdown_assets_keeps_pdf_fallback_but_skips_raw_html(
        self,
    ) -> None:
        pdf_content = ProviderContent(
            route_kind="pdf_fallback",
            source_url="https://example.test/article.pdf",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            needs_local_copy=True,
        )
        html_content = ProviderContent(
            route_kind="html",
            source_url="https://www.nature.com/articles/example",
            content_type="text/html; charset=utf-8",
            body=b"<html><body>Springer article</body></html>",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.from_download_dir(
                Path(tmpdir), artifact_mode="markdown-assets"
            )
            saved_warnings, saved_trail = store.save_provider_payload(
                "wiley",
                content=pdf_content,
                doi="10.1111/example",
                metadata={"title": "Example Article"},
            )
            html_warnings, html_trail = store.save_provider_html_payload(
                "springer",
                content=html_content,
                doi="10.1007/example",
                metadata={"title": "Springer Example"},
            )
            saved_paths = list(Path(tmpdir).glob("*"))

        self.assertEqual(saved_trail, ["download:wiley_saved"])
        self.assertTrue(
            any(
                "Wiley official full text was downloaded as PDF/binary to" in item
                for item in saved_warnings
            )
        )
        self.assertEqual(html_warnings, [])
        self.assertEqual(html_trail, [])
        self.assertTrue(any(path.name.endswith(".pdf") for path in saved_paths))
        self.assertFalse(
            any(path.name.endswith("_original.html") for path in saved_paths)
        )
