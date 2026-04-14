# 主链路工作流（中文版）

本文件是 [MAIN_CHAIN_WORKFLOW.md](/home/dictation/test/MAIN_CHAIN_WORKFLOW.md) 的中文版本，用于说明当前目录中已经验证可用的 Science/PNAS 全文抓取主链路。

## 目的

当前目录现在只保留了这台机器上已经验证通过的 Science/PNAS 全文抓取主工作流。

为了在其他主机上更通用，当前脚本的默认 preset 已经切到 `.env.flaresolverr-source-headless`，也就是 `HEADLESS=true + Xvfb`。
之前已经验证过的 WSLg preset 仍然保留在 `.env.flaresolverr-source-wslg`，当你明确想走有界面的 WSLg 路线时再显式指定它。
但在当前这台主机上，真正已经验证可用的本地路径仍然是显式的 WSLg preset，因为官方 `Xvfb` 路线在 `/tmp/.X11-unix` 为只读挂载时可能失败。

已验证的链路如下：

1. 从官方上游源码树运行 FlareSolverr。
2. 使用本机的 WSLg 显示环境，并设置 `HEADLESS=false`。
3. 当这个有界面的 WSLg 浏览器以后台模式启动时，保持 PTY 仍然挂接。
4. 用 `setsid` 把后台服务启动到独立 session 中，而不是单纯依赖 `nohup ... &`。
5. 在 `http://127.0.0.1:8191/v1` 暴露本地 FlareSolverr 服务。
6. 让 `fetch_fulltext.py` 使用 FlareSolverr 作为 HTML 抓取后端。
7. 如果出版社 HTML 路由落到摘要页，就复用 FlareSolverr 已解出的 cookies 和 user-agent，给 Playwright 的浏览器上下文注入种子，然后走 PDF fallback。

这是当前目录中唯一已经端到端验证过的链路。

## 当前保留内容

当前保留的重要文件有：

- `fetch_fulltext.py`
  主抓取流水线。负责 PMC、Crossref、出版社 HTML，以及 PDF fallback。
- `setup_flaresolverr_source.sh`
  官方 FlareSolverr 源码工作流的一次性初始化脚本。
- `start_flaresolverr_source.sh`
  以后台方式启动本地 FlareSolverr 服务。
- `run_flaresolverr_source.sh`
  以前台方式运行 FlareSolverr，便于诊断。
- `stop_flaresolverr_source.sh`
  停止后台 FlareSolverr 服务。
- `flaresolverr_source_common.sh`
  共享的环境变量解析和通用路径辅助函数。
- `.env.flaresolverr-source-wslg`
  供显式调用的 WSLg 有界面环境文件。
- `.env.flaresolverr-source-wslg.example`
  示例环境文件。
- `.env.flaresolverr-source-headless`
  默认的可移植 headless 环境文件。
- `.env.flaresolverr-source-headless.example`
  默认 headless preset 的示例环境文件。
- `FLARESOLVERR_SOURCE_WORKFLOW.md`
  同一条链路的简明操作说明。
- `MAIN_CHAIN_WORKFLOW.md`
  英文详细说明文档。
- `MAIN_CHAIN_WORKFLOW.zh-CN.md`
  本中文详细说明文档。

这套工作流依赖的运行时内容会在需要时由 setup 重新生成：

- `.work/FlareSolverr`
  由 setup 创建的官方上游 FlareSolverr 源码检出目录。
- `.venv-flaresolverr`
  用于运行 FlareSolverr 的虚拟环境。
- `.flaresolverr`
  已下载的 FlareSolverr 发布包，其中包含源码工作流使用的内置 Chrome。

## 为什么保留这条链路

这台主机使用的是 WSLg。对这里来说，稳定路径不是 Docker，也不是预先保存好的浏览器状态文件。

原因如下：

- 官方 Docker 路线并不是这个目标上的稳定赢家。
- 工作链路不需要手工维护 `storage_state.json`。
- 已验证的源码路径使用的是官方上游代码，没有打源码补丁。
- 在这台机器上，复用 WSLg 显示环境并设置 `HEADLESS=false` 已被证明更稳定。
- 对 PNAS 这类目标来说，即使已经绕过防护，HTML 文章路径仍然可能落到摘要页，所以 PDF fallback 是主链路中的实际组成部分。

## 推荐 preset 对照表

