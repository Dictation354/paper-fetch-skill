from __future__ import annotations

from paper_fetch.http import RequestErrorCategory
from paper_fetch.mcp._instructions import ERROR_CONTRACT
from paper_fetch.mcp.prompts import (
    summarize_paper_prompt,
    verify_citation_list_prompt,
)
from paper_fetch.reason_codes import (
    ERROR,
    NO_ACCESS,
    NO_RESULT,
    NOT_CONFIGURED,
    NOT_SUPPORTED,
    RATE_LIMITED,
)
from tests.paths import SKILL_DIR


FAILURE_HANDLING_PATH = SKILL_DIR / "references" / "failure-handling.md"
TOOL_CONTRACT_PATH = SKILL_DIR / "references" / "tool-contract.md"


def test_failure_handling_is_the_complete_agent_retry_fact_source() -> None:
    failure_handling = FAILURE_HANDLING_PATH.read_text(encoding="utf-8")
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    assert "唯一长规则事实源" in failure_handling
    assert "初次尝试 + 2 次有意义的重试" in failure_handling
    assert "最多 3 次工具调用尝试" in failure_handling
    assert "底层 HTTP transport" in failure_handling
    assert "Retry-After、5xx" in failure_handling
    assert "不要修改底层 HTTP retry 算法" in failure_handling
    assert "## Error Contract" in failure_handling
    assert "### 失败决策表" in failure_handling
    assert "触发条件" in failure_handling
    assert "参数/状态变化" in failure_handling
    assert "终止条件" in failure_handling
    assert "用户报告字段" in failure_handling
    assert "references/failure-handling.md" in skill
    assert "初次尝试 + 2 次有意义的重试" not in skill
    assert "### 失败决策表" not in skill


def test_failure_decision_table_covers_every_public_error_category() -> None:
    failure_handling = FAILURE_HANDLING_PATH.read_text(encoding="utf-8")
    categories = {
        "ambiguous",
        "validation_error",
        NO_RESULT,
        NOT_SUPPORTED,
        NO_ACCESS,
        NOT_CONFIGURED,
        RATE_LIMITED,
        "cancelled",
        "request_cancelled",
        ERROR,
        *(category.value for category in RequestErrorCategory),
    }

    for category in categories:
        assert f"`{category}`" in failure_handling

    table_rows = [
        line
        for line in failure_handling.splitlines()
        if line.startswith("|") and not line.startswith("|---")
    ]
    assert table_rows[0] == (
        "| 类别与触发条件 | 重试前必须发生的参数/状态变化 | 终止条件 | 用户报告字段 |"
    )
    assert len(table_rows) == 10
    assert all(row.count("|") == 5 for row in table_rows)


def test_failure_handling_defines_probe_chunking_concurrency_and_rate_limit() -> None:
    text = FAILURE_HANDLING_PATH.read_text(encoding="utf-8")

    for fact in (
        '`batch_check(mode="metadata")`',
        "`probe_state=likely_yes|unknown`",
        "不能报告成已经抓取正文",
        '`batch_check(mode="article")`',
        "执行真实 article fetch",
        "每次 `batch_resolve` / `batch_check` 最多 50 条",
        "原始 1-based `index`",
        "最终按原 index 排序",
        "同一阶段内身份独立的条目",
        "`concurrency=1..8`",
        "不假定默认并发为 3",
        "停止向相同 provider lane 提交新项",
        "不相关 provider lane 可以继续",
    ):
        assert fact in text


def test_failure_handling_forbids_fake_cache_bypass_and_blind_retries() -> None:
    text = FAILURE_HANDLING_PATH.read_text(encoding="utf-8")

    assert "`prefer_cache=false` 本来就是" in text
    assert "再传相同值不是“绕过缓存”" in text
    assert "认证状态未变" in text
    assert "尊重 Retry-After" in text
    assert "只有 browser profile/CDP endpoint" in text
    assert "`provider_status()` 不是 live 健康证明" in text
    assert "不得立即原样重跑" in text


def test_tool_contract_links_to_failure_policy_without_a_second_rule_table() -> None:
    text = TOOL_CONTRACT_PATH.read_text(encoding="utf-8")

    assert "## Batch Probe Contract" in text
    assert '`batch_check(mode="metadata")`' in text
    assert "`likely_yes` 不是已抓取正文或已验证 `has_fulltext`" in text
    assert '`batch_check(mode="article")`' in text
    assert "真实 article fetch" in text
    assert "单次调用最多 50 条" in text
    assert "原始 1-based index" in text
    assert "不假定默认值为 3" in text
    assert "[`failure-handling.md`](failure-handling.md)" in text
    assert "相同 `prefer_cache=false` 请求重跑不得称为绕过缓存" in text
    assert "### 失败决策表" not in text


def test_citation_prompts_preserve_probe_evidence_and_batch_order() -> None:
    for mode in ("metadata", "article"):
        prompt = verify_citation_list_prompt("Citation A\nCitation B", mode=mode)
        assert f'`batch_check(queries, mode="{mode}")`' in prompt
        assert "Metadata mode is a lower-cost likely probe" in prompt
        assert "article mode performs real fetches" in prompt
        assert "original 1-based index" in prompt
        assert "at most 50 queries" in prompt
        assert "sort by that index" in prompt
        assert "dependency order" in prompt
        assert "`concurrency=1..8`" in prompt
        assert "do not assume a default of 3" in prompt
        assert "`likely_yes` is only a readability signal" in prompt
        assert "verified `has_fulltext=true`" in prompt
        assert "a fetch attempt alone is not acceptance" in prompt


def test_prompts_share_the_bounded_meaningful_retry_guardrails() -> None:
    prompts = (
        summarize_paper_prompt("10.1000/example"),
        verify_citation_list_prompt("Citation A"),
    )

    for prompt in prompts:
        assert "`references/failure-handling.md`" in prompt
        for category in (
            "ambiguous",
            "validation_error",
            NO_RESULT,
            NOT_SUPPORTED,
            NO_ACCESS,
            NOT_CONFIGURED,
            RATE_LIMITED,
            "cancelled",
            "request_cancelled",
            ERROR,
            *(category.value for category in RequestErrorCategory),
        ):
            assert f"`{category}`" in prompt
        assert "one initial attempt and at most two meaningful agent retries" in prompt
        assert "Do not blindly retry ambiguity, validation errors" in prompt
        assert "retry no-access only after auth state changes" in prompt
        assert "honor Retry-After" in prompt
        assert "same rate-limited provider" in prompt
        assert "retry network or browser transients only after parameters" in prompt
        assert "An unchanged `prefer_cache=false` rerun is not a cache bypass" in prompt


def test_short_server_error_summary_does_not_invite_unchanged_no_access_retry() -> None:
    summaries = dict(ERROR_CONTRACT)

    assert "retry only after auth or entitlement state changes" in summaries[NO_ACCESS]
