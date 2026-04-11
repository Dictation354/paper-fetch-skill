# Paper Fetch Skill

`paper-fetch-skill` 用来把一篇已知论文（DOI、URL 或标题）抓取成 AI 更容易消费的正文和元数据。它既可以单独作为命令行工具使用，也可以通过 MCP + skill 接入 Codex、Claude Code 等 agent。

## 这个项目提供什么

- `paper-fetch`: 在终端里按 DOI、URL 或标题抓取论文
- `paper-fetch-mcp`: 给 agent runtime 使用的 stdio MCP server
- `scripts/install-codex-skill.sh`: 把 skill 安装到 Codex，并可顺手注册 MCP
- `scripts/install-claude-skill.sh`: 把 skill 安装到 Claude Code，并可顺手注册 MCP

## 快速开始

如果你只想先在当前环境里试用：

```bash
python3 -m pip install .
paper-fetch --query "10.1186/1471-2105-11-421"
```

如果需要出版社 API key 或自定义配置，默认配置文件放在 `~/.config/paper-fetch/.env`：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

变量说明见 [docs/providers.md](docs/providers.md)。

## 如何部署

### 部署到 Codex

```bash
python3 -m pip install .
./scripts/install-codex-skill.sh --register-mcp
```

### 部署到 Claude Code

```bash
python3 -m pip install .
./scripts/install-claude-skill.sh --register-mcp
```

## 如何更新

进入你原来安装用的那个 Python 环境后，重新安装当前仓库即可：

```bash
python3 -m pip install .
```

如果你还在用 Codex 或 Claude Code，推荐顺手再跑一次对应安装脚本，让 skill 和 MCP 一起更新：

```bash
./scripts/install-codex-skill.sh --register-mcp
./scripts/install-claude-skill.sh --register-mcp
```

### 可选：安装公式后端

如果你希望公式转换效果更好，可以额外安装公式后端：

```bash
paper-fetch-install-formula-tools
```

如果你是在当前仓库里做 repo-local 开发，而不是给已安装环境补依赖，才使用：

```bash
./install-formula-tools.sh
```

不安装公式后端也能使用主抓取链路，只是公式渲染会退回到较弱的内置路径。

## 文档

- [docs/deployment.md](docs/deployment.md): 安装、MCP 注册、公式后端和验证步骤
- [docs/providers.md](docs/providers.md): 环境变量、provider 配置和 API key 说明
- [docs/architecture/target-architecture.md](docs/architecture/target-architecture.md): 项目结构和架构说明
