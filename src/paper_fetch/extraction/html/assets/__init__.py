"""Canonical provider-neutral HTML asset extraction and download API."""

from __future__ import annotations

from . import (
    _kind as _kind,
)
from . import (
    dom as _dom,
)
from . import (
    download as download,
)
from . import (
    figures as _figures,
)
from . import (
    formulas as _formulas,
)
from . import (
    identity as _identity,
)
from . import (
    supplementary as _supplementary,
)
from ._kind import (
    FIGURE_KIND as FIGURE_KIND,
)
from ._kind import (
    SUPPLEMENTARY_KIND as SUPPLEMENTARY_KIND,
)
from ._kind import (
    AssetDownloadKind as AssetDownloadKind,
)
from .dom import (
    FULL_SIZE_IMAGE_ATTRS as FULL_SIZE_IMAGE_ATTRS,
)
from .dom import (
    PREVIEW_IMAGE_ATTRS as PREVIEW_IMAGE_ATTRS,
)
from .dom import (
    _soup_attr_url as _soup_attr_url,
)
from .dom import (
    looks_like_full_size_asset_url as looks_like_full_size_asset_url,
)
from .dom import (
    supplementary_response_block_reason as supplementary_response_block_reason,
)
from .download import (
    AssetDownloadOptions as AssetDownloadOptions,
)
from .download import (
    AssetFetchPolicy as AssetFetchPolicy,
)
from .download import (
    browser_asset_recovery_allowed as browser_asset_recovery_allowed,
)
from .figures import (
    FigurePageFetcher as FigurePageFetcher,
)
from .figures import (
    clean_noisy_image_alt_text as clean_noisy_image_alt_text,
)
from .figures import (
    extract_figure_assets as extract_figure_assets,
)
from .figures import (
    extract_full_size_figure_image_url as extract_full_size_figure_image_url,
)
from .formulas import extract_formula_assets as extract_formula_assets
from .identity import (
    filter_assets_for_profile as filter_assets_for_profile,
)
from .identity import (
    html_asset_identity_key as html_asset_identity_key,
)
from .identity import (
    html_asset_is_supplementary as html_asset_is_supplementary,
)
from .identity import (
    merge_extracted_and_downloaded_assets as merge_extracted_and_downloaded_assets,
)
from .identity import (
    split_body_and_supplementary_assets as split_body_and_supplementary_assets,
)
from .supplementary import (
    GENERIC_SUPPLEMENTARY_FILE_SUFFIXES as GENERIC_SUPPLEMENTARY_FILE_SUFFIXES,
)
from .supplementary import (
    GENERIC_SUPPLEMENTARY_TEXT_TOKENS as GENERIC_SUPPLEMENTARY_TEXT_TOKENS,
)
from .supplementary import (
    extract_html_assets as extract_html_assets,
)
from .supplementary import (
    extract_scoped_html_assets as extract_scoped_html_assets,
)
from .supplementary import (
    extract_supplementary_assets as extract_supplementary_assets,
)
from .supplementary import (
    has_supplementary_file_suffix as has_supplementary_file_suffix,
)
from .supplementary import (
    supplementary_file_suffixes as supplementary_file_suffixes,
)
from .supplementary import (
    supplementary_text_tokens_for_profile as supplementary_text_tokens_for_profile,
)

_PUBLIC_MODULES = (
    _dom,
    _figures,
    _formulas,
    _supplementary,
    _identity,
    _kind,
    download,
)

for _module in _PUBLIC_MODULES:
    globals().update({name: getattr(_module, name) for name in _module.__all__})

download_assets = download.download_assets


__all__ = list(
    dict.fromkeys(
        [
            *(name for module in _PUBLIC_MODULES for name in module.__all__),
            "download_assets",
        ]
    )
)
