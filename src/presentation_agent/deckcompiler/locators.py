"""Construct traceable Source Locator records with fail-fast bounds checks."""

from __future__ import annotations

import re
from typing import Any


_SOURCE_ID = re.compile(r"^src_[0-9a-f]{20}$")


def prompt_locator(source_id: str, *, start: int, end: int, quote: str | None = None) -> dict[str, Any]:
    _validate_source_id(source_id)
    _validate_char_range(start, end)
    locator: dict[str, Any] = {
        "source_id": source_id,
        "locator_type": "user_prompt",
        "char_range": {"start": start, "end": end},
    }
    if quote:
        locator["quote"] = quote
    return locator


def pdf_text_locator(
    source_id: str,
    *,
    page_number: int,
    start: int,
    end: int,
    quote: str | None = None,
) -> dict[str, Any]:
    _validate_source_id(source_id)
    if page_number < 1:
        raise ValueError("page_number must be one-based and at least 1")
    _validate_char_range(start, end)
    locator: dict[str, Any] = {
        "source_id": source_id,
        "locator_type": "pdf_text_span",
        "page_number": page_number,
        "char_range": {"start": start, "end": end},
    }
    if quote:
        locator["quote"] = quote
    return locator


def image_region_locator(
    source_id: str,
    *,
    asset_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> dict[str, Any]:
    _validate_source_id(source_id)
    if not asset_id:
        raise ValueError("asset_id is required")
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise ValueError("image region must fit within normalized [0, 1] bounds")
    return {
        "source_id": source_id,
        "locator_type": "image_region",
        "asset_id": asset_id,
        "bbox": {"x": x, "y": y, "width": width, "height": height, "unit": "normalized"},
    }


def _validate_source_id(source_id: str) -> None:
    if _SOURCE_ID.fullmatch(source_id) is None:
        raise ValueError("source_id must match src_<20 lowercase hex characters>")


def _validate_char_range(start: int, end: int) -> None:
    if start < 0 or end <= start:
        raise ValueError("character range must satisfy 0 <= start < end")


__all__ = ["image_region_locator", "pdf_text_locator", "prompt_locator"]
