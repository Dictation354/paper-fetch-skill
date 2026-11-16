import json
import tomllib
from paper_fetch.legacy_cleanup import cleanup


def test_custom_names_removed_and_unrelated_same_name_kept(tmp_path):
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    config = codex / "config.toml"
    config.write_text("""# retain comment
model = "keep"
[mcp_servers."custom.name"]
command = "python"
args = ["-m", "paper_fetch.mcp.server"]
[mcp_servers."custom.name".env]
TOKEN = "do-not-touch-other-services"
[mcp_servers.paper-fetch]
command = "unrelated"
""")
    claude = home / ".claude.json"
    claude.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "custom": {"command": "paper-fetch-mcp"},
                    "paper-fetch": {"command": "other"},
                },
                "projects": {
                    "p": {
                        "mcpServers": {
                            "nested": {
                                "command": "python",
                                "args": ["-m", "paper_fetch.mcp.server"],
                            }
                        }
                    }
                },
            }
        )
    )
    cleanup(home=home, codex_home=codex, antigravity_home=home / "agy")
    data = tomllib.loads(config.read_text())
    assert data["mcp_servers"] == {"paper-fetch": {"command": "unrelated"}}
    assert "# retain comment" in config.read_text() and data["model"] == "keep"
    assert json.loads(claude.read_text())["mcpServers"] == {
        "paper-fetch": {"command": "other"}
    }
    before = config.read_bytes()
    assert cleanup(home=home, codex_home=codex, antigravity_home=home / "agy") == []
    assert config.read_bytes() == before


def test_owned_wrappers_removed_user_files_retained(tmp_path):
    install = tmp_path / "install"
    directory = install / "bin"
    directory.mkdir(parents=True)
    old = directory / "paper-fetch-mcp"
    old.write_text("exec python -m paper_fetch.mcp.server\n")
    unrelated = directory / "paper-fetch-mcp.cmd"
    unrelated.write_text("unrelated user command")
    paper = install / "paper.md"
    paper.write_text("paper")
    cleanup(
        home=tmp_path / "home",
        install_root=install,
        codex_home=tmp_path / "codex",
        antigravity_home=tmp_path / "agy",
    )
    assert not old.exists() and unrelated.is_file() and paper.is_file()


def test_managed_custom_registration_is_owned_even_with_generic_wrapper(tmp_path):
    config = tmp_path / "codex/config.toml"
    config.parent.mkdir()
    config.write_text("""# BEGIN paper-fetch installer managed
[mcp_servers.custom]
command = "/old/managed/wrapper"
# END paper-fetch installer managed
[mcp_servers.keep]
command = "other"
""")
    cleanup(
        home=tmp_path / "home",
        codex_home=config.parent,
        antigravity_home=tmp_path / "agy",
    )
    assert tomllib.loads(config.read_text())["mcp_servers"] == {
        "keep": {"command": "other"}
    }
