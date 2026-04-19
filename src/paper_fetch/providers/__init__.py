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
from .pnas import PnasClient
from .science import ScienceClient
from .springer import (
    SpringerClient,
)
from .wiley import WileyClient

__all__ = [
    "CrossrefClient",
    "ElsevierClient",
    "PnasClient",
    "ScienceClient",
    "SpringerClient",
    "WileyClient",
    "build_elsevier_object_url",
    "download_elsevier_related_assets",
    "elsevier_asset_priority",
    "extract_elsevier_asset_references",
    "first_xml_child_text",
    "infer_elsevier_asset_group_key",
    "xml_local_name",
]
