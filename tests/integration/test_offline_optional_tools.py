"""Local conversion evidence; never install tools or access provider sites."""

import os
from pathlib import Path
import shutil

import pytest

from paper_fetch.offline_setup import verify_image


@pytest.mark.parametrize(
    ("tool", "variable", "names"),
    [
        ("ghostscript", "PAPER_FETCH_TEST_GHOSTSCRIPT_BIN", ("gs", "gswin64c.exe")),
        ("libvips", "PAPER_FETCH_TEST_VIPS_BIN", ("vips", "vips.exe")),
    ],
)
def test_optional_image_tool_converts_real_source_to_png(tool, variable, names):
    binary = os.environ.get(variable) or next(
        (found for name in names if (found := shutil.which(name))), None
    )
    if not binary:
        pytest.skip(f"Install {tool} first, or set {variable} to a prepared binary")
    verify_image(tool, Path(binary).absolute(), dict(os.environ))
