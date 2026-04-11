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

补充说明：

- 运行时依赖现在都显式声明在 `pyproject.toml` 里，安装不再依赖上游包“顺带带进来”的传递依赖
- HTTP 传输层默认带 `32 MiB` 响应上限，以及针对 `5xx` / timeout 的短重试；更详细的行为见 [docs/providers.md](docs/providers.md)
- provider 路由现在采用 `domain / Crossref publisher` 优先、`DOI prefix` 兜底的策略；像 `10.1006/jaer.1996.0085` 这类 Elsevier DOI 现在也能更稳定地命中官方链路

## 默认输出策略

当前默认值统一如下：

- `asset_profile="none"`
  - 不下载 figure / table-image / supplementary 到本地
  - Markdown 仍保留 figure captions
  - 不保留远程图片 URL，也不输出 supplementary 链接
- `max_tokens="full_text"`
  - 默认尽量输出完整 abstract + 正文文字
  - references 默认全量输出
  - 如果 `asset_profile` 允许展示本地资产，也会一并完整展示
- 只有显式传数值 `max_tokens` 时，才进入硬上限裁剪模式
  - 裁剪优先级为：正文文字 > 当前 profile 对应非文字内容 > references

可选资产层级：

- `none`: 适合泛读 / 搜索 / 大规模文献调研
- `body`: 下载并渲染正文 figure + 正文表格原图
- `all`: 下载并渲染 provider 已识别的全部相关资产，包括 supplementary

## Provider 路由说明

- `resolve_paper().provider_hint` 现在表示“基于落地 URL domain、Crossref publisher、Crossref landing page 综合得出的最佳 hint”，不再等同于 DOI 前缀猜测
- provider 候选优先级固定为：`domain > publisher > DOI fallback`
- `preferred_providers` 仍严格限制最终允许使用的 official/fulltext/html 路径
- 即使 `preferred_providers` 没有包含 `crossref`，运行时仍可能内部调用 Crossref 只做 routing signal；这不会让最终结果自动变成 Crossref 来源

## CLI 常用法

默认抓取：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
```

抓正文图和正文表格原图：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile body
```

抓全部资产：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile all
```

在 token 紧张时改成数值上限：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --asset-profile body --max-tokens 12000
```

如果只想拿全文文字，不想落任何文件：

```bash
paper-fetch --query "10.1016/j.rse.2025.114648" --no-download
```

注意：

- `--no-download` 优先级高于 `--asset-profile`
- `--include-refs` 现在默认不需要传
  - `max_tokens=full_text` 时默认等价于全量 refs
  - 显式传数值 `--max-tokens` 时默认等价于 `top10`

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

## Repo-local 验收

如果你是在仓库源码目录里直接跑测试，推荐显式带上 `PYTHONPATH=src`，这样会优先导入当前工作树，而不是环境里可能已经安装过的旧版 `paper_fetch`：

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_paper_fetch tests.unit.test_fetch_common tests.unit.test_publisher_identity tests.unit.test_resolve_query
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

## 文档

- [docs/deployment.md](docs/deployment.md): 安装、MCP 注册、公式后端和验证步骤
- [docs/providers.md](docs/providers.md): 环境变量、provider 配置和 API key 说明
- [docs/architecture/target-architecture.md](docs/architecture/target-architecture.md): 项目结构和架构说明
