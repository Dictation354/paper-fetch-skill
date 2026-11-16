from paper_fetch import cli


def test_presets_fill_only_omitted_cli_options():
    parser = cli.build_parser()
    for preset in ("temporary_read", "cacheable_read", "archive"):
        raw = ["fetch", "--query", "paper", "--preset", preset]
        args = parser.parse_args(raw)
        cli._apply_cli_preset(args, raw)
        assert args.asset_profile == "none" and args.artifact_mode == "none"
        assert args.max_tokens == "full_text" and args.include_refs == "all"
        assert args.prefer_cache == (preset != "temporary_read")
    raw = [
        "fetch",
        "--query",
        "paper",
        "--asset-profile",
        "body",
        "--artifact-mode",
        "all",
        "--max-tokens",
        "42",
    ]
    args = parser.parse_args(raw)
    cli._apply_cli_preset(args, raw)
    assert (args.asset_profile, args.artifact_mode, args.max_tokens) == (
        "body",
        "all",
        42,
    )
