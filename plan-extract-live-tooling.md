# 计划：把 live tooling 从 `paper_fetch` 包搬出去

Date: 2026-04-29
Status: proposed
Owner: 待指定

## 背景

`src/paper_fetch/` 当前夹杂了四个 dev-only / live-only 模块，它们随 wheel 一起被打包安装，但 README、`docs/architecture/target-architecture.md`、`docs/providers.md` 都已经把它们定义为 "repo-local internal tooling，不暴露 console script、不作为 MCP surface、不进入 public API"：

| 文件 | 行数 | 角色 |
| --- | --- | --- |
| `src/paper_fetch/golden_criteria_live.py` | 1300 | golden corpus live review 业务逻辑 |
| `src/paper_fetch/golden_criteria_live_cli.py` | 70 | 上面那一份的 CLI 包装 |
| `src/paper_fetch/geography_live.py` | 696 | 自然地理 live publisher 报告业务逻辑 |
| `src/paper_fetch/geography_issue_artifacts.py` | 347 | geography 报告的 issue 工件导出 |

它们和 `paper_fetch.cli` / `paper_fetch.mcp.server` / `paper_fetch.service` 等 product surface 没有运行时依赖关系，反向却在 import 核心包来跑 in-process live review。当前形态有 3 个具体问题：

1. **打包污染**：`pip install paper-fetch-skill` 后这 4 个文件会进 site-packages，拖大 wheel，模糊"对外 API"边界。
2. **导入路径暴露**：外部代码可以 `from paper_fetch.golden_criteria_live import ...`，无意中把 dev-only 接口当作稳定 API 用。
3. **测试归属混乱**：`tests/unit/test_golden_criteria_live.py`、`tests/unit/test_geography_live.py`、`tests/unit/test_geography_issue_artifacts.py` 名义上是单元测试，实际验证的是 dev tooling，跟 product surface 单测放在同一目录下增加阅读成本。

## 目标

- **完全把 live tooling 从 wheel 中移除**：`pip install` 之后不应包含 `geography_live` / `golden_criteria_live*` / `geography_issue_artifacts` 任一模块。
- **保留所有现有 entrypoint 行为不变**：`scripts/run_geography_live_report.py`、`scripts/run_golden_criteria_live_review.py`、`scripts/export_geography_issue_artifacts.py`、`scripts/group_geography_issue_artifacts.py` 调用方式、参数、产物路径都不能变。
- **保留所有现有 test 行为不变**：`pytest tests/unit/test_geography_live.py tests/unit/test_geography_issue_artifacts.py tests/unit/test_golden_criteria_live.py` 仍可在源树内正常跑通；live tests `tests/live/test_live_geography_publishers.py` 仍可由 `PAPER_FETCH_RUN_LIVE=1` 触发。
- **保留 `paper_fetch.providers` 和 `paper_fetch.workflow` 等核心模块对 live tooling 零依赖**（已经满足，本计划不改）。

## 非目标

- 不重写 live tooling 内部逻辑（只搬位置）。
- 不改变 `tests/unit/` vs `tests/integration/` vs `tests/live/` 的 pytest 收集策略。
- 不改 README 主体业务部分；只补一句指向新位置的引用更新。
- 不发 PyPI；当前分发渠道仍为 `install.sh` / `install-offline.sh` / `pip install .`。

## 现状盘点（依赖关系）

### 模块间内部依赖

```text
golden_criteria_live_cli.py
   └─→ golden_criteria_live.py
          └─→ geography_live.py  (is_authorless_briefing_like)

geography_issue_artifacts.py
   └─→ geography_live.py  (GeographySample, build_report_result)

geography_live.py
   └─→ paper_fetch.{service, models, providers, ...}  (核心包，单向依赖)
```

四者构成一个独立 cluster，对核心包是单向依赖，零反向依赖。可以整体外迁。

### 仓库内调用点

