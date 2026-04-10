# Paper Fetch Skill 文档

## 当前定位

这个项目现在只维护一个 **AI-friendly `paper-fetch` skill**：

- 输入可以是 `DOI`
- 也可以是论文 `URL`
- 也可以是 `题名 / 关键词`

主入口会尽量返回一份紧凑、适合直接塞进 agent context 的 Markdown 正文；如果只能拿到元数据，也会返回 metadata-only 的结构化结果，而不是静默失败。

## 主入口

推荐优先使用：

```bash
python scripts/paper_fetch.py --query "<DOI | URL | 题名>"
```

默认行为：

- 默认 `stdout` 输出 AI-friendly Markdown
- 默认不落盘，不产生临时文件；但 Wiley 若官方 TDM 返回 PDF / binary，默认会落到 `live-downloads/`
- 加上 `--save-markdown` 可在任何 provider 成功取到全文时，把渲染后的 AI Markdown 另存一份到 `--output-dir`（默认 `live-downloads/`），stdout / `--output` 的返回照常，等于"agent 读到正文 + 硬盘留档"。注意 Wiley 的 Markdown 是从 PDF 文本抽取出来的，保真度通常不如 Elsevier / Springer 的 XML 链路，复杂公式和表格尤其明显。
- 题名或 URL 解析歧义时，非零退出并在 `stderr` 输出候选 JSON
- 优先官方 API / XML；Wiley PDF 会优先尝试内存提取正文；官方路径不够用时再走 HTML fallback，最后退到 Crossref metadata-only

常用参数：

- `--format markdown|json|both`
- `--output -|<path>`
- `--output-dir <dir>`
- `--no-download`
- `--save-markdown`
- `--include-refs none|top10|all`
- `--max-tokens 8000`
- `--no-html-fallback`

### 输出合同

- `--format markdown`: `stdout` 直接输出 Markdown
- `--format json`: `stdout` 输出 `ArticleModel` JSON
- `--format both`: `stdout` 输出 `{"article": ..., "markdown": ...}`
- `ArticleModel.quality` 里会包含 `warnings` 和结构化 `source_trail`
- 出错时：`stderr` 始终输出 JSON，格式为 `{"status":"error|ambiguous","reason":"...","candidates":[...]}`

## 处理流程

`scripts/paper_fetch.py` 的主链路是：

1. `scripts/resolve_query.py` 统一解析输入
2. 有 DOI 时优先尝试官方 metadata
3. 优先尝试官方全文 raw payload
4. Elsevier / Springer XML 直接转成统一 `ArticleModel`
5. Wiley 如果官方 TDM 返回 PDF / binary，会先尝试用 PyMuPDF 从内存提取正文；是否落盘由 `--no-download` 控制
6. Wiley PDF 提取失败，或其他 provider 官方路径失败时，尝试 `scripts/providers/html_generic.py`
7. HTML 也不够好时，退到 Crossref metadata-only

## 当前支持

官方优先 provider：

- `Elsevier`
- `Springer`
- `Wiley`

统一 metadata / fallback：

- `Crossref`

HTML fallback：

- 使用 `trafilatura` 提取正文
- 使用 `citation_*` / `dc.*` meta 提取 DOI、标题、作者、期刊、日期
- 过滤 cookie、sign in、subscribe、navigation 类噪音
- 对 CJK-heavy 正文和带 DOI 的 short communication / editorial 使用自适应正文阈值，不再硬卡单一 800 字符门槛

Wiley 特殊行为：

- Wiley 官方 metadata endpoint 当前未实现，元数据仍走 Crossref
- Wiley 官方 TDM 当前仍以 PDF / binary 为主
- `paper_fetch.py` 会优先尝试从 Wiley PDF 中直接提取正文给 agent 使用
- `--no-download` 只关闭落盘副作用，不会关闭 PDF 正文提取
- 未显式指定 `--output-dir` 且未开启 `--no-download` 时，Wiley PDF 默认保存到 repo 根目录下的 `live-downloads/`

### 并行调用建议

- 同一篇论文不要在同一会话里高并发重复抓取。
- 更稳的做法是先抓一次，再复用返回的 Markdown / JSON。
- 如果你自己在外面包线程池或 worker 池，不要共享同一个 `HttpTransport` 实例；它的进程内缓存不是线程安全的。

## 作为 Claude Code Skill 一键安装

推荐方式：把本项目装成 Claude Code 的 skill，之后在任何目录里和 Claude Code 对话都能直接用"读这篇论文"这类指令触发。

### 三步上手

