# Paper Fetch Skill

> Fetch papers as agent-ready markdown — DOI/URL/title in, structured full text out. CLI · MCP · Skill.

**Paper Fetch Skill** —— 已知论文的 AI 阅读层。
你输入 DOI、URL 或标题，它返回结构化元数据 + 干净 Markdown 全文 + 图表资源，直接喂给 Codex / Claude Code / 任意 MCP host。
不绕付费墙，只在你本就有访问权限的地方，把 AI 从「只能读摘要」升级到「读全文」。

如果觉得有帮助，欢迎 star⭐ 支持！

## 🙁 AI agent 读论文的痛点

1. 你有权限获取全文，但 AI 没有权限，AI 只能搜到摘要。
2. PDF 无法正确解析文字、图片，agent 理解效果不如 markdown。
3. 文章 html 有很多无关的网页信息，给 agent 造成语义负担和 token 消耗。
4. 文章 html 中的图片 agent 读不到。

## 😍 这个项目做什么

✅这个项目把这些问题收敛到一个工具层：
1. 当你有全文获取权限时，让 AI 也能获取全文，而不仅是摘要。
2. 输入已知论文的 DOI、URL 或标题，抓取 AI 更容易理解的 markdown 版本，为后续知识库构建做好干净的数据基础。

✅项目提供三个主要入口：

1. `paper-fetch`：命令行工具，适合手动大规模快速抓取文献。
2. `paper-fetch-mcp`：stdio MCP server，适合接入 Codex、Claude Code 等支持 MCP 的 host。
3. `skills/paper-fetch-skill/`：静态 agent skill，告诉 agent 什么时候应该调用论文抓取工具。

核心能力：

- 支持 DOI、URL 和标题查询。
- 输出结构化论文元数据、正文 Markdown、引用信息和本地缓存资源。
- 支持 18 个出版社/平台全文 provider，包括 arXiv、Elsevier、Springer、Wiley、Science、PNAS、IEEE、Copernicus、AMS、MDPI、Royal Society Publishing、Annual Reviews、PLOS、Frontiers、Oxford Academic、ACS、IOP 和 AIP。
- 在无法取得全文时返回带警告的仅摘要或仅元数据结果。

项目边界：

- 不替代主题检索、文献推荐或综述生成；开放式搜索可先形成候选，当后续需要阅读、总结、比较、核验可读性或获取全文时，再把 DOI、URL、标题、arXiv ID 或引用条目交给 paper-fetch 抓取和核验候选论文全文。
- 不绕过付费墙或访问授权；可用性取决于 provider、凭据和本机运行环境。
- Wiley、Science、PNAS、Annual Reviews、Royal Society Publishing、ACS、IOP、AIP、MDPI 的浏览器路径统一使用 CDP browser workflow；未配置外部 endpoint 时由 cloakbrowser 启动受控 Chrome。AMS 使用 direct HTTP HTML/PDF 路径，不参与 browser runtime / auth / preflight。
- 用户可以自行 fork 后添加新出版社，见 [`onboarding/README.md`](onboarding/README.md)，但是需要人工审核确定全文获取、markdown 转换质量等能力。

## 效果展示

agent 安装 skill 后，可以识别 `paper-fetch-skill` 的适用边界，并在抓取前确认是否保存全文和图表资源。

![agent 识别 paper-fetch-skill 能力范围](figures/agent-skill-overview.png)

以下示例来自 `figures/` 中的真实开放抓取产物。

### Nature 示例

