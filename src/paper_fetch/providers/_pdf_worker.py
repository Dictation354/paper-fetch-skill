"""Isolated converter entry point; JSON result is written outside stdout/stderr."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    # Importing the converter and its dependencies may write to either stream.
    from ._pdf_common import (
        PdfFetchFailure,
        _render_default_pdf_markdown_in_process,
        _render_transparent_pdf_markdown_in_process,
    )

    mode, source, images, destination = sys.argv[1:]
    try:
        text = (
            _render_transparent_pdf_markdown_in_process(Path(source))
            if mode == "transparent"
            else _render_default_pdf_markdown_in_process(
                Path(source), image_dir=Path(images) if images else None
            )
        )
        result = {"markdown": text}
    except Exception as error:
        result = {
            "error": str(error),
            "kind": error.kind
            if isinstance(error, PdfFetchFailure)
            else "pdf_conversion_failed",
        }
    Path(destination).write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
