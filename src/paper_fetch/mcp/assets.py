"""Directed image acquisition for an existing, instance-owned content handle."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Any

from mcp.types import ImageContent

from ..targeted_assets import fetch_selected_assets
from .cache_index import read_scoped_file
from .content_store import ContentStore
from .results import _tool_result, error_payload_from_exception
from .schemas import (
    FetchAssetsRequest,
    InlineImageBudgetInput,
    DEFAULT_INLINE_IMAGE_MAX_IMAGES,
    DEFAULT_INLINE_IMAGE_MAX_BYTES_PER_IMAGE,
    DEFAULT_INLINE_IMAGE_MAX_TOTAL_BYTES,
)


def inline_asset_images(
    payload: dict[str, Any], budget: InlineImageBudgetInput | None = None
) -> list[ImageContent]:
    limits = (budget or InlineImageBudgetInput()).resolved()
    # Directed fetch keeps the existing response ceiling even with a larger budget.
    max_images = min(limits.max_images, DEFAULT_INLINE_IMAGE_MAX_IMAGES)
    max_each = min(limits.max_bytes_per_image, DEFAULT_INLINE_IMAGE_MAX_BYTES_PER_IMAGE)
    max_total = min(limits.max_total_bytes, DEFAULT_INLINE_IMAGE_MAX_TOTAL_BYTES)
    contents: list[ImageContent] = []
    total = 0
    for result in payload["results"]:
        result["inline"] = False
        if result["status"] != "ok":
            result["inline_reason"] = "download_failed"
            continue
        path = Path(result["path"])
        mime = mimetypes.guess_type(path.name)[0] or ""
        if not mime.startswith("image/"):
            result["inline_reason"] = "unsupported_image_type"
            continue
        if len(contents) >= max_images:
            result["inline_reason"] = "image_count_limit"
            continue
        opened = read_scoped_file(
            path.parent,
            str(path),
            max_bytes=min(max_each, max_total - total),
            expected_size=result.get("downloaded_bytes"),
        )
        if opened is None:
            result["inline_reason"] = "byte_limit_or_unreadable"
            continue
        _, body = opened
        total += len(body)
        contents.append(
            ImageContent(
                type="image",
                data=base64.b64encode(body).decode("ascii"),
                mime_type=mime,
            )
        )
        result["inline"] = True
        result["inline_reason"] = None
    payload["image_delivery"] = {
        "discovery_complete": payload["discovery_complete"],
        "formula_images": sum(
            result.get("kind") == "formula" for result in payload["results"]
        ),
        "local_images": sum(result["status"] == "ok" for result in payload["results"]),
        "returned_images": len(contents),
    }
    return contents


async def fetch_assets_tool(store: ContentStore, **arguments: Any):
    try:
        request = FetchAssetsRequest.model_validate(arguments)
        state = store.get_asset_context(request.content_id)
        if state is None:
            return _tool_result(
                store._error(
                    "content_handle_expired",
                    "Content handle is expired, evicted, unknown, or has no paper context.",
                ),
                is_error=True,
            )
        payload = await asyncio.to_thread(
            fetch_selected_assets,
            state,
            asset_ids=request.asset_ids,
            urls=request.urls,
            kind=request.kind,
            output_dir=request.output_dir,
            overwrite=request.overwrite,
        )
        payload["content_id"] = request.content_id
        images = inline_asset_images(payload, request.inline_image_budget)
        return _tool_result(
            payload, is_error=payload["status"] == "error", extra_content=images
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)
