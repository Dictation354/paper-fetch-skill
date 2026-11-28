# 图件与材料交接

## 指定图件

优先打开同一任务交接记录中的本地图片。按 `image_index_path` 找到缺失图片的 asset ID，再用原 manifest 定向补取。

有 `body_positions` 的公式图、插图和表格图可按位置筛选。行、列均从 1 开始，指向落盘正文中图片标记的起点。同一个 `asset_id` 在范围内多次出现时只需传一次。

```bash
paper-fetch fetch-assets --compact --manifest /absolute/path/manifest.json --asset-id img_first --asset-id img_second
paper-fetch fetch-assets --compact --manifest /absolute/path/manifest.json --kind formula
```

选择器互斥。用图片 reader 打开回执中成功项的实际路径。需要图注或下载诊断时读取 `details_path`。补图沿用原 manifest 的身份和索引，保留原始公式 fallback 验收。图注、链接或下载成功不能替代已看过图片的证据。

核对符号定义、公式或图中数值时阅读相关原始表达，并把解释限定在实际可见信息。PDF 以现有转换输出为边界，不追加内容清洗。

## 材料

读取附件时沿用用户文件或现有结果，必要时使用 `paper-fetch fetch --progress text --target supplementary --query DOI` 获取。按格式交给合适的本地 reader，只报告实际读取的内容。

根据 `target_satisfied`、acceptance.asset_summary 及实际路径区分仅发现链接、部分下载和完整下载；生命周期 `status=completed` 不表示全部附件已归档。

优先使用宿主已有 reader。没有 PDF reader 时，离线安装可用已定位的 CLI 执行 `doctor --catalog --json`，从 `runtime.installation_root` 取得安装目录。以下示例将 PDF 路径作为一个参数传入，在同目录生成同名 Markdown。

Unix 示例用系统的 `python3` 读取 JSON，用安装目录的私有解释器转换 PDF。将最后一个路径参数替换为实际 PDF 路径。

```bash
cli=$(command -v paper-fetch || echo "$HOME/.local/bin/paper-fetch")
install_root=$("$cli" doctor --catalog --json | python3 -c 'import json, sys; print(json.load(sys.stdin)["runtime"]["installation_root"])')
"$install_root/runtime/paper-fetch-python" - "/path to/supplement.pdf" <<'PYTHON'
from pathlib import Path
import sys
from paper_fetch.providers._pdf_common import render_pdf_markdown

pdf = Path(sys.argv[1])
pdf.with_suffix(".md").write_text(render_pdf_markdown(pdf), encoding="utf-8")
PYTHON
```

Windows PowerShell 中，`$cli` 使用已定位的启动器路径。命令在 PATH 时可直接使用下例。

```powershell
$cli = (Get-Command paper-fetch).Source
$catalog = (& $cli doctor --catalog --json | Out-String | ConvertFrom-Json)
$python = Join-Path $catalog.runtime.installation_root 'runtime\python.exe'
@'
from pathlib import Path
import sys
from paper_fetch.providers._pdf_common import render_pdf_markdown

pdf = Path(sys.argv[1])
pdf.with_suffix(".md").write_text(render_pdf_markdown(pdf), encoding="utf-8")
'@ | & $python - 'C:\path to\supplement.pdf'
```

源码 checkout 从仓库根目录调用项目解释器（Unix 为 `.venv/bin/python`，Windows 为 `.venv\python.exe`）执行同一段转换代码。打开生成的 Markdown，按 reader 的实际返回范围续读，保留转换器原始输出。

需要在离线安装的私有 Python（`runtime/paper-fetch-python`）中渲染或裁剪本地 PDF 页面时，使用随包提供的 PyMuPDF（`import pymupdf`），包内没有 PIL/Pillow。
