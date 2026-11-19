from paper_fetch import cli


def test_presets_fill_only_omitted_cli_options():
    for preset in ("temporary_read", "cacheable_read", "archive"):
        raw = ["fetch", "--query", "paper", "--preset", preset]
        command = cli.parse_cli_command(raw)
        assert isinstance(command, cli.SingleFetchCommand)
        options = command.options
        assert options.asset_profile == "none" and options.artifact_mode == "none"
        assert options.max_tokens == "full_text" and options.include_refs == "all"
        assert options.prefer_cache == (preset != "temporary_read")
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
    command = cli.parse_cli_command(raw)
    assert isinstance(command, cli.SingleFetchCommand)
    options = command.options
    assert (options.asset_profile, options.artifact_mode, options.max_tokens) == (
        "body",
        "all",
        42,
    )


def test_supplementary_presets_default_to_downloads_and_preserve_explicit_options():
    for preset in ("temporary_read", "cacheable_read", "archive"):
        for flags, expected in [
            ([], ("all", "markdown-assets")),
            (["--asset-profile=none"], ("none", "markdown-assets")),
            (["--artifact-mode=none"], ("all", "none")),
            (["--asset-profile=body", "--artifact-mode=all"], ("body", "all")),
        ]:
            raw = [
                "fetch",
                "--query=x",
                "--target=supplementary",
                "--preset",
                preset,
                *flags,
            ]
            command = cli.parse_cli_command(raw)
            assert isinstance(command, cli.SingleFetchCommand)
            options = command.options
            assert (options.asset_profile, options.artifact_mode) == expected
            assert options.prefer_cache == (preset != "temporary_read")