| 环境 | 推荐 preset | 模式 | 推荐原因 |
| --- | --- | --- | --- |
| WSLg | `.env.flaresolverr-source-wslg` | `HEADLESS=false` | 适合明确需要可见浏览器和主机侧交互调试的场景。 |
| 桌面 Linux | `.env.flaresolverr-source-headless` | `HEADLESS=true` + `Xvfb` | 更适合作为默认值，因为它对当前图形会话状态的依赖更小。 |
| 无头服务器 | `.env.flaresolverr-source-headless` | `HEADLESS=true` + `Xvfb` | 最适合 SSH、systemd、tmux、CI 这类没有真实显示环境的场景。 |

## 环境

脚本默认使用的环境文件是 `.env.flaresolverr-source-headless`。

显式的 WSLg 环境文件是 `.env.flaresolverr-source-wslg`。

headless preset 的主要设置有：

- `HEADLESS="true"`
- `FLARESOLVERR_LOG_FILE="/home/dictation/test/run_logs/flaresolverr-source-headless.log"`
- `FLARESOLVERR_PID_FILE="/home/dictation/test/run_logs/flaresolverr-source-headless.pid"`

WSLg preset 的关键区别设置是：

- `FLARESOLVERR_REPO_DIR="/home/dictation/test/.work/FlareSolverr"`
- `FLARESOLVERR_VENV_DIR="/home/dictation/test/.venv-flaresolverr"`
- `FLARESOLVERR_DOWNLOAD_DIR="/home/dictation/test/.flaresolverr"`
- `FLARESOLVERR_RELEASE_VERSION="v3.4.6"`
- `FLARESOLVERR_HOST="127.0.0.1"`
- `FLARESOLVERR_PORT="8191"`
- `HEADLESS="false"`
- `TZ="Asia/Shanghai"`

最终得到的服务端点是：

- `http://127.0.0.1:8191/v1`

## 一次性初始化

运行一次下面的命令，用来准备源码检出、Python 环境以及内置 Chrome：

```bash
cd /home/dictation/test
bash ./setup_flaresolverr_source.sh
```

因为脚本默认使用 `HEADLESS=true`，所以需要先安装 `Xvfb` 可执行文件。
在 Debian/Ubuntu 系统上，通常就是安装 `xvfb` 包：

```bash
sudo apt-get update
sudo apt-get install -y xvfb
```

如果你显式切换到 `.env.flaresolverr-source-wslg`，那条 WSLg 路线使用的是 `HEADLESS=false`，因此不依赖 `Xvfb`。
在当前这台主机上，这条显式 WSLg 路线仍然是已经验证过的本地可用路径。

它会完成以下事情：

1. 在 `.work/FlareSolverr` 下克隆或更新官方 FlareSolverr 仓库。
2. 在需要时创建 `.venv-flaresolverr`。
3. 把 FlareSolverr 的 Python 依赖安装进该虚拟环境。
4. 下载匹配版本的官方 FlareSolverr 发布包。
5. 解压内置 Chrome。
6. 确保源码树通过 `src/chrome` 指向内置 Chrome。

## 启动服务

正常的后台启动方式：

```bash
cd /home/dictation/test
bash ./start_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
```

默认情况下，当前保留脚本会自动使用 `.env.flaresolverr-source-headless`。

如果你想走显式的 WSLg 路线，请在命令行中传入 `.env.flaresolverr-source-wslg`。
上面这条显式 WSLg 命令，仍然是当前这台主机上已经验证过的本地命令。

当 `HEADLESS=false` 时，`start_flaresolverr_source.sh` 会用 `script` 包一层启动过程，这样服务在后台运行时，浏览器仍然有可用的 PTY。
这样可以避免一种失败模式：`sessions.list` 看起来成功了，但第一个真正的 `request.get` 会把后台服务打掉。

依赖说明：

- `HEADLESS=true` 需要安装 `Xvfb` 包，并且系统里能找到 `Xvfb` 可执行文件
- 当前目录里显式的 WSLg 路径使用 `HEADLESS=false`，因此它复用的是 WSLg 显示环境，而不是 `Xvfb`

在当前执行环境里，单纯依赖 `nohup ... &` 启一个后台子进程并不够可靠。
父命令退出后，子进程可能会被回收，于是你会看到一种很误导的现象：

- `start_flaresolverr_source.sh` 打印服务启动成功
- 一个很快的 `sessions.list` 探测仍然可能成功
- 但监听进程很快就消失
- 随后 `fetch_fulltext.py` 在创建 session 或发送 `request.get` 时报告 `flaresolverr_timeout`

这就是为什么当前保留的后台启动器优先使用 `setsid`。
`setsid` 和 `script` 解决的是两个不同的问题：

