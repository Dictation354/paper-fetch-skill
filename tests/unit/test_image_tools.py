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
from paper_fetch.reason_codes import (
    IMAGE_CONVERSION_BACKEND_MISSING,
    IMAGE_CONVERSION_BACKEND_READY,
    IMAGE_CONVERSION_BACKEND_TIMEOUT,
)


class ImageToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        image_convert._clear_image_tool_caches()

    def tearDown(self) -> None:
        image_convert._clear_image_tool_caches()

    def test_source_image_format_detection_reads_payload_content_type_and_url(
        self,
    ) -> None:
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
                mock.patch.object(
                    image_install.shutil, "which", return_value=str(source)
                ),
                mock.patch.object(
                    image_install, "_have_working_binary", return_value=True
                ),
            ):
                self.assertTrue(image_install.ensure_ghostscript(target))

            self.assertTrue((target / "bin" / executable_name).exists())

    def test_installer_offline_bundle_skips_path_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "image-tools"
            repo_root = root / "repo"
            repo_root.mkdir()

            with mock.patch.object(
                image_install, "_stage_from_path"
            ) as stage_from_path:
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

    def test_backend_probe_distinguishes_ready_missing_and_timeout(self) -> None:
        backend_cases = ("ghostscript", "libvips")
        outcomes = (
            ("ready", "ready", IMAGE_CONVERSION_BACKEND_READY),
            ("missing", "not_configured", IMAGE_CONVERSION_BACKEND_MISSING),
            ("timeout", "error", IMAGE_CONVERSION_BACKEND_TIMEOUT),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "image-tool"
            binary.write_bytes(b"")
            for backend in backend_cases:
                for outcome, expected_status, expected_code in outcomes:
                    with self.subTest(backend=backend, outcome=outcome):
                        image_convert._clear_image_tool_caches()
                        candidates = [] if outcome == "missing" else [binary]
                        run_side_effect = (
                            subprocess.TimeoutExpired(cmd=str(binary), timeout=1)
                            if outcome == "timeout"
                            else None
                        )
                        completed = subprocess.CompletedProcess(
                            [str(binary), "--version"], 0
                        )
                        with (
                            mock.patch.object(
                                image_convert,
                                "ghostscript_binary_candidates",
                                return_value=(
                                    candidates if backend == "ghostscript" else []
                                ),
                            ),
                            mock.patch.object(
                                image_convert,
                                "vips_binary_candidates",
                                return_value=(
                                    candidates if backend == "libvips" else []
                                ),
                            ),
                            mock.patch.object(
                                image_convert.subprocess,
                                "run",
                                side_effect=run_side_effect,
                                return_value=completed,
                            ),
                        ):
                            report = image_convert.probe_image_conversion_backends(
                                {
                                    "PATH": "",
                                    "PAPER_FETCH_IMAGE_TOOL_TIMEOUT_SECONDS": "1",
                                }
                            )

                        entry = report[backend]
                        self.assertEqual(entry["status"], expected_status)
                        self.assertEqual(entry["reason_code"], expected_code)
                        self.assertEqual(entry["available"], outcome == "ready")

    def test_convert_eps_reuses_cached_ghostscript_probe_for_multiple_images(
        self,
    ) -> None:
        version_calls: list[list[str]] = []
        conversion_calls: list[list[str]] = []

        def fake_run(args, **_kwargs):
            command = [str(item) for item in args]
            if "--version" in command:
                version_calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")
            output_arg = next(
                item for item in command if item.startswith("-sOutputFile=")
            )
            Path(output_arg.split("=", 1)[1]).write_bytes(b"\x89PNG\r\n\x1a\none")
            conversion_calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / ("gs.exe" if os.name == "nt" else "gs")
            binary.write_bytes(b"")
            response = {
                "body": b"%!PS-Adobe-3.0 EPSF-3.0\n",
                "headers": {"content-type": "application/postscript"},
            }
            with (
                mock.patch.dict(
                    os.environ, {"PAPER_FETCH_GHOSTSCRIPT_BIN": str(binary)}
                ),
                mock.patch.object(
                    image_convert.subprocess, "run", side_effect=fake_run
                ),
            ):
                first = image_convert.convert_source_image_response_to_png(
                    response,
                    source_url="https://example.test/one.eps",
                )
                second = image_convert.convert_source_image_response_to_png(
                    response,
                    source_url="https://example.test/two.eps",
                )

        self.assertEqual(first.tool, "ghostscript")
        self.assertEqual(second.tool, "ghostscript")
        self.assertEqual(len(version_calls), 1)
        self.assertEqual(len(conversion_calls), 2)

    def test_convert_tiff_reuses_cached_vips_probe_for_multiple_images(self) -> None:
        version_calls: list[list[str]] = []
        conversion_calls: list[list[str]] = []

        def fake_run(args, **_kwargs):
            command = [str(item) for item in args]
            if "--version" in command:
                version_calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")
            Path(command[-1]).write_bytes(b"\x89PNG\r\n\x1a\ntiff")
            conversion_calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / ("vips.exe" if os.name == "nt" else "vips")
            binary.write_bytes(b"")
            response = {
                "body": b"II*\x00payload",
                "headers": {"content-type": "image/tiff"},
            }
            with (
                mock.patch.dict(os.environ, {"PAPER_FETCH_VIPS_BIN": str(binary)}),
                mock.patch.object(
                    image_convert.subprocess, "run", side_effect=fake_run
                ),
            ):
                first = image_convert.convert_source_image_response_to_png(
                    response,
                    source_url="https://example.test/one.tif",
                )
                second = image_convert.convert_source_image_response_to_png(
                    response,
                    source_url="https://example.test/two.tif",
                )

        self.assertEqual(first.tool, "libvips")
        self.assertEqual(second.tool, "libvips")
        self.assertEqual(len(version_calls), 1)
        self.assertEqual(len(conversion_calls), 2)

    def test_probe_cache_key_changes_when_explicit_binary_env_changes(self) -> None:
        version_calls: list[str] = []

        def fake_run(args, **_kwargs):
            command = [str(item) for item in args]
            version_calls.append(command[0])
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as tmpdir:
            first = Path(tmpdir) / "first-gs"
            second = Path(tmpdir) / "second-gs"
            first.write_bytes(b"")
            second.write_bytes(b"")
            with mock.patch.object(
                image_convert.subprocess, "run", side_effect=fake_run
            ):
                with mock.patch.dict(
                    os.environ, {"PAPER_FETCH_GHOSTSCRIPT_BIN": str(first)}
                ):
                    self.assertEqual(image_convert._ghostscript_binary(), first)
                with mock.patch.dict(
                    os.environ, {"PAPER_FETCH_GHOSTSCRIPT_BIN": str(second)}
                ):
                    self.assertEqual(image_convert._ghostscript_binary(), second)

        self.assertEqual(version_calls, [str(first), str(second)])