- **scripts/**（4 处，都是 importlib 或 module-level import）
  - `scripts/run_geography_live_report.py` → `paper_fetch.geography_live`
  - `scripts/run_golden_criteria_live_review.py` → `paper_fetch.golden_criteria_live_cli`
  - `scripts/export_geography_issue_artifacts.py` → `paper_fetch.geography_issue_artifacts`
  - `scripts/group_geography_issue_artifacts.py` → `paper_fetch.geography_issue_artifacts`
- **tests/**（6 个文件）
  - `tests/unit/test_geography_live.py`
  - `tests/unit/test_geography_issue_artifacts.py`
  - `tests/unit/test_golden_criteria_live.py`
  - `tests/unit/test_science_pnas_provider.py`（仅 import 一个 helper：`from paper_fetch.geography_live import collect_issue_flags`）
  - `tests/live/test_live_geography_publishers.py`
  - `tests/live/geography_samples.py`
- **docs/**（README.md、CHANGELOG.md、docs/providers.md、docs/extraction-rules.md 中提到这些 script 名或 test 名 —— **这些是路径字符串，不是 import**，路径如果不变则文档不用动）。

### 一处需要单独处理的"核心包到 live"反向引用

`tests/unit/test_science_pnas_provider.py` 引用了 `paper_fetch.geography_live.collect_issue_flags`。从命名看 `collect_issue_flags` 既被 geography 用，又被 science_pnas 单测用 —— 这是一个本应属于 product surface 的 helper 被错放到了 live tooling 里。**搬包之前先把这个 helper 抽到核心**（见步骤 1），避免 science_pnas 单测产生对 dev-tooling 包的反向依赖。

## 方案

### 选型：sibling top-level 包，而不是 `paper_fetch._dev` 子模块

考虑过两个方案：

| 方案 | 评价 |
| --- | --- |
| A. 留在 `paper_fetch._dev/` 子包，靠 `pyproject.toml` 的 `setuptools.packages.find` 排除 | `find` 排除子包写法脆，且 `paper_fetch.X` 路径仍存在风险被 import；不能彻底切断 |
| B. **新建顶层 sibling 包 `paper_fetch_devtools/`，与 `paper_fetch/` 并列在 `src/`** | wheel 完全不包含；import path 是 `paper_fetch_devtools.*`，namespace 一目了然；测试和 scripts 的修改面也最小（只是改 import string） |

**采用方案 B。** 包名 `paper_fetch_devtools` 带 `devtools` 后缀，明确"开发期内部工具"。

### 目录目标布局

```text
src/
  paper_fetch/                          # 不变；product surface
    cli.py
    service.py
    mcp/...
    workflow/...
    providers/...
    ...
  paper_fetch_devtools/                 # 新增；dev-only
    __init__.py
    geography/
      __init__.py
      live.py                           # 原 geography_live.py
      issue_artifacts.py                # 原 geography_issue_artifacts.py
    golden_criteria/
      __init__.py
      live.py                           # 原 golden_criteria_live.py
      cli.py                            # 原 golden_criteria_live_cli.py
tests/
  devtools/                             # 新增；dev-tooling 单测
    __init__.py
    test_geography_live.py              # 原 tests/unit/test_geography_live.py
    test_geography_issue_artifacts.py   # 原 tests/unit/test_geography_issue_artifacts.py
    test_golden_criteria_live.py        # 原 tests/unit/test_golden_criteria_live.py
  unit/
    test_science_pnas_provider.py       # 改 import 后保留
  live/
    test_live_geography_publishers.py   # 改 import
    geography_samples.py                # 改 import
scripts/
  run_geography_live_report.py          # 改 import
  run_golden_criteria_live_review.py    # 改 import
  export_geography_issue_artifacts.py   # 改 import
  group_geography_issue_artifacts.py    # 改 import
pyproject.toml                          # 排除 paper_fetch_devtools 出 wheel
```

### `tests/devtools/` 是否进默认 pytest 收集

当前 `pyproject.toml` 的 `[tool.pytest.ini_options].testpaths = ["tests/unit", "tests/integration"]`。

**新目录 `tests/devtools/` 应进 testpaths**，否则 `pytest` 默认就跑不到它们 —— 这会偷偷扩大覆盖盲区。把它加入 `testpaths`，与 `tests/unit` 并列。

```toml
[tool.pytest.ini_options]
addopts = "-n auto"
testpaths = [
  "tests/unit",
  "tests/integration",
  "tests/devtools",
]
```

### `pyproject.toml` 调整

当前：

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

调整为：

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["paper_fetch*"]
exclude = ["paper_fetch_devtools*"]
```

`include = ["paper_fetch*"]` 防止未来再无意打包到 sibling 包；`exclude` 是 belt-and-suspenders。验证手段：`python3 -m build --wheel && unzip -l dist/paper_fetch_skill-*.whl | grep -i devtools` 应 0 命中。

### 是否还需要在 `src/paper_fetch/` 留 shim？

**不需要。**这些模块从来不是 public API，没有 CHANGELOG 条目对它们的 import path 做稳定承诺。直接断掉 `paper_fetch.geography_live` 等导入路径，外部如果有人误用会立即在 ImportError 处暴露出来，比沉默 deprecate 更好。

### `collect_issue_flags` 的归属处理

步骤 1 会先把它从 `geography_live.py` 抽到核心包合适位置。候选位置：

- 如果 `collect_issue_flags` 输入是 `FetchEnvelope` / `ArticleModel` 字段并产出 issue 标签，归 `paper_fetch.quality.html_availability` 或 `paper_fetch.quality.issues`（新建子模块）。
- 如果只是 science_pnas 测试用的辅助，可以归到 `paper_fetch.providers.science_pnas._issue_flags` 并由 geography_live 反向 import 它。

**实施时先读 `collect_issue_flags` 实现**，根据它实际依赖的字段决定。无论选哪个位置，最终结果都是：核心包有它，live tooling 反向 import；test_science_pnas_provider.py 改成 import 核心位置。

## 实施步骤

### Step 0：基线

```bash
PYTHONPATH=src pytest tests/unit tests/integration -x
PYTHONPATH=src python3 scripts/run_geography_live_report.py --help
PYTHONPATH=src python3 scripts/run_golden_criteria_live_review.py --help
PYTHONPATH=src python3 scripts/export_geography_issue_artifacts.py --help
PYTHONPATH=src python3 scripts/group_geography_issue_artifacts.py --help
```

四个 `--help` 命令 + 单测应全绿；这是回归基线。

### Step 1：先把 `collect_issue_flags` 提到核心包

1. `Read` `src/paper_fetch/geography_live.py` 中 `collect_issue_flags` 的定义和上下游。
2. 把它整体移到（按实现实际依赖择一）：
   - `src/paper_fetch/quality/issues.py`（新文件），或
   - `src/paper_fetch/providers/science_pnas/_issue_flags.py`。
3. 在原位置 `geography_live.py` 改成 `from paper_fetch.quality.issues import collect_issue_flags`（或 science_pnas 路径）。
4. 把 `tests/unit/test_science_pnas_provider.py` 的 import 改到核心包新位置。
5. 跑 `PYTHONPATH=src pytest tests/unit/test_science_pnas_provider.py tests/unit/test_geography_live.py -x`，应全绿。
6. 提交独立 commit：`refactor: move collect_issue_flags to product surface`。

### Step 2：创建 `paper_fetch_devtools/` 骨架并搬模块

1. `mkdir -p src/paper_fetch_devtools/geography src/paper_fetch_devtools/golden_criteria`
2. 写空 `__init__.py`（顶层和两个子包）。
3. 用 `git mv` 保留历史：

   ```bash
   git mv src/paper_fetch/geography_live.py            src/paper_fetch_devtools/geography/live.py
   git mv src/paper_fetch/geography_issue_artifacts.py src/paper_fetch_devtools/geography/issue_artifacts.py
   git mv src/paper_fetch/golden_criteria_live.py      src/paper_fetch_devtools/golden_criteria/live.py
   git mv src/paper_fetch/golden_criteria_live_cli.py  src/paper_fetch_devtools/golden_criteria/cli.py
   ```
4. 更新四个文件内部的相对 import：
   - `paper_fetch_devtools/geography/issue_artifacts.py`：`from .live import GeographySample, build_report_result`（原来是 `from .geography_live import ...`）
   - `paper_fetch_devtools/golden_criteria/live.py`：`from paper_fetch_devtools.geography.live import is_authorless_briefing_like`（跨子包，用绝对 import）
   - `paper_fetch_devtools/golden_criteria/cli.py`：`from paper_fetch_devtools.golden_criteria.live import (...)`
   - 仍引用 `paper_fetch` 核心 API 的地方（绝对 import）保持不变。
5. 提交：`refactor: move live tooling out of paper_fetch package`。

### Step 3：更新所有外部调用点

#### scripts/

| 文件 | 旧 import | 新 import |
| --- | --- | --- |
| `scripts/run_geography_live_report.py` | `from paper_fetch.geography_live import (GEOGRAPHY_PROVIDER_ORDER, default_report_paths, run_geography_live_report)` | `from paper_fetch_devtools.geography.live import ...` |
| `scripts/run_golden_criteria_live_review.py` | `from paper_fetch.golden_criteria_live_cli import main` | `from paper_fetch_devtools.golden_criteria.cli import main` |
| `scripts/export_geography_issue_artifacts.py` | `from paper_fetch.geography_issue_artifacts import (default_issue_artifact_output_dir, export_geography_issue_artifacts)` | `from paper_fetch_devtools.geography.issue_artifacts import ...` |
| `scripts/group_geography_issue_artifacts.py` | `from paper_fetch.geography_issue_artifacts import ...` | `from paper_fetch_devtools.geography.issue_artifacts import ...` |

注意：所有 4 个 scripts 都已经在文件顶部 `sys.path.insert(0, str(SRC_DIR))`，因为新包也在 `src/` 下，sys.path 不用动。

#### tests/

| 文件 | 旧 import | 新 import |
| --- | --- | --- |
| `tests/live/test_live_geography_publishers.py` | `from paper_fetch.geography_live import GEOGRAPHY_PROVIDER_ORDER, GEOGRAPHY_RESULT_STATUSES, run_geography_live_report` | `from paper_fetch_devtools.geography.live import ...` |
| `tests/live/geography_samples.py` | `from paper_fetch.geography_live import GEOGRAPHY_PROVIDER_ORDER, GeographySample` | `from paper_fetch_devtools.geography.live import ...` |
| `tests/unit/test_geography_live.py` | `from paper_fetch.geography_live import (...)` | `from paper_fetch_devtools.geography.live import (...)` |
| `tests/unit/test_geography_issue_artifacts.py` | `from paper_fetch.geography_issue_artifacts import collect_issue_rows, materialize_issue_type_view, schedule_issue_rows` | `from paper_fetch_devtools.geography.issue_artifacts import ...` |
| `tests/unit/test_golden_criteria_live.py` | `from paper_fetch import golden_criteria_live_cli` + `from paper_fetch.golden_criteria_live import (...)` | `from paper_fetch_devtools.golden_criteria import cli as golden_criteria_live_cli` + `from paper_fetch_devtools.golden_criteria.live import (...)` |

`tests/unit/test_science_pnas_provider.py` 在 Step 1 已处理，不再涉及 live tooling。

#### tests/ 文件搬位置

```bash
mkdir -p tests/devtools
git mv tests/unit/test_geography_live.py            tests/devtools/test_geography_live.py
git mv tests/unit/test_geography_issue_artifacts.py tests/devtools/test_geography_issue_artifacts.py
git mv tests/unit/test_golden_criteria_live.py      tests/devtools/test_golden_criteria_live.py
touch tests/devtools/__init__.py
```

提交：`test: relocate dev-tooling tests under tests/devtools`。

### Step 4：`pyproject.toml` 收紧 packaging 边界

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["paper_fetch*"]
exclude = ["paper_fetch_devtools*"]

[tool.pytest.ini_options]
addopts = "-n auto"
testpaths = [
  "tests/unit",
  "tests/integration",
  "tests/devtools",
]
```

提交：`build: exclude paper_fetch_devtools from wheel and add devtools test path`。

### Step 5：文档同步（最小改动）

只更改硬性失效的引用。**Script 文件名没变** → README 与 CHANGELOG 中 `python3 scripts/run_*.py` 的命令行不需要改。

需要更新的：

- `docs/architecture/target-architecture.md` 第 1 节"状态说明"列出 `paper_fetch.*` 入口时不曾提到这 4 个文件，**无需改动**。
- `docs/providers.md` 第 36–40 行只引用了 `scripts/run_geography_live_report.py` 这种文件路径，**无需改动**。
- `docs/extraction-rules.md` 引用 `tests/unit/test_golden_criteria_live.py` —— 该文件已搬到 `tests/devtools/test_golden_criteria_live.py`，**这里要更新路径**。
- `CHANGELOG.md` 的 "How tested" 块里提到 `pytest tests/unit/test_golden_criteria_live.py` —— **历史 changelog 不要改**，新增一条新条目说明本次迁移：

  ```markdown
  ## Unreleased
  ### Refactor
  - Move dev-only `geography_live` / `geography_issue_artifacts` / `golden_criteria_live*` modules
    from `paper_fetch.*` to a sibling top-level package `paper_fetch_devtools.*`. Wheel no longer
    ships these modules. All four `scripts/run_*.py` and `scripts/export_*.py` entrypoints keep
    the same CLI surface.
  ```

提交：`docs: point to relocated dev-tooling test paths`。

### Step 6：回归验证

```bash
# 1. 单测全绿
PYTHONPATH=src pytest tests/unit tests/integration tests/devtools -x

# 2. 4 个 dev script 仍可启动
PYTHONPATH=src python3 scripts/run_geography_live_report.py --help
PYTHONPATH=src python3 scripts/run_golden_criteria_live_review.py --help
PYTHONPATH=src python3 scripts/export_geography_issue_artifacts.py --help
PYTHONPATH=src python3 scripts/group_geography_issue_artifacts.py --help

# 3. 核心 entrypoint 行为不变
paper-fetch --query "10.1186/1471-2105-11-421" --no-download | head -20
paper-fetch-mcp < /dev/null  # 应正常启动 stdio loop（用 ctrl-c 退出即可）

# 4. wheel 验证：dev tooling 不应进 wheel
python3 -m pip install build
python3 -m build --wheel
unzip -l dist/paper_fetch_skill-*.whl | grep -E "(geography_live|golden_criteria_live|geography_issue_artifacts|paper_fetch_devtools)"
# 期望输出：空（只能找到 paper_fetch 命名空间下的文件，找不到任何 devtools / live tooling）

# 5. import 防护：从一个新解释器，确认 paper_fetch 命名空间不再暴露这些模块
python3 -c "import paper_fetch.geography_live" 2>&1 | grep ModuleNotFoundError
python3 -c "import paper_fetch.golden_criteria_live" 2>&1 | grep ModuleNotFoundError
# 期望：两条都报 ModuleNotFoundError
```

### Step 7：提交聚合

按上面拆出的 5 个独立 commit 做小步合并；如果分支策略需要单 PR，把它们打包到一个 PR 里，PR 描述列出本计划链接。**不要一锅 commit**：保留 `git mv` 的历史可追溯性比短暂的 commit 历史更重要。

## 风险与回滚

### 风险 1：external 集成方依赖 `paper_fetch.geography_live` 等路径

- **可能性**：低。这些模块从未在 README、SKILL.md、MCP tool schema、`paper_fetch/__init__.py` 公开 API 中出现过。
- **缓解**：如果担心，可以在 Step 2 完成后保留过渡 shim：
  ```python
  # src/paper_fetch/geography_live.py（过渡）
  import warnings
  warnings.warn(
      "paper_fetch.geography_live moved to paper_fetch_devtools.geography.live "
      "and will be removed from the wheel in the next release.",
      DeprecationWarning,
      stacklevel=2,
  )
  from paper_fetch_devtools.geography.live import *  # noqa: F401,F403
  ```
  但**不推荐**：留 shim 等于不解决"打包污染"这个核心问题。建议直接移除，让任何外部误用立刻失败。

### 风险 2：CI 配置硬编码了 `tests/unit/test_*live*.py` 路径

- **可能性**：中。需要 grep 一遍 `.github/workflows/`、`.codex` 类配置。
- **缓解**：Step 0 之前先 `grep -rn "test_geography_live\|test_geography_issue_artifacts\|test_golden_criteria_live" .github/ scripts/ Makefile* 2>/dev/null`，如有命中按 Step 3 同步更新。

### 风险 3：`tests/devtools/` 没进 pytest 默认 testpaths 导致测试静默漏跑

- **可能性**：高，如果忘了改 `pyproject.toml` 的 `testpaths`。
- **缓解**：Step 4 必须做；Step 6 第 1 条命令显式带上 `tests/devtools` 验证。

### 回滚

每一步都是独立 commit。回滚只需 `git revert <commit>` —— 因为用了 `git mv`，revert 自动恢复文件位置。

## 验收标准（DoD）

- [ ] `PYTHONPATH=src pytest tests/unit tests/integration tests/devtools -x` 全绿。
- [ ] 4 个 `scripts/run_*.py` / `scripts/export_*.py` / `scripts/group_*.py` 的 `--help` 仍正常输出。
- [ ] `paper-fetch --query <doi>` 和 `paper-fetch-mcp` 行为不变。
- [ ] `python3 -m build --wheel` 产出的 wheel 不包含 `paper_fetch_devtools/` 任何文件，也不包含 `paper_fetch.geography_live` / `paper_fetch.golden_criteria_live*` / `paper_fetch.geography_issue_artifacts`。
- [ ] `python3 -c "import paper_fetch.geography_live"` 报 `ModuleNotFoundError`。
- [ ] `python3 -c "import paper_fetch_devtools.geography.live; import paper_fetch_devtools.golden_criteria.cli"` 成功（仅在源树或 dev install 中）。
- [ ] `tests/unit/test_science_pnas_provider.py` 不再 import `paper_fetch.geography_live`，改为 import 核心包中 `collect_issue_flags` 的新位置。
- [ ] CHANGELOG 有一条 "Unreleased > Refactor" 记录此次迁移。

## 预估工作量

- Step 1（抽 helper）：30 分钟（含读代码定位归属）
- Step 2（git mv + 内部 import 修复）：15 分钟
- Step 3（更新 4 scripts + 6 tests，搬测试目录）：20 分钟
- Step 4（pyproject.toml）：5 分钟
- Step 5（文档）：10 分钟
- Step 6（回归 + wheel 验证）：20 分钟

合计约 1.5 小时，纯机械搬迁，无业务逻辑改动。
