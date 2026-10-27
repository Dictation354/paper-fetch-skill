"""Small deterministic supplementary task fixtures shared across test layers."""

from paper_fetch.acquisition import AcquisitionProvenance
from paper_fetch.models import FetchEnvelope, Metadata, SupplementaryResult
from paper_fetch.tracing import trace_event

DOI = "10.1371/journal.pone.0000001"
URL = f"https://journals.plos.org/plosone/article?id={DOI}"
XML_URL = f"https://journals.plos.org/plosone/article/file?id={DOI}&type=manuscript"
META = {"doi": DOI, "title": "Attachment contract", "landing_page_url": URL}


def html_page(
    doi=DOI,
    links='<section id="supplementary"><a href="/support.csv">Supplementary data</a></section>',
):
    return f'<html><head><meta name="citation_doi" content="{doi}"><meta name="citation_title" content="Attachment contract"></head><body><p>Purchase access to the full text</p><a href="/paper.pdf">Download PDF</a><a href="https://repository.example/dataset">Data availability</a>{links}</body></html>'


def envelope(assets=None, *, failures=None, complete=True):
    return FetchEnvelope(
        doi=DOI,
        source="plos",
        target="supplementary",
        has_fulltext=False,
        metadata=Metadata(title="Attachment contract"),
        markdown="",
        supplementary=SupplementaryResult(
            assets=assets or [],
            asset_failures=failures or [],
            discovery_complete=complete,
            identity_verified=True,
            source_urls=[URL],
        ),
        acquisition=AcquisitionProvenance(
            provider="plos",
            route="supplementary",
            representation="html",
            transport="http",
        ),
        trace=[trace_event("supplementary", "plos", "success")],
    )