- `setsid` 的作用是让后台 FlareSolverr 服务在父启动器退出后仍然存活
- `script` 的作用是在 `HEADLESS=false` 时，为有界面的 WSLg 浏览器路径保留 PTY

这两者都属于这台主机上已经验证过的后台工作流组成部分。

后台服务会写出以下文件：

- 默认日志文件：`run_logs/flaresolverr-source-headless.log`
- 默认 PID 文件：`run_logs/flaresolverr-source-headless.pid`
- 显式选择 WSLg 时的日志文件：`run_logs/flaresolverr-source-wslg.log`
- 显式选择 WSLg 时的 PID 文件：`run_logs/flaresolverr-source-wslg.pid`

要确认服务可达，可以运行：

```bash
curl --noproxy '*' -fsS -X POST http://127.0.0.1:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.list"}'
```

## 前台模式

如果你需要直接看到浏览器或 session 日志：

```bash
cd /home/dictation/test
bash ./run_flaresolverr_source.sh
```

这个模式适合用于诊断启动失败、挑战页处理，或者时序类问题。

## 停止服务

```bash
cd /home/dictation/test
bash ./stop_flaresolverr_source.sh
```

## 主抓取命令：fetch_fulltext.py

`fetch_fulltext.py` 应该在 Conda 环境 `science-fulltext` 中运行。

推荐写法：

```bash
conda run -n science-fulltext python fetch_fulltext.py \
  --input your.csv \
  --output-dir out \
  --html-fetcher flaresolverr \
  --enable-pdf-fallback \
  --flaresolverr-url http://127.0.0.1:8191/v1
```

如果你更喜欢先激活环境，也可以用：

```bash
cd /home/dictation/test
conda activate science-fulltext
python fetch_fulltext.py \
  --input your.csv \
  --output-dir out \
  --html-fetcher flaresolverr \
  --enable-pdf-fallback \
  --flaresolverr-url http://127.0.0.1:8191/v1
```

FlareSolverr 本身是通过本地源码工作流脚本启动的，不需要依赖 `science-fulltext` 这个 Conda 环境。
这里要求 Conda 环境，是因为 `fetch_fulltext.py` 及其 Python 侧依赖需要在这个环境里运行。

## 输入 CSV 格式

CSV 至少必须包含：

- `doi`

流水线还支持以下可选列：

- `label`
- `publisher`

最小示例如下：

```csv
doi
10.1073/pnas.81.23.7500
```

## 高层流水线

对每个 DOI，`fetch_fulltext.py` 会按以下顺序执行：

1. 规范化 DOI，并构造输出 slug。
2. 先尝试 PMC。
3. 如果 PMC 成功，就把 JATS XML 转成 Markdown 并结束。
4. 如果 PMC 没有产出可用结果，就查询 Crossref，拿出版社元数据和候选 URL。
5. 如果出版社受支持，就尝试出版社 HTML 候选地址。
6. 如果 HTML 成功，就保存原始 HTML 和 Markdown。
7. 如果 HTML 失败，且启用了 `--enable-pdf-fallback`，就用浏览器上下文去尝试 PDF 候选地址。
8. 对每个 DOI，在 manifest 中写一行 JSON，记录最终状态和所有尝试过程。

相关的成功状态有：

- `success_pmc`
- `success_html`
- `success_pdf_fallback`

## FlareSolverr HTML 分支如何工作

当选择 `--html-fetcher flaresolverr` 时：

1. `fetch_fulltext.py` 会创建一个 FlareSolverr session。
2. 按顺序尝试出版社 HTML 候选 URL。
3. 每个 URL 都通过 `request.get` 拉取。
4. 对返回页面做挑战页标记、重定向以及全文质量检查。
5. 如果成功，就把 HTML 转成 Markdown。
6. 函数退出前销毁 FlareSolverr session。

`fetch_fulltext.py` 里 FlareSolverr 的默认抓取参数是：

- `--flaresolverr-url http://127.0.0.1:8191/v1`
- `--flaresolverr-wait-seconds 8`
- `--flaresolverr-max-timeout-ms 120000`

对 `127.0.0.1:8191` 的本地请求会显式忽略 shell 里的代理环境变量，这样本地 HTTP 代理就不会误拦截 FlareSolverr 控制通道。
辅助 shell 脚本现在也做了同样的处理。

## 为什么 PDF fallback 是主链路的一部分

对一些 PNAS 文章来说，绕过防护并不等于拿到完整 HTML。

可能发生的情况是：

1. FlareSolverr 成功到达站点并通过了防护。
2. 出版社的 `/doi/full/...` 路由仍然跳到摘要页，比如 `/doi/abs/...`。
3. HTML 质量检查正确地把这个页面判定为“不是全文”。

