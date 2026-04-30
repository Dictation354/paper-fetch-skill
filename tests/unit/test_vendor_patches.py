import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RETURN_IMAGE_PAYLOAD_PATCH = REPO_ROOT / "vendor/flaresolverr/patches/return-image-payload.patch"
HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def _declared_count(value: str | None) -> int:
    return 1 if value is None else int(value)


class VendorPatchTests(unittest.TestCase):
    def test_return_image_payload_patch_hunk_counts_are_valid(self) -> None:
        lines = RETURN_IMAGE_PAYLOAD_PATCH.read_text(encoding="utf-8").splitlines()
        hunk_count = 0
        index = 0

        while index < len(lines):
            header = HUNK_HEADER_RE.match(lines[index])
            if header is None:
                index += 1
                continue

            hunk_count += 1
            old_expected = _declared_count(header.group("old_count"))
            new_expected = _declared_count(header.group("new_count"))
            old_actual = 0
            new_actual = 0
            header_line = index + 1
            index += 1

            while index < len(lines) and not (
                lines[index].startswith("@@ ") or lines[index].startswith("diff --git ")
            ):
                line = lines[index]
                if line.startswith(" "):
                    old_actual += 1
                    new_actual += 1
                elif line.startswith("-"):
                    old_actual += 1
                elif line.startswith("+"):
                    new_actual += 1
                elif line.startswith("\\"):
                    pass
                else:
                    self.fail(f"Unexpected patch hunk line at {index + 1}: {line!r}")
                index += 1

            with self.subTest(header_line=header_line):
                self.assertEqual(old_actual, old_expected)
                self.assertEqual(new_actual, new_expected)

        self.assertGreater(hunk_count, 0)
