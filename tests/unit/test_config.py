from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch import config


class ConfigTests(unittest.TestCase):
    def test_build_runtime_env_prefers_process_env_then_explicit_file_then_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            explicit_env = tmp / "explicit.env"

            user_env.write_text("SHARED=user\nUSER_ONLY=user\n", encoding="utf-8")
            explicit_env.write_text("SHARED=explicit\nEXPLICIT_ONLY=explicit\n", encoding="utf-8")

            with mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env):
                env = config.build_runtime_env(
                    {
                        "SHARED": "process",
                        "PROCESS_ONLY": "process",
                        config.ENV_FILE_ENV_VAR: str(explicit_env),
                    }
                )

        self.assertEqual(env["SHARED"], "process")
        self.assertEqual(env["PROCESS_ONLY"], "process")
        self.assertEqual(env["EXPLICIT_ONLY"], "explicit")
        self.assertEqual(env["USER_ONLY"], "user")

    def test_user_env_file_is_the_default_runtime_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            user_env.write_text("SHARED=user\n", encoding="utf-8")

            with mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env):
                env = config.build_runtime_env({})

        self.assertEqual(env["SHARED"], "user")

    def test_repo_local_env_is_not_loaded_implicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            user_env.write_text("SHARED=user\n", encoding="utf-8")
            seen_paths: list[Path] = []

            def fake_load_env_file(path: Path) -> dict[str, str]:
                seen_paths.append(path)
                return {}

            with (
                mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env),
                mock.patch.object(config, "load_env_file", side_effect=fake_load_env_file),
            ):
                config.build_runtime_env({})

        self.assertEqual(seen_paths, [user_env])

    def test_cli_default_download_dir_uses_xdg_user_data_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {config.XDG_DATA_HOME_ENV_VAR: tmpdir}
            expected = Path(tmpdir) / "paper-fetch" / "downloads"

            resolved = config.resolve_cli_download_dir(env)
            self.assertTrue(expected.exists())

        self.assertEqual(resolved, expected)

    def test_cli_download_dir_falls_back_to_cwd_when_default_user_data_dir_cannot_be_created(self) -> None:
        preferred_root = Path("/tmp/paper-fetch-test-user-data")
        preferred_dir = preferred_root / "downloads"
        original_mkdir = Path.mkdir

        def fake_mkdir(path: Path, *args, **kwargs):
            if path == preferred_dir:
                raise OSError("permission denied")
            return original_mkdir(path, *args, **kwargs)

        with (
            mock.patch.object(config, "resolve_user_data_dir", return_value=preferred_root),
            mock.patch.object(Path, "mkdir", fake_mkdir),
        ):
            resolved = config.resolve_cli_download_dir({})

        self.assertEqual(resolved, Path("live-downloads"))

    def test_cli_and_mcp_download_dirs_use_distinct_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {config.XDG_DATA_HOME_ENV_VAR: tmpdir}
            expected = Path(tmpdir) / "paper-fetch" / "downloads"

            self.assertEqual(config.resolve_cli_download_dir(env), expected)
            self.assertEqual(config.resolve_mcp_download_dir(env), expected)

    def test_download_dir_env_var_overrides_both_adapter_defaults(self) -> None:
        env = {config.DOWNLOAD_DIR_ENV_VAR: "~/paper-fetch-downloads"}
        expected = Path("~/paper-fetch-downloads").expanduser()

        self.assertEqual(config.resolve_cli_download_dir(env), expected)
        self.assertEqual(config.resolve_mcp_download_dir(env), expected)

    def test_flaresolverr_paths_default_to_repo_local_vendor_and_url(self) -> None:
        self.assertEqual(config.resolve_flaresolverr_source_dir({}), config.DEFAULT_VENDOR_FLARESOLVERR_DIR)
        self.assertEqual(config.resolve_flaresolverr_env_file({}), None)
        self.assertEqual(config.resolve_flaresolverr_url({}), config.DEFAULT_FLARESOLVERR_URL)

    def test_flaresolverr_paths_expand_explicit_configuration(self) -> None:
        env = {
            config.FLARESOLVERR_SOURCE_DIR_ENV_VAR: "~/custom-flaresolverr",
            config.FLARESOLVERR_ENV_FILE_ENV_VAR: "~/custom-flaresolverr/.env.test",
            config.FLARESOLVERR_URL_ENV_VAR: "http://127.0.0.1:9000/v1",
        }

        self.assertEqual(config.resolve_flaresolverr_source_dir(env), Path("~/custom-flaresolverr").expanduser())
        self.assertEqual(config.resolve_flaresolverr_env_file(env), Path("~/custom-flaresolverr/.env.test").expanduser())
        self.assertEqual(config.resolve_flaresolverr_url(env), "http://127.0.0.1:9000/v1")


if __name__ == "__main__":
    unittest.main()
