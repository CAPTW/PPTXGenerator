"""PowerPoint SVG support inspection for Magic Layer icons."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_svg_powerpoint_support(svg_text: str, *, role_id: str) -> dict[str, Any]:
    lowered = svg_text.lower()
    risks: list[str] = []
    uses_current_color = "currentcolor" in lowered
    has_style_block = "<style" in lowered
    if uses_current_color:
        risks.append("currentColor_may_render_as_default_black_or_invisible")
    if has_style_block:
        risks.append("style_blocks_have_inconsistent_powerpoint_support")
    if "<defs" in lowered or "<use" in lowered or "<symbol" in lowered:
        risks.append("defs_use_symbol_may_not_render_consistently")
    if "<mask" in lowered or "<clippath" in lowered:
        risks.append("mask_clipPath_may_not_render_consistently")
    if "<image" in lowered or "base64" in lowered:
        risks.append("raster_or_embedded_image_not_allowed")
    return {
        "role_id": role_id,
        "uses_current_color": uses_current_color,
        "has_style_block": has_style_block,
        "has_unsupported_svg_tags": any(risk for risk in risks if "support" in risk or "render" in risk),
        "powerpoint_risks": risks,
        "status": "needs_themed_variant" if uses_current_color or has_style_block else "compatible_candidate",
    }


def build_currentcolor_style_support_report(curated_manifest: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for role in curated_manifest.get("roles", []):
        path = Path(role.get("svg_path") or "")
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        rows.append(inspect_svg_powerpoint_support(text, role_id=role["role_id"]))
    return {
        "schema_name": "currentcolor_style_support_report",
        "status": "passed",
        "icon_count": len(rows),
        "currentcolor_icon_count": sum(row["uses_current_color"] for row in rows),
        "style_block_icon_count": sum(row["has_style_block"] for row in rows),
        "powerpoint_risk_icon_count": sum(bool(row["powerpoint_risks"]) for row in rows),
        "rows": rows,
    }
