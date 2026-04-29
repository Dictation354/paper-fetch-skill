from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from paper_fetch_devtools.geography.issue_artifacts import (
    collect_issue_rows,
    materialize_issue_type_view,
    schedule_issue_rows,
)


class GeographyIssueArtifactsTests(unittest.TestCase):
    def test_collect_issue_rows_keeps_only_flagged_rows_and_honors_filter(self) -> None:
        payload = {
            "results": [
                {"provider": "elsevier", "doi": "10.1000/e1", "issue_flags": ["abstract_inflated"]},
                {"provider": "springer", "doi": "10.1000/s1", "issue_flags": []},
                {"provider": "wiley", "doi": "10.1000/w1", "issue_flags": ["refs_doi_not_normalized", "abstract_inflated"]},
            ]
        }

        selected = collect_issue_rows(payload)
        filtered = collect_issue_rows(payload, issue_flags=["refs_doi_not_normalized"])

        self.assertEqual([row["doi"] for row in selected], ["10.1000/e1", "10.1000/w1"])
        self.assertEqual([row["doi"] for row in filtered], ["10.1000/w1"])

    def test_schedule_issue_rows_interleaves_providers_while_preserving_local_order(self) -> None:
        rows = [
            {"provider": "elsevier", "doi": "10.1000/e1", "issue_flags": ["abstract_inflated"]},
            {"provider": "elsevier", "doi": "10.1000/e2", "issue_flags": ["abstract_inflated"]},
            {"provider": "wiley", "doi": "10.1000/w1", "issue_flags": ["refs_doi_not_normalized"]},
            {"provider": "wiley", "doi": "10.1000/w2", "issue_flags": ["refs_doi_not_normalized"]},
            {"provider": "science", "doi": "10.1000/c1", "issue_flags": ["abstract_body_overlap"]},
        ]

        scheduled = schedule_issue_rows(rows, providers=["elsevier", "wiley", "science"])

        self.assertEqual(
            [row["doi"] for row in scheduled],
            ["10.1000/e1", "10.1000/w1", "10.1000/c1", "10.1000/e2", "10.1000/w2"],
        )

    def test_materialize_issue_type_view_creates_symlink_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "10.1000_e1"
            second = root / "10.1000_w1"
            first.mkdir()
            second.mkdir()
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "doi": "10.1000/e1",
                                "issue_flags": ["abstract_inflated"],
                                "output_dir": str(first),
                            },
                            {
                                "doi": "10.1000/w1",
                                "issue_flags": ["abstract_inflated", "refs_doi_not_normalized"],
                                "output_dir": str(second),
                            },
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            summary = materialize_issue_type_view(artifact_root=root)

            self.assertEqual(len(summary["issue_dirs"]), 2)
            inflated_link = root / "abstract_inflated" / "10.1000_e1"
            refs_link = root / "refs_doi_not_normalized" / "10.1000_w1"
            self.assertTrue(inflated_link.is_symlink())
            self.assertTrue(refs_link.is_symlink())
            self.assertEqual(inflated_link.resolve(), first.resolve())
            self.assertEqual(refs_link.resolve(), second.resolve())

    def test_materialize_issue_type_view_removes_stale_issue_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_dir = root / "10.1000_e1"
            export_dir.mkdir()
            stale_issue_dir = root / "abstract_body_overlap"
            stale_issue_dir.mkdir()
            (stale_issue_dir / "10.1000_e1").symlink_to(export_dir.resolve(), target_is_directory=True)
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "doi": "10.1000/e1",
                                "issue_flags": ["abstract_inflated"],
                                "output_dir": str(export_dir),
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            materialize_issue_type_view(artifact_root=root)

            self.assertFalse(stale_issue_dir.exists())
            self.assertTrue((root / "abstract_inflated" / "10.1000_e1").is_symlink())

    def test_materialize_issue_type_view_prefers_empty_current_issue_flags_over_original_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            export_dir = root / "10.1000_e1"
            export_dir.mkdir()
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "doi": "10.1000/e1",
                                "issue_flags": ["abstract_inflated"],
                                "current_issue_flags": [],
                                "output_dir": str(export_dir),
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            summary = materialize_issue_type_view(artifact_root=root)

            self.assertEqual(summary["issue_dirs"], [])
            self.assertFalse((root / "abstract_inflated").exists())


if __name__ == "__main__":
    unittest.main()
