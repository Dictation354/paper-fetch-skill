"""Publisher-specific provider clients."""

from .crossref import CrossrefClient
from .elsevier import (
    ElsevierClient,
    build_elsevier_object_url,
    download_elsevier_related_assets,
    elsevier_asset_priority,
    extract_elsevier_asset_references,
    first_xml_child_text,
    infer_elsevier_asset_group_key,
    xml_local_name,
)
from .springer import (
    SpringerClient,
    build_springer_static_asset_url,
    download_springer_related_assets,
    extract_springer_asset_references,
)
from .wiley import WileyClient

__all__ = [
    "CrossrefClient",
    "ElsevierClient",
    "SpringerClient",
    "WileyClient",
    "build_elsevier_object_url",
    "build_springer_static_asset_url",
    "download_elsevier_related_assets",
    "download_springer_related_assets",
    "elsevier_asset_priority",
    "extract_elsevier_asset_references",
    "extract_springer_asset_references",
    "first_xml_child_text",
    "infer_elsevier_asset_group_key",
    "xml_local_name",
]
