#!/usr/bin/env python3
"""Normalize journal titles for deterministic list matching."""

from __future__ import annotations

import argparse
import re
import unicodedata

PUNCT_TRANSLATION = str.maketrans(
    {
        "-": " ",
        "_": " ",
        "/": " ",
        "\\": " ",
        ":": " ",
        ";": " ",
        ",": " ",
        ".": " ",
        "(": " ",
        ")": " ",
        "[": " ",
        "]": " ",
        "{": " ",
        "}": " ",
        "'": " ",
        '"': " ",
        "’": " ",
        "“": " ",
        "”": " ",
    }
)


def normalize_journal_name(value: str | None) -> str:
    """Return a lowercase, punctuation-light journal title."""
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.lower()
    normalized = normalized.replace("&", " and ")
    normalized = normalized.translate(PUNCT_TRANSLATION)
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize a journal title for list matching.",
    )
    parser.add_argument("journal_name", help="Journal title to normalize")
    args = parser.parse_args()
    print(normalize_journal_name(args.journal_name))


if __name__ == "__main__":
    main()