```bash
git clone <this-repo-url> ~/tools/paper-fetch-skill
cd ~/tools/paper-fetch-skill
./install.sh
```

默认会做这些事：

1. 检查 `python3`（必需）
2. 在 `./.venv/` 下创建独立虚拟环境并 `pip install -r requirements.txt`
3. 优先尝试用 `cabal` 或 `stack` 编译安装 `texmath`
4. 如果 `texmath` 不可用，则回退到 `mathml-to-latex`；这一步需要 Node
5. 若没有 `.env`，从 `.env.example` 复制一份模板，让你去填 API key
6. 在 `~/.claude/skills/paper-fetch-skill/SKILL.md` 写入一份使用**绝对路径**的 skill 描述，指向本 repo 的 venv Python 与 `scripts/paper_fetch.py`
7. 检查 `~/.claude/settings.json` 是否可能屏蔽了该 skill，并给出提醒

装好后编辑 `~/tools/paper-fetch-skill/.env`，至少填：

- `CROSSREF_MAILTO`
- 你实际拥有的出版商 key（Springer / Elsevier / Wiley 等）

然后重启 Claude Code，skill 就会自动被发现。

### 安装选项

| 命令 | 作用 |
|---|---|
| `./install.sh` | 用户级安装，写入 `~/.claude/skills/…`（默认） |
| `./install.sh --project` | 项目级安装，只写入当前 repo 的 `.claude/skills/…` |
| `./install.sh --no-node` | 跳过 `mathml-to-latex` 的 Node fallback；仍会先尝试安装 `texmath` |
| `./install.sh --uninstall` | 删除已安装的 skill 条目（不动代码和 venv） |

### 升级

直接在 repo 目录下 `git pull` 即可。由于 skill 文件写的是绝对路径指回本 repo 的代码与 venv，拉新代码后通常无需重装。只有当 `requirements.txt` 或 `package.json` 发生变化时，再跑一次 `./install.sh` 让依赖同步即可。

如果这个 repo 被移动到新路径，请重新运行 `./install.sh`，否则 `~/.claude/skills/.../SKILL.md` 里的绝对路径会继续指向旧位置。

### 卸载

```bash
./install.sh --uninstall     # 移除 ~/.claude/skills/paper-fetch-skill
rm -rf ~/tools/paper-fetch-skill   # 如需连代码一起删
```

## 作为 Codex Skill 一键安装

如果你主要在 Codex 里使用这个项目，推荐安装 Codex 版 skill。安装完成后，Codex 会从 `~/.codex/skills/` 自动发现这个 skill。

### 三步上手

```bash
git clone <this-repo-url> ~/tools/paper-fetch-skill
cd ~/tools/paper-fetch-skill
./install-codex.sh
```

默认会做这些事：

1. 检查 `python3`（必需）
2. 在 `./.venv/` 下创建独立虚拟环境并 `pip install -r requirements.txt`
3. 优先尝试用 `cabal` 或 `stack` 编译安装 `texmath`
4. 如果 `texmath` 不可用，则回退到 `mathml-to-latex`；这一步需要 Node
5. 若没有 `.env`，从 `.env.example` 复制一份模板，让你去填 API key
6. 在 `~/.codex/skills/paper-fetch-skill/` 写入 `SKILL.md` 和 `agents/openai.yaml`，并使用绝对路径指向本 repo 的 venv Python 与 `scripts/paper_fetch.py`

装好后编辑 `~/tools/paper-fetch-skill/.env`，至少填：

- `CROSSREF_MAILTO`
- 你实际拥有的出版商 key（Springer / Elsevier / Wiley 等）

然后重启 Codex，skill 就会自动被发现。

### 安装选项

| 命令 | 作用 |
|---|---|
| `./install-codex.sh` | 用户级安装，写入 `~/.codex/skills/…`（默认） |
| `./install-codex.sh --project` | 项目级安装，只写入当前 repo 的 `.codex/skills/…` |
| `./install-codex.sh --no-node` | 跳过 `mathml-to-latex` 的 Node fallback；仍会先尝试安装 `texmath` |
| `./install-codex.sh --uninstall` | 删除已安装的 skill 条目（不动代码和 venv） |

补充说明：

- 如果设置了 `CODEX_HOME`，脚本会改写到 `$CODEX_HOME/skills/…`
- `--project` 主要用于在仓库里生成一份本地 skill 副本；Codex 通常仍优先从用户级 `~/.codex/skills/` 自动发现

### 升级

直接在 repo 目录下 `git pull` 即可。由于 skill 文件写的是绝对路径指回本 repo 的代码与 venv，拉新代码后通常无需重装。只有当 `requirements.txt` 或 `package.json` 发生变化时，再跑一次 `./install-codex.sh` 让依赖同步即可。

