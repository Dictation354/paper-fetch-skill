from __future__ import annotations

import pickle
import unittest
from dataclasses import FrozenInstanceError

from paper_fetch.quality.html_signals import (
    DatalayerFieldMatch,
    PNAS_SIGNAL_SET,
    SCIENCE_SIGNAL_SET,
    WILEY_SIGNAL_SET,
    evaluate_datalayer_blocking_signals,
    evaluate_datalayer_positive_signals,
)


def _science_datalayer(
    *,
    page_type: str,
    view_type: str,
    user_entitled: str,
    user_access: str,
    article_type: str | None = None,
) -> str:
    article_type_item = (
        f', "articleType": "{article_type}"' if article_type is not None else ""
    )
    return f"""
    <html><script>
    AAASdataLayer = {{
      "page": {{"pageInfo": {{
        "pageType": "{page_type}",
        "viewType": "{view_type}"
        {article_type_item}
      }}}},
      "user": {{"entitled": "{user_entitled}", "access": "{user_access}"}}
    }};
    </script></html>
    """


def _pnas_datalayer(*, access_type: str, free_access: str, user_access: str) -> str:
    return f"""
    <html><script>
    PNASdataLayer = {{
      "page": {{"attributes": {{
        "accessType": "{access_type}",
        "freeAccess": "{free_access}"
      }}}},
      "user": {{"access": "{user_access}"}}
    }};
    </script></html>
    """


def _wiley_datalayer(
    *, item_access: str, format_viewed: str, page_tertiary_section: str
) -> str:
    return f"""
    <html><script>
    window.adobeDataLayer.push({{
      "content": {{"item": {{
        "access": "{item_access}",
        "format-viewed": "{format_viewed}"
      }}}},
      "page": {{"tertiary-section": "{page_tertiary_section}"}}
    }});
    </script></html>
    """


class DatalayerSignalSetTests(unittest.TestCase):
    def test_signal_set_dataclasses_are_frozen_and_round_trip(self) -> None:
        match = DatalayerFieldMatch("user_access", "yes", negate=True)

        with self.assertRaises(FrozenInstanceError):
            match.field = "other"

        self.assertEqual(pickle.loads(pickle.dumps(match)), match)
        self.assertEqual(
            pickle.loads(pickle.dumps(SCIENCE_SIGNAL_SET)),
            SCIENCE_SIGNAL_SET,
        )

    def test_science_blocking_rules_trigger_from_signal_set(self) -> None:
        denial_html = _science_datalayer(
            page_type="journal-article-denial",
            view_type="full",
            user_entitled="true",
            user_access="yes",
        )
        abstract_denied_html = _science_datalayer(
            page_type="journal-article-abstract",
            view_type="abs",
            user_entitled="false",
            user_access="no",
        )

        self.assertEqual(
            evaluate_datalayer_blocking_signals(denial_html, SCIENCE_SIGNAL_SET),
            ["aaas_page_type_denial"],
        )
        self.assertEqual(
            evaluate_datalayer_blocking_signals(
                abstract_denied_html, SCIENCE_SIGNAL_SET
            ),
            [
                "aaas_page_type_abstract",
                "aaas_view_abs",
                "aaas_entitlement_denied",
            ],
        )

    def test_science_positive_rules_trigger_from_signal_set(self) -> None:
        fulltext_html = _science_datalayer(
            page_type="journal-article-full-text",
            view_type="full",
            user_entitled="true",
            user_access="yes",
            article_type="Research Article",
        )
        abstract_html = _science_datalayer(
            page_type="journal-article-abstract",
            view_type="abstract",
            user_entitled="false",
            user_access="no",
        )

        strong, soft, abstract_only = evaluate_datalayer_positive_signals(
            fulltext_html, SCIENCE_SIGNAL_SET
        )

        self.assertEqual(strong, ["aaas_user_entitled", "aaas_user_access_yes"])
        self.assertEqual(
            soft,
            [
                "aaas_page_type_full_text",
                "aaas_view_full",
                "aaas_article_type_present",
            ],
        )
        self.assertEqual(abstract_only, [])
        self.assertEqual(
            evaluate_datalayer_positive_signals(abstract_html, SCIENCE_SIGNAL_SET),
            ([], [], ["aaas_page_type_abstract", "aaas_view_abstract"]),
        )

    def test_pnas_blocking_combo_rule_triggers_from_signal_set(self) -> None:
        html = _pnas_datalayer(
            access_type="paywall",
            free_access="no",
            user_access="no",
        )

        self.assertEqual(
            evaluate_datalayer_blocking_signals(html, PNAS_SIGNAL_SET),
            ["pnas_paywall_no_access"],
        )

    def test_wiley_blocking_rules_trigger_from_signal_set(self) -> None:
        html = _wiley_datalayer(
            item_access="no",
            format_viewed="abstract",
            page_tertiary_section="abs",
        )

        self.assertEqual(
            evaluate_datalayer_blocking_signals(html, WILEY_SIGNAL_SET),
            [
                "wiley_access_no",
                "wiley_format_viewed_abstract",
                "wiley_page_tertiary_abs",
            ],
        )


if __name__ == "__main__":
    unittest.main()
