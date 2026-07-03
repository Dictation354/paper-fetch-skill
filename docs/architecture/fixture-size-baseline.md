# Fixture Size Baseline

Date: 2026-05-22

本文件记录 tracked fixture 体积治理基线，并明确区分本地 ignored 杂物和已纳入 Git 的 fixture。本报告只建立可复核基线，不删除 fixture、不迁移 git-lfs、不改变测试读取路径。

## 本地 ignored 杂物

`scripts/clean-local-artifacts.sh --dry-run` 报告 `.pytest_cache`、`.ruff_cache`、`.mypy_cache`、`build`、`dist`、`.paper-fetch-runs`、`live-downloads`。这些目标由 `git check-ignore` 保护，清理它们不应产生 tracked diff。本报告不执行实际删除。

当前本地目录体积快照：

- `tests/fixtures`: 102M
- `legacy`: 69M，本地 ignored；`git ls-files legacy build` 为 0
- `build`: 2.9M，本地 ignored；`git ls-files legacy build` 为 0

## Tracked Fixture 快照

- `git ls-files tests/fixtures | wc -l`: 340
- 本报告 top 40 均来自工作树；`tracked` 以 `git ls-files tests/fixtures` 判断。

| Size | Path | Type | Provider | Tracked | Known references | Suggested action |
| --- | --- | --- | --- | --- | --- | --- |
| 14.3 MiB | `tests/fixtures/golden_criteria/10.3390_en16186655/original.pdf` | pdf | mdpi | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | lfs-evaluate |
| 9.8 MiB | `tests/fixtures/golden_criteria/10.48550_arxiv.2006.11239v2/original.pdf` | pdf | arxiv | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | lfs-evaluate |
| 2.6 MiB | `tests/fixtures/golden_criteria/10.1175_jcli-d-25-0547.1/original.pdf` | pdf | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | compress-evaluate |
| 2.0 MiB | `tests/fixtures/golden_criteria/10.1175_mwr-d-24-0060.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.8 MiB | `tests/fixtures/golden_criteria/10.1175_waf-d-24-0019.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.6 MiB | `tests/fixtures/golden_criteria/10.1175_jhm-d-23-0228.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.6 MiB | `tests/fixtures/golden_criteria/10.1175_aies-d-23-0093.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.5 MiB | `tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/body_assets/sciadv.adl6155-f2.jpg` | image/jpg | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | compress-evaluate |
| 1.5 MiB | `tests/fixtures/golden_criteria/10.1175_jpo-d-23-0234.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.5 MiB | `tests/fixtures/golden_criteria/10.1175_jcli-d-23-0738.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.4 MiB | `tests/fixtures/golden_criteria/10.1175_jtech-d-24-0028.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.3 MiB | `tests/fixtures/golden_criteria/10.1175_jamc-d-24-0048.1/original.html` | html | ams | yes | docs/extraction-rules.md<br>tests/fixtures/golden_criteria/manifest.json | minimize-evaluate |
| 1.3 MiB | `tests/fixtures/golden_criteria/10.1175_bams-d-24-0270.1/original.pdf` | pdf | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | compress-evaluate |
| 1.3 MiB | `tests/fixtures/golden_criteria/10.1175_bams-d-24-0223.1/original.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 1.1 MiB | `tests/fixtures/golden_criteria/10.1126_science.abp8622/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | minimize-evaluate |
| 977 KiB | `tests/fixtures/golden_criteria/10.5194_cp-1-1-2005/original.pdf` | pdf | copernicus | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | compress-evaluate |
| 922 KiB | `tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 810 KiB | `tests/fixtures/golden_criteria/10.48550_arxiv.2605.06653v1/original.html` | html | arxiv | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md<br>tests/unit/test_arxiv_provider.py | keep |
| 804 KiB | `tests/fixtures/golden_criteria/10.1175_bams-d-24-0270.1/landing.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 794 KiB | `tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/body_assets/sciadv.adl6155-f3.jpg` | image/jpg | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | compress-evaluate |
| 777 KiB | `tests/fixtures/golden_criteria/10.3390_s23010001/original.html` | html | mdpi | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 774 KiB | `tests/fixtures/golden_criteria/10.48550_arxiv.2605.06556v1/original.html` | html | arxiv | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md<br>tests/unit/test_scaffold_provider_from_manifest.py | keep |
| 758 KiB | `tests/fixtures/golden_criteria/10.1126_sciadv.adl6155/body_assets/sciadv.adl6155-f4.jpg` | image/jpg | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | compress-evaluate |
| 712 KiB | `tests/fixtures/golden_criteria/10.1126_sciadv.abf8021/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 710 KiB | `tests/fixtures/golden_criteria/10.1016_j.rse.2026.115369/original.xml` | xml | elsevier | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 705 KiB | `tests/fixtures/golden_criteria/10.1111_gcb.16561/original.html` | html | wiley | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 690 KiB | `tests/fixtures/golden_criteria/10.1126_sciadv.abj3309/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 679 KiB | `tests/fixtures/golden_criteria/10.3390_membranes15030093/original.html` | html | mdpi | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md<br>tests/devtools/test_golden_criteria_live.py<br>tests/unit/test_onboard_from_manifests.py | keep |
| 676 KiB | `tests/fixtures/golden_criteria/10.3390_math11030657/original.html` | html | mdpi | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 664 KiB | `tests/fixtures/golden_criteria/10.1126_science.adp0212/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 641 KiB | `tests/fixtures/golden_criteria/10.3390_su12072826/original.html` | html | mdpi | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 629 KiB | `tests/fixtures/golden_criteria/10.1126_sciadv.abg9690/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 614 KiB | `tests/fixtures/golden_criteria/10.1111_gcb.16745/original.html` | html | wiley | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 613 KiB | `tests/fixtures/golden_criteria/10.1126_sciadv.adm9732/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 609 KiB | `tests/fixtures/golden_criteria/10.1073_pnas.2310157121/original.html` | html | pnas | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 605 KiB | `tests/fixtures/golden_criteria/10.1111_gcb.16455/original.html` | html | wiley | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 603 KiB | `tests/fixtures/golden_criteria/10.1016_j.rse.2025.114648/original.xml` | xml | elsevier | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 594 KiB | `tests/fixtures/golden_criteria/10.1126_science.ady3136/original.html` | html | science | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 591 KiB | `tests/fixtures/golden_criteria/10.3390_rs16010010/original.html` | html | mdpi | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |
| 584 KiB | `tests/fixtures/golden_criteria/10.1175_jcli-d-25-0547.1/landing.html` | html | ams | yes | tests/fixtures/golden_criteria/manifest.json<br>docs/extraction-rules.md | keep |

## 治理规则

- `keep`: 当前 fixture 体积与覆盖价值匹配，保留原路径。
- `compress-evaluate`: 优先评估无损或可接受质量压缩，必须先确认对应 golden/unit 断言仍覆盖同一行为。
- `minimize-evaluate`: 优先裁剪 HTML/XML 中与断言无关的站点 chrome 或重复片段，必须保留真实结构证据。
- `lfs-evaluate`: 仅评估，不在本报告内迁移；迁移前需要确认安装、离线包和 CI checkout 策略。
- `reference-unknown` 表示自动引用识别没有找到稳定测试名，不代表可删除；处理前必须人工追踪调用链。
