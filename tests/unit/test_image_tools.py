from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from paper_fetch.image_tools import ImageConversionFailure
from paper_fetch.image_tools import convert as image_convert
from paper_fetch.image_tools import install as image_install
from paper_fetch.image_tools import source_image_format_from_payload
from paper_fetch.image_tools.paths import (
    DEFAULT_IMAGE_TOOL_TIMEOUT_SECONDS,
    image_tool_timeout_seconds,
)


class ImageToolsTests(unittest.TestCase):
    def test_source_image_format_detection_reads_payload_content_type_and_url(self) -> None:
        self.assertEqual(
            source_image_format_from_payload(b"%!PS-Adobe-3.0 EPSF-3.0\n"),
            "eps",
        )
        self.assertEqual(
            source_image_format_from_payload(
                b"",
                content_type="application/postscript; charset=binary",
            ),
            "eps",
        )
        self.assertEqual(
            source_image_format_from_payload(
                b"",
                source_url="https://example.test/figure-f1.eps?download=true",
            ),
            "eps",
        )
        self.assertEqual(source_image_format_from_payload(b"II*\x00payload"), "tiff")
        self.assertEqual(
            source_image_format_from_payload(
                b"",
                source_url="https://example.test/figure-f1.tif?download=true",
            ),
            "tiff",
        )
        self.assertEqual(
            source_image_format_from_payload(
                b"\x89PNG\r\n\x1a\n",
                content_type="image/png",
                source_url="https://example.test/figure.png",
            ),
            "",
        )

    def test_installer_stages_path_binary_in_default_mode(self) -> None:
        executable_name = "gs.exe" if os.name == "nt" else "gs"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "system-bin" / executable_name
            source.parent.mkdir(parents=True)
            source.write_bytes(b"")
            target = root / "image-tools"

            with (
                mock.patch.object(image_install.shutil, "which", return_value=str(source)),
                mock.patch.object(image_install, "_have_working_binary", return_value=True),
            ):
                self.assertTrue(image_install.ensure_ghostscript(target))

            self.assertTrue((target / "bin" / executable_name).exists())

    def test_installer_offline_bundle_skips_path_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "image-tools"
            repo_root = root / "repo"
            repo_root.mkdir()

            with mock.patch.object(image_install, "_stage_from_path") as stage_from_path:
                self.assertFalse(
                    image_install.ensure_ghostscript(
                        target,
                        offline_bundle=True,
                        repo_root_path=repo_root,
                    )
                )

            stage_from_path.assert_not_called()
            self.assertFalse((target / "bin" / "gs").exists())

    def test_installer_offline_bundle_copies_repo_runtime(self) -> None:
        executable_name = "gs.exe" if os.name == "nt" else "gs"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            runtime_bin = repo_root / ".venv" / "ghostscript-runtime" / "bin"
            runtime_bin.mkdir(parents=True)
            (runtime_bin / executable_name).write_bytes(b"")
            target = root / "image-tools"

            self.assertTrue(
                image_install.ensure_ghostscript(
                    target,
                    offline_bundle=True,
                    repo_root_path=repo_root,
                )
            )

            self.assertTrue(
                (target / "ghostscript-runtime" / "bin" / executable_name).exists()
            )

    def test_image_tool_timeout_env_uses_positive_int_or_default(self) -> None:
        self.assertEqual(
            image_tool_timeout_seconds({"PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS": "7"}),
            7,
        )
        for value in ("", "0", "-1", "not-an-int"):
            self.assertEqual(
                image_tool_timeout_seconds(
                    {"PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS": value}
                ),
                DEFAULT_IMAGE_TOOL_TIMEOUT_SECONDS,
            )

    def test_conversion_subprocess_timeout_raises_conversion_failure(self) -> None:
        with mock.patch.object(
            image_convert.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="gs", timeout=3),
        ):
            with self.assertRaisesRegex(
                ImageConversionFailure,
                "timed out",
            ):
                image_convert._run(["gs"], env={})
