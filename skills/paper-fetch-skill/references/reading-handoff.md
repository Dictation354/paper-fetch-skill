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
paragraphs = ["".join(t.text or "" for t in p.findall(".//w:t", ns))
              for p in root.findall(".//w:p", ns)]
print("\n".join(paragraphs))
```

PDF 使用宿主 reader 按实际页段读取，不追加 PDF 清洗、OCR 或转换修复。

## 指定图件

只有问题依赖图内系数、误差条或面板标记时看图。从已有 Markdown 的 Figure 编号、图注和图片 URL，或 diagnostics/assets 的 heading/caption/source_url/path 确定目标。优先复用已有文件或工具返回的 ImageContent，调用宿主图像工具读取指定面板，例如 `view_image(path="已有的Figure6.png")`；保留 Figure 6e、论文身份和实际来源供追问复用。

远程图片打不开时只获取该图到临时路径再交给图像 reader。无需下载全部资产，不从图注推测图内数值，也不新增图表数字化框架。
