"""Identity checks on captured publisher originals, without network or conversion."""

from __future__ import annotations

from urllib.parse import urlsplit
import unicodedata

from bs4 import BeautifulSoup


def inspect_original(body: bytes, provider: str, doi: str, url: str) -> dict | None:
    expected = doi.casefold()
    if body.startswith(b"%PDF"):
        import pymupdf
        from paper_fetch.publisher_identity import extract_doi

        with pymupdf.open(stream=body, filetype="pdf") as document:
            metadata = document.metadata or {}
            metadata_doi = extract_doi(
                "\n".join(
                    str(metadata.get(key) or "")
                    for key in ("title", "subject", "keywords", "author")
                )
            )
            opening = " ".join(
                document[page].get_text() for page in range(min(3, len(document)))
            )
            ids = (
                [metadata_doi]
                if metadata_doi
                else [expected]
                if expected in opening.casefold()
                else []
            )
            return {
                "format": "pdf",
                "identity": (
                    "matched"
                    if expected in {value.casefold() for value in ids}
                    else "mismatch"
                    if ids
                    else "insufficient"
                ),
                "identifiers": ids,
                "doi_evidence": "pdf_metadata" if metadata_doi else "opening_text",
                "pages": len(document),
                "all_pages_readable": all(
                    document.load_page(page).rect.width > 0
                    for page in range(len(document))
                ),
                "title": metadata.get("title") or None,
                "scope": "PDF file and identity only; conversion quality excluded",
            }

    prefix = body[:2000].lower()
    if b"<html" in prefix or b"<!doctype html" in prefix:
        # Browser DOM captures are encoded as UTF-8. Letting the encoding
        # detector guess on a large MathJax page can yield an empty parse.
        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            html = body
        soup = BeautifulSoup(html, "lxml")
        identifiers = []
        titles = []
        for node in soup.select("meta[content]"):
            name = str(node.get("name") or node.get("property") or "").casefold()
            value = str(node.get("content") or "").strip()
            if name in {
                "citation_doi",
                "doi",
                "dc.identifier",
                "dc.identifier.doi",
                "prism.doi",
                "publication_doi",
                "citation_arxiv_id",
            }:
                identifiers.append(value)
            if name in {"citation_title", "dc.title", "og:title"}:
                titles.append(value)
        canonical = [
            str(n.get("href") or "") for n in soup.select('link[rel="canonical"]')
        ]
        matched = any(
            expected
            == value.casefold()
            .removeprefix("doi:")
            .removeprefix("https://doi.org/")
            .strip()
            for value in identifiers
        )
        if provider == "arxiv":
            arxiv_id = expected.split("arxiv.", 1)[-1]
            matched = any(
                arxiv_id == value.casefold().removeprefix("arxiv:")
                for value in identifiers
            )
            matched = matched or any(
                urlsplit(value).hostname in {"arxiv.org", "www.arxiv.org"}
                and urlsplit(value).path.rstrip("/")
                in {f"/html/{arxiv_id}", f"/abs/{arxiv_id}"}
                for value in canonical
            )
            # LaTeXML pages identify their version in the publisher header,
            # without citation metadata or a canonical link.
            matched = matched or (
                urlsplit(url).hostname == "arxiv.org"
                and urlsplit(url).path.rstrip("/") == f"/html/{arxiv_id}"
                and any(
                    node.get("href") == f"/abs/{arxiv_id}"
                    for node in soup.select('a[aria-label="Back to abstract page"]')
                )
            )
            if matched:
                identifiers.append(arxiv_id)
            if not titles:
                title = soup.select_one("h1.ltx_title_document, h1.title")
                if title:
                    titles.append(title.get_text(" ", strip=True))
        if provider == "ieee":
            from paper_fetch.providers._ieee_metadata import _parse_landing_metadata

            metadata = _parse_landing_metadata(body.decode("utf-8", "replace"))
            if metadata.get("doi"):
                identifiers.append(str(metadata["doi"]))
                matched = str(metadata["doi"]).casefold() == expected
                titles.insert(
                    0,
                    str(metadata.get("title") or metadata.get("displayDocTitle") or ""),
                )
        if not matched:
            return None
        return {
            "format": "html",
            "identity": "matched",
            "identifiers": identifiers,
            "canonical": canonical,
            "title": next((x for x in titles if x), None),
        }

    if (
        b"<?xml" in prefix
        or b"<article" in prefix
        or b"<full-text-retrieval-response" in prefix
    ):
        soup = BeautifulSoup(body, "xml")
        identifiers = []
        titles = []
        for meta in soup.find_all(["article-meta", "coredata"]):
            for node in meta.find_all(["article-id", "doi"]):
                if node.name == "doi" or node.get("pub-id-type") == "doi":
                    identifiers.append(node.get_text(strip=True))
            titles.extend(
                n.get_text(" ", strip=True)
                for n in meta.find_all(["article-title", "title"])
            )
        # Elsevier article XML keeps the authoritative DOI in coredata.
        if not identifiers:
            doi_node = soup.find("doi")
            if doi_node and not doi_node.find_parent(
                ["ref", "reference", "bib-reference"]
            ):
                identifiers.append(doi_node.get_text(strip=True))
        if expected not in {value.casefold() for value in identifiers}:
            return None
        return {
            "format": "xml",
            "identity": "matched",
            "identifiers": identifiers,
            "title": next((x for x in titles if x), None),
        }
    return None


