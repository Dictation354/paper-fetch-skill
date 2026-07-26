# ruff: noqa
from __future__ import annotations


def build_parser() -> argparse.ArgumentParser:
    parser = CoordinatorArgumentParser(
        description="Generate manifest-driven provider onboarding dry-run artifacts."
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=CoordinatorArgumentParser
    )

    discover = subparsers.add_parser(
        "discover",
        help="print a manifest discovery worker brief",
    )
    discover.add_argument("--provider", required=True, help="provider name seed")
    discover.add_argument("--domain", help="provider domain seed")
    discover.add_argument("--doi-prefix", help="DOI prefix seed")
    discover.add_argument(
        "--output",
        required=True,
        help="manifest path the discovery worker is allowed to write",
    )
    discover.add_argument(
        "--evidence-pack",
        help="prepared discovery evidence pack path to include in the brief",
    )
    discover.set_defaults(func=run_discover)

    prepare_discovery = subparsers.add_parser(
        "prepare-discovery",
        help="write the manifest discovery evidence pack",
    )
    prepare_discovery.add_argument(
        "--provider", required=True, help="provider name seed"
    )
    prepare_discovery.add_argument(
        "--domain", required=True, help="provider domain seed"
    )
    prepare_discovery.add_argument(
        "--doi-prefix", required=True, help="DOI prefix seed"
    )
    prepare_discovery.add_argument(
        "--output-dir",
        required=True,
        help="directory for discovery/evidence-pack.json",
    )
    prepare_discovery.add_argument(
        "--no-network",
        action="store_true",
        help="only write query plans and routing seed evidence",
    )
    prepare_discovery.add_argument(
        "--browser-fallback",
        choices=DISCOVERY_BROWSER_FALLBACK_MODES,
        default="auto",
        help="whether discovery may fall back from HTTP landing probes to browser probes",
    )
    prepare_discovery.set_defaults(func=run_prepare_discovery)

    autofix_manifest = subparsers.add_parser(
        "autofix-manifest",
        help="repair schema-level manifest discovery gaps from an evidence pack",
    )
    autofix_manifest.add_argument(
        "--manifest", required=True, help="ProviderManifest YAML path"
    )
    autofix_manifest.add_argument(
        "--evidence-pack", required=True, help="discovery evidence pack JSON"
    )
    write_group = autofix_manifest.add_mutually_exclusive_group(required=True)
    write_group.add_argument(
        "--write", action="store_true", help="write changes back to manifest"
    )
    write_group.add_argument(
        "--dry-run", action="store_true", help="print proposed changes only"
    )
    autofix_manifest.add_argument(
        "--targeted",
        action="store_true",
        help="mark this as a validate-manifest retry autofix",
    )
    autofix_manifest.set_defaults(func=run_autofix_manifest)

    inspect_discovery = subparsers.add_parser(
        "inspect-discovery",
        help="summarize candidates, low-confidence purposes, and proof gaps",
    )
    inspect_discovery.add_argument(
        "--manifest", required=True, help="ProviderManifest YAML path"
    )
    inspect_discovery.add_argument(
        "--evidence-pack", required=True, help="discovery evidence pack JSON"
    )
    inspect_discovery.set_defaults(func=run_inspect_discovery)

    start = subparsers.add_parser(
        "start",
        help="write a dry-run onboarding DAG and worker briefs",
    )
    source = start.add_mutually_exclusive_group(required=True)
    source.add_argument("--provider", help="provider name seed")
    source.add_argument("--manifest", help="existing manifest path for replay mode")
    start.add_argument("--domain", help="provider domain seed")
    start.add_argument("--doi-prefix", help="DOI prefix seed")
    start.add_argument(
        "--dry-run", action="store_true", help="write planned artifacts only"
    )
    start.add_argument(
        "--output-dir", required=True, help="directory for dry-run artifacts"
    )
    start.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    start.set_defaults(func=run_start)

    run = subparsers.add_parser(
        "run",
        help="execute the serial onboarding DAG for one provider",
    )
    run_source = run.add_mutually_exclusive_group(required=True)
    run_source.add_argument("--provider", help="provider name seed")
    run_source.add_argument("--manifest", help="existing manifest path for replay mode")
    run.add_argument("--domain", help="provider domain seed")
    run.add_argument("--doi-prefix", help="DOI prefix seed")
    run.add_argument(
        "--until",
        default="merge-ready",
        help="inclusive task id to stop after; defaults to merge-ready",
    )
    run.add_argument(
        "--output-dir",
        help="directory for DAG, briefs, and worker logs",
    )
    run.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    run.set_defaults(func=run_run)

    diagnose = subparsers.add_parser(
        "diagnose",
        help="summarize blocked provider failures from coordinator state",
    )
    diagnose.add_argument("--provider", help="optional provider name")
    diagnose.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    diagnose.set_defaults(func=run_diagnose)

    resume_blocked = subparsers.add_parser(
        "resume-blocked",
        help="resume one retryable blocked provider after preconditions are satisfied",
    )
    resume_blocked.add_argument("--provider", required=True, help="provider name")
    resume_blocked.add_argument(
        "--dry-run", action="store_true", help="print resume plan only"
    )
    resume_blocked.add_argument(
        "--until",
        default="provider-local-acceptance",
        help="inclusive task id to stop after; defaults to provider-local-acceptance",
    )
    resume_blocked.add_argument(
        "--output-dir",
        help="directory for DAG, briefs, and worker logs",
    )
    resume_blocked.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    resume_blocked.set_defaults(func=run_resume_blocked)

    summarize = subparsers.add_parser(
        "summarize",
        help="render an operator-facing provider onboarding summary",
    )
    summarize.add_argument("--provider", required=True, help="provider name")
    summarize.add_argument(
        "--format",
        choices=("json", "markdown", "agent-json", "agent-markdown"),
        default="json",
        help="summary output format",
    )
    summarize.add_argument(
        "--target",
        choices=tuple(AGENT_TARGET_STEPS),
        default="local-ready",
        help="agent summary target tier",
    )
    summarize.add_argument("--output", help="optional output path")
    summarize.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    summarize.set_defaults(func=run_summarize)

    prepare_human_preflight = subparsers.add_parser(
        "prepare-human-preflight",
        help="render the compact human review digest for access, waterfall, and purpose coverage",
    )
    prepare_human_preflight.add_argument(
        "--provider", required=True, help="provider name"
    )
    prepare_human_preflight.add_argument("--domain", help="provider domain seed")
    prepare_human_preflight.add_argument("--doi-prefix", help="DOI prefix seed")
    prepare_human_preflight.add_argument("--output", help="optional output path")
    prepare_human_preflight.set_defaults(func=run_prepare_human_preflight)

    finalize_review = subparsers.add_parser(
        "finalize-review-artifact",
        help="write final batch Markdown semantic signoff after human confirmation",
    )
    finalize_review.add_argument("--provider", required=True, help="provider name")
    finalize_review.add_argument(
        "--confirmed-final-quality",
        action="store_true",
        help="required: operator confirmed current extracted.md quality summary",
    )
    finalize_review.add_argument(
        "--reviewed-by",
        help="operator name to record in onboarding/reviews/<provider>.yml",
    )
    finalize_review.set_defaults(func=run_finalize_review_artifact)

    next_task = subparsers.add_parser(
        "next",
        help="print and persist the next serial task for one provider",
    )
    next_task.add_argument("--provider", required=True, help="provider name")
    next_task.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    next_task.set_defaults(func=run_next)

    verify = subparsers.add_parser(
        "verify",
        help="write dry-run verification plan for a provider task",
    )
    verify.add_argument("--provider", required=True, help="provider name")
    verify.add_argument("--task", required=True, help="task id to verify")
    verify.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    verify.set_defaults(func=run_verify)

    run_checks = subparsers.add_parser(
        "run-checks",
        help="execute local verification commands for a provider task",
    )
    run_checks.add_argument("--provider", required=True, help="provider name")
    task_group = run_checks.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--task", help="single task id to execute")
    task_group.add_argument(
        "--all-local",
        action="store_true",
        help="run access, manifest, review, shared integration, and global lint gates",
    )
    run_checks.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    run_checks.set_defaults(func=run_run_checks)

    repair_markdown_quality = subparsers.add_parser(
        REPAIR_MARKDOWN_QUALITY_STEP,
        help="repair a failing markdown-quality.json report through the onboarding agent CLI",
    )
    repair_markdown_quality.add_argument(
        "--provider", required=True, help="provider name"
    )
    repair_markdown_quality.add_argument("--doi", required=True, help="DOI to repair")
    repair_markdown_quality.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    repair_markdown_quality.add_argument(
        "--output-dir",
        help="directory for repair briefs, prompts, and logs",
    )
    repair_markdown_quality.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_WORKER_RETRIES,
        help="maximum repair attempts; defaults to 3",
    )
    repair_markdown_quality.set_defaults(func=run_repair_markdown_quality)

    check_snapshot = subparsers.add_parser(
        "check-snapshot",
        help="check that a DOI fixture has an expected snapshot",
    )
    check_snapshot.add_argument("--provider", required=True, help="provider name")
    check_snapshot.add_argument("--doi", required=True, help="DOI to check")
    check_snapshot.set_defaults(func=run_check_snapshot)

    check_cleaning = subparsers.add_parser(
        "check-cleaning-proposal",
        help="check cleaning proposal fixture digest freshness",
    )
    check_cleaning.add_argument("--provider", required=True, help="provider name")
    check_cleaning.add_argument("--proposal", help="optional compact proposal path")
    check_cleaning.set_defaults(func=run_check_cleaning_proposal)

    advance = subparsers.add_parser(
        "advance",
        help="mark a task complete and persist the next serial task",
    )
    advance.add_argument("--provider", required=True, help="provider name")
    advance.add_argument("--task", required=True, help="task id to mark complete")
    advance.add_argument(
        "--state",
        default=DEFAULT_STATE_PATH,
        help="coordinator state JSON path",
    )
    advance.set_defaults(func=run_advance)

    return parser


