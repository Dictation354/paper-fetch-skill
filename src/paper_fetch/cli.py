"""CLI entrypoint for paper-fetch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import build_runtime_env, resolve_cli_download_dir
from .models import FetchEnvelope, RenderOptions
from .providers.base import ProviderFailure
from .service import FetchStrategy, PaperFetchFailure, fetch_paper
from .utils import sanitize_filename


def extend_unique(target: list[str], items: list[str] | None) -> None:
    for item in items or []:
        if item and item not in target:
            target.append(item)


def save_markdown_to_disk(envelope: FetchEnvelope, *, output_dir: Path) -> None:
    has_usable_fulltext = bool(envelope.has_fulltext and envelope.markdown and envelope.article and envelope.article.sections)
    if not has_usable_fulltext:
        extend_unique(
            envelope.warnings,
            ["--save-markdown was set but full text was not available; nothing written to disk."],
        )
        extend_unique(envelope.source_trail, ["download:markdown_skipped_no_fulltext"])
        if envelope.article is not None:
            extend_unique(envelope.article.quality.warnings, envelope.warnings)
            extend_unique(envelope.article.quality.source_trail, envelope.source_trail)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    base = sanitize_filename(envelope.doi or envelope.article.metadata.title or "article")
    target = output_dir / f"{base}.md"
    target.write_text(envelope.markdown or "", encoding="utf-8")
    extend_unique(envelope.warnings, [f"Markdown full text was saved to {target}."])
    extend_unique(envelope.source_trail, ["download:markdown_saved"])
    if envelope.article is not None:
        extend_unique(envelope.article.quality.warnings, [f"Markdown full text was saved to {target}."])
        extend_unique(envelope.article.quality.source_trail, ["download:markdown_saved"])


def serialize_envelope(envelope: FetchEnvelope, *, output_format: str) -> str:
    if output_format == "markdown":
        return envelope.markdown or ""
    if output_format == "json":
        if envelope.article is None:
            raise ValueError("CLI json output requires the article payload.")
        return envelope.article.to_json()
    if envelope.article is None:
        raise ValueError("CLI both output requires the article payload.")
    return json.dumps({"article": envelope.article.to_dict(), "markdown": envelope.markdown}, ensure_ascii=False, indent=2)


def write_output(serialized: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(serialized)
        if not serialized.endswith("\n"):
            sys.stdout.write("\n")
        return
    Path(output).write_text(serialized, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch AI-friendly full text for a paper by DOI, URL, or title.")
    parser.add_argument("--query", required=True, help="DOI, paper landing URL, or title query")
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="markdown")
    parser.add_argument("--output", default="-", help="Output destination. Use - for stdout.")
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory for saving raw provider downloads such as Wiley PDFs. "
            "Defaults to PAPER_FETCH_DOWNLOAD_DIR or the user data downloads directory."
        ),
    )
    parser.add_argument("--no-download", action="store_true", help="Do not write provider PDF/binary payloads to disk.")
    parser.add_argument(
        "--save-markdown",
        action="store_true",
        help=(
            "Also write the rendered AI Markdown full text to disk (defaults to PAPER_FETCH_DOWNLOAD_DIR "
            "or the user data downloads directory, "
            "overridable via --output-dir). Only writes when full text was actually retrieved. "
            "For Wiley the Markdown is produced from PDF text extraction and may be lower fidelity "
            "than Elsevier/Springer XML."
        ),
    )
    parser.add_argument("--include-refs", choices=("none", "top10", "all"), default="top10")
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--no-html-fallback", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        runtime_env = build_runtime_env()
        output_dir = Path(args.output_dir) if args.output_dir else resolve_cli_download_dir(runtime_env)
        modes = {"markdown"} if args.format == "markdown" else {"article"}
        if args.format == "both" or args.save_markdown:
            modes.add("markdown")
        if args.save_markdown:
            modes.add("article")
        envelope = fetch_paper(
            args.query,
            modes=modes,
            strategy=FetchStrategy(
                allow_html_fallback=not args.no_html_fallback,
                allow_metadata_only_fallback=True,
            ),
            render=RenderOptions(include_refs=args.include_refs, max_tokens=args.max_tokens),
            download_dir=None if args.no_download else output_dir,
            env=runtime_env,
        )
        if args.save_markdown:
            save_markdown_to_disk(envelope, output_dir=output_dir)
        serialized = serialize_envelope(envelope, output_format=args.format)
        write_output(serialized, args.output)
        return 0
    except PaperFetchFailure as exc:
        sys.stderr.write(
            json.dumps(
                {
                    "status": exc.status,
                    "reason": exc.reason,
                    "candidates": exc.candidates or None,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return 2 if exc.status == "ambiguous" else 1
    except ProviderFailure as exc:
        sys.stderr.write(json.dumps({"status": "error", "reason": exc.message}, ensure_ascii=False) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