在这种情况下，主链路不会停在这里，而是继续走浏览器上下文下的 PDF fallback。

## FlareSolverr 分支中的 PDF fallback 如何工作

这是当前保留实现里非常关键的一部分。

FlareSolverr 目前的 `v1` 接口并不提供真正的 PDF 二进制下载 API。
因此主链路采用两阶段策略：

1. FlareSolverr 负责解出防护，并返回：
   - 最终 URL
   - cookies
   - 浏览器 user-agent
   - 渲染后的 HTML
2. `fetch_fulltext.py` 只在内存中保存这些 cookies 和 user-agent。
3. 如果 HTML 被拒绝且启用了 PDF fallback，Playwright 会启动一个浏览器上下文。
4. 这个上下文会注入从 FlareSolverr 派生出来的 cookies 和 user-agent。
5. 脚本访问 PDF 候选 URL，并等待真正的浏览器下载动作发生。
6. 下载到的 PDF 再被转换成 Markdown。

这样你就同时得到：

- 用 FlareSolverr 绕过防护
- 用 Playwright 获得真实浏览器下载行为
- 不依赖 `storage_state.json`

## 输出目录布局

假设你使用 `--output-dir out`，主要输出树如下：

- `out/manifest.jsonl`
  每个 DOI 一行 JSON，包含最终结果和尝试历史。
- `out/raw/xml/`
  当 PMC 路径成功时保存原始 PMC XML。
- `out/raw/html/`
  当 HTML 路径成功时保存原始出版社 HTML。
- `out/raw/pdf/`
  当 PDF fallback 路径成功时保存原始 PDF。
- `out/markdown/`
  最终 Markdown 输出。
- `out/logs/`
  失败产物，例如 HTML 快照、截图以及结构化失败 JSON。

## Manifest 语义

每一行 manifest 都包含：

- `doi`
- `publisher`
- `html_fetcher`
- `selected_source`
- `source_url`
- `status`
- `raw_path`
- `markdown_path`
- `error_kind`
- `attempts`

如果 FlareSolverr 的 HTML 路径失败，但 PDF fallback 成功，manifest 在高层通常会长成这样：

1. `publisher_html` 尝试以 `redirected_to_abstract` 失败。
2. `pdf_fallback` 尝试成功。
3. 最终整行状态变成 `success_pdf_fallback`。

## 失败产物

当 FlareSolverr 分支中的 HTML 抓取失败时，流水线可能会写出：

- `logs/<slug>.failure.html`
- `logs/<slug>.failure.png`
- `logs/<slug>.failure.response.json`
- `logs/<slug>.html-failure.json`

一个重要细节是：

- 写入磁盘前，记录下来的 FlareSolverr 响应会做脱敏处理，所以 cookie 值不会以明文存储。
- 用于 PDF fallback 的内存态 cookie 种子不会写入 manifest。

## 已验证示例

这条链路已经在本机上针对以下 DOI 验证过：

- `10.1126/science.aeg3511`
- `10.1126/science.ady3136`
- `10.1073/pnas.81.23.7500`

截至 2026-04-14，针对近期 `Science` DOI 观察到的行为如下：

1. 普通 `curl` 直接访问同一篇 `Science` 正文 URL 时，仍然会收到 Cloudflare challenge。
2. 显式的 WSLg `Flaresolverr` 路线可以成功拿到 `https://www.science.org/doi/full/...` 的 HTML。
3. `10.1126/science.aeg3511` 的最终状态为 `success_html`。
4. `10.1126/science.ady3136` 的最终状态也为 `success_html`，并且 Markdown 中包含 `Structured Abstract`、`Discussion`、`Materials and methods` 等正文部分。

针对 PNAS DOI 观察到的行为如下：

1. FlareSolverr 成功绕过防护。
2. HTML 路由仍然被判定为“仅摘要”或“重定向到摘要页”。
3. 注入种子的 Playwright PDF fallback 成功。
4. 最终状态为 `success_pdf_fallback`。

这说明当前目录中的已验证结果已经同时覆盖了两类情况：

- `Science` 近期样例可以直接拿到 `success_html`
- `PNAS` 样例仍然需要把 `--enable-pdf-fallback` 视为正常命令的一部分

## 实际操作流程

一次正常运行的操作顺序：

1. `cd /home/dictation/test`
2. `bash ./setup_flaresolverr_source.sh`
3. `bash ./start_flaresolverr_source.sh`
4. `conda run -n science-fulltext python fetch_fulltext.py --input your.csv --output-dir out --html-fetcher flaresolverr --enable-pdf-fallback --flaresolverr-url http://127.0.0.1:8191/v1`
5. `bash ./stop_flaresolverr_source.sh`

