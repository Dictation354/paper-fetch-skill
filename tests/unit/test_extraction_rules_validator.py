from __future__ import annotations

from pathlib import Path
from unittest import mock
import unittest

from scripts import validate_extraction_rules as validator


class ExtractionRulesValidatorUnitTests(unittest.TestCase):
    def test_docstring_marker_is_required_for_each_documented_rule(self) -> None:
        markdown = """
## Generic

<a id="rule-demo"></a>
### Demo

- 对应测试：
  - [`../tests/unit/test_demo.py`](../tests/unit/test_demo.py) 中的 `test_demo`
"""
        test_defs = {
            "test_demo": [
                validator.TestDefinition(
                    path=validator.REPO_ROOT / "tests/unit/test_demo.py",
                    rule_markers=frozenset(),
                )
            ]
        }

        with mock.patch.object(validator, "_iter_python_tests", return_value=test_defs):
            errors = validator.validate_test_docstring_markers(markdown)

        self.assertIn(
            "rule #rule-demo at line 4 has no documented test with matching docstring marker",
            errors,
        )

    def test_docstring_marker_must_match_documented_anchor(self) -> None:
        markdown = """
## Generic

<a id="rule-demo"></a>
### Demo

- 对应测试：
  - [`../tests/unit/test_demo.py`](../tests/unit/test_demo.py) 中的 `test_demo`
"""
        test_defs = {
            "test_demo": [
                validator.TestDefinition(
                    path=validator.REPO_ROOT / "tests/unit/test_demo.py",
                    rule_markers=frozenset({"rule-other"}),
                )
            ]
        }

        with mock.patch.object(validator, "_iter_python_tests", return_value=test_defs):
            errors = validator.validate_test_docstring_markers(markdown)

        self.assertTrue(
            any("documented test `test_demo` for #rule-demo" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("has no documented test with matching docstring marker" in error for error in errors),
            errors,
        )

    def test_non_generic_shared_rules_are_checked_against_provider_lists(self) -> None:
        markdown = """
## Models

<a id="rule-model-shared"></a>
### Model shared rule

- Owner：`paper_fetch.models.ArticleModel`。
- 对应测试：
  - [`../tests/unit/test_models.py`](../tests/unit/test_models.py) 中的 `test_science_model_rule`

## Science

- 共享规则另见：
  - [Other rule](#rule-other)
"""
        test_defs = {
            "test_science_model_rule": [
                validator.TestDefinition(
                    path=validator.REPO_ROOT / "tests/unit/test_models.py",
                    rule_markers=frozenset({"rule-model-shared"}),
                )
            ]
        }

        with mock.patch.object(validator, "_iter_python_tests", return_value=test_defs):
            errors = validator.validate_provider_shared_applicability(markdown)

        self.assertEqual(
            errors,
            [
                "shared rule #rule-model-shared at line 4 has Science owner/tests "
                "but Science shared-rule list does not include it"
            ],
        )

    def test_manifest_samples_with_assets_must_be_reverse_indexed_or_allowlisted(self) -> None:
        markdown = """
## 未直接挂规则 fixture 清单

<!-- extraction-rules-unlinked-fixtures:start -->
| 范围 | Sample | 用途说明 |
| --- | --- | --- |
<!-- extraction-rules-unlinked-fixtures:end -->
"""
        samples = {
            "10.1000_missing": {
                "assets": {
                    "original.html": "tests/fixtures/golden_criteria/10.1000_missing/original.html"
                }
            }
        }

        with mock.patch.object(validator, "_manifest_samples", return_value=samples):
            errors = validator.validate_manifest_fixture_reverse_index(markdown)

        self.assertEqual(
            errors,
            [
                "manifest sample is not covered by fixture reverse index or unlinked list: "
                "10.1000_missing"
            ],
        )

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

    def test_nature_names_are_explicitly_inferred_as_springer_shared_rules(self) -> None:
        self.assertEqual(validator._infer_providers("test_old_nature_fixture"), {"Springer"})

        markdown = """
## Generic

<a id="rule-nature-shared"></a>
### Nature shared rule

- Owner：`paper_fetch.models.ArticleModel`。
- 对应测试：
  - [`../tests/unit/test_springer.py`](../tests/unit/test_springer.py) 中的 `test_old_nature_fixture`

## Springer

- 共享规则另见：
  - [Nature shared rule](#rule-nature-shared)
"""
        test_defs = {
            "test_old_nature_fixture": [
                validator.TestDefinition(
                    path=Path(validator.REPO_ROOT / "tests/unit/test_springer.py"),
                    rule_markers=frozenset({"rule-nature-shared"}),
                )
            ]
        }

        with mock.patch.object(validator, "_iter_python_tests", return_value=test_defs):
            errors = validator.validate_provider_shared_applicability(markdown)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
