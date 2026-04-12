"""CLI entrypoint for paper-fetch."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from dataclasses import replace
from pathlib import Path

from .config import build_runtime_env, resolve_cli_download_dir
from .models import ArticleModel, FetchEnvelope, RenderOptions
from .providers.base import ProviderFailure
from .service import FetchStrategy, PaperFetchFailure, fetch_paper
from .utils import extend_unique, sanitize_filename

ASSET_LINK_PLACEHOLDER_PREFIX = "paper-fetch-asset://"


def _relative_asset_link(value: str | None, *, target_path: Path) -> str | None:
    original = str(value or "").strip()
    if not original or original.startswith(("http://", "https://", "//")):
        return None
    source_path = Path(original)
    if not source_path.is_absolute():
        return None
    relative = Path(os.path.relpath(source_path, start=target_path.parent))
    return urllib.parse.quote(relative.as_posix(), safe="/._-")


def _article_with_placeholder_asset_links(article: ArticleModel, *, target_path: Path) -> tuple[ArticleModel, dict[str, str]]:
    replacements: dict[str, str] = {}
    rewritten_assets = []
    placeholder_index = 0
    for asset in article.assets:
        placeholder_asset = asset
        relative_path = _relative_asset_link(asset.path, target_path=target_path)
        rewrite_field = "path"
        if relative_path is None:
            relative_path = _relative_asset_link(asset.url, target_path=target_path)
            rewrite_field = "url"
        if relative_path is not None:
            placeholder = f"{ASSET_LINK_PLACEHOLDER_PREFIX}{placeholder_index}"
            placeholder_index += 1
            replacements[placeholder] = relative_path
            placeholder_asset = replace(asset, **{rewrite_field: placeholder})
        rewritten_assets.append(placeholder_asset)
    return replace(article, assets=rewritten_assets), replacements


def rewrite_markdown_asset_links(
    markdown: str,
    envelope: FetchEnvelope,
    *,
    target_path: Path,
    render: RenderOptions,
) -> str:
    if not markdown or envelope.article is None:
        return markdown

    article_with_placeholders, replacements = _article_with_placeholder_asset_links(envelope.article, target_path=target_path)
    if not replacements:
        return markdown

    rewritten = article_with_placeholders.to_ai_markdown(
        include_refs=render.include_refs,
        asset_profile=render.asset_profile or "none",
        max_tokens=render.max_tokens,
    )
    for placeholder, relative_path in replacements.items():
        rewritten = rewritten.replace(placeholder, relative_path)
    return rewritten


def save_markdown_to_disk(envelope: FetchEnvelope, *, output_dir: Path, render: RenderOptions) -> None:
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
    target.write_text(
        rewrite_markdown_asset_links(envelope.markdown or "", envelope, target_path=target, render=render),
        encoding="utf-8",
    )
    extend_unique(envelope.warnings, [f"Markdown full text was saved to {target}."])
    extend_unique(envelope.source_trail, ["download:markdown_saved"])
    if envelope.article is not None:
        extend_unique(envelope.article.quality.warnings, [f"Markdown full text was saved to {target}."])
        extend_unique(envelope.article.quality.source_trail, ["download:markdown_saved"])


def serialize_envelope(envelope: FetchEnvelope, *, output_format: str, markdown_override: str | None = None) -> str:
    if output_format == "markdown":
        return markdown_override if markdown_override is not None else envelope.markdown or ""
    if output_format == "json":
        if envelope.article is None:
            raise ValueError("CLI json output requires the article payload.")
        return envelope.article.to_json()
    if envelope.article is None:
        raise ValueError("CLI both output requires the article payload.")
    markdown = markdown_override if markdown_override is not None else envelope.markdown
    return json.dumps({"article": envelope.article.to_dict(), "markdown": markdown}, ensure_ascii=False, indent=2)


def write_output(serialized: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(serialized)
        if not serialized.endswith("\n"):
            sys.stdout.write("\n")
        return
    Path(output).write_text(serialized, encoding="utf-8")


def parse_max_tokens(value: str) -> int | str:
    normalized = value.strip().lower()
    if normalized == "full_text":
        return "full_text"
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("max_tokens must be a positive integer or 'full_text'.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("max_tokens must be greater than 0.")
    return parsed


def _compute_modes(args: argparse.Namespace) -> set[str]:
    modes = {"markdown"} if args.format == "markdown" else {"article"}

    # Writing Markdown to a file or saving an extra Markdown copy needs the
    # structured article payload so we can rewrite local asset links relative
    # to the target path and decide whether full text was actually usable.
    if args.format == "markdown" and args.output != "-":
        modes.add("article")
    if args.format == "both" or args.save_markdown:
        modes.add("markdown")
    if args.save_markdown:
        modes.add("article")
    return modes


def exit_code_for_error(error: Exception) -> int:
    if isinstance(error, PaperFetchFailure):
        status = error.status
    elif isinstance(error, ProviderFailure):
        status = error.code
    else:
        status = "error"

    if status == "ambiguous":
        return 2
    if status == "no_access":
        return 3
    if status == "rate_limited":
        return 4
    return 1


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
    parser.add_argument("--include-refs", choices=("none", "top10", "all"), default=None)
    parser.add_argument("--asset-profile", choices=("none", "body", "all"), default="none")
    parser.add_argument("--max-tokens", type=parse_max_tokens, default="full_text")
    parser.add_argument("--no-html-fallback", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        runtime_env = build_runtime_env()
        output_dir = Path(args.output_dir) if args.output_dir else resolve_cli_download_dir(runtime_env)
        modes = _compute_modes(args)
        render_options = RenderOptions(
            include_refs=args.include_refs,
            asset_profile=args.asset_profile,
            max_tokens=args.max_tokens,
        )
        envelope = fetch_paper(
            args.query,
            modes=modes,
            strategy=FetchStrategy(
                allow_html_fallback=not args.no_html_fallback,
                allow_metadata_only_fallback=True,
                asset_profile=args.asset_profile,
            ),
            render=render_options,
            download_dir=None if args.no_download else output_dir,
            env=runtime_env,
        )
        if args.save_markdown:
            save_markdown_to_disk(envelope, output_dir=output_dir, render=render_options)
        markdown_override = (
            rewrite_markdown_asset_links(
                envelope.markdown or "",
                envelope,
                target_path=Path(args.output),
                render=render_options,
            )
            if args.output != "-" and args.format in {"markdown", "both"}
            else None
        )
        serialized = serialize_envelope(envelope, output_format=args.format, markdown_override=markdown_override)
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
        return exit_code_for_error(exc)
    except ProviderFailure as exc:
        sys.stderr.write(json.dumps({"status": exc.code, "reason": exc.message}, ensure_ascii=False) + "\n")
        return exit_code_for_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