## 故障排查

### 服务无法启动

检查以下内容：

- `.work/FlareSolverr` 是否存在
- `.venv-flaresolverr` 是否存在
- `.flaresolverr/.../chrome` 是否存在
- 如果使用 `HEADLESS=true`，确认已经安装 `Xvfb`，并且 `command -v Xvfb` 可以找到它
- 查看当前 preset 对应的日志文件中的实际启动错误
- 如果默认 headless preset 在这台 WSLg 主机上失败，显式改用 `.env.flaresolverr-source-wslg`

如果看起来是初始化不完整，可以重新运行：

```bash
bash ./setup_flaresolverr_source.sh
```

### FlareSolverr 可达，但 fetch_fulltext.py 提示 Timeout

检查：

- 服务是否真的能响应 `sessions.list`
- 几秒之后监听 PID 是否仍然存活
- `ss -ltnp '( sport = :8191 )'` 是否仍然显示 `127.0.0.1:8191` 上有活着的 Python 监听进程
- 是否需要用前台模式查看详细日志
- 本地 WSLg 浏览器启动是否健康

在这台主机上，已经定位到的一种具体失败模式是：

- 服务是通过单纯的 `nohup ... &` 启动的
- 启动探测看到了短暂成功的 `sessions.list`
- 父启动器退出后，后台子进程被回收
- 随后 `fetch_fulltext.py` 以 `flaresolverr_timeout` 失败

当前保留的解决方式是：

- 使用当前目录里保留的 `start_flaresolverr_source.sh`，它现在优先用 `setsid`
- 不要再把它替换成单纯的 `nohup` 启动器

你也可以临时提高以下参数：

- `--flaresolverr-wait-seconds`
- `--flaresolverr-max-timeout-ms`

### HTML 以 redirected_to_abstract 失败

这不一定意味着防护绕过失败。

对 PNAS 来说，这通常表示：

- FlareSolverr 已经成功到达页面
- 但出版社仍然返回了摘要路由，而不是全文 HTML

预期的补救方式是：

- 保持启用 `--enable-pdf-fallback`

### PDF fallback 没有触发

重点查看：

- `logs/<slug>.pdf-failure.html`
- `logs/<slug>.pdf-failure.png`
- `logs/<slug>.pdf-failure.json`

常见原因包括：

- 出版社没有触发真正的浏览器下载
- 返回内容并不是真正的 PDF
- 对该目标来说，浏览器种子 cookies 不够用

### 与代理相关的混淆

本地 FlareSolverr 控制调用已经绕过了代理环境变量，因此 `127.0.0.1:8191` 不应走 shell 中配置的代理。

如果出版社侧流量本身需要代理，那是与本地控制通道分开的另一件事。

## 当前默认值

当前保留脚本默认使用 headless 环境文件：

- `run_flaresolverr_source.sh`
- `start_flaresolverr_source.sh`
- `stop_flaresolverr_source.sh`
- `setup_flaresolverr_source.sh`

如果从跨主机可移植性的角度看，默认最短命令是：

```bash
cd /home/dictation/test
bash ./setup_flaresolverr_source.sh
bash ./start_flaresolverr_source.sh
conda run -n science-fulltext python fetch_fulltext.py --input your.csv --output-dir out --html-fetcher flaresolverr --enable-pdf-fallback
bash ./stop_flaresolverr_source.sh
```

如果你想走 WSLg 有界面路线，请在 `setup`、`start`、`run`、`stop` 这些脚本后面显式传入 `.env.flaresolverr-source-wslg`。

在当前这台 WSLg 主机上，最短的已验证可用命令仍然是：

```bash
cd /home/dictation/test
bash ./setup_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
bash ./start_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
conda run -n science-fulltext python fetch_fulltext.py --input your.csv --output-dir out --html-fetcher flaresolverr --enable-pdf-fallback --flaresolverr-url http://127.0.0.1:8191/v1
bash ./stop_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
```

## 最后结论

如果你只想记住真正可用的路径，只要记住下面几点：

1. 启动本地的 WSLg FlareSolverr 服务。
2. 运行 `fetch_fulltext.py`，并带上 `--html-fetcher flaresolverr --enable-pdf-fallback`。
3. 让 FlareSolverr 负责解防护。
4. 当完整 HTML 不可用时，让 Playwright 去执行已经注入种子的浏览器上下文 PDF 下载。
