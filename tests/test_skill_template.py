from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "render_skill_template.py"
SPEC = importlib.util.spec_from_file_location("render_skill_template", MODULE_PATH)
render_skill_template = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = render_skill_template
SPEC.loader.exec_module(render_skill_template)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "skill_template.md"


class SkillTemplateTests(unittest.TestCase):
    def test_shared_skill_template_covers_current_contract(self) -> None:
        rendered = render_skill_template.render_skill_template(
            TEMPLATE_PATH.read_text(encoding="utf-8"),
            render_skill_template.build_context(
                Path("/tmp/repo"),
                Path("/tmp/skill"),
                Path("/tmp/venv"),
            ),
        )

        self.assertIn("## Examples", rendered)
        self.assertIn("## When NOT to Use", rendered)
        self.assertIn("## stderr JSON Schema", rendered)
        self.assertIn("--output-dir <dir>", rendered)
        self.assertIn("--no-download", rendered)
        self.assertIn("Avoid firing many parallel requests", rendered)
        self.assertIn("not thread-safe", rendered)
        self.assertIn("If this repo is moved, re-run the installer", rendered)
        self.assertNotIn("fetch_article.py", rendered)
        self.assertNotIn("${", rendered)

    def test_build_context_supplies_all_template_variables(self) -> None:
        import re

        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        referenced = set(re.findall(r"\$\{([A-Z_]+)\}", template_text))
        provided = set(
            render_skill_template.build_context(
                Path("/tmp/repo"),
                Path("/tmp/skill"),
                Path("/tmp/venv"),
            ).keys()
        )
        missing = referenced - provided
        self.assertFalse(
            missing,
            f"render_skill_template.build_context is missing variables referenced by the template: {sorted(missing)}",
        )
