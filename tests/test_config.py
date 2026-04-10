from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch import config


class ConfigTests(unittest.TestCase):
    def test_build_runtime_env_prefers_process_env_then_explicit_file_then_user_then_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo_env = tmp / "repo.env"
            user_env = tmp / "user.env"
            explicit_env = tmp / "explicit.env"

            repo_env.write_text("SHARED=repo\nREPO_ONLY=repo\n", encoding="utf-8")
            user_env.write_text("SHARED=user\nUSER_ONLY=user\n", encoding="utf-8")
            explicit_env.write_text("SHARED=explicit\nEXPLICIT_ONLY=explicit\n", encoding="utf-8")

            with (
                mock.patch.object(config, "DEFAULT_ENV_FILE", repo_env),
                mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env),
            ):
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
        self.assertEqual(env["REPO_ONLY"], "repo")

    def test_user_env_file_overrides_repo_fallback_when_no_explicit_env_file_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo_env = tmp / "repo.env"
            user_env = tmp / "user.env"
            repo_env.write_text("SHARED=repo\n", encoding="utf-8")
            user_env.write_text("SHARED=user\n", encoding="utf-8")

            with (
                mock.patch.object(config, "DEFAULT_ENV_FILE", repo_env),
                mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env),
            ):
                env = config.build_runtime_env({})

        self.assertEqual(env["SHARED"], "user")

    def test_cli_and_mcp_download_dirs_use_distinct_defaults(self) -> None:
        self.assertEqual(config.resolve_cli_download_dir({}), Path("live-downloads"))
        self.assertEqual(config.resolve_mcp_download_dir({}), config.DEFAULT_MCP_DOWNLOAD_DIR)

    def test_download_dir_env_var_overrides_both_adapter_defaults(self) -> None:
        env = {config.DOWNLOAD_DIR_ENV_VAR: "~/paper-fetch-downloads"}
        expected = Path("~/paper-fetch-downloads").expanduser()

        self.assertEqual(config.resolve_cli_download_dir(env), expected)
        self.assertEqual(config.resolve_mcp_download_dir(env), expected)


if __name__ == "__main__":
    unittest.main()
