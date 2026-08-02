"""Shared quality and HTML extraction reason-code constants."""

from __future__ import annotations

CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
AWS_WAF_CHALLENGE = "aws_waf_challenge"
PUBLISHER_NOT_FOUND = "publisher_not_found"
PUBLISHER_ACCESS_DENIED = "publisher_access_denied"
PUBLISHER_PAYWALL = "publisher_paywall"
REDIRECTED_TO_ABSTRACT = "redirected_to_abstract"
FULLTEXT = "fulltext"
ABSTRACT_ONLY = "abstract_only"
METADATA_ONLY = "metadata_only"
BODY_SUFFICIENT = "body_sufficient"
INSUFFICIENT_BODY = "insufficient_body"
EMPTY_ARTICLE_SHELL = "empty_article_shell"
NO_ACCESS = "no_access"
STRUCTURED_ARTICLE_NOT_FULLTEXT = "structured_article_not_fulltext"
STRUCTURED_MISSING_BODY_SECTIONS = "structured_missing_body_sections"

ACCESS_PAGE_URL = "access_page_url"
FINAL_URL_MATCHES_CITATION_ABSTRACT_HTML_URL = (
    "final_url_matches_citation_abstract_html_url"
)
DATA_ARTICLE_ACCESS_ABSTRACT = "data_article_access_abstract"
DATA_ARTICLE_ACCESS_NO = "data_article_access_no"
WT_ABSTRACT_PAGE_TYPE = "wt_abstract_page_type"
CITATION_ABSTRACT_HTML_URL = "citation_abstract_html_url"


__all__ = [
    "ABSTRACT_ONLY",
    "ACCESS_PAGE_URL",
    "AWS_WAF_CHALLENGE",
    "BODY_SUFFICIENT",
    "CITATION_ABSTRACT_HTML_URL",
    "CLOUDFLARE_CHALLENGE",
    "DATA_ARTICLE_ACCESS_ABSTRACT",
    "DATA_ARTICLE_ACCESS_NO",
    "EMPTY_ARTICLE_SHELL",
    "FINAL_URL_MATCHES_CITATION_ABSTRACT_HTML_URL",
    "FULLTEXT",
    "INSUFFICIENT_BODY",
    "METADATA_ONLY",
    "NO_ACCESS",
    "PUBLISHER_ACCESS_DENIED",
    "PUBLISHER_NOT_FOUND",
    "PUBLISHER_PAYWALL",
    "REDIRECTED_TO_ABSTRACT",
    "STRUCTURED_ARTICLE_NOT_FULLTEXT",
    "STRUCTURED_MISSING_BODY_SECTIONS",
    "WT_ABSTRACT_PAGE_TYPE",
]
