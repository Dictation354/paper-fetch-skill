# 材料与图件交接

paper-fetch 提供已知论文的正文、材料清单及文件/URL；阅读使用宿主已有 reader。按问题选择范围，复用已取得的文件，不为附件或单张图重新 fetch 整篇。

## 附件

先从当前句柄 diagnostics 的 supplementary.assets、已有索引或用户指定路径/URL 确定文件。已有本地文件直接交给宿主 PDF、表格或文档 reader；远程附件只获取所需文件。记录论文身份、材料名称、来源和阅读页段供追问复用。用户指定审稿 PDF 时同样处理；peer-review 文件不在默认 supplementary 范围，不据此报告材料漏抓。

DOCX 没有宿主 reader 时可用标准库读取段落和表格中的文本：

```python
from zipfile import ZipFile
from xml.etree import ElementTree as ET

with ZipFile(path) as document:
    root = ET.fromstring(document.read("word/document.xml"))
ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
paragraphs = [
    "".join(t.text or "" for t in p.findall(".//w:t", ns))
    for p in root.findall(".//w:p", ns)
]
print("\n".join(paragraphs))
```

PDF 使用宿主 reader 按实际页段读取，不追加 PDF 清洗、OCR 或转换修复。

## 指定图件

问题依赖公式定义、符号、图内系数、误差条或面板标记时，实际读取相应表达或图片。从已有 Markdown 的 Figure 编号、图注和图片 URL，或 diagnostics 的 `image_index` / `assets` 的 asset_id、heading、caption、source_url、path 确定目标。优先复用已有文件或已返回的 ImageContent；图片链接、图注和周围文字不能替代公式原文核验。

缺少所需图片时调用 `fetch_assets`，三种选择方式互斥：指定 asset_id、已识别的图片 URL，或公式图片组。单图补取不会下载其他图片，公式组只选择已识别的公式图片。

```javascript
const images = await callTool("fetch_assets", {
  content_id: saved.content_ref.content_id, kind: "formula"
  // 单图可改用 asset_ids: ["img_..."] 或 urls: ["已识别的图片URL"]
});
text(images.structuredContent);
for (const content of images.content ?? []) {
  if (content.type === "image") image(content); // 显式转发 ImageContent
}
```

默认最多内联 3 张、单张 2 MiB、累计 8 MiB；每项 `inline` / `inline_reason` 说明实际交付情况。未内联的已下载图片仍返回 `path`，交给宿主图像 reader，例如 `view_image(path="返回的图片路径")`。MCP 临时文件归句柄所有，随句柄过期、淘汰或服务关闭清理；需要持久保留时指定 `output_dir`。重复补取复用已有文件。补图不会改变正文快照、字符偏移或原获取验收；失败和来源逐项记录。

CLI：

```bash
paper-fetch fetch-assets --query "10.1038/nclimate1907" --kind formula
paper-fetch fetch-assets --query "论文DOI" --asset-url "已识别的图片URL" --output-dir ./images
```

CLI stdout 是包含身份、逐项状态、来源及实际路径的 JSON，诊断写 stderr。默认文件留在系统临时目录，命令结束后仍可交给宿主 reader；显式目录用于归档，已有不同文件须 `--overwrite` 才覆盖。

`image_delivery` 的 `formula_images` 依据最终 Markdown 中已识别的公式图片引用计数；`discovery_complete=false` 时，零计数不能解释为没有公式图片。`local_images` 与本次实际返回的 `returned_images` 分开统计。交付图片不等于调用方已阅读；保留论文身份、公式或面板编号及实际来源供追问复用。PDF 图件继续使用宿主 PDF reader，不新增解析、OCR、图表数字化或转换修复。
