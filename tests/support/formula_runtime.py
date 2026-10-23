"""Use the already prepared local formula tools for real captured replays."""

import os
from pathlib import Path
import shutil

from tests._environment import PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR
from tests.paths import REPO_ROOT


def captured_formula_environment():
    root = Path(
        os.environ.get(PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR)
        or REPO_ROOT / ".formula-tools"
    )
    texmath = root / "bin" / ("texmath.exe" if os.name == "nt" else "texmath")
    return {
        "PAPER_FETCH_FORMULA_TOOLS_DIR": str(root),
        "MATHML_TO_LATEX_NODE_BIN": shutil.which("node") or "node",
        "TEXMATH_BIN": str(texmath)
        if texmath.exists()
        else shutil.which("texmath") or "texmath",
    }
