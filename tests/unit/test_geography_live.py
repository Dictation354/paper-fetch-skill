from __future__ import annotations

import unittest

from paper_fetch.geography_live import (
    GeographySample,
    build_report_result,
    has_inflated_abstract,
    has_abstract_body_overlap,
    reference_doi_requires_normalization,
    schedule_geography_samples,
)
from paper_fetch.models import (
    ArticleModel,
    FetchEnvelope,
    Metadata,
    Quality,
    Reference,
    Section,
    TokenEstimateBreakdown,
    build_references,
)


def make_sample(provider: str, doi: str) -> GeographySample:
    return GeographySample(
        provider=provider,
        doi=doi,
        title="Example",
        landing_url=f"https://doi.org/{doi}",
        topic_tags=("climate",),
        year=2024,
        seed_level=1,
    )


def make_envelope(
    *,
    provider: str,
    doi: str,
    source: str,
    metadata: Metadata,
    sections: list[Section],
    references: list[Reference],
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
    breakdown: TokenEstimateBreakdown | None = None,
) -> FetchEnvelope:
    article = ArticleModel(
        doi=doi,
        source=source,
        metadata=metadata,
        sections=sections,
        references=references,
        quality=Quality(
            has_fulltext=bool(sections),
            token_estimate=0,
            token_estimate_breakdown=breakdown or TokenEstimateBreakdown(),
        ),
    )
    return FetchEnvelope(
        doi=doi,
        source=source,
        has_fulltext=article.quality.has_fulltext,
        content_kind=article.quality.content_kind,
        has_abstract=article.quality.has_abstract,
        warnings=list(warnings or []),
        source_trail=list(source_trail or []),
        token_estimate=article.quality.token_estimate,
        token_estimate_breakdown=breakdown or TokenEstimateBreakdown(),
        article=article,
        markdown=None,
        metadata=article.metadata,
    )


