# LST HTML replay review

来源：https://www.tandfonline.com/doi/full/10.1080/17538947.2022.2137254

2026-09-13 捕获页的离线节选保留完整 article DOM、DC/citation 元数据、原始 MathML、引用预览、布局表格、参考文献，以及同页 tfviewerdata 的 tables/figures。移除 article 外站点导航、会话脚本、iframe/input、事件处理器、nonce、注释及 data-registered；重建的唯一脚本只保存论文表格和图载荷，不含会话、身份认证或跟踪配置。浏览器捕获注入的行矩阵仍留在原 DOM，完整 colspan/rowspan 来自同页出版社载荷。

人工核对依据为原始 HTML，未用转换结果生成正确答案。`test_tandf_lst_render.py` 中逐式转录的操作数、运算符与下标是数学 oracle；允许现有 native/外部 MathML 后端的分组和间距差异。公式 1 的求和范围为 t，公式 2 的积分范围为 t₁ 至 t₂，3 为 NDVI 分式，4/5 按 HTML 的全部波段系数检查，6–13 检查各模型下标和全局/局部系数或函数。

特别保留公式 12 HTML 的 `LST_modelLPLS`，即使同段讨论 LRFR，也不替作者更改。正文的 `are are`、`inferered`、重复引用，以及温度范围 −30 至 −70 °C、表 2 的 `0.84 (0.97)+` 等原样保留。

核验范围：13 个编号公式各一次；11 处公式引用原位保留；11 个隐藏预览移除；61 个原始行内 MathML 保留结构；44 个主要正文段落顺序完整；a/b/c 子项；22 个有内容章节（含摘要、数据声明和利益冲突声明）；3 张表逐格展开原始跨度，表 2 表头为 PLSR/RFR × Global/Local strategy；12 图及图注按顺序；64 项参考文献逐项与 HTML 可见文本比较。

`expected.json` 沿用现有 golden article 摘要契约：它的 figures/tables 是独立 Asset 对象计数，此 adapter 未注入下载资产，因此为 0；正文内 12 图、3 表由结构断言验证。不得把该字段解释成正文没有图表。

执行面 replay 替换身份解析和 provider 网络传输，真实运行 DOM 清理、公式后端、ArticleModel、service、CLI、MCP、序列化、链接改写及文件保存。离线资产使用已有 JPEG 作为传输占位，不宣称是本篇真实图片；真实 12 张全尺寸图的证据来自独立 CLI 归档 manifest 和文件审计。