def ieee_fragment_identity(
    body: bytes, doi: str, url: str, landing: bytes
) -> dict | None:
    """Bind a DOI-less REST body to metadata from the same document endpoint."""
    from paper_fetch.providers._ieee_metadata import _parse_landing_metadata

    metadata = _parse_landing_metadata(landing.decode("utf-8", "replace"))
    number = str(metadata.get("articleNumber") or "")
    if str(metadata.get("doi") or "").casefold() != doi.casefold() or not number:
        return None
    parsed = urlsplit(url)
    if (
        parsed.hostname != "ieeexplore.ieee.org"
        or parsed.path.rstrip("/") != f"/rest/document/{number}"
    ):
        return None
    soup = BeautifulSoup(body, "lxml")
    if soup.select_one("#BodyWrapper") is None:
        return None
    return {
        "format": "html",
        "identity": "matched",
        "identifiers": [metadata["doi"]],
        "article_number": number,
        "title": metadata.get("title"),
        "binding": "Captured same-document landing DOI plus REST document number",
    }


def pdf_landing_identity(
    body: bytes, provider: str, doi: str, url: str, landing: bytes, landing_url: str
) -> dict | None:
    """Compare identity only; never change PDF bytes or conversion output."""
    import pymupdf

    metadata = inspect_original(landing, provider, doi, landing_url)
    if not metadata or not body.startswith(b"%PDF"):
        return None
    soup = BeautifulSoup(landing.decode("utf-8"), "lxml")
    link = soup.select_one('meta[name="citation_pdf_url"]')
    if not link or link.get("content") != url:
        return None
    title = BeautifulSoup(metadata.get("title") or "", "lxml").get_text()

    def identity_characters(value: str) -> str:
        return "".join(
            ch for ch in unicodedata.normalize("NFKC", value).casefold() if ch.isalnum()
        )

    with pymupdf.open(stream=body, filetype="pdf") as document:
        opening = document[0].get_text()[:1800]
    expected_title = identity_characters(title)
    if len(expected_title) < 30 or expected_title not in identity_characters(opening):
        return None
    identity = inspect_original(body, provider, doi, url)
    assert identity is not None
    return {
        **identity,
        "identity": "matched",
        "title": title,
        "binding": "Captured landing DOI and explicit PDF URL plus first-page title",
        "embedded_doi_found": bool(identity["identifiers"]),
    }


def build_verified_source_article(row: dict):
    """Use the selected original rather than an unverified historical default."""
    from tests.golden_criteria import golden_criteria_sample
    from tests.golden_corpus import build_article_from_fixture
    from tests.paths import REPO_ROOT
    from tests.support.acquired_publisher_inputs import CapturedSourceFixture

    sample = golden_criteria_sample(row["sample_id"])
    sample.update(
        captured_source_path=row["source"],
        source_url=row["source_url"],
        landing_url=row["source_url"],
        title=row["identity"].get("title") or sample.get("title") or row["doi"],
        route_kind=row["format"],
        content_type="text/" + row["format"],
    )
    if row["provider"] != "ieee":
        return build_article_from_fixture(
            CapturedSourceFixture(row["sample_id"], sample)
        )

    from paper_fetch.http import HttpTransport
    from paper_fetch.providers import _ieee_html, _ieee_metadata
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from paper_fetch.providers.ieee import IeeeClient
    from paper_fetch.tracing import trace_from_markers

    landing_path = row.get("identity_companion") or row["source"]
    metadata = _ieee_metadata._parse_landing_metadata(
        (REPO_ROOT / landing_path).read_text()
    )
    assert str(metadata["doi"]).casefold() == row["doi"].casefold()
    body = (REPO_ROOT / row["source"]).read_text()
    extraction = _ieee_html._extract_ieee_html(
        body, row["source_url"], metadata=metadata
    )
    payload = RawFulltextPayload(
        provider="ieee",
        content=ProviderContent(
            route_kind="html",
            source_url=row["source_url"],
            content_type="text/html",
            body=extraction.html_text.encode(),
            markdown_text=extraction.markdown_text,
            merged_metadata=metadata,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                    "marker_counts": extraction.marker_counts,
                }
            },
            extracted_assets=extraction.extracted_assets,
        ),
        trace=trace_from_markers(["fulltext:ieee_html_ok"]),
    )
    return IeeeClient(HttpTransport(), {}).to_article_model(
        {"doi": row["doi"]}, payload
    )
