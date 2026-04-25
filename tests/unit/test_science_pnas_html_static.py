from __future__ import annotations

import ast
import unittest

from tests.paths import SRC_DIR


SCIENCE_PNAS_HTML = SRC_DIR / "paper_fetch" / "providers" / "_science_pnas_html.py"
EXPECTED_COMPATIBILITY_SYMBOLS = {
    "SciencePnasHtmlFailure",
    "assess_html_fulltext_availability",
    "assess_plain_text_fulltext_availability",
    "assess_structured_article_fulltext_availability",
    "availability_failure_message",
    "body_metrics",
    "build_html_candidates",
    "build_pdf_candidates",
    "clean_markdown",
    "detect_html_block",
    "extract_article_markdown",
    "extract_browser_workflow_markdown",
    "extract_pdf_url_from_crossref",
    "extract_science_pnas_markdown",
    "has_sufficient_article_body",
    "looks_like_abstract_redirect",
    "preferred_html_candidate_from_landing_page",
    "rewrite_inline_figure_links",
    "summarize_html",
}


def _top_level_defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


class SciencePnasHtmlStaticTests(unittest.TestCase):
    def test_browser_html_module_no_longer_defines_duplicate_availability_or_site_rules(self) -> None:
        tree = ast.parse(SCIENCE_PNAS_HTML.read_text(encoding="utf-8"))
        class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assigned_names: set[str] = set()
        function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned_names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assigned_names.add(node.target.id)

        self.assertNotIn("StructuredBodyAnalysis", class_names)
        self.assertNotIn("FulltextAvailabilityDiagnostics", class_names)
        self.assertFalse(
            {
                "SITE_RULE_OVERRIDES",
                "PUBLISHER_HOSTS",
                "PDF_URL_TOKENS",
                "DEFAULT_SITE_RULE",
                "HTML_FULLTEXT_MARKERS",
            }
            & assigned_names
        )
        self.assertFalse(
            {
                "_analyze_html_structure",
                "_analyze_markdown_structure",
                "_structure_accepts_fulltext",
                "_dom_access_hints",
                "_publisher_base_urls",
            }
            & function_names
        )

    def test_browser_html_compatibility_surface_is_explicit(self) -> None:
        tree = ast.parse(SCIENCE_PNAS_HTML.read_text(encoding="utf-8"))

        missing_symbols = EXPECTED_COMPATIBILITY_SYMBOLS - _top_level_defined_names(tree)

        self.assertEqual(missing_symbols, set())


if __name__ == "__main__":
    unittest.main()
