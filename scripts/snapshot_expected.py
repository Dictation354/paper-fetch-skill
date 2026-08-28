#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _structured_errors import ToolError, emit_error, error_payload  # noqa: E402
from paper_fetch_devtools.markdown_quality import (  # noqa: E402
    build_markdown_quality_prompt,
    build_pending_markdown_quality_report,
    write_markdown_quality_prompt,
    write_markdown_quality_report,
)
from paper_fetch.publisher_identity import normalize_doi  # noqa: E402
from paper_fetch.utils import normalize_text  # noqa: E402


class SnapshotArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_error(
            error_payload(
                "EXPECTED_SNAPSHOT_FAILED",
                message,
                provider=None,
                manifest=None,
                task_id="snapshot-expected-parse-args",
                retryable=False,
                details={"reason": message},
            )
        )
        raise SystemExit(2)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def doi_slug(doi: str) -> str:
    return normalize_doi(doi).replace("/", "_")


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"samples": {}}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"manifest root must be an object: {path}")
    samples = manifest.setdefault("samples", {})
    if not isinstance(samples, dict):
        raise ValueError(f"manifest samples must be an object: {path}")
    return manifest


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def _sample_for_doi(
    manifest: dict[str, Any], doi: str
) -> tuple[str, dict[str, Any]] | None:
    slug = doi_slug(doi)
    samples = manifest.get("samples", {})
    if slug in samples and isinstance(samples[slug], dict):
        return slug, samples[slug]
    for sample_id, sample in samples.items():
        if (
            isinstance(sample, dict)
            and normalize_doi(str(sample.get("doi") or "")) == doi
        ):
            return str(sample_id), sample
    return None


def _fixture_root(root: Path, sample_id: str, sample: dict[str, Any]) -> Path:
    family = str(sample.get("fixture_family") or "golden")
    if family == "block":
        assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
        for value in assets.values():
            path = root / str(value)
            if "tests/fixtures/block/" in path.as_posix():
                return path.parent
        return root / "tests" / "fixtures" / "block" / sample_id.removesuffix("__block")
    return root / "tests" / "fixtures" / "golden_criteria" / sample_id


def _raw_fixture_path(root: Path, sample_id: str, sample: dict[str, Any]) -> Path:
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    for name in (
        "original.html",
        "original.xml",
        "original.pdf",
        "raw.html",
        "article.html",
        "extracted.md",
    ):
        value = assets.get(name)
        if value:
            return root / str(value)
    fixture_root = _fixture_root(root, sample_id, sample)
    for name in (
        "original.html",
        "original.xml",
        "original.pdf",
        "raw.html",
        "article.html",
        "extracted.md",
    ):
        path = fixture_root / name
        if path.exists():
            return path
    raise FileNotFoundError(
        f"fixture is missing replay source or extracted.md: {sample_id}"
    )


def _meta_values(soup: BeautifulSoup, *names: str) -> list[str]:
    wanted = {name.lower() for name in names}
    values: list[str] = []
    for node in soup.find_all("meta"):
        key = str(node.get("name") or node.get("property") or "").lower()
        if key in wanted:
            value = normalize_text(str(node.get("content") or ""))
            if value:
                values.append(value)
    return values


def _text_from_selector(soup: BeautifulSoup, selector: str) -> str:
    node = soup.select_one(selector)
    return normalize_text(node.get_text(" ", strip=True)) if node else ""


def _review_summary_from_html(raw_path: Path, sample: dict[str, Any]) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(
            raw_path.read_text(encoding="utf-8", errors="ignore"), "html.parser"
        )
    title = (
        (_meta_values(soup, "citation_title", "dc.title", "og:title") or [""])[0]
        or _text_from_selector(soup, "h1")
        or _text_from_selector(soup, "title")
        or str(sample.get("title") or "")
    )
    authors = _meta_values(soup, "citation_author", "dc.creator")
    abstract = (
        (
            _meta_values(soup, "citation_abstract", "dc.description", "description")
            or [""]
        )[0]
        or _text_from_selector(soup, ".abstract")
        or _text_from_selector(soup, "[class*=abstract]")
    )
    headings = [
        normalize_text(node.get_text(" ", strip=True))
        for node in soup.find_all(re.compile(r"^h[1-6]$"))
        if normalize_text(node.get_text(" ", strip=True))
    ]
    formula_count = len(soup.find_all("math")) + len(
        soup.select("[class*=formula], [class*=math], .equation")
    )
    return {
        "title": normalize_text(title),
        "authors": authors,
        "abstract_length": len(normalize_text(abstract)),
        "section_headings": headings,
        "table_count": len(soup.find_all("table")),
        "figure_count": len(soup.find_all("figure")),
        "formula_count": formula_count,
    }


