from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from paper_fetch import cli as paper_fetch_cli
from paper_fetch.config import DOWNLOAD_DIR_ENV_VAR
from paper_fetch import service as paper_fetch
from paper_fetch.models import Asset, RenderOptions
from paper_fetch.providers.base import ProviderFailure

from ._paper_fetch_support import build_envelope, sample_article


class CliTests(unittest.TestCase):
    def test_main_version_reports_package_version(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        original_argv = sys.argv
        sys.argv = ["paper_fetch.py", "--version"]
        try:
            with (
                mock.patch.object(
                    paper_fetch_cli, "package_version", return_value="9.8.7"
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit) as raised,
            ):
                paper_fetch_cli.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), "paper-fetch 9.8.7")
        self.assertEqual(stderr.getvalue(), "")

    def test_help_documents_rendering_and_asset_options(self) -> None:
        help_text = paper_fetch_cli.build_parser().format_help()
        normalized_help = " ".join(help_text.split())

        self.assertIn("{fetch,auth,browser-preflight,manifest,doctor}", help_text)
        self.assertIn("Fetch one paper or a query-file batch.", help_text)
        self.assertIn("Open a headed browser", help_text)
        self.assertIn("Live-check browser-backed providers", help_text)
        self.assertIn(
            "root-level fetch flags remain available for one release cycle",
            normalized_help,
        )
        self.assertIn("Doctor performs static, network-free checks", normalized_help)
        self.assertIn("--include-refs {none,top10,all}", help_text)
        self.assertIn("Reference rendering mode", help_text)
        self.assertIn("--asset-profile {none,body,all}", help_text)
        self.assertIn("Local content asset scope", help_text)
        self.assertIn("--max-tokens MAX_TOKENS", help_text)
        self.assertIn("Markdown rendering budget", help_text)

    def test_top_level_and_subcommand_help_contract_snapshot(self) -> None:
        expected_fragments = {
            (): (
                "usage: paper-fetch",
                "commands:",
                "{fetch,auth,browser-preflight,manifest,doctor}",
                "Doctor performs static, network-free checks.",
            ),
            ("fetch",): (
                "usage: paper-fetch fetch",
                "--format {markdown,json,both}",
                "default: markdown",
                "--artifact-mode {markdown-assets,all,none}",
                "default: markdown-assets",
                "--asset-profile {none,body,all}",
                "default: body",
                "CLI artifact alias for --artifact-mode none",
                "does not block explicit --output",
            ),
            ("auth",): (
                "usage: paper-fetch auth",
                "Browser-backed provider to open for manual authentication.",
                "default: the provider's built-in sample article",
                "--timeout-ms TIMEOUT_MS",
            ),
            ("browser-preflight",): (
                "usage: paper-fetch browser-preflight",
                "--provider {wiley,science,pnas,mdpi",
                "default: all browser-backed providers",
                "save provider storage-state JSON on success",
            ),
            ("manifest",): (
                "usage: paper-fetch manifest",
                "{audit,reconcile}",
                "without writing files or using network",
            ),
            ("doctor",): (
                "usage: paper-fetch doctor",
                "--provider {crossref,elsevier",
                "--group {all,official,browser,direct,metadata}",
                "--detail {full,compact}",
                "without network access",
            ),
        }

        for command, fragments in expected_fragments.items():
            with self.subTest(command=command):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with (
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                    self.assertRaises(SystemExit) as raised,
                ):
                    paper_fetch_cli.main([*command, "--help"])

                self.assertEqual(raised.exception.code, 0)
                self.assertEqual(stderr.getvalue(), "")
                rendered = " ".join(stdout.getvalue().split()).replace("- ", "-")
                for fragment in fragments:
                    self.assertIn(fragment, rendered)

    def test_manifest_and_doctor_default_commands_remain_replaceable(self) -> None:
        registered: list[str] = []

        def register_manifest(subparsers) -> None:
            subparsers.add_parser("manifest", help="Injected manifest command.")
            registered.append("manifest")

        def register_doctor(subparsers) -> None:
            subparsers.add_parser("doctor", help="Injected doctor command.")
            registered.append("doctor")

        default_help = paper_fetch_cli.build_parser().format_help()
        injected_help = paper_fetch_cli.build_parser(
            manifest_registrar=register_manifest,
            doctor_registrar=register_doctor,
        ).format_help()

        self.assertEqual(registered, ["manifest", "doctor"])
        self.assertNotIn("Injected manifest command.", default_help)
        self.assertNotIn("Injected doctor command.", default_help)
        self.assertIn("Inspect static provider configuration and local", default_help)
        self.assertIn("Injected manifest command.", injected_help)
        self.assertIn("Injected doctor command.", injected_help)

    def test_doctor_json_is_static_machine_readable_and_includes_provenance(
        self,
    ) -> None:
        report = {
            "schema_version": 1,
            "status": "ready",
            "diagnostic_scope": "static_configuration_and_local_dependencies",
            "live_network_checked": False,
            "provider_status": {
                "providers": [
                    {
                        "provider": "crossref",
                        "status": "ready",
                        "reason": "Static requirements are ready.",
                        "suggested_action": "run the requested fetch",
                    }
                ]
            },
            "install_provenance": {
                "status": "not_applicable",
                "reason_code": "source_development_without_offline_manifest",
            },
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(
                paper_fetch_cli, "build_doctor_payload", return_value=report
            ) as build_report,
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = paper_fetch_cli.main(
                [
                    "doctor",
                    "--provider",
                    "crossref",
                    "--detail",
                    "compact",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), report)
        build_report.assert_called_once_with(
            provider="crossref",
            group=None,
            detail="compact",
            env_file=None,
            install_root=None,
        )

    def test_doctor_human_output_explains_static_preflight_auth_layers(self) -> None:
        report = {
            "status": "degraded",
            "provider_status": {
                "providers": [
                    {
                        "provider": "wiley",
                        "status": "not_configured",
                        "reason": "Local browser dependency is missing.",
                        "suggested_action": "prepare the browser runtime",
                    }
                ]
            },
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(
                paper_fetch_cli, "build_doctor_payload", return_value=report
            ),
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = paper_fetch_cli.main(["doctor", "--provider", "wiley"])

        rendered = stdout.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("static configuration and local dependencies", rendered)
        self.assertIn("Live publisher or browser-page checks: not run", rendered)
        self.assertIn("browser-preflight", rendered)
        self.assertIn("auth explicitly", rendered)

    def test_doctor_rejects_incompatible_provider_group_before_probing(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(paper_fetch_cli, "build_doctor_payload") as build_report,
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            build_report.side_effect = ValueError(
                "provider 'crossref' does not belong to group 'browser'."
            )
            paper_fetch_cli.main(
                ["doctor", "--provider", "crossref", "--group", "browser"]
            )

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("does not belong to group", stderr.getvalue())

    def test_fetch_subparser_preserves_root_defaults_and_pre_command_values(
        self,
    ) -> None:
        args = paper_fetch_cli.build_parser().parse_args(
            [
                "--artifact-mode",
                "none",
                "--asset-profile",
                "all",
                "fetch",
                "--query",
                "10.1000/example",
            ]
        )

        self.assertEqual(args.query, "10.1000/example")
        self.assertEqual(args.artifact_mode, "none")
        self.assertEqual(args.asset_profile, "all")
        self.assertEqual(args.format, "markdown")
        self.assertEqual(args.output, "-")

    def test_explicit_fetch_and_legacy_root_fetch_have_same_contract(self) -> None:
        def invoke(prefix: list[str], output_dir: Path):
            captured: dict[str, object] = {}
            article = sample_article()

            def fake_fetch(*args, **kwargs):
                captured.update(kwargs)
                return paper_fetch.build_fetch_envelope(
                    article, modes=kwargs["modes"], render=kwargs["render"]
                )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli,
                    "resolve_cli_download_dir",
                    return_value=output_dir,
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main(
                    [
                        *prefix,
                        "--query",
                        "10.1016/test",
                        "--output",
                        "-",
                        "--artifact-mode",
                        "none",
                        "--asset-profile",
                        "none",
                    ]
                )
            return exit_code, stdout.getvalue(), stderr.getvalue(), captured

        with tempfile.TemporaryDirectory() as tmpdir:
            legacy = invoke([], Path(tmpdir) / "legacy")
            explicit = invoke(["fetch"], Path(tmpdir) / "explicit")

        self.assertEqual(legacy[:3], explicit[:3])
        self.assertEqual(legacy[0], 0)
        self.assertIn("# Example Article", legacy[1])
        self.assertEqual(legacy[2], "")
        for key in ("modes", "render", "strategy"):
            self.assertEqual(legacy[3][key], explicit[3][key])
        self.assertEqual(legacy[3]["context"].artifact_mode, "none")
        self.assertEqual(explicit[3]["context"].artifact_mode, "none")

    def test_argparse_errors_use_command_specific_usage_and_stderr(self) -> None:
        cases = (
            (["unknown-command"], "usage: paper-fetch ", "invalid choice"),
            (["--unknown-option"], "usage: paper-fetch ", "unrecognized arguments"),
            (
                ["fetch", "--unknown-option"],
                "usage: paper-fetch ",
                "unrecognized arguments",
            ),
        )
        for argv, usage, message in cases:
            with self.subTest(argv=argv):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with (
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                    self.assertRaises(SystemExit) as raised,
                ):
                    paper_fetch_cli.main(argv)

                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue(stderr.getvalue().startswith(usage))
                self.assertIn(message, stderr.getvalue())

    def test_explicit_fetch_rejects_conflicting_query_sources(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            paper_fetch_cli.main(
                [
                    "fetch",
                    "--query",
                    "10.1000/a",
                    "--query-file",
                    "queries.txt",
                ]
            )

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertTrue(stderr.getvalue().startswith("usage: paper-fetch fetch "))
        self.assertIn("not allowed with argument", stderr.getvalue())

    def test_auth_ams_subcommand_is_not_supported(self) -> None:
        stderr = io.StringIO()
        original_argv = sys.argv
        sys.argv = ["paper_fetch.py", "auth", "ams"]
        try:
            with (
                mock.patch.object(
                    paper_fetch_cli, "authenticate_provider_profile"
                ) as authenticate,
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit) as raised,
            ):
                paper_fetch_cli.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())
        authenticate.assert_not_called()

    def test_auth_wiley_subcommand_invokes_generic_auth_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "storage-state.json"
            profile_dir = Path(tmpdir) / "publisher-browser-profiles" / "wiley"
            target_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
            auth_result = SimpleNamespace(
                storage_state_path=state_path,
                profile_dir=profile_dir,
                env_written=False,
                env_file_path=None,
                verified=True,
                final_url=target_url,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "auth",
                "wiley",
                "--url",
                target_url,
                "--timeout-ms",
                "45000",
                "--browser-user-agent",
                "Mozilla/5.0 auth-test",
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli,
                        "authenticate_provider_profile",
                        return_value=auth_result,
                    ) as authenticate,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            rendered = stdout.getvalue()
            self.assertIn("Wiley storage state:", rendered)
            self.assertIn("Wiley profile dir:", rendered)
            self.assertIn(
                "Persistent browser state is optional; fetches still run without it.",
                rendered,
            )
            authenticate.assert_called_once()
            kwargs = authenticate.call_args.kwargs
            self.assertEqual(kwargs["provider"], "wiley")
            self.assertEqual(kwargs["target_url"], target_url)
            self.assertEqual(kwargs["timeout_ms"], 45000)
            self.assertEqual(kwargs["browser_user_agent"], "Mozilla/5.0 auth-test")

    def test_auth_rejects_legacy_ams_only_args_for_all_providers(self) -> None:
        cases = (
            ("wiley", "--state-json", "state.json"),
            ("wiley", "--env-file", ".env"),
            ("wiley", "--no-env-write"),
            ("wiley", "--wait-seconds", "30"),
        )
        for case in cases:
            with self.subTest(case=case):
                stderr = io.StringIO()
                original_argv = sys.argv
                sys.argv = ["paper_fetch.py", "auth", *case]
                try:
                    with (
                        mock.patch.object(
                            paper_fetch_cli, "authenticate_provider_profile"
                        ) as authenticate,
                        contextlib.redirect_stderr(stderr),
                        self.assertRaises(SystemExit) as raised,
                    ):
                        paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(raised.exception.code, 2)
                self.assertIn("unsupported for provider auth", stderr.getvalue())
                authenticate.assert_not_called()

    def test_auth_subcommand_reports_provider_failure(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        original_argv = sys.argv
        sys.argv = ["paper_fetch.py", "auth", "wiley"]
        try:
            with (
                mock.patch.object(
                    paper_fetch_cli,
                    "authenticate_provider_profile",
                    side_effect=ProviderFailure(
                        "not_configured", "CloakBrowser missing."
                    ),
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["status"], "not_configured")
        self.assertEqual(payload["reason"], "CloakBrowser missing.")

    def test_browser_preflight_subcommand_invokes_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = (
                Path(tmpdir)
                / "publisher-browser-profiles"
                / "wiley"
                / "storage-state.json"
            )
            preflight_result = paper_fetch_cli.BrowserPreflightResult(
                provider="wiley",
                provider_label="Wiley",
                ok=True,
                target_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
                final_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
                storage_state_path=state_path,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "browser-preflight",
                "--provider",
                "wiley",
                "--timeout-ms",
                "45000",
                "--browser-user-agent",
                "Mozilla/5.0 preflight-test",
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli,
                        "run_browser_provider_preflight",
                        return_value=[preflight_result],
                    ) as run_preflight,
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            rendered = stdout.getvalue()
            self.assertIn("ok: Wiley (wiley)", rendered)
            self.assertIn("Storage state:", rendered)
            run_preflight.assert_called_once()
            kwargs = run_preflight.call_args.kwargs
            self.assertEqual(kwargs["providers"], ["wiley"])
            self.assertEqual(kwargs["timeout_ms"], 45000)
            self.assertEqual(kwargs["browser_user_agent"], "Mozilla/5.0 preflight-test")

    def test_browser_preflight_subcommand_reports_auth_hint_on_failure(self) -> None:
        preflight_result = paper_fetch_cli.BrowserPreflightResult(
            provider="wiley",
            provider_label="Wiley",
            ok=False,
            target_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
            reason="cloudflare_challenge",
            message="Encountered a challenge or CAPTCHA page while loading publisher HTML.",
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        original_argv = sys.argv
        sys.argv = ["paper_fetch.py", "browser-preflight", "--provider", "wiley"]
        try:
            with (
                mock.patch.object(
                    paper_fetch_cli,
                    "run_browser_provider_preflight",
                    return_value=[preflight_result],
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main()
        finally:
            sys.argv = original_argv

        self.assertEqual(exit_code, 1)
        self.assertIn("failed: Wiley (wiley)", stdout.getvalue())
        self.assertIn("paper-fetch auth wiley", stderr.getvalue())

    def test_main_writes_markdown_json_and_both_to_stdout(self) -> None:
        article = sample_article()
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            paper_fetch_cli.fetch_paper = lambda *args, **kwargs: build_envelope(
                article
            )
            for output_format in ("markdown", "json", "both"):
                stdout = io.StringIO()
                stderr = io.StringIO()
                argv = [
                    "paper_fetch.py",
                    "--query",
                    "10.1016/test",
                    "--format",
                    output_format,
                    "--artifact-mode",
                    "none",
                    "--asset-profile",
                    "none",
                ]
                original_argv = sys.argv
                sys.argv = argv
                try:
                    with (
                        contextlib.redirect_stdout(stdout),
                        contextlib.redirect_stderr(stderr),
                    ):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, 0)
                self.assertEqual(stderr.getvalue(), "")
                rendered = stdout.getvalue()
                self.assertTrue(rendered)
                if output_format == "markdown":
                    self.assertIn("# Example Article", rendered)
                else:
                    payload = json.loads(rendered)
                    if output_format == "json":
                        self.assertEqual(payload["doi"], "10.1016/test")
                    else:
                        self.assertIn("article", payload)
                        self.assertIn("markdown", payload)
        finally:
            paper_fetch_cli.fetch_paper = original_fetch

    def test_main_writes_single_output_file_when_requested(self) -> None:
        article = sample_article()
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            paper_fetch_cli.fetch_paper = lambda *args, **kwargs: build_envelope(
                article
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "article.md"
                stdout = io.StringIO()
                original_argv = sys.argv
                sys.argv = [
                    "paper_fetch.py",
                    "--query",
                    "10.1016/test",
                    "--output",
                    str(output_path),
                ]
                try:
                    with contextlib.redirect_stdout(stdout):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, 0)
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue(output_path.exists())
                self.assertIn(
                    "# Example Article", output_path.read_text(encoding="utf-8")
                )
        finally:
            paper_fetch_cli.fetch_paper = original_fetch

    def test_main_explicit_output_path_takes_precedence_over_output_dir_default(
        self,
    ) -> None:
        article = sample_article()

        def fake_fetch(*args, **kwargs):
            return paper_fetch.build_fetch_envelope(
                article, modes=kwargs["modes"], render=kwargs["render"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "explicit.md"
            output_dir = Path(tmpdir) / "papers"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--output",
                str(output_path),
                "--output-dir",
                str(output_dir),
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue(output_path.exists())
            self.assertIn("# Example Article", output_path.read_text(encoding="utf-8"))
            self.assertFalse(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_asset_profile_none_preserves_remote_markdown_images_in_output_file(
        self,
    ) -> None:
        article = sample_article()
        article.sections[0].text = "\n\n".join(
            [
                article.sections[0].text,
                "![Figure 1](https://example.test/figure-1.png)",
                "**Figure 1.** Remote figure caption.",
            ]
        )

        def fake_fetch(*args, **kwargs):
            return paper_fetch.build_fetch_envelope(
                article, modes=kwargs["modes"], render=kwargs["render"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "article.md"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--asset-profile",
                "none",
                "--artifact-mode",
                "none",
                "--output",
                str(output_path),
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            rendered = output_path.read_text(encoding="utf-8")
            self.assertIn("![Figure 1](https://example.test/figure-1.png)", rendered)
            self.assertFalse(any(Path(tmpdir).glob("*_assets")))

    def test_main_writes_markdown_to_output_dir_default_file_when_output_is_implicit(
        self,
    ) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "papers"
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir(parents=True)
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure.",
                    path=str(figure_path),
                    section="body",
                )
            ]

            def fake_fetch(*args, **kwargs):
                captured.update(kwargs)
                return paper_fetch.build_fetch_envelope(
                    article, modes=kwargs["modes"], render=kwargs["render"]
                )

            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--format",
                "markdown",
                "--output-dir",
                str(output_dir),
                "--asset-profile",
                "body",
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(captured["modes"], {"article", "markdown"})
            saved_path = output_dir / "Example_et_al_2026_Example_Article.md"
            self.assertTrue(saved_path.exists())
            rendered = saved_path.read_text(encoding="utf-8")
            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", rendered)
            self.assertNotIn(str(figure_path), rendered)

    def test_main_implicit_format_writes_markdown_to_output_dir_default_file(
        self,
    ) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            self.assertTrue(output_dir.is_dir())
            captured.update(kwargs)
            return paper_fetch.build_fetch_envelope(
                article, modes=kwargs["modes"], render=kwargs["render"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "papers"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--output-dir",
                str(output_dir),
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(captured["modes"], {"article", "markdown"})
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_creates_env_download_dir_before_fetch(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            self.assertTrue(output_dir.is_dir())
            captured.update(kwargs)
            return paper_fetch.build_fetch_envelope(
                article, modes=kwargs["modes"], render=kwargs["render"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "env-downloads"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    paper_fetch_cli,
                    "build_runtime_env",
                    return_value={DOWNLOAD_DIR_ENV_VAR: str(output_dir)},
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main(["--query", "10.1016/test"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("# Example Article", stdout.getvalue())
            self.assertEqual(captured["context"].download_dir, output_dir)
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_rejects_output_dir_that_is_existing_file_before_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "papers"
            output_dir.write_text("not a directory", encoding="utf-8")
            fetch_mock = mock.Mock(side_effect=AssertionError("fetch should not run"))
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(paper_fetch_cli, "fetch_paper", fetch_mock),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main(
                    ["--query", "10.1016/test", "--output-dir", str(output_dir)]
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(fetch_mock.call_count, 0)
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["status"], "error")
            self.assertIn("not a directory", payload["reason"])

    def test_main_does_not_create_parent_for_explicit_output_file(self) -> None:
        article = sample_article()
        calls: list[str] = []

        def fake_fetch(*args, **kwargs):
            calls.append("fetch")
            return paper_fetch.build_fetch_envelope(
                article, modes=kwargs["modes"], render=kwargs["render"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_path = Path(tmpdir) / "missing-parent" / "article.md"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli, "resolve_cli_download_dir", return_value=output_dir
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(FileNotFoundError),
            ):
                paper_fetch_cli.main(
                    ["--query", "10.1016/test", "--output", str(output_path)]
                )

            self.assertEqual(calls, ["fetch"])
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertFalse(output_path.parent.exists())

    def test_main_writes_json_and_both_to_output_dir_default_files_when_output_is_implicit(
        self,
    ) -> None:
        article = sample_article()

        for output_format, expected_name in (
            ("json", "Example_et_al_2026_Example_Article.json"),
            ("both", "Example_et_al_2026_Example_Article.both.json"),
        ):
            with (
                self.subTest(output_format=output_format),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                output_dir = Path(tmpdir) / "papers"

                def fake_fetch(*args, **kwargs):
                    return paper_fetch.build_fetch_envelope(
                        article, modes=kwargs["modes"], render=kwargs["render"]
                    )

                stdout = io.StringIO()
                stderr = io.StringIO()
                original_argv = sys.argv
                sys.argv = [
                    "paper_fetch.py",
                    "--query",
                    "10.1016/test",
                    "--artifact-mode",
                    "all",
                    "--format",
                    output_format,
                    "--output-dir",
                    str(output_dir),
                ]
                try:
                    with (
                        mock.patch.object(
                            paper_fetch_cli, "build_runtime_env", return_value={}
                        ),
                        mock.patch.object(
                            paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                        ),
                        contextlib.redirect_stdout(stdout),
                        contextlib.redirect_stderr(stderr),
                    ):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, 0)
                self.assertEqual(stderr.getvalue(), "")
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue((output_dir / expected_name).exists())
                payload = json.loads(
                    (output_dir / expected_name).read_text(encoding="utf-8")
                )
                if output_format == "json":
                    self.assertEqual(payload["doi"], "10.1016/test")
                else:
                    self.assertIn("article", payload)
                    self.assertIn("markdown", payload)

    def test_main_explicit_stdout_keeps_printing_with_output_dir(self) -> None:
        article = sample_article()

        def fake_fetch(*args, **kwargs):
            return paper_fetch.build_fetch_envelope(
                article, modes=kwargs["modes"], render=kwargs["render"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "papers"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--output",
                "-",
                "--output-dir",
                str(output_dir),
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("# Example Article", stdout.getvalue())
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_uses_resolved_default_download_dir_for_save_markdown(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            captured.update(kwargs)
            return build_envelope(article)

        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "downloads"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = ["paper_fetch.py", "--query", "10.1016/test", "--save-markdown"]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli,
                        "resolve_cli_download_dir",
                        return_value=default_dir,
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["context"].download_dir, default_dir)
            self.assertTrue(
                (default_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_save_markdown_to_disk_rewrites_local_asset_links_relative_to_saved_file(
        self,
    ) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir(parents=True)
            figure_path = asset_dir / "figure%201.png"
            supplement_path = asset_dir / "supplement data%.pdf"
            figure_path.write_bytes(b"figure")
            supplement_path.write_bytes(b"supplement")
            article.sections[0].text += f"\n\nAbsolute path mention: {figure_path}"

            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure.",
                    path=str(figure_path),
                    section="body",
                ),
                Asset(
                    kind="supplementary",
                    heading="Supplementary Data",
                    caption="Raw measurements.",
                    path=str(supplement_path),
                ),
                Asset(
                    kind="supplementary",
                    heading="Remote Appendix",
                    caption="Hosted by publisher.",
                    url="https://example.test/appendix.pdf",
                ),
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="all"),
            )

            assert envelope.markdown is not None
            self.assertIn(str(figure_path), envelope.markdown)
            self.assertIn(str(supplement_path), envelope.markdown)

            paper_fetch_cli.save_markdown_to_disk(
                envelope,
                output_dir=output_dir,
                render=RenderOptions(asset_profile="all"),
            )

            rendered = (output_dir / "Example_et_al_2026_Example_Article.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("![Figure 1](10.1016_test_assets/figure%25201.png)", rendered)
            self.assertIn(
                "[Supplementary Data](10.1016_test_assets/supplement%20data%25.pdf)",
                rendered,
            )
            self.assertIn(
                "[Remote Appendix](https://example.test/appendix.pdf)", rendered
            )
            self.assertIn(f"Absolute path mention: {figure_path}", rendered)
            self.assertEqual(rendered.count(str(figure_path)), 1)
            self.assertNotIn(f"]({figure_path})", rendered)
            self.assertNotIn(f"]({supplement_path})", rendered)

    def test_save_markdown_to_disk_skips_when_content_kind_is_not_fulltext(
        self,
    ) -> None:
        article = sample_article()
        article.sections = []
        article.quality.content_kind = "abstract_only"
        article.quality.has_fulltext = False
        article.quality.has_abstract = True
        envelope = paper_fetch.build_fetch_envelope(
            article,
            modes={"article", "markdown"},
            render=RenderOptions(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            paper_fetch_cli.save_markdown_to_disk(
                envelope,
                output_dir=output_dir,
                render=RenderOptions(),
            )

            self.assertFalse(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )
            self.assertIn(
                "download:markdown_skipped_no_fulltext", envelope.source_trail
            )
            self.assertTrue(
                any(
                    "nothing written to disk" in warning
                    for warning in envelope.warnings
                )
            )

    def test_main_rewrites_local_asset_links_for_markdown_output_file(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure.",
                    path=str(figure_path),
                    section="body",
                )
            ]

            def fake_fetch(*args, **kwargs):
                captured.update(kwargs)
                return paper_fetch.build_fetch_envelope(
                    article, modes=kwargs["modes"], render=kwargs["render"]
                )

            output_path = output_dir / "article.md"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--format",
                "markdown",
                "--asset-profile",
                "body",
                "--output",
                str(output_path),
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli,
                        "resolve_cli_download_dir",
                        return_value=output_dir,
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["modes"], {"article", "markdown"})
            self.assertEqual(captured["context"].download_dir, output_dir)
            rendered = output_path.read_text(encoding="utf-8")
            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", rendered)
            self.assertNotIn(str(figure_path), rendered)

    def test_rewrite_markdown_asset_links_only_changes_placeholder_links(self) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            supplementary_path = asset_dir / "figure-1.png.backup"
            figure_path.write_bytes(b"figure")
            supplementary_path.write_bytes(b"supplementary")
            article.sections[
                0
            ].text += f"\n\nBody mentions {figure_path} and {supplementary_path}."
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure.",
                    path=str(figure_path),
                    section="body",
                ),
                Asset(
                    kind="supplementary",
                    heading="Backup",
                    caption="Archive.",
                    path=str(supplementary_path),
                ),
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="all"),
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="all"),
            )

            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", rewritten)
            self.assertIn(
                "[Backup](10.1016_test_assets/figure-1.png.backup)", rewritten
            )
            self.assertIn(
                f"Body mentions {figure_path} and {supplementary_path}.", rewritten
            )

    def test_rewrite_markdown_asset_links_rewrites_inline_section_images_without_touching_plain_text_paths(
        self,
    ) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.sections[0].text = "\n".join(
                [
                    "Body mentions the original path in prose:",
                    str(figure_path),
                    "",
                    f"![Figure 1]({figure_path})",
                    "",
                    "**Figure 1.** Inline caption text.",
                ]
            )
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Inline caption text.",
                    path=str(figure_path),
                    section="body",
                )
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="body"),
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="body"),
            )

            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", rewritten)
            self.assertIn(str(figure_path), rewritten)
            self.assertEqual(rewritten.count(str(figure_path)), 1)

    def test_rewrite_markdown_asset_links_handles_image_alt_with_brackets(self) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "body_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.sections[
                0
            ].text = (
                f"![Functional relation $\\mathcal{{F}}[R(\\Delta)]$]({figure_path})"
            )
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Functional relation.",
                    path=str(figure_path),
                    section="body",
                )
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="body"),
            )
            envelope.markdown = (
                f"![Functional relation $\\mathcal{{F}}[R(\\Delta)]$]({figure_path})"
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="body"),
            )

            self.assertIn(
                "![Figure 1](body_assets/figure-1.png)",
                rewritten,
            )
            self.assertNotIn("Functional relation", rewritten)
            self.assertNotIn(str(figure_path), rewritten)

    def test_rewrite_markdown_asset_links_prefers_updated_asset_path_over_existing_old_path(
        self,
    ) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            old_asset_dir = output_dir / "10.3390_test_assets"
            new_asset_dir = output_dir / "body_assets"
            old_asset_dir.mkdir()
            new_asset_dir.mkdir()
            old_path = old_asset_dir / "figure-1.png"
            new_path = new_asset_dir / "figure-1.png"
            old_path.write_bytes(b"old figure")
            new_path.write_bytes(b"new figure")
            article.sections[0].text = f"![Figure 1]({old_path})"
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Inline caption text.",
                    path=str(new_path),
                    section="body",
                )
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="body"),
            )
            envelope.markdown = f"![Figure 1]({old_path})"

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="body"),
            )

            self.assertIn("![Figure 1](body_assets/figure-1.png)", rewritten)
            self.assertNotIn("10.3390_test_assets", rewritten)
            self.assertNotIn(str(old_path), rewritten)

    def test_rewrite_markdown_asset_links_maps_remote_figure_urls_to_downloaded_local_assets(
        self,
    ) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1073_pnas.1219683110_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "pnas.1219683110fig03.jpeg"
            figure_path.write_bytes(b"figure")
            article.sections[0].text = "\n".join(
                [
                    "Remote image before local rewrite:",
                    "![Figure 3](https://www.pnas.org/cms/10.1073/pnas.1219683110/asset/example/assets/graphic/pnas.1219683110fig03.jpeg)",
                    "",
                    "**Figure 3.** Inline caption text.",
                ]
            )
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 3",
                    caption="Inline caption text.",
                    path=str(figure_path),
                    section="body",
                )
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="body"),
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="body"),
            )

            self.assertIn(
                "![Figure 3](10.1073_pnas.1219683110_assets/pnas.1219683110fig03.jpeg)",
                rewritten,
            )
            self.assertNotIn(
                "https://www.pnas.org/cms/10.1073/pnas.1219683110/asset/example",
                rewritten,
            )

    def test_rewrite_markdown_asset_links_maps_ieee_full_and_preview_fallback_urls(
        self,
    ) -> None:
        article = sample_article()
        article.sections[0].text = "\n".join(
            [
                "IEEE inline images before local rewrite:",
                "![Fig. 1](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg1-0932570-large.gif)",
                "![Fig. 2](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg2-0932570-large.gif)",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1109_CICTN64563.2025.10932570_assets"
            asset_dir.mkdir()
            full_path = asset_dir / "garg1-0932570-large.gif"
            preview_path = asset_dir / "garg2-0932570-small.gif"
            full_path.write_bytes(b"full")
            preview_path.write_bytes(b"preview")
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Fig. 1",
                    caption="Full-size figure.",
                    path=str(full_path),
                    section="body",
                    original_url="https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg1-0932570-large.gif",
                    download_url="https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg1-0932570-large.gif",
                    download_tier="full_size",
                ),
                Asset(
                    kind="figure",
                    heading="Fig. 2",
                    caption="Preview fallback figure.",
                    path=str(preview_path),
                    section="body",
                    original_url="https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg2-0932570-large.gif",
                    download_url="https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg2-0932570-small.gif",
                    download_tier="preview",
                ),
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="body"),
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="body"),
            )

            self.assertIn(
                "![Figure 1](10.1109_CICTN64563.2025.10932570_assets/garg1-0932570-large.gif)",
                rewritten,
            )
            self.assertIn(
                "![Figure 2](10.1109_CICTN64563.2025.10932570_assets/garg2-0932570-small.gif)",
                rewritten,
            )
            self.assertNotIn("ieeexplore.ieee.org/mediastore", rewritten)

    def test_rewrite_markdown_asset_links_rewrites_repo_relative_local_paths_against_output_file(
        self,
    ) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmpdir:
            repo_root = Path(tmpdir)
            output_dir = repo_root / "scratch_outputs" / "10.1073_pnas.1219683110"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1073_pnas.1219683110_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "pnas.1219683110fig01.jpeg"
            figure_path.write_bytes(b"figure")
            repo_relative_path = figure_path.relative_to(Path.cwd())

            article.sections[0].text = "\n".join(
                [
                    "Repo-relative image before local rewrite:",
                    f"![Figure 1]({repo_relative_path.as_posix()})",
                    "",
                    "**Figure 1.** Inline caption text.",
                ]
            )
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Inline caption text.",
                    path=repo_relative_path.as_posix(),
                    section="body",
                )
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="body"),
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "10.1073_pnas.1219683110.md",
                render=RenderOptions(asset_profile="body"),
            )

            self.assertIn(
                "![Figure 1](10.1073_pnas.1219683110_assets/pnas.1219683110fig01.jpeg)",
                rewritten,
            )
            self.assertNotIn(f"![Figure 1]({repo_relative_path.as_posix()})", rewritten)

    def test_rewrite_markdown_asset_links_resolves_symlinked_absolute_asset_paths(
        self,
    ) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            real_root = tmp_root / "real"
            alias_root = tmp_root / "alias"
            real_root.mkdir()
            try:
                os.symlink(real_root, alias_root)
            except (OSError, NotImplementedError):
                self.skipTest("filesystem does not support symlinks")

            output_dir = real_root / "downloads"
            asset_dir = alias_root / "downloads" / "10.1016_test_assets"
            asset_dir.mkdir(parents=True)
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.sections[0].text = f"![Figure 1]({figure_path})"
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure.",
                    path=str(figure_path),
                    section="body",
                )
            ]
            envelope = paper_fetch.build_fetch_envelope(
                article,
                modes={"article", "markdown"},
                render=RenderOptions(asset_profile="body"),
            )

            rewritten = paper_fetch_cli.rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=output_dir / "article.md",
                render=RenderOptions(asset_profile="body"),
            )

            self.assertIn("![Figure 1](10.1016_test_assets/figure-1.png)", rewritten)
            self.assertNotIn(str(figure_path), rewritten)

    def test_main_rewrites_local_asset_links_for_both_output_file(self) -> None:
        article = sample_article()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            output_dir.mkdir(parents=True)
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir()
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"figure")
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure.",
                    path=str(figure_path),
                    section="body",
                )
            ]

            def fake_fetch(*args, **kwargs):
                return paper_fetch.build_fetch_envelope(
                    article, modes=kwargs["modes"], render=kwargs["render"]
                )

            output_path = output_dir / "result.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--format",
                "both",
                "--asset-profile",
                "body",
                "--output",
                str(output_path),
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli,
                        "resolve_cli_download_dir",
                        return_value=output_dir,
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertIn(
                "![Figure 1](10.1016_test_assets/figure-1.png)", payload["markdown"]
            )
            self.assertNotIn(str(figure_path), payload["markdown"])

    def test_main_defaults_to_markdown_assets_body_and_full_text(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            captured.update(kwargs)
            return build_envelope(article)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = ["paper_fetch.py", "--query", "10.1016/test"]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli,
                        "resolve_cli_download_dir",
                        return_value=output_dir,
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["modes"], {"article", "markdown"})
            self.assertEqual(
                captured["render"],
                RenderOptions(
                    include_refs=None, asset_profile="body", max_tokens="full_text"
                ),
            )
            self.assertEqual(
                captured["strategy"],
                paper_fetch.FetchStrategy(
                    allow_metadata_only_fallback=True,
                    preferred_providers=None,
                    asset_profile="body",
                ),
            )
            self.assertEqual(captured["context"].artifact_mode, "markdown-assets")
            self.assertEqual(captured["context"].download_dir, output_dir)
            self.assertIsNone(captured["context"].transport.disk_cache_dir)
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_markdown_assets_writes_json_or_both_primary_output_and_markdown_artifact(
        self,
    ) -> None:
        article = sample_article()

        for output_format, expected_name in (
            ("json", "Example_et_al_2026_Example_Article.json"),
            ("both", "Example_et_al_2026_Example_Article.both.json"),
        ):
            with (
                self.subTest(output_format=output_format),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                output_dir = Path(tmpdir) / "papers"

                def fake_fetch(*args, **kwargs):
                    return paper_fetch.build_fetch_envelope(
                        article, modes=kwargs["modes"], render=kwargs["render"]
                    )

                stdout = io.StringIO()
                stderr = io.StringIO()
                original_argv = sys.argv
                sys.argv = [
                    "paper_fetch.py",
                    "--query",
                    "10.1016/test",
                    "--format",
                    output_format,
                    "--output-dir",
                    str(output_dir),
                ]
                try:
                    with (
                        mock.patch.object(
                            paper_fetch_cli, "build_runtime_env", return_value={}
                        ),
                        mock.patch.object(
                            paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                        ),
                        contextlib.redirect_stdout(stdout),
                        contextlib.redirect_stderr(stderr),
                    ):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, 0)
                self.assertEqual(stderr.getvalue(), "")
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue((output_dir / expected_name).exists())
                self.assertTrue(
                    (output_dir / "Example_et_al_2026_Example_Article.md").exists()
                )

    def test_main_no_download_is_deprecated_alias_for_artifact_mode_none(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            captured.update(kwargs)
            return build_envelope(article)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--output-dir",
                str(output_dir),
                "--no-download",
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["context"].artifact_mode, "none")
            self.assertIsNone(captured["context"].download_dir)
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_artifact_mode_none_still_writes_primary_output_dir_file(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            captured.update(kwargs)
            return build_envelope(article)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--artifact-mode",
                "none",
                "--output-dir",
                str(output_dir),
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["context"].artifact_mode, "none")
            self.assertEqual(captured["context"].download_dir, output_dir)
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_artifact_mode_none_still_allows_explicit_save_markdown(self) -> None:
        article = sample_article()
        captured: dict[str, object] = {}

        def fake_fetch(*args, **kwargs):
            captured.update(kwargs)
            return build_envelope(article)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "paper_fetch.py",
                "--query",
                "10.1016/test",
                "--artifact-mode",
                "none",
                "--output-dir",
                str(output_dir),
                "--save-markdown",
            ]
            try:
                with (
                    mock.patch.object(
                        paper_fetch_cli, "build_runtime_env", return_value={}
                    ),
                    mock.patch.object(
                        paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                    ),
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(captured["context"].artifact_mode, "none")
            self.assertEqual(captured["context"].download_dir, output_dir)
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Example_Article.md").exists()
            )

    def test_main_markdown_assets_respects_explicit_asset_profile(self) -> None:
        article = sample_article()

        for asset_profile in ("none", "body", "all"):
            with (
                self.subTest(asset_profile=asset_profile),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                captured: dict[str, object] = {}

                def fake_fetch(*args, captured=captured, **kwargs):
                    captured.update(kwargs)
                    return build_envelope(article)

                stdout = io.StringIO()
                stderr = io.StringIO()
                original_argv = sys.argv
                sys.argv = [
                    "paper_fetch.py",
                    "--query",
                    "10.1016/test",
                    "--output-dir",
                    str(Path(tmpdir) / "downloads"),
                    "--asset-profile",
                    asset_profile,
                ]
                try:
                    with (
                        mock.patch.object(
                            paper_fetch_cli, "build_runtime_env", return_value={}
                        ),
                        mock.patch.object(
                            paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                        ),
                        contextlib.redirect_stdout(stdout),
                        contextlib.redirect_stderr(stderr),
                    ):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, 0)
                self.assertEqual(stderr.getvalue(), "")
                self.assertEqual(captured["render"].asset_profile, asset_profile)
                self.assertEqual(captured["strategy"].asset_profile, asset_profile)
                self.assertEqual(captured["context"].artifact_mode, "markdown-assets")

    def test_read_query_file_ignores_blank_lines_and_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            query_file = Path(tmpdir) / "queries.txt"
            query_file.write_text(
                "\n".join(
                    [
                        "",
                        "  # comment",
                        "  10.1000/a  ",
                        "Example paper title",
                        "",
                        "# another comment",
                        "https://example.test/paper",
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                paper_fetch_cli.read_query_file(query_file),
                ["10.1000/a", "Example paper title", "https://example.test/paper"],
            )

    def test_main_rejects_query_and_query_file_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            query_file = Path(tmpdir) / "queries.txt"
            query_file.write_text("10.1000/a\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit) as raised,
            ):
                paper_fetch_cli.main(
                    ["--query", "10.1000/a", "--query-file", str(query_file)]
                )

            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("not allowed with argument", stderr.getvalue())

    def test_main_rejects_empty_query_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            query_file = Path(tmpdir) / "queries.txt"
            query_file.write_text("\n# comment\n  \n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli,
                    "resolve_cli_download_dir",
                    return_value=Path(tmpdir) / "downloads",
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit) as raised,
            ):
                paper_fetch_cli.main(["--query-file", str(query_file)])

            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("query file did not contain any queries", stderr.getvalue())

    def test_main_rejects_batch_concurrency_out_of_range(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            paper_fetch_cli.main(["--query", "10.1000/a", "--batch-concurrency", "9"])

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("batch-concurrency", stderr.getvalue())

    def test_main_batch_writes_markdown_files_and_results_jsonl(self) -> None:
        captured: list[dict[str, object]] = []

        def fake_fetch(query, *args, **kwargs):
            del args
            captured.append(kwargs)
            article = sample_article()
            article.doi = query
            article.metadata.title = f"Article {query}"
            return paper_fetch.build_fetch_envelope(
                article, modes=kwargs["modes"], render=kwargs["render"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            query_file = Path(tmpdir) / "queries.txt"
            query_file.write_text(
                "\n# ignored\n10.1000/a\n\n10.1000/b\n", encoding="utf-8"
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertFalse(output_dir.exists())

            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main(
                    ["--query-file", str(query_file), "--output-dir", str(output_dir)]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue(output_dir.is_dir())
            self.assertEqual(len(captured), 2)
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Article_10.1000_a.md").exists()
            )
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Article_10.1000_b.md").exists()
            )
            self.assertNotIn("# Example Article", stdout.getvalue())
            self.assertTrue(
                all(item["modes"] == {"article", "markdown"} for item in captured)
            )
            self.assertTrue(
                all(item["render"].asset_profile == "body" for item in captured)
            )
            self.assertTrue(
                all(
                    item["context"].artifact_mode == "markdown-assets"
                    for item in captured
                )
            )
            self.assertTrue(
                all(item["context"].download_dir == output_dir for item in captured)
            )
            self.assertIs(
                captured[0]["context"].transport, captured[1]["context"].transport
            )

            result_lines = [
                json.loads(line)
                for line in (output_dir / "batch-results.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual([item["status"] for item in result_lines], ["ok", "ok"])
            self.assertEqual([item["index"] for item in result_lines], [1, 2])
            self.assertTrue(all(item["output_path"] for item in result_lines))
            self.assertTrue(
                all(item["saved_markdown_path"] is None for item in result_lines)
            )

    def test_main_batch_continues_after_failure_and_returns_status_exit_code(
        self,
    ) -> None:
        calls: list[str] = []

        def fake_fetch(query, *args, **kwargs):
            del args, kwargs
            calls.append(query)
            if query == "10.1000/b":
                raise ProviderFailure(
                    "no_access", "Forbidden", warnings=["license required"]
                )
            article = sample_article()
            article.doi = query
            article.metadata.title = f"Article {query}"
            return build_envelope(article)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "papers"
            query_file = Path(tmpdir) / "queries.txt"
            results_path = Path(tmpdir) / "summary" / "results.jsonl"
            query_file.write_text("10.1000/a\n10.1000/b\n10.1000/c\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                mock.patch.object(
                    paper_fetch_cli, "build_runtime_env", return_value={}
                ),
                mock.patch.object(
                    paper_fetch_cli, "fetch_paper", side_effect=fake_fetch
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = paper_fetch_cli.main(
                    [
                        "--query-file",
                        str(query_file),
                        "--output-dir",
                        str(output_dir),
                        "--batch-results",
                        str(results_path),
                    ]
                )

            self.assertEqual(exit_code, 3)
            self.assertEqual(calls, ["10.1000/a", "10.1000/b", "10.1000/c"])
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Article_10.1000_a.md").exists()
            )
            self.assertFalse(
                (output_dir / "Example_et_al_2026_Article_10.1000_b.md").exists()
            )
            self.assertTrue(
                (output_dir / "Example_et_al_2026_Article_10.1000_c.md").exists()
            )

            result_lines = [
                json.loads(line)
                for line in results_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [item["status"] for item in result_lines], ["ok", "no_access", "ok"]
            )
            self.assertEqual(result_lines[1]["warnings"], ["license required"])
            self.assertEqual(result_lines[1]["error"]["reason"], "Forbidden")
            self.assertEqual(result_lines[2]["index"], 3)

    def test_parse_max_tokens_accepts_full_text_and_integers(self) -> None:
        self.assertEqual(paper_fetch_cli.parse_max_tokens("full_text"), "full_text")
        self.assertEqual(paper_fetch_cli.parse_max_tokens("16000"), 16000)

    def test_compute_modes_covers_stdout_file_both_and_save_markdown(self) -> None:
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(
                    format="markdown",
                    output="-",
                    save_markdown=False,
                    no_download=False,
                )
            ),
            {"markdown"},
        )
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(
                    format="markdown",
                    output="/tmp/out.md",
                    save_markdown=False,
                    no_download=False,
                )
            ),
            {"article", "markdown"},
        )
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(
                    format="markdown",
                    output="-",
                    save_markdown=False,
                    no_download=False,
                    primary_output_to_output_dir=True,
                )
            ),
            {"article", "markdown"},
        )
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(
                    format="both", output="-", save_markdown=False, no_download=True
                )
            ),
            {"article", "markdown"},
        )
        self.assertEqual(
            paper_fetch_cli._compute_modes(
                SimpleNamespace(
                    format="json", output="-", save_markdown=True, no_download=True
                )
            ),
            {"article", "markdown"},
        )

    def test_exit_code_for_error_maps_specific_statuses(self) -> None:
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(
                paper_fetch.PaperFetchFailure("ambiguous", "Need user confirmation.")
            ),
            2,
        )
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(
                ProviderFailure("no_access", "Forbidden")
            ),
            3,
        )
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(
                ProviderFailure("rate_limited", "Slow down")
            ),
            4,
        )
        self.assertEqual(
            paper_fetch_cli.exit_code_for_error(
                ProviderFailure("error", "Unexpected provider error")
            ),
            1,
        )

    def test_main_reports_ambiguous_errors_as_json(self) -> None:
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            paper_fetch_cli.fetch_paper = lambda *args, **kwargs: (_ for _ in ()).throw(
                paper_fetch.PaperFetchFailure(
                    "ambiguous",
                    "Need user confirmation.",
                    candidates=[{"doi": "10.1000/a", "title": "Candidate A"}],
                )
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_argv = sys.argv
            sys.argv = ["paper_fetch.py", "--query", "ambiguous title"]
            try:
                with (
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                ):
                    exit_code = paper_fetch_cli.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["status"], "ambiguous")
            self.assertEqual(payload["candidates"][0]["doi"], "10.1000/a")
        finally:
            paper_fetch_cli.fetch_paper = original_fetch

    def test_main_reports_provider_failure_status_and_exit_code(self) -> None:
        original_fetch = paper_fetch_cli.fetch_paper
        try:
            for code, expected_exit_code in (
                ("no_access", 3),
                ("rate_limited", 4),
                ("error", 1),
            ):
                stdout = io.StringIO()
                stderr = io.StringIO()
                paper_fetch_cli.fetch_paper = lambda *args, _code=code, **kwargs: (
                    _ for _ in ()
                ).throw(ProviderFailure(_code, f"{_code} failure"))
                original_argv = sys.argv
                sys.argv = ["paper_fetch.py", "--query", "10.1016/test"]
                try:
                    with (
                        contextlib.redirect_stdout(stdout),
                        contextlib.redirect_stderr(stderr),
                    ):
                        exit_code = paper_fetch_cli.main()
                finally:
                    sys.argv = original_argv

                self.assertEqual(exit_code, expected_exit_code)
                payload = json.loads(stderr.getvalue())
                self.assertEqual(payload["status"], code)
                self.assertIn("failure", payload["reason"])
        finally:
            paper_fetch_cli.fetch_paper = original_fetch
