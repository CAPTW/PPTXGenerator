from __future__ import annotations

from typing import Any

from src.presentation_agent.magic_layer.schemas.common import bbox_valid, is_full_slide_bbox


def normalize_bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4:
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return None
    if isinstance(value, dict) and all(key in value for key in ("x", "y", "w", "h")):
        try:
            return [float(value["x"]), float(value["y"]), float(value["w"]), float(value["h"])]
        except (TypeError, ValueError):
            return None
    return None


def validate_bbox_norm(bbox: Any) -> dict[str, Any]:
    normalized = normalize_bbox(bbox)
    failures: list[str] = []
    if not bbox_valid(normalized):
        failures.append("bbox_norm must be [x, y, w, h] within normalized canvas bounds")
    return {
        "schema": "bbox_norm_validation.v1",
        "pass": not failures,
        "bbox_norm": normalized,
        "full_slide": is_full_slide_bbox(normalized),
        "failures": failures,
    }


def bbox_norm_to_slide(
    bbox: Any,
    slide_width_in: float = 13.333,
    slide_height_in: float = 7.5,
) -> dict[str, Any]:
    normalized = normalize_bbox(bbox)
    validation = validate_bbox_norm(normalized)
    if not validation["pass"]:
        return {"pass": False, "bbox_norm": normalized, "failures": validation["failures"]}
    x, y, w, h = normalized or [0.0, 0.0, 0.0, 0.0]
    return {
        "pass": True,
        "bbox_norm": normalized,
        "x_in": x * slide_width_in,
        "y_in": y * slide_height_in,
        "width_in": w * slide_width_in,
        "height_in": h * slide_height_in,
        "coordinate_space": "slide_inches",
        "geometry_source": "bbox_norm",
    }


def object_bbox(item: dict[str, Any]) -> list[float] | None:
    geometry = item.get("geometry")
    if isinstance(geometry, dict) and "bbox_norm" in geometry:
        return normalize_bbox(geometry.get("bbox_norm"))
    return normalize_bbox(item.get("bbox_norm"))
