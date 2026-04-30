---
name: paper-fetch-skill
description: "适用场景：按 DOI、URL 或标题抓取单篇已知论文，或核验一组可识别的参考文献。非适用场景：主题综述、文献发现、仅做推荐。"
---

# 论文抓取技能

当代理需要获取某一篇特定论文的内容或全文可用性，而不是做宽泛的主题概览时，使用这个技能。

## 适用场景

- 用户提供了 `doi`、论文 `url` 或论文 `title`。
- 用户要求阅读、总结、比较、批判、翻译，或提取某篇特定论文的方法/结果。
- 用户给出参考文献列表或书目，想知道哪些具体论文可读或可抓取。
- 你需要可直接放入模型上下文的精简 Markdown 或结构化元数据。

> ## 🚨 全局执行纪律（强制）
>
> **本工作流是严格的串行流水线。以下规则具有最高优先级，违反任意一条都构成执行失败：**
>
> 1. **串行执行**：步骤必须按顺序执行；每一步的输出都是下一步的输入。相邻的非 BLOCKING 步骤在前置条件满足后可以连续推进，无需等待用户说“继续”。
> 2. **BLOCKING = 强制暂停**：标记为 ⛔ BLOCKING 的步骤必须完全暂停；AI 必须等待用户明确回复后才能继续，且不得替用户做决定。


## Provider 特殊规则

- 如果目标论文属于 `science`、`pnas`、`wiley` 这类依赖浏览器运行时的 provider，在第一次抓取前先启动 FlareSolverr，并用 `provider_status()` 或仓库现成的状态脚本确认运行时健康后再抓取。
- 如果 `wiley`、`science`、`pnas` 这类依赖浏览器运行时的抓取首次失败，可以在排除明显配置错误后最多再重试 `2` 次；重试时优先绕过缓存，并确认本地浏览器运行时或 FlareSolverr 健康状态。若仍失败，要明确告诉用户失败发生在浏览器链路。

## 不适用场景

- 用户想要宽泛的文献综述或论文发现。
- 对话或工作区里已经有经过核验的完整论文文本，不需要再次抓取。

## 工作流

### 第 1 步：确认保存方式
GATE：在进入任何实际抓取动作前，必须先拿到保存决策。若用户已经明确说明是否保存、保存位置（如需保存）以及是否下载图片资源，则本步可直接视为已完成，并继续做参数映射。

BLOCKING：⛔ BLOCKING。只要以下任一信息缺失，就必须暂停并等待用户明确回复后再继续：`是否保存`、`保存到哪里`（当选择保存时）、`是否下载图片资源`。不得替用户默认这些选项。

1. 如果用户没有明确要求保存，在实际抓取前先确认3个问题：是否需要保存、保存到哪里、是否需要下载图片资源。
2. 将“是否保存”映射到 `save_markdown` / `no_download` 的选择；将“保存到哪里”映射到 `markdown_output_dir` 或 `download_dir`；将“是否下载图片”映射到 `strategy.asset_profile` 是否使用 `body` 或 `all`。

### 第 2 步：给出CLI操作
GATE：仅当第 1 步已经完成参数映射后，才能判断是否需要建议 CLI；判断依据是当前任务是否要处理 `>=3` 篇文献，或是否明显属于成批抓取/核验场景。若用户已经明确表示坚持不用 CLI，则本步只需简短说明“仍可直接抓取”，随后进入第 3 步。

BLOCKING：条件性 ⛔ BLOCKING。若判断应建议 CLI（通常是 `>=3` 篇文献或批量任务），在给出 CLI 用法后必须等待用户明确选择“改用 CLI”或“继续由当前代理直接抓取”；在用户作出选择前不得擅自进入批量抓取。若任务不是批量场景，则本步非 BLOCKING，可直接进入第 3 步。

1. 完成映射后，判断用户是否要抓取>=3篇文献，若是，建议用户改用 `paper-fetch` CLI 自助批量处理。
2. 当你建议用户使用 CLI 时，说明这是为了提高下载效率、节省 token。
3. 当你建议用户使用 CLI 时，按用户在第 1 步已选定的保存方式，给出对应的 CLI 操作方法。
4. 当你建议用户使用 CLI 时，要明确说明：如果用户坚持不使用 CLI，也可以继续由当前代理直接抓取。

