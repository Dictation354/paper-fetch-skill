# Deployment Guide

这份文档面向“把 `paper-fetch-skill` 部署到一个可用环境里”的场景，重点说明安装顺序、MCP 接入方式和可选依赖。

## 1. 安装 Python 包

先把包安装到目标环境：

```bash
python3 -m pip install .
```

安装完成后，当前环境会提供这些命令：

- `paper-fetch`
- `paper-fetch-mcp`
- `paper-fetch-install-formula-tools`

补充说明：

- runtime 依赖都在 `pyproject.toml` 里显式声明；安装后不需要再额外手动补 `pydantic`

## 2. 准备配置

默认主配置文件是 `~/.config/paper-fetch/.env`。如果你需要出版社 API key、`mailto` 或自定义下载目录，可以这样准备：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

详细变量说明见 [providers.md](providers.md)。

补充说明：

- 运行时默认读取 `~/.config/paper-fetch/.env`
- 仓库内的 `.env` 不会自动生效；如果你要在开发场景下使用它，请显式设置 `PAPER_FETCH_ENV_FILE=/path/to/.env`
- 安装脚本也不会自动绑定仓库 `.env`；如果你希望 MCP 使用某个特定配置文件，请显式传 `--env-file /path/to/.env`

## 3. 可选：安装公式后端

主抓取链路不依赖外部公式后端；不安装也能工作。只有当你希望 `texmath` / `mathml-to-latex` 真正在部署后的环境里可用时，才需要这一步。

推荐分两种场景理解：

- 已经 `pip install .`，或者要在另一台机器上部署：

  ```bash
  paper-fetch-install-formula-tools
  ```

- 只是在当前仓库里做 repo-local 开发：

  ```bash
  ./install-formula-tools.sh
  ```

区别是：

- `paper-fetch-install-formula-tools` 会把工具装到用户数据目录，适合安装后环境复用
- `install-formula-tools.sh` 会把工具装到当前仓库的 `./.formula-tools/`，更适合本仓库开发

## 4. 部署到 Codex

最常用的部署方式是：

```bash
python3 -m pip install .
./scripts/install-codex-skill.sh --register-mcp
```

这个脚本会做三件事：

- 在当前 `python3` 环境里执行 `pip install .`
- 把静态 skill 安装到用户级或项目级 Codex skill 目录
- 如果带了 `--register-mcp`，调用 Codex CLI 注册 `paper-fetch` 这个 stdio MCP server

常用选项：

- `--project`: 安装到当前仓库的 `.codex/skills/`
- `--env-file <path>`: 显式指定 MCP 启动时读取的环境文件
- `--mcp-name <name>`: 修改默认 MCP server 名称 `paper-fetch`

完成后重启 Codex，让它重新扫描 skill 和 MCP。

## 5. 部署到 Claude Code

最常用的部署方式是：

```bash
python3 -m pip install .
./scripts/install-claude-skill.sh --register-mcp
```

这个脚本同样会安装包、复制静态 skill，并在显式传入 `--register-mcp` 时注册 MCP。

常用选项：

- `--project`: 安装到当前仓库的 `.claude/skills/`
- `--env-file <path>`: 显式指定 MCP 启动时读取的环境文件
- `--mcp-scope local|user|project`: 指定 Claude MCP 配置作用域
- `--mcp-name <name>`: 修改默认 MCP server 名称 `paper-fetch`

完成后重启 Claude Code，让它重新扫描 skill 和 MCP。

## 6. 手动接入 MCP

如果你不想使用安装脚本，也可以手动注册一个 stdio MCP server，启动命令指向下面任一入口：

```bash
paper-fetch-mcp
```

或：

```bash
python3 -m paper_fetch.mcp.server
```

如果配置文件不在进程环境里，可以额外设置：

```bash
PAPER_FETCH_ENV_FILE=/path/to/.env
```

当前 MCP 入口是 stdio server，适合挂到 Codex、Claude Code 或其他支持 stdio MCP 的 agent runtime。

## 7. 验证是否部署成功

可以先做一个最小 smoke test：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

如果你还想验证仓库自带的离线测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/integration -q
```

如果你是在仓库源码目录里做 repo-local 验证，而不是验证已安装环境，推荐所有 `unittest` 命令都显式带上 `PYTHONPATH=src`，避免误导入环境里旧的已安装包。

部署到 agent 之后，推荐再实际调用一次：

- `resolve_paper(query)`
- `fetch_paper(query, modes, strategy, include_refs, max_tokens)`

`fetch_paper` 的当前 MCP 默认值是：

- `modes=["article", "markdown"]`
- `strategy.allow_html_fallback=true`
- `strategy.allow_metadata_only_fallback=true`
- `strategy.asset_profile="none"`
- `max_tokens="full_text"`
- `include_refs=null`

也就是默认更偏向“先把全文文字完整拿回来，但不额外下载图片/补充材料”。如果你希望精读某篇论文，可以在 MCP 请求里显式传：

- `strategy.asset_profile="body"`: 下载并渲染正文 figure + 正文表格原图
- `strategy.asset_profile="all"`: 下载并渲染全部识别资产
- `max_tokens=<整数>`: 改成 token 紧张场景下的硬上限模式

## 相关文档

- [providers.md](providers.md)
- [architecture/target-architecture.md](architecture/target-architecture.md)
