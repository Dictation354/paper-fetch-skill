from __future__ import annotations

import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch import config
from paper_fetch.providers import browser_runtime


class ConfigTests(unittest.TestCase):
    def test_default_user_agent_matches_project_version(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))["project"]

        self.assertEqual(
            config.DEFAULT_USER_AGENT, f"paper-fetch-skill/{project['version']}"
        )

    def test_load_env_file_uses_dotenv_syntax_without_interpolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "# comment",
                        'export EXPORTED="two words"',
                        "SINGLE='literal # value'",
                        "COMMENTED=ok # inline comment",
                        "EMPTY=",
                        "NO_INTERPOLATION=${EXPORTED}",
                        "BARE_KEY",
                    ]
                ),
                encoding="utf-8",
            )

            values = config.load_env_file(env_file)

        self.assertEqual(values["EXPORTED"], "two words")
        self.assertEqual(values["SINGLE"], "literal # value")
        self.assertEqual(values["COMMENTED"], "ok")
        self.assertEqual(values["EMPTY"], "")
        self.assertEqual(values["NO_INTERPOLATION"], "${EXPORTED}")
        self.assertNotIn("BARE_KEY", values)

    def test_build_runtime_env_prefers_process_env_then_explicit_file_then_user_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            explicit_env = tmp / "explicit.env"

            user_env.write_text("SHARED=user\nUSER_ONLY=user\n", encoding="utf-8")
            explicit_env.write_text(
                "SHARED=explicit\nEXPLICIT_ONLY=explicit\n", encoding="utf-8"
            )

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

    def test_build_runtime_env_explicit_arg_overrides_env_var_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            configured_env = tmp / "configured.env"
            explicit_env = tmp / "explicit.env"
            user_env.write_text("SHARED=user\n", encoding="utf-8")
            configured_env.write_text(
                "SHARED=configured\nCONFIGURED_ONLY=1\n", encoding="utf-8"
            )
            explicit_env.write_text(
                "SHARED=explicit\nEXPLICIT_ONLY=1\n", encoding="utf-8"
            )

            with mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env):
                env = config.build_runtime_env(
                    {config.ENV_FILE_ENV_VAR: str(configured_env)},
                    env_file=explicit_env,
                )

        self.assertEqual(env["SHARED"], "explicit")
        self.assertEqual(env["CONFIGURED_ONLY"], "1")
        self.assertEqual(env["EXPLICIT_ONLY"], "1")

    def test_runtime_configuration_report_preserves_precedence_without_values(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            configured_env = tmp / "configured.env"
            explicit_env = tmp / "explicit.env"
            user_env.write_text(
                "SHARED=user\nUSER_ONLY=user-secret\n", encoding="utf-8"
            )
            configured_env.write_text(
                "SHARED=configured\nCONFIGURED_ONLY=configured-secret\n",
                encoding="utf-8",
            )
            explicit_env.write_text(
                "SHARED=explicit\nEXPLICIT_ONLY=explicit-secret\n",
                encoding="utf-8",
            )

            with mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env):
                report = config.runtime_configuration_report(
                    {
                        "SHARED",
                        "USER_ONLY",
                        "CONFIGURED_ONLY",
                        "EXPLICIT_ONLY",
                        "DEFAULT_ONLY",
                        "UNSET_ONLY",
                    },
                    base_env={
                        "SHARED": "process-secret",
                        config.ENV_FILE_ENV_VAR: str(configured_env),
                    },
                    env_file=explicit_env,
                    default_names={"DEFAULT_ONLY"},
                    sensitive_names={"SHARED"},
                )

        entries = {entry["name"]: entry for entry in report["values"]}
        self.assertEqual(entries["SHARED"]["source"], "process_env")
        self.assertEqual(entries["EXPLICIT_ONLY"]["source"], "explicit_env_file")
        self.assertEqual(entries["CONFIGURED_ONLY"]["source"], "env_var_file")
        self.assertEqual(entries["USER_ONLY"]["source"], "user_config")
        self.assertEqual(entries["DEFAULT_ONLY"]["source"], "default")
        self.assertEqual(entries["UNSET_ONLY"]["source"], "unset")
        self.assertTrue(entries["SHARED"]["sensitive"])
        serialized = str(report)
        for secret in (
            "process-secret",
            "explicit-secret",
            "configured-secret",
            "user-secret",
        ):
            self.assertNotIn(secret, serialized)

    def test_user_env_file_is_the_default_runtime_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            user_env.write_text("SHARED=user\n", encoding="utf-8")

            with mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env):
                env = config.build_runtime_env({})

        self.assertEqual(env["SHARED"], "user")

    def test_build_runtime_env_treats_explicit_empty_env_as_isolated_from_process_env(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            user_env = tmp / "user.env"
            process_env_file = tmp / "process.env"
            user_env.write_text("USER_ONLY=user\n", encoding="utf-8")
            process_env_file.write_text("PROCESS_FILE_ONLY=process\n", encoding="utf-8")

            with (
                mock.patch.object(config, "DEFAULT_USER_ENV_FILE", user_env),
                mock.patch.dict(
                    os.environ,
                    {
                        "PROCESS_ONLY": "process",
                        config.ENV_FILE_ENV_VAR: str(process_env_file),
                    },
                    clear=False,
                ),
            ):
                env = config.build_runtime_env({})

        self.assertEqual(env["USER_ONLY"], "user")
        self.assertNotIn("PROCESS_ONLY", env)
        self.assertNotIn("PROCESS_FILE_ONLY", env)

    def test_build_publisher_user_agent_ignores_shared_tool_user_agent(self) -> None:
        user_agent = config.build_publisher_user_agent(
            {config.USER_AGENT_ENV_VAR: "paper-fetch-skill/999"}
        )

        self.assertIn("Mozilla/5.0", user_agent)
        self.assertNotIn("paper-fetch", user_agent)

    def test_build_publisher_user_agent_uses_explicit_browser_user_agent(self) -> None:
        user_agent = config.build_publisher_user_agent(
            {
                config.BROWSER_USER_AGENT_ENV_VAR: "Mozilla/5.0 test-browser",
                config.USER_AGENT_ENV_VAR: "paper-fetch-skill/999",
            }
        )

        self.assertEqual(user_agent, "Mozilla/5.0 test-browser")

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
                mock.patch.object(
                    config, "load_env_file", side_effect=fake_load_env_file
                ),
            ):
                config.build_runtime_env({})

        self.assertEqual(seen_paths, [user_env])

    def test_cli_default_download_dir_uses_xdg_user_data_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                config.BROWSER_BACKEND_ENV_VAR: "camoufox",
                config.XDG_DATA_HOME_ENV_VAR: tmpdir,
            }
            expected = Path(tmpdir) / "paper-fetch" / "downloads"

            resolved = config.resolve_cli_download_dir(env)
            self.assertTrue(expected.exists())

        self.assertEqual(resolved, expected)

    def test_user_data_dir_uses_platform_default_unless_xdg_overrides_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            platform_default = tmp / "platform-data"
            xdg_home = tmp / "xdg-data"

            with mock.patch.object(config, "DEFAULT_USER_DATA_DIR", platform_default):
                self.assertEqual(config.resolve_user_data_dir({}), platform_default)
                self.assertEqual(
                    config.resolve_user_data_dir(
                        {config.XDG_DATA_HOME_ENV_VAR: str(xdg_home)}
                    ),
                    xdg_home / "paper-fetch",
                )

    def test_cli_download_dir_falls_back_to_cwd_when_default_user_data_dir_cannot_be_created(
        self,
    ) -> None:
        preferred_root = Path("/tmp/paper-fetch-test-user-data")
        preferred_dir = preferred_root / "downloads"
        original_mkdir = Path.mkdir

        def fake_mkdir(path: Path, *args, **kwargs):
            if path == preferred_dir:
                raise OSError("permission denied")
            return original_mkdir(path, *args, **kwargs)

        with (
            mock.patch.object(
                config, "resolve_user_data_dir", return_value=preferred_root
            ),
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

    def test_camoufox_runtime_config_defaults_to_user_data_artifacts_without_browser_user_agent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_config = browser_runtime.load_runtime_config(
                {
                    config.BROWSER_BACKEND_ENV_VAR: "camoufox",
                    config.XDG_DATA_HOME_ENV_VAR: tmpdir,
                },
                provider="science",
                doi="10.1126/science.ady3136",
            )

        self.assertEqual(runtime_config.provider, "science")
        self.assertEqual(runtime_config.doi, "10.1126/science.ady3136")
        self.assertTrue(runtime_config.headless)
        self.assertIsNone(runtime_config.user_agent)
        self.assertIn("publisher-browser-artifacts", runtime_config.artifact_dir.parts)

    def test_camoufox_runtime_config_defaults_to_provider_user_data_dir(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                config.BROWSER_BACKEND_ENV_VAR: "camoufox",
                config.XDG_DATA_HOME_ENV_VAR: tmpdir,
            }
            science_runtime = browser_runtime.load_runtime_config(
                env,
                provider="science",
                doi="10.1126/science.ady3136",
            )
            pnas_runtime = browser_runtime.load_runtime_config(
                env,
                provider="pnas",
                doi="10.1073/pnas.2406303121",
            )

        expected_root = (
            Path(tmpdir).expanduser() / "paper-fetch" / "publisher-browser-profiles"
        )
        self.assertEqual(
            science_runtime.user_data_dir, expected_root / "science-camoufox"
        )
        self.assertEqual(pnas_runtime.user_data_dir, expected_root / "pnas-camoufox")
        self.assertNotEqual(science_runtime.user_data_dir, pnas_runtime.user_data_dir)

    def test_camoufox_runtime_config_does_not_use_shared_tool_user_agent_for_browser(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_config = browser_runtime.load_runtime_config(
                {
                    config.BROWSER_BACKEND_ENV_VAR: "camoufox",
                    config.USER_AGENT_ENV_VAR: "paper-fetch-test/1",
                    config.XDG_DATA_HOME_ENV_VAR: tmpdir,
                },
                provider="science",
                doi="10.1126/science.ady3136",
            )

        self.assertIsNone(runtime_config.user_agent)

    def test_camoufox_runtime_config_ignores_browser_user_agent_override(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_config = browser_runtime.load_runtime_config(
                {
                    config.BROWSER_BACKEND_ENV_VAR: "camoufox",
                    config.USER_AGENT_ENV_VAR: "paper-fetch-test/1",
                    config.BROWSER_USER_AGENT_ENV_VAR: "Mozilla/5.0",
                    config.XDG_DATA_HOME_ENV_VAR: tmpdir,
                },
                provider="science",
                doi="10.1126/science.ady3136",
            )

        self.assertIsNone(runtime_config.user_agent)

    def test_camoufox_runtime_config_expands_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            browser_binary = Path(tmpdir) / "chrome"
            browser_binary.write_text("#!/bin/sh\n", encoding="utf-8")
            browser_binary.chmod(0o755)
            runtime_config = browser_runtime.load_runtime_config(
                {
                    config.BROWSER_BACKEND_ENV_VAR: "camoufox",
                    config.BROWSER_BINARY_PATH_ENV_VAR: str(browser_binary),
                    config.BROWSER_HEADLESS_ENV_VAR: "false",
                    config.BROWSER_TIMEOUT_MS_ENV_VAR: "12345",
                    config.XDG_DATA_HOME_ENV_VAR: tmpdir,
                },
                provider="science",
                doi="10.1126/science.ady3136",
            )

        self.assertFalse(runtime_config.headless)
        self.assertEqual(runtime_config.timeout_ms, 12345)
        self.assertEqual(runtime_config.binary_path, str(browser_binary))
        self.assertTrue(
            str(runtime_config.artifact_dir).startswith(str(Path(tmpdir).expanduser()))
        )

    def test_camoufox_runtime_config_rejects_invalid_binary_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_binary_path = str(Path(tmpdir) / "missing-chrome")
            with self.assertRaisesRegex(Exception, config.BROWSER_BINARY_PATH_ENV_VAR):
                browser_runtime.load_runtime_config(
                    {
                        config.BROWSER_BACKEND_ENV_VAR: "camoufox",
                        config.BROWSER_BINARY_PATH_ENV_VAR: missing_binary_path,
                        config.XDG_DATA_HOME_ENV_VAR: tmpdir,
                    },
                    provider="science",
                    doi="10.1126/science.ady3136",
                )

    def test_removed_cloakbrowser_backend_is_rejected(self) -> None:
        with self.assertRaisesRegex(Exception, "expected one of: camoufox"):
            browser_runtime.load_runtime_config(
                {config.BROWSER_BACKEND_ENV_VAR: "cloakbrowser"},
                provider="science",
                doi="10.1126/science.ady3136",
            )


if __name__ == "__main__":
    unittest.main()
