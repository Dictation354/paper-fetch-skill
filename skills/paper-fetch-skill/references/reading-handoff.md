# 图件与材料交接

## 指定图件

先从正文路径及 image_index_path 找到目标图片。已有本地文件直接查看；只有远程链接时通过逐篇 manifest 定向补取：

```bash
paper-fetch fetch-assets --manifest /absolute/path/manifest.json --asset-id img_example
paper-fetch fetch-assets --manifest /absolute/path/manifest.json --kind formula
```

选择器互斥。命令返回下载后的实际路径，再用可用的图片 reader 打开。图注、链接或下载成功不能替代已看过图片的证据。

核对符号定义、公式或图中数值时阅读相关原始表达，并把解释限定在实际可见信息。PDF 以现有转换输出为边界，不追加内容清洗。

## 材料

读取附件时沿用用户文件或现有结果，必要时使用 `fetch --target supplementary --preset archive --query DOI` 获取。按格式交给合适的本地 reader，只报告实际读取的内容。
