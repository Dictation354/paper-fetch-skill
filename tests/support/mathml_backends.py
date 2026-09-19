"""Select already installed real formula tools without network or installation."""

import os
from pathlib import Path

import pytest

from tests._environment import PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR


def installed_formula_env(backend: str) -> dict[str, str]:
    root = os.environ.get(PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR, "")
    if not root or not Path(root).is_dir():
        pytest.skip("requires the existing local formula-tools bundle")
    return {
        "PAPER_FETCH_FORMULA_TOOLS_DIR": root,
        "MATHML_CONVERTER_BACKEND": backend,
        "PATH": os.environ.get("PATH", ""),
        "MATHML_TO_LATEX_WORKER": "false",
    }
