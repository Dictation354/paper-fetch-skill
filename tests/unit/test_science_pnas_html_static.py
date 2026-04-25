from __future__ import annotations

import ast
import unittest

from tests.paths import SRC_DIR


SCIENCE_PNAS_HTML = SRC_DIR / "paper_fetch" / "providers" / "_science_pnas_html.py"


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


if __name__ == "__main__":
    unittest.main()
