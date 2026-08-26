from __future__ import annotations

import unittest

from tests.block_fixtures import execute_block_fixture, iter_block_samples


class BlockCorpusTests(unittest.TestCase):
    def test_block_raw_responses_match_current_extractor_rejection_contract(
        self,
    ) -> None:
        for fixture in iter_block_samples():
            result = execute_block_fixture(fixture)

            with self.subTest(
                provider=fixture.provider,
                doi=fixture.doi,
                route=fixture.provider_route,
                content_kind=result.content_kind,
            ):
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, fixture.expected_reason)
                self.assertEqual(result.failure_code, fixture.expected_failure_code)
                self.assertEqual(result.content_kind, fixture.expected_content_kind)
                self.assertEqual(result.provider_route, fixture.provider_route)
                self.assertEqual(result.source_identity, fixture.source_identity)
                self.assertNotEqual(result.content_kind, "fulltext")


if __name__ == "__main__":
    unittest.main()