def _review_summary_from_pdf(raw_path: Path, sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": normalize_text(str(sample.get("title") or "")),
        "authors": [],
        "abstract_length": 0,
        "section_headings": [],
        "table_count": 0,
        "figure_count": 0,
        "formula_count": 0,
    }


def _review_summary_from_markdown(
    raw_path: Path, sample: dict[str, Any]
) -> dict[str, Any]:
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    headings = [
        normalize_text(match.group(1))
        for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, flags=re.MULTILINE)
        if normalize_text(match.group(1))
    ]
    abstract_match = re.search(
        r"^#{1,6}\s+Abstract\b(?P<body>.*?)(?:^#{1,6}\s+|\Z)",
        text,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    return {
        "title": normalize_text(str(sample.get("title") or "")),
        "authors": [],
        "abstract_length": len(normalize_text(abstract_match.group("body")))
        if abstract_match
        else 0,
        "section_headings": headings,
        "table_count": len(re.findall(r"^\s*\|.+\|\s*$", text, flags=re.MULTILINE)),
        "figure_count": len(re.findall(r"!\[[^\]]*\]\(", text)),
        "formula_count": text.count("$$") // 2,
    }


def _availability(sample: dict[str, Any], summary: dict[str, Any]) -> str:
    purpose = str(sample.get("purpose") or "")
    family = str(sample.get("fixture_family") or "golden")
    if purpose in {"access-gate", "empty-shell"}:
        return "blocked"
    if purpose == "abstract-only":
        return "abstract-only"
    if family == "block":
        return "blocked"
    if (
        summary["section_headings"]
        or summary["table_count"]
        or summary["figure_count"]
        or summary["formula_count"]
    ):
        return "fulltext"
    if summary["abstract_length"]:
        return "abstract-only"
    return "blocked"


def _expected_content_kind(availability: str) -> str:
    if availability == "fulltext":
        return "fulltext"
    if availability == "abstract-only":
        return "abstract_only"
    return "metadata_only"


def _expected_from_review_summary(summary: dict[str, Any]) -> dict[str, Any]:
    availability = str(summary["availability"])
    body = availability == "fulltext"
    abstract = bool(summary["abstract_length"]) or availability == "abstract-only"
    return {
        "has": {
            "title": bool(summary["title"]),
            "authors": bool(summary["authors"]),
            "abstract": abstract,
            "body": body,
            "figures": summary["figure_count"] > 0,
            "references": False,
            "data_availability": False,
            "code_availability": False,
        },
        "counts": {
            "sections": len(summary["section_headings"]),
            "abstract_sections": 1 if abstract else 0,
            "body_sections": len(summary["section_headings"]) if body else 0,
            "figures": summary["figure_count"],
            "tables": summary["table_count"],
            "references": 0,
        },
        "expected_content_kind": _expected_content_kind(availability),
    }


def _expected_from_golden_corpus(
    doi: str, sample_id: str, sample: dict[str, Any], root: Path
) -> dict[str, Any] | None:
    article = _article_from_golden_corpus(sample_id, sample, root)
    if article is None:
        return None
    try:
        from tests.golden_corpus import expected_summary_from_article
    except Exception:
        return None
    expected = expected_summary_from_article(article)
    expected["expected_content_kind"] = str(expected.get("expected_content_kind") or "")
    return expected


def _article_from_golden_corpus(
    sample_id: str, sample: dict[str, Any], root: Path
) -> Any | None:
    if (
        root != _repo_root().resolve()
        or str(sample.get("fixture_family") or "golden") != "golden"
    ):
        return None
    assets = sample.get("assets") if isinstance(sample.get("assets"), dict) else {}
    if not any(
        name in assets
        for name in ("original.html", "original.xml", "original.pdf", "article.html")
    ):
        return None
    repo_root = str(root)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from tests.golden_corpus import (
            GoldenCorpusFixture,
            build_article_from_fixture,
        )
    except Exception:
        return None
    return build_article_from_fixture(
        GoldenCorpusFixture(sample_id=sample_id, sample=dict(sample))
    )


def _fallback_markdown(review_summary: dict[str, Any]) -> str:
    lines = [
        f"# {review_summary.get('title') or review_summary.get('doi') or 'Untitled'}",
        "",
    ]
    if review_summary.get("abstract_length"):
        lines.extend(
            ["## Abstract", "", "Abstract text is present in the replay fixture.", ""]
        )
    for heading in review_summary.get("section_headings") or []:
        lines.extend(
            [f"## {heading}", "", "Section text is present in the replay fixture.", ""]
        )
    if review_summary.get("figure_count"):
        lines.extend(
            [
                "## Figures",
                "",
                "- Figure captions are present in the replay fixture.",
                "",
            ]
        )
    if review_summary.get("table_count"):
        lines.extend(
            [
                "## Tables",
                "",
                "| Column | Value |",
                "| --- | --- |",
                "| fixture | present |",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _markdown_from_article_or_summary(
    *,
    sample_id: str,
    sample: dict[str, Any],
    root: Path,
    review_summary: dict[str, Any],
) -> tuple[str, bool]:
    article = _article_from_golden_corpus(sample_id, sample, root)
    if article is None:
        existing_path = _fixture_root(root, sample_id, sample) / "extracted.md"
        if existing_path.is_file():
            return existing_path.read_text(encoding="utf-8", errors="replace"), False
        return _fallback_markdown(review_summary), False
    markdown = article.to_ai_markdown(
        include_refs="all",
        asset_profile="body",
        max_tokens="full_text",
    )
    return markdown, bool(getattr(article, "references", None))


def _build_review_summary(
    root: Path, doi: str, sample_id: str, sample: dict[str, Any]
) -> dict[str, Any]:
    raw_path = _raw_fixture_path(root, sample_id, sample)
    if raw_path.suffix.lower() == ".pdf":
        summary = _review_summary_from_pdf(raw_path, sample)
    elif raw_path.suffix.lower() == ".md":
        summary = _review_summary_from_markdown(raw_path, sample)
    else:
        summary = _review_summary_from_html(raw_path, sample)
    availability = _availability(sample, summary)
    summary.update(
        {
            "doi": doi,
            "availability": availability,
            "asset_failures": [],
            "source_trail": [
                f"fixture:{sample.get('fixture_family') or 'golden'}",
                f"route:{sample.get('route_kind') or raw_path.suffix.lstrip('.')}",
            ],
        }
    )
    return summary


def _manifest_outcome(expected: dict[str, Any], review_summary: dict[str, Any]) -> str:
    if expected.get("expected_content_kind") == "fulltext":
        return "fulltext"
    if expected.get("expected_content_kind") == "abstract_only":
        return "abstract-only"
    if review_summary["availability"] in {"blocked", "abstract-only"}:
        return str(review_summary["availability"])
    return "blocked"


def _infer_route_metadata(raw_path: Path, sample: dict[str, Any]) -> tuple[str, str]:
    provider = str(sample.get("publisher") or "")
    suffix = raw_path.suffix.lower()
    if suffix == ".pdf":
        return "pdf_fallback", "application/pdf"
    if suffix == ".xml":
        route = "official" if provider == "elsevier" else "xml"
        return route, "text/xml"
    if suffix in {".html", ".htm"}:
        return "html", "text/html"
    if suffix == ".md":
        return str(sample.get("route_kind") or "extracted"), "text/markdown"
    return str(sample.get("route_kind") or "unknown"), str(
        sample.get("content_type") or "application/octet-stream"
    )


def snapshot_expected(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    root = Path(args.output_dir).resolve()
    doi = normalize_doi(args.doi)
    manifest_path = root / "tests" / "fixtures" / "golden_criteria" / "manifest.json"
    manifest = _load_manifest(manifest_path)
    match = _sample_for_doi(manifest, doi)
    if match is None:
        if args.review:
            return (
                {
                    "doi": doi,
                    "available": False,
                    "error": "fixture sample is not registered in manifest",
                    "summary": None,
                },
                False,
            )
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            "Fixture sample is not registered in manifest.",
            retryable=False,
            manifest=manifest_path.as_posix(),
            task_id=f"{doi_slug(doi)}-step6-snapshot-expected",
            details={"doi": doi, "manifest": manifest_path.as_posix()},
        )

    sample_id, sample = match
    try:
        review_summary = _build_review_summary(root, doi, sample_id, sample)
    except FileNotFoundError as exc:
        raise ToolError(
            "FIXTURE_NOT_FOUND",
            str(exc),
            provider=str(sample.get("publisher") or "") or None,
            manifest=manifest_path.as_posix(),
            task_id=f"{sample_id}-step6-snapshot-expected",
            retryable=False,
            details={"doi": doi, "sample_id": sample_id},
        ) from exc
    except Exception as exc:
        raise ToolError(
            "EXPECTED_SNAPSHOT_FAILED",
            str(exc),
            provider=str(sample.get("publisher") or "") or None,
            manifest=manifest_path.as_posix(),
            task_id=f"{sample_id}-step6-snapshot-expected",
            retryable=False,
            details={"doi": doi, "sample_id": sample_id},
        ) from exc
    expected = _expected_from_golden_corpus(
        doi, sample_id, sample, root
    ) or _expected_from_review_summary(review_summary)
    markdown, _ = _markdown_from_article_or_summary(
        sample_id=sample_id,
        sample=sample,
        root=root,
        review_summary=review_summary,
    )
    fixture_root = _fixture_root(root, sample_id, sample)
    markdown_rel_path = (fixture_root / "extracted.md").relative_to(root).as_posix()
    prompt_rel_path = (
        (fixture_root / "markdown-quality-prompt.md").relative_to(root).as_posix()
    )
    quality_rel_path = (
        (fixture_root / "markdown-quality.json").relative_to(root).as_posix()
    )
    prompt = build_markdown_quality_prompt(
        provider=str(sample.get("publisher") or ""),
        doi=doi,
        sample_id=sample_id,
        purpose=str(sample.get("purpose") or ""),
        markdown_path=markdown_rel_path,
        prompt_path=prompt_rel_path,
        report_path=quality_rel_path,
    )
    quality = build_pending_markdown_quality_report(
        provider=str(sample.get("publisher") or ""),
        doi=doi,
        sample_id=sample_id,
        markdown_path=markdown_rel_path,
        prompt_path=prompt_rel_path,
    )
    review_summary["availability"] = _manifest_outcome(expected, review_summary)
    if args.review:
        return {
            "expected": expected,
            "review": review_summary,
            "markdown_quality_prompt": prompt,
            "markdown_quality_report": quality,
        }, False

    raw_path = _raw_fixture_path(root, sample_id, sample)
    if not sample.get("route_kind") or not sample.get("content_type"):
        route_kind, content_type = _infer_route_metadata(raw_path, sample)
        sample.setdefault("route_kind", route_kind)
        sample.setdefault("content_type", content_type)

    expected_path = fixture_root / "expected.json"
    markdown_path = expected_path.with_name("extracted.md")
    prompt_path = expected_path.with_name("markdown-quality-prompt.md")
    quality_path = expected_path.with_name("markdown-quality.json")
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    write_markdown_quality_prompt(prompt_path, prompt)
    write_markdown_quality_report(quality_path, quality)
    sample["expected_outcome"] = _manifest_outcome(expected, review_summary)
    assets = sample.setdefault("assets", {})
    if isinstance(assets, dict):
        assets["expected.json"] = expected_path.relative_to(root).as_posix()
        assets["extracted.md"] = markdown_path.relative_to(root).as_posix()
        assets["markdown-quality-prompt.md"] = prompt_path.relative_to(root).as_posix()
        assets["markdown-quality.json"] = quality_path.relative_to(root).as_posix()
    _write_manifest(manifest_path, manifest)
    return expected, True


def build_parser() -> argparse.ArgumentParser:
    parser = SnapshotArgumentParser(
        description="Generate expected.json from a local replay fixture."
    )
    parser.add_argument(
        "--doi", required=True, help="DOI to snapshot, for example 10.1234/sample"
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="print the generated summary without writing",
    )
    parser.add_argument(
        "--output-dir",
        default=_repo_root(),
        help="repo root to read/write; defaults to this checkout",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary, _ = snapshot_expected(args)
    except ToolError as exc:
        emit_error(
            error_payload(
                exc.code,
                exc.message,
                provider=exc.provider,
                manifest=exc.manifest,
                task_id=exc.task_id,
                retryable=exc.retryable,
                details=exc.details,
            )
        )
        return 1
    except Exception as exc:
        emit_error(
            error_payload(
                "EXPECTED_SNAPSHOT_FAILED",
                str(exc),
                provider=None,
                manifest=None,
                task_id="snapshot-expected",
                retryable=False,
                details={"reason": str(exc)},
            )
        )
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
