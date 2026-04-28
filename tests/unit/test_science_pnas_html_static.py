from __future__ import annotations

import ast
import unittest

from tests.paths import SRC_DIR


SCIENCE_PNAS_HTML = SRC_DIR / "paper_fetch" / "providers" / "_science_pnas_html.py"
PROVIDER_RULE_MODULES = (
    SRC_DIR / "paper_fetch" / "providers" / "_science_html.py",
    SRC_DIR / "paper_fetch" / "providers" / "_pnas_html.py",
    SRC_DIR / "paper_fetch" / "providers" / "_wiley_html.py",
)
EXPECTED_EXTRACTION_ENTRYPOINTS = {
    "extract_browser_workflow_markdown",
    "extract_science_pnas_markdown",
    "rewrite_inline_figure_links",
}
FORBIDDEN_DEAD_COMPATIBILITY_WRAPPERS = {
    "SciencePnasHtmlFailure",
    "assess_html_fulltext_availability",
    "assess_plain_text_fulltext_availability",
    "assess_structured_article_fulltext_availability",
    "availability_failure_message",
    "build_html_candidates",
    "build_pdf_candidates",
    "detect_html_block",
    "detect_html_hard_negative_signals",
    "extract_pdf_url_from_crossref",
    "looks_like_abstract_redirect",
    "preferred_html_candidate_from_landing_page",
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
                "score_container",
                "select_best_container",
                "should_drop_node",
                "clean_container",
            }
            & function_names
        )

    def test_browser_html_module_keeps_only_real_extraction_entrypoints(self) -> None:
        tree = ast.parse(SCIENCE_PNAS_HTML.read_text(encoding="utf-8"))
        defined_names = _top_level_defined_names(tree)

        missing_symbols = EXPECTED_EXTRACTION_ENTRYPOINTS - defined_names
        forbidden_symbols = FORBIDDEN_DEAD_COMPATIBILITY_WRAPPERS & defined_names

        self.assertEqual(missing_symbols, set())
        self.assertEqual(forbidden_symbols, set())

    def test_browser_html_module_imports_shared_helpers_without_shared_alias_layer(self) -> None:
        tree = ast.parse(SCIENCE_PNAS_HTML.read_text(encoding="utf-8"))
        shared_import_aliases: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                if alias.asname and alias.asname.startswith("_shared_"):
                    module = node.module or ""
                    shared_import_aliases.append(f"{module}:{alias.asname}")

        self.assertEqual(shared_import_aliases, [])

    def test_provider_rule_modules_do_not_define_candidate_or_markdown_delegate_wrappers(self) -> None:
        forbidden = {"build_html_candidates", "build_pdf_candidates", "extract_markdown"}
        offenders: list[str] = []
        for path in PROVIDER_RULE_MODULES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            defined = _top_level_defined_names(tree)
            for name in sorted(forbidden & defined):
                offenders.append(f"{path.name}:{name}")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
