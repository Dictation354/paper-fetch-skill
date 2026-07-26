# Markdown Quality Agent Review

You are reviewing the committed Markdown baseline for provider onboarding.

## Inputs

- Provider: `mdpi`
- DOI: `10.3390/rs16010010`
- Sample ID: `10.3390_rs16010010`
- Fixture purpose: `figure`
- Markdown to review: `tests/fixtures/golden_criteria/10.3390_rs16010010/extracted.md`
- Prompt path: `tests/fixtures/golden_criteria/10.3390_rs16010010/markdown-quality-prompt.md`
- Report to write: `tests/fixtures/golden_criteria/10.3390_rs16010010/markdown-quality.json`

## Task

Read the Markdown as a human reviewer. Judge whether it is a usable, provider-neutral semantic baseline for this article fixture. Do not mark the report pass by relying on deterministic regexes, fixture metadata, or the previous quality report. The decision must come from reviewing the Markdown content itself.

## Semantic Risks To Check

- Missing, duplicated, empty, or obviously misplaced title/abstract/body sections.
- Publisher chrome, navigation, cookie text, license boilerplate, or download widgets mixed into article content.
- Broken tables, orphan table rows, malformed formula blocks, or formula text glued to prose.
- Missing figure captions, empty figure/table sections, or media placeholders presented as content.
- Enforce `asset_contract.figures` only when this fixture purpose is listed in the provider manifest `asset_contract.figures.purposes`; for other purposes, remote figure links are not blocking by themselves.
- For figure-contract purposes with `asset_contract.figures.inline: body`, missing body `![Figure ...](...)` images before References/Figures/Supplementary tail sections is blocking; a caption-only `## Figures` appendix is not enough.
- For figure-contract purposes with `asset_contract.figures.download: required`, missing local asset-path rewrites for downloaded figure images is blocking; remote-only image links do not satisfy the asset contract.
- References that are absent when expected from the article, missing recognizable numbering or labels, mostly DOI-only, duplicated, or polluted by unrelated text.
- JavaScript placeholder links, unresolved template text, severe OCR noise, or repeated article fragments.
- Any other semantic corruption that would make `extracted.md` unsafe as a golden Markdown baseline.

## Output JSON Contract

Write JSON to the report path using this schema. Use `status: "pass"` only when there are no blocking issues. Use `status: "fail"` when one or more blocking issues remain, and set `blocking_issue_count` to the number of issues whose `blocking` field is `true`.

```json
{
  "blocking_issue_count": 0,
  "doi": "10.3390/rs16010010",
  "issues": [],
  "markdown_path": "tests/fixtures/golden_criteria/10.3390_rs16010010/extracted.md",
  "prompt_path": "tests/fixtures/golden_criteria/10.3390_rs16010010/markdown-quality-prompt.md",
  "provider": "mdpi",
  "review_method": "agent_prompt",
  "reviewed_at": "<UTC ISO-8601 timestamp>",
  "reviewed_by": "<agent-or-operator-id>",
  "sample_id": "10.3390_rs16010010",
  "schema_version": 2,
  "status": "pass"
}
```

Each issue must include `id`, `severity`, `blocking`, and `summary`; add `evidence` when a short excerpt or location helps. `reviewed_by` and `reviewed_at` are required for both `pass` and `fail` reports.