### 第 3 步：抓取
GATE：只有在保存策略已确认完毕，且 CLI 分流结果也已明确后，才能开始抓取。对标题或其他可能歧义的输入，必须先完成 `resolve_paper(...)` 并拿到唯一目标；对依赖浏览器运行时的 provider，必须先按上面的 `Provider 特殊规则` 确认 FlareSolverr / 运行时健康。

BLOCKING：默认非 BLOCKING，可连续执行抓取与后续处理；但遇到以下情况时必须立即暂停并等待用户明确回复：`resolve_paper(...)` 返回多个候选、输入信息不足以唯一定位论文、或用户尚未决定是否改用 CLI。除这些情形外，不需要逐步征求“继续”许可。

1. 确认好保存问题，并确认不使用CLI后，如果用户提供的是论文标题，不要直接拿标题进入抓取；先调用 `resolve_paper(...)` 定位 DOI 或落地页，再用解析后的 DOI 或 URL 抓取。若解析结果不唯一，先向用户确认目标论文。
2. 只要可用，优先使用 MCP 工具。
3. 在多轮会话里，重新抓取前先调用 `list_cached()` 或 `get_cached(doi)`。
4. 如果用户给的是标题，先调用 `resolve_paper(query | title, authors, year)` 定位 DOI 或落地页；确认唯一候选后，后续抓取一律优先使用解析出的 DOI，其次使用落地页 URL，不要继续直接拿标题调用 `fetch_paper(...)`。
5. 如果查询可能有歧义，也先调用 `resolve_paper(query | title, authors, year)` 并在必要时向用户消歧。
6. 如果是单篇文献，先询问用户是否保存、保存位置、是否下载图片资源，再决定 `save_markdown`、`download_dir` / `markdown_output_dir` 和 `strategy.asset_profile`。
7. 如果是多篇文献且用户有保存需求，也先按整批询问是否保存、保存位置、是否下载图片资源，再统一决定 `save_markdown`、`download_dir` / `markdown_output_dir` 和 `strategy.asset_profile`。
8. 对书目或参考文献列表任务，先调用 `batch_check(queries, mode, concurrency)` 做分诊；如果用户确实要处理多篇文献，优先建议他们改用 `paper-fetch` CLI。
9. 如果只需要低成本判断能否读取全文，调用 `has_fulltext(query)`。
10. 如果目标 provider 是 `wiley`、`science` 或 `pnas`，在第一次抓取前先启动 FlareSolverr；随后调用 `provider_status()` 或仓库现成的状态脚本确认本地浏览器运行时健康。
11. 如果提供方凭证、或 Wiley / Science / PNAS 的本地运行时状态可能影响结果，在第一次抓取前调用 `provider_status()`。
12. 当你需要适合 AI 的 Markdown、结构化文章数据或元数据时，调用 `fetch_paper(query, modes, strategy, include_refs, max_tokens, prefer_cache, no_download, save_markdown, markdown_output_dir, markdown_filename, download_dir)`。
13. 如果浏览器链路抓取失败，先检查 `provider_status()`、确认运行时健康，并优先以 `prefer_cache=false` 重试；总重试次数最多 `2` 次，不要无限重跑。
14. 不要仅因为本地没有 PDF 或缓存文本文件，就断定“不可读”。
15. 如果拿不到全文，也要继续利用返回的仅摘要或仅元数据结果，并明确告诉用户当前基于元数据或摘要工作。

## 参考资料

- 当你需要提供方凭证、下载目录行为，或 Wiley / Science / PNAS 运行时要求时，读取 [`references/environment.md`](references/environment.md)。
- 当 MCP 不可用，或用户明确要求 shell 命令时，读取 [`references/cli-fallback.md`](references/cli-fallback.md)。
- 当结果为 `ambiguous`、`no_access`、`rate_limited` 或仅有元数据时，读取 [`references/failure-handling.md`](references/failure-handling.md)。
