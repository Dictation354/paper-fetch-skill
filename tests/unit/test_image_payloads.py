from __future__ import annotations

import unittest

from paper_fetch.extraction.image_payloads import image_mime_type_from_bytes


class ImagePayloadDetectionTests(unittest.TestCase):
    def test_image_mime_type_from_bytes_detects_binary_image_formats(self) -> None:
        samples = {
            "image/png": b"\x89PNG\r\n\x1a\npayload",
            "image/jpeg": b"\xff\xd8\xff\xe0" + b"\x00" * 16,
            "image/gif": b"GIF89a" + b"\x00" * 16,
            "image/webp": b"RIFF" + (16).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00" * 16,
            "image/bmp": b"BM" + b"\x00" * 16,
            "image/x-icon": b"\x00\x00\x01\x00" + b"\x00" * 16,
            "image/apng": (
                b"\x89PNG\r\n\x1a\n"
                + (13).to_bytes(4, "big")
                + b"IHDR"
                + b"\x00" * 17
                + (8).to_bytes(4, "big")
                + b"acTL"
                + b"\x00" * 12
            ),
            "image/heic": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00heicmif1",
        }

        for expected_mime, body in samples.items():
            with self.subTest(expected_mime=expected_mime):
                self.assertEqual(image_mime_type_from_bytes(body), expected_mime)

    def test_image_mime_type_from_bytes_detects_svg_documents(self) -> None:
        samples = [
            b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            b"\xef\xbb\xbf  \n<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            " \n\ufeff<?xml version='1.0' encoding='UTF-8'?><svg></svg>".encode("utf-8"),
        ]

        for body in samples:
            with self.subTest(body=body[:24]):
                self.assertEqual(image_mime_type_from_bytes(body), "image/svg+xml")

    def test_image_mime_type_from_bytes_rejects_html_with_embedded_svg(self) -> None:
        body = b"<html><body><svg></svg><p>Just a moment...</p></body></html>"

        self.assertEqual(image_mime_type_from_bytes(body), "")


if __name__ == "__main__":
    unittest.main()
