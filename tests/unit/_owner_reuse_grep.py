from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern


OWNER_REUSE_EXCEPTION_PREFIX = "# OWNER_REUSE_EXCEPTION:"


@dataclass(frozen=True)
class OwnerReusePattern:
    description: str
    grep_pattern: str
    regex_template: str

    def compile(self, provider: str) -> Pattern[str]:
        pattern = self.regex_template.format(provider=re.escape(provider))
        return re.compile(pattern)


@dataclass(frozen=True)
class OwnerReuseMatch:
    path: Path
    line_number: int
    line: str
    pattern: OwnerReusePattern


OWNER_REUSE_PATTERNS: tuple[OwnerReusePattern, ...] = (
    OwnerReusePattern(
        description="HTTP header lookup（必须走 paper_fetch.http.headers.header_value）",
        grep_pattern="def _header_value|def _response_header",
        regex_template=r"def _header_value|def _response_header",
    ),
    OwnerReusePattern(
        description="Asset retry / merge（必须走 AssetRetryPolicy）",
        grep_pattern="def _merge_X_assets|def _is_retryable_X_asset_failure",
        regex_template=(
            r"def _merge_{provider}_assets"
            r"|def _is_retryable_{provider}_asset_failure"
        ),
    ),
    OwnerReusePattern(
        description="DOI URL 候选（必须走 ProviderSpec 模板）",
        grep_pattern="def _doi_(xml|pdf|landing)_candidate",
        regex_template=r"def _doi_(xml|pdf|landing)_candidate",
    ),
    OwnerReusePattern(
        description=(
            "Markdown table / figure / formula 渲染"
            "（必须走 paper_fetch.extraction.markdown_render）"
        ),
        grep_pattern=r"_render_(table|figure|formula)_markdown\b",
        regex_template=r"_render_(table|figure|formula)_markdown\b",
    ),
    OwnerReusePattern(
        description=(
            "自己写的 access-gate 文案"
            "（必须先登记 ACCESS_GATE_LABELS / ACCESS_GATE_PATTERNS）"
        ),
        grep_pattern=r'"check access"|"purchase this article"|"sign in"',
        regex_template=r'"check access"|"purchase this article"|"sign in"',
    ),
    OwnerReusePattern(
        description="自己写的 reference anchor 判定（必须走 citation_anchors）",
        grep_pattern=r"looks_like_reference|data-test.*reference|role.*doc-biblio",
        regex_template=r"looks_like_reference|data-test.*reference|role.*doc-biblio",
    ),
    OwnerReusePattern(
        description="session cache 自定义 key（必须走 SessionCacheKey）",
        grep_pattern=r"_session_cache_key_X_",
        regex_template=r"_session_cache_key_{provider}_",
    ),
    OwnerReusePattern(
        description="author extraction 自己写 fallback 链（必须走 AuthorExtractionPipeline）",
        grep_pattern=r"def _X_author_(meta|jsonld|dom)_fallback",
        regex_template=r"def _{provider}_author_(meta|jsonld|dom)_fallback",
    ),
    OwnerReusePattern(
        description="BeautifulSoup 死防御（项目已要求 bs4 是硬依赖）",
        grep_pattern=r"BeautifulSoup is None|Tag is None",
        regex_template=r"BeautifulSoup is None|Tag is None",
    ),
    OwnerReusePattern(
        description="raw_payload.metadata 写诊断（必须走 ProviderContent.diagnostics）",
        grep_pattern=r"raw_payload\.metadata\[",
        regex_template=r"raw_payload\.metadata\[",
    ),
)


def has_owner_reuse_exception(line: str) -> bool:
    marker_index = line.find(OWNER_REUSE_EXCEPTION_PREFIX)
    if marker_index < 0:
        return False
    reason = line[marker_index + len(OWNER_REUSE_EXCEPTION_PREFIX) :].strip()
    return bool(reason)


def iter_owner_reuse_matches(
    path: Path,
    provider: str,
    *,
    patterns: tuple[OwnerReusePattern, ...] = OWNER_REUSE_PATTERNS,
) -> tuple[OwnerReuseMatch, ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    compiled_patterns = tuple(
        (pattern, pattern.compile(provider)) for pattern in patterns
    )
    matches: list[OwnerReuseMatch] = []

    for index, line in enumerate(lines):
        previous_line = lines[index - 1] if index else ""
        if has_owner_reuse_exception(line) or has_owner_reuse_exception(previous_line):
            continue

        for pattern, regex in compiled_patterns:
            if regex.search(line):
                matches.append(
                    OwnerReuseMatch(
                        path=path,
                        line_number=index + 1,
                        line=line,
                        pattern=pattern,
                    )
                )

    return tuple(matches)