class GeographyLiveTests(unittest.TestCase):
    def test_schedule_geography_samples_interleaves_providers_but_preserves_local_order(self) -> None:
        samples = [
            make_sample("elsevier", "10.1000/e1"),
            make_sample("elsevier", "10.1000/e2"),
            make_sample("springer", "10.1000/s1"),
            make_sample("springer", "10.1000/s2"),
            make_sample("wiley", "10.1000/w1"),
        ]

        scheduled = schedule_geography_samples(samples, providers=["elsevier", "springer", "wiley"])

        self.assertEqual(
            [item.doi for item in scheduled],
            ["10.1000/e1", "10.1000/s1", "10.1000/w1", "10.1000/e2", "10.1000/s2"],
        )

    def test_report_result_flags_abstract_inflation_and_overlap(self) -> None:
        repeated_paragraph = (
            "Biophysical effects of forests can strongly impact the land surface through changes in heat, moisture, "
            "and momentum exchange across large regions. This repeated paragraph is intentionally long enough to "
            "trigger the paragraph-level overlap heuristic used by the geography live report."
        )
        envelope = make_envelope(
            provider="pnas",
            doi="10.1073/pnas.example1",
            source="pnas",
            metadata=Metadata(
                title="Example",
                authors=["Author"],
                abstract=(
                    "Short opening abstract paragraph.\n\n"
                    + "\n\n".join([repeated_paragraph] * 14)
                    + "\n\nA third paragraph keeps the abstract unusually long for this synthetic test."
                ),
            ),
            sections=[Section(heading="Results", level=2, kind="body", text=f"{repeated_paragraph} Additional body text.")],
            references=[],
            source_trail=["fulltext:pnas_html_ok", "fulltext:pnas_article_ok"],
            breakdown=TokenEstimateBreakdown(abstract=620, body=400, refs=0),
        )

        result = build_report_result(make_sample("pnas", envelope.doi or ""), envelope, elapsed_seconds=0.5)

        self.assertIn("abstract_inflated", result.issue_flags)
        self.assertIn("abstract_body_overlap", result.issue_flags)

    def test_single_repeated_sentence_does_not_flag_abstract_body_overlap(self) -> None:
        abstract_text = (
            "A repeated sentence from the publisher source appears in the body as-is and should not count alone. "
            "A second sentence adds more context so the abstract still looks normal."
        )
        body_text = (
            "Background context starts here. "
            "A repeated sentence from the publisher source appears in the body as-is and should not count alone. "
            "Additional body text continues with distinct analysis and discussion."
        )

        self.assertFalse(has_abstract_body_overlap(abstract_text, body_text))

    def test_long_but_distinct_abstract_does_not_flag_abstract_inflation(self) -> None:
        abstract_text = (
            "This abstract is legitimately long because it summarizes study design, datasets, methods, results, "
            "and implications in a single structured paragraph without leaking the body. "
            * 18
        ).strip()
        body_text = (
            "The body discusses a different narrative arc focused on methods, validation, uncertainty analysis, "
            "and regional interpretation. " * 20
        ).strip()

        self.assertFalse(
            has_inflated_abstract(
                abstract_text,
                abstract_tokens=520,
                body_text=body_text,
            )
        )

    def test_report_result_uses_primary_wiley_abstract_instead_of_total_bilingual_budget(self) -> None:
        english_abstract = (
            "This primary abstract summarizes the study design, disturbance gradient, satellite observations, "
            "and regional implications without reproducing the body text. "
            * 8
        ).strip()
        portuguese_abstract = (
            "Este resumo paralelo descreve o mesmo estudo em portugues e nao deve inflar a regra de issue "
            "quando o resumo primario continua em tamanho normal. "
            * 8
        ).strip()
        envelope = make_envelope(
            provider="wiley",
            doi="10.1111/gcb.16386",
            source="wiley_browser",
            metadata=Metadata(
                title="Bilingual Wiley Example",
                authors=["Author"],
                abstract=f"{english_abstract}\n\n{portuguese_abstract}",
            ),
            sections=[
                Section(heading="Abstract", level=2, kind="abstract", text=english_abstract),
                Section(heading="Resumo", level=2, kind="abstract", text=portuguese_abstract),
                Section(
                    heading="Main Text",
                    level=2,
                    kind="body",
                    text=("Body paragraphs discuss methods, results, and discussion in a distinct narrative. " * 40).strip(),
                ),
            ],
            references=[],
            source_trail=["fulltext:wiley_html_ok", "fulltext:wiley_article_ok"],
            breakdown=TokenEstimateBreakdown(abstract=980, body=700, refs=0),
        )

        result = build_report_result(make_sample("wiley", envelope.doi or ""), envelope, elapsed_seconds=0.2)

        self.assertNotIn("abstract_inflated", result.issue_flags)
        self.assertNotIn("abstract_body_overlap", result.issue_flags)

    def test_report_result_ignores_pnas_significance_when_canonical_abstract_exists(self) -> None:
        significance = (
            "This significance statement is intentionally long and should not become the primary abstract for "
            "geography issue detection even when metadata.abstract points at it. "
            * 10
        ).strip()
        canonical_abstract = (
            "This canonical abstract focuses on the core finding and remains short enough to stay below the "
            "inflation threshold when evaluated on its own. "
            * 7
        ).strip()
        envelope = make_envelope(
            provider="pnas",
            doi="10.1073/pnas.example-significance",
            source="pnas",
            metadata=Metadata(
                title="PNAS Significance Example",
                authors=["Author"],
                abstract=significance,
            ),
            sections=[
                Section(heading="Significance", level=2, kind="abstract", text=significance),
                Section(heading="Abstract", level=2, kind="abstract", text=canonical_abstract),
                Section(
                    heading="Results",
                    level=2,
                    kind="body",
                    text=("Results paragraphs remain distinct from the abstract and significance blocks. " * 45).strip(),
                ),
            ],
            references=[],
            source_trail=["fulltext:pnas_html_ok", "fulltext:pnas_article_ok"],
            breakdown=TokenEstimateBreakdown(abstract=1040, body=800, refs=0),
        )

        result = build_report_result(make_sample("pnas", envelope.doi or ""), envelope, elapsed_seconds=0.2)

        self.assertNotIn("abstract_inflated", result.issue_flags)
        self.assertNotIn("abstract_body_overlap", result.issue_flags)

    def test_report_result_flags_empty_authors_when_not_briefing_like(self) -> None:
        envelope = make_envelope(
            provider="wiley",
            doi="10.1111/example2",
            source="wiley_browser",
            metadata=Metadata(title="Example", authors=[]),
            sections=[Section(heading="Results", level=2, kind="body", text="Body text.")],
            references=[Reference(raw="ref", doi="10.1038/s41561-022-00912-7")],
            source_trail=["fulltext:wiley_html_ok", "fulltext:wiley_article_ok"],
            breakdown=TokenEstimateBreakdown(abstract=0, body=100, refs=30),
        )

        result = build_report_result(make_sample("wiley", envelope.doi or ""), envelope, elapsed_seconds=0.3)

        self.assertIn("empty_authors", result.issue_flags)
        self.assertNotIn("refs_doi_not_normalized", result.issue_flags)

    def test_report_result_does_not_flag_empty_authors_for_research_briefing_signature(self) -> None:
        envelope = make_envelope(
            provider="springer",
            doi="10.1038/example-briefing",
            source="springer_html",
            metadata=Metadata(title="Example Briefing", authors=[]),
            sections=[
                Section(heading="The question", level=2, kind="body", text="Question text."),
                Section(heading="The discovery", level=2, kind="body", text="Discovery text."),
                Section(heading="The implications", level=2, kind="body", text="Implication text."),
                Section(heading="Expert opinion", level=2, kind="body", text="Opinion text."),
                Section(heading="Behind the paper", level=2, kind="body", text="Behind the paper text."),
                Section(heading="From the editor", level=2, kind="body", text="Editor text."),
            ],
            references=[],
            source_trail=["fulltext:springer_html_ok", "fulltext:springer_article_ok"],
            breakdown=TokenEstimateBreakdown(abstract=0, body=300, refs=0),
        )

        result = build_report_result(make_sample("springer", envelope.doi or ""), envelope, elapsed_seconds=0.2)

        self.assertNotIn("empty_authors", result.issue_flags)

    def test_reference_normalization_removes_unicode_dash_before_issue_flagging(self) -> None:
        references = build_references([{"raw": "ref", "doi": "10.1038/s41561‐022‐00912‐7"}])

        self.assertEqual(references[0].doi, "10.1038/s41561-022-00912-7")
        self.assertFalse(reference_doi_requires_normalization(references[0].doi))

    def test_report_result_classifies_not_configured_even_with_metadata_fallback(self) -> None:
        envelope = make_envelope(
            provider="wiley",
            doi="10.1111/example3",
            source="metadata_only",
            metadata=Metadata(title="Example", authors=["Author"], abstract="Metadata abstract."),
            sections=[],
            references=[],
            warnings=[
                "Wiley browser workflow requires FLARESOLVERR_ENV_FILE pointing at a repo-local vendor/flaresolverr preset.",
                "Full text was not available; returning metadata and abstract only.",
            ],
            source_trail=["fulltext:wiley_not_configured", "fallback:metadata_only"],
            breakdown=TokenEstimateBreakdown(abstract=40, body=0, refs=0),
        )

        result = build_report_result(make_sample("wiley", envelope.doi or ""), envelope, elapsed_seconds=0.2)

        self.assertEqual(result.status, "not_configured")
        self.assertEqual(result.error_code, "not_configured")
        self.assertIn("FLARESOLVERR_ENV_FILE", result.error_message or "")

    def test_report_result_flags_unexpected_source_path_on_fulltext(self) -> None:
        envelope = make_envelope(
            provider="science",
            doi="10.1126/example4",
            source="crossref_meta",
            metadata=Metadata(title="Example", authors=["Author"]),
            sections=[Section(heading="Discussion", level=2, kind="body", text="Body text.")],
            references=[],
            source_trail=["fulltext:science_html_ok", "fulltext:science_article_ok"],
            breakdown=TokenEstimateBreakdown(abstract=0, body=100, refs=0),
        )

        result = build_report_result(make_sample("science", envelope.doi or ""), envelope, elapsed_seconds=0.1)

        self.assertEqual(result.status, "fulltext")
        self.assertIn("unexpected_source_path", result.issue_flags)


if __name__ == "__main__":
    unittest.main()
