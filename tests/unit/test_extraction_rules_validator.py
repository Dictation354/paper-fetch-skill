from __future__ import annotations

from pathlib import Path
from unittest import mock
import unittest

from scripts import validate_extraction_rules as validator


class ExtractionRulesValidatorUnitTests(unittest.TestCase):
    def test_non_generic_shared_rules_are_checked_against_provider_lists(self) -> None:
        markdown = """
## Models

<a id="rule-model-shared"></a>
### Model shared rule

- Owner：`paper_fetch.models.ArticleModel`。
## Science

- 共享规则另见：
  - [Other rule](#rule-other)
"""
        manifest = {
            "tests": [
                {
                    "test": "tests/unit/test_science_models.py::test_science_model_rule",
                    "anchors": ["rule-model-shared"],
                    "samples": ["sample"],
                }
            ]
        }
        with mock.patch.object(
            Path, "read_text", return_value=__import__("json").dumps(manifest)
        ):
            errors = validator.validate_provider_shared_applicability(markdown)

        self.assertEqual(
            errors,
            [
                "shared rule #rule-model-shared at line 4 has Science owner/tests "
                "but Science shared-rule list does not include it"
            ],
        )

    def test_rules_declaring_no_stable_doi_sample_must_be_in_summary_table(
        self,
    ) -> None:
        markdown = """
### 无稳定 DOI 样本规则汇总表

| 规则 | 当前证据状态 | 后续补样本触发 | 下一步候选 fixture |
| --- | --- | --- | --- |

## Generic

<a id="rule-needs-sample"></a>
### Needs sample

- Owner：`paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试。
"""

        errors = validator.validate_unstable_sample_summary(markdown)

        self.assertEqual(
            errors,
            [
                "rule #rule-needs-sample at line 9 declares no stable DOI sample but is missing "
                "from the low-stability summary table"
            ],
        )

    def test_rules_declaring_no_stable_doi_sample_pass_when_summary_lists_anchor(
        self,
    ) -> None:
        markdown = """
### 无稳定 DOI 样本规则汇总表

| 规则 | 当前证据状态 | 后续补样本触发 | 下一步候选 fixture |
| --- | --- | --- | --- |
| [Needs sample](#rule-needs-sample) | 无 DOI 级 replay。 | 新 fixture。 | 候选。 |

## Generic

<a id="rule-needs-sample"></a>
### Needs sample

- Owner：`paper_fetch.models.ArticleModel`。
- 代表性 HTML / XML：
  - 当前无稳定 DOI 样本，直接见对应测试。
"""

        self.assertEqual(validator.validate_unstable_sample_summary(markdown), [])

    def test_owner_validation_rejects_unrecognized_backtick_tokens(self) -> None:
        markdown = """
## Generic

<a id="rule-owner"></a>
### Owner rule

- Owner：`paper_fetch.models.ArticleModel` 与 `not/a/dotted/path`。
"""

        errors = validator.validate_rule_owners(markdown)

        self.assertEqual(
            errors,
            [
                "rule #rule-owner at line 4 has invalid Owner `not/a/dotted/path`: "
                "not a dotted import path",
            ],
        )

    def test_nature_names_are_explicitly_inferred_as_springer_shared_rules(
        self,
    ) -> None:
        self.assertEqual(
            validator._infer_providers("test_old_nature_fixture"), {"Springer"}
        )

        markdown = """
## Generic

<a id="rule-nature-shared"></a>
### Nature shared rule

- Owner：`paper_fetch.models.ArticleModel`。
## Springer

- 共享规则另见：
  - [Nature shared rule](#rule-nature-shared)
"""
        manifest = {
            "tests": [
                {
                    "test": "tests/unit/test_springer.py::test_old_nature_fixture",
                    "anchors": ["rule-nature-shared"],
                    "samples": ["sample"],
                }
            ]
        }
        with mock.patch.object(
            Path, "read_text", return_value=__import__("json").dumps(manifest)
        ):
            errors = validator.validate_provider_shared_applicability(markdown)

        self.assertEqual(errors, [])

    def test_provider_rule_registry_contains_required_provider_rules(self) -> None:
        self.assertEqual(validator.validate_provider_rule_registry(), [])

    def test_provider_rule_registry_reports_stale_noise_profiles(self) -> None:
        with mock.patch(
            "paper_fetch.extraction.html.provider_rules.REGISTERED_NOISE_PROFILES",
            frozenset({"generic", "stale_profile"}),
        ):
            errors = validator.validate_provider_rule_registry()

        self.assertIn(
            "REGISTERED_NOISE_PROFILES stale/missing profile(s): annualreviews, ieee, iop, mdpi, oxfordacademic, pnas, springer_nature",
            errors,
        )
        self.assertIn(
            "REGISTERED_NOISE_PROFILES stale/extra profile(s): stale_profile",
            errors,
        )

    def test_provider_rule_registry_reports_missing_required_rule_field(self) -> None:
        with mock.patch.dict(
            validator.PROVIDER_RULE_REQUIREMENTS,
            {"science": {"cleanup.markdown_promo_tokens"}},
            clear=True,
        ):
            errors = validator.validate_provider_rule_registry()

        self.assertEqual(
            errors,
            [
                "provider HTML rules registry provider `science` is missing required "
                "`cleanup.markdown_promo_tokens`"
            ],
        )

    def test_mdpi_provider_section_requires_shared_rule_list(self) -> None:
        markdown = """
## MDPI

<a id="rule-mdpi"></a>
### MDPI rule

- Owner：`paper_fetch.providers._mdpi_html`。
"""

        with mock.patch.object(validator, "PROVIDER_SECTIONS", ("MDPI",)):
            errors = validator.validate_provider_shared_lists(markdown, {"rule-mdpi"})

        self.assertEqual(
            errors,
            ["provider section MDPI is missing shared-rule list"],
        )

    def test_mdpi_provider_rule_registry_reports_missing_required_rule_field(
        self,
    ) -> None:
        with mock.patch.dict(
            validator.PROVIDER_RULE_REQUIREMENTS,
            {"mdpi": {"cleanup.access_block_text_tokens"}},
            clear=True,
        ):
            errors = validator.validate_provider_rule_registry()

        self.assertEqual(
            errors,
            [
                "provider HTML rules registry provider `mdpi` is missing required "
                "`cleanup.access_block_text_tokens`"
            ],
        )

    def test_site_ui_copy_constants_require_regression_marker(self) -> None:
        files = {
            validator.SRC_ROOT / "paper_fetch/providers/demo.py": (
                "DEMO_MARKDOWN_PROMO_TOKENS = ('subscribe now',)\n"
            )
        }

        def fake_read_text(path, encoding="utf-8"):
            del encoding
            return files[path]

        with (
            mock.patch.object(Path, "rglob", return_value=list(files)),
            mock.patch.object(Path, "read_text", fake_read_text),
        ):
            errors = validator.validate_site_ui_copy_markers()

        self.assertEqual(
            errors,
            [
                "src/paper_fetch/providers/demo.py:1 "
                "`DEMO_MARKDOWN_PROMO_TOKENS` is missing SITE_UI_COPY_REGRESSION_MARKER"
            ],
        )

    def test_site_ui_copy_marker_allows_provider_copy_constant(self) -> None:
        files = {
            validator.SRC_ROOT / "paper_fetch/providers/demo.py": (
                "# SITE_UI_COPY_REGRESSION_MARKER: provider UI copy.\n"
                "# STRUCTURAL_UI_COPY_HOOK: provider structure-only cleanup.\n"
                "DEMO_CHROME_TEXTS = ('save article',)\n"
                "COMMON_MARKDOWN_PROMO_TOKENS = ('learn more',)\n"
            )
        }

        def fake_read_text(path, encoding="utf-8"):
            del encoding
            return files[path]

        with (
            mock.patch.object(Path, "rglob", return_value=list(files)),
            mock.patch.object(Path, "read_text", fake_read_text),
        ):
            self.assertEqual(validator.validate_site_ui_copy_markers(), [])

    def test_site_ui_copy_marker_requires_policy_or_structural_owner(self) -> None:
        files = {
            validator.SRC_ROOT / "paper_fetch/providers/demo.py": (
                "# SITE_UI_COPY_REGRESSION_MARKER: provider UI copy.\n"
                "DEMO_CHROME_TEXTS = ('save article',)\n"
            )
        }

        def fake_read_text(path, encoding="utf-8"):
            del encoding
            return files[path]

        with (
            mock.patch.object(Path, "rglob", return_value=list(files)),
            mock.patch.object(Path, "read_text", fake_read_text),
        ):
            errors = validator.validate_site_ui_copy_markers()

        self.assertEqual(
            errors,
            [
                "src/paper_fetch/providers/demo.py:2 "
                "`DEMO_CHROME_TEXTS` is missing CleanupPolicy or "
                "STRUCTURAL_UI_COPY_HOOK ownership"
            ],
        )

    def test_site_ui_copy_marker_requires_owner_for_chrome_selector_constants(
        self,
    ) -> None:
        files = {
            validator.SRC_ROOT / "paper_fetch/providers/demo.py": (
                "# SITE_UI_COPY_REGRESSION_MARKER: provider chrome selectors.\n"
                "DEMO_CHROME_SELECTORS = ('.toolbar',)\n"
            )
        }

        def fake_read_text(path, encoding="utf-8"):
            del encoding
            return files[path]

        with (
            mock.patch.object(Path, "rglob", return_value=list(files)),
            mock.patch.object(Path, "read_text", fake_read_text),
        ):
            errors = validator.validate_site_ui_copy_markers()

        self.assertEqual(
            errors,
            [
                "src/paper_fetch/providers/demo.py:2 "
                "`DEMO_CHROME_SELECTORS` is missing CleanupPolicy or "
                "STRUCTURAL_UI_COPY_HOOK ownership"
            ],
        )

    def test_site_ui_copy_marker_allows_provider_rules_policy_owner(self) -> None:
        files = {
            validator.SRC_ROOT / "paper_fetch/extraction/html/provider_rules.py": (
                "# SITE_UI_COPY_REGRESSION_MARKER: provider UI copy.\n"
                "DEMO_MARKDOWN_PROMO_TOKENS = ('subscribe now',)\n"
            )
        }

        def fake_read_text(path, encoding="utf-8"):
            del encoding
            return files[path]

        with (
            mock.patch.object(Path, "rglob", return_value=list(files)),
            mock.patch.object(Path, "read_text", fake_read_text),
        ):
            self.assertEqual(validator.validate_site_ui_copy_markers(), [])


if __name__ == "__main__":
    unittest.main()
