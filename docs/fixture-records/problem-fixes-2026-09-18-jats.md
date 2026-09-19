# P19 / P22：JATS 定向修复（2026-09-18）

## P19：PLOS 行内公式

两篇原文分别含 1、7 个 `inline-formula > inline-graphic`，均有同篇 `info:doi` 资产身份。共享公式图片读取原先只识别 `graphic`；现在也识别公式容器内的 `inline-graphic`，普通行内图片不因此成为公式。PLOS 专属 XML 入口复用已有官方公式图片路由，将 `.eNNN`／`.exNNN` 解析为 `article/file?id=…&type=thumbnail`；下载候选正确读取 URL 的 `id` 参数，避免重复追加 query。

- [pbio.0040298 新捕获 XML](../../tests/fixtures/golden_criteria/10.1371_journal.pbio.0040298/acquisition/source-completion-2026-09-18/001-http_response_entity.xml)：98416 bytes；SHA-256 `31d798caba6926134c0d4109b50eb521673f46e7f999000bb0f6cdc450a93686`。唯一 inline 图片 `journal.pbio.0040298.ex001`；另有三个原有 display 公式图片，因此全文 fallback=4、missing=0。
- [pcbi.1003118 原始 XML](../../tests/fixtures/golden_criteria/10.1371_journal.pcbi.1003118/original.xml)：87509 bytes；SHA-256 `5bc10955e1774bbd49685a3a0bd7ac6d4fce9ff613051ac47b5616af8cd01daf`。七个 inline 图片 `journal.pcbi.1003118.e001` 至 `e007`；全文 fallback=7、missing=0。

八处图片的身份、顺序、正文前后位置、官方输出地址及资产候选均由源 XML 独立断言。MathML／TeX 优先；缺少或异篇 DOI 不伪造图片。保留旧 display `graphic` 行为。证据证明官方可追溯链接和下载候选，不证明本次取得 GIF／PNG 像素，不做 OCR。

## P22：Copernicus 空引文

[hess-28-1-2024 原始 XML](../../tests/fixtures/golden_criteria/10.5194_hess-28-1-2024/original.xml)：228041 bytes；SHA-256 `ef4c6556896f83469dcf22d45b3088da275da4cab610c75d269ebb792b25c435`。

正文有 90 个 bibr xref，其中 83 个空文本节点通过 rid 指向 101 个书目目标；其余七个已有文字保留。声明中的 `paren.91` 另指向 `bib1.bibx76`，故全文恢复 102 个关联，而非增加参考文献条目。书目已有作者年份 natbib label；仅移除其后附加的展开作者列表，使用已有短标签，不猜测作者或编号。例：`paren.45 → bib1.bibx20 → Hargreaves and Samani (1982)`。

Copernicus owner 在解析副本中恢复空标签，逐个多目标按源顺序展开；复用既有对象链接 helper 指向同篇官方 XML 的书目 ID。未知目标显示 `[Reference unavailable: …]`；目标存在但无 label 时保留明确的源书目 ID。已有文字、其他 xref 类型和调用者原始 XML 不修改。真实回归逐项核对 83 个节点的位置和 101 个目标，另核验声明目标；`include_refs=all/partial/none` 全部保持这 102 个关联。

## 验证

- [最小 unit](../../tests/unit/test_jats_problem_fixes.py)：公式类型和源数据优先级、缺失／异篇资产、官方下载候选；多目标／无效目标／已有 label／无源 URL／非 bibr／原树不变。
- [真实全文 golden](../../tests/golden/test_jats_problem_fixes.py)：三篇源身份、原始对象计数、逐对象输出与位置、引用过滤；不读取输出快照推导预期。
- P19 初轮修正后：9 passed；既有 PLOS golden 通过。
- 两 provider unit/golden 相关范围：34 passed，另一个计数断言发现原文声明中的第 102 个目标，已依据源 XML 修正。
- 最终新增 unit/golden 与 PLOS／Copernicus canonical summary：31 passed。canonical summary 无需改动，未更新 expected.json 或 Markdown 快照。
- 默认并行；Ruff、diff 检查通过。定向 mypy 的六条报错均在既存的 builders/fulltext/PLOS 下载资产代码，本次新增段落未报错，已告知主代理。

测试证据登记已更新；未更改 PDF、版本、CI 或全局策略。

后续阶段：本记录保留当时的离线验证与证据边界；当天稍后新增的真实图片/SVG响应、PLOS实体组装修复及实际分母见 [最终资产补证](problem-fixes-2026-09-18-asset-evidence.md)。此链接不把最初离线验证改写为联网结果。