- 论文：Towards end-to-end automation of AI research
- DOI：`10.1038/s41586-026-10265-5`
- 来源：Springer/Nature HTML full text
- 许可：[`CC BY 4.0`](https://creativecommons.org/licenses/by/4.0)
- Markdown 全文：[`towards-end-to-end-automation-of-ai-research.md`](figures/towards-end-to-end-automation-of-ai-research.md)

![Nature 论文抓取结果](figures/nature-oa-fetch-result.png)

### Science Advances 示例

- 论文：Deforestation-induced runoff changes dominated by forest-climate feedbacks
- DOI：`10.1126/sciadv.adp3964`
- 来源：Science Advances / Science provider
- Markdown 全文：[`deforestation-induced-runoff-changes-dominated-by-forest-climate-feedbacks.md`](figures/deforestation-induced-runoff-changes-dominated-by-forest-climate-feedbacks.md)

![Science Advances 论文抓取结果](figures/science-fetch-result.png)

## 快速安装

### 离线安装（推荐）

离线 release asset 包含 4 个 Linux ABI 自解压 `.sh` 安装器、4 个 macOS ABI tarball 和 1 个 Windows x86_64 安装器。macOS tarball 使用同一构建脚本在 `macos-latest` 上按 runner 架构和 CPython 3.11、3.12、3.13、3.14 生成，并由 macOS CI 验证安装、headful preset 和 CloakBrowser 浏览器启动 smoke。

```text
paper-fetch-skill-offline-linux-x86_64-cp311.sh
paper-fetch-skill-offline-linux-x86_64-cp312.sh
paper-fetch-skill-offline-linux-x86_64-cp313.sh
paper-fetch-skill-offline-linux-x86_64-cp314.sh
paper-fetch-skill-offline-macos-<arch>-cp311.tar.gz
paper-fetch-skill-offline-macos-<arch>-cp312.tar.gz
paper-fetch-skill-offline-macos-<arch>-cp313.tar.gz
paper-fetch-skill-offline-macos-<arch>-cp314.tar.gz
paper-fetch-skill-windows-x86_64-setup.exe
```

#### **I. Windows x86_64：**

**1. 下载安装包**

在 Releases 中下载 
```text
paper-fetch-skill-windows-x86_64-setup.exe
```

**2. 双击安装或者在本地终端运行安装程序**
```powershell
.\paper-fetch-skill-windows-x86_64-setup.exe
```

安装器默认安装到 `%LOCALAPPDATA%\PaperFetchSkill`，不要求管理员权限。会自动安装 paper-fetch CLI 工具、注册 MCP 并安装 Skill。若用户级 PATH / Skill / MCP 集成或 smoke check 在本机失败，runtime 仍会保留在安装目录，详细警告见 `%LOCALAPPDATA%\PaperFetchSkill\install-helper.log`。

**3. 验证安装**

安装后新开一个 PowerShell 

```powershell
paper-fetch --help
```
如果有输出`usage: cli.py [-h] -`（后略）则安装成功

**4. 开启 Wiley / Science / PNAS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 浏览器路径**

Browser workflow 会优先连接 `CLOAKBROWSER_CDP_ENDPOINT` 指向的现有 Chrome/CloakBrowser；未配置时，paper-fetch 会用 `cloakbrowser.ensure_binary()` 首次下载/定位 Chrome，并自动启动带 CDP 端口的受控浏览器。后续 Wiley / Science / PNAS / Annual Reviews / Royal Society Publishing / ACS / IOP / AIP / MDPI 的 HTML 抓取、browser-backed 资产下载和 seeded PDF/ePDF fallback 都使用该 CDP 浏览器路径。默认 managed 模式在同一进程内复用一个按 provider/browser 配置 keyed 的 browser manager，批量并发任务不会各自启动 Chrome 抢同一个 provider profile lock；每个 HTML/PDF/资产 context 会在调用线程建立自己的 CDP 连接，避免跨线程复用 Playwright sync 对象。外部 CDP 模式默认借用现有 browser context，并在 diagnostics 中报告被忽略的 context option；设置 `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1` 可在外部浏览器中新建 context。browser-backed 资产下载在安全的 caller-thread 路径内会复用同一 attempt 的 page/context，遇到 Playwright 线程所有权异常会自动降级；普通 HTTP 资产下载仍按配置并发。AMS 主路径是 direct HTTP HTML，不需要 browser runtime、`browser-preflight` 或 `auth ams`。

`CLOAKBROWSER_BINARY_PATH` 可指向预装 Chrome 以跳过下载；`CLOAKBROWSER_HEADLESS` 控制自动启动的 headed/headless，默认 managed headless 会确保传入 Chrome 原生 `--headless=new` 参数，避免依赖参数缺失时弹出浏览器窗口；未显式指定目录时，自动浏览器默认按 publisher 使用 `publisher-browser-profiles/<provider>/storage-state.json` 复用过滤后的 storage-state，以减少 Science/Wiley 等站点的冷启动 challenge。auth、preflight、HTML fetch 和 seeded PDF fallback 共享同一 storage-state 路径解析，保存时会加锁并原子替换。`CLOAKBROWSER_PROFILE_DIR` / `CLOAKBROWSER_USER_DATA_DIR` 只覆盖 managed Chrome 启动目录和 storage-state 保存位置，不承诺完整复用 IndexedDB、service worker 或扩展等浏览器 profile 状态。批量抓取前可运行 `paper-fetch browser-preflight` 串行使用各 browser-backed provider 的内置样例 DOI/URL 和正常 HTML candidate/bootstrap 语义预热 storage-state；失败时按提示运行 `paper-fetch auth <provider> [--url ...]` 打开同一 provider 的 headed browser 手动登录/验证，按 Enter 后保存本地 storage-state。未配置持久状态不阻止正常抓取。
Windows 安装器还会设置 `MATHML_TO_LATEX_NODE_BIN` 指向包内 Playwright Node，避免 Codex Desktop 的 WindowsApps/MSIX 内部 `node.exe` 被公式转换 fallback 误用；同时设置 `PAPER_FETCH_IMAGE_TOOLS_DIR` 指向安装目录内 `image-tools`。Ghostscript/libvips 存在时 AMS `Download Figure` 的 EPS/TIFF 源图会转为 PNG，缺失时回退网页 JPG/PNG。

**5. 开启 Elsevier 获取权限**

Elsevier 官方 XML/API 和 PDF fallback 需要从 <https://dev.elsevier.com/> 申请 key，并写入安装目录下的 `offline.env`：

```powershell
notepad "$env:LOCALAPPDATA\PaperFetchSkill\offline.env"
```

**6. 刷新 agent skill**

修改 Codex / Claude Code skill、MCP 配置或 `offline.env` 后需要重启对应 host；已经启动的 MCP 服务不会自动继承新环境变量。

**7. 常见问题**

Windows 安装器和离线安装细节见 [`docs/deployment.md`](docs/deployment.md)。


#### **II. Linux**

**1. 下载安装包**

检查python版本
```bash
python3 --version
```


在 Releases 中选择与目标机 Python 版本的包下载。
```text
paper-fetch-skill-offline-linux-x86_64-cp311.sh
paper-fetch-skill-offline-linux-x86_64-cp312.sh
paper-fetch-skill-offline-linux-x86_64-cp313.sh
paper-fetch-skill-offline-linux-x86_64-cp314.sh
```

Linux `.sh` 是自解压安装器，内部 payload 是预安装 runtime 包。默认安装到 `~/.local/share/paper-fetch-skill`，也可以用 `--install-dir <path>` 指定固定目录。

Ubuntu 24.04 系统默认 Python 版本 3.12，Ubuntu 26.04 为 3.14。

直接执行安装器：

```bash
chmod +x paper-fetch-skill-offline-linux-x86_64-cp312.sh
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

桌面显示环境可改用：

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headful --no-user-config
```

如需固定到自定义目录：

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --install-dir "$HOME/tools/paper-fetch-skill" --preset=headless --no-user-config
source "$HOME/tools/paper-fetch-skill/activate-offline.sh"
```

Linux / macOS 离线安装会优先把 `MATHML_TO_LATEX_NODE_BIN` 指向包内 Playwright Node，避免依赖系统 PATH 上的 `node`；同时把 `PAPER_FETCH_IMAGE_TOOLS_DIR` 指向安装目录内 `image-tools` 并把 `image-tools/bin` 加入 PATH。生成的 `activate-offline.sh` 可在 bash 或 zsh 中 `source`。

macOS 离线 release asset 按 CPython ABI 提供 tarball；下载与目标机架构和 Python 版本匹配的 `paper-fetch-skill-offline-macos-*-cp*.tar.gz` 后解压运行。macOS 可见浏览器调试使用：

```bash
tar -xzf paper-fetch-skill-offline-macos-arm64-cp312.tar.gz
cd paper-fetch-skill-offline-macos-arm64-cp312
./install-offline.sh --preset=headful --no-user-config
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

#### **III. 更新和卸载**

**更新**

Windows 下载新版 `paper-fetch-skill-windows-x86_64-setup.exe` 后直接运行。安装器会先备份 `%LOCALAPPDATA%\PaperFetchSkill\offline.env`，清理既有安装 payload，再安装新版运行时并写回用户配置，只刷新受管理的运行时配置、PATH、Skill 和 MCP 注册。

Linux 下载与目标机 Python 版本匹配的新版 `.sh` 后直接运行。默认安装目录固定为 `~/.local/share/paper-fetch-skill`，升级时会清理既有 runtime payload、移除源码/构建残留，并保留安装目录内的 `offline.env`。若希望复用外部 env 文件且不修改它，使用 `--reuse-env-file`：

```bash
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config
./paper-fetch-skill-offline-linux-x86_64-cp312.sh --preset=headless --no-user-config --reuse-env-file /path/to/shared/offline.env
source ~/.local/share/paper-fetch-skill/activate-offline.sh
```

`--reuse-env-file` 会让 shell / Skill / MCP 指向新版 runtime，但不会修改被复用的 `offline.env`。更新后重启 Codex / Claude Code。

**卸载**

Windows 在“设置 > 应用 > 已安装的应用”中卸载 `Paper Fetch Skill`，或运行：

```powershell
& "$env:LOCALAPPDATA\PaperFetchSkill\unins000.exe"
```

如需保留 `offline.env` 中的 API key，卸载前先备份该文件。

Linux 默认安装目录运行：

```bash
~/.local/share/paper-fetch-skill/install-offline.sh --uninstall
```

该命令只清理用户级 PATH / Skill / MCP 集成，不删除固定安装目录、`bin/`、`runtime/`、`offline.env` 或 `downloads/`；确认不再需要后运行 `~/.local/share/paper-fetch-skill/install-offline.sh --purge` 删除安装目录。

### 在线安装（不推荐，开发使用）

在仓库根目录执行：

```bash
./install.sh
```

默认会创建仓库内 `.venv`，安装 Python 包，并准备公式后端、图片转换后端等运行组件；需要浏览器路径时由 CDP browser workflow 通过 cloakbrowser 按需下载/定位 Chrome 或连接外部 CDP endpoint。AMS 正文图会优先使用页面 `Download Figure` 暴露的 EPS/TIFF 源文件，运行时用 Ghostscript/libvips 转为 PNG 保存，并保留原始源文件；转换不可用或失败时回退网页 JPG/PNG 候选。

如果只想安装 Python 包和基础配置：

```bash
./install.sh --lite
```

arXiv 路径细节见 [`docs/providers.md`](docs/providers.md#arxiv)。

如果只想装进当前 Python 环境：

```bash
python3 -m pip install .
```

轻量安装会跳过外部公式和图片转换后端；单独准备图片转换后端可运行 `./install-image-tools.sh` 或已安装环境中的 `paper-fetch-install-image-tools`。

图片转换是可选能力。若希望 AMS EPS/TIFF 源图能转 PNG，请先或后自行安装 Ghostscript 和 libvips，然后运行 `./install-image-tools.sh` 或 `paper-fetch-install-image-tools` 让 paper-fetch 记录工具位置；如果不安装，paper-fetch 仍可工作，会回退网页 JPG/PNG。

安装后可用命令：

```bash
paper-fetch --query "10.1186/1471-2105-11-421"
paper-fetch-mcp
paper-fetch-install-image-tools
```

### CLI 行为速查

`paper-fetch` 的输出与本地 artifact 参数分工如下：

- `--format markdown|json|both` 指定 stdout、`--output` 或 `--output-dir` 默认主输出文件的序列化格式，默认是 `markdown`。
- `--query-file <path>` 启用批量抓取，每行一个 DOI、URL 或标题；空行和以 `#` 开头的注释行会被忽略。批量模式不向 stdout 输出正文，而是把每篇主输出写到输出目录，并生成 JSONL 汇总。
- `--version` 输出当前安装的 `paper-fetch` 版本并退出。
- `--output <path>` 把这份格式化结果写到指定文件；显式 `--output -` 表示打印到终端。
- `--output-dir <dir>` 是默认主输出、Markdown、PDF fallback 来源文件和本地资产的保存目录；CLI 会在抓取前自动创建该目录，未显式传 `--output` 时，主输出会写到 `<doi>.md`、`<doi>.json` 或 `<doi>.both.json`，stdout 不输出正文。
- `--batch-concurrency <1..8>` 控制批量并发，默认 `1`；`--batch-results <path>` 可覆盖默认的 `<output-dir>/batch-results.jsonl`。
- `--artifact-mode markdown-assets|all|none` 控制中间产物保留，CLI 默认是 `markdown-assets`：保存 Markdown、按 `--asset-profile` 保存资产，不保留 provider 原始 HTML/XML、fetch-envelope/cache JSON 或 HTTP textual cache；如果正文来自 PDF fallback，仍会保存 PDF 源文件便于溯源，文件名优先使用 provider 抓取后合并的标题、作者和年份元数据。
- `--artifact-mode all` 保留完整调试 artifact：provider HTML/PDF、辅助 artifact、HTTP textual cache 等都可落盘。
- `--artifact-mode none` 不保存 provider artifact 或资产；显式 `--output <path>`、`--save-markdown`，以及未显式 `--output` 时由 `--output-dir` 承接的主输出仍可写文件。`--no-download` 等价于 `--artifact-mode none`。
- `--asset-profile none|body|all` 控制本地内容资产下载范围，CLI 默认是 `body`：`none` 不下载本地资产但保留 Markdown 中可解析的远程图片链接，`body` 保存正文图片/图表/公式图片，`all` 额外保存补充材料；PDF fallback 在 `body` / `all` 且允许 artifact 落盘时会保存 `pymupdf4llm` 导出的正文图片到 `<doi>_assets/`。

完整命令组合、主输出与 artifact 的区别、错误输出和 exit code 见 [`docs/cli.md`](docs/cli.md)。

例如：

```bash
paper-fetch --query "https://www.nature.com/articles/s41559-026-03039-9" \
  --output-dir ./papers
```

这会把 Markdown 写到 `./papers/<doi>.md`，不打印正文到终端，并按默认 `--asset-profile body` 保存正文图片等资产；默认不会保存 provider 原始 HTML/XML 或 JSON/cache sidecar。需要完整调试 artifact 时显式使用 `--artifact-mode all`。如果需要强制打印到终端，显式传 `--output -`。

批量抓取时先准备 query 文件：

```text
# 每行一个 DOI、URL 或标题
10.1186/1471-2105-11-421
https://www.nature.com/articles/s41559-026-03039-9
```

然后运行：

```bash
paper-fetch --query-file ./queries.txt \
  --output-dir ./papers \
  --batch-concurrency 4
```

这会把每篇 Markdown 和正文资产写到 `./papers`，并生成 `./papers/batch-results.jsonl`。单篇失败会记录到 JSONL 并继续处理后续条目。

如果只想控制格式化结果的文件路径，显式使用 `--output`：

```bash
paper-fetch --query "10.1186/1471-2105-11-421" \
  --format markdown \
  --output ./papers/article.md \
  --output-dir ./papers
```

显式 `--output <path>` 只控制主输出文件路径，不会自动创建该文件的父目录。

安装脚本结束时会提示 Elsevier 官方 API 配置入口。抓取 Elsevier 全文前，需要从 <https://dev.elsevier.com/> 申请 key，并在配置文件中填写 `ELSEVIER_API_KEY`。

### 配置文件

默认配置文件位置：

```text
~/.config/paper-fetch/.env
```

需要 API key、自定义下载目录或 User-Agent 时，可以先创建配置文件：

```bash
mkdir -p ~/.config/paper-fetch
cp .env.example ~/.config/paper-fetch/.env
```

其中 Elsevier 官方 XML/API 和 PDF fallback 至少需要从 <https://dev.elsevier.com/> 申请并配置：

```bash
ELSEVIER_API_KEY="..."
```

也可以通过环境变量显式指定：

```bash
export PAPER_FETCH_ENV_FILE=/path/to/.env
```

完整环境变量说明见 [`docs/providers.md`](docs/providers.md)。

Browser workflow 可显式复用已经运行的浏览器，也可让 paper-fetch 自动启动：

```bash
/path/to/chrome \
  --user-data-dir "$HOME/.cache/paper-fetch/browser-profile" \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --no-first-run

export CLOAKBROWSER_CDP_ENDPOINT="ws://127.0.0.1:9222/devtools/browser/..."
```

未配置 `CLOAKBROWSER_CDP_ENDPOINT` 时，paper-fetch 会通过 cloakbrowser 首次下载/定位 Chrome 并自动启动本机 CDP 浏览器，默认按 publisher 复用 `storage-state.json`，且默认 headless managed 浏览器会带 `--headless=new`；如需固定 binary 或显式指定 storage-state 所在目录，可设置 `CLOAKBROWSER_BINARY_PATH`、`CLOAKBROWSER_PROFILE_DIR` 或 `CLOAKBROWSER_USER_DATA_DIR`。配置外部 CDP endpoint 时，抓取默认借用现有 browser context，storage-state cookies 会尽量注入，UA、viewport 等新 context 参数不保证生效；设置 `PAPER_FETCH_CDP_EXTERNAL_NEW_CONTEXT=1` 可要求在外部浏览器中创建新 context。managed 和外部 CDP 的 browser-backed 资产下载会避免跨线程复用 Playwright sync 对象；普通 HTTP 资产下载仍按配置并发。

自动过盾失败时，可打开对应 provider 的 headed browser 手动登录/验证：

```bash
paper-fetch browser-preflight
paper-fetch auth <provider>
paper-fetch auth wiley --url "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
```

`provider` 来自 browser runtime catalog，例如 `wiley` / `science` / `pnas` / `annualreviews` / `acs` / `iop` / `aip` / `mdpi`。`browser-preflight` 会按 catalog 顺序使用这些 provider 的内置样例 DOI/URL 构造正常 HTML candidates，并复用 provider HTML bootstrap、同一 browser context 重试和 availability 判定；成功时保存 `publisher-browser-profiles/<provider>/storage-state.json`，失败时打印需要人工 auth 的出版社。该命令只验证 HTML 路径，不触发 PDF fallback；`auth` 未传 `--url` 时打开内置样例文章，传入 `--url` 时打开具体失败文章页。命令会打印 managed Chrome 启动目录和 storage-state 路径，终端按 Enter 后保存过滤后的本地 storage-state 并退出，不写 `.env`。


### 接入 Codex

安装 skill 并注册 MCP server：

```bash
./scripts/install-codex-skill.sh --register-mcp
```

带配置文件注册：

```bash
./scripts/install-codex-skill.sh --register-mcp --env-file ~/.config/paper-fetch/.env
```

只安装到当前项目：

```bash
./scripts/install-codex-skill.sh --project --register-mcp
```

安装后重启 Codex，让它重新扫描 skills 和 MCP 配置。

### 接入 Claude Code

```bash
./scripts/install-claude-skill.sh --register-mcp
```

常用参数包括：

```bash
./scripts/install-claude-skill.sh --project --register-mcp
./scripts/install-claude-skill.sh --register-mcp --env-file ~/.config/paper-fetch/.env
```

### 接入 Antigravity CLI

Antigravity CLI（`agy`）同样支持 SKILL.md 规范的 skill 和 MCP server：

```bash
./scripts/install-antigravity-skill.sh --register-mcp
```

常用参数：

```bash
# 只安装到当前项目（skill 写入 ./.agents/skills/，MCP 写入 ./.agents/mcp_config.json）
./scripts/install-antigravity-skill.sh --project --register-mcp
# 注册时指定环境变量文件
./scripts/install-antigravity-skill.sh --register-mcp --env-file ~/.config/paper-fetch/.env
```

- 用户级安装默认写入 `~/.gemini/antigravity-cli/skills/` 与 `~/.gemini/antigravity-cli/mcp_config.json`；用环境变量 `ANTIGRAVITY_HOME` 可覆盖全局目录。
- Antigravity 没有 `mcp add` 子命令，`--register-mcp` 会把本地 stdio server（`command`/`args`/`env`）合并进 `mcp_config.json`，已有的其它 server 条目会被保留。
- 安装后重启 `agy`，让它重新扫描 skills 和 MCP 配置。

### 手动注册 MCP

任何支持 stdio MCP 的 host 都可以直接运行：

```bash
paper-fetch-mcp
```

或：

```bash
python3 -m paper_fetch.mcp.server
```

Codex CLI 可手动注册同一个 stdio server：

```bash
codex mcp add paper-fetch -- python3 -X utf8 -m paper_fetch.mcp.server
```

### 常用抓取参数

MCP 默认模式、`artifact_mode`、`prefer_cache`、`no_download` 和 `save_markdown` 的完整语义见 [`docs/providers.md`](docs/providers.md#mcp-download-and-markdown-save)。MCP `artifact_mode` 默认是 `markdown-assets`；`strategy.asset_profile` 支持 `none`、`body`、`all`，MCP/Python API 未显式设置时默认由 provider 决定。

### 更新

更新仓库后重新安装包和 agent 集成：

```bash
python3 -m pip install .
./scripts/install-codex-skill.sh --register-mcp
```

Claude Code 用户对应执行：

```bash
./scripts/install-claude-skill.sh --register-mcp
```

## 文档

- [`docs/deployment.md`](docs/deployment.md)：安装、配置、MCP 注册和更新。
- [`docs/providers.md`](docs/providers.md)：provider 能力、环境变量和运行时配置。
- [`docs/README.md`](docs/README.md)：完整文档导航。
- [`docs/architecture/overview.md`](docs/architecture/overview.md)：架构边界和维护者视角。

## 免责声明

本项目通过公开可访问的开放获取接口、publisher 路由和用户配置的凭据获取研究论文内容。

- 获取的文献仅供个人学术研究和学习使用，不得用于商业用途。
- 请遵守所在国家/地区著作权法律法规及所在机构的知识产权政策。
- 本项目不绕过付费墙或访问授权；可用性取决于 provider、凭据和本机运行环境。
- 本项目不存储、分发或传播任何文献内容，仅协助用户定位、抓取或转换用户有权访问的论文内容。
- fixture 中的文献样本仅作为测试使用，严禁对 fixture 进行任何形式的二次分发。
- 使用者应对自身的文献获取和使用行为承担全部责任。

## 社区

<https://linux.do/>
