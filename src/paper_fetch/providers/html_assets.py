"""Compatibility facade over provider-neutral HTML asset helpers."""

from __future__ import annotations

from ..extraction.html import _assets as _asset_impl

FULL_SIZE_IMAGE_ATTRS = _asset_impl.FULL_SIZE_IMAGE_ATTRS
FULL_SIZE_URL_TOKENS = _asset_impl.FULL_SIZE_URL_TOKENS
PREVIEW_IMAGE_ATTRS = _asset_impl.PREVIEW_IMAGE_ATTRS
PREVIEW_URL_TOKENS = _asset_impl.PREVIEW_URL_TOKENS

_build_cookie_seeded_opener = _asset_impl._build_cookie_seeded_opener
_request_with_opener = _asset_impl._request_with_opener

extract_figure_assets = _asset_impl.extract_figure_assets
extract_formula_assets = _asset_impl.extract_formula_assets
extract_full_size_figure_image_url = _asset_impl.extract_full_size_figure_image_url
extract_html_assets = _asset_impl.extract_html_assets
extract_supplementary_assets = _asset_impl.extract_supplementary_assets
figure_download_candidates = _asset_impl.figure_download_candidates
html_asset_identity_key = _asset_impl.html_asset_identity_key
looks_like_full_size_asset_url = _asset_impl.looks_like_full_size_asset_url
resolve_figure_download_url = _asset_impl.resolve_figure_download_url


def download_figure_assets(*args, **kwargs):
    kwargs.setdefault("cookie_opener_builder", _build_cookie_seeded_opener)
    kwargs.setdefault("opener_requester", _request_with_opener)
    return _asset_impl.download_figure_assets(*args, **kwargs)


download_figure_assets_with_image_document_fetcher = _asset_impl.download_figure_assets_with_image_document_fetcher
