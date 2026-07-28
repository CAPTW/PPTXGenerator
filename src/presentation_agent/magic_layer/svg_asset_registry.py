"""Build a normalized SVG asset registry for semantic binding."""

from __future__ import annotations

from typing import Any


def build_svg_asset_registry(discovery_report: dict[str, Any]) -> dict[str, Any]:
    assets = [_registry_row(asset) for asset in discovery_report.get("assets", [])]
    by_id = {asset["asset_id"]: asset for asset in assets}
    return {
        "schema_name": "svg_asset_registry",
        "status": "passed" if assets else "failed",
        "asset_count": len(assets),
        "assets": assets,
        "assets_by_id": by_id,
        "canva_parity_claimed": False,
    }


def _registry_row(asset: dict[str, Any]) -> dict[str, Any]:
    tags = sorted(set(asset.get("semantic_keywords", []) + [asset.get("category_guess", ""), asset.get("normalized_name", "")]))
    return {
        "asset_id": asset["asset_id"],
        "source_path": asset["file_path"],
        "filename": asset["filename"],
        "sha256": asset["sha256"],
        "semantic_tags": [tag for tag in tags if tag],
        "compatible_roles": _compatible_roles(asset),
        "canonical_viewbox": asset.get("viewBox") or _derive_viewbox(asset),
        "default_stroke_policy": "recolor_to_currentColor_or_theme_accent",
        "default_fill_policy": "preserve_none_or_recolor_to_theme_accent",
        "monochrome_compatible": True,
        "recolor_supported": True,
        "pptx_direct_svg_supported": True,
        "native_path_conversion_supported": (asset.get("path_count", 0) + asset.get("primitive_count", 0)) > 0,
        "fallback_policy": "forbid_semantic_raster_fallback",
        "path_count": asset.get("path_count", 0),
        "primitive_count": asset.get("primitive_count", 0),
        "color_mode": asset.get("color_mode", "unknown"),
        "category_guess": asset.get("category_guess", "general"),
    }


def _derive_viewbox(asset: dict[str, Any]) -> str:
    width = _as_float(asset.get("width")) or 24
    height = _as_float(asset.get("height")) or 24
    return f"0 0 {width:g} {height:g}"


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace("px", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _compatible_roles(asset: dict[str, Any]) -> list[str]:
    category = asset.get("category_guess", "general")
    roles = {"semantic_icon", "decorative_vector"}
    if category in {"checklist", "safety", "navigation_process"}:
        roles.add("micro_component")
    if category == "dashboard":
        roles.add("dashboard_marker")
    if category == "table_matrix":
        roles.add("table_matrix_marker")
    return sorted(roles)