如果这个 repo 被移动到新路径，请重新运行 `./install-codex.sh`，否则 `~/.codex/skills/.../SKILL.md` 里的绝对路径会继续指向旧位置。

### 卸载

```bash
./install-codex.sh --uninstall     # 移除 ~/.codex/skills/paper-fetch-skill
rm -rf ~/tools/paper-fetch-skill   # 如需连代码一起删
```

---

## 本地验证（直接跑脚本）

如果你只是想在本地直接验证 skill 主入口，也可以手动装依赖后运行脚本：

```bash
python -m pip install -r requirements.txt
```

公式转换默认策略：

- 优先使用 `texmath`
- `texmath` 不可用时自动回退到 `mathml-to-latex`
- 两者都不可用时，退回内置 Python MathML 渲染器

项目通过根目录 `.env` 读取配置。建议至少配置：

- `PAPER_FETCH_SKILL_USER_AGENT`
- `CROSSREF_MAILTO`
- 对应出版商所需的 API key / token

详细变量说明见 [docs/providers.md](docs/providers.md)。

## Live Smoke Tests

仓库内新增了一个 opt-in 的真实出版商 smoke test：

```bash
python -m unittest discover -s tests -q
PAPER_FETCH_RUN_LIVE=1 python -m unittest tests.test_live_publishers -q
```

- 默认的 `python -m unittest discover -s tests -q` 仍然只跑离线测试；`tests/test_live_publishers.py` 会自动跳过。
- 只有在显式设置 `PAPER_FETCH_RUN_LIVE=1`，并且本地 `.env` 里填了对应 publisher 的 key / token 时，才会真正发起线上请求。
- 当前 live smoke 样本按 `2026-04-10` 实测通过：
  - Elsevier DOI `10.1016/j.rse.2025.114648`
  - Springer DOI `10.1186/1471-2105-11-421`
  - Wiley DOI `10.1002/ece3.9361`
  - Elsevier URL `https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525`
  - 短正文 HTML fallback `https://www.nature.com/articles/sj.bdj.2017.900`
- 其中 Springer 用当前仓库已配置的 `Meta API + Open Access API` 组合作为官方全文验收，不要求 `SPRINGER_FULLTEXT_API_KEY`。

## Legacy / 兼容工作流去向

本仓库现在只保留 skill 相关能力。

如果你还需要以下旧工作流：

- `metadata + fulltext + 本地落盘`
- 显式路由调试
- 对已下载 XML 批量重建 Markdown

请改用独立目录：

```bash
~/publisher-api-router
```

对应入口已经迁到那个独立项目：

- `~/publisher-api-router/scripts/fetch_article.py`
- `~/publisher-api-router/scripts/route_lookup.py`
- `~/publisher-api-router/scripts/regenerate_live_markdown.py`

## 主要模块

- `scripts/paper_fetch.py`: AI-friendly 主入口
- `scripts/resolve_query.py`: DOI / URL / 题名统一解析
- `scripts/article_model.py`: 统一内部模型与 AI Markdown / JSON 序列化
- `scripts/providers/html_generic.py`: HTML fallback provider
- `scripts/providers/crossref.py`: Crossref metadata 与题名候选
- `scripts/providers/elsevier.py`: Elsevier metadata / raw fulltext / XML 适配
- `scripts/providers/springer.py`: Springer metadata / raw fulltext / XML 适配
- `scripts/providers/wiley.py`: Wiley raw fulltext、PDF 提取与 PDF-aware fallback
- `scripts/article_markdown.py`: XML 结构解析与 provider Markdown 渲染
- `scripts/publisher_identity.py`: DOI 归一化与 provider 推断
- `scripts/provider_clients.py`: provider client registry

## 测试

当前推荐的回归命令：

```bash
python -m unittest \
  tests.test_elsevier_markdown \
  tests.test_springer_markdown \
  tests.test_formula_conversion \
  tests.test_publisher_identity \
  tests.test_resolve_query \
  tests.test_html_generic \
  tests.test_paper_fetch
```

## 已知边界

- Wiley 官方 TDM 在当前流程里仍以 PDF / binary 为主；运行时会尝试 PDF 文本抽取，但保真度通常不如 XML
- HTML fallback 更偏“读正文给 agent”，不是高保真网页归档
- 复杂表格、公式和少数 publisher-specific 结构，仍以 XML 专用链路为最佳
- 需要 legacy 落盘 / 路由调试 / Markdown 重建时，请切到 `~/publisher-api-router`