def _provider_from_args(args: argparse.Namespace) -> str | None:
    provider = getattr(args, "provider", None)
    if isinstance(provider, str):
        try:
            return _provider_slug(provider)
        except ValueError:
            return provider
    return None


def _manifest_from_args(args: argparse.Namespace) -> str | None:
    manifest = getattr(args, "manifest", None)
    return manifest if isinstance(manifest, str) else None


def _task_id_from_args(args: argparse.Namespace) -> str:
    provider = _provider_from_args(args)
    command = getattr(args, "command", None) or "coordinator"
    task = getattr(args, "task", None)
    if provider and task:
        return f"{provider}-{command}-{task}"
    if provider:
        return f"{provider}-{command}"
    return str(command)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ToolError as exc:
        emit_error(
            error_payload(
                exc.code,
                exc.message,
                provider=exc.provider or _provider_from_args(args),
                manifest=exc.manifest or _manifest_from_args(args),
                task_id=exc.task_id or _task_id_from_args(args),
                retryable=exc.retryable,
                details=exc.details,
            )
        )
        return 1
    except ValueError as exc:
        emit_error(
            error_payload(
                "TASK_BRIEF_INVALID",
                str(exc),
                provider=_provider_from_args(args),
                manifest=_manifest_from_args(args),
                task_id=_task_id_from_args(args),
                retryable=False,
                details={"reason": str(exc)},
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
