# 图件与材料交接

## 指定图件

优先打开同一任务交接记录中的本地图片。按 `image_index_path` 找到缺失图片的 asset ID，再用原 manifest 定向补取。

Wiley HTML 公式图的 `body_positions` 指向落盘正文中图片标记的起点，行、列均从 1 开始。根据已读的行范围和行内位置筛选相关公式，同一个 `asset_id` 在范围内多次出现时只需传一次。

```bash
paper-fetch fetch-assets --compact --manifest /absolute/path/manifest.json --asset-id img_first --asset-id img_second
paper-fetch fetch-assets --compact --manifest /absolute/path/manifest.json --kind formula
```

选择器互斥。用图片 reader 打开回执中成功项的实际路径。需要图注或下载诊断时读取 `details_path`。补图沿用原 manifest 的身份和索引，保留原始公式 fallback 验收。图注、链接或下载成功不能替代已看过图片的证据。

核对符号定义、公式或图中数值时阅读相关原始表达，并把解释限定在实际可见信息。PDF 以现有转换输出为边界，不追加内容清洗。

## 材料

读取附件时沿用用户文件或现有结果，必要时使用 `paper-fetch fetch --progress text --target supplementary --query DOI` 获取。按格式交给合适的本地 reader，只报告实际读取的内容。


根据 `target_satisfied`、acceptance.asset_summary 及实际路径区分仅发现链接、部分下载和完整下载；生命周期 `status=completed` 不表示全部附件已归档。

优先使用宿主已有 reader。没有 PDF reader 时，先定位实际安装目录及其 Python：Unix 从 `command -v paper-fetch` 找到启动器并查看其安装路径，使用该安装目录的 `runtime/paper-fetch-python`；Windows 从 `Get-Command paper-fetch` 找到启动器，使用相应安装目录的 `runtime/python.exe`；源码 checkout 使用根目录 `.venv/bin/python`。启动器可能是符号链接或包装脚本，需沿其真实目标定位，不能假定宿主 Python 已有依赖。

用选定的解释器复用现有 PDF 转换能力，例如 Unix 离线安装：

```bash
"/actual/install/runtime/paper-fetch-python" - <<'PYTHON'
from pathlib import Path
from paper_fetch.providers._pdf_common import render_pdf_markdown
pdf = Path("/absolute/path/supplement.pdf")
text = render_pdf_markdown(pdf)
pdf.with_suffix(".md").write_text(text, encoding="utf-8")
PYTHON
```

Windows 可将同一段 Python 保存为脚本，再用 `& 'C:\actual\install\runtime\python.exe' script.py` 执行。打开生成的 Markdown，按 reader 的实际返回范围续读；不对转换结果清洗或修复。
